#!/usr/bin/env python3
"""Deterministic checks for a proposal run, run by the dispatcher before each gate.

The revisor agent judges coherence and quality; this script covers what a
regular expression can prove, so the agent does not spend tokens re-deriving
it and a violation cannot slip through a gate (two em dashes in §10 of the
reference run did). Standard library only: every runtime (Claude Code, Pi,
OpenCode, Antigravity) runs it the same way.

Usage:
  python3 scripts/check_run.py [RUN_ROOT] [--final] [--json] [--flujo {base,sgr}] [--lang {es,en}]

RUN_ROOT defaults to the run named in proposals/.current-run. Without --final,
only files that already exist are checked (a mid-pipeline gate); --final also
requires every canonical section (in SGR with TDR chapters, the chapter files), a
filled cover and the total reference floor. Exit code 1 when any error is found. --json prints an object
{"flujo": ..., "findings": [...]}.

Writing language (lang): the run's, as scripts/language.py resolves it (the
`| idioma | en |` row of `_run.md`, else the project's `lang`, always `es` in the
SGR flow); --lang overrides it, except that the SGR flow refuses --lang en
(exit 2). A Spanish run gets exactly the output it got
before the setting existed, and --json prints "lang" only for an English run.
In English the language rules read English: the TRL message, the cover
placeholder ([To be defined, besides [Por definir), the table name in the PDF
(cuadro-en-pdf flags «Tabla N», «Cuadro N» or «Figura N») and the tree rules
(absence wording, objectives that open with a verb or «To», means, ends,
negative qualifiers and the shared variable), with English messages for those
rules; every other message stays in Spanish.

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
    arbol-variable-cambiada (error on the trunk, warning on a group),
    arbol-objetivo-titulo (warning: groups[].title is OE<n>, not the cause text)
  base flow: objetivo-general-sin-variable-del-arbol (warning, §6 vs tree)
  SGR flow: sgr-objetivo-general-distinto, sgr-objetivos-especificos-distintos
    (§6/§7 must be the objective tree texts), sgr-titulo-no-derivado (the
    title is the general objective with its verb as a noun), and with --final
    sgr-anexo-faltante for each missing MGA annex in SGR_SECTIONS;
    sgr-causa-sin-magnitud / sgr-efecto-sin-magnitud (warning, guía SGR §3),
    sgr-magnitud-repetida (warning: a direct cause reuses the trunk or an
    effect indicator, guía SGR §3),
    arbol-sin-aprobar-panel (warning), sgr-metodologia-sin-etapa,
    sgr-metodologia-sin-oe, sgr-cronograma-sin-etapas,
    sgr-cronograma-sin-ruta-critica (warnings, guía SGR §10 and §14),
    sgr-problema-estructura (warning: §3 misses one of the subsections
    Problema central, Descripción de la situación existente, Magnitud del
    problema, guía SGR §3).
  SGR call rules (artefactos/convocatoria.json, all keys optional; the base
  flow never reads it): convocatoria-invalida (error, the file is then ignored),
    convocatoria-trl-invertido (error: trl.salida below trl.entrada),
    piso-referencias (error when pisos_referencias declares the floor, warning
    with the base numbers otherwise), objetivos-no-son-3 (error against
    objetivos_especificos; undeclared, warning below 3), trl-ausente (names
    trl.salida), rubrica-capitulo-inexistente (error),
    rubrica-puntos (warning: the rubric does not add up to 100).
  SGR section rules: sgr-marca-trabajo (warning, error with --final: a
    [PENDIENTE, [VERIFICAR, [CONFIRMAR or [PROPUESTA mark in a section file);
    tdr*.tex go through the prose and citation checks; with
    estructura_tdr.json, --final requires its chapter files (diag_* are
    optional; sections 26 to 39 join the first chapter whose title matches,
    as scripts/ensamblar_main.py placed_chapters places them in main.tex)
    instead of the canonical sections and the MGA annexes, and
    tdr-capitulo-vacio is an error for a chapter without content; without it,
    tdr-estructura-faltante is an error when guia_ajustada_TDR.md has a chapter
    table.
  value chain and style (SGR flow only; scripts/cadena_valor_sgr.py and
    scripts/estilo_sgr.py, imported from this folder when they exist):
    every `cadena-*` finding of artefactos/sgr/cadena_valor.json;
    cadena-valor-faltante (warning: the run is past the objectives gate G4
    and has no cadena_valor.json); cadena-anexo-manual (error:
    23_cadena_valor.tex lacks the GENERADO header) and
    cadena-anexo-desactualizado (error: it is older than the json); and
    every `sgr-estilo-*` finding as a warning.
  alliance and territory (SGR flow only; scripts/alianza_territorio_sgr.py):
    every `alianza-*` / `territorio-*` finding of artefactos/sgr/alianza.json
    and territorio.json when they exist; alianza-datos-faltantes /
    territorio-datos-faltantes (warning: GTerritorio is approved in
    estado_propuesta.md and the file is missing); alianza-anexo-manual /
    territorio-anexo-manual (error: 26_identificacion, 28_matriz_responsabilidades
    or 27_demandas_territoriales lacks the GENERADO header) and
    alianza-anexo-desactualizado / territorio-anexo-desactualizado (error: the
    section is older than the json it is rendered from).
  budget and schedule (SGR flow only; scripts/presupuesto_sgr.py and
    scripts/cronograma_sgr.py, imported from this folder when they exist):
    every `presupuesto-*` finding of artefactos/sgr/presupuesto.json when it
    exists; every `cronograma-*` finding of cronograma_sgr.findings;
    presupuesto-datos-faltantes (warning: G6.4 is approved in
    estado_propuesta.md and the file is missing); presupuesto-anexo-manual
    (error: 30_fuentes_financiacion, or 13_presupuesto when presupuesto.json
    exists, lacks the GENERADO header) and presupuesto-anexo-desactualizado
    (error: the section is older than the json it is rendered from).
  TRL and transversal components (SGR flow only; scripts/componentes_sgr.py):
    every `componentes-*` finding of artefactos/sgr/componentes.json when it
    exists; componentes-datos-faltantes (warning: GComponentes is approved in
    estado_propuesta.md and the file is missing); componentes-anexo-manual
    (error: 31_trl to 35_medidas_diferenciales, or 18_apropiacion_social when
    componentes.json exists, lacks the GENERADO header) and
    componentes-anexo-desactualizado (error: the section is older than the
    json it is rendered from). A hand-written §18 of an older SGR run without
    componentes.json is left alone.
  products, talent and indicators (SGR flow only; scripts/productos_sgr.py):
    every `productos-*` finding of artefactos/sgr/productos.json when it
    exists; productos-datos-faltantes (warning: GProductos is approved in
    estado_propuesta.md and the file is missing); productos-anexo-manual
    (error: 36_talento_humano or 37_indicadores, or 15_productos_esperados
    when productos.json exists, lacks the GENERADO header) and
    productos-anexo-desactualizado (error: the section is older than the json
    it is rendered from). A hand-written §15 of an older SGR run without
    productos.json is left alone.
  requirements, licences and annexes (SGR flow only; scripts/requisitos_sgr.py):
    every `requisitos-*` finding of artefactos/sgr/requisitos.json when it
    exists; requisitos-datos-faltantes (warning: GRequisitos is approved in
    estado_propuesta.md and the file is missing); requisitos-anexo-manual
    (error: 38_licencias_permisos or 39_anexos lacks the GENERADO header) and
    requisitos-anexo-desactualizado (error: the section is older than the json
    it is rendered from). Applicable requirements that are not ready are
    errors only in `requisitos_sgr.py check --final` (Fase 7).
  tree figures (both flows): figura-desincronizada (error: diag_<tree>.tex is
    not the render of its spec), figura-spec-invalida, figura-sin-verificar.
  TDR chapters (artefactos/estructura_tdr.json, any flow):
    tdr-main-desactualizado, tdr-estructura-invalida (errors),
    tdr-titulo-capitulo (warning, error with --final), tdr-capitulo-secciones.
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
    "26_identificacion", "27_demandas_territoriales", "28_matriz_responsabilidades", "29_idoneidad_trayectoria",
    "30_fuentes_financiacion",
    "31_trl", "32_sostenibilidad", "33_uso_posterior", "34_transferencia", "35_medidas_diferenciales",
    "36_talento_humano", "37_indicadores",
    "38_licencias_permisos", "39_anexos",
)
FLUJOS = ("base", "sgr")
LANGS = ("es", "en")
PROBLEM_SPEC = Path("redaccion") / "specs" / "arbol_problemas.spec.json"
OBJECTIVES_FILE = Path("artefactos") / "arboles" / "arbol_objetivos.json"
REVIEW_FILE = Path("artefactos") / "arboles" / "revision.json"
CONVOCATORIA_FILE = Path("artefactos") / "convocatoria.json"
STRUCTURE_FILE = Path("artefactos") / "estructura_tdr.json"
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
        self.lang = "es"

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


def _floor(key: str, base: int, flujo: str, convocatoria: dict) -> tuple[int, str, str]:
    """Floor to apply, its severity and a closing note. In SGR the call decides:
    only a declared floor blocks; the base numbers remain as a warning."""
    if flujo != "sgr":
        return base, "error", ""
    declared = (convocatoria.get("pisos_referencias") or {}).get(key)
    if declared is None:
        return base, "warning", " Piso de la guía base: la convocatoria no lo declara en pisos_referencias."
    return declared, "error", ""


def check_floors(report: Report, sections: dict[str, Path], keys_by_section: dict[str, set[str]], final: bool,
                 flujo: str = "base", convocatoria: dict | None = None) -> None:
    convocatoria = convocatoria or {}
    for name, key, base in (("02_justificacion", "justificacion", FLOOR_JUSTIFICACION),
                            ("04_estado_arte", "estado_arte", FLOOR_ESTADO_ARTE)):
        floor, severity, note = _floor(key, base, flujo, convocatoria)
        if name in keys_by_section and len(keys_by_section[name]) < floor:
            report.add(severity, "piso-referencias",
                       f"{name} cita {len(keys_by_section[name])} referencias distintas (mínimo {floor}).{note}",
                       sections[name])
    if final:
        total = set().union(*keys_by_section.values()) if keys_by_section else set()
        floor, severity, note = _floor("total", FLOOR_TOTAL, flujo, convocatoria)
        if len(total) < floor:
            report.add(severity, "piso-referencias",
                       f"El documento cita {len(total)} referencias distintas (mínimo {floor}).{note}")


def _trl_requirement(flujo: str, convocatoria: dict, lang: str = "es") -> tuple[re.Pattern, str]:
    """What §2 and §11 must show and the message when they do not. In SGR the
    level is the call's trl.salida, also when written as the end of a range."""
    salida = (convocatoria.get("trl") or {}).get("salida")
    if flujo != "sgr":
        message = ("TRL 6 or 7 must be explicit in this section." if lang == "en"
                   else "TRL 6 o 7 debe ser explícito en esta sección.")
        return re.compile(r"\bTRL\b"), message
    if salida is None:
        return re.compile(r"\bTRL\b"), ("El nivel TRL de salida debe ser explícito en esta sección; la convocatoria "
                                         "lo fija en trl.salida de artefactos/convocatoria.json.")
    return (re.compile(rf"\bTRL[\s~]*(?:\d+[\s~]*(?:a|al|y|o|-|–)[\s~]*)?{salida}\b"),
            f"TRL {salida}, el nivel de salida de la convocatoria, debe ser explícito en esta sección.")


def check_trl(report: Report, sections: dict[str, Path], texts: dict[str, str], flujo: str = "base",
              convocatoria: dict | None = None) -> None:
    convocatoria = convocatoria or {}
    declared = convocatoria.get("trl") or {}
    if flujo == "sgr" and None not in (declared.get("entrada"), declared.get("salida")) \
            and declared["salida"] < declared["entrada"]:
        report.add("error", "convocatoria-trl-invertido",
                   f"trl.salida ({declared['salida']}) es menor que trl.entrada ({declared['entrada']}).",
                   report.run_root / CONVOCATORIA_FILE)
    trl = re.compile(r"\bTRL\b")
    for name in ("06_objetivo_general", "07_objetivos_especificos"):
        if name in texts:
            for number, line in prose_lines(texts[name]):
                if trl.search(line):
                    report.add("error", "trl-en-objetivos",
                               "TRL nombrado en un objetivo: expresar el nivel de forma funcional.",
                               sections[name], number)
    required, message = _trl_requirement(flujo, convocatoria, report.lang)
    for name in ("02_justificacion", "11_resultados_esperados"):
        if name in texts and not any(required.search(l) for _, l in prose_lines(texts[name])):
            report.add("error", "trl-ausente", message, sections[name])
    if "10_metodologia" in texts and not trl.search(texts["10_metodologia"]):
        report.add("warning", "trl-ausente", "El revisor espera la trayectoria TRL en la metodología.",
                   sections["10_metodologia"])


def check_objectives(report: Report, sections: dict[str, Path], texts: dict[str, str], flujo: str = "base",
                     convocatoria: dict | None = None) -> None:
    name = "07_objetivos_especificos"
    if name not in texts:
        return
    match = re.search(r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}", texts[name], re.S)
    items = len(re.findall(r"^\s*\\item\b", match.group(1), re.M)) if match else 0
    expected = (convocatoria or {}).get("objetivos_especificos") if flujo == "sgr" else 3
    if expected is None:
        if items < 3:
            report.add("warning", "objetivos-no-son-3",
                       f"§7 enumera {items} objetivos específicos; la plantilla usa 3. Si la convocatoria fija otro "
                       "número, decláralo en objetivos_especificos de artefactos/convocatoria.json.", sections[name])
    elif items != expected:
        report.add("error", "objetivos-no-son-3",
                   f"§7 enumera {items} objetivos específicos; el mapeo 1:1 exige {expected}.", sections[name])


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


# The Spanish template's placeholder and the English one (scripts/language.py).
COVER_PLACEHOLDERS = ("[Por definir", "[To be defined")


def check_cover(report: Report, red: Path, final: bool) -> None:
    datos = red / "datos_proyecto.tex"
    if not datos.is_file():
        return
    # Only the \newcommand values count: the seeded file explains the
    # placeholder in a comment, which must not keep the cover "incomplete".
    values = "\n".join(strip_comment(l) for l in datos.read_text(encoding="utf-8", errors="replace").splitlines())
    if any(placeholder in values for placeholder in COVER_PLACEHOLDERS):
        message = ("datos_proyecto.tex still has [To be defined: ...] fields." if report.lang == "en"
                   else "datos_proyecto.tex conserva campos [Por definir: ...].")
        report.add("error" if final else "warning", "portada-sin-completar", message, datos)


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


# Float names that betray the wrong babel setup: Spanish babel calls tables
# «Cuadro» unless main.tex renames them; an English run must say neither
# «Tabla» nor «Cuadro» nor «Figura».
PDF_FLOAT_NAME_RE = {"es": re.compile(r"\bCuadro \d+"), "en": re.compile(r"\b(?:Cuadro|Tabla|Figura) \d+")}


def pdf_table_name_problem(text: str, lang: str = "es") -> str | None:
    """The first float name the PDF text should not contain, or None."""
    match = PDF_FLOAT_NAME_RE.get(lang, PDF_FLOAT_NAME_RE["es"]).search(text)
    return match.group(0) if match else None


def check_pdf(report: Report, red: Path) -> None:
    pdf = red / "main.pdf"
    if not pdf.is_file() or shutil.which("pdftotext") is None:
        return
    result = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True)
    found = pdf_table_name_problem(result.stdout, report.lang)
    if found:
        message = (f"The PDF says «{found}»: an English run names its floats «Table» and «Figure» "
                   "(babel english in main.tex)." if report.lang == "en"
                   else f"El PDF dice «{found}»: las tablas se llaman «Tabla».")
        report.add("error", "cuadro-en-pdf", message, pdf)


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


def detect_lang(run_root: Path) -> str:
    """Writing language of the run, as scripts/language.py resolves it; "es"
    when that helper is missing."""
    module = _sibling_module("language")
    if module is None:
        return "es"
    try:
        value = module.run_lang(Path(run_root))
    except OSError:
        return "es"
    return value if value in LANGS else "es"


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


# English counterparts of the Spanish tree vocabulary above (S3, runs in English).
MGA_PROBLEM_RULE_EN = ("«A problem is not the absence of its solution but an existing negative state» "
                       "(MGA Instructivo 2023, p. 122)")
ABSENCE_RE_EN = re.compile(
    r"\b(?:lack|absence|non-?existence)\s+of\b|\bthere\s+(?:is|are)\s+no\b"
    r"|\b(?:is|are)\s+(?:required|needed)\b|\bneed\s+(?:for|to)\b", re.I)
# Verbs an objective opens with (bare infinitive); "To <verb>" always counts. A
# listed word followed by a preposition is a noun ("Increase in cases").
EN_OBJECTIVE_VERBS = frozenset("""
    accelerate achieve adapt adopt analyse analyze apply articulate assess automate broaden build certify
    characterise characterize classify collect connect consolidate conserve construct contribute create decrease
    deepen define deploy design detect determine develop diagnose digitize disseminate diversify empower enable
    encourage enhance ensure establish estimate evaluate expand extend facilitate formulate foster generate
    guarantee identify implement improve incorporate increase install integrate manage maximise maximize measure
    minimise minimize mitigate modernize offer optimise optimize predict prevent prioritize produce promote
    propose protect provide quantify raise recover reduce restore secure select standardize strengthen
    systematize train transfer update validate widen
""".split())
EN_NOUN_FOLLOWERS = frozenset("in of on for and with from at by rate rates level levels".split())
NEGATIVE_QUALIFIERS_EN = frozenset("""
    low high limited poor insufficient deficient inefficient inadequate inappropriate scarce weak slow unstable
    excessive fragmented unequal inequitable irregular growing increasing rising reduced few little precarious
    elevated ineffective persistent declining decreasing deteriorated deteriorating lower higher
""".split())
MEANS_RE_EN = re.compile(r"\b(?:by\s+means\s+of|through|via|by\s+(?:using|implementing|developing|applying|deploying)"
                         r"|using)\b", re.I)
ENDS_RE_EN = re.compile(r"\bin\s+order\s+to\b|\bso\s+as\s+to\b|\bso\s+that\b"
                        r"|\bwith\s+the\s+(?:aim|purpose|goal|objective)\s+of\b|\bfor\s+the\s+purpose\s+of\b"
                        r"|\bto\s+(?:improve|enhance|raise|contribute|benefit|guarantee|ensure|promote|increase|reduce|"
                        r"strengthen)\b", re.I)
STOPWORDS_EN = frozenset("""
    about above after against among around before below between beyond during except inside outside since
    through throughout toward towards under within without which where while whose these those their there
    other others another every level levels index degree general specific means being having rates higher
    lower greater fewer limited insufficient deficient scarce reduced increased improved adequate better worse
""".split())


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


def _words_en(text) -> list[str]:
    return [w.lower() for w in re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", _node_body(text))]


def starts_with_infinitive(text, lang: str = "es") -> bool:
    """Spanish: an infinitive first word. English: «To <word>», or a listed
    objective verb that is not followed by a preposition."""
    if lang == "en":
        words = _words_en(text)
        if len(words) >= 2 and words[0] == "to":
            return True
        return bool(words) and words[0] in EN_OBJECTIVE_VERBS and (len(words) == 1
                                                                   or words[1] not in EN_NOUN_FOLLOWERS)
    word = _first_word(_node_body(text))
    return bool(INFINITIVE_RE.match(word)) and word not in NOT_INFINITIVES


def _fold(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn")


def _content_words(text, lang: str = "es") -> set[str]:
    if lang == "en":
        words = _words_en(text)
        words = words[1:] if words[:1] == ["to"] else words
        return {w for w in words[1:] if len(w) >= 5 and w not in STOPWORDS_EN}
    words = [_fold(w.lower()) for w in re.findall(r"[^\W\d_]+", _node_body(text))]
    return {w for w in words[1:] if len(w) >= 5 and w not in STOPWORDS}


def shared_variable(ref: str, other: str, lang: str = "es") -> float:
    """Share of the content words of `ref` (the problem text) that `other` keeps.
    The first word (the qualifier or the verb, after an English «To») does not
    count. 1.0 when `ref` has no content words, since there is nothing to lose."""
    ref_words = _content_words(ref, lang)
    if not ref_words:
        return 1.0
    return len(ref_words & _content_words(other, lang)) / len(ref_words)


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


def opens_with_negative_qualifier(text, lang: str = "es") -> bool:
    if lang == "en":
        words = _words_en(text)
        return bool(words) and words[0] in NEGATIVE_QUALIFIERS_EN
    return _fold(_first_word(_node_body(text))) in NEGATIVE_QUALIFIERS


# English wording of the tree rules whose text quotes the language (S3).
TREE_MESSAGES_EN = {
    "arbol-ausencia-de-solucion": f"{MGA_PROBLEM_RULE_EN}: describe the negative situation that exists today.",
    "arbol-solucion-en-problema": "The problem tree describes the negative situation; the solution goes in the "
                                  "objective tree.",
    "arbol-problema-sin-calificativo-negativo": "The central problem opens with a negative qualifier that does not "
                                                "denote a lack (low, limited, insufficient, poor, high…).",
    "arbol-objetivos-no-infinitivo": "The objective tree is written in positive terms and each node opens with a "
                                     "verb («To strengthen…» or «Strengthen…»).",
    "objetivo-general-con-medio": "The general objective does not include the means («by means of…, through…, "
                                  "using…»): the means go in the roots of the tree.",
    "objetivo-general-con-fin": "The general objective does not include the ends («…in order to improve quality of "
                                "life»): the ends go in the branches of the tree.",
    "objetivo-general-con-meta": "The general objective does not include targets: quantification goes in the "
                                 "indicators.",
    "arbol-variable-cambiada": "The general objective changes the variable of the central problem: the positive "
                               "mirror keeps the variable and the population.",
    "arbol-variable-cambiada-grupo": "The specific objective does not keep the variable of its direct cause.",
}


def _tree_message(lang: str, code: str, spanish: str) -> str:
    return TREE_MESSAGES_EN.get(code, spanish) if lang == "en" else spanish


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


def problem_tree_findings(spec: dict, lang: str = "es") -> list[dict]:
    """SGR guide rules for the problem tree; empty texts are not findings."""
    if not isinstance(spec, dict):
        return []
    findings = []
    absence = ABSENCE_RE_EN if lang == "en" else ABSENCE_RE
    for node, raw in _problem_nodes(spec):
        text = _node_body(raw)
        if not text:
            continue
        if absence.search(text):
            findings.append(_finding("error", "arbol-ausencia-de-solucion", node, _tree_message(
                lang, "arbol-ausencia-de-solucion",
                f"{MGA_PROBLEM_RULE}: describe la situación negativa que existe hoy.")))
        if starts_with_infinitive(text, lang):
            findings.append(_finding("error", "arbol-solucion-en-problema", node, _tree_message(
                lang, "arbol-solucion-en-problema",
                "El árbol de problemas describe la situación negativa; la solución va en el árbol de objetivos.")))
    trunk_text = _node_body((spec.get("trunk") or {}).get("text"))
    if trunk_text and not opens_with_negative_qualifier(trunk_text, lang):
        findings.append(_finding("error", "arbol-problema-sin-calificativo-negativo", "trunk", _tree_message(
            lang, "arbol-problema-sin-calificativo-negativo",
            "El problema central empieza con un calificativo negativo que no indique carencia "
            "(poco, escaso, limitado, insuficiente, deficiente, bajo, alto…).")))
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


# The objective tree's group title is its label (src/morfeo/core/trees.py,
# _derive_objectives); the objective itself lives in `objective`.
OE_LABEL_RE = re.compile(r"^OE\s*\d+$", re.IGNORECASE)


def objective_tree_findings(objectives: dict, problem_spec: dict, lang: str = "es") -> list[dict]:
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
        if _node_body(raw) and not starts_with_infinitive(raw, lang):
            findings.append(_finding("error", "arbol-objetivos-no-infinitivo", node, _tree_message(
                lang, "arbol-objetivos-no-infinitivo",
                "El árbol de objetivos se escribe en positivo y empieza con un verbo en infinitivo.")))

    if trunk:
        means, ends = (MEANS_RE_EN, ENDS_RE_EN) if lang == "en" else (MEANS_RE, ENDS_RE)
        # In English the objective's own «To <verb>» is not an end: search after it.
        tail = re.sub(r"^\s*(?:to\s+)?[^\W\d_]+\s*", "", trunk, flags=re.I) if lang == "en" else trunk
        if means.search(trunk):
            findings.append(_finding("error", "objetivo-general-con-medio", "trunk", _tree_message(
                lang, "objetivo-general-con-medio",
                "El objetivo general no incluye el medio («mediante…, por intermedio de…, a través de…»): los "
                "medios van en las raíces del árbol.")))
        if ends.search(tail):
            findings.append(_finding("error", "objetivo-general-con-fin", "trunk", _tree_message(
                lang, "objetivo-general-con-fin",
                "El objetivo general no incluye los fines («…para mejorar la calidad de vida»): los fines van en "
                "las ramas del árbol.")))
        if TARGET_RE.search(trunk):
            findings.append(_finding("error", "objetivo-general-con-meta", "trunk", _tree_message(
                lang, "objetivo-general-con-meta",
                "El objetivo general no incluye metas: la cuantificación va en los indicadores.")))

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

    for i, group in enumerate(groups):
        title = str(group.get("title") or "").strip()
        if title and title != str(group.get("id") or "") and not OE_LABEL_RE.match(title):
            label = f"OE{i + 1}"
            findings.append(_finding("warning", "arbol-objetivo-titulo", str(group.get("id") or label),
                                     f"groups[].title es el rótulo {label}, nunca el texto de la causa: el panel y "
                                     "§7 muestran el objetivo limpio, sin preámbulo."))

    ptrunk = normalize_tree_text((problem_spec.get("trunk") or {}).get("text"))
    if ptrunk and trunk and shared_variable(ptrunk, trunk, lang) < 0.5:
        findings.append(_finding("error", "arbol-variable-cambiada", "trunk", _tree_message(
            lang, "arbol-variable-cambiada",
            "El objetivo general cambia la variable del problema central: el espejo positivo conserva la variable "
            "y la población.")))
    for node, pgroup, group in pairs:
        title, objective = _node_body(pgroup.get("title")), _node_body(group.get("objective"))
        if title and objective and shared_variable(title, objective, lang) < 0.5:
            findings.append(_finding("warning", "arbol-variable-cambiada", node, _tree_message(
                lang, "arbol-variable-cambiada-grupo",
                "El objetivo específico no conserva la variable de su causa directa.")))
    return findings


def _read_json_file(path: Path):
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _convocatoria_problems(data) -> list[str]:
    """Keys of artefactos/convocatoria.json with the wrong type; all are optional."""
    if not isinstance(data, dict):
        return ["el archivo debe ser un objeto JSON"]
    problems = []
    floors = data.get("pisos_referencias", {})
    if not isinstance(floors, dict) or not all(_is_int(floors[k]) for k in floors
                                               if k in ("justificacion", "estado_arte", "total")):
        problems.append("pisos_referencias debe ser un objeto con enteros")
    if "objetivos_especificos" in data and not _is_int(data["objetivos_especificos"]):
        problems.append("objetivos_especificos debe ser un entero")
    trl = data.get("trl", {})
    if not isinstance(trl, dict) or not all(_is_int(trl[k]) for k in ("entrada", "salida") if k in trl):
        problems.append("trl debe ser un objeto con entrada y salida enteras")
    rubrica = data.get("rubrica", [])
    if not isinstance(rubrica, list) or not all(
            isinstance(item, dict)
            and isinstance(item.get("capitulos", []), list)
            and isinstance(item.get("puntos", 0), (int, float)) and not isinstance(item.get("puntos"), bool)
            for item in rubrica):
        problems.append("rubrica debe ser una lista de objetos con puntos numéricos y capitulos en lista")
    return problems


def load_convocatoria(run_root: Path, report: Report | None = None) -> dict:
    """Rules of the call from artefactos/convocatoria.json: {} when absent or
    invalid, so the checks fall back to their undeclared behaviour. With `report`,
    an invalid file adds one convocatoria-invalida error."""
    path = Path(run_root) / CONVOCATORIA_FILE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except ValueError as exc:
        problems = [f"no es JSON válido: {exc}"]
    else:
        problems = _convocatoria_problems(data)
    if not problems:
        return data
    if report is not None:
        report.add("error", "convocatoria-invalida", f"artefactos/convocatoria.json: {'; '.join(problems)}.", path)
    return {}


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


def _has_magnitude(node: dict) -> bool:
    """Guía SGR §3: indicator, value and source, the three parts of a magnitude."""
    magnitude = node.get("magnitude")
    return isinstance(magnitude, dict) and all(str(magnitude.get(key) or "").strip()
                                               for key in ("indicador", "valor", "fuente"))


def sgr_magnitude_findings(spec: dict) -> list[dict]:
    """Guía SGR §3: in the SGR flow direct causes and direct effects carry their
    magnitude (indicator and source), not only the central problem."""
    findings = []
    for group in spec.get("groups") or []:
        if not _has_magnitude(group):
            findings.append(_finding("warning", "sgr-causa-sin-magnitud", str(group.get("id") or ""),
                                     "En el flujo SGR cada causa directa lleva su magnitud (indicador, valor y "
                                     "fuente) en groups[].magnitude."))
    for branch in spec.get("branches") or []:
        if not _has_magnitude(branch):
            findings.append(_finding("warning", "sgr-efecto-sin-magnitud", str(branch.get("id") or ""),
                                     "En el flujo SGR cada efecto directo lleva su magnitud (indicador, valor y "
                                     "fuente) en branches[].magnitude."))
    # Guía SGR §3: one indicator measures one variable, so a direct cause never
    # reuses the indicator of the central problem or of a direct effect.
    measured = {_indicator_key(node) for node in [spec.get("trunk") or {}] + list(spec.get("branches") or [])}
    measured.discard("")
    for group in spec.get("groups") or []:
        if _indicator_key(group) in measured:
            findings.append(_finding("warning", "sgr-magnitud-repetida", str(group.get("id") or ""),
                                     "La causa directa usa el mismo indicador que el problema central o un efecto: "
                                     "su magnitud mide la variable de la causa (por ejemplo, la cobertura de la "
                                     "información en una causa de información)."))
    return findings


def _indicator_key(node: dict) -> str:
    magnitude = node.get("magnitude") if isinstance(node, dict) else None
    if not isinstance(magnitude, dict):
        return ""
    return " ".join(_fold(str(magnitude.get("indicador") or "")).lower().split())


def check_trees(report: Report, run_root: Path, texts: dict[str, str], sections: dict[str, Path],
                flujo: str) -> None:
    problem_path = run_root / PROBLEM_SPEC
    objectives_path = run_root / OBJECTIVES_FILE
    problem = _read_json_file(problem_path)
    objectives = _read_json_file(objectives_path)
    if problem is not None:
        for f in problem_tree_findings(problem, report.lang):
            report.add(f["severity"], f["code"], f["message"], problem_path, node=f["node"])
        if flujo == "sgr":
            for f in sgr_magnitude_findings(problem):
                report.add(f["severity"], f["code"], f["message"], problem_path, node=f["node"])
    if objectives is None:
        return
    if problem is not None:
        for f in objective_tree_findings(objectives, problem, report.lang):
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
        if shared_variable(tree_general, general_objective_text(texts["06_objetivo_general"]), report.lang) < 0.34:
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
            if flujo != "sgr":
                continue
            report.add("warning", "figura-sin-verificar",
                       f"No se pudo cargar redaccion/scripts/render_tikz.py para comprobar que diag_{name}.tex "
                       "corresponde a su spec.", diag)
            continue
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


def _load_assembler():
    """scripts/ensamblar_main.py, or None in a kit that does not ship it."""
    assembler_path = Path(__file__).resolve().parent / "ensamblar_main.py"
    if not assembler_path.is_file():
        return None
    module_spec = importlib.util.spec_from_file_location("ensamblar_main", assembler_path)
    assembler = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(assembler)
    return assembler


def load_tdr_chapters(run_root: Path, flujo: str = "base") -> list[dict] | None:
    """Chapters of a valid estructura_tdr.json, else None. In the SGR flow they are
    the chapters main.tex prints (ensamblar_main.placed_chapters): each SGR section
    the structure does not list joins the first chapter whose title matches."""
    data = _read_json_file(run_root / STRUCTURE_FILE)
    assembler = _load_assembler() if data is not None else None
    if assembler is None:
        return None
    try:
        chapters = assembler.validate(data)
    except assembler.InputError:
        return None
    placed = getattr(assembler, "placed_chapters", None)
    return placed(data, flujo) if placed is not None else chapters


def check_tdr_structure(report: Report, run_root: Path, final: bool) -> None:
    """main.tex in the TDR chapter order (scripts/ensamblar_main.py), verbatim titles."""
    structure_path = run_root / STRUCTURE_FILE
    data = _read_json_file(structure_path)
    if data is None:
        return
    assembler = _load_assembler()
    if assembler is None:
        return
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


SGR_PROBLEM_SUBSECTIONS = ("Problema central", "Descripción de la situación existente", "Magnitud del problema")


def check_sgr_problem_structure(report: Report, texts: dict[str, str], sections: dict[str, Path], flujo: str) -> None:
    """Guía SGR §3: the problem statement keeps the three subsections of mga_resumido.md."""
    name = "03_descripcion_problema"
    if flujo != "sgr" or name not in texts:
        return
    body = "\n".join(strip_comment(line) for line in texts[name].splitlines())
    found = {_fold(title).strip().lower() for title in re.findall(r"\\subsection\*?\{([^}]*)\}", body)}
    missing = [title for title in SGR_PROBLEM_SUBSECTIONS if _fold(title).lower() not in found]
    if missing:
        report.add("warning", "sgr-problema-estructura",
                   "En el flujo SGR §3 sigue la estructura de mga_resumido.md (guía SGR §3, «Estructura de §3»). "
                   f"Faltan las subsecciones: {', '.join(missing)}.", sections[name])


def _sibling_module(name: str):
    """scripts/<name>.py next to this file, or None when it does not exist."""
    path = Path(__file__).resolve().parent / f"{name}.py"
    if not path.is_file():
        return None
    module_spec = importlib.util.spec_from_file_location(f"_check_run_{name}", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


CHAIN_FILE = Path("artefactos") / "sgr" / "cadena_valor.json"
CHAIN_SECTION = "23_cadena_valor"
CHAIN_HEADER = "% GENERADO por scripts/cadena_valor_sgr.py"
G4_APPROVED_RE = re.compile(r"(?im)^.*(?<![\w.])G4(?![\w.]).*\b(APROBADA|APROBADO|PASS)\b")


def _past_objectives_gate(run_root: Path, sec_dir: Path) -> bool:
    """G4 approved in estado_propuesta.md, or a section that comes after it (§8 onwards)."""
    estado = run_root / "artefactos" / "estado_propuesta.md"
    if estado.is_file() and G4_APPROVED_RE.search(estado.read_text(encoding="utf-8", errors="replace")):
        return True
    later = CANONICAL_SECTIONS[CANONICAL_SECTIONS.index("08_marco_conceptual"):]
    return any((sec_dir / f"{name}.tex").is_file() for name in later)


def check_sgr_value_chain(report: Report, run_root: Path, sec_dir: Path, flujo: str) -> None:
    """Value chain as data (scripts/cadena_valor_sgr.py): its findings, its absence, and annex A23."""
    if flujo != "sgr":
        return
    chain_path = run_root / CHAIN_FILE
    if chain_path.is_file():
        try:
            module = _sibling_module("cadena_valor_sgr")
            found = module.findings(run_root) if module is not None else []
        except Exception as exc:  # a broken helper must not hide the other checks
            report.add("warning", "cadena-no-verificable",
                       f"No se pudo correr scripts/cadena_valor_sgr.py: {exc!r}.", chain_path)
            found = []
        for f in found:
            report.add(f["severity"], f["code"], f["message"], chain_path, node=f.get("node"))
    elif _past_objectives_gate(run_root, sec_dir):
        report.add("warning", "cadena-valor-faltante",
                   "En el flujo SGR, después de G4 la cadena de valor vive en artefactos/sgr/cadena_valor.json "
                   "(unidad fase4_sgr): corré python3 scripts/cadena_valor_sgr.py init <RUN_ROOT>.")
    tex = sec_dir / f"{CHAIN_SECTION}.tex"
    if not tex.is_file():
        return
    first = tex.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
    if not first or first[0].strip() != CHAIN_HEADER:
        report.add("error", "cadena-anexo-manual",
                   "En el flujo SGR el anexo A23 no se escribe a mano: lo genera "
                   "python3 scripts/cadena_valor_sgr.py render <RUN_ROOT> desde cadena_valor.json.", tex)
    elif chain_path.is_file() and tex.stat().st_mtime < chain_path.stat().st_mtime:
        report.add("error", "cadena-anexo-desactualizado",
                   "23_cadena_valor.tex es anterior a cadena_valor.json: volvé a correr "
                   "python3 scripts/cadena_valor_sgr.py render <RUN_ROOT>.", tex)


ALLIANCE_FILE = Path("artefactos") / "sgr" / "alianza.json"
TERRITORY_FILE = Path("artefactos") / "sgr" / "territorio.json"
ALLIANCE_HEADER = "% GENERADO por scripts/alianza_territorio_sgr.py"
# Sections rendered by scripts/alianza_territorio_sgr.py: finding prefix and the json files they come from.
ALLIANCE_SECTIONS = {
    "26_identificacion": ("alianza", (ALLIANCE_FILE, TERRITORY_FILE)),
    "27_demandas_territoriales": ("territorio", (TERRITORY_FILE,)),
    "28_matriz_responsabilidades": ("alianza", (ALLIANCE_FILE,)),
}
GTERRITORIO_APPROVED_RE = re.compile(r"(?im)^.*(?<![\w.])GTerritorio(?![\w.]).*\b(APROBADA|APROBADO|PASS)\b")


def check_sgr_alliance_territory(report: Report, run_root: Path, sec_dir: Path, flujo: str) -> None:
    """Alliance and territory as data (scripts/alianza_territorio_sgr.py): findings, absence, rendered sections."""
    if flujo != "sgr":
        return
    files = {"alianza": run_root / ALLIANCE_FILE, "territorio": run_root / TERRITORY_FILE}
    if any(path.is_file() for path in files.values()):
        try:
            module = _sibling_module("alianza_territorio_sgr")
            found = module.findings(run_root) if module is not None else []
        except Exception as exc:  # a broken helper must not hide the other checks
            report.add("warning", "alianza-no-verificable",
                       f"No se pudo correr scripts/alianza_territorio_sgr.py: {exc!r}.", files["alianza"])
            found = []
        for f in found:
            path = files["territorio"] if str(f.get("code")).startswith("territorio-") else files["alianza"]
            report.add(f["severity"], f["code"], f["message"], path, node=f.get("node"))
    estado = run_root / "artefactos" / "estado_propuesta.md"
    if estado.is_file() and GTERRITORIO_APPROVED_RE.search(estado.read_text(encoding="utf-8", errors="replace")):
        for prefix, path in files.items():
            if not path.is_file():
                report.add("warning", f"{prefix}-datos-faltantes",
                           f"En el flujo SGR, después de GTerritorio los datos de {prefix} viven en "
                           f"{path.relative_to(run_root).as_posix()} (unidad fase1b_sgr «Alianza y territorio»).")
    for stem, (prefix, sources) in ALLIANCE_SECTIONS.items():
        tex = sec_dir / f"{stem}.tex"
        if not tex.is_file():
            continue
        first = tex.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        stamps = [(run_root / s).stat().st_mtime for s in sources if (run_root / s).is_file()]
        if not first or first[0].strip() != ALLIANCE_HEADER:
            report.add("error", f"{prefix}-anexo-manual",
                       f"En el flujo SGR {stem}.tex no se escribe a mano: lo genera "
                       "python3 scripts/alianza_territorio_sgr.py render <RUN_ROOT> desde alianza.json y territorio.json.",
                       tex)
        elif stamps and tex.stat().st_mtime < max(stamps):
            report.add("error", f"{prefix}-anexo-desactualizado",
                       f"{stem}.tex es anterior a los datos de los que sale: volvé a correr "
                       "python3 scripts/alianza_territorio_sgr.py render <RUN_ROOT>.", tex)


BUDGET_FILE = Path("artefactos") / "sgr" / "presupuesto.json"
BUDGET_HEADER = "% GENERADO por scripts/presupuesto_sgr.py"
# Sections rendered by scripts/presupuesto_sgr.py and the json files they come from.
BUDGET_SECTIONS = {
    "13_presupuesto": (BUDGET_FILE, ALLIANCE_FILE, CHAIN_FILE),
    "30_fuentes_financiacion": (BUDGET_FILE, ALLIANCE_FILE),
}
G64_APPROVED_RE = re.compile(r"(?im)^.*(?<![\w.-])(G6\.4|G-Presupuesto)(?![\w.]).*\b(APROBADA|APROBADO|PASS)\b")


def _module_findings(report: Report, name: str, code: str, run_root: Path, path: Path | None) -> list[dict]:
    """findings(run_root) of scripts/<name>.py; [] when it does not exist, a warning when it breaks."""
    try:
        module = _sibling_module(name)
        return list(module.findings(run_root) or []) if module is not None else []
    except Exception as exc:  # a broken helper must not hide the other checks
        report.add("warning", code, f"No se pudo correr scripts/{name}.py: {exc!r}.", path)
        return []


def check_sgr_budget_schedule(report: Report, run_root: Path, sec_dir: Path, flujo: str) -> None:
    """Budget as data (scripts/presupuesto_sgr.py) and schedule (scripts/cronograma_sgr.py): findings,
    absence after G6.4 and the rendered sections 13 and 30."""
    if flujo != "sgr":
        return
    budget = run_root / BUDGET_FILE
    if budget.is_file():
        for f in _module_findings(report, "presupuesto_sgr", "presupuesto-no-verificable", run_root, budget):
            report.add(f["severity"], f["code"], f["message"], budget, node=f.get("node"))
    else:
        estado = run_root / "artefactos" / "estado_propuesta.md"
        if estado.is_file() and G64_APPROVED_RE.search(estado.read_text(encoding="utf-8", errors="replace")):
            report.add("warning", "presupuesto-datos-faltantes",
                       "En el flujo SGR, después de G6.4 el presupuesto vive en artefactos/sgr/presupuesto.json "
                       "y §13 se genera con python3 scripts/presupuesto_sgr.py render <RUN_ROOT>.")
    chain = run_root / CHAIN_FILE
    for f in _module_findings(report, "cronograma_sgr", "cronograma-no-verificable", run_root, chain):
        report.add(f["severity"], f["code"], f["message"], chain, node=f.get("node"))
    for stem, sources in BUDGET_SECTIONS.items():
        tex = sec_dir / f"{stem}.tex"
        if not tex.is_file() or (stem == "13_presupuesto" and not budget.is_file()):
            continue
        first = tex.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        stamps = [(run_root / s).stat().st_mtime for s in sources if (run_root / s).is_file()]
        if not first or first[0].strip() != BUDGET_HEADER:
            report.add("error", "presupuesto-anexo-manual",
                       f"En el flujo SGR {stem}.tex no se escribe a mano: lo genera "
                       "python3 scripts/presupuesto_sgr.py render <RUN_ROOT> desde presupuesto.json.", tex)
        elif stamps and tex.stat().st_mtime < max(stamps):
            report.add("error", "presupuesto-anexo-desactualizado",
                       f"{stem}.tex es anterior a los datos de los que sale: volvé a correr "
                       "python3 scripts/presupuesto_sgr.py render <RUN_ROOT>.", tex)


COMPONENTS_FILE = Path("artefactos") / "sgr" / "componentes.json"
COMPONENTS_HEADER = "% GENERADO por scripts/componentes_sgr.py"
# Sections rendered by scripts/componentes_sgr.py and the json files they come from.
COMPONENTS_SECTIONS = {
    "31_trl": (COMPONENTS_FILE, CHAIN_FILE, ALLIANCE_FILE),
    "32_sostenibilidad": (COMPONENTS_FILE, CHAIN_FILE),
    "33_uso_posterior": (COMPONENTS_FILE, ALLIANCE_FILE),
    "34_transferencia": (COMPONENTS_FILE, CHAIN_FILE, ALLIANCE_FILE, BUDGET_FILE),
    "35_medidas_diferenciales": (COMPONENTS_FILE, CHAIN_FILE),
    "18_apropiacion_social": (COMPONENTS_FILE, CHAIN_FILE),
}
GCOMPONENTES_APPROVED_RE = re.compile(r"(?im)^.*(?<![\w.])GComponentes(?![\w.]).*\b(APROBADA|APROBADO|PASS)\b")


def check_sgr_components(report: Report, run_root: Path, sec_dir: Path, flujo: str) -> None:
    """TRL route and transversal components as data (scripts/componentes_sgr.py): findings, absence
    after GComponentes and the rendered sections 31 to 35 and 18."""
    if flujo != "sgr":
        return
    data = run_root / COMPONENTS_FILE
    if data.is_file():
        for f in _module_findings(report, "componentes_sgr", "componentes-no-verificable", run_root, data):
            report.add(f["severity"], f["code"], f["message"], data, node=f.get("node"))
    else:
        estado = run_root / "artefactos" / "estado_propuesta.md"
        if estado.is_file() and GCOMPONENTES_APPROVED_RE.search(estado.read_text(encoding="utf-8", errors="replace")):
            report.add("warning", "componentes-datos-faltantes",
                       "En el flujo SGR, después de GComponentes el TRL y los componentes transversales viven en "
                       "artefactos/sgr/componentes.json (unidad fase5_5_sgr «TRL y componentes transversales»).")
    for stem, sources in COMPONENTS_SECTIONS.items():
        tex = sec_dir / f"{stem}.tex"
        if not tex.is_file() or (stem == "18_apropiacion_social" and not data.is_file()):
            continue
        first = tex.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        stamps = [(run_root / s).stat().st_mtime for s in sources if (run_root / s).is_file()]
        if not first or first[0].strip() != COMPONENTS_HEADER:
            report.add("error", "componentes-anexo-manual",
                       f"En el flujo SGR {stem}.tex no se escribe a mano: lo genera "
                       "python3 scripts/componentes_sgr.py render <RUN_ROOT> desde componentes.json.", tex)
        elif stamps and tex.stat().st_mtime < max(stamps):
            report.add("error", "componentes-anexo-desactualizado",
                       f"{stem}.tex es anterior a los datos de los que sale: volvé a correr "
                       "python3 scripts/componentes_sgr.py render <RUN_ROOT>.", tex)


PRODUCTS_FILE = Path("artefactos") / "sgr" / "productos.json"
PRODUCTS_HEADER = "% GENERADO por scripts/productos_sgr.py"
# Sections rendered by scripts/productos_sgr.py and the json files they come from.
PRODUCTS_SECTIONS = {
    "36_talento_humano": (PRODUCTS_FILE, CHAIN_FILE, ALLIANCE_FILE),
    "37_indicadores": (PRODUCTS_FILE, CHAIN_FILE),
    "15_productos_esperados": (PRODUCTS_FILE, CHAIN_FILE, ALLIANCE_FILE),
}
GPRODUCTOS_APPROVED_RE = re.compile(r"(?im)^.*(?<![\w.])GProductos(?![\w.]).*\b(APROBADA|APROBADO|PASS)\b")


def check_sgr_products(report: Report, run_root: Path, sec_dir: Path, flujo: str) -> None:
    """Products, talent and indicators as data (scripts/productos_sgr.py): findings, absence after
    GProductos and the rendered sections 36, 37 and 15."""
    if flujo != "sgr":
        return
    data = run_root / PRODUCTS_FILE
    if data.is_file():
        for f in _module_findings(report, "productos_sgr", "productos-no-verificable", run_root, data):
            report.add(f["severity"], f["code"], f["message"], data, node=f.get("node"))
    else:
        estado = run_root / "artefactos" / "estado_propuesta.md"
        if estado.is_file() and GPRODUCTOS_APPROVED_RE.search(estado.read_text(encoding="utf-8", errors="replace")):
            report.add("warning", "productos-datos-faltantes",
                       "En el flujo SGR, después de GProductos los productos, el talento humano y los indicadores "
                       "viven en artefactos/sgr/productos.json (unidad fase5_sgr «Productos, talento e indicadores»).")
    for stem, sources in PRODUCTS_SECTIONS.items():
        tex = sec_dir / f"{stem}.tex"
        if not tex.is_file() or (stem == "15_productos_esperados" and not data.is_file()):
            continue
        first = tex.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        stamps = [(run_root / s).stat().st_mtime for s in sources if (run_root / s).is_file()]
        if not first or first[0].strip() != PRODUCTS_HEADER:
            report.add("error", "productos-anexo-manual",
                       f"En el flujo SGR {stem}.tex no se escribe a mano: lo genera "
                       "python3 scripts/productos_sgr.py render <RUN_ROOT> desde productos.json.", tex)
        elif stamps and tex.stat().st_mtime < max(stamps):
            report.add("error", "productos-anexo-desactualizado",
                       f"{stem}.tex es anterior a los datos de los que sale: volvé a correr "
                       "python3 scripts/productos_sgr.py render <RUN_ROOT>.", tex)


REQUIREMENTS_FILE = Path("artefactos") / "sgr" / "requisitos.json"
REQUIREMENTS_HEADER = "% GENERADO por scripts/requisitos_sgr.py"
# Sections rendered by scripts/requisitos_sgr.py and the json files they come from.
REQUIREMENTS_SECTIONS = {
    "38_licencias_permisos": (REQUIREMENTS_FILE, ALLIANCE_FILE),
    "39_anexos": (REQUIREMENTS_FILE, ALLIANCE_FILE, Path("artefactos") / "sgr" / "presupuesto.json"),
}
GREQUISITOS_APPROVED_RE = re.compile(r"(?im)^.*(?<![\w.])GRequisitos(?![\w.]).*\b(APROBADA|APROBADO|PASS)\b")


def check_sgr_requirements(report: Report, run_root: Path, sec_dir: Path, flujo: str) -> None:
    """Enabling requirements, licences and annexes as data (scripts/requisitos_sgr.py): findings, absence
    after GRequisitos and the rendered sections 38 and 39."""
    if flujo != "sgr":
        return
    data = run_root / REQUIREMENTS_FILE
    if data.is_file():
        for f in _module_findings(report, "requisitos_sgr", "requisitos-no-verificable", run_root, data):
            report.add(f["severity"], f["code"], f["message"], data, node=f.get("node"))
    else:
        estado = run_root / "artefactos" / "estado_propuesta.md"
        if estado.is_file() and GREQUISITOS_APPROVED_RE.search(estado.read_text(encoding="utf-8", errors="replace")):
            report.add("warning", "requisitos-datos-faltantes",
                       "En el flujo SGR, después de GRequisitos los requisitos habilitantes, las licencias y los "
                       "anexos viven en artefactos/sgr/requisitos.json (unidad fase6_9_sgr «Requisitos y anexos»).")
    for stem, sources in REQUIREMENTS_SECTIONS.items():
        tex = sec_dir / f"{stem}.tex"
        if not tex.is_file():
            continue
        first = tex.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        stamps = [(run_root / s).stat().st_mtime for s in sources if (run_root / s).is_file()]
        if not first or first[0].strip() != REQUIREMENTS_HEADER:
            report.add("error", "requisitos-anexo-manual",
                       f"En el flujo SGR {stem}.tex no se escribe a mano: lo genera "
                       "python3 scripts/requisitos_sgr.py render <RUN_ROOT> desde requisitos.json.", tex)
        elif stamps and tex.stat().st_mtime < max(stamps):
            report.add("error", "requisitos-anexo-desactualizado",
                       f"{stem}.tex es anterior a los datos de los que sale: volvé a correr "
                       "python3 scripts/requisitos_sgr.py render <RUN_ROOT>.", tex)


def check_sgr_style(report: Report, run_root: Path, flujo: str) -> None:
    """SGR style findings (scripts/estilo_sgr.py), as warnings: advice for the style reviewer."""
    if flujo != "sgr":
        return
    try:
        module = _sibling_module("estilo_sgr")
        found = module.findings(run_root) if module is not None else []
    except Exception as exc:
        report.add("warning", "sgr-estilo-no-verificable", f"No se pudo correr scripts/estilo_sgr.py: {exc!r}.")
        return
    for f in found or []:
        archivo = f.get("archivo")
        path = (run_root / archivo) if archivo and not Path(archivo).is_absolute() else (Path(archivo) if archivo else None)
        message = str(f.get("message") or "")
        if f.get("extracto"):
            message += f" «{f['extracto']}»"
        report.add("warning", str(f.get("code") or "sgr-estilo"), message, path, line=f.get("linea"))


def _file_has_content(path: Path) -> bool:
    """A file with something besides comments, headings and labels."""
    if not path.is_file():
        return False
    body = "\n".join(strip_comment(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines())
    return bool(re.sub(r"\\(?:sub)*section\*?\s*\{[^{}]*\}|\\label\{[^{}]*\}", "", body).strip())


def _guide_declares_chapters(run_root: Path) -> bool:
    """The adjusted guide has the chapter table of `ensamblar_main.py --from-guide`.
    A numbered table without files (a rubric, say) is not one."""
    assembler = _load_assembler()
    if assembler is None or not (run_root / assembler.GUIDE).is_file():
        return False
    try:
        data = assembler.from_guide((run_root / assembler.GUIDE).read_text(encoding="utf-8", errors="replace"))
    except assembler.InputError:
        return False
    return any(chapter["archivos"] for chapter in data["capitulos"])


def check_sgr_chapters(report: Report, run_root: Path, sec_dir: Path, chapters: list[dict] | None, flujo: str,
                       final: bool) -> None:
    """--final in SGR: the TDR chapters decide which files the document needs."""
    if flujo != "sgr" or not final:
        return
    structure_path = run_root / STRUCTURE_FILE
    if chapters is None:
        if structure_path.is_file():
            # A readable but invalid structure was reported by check_tdr_structure.
            if _read_json_file(structure_path) is None:
                report.add("error", "tdr-estructura-invalida", "artefactos/estructura_tdr.json no es un objeto JSON "
                                                               "válido.", structure_path)
        elif _guide_declares_chapters(run_root):
            report.add("error", "tdr-estructura-faltante",
                       "guia_ajustada_TDR.md declara capítulos propios del TDR y falta artefactos/estructura_tdr.json. "
                       f"Créalo con: python3 scripts/ensamblar_main.py {run_root} --from-guide")
        return
    reported: set[str] = set()
    for chapter in chapters:
        names = chapter["archivos"]
        for name in names:
            if not name.startswith("diag_") and name not in reported and not (sec_dir / f"{name}.tex").is_file():
                reported.add(name)
                report.add("error", "seccion-faltante", f"Falta sections/{name}.tex (capítulo {chapter['numero']}).")
        if not any(_file_has_content(sec_dir / f"{name}.tex") for name in names):
            report.add("error", "tdr-capitulo-vacio", f"El capítulo {chapter['numero']} no tiene archivos con "
                                                      "contenido.", run_root / STRUCTURE_FILE)


WORK_MARK_RE = re.compile(r"\[(?:PENDIENTE|VERIFICAR|CONFIRMAR|PROPUESTA)")


def check_sgr_marks(report: Report, sec_dir: Path, flujo: str, final: bool) -> None:
    """Working marks left in a section file; tables count, since they print."""
    if flujo != "sgr":
        return
    for path in sorted(sec_dir.glob("*.tex")):
        for number, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            for match in WORK_MARK_RE.finditer(strip_comment(raw)):
                report.add("error" if final else "warning", "sgr-marca-trabajo",
                           f"Marca de trabajo {match.group(0)}…] sin resolver.", path, number)


def check_rubrica(report: Report, run_root: Path, convocatoria: dict, chapters: list[dict] | None, flujo: str) -> None:
    """Rubric of the call: entries point to real chapters and the points add up."""
    rubrica = convocatoria.get("rubrica") or []
    if flujo != "sgr" or not rubrica:
        return
    path = run_root / CONVOCATORIA_FILE
    if chapters is not None:
        known = {str(chapter["numero"]) for chapter in chapters}
        for item in rubrica:
            for chapter in item.get("capitulos") or []:
                if str(chapter) not in known:
                    report.add("error", "rubrica-capitulo-inexistente",
                               f"El criterio {item.get('id')} de la rúbrica apunta al capítulo {chapter}, que no está "
                               "en artefactos/estructura_tdr.json.", path)
    total = sum(item.get("puntos") or 0 for item in rubrica)
    if abs(total - 100) > 1e-9:
        report.add("warning", "rubrica-puntos", f"La rúbrica suma {total:g} puntos, no 100.", path)


def check_sgr_sections(report: Report, sec_dir: Path, flujo: str, final: bool, by_chapters: bool = False) -> None:
    if flujo != "sgr" or not final or by_chapters:
        return
    for name in SGR_SECTIONS:
        if not (sec_dir / f"{name}.tex").is_file():
            report.add("error", "sgr-anexo-faltante", f"Falta sections/{name}.tex (anexo MGA del flujo SGR).")


def run_checks(run_root: Path, final: bool, flujo: str | None = None, lang: str | None = None) -> Report:
    report = Report(run_root)
    report.flujo = flujo if flujo in FLUJOS else detect_flujo(run_root)
    # The SGR flow is Spanish only (DNP/MGA).
    report.lang = "es" if report.flujo == "sgr" else lang if lang in LANGS else detect_lang(run_root)
    red = run_root / "redaccion"
    sec_dir = red / "sections"
    if not sec_dir.is_dir():
        report.add("error", "corrida-invalida", f"No existe {sec_dir}.")
        return report

    for stray in sorted(sec_dir.glob("01_titulo*.tex")):
        report.add("error", "seccion-1-en-cuerpo",
                   "No debe existir un archivo de §1: el título va solo en la portada de main.tex.", stray)

    sgr = report.flujo == "sgr"
    convocatoria = load_convocatoria(run_root, report) if sgr else {}
    chapters = load_tdr_chapters(run_root, report.flujo) if sgr else None
    # With a structure, even an invalid one, the TDR decides the required files.
    by_chapters = sgr and (run_root / STRUCTURE_FILE).is_file()

    sections = {name: sec_dir / f"{name}.tex" for name in CANONICAL_SECTIONS if (sec_dir / f"{name}.tex").is_file()}
    if sgr:
        sections.update((path.stem, path) for path in sorted(sec_dir.glob("tdr*.tex")))
    texts = {name: path.read_text(encoding="utf-8", errors="replace") for name, path in sections.items()}
    if final and not by_chapters:
        for name in CANONICAL_SECTIONS:
            if name not in sections:
                report.add("error", "seccion-faltante", f"Falta sections/{name}.tex.")

    prose_files = list(sections.items()) + [(p.stem, p) for p in sorted(sec_dir.glob("diag_*_caption.tex"))]
    for name, path in prose_files:
        check_prose(report, path, texts.get(name) or path.read_text(encoding="utf-8", errors="replace"))

    keys_by_section = check_citations(report, sections, texts)
    check_floors(report, sections, keys_by_section, final, report.flujo, convocatoria)
    check_trl(report, sections, texts, report.flujo, convocatoria)
    check_objectives(report, sections, texts, report.flujo, convocatoria)
    check_main(report, red, final)
    check_cover(report, red, final)
    check_bibliography(report, sections, texts)
    check_pdf(report, red)
    check_trees(report, run_root, texts, sections, report.flujo)
    check_tree_figures(report, run_root, report.flujo)
    check_tdr_structure(report, run_root, final)
    check_sgr_methodology_schedule(report, run_root, texts, sections, report.flujo)
    check_sgr_problem_structure(report, texts, sections, report.flujo)
    check_sgr_sections(report, sec_dir, report.flujo, final, by_chapters)
    check_sgr_chapters(report, run_root, sec_dir, chapters, report.flujo, final)
    check_sgr_marks(report, sec_dir, report.flujo, final)
    check_rubrica(report, run_root, convocatoria, chapters, report.flujo)
    check_sgr_value_chain(report, run_root, sec_dir, report.flujo)
    check_sgr_alliance_territory(report, run_root, sec_dir, report.flujo)
    check_sgr_budget_schedule(report, run_root, sec_dir, report.flujo)
    check_sgr_components(report, run_root, sec_dir, report.flujo)
    check_sgr_products(report, run_root, sec_dir, report.flujo)
    check_sgr_requirements(report, run_root, sec_dir, report.flujo)
    check_sgr_style(report, run_root, report.flujo)
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
    parser.add_argument("--lang", choices=LANGS, help="override the writing language read from the run")
    args = parser.parse_args()

    run_root = resolve_run_root(args.run_root)
    flujo = args.flujo if args.flujo in FLUJOS else detect_flujo(run_root)
    if flujo == "sgr" and args.lang == "en":
        # The SGR flow is Spanish only (DNP/MGA): say so instead of ignoring the flag.
        print("check_run: el flujo SGR se redacta solo en español; --lang en no aplica.", file=sys.stderr)
        return 2
    report = run_checks(run_root, args.final, args.flujo, args.lang)
    if args.json:
        payload = {"flujo": report.flujo, "findings": report.findings}
        if report.lang != "es":
            payload = {"flujo": report.flujo, "lang": report.lang, "findings": report.findings}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for f in report.findings:
            where = f["file"] + (f":{f['line']}" if f["line"] else "") + (f" [{f['node']}]" if f.get("node") else "")
            print(f"[{f['severity'].upper()}] {f['code']} {where} {f['message']}".rstrip())
        warnings = len(report.findings) - report.errors()
        print(f"check_run: {report.errors()} errores, {warnings} avisos")
    return 1 if report.errors() else 0


if __name__ == "__main__":
    sys.exit(main())
