"""Alianza y territorio SGR de una corrida, para la pestaña «Alianza y territorio».

Solo existe en el flujo SGR: en el flujo base no se lee nada y el tablero oculta
la pestaña. La unidad `fase1b_sgr` escribe `artefactos/sgr/alianza.json`
(esquema `morfeo.alianza-sgr/v1`) y `artefactos/sgr/territorio.json` (esquema
`morfeo.territorio-sgr/v1`); `scripts/alianza_territorio_sgr.py` los revisa
(`findings`, hallazgos `alianza-*` / `territorio-*` con la forma de check_run) y
estima en vivo los subcriterios contados de la rúbrica (`puntaje`). El script se
carga desde el kit como la cadena de valor carga el suyo: si falta, los datos se
muestran sin hallazgos ni puntaje y el tablero nunca se cae.

La aprobación comparte `artefactos/sgr/revision.json` con la cadena de valor,
bajo la clave `alianza_territorio`, con su mismo cerrojo y escritura atómica:
queda atada al hash de los dos archivos juntos, caduca si cualquiera cambia y no
se aprueba con hallazgos de error.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .trees import _detect_flujo, _hash, _workspace_path
from .value_chain import (
    _REVIEW_LOCK,
    SGR_DIR,
    ReviewFileError,
    _read_review,
    _write_review,
    load_kit_script,
)

ALIANZA_FILE = SGR_DIR / "alianza.json"
TERRITORIO_FILE = SGR_DIR / "territorio.json"
ALIANZA_SCHEMA = "morfeo.alianza-sgr/v1"
TERRITORIO_SCHEMA = "morfeo.territorio-sgr/v1"
ALLIANCE_SCRIPT = "alianza_territorio_sgr.py"
REVIEW_KEY = "alianza_territorio"
UNIT = "fase1b_sgr"
_SCRIPT_FUNCS = ("findings", "puntaje")


def _read_json(run_dir: Path, rel: Path, schema: str) -> tuple[dict[str, Any] | None, str | None]:
    """(datos, error). Un archivo ausente no es un error: la unidad aún no corre."""
    path = run_dir / rel
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as err:
        return None, f"{rel.as_posix()} no es un JSON válido: {err}"
    if not isinstance(data, dict):
        return None, f"{rel.as_posix()} debe ser un objeto JSON."
    if data.get("schema") != schema:
        return None, f"{rel.as_posix()} no declara el esquema {schema} (declara {data.get('schema')!r})."
    return data, None


def _call_script(run_dir: Path, name: str) -> tuple[Any, str | None]:
    module = load_kit_script(ALLIANCE_SCRIPT, _SCRIPT_FUNCS)
    fn = getattr(module, name, None) if module is not None else None
    if not callable(fn):
        return None, None
    try:
        return fn(run_dir), None
    except Exception as err:
        return None, f"{ALLIANCE_SCRIPT} no pudo calcular {name}: {err}"


def _findings(raw: Any) -> list[dict[str, Any]]:
    return [{
        "severity": str(f.get("severity") or "warning"),
        "code": str(f.get("code") or ""),
        "message": str(f.get("message") or ""),
        "node": str(f.get("node") or ""),
    } for f in (raw if isinstance(raw, list) else []) if isinstance(f, dict)]


def _number(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _puntaje(raw: Any) -> list[dict[str, Any]]:
    """Subcriterios contados `{subcriterio, nombre, puntaje, max, incompleto, calculo}`."""
    if isinstance(raw, dict):
        raw = raw.get("subcriterios") or raw.get("puntaje") or []
    return [{
        "subcriterio": str(s.get("subcriterio") or ""),
        "nombre": str(s.get("nombre") or ""),
        "puntaje": _number(s.get("puntaje")),
        "max": _number(s.get("max")),
        "incompleto": bool(s.get("incompleto")),
        "calculo": str(s.get("calculo") or ""),
    } for s in (raw if isinstance(raw, list) else []) if isinstance(s, dict)]


def load_alliance(run_dir: Path | str) -> dict[str, Any]:
    """Estado de la alianza y el territorio para el tablero; nunca lanza hacia la capa HTTP."""
    run_dir = Path(run_dir)
    flujo = _detect_flujo(run_dir)
    result: dict[str, Any] = {
        "flujo": flujo, "disponible": False, "alianza": None, "territorio": None, "hallazgos": [],
        "puntaje": [], "aprobado": False, "hash": None, "revision": None, "errores": [],
    }
    if flujo != "sgr":
        return result
    try:
        entry = _read_review(run_dir).get(REVIEW_KEY)
        result["revision"] = entry if isinstance(entry, dict) else None
    except ReviewFileError as err:
        result["errores"].append(str(err))
    alianza, err_a = _read_json(run_dir, ALIANZA_FILE, ALIANZA_SCHEMA)
    territorio, err_t = _read_json(run_dir, TERRITORIO_FILE, TERRITORIO_SCHEMA)
    result["errores"].extend(e for e in (err_a, err_t) if e)
    if alianza is None and territorio is None:
        return result
    current = _hash({"alianza": alianza, "territorio": territorio})
    raw_findings, err = _call_script(run_dir, "findings")
    if err:
        result["errores"].append(err)
    raw_puntaje, err = _call_script(run_dir, "puntaje")
    if err:
        result["errores"].append(err)
    revision = result["revision"] or {}
    result.update({
        "disponible": True,
        "alianza": alianza,
        "territorio": territorio,
        "hash": current,
        "hallazgos": _findings(raw_findings),
        "puntaje": _puntaje(raw_puntaje),
        "aprobado": bool(revision.get("aprobado")) and revision.get("hash") == current,
    })
    return result


def approve(run_dir: Path | str, expected_hash: str | None = None) -> dict[str, Any]:
    """Aprueba la alianza y el territorio vigentes. `expected_hash` es el que vio
    quien aprueba: si alguno de los dos archivos cambió, la aprobación se rechaza."""
    run_dir = Path(run_dir)
    with _REVIEW_LOCK:
        try:
            review = _read_review(run_dir)
        except ReviewFileError as err:
            return {"ok": False, "error": str(err)}
        state = load_alliance(run_dir)
        if state["flujo"] != "sgr":
            return {"ok": False, "error": "La alianza y el territorio solo existen en el flujo SGR."}
        if not state["disponible"]:
            error = "; ".join(state["errores"]) or (
                f"Todavía no hay alianza ni territorio: los escribe la unidad {UNIT} y se revisan con "
                f"scripts/{ALLIANCE_SCRIPT} check.")
            return {"ok": False, "error": error}
        missing = [rel.as_posix() for rel, data in ((ALIANZA_FILE, state["alianza"]), (TERRITORIO_FILE, state["territorio"]))
                   if data is None]
        if missing:
            detail = "; ".join(state["errores"])
            return {"ok": False, "error": "La aprobación cubre los dos archivos y falta o no se puede leer "
                                          + ", ".join(missing) + (f" ({detail})." if detail else ".")}
        if expected_hash and expected_hash != state["hash"]:
            return {"ok": False, "error": "La alianza o el territorio cambiaron desde que los abriste: revisa la versión nueva antes de aprobarla."}
        errors = sorted({f["code"] for f in state["hallazgos"] if f.get("severity") == "error"})
        if errors:
            return {"ok": False, "error": "Corrige los hallazgos de error de la alianza y el territorio antes de aprobarlos: "
                                          + ", ".join(errors) + "."}
        fecha = datetime.now().isoformat(timespec="seconds")
        review[REVIEW_KEY] = {"aprobado": True, "hash": state["hash"], "fecha": fecha}
        _write_review(run_dir, review)
        return {"ok": True, "hash": state["hash"], "fecha": fecha}


def build_adjust_prompt(run_dir: Path | str, nota: Any) -> str:
    """Instrucción de una línea para la terminal del agente. Una nota vacía o una
    corrida del flujo base levantan `ValueError`."""
    run_dir = Path(run_dir)
    if not isinstance(nota, str) or not nota.strip():
        raise ValueError("La solicitud de ajuste está vacía: escribe qué cambiar en la alianza o el territorio.")
    if _detect_flujo(run_dir) != "sgr":
        raise ValueError("La alianza y el territorio solo existen en el flujo SGR.")
    nota = " ".join(nota.split())
    alianza = _workspace_path(run_dir, ALIANZA_FILE)
    territorio = _workspace_path(run_dir, TERRITORIO_FILE)
    run = f"proposals/{run_dir.name}" if run_dir.parent.name == "proposals" else "."
    return (
        f"Ajusta la alianza y el territorio SGR de la corrida activa según esta indicación del tablero: «{nota}». "
        f"Despacha a investigador para editar solo {alianza} (esquema {ALIANZA_SCHEMA}) y {territorio} "
        f"(esquema {TERRITORIO_SCHEMA}): una sola entidad proponente; tipos, posiciones y aportes válidos; cada "
        "departamento de ejecución con al menos una entidad territorial; cada demanda ligada a causas del árbol de "
        "problemas y a objetivos específicos existentes y, si ya hay cadena de valor, a sus actividades y productos. "
        "Si faltan hechos (texto literal de una demanda del TdR, NIT, aportes, grupos o proyectos de trayectoria), "
        "despacha antes a insumos-observador para extraerlos de los insumos; no los inventes. "
        f"Después corre python3 scripts/{ALLIANCE_SCRIPT} check {run}, corrige los hallazgos de error y avísame "
        "cuando el tablero muestre la nueva versión. Si el ajuste cambia el texto de una demanda (se copia literal "
        "del TdR) o la entidad proponente, pregúntame antes."
    )
