#!/usr/bin/env python3
"""Deterministic half of the stage judge (juez-avance): validate and record.

The juez-avance agent reads the proposal "up to this point" (stage `arbol`:
idea, inputs, TDR-adjusted guide and the two trees; stage `novedad`: that plus
the novelty and hypotheses artifact) and writes a draft with a score, a short
verdict, the idea summary, strengths, weaknesses and alerts. This script does
what must not depend on the model: it validates the draft strictly, numbers the
round, dates it, keeps the earlier rounds in `historial` and writes the record
atomically. The agent never writes the record by hand. Standard library only,
like the rest of Morfeo's scripts. Advisory: nothing here touches a gate.

Usage:
  python3 scripts/juez_avance.py validar   RUN_ROOT --etapa arbol|novedad [--borrador PATH] [--json]
  python3 scripts/juez_avance.py registrar RUN_ROOT --etapa arbol|novedad [--borrador PATH] [--json]

Files (under RUN_ROOT/artefactos/juez/):
  avance_<etapa>_borrador.json  draft written by the agent (default --borrador);
                                removed once it is recorded
  avance_<etapa>.json           record (morfeo.juez-avance/v1), written here

`validar` with --borrador checks a draft; without it, the recorded file.
`registrar` validates the draft and appends a new round; an invalid draft
writes nothing and stays for the agent to fix.

Exit codes: 0 done; 1 the draft or record is invalid; 2 missing input, an
unknown stage or an unreadable previous record (never overwritten).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SCHEMA = "morfeo.juez-avance/v1"
ETAPAS = ("arbol", "novedad")
NIVELES = ("alta", "media", "baja")
JUEZ_DIR = Path("artefactos") / "juez"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Field limits: (min chars, max chars) for text, (min, max) items for lists.
VEREDICTO = (3, 200)
RESUMEN = (20, 2000)
TEXTO = (5, 600)
EVIDENCIA = (2, 400)
ACCION = (5, 600)
DONDE = (2, 200)
FORTALEZAS = (1, 10)
DEBILIDADES = (1, 10)
ALERTAS = (0, 12)

CONTENT_KEYS = ("puntaje", "veredicto", "resumen_idea", "fortalezas", "debilidades", "alertas")
DRAFT_KEYS = ("schema", "etapa") + CONTENT_KEYS
ROUND_KEYS = ("ronda", "fecha") + CONTENT_KEYS
RECORD_KEYS = ("schema", "etapa", "ronda", "fecha") + CONTENT_KEYS + ("historial",)


class JuezAvanceError(Exception):
    """Missing or unusable input: the command stops with exit code 2."""


def record_file(run: Path, etapa: str) -> Path:
    return run / JUEZ_DIR / f"avance_{etapa}.json"


def draft_file(run: Path, etapa: str) -> Path:
    return run / JUEZ_DIR / f"avance_{etapa}_borrador.json"


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
        raise JuezAvanceError(f"No existe {label} ({path}).") from None
    except (OSError, ValueError) as exc:
        raise JuezAvanceError(f"{path.name} no es un JSON válido: {exc}") from None


# --- Validation ---------------------------------------------------------------

def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _text(errors: list[str], where: str, value, limits: tuple[int, int]) -> None:
    low, high = limits
    if not isinstance(value, str):
        errors.append(f"{where}: debe ser texto.")
        return
    size = len(value.strip())
    if size < low or size > high:
        errors.append(f"{where}: debe tener entre {low} y {high} caracteres (tiene {size}).")


def _items(errors: list[str], name: str, value, limits: tuple[int, int], fields: dict) -> None:
    low, high = limits
    if not isinstance(value, list):
        errors.append(f"{name}: debe ser una lista.")
        return
    if len(value) < low or len(value) > high:
        errors.append(f"{name}: debe tener entre {low} y {high} elementos (tiene {len(value)}).")
    for i, item in enumerate(value, 1):
        where = f"{name}[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: debe ser un objeto.")
            continue
        for key in item:
            if key not in fields:
                errors.append(f"{where}: campo desconocido «{key}» (se esperan {', '.join(fields)}).")
        for key, check in fields.items():
            if key not in item:
                errors.append(f"{where}.{key}: falta.")
            else:
                check(errors, f"{where}.{key}", item[key])


def _nivel(errors: list[str], where: str, value) -> None:
    if value not in NIVELES:
        errors.append(f"{where}: debe ser {', '.join(NIVELES)} (es {value!r}).")


FORTALEZA_FIELDS = {
    "texto": lambda e, w, v: _text(e, w, v, TEXTO),
    "evidencia": lambda e, w, v: _text(e, w, v, EVIDENCIA),
}
DEBILIDAD_FIELDS = {
    "texto": lambda e, w, v: _text(e, w, v, TEXTO),
    "evidencia": lambda e, w, v: _text(e, w, v, EVIDENCIA),
    "accion": lambda e, w, v: _text(e, w, v, ACCION),
}
ALERTA_FIELDS = {
    "nivel": _nivel,
    "texto": lambda e, w, v: _text(e, w, v, TEXTO),
    "donde": lambda e, w, v: _text(e, w, v, DONDE),
}


def _content(errors: list[str], data: dict, prefix: str = "") -> None:
    for key in CONTENT_KEYS:
        if key not in data:
            errors.append(f"{prefix}{key}: falta.")
    if "puntaje" in data:
        score = data["puntaje"]
        if not _is_int(score) or not 0 <= score <= 100:
            errors.append(f"{prefix}puntaje: debe ser un entero entre 0 y 100 (es {score!r}).")
    if "veredicto" in data:
        _text(errors, f"{prefix}veredicto", data["veredicto"], VEREDICTO)
    if "resumen_idea" in data:
        _text(errors, f"{prefix}resumen_idea", data["resumen_idea"], RESUMEN)
    if "fortalezas" in data:
        _items(errors, f"{prefix}fortalezas", data["fortalezas"], FORTALEZAS, FORTALEZA_FIELDS)
    if "debilidades" in data:
        _items(errors, f"{prefix}debilidades", data["debilidades"], DEBILIDADES, DEBILIDAD_FIELDS)
    if "alertas" in data:
        _items(errors, f"{prefix}alertas", data["alertas"], ALERTAS, ALERTA_FIELDS)


def validate_draft(data, etapa: str) -> list[str]:
    """Errors of an agent draft; an empty list means it can be recorded."""
    if not isinstance(data, dict):
        return ["El borrador debe ser un objeto JSON."]
    errors: list[str] = []
    for key in data:
        if key not in DRAFT_KEYS:
            errors.append(f"{key}: campo desconocido; el borrador lleva {', '.join(CONTENT_KEYS)} "
                          "(la ronda, la fecha y el historial los pone el script).")
    if "schema" in data and data["schema"] != SCHEMA:
        errors.append(f"schema: debe ser {SCHEMA} (es {data['schema']!r}).")
    if "etapa" in data and data["etapa"] != etapa:
        errors.append(f"etapa: el borrador dice {data['etapa']!r} y se registra la etapa {etapa!r}.")
    _content(errors, data)
    return errors


def _round(errors: list[str], data: dict, prefix: str, allowed: tuple[str, ...]) -> None:
    for key in data:
        if key not in allowed:
            errors.append(f"{prefix}{key}: campo desconocido.")
    ronda = data.get("ronda")
    if not _is_int(ronda) or ronda < 1:
        errors.append(f"{prefix}ronda: debe ser un entero mayor o igual a 1 (es {ronda!r}).")
    fecha = data.get("fecha")
    if not isinstance(fecha, str) or not DATE_RE.match(fecha):
        errors.append(f"{prefix}fecha: debe ser una fecha ISO AAAA-MM-DD (es {fecha!r}).")
    _content(errors, data, prefix)


def validate_record(data, etapa: str) -> list[str]:
    """Errors of a recorded file, its history included."""
    if not isinstance(data, dict):
        return ["El registro debe ser un objeto JSON."]
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema: debe ser {SCHEMA} (es {data.get('schema')!r}).")
    if data.get("etapa") != etapa:
        errors.append(f"etapa: debe ser {etapa!r} (es {data.get('etapa')!r}).")
    _round(errors, data, "", RECORD_KEYS)
    historial = data.get("historial")
    if not isinstance(historial, list):
        errors.append("historial: debe ser una lista.")
        return errors
    previous = 0
    for i, entry in enumerate(historial, 1):
        prefix = f"historial[{i}]."
        if not isinstance(entry, dict):
            errors.append(f"historial[{i}]: debe ser un objeto.")
            continue
        _round(errors, entry, prefix, ROUND_KEYS)
        ronda = entry.get("ronda")
        if _is_int(ronda):
            if ronda <= previous:
                errors.append(f"{prefix}ronda: las rondas del historial deben ir en orden creciente.")
            previous = ronda
    if _is_int(data.get("ronda")) and historial and previous >= data["ronda"]:
        errors.append("historial: tiene una ronda igual o posterior a la ronda vigente.")
    return errors


# --- Recording ----------------------------------------------------------------

def build_record(draft: dict, previous: dict | None, etapa: str, fecha: str) -> dict:
    """The new record: previous round moved into `historial`, round number + 1."""
    historial: list[dict] = []
    ronda = 1
    if previous:
        historial = list(previous.get("historial") or [])
        historial.append({key: previous[key] for key in ROUND_KEYS})
        ronda = previous["ronda"] + 1
    record = {"schema": SCHEMA, "etapa": etapa, "ronda": ronda, "fecha": fecha}
    record.update({key: draft[key] for key in CONTENT_KEYS})
    record["historial"] = historial
    return record


def _previous(run: Path, etapa: str) -> dict | None:
    path = record_file(run, etapa)
    if not path.exists():
        return None
    data = _read_json(path, f"el registro {path.name}")
    errors = validate_record(data, etapa)
    if errors:
        raise JuezAvanceError(f"{path.name} existe pero no es válido y no se sobrescribe: {errors[0]} "
                              "Corrígelo o muévelo antes de registrar una ronda nueva.")
    return data


def _report_errors(label: str, errors: list[str]) -> None:
    print(f"Juez de avance: {label} no es válido ({len(errors)} errores):", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)


def cmd_validar(run: Path, etapa: str, borrador: Path | None, as_json: bool) -> int:
    if borrador is not None:
        data = _read_json(borrador, "el borrador")
        errors = validate_draft(data, etapa)
        label = f"el borrador {borrador.name}"
    else:
        path = record_file(run, etapa)
        data = _read_json(path, f"el registro {path.name}")
        errors = validate_record(data, etapa)
        label = f"el registro {path.name}"
    if as_json:
        print(json.dumps({"ok": not errors, "errores": errors}, ensure_ascii=False, indent=2))
    elif errors:
        _report_errors(label, errors)
    else:
        print(f"Juez de avance: {label} es válido.")
    return 1 if errors else 0


def cmd_registrar(run: Path, etapa: str, borrador: Path | None, as_json: bool) -> int:
    source = borrador if borrador is not None else draft_file(run, etapa)
    draft = _read_json(source, f"el borrador {source.name}")
    errors = validate_draft(draft, etapa)
    if errors:
        if as_json:
            print(json.dumps({"ok": False, "errores": errors}, ensure_ascii=False, indent=2))
        _report_errors(f"el borrador {source.name}", errors)
        return 1
    previous = _previous(run, etapa)
    record = build_record(draft, previous, etapa, datetime.date.today().isoformat())
    target = record_file(run, etapa)
    write_atomic(target, record)
    try:
        source.unlink()
    except OSError:
        pass
    archivo = target.relative_to(run).as_posix()
    if as_json:
        print(json.dumps({"ok": True, "etapa": etapa, "ronda": record["ronda"], "puntaje": record["puntaje"],
                          "archivo": archivo}, ensure_ascii=False, indent=2))
    else:
        print(f"Juez de avance ({etapa}), ronda {record['ronda']}: {record['puntaje']}/100. "
              f"{record['veredicto']} Registro: {archivo}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("comando", choices=("validar", "registrar"))
    parser.add_argument("run_root", help="carpeta de la corrida (proposals/<run-id>)")
    parser.add_argument("--etapa", required=True, help="arbol o novedad")
    parser.add_argument("--borrador", help="ruta del borrador (por defecto artefactos/juez/avance_<etapa>_borrador.json)")
    parser.add_argument("--json", action="store_true", help="salida en JSON")
    args = parser.parse_args(argv)
    run = Path(args.run_root).resolve()
    try:
        if args.etapa not in ETAPAS:
            raise JuezAvanceError(f"Etapa desconocida {args.etapa!r}: usa {' o '.join(ETAPAS)}.")
        if not run.is_dir():
            raise JuezAvanceError(f"No existe la corrida {run}.")
        borrador = Path(args.borrador).resolve() if args.borrador else None
        if args.comando == "validar":
            return cmd_validar(run, args.etapa, borrador, args.json)
        return cmd_registrar(run, args.etapa, borrador, args.json)
    except JuezAvanceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
