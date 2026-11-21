#!/usr/bin/env python3
"""Funding calls: search profiles, validation, Colombian eligibility rules and ranking (both flows).

The `explorador-convocatorias` agent writes workspace-level files under
`convocatorias/` (the workspace is the folder holding `.morfeo/config.json`,
else `.marco/config.json`; a run folder inside it works too):

  perfil.json and perfil_banco.json (schema `morfeo.perfil-convocatorias/v1`)
      {schema, alcance:"proyecto"|"banco", actualizado, titulo, idea, aplicantes:[...],
       temas:[str], palabras_clave:{es:[str], en:[str]}, financiadores_previos:[str],
       idiomas:[...], ambitos:[...], institucion:{nombre, pais:"CO", tipo},
       experiencia:[{id (slug), nombre, detalle:str|null, temas:[str], financiadores:[str]}]}
      perfil.json is the project profile (alcance proyecto, from idea.md);
      perfil_banco.json is the banco LIA profile (alcance banco, from banco-lia only).
      `alcance` and `experiencia` are optional.
  oportunidades.json (schema `morfeo.oportunidades/v1`)
      {schema, actualizado, fuentes_consultadas:[{fuente, url, fecha, resultado, n}],
       oportunidades:[{id, titulo, financiador, programa, url, fuente, ambito, idioma,
                       aplicantes, rol_colombia, estado, apertura, cierre, cierre_tipo,
                       monto, temas, resumen, elegibilidad, puntaje_agente, evidencia,
                       encontrada, titulo_corto, esfuerzo, requisitos, relacionados_banco}]}
      Optional: titulo_corto (≤ 32 chars), esfuerzo ("bajo"|"medio"|"alto"),
      requisitos [{tipo: consorcio|contrapartida|anfitrion|idioma|perfil|aval|entidad|otro,
      estado: cumple|por_verificar|no_cumple, texto ≤ 200 chars}], relacionados_banco
      [experiencia ids].

Commands:
  perfil DIR [--alcance proyecto|banco]
      Create convocatorias/perfil.json (proyecto, the default: title from the
      workspace config, idea text from idea.md or the active run's
      insumos/ideas/idea.md) or convocatorias/perfil_banco.json (banco: title from
      the config, no idea text) when missing; never overwrites; prints the path.
      The only command that writes.
  check DIR [--json]
      Validate both profiles and the calls; one line per finding `severidad código mensaje`.
  datos DIR [--alcance proyecto|banco] [--json] [--hoy YYYY-MM-DD]
      The ranked view (schema `morfeo.convocatorias-vista/v1`) scored against the
      chosen profile (default proyecto; banco when only perfil_banco.json exists);
      text output is one line per call: puntaje, estado, días, rol, título.
  fuentes [--json]
      The fixed source catalogue scripts/convocatorias/fuentes.json.

Eligibility rules (scripts/convocatorias/reglas_co.json): the first rule whose
regex matches financiador + programa + titulo (accent- and case-insensitive)
sets the final `rol_colombia` and its `aviso`; a rule never turns an agent
`no_elegible` into a more permissive role, and `estado: pausada` in a rule
marks the call paused. Affinity: `lexico` is the share (0-100) of the profile
tokens (temas + palabras_clave.es + palabras_clave.en, stopwords dropped,
accents folded, a trailing plural «s» dropped from tokens over three letters)
found in titulo + temas + resumen + elegibilidad; `puntaje` is
round-half-up(0.5 * puntaje_agente + 0.5 * lexico), or `lexico` alone without an
agent score. A call whose cierre is before hoy is `cerrada`.

Map and match (per call, view only): `titulo_corto` (given, else the title cut
at a word boundary within 28 chars plus «…»); `temas_match` [{tema, peso}] (the
profile temas whose tokens appear in the call, peso = share present, kept when
≥ 0.5); `experiencia` (ids of profile experiencia items sharing a matched tema,
plus the known relacionados_banco); `historial` (financiador + programa contains
a financiadores_previos or experiencia financiadores entry); `componentes`
{tematica = puntaje, experiencia = min(100, 30 × items + 25 with historial),
elegibilidad by final role (lider 100, socio 70, coaplicante 70,
anfitrion_exterior 40, desconocido 50, no_elegible 0), tiempo (cerrada 0,
pausada 10, no cierre 50, else clamp(round(100 × días / need / 1.5), 0, 100),
need = 15/45/90 days for esfuerzo bajo/medio/alto, medio by default)};
`match` = round-half-up(0.35 tematica + 0.25 experiencia + 0.25 elegibilidad +
0.15 tiempo), at most 20 when no_elegible or not vigente; `esfuerzo`;
`preparar_desde` = cierre − need; `alertas` [{severidad, texto}] from requisitos
not met, a deadline shorter than the effort, «Cierre estimado», «Sin fecha de
cierre publicada» and «Programa pausado» (the rule notice stays in `aviso`).
Top level: `alcance`, `perfil.alcance`, `perfiles` {proyecto, banco} (which
files exist) and `mapa` {temas: [{tema, n}], experiencia: [items with n]}.
Order: vigentes (estado abierta/proxima and cierre not past) first; then
rol_colombia other than no_elegible; then match desc; then nearest cierre.

Codes: esquema, json-invalido, valor-invalido, fecha-invalida, id-invalido,
id-repetido, campo-faltante, texto-largo, puntaje-fuera-de-rango,
cierre-antes-de-apertura (errors); sin-evidencia, rol-desconocido,
abierta-sin-cierre, experiencia-desconocida (warnings); sin-perfil,
sin-oportunidades, regla-rol-distinto (info, the last one from `datos` only).

Library (the dashboard): find_workspace(path), vista(dir, hoy=None, alcance=None),
check(dir), init_profile(dir, alcance="proyecto"), load_sources(), load_rules().

Exit codes: 0 ok, 1 error findings (check), 2 bad input (no workspace, bad
date, invalid alcance, unreadable catalogue). Standard library only; no network access.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

PROFILE_SCHEMA = "morfeo.perfil-convocatorias/v1"
CALLS_SCHEMA = "morfeo.oportunidades/v1"
VIEW_SCHEMA = "morfeo.convocatorias-vista/v1"
RULES_SCHEMA = "morfeo.reglas-elegibilidad-co/v1"
SOURCES_SCHEMA = "morfeo.fuentes-convocatorias/v1"

DATA_DIR = Path(__file__).resolve().parent / "convocatorias"
RULES_FILE = DATA_DIR / "reglas_co.json"
SOURCES_FILE = DATA_DIR / "fuentes.json"
FOLDER = Path("convocatorias")
PROFILE_FILE = FOLDER / "perfil.json"
PROFILE_BANK_FILE = FOLDER / "perfil_banco.json"
CALLS_FILE = FOLDER / "oportunidades.json"
CONFIG_MARKERS = (Path(".morfeo") / "config.json", Path(".marco") / "config.json")

APPLICANTS = ("investigador", "estudiante", "empresa", "centro", "universidad", "grupo")
LANGUAGES = ("es", "en", "pt", "fr")
SCOPES = ("colombia", "latam", "internacional")
ROLES = ("lider", "socio", "coaplicante", "anfitrion_exterior", "no_elegible", "desconocido")
STATES = ("abierta", "proxima", "cerrada", "pausada")
DEADLINE_TYPES = ("fijo", "estimado", "continuo", "desconocido")
SOURCE_RESULTS = ("ok", "sin_resultados", "bloqueado", "error")
CURRENT_STATES = ("abierta", "proxima")
REQUIRED_CALL_FIELDS = ("titulo", "financiador", "url", "ambito")
ALCANCES = ("proyecto", "banco")
PROFILE_FILES = {"proyecto": PROFILE_FILE, "banco": PROFILE_BANK_FILE}
EFFORT_DAYS = {"bajo": 15, "medio": 45, "alto": 90}
DEFAULT_EFFORT = "medio"
REQUIREMENT_TYPES = ("consorcio", "contrapartida", "anfitrion", "idioma", "perfil", "aval", "entidad", "otro")
REQUIREMENT_STATES = ("cumple", "por_verificar", "no_cumple")
REQUIREMENT_SEVERITY = {"no_cumple": "error", "por_verificar": "warning"}
ELIGIBILITY_SCORE = {"lider": 100, "socio": 70, "coaplicante": 70, "anfitrion_exterior": 40,
                     "desconocido": 50, "no_elegible": 0}
SHORT_TITLE_LIMIT = 32
SHORT_TITLE_CUT = 28
TOPIC_MIN_WEIGHT = 0.5
MATCH_CAP = 20
TEXT_LIMIT = 600
QUOTE_LIMIT = 200
IDEA_LIMIT = 2000
SLUG_RE = re.compile(r"^[a-z0-9-]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

STOPWORDS = frozenset("""
a al ante bajo como con cual cuando de del desde donde e el en entre es esa ese esta este estas estos
la las le les lo los mas muy no o para pero por que se segun si sin sobre son su sus tambien tras u
un una unas unos y ya
an and are as at be by for from in into is it its not of on or our over per than that the their
these this those to under via with without your
""".split())


class InputError(ValueError):
    """Bad input: no workspace, unreadable data file, bad date."""


# --- Helpers ------------------------------------------------------------------

def _fold(text: str) -> str:
    """Lowercase `text` without accents (NFKD, combining marks dropped)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", _fold(text)):
        if len(token) < 2 or token in STOPWORDS:
            continue
        if len(token) > 3 and token.endswith("s"):
            token = token[:-1]
        out.add(token)
    return out


def _strings(value) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _date(value) -> datetime.date | None:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def _read_json(path: Path):
    """(data, error message); data is None when the file is missing or unreadable."""
    if not path.is_file():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _write_atomic(path: Path, data: dict) -> None:
    """Write `data` as JSON through a temporary file in the same folder and os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _finding(severity: str, code: str, message: str, call_id: str | None = None) -> dict:
    return {"severidad": severity, "codigo": code, "mensaje": message, "id": call_id}


# --- Workspace ----------------------------------------------------------------

def find_workspace(path) -> Path:
    """The nearest folder at or above `path` holding .morfeo/config.json (else .marco/config.json)."""
    start = Path(path).expanduser().resolve()
    if not start.exists():
        raise InputError(f"no existe la carpeta {start}")
    if start.is_file():
        start = start.parent
    for folder in (start, *start.parents):
        if any((folder / marker).is_file() for marker in CONFIG_MARKERS):
            return folder
    raise InputError(f"{start} no está dentro de un proyecto Morfeo (falta .morfeo/config.json)")


def _config(workspace: Path) -> dict:
    for marker in CONFIG_MARKERS:
        data, _ = _read_json(workspace / marker)
        if isinstance(data, dict):
            return data
    return {}


def _clean_idea(text: str) -> str | None:
    """Plain idea text: HTML comments and heading markers removed; None when only headings remain."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    lines = [line.rstrip() for line in text.splitlines()]
    if not any(line.strip() and not line.lstrip().startswith("#") for line in lines):
        return None
    text = "\n".join(re.sub(r"^\s*#+\s*", "", line) for line in lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > IDEA_LIMIT:
        text = text[:IDEA_LIMIT].rstrip() + "…"
    return text or None


def _idea(workspace: Path) -> str | None:
    candidates = [workspace / "idea.md"]
    pointer = workspace / "proposals" / ".current-run"
    if pointer.is_file():
        try:
            run = pointer.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            run = ""
        if run:
            candidates.append(workspace / "proposals" / run / "insumos" / "ideas" / "idea.md")
    for path in candidates:
        if path.is_file():
            try:
                idea = _clean_idea(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            if idea:
                return idea
    return None


def _check_alcance(alcance) -> str:
    if alcance not in ALCANCES:
        raise InputError(f"alcance inválido {alcance!r}; use «proyecto» o «banco»")
    return alcance


def init_profile(path, alcance: str = "proyecto") -> tuple[Path, bool]:
    """Create the profile of `alcance` when missing; (path, created). Never overwrites.

    `proyecto` writes convocatorias/perfil.json with the idea text; `banco` writes
    convocatorias/perfil_banco.json without it (the agent fills it from banco-lia).
    """
    workspace = find_workspace(path)
    _check_alcance(alcance)
    target = workspace / PROFILE_FILES[alcance]
    if target.exists():
        return target, False
    config = _config(workspace)
    title = config.get("title") or config.get("titulo")
    _write_atomic(target, {
        "schema": PROFILE_SCHEMA,
        "alcance": alcance,
        "actualizado": None,
        "titulo": title.strip() if isinstance(title, str) and title.strip() else None,
        "idea": _idea(workspace) if alcance == "proyecto" else None,
        "aplicantes": [],
        "temas": [],
        "palabras_clave": {"es": [], "en": []},
        "financiadores_previos": [],
        "idiomas": ["es", "en"],
        "ambitos": list(SCOPES),
        "institucion": {"nombre": None, "pais": "CO", "tipo": None},
        "experiencia": [],
    })
    return target, True


# --- Data files ---------------------------------------------------------------

def _load_catalogue(path: Path, schema: str) -> dict:
    data, error = _read_json(path)
    if error or not isinstance(data, dict):
        raise InputError(f"no se pudo leer {path.name}: {error or 'falta el archivo'}")
    if data.get("schema") != schema:
        raise InputError(f"{path.name} no declara el esquema {schema}")
    return data


def load_sources() -> dict:
    """The fixed source catalogue (schema morfeo.fuentes-convocatorias/v1)."""
    return _load_catalogue(SOURCES_FILE, SOURCES_SCHEMA)


def load_rules() -> list[dict]:
    """The eligibility rules with their compiled, accent-folded pattern under `_re`."""
    rules = []
    for rule in _load_catalogue(RULES_FILE, RULES_SCHEMA).get("reglas") or []:
        if isinstance(rule, dict) and isinstance(rule.get("patron"), str):
            rules.append(dict(rule, _re=re.compile(_fold(rule["patron"]))))
    return rules


# --- Validation ---------------------------------------------------------------

def _check_enum_list(findings, value, allowed, field, call_id=None):
    if value is None:
        return
    if not isinstance(value, list):
        findings.append(_finding("error", "valor-invalido", f"«{field}» debe ser una lista", call_id))
        return
    for item in value:
        if item not in allowed:
            findings.append(_finding("error", "valor-invalido",
                                     f"«{field}» tiene un valor no permitido: {item!r}", call_id))


def _check_date(findings, value, field, call_id=None, nullable=True):
    if value is None and nullable:
        return
    if _date(value) is None:
        findings.append(_finding("error", "fecha-invalida",
                                 f"«{field}» debe ser una fecha AAAA-MM-DD: {value!r}", call_id))


def _is_text_list(value) -> bool:
    return isinstance(value, list) and len(_strings(value)) == len(value)


def _check_experience(findings: list[dict], value) -> None:
    """Validate the optional profile field `experiencia` (lab lines and items from banco-lia)."""
    if value is None:
        return
    if not isinstance(value, list):
        findings.append(_finding("error", "valor-invalido", "«experiencia» debe ser una lista"))
        return
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            findings.append(_finding("error", "valor-invalido", "un elemento de «experiencia» no es un objeto"))
            continue
        raw_id = item.get("id")
        item_id = raw_id if isinstance(raw_id, str) and raw_id else None
        label = f"experiencia {item_id or '(sin id)'}"
        if item_id is None:
            findings.append(_finding("error", "campo-faltante", "un elemento de «experiencia» no tiene «id»"))
        elif not SLUG_RE.match(item_id):
            findings.append(_finding("error", "id-invalido", f"{label}: «id» debe ser un slug [a-z0-9-]+"))
        elif item_id in seen:
            findings.append(_finding("error", "id-repetido", f"{label}: el id está repetido"))
        if item_id:
            seen.add(item_id)
        name = item.get("nombre")
        if not isinstance(name, str) or not name.strip():
            findings.append(_finding("error", "campo-faltante", f"{label}: falta «nombre»"))
        detail = item.get("detalle")
        if detail is not None and not isinstance(detail, str):
            findings.append(_finding("error", "valor-invalido", f"{label}: «detalle» debe ser texto o null"))
        for field in ("temas", "financiadores"):
            if item.get(field) is not None and not _is_text_list(item.get(field)):
                findings.append(_finding("error", "valor-invalido", f"{label}: «{field}» debe ser una lista de textos"))


def _check_profile(data, name: str = PROFILE_FILE.as_posix()) -> list[dict]:
    findings: list[dict] = []
    if not isinstance(data, dict) or data.get("schema") != PROFILE_SCHEMA:
        findings.append(_finding("error", "esquema", f"{name} no declara el esquema {PROFILE_SCHEMA}"))
        if not isinstance(data, dict):
            return findings
    if data.get("alcance") is not None and data.get("alcance") not in ALCANCES:
        findings.append(_finding("error", "valor-invalido", f"«alcance» no admite {data.get('alcance')!r}"))
    _check_experience(findings, data.get("experiencia"))
    _check_date(findings, data.get("actualizado"), "actualizado")
    _check_enum_list(findings, data.get("aplicantes"), APPLICANTS, "aplicantes")
    _check_enum_list(findings, data.get("idiomas"), LANGUAGES, "idiomas")
    _check_enum_list(findings, data.get("ambitos"), SCOPES, "ambitos")
    for field in ("temas", "financiadores_previos"):
        value = data.get(field)
        if value is not None and (not isinstance(value, list) or len(_strings(value)) != len(value)):
            findings.append(_finding("error", "valor-invalido", f"«{field}» debe ser una lista de textos"))
    keywords = data.get("palabras_clave")
    if keywords is not None:
        if not isinstance(keywords, dict):
            findings.append(_finding("error", "valor-invalido", "«palabras_clave» debe ser {es: [...], en: [...]}"))
        else:
            for lang in ("es", "en"):
                value = keywords.get(lang)
                if value is not None and (not isinstance(value, list) or len(_strings(value)) != len(value)):
                    findings.append(_finding("error", "valor-invalido",
                                             f"«palabras_clave.{lang}» debe ser una lista de textos"))
    return findings


def _check_map_fields(findings: list[dict], call: dict, label: str, call_id, known_ids) -> None:
    """Validate the optional fields of the opportunity map: titulo_corto, esfuerzo, requisitos, relacionados_banco."""
    short = call.get("titulo_corto")
    if short is not None:
        if not isinstance(short, str) or not short.strip():
            findings.append(_finding("error", "valor-invalido", f"{label}: «titulo_corto» debe ser un texto", call_id))
        elif len(short) > SHORT_TITLE_LIMIT:
            findings.append(_finding("error", "texto-largo",
                                     f"{label}: «titulo_corto» tiene {len(short)} caracteres "
                                     f"(máximo {SHORT_TITLE_LIMIT})", call_id))
    effort = call.get("esfuerzo")
    if effort is not None and effort not in EFFORT_DAYS:
        findings.append(_finding("error", "valor-invalido", f"{label}: «esfuerzo» no admite {effort!r}", call_id))
    requirements = call.get("requisitos")
    if requirements is not None and not isinstance(requirements, list):
        findings.append(_finding("error", "valor-invalido", f"{label}: «requisitos» debe ser una lista", call_id))
    for req in requirements if isinstance(requirements, list) else []:
        if not isinstance(req, dict):
            findings.append(_finding("error", "valor-invalido", f"{label}: un requisito no es un objeto", call_id))
            continue
        for field, allowed in (("tipo", REQUIREMENT_TYPES), ("estado", REQUIREMENT_STATES)):
            if req.get(field) not in allowed:
                findings.append(_finding("error", "valor-invalido",
                                         f"{label}: «requisitos.{field}» no admite {req.get(field)!r}", call_id))
        text = req.get("texto")
        if text is None or (isinstance(text, str) and not text.strip()):
            findings.append(_finding("error", "campo-faltante", f"{label}: un requisito no tiene «texto»", call_id))
        elif not isinstance(text, str):
            findings.append(_finding("error", "valor-invalido", f"{label}: «requisitos.texto» debe ser texto",
                                     call_id))
        elif len(text) > QUOTE_LIMIT:
            findings.append(_finding("error", "texto-largo",
                                     f"{label}: un requisito tiene {len(text)} caracteres (máximo {QUOTE_LIMIT})",
                                     call_id))
    related = call.get("relacionados_banco")
    if related is None:
        return
    if not _is_text_list(related):
        findings.append(_finding("error", "valor-invalido", f"{label}: «relacionados_banco» debe ser una lista de ids",
                                 call_id))
        return
    for exp_id in related:
        if known_ids is not None and exp_id not in known_ids:
            findings.append(_finding("warning", "experiencia-desconocida",
                                     f"{label}: «relacionados_banco» cita {exp_id!r}, que no está en la "
                                     "«experiencia» de ningún perfil", call_id))


def _check_call(findings: list[dict], call: dict, seen: set[str], known_ids: set[str] | None = None) -> None:
    raw_id = call.get("id")
    call_id = raw_id if isinstance(raw_id, str) and raw_id else None
    label = call_id or "(sin id)"
    if call_id is None:
        findings.append(_finding("error", "campo-faltante", "una oportunidad no tiene «id»"))
    elif not SLUG_RE.match(call_id):
        findings.append(_finding("error", "id-invalido", f"{label}: «id» debe ser un slug [a-z0-9-]+", call_id))
    elif call_id in seen:
        findings.append(_finding("error", "id-repetido", f"{label}: el id está repetido", call_id))
    if call_id:
        seen.add(call_id)
    for field in REQUIRED_CALL_FIELDS:
        value = call.get(field)
        if not isinstance(value, str) or not value.strip():
            findings.append(_finding("error", "campo-faltante", f"{label}: falta «{field}»", call_id))
    for field, allowed, required in (("ambito", SCOPES, False), ("idioma", LANGUAGES, True),
                                     ("rol_colombia", ROLES, False), ("estado", STATES, True),
                                     ("cierre_tipo", DEADLINE_TYPES, False)):
        value = call.get(field)
        if value is None and not required:
            continue
        if value not in allowed:
            findings.append(_finding("error", "valor-invalido",
                                     f"{label}: «{field}» no admite {value!r}", call_id))
    _check_enum_list(findings, call.get("aplicantes"), APPLICANTS, "aplicantes", call_id)
    for field in ("apertura", "cierre", "encontrada"):
        _check_date(findings, call.get(field), field, call_id)
    opening, deadline = _date(call.get("apertura")), _date(call.get("cierre"))
    if opening and deadline and deadline < opening:
        findings.append(_finding("error", "cierre-antes-de-apertura",
                                 f"{label}: el cierre ({deadline}) es anterior a la apertura ({opening})", call_id))
    amount = call.get("monto")
    if amount is not None:
        valid = isinstance(amount, dict) and all(
            amount.get(k) is None or (isinstance(amount.get(k), (int, float)) and not isinstance(amount.get(k), bool))
            for k in ("min", "max")) and isinstance(amount.get("moneda"), str)
        if not valid:
            findings.append(_finding("error", "valor-invalido",
                                     f"{label}: «monto» debe ser {{min, max, moneda}} o null", call_id))
    for field in ("resumen", "elegibilidad"):
        value = call.get(field)
        if isinstance(value, str) and len(value) > TEXT_LIMIT:
            findings.append(_finding("error", "texto-largo",
                                     f"{label}: «{field}» tiene {len(value)} caracteres (máximo {TEXT_LIMIT})",
                                     call_id))
    score = call.get("puntaje_agente")
    if score is not None and (not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100):
        findings.append(_finding("error", "puntaje-fuera-de-rango",
                                 f"{label}: «puntaje_agente» debe ser un entero de 0 a 100: {score!r}", call_id))
    evidence = call.get("evidencia")
    quotes = [e for e in evidence if isinstance(e, dict)] if isinstance(evidence, list) else []
    for quote in quotes:
        text = quote.get("texto")
        if isinstance(text, str) and len(text) > QUOTE_LIMIT:
            findings.append(_finding("error", "texto-largo",
                                     f"{label}: una cita de «evidencia» tiene {len(text)} caracteres "
                                     f"(máximo {QUOTE_LIMIT})", call_id))
    if not quotes:
        findings.append(_finding("warning", "sin-evidencia", f"{label}: no cita evidencia", call_id))
    if call.get("rol_colombia") in (None, "desconocido"):
        findings.append(_finding("warning", "rol-desconocido",
                                 f"{label}: no se sabe con qué rol participa Colombia", call_id))
    if call.get("estado") == "abierta" and call.get("cierre") is None:
        findings.append(_finding("warning", "abierta-sin-cierre", f"{label}: está abierta y no tiene cierre",
                                 call_id))
    _check_map_fields(findings, call, label, call_id, known_ids)


def _check_calls(data, known_ids: set[str] | None = None) -> list[dict]:
    findings: list[dict] = []
    name = CALLS_FILE.as_posix()
    if not isinstance(data, dict) or data.get("schema") != CALLS_SCHEMA:
        findings.append(_finding("error", "esquema", f"{name} no declara el esquema {CALLS_SCHEMA}"))
        if not isinstance(data, dict):
            return findings
    _check_date(findings, data.get("actualizado"), "actualizado", nullable=False)
    sources = data.get("fuentes_consultadas")
    if sources is not None and not isinstance(sources, list):
        findings.append(_finding("error", "valor-invalido", "«fuentes_consultadas» debe ser una lista"))
    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, dict):
            findings.append(_finding("error", "valor-invalido", "una fuente consultada no es un objeto"))
            continue
        label = source.get("fuente") or "(sin nombre)"
        if source.get("resultado") not in SOURCE_RESULTS:
            findings.append(_finding("error", "valor-invalido",
                                     f"fuente {label}: «resultado» no admite {source.get('resultado')!r}"))
        _check_date(findings, source.get("fecha"), f"fecha de la fuente {label}", nullable=False)
        count = source.get("n")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            findings.append(_finding("error", "valor-invalido", f"fuente {label}: «n» debe ser un entero ≥ 0"))
    calls = data.get("oportunidades")
    if not isinstance(calls, list):
        findings.append(_finding("error", "campo-faltante", "falta la lista «oportunidades»"))
        return findings
    seen: set[str] = set()
    for call in calls:
        if not isinstance(call, dict):
            findings.append(_finding("error", "valor-invalido", "una oportunidad no es un objeto"))
            continue
        _check_call(findings, call, seen, known_ids)
    return findings


def _experience_items(profile: dict | None) -> list[dict]:
    """The profile's `experiencia` items that carry a text id, first occurrence of each id."""
    items, seen = [], set()
    raw = (profile or {}).get("experiencia")
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] and item["id"] not in seen:
            seen.add(item["id"])
            items.append(item)
    return items


def _check_workspace(workspace: Path) -> tuple[list[dict], dict[str, dict | None], dict | None]:
    """(findings, {alcance: profile data}, calls data) of a workspace; data is None when missing or unreadable."""
    findings: list[dict] = []
    profiles: dict[str, dict | None] = {}
    for scope in ALCANCES:
        name = PROFILE_FILES[scope].as_posix()
        profile, error = _read_json(workspace / PROFILE_FILES[scope])
        if error:
            findings.append(_finding("error", "json-invalido", f"{name}: {error}"))
        elif profile is not None:
            scoped = _check_profile(profile, name)
            if scope != "proyecto":
                # The project profile keeps its historical messages; the others name their file.
                for f in scoped:
                    if not f["mensaje"].startswith(name):
                        f["mensaje"] = f"{name}: {f['mensaje']}"
            findings.extend(scoped)
        profiles[scope] = profile if isinstance(profile, dict) else None
    if not any((workspace / PROFILE_FILES[scope]).is_file() for scope in ALCANCES):
        findings.append(_finding("info", "sin-perfil",
                                 f"no existe {PROFILE_FILE.as_posix()} ni {PROFILE_BANK_FILE.as_posix()}; "
                                 "créelos con «convocatorias.py perfil [--alcance banco]»"))
    known_ids = {item["id"] for scope in ALCANCES for item in _experience_items(profiles[scope])}
    calls, error = _read_json(workspace / CALLS_FILE)
    if error:
        findings.append(_finding("error", "json-invalido", f"{CALLS_FILE.as_posix()}: {error}"))
    elif calls is None:
        findings.append(_finding("info", "sin-oportunidades",
                                 f"no existe {CALLS_FILE.as_posix()}; ejecute /propuesta-convocatorias"))
    else:
        findings.extend(_check_calls(calls, known_ids))
    return findings, profiles, calls if isinstance(calls, dict) else None


def check(path) -> list[dict]:
    """Findings {severidad, codigo, mensaje, id} for perfil.json and oportunidades.json."""
    return _check_workspace(find_workspace(path))[0]


# --- View ---------------------------------------------------------------------

def _profile_tokens(profile: dict | None) -> tuple[set[str], int]:
    if profile is None:
        return set(), 0
    keywords = profile.get("palabras_clave") if isinstance(profile.get("palabras_clave"), dict) else {}
    phrases = _strings(profile.get("temas")) + _strings(keywords.get("es")) + _strings(keywords.get("en"))
    tokens: set[str] = set()
    for phrase in phrases:
        tokens |= _tokens(phrase)
    return tokens, len(phrases)


def _call_tokens(call: dict) -> set[str]:
    parts = [call.get("titulo"), call.get("resumen"), call.get("elegibilidad"), *_strings(call.get("temas"))]
    return _tokens(" ".join(p for p in parts if isinstance(p, str)))


def _lexical(call_tokens: set[str], profile_tokens: set[str]) -> int:
    if not profile_tokens:
        return 0
    return _round_half_up(100 * len(profile_tokens & call_tokens) / len(profile_tokens))


def _short_title(call: dict) -> str:
    """`titulo_corto` when given, else the title cut at a word boundary within 28 characters plus «…»."""
    given = call.get("titulo_corto")
    if isinstance(given, str) and given.strip():
        return given.strip()
    title = call.get("titulo") if isinstance(call.get("titulo"), str) else str(call.get("id") or "")
    title = " ".join(title.split())
    if len(title) <= SHORT_TITLE_CUT:
        return title
    space = title.rfind(" ", 0, SHORT_TITLE_CUT + 1)
    head = title[:space] if space > 0 else title[:SHORT_TITLE_CUT]
    return head.rstrip(" ,;:.-–·") + "…"


def _topic_matches(call_tokens: set[str], topics: list[str]) -> list[dict]:
    """Profile temas found in the call: peso = share of the tema's tokens present, kept when ≥ 0.5."""
    found = []
    for index, topic in enumerate(topics):
        topic_tokens = _tokens(topic)
        if not topic_tokens:
            continue
        share = len(topic_tokens & call_tokens) / len(topic_tokens)
        if share >= TOPIC_MIN_WEIGHT:
            found.append((-share, index, {"tema": topic, "peso": round(share, 2)}))
    return [entry for _, _, entry in sorted(found, key=lambda f: (f[0], f[1]))]


def _call_experience(call: dict, topic_matches: list[dict], experience: list[dict]) -> list[str]:
    """Ids of the profile experiencia items sharing a matched tema, plus the call's known relacionados_banco."""
    matched = {frozenset(_tokens(m["tema"])) for m in topic_matches}
    related = set(_strings(call.get("relacionados_banco")))
    return [item["id"] for item in experience
            if item["id"] in related or any(frozenset(_tokens(t)) in matched for t in _strings(item.get("temas")))]


def _has_history(call: dict, profile: dict | None, experience: list[dict]) -> bool:
    """The funder (financiador + programa) contains a previous funder of the profile or of its experiencia."""
    funder = " ".join(_fold(" ".join(str(call.get(k)) for k in ("financiador", "programa")
                                     if isinstance(call.get(k), str))).split())
    names = _strings((profile or {}).get("financiadores_previos"))
    for item in experience:
        names += _strings(item.get("financiadores"))
    return any(key and key in funder for key in (" ".join(_fold(n).split()) for n in names))


def _time_score(state: str, days: int | None, need: int) -> int:
    if state == "cerrada":
        return 0
    if state == "pausada":
        return 10
    if days is None:
        return 50
    # round_half_up(100 * (days / need) / 1.5) in integer arithmetic.
    return max(0, min(100, (400 * days + 3 * need) // (6 * need)))


def _alerts(call: dict, state: str, vigente: bool, days: int | None, effort: str, need: int,
            deadline: datetime.date | None) -> list[dict]:
    """Requirement and time alerts; the rule notice stays in `aviso` and is not repeated here."""
    alerts = []
    if state == "pausada":
        alerts.append({"severidad": "error", "texto": "Programa pausado"})
    if vigente and days is not None and days < need:
        alerts.append({"severidad": "error",
                       "texto": f"Cierra en {days} días y el esfuerzo estimado es {effort} (unos {need} días)"})
    requirements = call.get("requisitos")
    for req in requirements if isinstance(requirements, list) else []:
        if isinstance(req, dict) and req.get("estado") in REQUIREMENT_SEVERITY:
            text = req.get("texto")
            text = text.strip() if isinstance(text, str) and text.strip() else f"Requisito: {req.get('tipo')}"
            alerts.append({"severidad": REQUIREMENT_SEVERITY[req["estado"]], "texto": text})
    if call.get("cierre_tipo") == "estimado":
        alerts.append({"severidad": "info", "texto": "Cierre estimado"})
    if vigente and deadline is None:
        alerts.append({"severidad": "info", "texto": "Sin fecha de cierre publicada"})
    return alerts


def _match_rule(rules: list[dict], call: dict) -> dict | None:
    text = _fold(" ".join(str(call.get(k)) for k in ("financiador", "programa", "titulo")
                          if isinstance(call.get(k), str)))
    return next((rule for rule in rules if rule["_re"].search(text)), None)


def _view_call(call: dict, rules: list[dict], profile: dict | None, profile_tokens: set[str],
               hoy: datetime.date, findings: list[dict]) -> dict:
    out = dict(call)
    agent_role = call.get("rol_colombia") if call.get("rol_colombia") in ROLES else "desconocido"
    role, notice, rule_ref = agent_role, None, None
    rule = _match_rule(rules, call)
    if rule is not None:
        rule_ref = {"id": rule.get("id"), "aviso": rule.get("aviso")}
        if rule.get("rol") is None:
            # A rule without a role only adds its notice (and its state): the role depends on the call.
            notice = rule.get("aviso")
        elif agent_role != "no_elegible" or rule.get("rol") == "no_elegible":
            role, notice = rule.get("rol"), rule.get("aviso")
        if rule.get("rol") is not None and agent_role not in ("desconocido", rule.get("rol")):
            kept = "se mantiene «no_elegible»" if role == "no_elegible" and rule.get("rol") != "no_elegible" \
                else f"se usa «{role}»"
            findings.append(_finding("info", "regla-rol-distinto",
                                     f"{call.get('id')}: la regla {rule.get('id')} indica «{rule.get('rol')}» y el "
                                     f"agente «{agent_role}»; {kept}", call.get("id")))
    state = call.get("estado") if call.get("estado") in STATES else "abierta"
    deadline = _date(call.get("cierre"))
    if deadline is not None and deadline < hoy:
        state = "cerrada"
    elif rule is not None and rule.get("estado") == "pausada":
        state = "pausada"
    call_tokens = _call_tokens(call)
    lexico = _lexical(call_tokens, profile_tokens)
    score = call.get("puntaje_agente")
    has_score = isinstance(score, (int, float)) and not isinstance(score, bool)
    puntaje = _round_half_up(0.5 * score + 0.5 * lexico) if has_score else lexico
    days = (deadline - hoy).days if deadline is not None else None
    vigente = state in CURRENT_STATES
    experience_items = _experience_items(profile)
    topic_matches = _topic_matches(call_tokens, _strings((profile or {}).get("temas")))
    experience = _call_experience(call, topic_matches, experience_items)
    history = _has_history(call, profile, experience_items)
    effort = call.get("esfuerzo") if call.get("esfuerzo") in EFFORT_DAYS else DEFAULT_EFFORT
    need = EFFORT_DAYS[effort]
    components = {
        "tematica": puntaje,
        "experiencia": min(100, 30 * len(experience) + (25 if history else 0)),
        "elegibilidad": ELIGIBILITY_SCORE.get(role, ELIGIBILITY_SCORE["desconocido"]),
        "tiempo": _time_score(state, days, need),
    }
    # round_half_up(0.35 tematica + 0.25 experiencia + 0.25 elegibilidad + 0.15 tiempo), exact on integers.
    match = (35 * components["tematica"] + 25 * components["experiencia"] + 25 * components["elegibilidad"]
             + 15 * components["tiempo"] + 50) // 100
    if role == "no_elegible" or not vigente:
        match = min(match, MATCH_CAP)
    out.update({
        "estado": state,
        "dias_restantes": days,
        "vigente": vigente,
        "rol_colombia": role,
        "rol_agente": agent_role,
        "regla": rule_ref,
        "aviso": notice,
        "lexico": lexico,
        "puntaje": puntaje,
        "titulo_corto": _short_title(call),
        "temas_match": topic_matches,
        "experiencia": experience,
        "historial": history,
        "componentes": components,
        "match": int(match),
        "esfuerzo": effort,
        "preparar_desde": (deadline - datetime.timedelta(days=need)).isoformat() if deadline is not None else None,
        "alertas": _alerts(call, state, vigente, days, effort, need, deadline),
    })
    return out


def _sort_key(call: dict):
    deadline = _date(call.get("cierre"))
    return (not call["vigente"], call["rol_colombia"] == "no_elegible", -call["match"],
            deadline is None, deadline or datetime.date.max, str(call.get("id")))


def _default_alcance(workspace: Path) -> str:
    """`proyecto`, or `banco` when only convocatorias/perfil_banco.json exists."""
    if not (workspace / PROFILE_FILE).is_file() and (workspace / PROFILE_BANK_FILE).is_file():
        return "banco"
    return "proyecto"


def vista(path, hoy: datetime.date | None = None, alcance: str | None = None) -> dict:
    """The ranked view of the workspace's calls (schema morfeo.convocatorias-vista/v1).

    `alcance` picks the profile the calls are scored against: `proyecto` (perfil.json)
    or `banco` (perfil_banco.json); None means proyecto, or banco when only it exists.
    """
    workspace = find_workspace(path)
    alcance = _default_alcance(workspace) if alcance is None else _check_alcance(alcance)
    hoy = hoy or datetime.date.today()
    findings, profiles, data = _check_workspace(workspace)
    profile = profiles[alcance]
    exists = {scope: (workspace / PROFILE_FILES[scope]).is_file() for scope in ALCANCES}
    if not exists[alcance] and any(exists.values()):
        findings.append(_finding("info", "sin-perfil",
                                 f"no existe {PROFILE_FILES[alcance].as_posix()}; créelo con "
                                 f"«convocatorias.py perfil --alcance {alcance}»"))
    rules = load_rules()
    profile_tokens, n_keywords = _profile_tokens(profile)
    raw_calls = data.get("oportunidades") if data is not None else None
    calls = [_view_call(c, rules, profile, profile_tokens, hoy, findings)
             for c in (raw_calls if isinstance(raw_calls, list) else []) if isinstance(c, dict)]
    calls.sort(key=_sort_key)
    topics = _strings((profile or {}).get("temas"))
    sources = data.get("fuentes_consultadas") if data is not None else None

    def count(field, keys):
        return {k: sum(1 for c in calls if c.get(field) == k) for k in keys}

    return {
        "schema": VIEW_SCHEMA,
        "hoy": hoy.isoformat(),
        "workspace": str(workspace),
        "alcance": alcance,
        "perfiles": exists,
        "perfil": {
            "existe": profile is not None,
            "alcance": profile.get("alcance") if profile and profile.get("alcance") in ALCANCES else alcance,
            "titulo": (profile or {}).get("titulo") if isinstance((profile or {}).get("titulo"), str) else None,
            "aplicantes": _strings((profile or {}).get("aplicantes")),
            "idiomas": _strings((profile or {}).get("idiomas")),
            "ambitos": _strings((profile or {}).get("ambitos")),
            "n_palabras_clave": n_keywords,
        },
        "resumen": {
            "total": len(calls),
            "vigentes": sum(1 for c in calls if c["vigente"]),
            "por_ambito": count("ambito", SCOPES),
            "por_rol": count("rol_colombia", ROLES),
            "por_idioma": count("idioma", LANGUAGES),
        },
        "fuentes_consultadas": [s for s in sources if isinstance(s, dict)] if isinstance(sources, list) else [],
        "oportunidades": calls,
        "mapa": {
            "temas": [{"tema": topic, "n": sum(1 for c in calls if any(m["tema"] == topic for m in c["temas_match"]))}
                      for topic in topics],
            "experiencia": [dict(item, n=sum(1 for c in calls if item["id"] in c["experiencia"]))
                            for item in _experience_items(profile)],
        },
        "hallazgos": findings,
    }


# --- CLI ----------------------------------------------------------------------

def _hoy_arg(value: str) -> datetime.date:
    parsed = _date(value)
    if parsed is None:
        raise argparse.ArgumentTypeError(f"fecha inválida {value!r}; use AAAA-MM-DD")
    return parsed


def _call_line(call: dict) -> str:
    days = call["dias_restantes"]
    days_text = "sin fecha" if days is None else f"{days} d"
    return f"{call['puntaje']:>3}  {call['estado']:<8} {days_text:>9}  {call['rol_colombia']:<18} {call.get('titulo')}"


def _print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("perfil", help="crea convocatorias/perfil.json (o perfil_banco.json) si no existe")
    p.add_argument("dir", type=Path)
    p.add_argument("--alcance", choices=ALCANCES, default="proyecto",
                   help="proyecto: perfil.json con la idea (por defecto); banco: perfil_banco.json")
    p = sub.add_parser("check", help="valida perfil.json y oportunidades.json")
    p.add_argument("dir", type=Path)
    p.add_argument("--json", action="store_true", help="imprime los hallazgos en JSON")
    p = sub.add_parser("datos", help="vista ordenada de las convocatorias")
    p.add_argument("dir", type=Path)
    p.add_argument("--json", action="store_true", help="imprime la vista en JSON")
    p.add_argument("--hoy", type=_hoy_arg, help="fecha de referencia AAAA-MM-DD (por defecto, hoy)")
    p.add_argument("--alcance", choices=ALCANCES,
                   help="perfil con el que se puntúa: proyecto (por defecto) o banco (por defecto si es el único)")
    p = sub.add_parser("fuentes", help="catálogo de fuentes fijas")
    p.add_argument("--json", action="store_true", help="imprime el catálogo en JSON")
    args = parser.parse_args(argv)
    try:
        if args.command == "perfil":
            path, created = init_profile(args.dir, alcance=args.alcance)
            if not created:
                print("ya existe; no se sobrescribe", file=sys.stderr)
            print(path)
            return 0
        if args.command == "check":
            findings = check(args.dir)
            if args.json:
                _print_json(findings)
            else:
                for f in findings:
                    print(f"{f['severidad']} {f['codigo']} {f['mensaje']}")
                if not findings:
                    print("sin hallazgos")
            return 1 if any(f["severidad"] == "error" for f in findings) else 0
        if args.command == "datos":
            view = vista(args.dir, hoy=args.hoy, alcance=args.alcance)
            if args.json:
                _print_json(view)
            elif view["oportunidades"]:
                for call in view["oportunidades"]:
                    print(_call_line(call))
            else:
                print("sin oportunidades registradas")
            return 0
        sources = load_sources()
        if args.json:
            _print_json(sources)
        else:
            for s in sources.get("fuentes") or []:
                print(f"{s.get('id')}  {s.get('metodo')}  {s.get('ambito')}  {s.get('nombre')}  {s.get('url')}")
        return 0
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
