#!/usr/bin/env python3
"""SGR alliance and territory as data: check, render, rubric preview and judge facts (flujo SGR only).

`artefactos/sgr/alianza.json` (schema `morfeo.alianza-sgr/v1`):

    {schema, monto_sgr_solicitado|null, duracion_meses|null,
     entidades:[{id:"E1", nombre, nit|null,
       tipo:"IES"|"SNCTI"|"entidad_territorial"|"usuario_adoptante"|"sector_productivo"|"internacional"|"otro",
       proponente:bool, departamento|null, rol,
       posicion:"cooperante"|"beneficiario"|"oponente"|"perjudicado"|null,
       interes|null, responsabilidades:[str], actividades:["1.1.1"], aporte_especie|null, aporte_efectivo|null,
       domicilio_en_region|null, tipo_diverso|null,
       grupos:[{nombre, codigo_gruplac|null, clasificacion|null, lineas:[str]}],
       trayectoria:[{nombre, codigo|null, financiador|null, anio|null, sgr_o_elegible:bool}]}],
     gobernanza:{toma_decisiones, instancias, propiedad_intelectual, seguimiento}|null}

`trayectoria` lists the projects that count beyond the minimum requirement of
the call; a project listed by two entities counts once (by code, else name).

`artefactos/sgr/territorio.json` (schema `morfeo.territorio-sgr/v1`):

    {schema, region_sgr|null, departamentos:[{nombre, municipios:[str]}],
     demandas:[{codigo, texto, departamento, fuente, causas:[tree node ids], objetivos:["OE1"],
                actividades:["1.1.1"], productos:["1.1"], articulacion}],
     configuracion_regional:[{actor, departamento, pertinencia}]}

`texto` is the demand copied verbatim from the TdR (estilo_sgr whitelists it).

Commands:
  check RUN_ROOT [--json]
      Findings with check_run's shape {severity, code, message, node}, codes
      prefixed `alianza-` or `territorio-`; a missing file is an error here.
  render RUN_ROOT
      Write redaccion/sections/26_identificacion.tex (Anexo 2 cap. 1),
      27_demandas_territoriales.tex (caps. 8 and 8.1) and
      28_matriz_responsabilidades.tex (cap. 10.1 and the governance model)
      deterministically. Refuses while there are error findings.
      29_idoneidad_trayectoria (cap. 27) is written by the redactor.
  puntaje RUN_ROOT [--json]
      [{subcriterio, nombre, puntaje, max, incompleto, calculo}] for the
      `conteo` subcriteria of the rubric (artefactos/juez/rubrica.json, else
      the one juez_sgr detects in the TdR, else none: empty list and a note).
  datos RUN_ROOT [--json]
      Partial `morfeo.datos-sgr/v1` facts (monto, departamentos, proponente,
      aliados, trayectoria, aliado internacional) with `fuente`.

Exit codes: 0 ok, 1 error findings (check, render), 2 bad input.
Standard library only. The value chain codes come from
artefactos/sgr/cadena_valor.json, the LaTeX escaping from
cadena_valor_sgr.py, the TdR chapters from ensamblar_main.py and the scoring
from juez_sgr.py (all in this folder). check_run imports `findings`.
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import re
import sys
from pathlib import Path

ALLIANCE_SCHEMA = "morfeo.alianza-sgr/v1"
TERRITORY_SCHEMA = "morfeo.territorio-sgr/v1"
DATA_SCHEMA = "morfeo.datos-sgr/v1"
ALLIANCE_FILE = Path("artefactos") / "sgr" / "alianza.json"
TERRITORY_FILE = Path("artefactos") / "sgr" / "territorio.json"
CHAIN_FILE = Path("artefactos") / "sgr" / "cadena_valor.json"
TREE_FILE = Path("artefactos") / "arboles" / "arbol_objetivos.json"
STRUCTURE_FILE = Path("artefactos") / "estructura_tdr.json"
RUBRIC_IN_RUN = Path("artefactos") / "juez" / "rubrica.json"
SECTIONS_DIR = Path("redaccion") / "sections"
GENERATED_HEADER = "% GENERADO por scripts/alianza_territorio_sgr.py"

ENTITY_TYPES = {
    "IES": "Institución de Educación Superior (IES)",
    "SNCTI": "Actor del SNCTI",
    "entidad_territorial": "Entidad territorial",
    "usuario_adoptante": "Actor usuario, participante o adoptante",
    "sector_productivo": "Sector productivo",
    "internacional": "Aliado internacional",
    "otro": "Otro",
}
POSITIONS = ("cooperante", "beneficiario", "oponente", "perjudicado")
GOVERNANCE = (("toma_decisiones", "Toma de decisiones"), ("instancias", "Instancias"),
              ("propiedad_intelectual", "Propiedad intelectual"), ("seguimiento", "Seguimiento"))
HERE = Path(__file__).resolve().parent


class InputError(Exception):
    pass


class RenderRefused(Exception):
    def __init__(self, errors: list[dict]) -> None:
        super().__init__("hallazgos de error")
        self.errors = errors


@functools.lru_cache(maxsize=None)
def _sibling(name: str):
    """scripts/<name>.py of this folder, loaded under a private module name."""
    spec = importlib.util.spec_from_file_location(f"_alianza_{name}", HERE / f"{name}.py")
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


def _key(value) -> str:
    return _text(value).casefold()


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _entities(alliance: dict) -> list[dict]:
    return [e for e in _list(alliance.get("entidades")) if isinstance(e, dict)]


def _chain_codes(chain) -> tuple[set[str], set[str]] | None:
    """(product codes, activity codes) of the value chain, or None without it."""
    if not isinstance(chain, dict):
        return None
    products, activities = set(), set()
    for objective in _list(chain.get("objetivos")):
        for product in _list(objective.get("productos") if isinstance(objective, dict) else None):
            if not isinstance(product, dict):
                continue
            products.add(str(product.get("codigo")))
            activities.update(str(a.get("codigo")) for a in _list(product.get("actividades")) if isinstance(a, dict))
    return products, activities


def _tree_objectives(tree) -> set[str] | None:
    if not isinstance(tree, dict):
        return None
    groups = [g for g in _list(tree.get("groups")) if isinstance(g, dict)]
    return {f"OE{n}" for n in range(1, len(groups) + 1)} | {str(g.get("id")) for g in groups if g.get("id")}


# --- Check ----------------------------------------------------------------

def _trajectory_projects(alliance: dict) -> list[dict]:
    """Unique trajectory projects: [{nombre, sgr, entidades}], identified by code, else by name."""
    projects: list[dict] = []
    index: dict[str, dict] = {}
    for entity in _entities(alliance):
        eid = str(entity.get("id") or "?")
        for item in _list(entity.get("trayectoria")):
            if not isinstance(item, dict):
                continue
            keys = [k for k in (f"codigo:{_key(item.get('codigo'))}" if _key(item.get("codigo")) else "",
                                f"nombre:{_key(item.get('nombre'))}" if _key(item.get("nombre")) else "") if k]
            if not keys:
                continue
            project = next((index[k] for k in keys if k in index), None)
            if project is None:
                project = {"nombre": _text(item.get("nombre")) or _text(item.get("codigo")), "sgr": False,
                           "entidades": []}
                projects.append(project)
            for k in keys:
                index.setdefault(k, project)
            project["sgr"] = project["sgr"] or item.get("sgr_o_elegible") is True
            if eid not in project["entidades"]:
                project["entidades"].append(eid)
    return projects


def alliance_findings(alliance, codes: tuple[set[str], set[str]] | None) -> list[dict]:
    """Rules of alianza.json (odd/tasks/sgr-alianza-territorio.md, Contracts)."""
    if not isinstance(alliance, dict) or alliance.get("schema") != ALLIANCE_SCHEMA:
        return [_finding("error", "alianza-esquema", "alianza", f"El archivo no declara el esquema {ALLIANCE_SCHEMA}.")]
    out: list[dict] = []
    entities = _entities(alliance)
    proponents = [str(e.get("id")) for e in entities if e.get("proponente") is True]
    if len(proponents) != 1:
        out.append(_finding("error", "alianza-proponente", "alianza",
                            f"La alianza declara {len(proponents)} entidades proponentes; debe haber exactamente una."))
    seen: set[str] = set()
    for entity in entities:
        eid = str(entity.get("id") or "?")
        if eid in seen:
            out.append(_finding("error", "alianza-id-duplicado", eid, f"El id de entidad {eid} está repetido."))
        seen.add(eid)
        if entity.get("tipo") not in ENTITY_TYPES:
            out.append(_finding("error", "alianza-tipo-invalido", eid,
                                f"La entidad {eid} tiene tipo «{entity.get('tipo')}»; los tipos válidos son "
                                f"{', '.join(ENTITY_TYPES)}."))
        position = entity.get("posicion")
        if position is not None and position not in POSITIONS:
            out.append(_finding("error", "alianza-posicion-invalida", eid,
                                f"La entidad {eid} tiene posición «{position}»; las posiciones de la MGA son "
                                f"{', '.join(POSITIONS)}."))
        for field in ("aporte_especie", "aporte_efectivo"):
            value = entity.get(field)
            if value is None:
                continue
            if _number(value) is None:
                out.append(_finding("error", "alianza-aporte-invalido", eid,
                                    f"El {field.replace('_', ' ')} de la entidad {eid} no es un número."))
            elif value < 0:
                out.append(_finding("error", "alianza-aporte-negativo", eid,
                                    f"El {field.replace('_', ' ')} de la entidad {eid} es negativo."))
        if codes is not None:
            unknown = [str(a) for a in _list(entity.get("actividades")) if str(a) not in codes[1]]
            if unknown:
                out.append(_finding("error", "alianza-actividad-desconocida", eid,
                                    f"La entidad {eid} cita actividades que no están en la cadena de valor: "
                                    f"{', '.join(unknown)}."))
    count = {kind: sum(1 for e in entities if e.get("tipo") == kind) for kind in ENTITY_TYPES}
    missing = []
    if count["IES"] < 1:
        missing.append("una IES")
    if count["IES"] + count["SNCTI"] < 2:
        missing.append("otra entidad del SNCTI")
    if count["entidad_territorial"] < 1:
        missing.append("una entidad territorial")
    if count["usuario_adoptante"] < 1:
        missing.append("un actor usuario, participante o adoptante")
    if missing:
        out.append(_finding("error", "alianza-composicion-minima", "alianza",
                            "La alianza no cumple la composición mínima del TdR (una IES, otra entidad del SNCTI, "
                            f"una entidad territorial y un usuario o adoptante): falta {', '.join(missing)}."))
    governance = alliance.get("gobernanza")
    empty = [label for key, label in GOVERNANCE
             if not isinstance(governance, dict) or not _governance_text(governance.get(key))]
    if empty:
        out.append(_finding("warning", "alianza-gobernanza-faltante", "gobernanza",
                            "El modelo de gobernanza (Anexo 1, rúbrica 4.1) está incompleto: falta "
                            f"{', '.join(label.lower() for label in empty)}."))
    for project in _trajectory_projects(alliance):
        if len(project["entidades"]) > 1:
            out.append(_finding("warning", "alianza-trayectoria-duplicada", project["entidades"][0],
                                f"El proyecto «{project['nombre']}» figura en la trayectoria de "
                                f"{', '.join(project['entidades'])}: cuenta una sola vez (rúbrica 3.1)."))
    return out


def territory_findings(territory, alliance, codes: tuple[set[str], set[str]] | None,
                       objectives: set[str] | None) -> list[dict]:
    """Rules of territorio.json; the department rules also read the alliance when it is valid."""
    if not isinstance(territory, dict) or territory.get("schema") != TERRITORY_SCHEMA:
        return [_finding("error", "territorio-esquema", "territorio",
                         f"El archivo no declara el esquema {TERRITORY_SCHEMA}.")]
    out: list[dict] = []
    departments = [_text(d.get("nombre")) for d in _list(territory.get("departamentos"))
                   if isinstance(d, dict) and _text(d.get("nombre"))]
    entities = _entities(alliance) if isinstance(alliance, dict) and alliance.get("schema") == ALLIANCE_SCHEMA \
        else None
    if entities is not None:
        territorial = {_key(e.get("departamento")) for e in entities if e.get("tipo") == "entidad_territorial"}
        for name in departments:
            if _key(name) not in territorial:
                out.append(_finding("warning", "territorio-departamento-sin-entidad", name,
                                    f"El departamento de ejecución {name} no tiene una entidad territorial en la "
                                    "alianza."))
        execution = {_key(name) for name in departments}
        for entity in entities:
            department = entity.get("departamento")
            if department and _key(department) not in execution:
                out.append(_finding("warning", "alianza-departamento-fuera", str(entity.get("id") or "?"),
                                    f"La entidad {entity.get('id')} está en {department}, que no es un departamento "
                                    "de ejecución de territorio.json."))
    demands = [d for d in _list(territory.get("demandas")) if isinstance(d, dict)]
    if demands and objectives is None:
        out.append(_finding("warning", "territorio-arbol-faltante", "territorio",
                            f"No se encontró {TREE_FILE.as_posix()}; no se pueden cotejar los objetivos de las demandas."))
    seen: set[str] = set()
    for n, demand in enumerate(demands, start=1):
        code = _text(demand.get("codigo")) or f"demanda {n}"
        if code in seen:
            out.append(_finding("error", "territorio-demanda-duplicada", code, f"El código de demanda {code} está repetido."))
        seen.add(code)
        missing = [field for field in ("codigo", "texto", "fuente") if not _text(demand.get(field))]
        if not _list(demand.get("objetivos")):
            missing.append("objetivos")
        if missing:
            out.append(_finding("error", "territorio-demanda-incompleta", code,
                                f"A la demanda {code} le falta: {', '.join(missing)}."))
        if not _text(demand.get("articulacion")):
            out.append(_finding("warning", "territorio-articulacion-faltante", code,
                                f"La demanda {code} no tiene el texto de articulación y contribución del proyecto."))
        if objectives is not None:
            unknown = [str(o) for o in _list(demand.get("objetivos")) if str(o) not in objectives]
            if unknown:
                out.append(_finding("error", "territorio-objetivo-desconocido", code,
                                    f"La demanda {code} cita objetivos que no están en el árbol de objetivos: "
                                    f"{', '.join(unknown)}."))
        if codes is None:
            continue
        for field, known, label, unknown_code, none_code in (
                ("actividades", codes[1], "actividades", "territorio-actividad-desconocida",
                 "territorio-demanda-sin-actividad"),
                ("productos", codes[0], "productos", "territorio-producto-desconocido",
                 "territorio-demanda-sin-producto")):
            listed = [str(c) for c in _list(demand.get(field))]
            if not listed:
                out.append(_finding("warning", none_code, code,
                                    f"La demanda {code} no se vincula con {label} de la cadena de valor."))
            unknown = [c for c in listed if c not in known]
            if unknown:
                out.append(_finding("error", unknown_code, code,
                                    f"La demanda {code} cita {label} que no están en la cadena de valor: "
                                    f"{', '.join(unknown)}."))
    return out


def _load_inputs(run: Path) -> dict:
    """Parsed files of the run, with the findings for unreadable ones."""
    out: dict = {"errores": []}
    for key, rel, prefix in (("alianza", ALLIANCE_FILE, "alianza"), ("territorio", TERRITORY_FILE, "territorio")):
        data, error = _read_json(run / rel)
        out[key] = data
        out[f"{key}_existe"] = (run / rel).is_file()
        if error:
            out["errores"].append(_finding("error", f"{prefix}-json-invalido", prefix,
                                           f"{rel.as_posix()} no es JSON válido: {error}"))
    chain, _ = _read_json(run / CHAIN_FILE)
    tree, _ = _read_json(run / TREE_FILE)
    out["codigos"] = _chain_codes(chain)
    out["objetivos"] = _tree_objectives(tree)
    return out


def findings(run_root: Path) -> list[dict]:
    """Findings of the files that exist; [] when neither does."""
    run = Path(run_root)
    data = _load_inputs(run)
    out = list(data["errores"])
    if data["alianza"] is not None:
        out += alliance_findings(data["alianza"], data["codigos"])
    if data["territorio"] is not None:
        out += territory_findings(data["territorio"], data["alianza"], data["codigos"], data["objetivos"])
    return out


def check_findings(run_root: Path) -> list[dict]:
    """findings() plus an error for each missing file (the CLI `check` and `render`)."""
    run = Path(run_root)
    out = findings(run)
    for rel, prefix in ((ALLIANCE_FILE, "alianza"), (TERRITORY_FILE, "territorio")):
        if not (run / rel).is_file():
            out.append(_finding("error", f"{prefix}-archivo-faltante", prefix, f"No existe {rel.as_posix()}."))
    return out


# --- Judge facts and rubric preview -----------------------------------------

def _member(entity: dict, source: str) -> dict:
    return {"nombre": _text(entity.get("nombre")), "tipo": entity.get("tipo"),
            "departamento": entity.get("departamento"), "contrapartida_especie": entity.get("aporte_especie"),
            "contrapartida_efectivo": entity.get("aporte_efectivo"), "fuente": source}


def datos(run_root: Path) -> dict:
    """Partial morfeo.datos-sgr/v1 facts taken from alianza.json and territorio.json."""
    run = Path(run_root)
    alliance, _ = _read_json(run / ALLIANCE_FILE)
    territory, _ = _read_json(run / TERRITORY_FILE)
    alliance = alliance if isinstance(alliance, dict) else None
    territory = territory if isinstance(territory, dict) else None
    a_src, t_src = ALLIANCE_FILE.as_posix(), TERRITORY_FILE.as_posix()
    out: dict = {"schema": DATA_SCHEMA, "monto_sgr": None, "duracion_meses": None, "departamentos_ejecucion": None,
                 "proponente": None, "aliados": None, "trayectoria": None, "aliado_internacional_con_aporte": None,
                 "fuente": []}
    if alliance is not None:
        out["fuente"].append(a_src)
        amount = _number(alliance.get("monto_sgr_solicitado"))
        if amount is not None:
            out["monto_sgr"] = {"valor": amount, "fuente": f"{a_src} (monto_sgr_solicitado)"}
        out["duracion_meses"] = alliance.get("duracion_meses")
        entities = _entities(alliance)
        proponent = next((e for e in entities if e.get("proponente") is True), None)
        if proponent is not None:
            member = _member(proponent, f"{a_src} ({proponent.get('id')})")
            for key in ("contrapartida_especie", "contrapartida_efectivo"):
                if member[key] is None:
                    del member[key]  # juez_sgr counts the proponent only for the fields it declares
            member.update({"domicilio_en_region": proponent.get("domicilio_en_region"),
                           "tipo_diverso": proponent.get("tipo_diverso")})
            out["proponente"] = member
        out["aliados"] = [_member(e, f"{a_src} ({e.get('id')})") for e in entities if e is not proponent]
        projects = _trajectory_projects(alliance)
        out["trayectoria"] = {"proyectos_adicionales": len(projects),
                              "proyectos_sgr_o_elegibles": sum(1 for p in projects if p["sgr"]),
                              "fuente": f"{a_src} (entidades[].trayectoria, cada proyecto una vez)"}
        international = [e for e in entities if e.get("tipo") == "internacional"]
        amounts = [_number(e.get(k)) for e in international for k in ("aporte_especie", "aporte_efectivo")]
        if any(a is not None and a > 0 for a in amounts):
            out["aliado_internacional_con_aporte"] = True
        elif not international or all(a is not None for a in amounts):
            out["aliado_internacional_con_aporte"] = False
    if territory is not None:
        out["fuente"].append(t_src)
        out["departamentos_ejecucion"] = [{"nombre": _text(d.get("nombre")), "fuente": f"{t_src} (departamentos)"}
                                          for d in _list(territory.get("departamentos"))
                                          if isinstance(d, dict) and _text(d.get("nombre"))]
    return out


def _rubric(run: Path):
    """(rubric, origin) or (None, note): the copy in the run, else the TdR detection of juez_sgr."""
    juez = _sibling("juez_sgr")
    try:
        rubric, origin, _ = juez.resolve_rubric(run, None)
    except juez.JuezError as exc:
        return None, f"Sin rúbrica para la vista previa: {exc}", juez
    return rubric, origin, juez


def puntaje_info(run_root: Path) -> dict:
    """{rubrica, origen, nota, subcriterios}: the counted subcriteria scored with juez_sgr.compute_conteo."""
    run = Path(run_root)
    rubric, origin, juez = _rubric(run)
    if rubric is None:
        return {"rubrica": None, "origen": None, "nota": origin, "subcriterios": []}
    facts = datos(run)
    rows = []
    for _, sub in juez.iter_subcriteria(rubric):
        if sub.get("modo") != "conteo":
            continue
        result = juez.compute_conteo(sub, facts)
        rows.append({"subcriterio": sub["id"], "nombre": sub.get("nombre"), "puntaje": result["puntaje"],
                     "max": sub["max"], "incompleto": result["incompleto"], "calculo": result["calculo"]})
    return {"rubrica": rubric.get("id"), "origen": origin, "nota": None, "subcriterios": rows}


def puntaje(run_root: Path) -> list[dict]:
    return puntaje_info(run_root)["subcriterios"]


# --- Render ---------------------------------------------------------------

def _escape(text) -> str:
    return _sibling("cadena_valor_sgr").escape(text)


def _money(value) -> str:
    number = _number(value)
    return "Por definir" if number is None else r"\$\," + f"{round(number):,}".replace(",", ".")


def _governance_text(value) -> str:
    if isinstance(value, list):
        return "; ".join(_text(v) for v in value if _text(v))
    return _text(value) if isinstance(value, str) else ""


def _heading_mode(run: Path, stem: str) -> tuple[str, str | None]:
    """("section", TdR title|None) when the section opens its TdR chapter or no TdR structure
    applies; ("sub", None) when another file of the chapter opens it (ensamblar_main placement)."""
    structure, _ = _read_json(run / STRUCTURE_FILE)
    if not isinstance(structure, dict):
        return "section", None
    assembler = _sibling("ensamblar_main")
    try:
        assembler.validate(structure)
    except assembler.InputError:
        return "section", None
    for chapter in assembler.placed_chapters(structure, "sgr"):
        files = [f for f in chapter["archivos"] if not f.startswith("diag_")]
        if stem in files:
            return ("section", chapter.get("titulo")) if files[0] == stem else ("sub", None)
    return "section", None


def _open(run: Path, stem: str, default_title: str, label: str, source: str) -> list[str]:
    mode, title = _heading_mode(run, stem)
    lines = [
        GENERATED_HEADER,
        f"% Fuente: {source}. No se edita a mano: se regenera con",
        "% python3 scripts/alianza_territorio_sgr.py render <RUN_ROOT>.",
    ]
    if mode == "section":
        lines += [rf"\section{{{_escape(title or default_title)}}}", rf"\label{{sec:{label}}}"]
    return lines


def _table(spec: str, header: list[str], rows: list[list[str]], caption: str, label: str) -> list[str]:
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
    lines += [" & ".join(cells) + r" \\" for cells in rows]
    lines += [r"\end{xltabular}", "}"]
    return lines


def _col(width: str) -> str:
    return rf">{{\raggedright\arraybackslash}}p{{{width}\textwidth}}"


_X = r">{\raggedright\arraybackslash}X"


def _join(values, empty: str = "Por definir") -> str:
    items = [_escape(v) for v in _list(values) if _text(v)]
    return ", ".join(items) if items else empty


def render_identification(run: Path, alliance: dict, territory: dict) -> str:
    lines = _open(run, "26_identificacion", "Identificación del proyecto", "identificacion",
                  f"{ALLIANCE_FILE.as_posix()} y {TERRITORY_FILE.as_posix()}")
    entities = _entities(alliance)
    lines += ["", r"\subsection{Entidades de la alianza}"]
    duration = alliance.get("duracion_meses")
    if duration is not None:
        lines += ["", f"Duración del proyecto: {_escape(duration)} meses."]
    rows = []
    for e in entities:
        name = _escape(e.get("nombre")) + (" (proponente)" if e.get("proponente") is True else "")
        rows.append([name, _escape(e.get("nit")) if _text(e.get("nit")) else "Por definir",
                     f"{_escape(ENTITY_TYPES.get(e.get('tipo'), e.get('tipo')))}. {_escape(e.get('rol'))}",
                     _escape(e.get("departamento")) if _text(e.get("departamento")) else "No aplica"])
    lines += _table(f"{_col('0.28')} {_col('0.13')} {_X} {_col('0.15')}",
                    ["Entidad", "NIT", "Tipo de entidad y rol en la alianza", "Departamento"], rows,
                    "Entidades que conforman la alianza.", "identificacion_entidades")
    lines += ["", r"\subsection{Localización}"]
    if _text(territory.get("region_sgr")):
        lines += ["", f"Región SGR: {_escape(territory.get('region_sgr'))}."]
    rows = [[_escape(d.get("nombre")), _join(d.get("municipios"))]
            for d in _list(territory.get("departamentos")) if isinstance(d, dict)]
    lines += _table(f"{_col('0.28')} {_X}", ["Departamento", "Municipios"], rows,
                    "Departamentos y municipios de ejecución.", "identificacion_localizacion")
    lines += ["", r"\subsection{Demandas territoriales}"]
    rows = [[_escape(d.get("codigo")), f"«{_escape(d.get('texto'))}»", _escape(d.get("departamento"))]
            for d in _list(territory.get("demandas")) if isinstance(d, dict)]
    lines += _table(f"{_col('0.14')} {_X} {_col('0.18')}", ["Código", "Demanda territorial", "Departamento"], rows,
                    "Demandas territoriales que atiende el proyecto.", "identificacion_demandas")
    groups = [(e, g) for e in entities for g in _list(e.get("grupos")) if isinstance(g, dict)]
    if groups:
        lines += ["", r"\subsection{Grupos de investigación}"]
        rows = []
        for e, g in groups:
            code = " ".join(_escape(v) for v in (g.get("codigo_gruplac"), g.get("clasificacion")) if _text(v))
            rows.append([_escape(g.get("nombre")), _escape(e.get("nombre")), code or "Por definir",
                         _join(g.get("lineas"))])
        lines += _table(f"{_col('0.26')} {_col('0.22')} {_col('0.16')} {_X}",
                        ["Nombre del grupo", "Entidad a la que pertenece", "Código GrupLAC y clasificación",
                         "Líneas de investigación"], rows,
                        "Grupos de investigación vinculados al proyecto.", "identificacion_grupos")
    return "\n".join(lines + [""])


def render_demands(run: Path, territory: dict) -> str:
    lines = _open(run, "27_demandas_territoriales", "Articulación del proyecto con las demandas territoriales",
                  "demandas_territoriales", TERRITORY_FILE.as_posix())
    rows = []
    for d in _list(territory.get("demandas")):
        if not isinstance(d, dict):
            continue
        links = [f"{label}: {_join(d.get(key), 'por vincular')}." for key, label in (
            ("objetivos", "Objetivos"), ("actividades", "Actividades"), ("productos", "Productos"))]
        rows.append([
            rf"\textbf{{{_escape(d.get('codigo'))}}}\newline {_escape(d.get('departamento'))}",
            rf"«{_escape(d.get('texto'))}»\newline Fuente: {_escape(d.get('fuente'))}",
            (_escape(d.get("articulacion")) or "Por redactar") + r"\newline " + " ".join(links),
        ])
    lines += _table(f"{_col('0.16')} {_X} {_X}",
                    ["Demanda territorial", "Descripción", "Articulación y contribución del proyecto"], rows,
                    "Articulación del proyecto con las demandas territoriales.", "demandas_territoriales")
    lines += ["", r"\subsection{Configuración regional: departamentos, municipios y actores}"]
    order = [_text(d.get("nombre")) for d in _list(territory.get("departamentos")) if isinstance(d, dict)]
    towns = {_key(d.get("nombre")): d.get("municipios") for d in _list(territory.get("departamentos"))
             if isinstance(d, dict)}
    actors = [a for a in _list(territory.get("configuracion_regional")) if isinstance(a, dict)]
    known = {_key(n) for n in order}
    order += sorted({_text(a.get("departamento")) for a in actors if _key(a.get("departamento")) not in known})
    rows = []
    for department in order:
        first = True
        for actor in (a for a in actors if _key(a.get("departamento")) == _key(department)):
            cell = ""
            if first:
                cell = _escape(department) or "Sin departamento"
                if _list(towns.get(_key(department))):
                    cell += rf"\newline Municipios: {_join(towns[_key(department)])}"
            rows.append([cell, _escape(actor.get("actor")), _escape(actor.get("pertinencia"))])
            first = False
    lines += _table(f"{_col('0.2')} {_col('0.25')} {_X}",
                    ["Departamento", "Actor", "Pertinencia frente a los objetivos y las demandas territoriales"],
                    rows, "Configuración regional: actores por departamento y su pertinencia.",
                    "configuracion_regional")
    return "\n".join(lines + [""])


def render_matrix(run: Path, alliance: dict) -> str:
    lines = _open(run, "28_matriz_responsabilidades", "Matriz de responsabilidades y gobernanza",
                  "matriz_responsabilidades", ALLIANCE_FILE.as_posix())
    lines += ["", r"\subsection{Matriz de responsabilidades de las entidades participantes que conforman la alianza}"]
    rows = []
    totals = {"aporte_especie": 0, "aporte_efectivo": 0}
    for e in _entities(alliance):
        duties = [f"- {_escape(r)}" for r in _list(e.get("responsabilidades")) if _text(r)]
        if _list(e.get("actividades")):
            duties.append(f"Actividades: {_join(e.get('actividades'))}")
        for key in totals:
            totals[key] += _number(e.get(key)) or 0
        position = e.get("posicion")
        rows.append([
            _escape(e.get("nombre")),
            _escape(ENTITY_TYPES.get(e.get("tipo"), e.get("tipo"))),
            position.capitalize() if position in POSITIONS else "Por definir",
            _escape(e.get("rol")),
            r"\newline ".join(duties) or "Por definir",
            rf"Especie: {_money(e.get('aporte_especie'))}\newline Efectivo: {_money(e.get('aporte_efectivo'))}",
        ])
    rows.append([r"\multicolumn{5}{r}{\textbf{Total}}",
                 rf"\textbf{{Especie: {_money(totals['aporte_especie'])}\newline "
                 rf"Efectivo: {_money(totals['aporte_efectivo'])}}}"])
    lines += _table(f"{_col('0.15')} {_col('0.12')} {_col('0.1')} {_col('0.13')} {_X} {_col('0.15')}",
                    ["Entidad", "Tipo de aliado", "Posición", "Rol", "Responsabilidades u obligaciones",
                     "Aportes (especie / efectivo)"], rows,
                    "Matriz de responsabilidades de las entidades de la alianza.", "matriz_responsabilidades")
    governance = alliance.get("gobernanza")
    if isinstance(governance, dict) and any(_governance_text(governance.get(k)) for k, _ in GOVERNANCE):
        lines += ["", r"\subsection{Modelo de gobernanza}"]
        rows = [[label, _escape(_governance_text(governance.get(key))) or "Por definir"] for key, label in GOVERNANCE]
        lines += _table(f"{_col('0.22')} {_X}", ["Componente", "Descripción"], rows,
                        "Modelo de gobernanza de la alianza.", "gobernanza")
    return "\n".join(lines + [""])


def render_sections(run_root: Path) -> list[Path]:
    """Write the three rendered sections; refuses while there are error findings."""
    run = Path(run_root)
    for rel in (ALLIANCE_FILE, TERRITORY_FILE):
        if not (run / rel).is_file():
            raise InputError(f"no existe {rel.as_posix()}: la unidad «Alianza y territorio» lo escribe")
    errors = [f for f in check_findings(run) if f["severity"] == "error"]
    if errors:
        raise RenderRefused(errors)
    alliance, _ = _read_json(run / ALLIANCE_FILE)
    territory, _ = _read_json(run / TERRITORY_FILE)
    texts = {
        "26_identificacion": render_identification(run, alliance, territory),
        "27_demandas_territoriales": render_demands(run, territory),
        "28_matriz_responsabilidades": render_matrix(run, alliance),
    }
    out_dir = run / SECTIONS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for stem, text in texts.items():
        path = out_dir / f"{stem}.tex"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


# --- CLI ------------------------------------------------------------------

def _print_findings(found: list[dict], stream) -> None:
    for f in found:
        print(f"[{f['severity'].upper()}] {f['code']} [{f['node']}] {f['message']}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("check", "validate alianza.json and territorio.json"),
                       ("render", "write sections 26, 27 and 28"),
                       ("puntaje", "preview the counted rubric subcriteria"),
                       ("datos", "partial datos_sgr facts")):
        p = sub.add_parser(name, help=text)
        p.add_argument("run_root", type=Path)
        if name != "render":
            p.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)
    run = args.run_root.resolve()

    if args.command == "render":
        try:
            for path in render_sections(run):
                print(f"SECCION: {path}")
        except RenderRefused as exc:
            print("error: alianza.json o territorio.json tienen hallazgos de error; no se generan las secciones.",
                  file=sys.stderr)
            _print_findings(exc.errors, sys.stderr)
            return 1
        except InputError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.command == "puntaje":
        info = puntaje_info(run)
        if info["nota"]:
            print(info["nota"], file=sys.stderr)
        if args.json:
            print(json.dumps(info["subcriterios"], ensure_ascii=False, indent=2))
        else:
            for row in info["subcriterios"]:
                flag = " (incompleto)" if row["incompleto"] else ""
                print(f"{row['subcriterio']} {row['nombre']}: {row['puntaje']}/{row['max']}{flag}. {row['calculo']}")
        return 0

    if args.command == "datos":
        print(json.dumps(datos(run), ensure_ascii=False, indent=2))
        return 0

    if not (run / ALLIANCE_FILE).is_file() and not (run / TERRITORY_FILE).is_file():
        print(f"error: no existen {ALLIANCE_FILE.as_posix()} ni {TERRITORY_FILE.as_posix()}", file=sys.stderr)
        return 2
    found = check_findings(run)
    errors = sum(1 for f in found if f["severity"] == "error")
    if args.json:
        print(json.dumps({"findings": found}, ensure_ascii=False, indent=2))
    else:
        _print_findings(found, sys.stdout)
        print(f"alianza_territorio: {errors} errores, {len(found) - errors} avisos")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
