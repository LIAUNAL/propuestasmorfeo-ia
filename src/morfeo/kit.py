"""Kit resolution and location."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .errors import KitError


def get_kit_root() -> Path:
    """Resolve the active kit directory.

    Order of precedence:
    1. Bundled package kit: `src/morfeo/_kit` (or installed wheel directory).
    2. Environment variable: `MORFEO_KIT_ROOT` or `MARCO_KIT_ROOT`.
    3. Source repository root (parent of `src/`).
    """
    pkg_dir = Path(__file__).resolve().parent
    bundled = pkg_dir / "_kit"
    if bundled.is_dir() and (bundled / "kit-manifest.json").is_file():
        return bundled

    env_root = os.environ.get("MORFEO_KIT_ROOT") or os.environ.get("MARCO_KIT_ROOT")
    if env_root:
        candidate = Path(env_root).resolve()
        if candidate.is_dir():
            return candidate

    repo_root = pkg_dir.parent.parent
    if (repo_root / "scripts" / "kit-manifest.json").is_file():
        return repo_root

    raise KitError("Unable to locate a valid Morfeo kit directory.")


def load_kit_manifest(kit_root: Path | None = None) -> dict:
    """Load the kit manifest dictionary from the kit root."""
    if kit_root is None:
        kit_root = get_kit_root()

    candidates = [
        kit_root / "kit-manifest.json",
        kit_root / "scripts" / "kit-manifest.json",
    ]
    for c in candidates:
        if c.is_file():
            with c.open("r", encoding="utf-8") as f:
                return json.load(f)

    raise KitError(f"No kit-manifest.json found under {kit_root}")
