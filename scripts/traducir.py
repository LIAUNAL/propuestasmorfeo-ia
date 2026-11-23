#!/usr/bin/env python3
"""Translation of a run's manuscript, Spanish to English or English to Spanish.

    traducir.py plan           [RUN_ROOT] --lang <en|es> [--term T]... [--json]
    traducir.py show           [RUN_ROOT] --lang <en|es> (--block ID | --fragment ID)
    traducir.py store          [RUN_ROOT] --lang <en|es> --block ID --file PATH
    traducir.py store-fragment [RUN_ROOT] --lang <en|es> --fragment ID --file PATH
    traducir.py audit          [RUN_ROOT] --lang <en|es>
    traducir.py build          [RUN_ROOT] --lang <en|es>
    traducir.py compile        [RUN_ROOT] --lang <en|es>
    traducir.py status         [RUN_ROOT] --lang <en|es>

`--lang` is the TARGET language and must differ from the run's writing
language (`scripts/language.py run`). The manuscript under `redaccion/` stays
the canonical source and nothing here ever writes it: the translation is a
derived artifact under `redaccion/traducciones/<lang>/`:

- `traduccion.json`: schema `morfeo.traduccion/v1`. Source and target
  language, the sha256 of every source file, one record per block
  (`source_digest`: the digest of the source text the translation was made
  from; `state`; `stored_at`; the block's style summary), one record per
  fragment and the glossary.
- `bloques/<id>.tex`: the translated text of each block.
- `main.tex`, `datos_proyecto.tex`, `sections/*.tex`: the built manuscript
  (`build`), with babel, table captions and cleveref names switched to the
  target language and the bibliography resolved from `redaccion/`.
- `auditoria.json`: the last `audit`, the target language's style check
  (`estilo_en.py` for English, `estilo_es.py` for Spanish) over the stored
  blocks plus the fidelity of each one against the current source.
- `main.pdf`: the compiled translation (`compile`).

Blocks are the paragraphs of each `sections/NN_*.tex`: text split at blank
lines outside any environment, so a table, a list or a figure is one block.
A block id is `<file stem>-b<NN>` in document order; its digest is the sha256
of its source text. A block is `missing` (no translation), `current` (stored
against the digest the block has now) or `stale` (the source changed after
the store). `plan` re-keys a translation whose source text moved to another
position, so inserting a paragraph never discards the translations below it.

Fragments are the prose outside blocks: sectioning titles (`\\section` to
`\\subparagraph`, the optional short title being a fragment of its own), the
`\\caption` of a figure that has no other text (and every caption in
`main.tex` and in `sections/diag_*_caption.tex`), and the project title and
affiliation in `datos_proyecto.tex`. A fragment id is
`<file stem>-<kind>-<n>-<sha8>`.

Every stored text passes the fidelity gate before a byte is written: no
marker line, no new placeholder, it reads as the target language, and it
keeps the source's citation commands and keys, labels and reference targets,
math, numbers, file arguments, environments, list items, table cells and
paragraph count. Glossary terms with a declared form (`--term "TEPT=PTSD"`,
`--term GCPDS`) must appear in that form. TikZ node labels inside
`sections/diag_*.tex` are copied untouched.

Output is JSON on stdout. A refusal prints `{"ok": false, "code", "message"}`
and exits 1; a usage error exits 2. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

SCHEMA = "morfeo.traduccion/v1"
AUDIT_SCHEMA = "morfeo.traduccion-auditoria/v1"
LANGS = ("es", "en")
STATES = ("missing", "current", "stale")
TRANSLATION_DIR = Path("traducciones")
MARKER = "% morfeo-traduccion"
HERE = Path(__file__).resolve().parent

HEADINGS = ("section", "subsection", "subsubsection", "paragraph", "subparagraph")
HEADING_LINE_RE = re.compile(r"\\(" + "|".join(HEADINGS) + r")(?![A-Za-z@])\*?")
CAPTION_RE = re.compile(r"\\caption(?![A-Za-z@])")
FRAGMENT_RE = re.compile(r"\\(" + "|".join(HEADINGS + ("title", "caption")) + r")(?![A-Za-z@])\*?")
COVER_MACROS = ("TituloProyecto", "AfiliacionProyecto")
COVER_RE = re.compile(r"\\newcommand\{\\(" + "|".join(COVER_MACROS) + r")\}")
COMMENT_RE = re.compile(r"(?<!\\)%.*$", re.M)
BEGIN_RE = re.compile(r"\\begin\{([A-Za-z*]+)\}")
END_RE = re.compile(r"\\end\{([A-Za-z*]+)\}")

CITE_RE = re.compile(r"\\(cite|citep|citet|citealp|citealt|citeauthor|citeyear|citeyearpar|nocite|Citet|Citep|"
                     r"Citeauthor)\*?((?:\s*\[[^\]]*\]){0,2})\s*\{([^}]*)\}")
REF_RE = re.compile(r"\\(?:ref|cref|Cref|pageref|eqref|autoref|nameref|vref|labelcref)\*?\{([^}]*)\}")
LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
FILE_RE = re.compile(r"\\(?:input|include|includegraphics|url|href|SeccionSiExiste|DiagramaSiExiste)"
                     r"(?:\[[^\]]*\])?\{([^}]*)\}")
DISPLAY_RE = re.compile(r"\\begin\{(equation|align|gather|multline|eqnarray|flalign|alignat|displaymath|math)"
                        r"(\*?)\}(.*?)\\end\{\1\2\}", re.S)
INLINE_MATH_RE = re.compile(r"(?<!\\)\$\$(.*?)(?<!\\)\$\$|(?<!\\)\$((?:[^$\\]|\\.)*?)(?<!\\)\$|\\\((.*?)\\\)|"
                            r"\\\[(.*?)\\\]", re.S)
NUMBER_RE = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*")
DIGIT_GROUP_RE = re.compile(r"(?<=\d)(?:\s|\\,|~|\\;|\\ )(?=\d{3}(?!\d))")
CELL_RE = re.compile(r"(?<!\\)&")
ITEM_RE = re.compile(r"\\item(?![A-Za-z@])")
WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")

# Commands whose arguments are never prose: a number is how many leading groups
# to drop (the rest is text, as in \multicolumn{2}{c}{Text}); None drops them all.
NON_TEXT = {
    "label": None, "ref": None, "cref": None, "Cref": None, "pageref": None, "eqref": None, "autoref": None,
    "nameref": None, "vref": None, "labelcref": None, "input": None, "include": None, "includegraphics": None,
    "url": None, "href": 1, "bibliography": None, "bibliographystyle": None, "addbibresource": None,
    "setcounter": None, "addtocounter": None, "setlength": None, "addtolength": None, "vspace": None,
    "hspace": None, "newcommand": None, "renewcommand": None, "providecommand": None, "definecolor": None,
    "usepackage": None, "documentclass": None, "pagestyle": None, "thispagestyle": None, "rule": None,
    "color": None, "textcolor": 1, "cellcolor": None, "rowcolor": None, "columncolor": None, "multicolumn": 2,
    "multirow": 2, "cline": None, "cmidrule": None, "SeccionSiExiste": None, "DiagramaSiExiste": None,
    "fancyhead": None, "fancyfoot": None, "resizebox": 2, "scalebox": 1, "makebox": None, "parbox": 1,
    "raisebox": 1, "arrayrulecolor": None, "renewenvironment": None, "newenvironment": None,
    "cite": None, "citep": None, "citet": None, "citealp": None, "citealt": None, "citeauthor": None,
    "citeyear": None, "citeyearpar": None, "nocite": None, "Citet": None, "Citep": None, "Citeauthor": None,
}
# Groups that follow \begin{env} and are layout, not text.
ENV_ARGS = {"tabular": 1, "tabular*": 2, "tabularx": 2, "xltabular": 2, "tabulary": 2, "longtable": 1,
            "array": 1, "minipage": 1, "multicols": 1, "ganttchart": 2, "wrapfigure": 2, "tikzpicture": 0}

# Function words that tell the two languages apart (none belongs to both).
FUNCTION_WORDS = {
    "es": frozenset("el la los las del que y en un una unos unas por para con se es son al lo como más pero sus su "
                    "este esta estos estas entre sobre desde cuando donde porque cada también sin ya fue han ha ser "
                    "está están muy hasta otros otras mediante según hacia cuyo cuya".split()),
    "en": frozenset("the of and to in is are this that with for by which on as an be from these it was were has "
                    "have not but its their than when where while into each also such between through those "
                    "whose within upon".split()),
}
LANG_NAMES = {"es": "Spanish", "en": "English"}
NOT_TARGET = {"es": "TRANSLATION_NOT_SPANISH", "en": "TRANSLATION_NOT_ENGLISH"}
PLACEHOLDER_RES = (
    ("to-be-defined", re.compile(r"\[\s*(?:Por definir|To be defined)", re.I)),
    ("todo", re.compile(r"\b(?:TODO|FIXME|TBD|XXX)\b")),
    ("pending", re.compile(r"\[\s*(?:pendiente|pending|traducir|translate|traducción|translation)\b", re.I)),
    ("ellipsis", re.compile(r"\[\s*(?:\.\.\.|…)\s*\]|\?\?\?|<<[^>]*>>")),
)
INSTITUTIONS = (
    "Universidad Nacional de Colombia", "Universidad Tecnológica de Pereira", "Universidad de Antioquia",
    "Sede Manizales", "Departamento Nacional de Planeación", "Ministerio de Ciencia, Tecnología e Innovación",
    "MinCiencias", "Sistema General de Regalías", "GCPDS", "LabIA",
)
ACRONYM_RE = re.compile(r"\(([A-Z][A-Za-z0-9-]*[A-Z0-9]s?)\)")
TERM_COMMAND_RE = re.compile(r"\\(?:texttt|textsc)\{([^{}]+)\}")


class Refused(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# --- Loading sibling kit scripts ------------------------------------------------

def _load(name: str, alias: str):
    spec = importlib.util.spec_from_file_location(alias, HERE / name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


_CACHE: dict = {}


def language_module():
    if "language" not in _CACHE:
        _CACHE["language"] = _load("language.py", "_traducir_language")
    return _CACHE["language"]


def style_engine(lang: str):
    """The style engine of `lang`: estilo_es.py itself, or estilo_en.py's engine."""
    if lang not in _CACHE:
        if lang == "en":
            _CACHE[lang] = _load("estilo_en.py", "_traducir_estilo_en").engine
        else:
            _CACHE[lang] = _load("estilo_es.py", "_traducir_estilo_es")
    return _CACHE[lang]


# --- Small I/O --------------------------------------------------------------------

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _write_json(path: Path, value: dict) -> None:
    _atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def translation_dir(run_root: Path, lang: str) -> Path:
    return Path(run_root) / "redaccion" / TRANSLATION_DIR / lang


def _shown(run_root: Path, path: Path) -> str:
    return Path(path).relative_to(Path(run_root)).as_posix()


def source_language(run_root: Path) -> str:
    return language_module().run_lang(Path(run_root))


def check_languages(run_root: Path, lang: str) -> str:
    """The run's writing language; refuses an unknown target or the same language."""
    if lang not in LANGS:
        raise Refused("TRANSLATION_LANGUAGE_UNSUPPORTED", f"--lang {lang!r}: use one of {', '.join(LANGS)}")
    if not (Path(run_root) / "redaccion").is_dir():
        raise Refused("TRANSLATION_NO_SOURCE", f"{Path(run_root) / 'redaccion'} does not exist")
    source = source_language(run_root)
    if source == lang:
        raise Refused("TRANSLATION_SAME_LANGUAGE",
                      f"the run is written in {LANG_NAMES[source]} ({source}); the target --lang must be the other "
                      f"language ({'en' if source == 'es' else 'es'})")
    return source


def _read_record(run_root: Path, lang: str) -> dict | None:
    path = translation_dir(run_root, lang) / "traduccion.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) and record.get("schema") == SCHEMA else None


def _require_record(run_root: Path, lang: str) -> dict:
    record = _read_record(run_root, lang)
    if record is None:
        raise Refused("TRANSLATION_NOT_PLANNED",
                      f"{_shown(run_root, translation_dir(run_root, lang) / 'traduccion.json')} is absent or "
                      f"unreadable; run `traducir.py plan --lang {lang}` first")
    return record


# --- LaTeX scanning -------------------------------------------------------------------

def _mask_comments(text: str) -> str:
    return COMMENT_RE.sub(lambda m: " " * len(m.group(0)), text)


def _group_end(text: str, position: int) -> int:
    """Index just after the [..] or {..} group opening at `position`, or -1."""
    opening = text[position]
    closing = "]" if opening == "[" else "}"
    depth, i = 0, position
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _skip_space(text: str, position: int) -> int:
    while position < len(text) and text[position] in " \t":
        position += 1
    return position


def _argument_spans(text: str, position: int, optional: bool = True) -> tuple[list[tuple[int, int]], int]:
    """Spans (without delimiters) of an optional [..] then one {..} group at
    `position`; the second value is the index after the last group, or -1."""
    spans = []
    position = _skip_space(text, position)
    if optional and position < len(text) and text[position] == "[":
        end = _group_end(text, position)
        if end < 0:
            return [], -1
        spans.append((position + 1, end - 1))
        position = _skip_space(text, end)
    if position >= len(text) or text[position] != "{":
        return [], -1
    end = _group_end(text, position)
    if end < 0:
        return [], -1
    spans.append((position + 1, end - 1))
    return spans, end


def _drop_groups(text: str, position: int, count: int | None) -> int:
    dropped = 0
    while count is None or dropped < count:
        probe = _skip_space(text, position)
        if probe < len(text) and text[probe] in "[{":
            end = _group_end(text, probe)
            if end < 0:
                return len(text)
            position = end
            if text[probe] == "{":
                dropped += 1
            continue
        break
    return position


def visible_text(tex: str) -> str:
    """The words a reader sees: no comments, math, citation, label or layout argument."""
    text = COMMENT_RE.sub("", tex)
    text = DISPLAY_RE.sub(" ", text)
    text = INLINE_MATH_RE.sub(" ", text)
    out, i = [], 0
    while i < len(text):
        char = text[i]
        if char != "\\":
            out.append(char)
            i += 1
            continue
        match = re.match(r"\\([A-Za-z@]+)\*?", text[i:])
        if not match:
            i += 2
            out.append(" ")
            continue
        name = match.group(1)
        i += match.end()
        if name in ("begin", "end"):
            env = re.match(r"\s*\{([A-Za-z*]+)\}", text[i:])
            if env:
                i += env.end()
                if name == "begin":
                    i = _drop_groups(text, i, 0)  # the optional [..] placement
                    i = _drop_groups(text, i, ENV_ARGS.get(env.group(1), 0))
            out.append(" ")
        elif name in NON_TEXT:
            i = _drop_groups(text, i, NON_TEXT[name])
            out.append(" ")
        else:
            out.append(" ")
    return re.sub(r"[{}\[\]&~$]", " ", "".join(out))


def has_text(tex: str) -> bool:
    return any(len(word) >= 2 for word in WORD_RE.findall(visible_text(tex)))


def _caption_free(tex: str) -> str:
    """`tex` with every \\caption argument blanked (a caption alone is a fragment)."""
    masked = _mask_comments(tex)
    chars = list(tex)
    for match in CAPTION_RE.finditer(masked):
        spans, _ = _argument_spans(masked, match.end())
        for start, stop in spans:
            chars[start:stop] = " " * (stop - start)
    return "".join(chars)


def segment(text: str) -> list[dict]:
    """Units of a section file in order, each `{kind, start, end}` with kind
    `heading`, `block` or `structural`. Units never overlap; what lies between
    them (blank lines, indentation) is kept verbatim by `build`."""
    masked = _mask_comments(text)
    units: list[dict] = []
    depth = 0
    chunk_start: int | None = None
    chunk_end = 0
    offset = 0

    def close() -> None:
        nonlocal chunk_start
        if chunk_start is not None:
            units.append({"kind": "chunk", "start": chunk_start, "end": chunk_end})
            chunk_start = None

    lines = text.splitlines(keepends=True)
    position = 0
    while position < len(lines):
        line = lines[position]
        line_start = offset
        offset += len(line)
        position += 1
        body = masked[line_start:line_start + len(line)]
        stripped = body.strip()
        if depth == 0 and not line.strip():
            close()
            continue
        indent = len(body) - len(body.lstrip())
        heading = HEADING_LINE_RE.match(body, indent) if depth == 0 else None
        if heading:
            close()
            spans, end = _argument_spans(masked, line_start + heading.end())
            if end > 0:
                units.append({"kind": "heading", "start": line_start + indent, "end": end})
                # A heading's group may span lines: skip the lines it consumed.
                while offset < end and position < len(lines):
                    offset += len(lines[position])
                    position += 1
                rest = masked[end:offset]
                if rest.strip():
                    lead = len(rest) - len(rest.lstrip())
                    chunk_start = end + lead
                    chunk_end = offset - (len(rest) - len(rest.rstrip()))
                continue
        if chunk_start is None and stripped:
            chunk_start = line_start + indent
        if stripped or chunk_start is not None:
            chunk_end = line_start + len(line.rstrip("\r\n").rstrip())
        for match in BEGIN_RE.finditer(body):
            if match.group(1) != "document":
                depth += 1
        for match in END_RE.finditer(body):
            if match.group(1) != "document":
                depth = max(0, depth - 1)
    close()
    for unit in units:
        if unit["kind"] == "chunk":
            piece = text[unit["start"]:unit["end"]]
            unit["kind"] = "block" if has_text(_caption_free(piece)) else "structural"
    return units


def _fragments_in(text: str, stem: str, region: tuple[int, int] | None, kinds, counters: dict) -> list[dict]:
    """Fragments of `kinds` inside `region` (the whole text when None)."""
    masked = _mask_comments(text)
    start_at, stop_at = region or (0, len(text))
    found = []
    for match in FRAGMENT_RE.finditer(masked, start_at, stop_at):
        kind = match.group(1)
        if kind not in kinds:
            continue
        spans, _ = _argument_spans(masked, match.end())
        found += _fragment_records(text, stem, kind, spans, counters)
    return found


def _fragment_records(text: str, stem: str, kind: str, spans, counters: dict) -> list[dict]:
    records = []
    for start, stop in spans:
        source = text[start:stop]
        if "#" in source or not has_text(source):
            continue
        counters[kind] = counters.get(kind, 0) + 1
        sha = _sha(source)
        records.append({"id": f"{stem}-{kind}-{counters[kind]}-{sha[:8]}", "kind": kind, "source": source,
                        "source_sha": sha, "start": start, "end": stop, "line": text.count("\n", 0, start) + 1})
    return records


def _cover_fragments(text: str, stem: str) -> list[dict]:
    masked = _mask_comments(text)
    counters: dict = {}
    found = []
    for match in COVER_RE.finditer(masked):
        spans, _ = _argument_spans(masked, match.end(), optional=False)
        if spans and not text[spans[0][0]:spans[0][1]].lstrip().startswith(("[Por definir", "[To be defined")):
            found += _fragment_records(text, stem, "title" if match.group(1) == "TituloProyecto" else "affiliation",
                                       spans, counters)
    return found


# --- The source manuscript ----------------------------------------------------------

def source_files(run_root: Path) -> list[dict]:
    """Every file of `redaccion/` the translation derives, with its role:
    `main` and `cover` (fragments only), `section` (blocks and fragments),
    `caption` (captions only) and `copy` (TikZ drawings, copied untouched)."""
    redaccion = Path(run_root) / "redaccion"
    files = []
    main = redaccion / "main.tex"
    if main.is_file():
        files.append(("main.tex", "main"))
    if (redaccion / "datos_proyecto.tex").is_file():
        files.append(("datos_proyecto.tex", "cover"))
    sections = redaccion / "sections"
    for path in sorted(sections.glob("*.tex")) if sections.is_dir() else []:
        if path.name.startswith("diag_"):
            role = "caption" if path.stem.endswith("_caption") else "copy"
        elif path.stem.startswith("01_titulo"):
            role = "copy"
        else:
            role = "section"
        files.append((f"sections/{path.name}", role))
    out = []
    for rel, role in files:
        text = (redaccion / rel).read_text(encoding="utf-8", errors="replace")
        out.append({"rel": rel, "role": role, "stem": Path(rel).stem, "text": text, "sha256": _sha(text)})
    return out


def analyse(run_root: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """(files, blocks, fragments) of the source manuscript, in document order."""
    files = source_files(run_root)
    blocks, fragments = [], []
    for item in files:
        text, stem, role = item["text"], item["stem"], item["role"]
        item["units"] = []
        if role == "section":
            counters: dict = {}
            number = 0
            for unit in segment(text):
                item["units"].append(unit)
                if unit["kind"] == "block":
                    number += 1
                    body = text[unit["start"]:unit["end"]]
                    unit["id"] = f"{stem}-b{number:02d}"
                    blocks.append({"id": unit["id"], "file": item["rel"], "start": unit["start"],
                                   "end": unit["end"], "body": body, "digest": _sha(body),
                                   "lines": [text.count("\n", 0, unit["start"]) + 1,
                                             text.count("\n", 0, unit["end"]) + 1]})
                elif unit["kind"] == "heading":
                    fragments += _with_file(_fragments_in(text, stem, (unit["start"], unit["end"]), HEADINGS,
                                                          counters), item)
                else:
                    fragments += _with_file(_fragments_in(text, stem, (unit["start"], unit["end"]), ("caption",),
                                                          counters), item)
        elif role in ("main", "caption"):
            kinds = ("caption",) if role == "caption" else HEADINGS + ("title", "caption")
            region = None
            if role == "main" and "\\begin{document}" in text:
                region = (text.index("\\begin{document}"), len(text))
            fragments += _with_file(_fragments_in(text, stem, region, kinds, {}), item)
        elif role == "cover":
            fragments += _with_file(_cover_fragments(text, stem), item)
    return files, blocks, fragments


def _with_file(records: list[dict], item: dict) -> list[dict]:
    for record in records:
        record["file"] = item["rel"]
    return records


def _source_sha(files: list[dict]) -> str:
    return _sha("\n".join(f"{f['rel']} {f['sha256']}" for f in files))


# --- Glossary ----------------------------------------------------------------------------

def parse_term(term: str) -> dict:
    """`SOURCE=TARGET` declares the target form; a bare term stays as written."""
    source, _, target = term.partition("=")
    source, target = source.strip(), target.strip()
    return {"term": source, "target": target or source, "origin": "user"}


def derive_glossary(blocks: list[dict], fragments: list[dict]) -> list[dict]:
    """Terms the manuscript names: acronyms in parentheses and \\texttt/\\textsc
    names (advisory: an acronym may have an established equivalent, such as IA
    and AI) and the institutions it mentions (kept as written)."""
    entries: dict[str, dict] = {}
    texts = [b["body"] for b in blocks] + [f["source"] for f in fragments]
    for text in texts:
        for match in list(ACRONYM_RE.finditer(text)) + list(TERM_COMMAND_RE.finditer(text)):
            term = match.group(1).strip()
            if term and term not in entries and (match.re is TERM_COMMAND_RE or sum(c.isupper() for c in term) >= 2):
                entries[term] = {"term": term, "target": term if match.re is TERM_COMMAND_RE else None,
                                 "origin": "command" if match.re is TERM_COMMAND_RE else "acronym"}
    joined = "\n".join(texts)
    for name in INSTITUTIONS:
        if name in joined and name not in entries:
            entries[name] = {"term": name, "target": name, "origin": "institution"}
    return list(entries.values())


def _glossary(record: dict) -> list[dict]:
    return [e for e in record.get("glossary") or [] if isinstance(e, dict) and isinstance(e.get("term"), str)]


# --- Facts and the gate -------------------------------------------------------------------

def _normal_math(text: str) -> str:
    return re.sub(r"\s+|~", "", text).replace("{,}", ".")


def _normal_number(token: str) -> str:
    """1,500 / 1.500 / 1500 are one number, and so are 0,25 and 0.25."""
    figure = token.replace(",", ".")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", figure) and not figure.startswith("0"):
        figure = figure.replace(".", "")
    return figure


def extract_facts(tex: str) -> dict[str, Counter]:
    body = COMMENT_RE.sub("", tex)
    cites = [f"\\{m.group(1)}{{{key.strip()}}}" for m in CITE_RE.finditer(body)
             for key in m.group(3).split(",") if key.strip()]
    refs = [key.strip() for m in REF_RE.finditer(body) for key in m.group(1).split(",") if key.strip()]
    math = [_normal_math(m.group(3)) for m in DISPLAY_RE.finditer(body)]
    rest = DISPLAY_RE.sub(" ", body)
    math += [_normal_math(next(g for g in m.groups() if g is not None)) for m in INLINE_MATH_RE.finditer(rest)]
    # A citation keeps its locator ([p.~12]); keys, labels and file names are not numbers of the text.
    visible = CITE_RE.sub(lambda m: " " + " ".join(re.findall(r"\[([^\]]*)\]", m.group(2))) + " ", rest)
    visible = INLINE_MATH_RE.sub(" ", visible)
    visible = REF_RE.sub(" ", LABEL_RE.sub(" ", FILE_RE.sub(" ", visible)))
    visible = visible.replace(r"\$", " ").replace(r"\%", " % ")
    visible = DIGIT_GROUP_RE.sub("", visible)
    return {
        "citations": Counter(cites),
        "labels": Counter(LABEL_RE.findall(body)),
        "references": Counter(refs),
        "math": Counter(math),
        "numbers": Counter(_normal_number(n) for n in NUMBER_RE.findall(visible)),
        "files": Counter(m.group(1).strip() for m in FILE_RE.finditer(body)),
        "environments": Counter(m.group(1) for m in BEGIN_RE.finditer(body)),
        "items": Counter({"\\item": len(ITEM_RE.findall(body))}) if ITEM_RE.search(body) else Counter(),
        "cells": Counter({"&": len(CELL_RE.findall(body))}) if CELL_RE.search(body) else Counter(),
    }


def paragraph_count(tex: str) -> int:
    pieces = re.split(r"\n[ \t]*\n", COMMENT_RE.sub("", tex).strip())
    return sum(1 for piece in pieces if has_text(piece))


def compare_facts(source: str, translation: str, *, paragraphs: bool = True) -> list[str]:
    """Every fact of `source` that `translation` does not keep, one line each."""
    differences = []
    one, two = extract_facts(source), extract_facts(translation)
    for kind in one:
        missing = sorted((one[kind] - two[kind]).elements())
        added = sorted((two[kind] - one[kind]).elements())
        if missing or added:
            differences.append(f"{kind}: missing {missing}; added {added}")
    if paragraphs:
        counts = paragraph_count(source), paragraph_count(translation)
        if counts[0] != counts[1]:
            differences.append(f"paragraphs: source {counts[0]}, translation {counts[1]}")
    return differences


def _without_terms(text: str, glossary: list[dict]) -> str:
    for entry in sorted(glossary, key=lambda e: -len(e["term"])):
        for form in {entry["term"], entry.get("target") or entry["term"]}:
            if form:
                text = re.sub(re.escape(form), " ", text, flags=re.I)
    for name in INSTITUTIONS:
        text = re.sub(re.escape(name), " ", text, flags=re.I)
    return text


def language_counts(tex: str, glossary: list[dict]) -> dict[str, int]:
    words = [w.lower() for w in WORD_RE.findall(_without_terms(visible_text(tex), glossary))]
    return {lang: sum(1 for w in words if w in table) for lang, table in FUNCTION_WORDS.items()}


def reads_as_target(tex: str, target: str, glossary: list[dict], *, fragment: bool) -> bool:
    counts = language_counts(tex, glossary)
    other = counts["es" if target == "en" else "en"]
    mine = counts[target]
    if fragment:
        return not (other >= 1 and other > mine)
    return not (other >= 2 and other >= mine)


def _placeholders(tex: str) -> Counter:
    visible = COMMENT_RE.sub("", tex)
    return Counter({name: len(rx.findall(visible)) for name, rx in PLACEHOLDER_RES if rx.search(visible)})


def gate(translation: str, source: str, target: str, glossary: list[dict], what: str, *,
         fragment: bool = False) -> None:
    """The checks every stored translation passes; refuses before any write."""
    for number, line in enumerate(translation.splitlines(), 1):
        if line.lstrip().startswith(MARKER):
            raise Refused("CONTENT_CARRIES_MARKER", f"the text for {what} carries a marker line {number}: {line!r}")
    extra = _placeholders(translation) - _placeholders(source)
    if extra:
        raise Refused("TRANSLATION_PLACEHOLDER_TEXT",
                      f"the text for {what} carries placeholders the source does not: {dict(extra)}")
    unchanged = " ".join(translation.split()) == " ".join(source.split()) and any(c.islower() for c in source)
    if unchanged or not reads_as_target(translation, target, glossary, fragment=fragment):
        sample = " ".join(visible_text(translation).split())[:120]
        raise Refused(NOT_TARGET[target], f"the text stored for {what} does not read as {LANG_NAMES[target]}: "
                                          f"{sample!r}")
    differences = compare_facts(source, translation, paragraphs=not fragment)
    if fragment:
        stripped = translation.strip()
        if re.search(r"\n\s*\n", stripped):
            differences.append("a fragment is one paragraph: remove the blank line")
        if _brace_balance(stripped) != 0:
            differences.append("braces: the fragment's { and } do not balance")
    for entry in glossary:
        wanted = entry.get("target")
        if wanted and re.search(rf"(?<!\w){re.escape(entry['term'])}(?!\w)", source) and wanted not in translation:
            differences.append(f"glossary: {entry['term']!r} must appear as {wanted!r}")
    if differences:
        raise Refused("TRANSLATION_FIDELITY",
                      f"the text for {what} does not keep the source facts: " + " | ".join(differences))


def _brace_balance(text: str) -> int:
    depth = 0
    for i, char in enumerate(text):
        if char in "{}" and (i == 0 or text[i - 1] != "\\"):
            depth += 1 if char == "{" else -1
            if depth < 0:
                return depth
    return depth


# --- States ---------------------------------------------------------------------------------

def _block_states(run_root: Path, lang: str, blocks: list[dict], record: dict | None) -> list[dict]:
    stored = (record or {}).get("blocks") or {}
    folder = translation_dir(run_root, lang) / "bloques"
    rows = []
    for block in blocks:
        entry = stored.get(block["id"]) if isinstance(stored.get(block["id"]), dict) else None
        if entry is None or not entry.get("source_digest") or not (folder / f"{block['id']}.tex").is_file():
            state, entry = "missing", None
        else:
            state = "current" if entry["source_digest"] == block["digest"] else "stale"
        rows.append({"id": block["id"], "file": block["file"], "state": state,
                     "stored_at": entry.get("stored_at") if entry else None})
    return rows


def _fragment_entry(record: dict | None, fragment: dict) -> dict | None:
    """The stored record of `fragment`, or of the fragment that held its place
    (same file, kind and ordinal) before its source changed."""
    stored = (record or {}).get("fragments") or {}
    entry = stored.get(fragment["id"])
    if isinstance(entry, dict) and entry.get("translation"):
        return entry
    prefix = fragment["id"].rsplit("-", 1)[0] + "-"
    for key, entry in stored.items():
        if key.startswith(prefix) and isinstance(entry, dict) and entry.get("translation"):
            return entry
    return None


def _fragment_states(record: dict | None, fragments: list[dict]) -> list[dict]:
    rows = []
    for fragment in fragments:
        entry = _fragment_entry(record, fragment)
        state = "missing" if entry is None else (
            "current" if entry.get("translation_source_sha") == fragment["source_sha"] else "stale")
        rows.append({"id": fragment["id"], "file": fragment["file"], "kind": fragment["kind"], "state": state,
                     "stored_at": entry.get("stored_at") if entry else None})
    return rows


def _counts(rows: list[dict]) -> dict:
    return {"total": len(rows), **{state: sum(1 for r in rows if r["state"] == state) for state in STATES}}


def _style_summary(report: dict, name: str) -> dict:
    section = next((s for s in report.get("secciones") or [] if s.get("seccion") == name), None) or {}
    findings = [f for f in report.get("hallazgos") or [] if f.get("seccion") == name]
    return {"indice": section.get("indice"), "puntaje_estilo": section.get("puntaje_estilo"),
            "puntaje_flujo": section.get("puntaje_flujo"), "veredicto": section.get("veredicto"),
            "hallazgos": len(findings)}


def style_report(texts: dict[str, str], lang: str, glossary: list[dict], run_root: Path | None) -> dict:
    """The target language's style check over `texts` ({name: LaTeX}), the
    names being block ids; redundancy is searched across all of them."""
    engine = style_engine(lang)
    sections = [engine.Section(name, engine.latex_paragraphs(text)) for name, text in texts.items()]
    terms = list(engine.build_terms(None))
    for entry in glossary:
        for label in {entry["term"], entry.get("target") or entry["term"]}:
            words = tuple(engine.fold(w) for w in engine.tokenize(label))
            if words:
                terms.append(engine.Term(words, label, "glosario"))
    return engine.audit(sections, terms, "base", Path(run_root).name if run_root else "traduccion", None, True)


# --- Verbs --------------------------------------------------------------------------------------

def plan(run_root: Path, lang: str, *, terms: list[str] | None = None) -> dict:
    """Writes or refreshes `traduccion.json` and lists the pending work."""
    run_root = Path(run_root)
    source_lang = check_languages(run_root, lang)
    files, blocks, fragments = analyse(run_root)
    if not blocks:
        raise Refused("TRANSLATION_NO_SOURCE",
                      f"{_shown(run_root, run_root / 'redaccion' / 'sections')} holds no section with text; "
                      f"write the manuscript first")
    folder = translation_dir(run_root, lang)
    previous = _read_record(run_root, lang) or {}
    user = [e for e in previous.get("glossary_user") or [] if isinstance(e, dict) and e.get("term")]
    for term in terms or ():
        entry = parse_term(term)
        if entry["term"]:
            user = [e for e in user if e["term"] != entry["term"]] + [entry]
    glossary = [e for e in derive_glossary(blocks, fragments) if e["term"] not in {u["term"] for u in user}] + user

    stored = {k: v for k, v in (previous.get("blocks") or {}).items() if isinstance(v, dict)}
    bodies = {k: (folder / "bloques" / f"{k}.tex") for k in stored}
    by_digest: dict[tuple[str, str], str] = {}
    for key, entry in stored.items():
        if entry.get("source_digest") and bodies[key].is_file():
            by_digest.setdefault((entry.get("file"), entry["source_digest"]), key)
    # A block whose source text moved to another position keeps its translation.
    moves: dict[str, tuple[dict, str]] = {}
    for block in blocks:
        entry = stored.get(block["id"])
        if entry and entry.get("source_digest") == block["digest"] and bodies.get(block["id"], Path()).is_file():
            continue
        origin = by_digest.get((block["file"], block["digest"]))
        if origin and origin != block["id"]:
            moves[block["id"]] = (dict(stored[origin]), bodies[origin].read_text(encoding="utf-8"))

    record = {"schema": SCHEMA, "source_language": source_lang, "language": lang,
              "source_sha256": _source_sha(files), "files": {f["rel"]: f["sha256"] for f in files},
              "blocks": {}, "fragments": {}, "glossary": glossary, "glossary_user": user}
    if isinstance(previous.get("built"), dict):
        record["built"] = previous["built"]
    origins = {by_digest.get((b["file"], b["digest"])) for b in blocks if b["id"] in moves}
    for block in blocks:
        entry = moves[block["id"]][0] if block["id"] in moves else dict(stored.get(block["id"]) or {})
        if block["id"] in origins and block["id"] not in moves and entry.get("source_digest") != block["digest"]:
            # Its translation followed its text to another id: nothing is stored for the text here now.
            entry = {}
        entry.update({"file": block["file"], "lines": block["lines"]})
        entry.setdefault("source_digest", None)
        entry.setdefault("stored_at", None)
        record["blocks"][block["id"]] = entry
    for block_id, (_, body) in moves.items():
        _atomic_write(folder / "bloques" / f"{block_id}.tex", body.encode("utf-8"))
    rows = _block_states(run_root, lang, blocks, record)
    for row in rows:
        record["blocks"][row["id"]]["state"] = row["state"]
    fragment_rows = _fragment_states(previous, fragments)
    for fragment, row in zip(fragments, fragment_rows):
        entry = {"file": fragment["file"], "kind": fragment["kind"], "source": fragment["source"],
                 "source_sha": fragment["source_sha"], "state": row["state"]}
        old = _fragment_entry(previous, fragment)
        if old is not None:
            entry.update({k: old[k] for k in ("translation", "translation_source_sha", "stored_at") if k in old})
        record["fragments"][fragment["id"]] = entry
    _write_json(folder / "traduccion.json", record)

    work = [{"id": b["id"], "state": r["state"], "file": b["file"], "lines": b["lines"],
             "excerpt": " ".join(visible_text(b["body"]).split())[:160]} for b, r in zip(blocks, rows)]
    listed = [{"id": f["id"], "kind": f["kind"], "file": f["file"], "state": r["state"], "source": f["source"]}
              for f, r in zip(fragments, fragment_rows)]
    return {"ok": True, "lang": lang, "source_language": source_lang,
            "translation": _shown(run_root, folder / "traduccion.json"), "blocks": work, "counts": _counts(rows),
            "fragments": listed, "fragment_counts": _counts(fragment_rows), "glossary": glossary,
            "moved": sorted(moves)}


def _find_block(blocks: list[dict], block_id: str, run_root: Path) -> dict:
    block = next((b for b in blocks if b["id"] == block_id), None)
    if block is None:
        raise Refused("BLOCK_UNKNOWN", f"no block {block_id!r} in {_shown(run_root, run_root / 'redaccion')}; "
                                       f"`traducir.py plan` lists the current ids")
    return block


def _find_fragment(fragments: list[dict], fragment_id: str, run_root: Path) -> dict:
    fragment = next((f for f in fragments if f["id"] == fragment_id), None)
    if fragment is None:
        raise Refused("FRAGMENT_UNKNOWN", f"no fragment {fragment_id!r} in {_shown(run_root, run_root / 'redaccion')}"
                                          f"; `traducir.py plan` lists the current ids")
    return fragment


def _read_translation(file: Path, what: str) -> str:
    try:
        text = Path(file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Refused("TRANSLATION_UNREADABLE", f"{file}: {exc}")
    if not text.strip():
        raise Refused("TRANSLATION_EMPTY", f"{file} holds no text for {what}")
    return text


def show(run_root: Path, lang: str, *, block_id: str | None = None, fragment_id: str | None = None) -> dict:
    """Read-only: the source text of one block or fragment, the glossary, the
    stored translation and its last style findings, for the translator."""
    run_root = Path(run_root)
    source_lang = check_languages(run_root, lang)
    record = _require_record(run_root, lang)
    _, blocks, fragments = analyse(run_root)
    folder = translation_dir(run_root, lang)
    result = {"ok": True, "lang": lang, "source_language": source_lang, "glossary": _glossary(record)}
    if block_id:
        block = _find_block(blocks, block_id, run_root)
        state = _block_states(run_root, lang, [block], record)[0]["state"]
        body = folder / "bloques" / f"{block_id}.tex"
        result.update({"id": block_id, "kind": "block", "file": block["file"], "lines": block["lines"],
                       "state": state, "source": block["body"],
                       "translation": body.read_text(encoding="utf-8") if body.is_file() else None,
                       "findings": _block_findings(run_root, lang, block_id)})
    else:
        fragment = _find_fragment(fragments, fragment_id or "", run_root)
        entry = _fragment_entry(record, fragment)
        result.update({"id": fragment["id"], "kind": fragment["kind"], "file": fragment["file"],
                       "state": _fragment_states(record, [fragment])[0]["state"], "source": fragment["source"],
                       "translation": entry.get("translation") if entry else None, "findings": []})
    return result


def _block_findings(run_root: Path, lang: str, block_id: str) -> list[dict]:
    try:
        audit_report = json.loads((translation_dir(run_root, lang) / "auditoria.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [f for f in audit_report.get("findings") or [] if isinstance(f, dict) and f.get("seccion") == block_id]


def store(run_root: Path, lang: str, block_id: str, file: Path) -> dict:
    """Gates one block's translation and stores it against the block's digest."""
    run_root = Path(run_root)
    check_languages(run_root, lang)
    record = _require_record(run_root, lang)
    _, blocks, _ = analyse(run_root)
    block = _find_block(blocks, block_id, run_root)
    text = _read_translation(file, f"block {block_id!r}")
    glossary = _glossary(record)
    gate(text, block["body"], lang, glossary, f"block {block_id!r}")
    body = text.strip("\n") + "\n"
    summary = _style_summary(style_report({block_id: body}, lang, glossary, run_root), block_id)
    now = _now()
    record.setdefault("blocks", {})[block_id] = {
        "file": block["file"], "lines": block["lines"], "source_digest": block["digest"], "state": "current",
        "stored_at": now, "translation_sha256": _sha(body), "style": summary}
    folder = translation_dir(run_root, lang)
    _atomic_write(folder / "bloques" / f"{block_id}.tex", body.encode("utf-8"))
    _write_json(folder / "traduccion.json", record)
    return {"ok": True, "lang": lang, "id": block_id, "state": "current", "stored_at": now,
            "path": _shown(run_root, folder / "bloques" / f"{block_id}.tex"), "style": summary}


def store_fragment(run_root: Path, lang: str, fragment_id: str, file: Path) -> dict:
    """Gates one fragment's translation and stores it in `traduccion.json`."""
    run_root = Path(run_root)
    check_languages(run_root, lang)
    record = _require_record(run_root, lang)
    _, _, fragments = analyse(run_root)
    fragment = _find_fragment(fragments, fragment_id, run_root)
    text = _read_translation(file, f"fragment {fragment_id!r}")
    gate(text, fragment["source"], lang, _glossary(record), f"fragment {fragment_id!r}", fragment=True)
    now = _now()
    stored = record.setdefault("fragments", {})
    prefix = fragment_id.rsplit("-", 1)[0] + "-"
    for key in [k for k in stored if k.startswith(prefix) and k != fragment_id]:
        del stored[key]
    stored[fragment_id] = {"file": fragment["file"], "kind": fragment["kind"], "source": fragment["source"],
                           "source_sha": fragment["source_sha"], "state": "current", "translation": text.strip(),
                           "translation_source_sha": fragment["source_sha"], "stored_at": now}
    _write_json(translation_dir(run_root, lang) / "traduccion.json", record)
    return {"ok": True, "lang": lang, "id": fragment_id, "kind": fragment["kind"], "state": "current",
            "stored_at": now, "translation": text.strip()}


def _last_store(record: dict | None) -> str | None:
    stamps = [e.get("stored_at") for group in ("blocks", "fragments")
              for e in ((record or {}).get(group) or {}).values() if isinstance(e, dict) and e.get("stored_at")]
    return max(stamps) if stamps else None


def audit(run_root: Path, lang: str) -> dict:
    """The target language's style check over the stored blocks and the
    fidelity of each stored text against the current source; writes `auditoria.json`."""
    run_root = Path(run_root)
    source_lang = check_languages(run_root, lang)
    record = _require_record(run_root, lang)
    _, blocks, fragments = analyse(run_root)
    folder = translation_dir(run_root, lang)
    stored = {b["id"]: (folder / "bloques" / f"{b['id']}.tex").read_text(encoding="utf-8")
              for b in blocks if (folder / "bloques" / f"{b['id']}.tex").is_file()}
    if not stored:
        raise Refused("TRANSLATION_NOTHING_STORED",
                      f"no block is stored under {_shown(run_root, folder / 'bloques')}; run `traducir.py store` first")
    glossary = _glossary(record)
    report = style_report(stored, lang, glossary, run_root)
    states = {r["id"]: r["state"] for r in _block_states(run_root, lang, blocks, record)}
    source = {b["id"]: b["body"] for b in blocks}
    fidelity = [{"id": key, "state": states.get(key), "differences": compare_facts(source[key], text)}
                for key, text in stored.items()]
    for fragment in fragments:
        entry = _fragment_entry(record, fragment)
        if entry:
            fidelity.append({"id": fragment["id"], "state": _fragment_states(record, [fragment])[0]["state"],
                             "differences": compare_facts(fragment["source"], entry["translation"], paragraphs=False)})
    for item in fidelity:
        item["ok"] = not item["differences"]
    document = {key: report.get(key) for key in ("indice", "puntaje_estilo", "puntaje_flujo", "veredicto")}
    document["palabras"] = (report.get("metricas") or {}).get("palabras")
    result = {"schema": AUDIT_SCHEMA, "ok": True, "lang": lang, "source_language": source_lang,
              "checker": "scripts/estilo_en.py" if lang == "en" else "scripts/estilo_es.py",
              "generated_at": _now(), "stored_through": _last_store(record), "notice": report.get("aviso"),
              "document": document,
              "blocks": [{"id": key, "state": states.get(key), **_style_summary(report, key)} for key in stored],
              "findings": report.get("hallazgos") or [], "fidelity": fidelity}
    _write_json(folder / "auditoria.json", result)
    return result


def _relocate(text: str, redaccion: Path) -> str:
    """The built files sit two folders under `redaccion/`: the bibliography,
    graphics paths and local styles resolve from there."""
    def up(entry: str) -> str:
        entry = entry.strip()
        return entry if not entry or entry.startswith(("/", "../", "~")) or re.match(r"[A-Za-z]:", entry) \
            else "../../" + entry

    text = re.sub(r"\\bibliography\{([^}]*)\}",
                  lambda m: "\\bibliography{" + ",".join(up(e) for e in m.group(1).split(",")) + "}", text)
    text = re.sub(r"\\addbibresource(\[[^\]]*\])?\{([^}]*)\}",
                  lambda m: f"\\addbibresource{m.group(1) or ''}{{{up(m.group(2))}}}", text)
    text = re.sub(r"\\graphicspath\{((?:\{[^}]*\})*)\}",
                  lambda m: "\\graphicspath{" + "".join("{" + up(d) + "}" for d in re.findall(r"\{([^}]*)\}",
                                                                                            m.group(1))) + "}", text)
    return re.sub(r"\\bibliographystyle\{([^}]*)\}",
                  lambda m: "\\bibliographystyle{" + (up(m.group(1)) if (redaccion / f"{m.group(1)}.bst").is_file()
                                                       else m.group(1)) + "}", text)


def _after_documentclass(text: str, line: str) -> str:
    match = re.search(r"^\\documentclass(?:\[[^\]]*\])?\{[^}]*\}[^\n]*\n?", text, re.M)
    if match is None:
        return line + text
    head = text[:match.end()] if text[:match.end()].endswith("\n") else text[:match.end()] + "\n"
    return head + line + text[match.end():]


def build(run_root: Path, lang: str) -> dict:
    """Writes the translated manuscript under `traducciones/<lang>/`; refuses
    while any block or fragment is missing or stale. Never writes `redaccion/`'s own files."""
    run_root = Path(run_root)
    source_lang = check_languages(run_root, lang)
    record = _require_record(run_root, lang)
    files, blocks, fragments = analyse(run_root)
    rows = _block_states(run_root, lang, blocks, record) + _fragment_states(record, fragments)
    pending = [f"{r['id']} ({r['state']})" for r in rows if r["state"] != "current"]
    if pending:
        raise Refused("TRANSLATION_INCOMPLETE",
                      f"{len(pending)} block(s) or fragment(s) are not current; store each one first: "
                      + ", ".join(pending[:40]) + (" …" if len(pending) > 40 else ""))
    folder = translation_dir(run_root, lang)
    redaccion = run_root / "redaccion"
    by_file: dict[str, list[tuple[int, int, str]]] = {}
    for block in blocks:
        body = (folder / "bloques" / f"{block['id']}.tex").read_text(encoding="utf-8").strip("\n")
        by_file.setdefault(block["file"], []).append((block["start"], block["end"], body))
    for fragment in fragments:
        by_file.setdefault(fragment["file"], []).append(
            (fragment["start"], fragment["end"], _fragment_entry(record, fragment)["translation"]))
    outputs: dict[str, str] = {}
    for item in files:
        text, cursor, out = item["text"], 0, []
        for start, stop, replacement in sorted(by_file.get(item["rel"], [])):
            out += [text[cursor:start], replacement]
            cursor = stop
        out.append(text[cursor:])
        built = "".join(out)
        if item["role"] == "main":
            try:
                built = language_module().switch_main_tex(built, source_lang, lang)
            except ValueError as exc:
                raise Refused("TRANSLATION_PREAMBLE", f"redaccion/main.tex: {exc}")
            built = _after_documentclass(built, "\\makeatletter\\def\\input@path{{../../}}\\makeatother\n")
        header = (f"{MARKER}: built from redaccion/{item['rel']} ({source_lang} -> {lang}); "
                  f"edit the canonical file and run traducir.py build again.\n")
        outputs[item["rel"]] = header + _relocate(built, redaccion)
    stale_sections = folder / "sections"
    if stale_sections.is_dir():
        for path in stale_sections.glob("*.tex"):
            if f"sections/{path.name}" not in outputs:
                path.unlink()
    for rel, text in outputs.items():
        _atomic_write(folder / rel, text.encode("utf-8"))
    record["built"] = {"at": _now(), "source_sha256": _source_sha(files),
                       "blocks": {b["id"]: b["digest"] for b in blocks}, "fragments": [f["id"] for f in fragments]}
    _write_json(folder / "traduccion.json", record)
    return {"ok": True, "lang": lang, "source_language": source_lang,
            "main_tex": _shown(run_root, folder / "main.tex"), "files": len(outputs), "blocks": len(blocks),
            "fragments": len(fragments), "compile": f"traducir.py compile --lang {lang}"}


def _built(run_root: Path, lang: str, files: list[dict], rows: list[dict], record: dict | None) -> bool:
    built = (record or {}).get("built") if isinstance((record or {}).get("built"), dict) else {}
    last = _last_store(record) or ""
    return bool((translation_dir(run_root, lang) / "main.tex").is_file()
                and built.get("source_sha256") == _source_sha(files)
                and all(r["state"] == "current" for r in rows) and (built.get("at") or "") >= last)


def status(run_root: Path, lang: str) -> dict:
    """Read-only: the state of every block and fragment, whether the built
    manuscript and its PDF match the current source, and the last audit."""
    run_root = Path(run_root)
    source_lang = check_languages(run_root, lang)
    files, blocks, fragments = analyse(run_root)
    record = _read_record(run_root, lang)
    rows = _block_states(run_root, lang, blocks, record)
    fragment_rows = _fragment_states(record, fragments)
    folder = translation_dir(run_root, lang)
    built = _built(run_root, lang, files, rows + fragment_rows, record)
    pdf = folder / "main.pdf"
    main_tex = folder / "main.tex"
    pdf_current = built and pdf.is_file() and pdf.stat().st_mtime_ns >= main_tex.stat().st_mtime_ns
    last = None
    try:
        saved = json.loads((folder / "auditoria.json").read_text(encoding="utf-8"))
        last = {"generated_at": saved.get("generated_at"), "stored_through": saved.get("stored_through"),
                "document": saved.get("document"), "checker": saved.get("checker"),
                "fidelity_failures": sum(1 for f in saved.get("fidelity") or [] if not f.get("ok")),
                "findings": len(saved.get("findings") or [])}
        last["fresh"] = (saved.get("stored_through") or "") >= (_last_store(record) or "")
    except (OSError, ValueError, AttributeError):
        last = None
    return {"ok": True, "lang": lang, "source_language": source_lang, "planned": record is not None,
            "blocks": rows, "counts": _counts(rows), "fragments": fragment_rows,
            "fragment_counts": _counts(fragment_rows), "built": built,
            "main_tex": _shown(run_root, main_tex) if main_tex.is_file() else None,
            "pdf": _shown(run_root, pdf) if pdf.is_file() else None, "pdf_current": bool(pdf_current),
            "audit": last, "last_store": _last_store(record)}


def compile_translation(run_root: Path, lang: str, timeout: int = 900) -> dict:
    """Compiles the built translation to `traducciones/<lang>/main.pdf`
    (latexmk, as redaccion/build.sh does; pdflatex and bibtex without it)."""
    run_root = Path(run_root)
    check_languages(run_root, lang)
    state = status(run_root, lang)
    if not state["built"]:
        raise Refused("TRANSLATION_NOT_BUILT", f"the translation to {lang} is not built for the current source; "
                                               f"run `traducir.py build --lang {lang}` first")
    folder = translation_dir(run_root, lang)
    if shutil.which("latexmk"):
        commands = [["latexmk", "-f", "-g", "-pdf", "-pdflatex=pdflatex -interaction=nonstopmode %O %S",
                     "-bibtex", "main.tex"]]
    elif shutil.which("pdflatex"):
        once = ["pdflatex", "-interaction=nonstopmode", "main.tex"]
        commands = [once, ["bibtex", "main"], once, once]
    else:
        raise Refused("TRANSLATION_NO_LATEX", "neither latexmk nor pdflatex is on PATH")
    output = []
    for command in commands:
        try:
            proc = subprocess.run(command, cwd=folder, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=timeout)
            output.append((proc.stdout or "") + (proc.stderr or ""))
        except subprocess.TimeoutExpired:
            raise Refused("TRANSLATION_COMPILE_TIMEOUT", f"compiling took more than {timeout} s")
    pdf = folder / "main.pdf"
    log = folder / "main.log"
    errors = 0
    if log.is_file():
        errors = sum(1 for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
                     if line.startswith("!"))
    fresh = pdf.is_file() and pdf.stat().st_mtime_ns >= (folder / "main.tex").stat().st_mtime_ns
    tail = "\n".join("".join(output).strip().splitlines()[-40:])
    if not fresh or errors:
        raise Refused("TRANSLATION_COMPILE_FAILED",
                      f"{'no main.pdf was produced' if not fresh else f'LaTeX reported {errors} error(s)'}; "
                      f"see {_shown(run_root, log)}\n{tail}")
    stat = pdf.stat()
    return {"ok": True, "lang": lang, "pdf": _shown(run_root, pdf), "version": f"{stat.st_mtime_ns}-{stat.st_size}",
            "log_tail": tail}


# --- CLI ----------------------------------------------------------------------------------------

def _active_run() -> Path:
    pointer = Path("proposals/.current-run")
    if not pointer.is_file():
        raise Refused("TRANSLATION_NO_RUN", "no RUN_ROOT given and proposals/.current-run does not exist")
    return Path("proposals", pointer.read_text(encoding="utf-8").strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    verbs = parser.add_subparsers(dest="verb", required=True)
    for name in ("plan", "show", "store", "store-fragment", "audit", "build", "compile", "status"):
        sub = verbs.add_parser(name)
        sub.add_argument("run_root", nargs="?", metavar="RUN_ROOT")
        sub.add_argument("--lang", required=True, choices=LANGS, help="target language")
        if name == "plan":
            sub.add_argument("--term", action="append", default=[],
                             help="glossary term kept as written, or SOURCE=TARGET")
        if name in ("show", "store"):
            sub.add_argument("--block", required=name == "store")
        if name in ("show", "store-fragment"):
            sub.add_argument("--fragment", required=name == "store-fragment")
        if name in ("store", "store-fragment"):
            sub.add_argument("--file", required=True, type=Path)
        sub.add_argument("--json", action="store_true", help="accepted for symmetry: output is always JSON")
    args = parser.parse_args(argv)
    try:
        run_root = Path(args.run_root) if args.run_root else _active_run()
        if args.verb == "plan":
            result = plan(run_root, args.lang, terms=args.term)
        elif args.verb == "show":
            if bool(args.block) == bool(args.fragment):
                parser.error("show needs exactly one of --block or --fragment")
            result = show(run_root, args.lang, block_id=args.block, fragment_id=args.fragment)
        elif args.verb == "store":
            result = store(run_root, args.lang, args.block, args.file)
        elif args.verb == "store-fragment":
            result = store_fragment(run_root, args.lang, args.fragment, args.file)
        elif args.verb == "audit":
            result = audit(run_root, args.lang)
        elif args.verb == "build":
            result = build(run_root, args.lang)
        elif args.verb == "compile":
            result = compile_translation(run_root, args.lang)
        else:
            result = status(run_root, args.lang)
    except Refused as refusal:
        print(json.dumps({"ok": False, "code": refusal.code, "message": refusal.message}, ensure_ascii=False,
                         indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
