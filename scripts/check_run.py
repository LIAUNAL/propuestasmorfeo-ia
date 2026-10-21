#!/usr/bin/env python3
"""Deterministic checks for a proposal run, run by the dispatcher before each gate.

The revisor agent judges coherence and quality; this script covers what a
regular expression can prove, so the agent does not spend tokens re-deriving
it and a violation cannot slip through a gate (two em dashes in §10 of the
reference run did). Standard library only: every runtime (Claude Code, Pi,
OpenCode, Antigravity) runs it the same way.

Usage:
  python3 scripts/check_run.py [RUN_ROOT] [--final] [--json] [--flujo {base,sgr}]

RUN_ROOT defaults to the run named in proposals/.current-run. Without --final,
only files that already exist are checked (a mid-pipeline gate); --final also
requires every canonical section, a filled cover and the total reference
floor. Exit code 1 when any error is found. --json prints an object
{"flujo": ..., "findings": [...]}.

Flow (flujo): read from the first `.morfeo/config.json` or `.marco/config.json`
found from RUN_ROOT upwards ("base" when missing or invalid); --flujo overrides
it. Both flows apply the SGR guide rules (MGA, DNP) to the problem and
objective trees when their files exist:
  problem tree (redaccion/specs/arbol_problemas.spec.json):
    arbol-ausencia-de-solucion (error), arbol-solucion-en-problema (error),
    arbol-problema-sin-calificativo-negativo (error, central problem only),
    arbol-sin-efectos (error), arbol-sin-magnitud (warning),
    arbol-causa-directa-sin-indirectas (warning), arbol-sin-efecto-final (warning)
  objective tree (artefactos/arboles/arbol_objetivos.json):
    arbol-objetivos-no-infinitivo, objetivo-general-con-medio,
    objetivo-general-con-fin, objetivo-general-con-meta, arbol-espejo-roto,
    arbol-variable-cambiada (error on the trunk, warning on a group)
  base flow: objetivo-general-sin-variable-del-arbol (warning, §6 vs tree)
  SGR flow: sgr-objetivo-general-distinto, sgr-objetivos-especificos-distintos
    (§6/§7 must be the objective tree texts), sgr-titulo-no-derivado (the
    title is the general objective with its verb as a noun), and with --final
    sgr-anexo-faltante for each missing MGA annex in SGR_SECTIONS.
The tree rule functions (problem_tree_findings, objective_tree_findings,
shared_variable, detect_flujo) are pure and imported by the dashboard.

Reference floors come from guiaProyectosIA_Agente.md (§2 "al menos 13
referencias", §4 "al menos 39 referencias", §16 total of 65); a test keeps
these constants and the guide in step.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

FLOOR_JUSTIFICACION = 13
FLOOR_ESTADO_ARTE = 39
FLOOR_TOTAL = 65
MAX_KEYS_PER_CALL = 3
MAX_USES_PER_KEY = 3

CANONICAL_SECTIONS = (
    "00_frontmatter", "02_justificacion", "03_descripcion_problema", "04_estado_arte",
    "05_hipotesis", "06_objetivo_general", "07_objetivos_especificos", "08_marco_conceptual",
    "09_equipo_trabajo", "10_metodologia", "11_resultados_esperados", "12_consideraciones_eticas",
    "13_presupuesto", "14_cronograma_actividades", "15_productos_esperados", "16_bibliografia",
    "17_articulacion_comunidades", "18_apropiacion_social",
)

# MGA annexes of the SGR flow (S5); the base flow never requires them.
SGR_SECTIONS = (
    "19_alineacion_planes", "20_participantes", "21_poblacion", "22_alternativas",
    "23_cadena_valor", "24_riesgos", "25_marco_logico",
)
FLUJOS = ("base", "sgr")
PROBLEM_SPEC = Path("redaccion") / "specs" / "arbol_problemas.spec.json"
OBJECTIVES_FILE = Path("artefactos") / "arboles" / "arbol_objetivos.json"
REVIEW_FILE = Path("artefactos") / "arboles" / "revision.json"
# Tree figures that must be compiled from the spec the panel shows.
TREE_FIGURES = {"arbol_problemas": "problemas", "arbol_objetivos": "objetivos"}

# Environments whose content is not narrative prose (tables, drawings, code, math)
NON_PROSE_ENVS = (
    "tabular", "tabularx", "xltabular", "longtable", "tikzpicture", "ganttchart",
    "verbatim", "lstlisting", "equation", "align", "math", "displaymath",
)
CITE_RE = re.compile(
    r"\\(cite|citep|citet|citealp|citealt|citeauthor|citeyear|citeyearpar|nocite)\*?"
    r"(?:\[[^\]]*\]){0,2}\{([^}]*)\}",
    re.S,
)
BEGIN_RE = re.compile(r"\\begin\{(" + "|".join(NON_PROSE_ENVS) + r")\*?\}")
END_RE = re.compile(r"\\end\{(" + "|".join(NON_PROSE_ENVS) + r")\*?\}")


def strip_comment(line: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", line)


class Report:
    def __init__(self, run_root: Path) -> None:
        self.run_root = run_root
        self.findings: list[dict] = []
        self.flujo = "base"

    def add(self, severity: str, code: str, message: str, path: Path | None = None, line: int | None = None,
            node: str | None = None) -> None:
        rel = ""
        if path is not None:
            try:
                rel = path.relative_to(self.run_root).as_posix()
            except ValueError:
                rel = str(path)
        finding = {"severity": severity, "code": code, "file": rel, "line": line, "message": message}
        if node is not None:
            finding["node"] = node
        self.findings.append(finding)

    def errors(self) -> int:
        return sum(1 for f in self.findings if f["severity"] == "error")


def prose_lines(text: str):
    """Yield (line number, text) for narrative lines: no comments, tables, drawings or math."""
    depth = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = strip_comment(raw)
        opens, closes = len(BEGIN_RE.findall(line)), len(END_RE.findall(line))
        if depth == 0 and opens == 0:
            prose = re.sub(r"\\url\{[^}]*\}|\\href\{[^}]*\}", "", line)
            prose = re.sub(r"\$[^$]*\$", "", prose)
            yield number, prose
        depth = max(0, depth + opens - closes)


def cite_calls(text: str):
    """Yield (line number, keys) for each logical citation call, comments removed."""
    clean = "\n".join(strip_comment(l) for l in text.splitlines())
    for match in CITE_RE.finditer(clean):
        keys = [k.strip() for k in match.group(2).split(",") if k.strip()]
        yield clean.count("\n", 0, match.start()) + 1, match.group(1), keys


def check_prose(report: Report, path: Path, text: str) -> None:
    for number, line in prose_lines(text):
        if "—" in line or "---" in line:
            report.add("error", "raya-en-prosa", "Raya (— o ---) en prosa: usar coma, punto y coma o paréntesis.",
                       path, number)
        if "--" in line.replace("---", ""):
            report.add("error", "doble-guion-en-prosa", "Doble guion (--) en prosa.", path, number)


def check_citations(report: Report, sections: dict[str, Path], texts: dict[str, str]) -> dict[str, set[str]]:
    keys_by_section: dict[str, set[str]] = {}
    total_uses: dict[str, int] = {}
    first_seen: dict[str, tuple[Path, int]] = {}
    for name, path in sections.items():
        seen_here: set[str] = set()
        keys_by_section[name] = set()
        for number, command, keys in cite_calls(texts[name]):
            if command == "cite":
                report.add("error", "cite-generico", "\\cite{} genérico: usar \\citep{} o \\citet{} (APA autor-año).",
                           path, number)
            if command != "nocite" and len(keys) > MAX_KEYS_PER_CALL:
                report.add("error", "cita-mas-de-3-claves",
                           f"Llamada con {len(keys)} claves (máximo {MAX_KEYS_PER_CALL}).", path, number)
            for key in keys:
                if command == "nocite":
                    continue
                keys_by_section[name].add(key)
                if key in seen_here:
                    report.add("error", "clave-repetida-en-seccion",
                               f"La clave {key} se cita dos veces en la misma sección.", path, number)
                seen_here.add(key)
                total_uses[key] = total_uses.get(key, 0) + 1
                first_seen.setdefault(key, (path, number))
    for key, uses in sorted(total_uses.items()):
        if uses > MAX_USES_PER_KEY:
            path, number = first_seen[key]
            report.add("error", "clave-sobreusada",
                       f"La clave {key} se usa {uses} veces (máximo {MAX_USES_PER_KEY}).", path, number)
    return keys_by_section


def check_floors(report: Report, sections: dict[str, Path], keys_by_section: dict[str, set[str]], final: bool) -> None:
    for name, floor in (("02_justificacion", FLOOR_JUSTIFICACION), ("04_estado_arte", FLOOR_ESTADO_ARTE)):
        if name in keys_by_section and len(keys_by_section[name]) < floor:
            report.add("error", "piso-referencias",
                       f"{name} cita {len(keys_by_section[name])} referencias distintas (mínimo {floor}).",
                       sections[name])
    if final:
        total = set().union(*keys_by_section.values()) if keys_by_section else set()
        if len(total) < FLOOR_TOTAL:
            report.add("error", "piso-referencias",
                       f"El documento cita {len(total)} referencias distintas (mínimo {FLOOR_TOTAL}).")


def check_trl(report: Report, sections: dict[str, Path], texts: dict[str, str]) -> None:
    trl = re.compile(r"\bTRL\b")
    for name in ("06_objetivo_general", "07_objetivos_especificos"):
        if name in texts:
            for number, line in prose_lines(texts[name]):
                if trl.search(line):
                    report.add("error", "trl-en-objetivos",
                               "TRL nombrado en un objetivo: expresar el nivel de forma funcional.",
                               sections[name], number)
    for name in ("02_justificacion", "11_resultados_esperados"):
        if name in texts and not any(trl.search(l) for _, l in prose_lines(texts[name])):
            report.add("error", "trl-ausente", "TRL 6 o 7 debe ser explícito en esta sección.", sections[name])
    if "10_metodologia" in texts and not trl.search(texts["10_metodologia"]):
        report.add("warning", "trl-ausente", "El revisor espera la trayectoria TRL en la metodología.",
                   sections["10_metodologia"])


def check_objectives(report: Report, sections: dict[str, Path], texts: dict[str, str]) -> None:
    name = "07_objetivos_especificos"
    if name not in texts:
        return
    match = re.search(r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}", texts[name], re.S)
    items = len(re.findall(r"^\s*\\item\b", match.group(1), re.M)) if match else 0
    if items != 3:
        report.add("error", "objetivos-no-son-3",
                   f"§7 enumera {items} objetivos específicos; el mapeo 1:1 exige 3.", sections[name])


def check_main(report: Report, red: Path, final: bool) -> None:
    main = red / "main.tex"
    if not main.is_file():
        if final:
            report.add("error", "main-ausente", "No existe redaccion/main.tex.")
        return
    text = main.read_text(encoding="utf-8", errors="replace")
    clean = "\n".join(strip_comment(l) for l in text.splitlines())
    if r"\setcounter{section}{1}" not in clean:
        report.add("error", "setcounter-ausente", "main.tex debe fijar \\setcounter{section}{1} (el cuerpo arranca en §2).",
                   main)
    if re.search(r"\\input\{sections/01_", clean):
        report.add("error", "seccion-1-en-cuerpo", "main.tex incluye una sección §1; el título va solo en la portada.",
                   main)
    # A logo wrapped in \IfFileExists is optional (the UTP one), wherever the
    # guarded \includegraphics sits: the template puts it on the next line.
    guarded = set(re.findall(r"\\IfFileExists\{(logos/[^}]+)\}", clean))
    for number, line in enumerate(text.splitlines(), start=1):
        line = strip_comment(line)
        for logo in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{(logos/[^}]+)\}", line):
            if logo in guarded:
                continue
            if not (red / logo).is_file():
                report.add("error", "logo-inexistente", f"{logo} no existe en redaccion/.", main, number)
    if r"\DiagramaSiExiste" in clean:
        for diag in sorted((red / "sections").glob("diag_*.tex")):
            if diag.stem.endswith("_caption"):
                continue
            if not (red / "sections" / f"{diag.stem}_caption.tex").is_file():
                report.add("error" if final else "warning", "caption-faltante",
                           f"{diag.name} no tiene {diag.stem}_caption.tex (caption concreto y \\label).", diag)


def check_cover(report: Report, red: Path, final: bool) -> None:
    datos = red / "datos_proyecto.tex"
    if not datos.is_file():
        return
    # Only the \newcommand values count: the seeded file explains the
    # placeholder in a comment, which must not keep the cover "incomplete".
    values = "\n".join(strip_comment(l) for l in datos.read_text(encoding="utf-8", errors="replace").splitlines())
    if "[Por definir" in values:
        report.add("error" if final else "warning", "portada-sin-completar",
                   "datos_proyecto.tex conserva campos [Por definir: ...].", datos)


def check_bibliography(report: Report, sections: dict[str, Path], texts: dict[str, str]) -> None:
    name = "16_bibliografia"
    if name not in texts:
        return
    clean = "\n".join(strip_comment(l) for l in texts[name].splitlines())
    if r"\renewcommand{\bibsection}{}" not in clean:
        report.add("error", "bibsection-ausente", "Falta \\renewcommand{\\bibsection}{} (título duplicado).",
                   sections[name])
    if r"\clearpage" not in clean:
        report.add("warning", "clearpage-ausente", "La bibliografía debe abrir con \\clearpage.", sections[name])


def check_pdf(report: Report, red: Path) -> None:
    pdf = red / "main.pdf"
    if not pdf.is_file() or shutil.which("pdftotext") is None:
        return
    result = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True)
    for match in re.finditer(r"\bCuadro \d+", result.stdout):
        report.add("error", "cuadro-en-pdf", f"El PDF dice «{match.group(0)}»: las tablas se llaman «Tabla».", pdf)
        break


# --- Flow and tree rules of the SGR guide (MGA, DNP) -------------------------

def detect_flujo(run_root: Path) -> str:
    """Flow of the project that holds `run_root`: the first `.morfeo/config.json`
    or `.marco/config.json` found from `run_root` upwards decides; "base" when
    none exists or its value is not a known flow."""
    try:
        start = Path(run_root).resolve()
    except OSError:
        return "base"
    for folder in (start, *start.parents):
        for name in (".morfeo", ".marco"):
            config = folder / name / "config.json"
            if not config.is_file():
                continue
            try:
                data = json.loads(config.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                return "base"
            value = data.get("flujo") if isinstance(data, dict) else None
            return value if value in FLUJOS else "base"
    return "base"


MGA_PROBLEM_RULE = ("«Un problema no es la ausencia de su solución, sino un estado existente negativo» "
                    "(Instructivo MGA 2023, p. 122)")
ABSENCE_RE = re.compile(
    r"\b(falta|ausencia|carencia|inexistencia)\s+de\b|\bno\s+(existe|existen|hay)\b"
    r"|\bse\s+requiere\b|\bnecesidad\s+de\b", re.I)
INFINITIVE_RE = re.compile(r"^[a-záéíóúñ]+(ar|er|ir)$")
# Spanish nouns and adjectives that end like an infinitive.
NOT_INFINITIVES = frozenset({
    "lugar", "hogar", "hogares", "poder", "mujer", "particular", "militar", "escolar", "familiar", "regular",
    "similar", "popular", "titular", "auxiliar", "peculiar", "singular", "circular", "celular", "molecular",
    "muscular", "vascular", "nuclear", "solar", "lunar", "polar", "estelar", "ejemplar", "secular", "bipolar",
    "altar", "pilar", "collar", "radar", "hangar", "azúcar", "dólar", "primer", "taller", "placer", "deber",
    "amanecer", "cáncer", "carácter", "líder", "mártir", "elixir", "nadir", "mayor", "menor", "par", "mar",
    "bar", "alfiler", "alquiler", "cadáver", "esfínter", "suéter", "póster", "máster", "chofer", "chófer",
    "sector", "superior", "inferior", "exterior", "interior", "anterior", "posterior",
    "irregular", "insular", "tabular", "angular", "rectangular", "ocular", "vulgar", "lumbar",
    "bienestar", "malestar", "consular", "escolar", "titular", "modular", "celular",
})
MEANS_RE = re.compile(r"\b(mediante|a\s+trav[eé]s\s+de|por\s+medio\s+de|por\s+intermedio\s+de)\b", re.I)
ENDS_RE = re.compile(r"\bpara\s+[a-záéíóúñ]+(ar|er|ir)\b|\bcon\s+el\s+(fin|prop[oó]sito|objetivo)\s+de\b", re.I)
TARGET_RE = re.compile(r"\d+(?:[.,]\d+)?\s*%")
NODE_PREFIX_RE = re.compile(r"^(SP|OE|CD|C)\d+\s*[·:.\-]\s*", re.I)
STOPWORDS = frozenset({
    "sobre", "entre", "desde", "hasta", "hacia", "segun", "durante", "mediante", "contra", "donde", "cuando",
    "porque", "aunque", "mismo", "misma", "mismos", "mismas", "otros", "otras", "estos", "estas",
    "aquellos", "aquellas", "cuales", "parte", "traves", "todos", "todas", "nivel", "niveles", "indice",
    "indices", "grado", "altos", "altas", "bajos", "bajas", "elevado", "elevados", "elevada", "elevadas",
    "escaso", "escasa", "escasos", "escasas", "deficiente", "deficientes", "limitado", "limitada",
    "limitados", "limitadas", "insuficiente", "insuficientes", "mayor", "menor", "mejor", "peor",
    "general", "especifico", "especifica", "medio", "medios",
})


def normalize_tree_text(text) -> str:
    """Plain text of a tree node: simple LaTeX removed, `\\n` and line breaks as spaces."""
    if not isinstance(text, str):
        return ""
    text = text.replace("\\n", " ")
    text = re.sub(r"\\(textbf|textit|emph|texttt|mbox|textsc|underline)\{([^{}]*)\}", r"\2", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", text)
    text = text.replace("~", " ").replace("{", "").replace("}", "").replace("\\", "")
    return re.sub(r"\s+", " ", text).strip()


def _node_body(text) -> str:
    """Normalized text without a leading node id such as «SP1 · »."""
    return NODE_PREFIX_RE.sub("", normalize_tree_text(text))


def _first_word(text: str) -> str:
    match = re.match(r"[^\W\d_]+", text)
    return match.group(0).lower() if match else ""


def starts_with_infinitive(text) -> bool:
    word = _first_word(_node_body(text))
    return bool(INFINITIVE_RE.match(word)) and word not in NOT_INFINITIVES


def _fold(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn")


def _content_words(text) -> set[str]:
    words = [_fold(w.lower()) for w in re.findall(r"[^\W\d_]+", _node_body(text))]
    return {w for w in words[1:] if len(w) >= 5 and w not in STOPWORDS}


def shared_variable(ref: str, other: str) -> float:
    """Share of the content words of `ref` (the problem text) that `other` keeps.
    The first word (the qualifier or the verb) does not count. 1.0 when `ref`
    has no content words, since there is nothing to lose."""
    ref_words = _content_words(ref)
    if not ref_words:
        return 1.0
    return len(ref_words & _content_words(other)) / len(ref_words)


# Negative qualifiers a central problem may open with: they describe an existing
# negative state without denoting a lack (sgrguia examples and the SGR team's
# recommendation: poco, escaso, limitado, insuficiente, deficiente). Folded.
NEGATIVE_QUALIFIERS = frozenset(
    f"{stem}{end}"
    for stem, ends in (
        ("poc", ("o", "a", "os", "as")), ("escas", ("o", "a", "os", "as")),
        ("limitad", ("o", "a", "os", "as")), ("baj", ("o", "a", "os", "as")),
        ("alt", ("o", "a", "os", "as")), ("elevad", ("o", "a", "os", "as")),
        ("reducid", ("o", "a", "os", "as")), ("inadecuad", ("o", "a", "os", "as")),
        ("inapropiad", ("o", "a", "os", "as")), ("precari", ("o", "a", "os", "as")),
        ("excesiv", ("o", "a", "os", "as")), ("fragmentad", ("o", "a", "os", "as")),
        ("inequitativ", ("o", "a", "os", "as")), ("lent", ("o", "a", "os", "as")),
        ("insuficiente", ("", "s")), ("deficiente", ("", "s")), ("ineficiente", ("", "s")),
        ("inestable", ("", "s")), ("creciente", ("", "s")), ("desigual", ("", "es")),
        ("irregular", ("", "es")), ("debil", ("", "es")), ("ineficaz", ("",)), ("ineficaces", ("",)),
    )
    for end in ends
)


def opens_with_negative_qualifier(text) -> bool:
    return _fold(_first_word(_node_body(text))) in NEGATIVE_QUALIFIERS


def _finding(severity: str, code: str, node: str, message: str) -> dict:
    return {"severity": severity, "code": code, "node": node, "message": message}


def _problem_nodes(spec: dict):
    """(node id, text) of every node of the problem tree."""
    yield "trunk", (spec.get("trunk") or {}).get("text")
    yield "crown", (spec.get("crown") or {}).get("text")
    for group in spec.get("groups") or []:
        yield str(group.get("id") or ""), group.get("title")
        for cause in group.get("causes") or []:
            yield str(cause.get("id") or ""), cause.get("text")
    for branch in spec.get("branches") or []:
        yield str(branch.get("id") or ""), branch.get("text")


def problem_tree_findings(spec: dict) -> list[dict]:
    """SGR guide rules for the problem tree; empty texts are not findings."""
    if not isinstance(spec, dict):
        return []
    findings = []
    for node, raw in _problem_nodes(spec):
        text = _node_body(raw)
        if not text:
            continue
        if ABSENCE_RE.search(text):
            findings.append(_finding("error", "arbol-ausencia-de-solucion", node,
                                     f"{MGA_PROBLEM_RULE}: describe la situación negativa que existe hoy."))
        if starts_with_infinitive(text):
            findings.append(_finding("error", "arbol-solucion-en-problema", node,
                                     "El árbol de problemas describe la situación negativa; la solución va en el "
                                     "árbol de objetivos."))
    trunk_text = _node_body((spec.get("trunk") or {}).get("text"))
    if trunk_text and not opens_with_negative_qualifier(trunk_text):
        findings.append(_finding("error", "arbol-problema-sin-calificativo-negativo", "trunk",
                                 "El problema central empieza con un calificativo negativo que no indique carencia "
                                 "(poco, escaso, limitado, insuficiente, deficiente, bajo, alto…)."))
    magnitude = (spec.get("trunk") or {}).get("magnitude")
    if not (isinstance(magnitude, dict) and str(magnitude.get("indicador") or "").strip()
            and str(magnitude.get("fuente") or "").strip()):
        findings.append(_finding("warning", "arbol-sin-magnitud", "trunk",
                                 "El problema central no registra su magnitud: agrega indicador, valor y fuente "
                                 "como línea base."))
    if not spec.get("branches"):
        findings.append(_finding("error", "arbol-sin-efectos", "trunk",
                                 "El árbol no tiene efectos directos: cada problema central produce efectos."))
    for group in spec.get("groups") or []:
        if not group.get("causes"):
            findings.append(_finding("warning", "arbol-causa-directa-sin-indirectas", str(group.get("id") or ""),
                                     "La causa directa no tiene causas indirectas debajo."))
    if not normalize_tree_text((spec.get("crown") or {}).get("text")):
        findings.append(_finding("warning", "arbol-sin-efecto-final", "crown",
                                 "Falta el efecto final (efecto indirecto) en la copa del árbol."))
    return findings


def objective_tree_findings(objectives: dict, problem_spec: dict) -> list[dict]:
    """SGR guide rules for the objective tree, the positive mirror of `problem_spec`."""
    if not isinstance(objectives, dict):
        return []
    problem_spec = problem_spec if isinstance(problem_spec, dict) else {}
    findings = []
    groups = objectives.get("groups") or []
    branches = objectives.get("branches") or []
    trunk = normalize_tree_text((objectives.get("trunk") or {}).get("text"))

    positive = [("trunk", trunk), ("crown", (objectives.get("crown") or {}).get("text"))]
    for group in groups:
        positive.append((str(group.get("id") or ""), group.get("objective")))
        positive += [(str(m.get("id") or ""), m.get("text")) for m in group.get("means") or []]
    positive += [(str(b.get("id") or ""), b.get("text")) for b in branches]
    for node, raw in positive:
        if _node_body(raw) and not starts_with_infinitive(raw):
            findings.append(_finding("error", "arbol-objetivos-no-infinitivo", node,
                                     "El árbol de objetivos se escribe en positivo y empieza con un verbo en "
                                     "infinitivo."))

    if trunk:
        if MEANS_RE.search(trunk):
            findings.append(_finding("error", "objetivo-general-con-medio", "trunk",
                                     "El objetivo general no incluye el medio («mediante…, por intermedio de…, a "
                                     "través de…»): los medios van en las raíces del árbol."))
        if ENDS_RE.search(trunk):
            findings.append(_finding("error", "objetivo-general-con-fin", "trunk",
                                     "El objetivo general no incluye los fines («…para mejorar la calidad de "
                                     "vida»): los fines van en las ramas del árbol."))
        if TARGET_RE.search(trunk):
            findings.append(_finding("error", "objetivo-general-con-meta", "trunk",
                                     "El objetivo general no incluye metas: la cuantificación va en los "
                                     "indicadores."))

    pgroups = problem_spec.get("groups") or []
    pbranches = problem_spec.get("branches") or []
    group_ids = {str(g.get("id")) for g in pgroups}
    cause_ids = {str(c.get("id")) for g in pgroups for c in g.get("causes") or []}
    branch_ids = {str(b.get("id")) for b in pbranches}
    by_id = {str(g.get("id")): g for g in pgroups}

    def broken(node: str, message: str) -> None:
        findings.append(_finding("error", "arbol-espejo-roto", node, message))

    if len(groups) != len(pgroups):
        broken("trunk", f"El árbol de objetivos tiene {len(groups)} objetivos específicos y el de problemas "
                        f"{len(pgroups)} causas directas: cada causa directa da un objetivo específico.")
    if len(branches) != len(pbranches):
        broken("trunk", f"El árbol de objetivos tiene {len(branches)} fines y el de problemas {len(pbranches)} "
                        "efectos: cada efecto da un fin.")
    pairs = []
    for i, group in enumerate(groups):
        node = str(group.get("id") or "")
        source = group.get("from")
        if source is not None and str(source) not in group_ids:
            broken(node, f"«{source}» no es una causa directa del árbol de problemas.")
        pgroup = by_id.get(str(source)) if source is not None else None
        if pgroup is None and source is None and i < len(pgroups):
            pgroup = pgroups[i]
        means = group.get("means") or []
        if pgroup is not None:
            pairs.append((node, pgroup, group))
            if len(means) != len(pgroup.get("causes") or []):
                broken(node, f"{node} tiene {len(means)} medios y su causa directa "
                             f"{len(pgroup.get('causes') or [])} causas indirectas: cada causa indirecta da un medio.")
        for mean in means:
            if mean.get("from") is not None and str(mean.get("from")) not in cause_ids:
                broken(str(mean.get("id") or ""), f"«{mean.get('from')}» no es una causa indirecta del árbol de "
                                                  "problemas.")
    for branch in branches:
        if branch.get("from") is not None and str(branch.get("from")) not in branch_ids:
            broken(str(branch.get("id") or ""), f"«{branch.get('from')}» no es un efecto del árbol de problemas.")

    ptrunk = normalize_tree_text((problem_spec.get("trunk") or {}).get("text"))
    if ptrunk and trunk and shared_variable(ptrunk, trunk) < 0.5:
        findings.append(_finding("error", "arbol-variable-cambiada", "trunk",
                                 "El objetivo general cambia la variable del problema central: el espejo positivo "
                                 "conserva la variable y la población."))
    for node, pgroup, group in pairs:
        title, objective = _node_body(pgroup.get("title")), _node_body(group.get("objective"))
        if title and objective and shared_variable(title, objective) < 0.5:
            findings.append(_finding("warning", "arbol-variable-cambiada", node,
                                     "El objetivo específico no conserva la variable de su causa directa."))
    return findings


def _read_json_file(path: Path):
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _latex_plain(tex: str) -> str:
    text = re.sub(r"\\(textbf|textit|emph|texttt|mbox)\{([^{}]*)\}", r"\2", tex)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", "", text)
    text = text.replace("~", " ").replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()


def general_objective_text(tex: str) -> str:
    """§6 as plain text (same extraction as the dashboard trees)."""
    clean = "\n".join(strip_comment(l) for l in tex.splitlines())
    clean = re.sub(r"\\(section|label)\*?\{[^{}]*\}", "", clean)
    return _latex_plain(clean)


def specific_objective_items(tex: str) -> list[str]:
    """§7 items in order as plain text."""
    clean = "\n".join(strip_comment(l) for l in tex.splitlines())
    clean = re.split(r"\\end\{enumerate\}", clean)[0]
    return [t for t in (_latex_plain(i) for i in re.split(r"\\item\b", clean)[1:]) if t]


def _same_text(a, b) -> bool:
    def key(x) -> str:
        return normalize_tree_text(x).rstrip(" .;:")
    return key(a) == key(b)


TITLE_RE = re.compile(r"\\newcommand\{\\TituloProyecto\}\{(.*)\}\s*$")


def project_title(red: Path) -> str:
    """\\TituloProyecto from datos_proyecto.tex, or "" when absent."""
    datos = red / "datos_proyecto.tex"
    if not datos.is_file():
        return ""
    for line in datos.read_text(encoding="utf-8", errors="replace").splitlines():
        match = TITLE_RE.match(strip_comment(line).strip())
        if match:
            return match.group(1)
    return ""


def _title_key(words: list[str]) -> str:
    return " ".join(_fold(w.lower()) for w in words).rstrip(" .;:")


def sgr_title_findings(title, general_objective) -> list[dict]:
    """SGR: the title is the general objective with only its first word changed,
    the infinitive turned into its noun (Fortalecer → Fortalecimiento de…).
    A placeholder or a missing objective is not a finding."""
    title = normalize_tree_text(title)
    objective = normalize_tree_text(general_objective)
    if not title or not objective or title.startswith("[Por definir"):
        return []
    t_words, o_words = title.split(), objective.split()
    rest = t_words[1:]
    # The noun takes "de" before the objective's object: "del" stands for "de el".
    if rest and rest[0].lower() == "del":
        rest = ["el"] + rest[1:]
    elif rest and rest[0].lower() == "de":
        rest = rest[1:]
    verb = _fold(o_words[0].lower())
    stem = verb[:-2] if INFINITIVE_RE.match(verb) else verb
    noun = _fold(t_words[0].lower())
    if len(o_words) > 1 and noun.startswith(stem[:4]) and noun != verb and _title_key(rest) == _title_key(o_words[1:]):
        return []
    return [_finding("error", "sgr-titulo-no-derivado", "titulo",
                     "En el flujo SGR el título es el objetivo general cambiando solo la primera palabra por su "
                     "sustantivo (Fortalecer las capacidades… → Fortalecimiento de las capacidades…).")]


def check_trees(report: Report, run_root: Path, texts: dict[str, str], sections: dict[str, Path],
                flujo: str) -> None:
    problem_path = run_root / PROBLEM_SPEC
    objectives_path = run_root / OBJECTIVES_FILE
    problem = _read_json_file(problem_path)
    objectives = _read_json_file(objectives_path)
    if problem is not None:
        for f in problem_tree_findings(problem):
            report.add(f["severity"], f["code"], f["message"], problem_path, node=f["node"])
    if objectives is None:
        return
    if problem is not None:
        for f in objective_tree_findings(objectives, problem):
            report.add(f["severity"], f["code"], f["message"], objectives_path, node=f["node"])

    tree_general = normalize_tree_text((objectives.get("trunk") or {}).get("text"))
    if flujo == "sgr":
        datos = run_root / "redaccion" / "datos_proyecto.tex"
        for f in sgr_title_findings(project_title(run_root / "redaccion"), tree_general):
            report.add(f["severity"], f["code"], f["message"], datos)
        if "06_objetivo_general" in texts and not _same_text(general_objective_text(texts["06_objetivo_general"]),
                                                             tree_general):
            report.add("error", "sgr-objetivo-general-distinto",
                       "En el flujo SGR §6 es literalmente el objetivo general del árbol de objetivos.",
                       sections["06_objetivo_general"])
        if "07_objetivos_especificos" in texts:
            items = specific_objective_items(texts["07_objetivos_especificos"])
            tree_items = [g.get("objective") for g in objectives.get("groups") or []]
            if len(items) != len(tree_items) or not all(_same_text(a, b) for a, b in zip(items, tree_items)):
                report.add("error", "sgr-objetivos-especificos-distintos",
                           "En el flujo SGR §7 enumera, en orden, los objetivos específicos del árbol de objetivos.",
                           sections["07_objetivos_especificos"])
    elif "06_objetivo_general" in texts and tree_general:
        if shared_variable(tree_general, general_objective_text(texts["06_objetivo_general"])) < 0.34:
            report.add("warning", "objetivo-general-sin-variable-del-arbol",
                       "§6 no conserva la variable del objetivo general del árbol de objetivos.",
                       sections["06_objetivo_general"])


def panel_tree_hash(tree_key: str, data: dict) -> str:
    """Hash the dashboard panel approves (src/morfeo/core/trees.py `_hash`): the
    problem tree is normalised from its spec, the objective tree is hashed as is."""
    if tree_key == "problemas":
        def magnitude(node: dict, source: dict) -> dict:
            if isinstance(source.get("magnitude"), dict):
                node["magnitude"] = source["magnitude"]
            return node

        data = {
            "caption": data.get("caption") or "",
            "groups": [
                magnitude({
                    "id": g.get("id"),
                    "title": g.get("title") or g.get("id"),
                    "causes": [{"id": c.get("id"), "text": c.get("text")} for c in g.get("causes") or []],
                }, g)
                for g in data.get("groups") or []
            ],
            "trunk": data.get("trunk") or {"label": "PROBLEMA CENTRAL", "text": None},
            "branches": [magnitude({"id": b.get("id"), "text": b.get("text")}, b) for b in data.get("branches") or []],
            "crown": data.get("crown") or {"label": "EFECTO FINAL", "text": None},
        }
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _run_renderer(red: Path):
    """The run's own render_tikz.py (the one that compiled its figures), else the framework's."""
    for path in (red / "scripts" / "render_tikz.py",
                 Path(__file__).resolve().parent.parent / "plantilla" / "scripts" / "render_tikz.py"):
        if path.is_file():
            module_spec = importlib.util.spec_from_file_location("run_render_tikz", path)
            module = importlib.util.module_from_spec(module_spec)
            try:
                module_spec.loader.exec_module(module)
            except Exception:
                return None
            return module
    return None


def check_tree_figures(report: Report, run_root: Path, flujo: str) -> None:
    """A tree figure is the panel's tree: re-render its spec and compare."""
    red = run_root / "redaccion"
    renderer = None
    for name in TREE_FIGURES:
        spec_path = red / "specs" / f"{name}.spec.json"
        diag = red / "sections" / f"diag_{name}.tex"
        spec = _read_json_file(spec_path)
        if spec is None or not diag.is_file():
            continue
        renderer = renderer or _run_renderer(red)
        if renderer is None:
            return
        overrides_path = spec_path.with_name(f"{name}.overrides.json")
        overrides = renderer.load_overrides(overrides_path) if hasattr(renderer, "load_overrides") else {}
        try:
            expected, _ = renderer.render(spec, overrides)
        except (SystemExit, Exception) as exc:
            report.add("error", "figura-spec-invalida", f"specs/{name}.spec.json no se puede renderizar: {exc}", spec_path)
            continue
        if expected.rstrip() != diag.read_text(encoding="utf-8", errors="replace").rstrip():
            report.add("error", "figura-desincronizada",
                       f"diag_{name}.tex no corresponde a specs/{name}.spec.json, el árbol que muestra el panel. "
                       f"Vuelve a compilarla: python3 redaccion/scripts/figura.py {name} "
                       f"--spec redaccion/specs/{name}.spec.json --project redaccion", diag)

    if flujo != "sgr":
        return
    review = _read_json_file(run_root / REVIEW_FILE) or {}
    sources = {"problemas": run_root / PROBLEM_SPEC, "objetivos": run_root / OBJECTIVES_FILE}
    for name, key in TREE_FIGURES.items():
        data = _read_json_file(sources[key])
        if data is None or (key == "objetivos" and not (red / "sections" / f"diag_{name}.tex").is_file()
                            and not (red / "specs" / f"{name}.spec.json").is_file()):
            continue
        approved = (review.get(key) or {}).get("approved_hash")
        if approved != panel_tree_hash(key, data):
            state = "quedó desactualizada" if approved else "no existe"
            report.add("warning", "arbol-sin-aprobar-panel",
                       f"En el flujo SGR la figura del árbol de {key} sale del árbol aprobado en el panel del tablero, "
                       f"y esa aprobación {state}. Revísalo y apruébalo en la pestaña de árboles.", sources[key])


SECTION_RE = re.compile(r"\\section(\*?)\s*\{")


def _braced(text: str, start: int) -> str:
    """Content of the {...} group whose opening brace is at text[start - 1]."""
    depth, i = 1, start
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[start:i - 1]


def check_tdr_structure(report: Report, run_root: Path, final: bool) -> None:
    """main.tex in the TDR chapter order (scripts/ensamblar_main.py), verbatim titles."""
    structure_path = run_root / "artefactos" / "estructura_tdr.json"
    data = _read_json_file(structure_path)
    if data is None:
        return
    assembler_path = Path(__file__).resolve().parent / "ensamblar_main.py"
    if not assembler_path.is_file():
        return
    module_spec = importlib.util.spec_from_file_location("ensamblar_main", assembler_path)
    assembler = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(assembler)
    try:
        chapters = assembler.validate(data)
    except assembler.InputError as exc:
        report.add("error", "tdr-estructura-invalida", str(exc), structure_path)
        return

    main_tex = run_root / "redaccion" / "main.tex"
    stamp = f"{assembler.HASH_PREFIX}{assembler.structure_hash(data)}"
    if main_tex.is_file() and stamp not in main_tex.read_text(encoding="utf-8", errors="replace"):
        report.add("error", "tdr-main-desactualizado",
                   "main.tex no sigue artefactos/estructura_tdr.json (el orden de capítulos del TDR). "
                   f"Ármalo con: python3 scripts/ensamblar_main.py {run_root}", main_tex)

    sec_dir = run_root / "redaccion" / "sections"
    for chapter in chapters:
        texts = []
        for name in chapter["archivos"]:
            path = sec_dir / f"{name}.tex"
            if not name.startswith("diag_") and path.is_file():
                raw = path.read_text(encoding="utf-8", errors="replace")
                texts.append((path, "\n".join(strip_comment(line) for line in raw.splitlines())))
        if not texts:
            continue
        heads = [(path, m) for path, text in texts for m in SECTION_RE.finditer(text)]
        numbered = [h for h in heads if not h[1].group(1)]
        if len(numbered) != 1:
            report.add("warning", "tdr-capitulo-secciones",
                       f"El capítulo {chapter['numero']} abre {len(numbered)} \\section numerados; debe abrir uno "
                       "solo para que LaTeX imprima el número del TDR (los sub-bloques van con \\subsection).",
                       texts[0][0])
        title = chapter.get("titulo")
        if not title or not heads:
            continue
        path, match = heads[0]
        text = dict(texts)[path]
        found = " ".join(_braced(text, match.end()).split())
        if found != " ".join(title.split()):
            report.add("error" if final else "warning", "tdr-titulo-capitulo",
                       f"El capítulo {chapter['numero']} debe titularse textualmente «{title}» "
                       f"(el TDR conserva los títulos); dice «{found}».", path)


SGR_STAGES = ("preinversion", "inversion", "operacion")


def check_sgr_methodology_schedule(report: Report, run_root: Path, texts: dict[str, str],
                                   sections: dict[str, Path], flujo: str) -> None:
    """Guía SGR §10 (value chain by stage, every OE covered) and §14 (stages, critical path)."""
    if flujo != "sgr":
        return
    spec_path = run_root / "redaccion" / "specs" / "metodologico.spec.json"
    spec = _read_json_file(spec_path)
    if spec is not None:
        phases = spec.get("phases") or []
        staged = [p for p in phases if _fold(str(p.get("etapa") or "")).strip().lower() in SGR_STAGES]
        if len(staged) != len(phases):
            missing = [str(p.get("id")) for p in phases if p not in staged]
            report.add("warning", "sgr-metodologia-sin-etapa",
                       "En el flujo SGR cada fase de la metodología nombra su etapa MGA (\"etapa\": preinversion, "
                       f"inversion u operacion). Fases sin etapa válida: {', '.join(missing)}.", spec_path)
        objectives = _read_json_file(run_root / OBJECTIVES_FILE) or {}
        expected = [str(g.get("id")) for g in objectives.get("groups") or [] if g.get("id")]
        covered = {str(oe) for p in phases for oe in (p.get("oe") or [])}
        uncovered = [oe for oe in expected if oe not in covered]
        if uncovered:
            report.add("warning", "sgr-metodologia-sin-oe",
                       "En el flujo SGR cada producto de la cadena de valor responde a un objetivo específico: "
                       f"ninguna fase declara \"oe\" para {', '.join(uncovered)}.", spec_path)

    name = "14_cronograma_actividades"
    if name in texts:
        plain = _fold("\n".join(strip_comment(line) for line in texts[name].splitlines())).lower()
        if not any(re.search(rf"\b{stage}\b", plain) for stage in SGR_STAGES):
            report.add("warning", "sgr-cronograma-sin-etapas",
                       "En el flujo SGR el cronograma agrupa las actividades por etapa (preinversión, inversión, "
                       "operación).", sections[name])
        if not re.search(r"ruta\s+critica", plain):
            report.add("warning", "sgr-cronograma-sin-ruta-critica",
                       "En el flujo SGR el cronograma marca las actividades de la ruta crítica.", sections[name])


def check_sgr_sections(report: Report, sec_dir: Path, flujo: str, final: bool) -> None:
    if flujo != "sgr" or not final:
        return
    for name in SGR_SECTIONS:
        if not (sec_dir / f"{name}.tex").is_file():
            report.add("error", "sgr-anexo-faltante", f"Falta sections/{name}.tex (anexo MGA del flujo SGR).")


def run_checks(run_root: Path, final: bool, flujo: str | None = None) -> Report:
    report = Report(run_root)
    report.flujo = flujo if flujo in FLUJOS else detect_flujo(run_root)
    red = run_root / "redaccion"
    sec_dir = red / "sections"
    if not sec_dir.is_dir():
        report.add("error", "corrida-invalida", f"No existe {sec_dir}.")
        return report

    for stray in sorted(sec_dir.glob("01_titulo*.tex")):
        report.add("error", "seccion-1-en-cuerpo",
                   "No debe existir un archivo de §1: el título va solo en la portada de main.tex.", stray)

    sections = {name: sec_dir / f"{name}.tex" for name in CANONICAL_SECTIONS if (sec_dir / f"{name}.tex").is_file()}
    texts = {name: path.read_text(encoding="utf-8", errors="replace") for name, path in sections.items()}
    if final:
        for name in CANONICAL_SECTIONS:
            if name not in sections:
                report.add("error", "seccion-faltante", f"Falta sections/{name}.tex.")

    prose_files = list(sections.items()) + [(p.stem, p) for p in sorted(sec_dir.glob("diag_*_caption.tex"))]
    for name, path in prose_files:
        check_prose(report, path, texts.get(name) or path.read_text(encoding="utf-8", errors="replace"))

    keys_by_section = check_citations(report, sections, texts)
    check_floors(report, sections, keys_by_section, final)
    check_trl(report, sections, texts)
    check_objectives(report, sections, texts)
    check_main(report, red, final)
    check_cover(report, red, final)
    check_bibliography(report, sections, texts)
    check_pdf(report, red)
    check_trees(report, run_root, texts, sections, report.flujo)
    check_tree_figures(report, run_root, report.flujo)
    check_tdr_structure(report, run_root, final)
    check_sgr_methodology_schedule(report, run_root, texts, sections, report.flujo)
    check_sgr_sections(report, sec_dir, report.flujo, final)
    return report


def resolve_run_root(arg: str | None) -> Path:
    if arg:
        return Path(arg).resolve()
    pointer = Path("proposals/.current-run")
    if not pointer.is_file():
        raise SystemExit("error: no RUN_ROOT given and proposals/.current-run does not exist")
    return Path("proposals", pointer.read_text(encoding="utf-8").strip()).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_root", nargs="?", help="run folder (default: the active run)")
    parser.add_argument("--final", action="store_true", help="also require every section, the cover and total floor")
    parser.add_argument("--json", action="store_true", help="print {flujo, findings} as JSON")
    parser.add_argument("--flujo", choices=FLUJOS, help="override the flow read from the project config")
    args = parser.parse_args()

    report = run_checks(resolve_run_root(args.run_root), args.final, args.flujo)
    if args.json:
        print(json.dumps({"flujo": report.flujo, "findings": report.findings}, ensure_ascii=False, indent=2))
    else:
        for f in report.findings:
            where = f["file"] + (f":{f['line']}" if f["line"] else "") + (f" [{f['node']}]" if f.get("node") else "")
            print(f"[{f['severity'].upper()}] {f['code']} {where} {f['message']}".rstrip())
        warnings = len(report.findings) - report.errors()
        print(f"check_run: {report.errors()} errores, {warnings} avisos")
    return 1 if report.errors() else 0


if __name__ == "__main__":
    sys.exit(main())
