#!/usr/bin/env python3
"""Build standalone wrapper for a diagram source, compile, and render PNG + SVG.

Usage:
    python3 compile_tikz.py arbol_problemas:tikz estado_arte:tikz metodologico:tikz gantt:gantt

For kind "tikz", looks for diag_<name>.tex under <project>/sections/. For kind
"gantt", the source is instead the Redactor's real §14 output,
`<project>/sections/14_cronograma_actividades.tex` — there is no standalone
diag_gantt.tex (single-owner fix: Disenador-TikZ does not produce a separate
Gantt file; Redactor owns §14 inline, as either a `tabular`+`tikz` table or a
`ganttchart` spec). `<project>` is always the parent of this script's own
directory, so the script works unmodified wherever the LaTeX project lives:
`<RUN_ROOT>/redaccion` in the per-run layout, `<repo>/proposal` in the legacy
flat one. All intermediate files (.tex wrappers, .pdf, .png, .svg, .log) go
under `<project>/sections/figuras/` (see WORK below and "Output location").

Every diagram is rendered to BOTH `fig_<name>-1.png` (raster, for the
compiled PDF/DOCX) and `fig_<name>.svg` (vector, for easier visualization —
zoom without loss, Obsidian/browser preview), plus a compact
`fig_<name>-preview.png` (longest side 1400 px) for the model-assisted visual
review. The SVG and the preview come from the same intermediate PDF as the PNG
via `pdftocairo -svg` / `pdftoppm -scale-to`, no second LaTeX compile. This
applies to every diagram (árbol de problemas, mapa de estado del arte —que
puede entregarse partido en `estado_arte_a` y `estado_arte_b` para que cada
mitad quepa a tamaño natural en A4—, diagrama metodológico y Gantt de §14) and
is runtime-agnostic (every supported runtime calls this same script).

Requires: pdflatex, pdftoppm, pdftocairo in PATH (all three ship with a
standard poppler install alongside pdftoppm, already a prerequisite).

Output location: `<project>/sections/figuras/`, alongside the `.tex` section
sources (NOT `/tmp` — a hidden/inconvenient path in Finder and most file
managers, and one that differs across machines). This directory is per-run
scratch just like the rest of `<project>/sections/`: gitignored with the whole
run folder, discarded with it, and identical across runtimes since every
runtime resolves it relative to this script's own location, not an OS-specific
temp directory.
"""
import sys, subprocess, re, pathlib

# LaTeX project root = the directory that holds this scripts/ directory. Layout
# independent on purpose: it resolves to <RUN_ROOT>/redaccion in the per-run
# layout and to <repo>/proposal in the legacy flat layout, with no hardcoded
# directory name and no assumption about how deep the run folder sits.
HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent
WORK = PROJ / "sections" / "figuras"
WORK.mkdir(parents=True, exist_ok=True)

# Overfull-hbox detection (anchored to the literal `Overfull \hbox` prefix
# only): matches ONLY the pdflatex header line that announces horizontal
# overflow, e.g. "Overfull \hbox (15.03pt too wide) in paragraph at lines
# 45--47" or "...detected at line 45". This structurally REJECTS
# `Underfull \hbox (badness N)` lines (different literal prefix, no "too
# wide") and never scans the discretionary-hyphen content lines pdflatex
# echoes immediately AFTER an Overfull header (e.g. "me-mo-ria") — those are
# separate lines this regex is never applied to in a hyphen-matching way,
# since we only ever match the header line itself.
OVERFULL_RE = re.compile(
    r'^Overfull \\hbox \((\d+(?:\.\d+)?)pt too wide\)'
    r'(?:.*?at lines (\d+)--(\d+)| at line (\d+))?',
    re.MULTILINE,
)


def _diag_line(wrapper_line, preamble_offset, d0):
    """Map a 1-based line number inside the compiled wrapper back to the
    corresponding 1-based line inside the real source file. Returns None
    (never a fabricated guess) when any input is unavailable."""
    if wrapper_line is None or preamble_offset is None or d0 is None:
        return None
    return d0 + wrapper_line - preamble_offset - 1


def _scan_overfull(log_text, preamble_offset, d0):
    """Scan a decoded pdflatex log for Overfull \\hbox occurrences.

    Returns (count, first_pt, first_diag_line): count of matches (may be 0),
    the first match's "...pt too wide" value (str, or None if count == 0),
    and the first match's mapped source line (int, or None when the log
    message carried no at-line(s) info, or when preamble_offset/d0 are
    unavailable for this kind).
    """
    count = 0
    first_pt = None
    first_wrapper_line = None
    for match in OVERFULL_RE.finditer(log_text):
        count += 1
        if first_pt is None:
            first_pt = match.group(1)
            if match.group(2) is not None:
                first_wrapper_line = int(match.group(2))
            elif match.group(4) is not None:
                first_wrapper_line = int(match.group(4))
    first_diag_line = _diag_line(first_wrapper_line, preamble_offset, d0)
    return count, first_pt, first_diag_line


def build(name, kind):
    if kind == "gantt":
        # §14 Cronograma is authored inline by Redactor, not as a standalone
        # diag_gantt.tex — source from the real section file.
        src = PROJ / "sections" / "14_cronograma_actividades.tex"
        if not src.exists():
            # La guía ajustada al TDR puede renumerar el cronograma (p. ej. §19
            # cuando el TDR añade secciones antes de él). Aceptar cualquier
            # <NN>_cronograma_actividades.tex sin romper el caso §14.
            candidates = sorted(
                (PROJ / "sections").glob("*_cronograma_actividades.tex")
            )
            if candidates:
                src = candidates[0]
    else:
        src = PROJ / "sections" / f"diag_{name}.tex"
    if not src.exists():
        raise SystemExit(
            f"no existe {src}. Los diagramas/secciones se generan por cada corrida de "
            "/propuesta (disenador-tikz o redactor); ejecuta /propuesta hasta esa fase antes de compilar figuras."
        )
    text = src.read_text(encoding='utf-8')

    if kind == "tikz":
        # extract the first tikzpicture
        m = re.search(r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}', text, flags=re.DOTALL)
        if not m:
            raise SystemExit(f"no tikzpicture found in {src}")
        body = m.group(0)
        # Source-line mapping (design ADR-5): D0 = 1-based line of
        # \begin{tikzpicture} inside the real diag_<name>.tex; preamble_offset
        # is computed below from the actual wrapper text just built, never
        # hardcoded, so it survives future preamble edits.
        d0 = text[:m.start()].count("\n") + 1
        wrapper = WORK / f"wrap_{name}.tex"
        wrapper_text = (
            "\\documentclass[tikz,border=10pt]{standalone}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage[T1]{fontenc}\n"
            "\\usepackage[spanish,es-tabla,es-noshorthands]{babel}\n"
            "\\usepackage{amssymb}\n"
            "\\usetikzlibrary{positioning,arrows.meta,shapes.geometric,calc,fit,backgrounds}\n"
            "\\definecolor{azulUNAL}{HTML}{0066B3}\n"
            "\\definecolor{grisLabIA}{HTML}{666666}\n"
            "\\definecolor{verdeGCPDS}{HTML}{2E8B57}\n"
            "\\definecolor{rojoLimitante}{HTML}{C0392B}\n"
            # No mid-word hyphenation in diagram node text (guiaProyectosIA_Agente.md,
            # "Convenciones técnicas de LaTeX" > hyphenation rule): a broken word inside
            # a fixed-width TikZ node reads as a layout defect, not normal prose wrapping.
            "\\hyphenpenalty=10000\n"
            "\\exhyphenpenalty=10000\n"
            "\\begin{document}\n"
            + body + "\n"
            + "\\end{document}\n"
        )
        preamble_offset = wrapper_text[
            :wrapper_text.index("\\begin{document}\n") + len("\\begin{document}\n")
        ].count("\n")
        wrapper.write_text(wrapper_text, encoding='utf-8')
    elif kind == "gantt":
        # extract the ganttchart block. redactor.md permits two forms for §14:
        #   (a) a bare \begin{ganttchart}...\end{ganttchart}, or
        #   (b) a ganttchart wrapped in \begin{tikzpicture}...\end{tikzpicture}
        #       (e.g. alongside a legend drawn with tikz).
        # \end{ganttchart} is the authoritative close marker for the chart
        # body itself; we only extend the extraction out to a wrapping
        # \end{tikzpicture} when a matching \begin{tikzpicture} is actually
        # present around the ganttchart, so bare ganttchart blocks don't
        # crash looking for a tikzpicture wrapper that was never promised.
        idx = text.find(r'\begin{ganttchart}')
        if idx < 0:
            raise SystemExit(f"could not find ganttchart in {src}")
        idx_gc_end = text.find(r'\end{ganttchart}', idx)
        if idx_gc_end < 0:
            raise SystemExit(f"could not find matching \\end{{ganttchart}} in {src}")
        end = idx_gc_end + len(r'\end{ganttchart}')

        # Optional wrapping tikzpicture: a \begin{tikzpicture} before the
        # ganttchart that is not already closed before it starts, and whose
        # matching \end{tikzpicture} appears after the ganttchart closes.
        tikz_begin = text.rfind(r'\begin{tikzpicture}', 0, idx)
        if tikz_begin >= 0:
            tikz_begin_close = text.find(r'\end{tikzpicture}', tikz_begin, idx)
            if tikz_begin_close < 0:
                tikz_end = text.find(r'\end{tikzpicture}', end)
                if tikz_end >= 0:
                    idx = tikz_begin
                    end = tikz_end + len(r'\end{tikzpicture}')

        body = text[idx:end]
        # Line-mapping for gantt is best-effort/non-critical (design ADR-5):
        # no diag_<name>.tex file, no revisor-figuras loop consumes it, but
        # computing it is cheap and harmless since idx is already the real
        # extraction start.
        d0 = text[:idx].count("\n") + 1
        # Use article class with explicit paper size to avoid standalone bbox detection issues
        wrapper = WORK / f"wrap_{name}.tex"
        wrapper_text = (
            "\\documentclass[11pt]{article}\n"
            "\\usepackage[paperwidth=17cm,paperheight=24cm,margin=0.5cm]{geometry}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage[T1]{fontenc}\n"
            "\\usepackage[spanish,es-tabla,es-noshorthands]{babel}\n"
            "\\usepackage{amssymb}\n"
            "\\usepackage{tikz}\n"
            "\\usepackage{pgfgantt}\n"
            "\\usetikzlibrary{positioning,arrows.meta,shapes.geometric,calc,fit,backgrounds}\n"
            "\\definecolor{azulUNAL}{HTML}{0066B3}\n"
            "\\definecolor{grisLabIA}{HTML}{666666}\n"
            "\\definecolor{verdeGCPDS}{HTML}{2E8B57}\n"
            "\\definecolor{rojoLimitante}{HTML}{C0392B}\n"
            "\\pagestyle{empty}\n"
            # No mid-word hyphenation in Gantt labels either — same rationale as the
            # tikz wrapper above.
            "\\hyphenpenalty=10000\n"
            "\\exhyphenpenalty=10000\n"
            "\\begin{document}\n"
            "\\centering\n"
            + body + "\n"
            + "\\end{document}\n"
        )
        preamble_offset = wrapper_text[
            :wrapper_text.index("\\begin{document}\n") + len("\\begin{document}\n")
        ].count("\n")
        wrapper.write_text(wrapper_text, encoding='utf-8')
    else:
        raise SystemExit(f"unknown kind: {kind}")

    log = WORK / f"log_{name}.txt"
    r = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
         "-output-directory", str(WORK), str(wrapper)],
        capture_output=True
    )
    # write log with safe decoding
    log.write_bytes(r.stdout + r.stderr)
    if r.returncode != 0:
        print(f"COMPILE FAILED for {name}, see {log}")
        sys.exit(1)
    # Overfull-hbox parse runs ONLY on this success branch — the hard-failure
    # sys.exit(1) above is completely untouched by everything below.
    log_text = (r.stdout + r.stderr).decode('utf-8', errors='replace')
    overfull_count, overfull_pt, overfull_diag_line = _scan_overfull(
        log_text, preamble_offset, d0
    )
    pdf = WORK / f"wrap_{name}.pdf"
    if not pdf.exists():
        print(f"PDF not produced for {name}")
        sys.exit(1)
    # clean up old PNGs and SVG
    for old in WORK.glob(f"fig_{name}-*.png"):
        old.unlink()
    svg_old = WORK / f"fig_{name}.svg"
    if svg_old.exists():
        svg_old.unlink()
    subprocess.run(["pdftoppm", "-png", "-r", "200", str(pdf), str(WORK / f"fig_{name}")], check=True)
    # SVG export (vector, for easier visualization/zoom) from the same PDF —
    # no second LaTeX compile needed. Single-page standalone diagrams only.
    subprocess.run(["pdftocairo", "-svg", str(pdf), str(WORK / f"fig_{name}.svg")], check=True)
    # Compact preview for the model-assisted visual review. The 200-DPI raster is
    # the artifact that ships in the compiled PDF/DOCX; handing that same raster
    # to a vision model costs far more image tokens than the check needs (a
    # measured `revisor-figuras` pass read a 658 kB PNG and took 4.2 min). The
    # preview caps the longest side at 1400 px, which is plenty to judge scale,
    # centring and overlap, and it comes from the same intermediate PDF.
    subprocess.run(
        ["pdftoppm", "-png", "-scale-to", "1400", str(pdf), str(WORK / f"fig_{name}-preview")],
        check=True,
    )
    # Structured Overfull signal (always printed, N may be 0 — the explicit
    # 0 is the release signal downstream tooling greps for).
    if overfull_count > 0:
        if overfull_diag_line is not None:
            print(
                f"OVERFULL: {name} {overfull_count} occurrence(s) "
                f"(first: {overfull_pt}pt too wide at {src.name}:{overfull_diag_line})"
            )
        else:
            print(
                f"OVERFULL: {name} {overfull_count} occurrence(s) "
                f"(first: {overfull_pt}pt too wide, line unavailable)"
            )
    else:
        print(f"OVERFULL: {name} {overfull_count} occurrence(s)")
    # Cleanup intermediates on success: keep ONLY the consumed outputs
    # (fig_<name>-1.png, fig_<name>.svg and fig_<name>-preview.png). Glob-based
    # and tolerant of files that don't exist (.fls/.fdb_latexmk aren't produced
    # under this plain -pdflatex invocation). Never touches fig_* (distinct
    # prefix).
    for stale in WORK.glob(f"wrap_{name}.*"):
        stale.unlink(missing_ok=True)
    log.unlink(missing_ok=True)
    print(f"OK: {name}")

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        name, kind = arg.split(":")
        build(name, kind)
