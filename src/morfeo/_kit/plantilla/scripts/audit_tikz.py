#!/usr/bin/env python3
"""Deterministic audit of a rendered proposal diagram.

The visual gate (`revisor-figuras`) used to run 8 checks over a 200-DPI PNG with
a model. Six of those 8 are properties of *text*, not of the image: the SVG was
exported, the compile had no `Overfull \\hbox`, the picture disables hyphenation,
node text carries explicit `\\fontsize` sizes instead of a bare relative size,
only the institutional palette is used, the expected number of blocks is
present, forbidden content is absent, and every connector is anchored on a real
node point. This script answers all of them in well under a second, so the model
only ever has to judge what is genuinely visual.

The remaining two criteria (scale/legibility and centring as a human reads them)
stay with `revisor-figuras`, which now receives this report instead of
re-deriving the mechanical half.

Usage
-----
    audit_tikz.py <name> [--project DIR] [--spec SPEC.json] [--compile-stdout FILE] [--json]
    audit_tikz.py <name> --compile-stdout <(compile_tikz.py <name>:tikz)

Exit code is 0 when every check passes, 1 otherwise. `--json` prints the machine
readable report on stdout (the human summary goes to stderr), so the dispatcher
can route off it without parsing prose.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

# Bare relative font switches are banned in diagram node text: their point value
# differs between the standalone wrapper compile and the inline `main.tex`
# compile, which is exactly the defect the doubled-font-size rule fixed. An
# explicit `\fontsize{N}{M}\selectfont` is required instead.
RELATIVE_FONT_RE = re.compile(
    r"\\(tiny|scriptsize|footnotesize|small|normalsize|large|Large|LARGE|huge|Huge)\b"
)

# A node body that carries text must also carry an explicit size somewhere in
# its style or body; a picture with no explicit size at all is suspicious.
EXPLICIT_FONT_RE = re.compile(r"\\fontsize\s*\{[0-9.]+\}\s*\{[0-9.]+\}\s*\\selectfont")

# The documented defect: `(nodeA.edge -| nodeB.edge) -- (nodeB.edge)`. The point
# computed by `-|` only lies on `nodeA`'s boundary while `nodeB`'s off-axis
# coordinate falls inside `nodeA`'s own extent; otherwise the connector starts
# floating in empty space. The renderer therefore emits no elbow operator at all
# inside a connector, and this check enforces that: an elbow inside a `\draw`
# statement is rejected outright, because a real point on each node is obtained
# by interpolating along that node's own edge instead.
ELBOW_IN_DRAW_RE = re.compile(r"\\draw\b[^;]*?(?:-\||\|-)[^;]*;", re.DOTALL)

# Ad-hoc colours: `\definecolor` is allowed only for the institutional palette,
# and no `{rgb}`/hex literal may appear outside those definitions.
ALLOWED_COLORS = {"azulUNAL", "grisLabIA", "verdeGCPDS", "rojoLimitante"}
DEFINE_COLOR_RE = re.compile(r"\\definecolor\{([^}]+)\}")
# Any hex literal is ad-hoc unless it is the payload of a `\definecolor`.
DEFINE_COLOR_HEX_RE = re.compile(r"\\definecolor\{[^}]+\}\{HTML\}\{[^}]+\}")
ANY_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")

FORBIDDEN_PERSONNEL_RE = re.compile(r"\b(?:Resp\.|Responsable|Responsables)\s*:")

CROSSREF_RE = re.compile(r"\\(?:cref|Cref|nameref|autoref)\b")


def figure_size_cm(figdir: pathlib.Path, name: str) -> tuple[float, float] | None:
    """Physical size of the 200-DPI raster, in cm.

    `pdftoppm -r 200` renders 200 px per inch, so a pixel is exactly 2.54/200 cm.
    Reporting the size makes 'does it fit the page' a number the pipeline can
    check, instead of something a reviewer estimates from a screenshot: the
    estado_arte figure measured ~17 x 31 cm, which is why `main.tex` had to
    squeeze it with a resizebox.
    """
    png = sorted(figdir.glob(f"fig_{name}-[0-9]*.png"))
    if not png:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(png[0]) as image:
        width_px, height_px = image.size
    cm_per_px = 2.54 / 200.0
    return round(width_px * cm_per_px, 2), round(height_px * cm_per_px, 2)


# A figure whose smallest text is below this prints as a caption-sized smear. The
# project's own audited canonical scale bottoms out at 7 pt (`rama` in the árbol
# de problemas), so the floor sits just under it: a regression to 6 pt text must
# fail, but the canonical minimum must not.
MIN_LEGIBLE_PT = 6.5

FONTSIZE_RE = re.compile(r"\\fontsize\s*\{([0-9.]+)\}")


def _check(report: list[dict], name: str, ok: bool, detail: str, blocking: bool = True):
    report.append({"id": name, "ok": bool(ok), "detail": detail, "blocking": blocking})


def expected_counts(spec: dict) -> dict:
    kind = spec.get("kind")
    if kind == "arbol":
        return {
            "causes": sum(len(g["causes"]) for g in spec["groups"]),
            "groups": len(spec["groups"]),
            "branches": len(spec["branches"]),
        }
    if kind == "estado_arte":
        return {
            "clusters": len(spec["clusters"]),
            "papers": sum(len(c["papers"]) for c in spec["clusters"]),
            "limitations": sum(1 for c in spec["clusters"] if c.get("limitation")),
        }
    if kind == "metodologico":
        return {
            "phases": len(spec["phases"]),
            "novelties": sum(1 for p in spec["phases"] if p.get("novelty")),
        }
    return {}


def audit(
    name: str,
    project: pathlib.Path,
    spec: dict,
    compile_stdout: str,
    page_fit: tuple[float, float] | None = None,
) -> dict:
    figdir = project / "sections" / "figuras"
    tex_path = project / "sections" / f"diag_{name}.tex"
    report: list[dict] = []

    # 1. Rendered outputs present (mechanical existence, not a visual judgment).
    png = sorted(figdir.glob(f"fig_{name}-*.png"))
    svg = figdir / f"fig_{name}.svg"
    _check(
        report,
        "export_present",
        bool(png) and svg.is_file(),
        f"png={[p.name for p in png]} svg={'ok' if svg.is_file() else 'MISSING'}",
    )
    if png:
        # A 200-DPI PNG of a proposal figure is a few hundred kB; a suspiciously
        # small one means the diagram rendered blank.
        smallest = min(p.stat().st_size for p in png)
        _check(report, "png_not_blank", smallest > 5_000, f"menor PNG = {smallest} bytes")

    # 1b. Physical size, reported always; page fit is enforced when the caller
    #     states a page budget (A4 with 2.5 cm margins by default for a figure
    #     that must sit at natural size).
    size = figure_size_cm(figdir, name)
    if size:
        width_cm, height_cm = size
        _check(report, "figure_size", True, f"{width_cm} x {height_cm} cm")
        if page_fit is not None:
            max_w, max_h = page_fit
            fits = width_cm <= max_w and height_cm <= max_h
            detail = f"{width_cm} x {height_cm} cm vs presupuesto {max_w} x {max_h} cm"
            if fits:
                detail += "; entra a tamaño natural, sin escalar"
            else:
                # A resizebox to fit the page shrinks every glyph by this factor,
                # which is how a 12 pt canonical size ends up printing at ~9 pt.
                scale = min(max_w / width_cm, max_h / height_cm)
                detail += (
                    f"; requeriría escalar al {scale * 100:.0f} % para caber "
                    "(acorta el texto, baja la densidad o divide la figura)"
                )
            _check(report, "fits_page", fits, detail)

    if not tex_path.is_file():
        _check(report, "tex_present", False, f"no existe {tex_path}")
        return _summary(name, report)

    text = tex_path.read_text(encoding="utf-8")

    # 2. No horizontal overflow, read from the deterministic compiler token.
    m = re.search(rf"OVERFULL:\s*{re.escape(name)}\s+(\d+)\s+occurrence", compile_stdout)
    if m:
        count = int(m.group(1))
        _check(report, "no_overfull", count == 0, f"{count} occurrence(s)")
    else:
        _check(
            report,
            "no_overfull",
            False,
            "no se encontró el token 'OVERFULL:' en la salida del compilador; "
            "compila con compile_tikz.py y pásale su stdout con --compile-stdout",
        )

    # 3. Hyphenation disabled inside the picture (the in-file setting is what
    #    survives `\input{}` into main.tex; the wrapper's own setting does not).
    has_hyphen = r"\hyphenpenalty=10000" in text and r"\exhyphenpenalty=10000" in text
    _check(report, "hyphenation_off", has_hyphen, "\\hyphenpenalty/\\exhyphenpenalty en el picture")

    # 4/5. Explicit font sizes only.
    relative = sorted(set(RELATIVE_FONT_RE.findall(text)))
    _check(
        report,
        "no_relative_fontsize",
        not relative,
        f"tamaños relativos encontrados: {relative}" if relative else "solo \\fontsize explícito",
    )
    explicit = EXPLICIT_FONT_RE.findall(text)
    _check(
        report,
        "explicit_fontsize_present",
        bool(explicit),
        f"{len(explicit)} declaraciones \\fontsize explícitas",
    )

    # 5b. Legibility proxy: the printed point size of the SMALLEST text in the
    #     figure. This is the mechanical half of the visual review's "escala y
    #     legibilidad" criterion -- the failure the operator actually hit was a
    #     map scaled to 74 %, which printed audited 12/14 pt type at ~9 pt. Read
    #     from the generated source so it reflects what will really be typeset.
    sizes = [float(value) for value in FONTSIZE_RE.findall(text)]
    if sizes:
        smallest = min(sizes)
        _check(
            report,
            "legibility_min_font_pt",
            smallest >= MIN_LEGIBLE_PT,
            f"texto más pequeño = {smallest:.1f} pt "
            f"(mínimo legible {MIN_LEGIBLE_PT} pt; aumenta el tamaño en la spec "
            "o divide la figura)",
        )

    # 6. Palette: only the institutional colours, no ad-hoc hex outside them.
    defined = DEFINE_COLOR_RE.findall(text)
    unknown = sorted(set(defined) - ALLOWED_COLORS)
    _check(
        report,
        "palette_institutional",
        not unknown,
        f"colores no institucionales: {unknown}" if unknown else f"definidos: {sorted(set(defined))}",
    )
    adhoc = ANY_HEX_RE.findall(DEFINE_COLOR_HEX_RE.sub("", text))
    _check(
        report,
        "no_adhoc_hex_color",
        not adhoc,
        f"hex fuera de \\definecolor: {adhoc}" if adhoc else "sin hex ad-hoc",
    )

    # 7. Expected block counts (the spec is the authority).
    counts = expected_counts(spec)
    # Node ids are emitted as `(id)` immediately before ` at`/`[` or after
    # `\node[...`, depending on the construct; a plain id-prefix count is the
    # stable signal for every kind, so each role is counted with its own
    # generator's naming convention.
    ID_PATTERNS = {
        "causes": r"\((r\d+)\)",
        "groups": r"\((tSP\d+)\)",
        "branches": r"\((b\d+)\)",
        "papers": r"\(([A-Za-z]+\d*n\d+)\)",
        "clusters": r"\((c\d+)t\)",
        "limitations": r"\((c\d+)lim\)",
        "phases": r"\((f\d+)\)",
        "novelties": r"\((f\d+)n\)",
    }
    mismatches = []
    for key, expected in counts.items():
        pattern = ID_PATTERNS.get(key)
        if pattern is None:
            continue
        have = len(set(re.findall(pattern, text)))
        if have != expected:
            mismatches.append(f"{key}: esperado {expected}, encontrado {have}")
    _check(
        report,
        "block_counts",
        not mismatches,
        "; ".join(mismatches) if mismatches else f"conteos conformes: {counts}",
    )

    # 8. Forbidden content.
    personnel = FORBIDDEN_PERSONNEL_RE.findall(text)
    _check(
        report,
        "no_personnel_in_blocks",
        not personnel,
        f"etiquetas de personal: {personnel}" if personnel else "sin etiquetas de personal",
    )
    crossrefs = CROSSREF_RE.findall(text)
    _check(
        report,
        "no_crossrefs",
        not crossrefs,
        f"referencias cruzadas: {crossrefs}" if crossrefs else "sin \\cref/\\Cref",
    )

    # 9. Connectors anchored on real points (no elbow operators at all).
    elbows = [m.group(0).strip()[:80] for m in ELBOW_IN_DRAW_RE.finditer(text)]
    _check(
        report,
        "no_elbow_in_connectors",
        not elbows,
        f"operador de codo dentro de un \\draw: {elbows}" if elbows else "conectores sin codos",
    )
    # Every `\draw` that names a node must anchor on a real anchor or on an
    # explicit edge interpolation.
    bad_anchor = [
        d.strip()[:80]
        for d in re.findall(r"\\draw\b[^;]*;", text)
        if re.search(r"\(\s*[A-Za-z][\w]*\s*[-,]", d)
        and not re.search(r"\.(north|south|east|west|center)", d)
        and not re.search(r"!\s*[0-9.]+\s*!", d)
    ]
    _check(
        report,
        "anchors_are_named_points",
        not bad_anchor,
        f"conectores sin ancla explícita: {bad_anchor}" if bad_anchor else "todas las anclas son explícitas",
    )

    # 10. Árbol de problemas: the copa must never connect directly to a raíz.
    if spec.get("kind") == "arbol":
        bad = []
        for draw in re.findall(r"\\draw[^\n]*", text):
            touches_crown = "(copa" in draw
            touches_root = re.search(r"\((r\d+)\)", draw) is not None
            if touches_crown and touches_root:
                bad.append(draw.strip())
        _check(
            report,
            "crown_never_touches_roots",
            not bad,
            f"conectores copa↔raíz: {bad}" if bad else "flujo raíces→tronco→ramas→copa sin atajos",
        )
        # Every branch must reach the crown.
        branch_ids = [b["id"] for b in spec["branches"]]
        reach = re.findall(r"\(b\d+\.north\)\s*--", text)
        _check(
            report,
            "every_branch_reaches_crown",
            len(reach) >= len(branch_ids),
            f"{len(reach)} conectores rama→copa para {len(branch_ids)} ramas",
        )

    return _summary(name, report)


def _summary(name: str, report: list[dict]) -> dict:
    failed = [c for c in report if not c["ok"]]
    return {
        "name": name,
        "verdict": "PASS" if not failed else "FAIL",
        "checks": report,
        "failed": [c["id"] for c in failed],
        "failed_blocking": [c["id"] for c in failed if c["blocking"]],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "name",
        help="id del diagrama (debe coincidir con diag_<name>.tex y la spec)",
    )
    ap.add_argument("--project", type=pathlib.Path, help="raíz del proyecto LaTeX (por defecto: cwd)")
    ap.add_argument("--spec", type=pathlib.Path, help="spec JSON de la figura")
    ap.add_argument(
        "--compile-stdout",
        type=pathlib.Path,
        help="archivo con el stdout de compile_tikz.py (para leer el token OVERFULL)",
    )
    ap.add_argument("--json", action="store_true", help="imprime el reporte JSON en stdout")
    ap.add_argument(
        "--page-fit",
        metavar="W cmxH cm",
        help="presupuesto de página: 'WxH' en cm, p. ej. 16x22 para A4 con márgenes",
    )
    args = ap.parse_args(argv)

    project = (args.project or pathlib.Path.cwd()).resolve()
    spec_path = args.spec
    if spec_path is None:
        candidate = project / "specs" / f"{args.name}.spec.json"
        spec_path = candidate if candidate.is_file() else None
    spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path and spec_path.is_file() else {}

    compile_stdout = ""
    if args.compile_stdout and args.compile_stdout.is_file():
        compile_stdout = args.compile_stdout.read_text(encoding="utf-8", errors="replace")

    page_fit = None
    if args.page_fit:
        match = re.match(r"^\s*([0-9.]+)\s*x\s*([0-9.]+)\s*$", args.page_fit)
        if not match:
            raise SystemExit("--page-fit espera 'WxH' en cm, p. ej. 16x22")
        page_fit = (float(match.group(1)), float(match.group(2)))

    report = audit(args.name, project, spec, compile_stdout, page_fit)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"AUDIT {report['verdict']}: {report['name']}")
        for check in report["checks"]:
            mark = "OK  " if check["ok"] else "FAIL"
            print(f"  [{mark}] {check['id']}: {check['detail']}")
        if report["failed"]:
            print(f"  -> {len(report['failed'])} chequeo(s) fallido(s): {report['failed']}")

    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
