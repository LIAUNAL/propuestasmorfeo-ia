"""Convocatorias afines al proyecto, para la pestaña «Convocatorias» del tablero.

Existe en los dos flujos y a nivel de espacio de trabajo: la búsqueda precede a
las corridas, así que no hace falta una corrida activa. La vista entera
(perfil, resumen, fuentes consultadas y convocatorias ordenadas con su rol para
Colombia, su cuenta regresiva y su puntaje) sale de `scripts/convocatorias.py`
(`vista(dir)`, esquema `morfeo.convocatorias-vista/v1`), que se carga desde el
kit como los demás scripts. Es de solo lectura: el tablero no escribe nada y
sus botones solo devuelven el prompt de `/propuesta-convocatorias` que se
entrega a la terminal.

Constelación: `render_opportunities_atlas` arma la página que muestra la vista
«Constelación de afinidad» (`/api/convocatorias/atlas`). La escena sale de
`convocatorias.py` (`constelacion`) y la dibuja `render_atlas.py` con su perfil
«convocatorias», el mismo visor 3D de la constelación SOTA. Sin convocatorias
devuelve una página de estado vacío; si un script falta o falla, una página de
error. Nada se guarda: cada petición lee la vista del momento. El alcance (`proyecto` o `banco`) elige el perfil contra
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
import html
import inspect
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

from .value_chain import load_kit_script

OPPORTUNITIES_SCRIPT = "convocatorias.py"
ATLAS_SCRIPT = "render_atlas.py"
ATLAS_PROFILE = "convocatorias"
ATLAS_GROUPINGS = ("tema", "ambito", "rol")
ATLAS_TITLE = "Constelación de convocatorias"
SCOPE_NAMES = {"proyecto": "Proyecto en formulación", "banco": "Banco LIA"}
#: The constellation page in English (``?lang=en`` from the dashboard): its
#: title, scope names and the messages of its empty and error pages. The
#: calls themselves are drawn as the search recorded them.
ATLAS_LANGUAGES = ("es", "en")
_ATLAS_EN = {
    ATLAS_TITLE: "Constellation of calls",
    "Proyecto en formulación": "Project being drafted",
    "Banco LIA": "LIA bank",
    "Constelación no disponible": "Constellation unavailable",
    "Todavía no hay convocatorias": "No calls yet",
    "Petición inválida": "Invalid request",
    "Todavía no hay convocatorias para este espacio de trabajo. Pulsa «Buscar para el proyecto» o «Buscar para el "
    "banco LIA» y la constelación aparece aquí.":
        "There are no calls for this workspace yet. Press «Search for the project» or «Search for the LIA bank» "
        "and the constellation appears here.",
}
_ATLAS_EN_TEMPLATES = (
    (re.compile(r"No se encontró scripts/(?P<script>\S+) con la función (?P<fn>\w+) en el kit\."),
     "scripts/{script} with the {fn} function was not found in the kit."),
    (re.compile(r"(?P<script>\S+) terminó con el código (?P<code>.*?) al armar la constelación\."),
     "{script} exited with code {code} while building the constellation."),
    (re.compile(r"(?P<script>\S+) no pudo armar la constelación: (?P<detail>.*)", re.S),
     "{script} could not build the constellation: {detail}"),
    (re.compile(r"(?P<script>\S+) no pudo dibujar la constelación: (?P<detail>.*)", re.S),
     "{script} could not draw the constellation: {detail}"),
)


def atlas_text(text: str, lang: str | None = None) -> str:
    """A text of the constellation page (title, scope, message) in ``lang``; Spanish as is."""
    if lang != "en":
        return text
    if text in _ATLAS_EN:
        return _ATLAS_EN[text]
    for pattern, english in _ATLAS_EN_TEMPLATES:
        match = pattern.fullmatch(text)
        if match:
            return english.format(**match.groupdict())
    return text


def validate_language(lang: Any) -> str | None:
    """None when absent; the page language otherwise. ValueError for anything else."""
    if lang is None:
        return None
    if not isinstance(lang, str) or lang not in ATLAS_LANGUAGES:
        raise ValueError("El idioma debe ser «es» o «en».")
    return lang
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


# --- Constellation page -------------------------------------------------------

def _validate_atlas_query(agrupar: Any, ids: Any) -> tuple[str, list[str] | None]:
    """(agrupar, ids) of the atlas route; ValueError for anything else.

    `ids` is a comma-separated list of call slugs (the panel's filters); absent
    means every call.
    """
    if agrupar is None:
        agrupar = "tema"
    if not isinstance(agrupar, str) or agrupar not in ATLAS_GROUPINGS:
        raise ValueError("El agrupamiento debe ser «tema», «ambito» o «rol».")
    if ids is None:
        return agrupar, None
    if not isinstance(ids, str):
        raise ValueError("Los ids deben ser slugs separados por comas.")
    values = [v for v in ids.split(",") if v]
    if any(not _ID_RE.fullmatch(v) for v in values):
        raise ValueError("Los ids deben ser slugs separados por comas.")
    return agrupar, values


def message_page(title: str, text: str, lang: str | None = None) -> str:
    """A small dark page for the constellation frame: an empty state or an error, as text.

    ``lang="en"`` writes it in English (:func:`atlas_text`); Spanish otherwise."""
    title, text = atlas_text(title, lang), atlas_text(text, lang)
    return f"""<!DOCTYPE html>
<html lang="{'en' if lang == 'en' else 'es'}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title></head>
<body style="background:#0a0a10;color:#9aa3bd;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px;box-sizing:border-box;text-align:center">
  <div style="background:#11131f;padding:2rem;border-radius:12px;border:1px solid #2a3350;max-width:520px;overflow-wrap:anywhere">
    <h3 style="color:#e4e4ed;margin:0 0 0.5rem;font-size:1.1rem">{html.escape(title)}</h3>
    <p style="font-size:0.9rem;line-height:1.5;margin:0">{html.escape(text)}</p>
  </div>
</body>
</html>"""


def atlas_page(built: dict[str, Any], lang: str | None = None) -> str:
    """The constellation page of a built scene (`convocatorias.py` `atlas_de_vista`).

    ``lang="en"`` asks render_atlas.py for its English chrome. LookupError when
    render_atlas.py is missing from the kit.
    """
    module = load_kit_script(ATLAS_SCRIPT, ("render",))
    render = getattr(module, "render", None) if module is not None else None
    if not callable(render):
        raise LookupError(f"No se encontró scripts/{ATLAS_SCRIPT} con la función render en el kit.")
    scope = atlas_text(SCOPE_NAMES.get(built.get("alcance"), SCOPE_NAMES["proyecto"]), lang)
    title = atlas_text(ATLAS_TITLE, lang)
    # A kit render_atlas.py older than the page languages draws its Spanish chrome.
    options = {"lang": "en"} if lang == "en" and "lang" in inspect.signature(render).parameters else {}
    return render(built["atlas"], title=title, heading=f"{title} · {scope}",
                  papers=built.get("fichas") or {}, profile=ATLAS_PROFILE, **options)


def render_opportunities_atlas(workspace_dir: Path | str, alcance: Any = None, agrupar: Any = None,
                               ids: Any = None, lang: Any = None) -> str:
    """HTML of the «Convocatorias» constellation; never writes.

    Invalid parameters raise ValueError (the HTTP layer answers 400); a missing
    or failing script becomes an error page, and a view without calls an empty
    state page. ``lang`` ("es" or "en", absent means Spanish) is the language
    of the page's own chrome and messages.
    """
    scope = validate_alcance(alcance)
    grouping, wanted = _validate_atlas_query(agrupar, ids)
    lang = validate_language(lang)
    module = load_kit_script(OPPORTUNITIES_SCRIPT, ("constelacion",))
    fn = getattr(module, "constelacion", None) if module is not None else None
    if not callable(fn):
        return message_page("Constelación no disponible",
                            f"No se encontró scripts/{OPPORTUNITIES_SCRIPT} con la función constelacion en el kit.", lang)
    try:
        built = fn(Path(workspace_dir), alcance=scope, agrupar=grouping, ids=wanted)
    except SystemExit as err:
        return message_page("Constelación no disponible",
                            f"{OPPORTUNITIES_SCRIPT} terminó con el código {err.code} al armar la constelación.", lang)
    except Exception as err:
        return message_page("Constelación no disponible", f"{OPPORTUNITIES_SCRIPT} no pudo armar la constelación: {err}",
                            lang)
    if not isinstance(built, dict) or not built.get("total"):
        return message_page("Todavía no hay convocatorias",
                            "Todavía no hay convocatorias para este espacio de trabajo. Pulsa «Buscar para el "
                            "proyecto» o «Buscar para el banco LIA» y la constelación aparece aquí.", lang)
    try:
        return atlas_page(built, lang)
    except LookupError as err:
        return message_page("Constelación no disponible", str(err), lang)
    except (OSError, ValueError) as err:
        return message_page("Constelación no disponible", f"{ATLAS_SCRIPT} no pudo dibujar la constelación: {err}", lang)


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
