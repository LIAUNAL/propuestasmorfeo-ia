#!/usr/bin/env python3
"""Readability and redundancy report for English proposal prose.

The English counterpart of `scripts/estilo_es.py`, for runs whose writing
language is `en` (`python3 scripts/language.py run <RUN_ROOT>`). `audit` scores
a run, a .docx or a text file and locates what slows a reader down: stock
phrases, overused academic vocabulary, trailing participle clauses, long
sentences, repeated openings and connectors, repeated phrases and
near-duplicate sentences. `verify` compares two versions of a text and fails
when a fact changed.

    estilo_en.py audit <RUN_ROOT> [--section N] [--all] [--json]
    estilo_en.py audit --docx <path> | --txt <path> [--section N] [--all] [--json]
    estilo_en.py verify <before> <after> [--json]

The Spanish names work too (`auditar`, `verificar`, `--seccion`, `--todo`), so
an agent swaps only the script name between languages. The report has the
schema of estilo_es.py (same keys, category ids and thresholds) plus
`"idioma": "en"`, and a run gets it in the same place:
`artefactos/estilo/reporte.json` and `reporte.md`.

The engine is estilo_es.py itself: this script loads a private copy of it and
replaces its language tables (catalog, connectors, function words, protected
vocabulary, sentence and fact patterns, guidance, report wording). Scoring,
redundancy search, protected-term collapsing and fact extraction are shared,
so both languages are measured the same way. Scores measure readability only:
they say nothing about who wrote the text or about its scientific value.

Exit codes: 0 report written, or `verify` found no change; 1 `verify` found a
change; 2 invalid input.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree


def _load_engine():
    """A private instance of estilo_es.py: rebinding its tables here never touches
    the module estilo_es.py itself runs with."""
    path = Path(__file__).resolve().with_name("estilo_es.py")
    spec = importlib.util.spec_from_file_location("_estilo_engine_en", path)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve the engine's string annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


engine = _load_engine()
LANGUAGE = "en"

AVISO = ("The index measures the readability and flow of the prose. It says nothing about who wrote the text "
         "or about its scientific value, and its thresholds are provisional: it guides the revision, it does not "
         "approve it.")
ESCALA = "puntaje_estilo and puntaje_flujo run from 0 to 1 (lower is better); indice runs from 0 to 100 (higher is better)."
MOTIVOS = {
    "sgr": "literal copy of the tree required by the SGR guide (§3, §6 and §7)",
    "protegido": "protected term of the run",
    "resumen": "the summary restates the body of the document",
    "dominio": "vocabulary of the run's title or trees",
}

# Short function words, then the long ones that carry no topic.
FUNCTION_WORDS = frozenset("""
    a about above after again against all also am an and any are as at be been before being below between both
    but by can could did do does doing down during each either else ever every few for from further had has have
    having he her here hers him his how however i if in into is it its itself just least less may me might more
    most much must my neither no nor not now of off on once one only or other others our ours out over own per
    rather same shall she should since so some such than that the their theirs them then there these they this
    those though through thus to too two under until up upon us very via was we were what when where whether
    which while who whom whose why will with within without would yet you your three four first second third
    many several whereas among across along around beyond toward towards onto unless
""".split())
LONG_STOPWORDS = frozenset("""
    about above after again against among around before behind below beneath beside besides between beyond
    during except inside outside since through throughout toward towards under underneath until within without
    which where while whose these those their there other others another every level levels index degree
    general specific means might could would should shall being having
""".split())
NOUN_CONTEXT = frozenset("the a an this that these those its their our his her each every such of".split())
STOP = FUNCTION_WORDS | LONG_STOPWORDS

PROTECTED_TERMS = (
    "problem tree", "objective tree", "objectives tree", "central problem", "direct cause", "direct causes",
    "indirect cause", "indirect causes", "direct effect", "direct effects", "indirect effect", "indirect effects",
    "general objective", "specific objective", "specific objectives", "value chain", "logical framework",
    "affected population", "target population", "baseline", "current situation", "expected situation",
    "expected result", "expected results", "research question", "technology readiness level",
    "technology transfer", "social appropriation of knowledge", "means of verification", "product indicator",
    "product indicators", "management indicator", "management indicators", "funding sources",
    "general methodology adjusted", "general royalties system",
)
INSTITUTIONS = (
    "Universidad Nacional de Colombia", "National University of Colombia", "Sede Manizales", "Manizales campus",
    "Universidad Tecnológica de Pereira", "Technological University of Pereira", "Universidad de Antioquia",
    "University of Antioquia", "Departamento Nacional de Planeación", "National Planning Department",
    "Ministerio de Ciencia, Tecnología e Innovación", "Ministry of Science, Technology and Innovation",
    "MinCiencias", "SNCTeI", "GCPDS", "LabIA",
)

# (category, regex). Seeded from estilo-natural-en, section 3. Category ids are
# the machine ids of the Spanish report, so both languages share one schema.
_CATALOG_SOURCE = (
    ("cliche", r"\bplay(?:s|ed|ing)? an? (?:\w+ )?(?:crucial|key|pivotal|vital|central|significant|critical|fundamental|important|essential) role\b"),
    ("cliche", r"\b(?:serv(?:e|es|ed|ing)|stands?|stood) as a testament to\b|\ba testament to\b"),
    ("cliche", r"\bpav(?:e|es|ed|ing) the way\b|\bopen(?:s|ed|ing)? (?:up )?new avenues\b"),
    ("cliche", r"\b(?:lay(?:s|ing)?|laid) the (?:foundation|foundations|groundwork)\b"),
    ("cliche", r"\bat the (?:heart|forefront|core) of\b"),
    ("cliche", r"\ba (?:game[- ]changer|paradigm shift|turning point|watershed moment|new era)\b|\bgame[- ]changing\b"),
    ("cliche", r"\bshed(?:s|ding)? (?:new )?light on\b"),
    ("cliche", r"\bnavigat(?:e|es|ed|ing) the (?:complexities|challenges|intricacies|landscape) of\b"),
    ("cliche", r"\b(?:in|within|across) the (?:realm|landscape|tapestry) of\b"),
    ("cliche", r"\bever[- ](?:evolving|changing|growing|expanding)\b"),
    ("cliche", r"\ba promising (?:future|horizon)\b|\ba step in the right direction\b"),
    ("cliche", r"\b(?:data|technology) is the new (?:oil|currency|mirror)\b"),
    ("comodin", r"\bdelv(?:e|es|ed|ing)\b"),
    ("comodin", r"\b(?:tapestry|tapestries|testament|beacon|paramount|multifaceted|meticulous(?:ly)?|seamless(?:ly)?|"
                r"holistic(?:ally)?|pivotal|interplay|overarching|realms?|intricacies|intricate|nuanced|myriad|"
                r"plethora|crucial(?:ly)?|synerg(?:y|ies)|quintessential|indispensable)\b"),
    ("comodin", r"\b(?:underscor|bolster|foster|harness|leverag|showcas)(?:e|es|ed|ing|s)?\b"),
    ("comodin", r"\bunlock(?:s|ed|ing)? the (?:full )?(?:potential|power)\b"),
    ("comodin", r"\ba (?:wide|broad|diverse|rich) (?:array|range|variety|spectrum) of\b"),
    ("comodin", r"\bultimately\b"),
    ("promocional", r"\b(?:revolutionary|revolutioniz(?:e|es|ed|ing)|groundbreaking|cutting[- ]edge|unprecedented|"
                    r"remarkable|vibrant|stunning|breathtaking|transformative|world[- ]class|unparalleled)\b"),
    ("promocional", r"\b(?:profound|tremendous|immense) impact\b|\bsecond to none\b"),
    ("atribucion_vaga", r"\b(?:experts|researchers|scholars|many authors) (?:agree|argue|believe|suggest|note)\b"),
    ("atribucion_vaga", r"\b(?:recent|several|many|numerous|various) studies (?:show|suggest|indicate|demonstrate|have shown|report)\b"),
    ("atribucion_vaga", r"\bthe literature (?:suggests|shows|indicates|reports)\b"),
    ("atribucion_vaga", r"\bit is (?:widely|generally|commonly) (?:accepted|believed|known|recognized|acknowledged)\b"),
    ("perifrasis", r"\b(?:due to|owing to) the fact that\b"),
    ("perifrasis", r"\bin order to\b"),
    ("perifrasis", r"\b(?:has|have|had) the (?:ability|capacity|capability) to\b"),
    ("perifrasis", r"\bfor the purpose of\b|\bwith the aim of\b|\bin the event that\b|\bat this point in time\b"),
    ("perifrasis", r"\ba (?:large|significant|considerable) number of\b"),
    ("copula_evitada", r"\b(?:serv(?:e|es|ed|ing)|stands?|functions?) as\b"),
    ("copula_evitada", r"\bboast(?:s|ed|ing)?\b"),
    ("calco", r"\binvestigation (?:groups?|projects?|lines?|teams?|centers?|centres?)\b|\blines? of investigation\b"),
    ("calco", r"\b(?:human talent )?formation of (?:human talent|researchers|students|young researchers)\b|\bcapacitation\b"),
    ("calco", r"\brealiz(?:e|es|ed|ing) (?:a|an|the) (?:study|analysis|survey|test|evaluation|validation|diagnosis)\b"),
    ("calco", r"\b(?:make|makes|made|making) (?:a|an) (?:study|analysis|investigation)\b"),
    ("calco", r"\b(?:in|on) base (?:to|of)\b"),
    ("calco", r"\bassist(?:s|ed|ing)? to\b"),
    ("calco", r"\bactual (?:situation|context|state|moment|conditions|scenario)\b"),
    ("calco", r"\b(?:project|proposal|methodology|plan|budget) (?:contemplates|pretends to)\b"),
    ("plantilla", r"\bit (?:is|should be) (?:worth noting|important to note|noted|noteworthy) that\b"),
    ("plantilla", r"\bit is (?:important|essential|crucial|necessary|worth) (?:to )?(?:note|mention|highlight|emphasize|stress|point out) that\b"),
    ("plantilla", r"\bit is (?:clear|evident|apparent) that\b"),
    ("plantilla", r"\bin (?:today's|the current|the modern) (?:world|era|digital age|landscape|society)\b|"
                  r"\bin the (?:digital|modern) (?:era|age)\b|\bnowadays\b"),
    ("plantilla", r"\bin this (?:section|chapter),? we (?:will )?(?:describe|present|discuss|outline)\b|"
                  r"\bthis section (?:will )?(?:describes?|presents?|discuss(?:es)?|outlines?)\b"),
    ("plantilla", r"\b(?:to be honest|truth be told|the truth is that)\b"),
    ("plantilla", r"\bthe real question is\b|\bwhat (?:really|truly) matters\b"),
    ("plantilla", r"\bi hope this (?:section|proposal)\b|\bof course\b|\blet(?:'s| us) (?:delve|dive|explore)\b"),
    ("plantilla", r"\b(?:this|which) (?:highlights|underscores|demonstrates|showcases|emphasizes) the (?:importance|need|potential|value)\b"),
    ("paralelismo_negativo", r"\bnot only\b[^.;]{1,120}?\bbut(?: also)?\b"),
    ("paralelismo_negativo", r"\b(?:it|this) is not (?:just|merely|simply) (?:a|an|about)\b[^.;]{1,120}?\b(?:but|it is)\b"),
    ("falso_rango", r"\branging from\b(?![^.;]{0,8}\d)[^.;\d]{3,80}?\bto\b(?!\s+\S*\d)"),
    ("falso_rango", r"\bfrom\b[^.;\d]{3,60}?\bto\b[^.;\d]{3,60}?\band everything in between\b"),
    ("matizacion", r"\b(?:could|might|may) (?:potentially|possibly|perhaps|arguably|conceivably)\b"),
    ("matizacion", r"\b(?:potentially|possibly|perhaps) (?:could|might|may)\b|\bit (?:could|might|may) be argued that\b"),
)
CATALOG = tuple((category, re.compile(pattern, re.I)) for category, pattern in _CATALOG_SOURCE)
STYLE_CATEGORIES = engine.STYLE_CATEGORIES | {"matizacion"}

# Folded and lower case, as the engine compares them.
CONNECTORS = (
    "on the other hand", "on the one hand", "in this context", "in this regard", "in this sense", "as a result",
    "to this end", "in addition", "in contrast", "in particular", "first of all", "that said", "in turn",
    "firstly", "secondly", "thirdly", "however", "moreover", "furthermore", "additionally", "notably",
    "specifically", "importantly", "consequently", "therefore", "thus", "hence", "indeed", "conversely",
    "finally", "interestingly", "crucially", "accordingly", "nevertheless", "nonetheless", "similarly",
    "likewise", "subsequently", "ultimately",
)
SYNTHESIS_CONNECTORS = ("in summary", "in conclusion", "to summarize", "in short", "all in all", "overall",
                        "taken together", "in sum")
_ALL_CONNECTORS = tuple(sorted(set(CONNECTORS + SYNTHESIS_CONNECTORS), key=len, reverse=True))
CONNECTOR_RE = re.compile(r"(" + "|".join(_ALL_CONNECTORS) + r")\b")
DEMONSTRATIVE_RE = re.compile(r"(?:This|These|That|Those|Such)\s+([^\W\d_]+)")
VERBS_AFTER_DEMONSTRATIVE = frozenset({
    "is", "are", "was", "were", "will", "would", "can", "could", "may", "might", "has", "have", "had", "means",
    "shows", "suggests", "indicates", "implies", "allows", "requires", "makes", "gives", "leads", "is", "also",
})
CAUSAL_RE = re.compile(r"\b(?:because|given that|(?:due|owing) to the fact that)\b", re.I)
TAIL_RE = re.compile(r",\s+which\b", re.I)
_PARTICIPLES = ("highlighting|underscoring|demonstrating|showcasing|emphasizing|emphasising|reflecting|ensuring|"
                "fostering|paving|enabling|contributing|reinforcing|marking|solidifying|signaling|signalling|"
                "positioning|cementing|underlining|illustrating|offering|providing|making|setting")
GERUND_TAIL_RE = re.compile(r",\s+(?:thereby\s+|thus\s+)?(" + _PARTICIPLES + r")\b[^,;:]*[.!?]?\s*$", re.I)
NOT_GERUNDS: frozenset = frozenset()
TRIAD_RE = re.compile(r"(?<!, )\b([^\W\d_]{4,}), ([^\W\d_]{4,}),? and ([^\W\d_]{4,})\b")
# English writes the em dash with or without spaces; both break the rule.
DASH_RE = re.compile(r"\s—\s|(?<=[^\W\d_])—(?=[^\W\d_])|\s-{2,3}\s|(?<=[^\W\d_])-{2,3}(?=[^\W\d_])")
ABBREVIATIONS = frozenset({
    "p", "pp", "e.g", "i.e", "fig", "figs", "eq", "eqs", "no", "nos", "vol", "vols", "ed", "eds", "ch", "chap",
    "sec", "secs", "dr", "mr", "mrs", "ms", "prof", "inc", "ltd", "co", "vs", "cf", "approx", "dept", "univ",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "st", "et", "al",
})
CITE_LABEL = "(citation)"
CONNECTOR_DENSITY_SPAN = "{opened} of {n} sentences open with a connector"
PLACEHOLDER_PREFIXES = ("[Por definir", "[To be defined")

ORIENTACION = {
    "cliche": "Replace the stock phrase with what the project does: a direct verb, its object and, when it exists, its figure.",
    "comodin": "Keep the word only if it says something measurable; otherwise name the concrete property or action.",
    "promocional": "Replace the praise with the technical scope or the evidence behind it.",
    "atribucion_vaga": "Cite the source in the same sentence, or state the fact without a vague subject.",
    "perifrasis": "Use the short form: «because», «to», «can».",
    "copula_evitada": "Prefer «is», «are» or «has» when the longer verb adds no meaning.",
    "calco": "Replace the Spanish-shaped phrase with the English academic form (research group, training, conduct a study, current).",
    "plantilla": "Drop the preamble and open with the substantive claim.",
    "paralelismo_negativo": "State directly what the system does, without the ready-made contrast.",
    "falso_rango": "Check that both ends sit on one scale; if not, list the dimensions separately.",
    "matizacion": "One calibrated hedge is enough: keep the modal the evidence supports and drop the rest.",
    "gerundio_cierre": "Turn the trailing participle into its own clause with a finite verb, or end on the main claim.",
    "raya": "Resolve the aside with commas, a semicolon or parentheses.",
    "oracion_larga": "Split the sentence where the idea changes; over 45 words tire the reviewer.",
    "triada": "Keep the two items that matter, or rank the list in clauses.",
    "conector_repeticion": "Name the logical relation between the sentences and express it with their content; do not swap one connector for another.",
    "conector_densidad": "Remove most opening connectors; keep the one without which the logical relation is lost.",
    "conector_sobreuso": "One connector carries the transitions: rebuild some with a subordinate clause or a subject that points back.",
    "sintesis_repetida": "Do not close several paragraphs with the same summary formula; end on the deliverable or the milestone.",
    "apertura_repetida": "Change how one of the two sentences opens: a phrase, a condition or a figure.",
    "apertura_dominante": "Too many sentences open the same way; vary the subject or the opening phrase.",
    "demostrativo": "Name the referent instead of opening with This/These plus a noun.",
    "causal_densidad": "Many causal clauses in a row: keep the explicit relation only where the reader cannot infer it.",
    "cola_relativa": "Turn the trailing «, which» clause into its own sentence with a concrete subject.",
    "clausula_repetida": "The same subordinate clause recurs in nearby sentences; reorder or merge the ideas.",
    "frase_repetida": "Decide where the phrase belongs and refer back to it briefly afterwards; technical terms stay.",
    "casi_duplicado": "Two sentences say almost the same: keep the better wording and every figure.",
    "sobreuso": "The word weighs far more than the rest of the document's vocabulary; check whether each use adds something or admits a more precise form.",
}

MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
DATE_RE = re.compile(rf"\b(?:\d{{1,2}}\s+)?(?:{MONTHS})(?:\s+\d{{1,2}}(?:st|nd|rd|th)?,?)?(?:\s+\d{{4}})?\b"
                     r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b", re.I)
MONEY_RE = re.compile(r"\\\$\s*\d+(?:[.,]\d+)*(?:\s*(?:million|billion|thousand|millones|mil millones|mil))?", re.I)
TRL_RE = re.compile(r"\bTRL[\s~]*\d(?:\s*(?:,|to|or|and|-|–)\s*\d)*")


def _is_summary(section: str) -> bool:
    name = engine.fold(section.lower())
    return (name.startswith("00_frontmatter") or "resumen" in name or "abstract" in name
            or "summary" in name)


def render_markdown(report: dict) -> str:
    metrics = report["metricas"]
    lines = [f"# Style report: {report['fuente']}", "", f"> {report['aviso']}", ""]
    if report["indice"] is None:
        lines += ["The run has no prose to score yet.", ""]
        return "\n".join(lines)
    lines += [f"- Index: **{report['indice']}** of 100 ({report['veredicto']})",
              f"- Style score: {report['puntaje_estilo']}; flow score: {report['puntaje_flujo']} (0 to 1, lower is better)",
              f"- Words: {metrics['palabras']}; sentences: {metrics['oraciones']}; paragraphs: {metrics['parrafos']}",
              f"- MATTR: {metrics['mattr']}; sentences over {report['umbrales']['oracion_larga_palabras']} words: "
              f"{round(100 * metrics['oraciones_largas_proporcion'])} %",
              f"- Informative only: coefficient of variation of sentence length {metrics['cv_longitud']}", ""]
    if report["secciones"]:
        lines += ["## Sections", "", "| Section | Words | Index | Verdict |", "|---|---:|---:|---|"]
        lines += [f"| {s['seccion']} | {s['palabras']} | {s['indice']} | {s['veredicto']} |" for s in report["secciones"]]
        lines.append("")
    by_category: dict[str, list[dict]] = {}
    for finding in report["hallazgos"]:
        by_category.setdefault(finding["categoria"], []).append(finding)
    lines += ["## Findings", ""]
    limit = 12
    for category, findings in sorted(by_category.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines += [f"### {category} ({len(findings)})", "", findings[0]["orientacion"], ""]
        for f in findings[:limit]:
            places = f.get("ubicaciones") or [f]
            where = "; ".join(f"{p['seccion']} par. {p['parrafo']}, sent. {p['oracion']}" for p in places[:6])
            lines.append(f"- {where}: «{f['fragmento']}»")
        if len(findings) > limit:
            lines.append(f"- {len(findings) - limit} more in `reporte.json`.")
        lines.append("")
    if report["exentos"]:
        lines += [f"## Exempt ({len(report['exentos'])})", ""]
        for e in report["exentos"][:30]:
            lines.append(f"- «{e['termino'][:90]}» ({e['fuente']}, {e['ocurrencias']}): {e['motivo']}")
        lines.append("")
    return "\n".join(lines)


def render_verification(result: dict) -> str:
    if result["fiel"]:
        return f"Facts preserved in {len(result['archivos'])} file(s)."
    lines = ["Facts that had to stay identical changed:"]
    for item in result["archivos"]:
        for d in item["diferencias"]:
            if d["clase"] == "parrafos":
                lines.append(f"- {item['archivo']}: {d['antes']} paragraphs before, {d['despues']} after")
            else:
                lines.append(f"- {item['archivo']}: {d['clase']}; missing {d['faltan']}; added {d['sobran']}")
    return "\n".join(lines)


def _bind() -> None:
    """Swap the engine's language tables for the English ones above."""
    for name in ("AVISO", "ESCALA", "MOTIVOS", "FUNCTION_WORDS", "NOUN_CONTEXT", "STOP", "INSTITUTIONS", "CATALOG",
                 "STYLE_CATEGORIES", "CONNECTORS", "SYNTHESIS_CONNECTORS", "_ALL_CONNECTORS", "CONNECTOR_RE",
                 "DEMONSTRATIVE_RE", "VERBS_AFTER_DEMONSTRATIVE", "CAUSAL_RE", "TAIL_RE", "GERUND_TAIL_RE",
                 "NOT_GERUNDS", "TRIAD_RE", "DASH_RE", "ABBREVIATIONS", "CITE_LABEL", "CONNECTOR_DENSITY_SPAN",
                 "PLACEHOLDER_PREFIXES", "ORIENTACION", "MONTHS", "DATE_RE", "MONEY_RE", "TRL_RE", "_is_summary",
                 "render_markdown", "render_verification"):
        setattr(engine, name, globals()[name])
    engine.MGA_TERMS = PROTECTED_TERMS


_bind()


# --- CLI ----------------------------------------------------------------------

def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def _with_language(report: dict) -> dict:
    """The Spanish schema plus `idioma`, placed after `flujo`."""
    out: dict = {}
    for key, value in report.items():
        out[key] = value
        if key == "flujo":
            out["idioma"] = LANGUAGE
    return out


def command_audit(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root) if args.run_root else None
    file_path = Path(args.docx or args.txt) if (args.docx or args.txt) else None
    if run_root is None and file_path is None:
        return _fail("Give RUN_ROOT, --docx or --txt.")
    if run_root is not None and not run_root.is_dir():
        return _fail(f"The run {run_root} does not exist.")
    if file_path is not None:
        if not file_path.is_file():
            return _fail(f"The file {file_path} does not exist.")
        try:
            sections = engine.read_docx(file_path) if args.docx else engine.read_text_file(file_path)
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
            return _fail(f"{file_path} is not a readable .docx: {error}")
        source = file_path.name
    else:
        sections = engine.run_sections(run_root)
        source = run_root.resolve().name

    only = None
    if args.section:
        only = engine.select_sections(sections, args.section, by_position=file_path is not None)
        if not only:
            return _fail(f"There is no section «{args.section}».")
    flujo = engine.check_run.detect_flujo(run_root) if run_root else "base"
    report = _with_language(engine.audit(sections, engine.build_terms(run_root), flujo, source, only, args.all))
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    markdown = render_markdown(report)
    if run_root is not None:
        folder = run_root / engine.REPORT_DIR
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "reporte.json").write_text(payload, encoding="utf-8")
        (folder / "reporte.md").write_text(markdown, encoding="utf-8")
    print(payload if args.json else markdown, end="")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    before, after = Path(args.before), Path(args.after)
    if not before.exists() or not after.exists():
        return _fail("Both paths to compare are required.")
    if before.is_dir() != after.is_dir():
        return _fail("Compare two files or two folders, not one of each.")
    result = engine.verify(before, after)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_verification(result))
    return 0 if result["fiel"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Readability and redundancy of English prose.")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", aliases=["auditar"], help="Score a run, a .docx or a text file.")
    audit.add_argument("run_root", nargs="?", metavar="RUN_ROOT")
    audit.add_argument("--section", "--seccion", dest="section", metavar="N",
                       help="Number or name of the section, e.g. 3 or tdr05.")
    audit.add_argument("--all", "--todo", dest="all", action="store_true",
                       help="Also search for redundancy across sections.")
    audit.add_argument("--json", action="store_true", help="Print the report as JSON.")
    source = audit.add_mutually_exclusive_group()
    source.add_argument("--docx", metavar="PATH", help="Audit a .docx instead of the run's sections.")
    source.add_argument("--txt", metavar="PATH", help="Audit a plain text file instead of the run's sections.")
    audit.set_defaults(handler=command_audit)
    verify = commands.add_parser("verify", aliases=["verificar"], help="Fail when a rewrite changed a fact.")
    verify.add_argument("before")
    verify.add_argument("after")
    verify.add_argument("--json", action="store_true", help="Print the result as JSON.")
    verify.set_defaults(handler=command_verify)
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
