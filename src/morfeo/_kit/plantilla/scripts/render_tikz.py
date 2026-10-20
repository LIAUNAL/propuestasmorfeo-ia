#!/usr/bin/env python3
"""Render a proposal diagram's TikZ source deterministically from a JSON spec.

Why this exists
---------------
Before this script the three proposal diagrams (árbol de problemas, mapa de
estado del arte, diagrama metodológico) were hand-authored line by line by an
LLM: manual anchors, manual `text width`, manual `fit` groups. Measured on run
`2026-09-tept-depresion-ia-portable`, that cost ~28.8 minutes per figure
(`artefactos/pipeline/30-fase2.md`), almost all of it the model re-deriving
geometry it cannot reliably derive, while the actual LaTeX compile takes ~1 s.

The separation of concerns here is deliberately strict:

  * the **LLM** decides *content* — which nodes, which labels, which edges —
    and writes it as a compact JSON spec;
  * this **script** decides *geometry* — node widths that fit the longest
    unbreakable word, equispaced columns/rows, real anchor points on every
    connector, the institutional palette and the canonical font sizes.

Every layout defect the pipeline used to hunt for in a retry loop (overlapping
blocks, floating arrow endpoints, text spilling out of a node, mid-word
hyphenation, ad-hoc colours, bare relative font sizes) is a property of the
generated geometry, so it is fixed here once and cannot regress through a model
mistake.

Contract with `compile_tikz.py`
-------------------------------
The generated file is a normal `diag_<name>.tex`: it is `\\input{}`-able from
`main.tex`, it carries `\\hyphenpenalty`/`\\exhyphenpenalty` inside the picture
(it does not rely on the standalone wrapper), and it defines the palette
locally so the standalone wrapper and the inline compile render identically.
`compile_tikz.py` is unchanged and still owns compilation, the PNG/SVG export
and the deterministic `OVERFULL:` token.

Deterministic overfull autofix
------------------------------
Horizontal overflow is the only failure mode left, and it is a pure function of
`text width`: a node never clips vertically (TikZ grows the node instead).
`render_tikz.py` therefore writes a sidecar `line -> node id` map next to the
output, and `--fix-overfull WIDTH_FIX` consumes one mapped line plus the
`pt too wide` value to widen exactly that node, recording the override in a
sidecar overrides file. `figura.py` drives that loop; it converges in a couple
of iterations and each iteration is ~1 s.

Usage
-----
    render_tikz.py <spec.json> [-o OUT.tex]
    render_tikz.py <spec.json> --fix-overfull "<LINE>:<PT>" [--overrides PATH]

`<spec.json>` carries a `kind` field: `arbol`, `estado_arte` or `metodologico`.
See `docs/pipeline-flow.md` for the schemas.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys

# --------------------------------------------------------------------------
# Canonical visual constants (single source: the palette and type scale the
# framework's figures have always used).
# --------------------------------------------------------------------------
PALETTE = {
    "azulUNAL": "0066B3",
    "grisLabIA": "666666",
    "verdeGCPDS": "2E8B57",
    "rojoLimitante": "C0392B",
}

# Average glyph advance as a fraction of the font size, for the Latin text of
# the proposal (Spanish, mostly lowercase). Used only to pick a starting
# `text width`; the deterministic autofix is the backstop that guarantees the
# final width, so a rough constant is safe and never load-bearing.
_GLYPH_EM = 0.52

# inner sep of the node styles, in cm (matches the generated styles below).
_INNER_SEP_CM = 0.13

# Width clamp per node role, in cm. The floor is the *canonical audited width*
# the project's figures already used (so the rendered proportions match what the
# visual review approved); the fit computation only ever raises it, when the
# longest unbreakable word would not fit.
WIDTH_CLAMP = {
    "raiz": (3.9, 5.8),
    "rama": (3.1, 4.4),
    "tronco": (12.0, 16.0),
    "copa": (12.0, 16.0),
    "gtitulo": (3.9, 5.8),
    "paper": (3.3, 5.0),
    "paperlinea": (3.3, 5.6),
    # The floors for ctitulo/limitex were inherited from the first 12 pt design;
    # at a compact size they only served to keep the 3-column grid wider than an
    # A4 text block (measured: 4.45 cm floor -> 18.2 cm grid width).
    "ctitulo": (3.4, 5.4),
    "limitex": (3.2, 5.4),
    "fase": (3.4, 4.8),
    "novedad": (3.0, 4.6),
}

# Horizontal gap between sibling columns (cm).
COL_GAP_CM = 0.6
# Horizontal gap between the level-label column and its neighbours (cm).
LABEL_COL_CM = 0.55

FONT = {
    # role: (fontsize pt, baselineskip pt)
    "raiz": (7.5, 9),
    "gtitulo": (8.5, 10),
    "tronco": (9, 11),
    "rama": (7, 8.4),
    "copa": (9, 11),
    "paper": (12, 14),
    "paperlinea": (9.5, 11),
    "paperconcepto": (10, 12),
    "ctitulo": (14, 17),
    "limitex": (12, 14),
    "fase": (9, 11),
    "novedad": (7.5, 9),
    "nivel": (7.5, 9),
    "closing": (12, 14),
    "etiqueta": (8, 9.6),
    "benef": (8, 9.6),
}


def _strip_tex(text: str) -> str:
    """Length estimate input: drop markup that does not occupy horizontal space."""
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", "", text)
    text = text.replace("\\\\", " ").replace("{", "").replace("}", "")
    text = text.replace("~", " ").replace("--", "-").replace("$", "")
    return text


def effective_fonts(spec: dict) -> dict:
    """Per-diagram font sizes: the canonical `FONT` merged with `spec["fonts"]`.

    A diagram that must fit a fixed page is a typographic decision, not a
    layout bug: the estado_arte figure measured ~31.3 cm tall at the canonical
    12/14 pt, which forced `main.tex` to squeeze it with `\resizebox` and
    printed the audited sizes at ~9 pt anyway. Letting the spec state the sizes
    explicitly keeps the choice visible and reviewable instead of hiding it in a
    resizebox.
    """
    fonts = {role: tuple(size) for role, size in FONT.items()}
    for role, size in (spec.get("fonts") or {}).items():
        if role not in fonts:
            raise SystemExit(
                f"spec inválida: 'fonts' nombra un rol desconocido '{role}' "
                f"(roles válidos: {sorted(fonts)})"
            )
        if not isinstance(size, (list, tuple)) or len(size) != 2:
            raise SystemExit(
                f"spec inválida: fonts['{role}'] debe ser [tamaño, interlineado]"
            )
        fonts[role] = (float(size[0]), float(size[1]))
    return fonts


def longest_word_cm(text: str, font_pt: float) -> float:
    """Rendered width of the widest unbreakable chunk of `text`, in cm.

    Hyphenation is disabled inside the picture, so the widest chunk that must
    fit on one line is the longest whitespace-delimited token. This is the only
    quantity that can produce an `Overfull \\hbox` in a fixed-width node.
    """
    words = _strip_tex(text).split()
    if not words:
        return 0.0
    longest = max(words, key=len)
    return len(longest) * _GLYPH_EM * font_pt * 0.03528  # pt -> cm


def line_width_cm(text: str, font_pt: float, bold: bool = False) -> float:
    r"""Rendered width of `text` on a single unwrapped line, in cm.

    `longest_word_cm` answers whether a fixed-width node can avoid an `Overfull
    \hbox`; this answers how wide a label that must not wrap actually prints.
    Used to decide whether the two TRL markers fit on the bar side by side.
    """
    factor = _GLYPH_EM * (1.08 if bold else 1.0)
    return len(_strip_tex(text)) * factor * font_pt * 0.03528  # pt -> cm


def fit_width(texts: list[str], role: str, fonts: dict | None = None) -> float:
    """Pick a `text width` (cm) that fits every longest word in `role`'s font."""
    font_pt = (fonts or FONT)[role][0]
    need = 0.0
    for text in texts:
        need = max(need, longest_word_cm(text, font_pt))
    need += 2 * _INNER_SEP_CM + 0.25
    low, high = WIDTH_CLAMP[role]
    return round(min(max(need, low), high), 2)


def widest_role(texts: list[str], role: str, fonts: dict | None = None) -> float:
    """Fit width for `role`, ignoring the clamp floor so the caller can widen."""
    font_pt = (fonts or FONT)[role][0]
    need = max((longest_word_cm(t, font_pt) for t in texts), default=0.0)
    return round(need + 2 * _INNER_SEP_CM + 0.25, 2)


def est_node_height_cm(text: str, role: str, width_cm: float, fonts: dict | None = None) -> float:
    """Estimate a fixed-width node's rendered height, in cm.

    Used only to space the level-label legend so each label lands on its own
    band. The estimate never affects node geometry: TikZ still sizes every node
    from its real content, so an imprecise estimate can only shift a label
    within a band that is several centimetres tall, never cause an overlap.
    """
    font_pt, baseline_pt = (fonts or FONT)[role]
    inner_cm = _INNER_SEP_CM if role != "novedad" else 0.11
    usable_cm = max(width_cm - 2 * inner_cm, 0.5)
    char_cm = _GLYPH_EM * font_pt * 0.03528
    chars_per_line = max(int(usable_cm / char_cm), 4)
    explicit = str(text).replace("\\", "\n").split("\n")
    lines = 0
    for chunk in explicit:
        stripped = _strip_tex(chunk).strip()
        lines += max(1, math.ceil(len(stripped) / chars_per_line)) if stripped else 1
    return lines * baseline_pt * 0.03528 + 2 * inner_cm + 0.15


def spread_fractions(centers: list[float], min_gaps: list[float]) -> list[float]:
    """Push ordered centres apart until every consecutive gap is >= its minimum.

    `min_gaps[i]` is the smallest allowed distance between `centers[i]` and
    `centers[i+1]`, in the same normalised units. A forward then backward pass
    is repeated until stable, so the result keeps the desired band alignment
    wherever there is room and falls back to a safe pitch where there is not.
    Both passes clamp to [0, 1], the span of the legend line.
    """
    out = list(centers)
    n = len(out)
    if n < 2:
        return out
    for _ in range(64):
        changed = False
        for i in range(n - 1):
            need = min_gaps[i]
            gap = out[i + 1] - out[i]
            if gap < need - 1e-9:
                deficit = need - gap
                out[i + 1] += deficit
                changed = True
        out[-1] = min(out[-1], 1.0)
        for i in range(n - 1, 0, -1):
            need = min_gaps[i - 1]
            gap = out[i] - out[i - 1]
            if gap < need - 1e-9:
                deficit = need - gap
                out[i - 1] -= deficit
                changed = True
        out[0] = max(out[0], 0.0)
        if not changed:
            break
    return out


def font_vars(fonts: dict) -> dict:
    """Placeholder values for `\\fontsize{FP_<ROLE>}{FS_<ROLE>}` in the templates."""
    out = {}
    for role, (size, skip) in fonts.items():
        out[f"FP_{role}"] = size
        out[f"FS_{role}"] = skip
    return out


def tex(text: str) -> str:
    """Escape the characters that would break a raw TikZ node body.

    The specs are authored with plain Spanish text, so `%`, `&`, `#` and `_`
    arrive unescaped and would otherwise be TeX syntax errors. An explicit line
    break is requested with a real newline in the JSON string (or a literal
    `\\`), and is emitted as TikZ's `\\\\`: authors never hand-write TeX
    escapes, which is what kept breaking node bodies when a model authored the
    `.tex` directly.
    """
    raw = str(text).replace("\\", "\n")
    parts = raw.split("\n")
    escaped = []
    for part in parts:
        escaped.append(
            part.replace("&", r"\&")
            .replace("%", r"\%")
            .replace("#", r"\#")
            .replace("_", r"\_")
            .strip()
        )
    return r"\\".join(escaped)


def _f(value: float) -> str:
    """Fixed-point coordinate, without a trailing `.0` noise suffix."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


PREAMBLE_STYLES = {
    "arbol": r"""  raiz/.style={draw=azulUNAL!75, fill=white, rounded corners=2pt,
               text width={W_RAIZ}cm, align=center, inner sep=3.5pt,
               font=\fontsize{{FP_RAIZ}}{{FS_RAIZ}}\selectfont},
  gtitulo/.style={text=azulUNAL, align=center, text width={W_GTITULO}cm,
                  inner sep=2pt, font=\fontsize{{FP_GTITULO}}{{FS_GTITULO}}\selectfont\bfseries},
  gcaja/.style={draw=grisLabIA, dashed, rounded corners=4pt,
                fill=grisLabIA!7, inner sep=7pt},
  tronco/.style={draw=azulUNAL, line width=1.1pt, fill=azulUNAL!12,
                 rounded corners=3pt, text width={W_TRONCO}cm, align=center,
                 inner sep=6pt, font=\fontsize{{FP_TRONCO}}{{FS_TRONCO}}\selectfont},
  rama/.style={draw=azulUNAL!80, fill=azulUNAL!10, rounded corners=2pt,
               text width={W_RAMA}cm, align=center, inner sep=3pt,
               font=\fontsize{{FP_RAMA}}{{FS_RAMA}}\selectfont},
  copa/.style={draw=verdeGCPDS, line width=1.1pt, fill=verdeGCPDS,
               text=white, rounded corners=9pt, text width={W_COPA}cm,
               align=center, inner sep=7pt, font=\fontsize{{FP_COPA}}{{FS_COPA}}\selectfont},
  flecha/.style={-{Stealth[length=2.6mm]}, line width=0.9pt, draw=azulUNAL!85},
  nivel/.style={rotate=90, text=grisLabIA, align=center,
                font=\fontsize{{FP_NIVEL}}{{FS_NIVEL}}\selectfont\bfseries},""",
    "estado_arte": r"""  paper/.style={draw=azulUNAL!55, fill=azulUNAL!4, rounded corners=2pt,
                text width={W_PAPER}cm, align=center, inner sep=3pt,
                font=\fontsize{{FP_PAPER}}{{FS_PAPER}}\selectfont},
  papelinea/.style={draw=azulUNAL!55, fill=azulUNAL!4, rounded corners=2pt,
                text width={W_PAPERLINEA}cm, align=center, inner sep=2.6pt,
                font=\fontsize{{FP_PAPERLINEA}}{{FS_PAPERLINEA}}\selectfont},
  ctitulo/.style={text=azulUNAL, align=center, text width={W_CTITULO}cm,
                  inner sep=2pt, font=\fontsize{{FP_CTITULO}}{{FS_CTITULO}}\selectfont\bfseries},
  limitex/.style={text=rojoLimitante, align=center, text width={W_LIMITEX}cm,
                  inner sep=2pt, font=\fontsize{{FP_LIMITEX}}{{FS_LIMITEX}}\selectfont\bfseries},
  cborde/.style={draw=grisLabIA, dashed, rounded corners=4pt,
                 fill=grisLabIA!6, inner sep=0.26cm},
  enlace/.style={draw=azulUNAL!75, line width=0.8pt,
                 -{Stealth[length=2mm]}},
  cierre/.style={text=azulUNAL, align=center, text width={W_CIERRE}cm,
                 font=\fontsize{{FP_CLOSING}}{{FS_CLOSING}}\selectfont\bfseries},""",
    "metodologico": r"""  fase/.style={draw=azulUNAL, line width=1pt, fill=azulUNAL!10,
               rounded corners=3pt, text width={W_FASE}cm, align=center,
               inner sep=5pt, font=\fontsize{{FP_FASE}}{{FS_FASE}}\selectfont},
  novedad/.style={draw=verdeGCPDS!80, fill=verdeGCPDS!12, rounded corners=2pt,
                  text width={W_NOVEDAD}cm, align=center, inner sep=3pt,
                  font=\fontsize{{FP_NOVEDAD}}{{FS_NOVEDAD}}\selectfont},
  flecha/.style={-{Stealth[length=2.6mm]}, line width=1pt, draw=azulUNAL!85},
  trlbarra/.style={draw=azulUNAL, line width=1.2pt,
                   -{Stealth[length=3mm]}, draw=verdeGCPDS},
  etiqueta/.style={text=grisLabIA, font=\fontsize{{FP_ETIQUETA}}{{FS_ETIQUETA}}\selectfont\bfseries},
  benef/.style={draw=grisLabIA!70, rounded corners=4pt, fill=grisLabIA!6,
                text width={W_BENEF}cm, align=center, inner sep=6pt,
                font=\fontsize{{FP_BENEF}}{{FS_BENEF}}\selectfont},""",
}

LIBRARIES = r"\usetikzlibrary{positioning,arrows.meta,calc,fit,backgrounds}"


def _styles(kind: str, widths: dict[str, float]) -> str:
    """Fill `{W_<ROLE>}` placeholders textually.

    `str.format` cannot be used: the style templates contain `{Stealth[...]}`
    from arrows.meta, whose braces are literal TeX, not format fields.

    Every template line's braces are verified here, because an unbalanced brace
    inside `\begin{tikzpicture}[...]` fails the whole compile with a confusing
    `\tikz@picture was complete` error (observed when a mechanical rewrite of
    the templates dropped one closing brace).
    """
    text = PREAMBLE_STYLES[kind]
    for key, value in widths.items():
        text = text.replace("{" + key.upper() + "}", _f(value))
    # Un placeholder sin resolver llega al `.tex` como llave literal y TeX lo lee
    # como argumento numérico de `\fontsize`, que falla con un «Missing number,
    # treated as zero» a decenas de líneas de distancia. Ocurrió: el estilo
    # `etiqueta` del tipo `metodologico` referenciaba `FP_ETIQUETA`, un rol que
    # `FONT` no declaraba, y el camino de `metodologico` no se había ejercitado
    # nunca. Mejor fallar acá, señalando el rol que falta.
    for m in re.finditer(r"\{{2,}([A-Z_]+)\}{2,}", text):
        role = m.group(1).removeprefix("FP_").removeprefix("FS_").removeprefix("W_")
        raise SystemExit(
            f"estilo sin resolver en {kind}: {{{m.group(1)}}} — el rol '{role}' "
            f"no está declarado (revisá FONT y los overrides del spec)"
        )
    depth = 0
    for line in text.splitlines():
        depth += line.count("{") - line.count("}")
        if depth < 0:
            raise SystemExit(f"estilo desbalanceado en {kind}: {line!r}")
    if depth != 0:
        raise SystemExit(f"estilos de {kind} con desbalance de llaves: {depth}")
    return text


# Node ids follow the generators' naming convention; an override is keyed by the
# STYLE role whose `text width` the node uses, not by the id itself. Getting this
# wrong sent a fix for `b1` looking for a style called `b1` (observed).
_ID_ROLE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^tSP\d+$"), "gtitulo"),
    (re.compile(r"^r\d+$"), "raiz"),
    (re.compile(r"^b\d+$"), "rama"),
    (re.compile(r"^tronco$"), "tronco"),
    (re.compile(r"^copa$"), "copa"),
    (re.compile(r"^c\d+t$"), "ctitulo"),
    (re.compile(r"^c\d+lim$"), "limitex"),
    (re.compile(r"^[A-Za-z]+\d*n\d+$"), "paper"),
    (re.compile(r"^f\d+n$"), "novedad"),
    (re.compile(r"^f\d+$"), "fase"),
    (re.compile(r"^benef$"), "benef"),
)


def role_for_node(node_id: str) -> str:
    """Map a generated node id to the style role whose width it uses."""
    for pattern, role in _ID_ROLE_PATTERNS:
        if pattern.match(node_id):
            return role
    return node_id


# --------------------------------------------------------------------------
# kind: arbol
# --------------------------------------------------------------------------
def build_arbol(spec: dict, over: dict) -> tuple[str, list[int], dict[int, str]]:
    groups = spec["groups"]
    branches = spec["branches"]
    trunk = spec["trunk"]
    crown = spec["crown"]

    all_causes = [c["text"] for g in groups for c in g["causes"]]
    all_branch = [b["text"] for b in branches]
    fonts = effective_fonts(spec)

    w_raiz = over.get("raiz") or fit_width(all_causes, "raiz", fonts)
    w_rama = over.get("rama") or fit_width(all_branch, "rama", fonts)
    w_gtitulo = over.get("gtitulo") or fit_width([g["title"] for g in groups], "gtitulo", fonts)
    w_tronco = over.get("tronco") or fit_width([trunk["text"]], "tronco", fonts)
    w_copa = over.get("copa") or fit_width([crown["text"]], "copa", fonts)

    widths = {
        "W_RAIZ": w_raiz,
        "W_RAMA": w_rama,
        "W_GTITULO": w_gtitulo,
        "W_TRONCO": w_tronco,
        "W_COPA": w_copa,
        **font_vars(fonts),
    }

    lines: list[str] = []
    line_map: dict[int, str] = {}

    def emit(text: str, node: str | None = None) -> None:
        lines.append(text)
        if node:
            line_map[len(lines)] = node

    emit("% " + "=" * 69)
    emit("% ÁRBOL DE PROBLEMAS — §3 Descripción del problema")
    emit("% GENERADO por plantilla/scripts/render_tikz.py desde la spec JSON.")
    emit("% No editar a mano: la geometría la calcula el script (anchos que")
    emit("% caben el token más largo, anclas reales, columnas equiespaciadas).")
    emit("% Flujo: raíces → tronco → ramas → copa (la copa NUNCA toca raíces).")
    emit("% " + "=" * 69)
    emit("")
    emit(r"\begin{tikzpicture}[")
    for style_line in _styles("arbol", widths).splitlines():
        emit(style_line)
    emit("]")
    emit(r"\hyphenpenalty=10000")
    emit(r"\exhyphenpenalty=10000")
    emit(LIBRARIES)
    for name, html in PALETTE.items():
        emit(rf"\definecolor{{{name}}}{{HTML}}{{{html}}}")
    emit("")

    n = len(groups)
    col_step = round(w_raiz + COL_GAP_CM, 2)
    emit(f"% ---- Nivel 1: raíces — {n} columnas equiespaciadas ({_f(col_step)} cm) ----")
    for gi, group in enumerate(groups):
        x = (gi - (n - 1) / 2) * col_step
        emit(f"% --- Grupo {group['id']} (x = {_f(x)}) ---")
        emit(
            rf"\node[gtitulo, anchor=north] (t{group['id']}) at ({_f(x)},0.45)"
        )
        emit(rf"  {{{tex(group['title'])}}};")
        prev = f"t{group['id']}"
        for ci, cause in enumerate(group["causes"]):
            gap = "0.18" if ci == 0 else "0.14"
            body = cause["text"]
            if ci == 0:
                body = rf"{{\bfseries\textcolor{{azulUNAL}}{{{cause['id']}.}}}} {tex(body)}"
            else:
                body = rf"{{\bfseries\textcolor{{azulUNAL}}{{{cause['id']}.}}}} {tex(body)}"
            emit(rf"\node[raiz, below={gap}cm of {prev}] ({cause['id']})")
            emit(rf"  {{{body}}};")
            line_map[len(lines)] = cause["id"]
            prev = cause["id"]
        emit("")

    emit("% ---- Contenedores de grupo (capa de fondo) ----")
    emit(r"\begin{pgfonlayer}{background}")
    for group in groups:
        ids = "".join(f"({c['id']})" for c in group["causes"])
        emit(rf"  \node[gcaja, fit=(t{group['id']}){ids}] (g{group['id']}) {{}};")
    emit(r"\end{pgfonlayer}")
    emit("")
    emit(r"\node[inner sep=0pt] (gAll) [fit=" + "".join(f"(g{g['id']})" for g in groups) + "] {};")
    emit("")

    emit("% ---- Nivel 2: tronco ----")
    emit(r"\node[tronco, above=1.0cm of gAll.north] (tronco)")
    emit(
        "  {{"
        + r"\fontsize{" + _f(fonts["tronco"][0]) + "}{" + _f(fonts["tronco"][1])
        + r"}\selectfont\bfseries " + tex(trunk["label"]) + r"}\\[2pt]"
    )
    emit(f"   {tex(trunk['text'])}}};")
    line_map[len(lines)] = "tronco"
    emit("")

    nb = len(branches)
    span = max(w_tronco, round(nb * (w_rama + 0.35), 2))
    emit(f"% ---- Nivel 3: ramas — {nb} bloques, span {_f(span)} cm ----")
    emit(r"\coordinate (ramaAnchor) at ($(tronco.north)+(0,3.4)$);")
    for bi, branch in enumerate(branches):
        x = -span / 2 + (bi + 0.5) * span / nb
        emit(
            rf"\node[rama, anchor=north] ({branch['id']}) at ($(ramaAnchor)+({_f(x)},0)$)"
        )
        emit(
            "  {" + rf"{{\bfseries\textcolor{{azulUNAL}}{{{branch['id']}.}}}} {tex(branch['text'])}}};"
        )
        line_map[len(lines)] = branch["id"]
    emit("")

    emit("% ---- Nivel 4: copa ----")
    emit(r"\node[inner sep=0pt] (bAll) [fit=" + "".join(f"({b['id']})" for b in branches) + "] {};")
    # `above=X of` anchors the copa's SOUTH edge, so the gap is exactly X.
    # Placing the copa by its centre against bAll.north (as a hand-authored
    # figure tends to do) silently overlaps the branch row by half the copa's
    # own height.
    emit(r"\node[copa, above=1.0cm of bAll.north] (copa)")
    emit(
        "  {{"
        + r"\fontsize{" + _f(fonts["copa"][0]) + "}{" + _f(fonts["copa"][1])
        + r"}\selectfont\bfseries " + tex(crown["label"]) + r"}\\[2pt]"
    )
    emit(f"   {tex(crown['text'])}}};")
    line_map[len(lines)] = "copa"
    emit("")

    emit("% ---- Conectores (anclas reales en ambos extremos) ----")
    for gi, group in enumerate(groups):
        frac = (gi + 1) / (n + 1)
        emit(
            rf"\draw[flecha] (g{group['id']}.north) -- "
            rf"($(tronco.south west)!{frac:.3f}!(tronco.south east)$);"
        )
    emit(
        "% Conector desde un punto REAL del borde norte del tronco hasta el borde\n"
        "% sur de cada rama. El punto se obtiene interpolando sobre el propio borde\n"
        "% del tronco (siempre está sobre el tronco, sin depender de que la rama caiga\n"
        "% dentro de su extensión) y cada flecha queda dentro de su columna, así que\n"
        "% ninguna cruza un bloque ajeno.\n"
    )
    for bi, branch in enumerate(branches):
        x = -span / 2 + (bi + 0.5) * span / nb
        frac = 0.5 + (x / span) * 0.88
        emit(
            rf"\draw[flecha] ($(tronco.north west)!{frac:.4f}!(tronco.north east)$) "
            rf"-- ({branch['id']}.south);"
        )
    for bi, branch in enumerate(branches):
        frac = (bi + 1) / (nb + 1)
        emit(
            rf"\draw[flecha] ({branch['id']}.north) -- "
            rf"($(copa.south west)!{frac:.3f}!(copa.south east)$);"
        )
    emit("")

    emit("% ---- Etiquetas de nivel (gris, columna izquierda) ----")
    # A legend column anchored to the picture's own top and bottom, with an
    # even pitch. Anchoring each label to its own band centre reads nicer but
    # cannot be collision-checked here: band heights are computed by LaTeX, so
    # two adjacent rotated labels can end up millimetres apart (observed) or
    # overlapping. An even pitch over the real figure height cannot collide,
    # because the pitch is always several times any label's own height.
    labels = [
        # MGA levels: the crown is the final indirect effect, never the solution.
        ("EFECTO", "FINAL"),
        ("EFECTOS", "DIRECTOS"),
        ("PROBLEMA", "CENTRAL"),
        ("CAUSAS", "(RAÍCES)"),
    ]
    # Band heights, estimated from the content the renderer itself laid out, so
    # each legend label lands on its own band instead of on an even pitch (the
    # causas band is by far the tallest, which pushed the middle labels off
    # their band). FALLBACK_GAP_CM keeps the estimate from ever collapsing the
    # pitch: the legend line spans copa.north -> gAll.south and each band is at
    # least a few centimetres tall.
    band_heights = [
        est_node_height_cm(crown["text"], "copa", w_copa, fonts) + 0.5,
        max(est_node_height_cm(b["text"], "rama", w_rama, fonts) for b in branches),
        est_node_height_cm(trunk["text"], "tronco", w_tronco, fonts) + 0.5,
        max(
            est_node_height_cm(g["title"], "gtitulo", w_gtitulo, fonts)
            + sum(
                est_node_height_cm(c["text"], "raiz", w_raiz, fonts)
                for c in g["causes"]
            )
            + 2 * 0.32
            for g in groups
        )
        + 0.5,
    ]
    BAND_GAP_CM = 1.0
    total = sum(band_heights) + BAND_GAP_CM * (len(band_heights) - 1)
    centers = []
    cursor = 0.0
    for height in band_heights:
        centers.append((cursor + height / 2) / total)
        cursor += height + BAND_GAP_CM

    # Each label is two short rotated lines, so its vertical footprint is the
    # width of its longest line (~8 chars) instead of the full phrase (~17
    # chars). A single-line legend of 16-character phrases at 7.5 pt is ~3.4 cm
    # tall, which is wider than the ~3.0 cm gap between band centres and made
    # consecutive labels touch (measured on the rendered PNG).
    label_cm = [
        max(len(line) for line in pair) * _GLYPH_EM * 1.08 * 7.5 * 0.03528 + 0.25
        for pair in labels
    ]
    min_gaps = [
        (label_cm[i] / 2 + label_cm[i + 1] / 2 + 0.9) / total
        for i in range(len(labels) - 1)
    ]
    fractions = spread_fractions(centers, min_gaps)

    emit(rf"\coordinate (lbltop) at ([xshift=-{_f(LABEL_COL_CM + 0.35)}cm]gAll.west |- copa.north);")
    emit(rf"\coordinate (lblbot) at ([xshift=-{_f(LABEL_COL_CM + 0.35)}cm]gAll.west |- gAll.south);")
    for frac, pair in zip(fractions, labels):
        emit(
            "\\node[nivel, anchor=center] at ($(lbltop)!%.4f!(lblbot)$) {%s};"
            % (frac, r"\\".join(pair))
        )
    emit("")
    emit(r"\end{tikzpicture}")
    return "\n".join(lines) + "\n", [], line_map


# --------------------------------------------------------------------------
# kind: estado_arte
# --------------------------------------------------------------------------
def build_estado_arte(spec: dict, over: dict) -> tuple[str, list[int], dict[int, str]]:
    clusters = spec["clusters"]
    closing = spec.get("closing", "")
    links = spec.get("links", [])
    cols = int(spec.get("cols", 3))

    fonts = effective_fonts(spec)
    # `paper_layout`: "inline" (default) puts the author-year and the coded
    # concept phrase on ONE line; "stacked" keeps the two-line node, which is
    # only viable for a figure that gets scaled down anyway.
    inline_papers = str(spec.get("paper_layout", "inline")).lower() != "stacked"
    papers = [p for c in clusters for p in c["papers"]]
    if over.get("paper"):
        # An autofix override is authoritative: it was measured against a real
        # `Overfull \hbox`, so it must not be shrunk back by the heuristic fit.
        w_paper = float(over["paper"])
    else:
        if inline_papers:
            w_paper = fit_width(
                [f"{p['author']} {p.get('concept', '')}" for p in papers],
                "paperlinea",
                fonts,
            )
        else:
            w_paper = fit_width(
                [f"{p['author']} {p.get('concept', '')}" for p in papers], "paper", fonts
            )
            w_concept = widest_role(
                [p.get("concept", "") for p in papers], "paperconcepto", fonts
            )
            w_paper = max(w_paper, w_concept)
    w_ctitulo = over.get("ctitulo") or fit_width(
        [c["title"] for c in clusters], "ctitulo", fonts
    )
    w_limitex = over.get("limitex") or fit_width(
        [c.get("limitation", "") for c in clusters], "limitex", fonts
    )
    # An intra-cluster arrow between non-consecutive papers (e.g. n1 -> n4) has
    # to leave the column to avoid crossing the intermediate boxes, so the grid
    # needs horizontal room for that detour on the right of each card.
    def _far_arrow(cluster: dict) -> bool:
        order = {p["id"]: i for i, p in enumerate(cluster["papers"])}
        return any(
            abs(order[a] - order[b]) > 1
            for a, b in (tuple(pair) for pair in cluster.get("arrows", []))
        )

    extra = 0.55 if any(_far_arrow(c) for c in clusters) else 0.0
    col_step = round(max(w_paper, w_ctitulo, w_limitex) + 0.5 + extra, 2)

    widths = {
        "W_PAPER": w_paper,
        "W_PAPERLINEA": w_paper,
        "W_CTITULO": w_ctitulo,
        "W_LIMITEX": w_limitex,
        # The closing phrase spans the real grid width, so it can never be the
        # element that widens the figure past the page.
        "W_CIERRE": round(cols * col_step - (col_step - max(w_paper, w_ctitulo, w_limitex)), 2),
        **font_vars(fonts),
    }

    lines: list[str] = []
    line_map: dict[int, str] = {}

    def emit(text: str, node: str | None = None) -> None:
        lines.append(text)
        if node:
            line_map[len(lines)] = node

    emit("% " + "=" * 69)
    emit("% MAPA DE ESTADO DEL ARTE — §4 Estado del arte")
    emit("% GENERADO por plantilla/scripts/render_tikz.py desde la spec JSON.")
    emit("% No editar a mano. Cada clúster es una tarjeta vertical: título,")
    emit("% nodos de paper (autor-año + frase-concepto azul) y limitante roja.")
    emit("% " + "=" * 69)
    emit("")
    emit(r"\begin{tikzpicture}[")
    for style_line in _styles("estado_arte", widths).splitlines():
        emit(style_line)
    emit("]")
    emit(r"\hyphenpenalty=10000")
    emit(r"\exhyphenpenalty=10000")
    emit(LIBRARIES)
    for name, html in PALETTE.items():
        emit(rf"\definecolor{{{name}}}{{HTML}}{{{html}}}")
    emit("")

    node_ids: list[str] = []
    row_fit_prev: str | None = None
    cluster_col: dict[str, int] = {}
    cluster_row: dict[str, int] = {}

    for ci, cluster in enumerate(clusters):
        col = ci % cols
        row = ci // cols
        # Centre a partial last row on the full grid width: a row of two cards
        # left-aligned under a row of three reads as a broken composition. The
        # continuation nodes of the row are positioned relative to the first one,
        # so they inherit the shift.
        in_row = min(cols, len(clusters) - row * cols)
        shift = (cols - in_row) * col_step / 2
        x = (col - (cols - 1) / 2) * col_step + shift
        cid = f"c{ci + 1}"
        cluster_col[cid] = col
        cluster_row[cid] = row
        emit(f"% --- Clúster {ci + 1}: {tex(cluster['title'])} ---")
        if row == 0 or ci % cols == 0:
            if row == 0:
                emit(rf"\node[ctitulo, anchor=north] ({cid}t) at ({_f(x)},0)")
            else:
                tid = f"c{ci - cols + 1}"
                emit(
                    rf"\node[ctitulo, anchor=north] ({cid}t) "
                    rf"at ($(r{row - 1}fit.south) + ({_f(x)},-1.0)$)"
                )
        else:
            emit(
                rf"\node[ctitulo, anchor=north] ({cid}t) "
                rf"at ($(c{ci}t.north) + ({_f(col_step)},0)$)"
            )
        emit(f"  {{{tex(cluster['title'])}}};")
        line_map[len(lines)] = f"{cid}t"
        prev = f"{cid}t"
        for pi, paper in enumerate(cluster["papers"]):
            gap = "0.25" if pi == 0 else ("0.09" if inline_papers else "0.14")
            pid = paper["id"]
            if inline_papers:
                # One line per paper instead of two. A 5-cluster x 5-paper map
                # with a stacked (author over concept) node measures ~26.5 cm
                # tall at any legible size, which cannot sit on A4 at natural
                # size; this keeps every piece of information and roughly halves
                # the height. Chosen by `paper_layout` in the spec.
                emit(rf"\node[papelinea, below={gap}cm of {prev}] ({pid})")
                emit(
                    "  {{"
                    + rf"\textbf{{{tex(paper['author'])}}}"
                    + r"\;\textcolor{azulUNAL}{"
                    + tex(paper.get("concept", ""))
                    + "}}"
                    + "};"
                )
            else:
                emit(rf"\node[paper, below={gap}cm of {prev}] ({pid})")
                emit(
                    "  {"
                    + rf"{{\bfseries {tex(paper['author'])}}}\\[1pt]"
                    + "{{\\fontsize{" + _f(fonts["paperconcepto"][0]) + "}{"
                    + _f(fonts["paperconcepto"][1]) + "}\\selectfont\\textcolor{azulUNAL}{"
                    + tex(paper.get("concept", "")) + "}}}"
                    + "};"
                )
            line_map[len(lines)] = pid
            node_ids.append(pid)
            prev = pid
        if cluster.get("limitation"):
            emit(rf"\node[limitex, below=0.30cm of {prev}] ({cid}lim)")
            emit(f"  {{{tex(cluster['limitation'])}}};")
            line_map[len(lines)] = f"{cid}lim"
            prev = f"{cid}lim"
        emit(r"% borde del clúster")
        emit(r"\begin{pgfonlayer}{background}")
        emit(rf"  \node[cborde, fit=({cid}t)({prev})] ({cid}box) {{}};")
        emit(r"\end{pgfonlayer}")
        emit("")

        # Close the row with a fit node used to stack the next row.
        if col == cols - 1 or ci == len(clusters) - 1:
            members = "".join(
                f"(c{j + 1}box)" for j in range(row * cols, ci + 1)
            )
            emit(rf"\node[inner sep=0pt] (r{row}fit) [fit={members}] {{}};")
            emit("")

    emit("% ---- Enlaces internos ----")
    for cluster in clusters:
        ids = [p["id"] for p in cluster["papers"]]
        # `arrows` is the relationship set the Bibliografo-Propuesta specified
        # (e.g. "n15 -> n11, n11 -> n12"): a mini-graph, not a chain. Falling
        # back to the consecutive chain keeps the schema usable when a cluster
        # declares no relationships, but the declared set is what gets drawn.
        declared = [tuple(pair) for pair in cluster.get("arrows", [])]
        order = {pid: i for i, pid in enumerate(ids)}
        pairs = declared if declared else list(zip(ids, ids[1:]))
        for a, b in pairs:
            if abs(order[a] - order[b]) <= 1:
                # Adjacent: a short vertical hop across the gap between boxes.
                emit(rf"\draw[enlace] ({a}.south) -- ({b}.north);")
            else:
                # Skips intermediate boxes: detour on the right margin instead of
                # cutting straight through the unrelated fragments between them.
                emit(
                    rf"\draw[enlace] ({a}.east) to[bend right=22] ({b}.east);"
                )
    emit("")
    drawn_links, skipped_links = [], []
    for link in links:
        a, b = link[0], link[1]
        if cluster_row.get(a) == cluster_row.get(b) and abs(
            cluster_col.get(a, 0) - cluster_col.get(b, 0)
        ) == 1:
            drawn_links.append((a, b))
        else:
            skipped_links.append((a, b))
    if drawn_links:
        # Inter-cluster links connect the CLUSTER CARDS and only between
        # neighbours in the SAME row. A cross-row link has to leave rightward and
        # re-enter from the left, wrapping the whole figure: measured at +7.4 cm
        # of width (20.6 cm for a grid whose cards span only ~13 cm). The source
        # block marks these relations as optional, and §4's prose states them, so
        # skipping them in the figure is the honest trade instead of a figure
        # that cannot sit on the page.
        emit("% ---- Enlaces entre clústeres (solo vecinos de la misma fila) ----")
        for a, b in drawn_links:
            emit(
                rf"\draw[enlace, dashed] ({a}box.east) -- ({b}box.west);"
            )
        emit("")
    if skipped_links:
        for a, b in skipped_links:
            emit(
                f"% enlace {a}->{b} omitido en la figura: cruza filas de la "
                "cuadrícula (su relación queda en la prosa de §4)"
            )
        emit("")

    if closing:
        emit("% ---- Frase transversal de cierre ----")
        # Centred on ALL cluster cards, not on the last row: anchoring it to the
        # last row shifted it off-centre and its 15 cm fixed width then pushed
        # the picture's bounding box past the page on the opposite side.
        emit(
            r"\node[inner sep=0pt] (allClusters) [fit="
            + "".join(f"(c{i + 1}box)" for i in range(len(clusters)))
            + r"] {};"
        )
        emit(r"\node[cierre, below=1.1cm of allClusters.south] (cierre)")
        emit(f"  {{{tex(closing)}}};")
        line_map[len(lines)] = "cierre"
        emit("")

    emit(r"\end{tikzpicture}")
    return "\n".join(lines) + "\n", node_ids, line_map


# --------------------------------------------------------------------------
# kind: metodologico
# --------------------------------------------------------------------------
def build_metodologico(spec: dict, over: dict) -> tuple[str, list[int], dict[int, str]]:
    phases = spec["phases"]
    trl = spec.get("trl", {})
    beneficiaries = spec.get("beneficiaries", [])

    fonts = effective_fonts(spec)
    w_fase = over.get("fase") or fit_width(
        [f"{p['title']} {p['text']}" for p in phases], "fase", fonts
    )
    w_novedad = over.get("novedad") or fit_width(
        [p.get("novelty", "") for p in phases], "novedad", fonts
    )
    step = round(w_fase + 1.0, 2)
    n = len(phases)
    # El bloque de beneficiarios abarca la cadena completa. Sin un `text width`
    # propio crecía hasta el ancho de su propio texto y estiraba el diagrama a
    # 22,14 cm, por encima del área de texto de la página (16,26 cm).
    w_benef = round((n - 1) * step + w_fase, 2)
    widths = {
        "W_FASE": w_fase,
        "W_NOVEDAD": w_novedad,
        "W_BENEF": w_benef,
        **font_vars(fonts),
    }
    lines: list[str] = []
    line_map: dict[int, str] = {}

    def emit(text: str, node: str | None = None) -> None:
        lines.append(text)
        if node:
            line_map[len(lines)] = node

    emit("% " + "=" * 69)
    emit("% DIAGRAMA METODOLÓGICO — §10 Metodología")
    emit("% GENERADO por plantilla/scripts/render_tikz.py desde la spec JSON.")
    emit("% No editar a mano. Nunca incluye personal responsable dentro de los")
    emit("% bloques: los responsables viven en §10 (prosa) y §9 (equipo).")
    emit("% " + "=" * 69)
    emit("")
    emit(r"\begin{tikzpicture}[")
    for style_line in _styles("metodologico", widths).splitlines():
        emit(style_line)
    emit("]")
    emit(r"\hyphenpenalty=10000")
    emit(r"\exhyphenpenalty=10000")
    emit(LIBRARIES)
    for name, html in PALETTE.items():
        emit(rf"\definecolor{{{name}}}{{HTML}}{{{html}}}")
    emit("")

    emit("% ---- Fases (cadena horizontal) ----")
    for pi, phase in enumerate(phases):
        x = (pi - (n - 1) / 2) * step
        emit(rf"\node[fase, anchor=north] ({phase['id']}) at ({_f(x)},0)")
        emit(
            "  {"
            + rf"{{\bfseries\textcolor{{azulUNAL}}{{{tex(phase['title'])}}}}}\\[2pt]"
            + tex(phase["text"])
            + "};"
        )
        line_map[len(lines)] = phase["id"]
        if phase.get("novelty"):
            emit(rf"\node[novedad, above=0.7cm of {phase['id']}.north] ({phase['id']}n)")
            emit(f"  {{{tex(phase['novelty'])}}};")
            line_map[len(lines)] = f"{phase['id']}n"
            emit(rf"\draw[flecha, draw=verdeGCPDS] ({phase['id']}n.south) -- ({phase['id']}.north);")
        emit("")

    emit("% ---- Cadena de fases ----")
    for a, b in zip(phases, phases[1:]):
        emit(rf"\draw[flecha] ({a['id']}.east) -- ({b['id']}.west);")
    emit("")

    if trl:
        emit("% ---- Trayectoria TRL ----")
        emit(rf"\node[inner sep=0pt] (fAll) [fit=(" + ")(".join(p["id"] for p in phases) + r")] {};")
        emit(r"\coordinate (trlY) at ($(fAll.south)+(0,-1.6)$);")
        emit(
            r"\draw[trlbarra] ($(fAll.south west)+(0,-1.6)$) -- "
            r"($(fAll.south east)+(0,-1.6)$);"
        )
        start = tex(trl.get("start", ""))
        end = tex(trl.get("end", ""))
        # Los dos marcadores TRL se reparten en los extremos de la barra. Con
        # textos largos la suma supera el ancho de la cadena y se pisaban en el
        # centro, así que se apilan: el inicial arriba y el final abajo, con el
        # rótulo de la barra al lado del final. Se miden en la fuente `etiqueta`,
        # que va en negrita.
        et_pt = fonts["etiqueta"][0]
        side_by_side = (
            line_width_cm(start, et_pt, bold=True)
            + line_width_cm(end, et_pt, bold=True)
            + 0.6
        ) <= w_benef
        if side_by_side:
            emit(rf"\node[etiqueta, anchor=south west] at ($(fAll.south west)+(0,-1.35)$) {{{start}}};")
            emit(rf"\node[etiqueta, anchor=south east] at ($(fAll.south east)+(0,-1.35)$) {{{end}}};")
            emit(r"\node[etiqueta, anchor=north] at ($(fAll.south)+(0,-2.0)$) {Trayectoria TRL};")
        else:
            emit(rf"\node[etiqueta, anchor=south west] at ($(fAll.south west)+(0,-1.35)$) {{{start}}};")
            emit(r"\node[etiqueta, anchor=north west] at ($(fAll.south west)+(0,-1.85)$) {Trayectoria TRL};")
            emit(rf"\node[etiqueta, anchor=north east] at ($(fAll.south east)+(0,-1.85)$) {{{end}}};")
        emit("")

    if beneficiaries:
        emit("% ---- Beneficiarios ----")
        anchor = "trlY" if trl else "fAll.south"
        emit(
            rf"\node[benef, below=1.1cm of {anchor}] (benef) "
            r"{{\bfseries\textcolor{azulUNAL}{Beneficiarios:}}\\[1pt] "
            + tex(" · ".join(beneficiaries))
            + "};"
        )
        line_map[len(lines)] = "benef"
        emit("")

    emit(r"\end{tikzpicture}")
    return "\n".join(lines) + "\n", [], line_map


BUILDERS = {
    "arbol": build_arbol,
    "estado_arte": build_estado_arte,
    "metodologico": build_metodologico,
}


# A node declaration is `\node[OPTIONS] (ID)`; the id is the FIRST parenthesised
# name after the options close. Taking the last one instead picked up a `calc`
# coordinate reference (`$(ramaAnchor)`) and sent a fix looking for a style
# literally named `ramaAnchor` (observed).
NODE_NAME_RE = re.compile(r"^\s*\\node\[[^\]]*\]\s*\(([A-Za-z][\w]*)\)")


def build_line_map(lines: list[str]) -> dict[int, str]:
    """Map every emitted line of a node's block to that node's id.

    Derived from the generated source itself instead of being threaded through
    the builders by hand: leaking a line out of the map is what made an autofix
    land on the wrong node. A node block runs from its `\\node[...] (id)`
    declaration to the `};` that closes its body, so every line of the block is
    covered and a fix can never fall back to "the nearest earlier node".
    """
    line_map: dict[int, str] = {}
    current: str | None = None
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if "fit=" in stripped and stripped.startswith(r"\node["):
            # Helper fit nodes carry no text of their own; their children are
            # already mapped, so a report can never point inside them.
            current = None
            continue
        match = NODE_NAME_RE.match(line)
        if match:
            current = match.group(1)
            line_map[number] = current
            if stripped.endswith(";"):
                current = None
            continue
        if current is not None:
            line_map[number] = current
            if stripped.endswith(";"):
                current = None
    return line_map


def validate_spec(spec: dict) -> None:
    """Fail early, with an actionable message, on a malformed spec.

    The spec is authored by an agent, so a clear error is the difference between
    one self-correcting retry and a cryptic pgf failure deep inside a compile
    (observed: `No shape named 'c4n1' is known` from a link pointing at a paper
    id that does not exist). Errors name the offending field.
    """
    kind = spec.get("kind")
    if kind not in BUILDERS:
        raise SystemExit(
            f"spec.kind debe ser uno de {sorted(BUILDERS)}; recibido: {kind!r}"
        )

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise SystemExit(f"spec inválida: {message}")

    if kind == "arbol":
        for key in ("groups", "branches", "trunk", "crown"):
            require(key in spec, f"falta '{key}'")
        require(bool(spec["groups"]), "'groups' no puede estar vacío")
        require(bool(spec["branches"]), "'branches' no puede estar vacío")
        for key in ("label", "text"):
            require(key in spec["trunk"], f"falta 'trunk.{key}'")
            require(key in spec["crown"], f"falta 'crown.{key}'")
        ids: list[str] = []
        for group in spec["groups"]:
            require("id" in group and "title" in group, "cada grupo necesita 'id' y 'title'")
            require(bool(group.get("causes")), f"el grupo {group.get('id')} no tiene causas")
            for cause in group["causes"]:
                require(
                    "id" in cause and "text" in cause,
                    f"cada causa de {group['id']} necesita 'id' y 'text'",
                )
                ids.append(cause["id"])
        for branch in spec["branches"]:
            require("id" in branch and "text" in branch, "cada rama necesita 'id' y 'text'")
            ids.append(branch["id"])
        for group in spec["groups"]:
            ids.append(f"t{group['id']}")
        _require_unique(ids, "ids del árbol")

    elif kind == "estado_arte":
        require(bool(spec.get("clusters")), "'clusters' no puede estar vacío")
        paper_ids: list[str] = []
        for index, cluster in enumerate(spec["clusters"], start=1):
            require(
                bool(cluster.get("papers")),
                f"el clúster {index} ({cluster.get('title', '?')}) no tiene papers",
            )
            for paper in cluster["papers"]:
                for key in ("id", "author", "concept"):
                    require(
                        key in paper,
                        f"cada paper del clúster {index} necesita 'id', 'author' y 'concept' "
                        f"(falta '{key}')",
                    )
                paper_ids.append(paper["id"])
        _require_unique(paper_ids, "ids de paper")
        cluster_ids = [f"c{i + 1}" for i in range(len(spec["clusters"]))]
        for link in spec.get("links", []):
            require(
                len(link) == 2,
                f"cada enlace entre clústeres es un par [origen, destino]; recibido {link!r}",
            )
            for endpoint in link:
                require(
                    endpoint in cluster_ids,
                    f"el enlace {link!r} apunta a '{endpoint}', que no es un id de "
                    f"clúster (disponibles: {cluster_ids}); las relaciones internas "
                    "se declaran con 'arrows' dentro de cada clúster",
                )
        for index, cluster in enumerate(spec["clusters"], start=1):
            own = {p["id"] for p in cluster["papers"]}
            for pair in cluster.get("arrows", []):
                require(
                    len(pair) == 2,
                    f"cada arista del clúster {index} es un par [origen, destino]; "
                    f"recibido {pair!r}",
                )
                for endpoint in pair:
                    require(
                        endpoint in own,
                        f"la arista {pair!r} del clúster {index} apunta a "
                        f"'{endpoint}', que no pertenece a ese clúster "
                        f"(ids del clúster: {sorted(own)})",
                    )

    elif kind == "metodologico":
        require(bool(spec.get("phases")), "'phases' no puede estar vacío")
        for phase in spec["phases"]:
            for key in ("id", "title", "text"):
                require(key in phase, f"cada fase necesita 'id', 'title' y 'text' (falta '{key}')")
        _require_unique([p["id"] for p in spec["phases"]], "ids de fase")


def _require_unique(ids: list[str], what: str) -> None:
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise SystemExit(f"spec inválida: {what} repetidos: {duplicates}")


def assert_balanced_braces(text: str, kind: str) -> None:
    """Fail the render when the generated TeX has unbalanced braces.

    A missing closing brace does not produce a clear TeX error: the picture
    swallows the next construct and fails later with `Undefined control
    sequence` at an unrelated line (observed: one missing `}` in the
    estado_arte paper-node body produced exactly that at the following `\node`).
    Checking balance here turns it into an immediate, localisable error.
    """
    depth = 0
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("%"):
            continue
        depth += line.count("{") - line.count("}")
        if depth < 0:
            raise SystemExit(
                f"render de {kind}: llaves desbalanceadas en la línea {number} "
                f"(profundidad {depth}); revisa los constructores de estilo o de nodo"
            )
    if depth != 0:
        raise SystemExit(
            f"render de {kind}: el documento generado termina con {depth} llave(s) "
            "sin cerrar"
        )


def render(spec: dict, overrides: dict) -> tuple[str, dict[int, str]]:
    validate_spec(spec)
    kind = spec["kind"]
    text, _ids, _map = BUILDERS[kind](spec, overrides)
    assert_balanced_braces(text, kind)
    return text, build_line_map(text.splitlines())

def resolve_paths(spec_path: pathlib.Path, out: str | None, over: str | None):
    out_path = pathlib.Path(out) if out else spec_path.with_suffix("")
    if out_path.suffix != ".tex":
        out_path = out_path.with_suffix(".tex")
    over_path = (
        pathlib.Path(over)
        if over
        else spec_path.with_name(out_path.stem + ".overrides.json")
    )
    return out_path, over_path


def load_overrides(over_path: pathlib.Path) -> dict:
    if over_path.exists():
        try:
            data = json.loads(over_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data.get("widths", {}) if isinstance(data, dict) else {}
    return {}


def save_overrides(over_path: pathlib.Path, widths: dict) -> None:
    over_path.write_text(
        json.dumps({"_note": "Anchos ensanchados por render_tikz.py --fix-overfull.", "widths": widths}, indent=2)
        + "\n",
        encoding="utf-8",
    )


def apply_overfull_fix(
    line_map: dict[int, str], overrides: dict, item: str, spec: dict
) -> str:
    """Widen exactly the node that overflowed, by the amount pdflatex measured.

    `item` is `<source line>:<pt too wide>` as reported by `compile_tikz.py`'s
    `OVERFULL:` token. The source line is mapped back to a node id through the
    sidecar map written on the previous render, so the fix targets the real
    overflow instead of guessing.
    """
    m = re.match(r"^\s*(\d+)\s*:\s*([0-9.]+)\s*$", item)
    if not m:
        raise SystemExit(
            f"--fix-overfull espera '<línea>:<pt>' (p. ej. '84:1.51'); recibido: {item!r}"
        )
    src_line = int(m.group(1))
    pt = float(m.group(2))

    node = line_map.get(src_line)
    if node is None:
        # The reported line may fall on the closing brace of a multi-line node
        # body; walk back to the nearest mapped line.
        for candidate in range(src_line, 0, -1):
            if candidate in line_map:
                node = line_map[candidate]
                break
    if node is None:
        raise SystemExit(
            f"no hay nodo mapeado para la línea {src_line}; "
            "no se puede aplicar el fix determinista"
        )

    # The overflowing node's role determines which style width to widen; the
    # increment is converted with that role's type size.
    role = role_for_node(node)

    increment_cm = max(round(pt * 0.03528 + 0.12, 2), 0.12)
    base = overrides.get(role)
    canonical = _current_width_of(role, spec)
    if base is None:
        base = canonical
    # Jump straight to the canonical fit width when it is wider than the current
    # one: the renderer already knows the longest unbreakable word, so climbing
    # from the measured overflow centimetre by centimetre only burns compile
    # iterations. `max` keeps the override authoritative when an earlier fix
    # already pushed the node past the canonical ceiling.
    new_width = round(max(float(base) + increment_cm, canonical), 2)
    if new_width <= float(base) + 1e-9:
        raise SystemExit(
            f"el nodo '{node}' (rol '{role}') no puede crecer más "
            f"({_f(base)} cm, tope canónico {_f(canonical)} cm) y sigue desbordando: "
            "el texto es demasiado largo para un ancho legible. Acórtalo o divídelo "
            "en dos bloques en la spec; no reduzcas la fuente."
        )
    overrides[role] = new_width
    return (
        f"FIX: nodo '{node}' (rol '{role}') {_f(base)} cm -> {_f(new_width)} cm "
        f"(+{_f(increment_cm)} cm por {pt}pt)"
    )


def _current_width_of(role: str, spec: dict) -> float:
    """Recompute the width the renderer would have used for `role` without overrides."""
    text, _map = render(spec, {})
    m = re.search(rf"{re.escape(role)}/\.style=\{{[^}}]*text width=([0-9.]+)cm", text)
    if not m:
        raise SystemExit(f"no se pudo leer el text width del rol '{role}'")
    return float(m.group(1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec", type=pathlib.Path, help="ruta del JSON de especificación")
    ap.add_argument("-o", "--out", help="ruta del .tex de salida (por defecto, el spec con .tex)")
    ap.add_argument(
        "--fix-overfull",
        metavar="LINE:PT",
        help="ensancha el nodo que desbordó, usando el token OVERFULL de compile_tikz.py",
    )
    ap.add_argument("--overrides", help="ruta del JSON de overrides de ancho")
    ap.add_argument(
        "--print-map",
        action="store_true",
        help="imprime el mapa línea->nodo en JSON (para depurar el autofix)",
    )
    args = ap.parse_args(argv)

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    out_path, over_path = resolve_paths(args.spec, args.out, args.overrides)
    overrides = load_overrides(over_path)

    # A fix needs the map of the *previous* render, so it is computed first.
    if args.fix_overfull:
        _text, line_map = render(spec, overrides)
        message = apply_overfull_fix(line_map, overrides, args.fix_overfull, spec)
        save_overrides(over_path, overrides)
        print(message)
        text, line_map = render(spec, overrides)
    else:
        text, line_map = render(spec, overrides)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    # Sidecar map: 1-based line inside the .tex -> node id, for `--fix-overfull`.
    map_path = out_path.with_suffix(".map.json")
    map_path.write_text(
        json.dumps({str(k): v for k, v in sorted(line_map.items())}, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"RENDER: {out_path} ({len(text.splitlines())} líneas)")
    if args.print_map:
        print(json.dumps({str(k): v for k, v in sorted(line_map.items())}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
