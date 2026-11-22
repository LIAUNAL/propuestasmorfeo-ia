"""Convocatorias afines al proyecto, para la pestaña «Convocatorias» del tablero.

Existe en los dos flujos y a nivel de espacio de trabajo: la búsqueda precede a
las corridas, así que no hace falta una corrida activa. La vista entera
(perfil, resumen, fuentes consultadas y convocatorias ordenadas con su rol para
Colombia, su cuenta regresiva y su puntaje) sale de `scripts/convocatorias.py`
(`vista(dir)`, esquema `morfeo.convocatorias-vista/v1`), que se carga desde el
kit como los demás scripts. Es de solo lectura: el tablero no escribe nada y
sus botones solo devuelven el prompt de `/propuesta-convocatorias` que se
entrega a la terminal. El alcance (`proyecto` o `banco`) elige el perfil contra
el que se puntúa; solo se pasa al script cuando la petición lo trae. Si el script falta o falla, la pestaña muestra el error
y el tablero nunca se cae.

Avance de la búsqueda: el agente anota el inicio y el fin de cada una de sus
cinco fases con `convocatorias.py progreso`, que escribe
`convocatorias/progreso.json` (esquema `morfeo.convocatorias-progreso/v1`).
`estimate_progress` convierte ese archivo en un porcentaje y un tiempo restante
estimados, de forma determinista y sin escribir nada:

- Duración previa por fase (`PHASE_PRIORS`, en segundos): Perfil 60, Fuentes
  fijas 240, Búsqueda abierta 300, Registro 120 y Verificación 30. Con dos o
  más búsquedas terminadas en `historial`, la previa de una fase es la mediana
  de sus duraciones registradas.
- Ritmo: duración real de las fases terminadas sobre la suma de sus previas
  (1 sin fases terminadas), acotado entre 0,25 y 4.
- Restante: previas de las fases pendientes por el ritmo, más lo que le falta
  a la fase en curso; una fase que supera su estimado conserva un piso del
  15 % de su previa escalada, para que el restante no llegue a cero antes de
  que termine.
- Porcentaje: avance ponderado por las previas (la fase en curso aporta hasta
  el 95 % de la suya), con tope de 99 hasta que la búsqueda termina.
- Terminada (100 %, restante 0): `finished_at` presente, o un
  `oportunidades.json` posterior al inicio de la búsqueda cuando la fase de
  Registro ya terminó o cuando el agente no anotó ninguna fase.
- Detenida (`stale`): sin anotaciones durante `STALE_SECONDS` (20 minutos) y
  sin terminar; el tablero vuelve entonces al mensaje de siempre.
"""

from __future__ import annotations

import datetime
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

from .value_chain import load_kit_script

OPPORTUNITIES_SCRIPT = "convocatorias.py"
OPPORTUNITIES_SCHEMA = "morfeo.convocatorias-vista/v1"
SEARCH_COMMAND = "/propuesta-convocatorias"
_ID_RE = re.compile(r"[a-z0-9-]+")
ALCANCES = ("proyecto", "banco")

PROGRESS_SCHEMA = "morfeo.convocatorias-progreso/v1"
PROGRESS_FILE = Path("convocatorias") / "progreso.json"
CALLS_FILE = Path("convocatorias") / "oportunidades.json"
_CONFIG_MARKERS = (Path(".morfeo") / "config.json", Path(".marco") / "config.json")
PHASE_NAMES = {1: "Perfil", 2: "Fuentes fijas", 3: "Búsqueda abierta", 4: "Registro", 5: "Verificación"}
PHASE_PRIORS = {1: 60, 2: 240, 3: 300, 4: 120, 5: 30}
REGISTER_PHASE = 4
STALE_SECONDS = 20 * 60
HISTORY_MIN_RUNS = 2
PACE_BOUNDS = (0.25, 4.0)
RUNNING_SHARE_CAP = 0.95
OVERRUN_FLOOR = 0.15


def validate_alcance(alcance: Any) -> str | None:
    """None when absent; the scope otherwise. ValueError for anything else."""
    if alcance is None:
        return None
    if not isinstance(alcance, str) or alcance not in ALCANCES:
        raise ValueError("El alcance debe ser «proyecto» o «banco».")
    return alcance


def _call_view(workspace_dir: Path, alcance: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    module = load_kit_script(OPPORTUNITIES_SCRIPT, ("vista",))
    fn = getattr(module, "vista", None) if module is not None else None
    if not callable(fn):
        return None, f"No se encontró scripts/{OPPORTUNITIES_SCRIPT} con la función vista en el kit."
    try:
        # The keyword only travels when asked for, so a script without it keeps working.
        view = fn(workspace_dir, alcance=alcance) if alcance else fn(workspace_dir)
    except SystemExit as err:
        return None, f"{OPPORTUNITIES_SCRIPT} terminó con el código {err.code} al calcular la vista."
    except Exception as err:
        return None, f"{OPPORTUNITIES_SCRIPT} no pudo calcular la vista: {err}"
    if not isinstance(view, dict) or view.get("schema") != OPPORTUNITIES_SCHEMA:
        return None, f"{OPPORTUNITIES_SCRIPT} devolvió una vista que no sigue el esquema {OPPORTUNITIES_SCHEMA}."
    return view, None


def load_opportunities(workspace_dir: Path | str, alcance: Any = None) -> dict[str, Any]:
    """Vista de convocatorias del espacio de trabajo; no escribe.

    Un alcance inválido lanza ValueError (la capa HTTP responde 400); cualquier
    fallo del script vuelve como error en la carga útil.
    """
    view, error = _call_view(Path(workspace_dir), validate_alcance(alcance))
    return {"disponible": view is not None, "vista": view, "error": error}


def build_search_prompt(alcance: Any = None) -> str:
    """Prompt de los botones de búsqueda; ValueError si el alcance no es válido."""
    value = validate_alcance(alcance)
    return f"{SEARCH_COMMAND} buscar --alcance {value}" if value else SEARCH_COMMAND


def build_start_prompt(opportunity_id: Any) -> str:
    """Prompt de «Iniciar propuesta con esta»; ValueError si el id no es un slug."""
    value = opportunity_id if isinstance(opportunity_id, str) else ""
    if not value:
        raise ValueError("Falta el id de la convocatoria.")
    if not _ID_RE.fullmatch(value):
        raise ValueError("El id de la convocatoria debe ser un slug (minúsculas, dígitos y guiones).")
    return f"{SEARCH_COMMAND} iniciar {value}"


# --- Search progress ----------------------------------------------------------

def _instant(value: Any) -> datetime.datetime | None:
    """An aware datetime from an ISO-8601 string (naive means UTC); None otherwise."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)


def _priors(history: Any) -> dict[int, float]:
    """Default priors, each replaced by the median of its recorded runs when there are enough."""
    recorded: dict[int, list[float]] = {n: [] for n in PHASE_PRIORS}
    for entry in history if isinstance(history, list) else []:
        durations = entry.get("duraciones") if isinstance(entry, dict) else None
        if not isinstance(durations, dict):
            continue
        for n in PHASE_PRIORS:
            value = durations.get(str(n))
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                recorded[n].append(float(value))
    return {n: statistics.median(values) if len(values) >= HISTORY_MIN_RUNS else float(PHASE_PRIORS[n])
            for n, values in recorded.items()}


def estimate_progress(data: dict[str, Any], now: datetime.datetime, calls_mtime: float | None = None) -> dict[str, Any]:
    """Estimated percent, time left and current phase of a progress document (see the module docstring)."""
    priors = _priors(data.get("historial"))
    rows = {row.get("n"): row for row in data.get("phases") or [] if isinstance(row, dict)}
    started = _instant(data.get("started_at"))
    stamps = [t for t in (started, _instant(data.get("updated_at"))) if t]
    done: dict[int, float] = {}
    running: tuple[int, datetime.datetime] | None = None
    for n in PHASE_PRIORS:
        row = rows.get(n) or {}
        begin, end = _instant(row.get("started_at")), _instant(row.get("ended_at"))
        stamps += [t for t in (begin, end) if t]
        if begin and end:
            done[n] = max(0.0, (end - begin).total_seconds())
        elif begin:
            running = (n, begin)
    prior_done = sum(priors[n] for n in done)
    pace = 1.0
    if done and prior_done > 0:
        pace = min(max(sum(done.values()) / prior_done, PACE_BOUNDS[0]), PACE_BOUNDS[1])
    remaining = sum(priors[n] * pace for n in PHASE_PRIORS if n not in done and (not running or n != running[0]))
    weight = prior_done
    if running:
        n, begin = running
        expected = priors[n] * pace
        elapsed = max(0.0, (now - begin).total_seconds())
        remaining += max(expected - elapsed, OVERRUN_FLOOR * expected)
        share = min(elapsed / expected, RUNNING_SHARE_CAP) if expected > 0 else RUNNING_SHARE_CAP
        weight += share * priors[n]
    total = sum(priors.values())
    percent = min(99, int(math.floor(100 * weight / total))) if total > 0 else 0

    any_started = bool(done) or running is not None
    fresh_calls = calls_mtime is not None and started is not None and calls_mtime > started.timestamp()
    finished = _instant(data.get("finished_at")) is not None or (
        fresh_calls and (REGISTER_PHASE in done or not any_started))
    if running:
        phase = running[0]
    else:
        phase = next((n for n in PHASE_PRIORS if n not in done and n > max(done, default=0)), max(PHASE_PRIORS))
    last = max(stamps) if stamps else None
    stale = not finished and (last is None or (now - last).total_seconds() > STALE_SECONDS)
    name = (rows.get(phase) or {}).get("nombre")
    name = name if isinstance(name, str) and name else PHASE_NAMES[phase]
    return {
        "estado": "terminada" if finished else ("detenida" if stale else "en_curso"),
        "alcance": data.get("alcance") if data.get("alcance") in ALCANCES else None,
        "started_at": data.get("started_at"),
        "updated_at": last.isoformat(timespec="seconds") if last else None,
        "finished_at": data.get("finished_at"),
        "fase": phase,
        "fases_total": len(PHASE_PRIORS),
        "fase_nombre": name,
        "phase_label": f"Fase {phase}/{len(PHASE_PRIORS)} · {name}",
        "percent": 100 if finished else percent,
        "remaining_seconds": 0 if finished else int(round(remaining)),
        "stale": stale,
        "priors": {str(n): round(v) for n, v in priors.items()},
    }


def _progress_root(workspace_dir: Path) -> Path:
    """The folder holding the Morfeo config at or above `workspace_dir`, as the script resolves it."""
    for folder in (workspace_dir, *workspace_dir.parents):
        if any((folder / marker).is_file() for marker in _CONFIG_MARKERS):
            return folder
    return workspace_dir


def load_progress(workspace_dir: Path | str, now: datetime.datetime | None = None) -> dict[str, Any]:
    """{progreso, error}: the estimate of convocatorias/progreso.json, or None; never writes."""
    root = _progress_root(Path(workspace_dir).expanduser().resolve())
    path = root / PROGRESS_FILE
    if not path.is_file():
        return {"progreso": None, "error": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as err:
        return {"progreso": None, "error": f"No se pudo leer {PROGRESS_FILE.as_posix()}: {err}"}
    if not isinstance(data, dict) or data.get("schema") != PROGRESS_SCHEMA:
        return {"progreso": None, "error": f"{PROGRESS_FILE.as_posix()} no sigue el esquema {PROGRESS_SCHEMA}."}
    try:
        calls_mtime = (root / CALLS_FILE).stat().st_mtime
    except OSError:
        calls_mtime = None
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    return {"progreso": estimate_progress(data, moment, calls_mtime), "error": None}
