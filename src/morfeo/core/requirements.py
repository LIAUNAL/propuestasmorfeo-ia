"""Requisitos habilitantes, aval institucional, licencias y cifras SGR de una corrida, para la pestaña «Requisitos y anexos».

Solo existe en el flujo SGR: en el flujo base no se lee nada y el tablero oculta
la pestaña. En la unidad `fase6_9_sgr` `scripts/requisitos_sgr.py init` siembra
`artefactos/sgr/requisitos.json` (esquema `morfeo.requisitos-sgr/v1`) desde la
rúbrica de la convocatoria; el investigador escribe el bloque de licencias, el
redactor su introducción y el usuario marca cada requisito y declara las cifras
de los anexos desde el tablero. Toda la vista (`vista`), los hallazgos
(`findings`) y las ediciones (`actualizar_item`) salen de ese script, que se
carga desde el kit como la cadena de valor carga el suyo: si falta, la pestaña
lo dice y el tablero nunca se cae. Sin `requisitos.json` la vista sigue
funcionando (los requisitos se leen como pendientes).

La aprobación (compuerta GRequisitos) comparte `artefactos/sgr/revision.json`
con las demás pestañas SGR, bajo la clave `requisitos`, con su mismo cerrojo y
escritura atómica: queda atada al hash de `requisitos.json`, caduca si cambia
(también con cada edición en línea) y no se aprueba con hallazgos de error. Las
ediciones en línea toman el mismo cerrojo, así que una aprobación nunca se cruza
con una escritura a medias.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .alliance import ALIANZA_FILE, ALIANZA_SCHEMA, _findings, _read_json
from .components import _entidades
from .trees import _detect_flujo, _hash, _workspace_path
from .value_chain import (
    _REVIEW_LOCK,
    SGR_DIR,
    ReviewFileError,
    _read_review,
    _write_review,
    load_kit_script,
)

REQUISITOS_FILE = SGR_DIR / "requisitos.json"
PRESUPUESTO_FILE = SGR_DIR / "presupuesto.json"
REQUISITOS_SCHEMA = "morfeo.requisitos-sgr/v1"
REQUIREMENTS_SCRIPT = "requisitos_sgr.py"
REVIEW_KEY = "requisitos"
UNIT = "fase6_9_sgr"
# Campos de un requisito que el tablero puede editar en línea.
EDITABLE_FIELDS = ("estado", "responsable", "archivo", "fecha", "nota", "justificacion")
# Documentos cuyas cifras declaradas se editan con el id `cifras.<documento>`.
FIGURE_DOCUMENTS = ("sigp", "anexo1", "anexo3", "mga")
# Tope del cuerpo de los POST de la pestaña: una edición es un puñado de campos.
MAX_BODY_BYTES = 64 * 1024
_SGR_ONLY = "Los requisitos habilitantes, las licencias y las cifras de los anexos solo existen en el flujo SGR."


def _script(*required: str) -> Any:
    return load_kit_script(REQUIREMENTS_SCRIPT, required or ("vista", "findings", "actualizar_item"))


def _call_script(run_dir: Path, name: str) -> tuple[Any, str | None]:
    module = _script()
    fn = getattr(module, name, None) if module is not None else None
    if not callable(fn):
        return None, None
    try:
        return fn(run_dir), None
    except Exception as err:
        return None, f"{REQUIREMENTS_SCRIPT} no pudo calcular {name}: {err}"


def load_requirements(run_dir: Path | str) -> dict[str, Any]:
    """Estado de los requisitos y anexos para el tablero; nunca lanza hacia la capa HTTP."""
    run_dir = Path(run_dir)
    flujo = _detect_flujo(run_dir)
    result: dict[str, Any] = {
        "flujo": flujo, "disponible": False, "requisitos": None, "vista": None, "hallazgos": [],
        "entidades": {}, "aprobado": False, "hash": None, "revision": None, "errores": [],
    }
    if flujo != "sgr":
        return result
    try:
        entry = _read_review(run_dir).get(REVIEW_KEY)
        result["revision"] = entry if isinstance(entry, dict) else None
    except ReviewFileError as err:
        result["errores"].append(str(err))
    requisitos, err_r = _read_json(run_dir, REQUISITOS_FILE, REQUISITOS_SCHEMA)
    alianza, err_a = _read_json(run_dir, ALIANZA_FILE, ALIANZA_SCHEMA)
    result["errores"].extend(e for e in (err_r, err_a) if e)
    result["entidades"] = _entidades(alianza)
    result["requisitos"] = requisitos
    vista, err_v = _call_script(run_dir, "vista")
    if err_v:
        result["errores"].append(err_v)
    if isinstance(vista, dict):
        result["vista"] = vista
        result["disponible"] = True
        raw = vista.get("findings")
        if raw is None:
            raw, err_f = _call_script(run_dir, "findings")
            if err_f:
                result["errores"].append(err_f)
        result["hallazgos"] = _findings(raw)
    if requisitos is not None:
        current = _hash(requisitos)
        revision = result["revision"] or {}
        result["hash"] = current
        result["aprobado"] = bool(revision.get("aprobado")) and revision.get("hash") == current
    return result


def approve(run_dir: Path | str, expected_hash: str | None = None) -> dict[str, Any]:
    """Aprueba los requisitos, las licencias y las cifras vigentes (compuerta GRequisitos).
    `expected_hash` es el que vio quien aprueba: si el archivo cambió, se rechaza."""
    run_dir = Path(run_dir)
    with _REVIEW_LOCK:
        try:
            review = _read_review(run_dir)
        except ReviewFileError as err:
            return {"ok": False, "error": str(err)}
        state = load_requirements(run_dir)
        if state["flujo"] != "sgr":
            return {"ok": False, "error": _SGR_ONLY}
        if state["requisitos"] is None:
            detail = "; ".join(state["errores"])
            return {"ok": False, "error": (
                f"Todavía no hay {REQUISITOS_FILE.as_posix()} que aprobar: lo siembra scripts/{REQUIREMENTS_SCRIPT} init "
                f"en la unidad {UNIT} y se revisa con scripts/{REQUIREMENTS_SCRIPT} check."
                + (f" ({detail})" if detail else ""))}
        if expected_hash and expected_hash != state["hash"]:
            return {"ok": False, "error": "Los requisitos o las cifras cambiaron desde que los abriste: revisa la versión nueva antes de aprobarla."}
        errors = sorted({f["code"] for f in state["hallazgos"] if f.get("severity") == "error"})
        if errors:
            return {"ok": False, "error": "Corrige los hallazgos de error de los requisitos y los anexos antes de aprobarlos: "
                                          + ", ".join(errors) + "."}
        fecha = datetime.now().isoformat(timespec="seconds")
        review[REVIEW_KEY] = {"aprobado": True, "hash": state["hash"], "fecha": fecha}
        _write_review(run_dir, review)
        return {"ok": True, "hash": state["hash"], "fecha": fecha}


def _validate_edit(payload: Any) -> tuple[str, dict[str, Any]]:
    """`(id, cambios)` de un cuerpo `{id, cambios}`; levanta `ValueError` si la forma no sirve."""
    if not isinstance(payload, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON con «id» y «cambios».")
    item_id = payload.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError("El campo «id» debe ser el texto del requisito (p. ej. «11.4») o «cifras.<documento>».")
    item_id = item_id.strip()
    cambios = payload.get("cambios")
    if item_id.startswith("cifras."):
        documento = item_id.split(".", 1)[1]
        if documento not in FIGURE_DOCUMENTS:
            raise ValueError(f"Documento de cifras desconocido: «{documento}». Usa uno de: {', '.join(FIGURE_DOCUMENTS)}.")
        if not isinstance(cambios, dict):
            raise ValueError("Las cifras declaradas deben ser un objeto JSON en «cambios».")
        return item_id, cambios
    if not isinstance(cambios, dict) or not cambios:
        raise ValueError("El campo «cambios» debe ser un objeto con al menos un campo editable.")
    unknown = sorted(k for k in cambios if k not in EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"Campos no editables: {', '.join(unknown)}. Solo se editan: {', '.join(EDITABLE_FIELDS)}.")
    for key, value in cambios.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(f"El campo «{key}» debe ser texto o null.")
    return item_id, dict(cambios)


def _is_validation_error(err: Exception, module: Any) -> bool:
    """Errores de validación del script: `ValueError`, `TypeError`, `KeyError` o una excepción propia del script."""
    return isinstance(err, (ValueError, TypeError, KeyError)) or type(err).__module__ == getattr(module, "__name__", None)


def update_item(run_dir: Path | str, payload: Any) -> dict[str, Any]:
    """Edita un requisito (o un bloque de cifras) con `actualizar_item` del script.

    Un cuerpo mal formado o un valor que el script rechaza levantan `ValueError`
    con su mensaje (la capa HTTP responde 400). El flujo base o un script ausente
    devuelven `{ok: False, error}`. Si todo sale bien devuelve el ítem
    actualizado y la vista recalculada."""
    run_dir = Path(run_dir)
    item_id, cambios = _validate_edit(payload)
    if _detect_flujo(run_dir) != "sgr":
        return {"ok": False, "error": _SGR_ONLY}
    module = _script("actualizar_item")
    fn = getattr(module, "actualizar_item", None) if module is not None else None
    if not callable(fn):
        return {"ok": False, "error": f"No se encontró scripts/{REQUIREMENTS_SCRIPT} con actualizar_item: no se puede editar desde el tablero."}
    with _REVIEW_LOCK:
        try:
            item = fn(run_dir, item_id, cambios)
        except Exception as err:
            if _is_validation_error(err, module):
                message = err.args[0] if isinstance(err, KeyError) and err.args else err
                raise ValueError(str(message) or type(err).__name__) from err
            raise
    return {"ok": True, "item": item, **load_requirements(run_dir)}


def build_adjust_prompt(run_dir: Path | str, nota: Any) -> str:
    """Instrucción de una línea para la terminal del agente. Una nota vacía o una
    corrida del flujo base levantan `ValueError`."""
    run_dir = Path(run_dir)
    if not isinstance(nota, str) or not nota.strip():
        raise ValueError("La solicitud de ajuste está vacía: escribe qué cambiar en los requisitos, las licencias o las cifras.")
    if _detect_flujo(run_dir) != "sgr":
        raise ValueError(_SGR_ONLY)
    nota = " ".join(nota.split())
    requisitos = _workspace_path(run_dir, REQUISITOS_FILE)
    alianza = _workspace_path(run_dir, ALIANZA_FILE)
    presupuesto = _workspace_path(run_dir, PRESUPUESTO_FILE)
    run = f"proposals/{run_dir.name}" if run_dir.parent.name == "proposals" else "."
    return (
        f"Ajusta los requisitos habilitantes, las licencias y las cifras de los anexos SGR de la corrida activa según esta indicación del tablero: «{nota}». "
        f"Edita solo {requisitos} (esquema {REQUISITOS_SCHEMA}). "
        "Si el ajuste toca el análisis de licencias y permisos, despacha a investigador para editar los ítems del bloque "
        "licencias (licencia, norma, si aplica, justificación, responsable y momento del trámite) y a redactor para su "
        "introducción en tercera persona, con revisor-estilo-sgr sobre la prosa. "
        "El estado, el archivo y la fecha de cada requisito los marca el usuario en el tablero: no marques un requisito "
        "como listo sin su archivo en insumos/requisitos/ ni como no_aplica sin justificación. "
        f"Las cifras declaradas deben coincidir con {presupuesto} y con los aportes de las entidades de {alianza}; "
        "si faltan hechos, despacha antes a insumos-observador para extraerlos de los insumos; no los inventes. "
        f"Después corre python3 scripts/{REQUIREMENTS_SCRIPT} check {run}, corrige los hallazgos de error y avísame "
        "cuando el tablero muestre la nueva versión."
    )
