"""Productos, talento humano e indicadores SGR de una corrida, para la pestaña «Productos e indicadores».

Solo existe en el flujo SGR: en el flujo base no se lee nada y el tablero oculta
la pestaña. En la unidad `fase5_sgr` el investigador y el redactor escriben
`artefactos/sgr/productos.json` (esquema `morfeo.productos-sgr/v1`): el talento
humano a vincular, los productos de CTeI por encima del mínimo de la
convocatoria, la estrategia de divulgación pública de la ciencia y los
indicadores de gestión. Los indicadores de producto se leen de la cadena de
valor (`codigo_dnp`, `indicador`, `unidad`, `meta`) y nunca se duplican aquí;
los mínimos de talento vienen de la rúbrica de la corrida
(`artefactos/juez/rubrica.json`, claves `minimos_talento` y `minimo_productos`).
`scripts/productos_sgr.py` (`findings`, `datos`) se carga desde el kit como la
cadena de valor carga el suyo: si falta, los datos se muestran sin hallazgos y
el tablero nunca se cae.

La aprobación (compuerta GProductos) comparte `artefactos/sgr/revision.json`
con la cadena de valor, la alianza, el presupuesto y los componentes, bajo la
clave `productos`, con su mismo cerrojo y escritura atómica: queda atada al hash
de `productos.json`, caduca si cambia y no se aprueba con hallazgos de error.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .alliance import ALIANZA_FILE, ALIANZA_SCHEMA, _findings, _number, _read_json
from .components import _entidades
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

PRODUCTOS_FILE = SGR_DIR / "productos.json"
PRESUPUESTO_FILE = SGR_DIR / "presupuesto.json"
RUBRICA_FILE = Path("artefactos") / "juez" / "rubrica.json"
PRODUCTOS_SCHEMA = "morfeo.productos-sgr/v1"
RUBRICA_SCHEMA = "morfeo.rubrica-sgr/v1"
PRODUCTS_SCRIPT = "productos_sgr.py"
REVIEW_KEY = "productos"
UNIT = "fase5_sgr"
_CADENA_KEYS = ("codigo", "codigo_dnp", "nombre", "medido_a_traves_de", "indicador", "unidad", "meta")


def _call_script(run_dir: Path, name: str) -> tuple[Any, str | None]:
    module = load_kit_script(PRODUCTS_SCRIPT, ("findings", "datos"))
    fn = getattr(module, name, None) if module is not None else None
    if not callable(fn):
        return None, None
    try:
        return fn(run_dir), None
    except Exception as err:
        return None, f"{PRODUCTS_SCRIPT} no pudo calcular {name}: {err}"


def _cadena_productos(cadena: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Productos de la cadena de valor por objetivo, con su indicador de producto."""
    out: list[dict[str, Any]] = []
    for oe in (cadena or {}).get("objetivos") or []:
        if not isinstance(oe, dict):
            continue
        for prod in oe.get("productos") or []:
            if isinstance(prod, dict):
                out.append({"oe": oe.get("id"), "oe_texto": oe.get("texto"),
                            **{key: prod.get(key) for key in _CADENA_KEYS}})
    return out


def _minimos_raw(raw: Any) -> list[tuple[str, Any, str]]:
    """`(categoria, cantidad, texto)` de `minimos_talento`, como lista de objetos o mapa."""
    if isinstance(raw, dict):
        items = []
        for cat, value in raw.items():
            if isinstance(value, dict):
                items.append({"categoria": cat, **value})
            else:
                items.append({"categoria": cat, "cantidad": value})
        raw = items
    out = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not item.get("categoria"):
            continue
        cantidad = item.get("cantidad", item.get("minimo"))
        texto = item.get("texto", item.get("descripcion")) or ""
        out.append((str(item["categoria"]), cantidad, str(texto)))
    return out


def _minimos_talento(rubrica: dict[str, Any] | None, productos: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Mínimos de talento de la rúbrica frente a la cantidad comprometida por categoría."""
    comprometido: dict[str, int | float] = {}
    for t in (productos or {}).get("talento") or []:
        if isinstance(t, dict) and t.get("categoria"):
            cat = str(t["categoria"])
            comprometido[cat] = comprometido.get(cat, 0) + (_number(t.get("cantidad")) or 0)
    out = []
    for cat, cantidad, texto in _minimos_raw((rubrica or {}).get("minimos_talento")):
        requerido = _number(cantidad) or 0
        actual = comprometido.get(cat, 0)
        out.append({"categoria": cat, "requerido": requerido, "comprometido": actual,
                    "cumple": actual >= requerido, "texto": texto})
    return out


def load_products(run_dir: Path | str) -> dict[str, Any]:
    """Estado de productos, talento e indicadores para el tablero; nunca lanza hacia la capa HTTP."""
    run_dir = Path(run_dir)
    flujo = _detect_flujo(run_dir)
    result: dict[str, Any] = {
        "flujo": flujo, "disponible": False, "productos": None, "cadena_productos": [], "minimos_talento": [],
        "minimo_productos": None, "datos": None, "hallazgos": [], "entidades": {}, "aprobado": False,
        "hash": None, "revision": None, "errores": [],
    }
    if flujo != "sgr":
        return result
    try:
        entry = _read_review(run_dir).get(REVIEW_KEY)
        result["revision"] = entry if isinstance(entry, dict) else None
    except ReviewFileError as err:
        result["errores"].append(str(err))
    productos, err_p = _read_json(run_dir, PRODUCTOS_FILE, PRODUCTOS_SCHEMA)
    cadena, err_c = _read_cadena(run_dir)
    alianza, err_a = _read_json(run_dir, ALIANZA_FILE, ALIANZA_SCHEMA)
    rubrica, err_r = _read_json(run_dir, RUBRICA_FILE, RUBRICA_SCHEMA)
    result["errores"].extend(e for e in (err_p, err_c, err_a, err_r) if e)
    result["cadena_productos"] = _cadena_productos(cadena)
    result["entidades"] = _entidades(alianza)
    result["minimos_talento"] = _minimos_talento(rubrica, productos)
    result["minimo_productos"] = (rubrica or {}).get("minimo_productos")
    if productos is None:
        return result
    raw, err = _call_script(run_dir, "findings")
    result["hallazgos"] = _findings(raw)
    datos, err_d = _call_script(run_dir, "datos")
    result["datos"] = datos if isinstance(datos, dict) else None
    result["errores"].extend(e for e in (err, err_d) if e)
    current = _hash(productos)
    revision = result["revision"] or {}
    result.update({
        "disponible": True,
        "productos": productos,
        "hash": current,
        "aprobado": bool(revision.get("aprobado")) and revision.get("hash") == current,
    })
    return result


def approve(run_dir: Path | str, expected_hash: str | None = None) -> dict[str, Any]:
    """Aprueba los productos, el talento y los indicadores vigentes (compuerta GProductos).
    `expected_hash` es el que vio quien aprueba: si el archivo cambió, se rechaza."""
    run_dir = Path(run_dir)
    with _REVIEW_LOCK:
        try:
            review = _read_review(run_dir)
        except ReviewFileError as err:
            return {"ok": False, "error": str(err)}
        state = load_products(run_dir)
        if state["flujo"] != "sgr":
            return {"ok": False, "error": "Los productos, el talento y los indicadores estructurados solo existen en el flujo SGR."}
        if state["productos"] is None:
            detail = "; ".join(state["errores"])
            return {"ok": False, "error": (
                f"Todavía no hay {PRODUCTOS_FILE.as_posix()} que aprobar: lo escriben el investigador y el redactor "
                f"en la unidad {UNIT} y se revisa con scripts/{PRODUCTS_SCRIPT} check."
                + (f" ({detail})" if detail else ""))}
        if expected_hash and expected_hash != state["hash"]:
            return {"ok": False, "error": "Los productos o los indicadores cambiaron desde que los abriste: revisa la versión nueva antes de aprobarla."}
        errors = sorted({f["code"] for f in state["hallazgos"] if f.get("severity") == "error"})
        if errors:
            return {"ok": False, "error": "Corrige los hallazgos de error de los productos y los indicadores antes de aprobarlos: "
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
        raise ValueError("La solicitud de ajuste está vacía: escribe qué cambiar en los productos, el talento o los indicadores.")
    if _detect_flujo(run_dir) != "sgr":
        raise ValueError("Los productos, el talento y los indicadores estructurados solo existen en el flujo SGR.")
    nota = " ".join(nota.split())
    productos = _workspace_path(run_dir, PRODUCTOS_FILE)
    cadena = _workspace_path(run_dir, CADENA_FILE)
    alianza = _workspace_path(run_dir, ALIANZA_FILE)
    presupuesto = _workspace_path(run_dir, PRESUPUESTO_FILE)
    rubrica = _workspace_path(run_dir, RUBRICA_FILE)
    run = f"proposals/{run_dir.name}" if run_dir.parent.name == "proposals" else "."
    return (
        f"Ajusta los productos, el talento humano y los indicadores SGR de la corrida activa según esta indicación del tablero: «{nota}». "
        f"Edita solo {productos} (esquema {PRODUCTOS_SCHEMA}). "
        "Si el ajuste toca los productos de CTeI, la estrategia de divulgación o los indicadores de gestión, despacha a "
        "investigador para editar los bloques productos_ctei (tipo, subtipo, categoría TOP/A/B, cantidad, si es adicional "
        "al mínimo de la convocatoria y su producto de la cadena), divulgacion (públicos, medios, productos, responsable, "
        "cronograma y si está costeada) e indicadores_gestion (al menos supervisión e informes técnico-financieros, con "
        "fórmula, tipo de fuente y periodicidad). "
        "Si toca los perfiles del talento humano, despacha a redactor para editar el bloque talento en tercera persona "
        "(categoría, cantidad, entidad, perfil, formación, actividades, duración, valor mensual y producto final). "
        f"Los indicadores de producto y los códigos DNP viven en {cadena}: no los copies aquí. Las actividades deben "
        f"existir en {cadena}, las entidades en {alianza}, el talento con valor debe coincidir con los ítems de "
        f"talento humano de {presupuesto} y los mínimos de talento y de productos están en {rubrica}; si faltan hechos, "
        "despacha antes a insumos-observador para extraerlos de los insumos; no los inventes. "
        f"Después corre python3 scripts/{PRODUCTS_SCRIPT} check {run}, corrige los hallazgos de error y avísame "
        "cuando el tablero muestre la nueva versión. Si el ajuste deja el talento por debajo de los mínimos de la convocatoria, pregúntame antes."
    )
