#!/usr/bin/env python3
"""Read-only view of the Anexo 2 chapters of an SGR run: state, rule, lexicon and rubric (flujo SGR only).

For each chapter of the Anexo 2 (Conv 54, 31 chapters) the view lists the
Morfeo sections that fill it with their state and findings, the writing rule
of the chapter, its lexicon entries and the rubric subcriteria that read it.
Schema `morfeo.anexo2-sgr/v1`:

    {schema, flujo:"sgr", fuente_capitulos:"artefactos/estructura_tdr.json"|"scripts/sgr/lexico_sgr.json",
     fuente_reglas:"docs/sgr/patrones_redaccion_sgr.md"|null, rubrica:"conv54"|null,
     resumen:{capitulos, por_estado:{falta, incompleto, desactualizado, listo}, palabras},
     capitulos:[{numero, titulo, estado, palabras,
                 secciones:[{stem, existe, palabras, origen:"generado"|"manual"|null, script|null,
                             estado:"falta"|"borrador"|"redactado"|"generado"|"desactualizado",
                             hallazgos:{error, warning, info}, guia:"§N"|"A<N>"}],
                 regla:{proposito, estructura, extension, aperturas:[str], evitar:[str], fuente}|null,
                 lexico:{favorecida, desaconsejada, prohibida}, criterios:[{id, nombre, max}],
                 hallazgos:[{severidad, codigo, mensaje, seccion}]}]}

Chapters come from artefactos/estructura_tdr.json placed for the SGR flow
(ensamblar_main.placed_chapters) when it exists and is valid, else from
`mapa_capitulos` of scripts/sgr/lexico_sgr.json. `diag_*` files are not
sections. Section state: `falta` without a file; `generado` when its first
lines carry `% GENERADO por scripts/<x>.py`, `desactualizado` when check_run
also reports a `*-anexo-desactualizado` finding on it; otherwise `borrador`
(50 words or fewer once `%` comments are stripped, the dashboard heuristic;
16_bibliografia is never a draft) or `redactado`. Chapter state: `falta`
when no section exists, `desactualizado` when a section is stale,
`incompleto` when a section is missing or a draft, else `listo`.

The rule of a chapter is parsed from section «## 2.» of
docs/sgr/patrones_redaccion_sgr.md (`### N. TITLE` headings and the bullets
Propósito, Estructura, Extensión, Aperturas favorecidas, Evitar and Fuente,
label variants such as «Propósito (plantilla)» included) and matched by title
with accents, case and punctuation ignored (equal, or one a prefix of the
other); lexicon chapters also match by number. String fields of a rule are
null when the bullet is missing; nested items are appended as «- item» lines.
Lexicon counts come from `secciones[stem]` of the lexicon; rubric criteria
are the subcriteria of the run's rubric (juez_sgr.resolve_rubric: the copy in
artefactos/juez/rubrica.json, else TdR detection) whose `evidencia` lists a
stem of the chapter. Findings come from one check_run pass (non-final, flow
sgr) and one estilo_sgr pass with its own severities (advertencia -> warning),
mapped to sections by file stem; each chapter lists at most 20, errors first.

Commands:
  datos RUN_ROOT [--json]
      One line per chapter (number, state, title, sections with their state),
      or the JSON view with --json. A base run is refused. Writes nothing.

Exit codes: 0 ok, 2 bad input (missing run, base flow). Standard library
only; check_run, ensamblar_main, estilo_sgr and juez_sgr come from this
folder (imported defensively). The dashboard imports `vista`.
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path

SCHEMA = "morfeo.anexo2-sgr/v1"
HERE = Path(__file__).resolve().parent
LEXICON_FILE = HERE / "sgr" / "lexico_sgr.json"
RULES_FILE = HERE.parent / "docs" / "sgr" / "patrones_redaccion_sgr.md"
LEXICON_SOURCE = "scripts/sgr/lexico_sgr.json"
RULES_SOURCE = "docs/sgr/patrones_redaccion_sgr.md"
STRUCTURE_FILE = Path("artefactos") / "estructura_tdr.json"
SECTIONS_DIR = Path("redaccion") / "sections"

DRAFT_MAX_WORDS = 50
NEVER_DRAFT = frozenset({"16_bibliografia"})
MAX_CHAPTER_FINDINGS = 20
CHAPTER_STATES = ("falta", "incompleto", "desactualizado", "listo")
LEXICON_TYPES = ("favorecida", "desaconsejada", "prohibida")
SEVERITIES = ("error", "warning", "info")
SEVERITY_MAP = {"error": "error", "warning": "warning", "advertencia": "warning", "info": "info"}
STYLE_PREFIX = "sgr-estilo"
STALE_SUFFIX = "-anexo-desactualizado"

GENERATED_RE = re.compile(r"^\s*%\s*GENERADO por (scripts/[A-Za-z0-9_./-]+\.py)")
HEADER_LINES = 3
RULES_SECTION_RE = re.compile(r"^##\s+2\.(\s|$)")
RULE_HEADING_RE = re.compile(r"^###\s+(\d+)\.\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^- \*\*(.+?)\*\*\s*(.*)$")
NESTED_RE = re.compile(r"^\s{2,}- (.*)$")
RULE_KEYS = {"proposito": "proposito", "estructura": "estructura", "extension": "extension",
             "aperturas": "aperturas", "evitar": "evitar", "fuente": "fuente"}
LIST_KEYS = ("aperturas", "evitar")


class InputError(Exception):
    pass


@functools.lru_cache(maxsize=None)
def _sibling(name: str):
    """scripts/<name>.py of this folder, loaded under a private module name; None when missing."""
    path = HERE / f"{name}.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"_anexo2_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _flujo(run: Path) -> str:
    module = _sibling("check_run")
    return module.detect_flujo(run) if module is not None else "base"


def _fold(text) -> str:
    """Lowercase, accents and punctuation removed, spaces collapsed."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain).split())


def _is_prefix(short: str, long: str) -> bool:
    return bool(short) and long.startswith(short) and (len(long) == len(short) or long[len(short)] == " ")


# --- Chapters -----------------------------------------------------------------

def _chapters(run: Path, lexicon: dict) -> tuple[list[dict], str]:
    """([{numero, titulo, archivos}], source): the placed structure when valid, else the lexicon map."""
    structure = _read_json(run / STRUCTURE_FILE)
    assembler = _sibling("ensamblar_main")
    if isinstance(structure, dict) and assembler is not None:
        try:
            assembler.validate(structure)
        except assembler.InputError:
            structure = None
        if structure is not None:
            placed = assembler.placed_chapters(structure, "sgr")
            return ([{"numero": c["numero"], "titulo": c.get("titulo") or "", "archivos": c["archivos"]}
                     for c in placed], STRUCTURE_FILE.as_posix())
    mapa = lexicon.get("mapa_capitulos") if isinstance(lexicon, dict) else None
    if not isinstance(mapa, list) or not mapa:
        raise InputError(f"no hay {STRUCTURE_FILE.as_posix()} válido ni mapa_capitulos en {LEXICON_SOURCE}")
    chapters = [{"numero": c["capitulo"], "titulo": str(c.get("titulo") or ""),
                 "archivos": [s for s in c.get("secciones") or [] if isinstance(s, str)]}
                for c in mapa if isinstance(c, dict) and isinstance(c.get("capitulo"), int)]
    return chapters, LEXICON_SOURCE


# --- Rules --------------------------------------------------------------------

def parse_rules(text: str) -> list[dict]:
    """[{numero, titulo, regla}] of the `### N. TITLE` chapters under «## 2.»."""
    rules: list[dict] = []
    inside = False
    current = None  # (fields, key of the open bullet)
    key = None
    for line in text.splitlines():
        if line.startswith("## "):
            inside = bool(RULES_SECTION_RE.match(line))
            key = None
            continue
        if not inside:
            continue
        heading = RULE_HEADING_RE.match(line)
        if heading:
            current = {"inline": {}, "nested": {}}
            rules.append({"numero": int(heading.group(1)), "titulo": heading.group(2), "_raw": current})
            key = None
            continue
        if current is None:
            continue
        bullet = BULLET_RE.match(line)
        if bullet:
            word = re.match(r"[a-z]+", _fold(bullet.group(1)))
            key = RULE_KEYS.get(word.group(0)) if word else None
            if key is not None and key in current["inline"]:
                key = None  # the first bullet of each kind wins
            if key is not None:
                current["inline"][key] = bullet.group(2).strip()
                current["nested"][key] = []
            continue
        nested = NESTED_RE.match(line)
        if nested and key is not None:
            current["nested"][key].append(nested.group(1).strip())
        elif line.strip() and not nested:
            key = None
    for rule in rules:
        raw = rule.pop("_raw")
        regla = {}
        for name in ("proposito", "estructura", "extension", "aperturas", "evitar", "fuente"):
            inline, items = raw["inline"].get(name), raw["nested"].get(name) or []
            if name in LIST_KEYS:
                regla[name] = ([inline] if inline else []) + items
            elif inline is None:
                regla[name] = None
            else:
                regla[name] = "\n".join(([inline] if inline else []) + [f"- {item}" for item in items]) or None
        rule["regla"] = regla
    return rules


def _rules() -> list[dict] | None:
    try:
        return parse_rules(Path(RULES_FILE).read_text(encoding="utf-8"))
    except OSError:
        return None


def _match_rule(rules: list[dict], titulo: str, numero: int, by_number: bool) -> dict | None:
    title = _fold(titulo)
    if title:
        folded = [(_fold(r["titulo"]), r) for r in rules]
        for other, rule in folded:
            if other == title:
                return rule["regla"]
        for other, rule in folded:
            if _is_prefix(title, other) or _is_prefix(other, title):
                return rule["regla"]
    if by_number:
        return next((r["regla"] for r in rules if r["numero"] == numero), None)
    return None


# --- Sections and findings ----------------------------------------------------

def _severity(value) -> str:
    return SEVERITY_MAP.get(str(value or "").lower(), "warning")


def _tex_stem(path) -> str | None:
    if not path:
        return None
    candidate = Path(str(path))
    return candidate.stem if candidate.suffix == ".tex" else None


def _findings(run: Path) -> tuple[dict[str, list[dict]], set[str]]:
    """({stem: [{severidad, codigo, mensaje, seccion}]}, stale stems) from check_run and estilo_sgr."""
    by_stem: dict[str, list[dict]] = {}
    stale: set[str] = set()
    checker = _sibling("check_run")
    found: list[dict] = []
    if checker is not None:
        try:
            found = checker.run_checks(run, final=False, flujo="sgr").findings
        except Exception:  # a broken check never hides the view
            found = []
    for f in found:
        code = str(f.get("code") or "")
        stem = _tex_stem(f.get("file"))
        if code.startswith(STYLE_PREFIX) or stem is None:
            continue  # style findings come from the estilo_sgr pass below, with their own severity
        if code.endswith(STALE_SUFFIX):
            stale.add(stem)
        by_stem.setdefault(stem, []).append({"severidad": _severity(f.get("severity")), "codigo": code,
                                             "mensaje": str(f.get("message") or ""), "seccion": stem})
    style = _sibling("estilo_sgr")
    style_found: list[dict] = []
    if style is not None:
        try:
            style_found = style.findings(run) or []
        except Exception:
            style_found = []
    for f in style_found:
        stem = _tex_stem(f.get("archivo"))
        if stem is None:
            continue
        message = str(f.get("message") or "")
        if f.get("extracto"):
            message += f" «{f['extracto']}»"
        by_stem.setdefault(stem, []).append({"severidad": _severity(f.get("severity")),
                                             "codigo": str(f.get("code") or STYLE_PREFIX), "mensaje": message,
                                             "seccion": stem})
    return by_stem, stale


def _guide_key(stem: str) -> str | None:
    match = re.match(r"^(\d+)_", stem)
    if not match:
        return None
    number = int(match.group(1))
    return f"A{number}" if number >= 19 else f"§{number}"


def _section(run: Path, stem: str, findings: list[dict], stale: set[str]) -> dict:
    path = run / SECTIONS_DIR / f"{stem}.tex"
    counts = {s: sum(1 for f in findings if f["severidad"] == s) for s in SEVERITIES}
    entry = {"stem": stem, "existe": False, "palabras": 0, "origen": None, "script": None, "estado": "falta",
             "hallazgos": counts, "guia": _guide_key(stem)}
    if not path.is_file():
        return entry
    raw = path.read_text(encoding="utf-8", errors="replace")
    words = len(re.sub(r"%.*", "", raw).split())
    script = next((m.group(1) for m in (GENERATED_RE.match(l) for l in raw.splitlines()[:HEADER_LINES]) if m),
                  None)
    if script is not None:
        state = "desactualizado" if stem in stale else "generado"
    elif words <= DRAFT_MAX_WORDS and stem not in NEVER_DRAFT:
        state = "borrador"
    else:
        state = "redactado"
    entry.update(existe=True, palabras=words, origen="generado" if script else "manual", script=script,
                 estado=state)
    return entry


def _chapter_state(sections: list[dict]) -> str:
    if not any(s["existe"] for s in sections):
        return "falta"
    if any(s["estado"] == "desactualizado" for s in sections):
        return "desactualizado"
    if any(s["estado"] in ("falta", "borrador") for s in sections):
        return "incompleto"
    return "listo"


def _rubric(run: Path) -> dict | None:
    juez = _sibling("juez_sgr")
    if juez is None:
        return None
    try:
        rubric, _, _ = juez.resolve_rubric(run, None)
    except (juez.JuezError, OSError, ValueError):
        return None
    return rubric if isinstance(rubric, dict) else None


def _criteria(rubric: dict | None, stems: list[str]) -> list[dict]:
    if rubric is None:
        return []
    out: list[dict] = []
    for _, sub in _sibling("juez_sgr").iter_subcriteria(rubric):
        evidence = sub.get("evidencia") if isinstance(sub, dict) else None
        if isinstance(evidence, list) and set(evidence) & set(stems) and sub.get("id") not in [c["id"] for c in out]:
            out.append({"id": sub.get("id"), "nombre": sub.get("nombre"), "max": sub.get("max")})
    return out


def _lexicon_counts(lexicon: dict, stems: list[str]) -> dict:
    counts = dict.fromkeys(LEXICON_TYPES, 0)
    sections = lexicon.get("secciones") if isinstance(lexicon, dict) else None
    for stem in stems:
        for entry in (sections or {}).get(stem) or []:
            if isinstance(entry, dict) and entry.get("tipo") in counts:
                counts[entry["tipo"]] += 1
    return counts


# --- View ---------------------------------------------------------------------

def vista(run: Path) -> dict:
    """The Anexo 2 view of an SGR run (schema morfeo.anexo2-sgr/v1); InputError outside the SGR flow."""
    run = Path(run)
    if not run.is_dir():
        raise InputError(f"no existe la corrida {run}")
    if _flujo(run) != "sgr":
        raise InputError("la vista del Anexo 2 solo existe en el flujo SGR; esta corrida es del flujo base")
    lexicon = _read_json(LEXICON_FILE) or {}
    chapters, source = _chapters(run, lexicon)
    rules = _rules()
    rubric = _rubric(run)
    by_stem, stale = _findings(run)
    rank = {s: n for n, s in enumerate(SEVERITIES)}

    out_chapters: list[dict] = []
    words_by_stem: dict[str, int] = {}
    for chapter in chapters:
        stems: list[str] = []
        for name in chapter["archivos"]:
            if not name.startswith("diag_") and name not in stems:
                stems.append(name)
        sections = [_section(run, stem, by_stem.get(stem, []), stale) for stem in stems]
        for section in sections:
            words_by_stem[section["stem"]] = section["palabras"]
        findings = sorted((f for stem in stems for f in by_stem.get(stem, [])), key=lambda f: rank[f["severidad"]])
        regla = None
        if rules is not None:
            regla = _match_rule(rules, chapter["titulo"], chapter["numero"], source == LEXICON_SOURCE)
        out_chapters.append({
            "numero": chapter["numero"],
            "titulo": chapter["titulo"],
            "estado": _chapter_state(sections),
            "palabras": sum(s["palabras"] for s in sections),
            "secciones": sections,
            "regla": dict(regla, aperturas=list(regla["aperturas"]), evitar=list(regla["evitar"])) if regla else None,
            "lexico": _lexicon_counts(lexicon, stems),
            "criterios": _criteria(rubric, stems),
            "hallazgos": findings[:MAX_CHAPTER_FINDINGS],
        })
    por_estado = {state: sum(1 for c in out_chapters if c["estado"] == state) for state in CHAPTER_STATES}
    rubric_id = rubric.get("id") if rubric is not None else None
    return {
        "schema": SCHEMA,
        "flujo": "sgr",
        "fuente_capitulos": source,
        "fuente_reglas": RULES_SOURCE if rules is not None else None,
        "rubrica": rubric_id if isinstance(rubric_id, str) else None,
        "resumen": {"capitulos": len(out_chapters), "por_estado": por_estado,
                    "palabras": sum(words_by_stem.values())},
        "capitulos": out_chapters,
    }


def _text_line(chapter: dict) -> str:
    sections = ", ".join(f"{s['stem']} ({s['estado']})" for s in chapter["secciones"]) or "sin secciones"
    return f"{chapter['numero']}. [{chapter['estado']}] {chapter['titulo']}: {sections}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("datos", help="Anexo 2 chapters with state, rule, lexicon and rubric")
    p.add_argument("run_root", type=Path)
    p.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)
    try:
        view = vista(args.run_root.resolve())
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(view, ensure_ascii=False, indent=2))
    else:
        for chapter in view["capitulos"]:
            print(_text_line(chapter))
    return 0


if __name__ == "__main__":
    sys.exit(main())
