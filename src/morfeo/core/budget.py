"""Presupuesto y cronograma SGR de una corrida, para la pestaña «Presupuesto y cronograma».

Solo existe en el flujo SGR: en el flujo base no se lee nada y el tablero oculta
la pestaña. En la Fase 6.4 el presupuestador escribe
`artefactos/sgr/presupuesto.json` (esquema `morfeo.presupuesto-sgr/v1`) y en la
6.45 el investigador escribe `artefactos/sgr/hitos.json` (esquema
`morfeo.hitos-sgr/v1`); los meses, la etapa y la ruta crítica de cada actividad
viven en la cadena de valor. `scripts/presupuesto_sgr.py` (`findings`,
`resumen`) y `scripts/cronograma_sgr.py` (`findings`, `proyeccion`) se cargan
desde el kit como la cadena de valor carga el suyo: si faltan, los datos se
muestran sin hallazgos, resumen ni proyección y el tablero nunca se cae.

La aprobación (compuerta G6.4) comparte `artefactos/sgr/revision.json` con la
cadena de valor y la alianza, bajo la clave `presupuesto`, con su mismo cerrojo
y escritura atómica: queda atada al hash del presupuesto y los hitos juntos,
caduca si cualquiera cambia y no se aprueba con hallazgos de error.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .alliance import _findings, _number, _read_json
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

PRESUPUESTO_FILE = SGR_DIR / "presupuesto.json"
HITOS_FILE = SGR_DIR / "hitos.json"
PRESUPUESTO_SCHEMA = "morfeo.presupuesto-sgr/v1"
HITOS_SCHEMA = "morfeo.hitos-sgr/v1"
BUDGET_SCRIPT = "presupuesto_sgr.py"
SCHEDULE_SCRIPT = "cronograma_sgr.py"
REVIEW_KEY = "presupuesto"
UNIT = "fase6_4"
DEFAULT_ETAPA = "inversion"
_SCRIPT_FUNCS = {BUDGET_SCRIPT: ("findings", "resumen"), SCHEDULE_SCRIPT: ("findings", "proyeccion")}


def _call_script(run_dir: Path, script: str, name: str) -> tuple[Any, str | None]:
    module = load_kit_script(script, _SCRIPT_FUNCS[script])
    fn = getattr(module, name, None) if module is not None else None
    if not callable(fn):
        return None, None
    try:
        return fn(run_dir), None
    except Exception as err:
        return None, f"{script} no pudo calcular {name}: {err}"


def _strings(value: Any) -> list[str]:
    return [str(v) for v in value if v not in (None, "")] if isinstance(value, list) else []


def _cadena_meses(cadena: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Actividades de la cadena en orden OE → producto → actividad, con sus meses."""
    out: list[dict[str, Any]] = []
    for oe in (cadena or {}).get("objetivos") or []:
        if not isinstance(oe, dict):
            continue
        for prod in oe.get("productos") or []:
            if not isinstance(prod, dict):
                continue
            for act in prod.get("actividades") or []:
                if not isinstance(act, dict):
                    continue
                etapa = act.get("etapa")
                out.append({
                    "codigo": str(act.get("codigo") or ""),
                    "nombre": str(act.get("nombre") or ""),
                    "oe": str(oe.get("id") or ""),
                    "oe_texto": str(oe.get("texto") or ""),
                    "producto": str(prod.get("codigo") or ""),
                    "producto_nombre": str(prod.get("nombre") or ""),
                    "mes_inicio": _number(act.get("mes_inicio")),
                    "mes_fin": _number(act.get("mes_fin")),
                    "ruta_critica": bool(act.get("ruta_critica")),
                    "etapa": etapa if isinstance(etapa, str) and etapa else DEFAULT_ETAPA,
                })
    return out


def _hitos(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw = (data or {}).get("hitos")
    return [{
        "codigo": str(h.get("codigo") or ""),
        "nombre": str(h.get("nombre") or ""),
        "mes": _number(h.get("mes")),
        "actividades": _strings(h.get("actividades")),
        "verificacion": str(h.get("verificacion") or ""),
    } for h in (raw if isinstance(raw, list) else []) if isinstance(h, dict)]


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def load_budget(run_dir: Path | str) -> dict[str, Any]:
    """Estado del presupuesto y el cronograma para el tablero; nunca lanza hacia la capa HTTP."""
    run_dir = Path(run_dir)
    flujo = _detect_flujo(run_dir)
    result: dict[str, Any] = {
        "flujo": flujo, "disponible": False, "presupuesto": None, "resumen": None, "proyeccion": None,
        "cadena_meses": [], "hitos": [], "duracion_meses": None, "hallazgos": [], "aprobado": False,
        "hash": None, "revision": None, "errores": [],
    }
    if flujo != "sgr":
        return result
    try:
        entry = _read_review(run_dir).get(REVIEW_KEY)
        result["revision"] = entry if isinstance(entry, dict) else None
    except ReviewFileError as err:
        result["errores"].append(str(err))
    presupuesto, err_p = _read_json(run_dir, PRESUPUESTO_FILE, PRESUPUESTO_SCHEMA)
    hitos, err_h = _read_json(run_dir, HITOS_FILE, HITOS_SCHEMA)
    cadena, err_c = _read_cadena(run_dir)
    result["errores"].extend(e for e in (err_p, err_h, err_c) if e)
    result["cadena_meses"] = _cadena_meses(cadena)
    result["hitos"] = _hitos(hitos)
    result["duracion_meses"] = _number((presupuesto or {}).get("duracion_meses")) or _number(
        (cadena or {}).get("duracion_meses"))
    hallazgos: list[dict[str, Any]] = []
    if presupuesto is not None:
        raw, err = _call_script(run_dir, BUDGET_SCRIPT, "findings")
        hallazgos.extend(_findings(raw))
        resumen, err_r = _call_script(run_dir, BUDGET_SCRIPT, "resumen")
        result["resumen"] = _dict_or_none(resumen)
        result["errores"].extend(e for e in (err, err_r) if e)
    if cadena is not None:
        raw, err = _call_script(run_dir, SCHEDULE_SCRIPT, "findings")
        hallazgos.extend(_findings(raw))
        proyeccion, err_y = _call_script(run_dir, SCHEDULE_SCRIPT, "proyeccion")
        result["proyeccion"] = _dict_or_none(proyeccion)
        result["errores"].extend(e for e in (err, err_y) if e)
    result["hallazgos"] = hallazgos
    if presupuesto is None and hitos is None:
        return result
    current = _hash({"presupuesto": presupuesto, "hitos": hitos})
    revision = result["revision"] or {}
    result.update({
        "disponible": True,
        "presupuesto": presupuesto,
        "hash": current,
        "aprobado": bool(revision.get("aprobado")) and revision.get("hash") == current,
    })
    return result


def approve(run_dir: Path | str, expected_hash: str | None = None) -> dict[str, Any]:
    """Aprueba el presupuesto y los hitos vigentes (compuerta G6.4). `expected_hash`
    es el que vio quien aprueba: si alguno de los dos archivos cambió, se rechaza.
    Los hitos son opcionales (se escriben en la Fase 6.45), el presupuesto no."""
    run_dir = Path(run_dir)
    with _REVIEW_LOCK:
        try:
            review = _read_review(run_dir)
        except ReviewFileError as err:
            return {"ok": False, "error": str(err)}
        state = load_budget(run_dir)
        if state["flujo"] != "sgr":
            return {"ok": False, "error": "El presupuesto y el cronograma estructurados solo existen en el flujo SGR."}
        if state["presupuesto"] is None:
            detail = "; ".join(state["errores"])
            return {"ok": False, "error": (
                f"Todavía no hay {PRESUPUESTO_FILE.as_posix()} que aprobar: lo escribe el presupuestador en la "
                f"unidad {UNIT} y se revisa con scripts/{BUDGET_SCRIPT} check."
                + (f" ({detail})" if detail else ""))}
        _, err_h = _read_json(run_dir, HITOS_FILE, HITOS_SCHEMA)
        if err_h:
            return {"ok": False, "error": f"La aprobación cubre el presupuesto y los hitos, y {err_h}"}
        if expected_hash and expected_hash != state["hash"]:
            return {"ok": False, "error": "El presupuesto o los hitos cambiaron desde que los abriste: revisa la versión nueva antes de aprobarla."}
        errors = sorted({f["code"] for f in state["hallazgos"] if f.get("severity") == "error"})
        if errors:
            return {"ok": False, "error": "Corrige los hallazgos de error del presupuesto y el cronograma antes de aprobarlos: "
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
        raise ValueError("La solicitud de ajuste está vacía: escribe qué cambiar en el presupuesto o el cronograma.")
    if _detect_flujo(run_dir) != "sgr":
        raise ValueError("El presupuesto y el cronograma estructurados solo existen en el flujo SGR.")
    nota = " ".join(nota.split())
    presupuesto = _workspace_path(run_dir, PRESUPUESTO_FILE)
    hitos = _workspace_path(run_dir, HITOS_FILE)
    cadena = _workspace_path(run_dir, CADENA_FILE)
    run = f"proposals/{run_dir.name}" if run_dir.parent.name == "proposals" else "."
    return (
        f"Ajusta el presupuesto y el cronograma SGR de la corrida activa según esta indicación del tablero: «{nota}». "
        f"Si el ajuste toca el presupuesto, despacha a presupuestador para editar solo {presupuesto} "
        f"(esquema {PRESUPUESTO_SCHEMA}): rubros de Minciencias e insumos MGA válidos, entidad y fuente (sgr, especie "
        "o efectivo) de cada ítem, actividades que existan en la cadena de valor, al menos dos cotizaciones para "
        "equipos y servicios tecnológicos, el rubro de Seguimiento con recursos SGR, transferencia de al menos el "
        "1 % y movilidad de máximo el 2 % del total SGR, y contrapartidas iguales a los aportes de alianza.json. "
        f"Si toca los hitos o los meses de las actividades, despacha a investigador para editar solo {hitos} "
        f"(esquema {HITOS_SCHEMA}) y los campos mes_inicio, mes_fin, ruta_critica y etapa de {cadena}. "
        "Si faltan hechos (cotizaciones, valores hora, aportes de las entidades), despacha antes a "
        "insumos-observador para extraerlos de los insumos; no los inventes. "
        f"Después corre python3 scripts/{BUDGET_SCRIPT} check {run}, python3 scripts/{BUDGET_SCRIPT} sync-cadena "
        f"{run} y python3 scripts/{SCHEDULE_SCRIPT} check {run}, corrige los hallazgos de error y avísame cuando el "
        "tablero muestre la nueva versión. Si el ajuste sube el total SGR por encima del tope o cambia los aportes "
        "de una entidad, pregúntame antes."
    )
