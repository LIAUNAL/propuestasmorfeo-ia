#!/usr/bin/env python3
"""split_latex_section.py — thin shim over the external latex-section-splitter skill.

The splitter itself is a **user-level** skill, not part of this repository: it
lives under ``~/.agents/skills/latex-section-splitter/scripts/split_latex.py``.
This shim exists so the pipeline can call it by a stable path from inside a run
(`redaccion/scripts/`) without agents hardcoding a home-relative path, and so a
missing skill fails loudly with an actionable message instead of a traceback.

Resolution is explicit and home-anchored on purpose. An earlier version walked
``Path(__file__).parents[3]``, which pointed above the repository from
``plantilla/scripts/`` and at ``proposals/`` from a run's ``redaccion/scripts/``
— it could never find the skill from either location.

Override with MARCO_LATEX_SPLITTER if the skill lives elsewhere.
"""

import importlib.util
import os
import sys
from pathlib import Path

DEFAULT_SKILL = (
    Path.home() / ".agents" / "skills" / "latex-section-splitter" / "scripts" / "split_latex.py"
)


def _resolve() -> Path:
    override = os.environ.get("MARCO_LATEX_SPLITTER")
    return Path(override).expanduser() if override else DEFAULT_SKILL


def main() -> int:
    skill = _resolve()
    if not skill.is_file():
        print(
            f"error: latex-section-splitter skill not found at {skill}\n"
            "It is a user-level skill, not shipped with this repository. Install it, "
            "or point MARCO_LATEX_SPLITTER at its split_latex.py.",
            file=sys.stderr,
        )
        return 1
    spec = importlib.util.spec_from_file_location("split_latex", skill)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main() or 0


if __name__ == "__main__":
    raise SystemExit(main())
