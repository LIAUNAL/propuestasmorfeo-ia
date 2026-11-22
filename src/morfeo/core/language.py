"""Writing language of a Morfeo project and of each of its runs.

The project setting lives in `.morfeo/config.json` (legacy `.marco/config.json`)
as `"lang": "es" | "en"`; a missing file, key or unknown value means `es`. The
SGR flow is Spanish only (DNP/MGA methodology), so an `sgr` project is always
`es`, whatever its config says.

A run records its language when `scripts/init-run.sh` creates it: an English
run gets the row `| idioma | en |` in its `_run.md`, a Spanish run gets no row
(so Spanish runs stay byte-identical to the ones created before the setting
existed). The run's language never follows a later project change: switching
the project to English leaves the runs already written in Spanish in Spanish.

`scripts/language.py` holds the same rules for the kit scripts, which run
without this package; a test keeps both in step.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

VALID_LANGS = ("es", "en")
DEFAULT_LANG = "es"
LANG_LABELS = {"es": "español", "en": "inglés"}
CONFIG_MARKERS = (".morfeo", ".marco")
RUN_LANG_RE = re.compile(r"^\|\s*idioma\s*\|\s*`?([a-z]{2})`?\s*\|", re.MULTILINE)


def config_files(target_dir: Path) -> list[Path]:
    """The project's config.json files, `.morfeo` first, that exist."""
    return [target_dir / marker / "config.json" for marker in CONFIG_MARKERS
            if (target_dir / marker / "config.json").is_file()]


def read_config(target_dir: Path) -> dict:
    """The first readable config.json of the project, or {}."""
    for path in config_files(target_dir):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def lang_of(config: dict) -> str:
    """Writing language a config dict declares: `es` for SGR, unknown or missing values."""
    if config.get("flujo") == "sgr":
        return DEFAULT_LANG
    value = config.get("lang")
    return value if value in VALID_LANGS else DEFAULT_LANG


def read_project_lang(target_dir: Path) -> str:
    return lang_of(read_config(Path(target_dir)))


def read_run_lang(run_root: Path, project_dir: Path | None = None) -> str:
    """Language recorded in the run's `_run.md`; `es` when the run has no row.

    Only a run without `_run.md` (built by hand) falls back to the project
    setting, found in `project_dir` or two levels above the run
    (`<project>/proposals/<run-id>`)."""
    run_root = Path(run_root)
    manifest = run_root / "_run.md"
    project = Path(project_dir) if project_dir is not None else run_root.parent.parent
    if read_config(project).get("flujo") == "sgr":
        return DEFAULT_LANG
    if not manifest.is_file():
        return read_project_lang(project)
    match = RUN_LANG_RE.search(manifest.read_text(encoding="utf-8", errors="replace"))
    if match and match.group(1) in VALID_LANGS:
        return match.group(1)
    return DEFAULT_LANG
