#!/usr/bin/env python3
"""Deterministic half of the SGR judge (juez-sgr): rubric, checks and scoring.

The juez-sgr agent reads the proposal like a demanding peer and writes one
evaluation round per run of the judge. This script does what must not depend
on the model: it picks and copies the official rubric of the call, gathers the
mechanical evidence the agent needs, validates the round against the rubric,
computes the count-based subcriteria from the project facts, cross-checks the
money figures, sums, decides eligibility and keeps the round history. Standard
library only, like the rest of Morfeo's scripts.

Usage:
  python3 scripts/juez_sgr.py preparar  RUN_ROOT [--rubrica ID|PATH] [--forzar] [--json]
  python3 scripts/juez_sgr.py calificar RUN_ROOT [--json]
  python3 scripts/juez_sgr.py estado    RUN_ROOT [--json]

Files (all under RUN_ROOT/artefactos/juez/):
  rubrica.json              copy of scripts/rubricas_sgr/<id>.json (morfeo.rubrica-sgr/v1)
  verificaciones.json       written by `preparar` (morfeo.verificaciones-juez-sgr/v1)
  datos_sgr.json            facts with source, written by the agent (morfeo.datos-sgr/v1)
  evaluacion_ronda_<N>.json one round, written by the agent (morfeo.evaluacion-sgr/v1)
  evaluacion.json / .md     consolidated result, written by `calificar`
                            (morfeo.evaluacion-sgr-consolidada/v1)

Rubric choice (`preparar`): --rubrica, then the rubric already copied into the
run, then the `deteccion` regexes of each rubric over the text files of
insumos/tdr/ and artefactos/insumos.md. When no rubric (or more than one)
matches, it stops and lists the available ids: it never guesses.

Exit codes: 0 done; 1 the round is invalid (`calificar` still writes
`errores_validacion` into evaluacion.json); 2 missing input, flow is not
SGR (without --forzar) or the rubric cannot be resolved.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RUBRICS_DIR = SCRIPT_DIR / "rubricas_sgr"
GUIDE_FILE = RUBRICS_DIR / "_guia_comun.json"
JUEZ_DIR = Path("artefactos") / "juez"
SECTIONS_DIR = Path("redaccion") / "sections"

RUBRIC_SCHEMA = "morfeo.rubrica-sgr/v1"
DATA_SCHEMA = "morfeo.datos-sgr/v1"
ROUND_SCHEMA = "morfeo.evaluacion-sgr/v1"
CONSOLIDATED_SCHEMA = "morfeo.evaluacion-sgr-consolidada/v1"
CHECKS_SCHEMA = "morfeo.verificaciones-juez-sgr/v1"

MODES = ("niveles", "acumulable", "conteo")
COUNT_TYPES = ("departamentos", "trayectoria", "alianza", "arraigo", "aliado_internacional", "cofinanciacion",
               "contrapartida_efectivo")
AGENTS = ("redactor", "investigador", "presupuestador", "disenador-tikz", "bibliografo-propuesta",
          "grant-flow-auditor", "usuario")
SEVERITIES = ("error", "advertencia", "info")
ALERT_TYPES = ("inconsistencia", "faltante", "riesgo_puntaje", "forma")
REQUIREMENT_CONDITIONS = ("etica", "internacional", "sector_productivo", "sociedad_civil", "infraestructura",
                          "inmuebles", "cofinanciacion", "desastre", "otro")
REQUIREMENT_KEYS = ("id", "nombre", "texto", "documento", "numeral_fuente")
ROUND_RE = re.compile(r"^evaluacion_ronda_(\d+)\.json$")
TEXT_SUFFIXES = {".txt", ".md", ".tex", ".csv", ".json", ".html", ".htm", ".xml"}
MONEY_TOLERANCE = 0.5  # pesos: any whole-peso difference counts

TRL_RE = re.compile(r"\bTRL\b[^0-9\n.;]{0,25}?(\d)\b")
TRL_ENTRY_RE = re.compile(r"entrada|inicial|partida|actual|de\s+inicio", re.I)
TRL_EXIT_RE = re.compile(r"salida|final|alcanz\w*|lleg\w*|comprometid\w*", re.I)
LABEL_RE = re.compile(r"\\label\{([^}]*)\}")
EMPTY_CAPTION_RE = re.compile(r"\\caption(?:\[[^\]]*\])?\{\s*\}")


class JuezError(Exception):
    """Missing or unusable input: the command stops with exit code 2."""


# --- Small helpers ------------------------------------------------------------

def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise JuezError(f"No existe {path}.") from None
    except (OSError, ValueError) as exc:
        raise JuezError(f"{path} no es un JSON válido: {exc}") from None


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _num(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _money(value: float) -> str:
    return f"${value:,.0f}".replace(",", ".")


def _today() -> str:
    return datetime.date.today().isoformat()


def _load_check_run():
    path = SCRIPT_DIR / "check_run.py"
    spec = importlib.util.spec_from_file_location("juez_check_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iter_subcriteria(rubric: dict):
    for criterion in rubric.get("criterios") or []:
        for sub in criterion.get("subcriterios") or []:
            yield criterion, sub


# --- Rubric -------------------------------------------------------------------

def available_rubrics() -> list[str]:
    return sorted(p.stem for p in RUBRICS_DIR.glob("*.json") if not p.name.startswith("_"))


def _guide_families() -> set[str] | None:
    try:
        return set(json.loads(GUIDE_FILE.read_text(encoding="utf-8")).get("familias", {}))
    except (OSError, ValueError):
        return None


def validate_rubric(rubric) -> list[str]:
    """Errors that make a rubric unusable (empty list when it is valid)."""
    if not isinstance(rubric, dict):
        return ["La rúbrica no es un objeto JSON."]
    errors: list[str] = []
    if rubric.get("schema") != RUBRIC_SCHEMA:
        errors.append(f"schema debe ser {RUBRIC_SCHEMA}.")
    for key in ("id", "convocatoria", "fuente"):
        if not isinstance(rubric.get(key), str) or not rubric.get(key):
            errors.append(f"Falta el campo de texto '{key}'.")
    for pattern in rubric.get("deteccion") or []:
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"Regex de detección inválida {pattern!r}: {exc}")
    eligibility = rubric.get("elegibilidad") or {}
    if not _is_int(eligibility.get("umbral_total")):
        errors.append("elegibilidad.umbral_total debe ser entero.")
    justification = rubric.get("justificacion") or {}
    if not (_is_int(justification.get("min_chars")) and _is_int(justification.get("max_chars"))):
        errors.append("justificacion necesita min_chars y max_chars enteros.")
    if not _is_int((rubric.get("concepto") or {}).get("min_palabras")):
        errors.append("concepto.min_palabras debe ser entero.")
    criteria = rubric.get("criterios")
    if not isinstance(criteria, list) or not criteria:
        return errors + ["La rúbrica necesita una lista 'criterios' no vacía."]
    families = _guide_families()
    seen: set[str] = set()
    criterion_ids = set()
    for criterion in criteria:
        cid = criterion.get("id")
        criterion_ids.add(cid)
        subs = criterion.get("subcriterios") or []
        if not subs:
            errors.append(f"El criterio {cid} no tiene subcriterios.")
        if sum(s.get("max", 0) for s in subs if _is_int(s.get("max"))) != criterion.get("max"):
            errors.append(f"Los subcriterios del criterio {cid} no suman su máximo ({criterion.get('max')}).")
        for sub in subs:
            sid = sub.get("id")
            if sid in seen:
                errors.append(f"Subcriterio repetido: {sid}.")
            seen.add(sid)
            errors.extend(_validate_subcriterion(sub, families))
    total = sum(c.get("max", 0) for c in criteria if _is_int(c.get("max")))
    if rubric.get("total") != total:
        errors.append(f"total ({rubric.get('total')}) no coincide con la suma de los criterios ({total}).")
    for minimum in eligibility.get("minimos") or []:
        if minimum.get("criterio") not in criterion_ids:
            errors.append(f"Mínimo sobre un criterio inexistente: {minimum.get('criterio')}.")
    for key in ("minimos_talento", "minimo_productos"):
        if key in rubric and not _valid_minimums(rubric[key]):
            errors.append(f"{key} debe ser una lista de {{categoria, cantidad entera, texto}} (texto literal del TdR).")
    if "requisitos" in rubric and not _valid_requirements(rubric["requisitos"]):
        errors.append("requisitos debe ser una lista de {id único, nombre, texto, condicion (null o una condición "
                      "conocida), documento, numeral_fuente} (textos literales del TdR).")
    for _, sub in iter_subcriteria(rubric):
        for part in sub.get("componentes") or []:
            if "verificacion" in part and not (isinstance(part["verificacion"], str) and part["verificacion"]):
                errors.append(f"{sub.get('id')}: componentes.{part.get('id')}.verificacion debe ser texto.")
    return errors


def _valid_requirements(value) -> bool:
    """Optional enabling requirements of the call (read by scripts/requisitos_sgr.py)."""
    if not isinstance(value, list):
        return False
    ids = [r.get("id") for r in value if isinstance(r, dict)]
    return len(ids) == len(value) and len(set(ids)) == len(ids) and all(
        all(isinstance(r.get(key), str) and r[key].strip() for key in REQUIREMENT_KEYS)
        and (r.get("condicion") is None or r.get("condicion") in REQUIREMENT_CONDITIONS) for r in value)


def _valid_minimums(value) -> bool:
    """Optional talent and product minimums of the call (read by scripts/productos_sgr.py)."""
    return isinstance(value, list) and all(
        isinstance(m, dict) and isinstance(m.get("categoria"), str) and m["categoria"]
        and _is_int(m.get("cantidad")) and m["cantidad"] >= 0
        and isinstance(m.get("texto"), str) and m["texto"] for m in value)


def _validate_subcriterion(sub: dict, families: set[str] | None) -> list[str]:
    sid, top, mode = sub.get("id"), sub.get("max"), sub.get("modo")
    errors: list[str] = []
    if not _is_int(top):
        return [f"{sid}: max debe ser entero."]
    if mode not in MODES:
        return [f"{sid}: modo desconocido {mode!r}."]
    if mode == "niveles":
        points = [level.get("puntos") for level in sub.get("niveles") or []]
        if not points or not all(_is_int(p) and 0 <= p <= top for p in points):
            errors.append(f"{sid}: los niveles deben ser enteros entre 0 y {top}.")
        elif max(points) != top:
            errors.append(f"{sid}: el nivel más alto ({max(points)}) no es el máximo ({top}).")
    elif mode == "acumulable":
        parts = sub.get("componentes") or []
        if not parts or not all(isinstance(p.get("id"), str) and _is_int(p.get("max")) for p in parts):
            errors.append(f"{sid}: un subcriterio acumulable necesita componentes con id y max.")
        elif sum(p["max"] for p in parts) < top:
            errors.append(f"{sid}: los componentes no alcanzan el máximo ({top}).")
    else:
        rule = sub.get("regla_conteo") or {}
        if rule.get("tipo") not in COUNT_TYPES:
            errors.append(f"{sid}: regla_conteo.tipo desconocido {rule.get('tipo')!r}.")
    if families is not None and sub.get("familia") not in families:
        errors.append(f"{sid}: familia {sub.get('familia')!r} no existe en _guia_comun.json.")
    for agent in sub.get("agentes") or []:
        if agent not in AGENTS:
            errors.append(f"{sid}: agente desconocido {agent!r}.")
    return errors


def _rubric_from_flag(flag: str) -> tuple[Path, str]:
    path = Path(flag)
    if path.is_file():
        return path, f"--rubrica {flag}"
    candidate = RUBRICS_DIR / f"{flag}.json"
    if candidate.is_file() and not flag.startswith("_"):
        return candidate, f"--rubrica {flag}"
    raise JuezError(f"No encuentro la rúbrica «{flag}». Disponibles: {', '.join(available_rubrics())}.")


def _tdr_texts(run: Path) -> list[tuple[str, str]]:
    texts = []
    tdr_dir = run / "insumos" / "tdr"
    files = sorted(p for p in tdr_dir.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES) \
        if tdr_dir.is_dir() else []
    notes = run / "artefactos" / "insumos.md"
    if notes.is_file():
        files.append(notes)
    for path in files:
        try:
            texts.append((path.relative_to(run).as_posix(), path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return texts


def detect_rubric(run: Path) -> tuple[Path, str]:
    texts = _tdr_texts(run)
    matches: dict[str, str] = {}
    for rid in available_rubrics():
        rubric = json.loads((RUBRICS_DIR / f"{rid}.json").read_text(encoding="utf-8"))
        for name, text in texts:
            if any(re.search(p, text, re.I) for p in rubric.get("deteccion") or []):
                matches[rid] = name
                break
    ids = ", ".join(available_rubrics())
    if len(matches) == 1:
        rid, name = next(iter(matches.items()))
        return RUBRICS_DIR / f"{rid}.json", f"detectada en {name}"
    if not matches:
        where = "insumos/tdr/ ni artefactos/insumos.md" if texts else \
            "ningún archivo de texto en insumos/tdr/ ni artefactos/insumos.md"
        raise JuezError(f"No pude detectar la convocatoria: no hay coincidencias en {where}. "
                        f"Elige la rúbrica con --rubrica ID. Disponibles: {ids}.")
    raise JuezError(f"El TdR coincide con varias convocatorias ({', '.join(sorted(matches))}). "
                    f"Elige la rúbrica con --rubrica ID. Disponibles: {ids}.")


def resolve_rubric(run: Path, flag: str | None) -> tuple[dict, str, bytes]:
    """(rubric, origin, raw bytes): flag > copy in the run > TdR detection."""
    in_run = run / JUEZ_DIR / "rubrica.json"
    if flag:
        path, origin = _rubric_from_flag(flag)
    elif in_run.is_file():
        path, origin = in_run, "ya copiada en la corrida"
    else:
        path, origin = detect_rubric(run)
    raw = path.read_bytes()
    rubric = _read_json(path)
    errors = validate_rubric(rubric)
    if errors:
        raise JuezError(f"La rúbrica {path} no es válida:\n  - " + "\n  - ".join(errors))
    return rubric, origin, raw


# --- Evidence gathered by `preparar` ------------------------------------------

def _strip_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def word_count(tex: str) -> int:
    text = _strip_comments(tex)
    text = re.sub(r"\\(begin|end)\{[^}]*\}", " ", text)
    text = re.sub(r"\\(label|ref|cref|eqref|input|includegraphics|cite\w*)(\[[^\]]*\])*\{[^}]*\}", " ", text)
    text = re.sub(r"\\[A-Za-z@]+\*?", " ", text)
    return len(re.findall(r"[^\W\d_]+", text))


def _section_files(run: Path) -> dict[str, Path]:
    sec_dir = run / SECTIONS_DIR
    return {p.stem: p for p in sorted(sec_dir.glob("*.tex"))} if sec_dir.is_dir() else {}


def _latex_issues(run: Path, files: dict[str, Path]) -> dict:
    labels: dict[str, list[str]] = {}
    empty_captions = []
    for stem, path in files.items():
        text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        rel = path.relative_to(run).as_posix()
        for label in LABEL_RE.findall(text):
            labels.setdefault(label, []).append(rel)
        for number, line in enumerate(text.splitlines(), 1):
            if EMPTY_CAPTION_RE.search(line):
                empty_captions.append({"archivo": rel, "linea": number})
        if stem.endswith("_caption") and not text.strip():
            empty_captions.append({"archivo": rel, "linea": None})
    duplicated = [{"label": k, "archivos": v} for k, v in sorted(labels.items()) if len(v) > 1]
    return {"labels_duplicados": duplicated, "captions_vacios": empty_captions}


def _nearest(pattern: re.Pattern, text: str, start: int, end: int) -> int | None:
    distances = []
    for match in pattern.finditer(text):
        if match.end() <= start:
            distances.append(start - match.end())
        elif match.start() >= end:
            distances.append(match.start() - end)
    distances = [d for d in distances if d <= 40]
    return min(distances) if distances else None


def trl_mentions(run: Path, files: dict[str, Path]) -> dict:
    """Explicit TRL levels, classified as entry or exit by the nearest keyword."""
    found = {"entrada": set(), "salida": set(), "otros": set()}
    menciones = []
    for path in files.values():
        rel = path.relative_to(run).as_posix()
        for number, line in enumerate(_strip_comments(path.read_text(encoding="utf-8", errors="replace"))
                                      .splitlines(), 1):
            for match in TRL_RE.finditer(line):
                level = int(match.group(1))
                entry = _nearest(TRL_ENTRY_RE, line, match.start(), match.end())
                leave = _nearest(TRL_EXIT_RE, line, match.start(), match.end())
                if entry is not None and (leave is None or entry < leave):
                    kind = "entrada"
                elif leave is not None:
                    kind = "salida"
                else:
                    kind = "otros"
                found[kind].add(level)
                menciones.append({"archivo": rel, "linea": number, "nivel": level, "tipo": kind,
                                  "texto": line.strip()[:200]})
    result = {kind: sorted(levels) for kind, levels in found.items()}
    result["menciones"] = menciones
    return result


def _run_check_run(run: Path) -> dict:
    try:
        report = _load_check_run().run_checks(run, final=False)
    except Exception as exc:  # the judge must not die because a sibling check failed
        return {"error": f"check_run falló: {exc}", "errores": 0, "avisos": 0, "hallazgos": []}
    errors = sum(1 for f in report.findings if f.get("severity") == "error")
    return {"flujo": report.flujo, "errores": errors, "avisos": len(report.findings) - errors,
            "hallazgos": report.findings}


def build_verifications(run: Path, rubric: dict, next_round: int) -> dict:
    files = _section_files(run)
    words = {stem: word_count(path.read_text(encoding="utf-8", errors="replace")) for stem, path in files.items()}
    coverage = []
    for criterion, sub in iter_subcriteria(rubric):
        evidence = [{"clave": key, "archivo": (SECTIONS_DIR / f"{key}.tex").as_posix(), "existe": key in files,
                     "palabras": words.get(key, 0)} for key in sub.get("evidencia") or []]
        coverage.append({"subcriterio": sub["id"], "criterio": criterion["id"], "nombre": sub["nombre"],
                         "modo": sub["modo"], "evidencia": evidence,
                         "palabras_total": sum(e["palabras"] for e in evidence),
                         "faltantes": [e["clave"] for e in evidence if not e["existe"]]})
    return {
        "schema": CHECKS_SCHEMA,
        "fecha": _today(),
        "rubrica": rubric["id"],
        "ronda_siguiente": next_round,
        "datos_sgr_existe": (run / JUEZ_DIR / "datos_sgr.json").is_file(),
        "estructura_tdr_existe": (run / "artefactos" / "estructura_tdr.json").is_file(),
        "secciones": [{"archivo": (SECTIONS_DIR / f"{stem}.tex").as_posix(), "palabras": words[stem]}
                      for stem in files],
        "cobertura": coverage,
        "check_run": _run_check_run(run),
        "latex": _latex_issues(run, files),
        "trl": trl_mentions(run, files),
    }


def _round_numbers(run: Path) -> list[int]:
    folder = run / JUEZ_DIR
    if not folder.is_dir():
        return []
    return sorted(int(m.group(1)) for p in folder.iterdir() if (m := ROUND_RE.match(p.name)))


# --- Count-based subcriteria ------------------------------------------------------

def _tiers(value: float, tiers: list[dict]) -> int:
    for tier in tiers:
        limit = tier["valor"]
        if (tier["op"] == ">" and value > limit) or (tier["op"] == ">=" and value >= limit):
            return tier["puntos"]
    return 0


def _sgr_amount(datos: dict) -> float | None:
    amount = datos.get("monto_sgr")
    return _num(amount.get("valor")) if isinstance(amount, dict) else _num(amount)


def _members(datos: dict) -> list[dict] | None:
    allies = datos.get("aliados")
    if not isinstance(allies, list):
        return None
    proponent = datos.get("proponente") if isinstance(datos.get("proponente"), dict) else {}
    return [{**proponent, "_proponente": True}] + [a for a in allies if isinstance(a, dict)]


def counterpart_sum(datos: dict, kinds=("contrapartida_especie", "contrapartida_efectivo")) -> tuple[float | None, bool]:
    """(sum of the counterparts of every member, any value unknown). The
    proponent counts when it declares its own counterpart fields."""
    members = _members(datos)
    if members is None:
        return None, True
    total, unknown = 0.0, False
    for member in members:
        for kind in kinds:
            if member.get("_proponente") and kind not in member:
                continue
            value = _num(member.get(kind))
            if value is None:
                unknown = True
            else:
                total += value
    return total, unknown


def _alliance_category(members: list[dict], categories: list[dict]) -> tuple[str | None, dict]:
    count = {kind: sum(1 for m in members if m.get("tipo") == kind)
             for kind in ("IES", "SNCTI", "entidad_territorial", "usuario_adoptante", "internacional")}
    n = len(members)
    ies, sncti, terr, users, intl = (count[k] for k in ("IES", "SNCTI", "entidad_territorial",
                                                        "usuario_adoptante", "internacional"))
    basic = ies >= 1 and ies + sncti >= 2 and terr >= 1 and users >= 1 and terr + users >= 3
    media = basic and ies + sncti + intl >= 3 and terr >= 2 and users >= 2
    meets = {"basica": basic, "media": media, "avanzada": media}
    for category in categories:  # highest first in the rubric
        if n >= category["min_integrantes"] and meets.get(category["id"]):
            return category["id"], {"integrantes": n, **count}
    return None, {"integrantes": n, **count}


def compute_conteo(sub: dict, datos: dict) -> dict:
    """{puntaje, incompleto, calculo} of a `conteo` subcriterion. Unknown
    (null) facts score 0 and mark the result incomplete."""
    rule = sub["regla_conteo"]
    kind = rule["tipo"]
    datos = datos if isinstance(datos, dict) else {}

    def result(points: int, incomplete: bool, text: str) -> dict:
        return {"puntaje": min(points, sub["max"]), "incompleto": incomplete, "calculo": text}

    if kind == "departamentos":
        deps = datos.get("departamentos_ejecucion")
        if not isinstance(deps, list):
            return result(0, True, "departamentos_ejecucion es null: no se puede contar.")
        names = {str(d.get("nombre") if isinstance(d, dict) else d).strip().casefold() for d in deps}
        names.discard("none")
        return result(_tiers(len(names), rule["tramos"]), False, f"{len(names)} departamento(s) de ejecución.")

    if kind == "trayectoria":
        data = datos.get("trayectoria") if isinstance(datos.get("trayectoria"), dict) else {}
        extra, sgr = data.get("proyectos_adicionales"), data.get("proyectos_sgr_o_elegibles")
        if not (_is_int(extra) and _is_int(sgr)):
            return result(0, True, "trayectoria.proyectos_adicionales o proyectos_sgr_o_elegibles es null.")
        base = _tiers(extra, rule["escala"])
        note = ""
        if base == rule["puntos_tope_requiere_sgr"] and sgr < 1:
            base, note = rule["puntos_sin_sgr"], " (sin proyecto SGR o elegible: escala de tres proyectos)"
        bonus = sgr * rule["punto_por_proyecto_sgr"] if extra >= rule["min_adicionales_para_punto_sgr"] else 0
        points = min(base + bonus, rule["tope"])
        return result(points, False, f"{extra} proyecto(s) adicional(es): escala {base}{note}; "
                                     f"+{bonus} por proyectos SGR o elegibles; tope {rule['tope']}.")

    if kind == "alianza":
        members = _members(datos)
        if members is None:
            return result(0, True, "aliados es null: no se puede verificar la composición.")
        unknown = [m for m in members if m.get("tipo") is None]
        category, count = _alliance_category(members, rule["categorias"])
        points = next((c["puntos"] for c in rule["categorias"] if c["id"] == category), 0)
        text = (f"{count['integrantes']} integrantes con el proponente (IES {count['IES']}, SNCTI {count['SNCTI']}, "
                f"entidades territoriales {count['entidad_territorial']}, usuarios {count['usuario_adoptante']}, "
                f"internacionales {count['internacional']}): " + (f"alianza {category}." if category else
                                                                   "no cumple la alianza básica."))
        if unknown:
            text += f" {len(unknown)} integrante(s) sin tipo declarado."
        return result(points, bool(unknown), text)

    if kind == "arraigo":
        proponent = datos.get("proponente") if isinstance(datos.get("proponente"), dict) else {}
        home, diverse = proponent.get("domicilio_en_region"), proponent.get("tipo_diverso")
        points = (rule["puntos_domicilio"] if home is True else 0) + (rule["puntos_tipo_diverso"] if diverse is True
                                                                       else 0)
        incomplete = not isinstance(home, bool) or not isinstance(diverse, bool)
        return result(min(points, rule["tope"]), incomplete,
                      f"domicilio en la región: {home}; entidad territorial, comunitaria, étnica o MIPYME: {diverse}.")

    if kind == "aliado_internacional":
        value = datos.get("aliado_internacional_con_aporte")
        if not isinstance(value, bool):
            return result(0, True, "aliado_internacional_con_aporte es null.")
        return result(rule["puntos"] if value else 0, False, f"aliado internacional con aporte: {value}.")

    if kind in ("cofinanciacion", "contrapartida_efectivo"):
        amount = _sgr_amount(datos)
        kinds = ("contrapartida_efectivo",) if kind == "contrapartida_efectivo" else \
            ("contrapartida_especie", "contrapartida_efectivo")
        total, unknown = counterpart_sum(datos, kinds)
        label = "contrapartida en efectivo" if kind == "contrapartida_efectivo" else "cofinanciación"
        if total is None and kind == "cofinanciacion":
            declared = [_num(t.get("valor")) for t in datos.get("totales_declarados") or []
                        if isinstance(t, dict) and t.get("concepto") == "contrapartida"]
            declared = [d for d in declared if d is not None]
            if declared:
                total, unknown = declared[0], False
        if amount is None or amount <= 0 or total is None:
            return result(0, True, f"monto_sgr o los aportes de la alianza son null: no se calcula la {label}.")
        pct = 100.0 * total / amount
        return result(_tiers(pct, rule["tramos"]), unknown,
                      f"{label} {_money(total)} = {pct:.2f} % de {_money(amount)} solicitados al SGR.")

    raise ValueError(f"regla_conteo desconocida: {kind}")


# --- Round validation -----------------------------------------------------------

def _justification_range(rubric: dict, criterion_id: str, sub_id: str) -> tuple[int, int]:
    spec = rubric["justificacion"]
    exceptions = spec.get("excepciones") or {}
    low_high = exceptions.get(sub_id) or exceptions.get(criterion_id)
    return tuple(low_high) if low_high else (spec["min_chars"], spec["max_chars"])


def validate_round(data, rubric: dict, number: int) -> list[str]:
    if not isinstance(data, dict):
        return ["La ronda no es un objeto JSON."]
    errors: list[str] = []
    if "schema" in data and data["schema"] != ROUND_SCHEMA:
        errors.append(f"schema debe ser {ROUND_SCHEMA}.")
    if data.get("ronda") != number:
        errors.append(f"ronda vale {data.get('ronda')!r} pero el archivo es evaluacion_ronda_{number}.json.")
    if data.get("rubrica") != rubric["id"]:
        errors.append(f"rubrica vale {data.get('rubrica')!r}; la corrida usa {rubric['id']}.")
    subs = {sub["id"]: (criterion, sub) for criterion, sub in iter_subcriteria(rubric)}
    known_ids = set(subs) | {c["id"] for c in rubric["criterios"]}
    entries = data.get("criterios")
    if not isinstance(entries, list):
        return errors + ["criterios debe ser una lista con un elemento por subcriterio."]
    seen: dict[str, int] = {}
    for entry in entries:
        sid = entry.get("id") if isinstance(entry, dict) else None
        if sid not in subs:
            errors.append(f"Subcriterio desconocido en la ronda: {sid!r}.")
            continue
        seen[sid] = seen.get(sid, 0) + 1
        errors.extend(_validate_entry(entry, *subs[sid], rubric))
    for sid, times in seen.items():
        if times > 1:
            errors.append(f"El subcriterio {sid} aparece {times} veces.")
    for sid in subs:
        if sid not in seen:
            errors.append(f"Falta el subcriterio {sid}.")
    errors.extend(_validate_alerts(data.get("alertas"), known_ids))
    errors.extend(_validate_actions(data.get("acciones"), known_ids))
    concept = data.get("concepto")
    min_words = rubric["concepto"]["min_palabras"]
    words = len(concept.split()) if isinstance(concept, str) else 0
    if words < min_words:
        errors.append(f"El concepto final tiene {words} palabras (mínimo {min_words}).")
    if not isinstance(data.get("recomienda"), bool):
        errors.append("recomienda debe ser true o false.")
    return errors


def _validate_entry(entry: dict, criterion: dict, sub: dict, rubric: dict) -> list[str]:
    sid, mode, errors = sub["id"], sub["modo"], []
    text = entry.get("justificacion")
    low, high = _justification_range(rubric, criterion["id"], sid)
    length = len(text.strip()) if isinstance(text, str) else 0
    if not low <= length <= high:
        errors.append(f"{sid}: la justificación tiene {length} caracteres (debe tener entre {low} y {high}).")
    evidence = entry.get("evidencia")
    if not isinstance(evidence, list) or not all(isinstance(e, dict) and isinstance(e.get("ubicacion"), str)
                                                 and isinstance(e.get("cita"), str) for e in evidence):
        errors.append(f"{sid}: evidencia debe ser una lista de {{ubicacion, cita}}.")
        evidence = []
    score = entry.get("puntaje")
    if mode == "niveles":
        allowed = sorted({level["puntos"] for level in sub["niveles"]})
        if not _is_int(score) or score not in allowed:
            errors.append(f"{sid}: puntaje {score!r} no está en la escala oficial {allowed}.")
        elif score > 0 and not evidence:
            errors.append(f"{sid}: un puntaje mayor que 0 necesita evidencia ubicada en el documento.")
    elif mode == "acumulable":
        parts = entry.get("componentes")
        spec = {p["id"]: p["max"] for p in sub["componentes"]}
        if not isinstance(parts, dict) or set(parts) != set(spec):
            errors.append(f"{sid}: componentes debe traer exactamente {sorted(spec)}.")
        else:
            bad = [f"{sid}: el componente {pid} vale {value!r} (entero entre 0 y {spec[pid]})."
                   for pid, value in parts.items() if not _is_int(value) or not 0 <= value <= spec[pid]]
            errors.extend(bad)
            if not bad:
                capped = min(sum(parts.values()), sub["max"])
                if score is not None and score != capped:
                    errors.append(f"{sid}: puntaje {score!r} no coincide con la suma de componentes ({capped}).")
                if capped > 0 and not evidence:
                    errors.append(f"{sid}: un puntaje mayor que 0 necesita evidencia ubicada en el documento.")
    target = entry.get("para_subir")
    if target is not None and not (isinstance(target, dict) and isinstance(target.get("que_falta"), str)):
        errors.append(f"{sid}: para_subir debe ser null o {{puntaje_objetivo, que_falta}}.")
    return errors


def _validate_alerts(alerts, known_ids: set[str]) -> list[str]:
    if not isinstance(alerts, list):
        return ["alertas debe ser una lista."]
    errors = []
    for alert in alerts:
        if not isinstance(alert, dict):
            errors.append("Cada alerta debe ser un objeto.")
            continue
        aid = alert.get("id")
        if alert.get("severidad") not in SEVERITIES:
            errors.append(f"Alerta {aid}: severidad {alert.get('severidad')!r} no es {'|'.join(SEVERITIES)}.")
        if alert.get("tipo") not in ALERT_TYPES:
            errors.append(f"Alerta {aid}: tipo {alert.get('tipo')!r} no es {'|'.join(ALERT_TYPES)}.")
        if not isinstance(alert.get("mensaje"), str) or not alert.get("mensaje").strip():
            errors.append(f"Alerta {aid}: falta el mensaje.")
        for cid in alert.get("criterios") or []:
            if cid not in known_ids:
                errors.append(f"Alerta {aid}: criterio desconocido {cid!r}.")
    return errors


def _validate_actions(actions, known_ids: set[str]) -> list[str]:
    if not isinstance(actions, list):
        return ["acciones debe ser una lista."]
    errors = []
    for action in actions:
        if not isinstance(action, dict):
            errors.append("Cada acción debe ser un objeto.")
            continue
        aid = action.get("id")
        if action.get("agente") not in AGENTS:
            errors.append(f"Acción {aid}: agente {action.get('agente')!r} no es uno de {', '.join(AGENTS)}.")
        if action.get("prioridad") not in (1, 2, 3) or isinstance(action.get("prioridad"), bool):
            errors.append(f"Acción {aid}: prioridad debe ser 1, 2 o 3.")
        if not isinstance(action.get("instruccion"), str) or not action.get("instruccion").strip():
            errors.append(f"Acción {aid}: falta la instrucción.")
        for cid in action.get("criterios") or []:
            if cid not in known_ids:
                errors.append(f"Acción {aid}: criterio desconocido {cid!r}.")
    return errors


# --- Scoring and cross-checks ------------------------------------------------------

def _ids_by_family(rubric: dict, *families: str) -> list[str]:
    return [sub["id"] for _, sub in iter_subcriteria(rubric) if sub.get("familia") in families]


def cross_checks(rubric: dict, datos: dict, scores: dict[str, dict]) -> list[dict]:
    """Deterministic alerts from datos_sgr.json and the resolved scores."""
    alerts: list[dict] = []

    def add(code, severity, kind, message, criteria, **extra):
        alerts.append({"id": f"V{len(alerts) + 1}", "codigo": code, "severidad": severity, "tipo": kind,
                       "mensaje": message, "ubicacion": (JUEZ_DIR / "datos_sgr.json").as_posix(),
                       "criterios": criteria, "origen": "juez_sgr.py", **extra})

    amount = _sgr_amount(datos)
    cap = rubric.get("tope_solicitud_sgr")
    if amount is not None and _num(cap) is not None and amount > cap:
        add("tope-solicitud", "error", "inconsistencia",
            f"El valor solicitado al SGR ({_money(amount)}) supera el tope de la convocatoria ({_money(cap)}): "
            "es condición inhabilitante.", [], inhabilitante=True)

    declared: dict[str, list[tuple[str, float]]] = {}
    for item in datos.get("totales_declarados") or []:
        if isinstance(item, dict) and _num(item.get("valor")) is not None:
            declared.setdefault(str(item.get("concepto")), []).append((str(item.get("documento")),
                                                                       _num(item["valor"])))
    budget_ids = _ids_by_family(rubric, "presupuesto")
    for concept, values in declared.items():
        if max(v for _, v in values) - min(v for _, v in values) > MONEY_TOLERANCE:
            listed = "; ".join(f"{doc}: {_money(v)}" for doc, v in values)
            add("totales-distintos", "error", "inconsistencia",
                f"El total «{concept}» cambia entre documentos ({listed}).", budget_ids)

    total, unknown = counterpart_sum(datos)
    if total is not None and not unknown:
        for doc, value in declared.get("contrapartida", []):
            if abs(value - total) > MONEY_TOLERANCE:
                add("contrapartida-no-cuadra", "error", "inconsistencia",
                    f"La suma de las contrapartidas de la alianza ({_money(total)}) no coincide con la contrapartida "
                    f"declarada en {doc} ({_money(value)}).", budget_ids + _ids_by_family(rubric, "cofinanciacion"))

    transfer = _num(datos.get("transferencia_valor"))
    if transfer is not None and amount:
        if transfer < 0.01 * amount:
            add("transferencia-baja", "advertencia", "riesgo_puntaje",
                f"El valor del plan de transferencia ({_money(transfer)}) es menor que el 1 % del valor solicitado "
                f"al SGR ({_money(0.01 * amount)}).", _ids_by_family(rubric, "transferencia"))

    trl = datos.get("trl") if isinstance(datos.get("trl"), dict) else {}
    declared_exit = _num(trl.get("salida"))
    for _, sub in iter_subcriteria(rubric):
        mapping = sub.get("trl_salida_por_puntaje")
        score = scores.get(sub["id"], {}).get("puntaje")
        if not mapping or not score or declared_exit is None:
            continue
        expected = mapping.get(str(score))
        if expected is not None and expected != declared_exit:
            add("trl-inconsistente", "advertencia", "inconsistencia",
                f"El nivel asignado en {sub['id']} ({score} puntos) corresponde a TRL {expected}, pero datos_sgr.json "
                f"declara TRL de salida {declared_exit:g}.", [sub["id"]])

    products = datos.get("productos_adicionales") if isinstance(datos.get("productos_adicionales"), dict) else {}
    n_total, n_top = products.get("total"), products.get("top_o_a")
    for _, sub in iter_subcriteria(rubric):
        parts = scores.get(sub["id"], {}).get("componentes")
        if sub.get("familia") != "productos_divulgacion" or not isinstance(parts, dict) or "A" not in parts:
            continue
        if _is_int(n_total) and _is_int(n_top):
            expected = 3 if n_total >= 3 and n_top >= 2 else 2 if n_total >= 2 and n_top >= 1 else \
                1 if n_total >= 1 else 0
            if parts["A"] != expected:
                add("productos-inconsistentes", "advertencia", "inconsistencia",
                    f"El componente A de {sub['id']} vale {parts['A']}, pero productos_adicionales "
                    f"({n_total}, {n_top} TOP o A) da {expected}.", [sub["id"]])

    requirements = datos.get("requisitos") if isinstance(datos.get("requisitos"), dict) else {}
    for rid in requirements.get("pendientes") or []:
        add("requisito-pendiente", "advertencia", "faltante",
            f"El requisito habilitante {rid} aplica y no está listo (requisitos_sgr.py): «se tendrá por no cumplida "
            "toda condición que no haya sido soportada documentalmente».", [])
    differences = [d for d in datos.get("cifras_diferencias") or [] if isinstance(d, dict)]
    for diff in differences:
        declared, expected = _num(diff.get("declarado")), _num(diff.get("esperado"))
        add("cifras-distintas", "error", "inconsistencia",
            f"La cifra {diff.get('campo')} declarada en {diff.get('documento')} "
            f"({_money(declared) if declared is not None else diff.get('declarado')}) no coincide con el presupuesto "
            f"o la alianza ({_money(expected) if expected is not None else diff.get('esperado')}).", budget_ids)
    if not differences and datos.get("cifras_coherentes") is False:
        add("cifras-distintas", "error", "inconsistencia",
            "Las cifras declaradas en el SIGP, el Anexo 1, el Anexo 3 o la MGA Web no coinciden con el presupuesto o "
            "la alianza (requisitos_sgr.py check).", budget_ids)
    return alerts


def _history(previous: dict | None, entry: dict) -> list[dict]:
    history = [h for h in (previous or {}).get("historial") or []
               if isinstance(h, dict) and h.get("ronda") != entry["ronda"]]
    return sorted(history + [entry], key=lambda h: h.get("ronda") or 0)


def consolidate(rubric: dict, data: dict, datos: dict | None, previous: dict | None) -> dict:
    entries = {e["id"]: e for e in data["criterios"]}
    datos_missing = datos is None
    datos = datos or {}
    resolved, scores, subtotals, notes = [], {}, {}, []
    incomplete = datos_missing
    for criterion, sub in iter_subcriteria(rubric):
        entry = dict(entries[sub["id"]])
        entry.update({"criterio": criterion["id"], "nombre": sub["nombre"], "max": sub["max"], "modo": sub["modo"]})
        if sub["modo"] == "acumulable":
            entry["puntaje"] = min(sum(entry["componentes"].values()), sub["max"])
        elif sub["modo"] == "conteo":
            if entry.get("puntaje") is not None:
                notes.append(sub["id"])
            entry.update(compute_conteo(sub, datos))
            incomplete = incomplete or entry["incompleto"]
        scores[sub["id"]] = entry
        subtotals[criterion["id"]] = subtotals.get(criterion["id"], 0) + entry["puntaje"]
        resolved.append(entry)

    alerts = cross_checks(rubric, datos, scores)

    def add(code, severity, kind, message, criteria):
        alerts.append({"id": f"V{len(alerts) + 1}", "codigo": code, "severidad": severity, "tipo": kind,
                       "mensaje": message, "ubicacion": (JUEZ_DIR / "datos_sgr.json").as_posix(),
                       "criterios": criteria, "origen": "juez_sgr.py"})

    if datos_missing:
        add("datos-sgr-ausente", "advertencia", "faltante",
            "No existe artefactos/juez/datos_sgr.json: los subcriterios de conteo valen 0.",
            [s["id"] for _, s in iter_subcriteria(rubric) if s["modo"] == "conteo"])
    else:
        for entry in resolved:
            if entry.get("incompleto"):
                add("dato-faltante", "advertencia", "faltante",
                    f"{entry['id']} queda en 0 por datos sin verificar: {entry['calculo']}", [entry["id"]])
    for sid in notes:
        add("puntaje-conteo-ignorado", "info", "forma",
            f"{sid} es de conteo: el script calcula su puntaje y descarta el que trae la ronda.", [sid])

    total = sum(subtotals.values())
    eligibility = rubric["elegibilidad"]
    reasons = []
    if total < eligibility["umbral_total"]:
        reasons.append(f"El total ({total}) es menor que el umbral de {eligibility['umbral_total']}.")
    names = {c["id"]: c["nombre"] for c in rubric["criterios"]}
    for minimum in eligibility.get("minimos") or []:
        got = subtotals.get(minimum["criterio"], 0)
        if got < minimum["minimo"]:
            reasons.append(f"El criterio {minimum['criterio']} ({names.get(minimum['criterio'], '')}) suma {got}; "
                           f"el mínimo es {minimum['minimo']}.")
    for alert in alerts:
        if alert.get("inhabilitante"):
            reasons.append(alert["mensaje"])

    result = {
        "schema": CONSOLIDATED_SCHEMA,
        "rubrica": rubric["id"],
        "convocatoria": rubric["convocatoria"],
        "ronda": data["ronda"],
        "fecha": data.get("fecha"),
        "fecha_calificacion": _today(),
        "criterios": resolved,
        "alertas": data.get("alertas") or [],
        "acciones": data.get("acciones") or [],
        "concepto": data.get("concepto"),
        "recomienda": data.get("recomienda"),
        "maximos": {c["id"]: c["max"] for c in rubric["criterios"]},
        "subtotales": subtotals,
        "total": total,
        "umbral_total": eligibility["umbral_total"],
        "minimos": eligibility.get("minimos") or [],
        "elegible": not reasons,
        "motivos_no_elegible": reasons,
        "incompleto": incomplete,
        "verificaciones": alerts,
        "errores_validacion": [],
    }
    result["historial"] = _history(previous, {"ronda": data["ronda"], "fecha": data.get("fecha"), "total": total,
                                              "elegible": result["elegible"]})
    return result


# --- Markdown form -----------------------------------------------------------------

def _cell(value) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def render_markdown(rubric: dict, result: dict) -> str:
    lines = [f"# Juez SGR: evaluación estimada, ronda {result.get('ronda')}", "",
             f"Rúbrica: {rubric['id']} ({rubric['convocatoria']}).", ""]
    if result.get("errores_validacion"):
        lines += ["**La ronda no pasó la validación.** Corrige estos puntos y vuelve a calificar:", ""]
        lines += [f"- {e}" for e in result["errores_validacion"]] + [""]
        return "\n".join(lines)
    verdict = "sí" if result["elegible"] else "no"
    lines += [f"**Total: {result['total']}/{rubric['total']}** (umbral {result['umbral_total']}). "
              f"Elegible: {verdict}." + (" Resultado incompleto: hay datos sin verificar." if result["incompleto"]
                                          else ""), ""]
    lines += [f"- {reason}" for reason in result["motivos_no_elegible"]]
    lines += ["", "| Criterio | Máx. | Puntaje |", "|---|---|---|"]
    entries = {e["id"]: e for e in result["criterios"]}
    for criterion in rubric["criterios"]:
        lines.append(f"| **{_cell(criterion['id'])}. {_cell(criterion['nombre'])}** | **{criterion['max']}** | "
                     f"**{result['subtotales'].get(criterion['id'], 0)}** |")
        for sub in criterion["subcriterios"]:
            if sub["id"] != criterion["id"]:
                lines.append(f"| {_cell(sub['id'])} {_cell(sub['nombre'])} | {sub['max']} | "
                             f"{entries[sub['id']]['puntaje']} |")
    lines += [f"| **Total** | **{rubric['total']}** | **{result['total']}** |", "", "## Justificaciones", ""]
    for entry in result["criterios"]:
        lines += [f"### {entry['id']} {entry['nombre']} ({entry['puntaje']}/{entry['max']})", ""]
        if entry.get("nivel_descriptor"):
            lines += [f"*{entry['nivel_descriptor']}*", ""]
        if entry.get("calculo"):
            lines += [f"Cálculo: {entry['calculo']}", ""]
        if entry.get("justificacion"):
            lines += [entry["justificacion"], ""]
        for item in entry.get("evidencia") or []:
            lines.append(f"- {item.get('ubicacion')}: «{item.get('cita')}»")
        target = entry.get("para_subir")
        if isinstance(target, dict):
            lines += ["", f"Para subir a {target.get('puntaje_objetivo')}: {target.get('que_falta')}"]
        lines.append("")
    lines += ["## Alertas", ""]
    all_alerts = list(result["alertas"]) + list(result["verificaciones"])
    if not all_alerts:
        lines.append("Sin alertas.")
    for alert in all_alerts:
        where = f" ({alert['ubicacion']})" if alert.get("ubicacion") else ""
        criteria = f" [{', '.join(alert.get('criterios') or [])}]" if alert.get("criterios") else ""
        origin = " (script)" if alert.get("origen") == "juez_sgr.py" else ""
        lines.append(f"- **{str(alert.get('severidad')).upper()}**{origin} {alert.get('mensaje')}{where}{criteria}")
    lines += ["", "## Acciones de mejora", "", "| Prioridad | Agente | Criterios | Instrucción |", "|---|---|---|---|"]
    for action in sorted(result["acciones"], key=lambda a: a.get("prioridad") or 9):
        lines.append(f"| {action.get('prioridad')} | {_cell(action.get('agente'))} | "
                     f"{_cell(', '.join(action.get('criterios') or []))} | {_cell(action.get('instruccion'))} |")
    lines += ["", "## Concepto final", "", str(result.get("concepto") or ""), "",
              f"Recomienda: {'Sí' if result.get('recomienda') else 'No'}", "", "## Historial", "",
              "| Ronda | Fecha | Total | Elegible |", "|---|---|---|---|"]
    for item in result["historial"]:
        lines.append(f"| {item.get('ronda')} | {_cell(item.get('fecha'))} | {item.get('total')} | "
                     f"{'sí' if item.get('elegible') else 'no'} |")
    return "\n".join(lines) + "\n"


# --- Commands ------------------------------------------------------------------------

def cmd_preparar(run: Path, flag: str | None, force: bool, as_json: bool) -> int:
    flujo = _load_check_run().detect_flujo(run)
    if flujo != "sgr" and not force:
        raise JuezError(f"La corrida es de flujo «{flujo}», no «sgr»: el juez SGR solo evalúa proyectos de "
                        "regalías. Usa --forzar para evaluarla de todos modos.")
    rubric, origin, raw = resolve_rubric(run, flag)
    target = run / JUEZ_DIR / "rubrica.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or target.read_bytes() != raw:
        target.write_bytes(raw)
    numbers = _round_numbers(run)
    next_round = (numbers[-1] + 1) if numbers else 1
    checks = build_verifications(run, rubric, next_round)
    _write_json(run / JUEZ_DIR / "verificaciones.json", checks)
    files = [(JUEZ_DIR / "datos_sgr.json").as_posix(), (JUEZ_DIR / f"evaluacion_ronda_{next_round}.json").as_posix()]
    if as_json:
        print(json.dumps({"rubrica": rubric["id"], "origen": origin, "flujo": flujo, "ronda_siguiente": next_round,
                          "archivos": files, "verificaciones": (JUEZ_DIR / "verificaciones.json").as_posix()},
                         ensure_ascii=False, indent=2))
        return 0
    cr = checks["check_run"]
    missing = sum(len(c["faltantes"]) for c in checks["cobertura"])
    print(f"Juez SGR: rúbrica {rubric['id']} ({origin}).")
    if flujo != "sgr":
        print(f"Aviso: la corrida es de flujo «{flujo}»; se evalúa por --forzar.")
    print(f"Verificaciones en {JUEZ_DIR.as_posix()}/verificaciones.json: check_run con {cr['errores']} errores y "
          f"{cr['avisos']} avisos; {missing} secciones de evidencia faltantes; "
          f"{len(checks['latex']['labels_duplicados'])} labels duplicados; "
          f"{len(checks['latex']['captions_vacios'])} captions vacíos.")
    print(f"Siguiente ronda: {next_round}. El juez debe escribir:")
    print(f"  - {files[0]} ({DATA_SCHEMA}; actualízalo si ya existe)")
    print(f"  - {files[1]} ({ROUND_SCHEMA})")
    print(f"Luego: python3 scripts/juez_sgr.py calificar {run}")
    return 0


def cmd_calificar(run: Path, as_json: bool) -> int:
    folder = run / JUEZ_DIR
    rubric = _read_json(folder / "rubrica.json")
    rubric_errors = validate_rubric(rubric)
    if rubric_errors:
        raise JuezError("La rúbrica de la corrida no es válida:\n  - " + "\n  - ".join(rubric_errors))
    numbers = _round_numbers(run)
    if not numbers:
        raise JuezError(f"No hay rondas en {JUEZ_DIR.as_posix()}/ (evaluacion_ronda_<N>.json). "
                        "Corre primero preparar y el agente juez-sgr.")
    number = numbers[-1]
    previous_path = folder / "evaluacion.json"
    try:
        previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.is_file() else None
    except (OSError, ValueError):
        previous = None
    errors: list[str] = []
    try:
        data = _read_json(folder / f"evaluacion_ronda_{number}.json")
    except JuezError as exc:
        data, errors = None, [str(exc)]
    if data is not None:
        errors = validate_round(data, rubric, number)
    datos = None
    datos_path = folder / "datos_sgr.json"
    if datos_path.is_file():
        try:
            datos = _read_json(datos_path)
            if not isinstance(datos, dict):
                errors.append("datos_sgr.json no es un objeto JSON.")
                datos = None
            elif "schema" in datos and datos["schema"] != DATA_SCHEMA:
                errors.append(f"datos_sgr.json: schema debe ser {DATA_SCHEMA}.")
        except JuezError as exc:
            errors.append(str(exc))

    if errors:
        result = {"schema": CONSOLIDATED_SCHEMA, "rubrica": rubric["id"], "convocatoria": rubric["convocatoria"],
                  "ronda": number, "fecha": (data or {}).get("fecha") if isinstance(data, dict) else None,
                  "fecha_calificacion": _today(), "criterios": [], "alertas": [], "acciones": [], "concepto": None,
                  "recomienda": None, "maximos": {c["id"]: c["max"] for c in rubric["criterios"]},
                  "subtotales": {}, "total": None, "umbral_total": rubric["elegibilidad"]["umbral_total"],
                  "minimos": rubric["elegibilidad"].get("minimos") or [], "elegible": None,
                  "motivos_no_elegible": [], "incompleto": True, "verificaciones": [],
                  "historial": (previous or {}).get("historial") or [], "errores_validacion": errors}
    else:
        result = consolidate(rubric, data, datos, previous)
    _write_json(previous_path, result)
    (folder / "evaluacion.md").write_text(render_markdown(rubric, result), encoding="utf-8")

    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        print(f"Juez SGR: la ronda {number} no es válida ({len(errors)} errores):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
    else:
        print(summary(result))
    return 1 if errors else 0


def _open_errors(result: dict) -> int:
    return sum(1 for a in list(result.get("alertas") or []) + list(result.get("verificaciones") or [])
               if isinstance(a, dict) and a.get("severidad") == "error")


def summary(result: dict) -> str:
    if result.get("errores_validacion"):
        return (f"Juez SGR ({result.get('rubrica')}), ronda {result.get('ronda')}: la ronda no pasó la validación "
                f"({len(result['errores_validacion'])} errores); corrígela y vuelve a calificar.")
    verdict = "elegible" if result.get("elegible") else "no elegible"
    text = (f"Juez SGR ({result.get('rubrica')}), ronda {result.get('ronda')}: {result.get('total')}/100, "
            f"{verdict} (umbral {result.get('umbral_total')}); {_open_errors(result)} alertas de error abiertas.")
    if result.get("motivos_no_elegible"):
        text += " Motivos: " + " ".join(result["motivos_no_elegible"])
    if result.get("incompleto"):
        text += " Resultado incompleto: hay datos sin verificar."
    return text


def cmd_estado(run: Path, as_json: bool) -> int:
    path = run / JUEZ_DIR / "evaluacion.json"
    result = None
    if path.is_file():
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            result = None
    if as_json:
        if result is None:
            print(json.dumps({"existe": False}, ensure_ascii=False))
        else:
            print(json.dumps({"existe": True, "rubrica": result.get("rubrica"), "ronda": result.get("ronda"),
                              "total": result.get("total"), "umbral_total": result.get("umbral_total"),
                              "elegible": result.get("elegible"), "incompleto": result.get("incompleto"),
                              "alertas_error": _open_errors(result),
                              "errores_validacion": len(result.get("errores_validacion") or [])},
                             ensure_ascii=False, indent=2))
        return 0
    if result is None:
        print(f"Juez SGR: aún no hay evaluación en {JUEZ_DIR.as_posix()}/evaluacion.json. "
              "Corre preparar, el agente juez-sgr y luego calificar.")
    else:
        print(summary(result))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("comando", choices=("preparar", "calificar", "estado"))
    parser.add_argument("run_root", help="carpeta de la corrida (proposals/<run-id>)")
    parser.add_argument("--rubrica", help="id de scripts/rubricas_sgr/ o ruta a un JSON de rúbrica (preparar)")
    parser.add_argument("--forzar", action="store_true", help="preparar aunque el flujo no sea sgr")
    parser.add_argument("--json", action="store_true", help="salida en JSON")
    args = parser.parse_args(argv)
    run = Path(args.run_root).resolve()
    try:
        if not run.is_dir():
            raise JuezError(f"No existe la corrida {run}.")
        if args.comando == "preparar":
            return cmd_preparar(run, args.rubrica, args.forzar, args.json)
        if args.comando == "calificar":
            return cmd_calificar(run, args.json)
        return cmd_estado(run, args.json)
    except JuezError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
