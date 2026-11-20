"""Vista del Anexo 2 de una corrida SGR, para la pestaña «Anexo 2» del tablero.

Solo existe en el flujo SGR: en el flujo base no se lee nada, el tablero oculta
la pestaña y la ruta responde 409. La vista entera (capítulos del Anexo 2 con
las secciones de Morfeo que los llenan, su estado, sus hallazgos, la regla de
redacción del capítulo, su léxico y los criterios de la rúbrica que lo leen)
sale de `scripts/anexo2_sgr.py` (`vista(run)`, esquema `morfeo.anexo2-sgr/v1`),
que se carga desde el kit como los demás scripts SGR. Es de solo lectura: no
hay aprobación, ni ediciones, ni escrituras. Si el script falta o falla, la
pestaña muestra el error y el tablero nunca se cae.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .trees import _detect_flujo
from .value_chain import load_kit_script

ANNEX2_SCRIPT = "anexo2_sgr.py"
ANNEX2_SCHEMA = "morfeo.anexo2-sgr/v1"
SGR_ONLY = "La vista del Anexo 2 solo existe en el flujo SGR."


def _script() -> Any:
    return load_kit_script(ANNEX2_SCRIPT, ("vista",))


def _call_view(run_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    module = _script()
    fn = getattr(module, "vista", None) if module is not None else None
    if not callable(fn):
        return None, f"No se encontró scripts/{ANNEX2_SCRIPT} con la función vista en el kit de la corrida."
    try:
        view = fn(run_dir)
    except SystemExit as err:
        return None, f"{ANNEX2_SCRIPT} terminó con el código {err.code} al calcular la vista."
    except Exception as err:
        return None, f"{ANNEX2_SCRIPT} no pudo calcular la vista: {err}"
    if not isinstance(view, dict) or view.get("schema") != ANNEX2_SCHEMA:
        return None, f"{ANNEX2_SCRIPT} devolvió una vista que no sigue el esquema {ANNEX2_SCHEMA}."
    return view, None


def load_annex2(run_dir: Path | str) -> dict[str, Any]:
    """Vista del Anexo 2 para el tablero; nunca lanza hacia la capa HTTP ni escribe."""
    run_dir = Path(run_dir)
    flujo = _detect_flujo(run_dir)
    result: dict[str, Any] = {"flujo": flujo, "disponible": False, "vista": None, "error": None}
    if flujo != "sgr":
        result["error"] = SGR_ONLY
        return result
    view, error = _call_view(run_dir)
    result["error"] = error
    if view is not None:
        result["vista"] = view
        result["disponible"] = True
    return result
