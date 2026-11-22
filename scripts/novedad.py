#!/usr/bin/env python3
"""Deterministic half of the novelty panel: validate, record and derive the matrix.

The investigador (MODE=novedad, dispatched by /propuesta-novedad) proposes the
novelty pillars and the hypotheses of the proposal, each hypothesis with the
experiments, actions, implementations, interventions or transfers that would
produce its evidence, linked to the direct causes of the problem tree and the
specific objectives of the objective tree. It writes a draft; this script does
what must not depend on the model: it validates the draft strictly, dates it
and writes the record atomically. The agent never writes the record by hand.
`matriz` derives the project matrix, one row per specific objective following
the value chain: direct cause, specific objective, pillars, hypotheses,
experiments or actions (with their type), products, expected result and
indicator, and the effects of the problem tree. The dashboard imports this
module for GET /api/novedad. Standard library only; text helpers come from
check_run.py (same folder). Advisory: nothing here touches a gate or a section.

Usage:
  python3 scripts/novedad.py validar   RUN_ROOT [--borrador PATH] [--json]
  python3 scripts/novedad.py registrar RUN_ROOT [--borrador PATH] [--json]
  python3 scripts/novedad.py matriz    RUN_ROOT

Files (under RUN_ROOT):
  artefactos/novedad/novedad_borrador.json  draft written by the agent (default
                                            --borrador); removed once recorded
  artefactos/novedad/novedad.json           record (morfeo.novedad/v1)
  redaccion/specs/arbol_problemas.spec.json and
  artefactos/arboles/arbol_objetivos.json   the trees; when present, the
                                            problem, causes and objectives
                                            must match them verbatim

`validar` with --borrador checks a draft; without it, the recorded file.
`registrar` validates the draft and writes the record; an invalid draft writes
nothing and stays for the agent to fix. `matriz` prints the matrix as JSON.

Exit codes: 0 done; 1 the draft or record is invalid; 2 missing input.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SCHEMA = "morfeo.novedad/v1"
NOVEDAD_DIR = Path("artefactos") / "novedad"
PROBLEM_SPEC = Path("redaccion") / "specs" / "arbol_problemas.spec.json"
OBJECTIVES_FILE = Path("artefactos") / "arboles" / "arbol_objetivos.json"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIPOS = ("experimento", "intervencion", "transferencia", "implementacion", "accion")
TIPO_LABELS = {
    "experimento": "Experimento",
    "intervencion": "Intervención",
    "transferencia": "Transferencia",
    "implementacion": "Implementación",
    "accion": "Acción",
}
TRL_RE = re.compile(r"\bTRL\b")

ID_RES = {
    "causas": re.compile(r"^CD\d{1,2}$"),
    "objetivos": re.compile(r"^OE\d{1,2}$"),
    "pilares": re.compile(r"^P\d{1,2}$"),
    "hipotesis": re.compile(r"^H\d{1,2}$"),
    "experimentos": re.compile(r"^E\d{1,3}$"),
    "efectos": re.compile(r"^EF\d{1,2}$"),
}
ID_EXAMPLES = {"causas": "CD1", "objetivos": "OE1", "pilares": "P1", "hipotesis": "H1",
               "experimentos": "E1", "efectos": "EF1"}

# Field limits: (min, max) chars for text, (min, max) items for lists. The
# guide fixes three subproblems mapped 1:1 to three specific objectives.
PROBLEMA = (10, 600)
GENERAL = (10, 700)
TEXTO = (5, 600)
NOMBRE = (3, 120)
RESUMEN = (10, 400)
DETALLE = (10, 1200)
TITULO = (5, 160)
ENUNCIADO = (20, 700)
DESCRIPCION = (10, 600)
CORTO = (3, 300)
RESULTADO = (5, 400)
N_CAUSAS = (3, 3)
N_PILARES = (1, 6)
N_HIPOTESIS = (1, 8)
N_EXPERIMENTOS = (1, 5)
N_EFECTOS = (0, 8)

CONTENT_KEYS = ("problema_central", "objetivo_general", "causas", "objetivos", "pilares", "hipotesis")
OPTIONAL_KEYS = ("efectos",)
DRAFT_KEYS = ("schema",) + CONTENT_KEYS + OPTIONAL_KEYS
RECORD_KEYS = ("schema", "fecha") + CONTENT_KEYS + OPTIONAL_KEYS

_CHECK_RUN_PATH = Path(__file__).resolve().parent / "check_run.py"
_CHECK_RUN = None


class NovedadError(Exception):
    """Missing or unusable input: the command stops with exit code 2."""


def _check_run():
    """check_run.py of this folder, for the tree text helpers and the target regex."""
    global _CHECK_RUN
    if _CHECK_RUN is not None:
        return _CHECK_RUN
    for name in ("check_run", "__main__"):
        module = sys.modules.get(name)
        file = getattr(module, "__file__", None)
        if file and Path(file).resolve() == _CHECK_RUN_PATH and hasattr(module, "normalize_tree_text"):
            _CHECK_RUN = module
            return module
    spec = importlib.util.spec_from_file_location("_novedad_check_run", _CHECK_RUN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CHECK_RUN = module
    return module


def _plain(text) -> str:
    """Tree text without LaTeX, line breaks or a leading node id («SP1 · »)."""
    rules = _check_run()
    return rules.NODE_PREFIX_RE.sub("", rules.normalize_tree_text(text))


def record_file(run: Path) -> Path:
    return run / NOVEDAD_DIR / "novedad.json"


def draft_file(run: Path) -> Path:
    return run / NOVEDAD_DIR / "novedad_borrador.json"


def write_atomic(path: Path, data) -> None:
    """Write JSON through a temporary file in the same folder and os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_json(path: Path, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise NovedadError(f"No existe {label} ({path}).") from None
    except (OSError, ValueError) as exc:
        raise NovedadError(f"{path.name} no es un JSON válido: {exc}") from None


def _read_optional(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load_trees(run: Path) -> dict:
    """The two trees of the run, None where a file is absent or unreadable."""
    return {"problemas": _read_optional(Path(run) / PROBLEM_SPEC),
            "objetivos": _read_optional(Path(run) / OBJECTIVES_FILE)}


# --- Validation ---------------------------------------------------------------

def _text(errors: list[str], where: str, value, limits: tuple[int, int]) -> None:
    low, high = limits
    if not isinstance(value, str):
        errors.append(f"{where}: debe ser texto.")
        return
    size = len(value.strip())
    if size < low or size > high:
        errors.append(f"{where}: debe tener entre {low} y {high} caracteres (tiene {size}).")


def _qualitative(errors: list[str], where: str, value, *, trl: bool) -> None:
    """Objectives and hypotheses stay qualitative: no fixed percent targets, no TRL."""
    if not isinstance(value, str):
        return
    if _check_run().TARGET_RE.search(value):
        errors.append(f"{where}: lleva una meta porcentual fija (%); los objetivos y las hipótesis son cualitativos, "
                      "la meta numérica va en el indicador del experimento.")
    if trl and TRL_RE.search(value):
        errors.append(f"{where}: nombra el TRL; el objetivo describe la función, el nivel TRL va en §2, §10 y §11.")


def _fields(errors: list[str], where: str, item, fields: dict) -> bool:
    if not isinstance(item, dict):
        errors.append(f"{where}: debe ser un objeto.")
        return False
    for key in item:
        if key not in fields:
            errors.append(f"{where}: campo desconocido «{key}» (se esperan {', '.join(fields)}).")
    for key, check in fields.items():
        if key not in item:
            errors.append(f"{where}.{key}: falta.")
        else:
            check(errors, f"{where}.{key}", item[key])
    return True


def _collection(errors: list[str], data: dict, name: str, limits: tuple[int, int], fields: dict,
                label: str | None = None) -> list[dict]:
    """Valid objects of a list, with format and uniqueness of their ids."""
    value = data.get(name)
    label = label or name
    if not isinstance(value, list):
        errors.append(f"{label}: debe ser una lista.")
        return []
    low, high = limits
    if len(value) < low or len(value) > high:
        errors.append(f"{label}: debe tener entre {low} y {high} elementos (tiene {len(value)}).")
    items, seen = [], set()
    for i, item in enumerate(value, 1):
        if not _fields(errors, f"{label}[{i}]", item, fields):
            continue
        ident = item.get("id")
        if not isinstance(ident, str) or not ID_RES[name].match(ident):
            errors.append(f"{label}[{i}].id: «{ident}» no tiene el formato {ID_EXAMPLES[name]}.")
        elif ident in seen:
            errors.append(f"{label}[{i}].id: «{ident}» está repetido.")
        else:
            seen.add(ident)
        items.append(item)
    return items


def _id_list(name: str, minimum: int):
    def check(errors: list[str], where: str, value) -> None:
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            errors.append(f"{where}: debe ser una lista de identificadores {ID_EXAMPLES[name]}.")
            return
        if len(value) < minimum:
            errors.append(f"{where}: debe tener al menos {minimum} elemento.")
        if len(set(value)) != len(value):
            errors.append(f"{where}: tiene identificadores repetidos.")
    return check


def _tipo(errors: list[str], where: str, value) -> None:
    if value not in TIPOS:
        errors.append(f"{where}: «{value}» no es un tipo válido (usa {', '.join(TIPOS)}).")


def _id_text(errors: list[str], where: str, value) -> None:
    if not isinstance(value, str):
        errors.append(f"{where}: debe ser texto.")


CAUSA_FIELDS = {"id": _id_text, "texto": lambda e, w, v: _text(e, w, v, TEXTO)}
OBJETIVO_FIELDS = {"id": _id_text, "texto": lambda e, w, v: _text(e, w, v, TEXTO), "causa": _id_text}
PILAR_FIELDS = {
    "id": _id_text,
    "nombre": lambda e, w, v: _text(e, w, v, NOMBRE),
    "resumen": lambda e, w, v: _text(e, w, v, RESUMEN),
    "detalle": lambda e, w, v: _text(e, w, v, DETALLE),
    "objetivos": _id_list("objetivos", 1),
    "causas": _id_list("causas", 0),
}
EXPERIMENTO_FIELDS = {
    "id": _id_text,
    "tipo": _tipo,
    "titulo": lambda e, w, v: _text(e, w, v, TITULO),
    "descripcion": lambda e, w, v: _text(e, w, v, DESCRIPCION),
    "metrica": lambda e, w, v: _text(e, w, v, CORTO),
    "producto": lambda e, w, v: _text(e, w, v, CORTO),
    "resultado_esperado": lambda e, w, v: _text(e, w, v, RESULTADO),
}
HIPOTESIS_FIELDS = {
    "id": _id_text,
    "titulo": lambda e, w, v: _text(e, w, v, TITULO),
    "enunciado": lambda e, w, v: _text(e, w, v, ENUNCIADO),
    "pilares": _id_list("pilares", 1),
    "objetivos": _id_list("objetivos", 1),
    "experimentos": lambda e, w, v: None,  # validated as its own collection below
}
EFECTO_FIELDS = {"id": _id_text, "texto": lambda e, w, v: _text(e, w, v, TEXTO)}


def _refs(errors: list[str], where: str, values, known: set[str], what: str) -> None:
    for ident in values if isinstance(values, list) else []:
        if isinstance(ident, str) and ident not in known:
            errors.append(f"{where}: «{ident}» no es {what} del artefacto.")


def _ids(items: list[dict]) -> list[str]:
    return [i["id"] for i in items if isinstance(i.get("id"), str)]


def _tree_consistency(errors: list[str], data: dict, causas: list[dict], objetivos: list[dict], trees: dict) -> None:
    """The problem, causes and objectives copy the trees verbatim when they exist."""
    spec = trees.get("problemas")
    otree = trees.get("objetivos")
    if isinstance(spec, dict):
        trunk = _plain((spec.get("trunk") or {}).get("text"))
        if trunk and _plain(data.get("problema_central")) != trunk:
            errors.append(f"problema_central: debe copiar el tronco del árbol de problemas: «{trunk}».")
        groups = [g for g in spec.get("groups") or [] if isinstance(g, dict)]
        if groups and len(groups) != len(causas):
            errors.append(f"causas: el árbol de problemas tiene {len(groups)} causas directas y el artefacto {len(causas)}.")
        for causa, group in zip(causas, groups):
            expected = _plain(group.get("title") or group.get("id"))
            if expected and _plain(causa.get("texto")) != expected:
                errors.append(f"causas[{causa.get('id')}].texto: debe copiar la causa directa {group.get('id')} "
                              f"del árbol de problemas: «{expected}».")
    if isinstance(otree, dict):
        general = _plain((otree.get("trunk") or {}).get("text"))
        if general and _plain(data.get("objetivo_general")) != general:
            errors.append(f"objetivo_general: debe copiar el tronco del árbol de objetivos: «{general}».")
        groups = [g for g in otree.get("groups") or [] if isinstance(g, dict)]
        if groups and len(groups) != len(objetivos):
            errors.append(f"objetivos: el árbol de objetivos tiene {len(groups)} objetivos específicos "
                          f"y el artefacto {len(objetivos)}.")
        for objetivo, group in zip(objetivos, groups):
            expected = _plain(group.get("objective"))
            if expected and _plain(objetivo.get("texto")) != expected:
                errors.append(f"objetivos[{objetivo.get('id')}].texto: debe copiar el objetivo {group.get('id')} "
                              f"del árbol de objetivos: «{expected}».")


def _content(errors: list[str], data: dict, trees: dict | None) -> None:
    for key in CONTENT_KEYS:
        if key not in data:
            errors.append(f"{key}: falta.")
    if "problema_central" in data:
        _text(errors, "problema_central", data["problema_central"], PROBLEMA)
    if "objetivo_general" in data:
        _text(errors, "objetivo_general", data["objetivo_general"], GENERAL)
        _qualitative(errors, "objetivo_general", data["objetivo_general"], trl=True)

    causas = _collection(errors, data, "causas", N_CAUSAS, CAUSA_FIELDS) if "causas" in data else []
    objetivos = _collection(errors, data, "objetivos", N_CAUSAS, OBJETIVO_FIELDS) if "objetivos" in data else []
    pilares = _collection(errors, data, "pilares", N_PILARES, PILAR_FIELDS) if "pilares" in data else []
    hipotesis = _collection(errors, data, "hipotesis", N_HIPOTESIS, HIPOTESIS_FIELDS) if "hipotesis" in data else []
    if "efectos" in data:
        _collection(errors, data, "efectos", N_EFECTOS, EFECTO_FIELDS)

    causa_ids, oe_ids, pilar_ids = set(_ids(causas)), set(_ids(objetivos)), set(_ids(pilares))

    # Causes and specific objectives map 1:1.
    if causas and objetivos and len(causas) != len(objetivos):
        errors.append(f"objetivos: debe haber un objetivo específico por causa directa ({len(causas)} causas, "
                      f"{len(objetivos)} objetivos).")
    used: dict[str, str] = {}
    for objetivo in objetivos:
        where = f"objetivos[{objetivo.get('id')}]"
        _qualitative(errors, f"{where}.texto", objetivo.get("texto"), trl=True)
        causa = objetivo.get("causa")
        if isinstance(causa, str) and causa not in causa_ids:
            errors.append(f"{where}.causa: «{causa}» no es una causa directa del artefacto.")
        elif isinstance(causa, str) and causa in used:
            errors.append(f"{where}.causa: «{causa}» ya es la causa de {used[causa]}; el mapeo causa y objetivo es 1:1.")
        elif isinstance(causa, str):
            used[causa] = objetivo.get("id")
    for causa in sorted(causa_ids - set(used)):
        if objetivos:
            errors.append(f"causas[{causa}]: ningún objetivo específico la atiende.")

    for pilar in pilares:
        where = f"pilares[{pilar.get('id')}]"
        _refs(errors, f"{where}.objetivos", pilar.get("objetivos"), oe_ids, "un objetivo específico")
        _refs(errors, f"{where}.causas", pilar.get("causas"), causa_ids, "una causa directa")

    experiment_ids: set[str] = set()
    for hip in hipotesis:
        where = f"hipotesis[{hip.get('id')}]"
        _qualitative(errors, f"{where}.titulo", hip.get("titulo"), trl=False)
        _qualitative(errors, f"{where}.enunciado", hip.get("enunciado"), trl=False)
        _refs(errors, f"{where}.pilares", hip.get("pilares"), pilar_ids, "un pilar")
        _refs(errors, f"{where}.objetivos", hip.get("objetivos"), oe_ids, "un objetivo específico")
        if "experimentos" not in hip:
            continue
        for exp in _collection(errors, hip, "experimentos", N_EXPERIMENTOS, EXPERIMENTO_FIELDS,
                               label=f"{where}.experimentos"):
            ident = exp.get("id")
            if isinstance(ident, str) and ID_RES["experimentos"].match(ident):
                if ident in experiment_ids:
                    errors.append(f"{where}.experimentos: «{ident}» ya existe en otra hipótesis; los ids de "
                                  "experimentos y acciones son únicos en todo el artefacto.")
                experiment_ids.add(ident)

    def linked(items: list[dict], oe: str) -> bool:
        return any(isinstance(i.get("objetivos"), list) and oe in i["objetivos"] for i in items)

    for oe in _ids(objetivos):
        if pilares and not linked(pilares, oe):
            errors.append(f"objetivos[{oe}]: ningún pilar de novedad lo atiende.")
        if hipotesis and not linked(hipotesis, oe):
            errors.append(f"objetivos[{oe}]: ninguna hipótesis lo atiende.")
    for pid in _ids(pilares):
        if hipotesis and not any(isinstance(h.get("pilares"), list) and pid in h["pilares"] for h in hipotesis):
            errors.append(f"pilares[{pid}]: no sostiene ninguna hipótesis.")

    if trees:
        _tree_consistency(errors, data, causas, objetivos, trees)


def validate_draft(data, trees: dict | None = None) -> list[str]:
    """Errors of an agent draft; an empty list means it can be recorded."""
    if not isinstance(data, dict):
        return ["El borrador debe ser un objeto JSON."]
    errors: list[str] = []
    for key in data:
        if key not in DRAFT_KEYS:
            errors.append(f"{key}: campo desconocido; el borrador lleva {', '.join(CONTENT_KEYS + OPTIONAL_KEYS)} "
                          "(la fecha la pone el script).")
    if "schema" in data and data["schema"] != SCHEMA:
        errors.append(f"schema: debe ser {SCHEMA} (es {data['schema']!r}).")
    _content(errors, data, trees)
    return errors


def validate_record(data, trees: dict | None = None) -> list[str]:
    """Errors of a recorded file."""
    if not isinstance(data, dict):
        return ["El registro debe ser un objeto JSON."]
    errors: list[str] = []
    for key in data:
        if key not in RECORD_KEYS:
            errors.append(f"{key}: campo desconocido.")
    if data.get("schema") != SCHEMA:
        errors.append(f"schema: debe ser {SCHEMA} (es {data.get('schema')!r}).")
    fecha = data.get("fecha")
    if not isinstance(fecha, str) or not DATE_RE.match(fecha):
        errors.append(f"fecha: debe ser una fecha ISO AAAA-MM-DD (es {fecha!r}).")
    _content(errors, data, trees)
    return errors


def build_record(draft: dict, fecha: str) -> dict:
    record = {"schema": SCHEMA, "fecha": fecha}
    record.update({key: draft[key] for key in CONTENT_KEYS})
    if "efectos" in draft:
        record["efectos"] = draft["efectos"]
    return record


# --- Matrix -------------------------------------------------------------------

def _list(value) -> list:
    return value if isinstance(value, list) else []


def _dicts(value) -> list[dict]:
    return [v for v in _list(value) if isinstance(v, dict)]


def _unique(values) -> list[str]:
    out: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip() and value not in out:
            out.append(value)
    return out


def derive_matrix(data: dict, trees: dict | None = None) -> dict:
    """The project matrix, one row per specific objective, following the value chain.

    Tolerant of an incomplete record (the dashboard shows it next to its
    validation errors): missing pieces stay empty instead of raising.
    """
    data = data if isinstance(data, dict) else {}
    trees = trees or {}
    causas = {c.get("id"): c for c in _dicts(data.get("causas"))}
    pilares = _dicts(data.get("pilares"))
    hipotesis = _dicts(data.get("hipotesis"))

    spec = trees.get("problemas") if isinstance(trees.get("problemas"), dict) else None
    branches = [b for b in _dicts(spec.get("branches")) if b.get("text")] if spec else []
    if branches:
        efectos = [{"id": b.get("id"), "texto": _check_run().normalize_tree_text(b.get("text"))} for b in branches]
        fuente = "arbol"
    else:
        efectos = [{"id": e.get("id"), "texto": e.get("texto")} for e in _dicts(data.get("efectos")) if e.get("texto")]
        fuente = "novedad" if efectos else None
    crown = _check_run().normalize_tree_text((spec.get("crown") or {}).get("text")) if spec else ""
    effect_ids = [e["id"] for e in efectos]

    filas = []
    for objetivo in _dicts(data.get("objetivos")):
        oe = objetivo.get("id")
        causa = causas.get(objetivo.get("causa")) or {}
        row_pilares = [p for p in pilares if oe in _list(p.get("objetivos"))]
        row_hipotesis = [h for h in hipotesis if oe in _list(h.get("objetivos"))]
        experimentos = [
            {"id": e.get("id"), "hipotesis": h.get("id"), "tipo": e.get("tipo"), "titulo": e.get("titulo"),
             "descripcion": e.get("descripcion"), "metrica": e.get("metrica"), "producto": e.get("producto"),
             "resultado_esperado": e.get("resultado_esperado")}
            for h in row_hipotesis for e in _dicts(h.get("experimentos"))
        ]
        filas.append({
            "objetivo": {"id": oe, "texto": objetivo.get("texto")},
            "causa": {"id": objetivo.get("causa"), "texto": causa.get("texto")},
            "pilares": [{"id": p.get("id"), "nombre": p.get("nombre"), "resumen": p.get("resumen")} for p in row_pilares],
            "hipotesis": [{"id": h.get("id"), "titulo": h.get("titulo"), "enunciado": h.get("enunciado"),
                           "pilares": _list(h.get("pilares"))} for h in row_hipotesis],
            "experimentos": experimentos,
            "productos": _unique(e["producto"] for e in experimentos),
            "indicadores": _unique(e["metrica"] for e in experimentos),
            "resultados": _unique(e["resultado_esperado"] for e in experimentos),
            "efectos": list(effect_ids),
        })

    all_experiments = [e for h in hipotesis for e in _dicts(h.get("experimentos"))]
    por_tipo = {tipo: sum(1 for e in all_experiments if e.get("tipo") == tipo) for tipo in TIPOS}
    return {
        "problema_central": data.get("problema_central"),
        "objetivo_general": data.get("objetivo_general"),
        "efecto_final": crown or None,
        "efectos": efectos,
        "fuente_efectos": fuente,
        "tipos": [{"id": tipo, "etiqueta": TIPO_LABELS[tipo]} for tipo in TIPOS],
        "filas": filas,
        "totales": {"objetivos": len(filas), "pilares": len(pilares), "hipotesis": len(hipotesis),
                    "experimentos": len(all_experiments), "por_tipo": por_tipo},
    }


# --- Commands -----------------------------------------------------------------

def _report_errors(label: str, errors: list[str]) -> None:
    print(f"Novedad: {label} no es válido ({len(errors)} errores):", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)


def cmd_validar(run: Path, borrador: Path | None, as_json: bool) -> int:
    trees = load_trees(run)
    if borrador is not None:
        data = _read_json(borrador, "el borrador")
        errors = validate_draft(data, trees)
        label = f"el borrador {borrador.name}"
    else:
        path = record_file(run)
        data = _read_json(path, f"el registro {path.name}")
        errors = validate_record(data, trees)
        label = f"el registro {path.name}"
    if as_json:
        print(json.dumps({"ok": not errors, "errores": errors}, ensure_ascii=False, indent=2))
    elif errors:
        _report_errors(label, errors)
    else:
        print(f"Novedad: {label} es válido.")
    return 1 if errors else 0


def cmd_registrar(run: Path, borrador: Path | None, as_json: bool) -> int:
    source = borrador if borrador is not None else draft_file(run)
    draft = _read_json(source, f"el borrador {source.name}")
    errors = validate_draft(draft, load_trees(run))
    if errors:
        if as_json:
            print(json.dumps({"ok": False, "errores": errors}, ensure_ascii=False, indent=2))
        _report_errors(f"el borrador {source.name}", errors)
        return 1
    record = build_record(draft, datetime.date.today().isoformat())
    target = record_file(run)
    write_atomic(target, record)
    try:
        source.unlink()
    except OSError:
        pass
    archivo = target.relative_to(run).as_posix()
    totals = derive_matrix(record, load_trees(run))["totales"]
    if as_json:
        print(json.dumps({"ok": True, "archivo": archivo, "totales": totals}, ensure_ascii=False, indent=2))
    else:
        print(f"Novedad registrada: {totals['pilares']} pilares, {totals['hipotesis']} hipótesis y "
              f"{totals['experimentos']} experimentos o acciones. Registro: {archivo}")
    return 0


def cmd_matriz(run: Path) -> int:
    path = record_file(run)
    data = _read_json(path, f"el registro {path.name}")
    print(json.dumps(derive_matrix(data, load_trees(run)), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("comando", choices=("validar", "registrar", "matriz"))
    parser.add_argument("run_root", help="carpeta de la corrida (proposals/<run-id>)")
    parser.add_argument("--borrador", help="ruta del borrador (por defecto artefactos/novedad/novedad_borrador.json)")
    parser.add_argument("--json", action="store_true", help="salida en JSON")
    args = parser.parse_args(argv)
    run = Path(args.run_root).resolve()
    try:
        if not run.is_dir():
            raise NovedadError(f"No existe la corrida {run}.")
        borrador = Path(args.borrador).resolve() if args.borrador else None
        if args.comando == "validar":
            return cmd_validar(run, borrador, args.json)
        if args.comando == "registrar":
            return cmd_registrar(run, borrador, args.json)
        return cmd_matriz(run)
    except NovedadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
