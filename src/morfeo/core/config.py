"""Implementation of 'morfeo config': read or change a project setting.

Only the writing language (`lang`) is settable today. The value is written to
every config.json the project has (`.morfeo/` and the legacy `.marco/`), keeping
the other keys. Runs already created keep the language recorded in their
`_run.md`; only new runs pick the new value.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..errors import UserError
from .language import CONFIG_MARKERS, LANG_LABELS, VALID_LANGS, read_config, read_project_lang

SETTABLE_KEYS = ("lang",)


def config_project(target_dir: Path, key: str, value: str | None = None, quiet: bool = False) -> int:
    target_dir = Path(target_dir).resolve()
    markers = [target_dir / m for m in CONFIG_MARKERS if (target_dir / m).is_dir()]
    if not markers:
        raise UserError(f"El directorio no es un proyecto Morfeo (falta .morfeo/ o .marco/): {target_dir}")
    if key not in SETTABLE_KEYS:
        raise UserError(f"Clave desconocida: {key} (válidas: {', '.join(SETTABLE_KEYS)})")

    if value is None:
        print(read_project_lang(target_dir))
        return 0
    if value not in VALID_LANGS:
        raise UserError(f"Idioma desconocido: {value} (válidos: {', '.join(VALID_LANGS)})")
    if read_config(target_dir).get("flujo") == "sgr" and value != "es":
        raise UserError(
            "El flujo SGR se redacta solo en español: la metodología MGA del DNP y las plantillas de "
            "Minciencias están en español. El idioma del proyecto sigue siendo es."
        )

    for marker in markers:
        path = marker / "config.json"
        data: dict = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except ValueError as error:
                raise UserError(f"{path} no es un JSON válido: {error}") from error
            data = loaded if isinstance(loaded, dict) else {}
        data["lang"] = value
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    if not quiet:
        print(f"Idioma de redacción: {value} ({LANG_LABELS[value]}).")
        print("Las corridas nuevas se redactan en ese idioma; las existentes conservan el idioma con el que "
              "se crearon (fila «idioma» de su _run.md).")
    return 0
