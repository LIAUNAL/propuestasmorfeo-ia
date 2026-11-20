#!/usr/bin/env python3
"""Funding calls: search profile, validation, Colombian eligibility rules and ranking (both flows).

The `explorador-convocatorias` agent writes two workspace-level files under
`convocatorias/` (the workspace is the folder holding `.morfeo/config.json`,
else `.marco/config.json`; a run folder inside it works too):

  perfil.json (schema `morfeo.perfil-convocatorias/v1`)
      {schema, actualizado, titulo, idea, aplicantes:[...], temas:[str],
       palabras_clave:{es:[str], en:[str]}, financiadores_previos:[str],
       idiomas:[...], ambitos:[...], institucion:{nombre, pais:"CO", tipo}}
  oportunidades.json (schema `morfeo.oportunidades/v1`)
      {schema, actualizado, fuentes_consultadas:[{fuente, url, fecha, resultado, n}],
       oportunidades:[{id, titulo, financiador, programa, url, fuente, ambito, idioma,
                       aplicantes, rol_colombia, estado, apertura, cierre, cierre_tipo,
                       monto, temas, resumen, elegibilidad, puntaje_agente, evidencia,
                       encontrada}]}

Commands:
  perfil DIR
      Create convocatorias/perfil.json when missing (title from the workspace
      config, idea text from idea.md or the active run's insumos/ideas/idea.md);
      never overwrites; prints the path. The only command that writes.
  check DIR [--json]
      Validate both files; one line per finding `severidad código mensaje`.
  datos DIR [--json] [--hoy YYYY-MM-DD]
      The ranked view (schema `morfeo.convocatorias-vista/v1`); text output is
      one line per call: puntaje, estado, días, rol, título.
  fuentes [--json]
      The fixed source catalogue scripts/convocatorias/fuentes.json.

Eligibility rules (scripts/convocatorias/reglas_co.json): the first rule whose
regex matches financiador + programa + titulo (accent- and case-insensitive)
sets the final `rol_colombia` and its `aviso`; a rule never turns an agent
`no_elegible` into a more permissive role, and `estado: pausada` in a rule
marks the call paused. Ranking: `lexico` is the share (0-100) of the profile
tokens (temas + palabras_clave.es + palabras_clave.en, stopwords dropped,
accents folded, a trailing plural «s» dropped from tokens over three letters)
found in titulo + temas + resumen + elegibilidad; `puntaje` is
round-half-up(0.5 * puntaje_agente + 0.5 * lexico), or `lexico` alone without an
agent score. Order: vigentes (estado abierta/proxima and cierre not past)
first; then rol_colombia other than no_elegible; then puntaje desc; then
nearest cierre. A call whose cierre is before hoy is `cerrada`.

Codes: esquema, json-invalido, valor-invalido, fecha-invalida, id-invalido,
id-repetido, campo-faltante, texto-largo, puntaje-fuera-de-rango,
cierre-antes-de-apertura (errors); sin-evidencia, rol-desconocido,
abierta-sin-cierre (warnings); sin-perfil, sin-oportunidades,
regla-rol-distinto (info, the last one from `datos` only).

Library (the dashboard): find_workspace(path), vista(dir, hoy=None),
check(dir), init_profile(dir), load_sources(), load_rules().

Exit codes: 0 ok, 1 error findings (check), 2 bad input (no workspace, bad
date, unreadable catalogue). Standard library only; no network access.
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


def init_profile(path) -> tuple[Path, bool]:
    """Create convocatorias/perfil.json when missing; (path, created). Never overwrites."""
    workspace = find_workspace(path)
    target = workspace / PROFILE_FILE
    if target.exists():
        return target, False
    config = _config(workspace)
    title = config.get("title") or config.get("titulo")
    _write_atomic(target, {
        "schema": PROFILE_SCHEMA,
        "actualizado": None,
        "titulo": title.strip() if isinstance(title, str) and title.strip() else None,
        "idea": _idea(workspace),
        "aplicantes": [],
        "temas": [],
        "palabras_clave": {"es": [], "en": []},
        "financiadores_previos": [],
        "idiomas": ["es", "en"],
        "ambitos": list(SCOPES),
        "institucion": {"nombre": None, "pais": "CO", "tipo": None},
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


def _check_profile(data) -> list[dict]:
    findings: list[dict] = []
    name = PROFILE_FILE.as_posix()
    if not isinstance(data, dict) or data.get("schema") != PROFILE_SCHEMA:
        findings.append(_finding("error", "esquema", f"{name} no declara el esquema {PROFILE_SCHEMA}"))
        if not isinstance(data, dict):
            return findings
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


def _check_call(findings: list[dict], call: dict, seen: set[str]) -> None:
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


def _check_calls(data) -> list[dict]:
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
        _check_call(findings, call, seen)
    return findings


def _check_workspace(workspace: Path) -> tuple[list[dict], dict | None, dict | None]:
    """(findings, profile data, calls data) of a workspace; data is None when missing or unreadable."""
    findings: list[dict] = []
    profile, error = _read_json(workspace / PROFILE_FILE)
    if error:
        findings.append(_finding("error", "json-invalido", f"{PROFILE_FILE.as_posix()}: {error}"))
    elif profile is None:
        findings.append(_finding("info", "sin-perfil",
                                 f"no existe {PROFILE_FILE.as_posix()}; créelo con «convocatorias.py perfil»"))
    else:
        findings.extend(_check_profile(profile))
    calls, error = _read_json(workspace / CALLS_FILE)
    if error:
        findings.append(_finding("error", "json-invalido", f"{CALLS_FILE.as_posix()}: {error}"))
    elif calls is None:
        findings.append(_finding("info", "sin-oportunidades",
                                 f"no existe {CALLS_FILE.as_posix()}; ejecute /propuesta-convocatorias"))
    else:
        findings.extend(_check_calls(calls))
    return findings, profile if isinstance(profile, dict) else None, calls if isinstance(calls, dict) else None


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


def _lexical(call: dict, profile_tokens: set[str]) -> int:
    if not profile_tokens:
        return 0
    parts = [call.get("titulo"), call.get("resumen"), call.get("elegibilidad"), *_strings(call.get("temas"))]
    call_tokens = _tokens(" ".join(p for p in parts if isinstance(p, str)))
    return _round_half_up(100 * len(profile_tokens & call_tokens) / len(profile_tokens))


def _match_rule(rules: list[dict], call: dict) -> dict | None:
    text = _fold(" ".join(str(call.get(k)) for k in ("financiador", "programa", "titulo")
                          if isinstance(call.get(k), str)))
    return next((rule for rule in rules if rule["_re"].search(text)), None)


def _view_call(call: dict, rules: list[dict], profile_tokens: set[str], hoy: datetime.date,
               findings: list[dict]) -> dict:
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
    lexico = _lexical(call, profile_tokens)
    score = call.get("puntaje_agente")
    has_score = isinstance(score, (int, float)) and not isinstance(score, bool)
    out.update({
        "estado": state,
        "dias_restantes": (deadline - hoy).days if deadline is not None else None,
        "vigente": state in CURRENT_STATES,
        "rol_colombia": role,
        "rol_agente": agent_role,
        "regla": rule_ref,
        "aviso": notice,
        "lexico": lexico,
        "puntaje": _round_half_up(0.5 * score + 0.5 * lexico) if has_score else lexico,
    })
    return out


def _sort_key(call: dict):
    deadline = _date(call.get("cierre"))
    return (not call["vigente"], call["rol_colombia"] == "no_elegible", -call["puntaje"],
            deadline is None, deadline or datetime.date.max, str(call.get("id")))


def vista(path, hoy: datetime.date | None = None) -> dict:
    """The ranked view of the workspace's calls (schema morfeo.convocatorias-vista/v1)."""
    workspace = find_workspace(path)
    hoy = hoy or datetime.date.today()
    findings, profile, data = _check_workspace(workspace)
    rules = load_rules()
    profile_tokens, n_keywords = _profile_tokens(profile)
    raw_calls = data.get("oportunidades") if data is not None else None
    calls = [_view_call(c, rules, profile_tokens, hoy, findings)
             for c in (raw_calls if isinstance(raw_calls, list) else []) if isinstance(c, dict)]
    calls.sort(key=_sort_key)
    sources = data.get("fuentes_consultadas") if data is not None else None

    def count(field, keys):
        return {k: sum(1 for c in calls if c.get(field) == k) for k in keys}

    return {
        "schema": VIEW_SCHEMA,
        "hoy": hoy.isoformat(),
        "workspace": str(workspace),
        "perfil": {
            "existe": profile is not None,
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
    p = sub.add_parser("perfil", help="crea convocatorias/perfil.json si no existe")
    p.add_argument("dir", type=Path)
    p = sub.add_parser("check", help="valida perfil.json y oportunidades.json")
    p.add_argument("dir", type=Path)
    p.add_argument("--json", action="store_true", help="imprime los hallazgos en JSON")
    p = sub.add_parser("datos", help="vista ordenada de las convocatorias")
    p.add_argument("dir", type=Path)
    p.add_argument("--json", action="store_true", help="imprime la vista en JSON")
    p.add_argument("--hoy", type=_hoy_arg, help="fecha de referencia AAAA-MM-DD (por defecto, hoy)")
    p = sub.add_parser("fuentes", help="catálogo de fuentes fijas")
    p.add_argument("--json", action="store_true", help="imprime el catálogo en JSON")
    args = parser.parse_args(argv)
    try:
        if args.command == "perfil":
            path, created = init_profile(args.dir)
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
            view = vista(args.dir, hoy=args.hoy)
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
