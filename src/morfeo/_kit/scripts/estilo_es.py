#!/usr/bin/env python3
"""Readability and redundancy report for Spanish proposal prose.

`auditar` scores a run, a .docx or a text file and locates what slows a reader
down: stock phrases, closing gerunds, long sentences, repeated openings and
connectors, repeated phrases and near-duplicate sentences. `verificar` compares
two versions of a text and fails when a fact changed.

    estilo_es.py auditar <RUN_ROOT> [--seccion N] [--todo] [--json]
    estilo_es.py auditar --docx <ruta> | --txt <ruta> [--seccion N] [--todo] [--json]
    estilo_es.py verificar <antes> <despues> [--json]

Without `--todo`, each section is read alone. With it, repeated phrases and
near-duplicates are also searched across sections, and every location is listed.
A run gets `artefactos/estilo/reporte.json` and `reporte.md`. A file on its own
prints the report and writes nothing; adding RUN_ROOT uses that run's protected
terms and writes there.

Scores: `puntaje_estilo` and `puntaje_flujo` run from 0.0 (nothing to revise) to
1.0; `indice` = 100 * (1 - (estilo + flujo) / 2), so higher is better. Counts are
normalized per 1000 words. Thresholds are provisional constants, published in the
report under `umbrales`. A score never fails anything.

Protected terms are built for each run (closed MGA vocabulary, both trees, the
project title, TDR chapter titles, institutions). Each phrase collapses to one
token before n-grams, Jaccard, MATTR and the catalog run, so the literal copies
the SGR guide requires are not penalized; every exemption is logged in `exentos`.

Exit codes: 0 report written, or `verificar` found no change; 1 `verificar` found
a change; 2 invalid input.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import statistics
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree


def _load_check_run():
    """check_run.py owns the prose filter, the citation regex and the section order."""
    path = Path(__file__).resolve().with_name("check_run.py")
    spec = importlib.util.spec_from_file_location("check_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_run = _load_check_run()
fold = check_run._fold

REPORT_DIR = Path("artefactos") / "estilo"
AVISO = ("El índice mide legibilidad y fluidez de la prosa. No dice nada sobre la autoría del texto "
         "ni sobre su valor científico, y sus umbrales son provisionales: orienta la revisión, no la aprueba.")

UMBRALES: dict = {
    "bandas": {"clara": 0.20, "irregular": 0.45},
    "palabras_minimas_normalizacion": 200,
    "mattr_ventana": 200,
    "mattr_piso": 0.45,
    "mattr_techo": 0.65,
    "oracion_larga_palabras": 45,
    "oraciones_largas_piso": 0.05,
    "oraciones_largas_techo": 0.30,
    "ngrama": 5,
    "ngrama_palabras_contenido": 3,
    "ngrama_oraciones": 3,
    "ngrama_parrafos": 2,
    "jaccard": 0.6,
    "jaccard_palabras_minimas": 6,
    "conector_ventana_oraciones": 5,
    "conector_proporcion": 0.25,
    "conector_sobreuso_por_1000": 3.0,
    "sintesis_por_1000": 0.5,
    "apertura_dominante": 0.15,
    "demostrativo_proporcion": 0.15,
    "causal_por_1000": 4.0,
    "cola_relativa_por_1000": 3.0,
    "clausula_ventana_oraciones": 3,
    "triada_por_1000": 3.0,
    "sobreuso_conteo_minimo": 8,
    "sobreuso_veces_mediana": 4.0,
    "sobreuso_tipos_para_mediana": 20,
    "sobreuso_contexto_nominal": 0.4,
    "sobreuso_usos_en_arboles": 2,
    "sobreuso_maximo": 10,
    "saturacion_por_1000": {"catalogo": 15.0, "sobreuso": 2.0, "conectores": 6.0, "aperturas": 6.0,
                            "clausulas": 6.0, "redundancia": 8.0, "plantillas": 5.0},
    "pesos_estilo": {"catalogo": 0.50, "oraciones_largas": 0.30, "mattr": 0.10, "sobreuso": 0.10},
    "pesos_flujo": {"conectores": 0.25, "aperturas": 0.15, "clausulas": 0.15, "redundancia": 0.25,
                    "plantillas": 0.20},
}

# Words that carry no topic. check_run.STOPWORDS holds the long ones it needs for
# tree nodes; this adds the short function words. All folded (no accents).
FUNCTION_WORDS = frozenset("""
    a al algo algun alguna algunas alguno algunos ante antes aqui asi aun cada casi como con cual cuales cuyo
    cuya de del dos e el ella ellas ello ellos en era eran es esa esas ese eso esos esta estan estar este esto
    estos fue fueron ha han hay la las le les lo los mas me muy ni no nos o os otra otro para pero poco por pues
    que se sea sean segun ser si sin sino siempre son su sus tal tambien tan tanto te tiene tienen toda todo tres
    tu u un una unas uno unos ya y
    cuanto dentro fuera luego mientras nunca solo tras varios varias vez veces ademas
    sobre entre desde hasta hacia contra durante donde cuando porque aunque puede pueden mismo misma mismos mismas
    estas otros otras todos todas parte forma
""".split())
# A word usually preceded by one of these behaves as a noun, which here means
# topic vocabulary; tics are verbs, prepositions and adverbs.
NOUN_CONTEXT = frozenset("el la los las un una unos unas del al de este esta estos estas ese esa esos esas su sus cada".split())
STOP = FUNCTION_WORDS | check_run.STOPWORDS

MGA_TERMS = (
    "metodología general ajustada", "sistema general de regalías", "árbol de problemas", "árbol de objetivos",
    "problema central", "causa directa", "causas directas", "causa indirecta", "causas indirectas",
    "efecto directo", "efectos directos", "efecto indirecto", "efectos indirectos", "objetivo general",
    "objetivo específico", "objetivos específicos", "cadena de valor", "marco lógico", "población afectada",
    "población objetivo", "línea base", "situación existente", "situación esperada",
    "descripción de la situación existente", "magnitud del problema", "análisis de participantes",
    "análisis de riesgos", "alternativa de solución", "alternativas de solución", "medio de verificación",
    "medios de verificación", "fuente de verificación", "fuentes de verificación", "indicador de producto",
    "indicadores de producto", "indicador de gestión", "indicadores de gestión", "fuentes de financiación",
    "plan de desarrollo", "plan nacional de desarrollo", "resultado esperado", "resultados esperados",
)
INSTITUTIONS = (
    "Universidad Nacional de Colombia", "Sede Manizales", "Universidad Tecnológica de Pereira",
    "Universidad de Antioquia", "Departamento Nacional de Planeación", "Ministerio de Ciencia, Tecnología e Innovación",
    "MinCiencias", "Sistema Nacional de Ciencia, Tecnología e Innovación", "SNCTeI", "GCPDS", "LabIA",
)

# (category, regex). Seeded from estilo-natural-es, sections 3 and 4.
_CATALOG_SOURCE = (
    ("cliche", r"\bse erigen? como\b"),
    ("cliche", r"\b(?:juegan?|desempeñan?) un (?:papel|rol) (?:\w+ )?(?:fundamental|crucial|clave|vital|central|esencial)\b"),
    ("cliche", r"\bmarcan? un antes y un después\b"),
    ("cliche", r"\bun punto de inflexión\b"),
    ("cliche", r"\bsent(?:ando|ar|ó|a|an) las bases\b"),
    ("cliche", r"\ben el corazón de\b"),
    ("cliche", r"\bhorizonte prometedor\b"),
    ("cliche", r"\bsin duda, un avance\b"),
    ("cliche", r"\b(?:la tecnología|el dato) es (?:el espejo|la moneda)\b"),
    ("comodin", r"\b(?:robust[oa]s?|crucial(?:es)?|fundamental(?:es)?|ecosistemas?|tapiz|entramados?)\b"),
    ("comodin", r"\bun abanico de\b"),
    ("comodin", r"\ben última instancia\b"),
    ("comodin", r"\bde la mano de\b"),
    ("promocional", r"\b(?:vibrantes?|revolucionari[oa]s?|impresionantes?)\b"),
    ("promocional", r"\b(?:de vanguardia|rico patrimonio|profundo impacto)\b"),
    ("atribucion_vaga", r"\bdiversos expertos\b"),
    ("atribucion_vaga", r"\bestudios recientes (?:señalan|muestran|indican|sugieren|demuestran)\b"),
    ("atribucion_vaga", r"\bla literatura (?:sugiere|señala|indica|muestra)\b"),
    ("perifrasis", r"\bcon el fin de lograr este propósito\b"),
    ("perifrasis", r"\bdebido al hecho de que\b"),
    ("perifrasis", r"\btienen? la capacidad de\b"),
    ("copula_evitada", r"\bse posicionan? como\b"),
    ("copula_evitada", r"\b(?:constituyen?|albergan?|cuentan? con)\b"),
    ("calco", r"\bhacer sentido\b"),
    ("calco", r"\beventualmente\b"),
    ("calco", r"\bremo(?:ver|viendo|vió|vido)\b"),
    ("calco", r"\bconsistentes? con\b"),
    ("calco", r"\baplicar a (?:una |la |esta )?convocatoria\b"),
    ("calco", r"\ben orden de\b"),
    ("calco", r"\bdramátic(?:o|a|os|as|amente)\b"),
    ("plantilla", r"\bcabe (?:destacar|mencionar|señalar|resaltar)(?: que)?\b"),
    ("plantilla", r"\bes (?:importante|fundamental|necesario) (?:destacar|mencionar|señalar|comprender|resaltar) que\b"),
    ("plantilla", r"\b(?:en el mundo actual|en la era digital|hoy en día)\b"),
    ("plantilla", r"\ba continuación (?:se (?:presenta|describe|procede)|presento)\b"),
    ("plantilla", r"\ben esta sección (?:se |procederemos)"),
    ("plantilla", r"\b(?:la verdad es que|siendo honestos|a decir verdad)\b"),
    ("plantilla", r"\b(?:la verdadera pregunta es|lo que de verdad importa)\b"),
    ("plantilla", r"\bespero que esta sección\b"),
    ("plantilla", r"\bpor supuesto\b"),
    ("paralelismo_negativo", r"\bno solo\b[^.;]{1,120}?\bsino\b"),
    ("paralelismo_negativo", r"\bno se trata de\b[^.;]{1,120}?\bsino\b"),
    ("falso_rango", r"\bdesde\b(?![^.;]{0,8}\d)[^.;\d]{3,80}?\bhasta\b(?!\s+\S*\d)"),
)
CATALOG = tuple((category, re.compile(pattern, re.I)) for category, pattern in _CATALOG_SOURCE)
TEMPLATE_CATEGORIES = frozenset({"plantilla", "paralelismo_negativo", "falso_rango"})
STYLE_CATEGORIES = frozenset({"cliche", "comodin", "promocional", "atribucion_vaga", "perifrasis",
                              "copula_evitada", "calco", "triada", "raya"})
CONNECTOR_CATEGORIES = frozenset({"conector_repeticion", "conector_densidad", "conector_sobreuso", "sintesis_repetida"})
OPENING_CATEGORIES = frozenset({"apertura_repetida", "apertura_dominante", "demostrativo"})
CLAUSE_CATEGORIES = frozenset({"causal_densidad", "cola_relativa", "clausula_repetida", "gerundio_cierre"})
REDUNDANCY_CATEGORIES = frozenset({"frase_repetida", "casi_duplicado"})

# Folded, longest first where one contains another.
CONNECTORS = (
    "por consiguiente", "en este sentido", "en tal sentido", "de igual manera", "de igual forma", "de ahi que",
    "por otro lado", "por otra parte", "por una parte", "en primer lugar", "en segundo lugar", "en tercer lugar",
    "sin embargo", "no obstante", "por lo tanto", "por tanto", "por ende", "en consecuencia", "de este modo",
    "de esta manera", "de esta forma", "con todo", "ahora bien", "en concreto", "a su vez", "en contraposicion",
    "asi las cosas", "en efecto", "asimismo", "adicionalmente", "ademas", "finalmente",
)
SYNTHESIS_CONNECTORS = ("en resumen", "en sintesis", "en conclusion", "en suma", "en definitiva", "en conjunto")
_ALL_CONNECTORS = tuple(sorted(CONNECTORS + SYNTHESIS_CONNECTORS, key=len, reverse=True))
CONNECTOR_RE = re.compile(r"(" + "|".join(_ALL_CONNECTORS) + r")\b")
DEMONSTRATIVE_RE = re.compile(r"(?:Este|Esta|Estos|Estas|Dicho|Dicha|Dichos|Dichas)\s+([^\W\d_]+)")
VERBS_AFTER_DEMONSTRATIVE = frozenset({"es", "son", "fue", "fueron", "será", "serán", "ha", "han", "tiene", "tienen"})
CAUSAL_RE = re.compile(r"\b(?:porque|ya que|puesto que)\b", re.I)
TAIL_RE = re.compile(r",\s+lo (?:cual|que)\b", re.I)
GERUND_TAIL_RE = re.compile(r",\s+([^\W\d_]+(?:ando|iendo|yendo))\b[^,;:]*[.!?]?\s*$", re.I)
NOT_GERUNDS = frozenset({"cuando", "comando", "mando", "bando", "contrabando", "demando", "estruendo", "aprendo",
                         "entiendo", "comprendo", "vendo", "ando", "doctorando", "graduando", "educando"})
TRIAD_RE = re.compile(r"(?<!, )\b([^\W\d_]{4,}), ([^\W\d_]{4,}) [ye] ([^\W\d_]{4,})\b")
DASH_RE = re.compile(r"\s—\s|\s-{2,3}\s|(?<=[^\W\d_])-{2,3}(?=[^\W\d_])")

TOKEN_RE = re.compile(r"⟦[^⟧]*⟧|\d+(?:[.,]\d+)*|[^\W\d_]+(?:[-'’][^\W\d_]+)*")
CITE_TOKEN = "⟦c⟧"
PLACEHOLDER_RE = re.compile(r"⟦(\d+)⟧")
CITE_MARK = "\ue001"
DOLLAR = "\ue000"

ABBREVIATIONS = frozenset({
    "p", "pp", "ej", "fig", "figs", "tab", "núm", "num", "vol", "ed", "eds", "cap", "caps", "sec", "dr", "dra",
    "sr", "sra", "srta", "prof", "ing", "lic", "art", "inc", "aprox", "máx", "mín", "cf", "vs", "ca", "ltda",
    "dpto", "av", "cra", "mg", "phd", "e.g", "i.e", "s.a", "et",
})
SENTENCE_END_RE = re.compile(r"[.!?…]+[\"»”)\]\ue001]*\s+")
OPENING_PUNCTUATION = "¿¡«\"“([" + CITE_MARK

SECTION_COMMANDS = ("part", "chapter", "section", "subsection", "subsubsection", "paragraph", "subparagraph")
DROPPED_COMMANDS = (
    "label", "ref", "cref", "Cref", "pageref", "eqref", "autoref", "nameref", "includegraphics", "input", "include",
    "vspace", "hspace", "setlength", "addtolength", "setcounter", "addtocounter", "bibliography",
    "bibliographystyle", "newcommand", "renewcommand", "DiagramaSiExiste", "SeccionSiExiste", "rowcolor",
    "cellcolor", "color", "pagestyle", "thispagestyle", "captionsetup", "hypersetup", "addcontentsline",
    "bibsection", "fontsize", "linespread", "url", "href",
)
LAYOUT_ENV_RE = re.compile(r"\\begin\{(?:tabular\w*|xltabular|longtable|minipage|wrapfigure)\*?\}")

ORIENTACION = {
    "cliche": "Cambia la fórmula por lo que el proyecto hace: un verbo directo con su objeto y, si existe, su cifra.",
    "comodin": "Conserva el adjetivo solo si dice algo medible; si no, nombra la propiedad concreta.",
    "promocional": "Sustituye el elogio por el alcance técnico o la evidencia que lo sostiene.",
    "atribucion_vaga": "Cita la fuente en la misma oración o afirma el hecho sin atribuirlo a un sujeto vago.",
    "perifrasis": "Usa la forma corta: «dado que», «para», «puede».",
    "copula_evitada": "Prefiere «es», «son» o «tiene» cuando la perífrasis no agrega significado.",
    "calco": "Reemplaza el calco del inglés por la forma propia del español académico.",
    "plantilla": "Quita el preámbulo y arranca con la afirmación sustantiva.",
    "paralelismo_negativo": "Afirma de manera directa lo que el sistema hace, sin el contraste prefabricado.",
    "falso_rango": "Comprueba que los extremos estén en una misma escala; si no, enumera las dimensiones por separado.",
    "gerundio_cierre": "Convierte el gerundio final en una oración con verbo conjugado o termina en el aserto principal.",
    "raya": "Resuelve el inciso con comas, punto y coma o paréntesis.",
    "oracion_larga": "Divide la oración en el punto donde cambia la idea; más de 45 palabras cansan al evaluador.",
    "triada": "Deja los dos elementos que importan o jerarquiza la enumeración en cláusulas.",
    "conector_repeticion": "Nombra la relación lógica entre las oraciones y exprésala con su contenido; no cambies un conector por otro.",
    "conector_densidad": "Quita la mayoría de los conectores de arranque; conserva el que evita perder la relación lógica.",
    "conector_sobreuso": "Un solo conector carga las transiciones: reconstruye algunas con una subordinada o un sujeto que retome lo anterior.",
    "sintesis_repetida": "Evita cerrar varios párrafos con la misma fórmula de síntesis; termina en el entregable o el hito.",
    "apertura_repetida": "Cambia el arranque de una de las dos oraciones: un complemento, una condición o una cifra.",
    "apertura_dominante": "Demasiadas oraciones abren igual; varía el sujeto o el complemento inicial.",
    "demostrativo": "Nombra el referente en lugar de abrir con un demostrativo más sustantivo.",
    "causal_densidad": "Hay muchas causales juntas: deja la relación explícita solo donde el lector no la infiere.",
    "cola_relativa": "Convierte la cola «, lo cual» en una oración propia con sujeto concreto.",
    "clausula_repetida": "La misma subordinada se repite en oraciones vecinas; reorganiza el orden o fusiona las ideas.",
    "frase_repetida": "Decide en qué lugar va la frase y retómala después con una mención breve; los términos técnicos se conservan.",
    "casi_duplicado": "Dos oraciones dicen casi lo mismo: unifica la mejor formulación y conserva todos los datos.",
    "sobreuso": "La palabra pesa mucho más que el resto del léxico del documento; revisa si cada uso aporta o admite una forma más precisa.",
}


# --- Text model ---------------------------------------------------------------

@dataclass
class Paragraph:
    text: str
    listed: bool = False


@dataclass
class Section:
    name: str
    paragraphs: list[Paragraph]


@dataclass
class Sentence:
    section: str
    paragraph: int
    index: int
    text: str
    collapsed: str
    words: list[str]
    cited: bool
    listed: bool
    terms: list[int]


@dataclass
class Term:
    words: tuple[str, ...]
    label: str
    source: str


@dataclass
class Exemptions:
    """Exemptions grouped by what was exempted, for the `exentos` field."""
    entries: dict = field(default_factory=dict)

    def log(self, term: str, source: str, reason: str, sections, count: int = 1) -> None:
        entry = self.entries.setdefault((term, source, reason), {"ocurrencias": 0, "secciones": set()})
        entry["ocurrencias"] += count
        entry["secciones"].update(sections)

    def rows(self) -> list[dict]:
        rows = [{"termino": term, "fuente": source, "motivo": reason, "ocurrencias": data["ocurrencias"],
                 "secciones": sorted(data["secciones"])}
                for (term, source, reason), data in self.entries.items()]
        return sorted(rows, key=lambda r: (r["fuente"], r["termino"]))


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def _is_abbreviation(text: str, dot: int) -> bool:
    if text[dot] != ".":
        return False
    match = re.search(r"([^\W\d_]+(?:\.[^\W\d_]+)*)$", text[:dot])
    if not match:
        return False
    word = match.group(1)
    if len(word) == 1 and word.isupper():
        return True
    if word.lower() == "al":
        return text[:match.start()].rstrip().lower().endswith("et")
    return word.lower() in ABBREVIATIONS


def split_sentences(text: str) -> list[str]:
    sentences, start = [], 0
    for match in SENTENCE_END_RE.finditer(text):
        position = match.end()
        while position < len(text) and text[position] in OPENING_PUNCTUATION:
            position += 1
        if position >= len(text):
            continue
        following = text[position]
        opens = following.isupper() or following.isdigit() or following == "⟦" or text[match.end()] in "¿¡"
        if opens and not _is_abbreviation(text, match.start()):
            sentences.append(text[start:match.end()].strip())
            start = match.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def mattr(words: list[str], window: int) -> float | None:
    """Mean type-token ratio over sliding windows; None below one full window."""
    if len(words) < window:
        return None
    counts = Counter(words[:window])
    total = len(counts)
    windows = 1
    for i in range(window, len(words)):
        counts[words[i]] += 1
        counts[words[i - window]] -= 1
        if counts[words[i - window]] == 0:
            del counts[words[i - window]]
        total += len(counts)
        windows += 1
    return total / (windows * window)


# --- LaTeX --------------------------------------------------------------------

def _group_end(text: str, position: int) -> int:
    """Index just after the [..] or {..} group that opens at `position`."""
    opening = text[position]
    closing = "]" if opening == "[" else "}"
    depth, i = 0, position
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _skip_groups(text: str, position: int) -> int:
    """Index just after the [..] and {..} groups that start at `position`."""
    while position < len(text) and text[position] in "[{":
        position = _group_end(text, position)
    return position


def _drop_commands(text: str, names, replacement: str = " ") -> str:
    pattern = re.compile(r"\\(?:" + "|".join(names) + r")\*?(?![a-zA-Z])")
    out, position = [], 0
    for match in pattern.finditer(text):
        if match.start() < position:
            continue
        out.append(text[position:match.start()])
        out.append(replacement)
        position = _skip_groups(text, match.end())
    out.append(text[position:])
    return "".join(out)


def _unwrap_caption(text: str) -> str:
    out, position = [], 0
    for match in re.finditer(r"\\caption\*?", text):
        if match.start() < position:
            continue
        out.append(text[position:match.start()])
        start = match.end()
        if text[start:start + 1] == "[":
            start = _group_end(text, start)
        if text[start:start + 1] != "{":
            position = start
            continue
        end = _group_end(text, start)
        out.append("\n\n" + text[start + 1:end - 1] + "\n\n")
        position = end
    out.append(text[position:])
    return "".join(out)


def _strip_inline(text: str) -> str:
    def citation(match: re.Match) -> str:
        return (CITE_TOKEN if match.group(1) in ("citet", "citealt", "citeauthor") else "") + CITE_MARK

    text = check_run.CITE_RE.sub(citation, text)
    text = _drop_commands(text, DROPPED_COMMANDS)
    text = re.sub(r"\\(?:begin|end)\{[^}]*\}(?:\[[^\]]*\])?", "\n\n", text)
    text = re.sub(r"\\([%&_#])", r"\1", text)
    text = re.sub(r"\\[,;:! ]|\\\\(?:\[[^\]]*\])?", " ", text).replace("~", " ")
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    text = text.replace("{", "").replace("}", "").replace("``", '"').replace("''", '"')
    return text.replace(DOLLAR, "$")


def latex_paragraphs(tex: str) -> list[Paragraph]:
    """Narrative paragraphs of a section: check_run.prose_lines, then the markup goes and its text stays."""
    source = tex.replace(r"\$", DOLLAR)
    raw = source.splitlines()
    lines, last = [], 0
    for number, line in check_run.prose_lines(source):
        if raw[number - 1].lstrip().startswith("%"):
            last = number
            continue
        if number != last + 1:
            lines.append("")
        lines.append(line)
        last = number
    text = "\n".join(lines)
    text = _drop_commands(text, SECTION_COMMANDS, "\n\n")
    text = _unwrap_caption(text)
    text = re.sub(r"\\item(?:\[[^\]]*\])?", "\n\n\ue002", text)
    text = _strip_inline(text)
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        listed = "\ue002" in block
        clean = re.sub(r"\s+", " ", block.replace("\ue002", " ")).strip()
        clean = re.sub(r"\s+(\ue001*[.,;:])", r"\1", clean)
        if TOKEN_RE.search(clean.replace(CITE_TOKEN, "")):
            paragraphs.append(Paragraph(clean, listed))
    return paragraphs


# --- Sources ------------------------------------------------------------------

def run_sections(run_root: Path) -> list[Section]:
    folder = run_root / "redaccion" / "sections"
    if not folder.is_dir():
        return []
    present = {p.stem for p in folder.glob("*.tex")
               if not p.stem.startswith(("diag_", "01_titulo"))}
    ordered: list[str] = []
    for chapter in _tdr_chapters(run_root):
        ordered += [n for n in chapter.get("archivos") or [] if isinstance(n, str)]
    ordered += list(check_run.CANONICAL_SECTIONS) + list(check_run.SGR_SECTIONS) + sorted(present)
    names = [n for n in dict.fromkeys(ordered) if n in present]
    sections = []
    for name in names:
        text = (folder / f"{name}.tex").read_text(encoding="utf-8", errors="replace")
        sections.append(Section(name, latex_paragraphs(text)))
    return sections


def plain_sections(blocks: list[tuple[int | None, str]]) -> list[Section]:
    """Sections from (heading level or None, text) blocks: the top heading level
    opens a section, deeper headings only end a paragraph. Without a heading style,
    numbering or a short line in capitals stands in for it."""
    marked = [(level if level is not None else _guess_heading(text), text) for level, text in blocks]
    levels = [level for level, _ in marked if level is not None]
    top = min(levels) if levels else None
    sections: list[Section] = []
    for level, text in marked:
        if level is None:
            if not sections:
                sections.append(Section("documento" if top is None else "preliminar", []))
            sections[-1].paragraphs.append(Paragraph(text))
        elif level == top:
            sections.append(Section(text.strip("# ")[:80], []))
    return sections


def _guess_heading(text: str) -> int | None:
    words = text.split()
    if len(words) > 12 or text.rstrip().endswith((".", ":", ";", ",")):
        return None
    numbered = re.match(r"(\d+(?:\.\d+)*)\.?\s+\S", text)
    if numbered:
        return numbered.group(1).count(".") + 1
    if len(words) >= 1 and text.isupper() and any(c.isalpha() for c in text):
        return 1
    return None


def read_text_file(path: Path) -> list[Section]:
    blocks: list[tuple[int | None, str]] = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8", errors="replace")):
        text = re.sub(r"\s+", " ", block).strip()
        if not text:
            continue
        hashes = re.match(r"(#{1,6})\s", text)
        blocks.append((len(hashes.group(1)) if hashes else None, text))
    return plain_sections(blocks)


W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HEADING_STYLE_RE = re.compile(r"(?:heading|t[ií]?tulo|ttulo)\s*(\d)", re.I)
MARKER_RE = re.compile(r"\[\s*[xX]?\s*\]")


def _is_grey(color: str) -> bool:
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", color or ""):
        return False
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return max(r, g, b) - min(r, g, b) <= 12 and 0x60 <= r <= 0xE0


def _run_is_placeholder(run) -> bool:
    props = run.find(f"{W_NS}rPr")
    if props is None:
        return False
    color = props.find(f"{W_NS}color")
    style = props.find(f"{W_NS}rStyle")
    return ((color is not None and _is_grey(color.get(f"{W_NS}val", "")))
            or (style is not None and "placeholder" in style.get(f"{W_NS}val", "").lower()))


def _docx_paragraph(node) -> tuple[int | None, str]:
    level = None
    props = node.find(f"{W_NS}pPr")
    if props is not None and props.find(f"{W_NS}pStyle") is not None:
        match = HEADING_STYLE_RE.search(props.find(f"{W_NS}pStyle").get(f"{W_NS}val", ""))
        level = int(match.group(1)) if match else None
    parts = []
    for run in node.iter(f"{W_NS}r"):
        if not _run_is_placeholder(run):
            parts += [t.text or "" for t in run.iter(f"{W_NS}t")]
    return level, re.sub(r"\s+", " ", MARKER_RE.sub(" ", "".join(parts))).strip()


def read_docx(path: Path) -> list[Section]:
    """Body paragraphs only: tables, grey template text and `[ ]` markers stay out."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{W_NS}body")
    blocks = []
    for child in list(body) if body is not None else []:
        nodes = [child] if child.tag == f"{W_NS}p" else []
        if child.tag == f"{W_NS}sdt":
            content = child.find(f"{W_NS}sdtContent")
            nodes = list(content.findall(f"{W_NS}p")) if content is not None else []
        for node in nodes:
            level, text = _docx_paragraph(node)
            if text:
                blocks.append((level, text))
    return plain_sections(blocks)


# --- Protected terms ----------------------------------------------------------

def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def _tdr_chapters(run_root: Path) -> list[dict]:
    data = _read_json(run_root / "artefactos" / "estructura_tdr.json")
    chapters = data.get("capitulos") if isinstance(data, dict) else None
    return [c for c in chapters if isinstance(c, dict)] if isinstance(chapters, list) else []


def _tree_strings(value):
    """Node texts of a tree: the `text`, `title` and `objective` values at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("text", "title", "objective") and isinstance(item, str):
                yield item
            else:
                yield from _tree_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _tree_strings(item)


def _command_value(text: str, name: str) -> str | None:
    match = re.search(r"\\newcommand\{\\" + name + r"\}\{", text)
    if not match:
        return None
    return text[match.end():_group_end(text, match.end() - 1) - 1]


def build_terms(run_root: Path | None) -> list[Term]:
    found: dict[tuple[str, ...], Term] = {}

    def add(label: str, source: str, minimum: int = 1) -> None:
        label = label.strip().rstrip(".")
        words = tuple(fold(w) for w in tokenize(label))
        if len(label.split()) >= minimum and words not in found:
            found[words] = Term(words, label, source)

    for term in MGA_TERMS:
        add(term, "vocabulario_mga")
    for name in INSTITUTIONS:
        add(name, "institucion")
    if run_root is None:
        return list(found.values())

    for relative, source in ((check_run.OBJECTIVES_FILE, "arbol_objetivos"), (check_run.PROBLEM_SPEC, "arbol_problemas")):
        for text in _tree_strings(_read_json(run_root / relative)):
            add(check_run._node_body(text), source, minimum=2)
    for chapter in _tdr_chapters(run_root):
        if isinstance(chapter.get("titulo"), str):
            add(check_run.normalize_tree_text(chapter["titulo"]), "estructura_tdr", minimum=2)
    for relative in ("datos_proyecto.tex", "main.tex"):
        path = run_root / "redaccion" / relative
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        title = _command_value(text, "TituloProyecto")
        if title and not title.startswith("[Por definir"):
            add(check_run.normalize_tree_text(title), "titulo", minimum=2)
        affiliation = _command_value(text, "AfiliacionProyecto")
        if affiliation and not affiliation.startswith("[Por definir"):
            add(check_run.normalize_tree_text(affiliation), "institucion", minimum=2)
    return list(found.values())


class Collapser:
    """Replaces each protected phrase with one placeholder token, longest phrase first."""

    def __init__(self, terms: list[Term], flujo: str, log: Exemptions) -> None:
        self.terms = terms
        self.flujo = flujo
        self.log = log
        self.by_first: dict[str, list[int]] = {}
        for i, term in enumerate(terms):
            self.by_first.setdefault(term.words[0], []).append(i)
        for candidates in self.by_first.values():
            candidates.sort(key=lambda i: -len(terms[i].words))

    def reason(self, term: Term) -> str:
        if term.source.startswith("arbol_") and self.flujo == "sgr":
            return "copia literal del árbol exigida por la guía SGR (§3, §6 y §7)"
        return "término protegido de la corrida"

    def collapse(self, text: str) -> tuple[str, list[int]]:
        matches = list(TOKEN_RE.finditer(text))
        folded = [fold(m.group(0).lower()) for m in matches]
        out, position, i, hits = [], 0, 0, []
        while i < len(matches):
            hit = None
            for index in self.by_first.get(folded[i], ()):
                words = self.terms[index].words
                if tuple(folded[i:i + len(words)]) == words:
                    hit = index
                    break
            if hit is None:
                i += 1
                continue
            term = self.terms[hit]
            out.append(text[position:matches[i].start()])
            out.append(f"⟦{hit}⟧")
            position = matches[i + len(term.words) - 1].end()
            i += len(term.words)
            hits.append(hit)
        out.append(text[position:])
        return "".join(out), hits

    def log_terms(self, sentences: list[Sentence]) -> None:
        for sentence in sentences:
            for index in sentence.terms:
                term = self.terms[index]
                self.log.log(term.label, term.source, self.reason(term), [sentence.section])

    def restore(self, text: str) -> str:
        text = PLACEHOLDER_RE.sub(lambda m: self.terms[int(m.group(1))].label, text)
        return text.replace(CITE_TOKEN, "(cita)").replace(CITE_MARK, "")


def build_sentences(sections: list[Section], collapser: Collapser) -> list[Sentence]:
    sentences = []
    for section in sections:
        index = 0
        for number, paragraph in enumerate(section.paragraphs, start=1):
            for text in split_sentences(paragraph.text):
                collapsed, terms = collapser.collapse(text)
                words = tokenize(collapsed)
                if not words:
                    continue
                index += 1
                sentences.append(Sentence(section.name, number, index, collapser.restore(text), collapsed, words,
                                          CITE_MARK in text, paragraph.listed, terms))
    return sentences


# --- Findings -----------------------------------------------------------------

def _per_1000(count: float, words: int) -> float:
    return 1000.0 * count / max(words, UMBRALES["palabras_minimas_normalizacion"])


def _finding(category: str, sentence: Sentence, span: str, **extra) -> dict:
    return {"seccion": sentence.section, "parrafo": sentence.paragraph, "oracion": sentence.index,
            "categoria": category, "fragmento": span, "orientacion": ORIENTACION[category], **extra}


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def _is_content(word: str) -> bool:
    return not word.startswith("⟦") and not word[0].isdigit() and fold(word) not in STOP


def catalog_findings(sentences: list[Sentence], collapser: Collapser) -> list[dict]:
    th = UMBRALES
    findings = []
    words = sum(len(s.words) for s in sentences)
    triads = []
    for s in sentences:
        taken: list[tuple[int, int]] = []
        for category, regex in CATALOG:
            if category == "atribucion_vaga" and s.cited:
                continue
            for match in regex.finditer(s.collapsed):
                if any(a < match.end() and match.start() < b for a, b in taken):
                    continue
                taken.append(match.span())
                findings.append(_finding(category, s, collapser.restore(match.group(0))))
        tail = GERUND_TAIL_RE.search(s.collapsed)
        if tail and tail.group(1).lower() not in NOT_GERUNDS:
            findings.append(_finding("gerundio_cierre", s, collapser.restore(tail.group(0).strip(" ,."))))
        for match in DASH_RE.finditer(s.collapsed):
            findings.append(_finding("raya", s, collapser.restore(s.collapsed[max(0, match.start() - 20):match.end() + 20])))
        if len(s.words) > th["oracion_larga_palabras"]:
            findings.append(_finding("oracion_larga", s, s.text[:160], palabras=len(s.words)))
        if not s.listed:
            for match in TRIAD_RE.finditer(s.collapsed):
                if not {fold(g.lower()) for g in match.groups()} & STOP:
                    triads.append((s, match.group(0)))
    if len(triads) >= 2 and _per_1000(len(triads), words) > th["triada_por_1000"]:
        findings += [_finding("triada", s, span) for s, span in triads]
    return findings


def _opening_connector(sentence: Sentence) -> str | None:
    match = CONNECTOR_RE.match(fold(sentence.collapsed.lstrip("¿¡«\"(").lower()))
    return match.group(1) if match else None


def flow_findings(sentences: list[Sentence], collapser: Collapser) -> list[dict]:
    """Connector, opening and clause patterns of one section (windows never cross sections)."""
    th = UMBRALES
    prose = [s for s in sentences if not s.listed]
    words = sum(len(s.words) for s in sentences)
    n = len(prose)
    findings: list[dict] = []

    openers = [(s, _opening_connector(s)) for s in prose]
    counts: Counter = Counter()
    last_seen: dict[str, int] = {}
    for position, (s, connector) in enumerate(openers):
        if not connector:
            continue
        counts[connector] += 1
        previous = last_seen.get(connector)
        if previous is not None and position - previous < th["conector_ventana_oraciones"]:
            findings.append(_finding("conector_repeticion", s, connector, oracion_previa=prose[previous].index))
        last_seen[connector] = position
    opened = sum(counts.values())
    if n >= 4 and opened / n > th["conector_proporcion"]:
        findings.append(_finding("conector_densidad", prose[0], f"{opened} de {n} oraciones abren con un conector"))
    for connector, count in sorted(counts.items()):
        if count >= 3 and _per_1000(count, words) > th["conector_sobreuso_por_1000"]:
            first = next(s for s, c in openers if c == connector)
            findings.append(_finding("conector_sobreuso", first, connector, conteo=count))
    synthesis = [(s, c) for s, c in openers if c in SYNTHESIS_CONNECTORS]
    if len(synthesis) >= 2 and (words < 1000 or _per_1000(len(synthesis), words) > th["sintesis_por_1000"]):
        findings += [_finding("sintesis_repetida", s, c, conteo=len(synthesis)) for s, c in synthesis[1:]]

    def opening(s: Sentence) -> str | None:
        head = s.words[:2]
        return " ".join(head) if len(head) == 2 and not any(w.startswith("⟦") for w in head) else None

    bigrams = [opening(s) for s in prose]
    for i in range(1, n):
        if bigrams[i] and bigrams[i] == bigrams[i - 1]:
            findings.append(_finding("apertura_repetida", prose[i], bigrams[i], oracion_previa=prose[i - 1].index))
    for bigram, count in sorted(Counter(b for b in bigrams if b).items()):
        if n >= 6 and count >= 3 and count / n > th["apertura_dominante"]:
            findings.append(_finding("apertura_dominante", prose[bigrams.index(bigram)], bigram, conteo=count))
    demonstratives = []
    for s in prose:
        match = DEMONSTRATIVE_RE.match(s.collapsed)
        if match and match.group(1).lower() not in VERBS_AFTER_DEMONSTRATIVE:
            demonstratives.append((s, match.group(0)))
    if n >= 4 and len(demonstratives) >= 3 and len(demonstratives) / n > th["demostrativo_proporcion"]:
        findings += [_finding("demostrativo", s, span, conteo=len(demonstratives)) for s, span in demonstratives]

    for regex, category, limit in ((CAUSAL_RE, "causal_densidad", th["causal_por_1000"]),
                                   (TAIL_RE, "cola_relativa", th["cola_relativa_por_1000"])):
        hits = [(position, s, m.group(0).strip(", ")) for position, s in enumerate(prose)
                for m in regex.finditer(s.collapsed)]
        if len(hits) >= 2 and _per_1000(len(hits), words) > limit:
            seen = set()
            for _, s, span in hits:
                if s.index not in seen:
                    seen.add(s.index)
                    findings.append(_finding(category, s, span))
        for (before, previous, _), (position, s, span) in zip(hits, hits[1:]):
            if 0 < position - before < th["clausula_ventana_oraciones"]:
                findings.append(_finding("clausula_repetida", s, span, oracion_previa=previous.index))
    return findings


def _is_summary(section: str) -> bool:
    name = fold(section.lower())
    return name.startswith("00_frontmatter") or "resumen" in name


def _location(s: Sentence) -> dict:
    return {"seccion": s.section, "parrafo": s.paragraph, "oracion": s.index}


def redundancy_findings(sentences: list[Sentence], collapser: Collapser, log: Exemptions) -> list[dict]:
    """Repeated phrases and near-duplicates inside `sentences`. A summary may repeat
    the body it condenses, so that pairing alone never produces a finding."""
    th = UMBRALES
    size = th["ngrama"]
    grams: dict[tuple[str, ...], list[tuple[int, int]]] = {}
    for i, s in enumerate(sentences):
        for start in range(len(s.words) - size + 1):
            gram = tuple(s.words[start:start + size])
            if sum(1 for w in gram if _is_content(w)) >= th["ngrama_palabras_contenido"]:
                grams.setdefault(gram, []).append((i, start))
    paragraphs_total = len({(s.section, s.paragraph) for s in sentences})
    minimum_paragraphs = th["ngrama_parrafos"] if paragraphs_total >= 2 else 1

    def qualifies(hits) -> bool:
        return (len({i for i, _ in hits}) >= th["ngrama_oraciones"]
                and len({(sentences[i].section, sentences[i].paragraph) for i, _ in hits}) >= minimum_paragraphs)

    covered: dict[int, set[int]] = {}
    for gram, hits in grams.items():
        if not qualifies(hits):
            continue
        body = [h for h in hits if not _is_summary(sentences[h[0]].section)] or hits
        if not qualifies(body):
            log.log(collapser.restore(" ".join(gram)), "resumen", "el resumen retoma el cuerpo del documento",
                    {sentences[i].section for i, _ in hits}, len(hits))
            continue
        for i, start in hits:
            covered.setdefault(i, set()).update(range(start, start + size))

    phrases: dict[tuple[str, ...], list[int]] = {}
    for i, positions in covered.items():
        ordered = sorted(positions)
        begin = previous = ordered[0]
        for position in ordered[1:] + [None]:
            if position is not None and position == previous + 1:
                previous = position
                continue
            phrases.setdefault(tuple(sentences[i].words[begin:previous + 1]), []).append(i)
            if position is not None:
                begin = previous = position
    findings: list[dict] = []
    reported: list[tuple[str, set[int]]] = []
    for phrase, hits in sorted(phrases.items(), key=lambda kv: (-len(kv[0]), kv[0])):
        text = " ".join(phrase)
        if any(text in longer and set(hits) <= where for longer, where in reported):
            continue
        reported.append((text, set(hits)))
        ordered = sorted(set(hits))
        findings.append(_finding("frase_repetida", sentences[ordered[0]], collapser.restore(text),
                                 conteo=len(ordered), ubicaciones=[_location(sentences[i]) for i in ordered]))

    content = [frozenset(fold(w) for w in s.words if _is_content(w)) for s in sentences]
    least = th["jaccard_palabras_minimas"]
    limit = th["jaccard"]
    for i, one in enumerate(content):
        if len(one) < least:
            continue
        for j in range(i + 1, len(content)):
            two = content[j]
            if len(two) < least or min(len(one), len(two)) < limit * max(len(one), len(two)):
                continue
            score = len(one & two) / len(one | two)
            if score < limit:
                continue
            a, b = sentences[i], sentences[j]
            if _is_summary(a.section) != _is_summary(b.section):
                log.log(a.text[:120], "resumen", "el resumen retoma el cuerpo del documento", [a.section, b.section])
                continue
            findings.append(_finding("casi_duplicado", b, b.text[:160], jaccard=round(score, 2),
                                     ubicaciones=[_location(a), _location(b)]))
    return findings


def domain_words(terms: list[Term]) -> set[str]:
    """Topic vocabulary of the run: what its title says, or its trees say more than once."""
    uses = Counter(w for t in terms if t.source.startswith("arbol_") for w in t.words)
    title = {w for t in terms if t.source == "titulo" for w in t.words}
    return title | {w for w, n in uses.items() if n >= UMBRALES["sobreuso_usos_en_arboles"]}


def overuse_findings(sentences: list[Sentence], domain: set[str], log: Exemptions) -> list[dict]:
    """Words far above the document's own vocabulary, most used first. A word that
    mostly follows an article or `de` is topic vocabulary, like the words of the trees
    and the title, and stays out; protected phrases are already collapsed, so literal
    copies feed no count."""
    th = UMBRALES
    total = sum(len(s.words) for s in sentences)
    counts: Counter = Counter()
    nominal: Counter = Counter()
    for s in sentences:
        for previous, word in zip([""] + s.words, s.words):
            if len(word) >= 5 and word[0].isalpha() and fold(word) not in FUNCTION_WORDS:
                counts[word] += 1
                nominal[word] += previous in NOUN_CONTEXT
    repeated = [c for c in counts.values() if c >= 2]
    baseline = statistics.median(repeated) if len(repeated) >= th["sobreuso_tipos_para_mediana"] else 1
    limit = max(th["sobreuso_conteo_minimo"], th["sobreuso_veces_mediana"] * baseline)
    findings = []
    for word, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if count < limit or nominal[word] / count >= th["sobreuso_contexto_nominal"]:
            continue
        by_section = Counter(s.section for s in sentences for w in s.words if w == word)
        if fold(word) in domain:
            log.log(word, "dominio", "vocabulario del título o de los árboles de la corrida", by_section, count)
            continue
        if len(findings) == th["sobreuso_maximo"]:
            break
        top = by_section.most_common(1)[0][0]
        first = next(s for s in sentences if s.section == top and word in s.words)
        findings.append(_finding("sobreuso", first, word, conteo=count, por_1000=round(_per_1000(count, total), 2),
                                 por_seccion=dict(by_section)))
    return findings


# --- Scoring ------------------------------------------------------------------

def _counts_by_family(findings: list[dict]) -> dict[str, int]:
    families = {"catalogo": STYLE_CATEGORIES, "sobreuso": {"sobreuso"}, "conectores": CONNECTOR_CATEGORIES,
                "aperturas": OPENING_CATEGORIES, "clausulas": CLAUSE_CATEGORIES,
                "redundancia": REDUNDANCY_CATEGORIES, "plantillas": TEMPLATE_CATEGORIES}
    return {name: sum(1 for f in findings if f["categoria"] in categories) for name, categories in families.items()}


def score(sentences: list[Sentence], findings: list[dict]) -> dict:
    th = UMBRALES
    words = [w for s in sentences for w in s.words]
    total = len(words)
    lengths = [len(s.words) for s in sentences]
    alpha = [w for w in words if not w[0].isdigit() and w != CITE_TOKEN]
    diversity = mattr(alpha, th["mattr_ventana"])
    long_share = sum(1 for n in lengths if n > th["oracion_larga_palabras"]) / len(lengths) if lengths else 0.0
    mean = statistics.fmean(lengths) if lengths else 0.0
    cv = statistics.stdev(lengths) / mean if len(lengths) > 1 and mean else 0.0

    counts = _counts_by_family(findings)
    saturation = th["saturacion_por_1000"]
    density = {name: _clip(_per_1000(count, total) / saturation[name]) for name, count in counts.items()}
    families = dict(density)
    families["oraciones_largas"] = _clip((long_share - th["oraciones_largas_piso"])
                                         / (th["oraciones_largas_techo"] - th["oraciones_largas_piso"]))
    families["mattr"] = 0.0 if diversity is None else 1.0 - _clip(
        (diversity - th["mattr_piso"]) / (th["mattr_techo"] - th["mattr_piso"]))
    style = sum(weight * families[name] for name, weight in th["pesos_estilo"].items())
    flow = sum(weight * families[name] for name, weight in th["pesos_flujo"].items())
    style, flow = round(style, 3), round(flow, 3)
    has_text = total > 0
    penalty = (style + flow) / 2
    bands = th["bandas"]
    verdict = "clara" if penalty <= bands["clara"] else "irregular" if penalty <= bands["irregular"] else "requiere_revision"
    return {
        "puntaje_estilo": style if has_text else None,
        "puntaje_flujo": flow if has_text else None,
        "indice": round(100 * (1 - penalty)) if has_text else None,
        "veredicto": verdict if has_text else None,
        "familias": {name: round(value, 3) for name, value in sorted(families.items())},
        "metricas": {
            "palabras": total,
            "oraciones": len(sentences),
            "parrafos": len({(s.section, s.paragraph) for s in sentences}),
            "mattr": None if diversity is None else round(diversity, 3),
            "oraciones_largas_proporcion": round(long_share, 3),
            "longitud_media": round(mean, 1),
            "cv_longitud": round(cv, 3),
            "densidad_se_por_1000": round(_per_1000(sum(1 for w in words if w == "se"), total), 2),
        },
    }


def select_sections(sections: list[Section], wanted: str, by_position: bool) -> list[Section]:
    if wanted.isdigit():
        chosen = [s for s in sections if re.match(rf"0*{int(wanted)}(?!\d)", s.name)]
        if not chosen and by_position and 1 <= int(wanted) <= len(sections):
            chosen = [sections[int(wanted) - 1]]
        return chosen
    key = fold(wanted.lower())
    exact = [s for s in sections if fold(s.name.lower()) == key]
    return exact or [s for s in sections if fold(s.name.lower()).startswith(key)]


def audit(sections: list[Section], terms: list[Term], flujo: str, source: str,
          only: list[Section] | None = None, whole: bool = False) -> dict:
    log = Exemptions()
    collapser = Collapser(terms, flujo, log)
    every = build_sentences(sections, collapser)
    names = [s.name for s in (only if only is not None else sections)]
    scope = set(names)
    selected = [s for s in every if s.section in scope]
    collapser.log_terms(selected)
    groups = {name: [s for s in selected if s.section == name] for name in names}

    findings: list[dict] = []
    for group in groups.values():
        findings += catalog_findings(group, collapser) + flow_findings(group, collapser)
    if whole:
        findings += redundancy_findings(selected, collapser, log)
    else:
        for group in groups.values():
            findings += redundancy_findings(group, collapser, log)
    findings += [f for f in overuse_findings(every, domain_words(terms), log) if f["seccion"] in scope]

    order = {name: i for i, name in enumerate(names)}
    findings.sort(key=lambda f: (order[f["seccion"]], f["oracion"], f["categoria"], f["fragmento"]))

    report = {"version": 1, "fuente": source, "flujo": flujo,
              "alcance": "documento" if whole else "seccion" if only is not None else "secciones",
              "aviso": AVISO, "escala": "puntaje_estilo y puntaje_flujo van de 0 a 1 (menor es mejor); indice va de 0 a 100 (mayor es mejor)."}
    report.update(score(selected, findings))
    report["secciones"] = []
    for name, group in groups.items():
        if group:
            local = score(group, [f for f in findings if f["seccion"] == name])
            report["secciones"].append({"seccion": name, "palabras": local["metricas"]["palabras"],
                                        **{k: local[k] for k in ("puntaje_estilo", "puntaje_flujo", "indice", "veredicto")}})
    report["hallazgos"] = findings
    report["exentos"] = log.rows()
    report["umbrales"] = UMBRALES
    return report


def render_markdown(report: dict) -> str:
    metrics = report["metricas"]
    lines = [f"# Reporte de estilo: {report['fuente']}", "", f"> {report['aviso']}", ""]
    if report["indice"] is None:
        lines += ["La corrida todavía no tiene prosa que puntuar.", ""]
        return "\n".join(lines)
    lines += [f"- Índice: **{report['indice']}** de 100 ({report['veredicto']})",
              f"- Puntaje de estilo: {report['puntaje_estilo']}; puntaje de flujo: {report['puntaje_flujo']} (0 a 1, menor es mejor)",
              f"- Palabras: {metrics['palabras']}; oraciones: {metrics['oraciones']}; párrafos: {metrics['parrafos']}",
              f"- MATTR: {metrics['mattr']}; oraciones de más de {report['umbrales']['oracion_larga_palabras']} palabras: "
              f"{round(100 * metrics['oraciones_largas_proporcion'])} %",
              f"- Solo informativos: coeficiente de variación de longitud {metrics['cv_longitud']}; "
              f"«se» por 1000 palabras {metrics['densidad_se_por_1000']}", ""]
    if report["secciones"]:
        lines += ["## Secciones", "", "| Sección | Palabras | Índice | Veredicto |", "|---|---:|---:|---|"]
        lines += [f"| {s['seccion']} | {s['palabras']} | {s['indice']} | {s['veredicto']} |" for s in report["secciones"]]
        lines.append("")
    by_category: dict[str, list[dict]] = {}
    for finding in report["hallazgos"]:
        by_category.setdefault(finding["categoria"], []).append(finding)
    lines += ["## Hallazgos", ""]
    limit = 12
    for category, findings in sorted(by_category.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines += [f"### {category} ({len(findings)})", "", findings[0]["orientacion"], ""]
        for f in findings[:limit]:
            places = f.get("ubicaciones") or [f]
            where = "; ".join(f"{p['seccion']} párr. {p['parrafo']}, or. {p['oracion']}" for p in places[:6])
            lines.append(f"- {where}: «{f['fragmento']}»")
        if len(findings) > limit:
            lines.append(f"- Hay {len(findings) - limit} más en `reporte.json`.")
        lines.append("")
    if report["exentos"]:
        lines += [f"## Exentos ({len(report['exentos'])})", ""]
        for e in report["exentos"][:30]:
            lines.append(f"- «{e['termino'][:90]}» ({e['fuente']}, {e['ocurrencias']}): {e['motivo']}")
        lines.append("")
    return "\n".join(lines)


# --- verificar ----------------------------------------------------------------

MONTHS = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre"
DATE_RE = re.compile(rf"\b(?:\d{{1,2}}\s+de\s+)?(?:{MONTHS})(?:\s+(?:de|del)\s+\d{{4}})?\b|\b\d{{1,2}}/\d{{1,2}}/\d{{2,4}}\b"
                     r"|\b\d{4}-\d{2}-\d{2}\b", re.I)
MATH_RE = re.compile(r"(?<!\\)\$((?:[^$\\]|\\.)*?)(?<!\\)\$", re.S)
MONEY_RE = re.compile(r"\\\$\s*\d+(?:[.,]\d+)*(?:\s*(?:millones|mil millones|mil|billones))?", re.I)
COHORT_RE = re.compile(r"\b[A-Z]{2,6}-[A-Z]{2,6}-(?:\d+|x+)\b")
TRL_RE = re.compile(r"\bTRL[\s~]*\d(?:\s*(?:,|a|o|y|-)\s*\d)*")
NUMBER_RE = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*(?![^\W\d_])")
REF_RE = re.compile(r"\\(?:ref|cref|Cref|pageref|eqref|autoref|nameref)\*?\{([^}]*)\}")
LABEL_RE = re.compile(r"\\label\{([^}]*)\}")


def _normal(text: str) -> str:
    return re.sub(r"[\s~]+", " ", text).strip()


def extract_facts(text: str) -> dict[str, Counter]:
    body = "\n".join(check_run.strip_comment(line) for line in text.splitlines())
    keys = [key.strip() for match in check_run.CITE_RE.finditer(body) for key in match.group(2).split(",") if key.strip()]
    refs = [key.strip() for match in REF_RE.finditer(body) for key in match.group(1).split(",") if key.strip()]
    labels = LABEL_RE.findall(body)
    formulas = [_normal(m) for m in MATH_RE.findall(body)]
    money = [_normal(m) for m in MONEY_RE.findall(body)]

    # A citation keeps its page locator; layout arguments and keys are not facts of the text.
    visible = check_run.CITE_RE.sub(lambda m: " ".join(re.findall(r"\[([^\]]*)\]", m.group(0).split("{")[0])), body)
    visible = MATH_RE.sub(" ", visible)
    visible = _drop_commands(visible, DROPPED_COMMANDS)
    out, position = [], 0
    for match in LAYOUT_ENV_RE.finditer(visible):
        out.append(visible[position:match.start()])
        position = _skip_groups(visible, match.end())
    visible = "".join(out) + visible[position:]
    visible = visible.replace(r"\$", " ").replace(r"\%", " %")
    return {
        "numeros": Counter(NUMBER_RE.findall(visible)),
        "fechas": Counter(_normal(m).lower() for m in DATE_RE.findall(visible)),
        "dinero": Counter(money),
        "citas": Counter(keys),
        "etiquetas": Counter(labels),
        "referencias": Counter(refs),
        "cohortes": Counter(COHORT_RE.findall(visible)),
        "trl": Counter(_normal(m) for m in TRL_RE.findall(visible)),
        "formulas": Counter(formulas),
    }


def compare_texts(before: str, after: str) -> list[dict]:
    differences = []
    one, two = extract_facts(before), extract_facts(after)
    for kind in one:
        missing = sorted((one[kind] - two[kind]).elements())
        added = sorted((two[kind] - one[kind]).elements())
        if missing or added:
            differences.append({"clase": kind, "faltan": missing, "sobran": added})
    paragraphs = len(latex_paragraphs(before)), len(latex_paragraphs(after))
    if paragraphs[0] != paragraphs[1]:
        differences.append({"clase": "parrafos", "antes": paragraphs[0], "despues": paragraphs[1]})
    return differences


def verify(before: Path, after: Path) -> dict:
    pairs: list[tuple[str, Path | None, Path | None]]
    if before.is_dir():
        one = {p.relative_to(before).as_posix(): p for p in before.rglob("*.tex")}
        two = {p.relative_to(after).as_posix(): p for p in after.rglob("*.tex")}
        pairs = [(name, one.get(name), two.get(name)) for name in sorted(one.keys() | two.keys())]
    else:
        pairs = [(after.name, before, after)]
    files = []
    for name, a, b in pairs:
        if a is None or b is None:
            differences = [{"clase": "archivo", "faltan": [name] if b is None else [], "sobran": [name] if a is None else []}]
        else:
            differences = compare_texts(a.read_text(encoding="utf-8", errors="replace"),
                                        b.read_text(encoding="utf-8", errors="replace"))
        files.append({"archivo": name, "diferencias": differences})
    return {"fiel": not any(f["diferencias"] for f in files), "archivos": files}


def render_verification(result: dict) -> str:
    if result["fiel"]:
        return f"Fidelidad conservada en {len(result['archivos'])} archivo(s)."
    lines = ["Cambiaron datos que debían quedar idénticos:"]
    for item in result["archivos"]:
        for d in item["diferencias"]:
            if d["clase"] == "parrafos":
                lines.append(f"- {item['archivo']}: párrafos {d['antes']} antes, {d['despues']} después")
            else:
                lines.append(f"- {item['archivo']}: {d['clase']}; faltan {d['faltan']}; sobran {d['sobran']}")
    return "\n".join(lines)


# --- CLI ----------------------------------------------------------------------

def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def command_audit(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root) if args.run_root else None
    file_path = Path(args.docx or args.txt) if (args.docx or args.txt) else None
    if run_root is None and file_path is None:
        return _fail("Indica RUN_ROOT, --docx o --txt.")
    if run_root is not None and not run_root.is_dir():
        return _fail(f"No existe la corrida {run_root}.")
    if file_path is not None:
        if not file_path.is_file():
            return _fail(f"No existe el archivo {file_path}.")
        try:
            sections = read_docx(file_path) if args.docx else read_text_file(file_path)
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
            return _fail(f"{file_path} no es un .docx legible: {error}")
        source = file_path.name
    else:
        sections = run_sections(run_root)
        source = run_root.resolve().name

    only = None
    if args.seccion:
        only = select_sections(sections, args.seccion, by_position=file_path is not None)
        if not only:
            return _fail(f"No hay una sección «{args.seccion}».")
    flujo = check_run.detect_flujo(run_root) if run_root else "base"
    report = audit(sections, build_terms(run_root), flujo, source, only, args.todo)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    markdown = render_markdown(report)
    if run_root is not None:
        folder = run_root / REPORT_DIR
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "reporte.json").write_text(payload, encoding="utf-8")
        (folder / "reporte.md").write_text(markdown, encoding="utf-8")
    print(payload if args.json else markdown, end="")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    before, after = Path(args.antes), Path(args.despues)
    if not before.exists() or not after.exists():
        return _fail("Faltan rutas para comparar.")
    if before.is_dir() != after.is_dir():
        return _fail("Compara dos archivos o dos carpetas, no una mezcla.")
    result = verify(before, after)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_verification(result))
    return 0 if result["fiel"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Legibilidad y redundancia de prosa en español.")
    commands = parser.add_subparsers(dest="comando", required=True)
    auditar = commands.add_parser("auditar", help="Puntúa una corrida, un .docx o un texto.")
    auditar.add_argument("run_root", nargs="?", metavar="RUN_ROOT")
    auditar.add_argument("--seccion", metavar="N", help="Número o nombre de la sección, por ejemplo 3 o tdr05.")
    auditar.add_argument("--todo", action="store_true", help="Busca también la redundancia entre secciones.")
    auditar.add_argument("--json", action="store_true", help="Imprime el reporte en JSON.")
    source = auditar.add_mutually_exclusive_group()
    source.add_argument("--docx", metavar="RUTA", help="Audita un .docx en lugar de las secciones de la corrida.")
    source.add_argument("--txt", metavar="RUTA", help="Audita un texto plano en lugar de las secciones de la corrida.")
    auditar.set_defaults(handler=command_audit)
    verificar = commands.add_parser("verificar", help="Falla si una reescritura cambió un dato.")
    verificar.add_argument("antes")
    verificar.add_argument("despues")
    verificar.add_argument("--json", action="store_true", help="Imprime el resultado en JSON.")
    verificar.set_defaults(handler=command_verify)
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
