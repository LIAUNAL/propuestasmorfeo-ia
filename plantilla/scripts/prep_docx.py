#!/usr/bin/env python3
r"""Stage a docx-safe copy of the LaTeX project's main.tex for pandoc conversion.

The project root is the parent of this script's own directory, so it works
unmodified wherever that project lives: `<RUN_ROOT>/redaccion` in the per-run
layout, `<repo>/proposal` in the legacy flat one.

Pandoc's LaTeX reader cannot parse raw `tikzpicture`/`ganttchart`
environments, so this script builds a staging tree that mirrors the project
root but replaces each diagram section (`diag_*.tex`) with a plain
`\includegraphics` stub pointing at a PNG rasterized via `compile_tikz.py`
(reused as-is, via subprocess — kept a pure rasterizer per ADR-3).

§14 Cronograma (`14_cronograma_actividades.tex`) is a special case: Redactor
is the single owner of that section and may emit either a plain `tabular`
(pandoc-safe, copied verbatim) or a `ganttchart`/`tikzpicture` spec (needs
rasterization, same as the other diagrams). This module detects which form
is present before deciding whether to rasterize it.

Usage:
    python3 prep_docx.py --stage <dir>

Requires: pdflatex, pdftoppm in PATH (same as compile_tikz.py).
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
# LaTeX project root = the directory that holds this scripts/ directory. Layout
# independent on purpose: <RUN_ROOT>/redaccion in the per-run layout,
# <repo>/proposal in the legacy flat layout, with no hardcoded directory name.
PROP = HERE.parent
# Same location compile_tikz.py writes to — <project>/sections/figuras/, not
# /tmp (hidden/inconvenient in Finder, OS-specific). Already covered by the
# run folder being gitignored as a whole.
WORK = PROP / "sections" / "figuras"

# diag_<name>.tex -> (compile_tikz name, kind)
DIAGRAM_MAP = {
    "diag_arbol_problemas.tex": ("arbol_problemas", "tikz"),
    "diag_estado_arte.tex": ("estado_arte", "tikz"),
    "diag_metodologico.tex": ("metodologico", "tikz"),
}

# §14 Cronograma: single owner is Redactor (not a diag_*.tex). Only
# rasterize it when it actually contains a diagram env; a plain tabular is
# pandoc-safe and gets copied verbatim.
CRONOGRAMA_FILE = "14_cronograma_actividades.tex"
# La guía ajustada al TDR puede renumerar el cronograma (p. ej. §19), así que
# el archivo se localiza por sufijo y no solo por su nombre en la guía base.
CRONOGRAMA_SUFFIX = "_cronograma_actividades.tex"
_GANTT_ENV_RE = re.compile(r'\\begin\{(ganttchart|tikzpicture)\}')


def cronograma_path(sections_dir: pathlib.Path):
    """Resolve the Cronograma section file, whatever its section number."""
    f = sections_dir / CRONOGRAMA_FILE
    if f.exists():
        return f
    candidates = sorted(sections_dir.glob("*" + CRONOGRAMA_SUFFIX))
    return candidates[0] if candidates else None


def warn(msg: str) -> None:
    print(f"[WARN] {msg}", file=sys.stderr)


def cronograma_has_diagram_env(sections_dir: pathlib.Path) -> bool:
    """Detect whether Redactor's §14 output uses a `ganttchart`/`tikzpicture`
    env (needs rasterization for pandoc) vs. a plain `tabular` (pandoc-safe,
    copy verbatim)."""
    f = cronograma_path(sections_dir)
    if f is None or not f.exists():
        return False
    text = f.read_text(encoding="utf-8")
    return bool(_GANTT_ENV_RE.search(text))


def rasterize_diagrams(sections_dir: pathlib.Path) -> None:
    """Invoke compile_tikz.py for whichever diagrams actually exist in
    `sections_dir`. Only rasterizes what is present (main.tex may not
    reference all diagrams yet at every pipeline stage). §14 Cronograma is
    included only when it contains a diagram env (see
    `cronograma_has_diagram_env`)."""
    args = [
        f"{name}:{kind}"
        for filename, (name, kind) in DIAGRAM_MAP.items()
        if (sections_dir / filename).exists()
    ]
    if cronograma_has_diagram_env(sections_dir):
        args.append("gantt:gantt")
    if not args:
        return
    r = subprocess.run(
        [sys.executable, str(HERE / "compile_tikz.py"), *args],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit("prep_docx: compile_tikz.py failed to rasterize diagrams")


def stage_diagram_image(name: str, stage: pathlib.Path) -> str:
    """Copy the rasterized PNG(s) for `name` into `stage`.

    Gate-fix: glob `fig_<name>-*.png` (never hardcode `-1.png`) and WARN on
    multi-page overflow instead of silently truncating to page 1 — the
    Gantt wrapper uses a fixed paper size and can overflow to page 2 for an
    unusually long schedule.
    """
    pages = sorted(WORK.glob(f"fig_{name}-*.png"))
    if not pages:
        raise SystemExit(f"prep_docx: no rasterized PNG found for '{name}' in {WORK}")
    if len(pages) > 1:
        warn(
            f"diagram '{name}' rasterized to {len(pages)} pages "
            f"({', '.join(p.name for p in pages)}); only page 1 is embedded "
            "in the docx. The diagram likely overflowed its fixed paper size "
            "(e.g. a long Gantt chart) — shorten it or split it manually."
        )
    chosen = pages[0]
    dest_name = f"fig_{name}.png"
    shutil.copy2(chosen, stage / dest_name)
    return dest_name


_FIGURE_ENV_RE = re.compile(r'\\begin\{(?:figure|table)\}.*?\\end\{(?:figure|table)\}', re.DOTALL)
_FIGURE_HEAD_RE = re.compile(r'\\begin\{(?:figure|table)\}[^\n]*\n(\\centering\n)?')
_CAPTION_START_RE = re.compile(r'\\caption\{')


def swap_figure_graphics(text: str, png_name: str) -> str:
    """Replace only the graphics-producing body of the single `figure` env
    in `text` with a plain `\\includegraphics`, preserving `\\begin{figure}`,
    an optional leading `\\centering`, and everything from `\\caption{`
    onward (caption + label + `\\end{figure}`) — so section headers, labels,
    and surrounding prose survive the docx staging swap, and pandoc still
    gets a real caption/label to resolve `\\ref{}` against."""
    fig_m = _FIGURE_ENV_RE.search(text)
    if not fig_m:
        raise SystemExit("prep_docx: no figure environment found to swap graphics into")
    block = fig_m.group(0)
    cap_m = _CAPTION_START_RE.search(block)
    if not cap_m:
        raise SystemExit("prep_docx: figure environment has no \\caption{}")
    head_m = _FIGURE_HEAD_RE.match(block)
    if not head_m:
        raise SystemExit("prep_docx: could not parse \\begin{figure} header")
    new_block = (
        head_m.group(0)
        + f"\\includegraphics[width=\\linewidth]{{{png_name}}}\n"
        + block[cap_m.start():]
    )
    return text[:fig_m.start()] + new_block + text[fig_m.end():]


_CREF_NOUNS = {"fig": "Figura", "sec": "Sección", "tab": "Tabla"}
_CREF_RE = re.compile(r'\\([Cc])ref\{((fig|sec|tab):[^}]+)\}')


def resolve_cref(text: str) -> str:
    """Rewrite cleveref `\\Cref{}`/`\\cref{}` into `<Noun>~\\ref{}` before
    pandoc runs — pandoc's LaTeX reader resolves plain `\\ref{}` to a bare
    number but does not know cleveref, so `\\Cref{fig:x}` would otherwise
    survive as a raw, unresolved label or a bare number with no noun."""
    def repl(m):
        cap, label, prefix = m.groups()
        noun = _CREF_NOUNS[prefix]
        if cap == "c":
            noun = noun.lower()
        return f"{noun}~\\ref{{{label}}}"
    return _CREF_RE.sub(repl, text)


_RESIZEBOX_DIAG_RE = re.compile(
    r'\\resizebox\{[^{}]*\}\{[^{}]*\}\{(\\input\{sections/diag_[a-zA-Z_]+\})\}'
)


def strip_resizebox_diagrams(text: str) -> str:
    """Unwrap `\\resizebox{...}{...}{\\input{sections/diag_*}}` in main.tex
    down to the bare `\\input{...}`.

    Pandoc's LaTeX reader has no built-in understanding of `\\resizebox` and
    silently drops its whole argument (verified empirically: no warning, no
    error — the macro and everything inside it is just skipped). After
    diagram staging, that argument is a plain `\\includegraphics{fig_*.png}`,
    so leaving `\\resizebox` in place means the diagram images for the árbol
    de problemas, estado del arte, and metodológico figures never reach the
    docx media stream even though the PNGs are staged correctly. The PDF
    build never goes through this staging tree, so removing the wrapper
    here does not affect print scaling in main.pdf."""
    return _RESIZEBOX_DIAG_RE.sub(lambda m: m.group(1), text)


def build_stage(stage: pathlib.Path) -> pathlib.Path:
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "sections").mkdir(parents=True, exist_ok=True)

    main_tex = PROP / "main.tex"
    refs_bib = PROP / "refs.bib"
    logos_dir = PROP / "logos"
    sections_dir = PROP / "sections"

    if not main_tex.exists():
        raise SystemExit(f"prep_docx: {main_tex} does not exist — compile the PDF first")

    shutil.copy2(main_tex, stage / "main.tex")
    (stage / "main.tex").write_text(
        strip_resizebox_diagrams((stage / "main.tex").read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    if refs_bib.exists():
        shutil.copy2(refs_bib, stage / "refs.bib")
    if logos_dir.exists():
        shutil.copytree(logos_dir, stage / "logos", dirs_exist_ok=True)

    if sections_dir.exists():
        rasterize_diagrams(sections_dir)
        cronograma_is_diagram = cronograma_has_diagram_env(sections_dir)
        for f in sorted(sections_dir.glob("*.tex")):
            if f.name in DIAGRAM_MAP:
                name, _kind = DIAGRAM_MAP[f.name]
                png_name = stage_diagram_image(name, stage)
                (stage / "sections" / f.name).write_text(
                    f"\\includegraphics[width=\\linewidth]{{{png_name}}}\n",
                    encoding="utf-8",
                )
            elif f.name.endswith(CRONOGRAMA_SUFFIX) and cronograma_is_diagram:
                png_name = stage_diagram_image("gantt", stage)
                original = f.read_text(encoding="utf-8")
                (stage / "sections" / f.name).write_text(
                    swap_figure_graphics(original, png_name), encoding="utf-8",
                )
            else:
                shutil.copy2(f, stage / "sections" / f.name)

    for staged_tex in [stage / "main.tex", *sorted((stage / "sections").glob("*.tex"))]:
        staged_tex.write_text(resolve_cref(staged_tex.read_text(encoding="utf-8")), encoding="utf-8")

    return stage / "main.tex"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", required=True,
        help="staging directory to build the docx-safe tex tree in",
    )
    args = parser.parse_args()

    staged_main = build_stage(pathlib.Path(args.stage))
    print(staged_main)


if __name__ == "__main__":
    main()
