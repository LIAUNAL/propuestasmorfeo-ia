#!/usr/bin/env python3
"""SGR TRL route and transversal components as data: check, render and judge facts (flujo SGR only).

`artefactos/sgr/componentes.json` (schema `morfeo.componentes-sgr/v1`) holds the
TRL route and its verification and the transversal components the TdR scores:
transfer, social appropriation of knowledge (ASC), social and environmental
sustainability, post-project use and operation, and differential measures.

    {schema,
     trl:{introduccion, tipologia:"A"|"B"|null, entrada:int|null, salida:int|null, evidencia_entrada:[str],
          ruta:[{hito, mes, trl, actividades:["1.1.1"], evidencia}],
          verificacion:{escenario, responsables:["E1"], criterios_aceptacion:[str], evidencias:[str],
                        actor_usuario:"E3"|null}},
     transferencia:{introduccion, resultados:[{resultado, usuarios:[str], proteccion_pi|null}],
          ruta:[{etapa, mecanismo, barreras, acciones}], actividades:["1.1.1"], continuidad},
     asc:{introduccion, actores:[{grupo, relacion_problematica, saberes, rol_momento, incidencia}],
          ruta:[{elemento:"identificacion_problema"|"vinculacion_actores"|"diseno"|"planeacion"|"ejecucion"
                          |"seguimiento"|"resultados_sostenibilidad",
                 meses, que_se_hace, actividades:["1.1.1"]}],
          productos:[{producto, descripcion, medio_verificacion, mes, actividad:"1.1.1"}]},
     sostenibilidad:{introduccion, ods:[{ods, contribucion, productos:[str]}],
          actores:[{actor, funciones, compromiso}], ambiental:[{actividad, medio, efecto, manejo}]},
     uso_posterior:{introduccion, bienes:[{bien, valor_sgr, operador:"E1", financiacion, mantenimiento}],
          adopcion:[{actor:"E3", resultado, condiciones}]},
     diferencial:{introduccion, barreras:[{barrera, poblacion, medida, actividades:["1.1.1"], indicador, meta,
          evidencia}], justificacion_sin_barreras|null}}

Each `introduccion` is agent-written prose (third person) rendered before the
component's tables. `meses` of an ASC route element is a list of month
numbers or a free text.

Commands:
  check RUN_ROOT [--json]
      Findings with check_run's shape {severity, code, message, node}, codes
      prefixed `componentes-`; a missing file is an error here.
  render RUN_ROOT
      Write redaccion/sections/31_trl.tex (Anexo 2 caps. 14.1 and 14.2),
      32_sostenibilidad.tex (cap. 16), 33_uso_posterior.tex (cap. 17.1),
      34_transferencia.tex (cap. 18), 35_medidas_diferenciales.tex (cap. 21.1)
      and 18_apropiacion_social.tex (cap. 19) deterministically. SGR runs
      only (a base run's §18 is never touched); refuses while there are error
      findings.
  datos RUN_ROOT [--json]
      {trl:{tipologia, entrada, salida, fuente}|null, transferencia_valor|null,
      fuente}: the facts the judge copies into datos_sgr.json.

Exit codes: 0 ok, 1 error findings (check, render), 2 bad input.
Standard library only. The value chain comes from
artefactos/sgr/cadena_valor.json, the entities from artefactos/sgr/alianza.json,
the budget from presupuesto_sgr.py, the LaTeX escaping from cadena_valor_sgr.py,
the flow from check_run.py, the TdR chapters from ensamblar_main.py and the
call's rubric from juez_sgr.py (all in this folder, imported defensively).
check_run imports `findings`; the dashboard imports `findings` and `datos`.
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import re
import sys
from pathlib import Path

SCHEMA = "morfeo.componentes-sgr/v1"
COMPONENTS_FILE = Path("artefactos") / "sgr" / "componentes.json"
CHAIN_FILE = Path("artefactos") / "sgr" / "cadena_valor.json"
ALLIANCE_FILE = Path("artefactos") / "sgr" / "alianza.json"
BUDGET_FILE = Path("artefactos") / "sgr" / "presupuesto.json"
STRUCTURE_FILE = Path("artefactos") / "estructura_tdr.json"
SECTIONS_DIR = Path("redaccion") / "sections"
GENERATED_HEADER = "% GENERADO por scripts/componentes_sgr.py"
HERE = Path(__file__).resolve().parent

BLOCKS = ("trl", "transferencia", "asc", "sostenibilidad", "uso_posterior", "diferencial")
TIPOLOGIAS = ("A", "B")
ASC_ELEMENTS = {
    "identificacion_problema": "Identificación del problema",
    "vinculacion_actores": "Vinculación de actores",
    "diseno": "Diseño",
    "planeacion": "Planeación",
    "ejecucion": "Ejecución",
    "seguimiento": "Seguimiento",
    "resultados_sostenibilidad": "Resultados y sostenibilidad",
}
TRANSFER_MIN_PCT = 1.0
# An ASC activity whose name reads as one-way communication (TdR 6.1: «no se limite a actividades
# aisladas de divulgación»).
DISSEMINATION_RE = re.compile(
    r"\b(socializ\w*|divulg\w*|difund\w*|difusi[óo]n|publicar|publicaci[óo]n(es)?|sensibiliz\w*|comunicar"
    r"|dar\s+a\s+conocer|presentar\s+los\s+resultados)\b", re.I)

STEMS = ("31_trl", "32_sostenibilidad", "33_uso_posterior", "34_transferencia", "35_medidas_diferenciales")
ASC_STEM = "18_apropiacion_social"


class InputError(Exception):
    pass


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
    spec = importlib.util.spec_from_file_location(f"_componentes_{name}", path)
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


def _int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _text(value) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _dicts(value) -> list[dict]:
    return [v for v in _list(value) if isinstance(v, dict)]


def _texts(value) -> list[str]:
    return [_text(v) for v in _list(value) if _text(v)]


def _codes(value) -> list[str]:
    out: list[str] = []
    for code in _texts(value):
        if code not in out:
            out.append(code)
    return out


def _block(data: dict, key: str) -> dict:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


# --- Context: value chain, alliance, budget ---------------------------------------

def _chain_index(chain) -> dict | None:
    """{code: {nombre, mes_inicio, mes_fin, producto, objetivo}} of the value chain, or None without it."""
    if not isinstance(chain, dict):
        return None
    index: dict[str, dict] = {}
    for objective in _dicts(chain.get("objetivos")):
        for product in _dicts(objective.get("productos")):
            for activity in _dicts(product.get("actividades")):
                code = _text(activity.get("codigo"))
                if code:
                    index[code] = {"actividad": activity, "producto": product, "objetivo": objective}
    return index


def _entities(alliance) -> dict[str, dict] | None:
    if not isinstance(alliance, dict):
        return None
    return {_text(e.get("id")): e for e in _dicts(alliance.get("entidades")) if _text(e.get("id"))}


def _duration(chain, alliance, budget):
    for source in (chain, alliance, budget):
        if isinstance(source, dict) and _int(source.get("duracion_meses")) and source["duracion_meses"] > 0:
            return source["duracion_meses"]
    return None


def _budget_summary(run: Path):
    """presupuesto_sgr.resumen(run), or None when the module or the budget is unavailable."""
    try:
        module = _sibling("presupuesto_sgr")
        return module.resumen(run) if module is not None else None
    except Exception:  # the budget is optional context: its own checks report its problems
        return None


def _budget_transfer_value(run: Path):
    try:
        module = _sibling("presupuesto_sgr")
        return module.datos(run).get("transferencia_valor") if module is not None else None
    except Exception:
        return None


def _rubric_id(run: Path):
    """id of the call's rubric (juez_sgr.resolve_rubric), or None when none can be resolved."""
    juez = _sibling("juez_sgr")
    if juez is None:
        return None
    try:
        rubric, _, _ = juez.resolve_rubric(run, None)
    except juez.JuezError:
        return None
    return rubric.get("id") if isinstance(rubric, dict) else None


def _load(run: Path) -> dict:
    out: dict = {"errores": []}
    data, error = _read_json(run / COMPONENTS_FILE)
    if error:
        out["errores"].append(_finding("error", "componentes-json-invalido", "componentes",
                                       f"{COMPONENTS_FILE.as_posix()} no es JSON válido: {error}"))
    out["componentes"] = data
    out["cadena"], _ = _read_json(run / CHAIN_FILE)
    out["alianza"], _ = _read_json(run / ALLIANCE_FILE)
    out["presupuesto"], _ = _read_json(run / BUDGET_FILE)
    return out


# --- Check ----------------------------------------------------------------------

class _Rules:
    """The rules of componentes.json (odd/tasks/sgr-trl-componentes.md, Contracts)."""

    def __init__(self, run: Path, data: dict, chain, alliance, budget) -> None:
        self.run = run
        self.data = data
        self.chain = _chain_index(chain)
        self.entities = _entities(alliance)
        self.budget = budget if isinstance(budget, dict) else None
        self.duration = _duration(chain, alliance, budget)
        self.out: list[dict] = []

    def add(self, severity: str, code: str, node: str, message: str) -> None:
        self.out.append(_finding(severity, code, node, message))

    def activities(self, node: str, codes) -> None:
        if self.chain is None:
            return
        unknown = [c for c in _codes(codes) if c not in self.chain]
        if unknown:
            self.add("error", "componentes-actividad-desconocida", node,
                     f"{node} cita actividades que no están en la cadena de valor: {', '.join(unknown)}.")

    def entity(self, node: str, eid) -> None:
        if self.entities is None or not _text(eid):
            return
        if _text(eid) not in self.entities:
            self.add("error", "componentes-entidad-desconocida", node,
                     f"{node} cita la entidad «{eid}», que no está en {ALLIANCE_FILE.as_posix()}.")

    def month(self, node: str, value) -> None:
        month = _int(value)
        if month is None or month < 1 or (self.duration is not None and month > self.duration):
            limit = f"entre 1 y {self.duration}" if self.duration is not None else "un entero mayor que 0"
            self.add("error", "componentes-mes-fuera", node,
                     f"{node} tiene el mes «{value}»; debe ser {limit} (duración del proyecto).")

    def run_all(self) -> list[dict]:
        if self.chain is None:
            self.add("warning", "componentes-cadena-faltante", "componentes",
                     f"No se encontró {CHAIN_FILE.as_posix()}: no se cotejan los códigos de actividad.")
        if self.entities is None:
            self.add("warning", "componentes-alianza-faltante", "componentes",
                     f"No se encontró {ALLIANCE_FILE.as_posix()}: no se cotejan las entidades.")
        checks = {"trl": self.trl, "transferencia": self.transfer, "asc": self.asc,
                  "sostenibilidad": self.sustainability, "uso_posterior": self.post_use,
                  "diferencial": self.differential}
        for key in BLOCKS:
            if not isinstance(self.data.get(key), dict):
                self.add("error", "componentes-bloque-faltante", key,
                         f"componentes.json no tiene el bloque «{key}».")
                continue
            checks[key](self.data[key])
        return self.out

    # TRL ---------------------------------------------------------------------
    def trl(self, trl: dict) -> None:
        tipologia = trl.get("tipologia")
        if tipologia not in TIPOLOGIAS:
            self.add("error", "componentes-trl-tipologia", "trl",
                     f"La tipología declarada es «{tipologia}»; debe ser A o B (Tabla 4 del TdR).")
        entry, exit_ = _int(trl.get("entrada")), _int(trl.get("salida"))
        for label, value in (("entrada", entry), ("salida", exit_)):
            if value is None or not 1 <= value <= 9:
                self.add("error", "componentes-trl-nivel", "trl",
                         f"El TRL de {label} es «{trl.get(label)}»; debe ser un entero de 1 a 9.")
        valid = entry is not None and exit_ is not None and 1 <= entry <= 9 and 1 <= exit_ <= 9
        if valid and exit_ <= entry:
            self.add("error", "componentes-trl-salida-no-mayor", "trl",
                     f"El TRL de salida ({exit_}) debe ser mayor que el de entrada ({entry}).")
        route = _dicts(trl.get("ruta"))
        levels = []
        for n, milestone in enumerate(route, start=1):
            node = f"trl.ruta[{n}]"
            self.month(node, milestone.get("mes"))
            self.activities(node, milestone.get("actividades"))
            if _int(milestone.get("trl")) is not None:
                levels.append(milestone["trl"])
        if exit_ is not None and (not levels or max(levels) < exit_):
            reached = f"llega a TRL {max(levels)}" if levels else "no tiene hitos con TRL"
            self.add("error", "componentes-trl-ruta-incompleta", "trl.ruta",
                     f"La ruta de maduración {reached}; sus hitos deben alcanzar el TRL de salida ({exit_}).")
        check = _block(trl, "verificacion")
        missing = [label for key, label in (("escenario", "escenario"), ("responsables", "responsables"),
                                            ("criterios_aceptacion", "criterios de aceptación"),
                                            ("evidencias", "evidencias"))
                   if not (_texts(check.get(key)) if isinstance(check.get(key), list) else _text(check.get(key)))]
        if missing:
            self.add("error", "componentes-trl-verificacion-incompleta", "trl.verificacion",
                     f"Al plan de verificación del TRL de salida le falta: {', '.join(missing)} (rúbrica 1.3).")
        for eid in _texts(check.get("responsables")):
            self.entity("trl.verificacion", eid)
        actor = check.get("actor_usuario")
        self.entity("trl.verificacion", actor)
        if tipologia == "B" and not _text(actor):
            self.add("error", "componentes-trl-actor-usuario", "trl.verificacion",
                     "En la tipología B la verificación se hace en entorno operativo real con el actor usuario "
                     "que adoptará la solución: falta actor_usuario.")
        self.trl_range(trl, tipologia, entry, exit_)

    def trl_range(self, trl: dict, tipologia, entry, exit_) -> None:
        rubric = _rubric_id(self.run)
        if rubric == "conv54":
            if tipologia == "A":
                if exit_ is not None and exit_ > 6:
                    self.add("error", "componentes-trl-rango-tdr", "trl",
                             f"En la Convocatoria 54 la tipología A llega hasta TRL 6; el TRL de salida es {exit_}.")
                if not _texts(trl.get("evidencia_entrada")):
                    self.add("error", "componentes-trl-evidencia-entrada", "trl",
                             "En la Convocatoria 54 el TRL de entrada de la tipología A se respalda con evidencia "
                             "(planteamiento científico, línea base o resultados previos): evidencia_entrada está "
                             "vacía (rúbrica 1.3).")
            elif tipologia == "B":
                if entry is not None and entry < 4:
                    self.add("error", "componentes-trl-rango-tdr", "trl",
                             f"En la Convocatoria 54 la tipología B entra como mínimo en TRL 4; el TRL de entrada "
                             f"es {entry}.")
                if exit_ is not None and not 7 <= exit_ <= 9:
                    self.add("error", "componentes-trl-rango-tdr", "trl",
                             f"En la Convocatoria 54 la tipología B sale entre TRL 7 y 9; el TRL de salida es "
                             f"{exit_}.")
        elif rubric == "conv56" and exit_ is not None and exit_ < 7:
            self.add("warning", "componentes-trl-rango-tdr", "trl",
                     f"En la Convocatoria 56 un TRL de salida menor que 7 vale 0 puntos en el criterio 3.1; el "
                     f"TRL de salida es {exit_}.")

    # Transfer ----------------------------------------------------------------
    def transfer(self, block: dict) -> None:
        if not any(_text(r.get("resultado")) and _texts(r.get("usuarios")) for r in _dicts(block.get("resultados"))):
            self.add("error", "componentes-transferencia-sin-resultados", "transferencia.resultados",
                     "La transferencia necesita al menos un resultado con sus usuarios o receptores (numeral 18.2).")
        if not any(_text(s.get("barreras")) and _text(s.get("acciones")) for s in _dicts(block.get("ruta"))):
            self.add("error", "componentes-transferencia-sin-ruta", "transferencia.ruta",
                     "La ruta de transferencia necesita al menos una etapa con sus barreras y acciones "
                     "(numeral 18.3).")
        codes = _codes(block.get("actividades"))
        if not codes:
            self.add("error", "componentes-transferencia-sin-actividades", "transferencia.actividades",
                     "La transferencia no cita actividades de la cadena de valor (numeral 18.4).")
        self.activities("transferencia.actividades", codes)
        if self.budget is None:
            return
        summary = _budget_summary(self.run)
        pct = summary.get("transferencia_pct") if isinstance(summary, dict) else None
        if _number(pct) is not None and pct < TRANSFER_MIN_PCT:
            self.add("warning", "componentes-transferencia-presupuesto-bajo", "transferencia",
                     f"El componente de transferencia suma el {_plain_pct(pct)} del total SGR en presupuesto.json; "
                     f"el mínimo es {_plain_pct(TRANSFER_MIN_PCT)}.")
        tagged: list[str] = []
        for item in _dicts(self.budget.get("items")):
            if item.get("componente") == "transferencia":
                tagged += [c for c in _codes(item.get("actividades")) if c not in tagged]
        only_here = [c for c in codes if c not in tagged]
        only_budget = [c for c in tagged if c not in codes]
        if only_here or only_budget:
            parts = []
            if only_here:
                parts.append(f"sin ítems de transferencia en el presupuesto: {', '.join(only_here)}")
            if only_budget:
                parts.append(f"con ítems de transferencia pero fuera del componente: {', '.join(only_budget)}")
            self.add("warning", "componentes-transferencia-presupuesto-desalineado", "transferencia.actividades",
                     "Las actividades de transferencia no coinciden con los ítems de presupuesto.json con "
                     f"componente «transferencia»; {'; '.join(parts)}.")

    # ASC ---------------------------------------------------------------------
    def asc(self, block: dict) -> None:
        present: list[str] = []
        names: list[str] = []
        for n, step in enumerate(_dicts(block.get("ruta")), start=1):
            element = step.get("elemento")
            node = f"asc.ruta[{element if element in ASC_ELEMENTS else n}]"
            if element not in ASC_ELEMENTS:
                self.add("error", "componentes-asc-elemento-invalido", node,
                         f"El elemento «{element}» de la ruta ASC no es válido; los elementos son "
                         f"{', '.join(ASC_ELEMENTS)}.")
                continue
            present.append(element)
            months = step.get("meses")
            if isinstance(months, list):
                for month in months:
                    self.month(node, month)
            codes = _codes(step.get("actividades"))
            if not codes:
                self.add("error", "componentes-asc-elemento-sin-actividad", node,
                         f"El elemento «{ASC_ELEMENTS[element]}» de la ruta ASC no tiene actividades.")
            self.activities(node, codes)
            names += self.activity_names(codes)
        missing = [label for key, label in ASC_ELEMENTS.items() if key not in present]
        if missing:
            self.add("error", "componentes-asc-elemento-faltante", "asc.ruta",
                     "La ruta ASC debe cubrir los siete elementos del TdR (numeral 6.1); falta: "
                     f"{', '.join(label.lower() for label in missing)}.")
        products = _dicts(block.get("productos"))
        for n, product in enumerate(products, start=1):
            node = f"asc.productos[{n}]"
            if product.get("mes") is not None:
                self.month(node, product.get("mes"))
            self.activities(node, [product.get("actividad")] if _text(product.get("actividad")) else [])
            names += self.activity_names([product.get("actividad")])
        if not any(_text(p.get("producto")) and _text(p.get("medio_verificacion")) and _int(p.get("mes"))
                   for p in products):
            self.add("error", "componentes-asc-sin-productos", "asc.productos",
                     "La ASC necesita al menos un producto con su medio de verificación y su mes; sin productos "
                     "verificables la rúbrica 2.4 no da puntos.")
        if names and all(DISSEMINATION_RE.search(name) for name in names):
            self.add("warning", "componentes-asc-solo-divulgacion", "asc",
                     "Todas las actividades de la ASC se leen como divulgación o socialización; el TdR pide que "
                     "«no se limite a actividades aisladas de divulgación» (numeral 6.1).")

    def activity_names(self, codes) -> list[str]:
        if self.chain is None:
            return []
        return [_text(self.chain[c]["actividad"].get("nombre")) for c in _codes(codes) if c in self.chain]

    # Sustainability and post-project use ---------------------------------------
    def sustainability(self, block: dict) -> None:
        if not any(_text(o.get("ods")) and _texts(o.get("productos")) for o in _dicts(block.get("ods"))):
            self.add("error", "componentes-sostenibilidad-sin-ods", "sostenibilidad.ods",
                     "La sostenibilidad necesita al menos un ODS con los productos que respaldan la contribución.")
        if not any(_text(a.get("actor")) and _text(a.get("compromiso")) for a in _dicts(block.get("actores"))):
            self.add("error", "componentes-sostenibilidad-sin-actores", "sostenibilidad.actores",
                     "La sostenibilidad necesita al menos un actor con su compromiso (rúbrica 4.2).")

    def post_use(self, block: dict) -> None:
        for n, good in enumerate(_dicts(block.get("bienes")), start=1):
            node = f"uso_posterior.bienes[{n}]"
            value = good.get("valor_sgr")
            if value is not None and (_number(value) is None or value < 0):
                self.add("error", "componentes-valor-invalido", node,
                         f"El valor SGR del bien {n} no es un número mayor o igual que 0.")
                continue
            self.entity(node, good.get("operador"))
            if _number(value) and value > 0:
                missing = [label for key, label in (("operador", "entidad que lo opera"),
                                                    ("financiacion", "fuente de recursos"))
                           if not _text(good.get(key))]
                if missing:
                    self.add("error", "componentes-uso-bien-incompleto", node,
                             f"El bien «{_text(good.get('bien'))}» se compra con recursos SGR y le falta: "
                             f"{', '.join(missing)} (numeral 17.1, rúbrica 4.2).")
        adoptions = _dicts(block.get("adopcion"))
        for n, adoption in enumerate(adoptions, start=1):
            self.entity(f"uso_posterior.adopcion[{n}]", adoption.get("actor"))
        if self.entities is None:
            adopted = any(_text(a.get("actor")) for a in adoptions)
        else:
            adopted = any(self.entities.get(_text(a.get("actor")), {}).get("tipo") == "usuario_adoptante"
                          for a in adoptions)
        if not adopted:
            self.add("warning", "componentes-uso-sin-adopcion", "uso_posterior.adopcion",
                     "Ningún actor usuario o adoptante de la alianza asume un compromiso de adopción "
                     "(numeral 17.1, rúbrica 4.2).")

    # Differential measures -------------------------------------------------------
    def differential(self, block: dict) -> None:
        barriers = _dicts(block.get("barreras"))
        for n, barrier in enumerate(barriers, start=1):
            self.activities(f"diferencial.barreras[{n}]", barrier.get("actividades"))
        if not barriers and not _text(block.get("justificacion_sin_barreras")):
            self.add("error", "componentes-diferencial-vacio", "diferencial",
                     "Las medidas diferenciales necesitan barreras con su medida o la justificación de que no las "
                     "hay (rúbrica 4.4).")


def components_findings(data, run: Path, chain, alliance, budget) -> list[dict]:
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return [_finding("error", "componentes-esquema", "componentes", f"El archivo no declara el esquema {SCHEMA}.")]
    return _Rules(run, data, chain, alliance, budget).run_all()


def findings(run_root: Path) -> list[dict]:
    """Findings of componentes.json; [] when it does not exist."""
    run = Path(run_root)
    if not (run / COMPONENTS_FILE).is_file():
        return []
    data = _load(run)
    if data["errores"]:
        return data["errores"]
    return components_findings(data["componentes"], run, data["cadena"], data["alianza"], data["presupuesto"])


def check_findings(run_root: Path) -> list[dict]:
    """findings() plus an error when the file is missing (the CLI `check` and `render`)."""
    run = Path(run_root)
    if not (run / COMPONENTS_FILE).is_file():
        return [_finding("error", "componentes-archivo-faltante", "componentes",
                         f"No existe {COMPONENTS_FILE.as_posix()}.")]
    return findings(run)


# --- Judge facts ------------------------------------------------------------------

def datos(run_root: Path) -> dict:
    """{trl, transferencia_valor, fuente}: the TRL and transfer facts of datos_sgr."""
    run = Path(run_root)
    out: dict = {"trl": None, "transferencia_valor": None, "fuente": []}
    data, _ = _read_json(run / COMPONENTS_FILE)
    if isinstance(data, dict):
        source = COMPONENTS_FILE.as_posix()
        out["fuente"].append(source)
        trl = _block(data, "trl")
        out["trl"] = {"tipologia": trl.get("tipologia"), "entrada": trl.get("entrada"), "salida": trl.get("salida"),
                      "fuente": f"{source} (trl)"}
    if (run / BUDGET_FILE).is_file():
        value = _budget_transfer_value(run)
        if _number(value) is not None:
            out["transferencia_valor"] = value
            out["fuente"].append(BUDGET_FILE.as_posix())
    return out


# --- Render -------------------------------------------------------------------------

def _escape(text) -> str:
    return _sibling("cadena_valor_sgr").escape(text)


def _money(value) -> str:
    return r"\$\," + f"{round(value):,}".replace(",", ".")


def _plain_pct(value) -> str:
    return f"{value:.2f}".replace(".", ",") + " %"


def _heading_mode(run: Path, stem: str) -> tuple[str, str | None]:
    """("section", TdR title|None) when the file opens its TdR chapter or no structure applies;
    ("sub", None) when another file of the chapter opens it (ensamblar_main placement)."""
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


def _open(run: Path, stem: str, default_title: str, label: str, sources: str,
          sub_title: str | None = None) -> list[str]:
    """Header and heading. A section that opens its TdR chapter gets \\section{<title>}; a subsection
    stem (sub_title) placed inside another file's chapter gets only \\subsection{<sub_title>}."""
    mode, title = _heading_mode(run, stem)
    lines = [
        GENERATED_HEADER,
        f"% Fuente: {sources}. No se edita a mano: se regenera con",
        "% python3 scripts/componentes_sgr.py render <RUN_ROOT>.",
    ]
    if mode == "section":
        lines += [rf"\section{{{_escape(title or default_title)}}}", rf"\label{{sec:{label}}}"]
        if sub_title and title:
            lines += ["", rf"\subsection{{{sub_title}}}"]
    elif sub_title:
        lines += [rf"\subsection{{{sub_title}}}", rf"\label{{sec:{label}}}"]
    return lines


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


def _paragraph(text) -> list[str]:
    return ["", _escape(text)] if _text(text) else []


def _cell(value, empty: str = "Por definir") -> str:
    return _escape(value) if _text(value) else empty


def _items(values, empty: str = "Por definir") -> str:
    items = [_escape(v) for v in _texts(values)]
    return r"\newline ".join(items) if items else empty


class _Renderer:
    def __init__(self, run: Path, data: dict, chain, alliance) -> None:
        self.run = run
        self.data = data
        self.chain = _chain_index(chain) or {}
        self.entities = _entities(alliance) or {}
        self.alliance = alliance if isinstance(alliance, dict) else {}

    def block(self, key: str) -> dict:
        return _block(self.data, key)

    def activity(self, code) -> str:
        code = _text(code)
        info = self.chain.get(code)
        name = _text(info["actividad"].get("nombre")) if info else ""
        return _escape(f"{code} {name}" if name else code)

    def activities(self, codes) -> str:
        names = [self.activity(c) for c in _codes(codes)]
        return r"\newline ".join(names) if names else "Por definir"

    def entity(self, eid) -> str:
        entity = self.entities.get(_text(eid))
        return _escape(_text(entity.get("nombre")) if entity and _text(entity.get("nombre")) else eid)

    def entity_list(self, ids) -> str:
        names = [self.entity(e) for e in _texts(ids)]
        return r"\newline ".join(names) if names else "Por definir"

    def maybe_activity(self, value) -> str:
        """An activity code with its chain name, or the text as written."""
        return self.activity(value) if _text(value) in self.chain else _cell(value)

    # 31 --------------------------------------------------------------------------
    def trl(self) -> str:
        trl = self.block("trl")
        lines = _open(self.run, "31_trl", "Madurez tecnológica y verificación del TRL", "trl",
                      f"{COMPONENTS_FILE.as_posix()}, {CHAIN_FILE.as_posix()} y {ALLIANCE_FILE.as_posix()}")
        lines += ["", r"\subsection{Estado de desarrollo y madurez tecnológica de la solución}"]
        lines += _paragraph(trl.get("introduccion"))
        tipologia = trl.get("tipologia")
        rows = [[f"Tipología {_escape(tipologia)}" if _text(tipologia) else "Por definir",
                 f"TRL {_escape(trl.get('entrada'))}", _items(trl.get("evidencia_entrada")),
                 f"TRL {_escape(trl.get('salida'))}"]]
        lines += _table(f"{_col('0.14')} {_col('0.12')} {_X} {_col('0.14')}",
                        ["Tipología declarada", "TRL de entrada", "Evidencia del punto de partida",
                         "TRL de salida comprometido"], rows,
                        "Tipología declarada, TRL de entrada con su evidencia y TRL de salida.", "trl_entrada")
        rows = [[_cell(m.get("hito")), _cell(m.get("mes")), f"TRL {_escape(m.get('trl'))}",
                 self.activities(m.get("actividades")), _cell(m.get("evidencia"))]
                for m in _dicts(trl.get("ruta"))]
        lines += _table(f"{_col('0.2')} {_col('0.06', 'centering')} {_col('0.07', 'centering')} {_X} {_col('0.22')}",
                        ["Hito", "Mes", "TRL", "Actividades", "Evidencia"], rows,
                        "Ruta de maduración tecnológica: hitos verificables desde el TRL de entrada hasta el de salida.",
                        "trl_ruta")
        lines += ["", r"\subsection{Plan de verificación del TRL de salida}"]
        check = _block(trl, "verificacion")
        rows = [[_cell(check.get("escenario")), self.entity_list(check.get("responsables")),
                 _items(check.get("criterios_aceptacion")), _items(check.get("evidencias"))]]
        lines += _table(f"{_col('0.2')} {_col('0.18')} {_X} {_X}",
                        ["Escenario", "Responsables", "Criterios de aceptación", "Evidencias"], rows,
                        "Plan de verificación del TRL de salida.", "trl_verificacion")
        if _text(check.get("actor_usuario")):
            lines += ["", rf"\noindent Actor usuario que participa en la verificación: {self.entity(check['actor_usuario'])}."]
        return "\n".join(lines + [""])

    # 32 --------------------------------------------------------------------------
    def sustainability(self) -> str:
        block = self.block("sostenibilidad")
        lines = _open(self.run, "32_sostenibilidad", "Sostenibilidad social y ambiental del proyecto",
                      "sostenibilidad", f"{COMPONENTS_FILE.as_posix()} y {CHAIN_FILE.as_posix()}")
        lines += _paragraph(block.get("introduccion"))
        lines += ["", r"\subsection{Contribución a los Objetivos de Desarrollo Sostenible}"]
        rows = [[_cell(o.get("ods")), _cell(o.get("contribucion")), _items(o.get("productos"))]
                for o in _dicts(block.get("ods"))]
        lines += _table(f"{_col('0.2')} {_X} {_col('0.3')}",
                        ["ODS", "Contribución del proyecto", "Productos y resultados que la respaldan"], rows,
                        "Contribución del proyecto a los Objetivos de Desarrollo Sostenible.", "sostenibilidad_ods")
        lines += ["", r"\subsection{Estrategias de sostenibilidad y articulación de actores}"]
        rows = [[_cell(a.get("actor")), _cell(a.get("funciones")), _cell(a.get("compromiso"))]
                for a in _dicts(block.get("actores"))]
        lines += _table(f"{_col('0.22')} {_X} {_X}",
                        ["Actores", "Funciones en el proyecto", "Compromiso con la sostenibilidad"], rows,
                        "Funciones y compromisos de los actores con la sostenibilidad.", "sostenibilidad_actores")
        environmental = _dicts(block.get("ambiental"))
        if environmental:
            lines += ["", r"\subsection{Efectos ambientales y medidas de manejo}"]
            rows = [[self.maybe_activity(e.get("actividad")), _cell(e.get("medio")), _cell(e.get("efecto")),
                     _cell(e.get("manejo"))] for e in environmental]
            lines += _table(f"{_col('0.22')} {_col('0.14')} {_X} {_X}",
                            ["Actividad", "Medio", "Efecto", "Manejo"], rows,
                            "Efectos ambientales de las actividades y medidas de manejo.", "sostenibilidad_ambiental")
        return "\n".join(lines + [""])

    # 33 --------------------------------------------------------------------------
    def post_use(self) -> str:
        block = self.block("uso_posterior")
        sub = "Uso y operación posterior de los resultados"
        lines = _open(self.run, "33_uso_posterior", sub, "uso_posterior",
                      f"{COMPONENTS_FILE.as_posix()} y {ALLIANCE_FILE.as_posix()}", sub_title=sub)
        lines += _paragraph(block.get("introduccion"))
        goods = _dicts(block.get("bienes"))
        if goods:
            rows = [[_cell(g.get("bien")), _money(g["valor_sgr"]) if _number(g.get("valor_sgr")) is not None
                     else "Por definir", self.entity(g.get("operador")) if _text(g.get("operador")) else "Por definir",
                     _cell(g.get("mantenimiento")), _cell(g.get("financiacion"))] for g in goods]
            lines += _table(f"{_col('0.2')} {_col('0.13', 'raggedleft')} {_col('0.17')} {_X} {_col('0.18')}",
                            ["Bienes adquiridos con SGR", "Valor SGR", "Entidad responsable",
                             "Operación y mantenimiento posterior", "Fuente de recursos"], rows,
                            "Bienes adquiridos con recursos SGR: operación, mantenimiento y fuente de recursos.",
                            "uso_posterior_bienes")
        rows = [[self.entity(a.get("actor")) if _text(a.get("actor")) else "Por definir", _cell(a.get("resultado")),
                 _cell(a.get("condiciones"))] for a in _dicts(block.get("adopcion"))]
        lines += _table(f"{_col('0.22')} {_X} {_X}", ["Actor", "Resultado que adoptará", "Condiciones de adopción"],
                        rows, "Compromisos de adopción de los resultados.", "uso_posterior_adopcion")
        return "\n".join(lines + [""])

    # 34 --------------------------------------------------------------------------
    def transfer(self, summary) -> str:
        block = self.block("transferencia")
        lines = _open(self.run, "34_transferencia",
                      "Componente transversal de transferencia, adopción y valoración tecnológica del conocimiento",
                      "transferencia", f"{COMPONENTS_FILE.as_posix()}, {CHAIN_FILE.as_posix()}, "
                                       f"{ALLIANCE_FILE.as_posix()} y {BUDGET_FILE.as_posix()}")
        lines += ["", r"\subsection{Plan de transferencia, adopción y valoración tecnológica del conocimiento}"]
        lines += _paragraph(block.get("introduccion"))
        lines += ["", r"\subsection{Resultados, usuarios y oportunidades de transferencia}"]
        rows = [[_cell(r.get("resultado")), _items(r.get("usuarios")), _cell(r.get("proteccion_pi"), "No aplica")]
                for r in _dicts(block.get("resultados"))]
        lines += _table(f"{_X} {_col('0.3')} {_col('0.22')}", ["Resultado", "Usuarios", "Protección de PI"], rows,
                        "Resultados, usuarios y oportunidades de transferencia.", "transferencia_resultados")
        lines += ["", r"\subsection{Estrategia o ruta de transferencia, adopción y valoración tecnológica}"]
        rows = [[_cell(s.get("etapa")), _cell(s.get("mecanismo")), _cell(s.get("barreras")), _cell(s.get("acciones"))]
                for s in _dicts(block.get("ruta"))]
        lines += _table(f"{_col('0.15')} {_X} {_X} {_X}", ["Etapa", "Mecanismo", "Barreras", "Acciones"], rows,
                        "Ruta de transferencia, adopción y valoración tecnológica.", "transferencia_ruta")
        lines += ["", r"\subsection{Actividades, productos, indicadores y presupuesto}"]
        shares = summary.get("por_actividad") if isinstance(summary, dict) else None
        rows: list = []
        total = 0
        for code in _codes(block.get("actividades")):
            info = self.chain.get(code)
            activity = info["actividad"] if info else {}
            product = info["producto"] if info else {}
            objective = info["objetivo"] if info else {}
            result = " ".join(v for v in (_text(objective.get("id")), _text(objective.get("texto"))) if v)
            indicator = _text(product.get("indicador"))
            goal = " ".join(_text(product.get(k)) for k in ("meta", "unidad") if _text(product.get(k)))
            responsible = [self.entity(e.get("id")) for e in _dicts(self.alliance.get("entidades"))
                           if code in _codes(e.get("actividades"))]
            start, end = _int(activity.get("mes_inicio")), _int(activity.get("mes_fin"))
            period = ("Por definir" if start is None or end is None
                      else f"Mes {start}" if start == end else f"Meses {start} a {end}")
            share = shares.get(code) if isinstance(shares, dict) else None
            if _number(share) is not None:
                total += share
            rows.append([self.activity(code), _cell(result),
                         _escape(" ".join(v for v in (_text(product.get("codigo")), _text(product.get("nombre"))) if v))
                         or "Por definir",
                         (_escape(indicator) + (f" (meta: {_escape(goal)})" if goal else "")) if indicator
                         else "Por definir",
                         r"\newline ".join(responsible) or "Por definir", period,
                         _money(share) if _number(share) is not None else "Por definir"])
        if isinstance(shares, dict) and rows:
            rows += [r"\midrule", [r"\multicolumn{6}{r}{\textbf{Total}}", rf"\textbf{{{_money(total)}}}"]]
        lines += _table(f"{_col('0.16')} {_col('0.15')} {_col('0.14')} {_X} {_col('0.12')} {_col('0.08')} "
                        f"{_col('0.1', 'raggedleft')}",
                        ["Actividad", "Resultado", "Producto", "Indicador", "Responsable", "Periodo", "Presupuesto"],
                        rows, "Actividades, productos, indicadores y presupuesto del componente de transferencia.",
                        "transferencia_actividades")
        lines += ["", r"\subsection{Continuidad del proceso}"]
        lines += _paragraph(block.get("continuidad"))
        return "\n".join(lines + [""])

    # 35 --------------------------------------------------------------------------
    def differential(self) -> str:
        block = self.block("diferencial")
        sub = "Medidas diferenciales"
        lines = _open(self.run, "35_medidas_diferenciales", sub, "medidas_diferenciales",
                      f"{COMPONENTS_FILE.as_posix()} y {CHAIN_FILE.as_posix()}", sub_title=sub)
        lines += _paragraph(block.get("introduccion"))
        barriers = _dicts(block.get("barreras"))
        if barriers:
            rows = [[_cell(b.get("barrera")), _cell(b.get("poblacion")), _cell(b.get("medida")),
                     self.activities(b.get("actividades")), _cell(b.get("indicador")), _cell(b.get("meta")),
                     _cell(b.get("evidencia"))] for b in barriers]
            lines += _table(f"{_col('0.15')} {_col('0.12')} {_X} {_col('0.14')} {_col('0.12')} {_col('0.07')} "
                            f"{_col('0.12')}",
                            ["Barrera", "Población", "Medida", "Actividades", "Indicador", "Meta", "Evidencia"], rows,
                            "Medidas diferenciales: barrera, medida, actividades, indicador, meta y evidencia.",
                            "medidas_diferenciales")
        else:
            lines += _paragraph(block.get("justificacion_sin_barreras"))
        return "\n".join(lines + [""])

    # 18 --------------------------------------------------------------------------
    def asc(self) -> str:
        block = self.block("asc")
        lines = _open(self.run, ASC_STEM, "Componente transversal de apropiación social del conocimiento (ASC)",
                      "apropiacion_social", f"{COMPONENTS_FILE.as_posix()} y {CHAIN_FILE.as_posix()}")
        lines += _paragraph(block.get("introduccion"))
        lines += ["", r"\subsection{Estrategia de apropiación social del conocimiento}"]
        rows = [[_cell(a.get("grupo")), _cell(a.get("relacion_problematica")), _cell(a.get("saberes")),
                 _cell(a.get("rol_momento")), _cell(a.get("incidencia"))] for a in _dicts(block.get("actores"))]
        lines += _table(f"{_col('0.16')} {_X} {_X} {_X} {_X}",
                        ["Grupo y actores", "Relación con la problemática", "Saberes y capacidades",
                         "Rol y momento de participación", "Incidencia"], rows,
                        "Actores de la apropiación social del conocimiento: saberes, rol e incidencia.", "asc_actores")
        order = {key: n for n, key in enumerate(ASC_ELEMENTS)}
        steps = sorted((s for s in _dicts(block.get("ruta")) if s.get("elemento") in ASC_ELEMENTS),
                       key=lambda s: order[s["elemento"]])
        rows = [[ASC_ELEMENTS[s["elemento"]], _months(s.get("meses")), _cell(s.get("que_se_hace")),
                 self.activities(s.get("actividades"))] for s in steps]
        lines += _table(f"{_col('0.15')} {_col('0.1')} {_X} {_col('0.28')}",
                        ["Elemento", "Meses", "Qué se hace con los actores", "Actividades"], rows,
                        "Ruta de apropiación social del conocimiento por elemento del ciclo del proyecto.", "asc_ruta")
        rows = [[_cell(p.get("producto")), _cell(p.get("descripcion")), _cell(p.get("medio_verificacion")),
                 _cell(p.get("mes")), self.activity(p.get("actividad")) if _text(p.get("actividad")) else "Por definir"]
                for p in _dicts(block.get("productos"))]
        lines += _table(f"{_col('0.17')} {_X} {_col('0.2')} {_col('0.06', 'centering')} {_col('0.2')}",
                        ["Producto", "Descripción", "Medio de verificación", "Mes", "Actividad"], rows,
                        "Productos de la apropiación social del conocimiento.", "asc_productos")
        return "\n".join(lines + [""])


def _months(value) -> str:
    """«1 a 3, 6» for a list of months; the text as written otherwise."""
    if not isinstance(value, list):
        return _cell(value)
    months = sorted({m for m in value if _int(m) is not None})
    if not months:
        return "Por definir"
    runs: list[list[int]] = []
    for month in months:
        if runs and month == runs[-1][1] + 1:
            runs[-1][1] = month
        else:
            runs.append([month, month])
    return ", ".join(str(a) if a == b else f"{a} a {b}" for a, b in runs)


def _flujo(run: Path) -> str:
    module = _sibling("check_run")
    return module.detect_flujo(run) if module is not None else "base"


def render_sections(run_root: Path) -> list[Path]:
    """Write sections 31 to 35 and §18; refuses outside the SGR flow and while there are error findings."""
    run = Path(run_root)
    if _flujo(run) != "sgr":
        raise InputError("los componentes como datos son solo del flujo SGR; en el flujo base §18 se redacta a mano")
    if not (run / COMPONENTS_FILE).is_file():
        raise InputError(f"no existe {COMPONENTS_FILE.as_posix()}: la unidad «TRL y componentes transversales» "
                         "lo escribe")
    errors = [f for f in check_findings(run) if f["severity"] == "error"]
    if errors:
        raise RenderRefused(errors)
    data, _ = _read_json(run / COMPONENTS_FILE)
    chain, _ = _read_json(run / CHAIN_FILE)
    alliance, _ = _read_json(run / ALLIANCE_FILE)
    renderer = _Renderer(run, data, chain, alliance)
    summary = _budget_summary(run) if (run / BUDGET_FILE).is_file() else None
    texts = {
        "31_trl": renderer.trl(),
        "32_sostenibilidad": renderer.sustainability(),
        "33_uso_posterior": renderer.post_use(),
        "34_transferencia": renderer.transfer(summary),
        "35_medidas_diferenciales": renderer.differential(),
        ASC_STEM: renderer.asc(),
    }
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
    for name, text in (("check", "validate componentes.json"),
                       ("render", "write sections 31 to 35 and 18"),
                       ("datos", "TRL and transfer facts of datos_sgr")):
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
            print("error: componentes.json tiene hallazgos de error; no se generan las secciones.", file=sys.stderr)
            _print_findings(exc.errors, sys.stderr)
            return 1
        except InputError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.command == "datos":
        print(json.dumps(datos(run), ensure_ascii=False, indent=2))
        return 0

    if not (run / COMPONENTS_FILE).is_file():
        print(f"error: no existe {COMPONENTS_FILE.as_posix()}", file=sys.stderr)
        return 2
    found = check_findings(run)
    errors = sum(1 for f in found if f["severity"] == "error")
    if args.json:
        print(json.dumps({"findings": found}, ensure_ascii=False, indent=2))
    else:
        _print_findings(found, sys.stdout)
        print(f"componentes: {errors} errores, {len(found) - errors} avisos")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
