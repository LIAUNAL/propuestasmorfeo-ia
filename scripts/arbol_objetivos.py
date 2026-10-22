#!/usr/bin/env python3
"""Objective-tree figure spec straight from the trees panel (SGR, MGA mirror).

Reads `artefactos/arboles/arbol_objetivos.json` (the file the dashboard trees
panel shows and approves) and writes `redaccion/specs/arbol_objetivos.spec.json`
as a `kind: arbol` spec, so the existing renderer draws it with the same
geometry as the problem tree:

    specific objective (group)  <- converted direct cause
    means (causes of a group)   <- converted indirect causes
    general objective (trunk)   <- converted central problem
    ends (branches) / last end (crown)

No agent rewrites the texts: the figure says exactly what the panel shows.
Then compile it with the run's own pipeline:

    python3 redaccion/scripts/figura.py arbol_objetivos \\
        --spec redaccion/specs/arbol_objetivos.spec.json --project redaccion

Usage: arbol_objetivos.py <RUN_ROOT> [--json]
Exit codes: 0 spec written, 2 missing or incomplete objective tree.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

OBJECTIVES_FILE = Path("artefactos") / "arboles" / "arbol_objetivos.json"
PROBLEM_SPEC = Path("redaccion") / "specs" / "arbol_problemas.spec.json"
OUT_SPEC = Path("redaccion") / "specs" / "arbol_objetivos.spec.json"
# Presentation keys copied from the problem spec so both trees look alike.
SHARED_KEYS = ("fonts", "layout")


def missing_texts(tree: dict) -> list[str]:
    """Same wording as the panel (src/morfeo/core/trees.py)."""
    missing = []
    if not (tree.get("trunk") or {}).get("text"):
        missing.append("objetivo general")
    for g in tree.get("groups") or []:
        if not g.get("objective"):
            missing.append(f"objetivo {g.get('id')}")
        missing += [f"medio {m.get('id')}" for m in g.get("means") or [] if not m.get("text")]
    missing += [f"fin {b.get('id')}" for b in tree.get("branches") or [] if not b.get("text")]
    if not (tree.get("crown") or {}).get("text"):
        missing.append("fin último")
    if not tree.get("groups"):
        missing.append("objetivos específicos")
    if not tree.get("branches"):
        missing.append("fines")
    return missing


def to_spec(tree: dict, problem: dict | None) -> dict:
    spec: dict = {
        "kind": "arbol",
        "header": "ÁRBOL DE OBJETIVOS",
        "caption": tree.get("caption") or "",
        "groups": [
            {
                "id": g["id"],
                "title": g["objective"],
                "causes": [{"id": m["id"], "text": m["text"]} for m in g.get("means") or []],
            }
            for g in tree["groups"]
        ],
        "trunk": {"label": (tree["trunk"].get("label") or "OBJETIVO GENERAL"), "text": tree["trunk"]["text"]},
        "branches": [{"id": b["id"], "text": b["text"]} for b in tree["branches"]],
        "crown": {"label": (tree["crown"].get("label") or "FIN ÚLTIMO"), "text": tree["crown"]["text"]},
    }
    for key in SHARED_KEYS:
        if problem and key in problem:
            spec[key] = problem[key]
    return spec


class InputError(Exception):
    def __init__(self, error: str, **extra) -> None:
        super().__init__(error)
        self.result = {"error": error, **extra}


def _read_json(path: Path, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise InputError(f"{what} no es JSON válido: {exc}") from exc


def build(run: Path) -> dict:
    source = run / OBJECTIVES_FILE
    if not source.is_file():
        raise InputError(f"no existe {OBJECTIVES_FILE.as_posix()}: el investigador lo escribe en la Fase 1b")
    tree = _read_json(source, OBJECTIVES_FILE.as_posix())
    try:
        missing = missing_texts(tree)
    except (AttributeError, TypeError) as exc:
        raise InputError(f"{OBJECTIVES_FILE.as_posix()} no sigue el esquema del panel: {exc!r}") from exc
    if missing:
        raise InputError(f"{OBJECTIVES_FILE.as_posix()} tiene textos sin redactar", missing=missing)
    problem_path = run / PROBLEM_SPEC
    problem = _read_json(problem_path, PROBLEM_SPEC.as_posix()) if problem_path.is_file() else None
    if problem is not None and not isinstance(problem, dict):
        raise InputError(f"{PROBLEM_SPEC.as_posix()} debe ser un objeto JSON (la spec del árbol de problemas)")
    try:
        spec = to_spec(tree, problem)
    except (KeyError, TypeError, AttributeError) as exc:
        raise InputError(f"{OBJECTIVES_FILE.as_posix()} no sigue el esquema del panel: {exc!r}") from exc
    out = run / OUT_SPEC
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"spec": str(out), "groups": len(tree["groups"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_root", type=Path, help="run folder (proposals/<run-id>)")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args(argv)

    try:
        result, code = build(args.run_root.resolve()), 0
    except InputError as exc:
        result, code = exc.result, 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    elif code == 0:
        print(f"SPEC: {result['spec']}")
    else:
        print(f"error: {result['error']}" + (f": {', '.join(result['missing'])}" if "missing" in result else ""),
              file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
