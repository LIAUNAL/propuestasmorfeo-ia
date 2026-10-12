#!/usr/bin/env python3
"""Assemble the bundled kit at src/morfeo/_kit for the PyPI wheel."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
KIT = SRC / "morfeo" / "_kit"
MANIFEST = ROOT / "scripts" / "kit-manifest.json"


def assemble(quiet: bool = False) -> None:
    if not MANIFEST.is_file():
        raise SystemExit(f"error: kit manifest not found at {MANIFEST}")

    with MANIFEST.open("r", encoding="utf-8") as f:
        data = json.load(f)

    kit_paths = data.get("kit_paths", [])
    if not kit_paths:
        raise SystemExit("error: no kit_paths found in kit-manifest.json")

    if KIT.exists():
        shutil.rmtree(KIT)
    KIT.mkdir(parents=True, exist_ok=True)

    copied = 0
    for rel in kit_paths:
        src = ROOT / rel
        if not src.exists():
            if not quiet:
                print(f"warning: kit file missing from repo: {rel}", file=sys.stderr)
            continue
        dst = KIT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            shutil.copyfile(src, dst)
            copied += 1
        elif src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            copied += 1

    # Copy manifest into kit
    shutil.copyfile(MANIFEST, KIT / "kit-manifest.json")

    if not quiet:
        print(f"kit assembled: {copied} entries copied to {KIT}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="suppress output")
    args = parser.parse_args()
    assemble(quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
