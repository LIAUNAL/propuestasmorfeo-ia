#!/usr/bin/env python3
"""Assemble redaccion/main.tex in the chapter order the TDR fixes.

When the call mandates its own chapters (e.g. the 30 chapters of the SGR
"Anexo 2, Documento técnico", whose titles must be kept verbatim), the base
order of plantilla/main.tex cannot hold them. This script keeps the template
preamble and cover, and rewrites only the body from
`artefactos/estructura_tdr.json`:

    {"fuente": "Anexo 2 (Documento técnico)",
     "capitulos": [{"numero": 1, "titulo": "<verbatim TDR title>",
                    "archivos": ["tdr01_identificacion", "diag_arbol_problemas", ...]}]}

`archivos` are names under redaccion/sections/ without `.tex`; `diag_*` go in
through \\DiagramaSiExiste, the rest through \\SeccionSiExiste, so a file that
does not exist yet prints nothing. `\\setcounter{section}{1}` is dropped: each
chapter opens with exactly one numbered \\section, so LaTeX prints the TDR
number. A file listed in two chapters is included once, at its first place.

`--from-guide` bootstraps the structure from the chapter table of
`artefactos/guia_ajustada_TDR.md` (chapter number in the first column,
backticked `<name>.tex` files in the last one) with `titulo: null`; the
dispatcher then fills the verbatim titles.

The body carries the structure hash, which scripts/check_run.py compares to
flag a main.tex assembled from an older structure.

Usage: ensamblar_main.py <RUN_ROOT> [--from-guide] [--json]
Exit codes: 0 written (or already current), 2 missing/invalid input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

STRUCTURE = Path("artefactos") / "estructura_tdr.json"
GUIDE = Path("artefactos") / "guia_ajustada_TDR.md"
MAIN = Path("redaccion") / "main.tex"
COVER_END = r"\thispagestyle{fancy}"
HASH_PREFIX = "% estructura_tdr sha256: "
NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
ROW_RE = re.compile(r"^\|\s*(\d+)\b[^|]*\|")
FILE_RE = re.compile(r"`([A-Za-z0-9_]+)\.tex`")


class InputError(Exception):
    pass


def structure_hash(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def from_guide(text: str) -> dict:
    """Chapters from the adjusted guide's table; rows sharing a number merge."""
    chapters: dict[int, list[str]] = {}
    for line in text.splitlines():
        match = ROW_RE.match(line.strip())
        if not match:
            continue
        files = FILE_RE.findall(line.strip().rstrip("|").rsplit("|", 1)[-1])
        bucket = chapters.setdefault(int(match.group(1)), [])
        bucket.extend(f for f in files if f not in bucket)
    if not chapters:
        raise InputError(f"{GUIDE.as_posix()} no trae la tabla de capítulos (| N | ... | `archivo.tex` |)")
    return {
        "fuente": f"tabla de {GUIDE.as_posix()}",
        "capitulos": [{"numero": n, "titulo": None, "archivos": files} for n, files in sorted(chapters.items())],
    }


def validate(data: dict) -> list[dict]:
    chapters = data.get("capitulos") if isinstance(data, dict) else None
    if not isinstance(chapters, list) or not chapters:
        raise InputError(f"{STRUCTURE.as_posix()} necesita una lista 'capitulos' no vacía")
    for chapter in chapters:
        if not isinstance(chapter, dict) or not isinstance(chapter.get("numero"), int):
            raise InputError(f"cada capítulo necesita 'numero' entero: {chapter!r}")
        files = chapter.get("archivos")
        if not isinstance(files, list):
            raise InputError(f"el capítulo {chapter['numero']} necesita una lista 'archivos'")
        for name in files:
            if not isinstance(name, str) or not NAME_RE.match(name):
                raise InputError(f"nombre de archivo inválido en el capítulo {chapter['numero']}: {name!r} "
                                 "(solo letras, dígitos y _, sin ruta ni .tex)")
    return chapters


def body(data: dict) -> str:
    lines = [
        "",
        "% --- Cuerpo en el orden de capítulos del TDR -----------------------------------",
        "% GENERADO por scripts/ensamblar_main.py desde artefactos/estructura_tdr.json.",
        "% No editar a mano: cambia la estructura y vuelve a correr el script. Sin",
        "% \\setcounter: cada capítulo abre con un único \\section numerado.",
        f"{HASH_PREFIX}{structure_hash(data)}",
    ]
    seen: set[str] = set()
    for chapter in data["capitulos"]:
        title = chapter.get("titulo") or "(título pendiente)"
        lines += ["", f"% Cap. {chapter['numero']}: {title}"]
        for name in chapter["archivos"]:
            if name in seen:
                continue
            seen.add(name)
            macro = "DiagramaSiExiste" if name.startswith("diag_") else "SeccionSiExiste"
            lines.append(f"\\{macro}{{{name}}}")
    lines += ["", r"\end{document}", ""]
    return "\n".join(lines)


def assemble(run: Path, use_guide: bool) -> dict:
    structure_path = run / STRUCTURE
    created = False
    if structure_path.is_file():
        try:
            data = json.loads(structure_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise InputError(f"{STRUCTURE.as_posix()} no es JSON válido: {exc}") from exc
    elif use_guide and (run / GUIDE).is_file():
        data = from_guide((run / GUIDE).read_text(encoding="utf-8", errors="replace"))
        created = True
    else:
        raise InputError(f"no existe {STRUCTURE.as_posix()} (usa --from-guide para derivarlo de {GUIDE.as_posix()})")
    validate(data)

    main_path = run / MAIN
    if not main_path.is_file():
        raise InputError(f"no existe {MAIN.as_posix()}")
    current = main_path.read_text(encoding="utf-8")
    cut = current.find(COVER_END)
    if cut < 0:
        raise InputError(f"{MAIN.as_posix()} no tiene la portada de la plantilla ({COVER_END})")
    new = current[: cut + len(COVER_END)] + "\n" + body(data)

    if created:
        structure_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    changed = new != current
    if changed:
        prev = main_path.with_name("main.tex.prev")
        if HASH_PREFIX not in current or not prev.exists():
            prev.write_text(current, encoding="utf-8")
        main_path.write_text(new, encoding="utf-8")
    return {"main": str(main_path), "capitulos": len(data["capitulos"]), "changed": changed,
            "estructura_creada": created, "hash": structure_hash(data),
            "titulos_pendientes": [c["numero"] for c in data["capitulos"] if not c.get("titulo")]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_root", type=Path, help="run folder (proposals/<run-id>)")
    parser.add_argument("--from-guide", action="store_true",
                        help=f"derive {STRUCTURE.as_posix()} from {GUIDE.as_posix()} when it is missing")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args(argv)
    try:
        result = assemble(args.run_root.resolve(), args.from_guide)
    except InputError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False) if args.json else f"error: {exc}",
              file=sys.stdout if args.json else sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"main.tex: {result['main']} ({result['capitulos']} capítulos, "
              f"{'actualizado' if result['changed'] else 'sin cambios'})")
        if result["titulos_pendientes"]:
            print(f"títulos pendientes en {STRUCTURE.as_posix()}: capítulos {result['titulos_pendientes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
