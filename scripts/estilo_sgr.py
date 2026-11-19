#!/usr/bin/env python3
"""Deterministic SGR style checks: voice, per-section lexicon, activity names, redundancy.

Only the SGR flow uses this script (check_run calls it when the run flow is
`sgr`; the revisor-estilo-sgr agent runs it before editing a section). It is
flow-agnostic itself: it reports what a regular expression can prove against
scripts/sgr/lexico_sgr.json and leaves judgment to the agent. Standard library
only; the prose helpers and the MGA patterns come from check_run.py in this
same folder.

Usage:
  python3 scripts/estilo_sgr.py RUN_ROOT [--section KEY] [--json]

KEY is a Morfeo section stem (02_justificacion, ..., 25_marco_logico). Exit 0
whatever the findings; exit 2 for bad input (missing run folder, unknown
section, unreadable lexicon). --json prints {"seccion": KEY|null,
"findings": [...]}, each finding being
{severity: "advertencia"|"info", code: "sgr-estilo-<regla>", message,
 archivo, linea, extracto, regla}.

Rules:
  primera-persona (advertencia): first person anywhere in prose or tables.
  lexicon entries (global and per section): `prohibida` -> advertencia,
    `desaconsejada` -> info; `aplica_a` picks prose, table cells or activity
    names. The MGA activity-verb ban (Manual MGA 2015, p. 81) reads activity
    names only: table cells of 10_metodologia, 14_cronograma_actividades and
    23_cadena_valor that carry an activity code or sit under an «Actividad»
    header, and the activity `nombre` of artefactos/sgr/cadena_valor.json.
  presente-proyecto (info): «El presente proyecto» more than once per section.
  conectores-en-serie (info): two consecutive sentences open with the same
    connector (R14).
  redundancia-entre-secciones (info): a span of 12 or more words copied
    literally from another section (R1-R10).
Exempt from every prose and table rule: quoted text, official names listed in
`exenciones`, and the texts that must repeat verbatim (title, central problem,
general and specific objectives, product and activity names).
"""

from __future__ import annotations

import argparse
import bisect
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEXICON_FILE = HERE / "sgr" / "lexico_sgr.json"
LEXICON_SCHEMA = "morfeo.lexico-sgr/v1"
SECTIONS_DIR = Path("redaccion") / "sections"
CHAIN_FILE = Path("artefactos") / "sgr" / "cadena_valor.json"
ACTIVITY_SECTIONS = ("10_metodologia", "14_cronograma_actividades", "23_cadena_valor")
SKIPPED_SECTIONS = frozenset({"16_bibliografia"})
SEVERITY = {"prohibida": "advertencia", "desaconsejada": "info"}
MASK = "\x00"

TABLE_ENVS = r"(?:tabular|tabularx|xltabular|longtable)\*?"
TABLE_BEGIN_RE = re.compile(r"\\begin\{" + TABLE_ENVS + r"\}")
TABLE_END_RE = re.compile(r"\\end\{" + TABLE_ENVS + r"\}")
# \begin{env} plus its width and column-spec arguments (one level of nested braces).
TABLE_BEGIN_ARGS_RE = re.compile(r"\\begin\{" + TABLE_ENVS + r"\}(\[[^\]]*\])?(\{(?:[^{}]|\{[^{}]*\})*\})*")
ROW_END_RE = re.compile(r"\\\\(\[[^\]]*\])?")
CELL_SPLIT_RE = re.compile(r"(?<!\\)&")
# Commands whose arguments are not prose: citations, references, headings (TdR titles are literal), files.
DROP_RE = re.compile(
    r"\\(?:cite[a-zA-Z]*|nocite|ref|cref|Cref|autoref|eqref|pageref|label|url|href|input|include"
    r"|includegraphics|(?:sub)*section|paragraph|chapter|caption\[[^\]]*\]|bibliography[a-z]*"
    r"|hspace|vspace|setlength|rule|cline|cmidrule)\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?")
PRE_ARGS_RE = re.compile(r"\\(?:multicolumn|multirow|textcolor|cellcolor|rowcolor)\{[^{}]*\}(?:\{[^{}]*\})?")
# check_run.normalize_tree_text turns a literal "\n" into a space (tree labels), so commands
# such as \noindent or \newline are removed before it runs.
N_COMMAND_RE = re.compile(r"\\n[a-zA-Z]*\*?")
ACTIVITY_PREFIX_RE = re.compile(
    r"^\s*(?:actividad\s*\d+(?:\.\d+)*\s*[:.\-]?\s*|\d+\.\d+\.\d+\.?\s+(?:actividad\s*\d+(?:\.\d+)*\s*[:.\-]\s*)?)",
    re.I)
CODE_PREFIX_RE = re.compile(r"^\s*\d+(?:\.\d+)+\.?\s+")
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]*")
WORD_RE = re.compile(r"[^\W_]+|\x00+")


def _check_run():
    """check_run.py from this folder, imported lazily (check_run imports this script too)."""
    module = sys.modules.get("check_run")
    if module is None:
        spec = importlib.util.spec_from_file_location("check_run", HERE / "check_run.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["check_run"] = module
        spec.loader.exec_module(module)
    return module


def compile_rule(pattern: str) -> re.Pattern:
    """Compile a lexicon regex; `check_run:NAME` reuses check_run's compiled pattern NAME."""
    if pattern.startswith("check_run:"):
        name = pattern.split(":", 1)[1]
        compiled = getattr(_check_run(), name, None)
        if not isinstance(compiled, re.Pattern):
            raise ValueError(f"check_run.py no define el patrón {name}")
        return compiled
    try:
        return re.compile(pattern, re.I | re.M)
    except re.error as exc:
        raise ValueError(f"Regex inválida en el léxico SGR ({pattern!r}): {exc}") from exc


def load_lexicon(path: Path = LEXICON_FILE) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"No se pudo leer el léxico SGR {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != LEXICON_SCHEMA:
        raise ValueError(f"{path} no declara el esquema {LEXICON_SCHEMA}")
    return data


def section_keys() -> tuple[str, ...]:
    cr = _check_run()
    return tuple(cr.CANONICAL_SECTIONS) + tuple(cr.SGR_SECTIONS)


# --- Text extraction ----------------------------------------------------------

def plain(fragment: str) -> str:
    """LaTeX-free text of one line or cell: no citations, labels, headings or commands."""
    text = PRE_ARGS_RE.sub(" ", fragment)
    text = DROP_RE.sub(" ", text)
    text = N_COMMAND_RE.sub(" ", text)
    return _check_run().normalize_tree_text(text)


class Stream:
    """Concatenated text with a map from offsets back to source line numbers."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.starts: list[int] = []
        self.lines: list[int] = []
        self.size = 0

    def add(self, text: str, line: int) -> None:
        if not text:
            return
        if self.parts:
            self.size += 1
        self.starts.append(self.size)
        self.lines.append(line)
        self.parts.append(text)
        self.size += len(text)

    def text(self) -> str:
        return " ".join(self.parts)

    def locate(self, offset: int) -> tuple[int, str]:
        index = max(0, bisect.bisect_right(self.starts, offset) - 1)
        return self.lines[index], self.parts[index]


def prose_stream(text: str) -> Stream:
    stream = Stream()
    for number, line in _check_run().prose_lines(text):
        stream.add(plain(line), number)
    return stream


def table_rows(text: str):
    """Yield (table index, line number, raw cells) for each row of the tabular environments."""
    strip_comment = _check_run().strip_comment
    depth, table, buffer, start = 0, -1, "", None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = strip_comment(raw)
        opens, closes = len(TABLE_BEGIN_RE.findall(line)), len(TABLE_END_RE.findall(line))
        if depth == 0 and opens == 0:
            continue
        if depth == 0:
            table, buffer, start = table + 1, "", None
        content = TABLE_END_RE.sub(" ", TABLE_BEGIN_ARGS_RE.sub(" ", line))
        pieces = ROW_END_RE.split(content)
        # split() interleaves the optional [spacing] group: keep the text pieces only.
        texts = pieces[0::2]
        for i, piece in enumerate(texts):
            if piece.strip() and start is None:
                start = number
            buffer += " " + piece
            if i < len(texts) - 1:
                if buffer.strip():
                    yield table, start or number, CELL_SPLIT_RE.split(buffer)
                buffer, start = "", None
        depth = max(0, depth + opens - closes)
        if depth == 0 and buffer.strip():
            yield table, start or number, CELL_SPLIT_RE.split(buffer)
            buffer, start = "", None


def table_cells(text: str) -> list[tuple[int, int, int, str]]:
    """(table, line, column, plain text) of every non-empty cell."""
    out = []
    for table, line, cells in table_rows(text):
        for column, cell in enumerate(cells):
            value = plain(cell)
            if value:
                out.append((table, line, column, value))
    return out


def activity_names(cells: list[tuple[int, int, int, str]]) -> list[tuple[int, str]]:
    """(line, name) of the activity names in a section's tables."""
    fold = _check_run()._fold
    header_columns: dict[int, set[int]] = {}
    first_line: dict[int, int] = {}
    for table, line, column, value in cells:
        first_line.setdefault(table, line)
        if line == first_line[table] and fold(value.lower()).startswith("actividad") \
                and not ACTIVITY_PREFIX_RE.match(value):
            header_columns.setdefault(table, set()).add(column)
    names, seen = [], set()
    for table, line, column, value in cells:
        name = None
        prefix = ACTIVITY_PREFIX_RE.match(value)
        if prefix and value[prefix.end():].strip():
            name = value[prefix.end():]
        elif column in header_columns.get(table, set()) and line != first_line[table]:
            name = CODE_PREFIX_RE.sub("", value)
        if name and (line, column) not in seen:
            seen.add((line, column))
            names.append((line, name.strip()))
    return names


# --- Exemptions and verbatim whitelist ----------------------------------------

def _phrase_pattern(text: str) -> re.Pattern | None:
    words = _check_run().normalize_tree_text(text).rstrip(" .;:").split()
    if len(words) < 3 or words[0].startswith("[Por"):
        return None
    return re.compile(r"\s+".join(re.escape(w) for w in words), re.I)


def whitelist_patterns(run_root: Path) -> list[re.Pattern]:
    """Texts that must repeat verbatim: title, central problem, objectives, products, activities."""
    cr = _check_run()
    texts: list[str] = [cr.project_title(run_root / "redaccion")]
    spec = cr._read_json_file(run_root / cr.PROBLEM_SPEC) or {}
    texts.append(str((spec.get("trunk") or {}).get("text") or ""))
    objectives = cr._read_json_file(run_root / cr.OBJECTIVES_FILE) or {}
    texts.append(str((objectives.get("trunk") or {}).get("text") or ""))
    texts += [str(g.get("objective") or "") for g in objectives.get("groups") or [] if isinstance(g, dict)]
    for objective, product, activity in _chain_items(run_root):
        texts += [objective.get("texto") or "", product.get("nombre") or "",
                  (activity or {}).get("nombre") or ""]
    patterns = {}
    for text in texts:
        pattern = _phrase_pattern(str(text))
        if pattern is not None:
            patterns[pattern.pattern] = pattern
    # Longest first, so a whole objective is masked before a product name inside it.
    return sorted(patterns.values(), key=lambda p: -len(p.pattern))


def _chain_items(run_root: Path):
    """(objective, product, activity|None) dicts of cadena_valor.json, when it exists."""
    data = _check_run()._read_json_file(run_root / CHAIN_FILE) or {}
    for objective in data.get("objetivos") or []:
        if not isinstance(objective, dict):
            continue
        for product in objective.get("productos") or []:
            if not isinstance(product, dict):
                continue
            activities = [a for a in product.get("actividades") or [] if isinstance(a, dict)]
            if not activities:
                yield objective, product, None
            for activity in activities:
                yield objective, product, activity


def mask(text: str, patterns: list[re.Pattern]) -> str:
    """Replace every match with MASK characters of the same length (offsets stay valid)."""
    for pattern in patterns:
        text = pattern.sub(lambda m: MASK * len(m.group(0)), text)
    return text


# --- Findings -----------------------------------------------------------------

def _finding(severity: str, rule: str, message: str, archivo: str, linea, extracto: str) -> dict:
    extracto = re.sub(r"\s+", " ", extracto).strip()
    if len(extracto) > 200:
        extracto = extracto[:197] + "..."
    return {"severity": severity, "code": f"sgr-estilo-{rule}", "message": message,
            "archivo": archivo, "linea": linea, "extracto": extracto, "regla": rule}


class Rule:
    def __init__(self, entry: dict) -> None:
        self.id = entry["id"]
        self.severity = SEVERITY[entry["tipo"]]
        self.motivo = entry["motivo"]
        self.aplica_a = entry["aplica_a"]
        self.pattern = compile_rule(entry["regex"])


def section_rules(lexicon: dict, stem: str) -> list[Rule]:
    entries = list(lexicon.get("global") or []) + list((lexicon.get("secciones") or {}).get(stem) or [])
    return [Rule(e) for e in entries if e.get("regex") and e.get("tipo") in SEVERITY]


def _stream_hits(rule_id, severity, pattern, motivo, stream, masked, archivo, out) -> None:
    seen = set()
    for match in pattern.finditer(masked):
        line, extracto = stream.locate(match.start())
        if line in seen:
            continue
        seen.add(line)
        out.append(_finding(severity, rule_id, f"«{match.group(0).strip()}»: {motivo}", archivo, line, extracto))


def _cell_hits(rule_id, severity, pattern, motivo, cells, archivo, out) -> None:
    seen = set()
    for line, original, masked in cells:
        match = pattern.search(masked)
        if match and line not in seen:
            seen.add(line)
            out.append(_finding(severity, rule_id, f"«{match.group(0).strip()}»: {motivo}", archivo, line,
                                original))


def _connector_hits(connectors: list[str], stream: Stream, archivo: str, out: list[dict]) -> None:
    fold = _check_run()._fold
    ordered = sorted((fold(c.lower()) for c in connectors), key=len, reverse=True)
    previous = None
    for match in SENTENCE_RE.finditer(stream.text()):
        sentence = fold(match.group(0).strip().lower())
        current = next((c for c in ordered if re.match(re.escape(c) + r"\b", sentence)), None)
        if current and current == previous:
            line, extracto = stream.locate(match.start() + len(match.group(0)) - len(match.group(0).lstrip()))
            out.append(_finding("info", "conectores-en-serie",
                                f"Dos oraciones seguidas abren con «{current}»: variar o suprimir el conector (R14).",
                                archivo, line, extracto))
        previous = current


def _tokens(text: str, line_of) -> list[tuple[str, int, str] | None]:
    """(folded word, line, word) per word; None where a masked span breaks the text."""
    fold = _check_run()._fold
    out: list[tuple[str, int, str] | None] = []
    for match in WORD_RE.finditer(text):
        word = match.group(0)
        out.append(None if word.startswith(MASK) else (fold(word.lower()), line_of(match.start()), word))
    return out


def _grams(tokens: list, size: int):
    """(start index, gram) of the n-grams that cross no mask and carry real words."""
    for i in range(len(tokens) - size + 1):
        window = tokens[i:i + size]
        if any(t is None for t in window):
            continue
        words = tuple(t[0] for t in window)
        if sum(1 for w in words if len(w) >= 4 and w.isalpha()) * 2 >= size:
            yield i, words


def _redundancy(section_tokens: dict[str, list], targets: list[str], size: int, archivos: dict[str, str],
                out: list[dict]) -> None:
    index: dict[tuple, set[str]] = {}
    for stem, tokens in section_tokens.items():
        for _, gram in _grams(tokens, size):
            index.setdefault(gram, set()).add(stem)
    for stem in targets:
        tokens = section_tokens.get(stem) or []
        covered: dict[str, set[int]] = {}
        for i, gram in _grams(tokens, size):
            for other in index.get(gram, ()):
                if other != stem:
                    covered.setdefault(other, set()).update(range(i, i + size))
        for other in sorted(covered):
            positions = sorted(covered[other])
            spans, first = 1, [positions[0]]
            for a, b in zip(positions, positions[1:]):
                if b != a + 1:
                    spans += 1
                elif spans == 1:
                    first.append(b)
            words = [tokens[p][2] for p in first]
            excerpt = " ".join(words[:24]) + (" ..." if len(words) > 24 else "")
            out.append(_finding(
                "info", "redundancia-entre-secciones",
                f"{spans} fragmento(s) de {size} o más palabras copiados literalmente de {other}.tex: "
                "remitir en una oración en lugar de repetir (patrones R1-R10).",
                archivos[stem], tokens[first[0]][1], excerpt))


def findings(run_root: Path, section: str | None = None) -> list[dict]:
    """SGR style findings for the run (or one section of it), sorted by file and line."""
    run_root = Path(run_root)
    keys = section_keys()
    if section is not None and section not in keys:
        raise ValueError(f"Sección desconocida: {section} (usar un stem de Morfeo, p. ej. 02_justificacion)")
    lexicon = load_lexicon()
    sec_dir = run_root / SECTIONS_DIR
    present = [k for k in keys if k not in SKIPPED_SECTIONS and (sec_dir / f"{k}.tex").is_file()]
    targets = present if section is None else [k for k in present if k == section]
    voice = lexicon.get("voz") or {}
    first_person = compile_rule(voice["primera_persona"]["regex"])
    first_person_motivo = voice["primera_persona"]["motivo"]
    limits = [(item, compile_rule(item["regex"])) for item in voice.get("limites") or []]
    exempt = [compile_rule(item["regex"]) for item in lexicon.get("exenciones") or []]
    whitelist = whitelist_patterns(run_root)
    redundancy = lexicon.get("redundancia") or {}
    out: list[dict] = []

    # Activity names of the value chain file come first, so the rendered tables do not repeat them.
    flagged_names: set[str] = set()
    fold = _check_run()._fold
    activity_rules = [r for stem in ("23_cadena_valor",) for r in section_rules(lexicon, stem)
                      if r.aplica_a == "nombres_actividad"]
    if section in (None, "23_cadena_valor"):
        for _, _, activity in _chain_items(run_root):
            name = str((activity or {}).get("nombre") or "").strip()
            if not name:
                continue
            for rule in activity_rules:
                match = rule.pattern.search(mask(name, exempt))
                if match:
                    flagged_names.add(fold(name.lower()))
                    out.append(_finding(rule.severity, rule.id,
                                        f"Actividad {activity.get('codigo') or '?'} «{name}»: {rule.motivo}",
                                        CHAIN_FILE.as_posix(), None, name))

    section_tokens: dict[str, list] = {}
    archivos: dict[str, str] = {}
    for stem in present:
        path = sec_dir / f"{stem}.tex"
        archivo = (SECTIONS_DIR / f"{stem}.tex").as_posix()
        archivos[stem] = archivo
        text = path.read_text(encoding="utf-8", errors="replace")
        stream = prose_stream(text)
        masked = mask(mask(stream.text(), exempt), whitelist)
        cells = table_cells(text)
        masked_cells = [(line, value, mask(mask(value, exempt), whitelist)) for _, line, _, value in cells]
        table_text = Stream()
        for line, _, masked_value in masked_cells:
            table_text.add(masked_value, line)
        section_tokens[stem] = (_tokens(masked, lambda o, s=stream: s.locate(o)[0]) + [None]
                                + _tokens(table_text.text(), lambda o, s=table_text: s.locate(o)[0]))
        if stem not in targets:
            continue

        _stream_hits("primera-persona", "advertencia", first_person, first_person_motivo, stream, masked, archivo,
                     out)
        _cell_hits("primera-persona", "advertencia", first_person, first_person_motivo, masked_cells, archivo,
                   out)
        for rule in section_rules(lexicon, stem):
            if rule.aplica_a == "prosa":
                _stream_hits(rule.id, rule.severity, rule.pattern, rule.motivo, stream, masked, archivo, out)
            elif rule.aplica_a == "tabla":
                _cell_hits(rule.id, rule.severity, rule.pattern, rule.motivo, masked_cells, archivo, out)
        if stem in ACTIVITY_SECTIONS:
            rules = [r for r in section_rules(lexicon, stem) if r.aplica_a == "nombres_actividad"]
            for line, name in activity_names(cells):
                if fold(name.lower()) in flagged_names:
                    continue
                for rule in rules:
                    match = rule.pattern.search(mask(name, exempt))
                    if match:
                        out.append(_finding(rule.severity, rule.id, f"Actividad «{name}»: {rule.motivo}",
                                            archivo, line, name))
        for item, pattern in limits:
            hits = list(pattern.finditer(masked))
            if len(hits) > int(item.get("max_por_seccion", 1)):
                line, extracto = stream.locate(hits[int(item.get("max_por_seccion", 1))].start())
                out.append(_finding("info", item["id"],
                                    f"«{item['expresion']}» aparece {len(hits)} veces: {item['motivo']}",
                                    archivo, line, extracto))
        _connector_hits(redundancy.get("conectores_en_serie") or [], stream, archivo, out)

    _redundancy(section_tokens, targets, int(redundancy.get("ngrama_min_palabras") or 12), archivos, out)
    out.sort(key=lambda f: (f["archivo"], f["linea"] or 0, f["code"]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_root", help="run folder (proposals/<run-id>)")
    parser.add_argument("--section", help="only this section stem, e.g. 02_justificacion")
    parser.add_argument("--json", action="store_true", help='print {"seccion", "findings"} as JSON')
    args = parser.parse_args()
    run_root = Path(args.run_root)
    if not run_root.is_dir():
        print(f"error: {run_root} no es una carpeta de corrida", file=sys.stderr)
        return 2
    try:
        found = findings(run_root.resolve(), args.section)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"seccion": args.section, "findings": found}, ensure_ascii=False, indent=2))
        return 0
    for f in found:
        where = f["archivo"] + (f":{f['linea']}" if f["linea"] else "")
        print(f"[{f['severity'].upper()}] {f['code']} {where} {f['message']}")
    warnings = sum(1 for f in found if f["severity"] == "advertencia")
    print(f"estilo_sgr: {warnings} advertencias, {len(found) - warnings} notas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
