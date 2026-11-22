"""Novedad e hipótesis del tablero: lectura del artefacto, su matriz y el comando.

`scripts/novedad.py registrar` escribe `artefactos/novedad/novedad.json`
(esquema `morfeo.novedad/v1`) a partir del borrador del investigador en modo
novedad: pilares de novedad, hipótesis y sus experimentos, acciones,
implementaciones, intervenciones o transferencias, ligados a las causas
directas y a los objetivos específicos de los árboles. Este módulo carga ese
script desde el kit, como `value_chain` carga el de la cadena de valor, para
validar el artefacto contra los árboles y derivar la matriz del proyecto con
las mismas reglas que el script. Nunca lanza una excepción hacia la capa HTTP
por un archivo ausente o dañado: eso se informa en `errores`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .value_chain import load_kit_script

NOVEDAD_FILE = Path("artefactos") / "novedad" / "novedad.json"
NOVEDAD_SCHEMA = "morfeo.novedad/v1"
NOVEDAD_COMMAND = "/propuesta-novedad"
NOVEDAD_SCRIPT = "novedad.py"
_REQUIRED = ("derive_matrix", "validate_record", "load_trees")


def build_run_command() -> str:
    """Comando de barra que el tablero entrega a la terminal del agente."""
    return NOVEDAD_COMMAND


def load_novedad(run_dir: Path | str) -> dict[str, Any]:
    """Artefacto de novedad con su matriz y su validación; estado vacío si no existe."""
    run = Path(run_dir)
    rel = NOVEDAD_FILE.as_posix()
    result: dict[str, Any] = {"disponible": False, "archivo": rel, "novedad": None, "matriz": None,
                              "validacion": None, "actualizado": None, "errores": []}
    path = run / NOVEDAD_FILE
    if not path.is_file():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        mtime = path.stat().st_mtime
    except (OSError, ValueError) as err:
        result["errores"].append(f"{rel} no es un JSON válido: {err}")
        return result
    if not isinstance(data, dict):
        result["errores"].append(f"{rel} debe ser un objeto JSON.")
        return result
    if data.get("schema") != NOVEDAD_SCHEMA:
        result["errores"].append(f"{rel} no declara el esquema {NOVEDAD_SCHEMA} (declara {data.get('schema')!r}).")
        return result
    module = load_kit_script(NOVEDAD_SCRIPT, _REQUIRED)
    if module is None or not all(callable(getattr(module, name, None)) for name in _REQUIRED):
        result["errores"].append(f"No se encontró scripts/{NOVEDAD_SCRIPT}: el artefacto se muestra sin matriz.")
        result.update(disponible=True, novedad=data, actualizado=datetime.fromtimestamp(mtime).isoformat())
        return result
    try:
        trees = module.load_trees(run)
        errores = module.validate_record(data, trees)
        matriz = module.derive_matrix(data, trees)
    except Exception as err:  # the dashboard never falls over on a malformed record
        result["errores"].append(f"No se pudo derivar la matriz de {rel}: {err}")
        result.update(disponible=True, novedad=data, actualizado=datetime.fromtimestamp(mtime).isoformat())
        return result
    result.update(
        disponible=True,
        novedad=data,
        matriz=matriz,
        validacion={"ok": not errores, "errores": errores},
        actualizado=datetime.fromtimestamp(mtime).isoformat(),
    )
    return result
