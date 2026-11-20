#!/usr/bin/env python3
"""SGR enabling requirements, institutional endorsement, figures, licences and annexes as data (flujo SGR only).

`artefactos/sgr/requisitos.json` (schema `morfeo.requisitos-sgr/v1`) tracks
the enabling requirements of the call (copied verbatim from the TdR into the
rubric, key `requisitos`: Conv 54 numeral 11, Conv 56 numeral 10), the
figures declared in the other documents of the proposal, the licences and
permits of Anexo 2 chapter 28 and the institutional endorsement documents:

    {schema, convocatoria:"conv54"|"conv56"|null,
     items:[{id:"11.4", estado:"pendiente"|"en_tramite"|"listo"|"no_aplica", responsable:"E1"|null,
             archivo:str|null, fecha:"YYYY-MM-DD"|null, nota:str|null, justificacion:str|null}],
     cifras:{sigp:{total_sgr, total_contrapartida, total}|null,
             anexo1:{por_entidad:{"E1":{especie, efectivo}}}|null,
             anexo3:{total_sgr, total_contrapartida, total}|null,
             mga:{total_sgr, total}|null},
     licencias:{introduccion, items:[{licencia, norma, aplica:bool, justificacion, responsable:"E1"|null,
                momento:"previo"|"ejecucion"}]}|null,
     aval_institucional:{institucion:"unal"|null, documentos:[{indice, estado, archivo|null}]}|null}

`archivo` is a path relative to the run root (normally under
insumos/requisitos/). The rubric requirement is
{id, nombre, texto, condicion, documento, numeral_fuente}; `condicion` is set
only when the TdR marks the requirement as conditional («cuando aplique»,
«Si Aplica»), and only those requirements may be `no_aplica`. Four conditions
are derived from the data: `internacional` (an alliance entity of type
«internacional»), `sector_productivo` (an entity of type «sector_productivo»),
`infraestructura` (SGR money in the budget rubro `infraestructura`) and
`cofinanciacion` (an entity other than the proponent declares
`aporte_efectivo` > 0). A requirement applies unless it is `no_aplica` or its
derived condition is false. The endorsement procedure of each institution
lives in scripts/rubricas_sgr/_aval_institucional.json
(`morfeo.aval-institucional/v1`); it applies when the proponent's name
matches `patron_nombre` and the call is in `convocatorias`.

Commands:
  init RUN_ROOT
      Create requisitos.json from the rubric (every requirement `pendiente`,
      the endorsement documents of the proponent's institution), or add the
      requirements and endorsement documents it lacks; never overwrites.
  check RUN_ROOT [--final] [--json]
      Findings with check_run's shape {severity, code, message, node}, codes
      prefixed `requisitos-`; a missing file is exit 2. --final turns every
      applicable requirement that is not `listo` into an error.
  render RUN_ROOT
      Write redaccion/sections/38_licencias_permisos.tex (Anexo 2 cap. 28:
      introduction and licences table) and 39_anexos.tex (cap. 31: the list
      of the applicable requirement documents, without prose)
      deterministically. SGR runs only; refuses while there are error findings.
  datos RUN_ROOT [--json]
      {requisitos:{aplicables, listos, pendientes:[ids], no_aplica:[ids]}|null,
       cifras_coherentes:bool|null, cifras_diferencias:[{documento, campo, declarado, esperado}], fuente}:
      the facts the judge copies into datos_sgr.json.

Library (the dashboard): vista(run_root), actualizar_item(run_root, id, cambios), findings(run_root).

Rules (codes): requisitos-esquema, requisitos-json-invalido, requisitos-id-desconocido,
requisitos-id-repetido, requisitos-valor-invalido, requisitos-justificacion-faltante,
requisitos-no-aplica-invalido, requisitos-condicion-aplica, requisitos-archivo-inexistente,
requisitos-entidad-desconocida, requisitos-cifras-distintas (beyond 1 peso),
requisitos-licencia-incompleta, requisitos-licencia-sin-justificacion, requisitos-pendiente-final
(--final) (errors); requisitos-item-faltante, requisitos-sin-archivo, requisitos-licencias-faltantes,
requisitos-aval-documento-faltante, requisitos-rubrica-faltante, requisitos-alianza-faltante,
requisitos-presupuesto-faltante (warnings); requisitos-cifras-sin-declarar (info).
The declared figures are compared with presupuesto_sgr.resumen (total_sgr,
especie + efectivo as contrapartida, total) and, for the Anexo 1, with the
`aporte_especie` / `aporte_efectivo` of each entity of alianza.json.

Exit codes: 0 ok, 1 error findings (check, render), 2 bad input.
Standard library only. The budget summary comes from presupuesto_sgr.py, the
LaTeX escaping from cadena_valor_sgr.py, the flow from check_run.py, the TdR
chapters from ensamblar_main.py and the call's rubric from juez_sgr.py (all
in this folder, imported defensively).
"""

from __future__ import annotations

import argparse
import datetime
import functools
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SCHEMA = "morfeo.requisitos-sgr/v1"
REQUIREMENTS_FILE = Path("artefactos") / "sgr" / "requisitos.json"
ALLIANCE_FILE = Path("artefactos") / "sgr" / "alianza.json"
BUDGET_FILE = Path("artefactos") / "sgr" / "presupuesto.json"
STRUCTURE_FILE = Path("artefactos") / "estructura_tdr.json"
SECTIONS_DIR = Path("redaccion") / "sections"
GENERATED_HEADER = "% GENERADO por scripts/requisitos_sgr.py"
HERE = Path(__file__).resolve().parent
AVAL_FILE = HERE / "rubricas_sgr" / "_aval_institucional.json"

LICENSES_STEM = "38_licencias_permisos"
ANNEXES_STEM = "39_anexos"
LICENSES_TITLE = "Análisis de licencias y permisos"
ANNEXES_TITLE = "ANEXOS REQUISITOS SECTORIALES QUE LE SEAN APLICABLES."

STATES = ("pendiente", "en_tramite", "listo", "no_aplica")
CONDITIONS = ("etica", "internacional", "sector_productivo", "sociedad_civil", "infraestructura", "inmuebles",
              "cofinanciacion", "desastre", "otro")
DERIVED = ("internacional", "sector_productivo", "infraestructura", "cofinanciacion")
MOMENTS = {"previo": "Previo a la ejecución", "ejecucion": "Durante la ejecución"}
ITEM_FIELDS = ("estado", "responsable", "archivo", "fecha", "nota", "justificacion")
FIGURE_FIELDS = {"sigp": ("total_sgr", "total_contrapartida", "total"),
                 "anexo1": ("especie", "efectivo"),
                 "anexo3": ("total_sgr", "total_contrapartida", "total"),
                 "mga": ("total_sgr", "total")}
FIGURE_LABELS = {"sigp": "SIGP", "anexo1": "Anexo 1", "anexo3": "Anexo 3", "mga": "MGA Web"}
TOLERANCE = 1  # pesos
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class InputError(ValueError):
    """Bad input: missing or invalid data, unknown id or field, wrong flow."""


class RenderRefused(Exception):
    def __init__(self, errors: list[dict]) -> None:
        super().__init__("hallazgos de error")
        self.errors = errors


@functools.lru_cache(maxsize=None)
def _sibling(name: str):
    """scripts/<name>.py of this folder, loaded under a private module name; None when missing."""
    path = HERE / f"{name}.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"_requisitos_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path):
    """(data, error message): None data when the file is missing or invalid."""
    if not path.is_file():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        return None, str(exc)


def _finding(severity: str, code: str, node: str, message: str) -> dict:
    return {"severity": severity, "code": code, "message": message, "node": node}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _text(value) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _dicts(value) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _plain_money(value) -> str:
    return "$" + f"{round(value):,}".replace(",", ".")


def _valid_date(value) -> bool:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _valid_path(value) -> bool:
    """A non-empty path relative to the run root that stays inside it."""
    if not isinstance(value, str) or not value.strip():
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts and not re.match(r"^[A-Za-z]:", value)


# --- Context: rubric, alliance, budget, endorsement ----------------------------------

def _rubric(run: Path) -> dict | None:
    """The call's rubric (juez_sgr.resolve_rubric), or None when none can be resolved."""
    juez = _sibling("juez_sgr")
    if juez is None:
        return None
    try:
        rubric, _, _ = juez.resolve_rubric(run, None)
    except (juez.JuezError, OSError, ValueError):
        return None
    return rubric if isinstance(rubric, dict) else None


def _requirements(rubric) -> list[dict]:
    """The rubric's enabling requirements with an id, in the TdR order."""
    if not isinstance(rubric, dict):
        return []
    return [r for r in _dicts(rubric.get("requisitos")) if _text(r.get("id"))]


def _entities(alliance) -> dict[str, dict] | None:
    if not isinstance(alliance, dict):
        return None
    return {_text(e.get("id")): e for e in _dicts(alliance.get("entidades")) if _text(e.get("id"))}


def _proponent(alliance) -> dict | None:
    return next((e for e in (_entities(alliance) or {}).values() if e.get("proponente") is True), None)


def _summary(run: Path) -> dict | None:
    """presupuesto_sgr.resumen, or None without a readable budget."""
    module = _sibling("presupuesto_sgr")
    if module is None:
        return None
    try:
        return module.resumen(run)
    except Exception:  # the budget is optional context: its own checks report its problems
        return None


def _procedures() -> list[dict]:
    data, _ = _read_json(AVAL_FILE)
    return _dicts(data.get("instituciones")) if isinstance(data, dict) else []


def _institution(alliance, convocatoria) -> dict | None:
    """The endorsement procedure that applies to the proponent and the call, or None."""
    name = _text((_proponent(alliance) or {}).get("nombre"))
    if not name or not convocatoria:
        return None
    for institution in _procedures():
        try:
            matches = re.search(institution.get("patron_nombre") or "$^", name, re.I)
        except re.error:
            continue
        if matches and convocatoria in (institution.get("convocatorias") or []):
            return institution
    return None


def _institution_by_id(iid) -> dict | None:
    return next((i for i in _procedures() if i.get("id") == iid), None) if iid else None


def _derived(alliance, summary) -> dict[str, bool | None]:
    """{condition: applies} for every condition; None when it is not derived or its data is missing."""
    out: dict[str, bool | None] = {c: None for c in CONDITIONS}
    entities = _entities(alliance)
    if entities is not None:
        kinds = {e.get("tipo") for e in entities.values()}
        out["internacional"] = "internacional" in kinds
        out["sector_productivo"] = "sector_productivo" in kinds
        out["cofinanciacion"] = any(e.get("proponente") is not True and (_number(e.get("aporte_efectivo")) or 0) > 0
                                    for e in entities.values())
    if isinstance(summary, dict):
        rubro = (summary.get("por_rubro") or {}).get("infraestructura") or {}
        out["infraestructura"] = (_number(rubro.get("sgr")) or 0) > 0
    return out


def _context(run: Path) -> dict:
    rubric = _rubric(run)
    alliance, _ = _read_json(run / ALLIANCE_FILE)
    summary = _summary(run)
    return {"rubric": rubric, "requirements": _requirements(rubric), "alliance": alliance,
            "entities": _entities(alliance), "summary": summary, "derived": _derived(alliance, summary)}


def condiciones_derivadas(run_root: Path) -> dict[str, bool | None]:
    """{condition: True|False|None} derived from alianza.json and presupuesto.json."""
    run = Path(run_root)
    alliance, _ = _read_json(run / ALLIANCE_FILE)
    return _derived(alliance, _summary(run))


def _applies(requirement: dict, item: dict | None, derived: dict) -> bool:
    if (item or {}).get("estado") == "no_aplica" and requirement.get("condicion"):
        return False
    return derived.get(requirement.get("condicion")) is not False if requirement.get("condicion") else True


def _derived_for(requirement: dict, derived: dict) -> bool | None:
    condition = requirement.get("condicion")
    return True if not condition else derived.get(condition)


# --- Init and write -----------------------------------------------------------------

def _empty_item(iid: str) -> dict:
    return {"id": iid, "estado": "pendiente", "responsable": None, "archivo": None, "fecha": None, "nota": None,
            "justificacion": None}


def _skeleton(ctx: dict) -> dict:
    rubric = ctx["rubric"]
    convocatoria = _text(rubric.get("id")) if isinstance(rubric, dict) and _text(rubric.get("id")) else None
    institution = _institution(ctx["alliance"], convocatoria)
    return {
        "schema": SCHEMA,
        "convocatoria": convocatoria,
        "items": [_empty_item(_text(r["id"])) for r in ctx["requirements"]],
        "cifras": {doc: None for doc in FIGURE_FIELDS},
        "licencias": None,
        "aval_institucional": None if institution is None else {
            "institucion": institution.get("id"),
            "documentos": [{"indice": d.get("indice"), "estado": "pendiente", "archivo": None}
                           for d in _dicts(institution.get("documentos"))]},
    }


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


def _flujo(run: Path) -> str:
    module = _sibling("check_run")
    return module.detect_flujo(run) if module is not None else "base"


def init(run_root: Path) -> tuple[Path, list[str]]:
    """Create requisitos.json, or add the rubric requirements and endorsement documents it lacks.
    Returns (path, ids of the added requirements). Never overwrites an existing entry."""
    run = Path(run_root)
    if _flujo(run) != "sgr":
        raise InputError("los requisitos habilitantes son solo del flujo SGR")
    path = run / REQUIREMENTS_FILE
    ctx = _context(run)
    data, error = _read_json(path)
    if error:
        raise InputError(f"{REQUIREMENTS_FILE.as_posix()} no es JSON válido: {error}")
    if data is None:
        data = _skeleton(ctx)
        _write_atomic(path, data)
        return path, [item["id"] for item in data["items"]]
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise InputError(f"{REQUIREMENTS_FILE.as_posix()} no declara el esquema {SCHEMA}")
    changed = False
    items = data.setdefault("items", [])
    if not isinstance(items, list):
        raise InputError(f"{REQUIREMENTS_FILE.as_posix()}: «items» debe ser una lista")
    known = {_text(i.get("id")) for i in _dicts(items)}
    added = [_text(r["id"]) for r in ctx["requirements"] if _text(r["id"]) not in known]
    if added:
        items.extend(_empty_item(iid) for iid in added)
        changed = True
    skeleton = _skeleton(ctx)
    for key in ("convocatoria", "cifras", "licencias", "aval_institucional"):
        if key not in data:
            data[key] = skeleton[key]
            changed = True
    block = data.get("aval_institucional")
    institution = _institution_by_id(block.get("institucion")) if isinstance(block, dict) else None
    if institution is not None:
        documents = block.setdefault("documentos", [])
        have = {d.get("indice") for d in _dicts(documents)}
        for doc in _dicts(institution.get("documentos")):
            if doc.get("indice") not in have:
                documents.append({"indice": doc.get("indice"), "estado": "pendiente", "archivo": None})
                changed = True
    if changed:
        _write_atomic(path, data)
    return path, added


# --- Check ----------------------------------------------------------------------------

class _Rules:
    """The rules of requisitos.json (odd/tasks/sgr-requisitos-anexos.md, Contracts)."""

    def __init__(self, run: Path, data: dict, ctx: dict, final: bool) -> None:
        self.run = run
        self.data = data
        self.ctx = ctx
        self.final = final
        self.requirements = {_text(r["id"]): r for r in ctx["requirements"]}
        self.entities = ctx["entities"]
        self.out: list[dict] = []

    def add(self, severity: str, code: str, node: str, message: str) -> None:
        self.out.append(_finding(severity, code, node, message))

    def entity(self, node: str, eid) -> None:
        if self.entities is None or eid is None:
            return
        if not isinstance(eid, str) or _text(eid) not in self.entities:
            self.add("error", "requisitos-entidad-desconocida", node,
                     f"{node} cita la entidad «{eid}», que no está en {ALLIANCE_FILE.as_posix()}.")

    def run_all(self) -> list[dict]:
        if self.ctx["rubric"] is None:
            self.add("warning", "requisitos-rubrica-faltante", "requisitos",
                     "No se pudo resolver la rúbrica de la convocatoria (artefactos/juez/rubrica.json o el TdR): no "
                     "se cotejan los requisitos habilitantes.")
        elif not self.requirements:
            self.add("warning", "requisitos-rubrica-faltante", "requisitos",
                     "La rúbrica de la convocatoria no trae «requisitos»: no se cotejan los requisitos habilitantes.")
        if self.entities is None:
            self.add("warning", "requisitos-alianza-faltante", "requisitos",
                     f"No se encontró {ALLIANCE_FILE.as_posix()}: no se derivan las condiciones de la alianza ni se "
                     "cotejan las entidades responsables.")
        self.items()
        self.figures()
        self.licences()
        self.endorsement()
        return self.out

    # Requirements ----------------------------------------------------------------------
    def items(self) -> None:
        items = self.data.get("items")
        if not isinstance(items, list):
            self.add("error", "requisitos-valor-invalido", "items", "requisitos.json necesita la lista «items».")
            items = []
        seen: set[str] = set()
        derived = self.ctx["derived"]
        for n, item in enumerate(items, start=1):
            if not isinstance(item, dict) or not _text(item.get("id")):
                self.add("error", "requisitos-valor-invalido", f"items[{n}]", f"items[{n}] no es un objeto con «id».")
                continue
            iid = _text(item["id"])
            if iid in seen:
                self.add("error", "requisitos-id-repetido", iid, f"El requisito {iid} aparece dos veces en items.")
            seen.add(iid)
            requirement = self.requirements.get(iid)
            if requirement is None and self.requirements:
                self.add("error", "requisitos-id-desconocido", iid,
                         f"El requisito {iid} no está en la rúbrica de la convocatoria.")
            self.item_values(iid, item)
            self.entity(iid, item.get("responsable"))
            state = item.get("estado")
            if state == "no_aplica":
                if not _text(item.get("justificacion")):
                    self.add("error", "requisitos-justificacion-faltante", iid,
                             f"El requisito {iid} está marcado «no_aplica» sin justificación.")
                if requirement is not None and not requirement.get("condicion"):
                    self.add("error", "requisitos-no-aplica-invalido", iid,
                             f"El requisito {iid} «{_text(requirement.get('nombre'))}» no es condicional en el TdR: "
                             "no puede marcarse «no_aplica» («se tendrá por no cumplida toda condición que no haya "
                             "sido soportada documentalmente»).")
                elif requirement is not None and derived.get(requirement.get("condicion")) is True:
                    self.add("error", "requisitos-condicion-aplica", iid,
                             f"El requisito {iid} está marcado «no_aplica», pero la condición "
                             f"«{requirement['condicion']}» se cumple según la alianza o el presupuesto.")
            if state == "listo":
                archivo = item.get("archivo")
                if archivo is None or not _text(archivo):
                    self.add("warning", "requisitos-sin-archivo", iid,
                             f"El requisito {iid} está «listo» sin archivo de soporte.")
                elif _valid_path(archivo) and not (self.run / archivo).is_file():
                    self.add("error", "requisitos-archivo-inexistente", iid,
                             f"El requisito {iid} cita el archivo «{archivo}», que no existe en la corrida.")
            if self.final and requirement is not None and state != "listo" and _applies(requirement, item, derived):
                self.add("error", "requisitos-pendiente-final", iid,
                         f"El requisito habilitante {iid} «{_text(requirement.get('nombre'))}» aplica y está "
                         f"«{state}»: para radicar debe estar «listo».")
        for iid, requirement in self.requirements.items():
            if iid not in seen:
                self.add("warning", "requisitos-item-faltante", iid,
                         f"El requisito {iid} «{_text(requirement.get('nombre'))}» de la rúbrica no tiene entrada en "
                         "requisitos.json (python3 scripts/requisitos_sgr.py init <RUN_ROOT> la agrega).")
                if self.final and _applies(requirement, None, derived):
                    self.add("error", "requisitos-pendiente-final", iid,
                             f"El requisito habilitante {iid} «{_text(requirement.get('nombre'))}» aplica y no "
                             "está «listo».")

    def item_values(self, iid: str, item: dict) -> None:
        invalid = []
        if item.get("estado") not in STATES:
            invalid.append(f"estado «{item.get('estado')}» (uno de {', '.join(STATES)})")
        if item.get("fecha") is not None and not _valid_date(item.get("fecha")):
            invalid.append(f"fecha «{item.get('fecha')}» (AAAA-MM-DD)")
        if item.get("archivo") is not None and not _valid_path(item.get("archivo")):
            invalid.append(f"archivo «{item.get('archivo')}» (ruta relativa dentro de la corrida)")
        for key in ("nota", "justificacion"):
            if item.get(key) is not None and not isinstance(item.get(key), str):
                invalid.append(f"{key} (texto o null)")
        if invalid:
            self.add("error", "requisitos-valor-invalido", iid, f"El requisito {iid} tiene valores inválidos: "
                                                                f"{'; '.join(invalid)}.")

    # Figures ---------------------------------------------------------------------------
    def figures(self) -> None:
        block = self.data.get("cifras")
        if block is None:
            block = {}
        if not isinstance(block, dict):
            self.add("error", "requisitos-valor-invalido", "cifras", "«cifras» debe ser un objeto.")
            return
        rows, problems = _figure_rows(block, self.ctx)
        for node, message in problems:
            self.add("error", "requisitos-valor-invalido", node, message)
        declared = any(r["declarado"] is not None for r in rows)
        if declared and self.ctx["summary"] is None:
            self.add("warning", "requisitos-presupuesto-faltante", "cifras",
                     f"No se encontró {BUDGET_FILE.as_posix()}: no se cotejan las cifras declaradas del SIGP, el "
                     "Anexo 3 y la MGA Web.")
        for row in rows:
            if row["coincide"] is False:
                node = f"cifras.{row['documento']}.{row['campo']}"
                self.add("error", "requisitos-cifras-distintas", node,
                         f"{FIGURE_LABELS[row['documento']]}: {row['campo']} declara "
                         f"{_plain_money(row['declarado'])} y {row['fuente']} da {_plain_money(row['esperado'])} "
                         "(«Coherencia de las cifras entre el SIGP, el Anexo 1 … el Anexo 2 … y el Anexo 3»).")
        for doc in FIGURE_FIELDS:
            if block.get(doc) is None:
                self.add("info", "requisitos-cifras-sin-declarar", f"cifras.{doc}",
                         f"No se han declarado las cifras de {FIGURE_LABELS[doc]}; se cotejan cuando se declaren.")

    # Licences --------------------------------------------------------------------------
    def licences(self) -> None:
        block = self.data.get("licencias")
        if block is None:
            self.add("warning", "requisitos-licencias-faltantes", "licencias",
                     "No hay análisis de licencias y permisos (Anexo 2, cap. 28): «Enuncie las licencias, estudios, "
                     "permisos y demás requerimientos que se consideren necesarios previo o durante la ejecución "
                     "del proyecto».")
            return
        if not isinstance(block, dict) or not isinstance(block.get("items"), list):
            self.add("error", "requisitos-valor-invalido", "licencias",
                     "«licencias» debe ser un objeto con «introduccion» y la lista «items».")
            return
        if block.get("introduccion") is not None and not isinstance(block.get("introduccion"), str):
            self.add("error", "requisitos-valor-invalido", "licencias", "licencias.introduccion debe ser texto.")
        for n, licence in enumerate(block["items"], start=1):
            node = f"licencias.items[{n}]"
            if not isinstance(licence, dict):
                self.add("error", "requisitos-valor-invalido", node, f"{node} no es un objeto.")
                continue
            invalid = []
            if not _text(licence.get("licencia")):
                invalid.append("licencia (nombre)")
            if not isinstance(licence.get("aplica"), bool):
                invalid.append("aplica (true o false)")
            moment = licence.get("momento")
            if moment is not None and moment not in MOMENTS:
                invalid.append(f"momento «{moment}» (previo o ejecucion)")
            if invalid:
                self.add("error", "requisitos-valor-invalido", node, f"{node} tiene valores inválidos: "
                                                                     f"{'; '.join(invalid)}.")
            self.entity(node, licence.get("responsable"))
            if licence.get("aplica") is True:
                missing = [key for key in ("norma", "responsable", "momento") if not _text(licence.get(key))]
                if missing:
                    self.add("error", "requisitos-licencia-incompleta", node,
                             f"La licencia o permiso «{_text(licence.get('licencia'))}» aplica y le falta: "
                             f"{', '.join(missing)}.")
            elif licence.get("aplica") is False and not _text(licence.get("justificacion")):
                self.add("error", "requisitos-licencia-sin-justificacion", node,
                         f"La licencia o permiso «{_text(licence.get('licencia'))}» no aplica y no tiene "
                         "justificación.")

    # Institutional endorsement ----------------------------------------------------------
    def endorsement(self) -> None:
        block = self.data.get("aval_institucional")
        institution = None
        if isinstance(block, dict) and block.get("institucion"):
            institution = _institution_by_id(block.get("institucion"))
        if institution is None:
            institution = _institution(self.ctx["alliance"], _text(self.data.get("convocatoria"))
                                       or _text((self.ctx["rubric"] or {}).get("id")))
        if block is not None and not isinstance(block, dict):
            self.add("error", "requisitos-valor-invalido", "aval_institucional",
                     "«aval_institucional» debe ser un objeto o null.")
            return
        entries = {}
        for n, doc in enumerate(_dicts((block or {}).get("documentos")), start=1):
            node = f"aval_institucional.documentos[{doc.get('indice', n)}]"
            entries[doc.get("indice")] = doc
            if doc.get("estado") not in STATES:
                self.add("error", "requisitos-valor-invalido", node,
                         f"{node} tiene estado «{doc.get('estado')}» (uno de {', '.join(STATES)}).")
            if doc.get("archivo") is not None and not _valid_path(doc.get("archivo")):
                self.add("error", "requisitos-valor-invalido", node,
                         f"{node} tiene archivo «{doc.get('archivo')}» (ruta relativa dentro de la corrida).")
        if institution is None:
            return
        for doc in _dicts(institution.get("documentos")):
            if doc.get("indice") not in entries:
                self.add("warning", "requisitos-aval-documento-faltante",
                         f"aval_institucional.documentos[{doc.get('indice')}]",
                         f"El aval institucional de {_text(institution.get('nombre'))} pide «{_text(doc.get('texto'))}» "
                         "y requisitos.json no lo registra.")


def _figure_rows(block: dict, ctx: dict) -> tuple[list[dict], list[tuple[str, str]]]:
    """([{documento, campo, declarado, esperado, coincide, fuente}], [(node, invalid-value message)])."""
    summary, entities = ctx["summary"], ctx["entities"]
    expected_totals = None
    if isinstance(summary, dict):
        expected_totals = {"total_sgr": summary.get("total_sgr"),
                           "total_contrapartida": (summary.get("total_especie") or 0)
                           + (summary.get("total_efectivo") or 0),
                           "total": summary.get("total")}
    rows: list[dict] = []
    problems: list[tuple[str, str]] = []

    def row(doc, field, declared, expected, source):
        match = None if declared is None or expected is None else abs(declared - expected) <= TOLERANCE
        rows.append({"documento": doc, "campo": field, "declarado": declared, "esperado": expected,
                     "coincide": match, "fuente": source})

    for doc in ("sigp", "anexo3", "mga"):
        value = block.get(doc)
        if value is not None and not isinstance(value, dict):
            problems.append((f"cifras.{doc}", f"cifras.{doc} debe ser un objeto o null."))
            value = None
        for field in FIGURE_FIELDS[doc]:
            declared = (value or {}).get(field)
            if declared is not None and _number(declared) is None:
                problems.append((f"cifras.{doc}.{field}", f"cifras.{doc}.{field} debe ser un número."))
                declared = None
            row(doc, field, declared, (expected_totals or {}).get(field), BUDGET_FILE.as_posix())
    value = block.get("anexo1")
    if value is not None and not (isinstance(value, dict) and isinstance(value.get("por_entidad", {}), dict)):
        problems.append(("cifras.anexo1", "cifras.anexo1 debe ser {por_entidad:{E1:{especie, efectivo}}} o null."))
        value = None
    declared_by_entity = (value or {}).get("por_entidad") or {}
    ids = list((entities or {}).keys()) + [e for e in declared_by_entity if e not in (entities or {})]
    for eid in ids:
        entity = (entities or {}).get(eid)
        declared_entity = declared_by_entity.get(eid)
        if declared_entity is not None and not isinstance(declared_entity, dict):
            problems.append((f"cifras.anexo1.{eid}", f"cifras.anexo1.por_entidad.{eid} debe ser un objeto."))
            declared_entity = None
        for kind in FIGURE_FIELDS["anexo1"]:
            declared = (declared_entity or {}).get(kind)
            if declared is not None and _number(declared) is None:
                problems.append((f"cifras.anexo1.{eid}.{kind}", f"cifras.anexo1.{eid}.{kind} debe ser un número."))
                declared = None
            expected = (_number(entity.get(f"aporte_{kind}")) or 0) if entity is not None else None
            row("anexo1", f"{eid}.{kind}", declared, expected, ALLIANCE_FILE.as_posix())
    order = {doc: n for n, doc in enumerate(FIGURE_FIELDS)}
    rows.sort(key=lambda r: order[r["documento"]])
    return rows, problems


def requirements_findings(data, run: Path, ctx: dict, final: bool = False) -> list[dict]:
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return [_finding("error", "requisitos-esquema", "requisitos", f"El archivo no declara el esquema {SCHEMA}.")]
    return _Rules(run, data, ctx, final).run_all()


def _load(run: Path) -> tuple[dict | None, list[dict]]:
    data, error = _read_json(run / REQUIREMENTS_FILE)
    if error:
        return None, [_finding("error", "requisitos-json-invalido", "requisitos",
                               f"{REQUIREMENTS_FILE.as_posix()} no es JSON válido: {error}")]
    return data, []


def findings(run_root: Path, final: bool = False) -> list[dict]:
    """Findings of requisitos.json; [] when it does not exist."""
    run = Path(run_root)
    if not (run / REQUIREMENTS_FILE).is_file():
        return []
    data, errors = _load(run)
    if errors:
        return errors
    return requirements_findings(data, run, _context(run), final)


def check_findings(run_root: Path, final: bool = False) -> list[dict]:
    """findings() plus an error when the file is missing (the CLI `check` and `render`)."""
    run = Path(run_root)
    if not (run / REQUIREMENTS_FILE).is_file():
        return [_finding("error", "requisitos-archivo-faltante", "requisitos",
                         f"No existe {REQUIREMENTS_FILE.as_posix()}.")]
    return findings(run, final)


# --- Read model, updates and judge facts ------------------------------------------------

def _items_by_id(data) -> dict[str, dict]:
    return {_text(i.get("id")): i for i in _dicts((data or {}).get("items")) if _text(i.get("id"))}


def _requirement_rows(data, ctx: dict) -> list[dict]:
    items = _items_by_id(data)
    rows = []
    for requirement in ctx["requirements"]:
        iid = _text(requirement["id"])
        item = items.get(iid) or _empty_item(iid)
        row = {key: requirement.get(key) for key in ("id", "nombre", "texto", "condicion", "documento",
                                                     "numeral_fuente")}
        row.update({key: item.get(key) for key in ITEM_FIELDS})
        row["estado"] = item.get("estado") if item.get("estado") in STATES else "pendiente"
        row["aplica_derivada"] = _derived_for(requirement, ctx["derived"])
        row["aplica"] = _applies(requirement, item, ctx["derived"])
        rows.append(row)
    return rows


def _endorsement_view(data, ctx: dict, convocatoria) -> dict:
    block = (data or {}).get("aval_institucional")
    block = block if isinstance(block, dict) else {}
    institution = _institution_by_id(block.get("institucion")) or _institution(ctx["alliance"], convocatoria)
    if institution is None:
        return {"institucion": None, "nombre": None, "fuente": None, "documentos": [], "hitos": []}
    entries = {d.get("indice"): d for d in _dicts(block.get("documentos"))}
    today = datetime.date.today()
    hitos = []
    for hito in _dicts(institution.get("hitos")):
        try:
            left = (datetime.date.fromisoformat(hito.get("fecha")) - today).days
        except (TypeError, ValueError):
            left = None
        hitos.append({**hito, "dias_restantes": left})
    return {
        "institucion": institution.get("id"), "nombre": institution.get("nombre"), "fuente": institution.get("fuente"),
        "documentos": [{"indice": d.get("indice"), "texto": d.get("texto"),
                        "estado": (entries.get(d.get("indice")) or {}).get("estado") or "pendiente",
                        "archivo": (entries.get(d.get("indice")) or {}).get("archivo")}
                       for d in _dicts(institution.get("documentos"))],
        "hitos": hitos,
    }


def vista(run_root: Path) -> dict:
    """{convocatoria, requisitos, progreso, cifras, licencias, aval, findings}: the dashboard read model.
    Works when requisitos.json is missing (every requirement reads as `pendiente`)."""
    run = Path(run_root)
    ctx = _context(run)
    data, _ = _load(run)
    data = data if isinstance(data, dict) else {}
    rubric = ctx["rubric"] or {}
    convocatoria = _text(data.get("convocatoria")) or _text(rubric.get("id")) or None
    rows = _requirement_rows(data, ctx)
    figures, _ = _figure_rows(data.get("cifras") if isinstance(data.get("cifras"), dict) else {}, ctx)
    applicable = [r for r in rows if r["aplica"]]
    return {
        "convocatoria": convocatoria,
        "requisitos": rows,
        "progreso": {"listos": sum(1 for r in applicable if r["estado"] == "listo"), "aplicables": len(applicable)},
        "cifras": [{k: r[k] for k in ("documento", "campo", "declarado", "esperado", "coincide")} for r in figures],
        "licencias": data.get("licencias") if isinstance(data.get("licencias"), dict) else None,
        "aval": _endorsement_view(data, ctx, convocatoria),
        "findings": findings(run),
    }


def _validate_change(field: str, value, entities) -> None:
    if field == "estado":
        if value not in STATES:
            raise InputError(f"estado «{value}» no es válido; los estados son {', '.join(STATES)}")
    elif field == "responsable":
        if value is not None and (not isinstance(value, str) or (entities is not None and value not in entities)):
            raise InputError(f"la entidad «{value}» no está en {ALLIANCE_FILE.as_posix()}")
    elif field == "archivo":
        if value is not None and not _valid_path(value):
            raise InputError(f"archivo «{value}» debe ser una ruta relativa dentro de la corrida")
    elif field == "fecha":
        if value is not None and not _valid_date(value):
            raise InputError(f"fecha «{value}» debe ser AAAA-MM-DD")
    elif value is not None and not isinstance(value, str):
        raise InputError(f"{field} debe ser texto o null")


def _validate_figures(doc: str, block) -> None:
    if block is None:
        return
    if not isinstance(block, dict):
        raise InputError(f"cifras.{doc} debe ser un objeto o null")
    if doc == "anexo1":
        if set(block) - {"por_entidad"} or not isinstance(block.get("por_entidad"), dict):
            raise InputError("cifras.anexo1 debe ser {por_entidad:{E1:{especie, efectivo}}}")
        for eid, values in block["por_entidad"].items():
            if not isinstance(values, dict) or set(values) - set(FIGURE_FIELDS["anexo1"]) or any(
                    v is not None and _number(v) is None for v in values.values()):
                raise InputError(f"cifras.anexo1.por_entidad.{eid} debe ser {{especie, efectivo}} numéricos")
        return
    if set(block) - set(FIGURE_FIELDS[doc]) or any(v is not None and _number(v) is None for v in block.values()):
        raise InputError(f"cifras.{doc} admite solo {', '.join(FIGURE_FIELDS[doc])}, numéricos")


def actualizar_item(run_root: Path, item_id: str, cambios: dict):
    """Update one requirement (fields estado, responsable, archivo, fecha, nota, justificacion) or, with
    id `cifras.<documento>`, replace one declared figures block. Creates the file through init when it is
    missing, writes atomically and returns the updated item (or block). Raises InputError (a ValueError)."""
    run = Path(run_root)
    item_id = _text(item_id)
    if item_id.startswith("cifras."):
        doc = item_id.split(".", 1)[1]
        if doc not in FIGURE_FIELDS:
            raise InputError(f"documento de cifras desconocido «{doc}»; los documentos son {', '.join(FIGURE_FIELDS)}")
        _validate_figures(doc, cambios)
    else:
        if not isinstance(cambios, dict):
            raise InputError("los cambios deben ser un objeto")
        unknown = sorted(set(cambios) - set(ITEM_FIELDS))
        if unknown:
            raise InputError(f"campos no editables: {', '.join(unknown)}; se editan {', '.join(ITEM_FIELDS)}")
        ctx = _context(run)
        for field, value in cambios.items():
            _validate_change(field, value, ctx["entities"])
    path = run / REQUIREMENTS_FILE
    if not path.is_file():
        init(run)
    data, errors = _load(run)
    if errors or not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise InputError(f"{REQUIREMENTS_FILE.as_posix()} no es válido; corrígelo antes de editarlo")
    if item_id.startswith("cifras."):
        figures = data.get("cifras") if isinstance(data.get("cifras"), dict) else {}
        figures[item_id.split(".", 1)[1]] = cambios
        data["cifras"] = figures
        _write_atomic(path, data)
        return cambios
    known = {_text(r["id"]) for r in _requirements(_rubric(run))} or set(_items_by_id(data))
    if item_id not in known:
        raise InputError(f"el requisito «{item_id}» no está en la rúbrica de la convocatoria")
    items = data.setdefault("items", [])
    item = next((i for i in _dicts(items) if _text(i.get("id")) == item_id), None)
    if item is None:
        item = _empty_item(item_id)
        items.append(item)
    item.update(cambios)
    _write_atomic(path, data)
    return item


def datos(run_root: Path) -> dict:
    """{requisitos, cifras_coherentes, cifras_diferencias, fuente}: the requirement facts of datos_sgr."""
    run = Path(run_root)
    out: dict = {"requisitos": None, "cifras_coherentes": None, "cifras_diferencias": [], "fuente": []}
    ctx = _context(run)
    data, _ = _load(run)
    exists = isinstance(data, dict)
    data = data if exists else {}
    if exists:
        out["fuente"].append(REQUIREMENTS_FILE.as_posix())
    if ctx["requirements"]:
        rows = _requirement_rows(data, ctx)
        applicable = [r for r in rows if r["aplica"]]
        out["requisitos"] = {"aplicables": len(applicable),
                             "listos": sum(1 for r in applicable if r["estado"] == "listo"),
                             "pendientes": [r["id"] for r in applicable if r["estado"] != "listo"],
                             "no_aplica": [r["id"] for r in rows if r["estado"] == "no_aplica" and not r["aplica"]]}
        if not exists:
            out["fuente"].append("artefactos/juez/rubrica.json (requisitos)")
    figures, _ = _figure_rows(data.get("cifras") if isinstance(data.get("cifras"), dict) else {}, ctx)
    compared = [r for r in figures if r["coincide"] is not None]
    if compared:
        out["cifras_coherentes"] = all(r["coincide"] for r in compared)
        out["cifras_diferencias"] = [{k: r[k] for k in ("documento", "campo", "declarado", "esperado")}
                                     for r in compared if not r["coincide"]]
    return out


# --- Render ---------------------------------------------------------------------------

def _escape(text) -> str:
    return _sibling("cadena_valor_sgr").escape(text)


def _placement(run: Path, stem: str) -> tuple[str, str | None]:
    """("section", TdR title|None) when the file opens its TdR chapter or no structure applies; ("sub", None)
    when another file of the chapter opens it (ensamblar_main)."""
    structure, _ = _read_json(run / STRUCTURE_FILE)
    assembler = _sibling("ensamblar_main")
    if not isinstance(structure, dict) or assembler is None:
        return "section", None
    try:
        assembler.validate(structure)
    except assembler.InputError:
        return "section", None
    for chapter in assembler.placed_chapters(structure, "sgr"):
        files = [f for f in chapter["archivos"] if not f.startswith("diag_")]
        if stem in files:
            return ("section", chapter.get("titulo")) if files[0] == stem else ("sub", None)
    return "section", None


def _header(sources: str) -> list[str]:
    return [
        GENERATED_HEADER,
        f"% Fuente: {sources}. No se edita a mano: se regenera con",
        "% python3 scripts/requisitos_sgr.py render <RUN_ROOT>.",
    ]


def _col(width: str, align: str = "raggedright") -> str:
    return rf">{{\{align}\arraybackslash}}p{{{width}\textwidth}}"


_X = r">{\raggedright\arraybackslash}X"


def _table(spec: str, header: list[str], rows: list, caption: str, label: str) -> list[str]:
    head = " & ".join(rf"\textbf{{{h}}}" for h in header) + r" \\"
    lines = [
        "",
        "{\\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        rf"\begin{{xltabular}}{{\textwidth}}{{{spec}}}",
        rf"\caption{{{caption}}}\label{{tab:{label}}}\\",
        r"\toprule", head, r"\midrule", r"\endfirsthead",
        r"\toprule", head, r"\midrule", r"\endhead",
        r"\bottomrule", r"\endlastfoot",
    ]
    lines += [row if isinstance(row, str) else " & ".join(row) + r" \\" for row in rows]
    lines += [r"\end{xltabular}", "}"]
    return lines


def _cell(value, empty: str = "Por definir") -> str:
    return _escape(_text(value)) if _text(value) else empty


class _Renderer:
    def __init__(self, run: Path, data: dict, ctx: dict) -> None:
        self.run = run
        self.data = data
        self.ctx = ctx
        self.entities = ctx["entities"] or {}

    def entity(self, eid) -> str:
        if not _text(eid):
            return "Por definir"
        entity = self.entities.get(_text(eid))
        return _escape(_text(entity.get("nombre")) if entity and _text(entity.get("nombre")) else eid)

    def heading(self, stem: str, default: str, label: str) -> list[str]:
        mode, title = _placement(self.run, stem)
        command = "section" if mode == "section" else "subsection"
        return [rf"\{command}{{{_escape(title or default)}}}", rf"\label{{sec:{label}}}"]

    # 38 --------------------------------------------------------------------------
    def licences(self) -> str:
        lines = _header(f"{REQUIREMENTS_FILE.as_posix()} y {ALLIANCE_FILE.as_posix()}")
        lines += self.heading(LICENSES_STEM, LICENSES_TITLE, "licencias_permisos")
        block = self.data.get("licencias") if isinstance(self.data.get("licencias"), dict) else {}
        if _text(block.get("introduccion")):
            lines += ["", _escape(_text(block.get("introduccion")))]
        rows = []
        for licence in _dicts(block.get("items")):
            applies = licence.get("aplica") is True
            rows.append([_cell(licence.get("licencia")), _cell(licence.get("norma"), "No aplica"),
                         "Sí" if applies else "No", _cell(licence.get("justificacion"), "Sin justificación"),
                         self.entity(licence.get("responsable")) if applies else "No aplica",
                         MOMENTS.get(licence.get("momento"), "Por definir") if applies else "No aplica"])
        if not rows:
            rows = [r"\multicolumn{6}{l}{Por definir} \\"]
        lines += _table(f"{_col('0.17')} {_col('0.15')} {_col('0.07', 'centering')} {_X} {_col('0.15')} "
                        f"{_col('0.12')}",
                        ["Licencia o permiso", "Norma", "¿Aplica?", "Justificación", "Responsable",
                         "Momento del trámite"], rows,
                        "Licencias, permisos y demás requerimientos previos o durante la ejecución del proyecto.",
                        "licencias_permisos")
        return "\n".join(lines + [""])

    # 39 --------------------------------------------------------------------------
    def annexes(self) -> str:
        lines = _header(f"{REQUIREMENTS_FILE.as_posix()}, la rúbrica de la convocatoria, {ALLIANCE_FILE.as_posix()} "
                        f"y {BUDGET_FILE.as_posix()}")
        lines += self.heading(ANNEXES_STEM, ANNEXES_TITLE, "anexos")
        rows = [r for r in _requirement_rows(self.data, self.ctx) if r["aplica"]]
        lines += ["", r"\begin{itemize}"]
        if rows:
            lines += [rf"\item {_escape(_text(r['documento']))} (requisito {_escape(r['id'])}: "
                      rf"{_escape(_text(r['nombre']))})" for r in rows]
        else:
            lines.append(r"\item Por definir")
        lines += [r"\end{itemize}"]
        return "\n".join(lines + [""])


def render_sections(run_root: Path) -> list[Path]:
    """Write sections 38 and 39; refuses outside the SGR flow and while there are error findings."""
    run = Path(run_root)
    if _flujo(run) != "sgr":
        raise InputError("los requisitos y anexos son solo del flujo SGR")
    if not (run / REQUIREMENTS_FILE).is_file():
        raise InputError(f"no existe {REQUIREMENTS_FILE.as_posix()}: python3 scripts/requisitos_sgr.py init "
                         "<RUN_ROOT> lo crea")
    errors = [f for f in check_findings(run) if f["severity"] == "error"]
    if errors:
        raise RenderRefused(errors)
    data, _ = _read_json(run / REQUIREMENTS_FILE)
    renderer = _Renderer(run, data, _context(run))
    texts = {LICENSES_STEM: renderer.licences(), ANNEXES_STEM: renderer.annexes()}
    out_dir = run / SECTIONS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for stem, text in texts.items():
        path = out_dir / f"{stem}.tex"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


# --- CLI ----------------------------------------------------------------------------

def _print_findings(found: list[dict], stream) -> None:
    for f in found:
        print(f"[{f['severity'].upper()}] {f['code']} [{f['node']}] {f['message']}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("init", "create or complete requisitos.json from the rubric"),
                       ("check", "validate requisitos.json"),
                       ("render", "write sections 38 and 39"),
                       ("datos", "requirement facts of datos_sgr")):
        p = sub.add_parser(name, help=text)
        p.add_argument("run_root", type=Path)
        if name in ("check", "datos"):
            p.add_argument("--json", action="store_true", help="print JSON")
        if name == "check":
            p.add_argument("--final", action="store_true", help="applicable requirements not ready are errors")
    args = parser.parse_args(argv)
    run = args.run_root.resolve()

    if args.command == "init":
        try:
            path, added = init(run)
        except InputError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"REQUISITOS: {path} ({len(added)} requisitos agregados)")
        return 0

    if args.command == "render":
        try:
            for path in render_sections(run):
                print(f"SECCION: {path}")
        except RenderRefused as exc:
            print("error: requisitos.json tiene hallazgos de error; no se generan las secciones.", file=sys.stderr)
            _print_findings(exc.errors, sys.stderr)
            return 1
        except InputError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.command == "datos":
        print(json.dumps(datos(run), ensure_ascii=False, indent=2))
        return 0

    if not (run / REQUIREMENTS_FILE).is_file():
        print(f"error: no existe {REQUIREMENTS_FILE.as_posix()}", file=sys.stderr)
        return 2
    found = check_findings(run, final=args.final)
    errors = sum(1 for f in found if f["severity"] == "error")
    view = vista(run)
    if args.json:
        print(json.dumps({"findings": found, "progreso": view["progreso"]}, ensure_ascii=False, indent=2))
    else:
        _print_findings(found, sys.stdout)
        print(f"requisitos: {errors} errores, {len(found) - errors} avisos; listos {view['progreso']['listos']} de "
              f"{view['progreso']['aplicables']} aplicables")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
