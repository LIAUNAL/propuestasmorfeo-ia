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
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .value_chain import load_kit_script

OPPORTUNITIES_SCRIPT = "convocatorias.py"
OPPORTUNITIES_SCHEMA = "morfeo.convocatorias-vista/v1"
SEARCH_COMMAND = "/propuesta-convocatorias"
_ID_RE = re.compile(r"[a-z0-9-]+")
ALCANCES = ("proyecto", "banco")


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
