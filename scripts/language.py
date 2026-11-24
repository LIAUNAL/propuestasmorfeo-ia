#!/usr/bin/env python3
"""Writing language of the project and of a run, for the kit scripts.

    language.py project [DIR]       print the project's language (es | en)
    language.py run [RUN_ROOT]      print the run's language (es | en)
    language.py localize --lang en FILE...
                                    rewrite a freshly seeded main.tex or
                                    datos_proyecto.tex in that language

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


# --- LaTeX template ------------------------------------------------------------
# plantilla/main.tex and datos_proyecto.tex are Spanish. init-run.sh seeds a new
# English run with these replacements applied once; a Spanish run gets the files
# untouched. Every anchor must appear exactly once, so a template edit that drops
# one fails loudly here (and in tests/test_plantilla_main.py) instead of leaving
# a half-Spanish document.
MAIN_TEX_EN = (
    (r"\usepackage[spanish,es-noindentfirst]{babel}", r"\usepackage[english]{babel}"),
    ("% --- Referencias cruzadas en español ----------------------------------------",
     "% --- Referencias cruzadas en inglés (run language: en) ----------------------"),
    (r"\crefname{section}{sección}{secciones}", r"\crefname{section}{section}{sections}"),
    (r"\crefname{figure}{figura}{figuras}", r"\crefname{figure}{figure}{figures}"),
    (r"\crefname{table}{tabla}{tablas}", r"\crefname{table}{table}{tables}"),
    (r"\crefname{equation}{ecuación}{ecuaciones}", r"\crefname{equation}{equation}{equations}"),
    ('% --- Captions de tabla: "Tabla", nunca "Cuadro" (babel exige el hook) -------',
     '% --- Captions de tabla: "Table" (babel english; el hook lo deja explícito) ---'),
    (r"\addto\captionsspanish{\renewcommand{\tablename}{Tabla}}",
     r"\addto\captionsenglish{\renewcommand{\tablename}{Table}}"),
    (r"\caption{\textbf{[Falta caption: #1]}}", r"\caption{\textbf{[Missing caption: #1]}}"),
    (r"\section*{Referencias}", r"\section*{References}"),
    ("Investigador principal: \\InvestigadorPrincipal", "Principal investigator: \\InvestigadorPrincipal"),
)
COVER_EN = (
    ("% Datos de portada de la propuesta. main.tex los usa en el bloque de título;\n"
     "% el título no se repite en ninguna sección del cuerpo. Reemplazar cada\n"
     '% "[Por definir: ...]": scripts/check_run.py marca los que queden.',
     "% Cover data of the proposal. main.tex uses them in the title block; the\n"
     "% title is never repeated in a body section. Replace each\n"
     '% "[To be defined: ...]": scripts/check_run.py reports the ones left.'),
    ("[Por definir: título del proyecto]", "[To be defined: project title]"),
    ("[Por definir: investigador principal]", "[To be defined: principal investigator]"),
    ("[Por definir: grupo, laboratorio, facultad y sede]", "[To be defined: group, laboratory, faculty and campus]"),
)


def _replace_all(text: str, pairs, what: str) -> str:
    for old, new in pairs:
        if text.count(old) != 1:
            raise ValueError(f"{what}: expected exactly one {old!r}, found {text.count(old)}")
        text = text.replace(old, new)
    return text


def localize_main_tex(text: str, lang: str) -> str:
    """main.tex in `lang`: the template itself for Spanish."""
    return text if lang != "en" else _replace_all(text, MAIN_TEX_EN, "main.tex")


def localize_cover(text: str, lang: str) -> str:
    """datos_proyecto.tex in `lang`: the template itself for Spanish."""
    return text if lang != "en" else _replace_all(text, COVER_EN, "datos_proyecto.tex")


_BABEL_RE = re.compile(r"\\usepackage\[([^\]]*)\]\{babel\}")
_BABEL_FOR = {"es": r"\usepackage[spanish,es-noindentfirst]{babel}", "en": r"\usepackage[english]{babel}"}


def switch_main_tex(text: str, source: str, target: str) -> str:
    """A run's main.tex moved from `source` to `target` for a translation
    (scripts/traducir.py build). Unlike localize_main_tex it starts from a
    run's own main.tex, which may predate the template or have been edited:
    each anchor of MAIN_TEX_EN is swapped where it appears and skipped where it
    does not. Only the babel line is required; a babel line with other options
    is replaced whole."""
    if source == target:
        return text
    if (source, target) == ("es", "en"):
        pairs = MAIN_TEX_EN
    elif (source, target) == ("en", "es"):
        pairs = tuple((new, old) for old, new in MAIN_TEX_EN)
    else:
        raise ValueError(f"unsupported language pair {source!r} -> {target!r}")
    babel_from, babel_to = pairs[0]
    if text.count(babel_from) != 1:
        lines = [m for m in _BABEL_RE.finditer(text) if source == "es" and "spanish" in m.group(1)
                 or source == "en" and "english" in m.group(1) and "spanish" not in m.group(1)]
        if len(lines) != 1:
            raise ValueError(f"expected one babel line declaring the source language {source!r}, "
                             f"found {len(lines)}")
        text = text[:lines[0].start()] + _BABEL_FOR[target] + text[lines[0].end():]
    for old, new in pairs:
        text = text.replace(old, new)
    return text


def localize_files(paths: list[Path], lang: str) -> None:
    for path in paths:
        localize = localize_cover if path.name == "datos_proyecto.tex" else localize_main_tex
        path.write_text(localize(path.read_text(encoding="utf-8"), lang), encoding="utf-8")


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
    localize = commands.add_parser("localize", help="rewrite freshly seeded main.tex / datos_proyecto.tex in LANG")
    localize.add_argument("--lang", choices=VALID_LANGS, required=True)
    localize.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    if args.command == "project":
        print(project_lang(Path(args.dir)))
    elif args.command == "localize":
        try:
            localize_files(args.files, args.lang)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    else:
        print(run_lang(Path(args.run_root) if args.run_root else _active_run()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
