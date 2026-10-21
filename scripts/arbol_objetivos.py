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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_root", type=Path, help="run folder (proposals/<run-id>)")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args(argv)

    run = args.run_root.resolve()
    source = run / OBJECTIVES_FILE
    result: dict
    if not source.is_file():
        result, code = {"error": f"no existe {OBJECTIVES_FILE.as_posix()}: el investigador lo escribe en la Fase 1b"}, 2
    else:
        try:
            tree = json.loads(source.read_text(encoding="utf-8"))
        except ValueError as exc:
            tree, result, code = None, {"error": f"{OBJECTIVES_FILE.as_posix()} no es JSON válido: {exc}"}, 2
        if tree is not None:
            missing = missing_texts(tree)
            if missing:
                result, code = {"error": "el árbol de objetivos tiene textos sin redactar", "missing": missing}, 2
            else:
                problem_path = run / PROBLEM_SPEC
                problem = json.loads(problem_path.read_text(encoding="utf-8")) if problem_path.is_file() else None
                out = run / OUT_SPEC
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(to_spec(tree, problem), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                result, code = {"spec": str(out), "groups": len(tree["groups"])}, 0

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
