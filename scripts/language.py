#!/usr/bin/env python3
"""Writing language of the project and of a run, for the kit scripts.

    language.py project [DIR]       print the project's language (es | en)
    language.py run [RUN_ROOT]      print the run's language (es | en)

The project setting is `"lang"` in `.morfeo/config.json` (legacy
`.marco/config.json`), found from DIR upwards; `es` when missing or unknown,
and always `es` in the SGR flow (DNP/MGA, Spanish only). A run records its
language at creation: `scripts/init-run.sh` writes the row `| idioma | en |`
into an English run's `_run.md` and no row into a Spanish one, so a run with a
`_run.md` and no row is Spanish and a later project change never mixes two
languages inside one run. Only a run without `_run.md` falls back to the
project setting.

Standard library only; `src/morfeo/core/language.py` holds the same rules for
the package and a test keeps both in step. RUN_ROOT defaults to the run named
in proposals/.current-run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VALID_LANGS = ("es", "en")
DEFAULT_LANG = "es"
CONFIG_MARKERS = (".morfeo", ".marco")
RUN_LANG_RE = re.compile(r"^\|\s*idioma\s*\|\s*`?([a-z]{2})`?\s*\|", re.MULTILINE)


def find_config(start: Path) -> dict:
    """The first readable config.json from `start` upwards, or {}."""
    try:
        folder = Path(start).resolve()
    except OSError:
        return {}
    for candidate in (folder, *folder.parents):
        for marker in CONFIG_MARKERS:
            path = candidate / marker / "config.json"
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                return {}
            return data if isinstance(data, dict) else {}
    return {}


def lang_of(config: dict) -> str:
    if config.get("flujo") == "sgr":
        return DEFAULT_LANG
    value = config.get("lang")
    return value if value in VALID_LANGS else DEFAULT_LANG


def project_lang(start: Path) -> str:
    return lang_of(find_config(start))


def run_lang(run_root: Path) -> str:
    """The language recorded in the run's `_run.md` (see the module docstring)."""
    run_root = Path(run_root)
    config = find_config(run_root)
    if config.get("flujo") == "sgr":
        return DEFAULT_LANG
    manifest = run_root / "_run.md"
    if not manifest.is_file():
        return lang_of(config)
    match = RUN_LANG_RE.search(manifest.read_text(encoding="utf-8", errors="replace"))
    if match and match.group(1) in VALID_LANGS:
        return match.group(1)
    return DEFAULT_LANG


def _active_run() -> Path:
    pointer = Path("proposals/.current-run")
    if not pointer.is_file():
        raise SystemExit("error: no RUN_ROOT given and proposals/.current-run does not exist")
    return Path("proposals", pointer.read_text(encoding="utf-8").strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    project = commands.add_parser("project", help="print the project's writing language")
    project.add_argument("dir", nargs="?", default=".")
    run = commands.add_parser("run", help="print the run's writing language")
    run.add_argument("run_root", nargs="?")
    args = parser.parse_args(argv)
    if args.command == "project":
        print(project_lang(Path(args.dir)))
    else:
        print(run_lang(Path(args.run_root) if args.run_root else _active_run()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
