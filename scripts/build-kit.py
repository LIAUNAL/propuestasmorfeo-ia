#!/usr/bin/env python3
"""Assemble the bundled kit at src/morfeo/_kit for the PyPI wheel.

`--check` compares the committed kit with its sources (content and executable
bit, plus stray files) and exits non-zero on drift without rewriting anything.
"""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
KIT = SRC / "morfeo" / "_kit"
MANIFEST = ROOT / "scripts" / "kit-manifest.json"
KIT_MANIFEST_NAME = "kit-manifest.json"


def load_manifest(path: Path = MANIFEST) -> dict:
    if not path.is_file():
        raise SystemExit(f"error: kit manifest not found at {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not data.get("kit_paths"):
        raise SystemExit("error: no kit_paths found in kit-manifest.json")
    return data


def _source_files(root: Path, manifest: dict) -> dict[str, Path]:
    """Map every kit-relative file path to its source file."""
    files: dict[str, Path] = {}
    for rel in manifest["kit_paths"]:
        src = root / rel
        if src.is_file():
            files[rel] = src
        elif src.is_dir():
            for item in sorted(src.rglob("*")):
                if item.is_file():
                    files[item.relative_to(root).as_posix()] = item
    return files


def _executable(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_IXUSR)


def assemble(root: Path = ROOT, kit: Path = KIT, manifest: dict | None = None, quiet: bool = False) -> None:
    manifest = manifest if manifest is not None else load_manifest()

    if kit.exists():
        shutil.rmtree(kit)
    kit.mkdir(parents=True, exist_ok=True)

    for rel in manifest["kit_paths"]:
        if not (root / rel).exists() and not quiet:
            print(f"warning: kit file missing from repo: {rel}", file=sys.stderr)

    copied = 0
    for rel, src in _source_files(root, manifest).items():
        dst = kit / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        # copy2 keeps the executable bit, which copyfile dropped
        shutil.copy2(src, dst)
        copied += 1

    (kit / KIT_MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if root == ROOT and MANIFEST.is_file():
        shutil.copyfile(MANIFEST, kit / KIT_MANIFEST_NAME)

    if not quiet:
        print(f"kit assembled: {copied} files copied to {kit}")


def check(root: Path = ROOT, kit: Path = KIT, manifest: dict | None = None) -> list[str]:
    """Return one line per drift between the sources and the assembled kit."""
    manifest = manifest if manifest is not None else load_manifest()
    problems: list[str] = []
    sources = _source_files(root, manifest)

    for rel, src in sources.items():
        dst = kit / rel
        if not dst.is_file():
            problems.append(f"missing in kit: {rel}")
            continue
        if src.read_bytes() != dst.read_bytes():
            problems.append(f"content differs: {rel}")
        if _executable(src) != _executable(dst):
            problems.append(f"executable bit differs: {rel}")

    if kit.is_dir():
        for item in sorted(kit.rglob("*")):
            rel = item.relative_to(kit).as_posix()
            if item.is_file() and rel != KIT_MANIFEST_NAME and rel not in sources and "__pycache__" not in rel:
                problems.append(f"stray file in kit: {rel}")

    if root == ROOT:
        kit_manifest = kit / KIT_MANIFEST_NAME
        if not kit_manifest.is_file() or kit_manifest.read_bytes() != MANIFEST.read_bytes():
            problems.append(f"content differs: {KIT_MANIFEST_NAME}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="suppress output")
    parser.add_argument("--check", action="store_true", help="report drift without rewriting the kit")
    args = parser.parse_args()
    if args.check:
        problems = check()
        for line in problems:
            print(line)
        if not problems and not args.quiet:
            print("kit in step with its sources")
        return 1 if problems else 0
    assemble(quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
