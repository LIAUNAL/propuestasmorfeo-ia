"""TRL y componentes transversales SGR de una corrida, para la pestaña «TRL y componentes».

Solo existe en el flujo SGR: en el flujo base no se lee nada y el tablero oculta
la pestaña. En la unidad `fase5_5_sgr` el investigador y el redactor escriben
`artefactos/sgr/componentes.json` (esquema `morfeo.componentes-sgr/v1`): la ruta
y la verificación del TRL, la transferencia, la apropiación social del
conocimiento (ASC), la sostenibilidad, el uso posterior y las medidas
diferenciales. `scripts/componentes_sgr.py` (`findings`) y el `resumen` de
`scripts/presupuesto_sgr.py` (para el porcentaje de transferencia) se cargan
desde el kit como la cadena de valor carga el suyo: si faltan, los datos se
muestran sin hallazgos ni porcentaje y el tablero nunca se cae.

La aprobación (compuerta GComponentes) comparte `artefactos/sgr/revision.json`
con la cadena de valor, la alianza y el presupuesto, bajo la clave
`componentes`, con su mismo cerrojo y escritura atómica: queda atada al hash de
`componentes.json`, caduca si cambia y no se aprueba con hallazgos de error.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .alliance import ALIANZA_FILE, ALIANZA_SCHEMA, _findings, _number, _read_json
from .trees import _detect_flujo, _hash, _workspace_path
from .value_chain import (
    _REVIEW_LOCK,
    CADENA_FILE,
    SGR_DIR,
    ReviewFileError,
    _read_cadena,
    _read_review,
    _write_review,
    load_kit_script,
)

COMPONENTES_FILE = SGR_DIR / "componentes.json"
PRESUPUESTO_FILE = SGR_DIR / "presupuesto.json"
COMPONENTES_SCHEMA = "morfeo.componentes-sgr/v1"
COMPONENTS_SCRIPT = "componentes_sgr.py"
BUDGET_SCRIPT = "presupuesto_sgr.py"
REVIEW_KEY = "componentes"
UNIT = "fase5_5_sgr"
_SCRIPT_FUNCS = {COMPONENTS_SCRIPT: ("findings", "datos"), BUDGET_SCRIPT: ("findings", "resumen")}


def _call_script(run_dir: Path, script: str, name: str) -> tuple[Any, str | None]:
    module = load_kit_script(script, _SCRIPT_FUNCS[script])
    fn = getattr(module, name, None) if module is not None else None
    if not callable(fn):
        return None, None
    try:
        return fn(run_dir), None
    except Exception as err:
        return None, f"{script} no pudo calcular {name}: {err}"


def _cadena_nombres(cadena: dict[str, Any] | None) -> dict[str, str]:
    """`{codigo: nombre}` de las actividades de la cadena de valor."""
    out: dict[str, str] = {}
    for oe in (cadena or {}).get("objetivos") or []:
        for prod in (oe.get("productos") or []) if isinstance(oe, dict) else []:
            for act in (prod.get("actividades") or []) if isinstance(prod, dict) else []:
                if isinstance(act, dict) and act.get("codigo"):
                    out[str(act["codigo"])] = str(act.get("nombre") or "")
    return out


def _entidades(alianza: dict[str, Any] | None) -> dict[str, str]:
    """`{id: nombre}` de las entidades de la alianza."""
    raw = (alianza or {}).get("entidades")
    return {str(e["id"]): str(e.get("nombre") or "") for e in (raw if isinstance(raw, list) else [])
            if isinstance(e, dict) and e.get("id")}


def load_components(run_dir: Path | str) -> dict[str, Any]:
    """Estado del TRL y los componentes para el tablero; nunca lanza hacia la capa HTTP."""
    run_dir = Path(run_dir)
    flujo = _detect_flujo(run_dir)
    result: dict[str, Any] = {
        "flujo": flujo, "disponible": False, "componentes": None, "hallazgos": [], "transferencia_pct": None,
        "cadena": {}, "entidades": {}, "aprobado": False, "hash": None, "revision": None, "errores": [],
    }
    if flujo != "sgr":
        return result
    try:
        entry = _read_review(run_dir).get(REVIEW_KEY)
        result["revision"] = entry if isinstance(entry, dict) else None
    except ReviewFileError as err:
        result["errores"].append(str(err))
    componentes, err_k = _read_json(run_dir, COMPONENTES_FILE, COMPONENTES_SCHEMA)
    cadena, err_c = _read_cadena(run_dir)
    alianza, err_a = _read_json(run_dir, ALIANZA_FILE, ALIANZA_SCHEMA)
    result["errores"].extend(e for e in (err_k, err_c, err_a) if e)
    result["cadena"] = _cadena_nombres(cadena)
    result["entidades"] = _entidades(alianza)
    if (run_dir / PRESUPUESTO_FILE).is_file():
        resumen, err_r = _call_script(run_dir, BUDGET_SCRIPT, "resumen")
        if isinstance(resumen, dict):
            result["transferencia_pct"] = _number(resumen.get("transferencia_pct"))
        if err_r:
            result["errores"].append(err_r)
    if componentes is None:
        return result
    raw, err = _call_script(run_dir, COMPONENTS_SCRIPT, "findings")
    result["hallazgos"] = _findings(raw)
    if err:
        result["errores"].append(err)
    current = _hash(componentes)
    revision = result["revision"] or {}
    result.update({
        "disponible": True,
        "componentes": componentes,
        "hash": current,
        "aprobado": bool(revision.get("aprobado")) and revision.get("hash") == current,
    })
    return result


def approve(run_dir: Path | str, expected_hash: str | None = None) -> dict[str, Any]:
    """Aprueba el TRL y los componentes vigentes (compuerta GComponentes).
    `expected_hash` es el que vio quien aprueba: si el archivo cambió, se rechaza."""
    run_dir = Path(run_dir)
    with _REVIEW_LOCK:
        try:
            review = _read_review(run_dir)
        except ReviewFileError as err:
            return {"ok": False, "error": str(err)}
        state = load_components(run_dir)
        if state["flujo"] != "sgr":
            return {"ok": False, "error": "El TRL y los componentes transversales estructurados solo existen en el flujo SGR."}
        if state["componentes"] is None:
            detail = "; ".join(state["errores"])
            return {"ok": False, "error": (
                f"Todavía no hay {COMPONENTES_FILE.as_posix()} que aprobar: lo escriben el investigador y el redactor "
                f"en la unidad {UNIT} y se revisa con scripts/{COMPONENTS_SCRIPT} check."
                + (f" ({detail})" if detail else ""))}
        if expected_hash and expected_hash != state["hash"]:
            return {"ok": False, "error": "El TRL o los componentes cambiaron desde que los abriste: revisa la versión nueva antes de aprobarla."}
        errors = sorted({f["code"] for f in state["hallazgos"] if f.get("severity") == "error"})
        if errors:
            return {"ok": False, "error": "Corrige los hallazgos de error del TRL y los componentes antes de aprobarlos: "
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
        raise ValueError("La solicitud de ajuste está vacía: escribe qué cambiar en el TRL o los componentes.")
    if _detect_flujo(run_dir) != "sgr":
        raise ValueError("El TRL y los componentes transversales estructurados solo existen en el flujo SGR.")
    nota = " ".join(nota.split())
    componentes = _workspace_path(run_dir, COMPONENTES_FILE)
    cadena = _workspace_path(run_dir, CADENA_FILE)
    alianza = _workspace_path(run_dir, ALIANZA_FILE)
    run = f"proposals/{run_dir.name}" if run_dir.parent.name == "proposals" else "."
    return (
        f"Ajusta el TRL y los componentes transversales SGR de la corrida activa según esta indicación del tablero: «{nota}». "
        f"Edita solo {componentes} (esquema {COMPONENTES_SCHEMA}). "
        "Si el ajuste toca la ruta o la verificación del TRL, la transferencia o el uso posterior, despacha a "
        "investigador para editar los bloques trl, transferencia y uso_posterior: tipología, TRL de entrada con "
        "evidencia y de salida, hitos de la ruta con mes, nivel y evidencia, plan de verificación completo, "
        "resultados con usuarios, etapas con barreras y acciones, bienes con operador y financiación. "
        "Si toca las introducciones, la apropiación social del conocimiento, la sostenibilidad o las medidas "
        "diferenciales, despacha a redactor para editar los textos introduccion y los bloques asc, sostenibilidad "
        "y diferencial en tercera persona (los siete elementos de la ruta ASC, productos con medio de verificación "
        "y mes, ODS con productos, actores con compromiso, barreras con medida, indicador y meta o la justificación "
        "de su ausencia), y pasa la prosa por revisor-estilo-sgr. "
        f"Las actividades deben existir en {cadena} y las entidades en {alianza}; si faltan hechos, despacha antes a "
        "insumos-observador para extraerlos de los insumos; no los inventes. "
        f"Después corre python3 scripts/{COMPONENTS_SCRIPT} check {run}, corrige los hallazgos de error y avísame "
        "cuando el tablero muestre la nueva versión. Si el ajuste cambia el TRL de salida o la tipología, pregúntame antes."
    )
