#!/usr/bin/env python3
"""SGR budget as data: check, sync to the value chain, render §13 and §30 (flujo SGR only).

`artefactos/sgr/presupuesto.json` (schema `morfeo.presupuesto-sgr/v1`) holds the
budget items of an SGR project. Each item carries its Minciencias rubro (TdR
Conv 54 §13.2) and its MGA insumo (Instructivo MGA 2023, p. 68): two views of
the same money, per entity and source.

    {schema, duracion_meses|null, tope_sgr|null, semanas_por_mes:4, factor_prestacional|null,
     items:[{id:"P1", rubro, insumo_mga, descripcion, justificacion, entidad:"E1",
             fuente:"sgr"|"especie"|"efectivo",
             componente:"transferencia"|"asc"|"seguimiento"|null,
             cantidad, valor_unitario,
             talento:{perfil, horas_semana, valor_hora, meses}|null,
             actividades:["1.1.1"], cotizaciones:int, soporte|null}]}

The value of an item is cantidad × valor_unitario; with `talento`, it is
horas_semana × valor_hora × meses × semanas_por_mes × (factor_prestacional or
1). Values are rounded to whole pesos. An item's value is split evenly across
its activities (the reference workbook's rule): every share is rounded to whole
pesos and the remainder goes to the last activity, so the activity costs add up
exactly to the budget total.

Commands:
  check RUN_ROOT [--json]
      Findings with check_run's shape {severity, code, message, node}, codes
      prefixed `presupuesto-`; a missing file is an error here.
  sync-cadena RUN_ROOT
      Write each activity's `costo` (the sum of its shares, every source) into
      artefactos/sgr/cadena_valor.json, keeping every other field and the key
      order. Refuses while the items cannot be split (invalid values, unknown
      activities).
  render RUN_ROOT
      Write redaccion/sections/13_presupuesto.tex (SGR form: rubro × source per
      entity, MGA insumos view, item justification and annual projection) and
      30_fuentes_financiacion.tex (Anexo 2 cap. 29: the three literal lines in
      letters and numbers and the Entidad | Fuente de recursos | Valor table).
      SGR runs only; refuses while there are error findings.
  resumen RUN_ROOT [--json]
      Totals by source, rubro, MGA insumo, entity and activity, and the
      percentages the live checks use.
  datos RUN_ROOT [--json]
      The money part of `morfeo.datos-sgr/v1` (monto_sgr, entity contributions,
      transferencia_valor and the totals declared by «presupuesto»).

Exit codes: 0 ok, 1 error findings (check, sync-cadena, render), 2 bad input.
Standard library only. The value chain comes from artefactos/sgr/cadena_valor.json,
the entities from artefactos/sgr/alianza.json, the LaTeX escaping from
cadena_valor_sgr.py, the flow from check_run.py, the TdR chapters from
ensamblar_main.py, the call's cap from juez_sgr.py and the annual projection
from cronograma_sgr.py when it exists (all in this folder). check_run imports
`findings`; the dashboard imports `findings`, `resumen` and `datos`.
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SCHEMA = "morfeo.presupuesto-sgr/v1"
DATA_SCHEMA = "morfeo.datos-sgr/v1"
BUDGET_FILE = Path("artefactos") / "sgr" / "presupuesto.json"
ALLIANCE_FILE = Path("artefactos") / "sgr" / "alianza.json"
CHAIN_FILE = Path("artefactos") / "sgr" / "cadena_valor.json"
STRUCTURE_FILE = Path("artefactos") / "estructura_tdr.json"
SECTIONS_DIR = Path("redaccion") / "sections"
BUDGET_STEM = "13_presupuesto"
SOURCES_STEM = "30_fuentes_financiacion"
GENERATED_HEADER = "% GENERADO por scripts/presupuesto_sgr.py"
HERE = Path(__file__).resolve().parent

RUBROS = {
    "talento_humano": "Talento humano",
    "equipos_software": "Equipos y software",
    "capacitacion_eventos": "Capacitación y eventos",
    "servicios_tecnologicos_pruebas": "Servicios tecnológicos y pruebas",
    "materiales_insumos_documentacion": "Materiales, insumos y documentación",
    "proteccion_conocimiento_divulgacion": "Protección del conocimiento y divulgación",
    "gastos_viaje": "Gastos de viaje",
    "infraestructura": "Infraestructura",
    "administrativos": "Administrativos",
    "seguimiento": "Seguimiento",
    "otros": "Otros",
}
INSUMOS_MGA = {
    "mano_obra_calificada": "Mano de obra calificada",
    "mano_obra_no_calificada": "Mano de obra no calificada",
    "materiales": "Materiales",
    "servicios_domiciliarios": "Servicios domiciliarios",
    "terrenos": "Terrenos",
    "edificios": "Edificios",
    "maquinaria_equipo": "Maquinaria y equipo",
    "transporte": "Transporte",
    "alojamiento_comidas": "Alojamiento y comidas",
    "servicios_empresas": "Servicios a empresas y a la producción",
    "servicios_comunitarios": "Servicios comunitarios",
}
SOURCES = {"sgr": "SGR", "especie": "Especie", "efectivo": "Efectivo"}
SOURCE_NAMES = {"sgr": "Sistema General de Regalías (SGR)", "especie": "Contrapartida en especie",
                "efectivo": "Contrapartida en efectivo"}
COMPONENTS = ("transferencia", "asc", "seguimiento")
QUOTED_RUBROS = ("equipos_software", "servicios_tecnologicos_pruebas")
MIN_QUOTES = 2
MOBILITY_MAX_PCT = 2.0
TRANSFER_MIN_PCT = 1.0
TOLERANCE = 0.5  # pesos
# Errors that make the split across activities meaningless: sync-cadena refuses on them.
SPLIT_BLOCKERS = ("presupuesto-json-invalido", "presupuesto-esquema", "presupuesto-sin-actividades",
                  "presupuesto-actividad-desconocida", "presupuesto-valor-invalido", "presupuesto-valor-negativo")

SRC_LINE = ("Valor total de recursos solicitados a la Asignación de CTeI/ Asignación de CTeI Ambiental del SGR "
            "– Sistema General de Regalías:")
COUNTERPART_LINE = "Valor total contrapartida (en efectivo y en especie):"
TOTAL_LINE = "Valor total del proyecto:"


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
    spec = importlib.util.spec_from_file_location(f"_presupuesto_{name}", path)
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


def _list(value) -> list:
    return value if isinstance(value, list) else []


def pesos(value) -> int:
    """Whole pesos, rounding half up (deterministic, unlike round())."""
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _pct(part: float, whole: float):
    return None if not whole else round(100 * part / whole, 2)


# --- Number to words ----------------------------------------------------------

_UNITS = ("", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
          "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte",
          "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete",
          "veintiocho", "veintinueve")
_TENS = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_HUNDREDS = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos",
             6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def _below_thousand(n: int) -> str:
    if n == 100:
        return "cien"
    hundreds, rest = divmod(n, 100)
    parts = [_HUNDREDS[hundreds]] if hundreds else []
    if rest:
        if rest < 30:
            parts.append(_UNITS[rest])
        else:
            tens, unit = divmod(rest, 10)
            parts.append(_TENS[tens] + (f" y {_UNITS[unit]}" if unit else ""))
    return " ".join(parts)


def _apocope(words: str) -> str:
    """«uno» becomes «un» and «veintiuno» «veintiún» before a noun (mil, millones, pesos)."""
    if words.endswith("veintiuno"):
        return words[: -len("veintiuno")] + "veintiún"
    if words == "uno" or words.endswith(" uno"):
        return words[:-3] + "un"
    return words


def _below_million(n: int, before_noun: bool) -> str:
    thousands, rest = divmod(n, 1000)
    parts = []
    if thousands:
        parts.append("mil" if thousands == 1 else f"{_apocope(_below_thousand(thousands))} mil")
    if rest:
        words = _below_thousand(rest)
        parts.append(_apocope(words) if before_noun else words)
    return " ".join(parts)


def number_words(n: int, before_noun: bool = False) -> str:
    """Spanish cardinal of a whole number below 10^18 («diecisiete mil ciento setenta y siete millones…»)."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 0 or n >= 10 ** 18:
        raise ValueError(f"no se puede escribir en letras: {n!r}")
    if n == 0:
        return "cero"
    billions, rest = divmod(n, 10 ** 12)
    millions, units = divmod(rest, 10 ** 6)
    parts = []
    if billions:
        parts.append("un billón" if billions == 1 else f"{_below_million(billions, True)} billones")
    if millions:
        parts.append("un millón" if millions == 1 else f"{_below_million(millions, True)} millones")
    if units:
        parts.append(_below_million(units, before_noun))
    return " ".join(parts)


def pesos_en_letras(n: int) -> str:
    """«DIECISIETE MIL … PESOS M/CTE»: the amount in letters, as the Anexo 2 asks."""
    if n == 1:
        return "UN PESO M/CTE"
    words = number_words(n, before_noun=True)
    joiner = " de" if n and n % 10 ** 6 == 0 else ""
    return f"{words}{joiner} pesos m/cte".upper()


# --- Data ---------------------------------------------------------------------

def _items(budget: dict) -> list[dict]:
    return [i for i in _list(budget.get("items")) if isinstance(i, dict)]


def _weeks(budget: dict):
    weeks = budget.get("semanas_por_mes")
    return 4 if weeks is None else weeks


def item_value(item: dict, budget: dict) -> int:
    """Whole-peso value of an item; 0 when a factor is not a valid number."""
    talent = item.get("talento")
    if isinstance(talent, dict):
        factor = budget.get("factor_prestacional")
        factors = [talent.get("horas_semana"), talent.get("valor_hora"), talent.get("meses"), _weeks(budget),
                   1 if factor is None else factor]
    else:
        factors = [item.get("cantidad"), item.get("valor_unitario")]
    if any(_number(f) is None or f < 0 for f in factors):
        return 0
    value = Decimal(1)
    for f in factors:
        value *= Decimal(str(f))
    return pesos(value)


def _codes(item: dict) -> list[str]:
    seen: list[str] = []
    for code in _list(item.get("actividades")):
        code = _text(code)
        if code and code not in seen:
            seen.append(code)
    return seen


def split(value: int, codes: list[str]) -> list[tuple[str, int]]:
    """Even shares of `value` across `codes`, whole pesos, remainder on the last one."""
    if not codes:
        return []
    share = pesos(Decimal(value) / len(codes))
    shares = [(code, share) for code in codes[:-1]]
    return shares + [(codes[-1], value - share * (len(codes) - 1))]


def activity_shares(budget: dict) -> dict[str, int]:
    """Cost of each activity code: the sum of its shares over every item and source."""
    out: dict[str, int] = {}
    for item in _items(budget):
        for code, share in split(item_value(item, budget), _codes(item)):
            out[code] = out.get(code, 0) + share
    return out


def _chain_activities(chain) -> list[dict] | None:
    if not isinstance(chain, dict):
        return None
    out = []
    for objective in _list(chain.get("objetivos")):
        for product in _list(objective.get("productos") if isinstance(objective, dict) else None):
            if isinstance(product, dict):
                out += [a for a in _list(product.get("actividades")) if isinstance(a, dict)]
    return out


def _entities(alliance) -> list[dict]:
    if not isinstance(alliance, dict):
        return []
    return [e for e in _list(alliance.get("entidades")) if isinstance(e, dict)]


def _rubric_cap(run: Path):
    """(cap, origin) of the call's rubric (juez_sgr.resolve_rubric), or (None, None)."""
    try:
        juez = _sibling("juez_sgr")
        if juez is None:
            return None, None
        rubric, origin, _ = juez.resolve_rubric(run, None)
    except Exception:  # no rubric resolvable: the cap check is skipped
        return None, None
    cap = _number(rubric.get("tope_solicitud_sgr"))
    return (cap, f"rúbrica {rubric.get('id')} ({origin})") if cap is not None else (None, None)


def effective_cap(run: Path, budget: dict):
    """(cap, origin): tope_sgr of the budget, else the cap of the call's rubric."""
    cap = _number(budget.get("tope_sgr"))
    if cap is not None:
        return cap, f"{BUDGET_FILE.as_posix()} (tope_sgr)"
    return _rubric_cap(run)


def _totals(budget: dict) -> dict:
    """Totals of a parsed budget (valid sources only)."""
    zero = lambda: {"sgr": 0, "especie": 0, "efectivo": 0}  # noqa: E731
    sources = zero()
    by_rubro: dict[str, dict] = {}
    by_insumo: dict[str, dict] = {}
    by_entity: dict[str, dict] = {}
    transfer = mobility = follow_up = 0
    missing_quotes = 0
    for item in _items(budget):
        source = item.get("fuente")
        value = item_value(item, budget)
        if item.get("rubro") in QUOTED_RUBROS and _quotes(item) < MIN_QUOTES:
            missing_quotes += 1
        if item.get("componente") == "transferencia":
            transfer += value
        if source not in SOURCES:
            continue
        sources[source] += value
        for table, key in ((by_rubro, item.get("rubro")), (by_insumo, item.get("insumo_mga")),
                           (by_entity, _text(item.get("entidad")))):
            table.setdefault(str(key), zero())[source] += value
        if source == "sgr" and item.get("rubro") == "gastos_viaje":
            mobility += value
        if source == "sgr" and item.get("rubro") == "seguimiento":
            follow_up += value
    return {"fuentes": sources, "por_rubro": by_rubro, "por_insumo": by_insumo, "por_entidad": by_entity,
            "transferencia": transfer, "movilidad": mobility, "seguimiento": follow_up,
            "cotizaciones_faltantes": missing_quotes}


def _quotes(item: dict) -> int:
    quotes = item.get("cotizaciones")
    return quotes if isinstance(quotes, int) and not isinstance(quotes, bool) and quotes > 0 else 0


def _ordered(table: dict, order) -> dict:
    keys = [k for k in order if k in table] + [k for k in table if k not in order]
    return {k: table[k] for k in keys}


# --- Check --------------------------------------------------------------------

def budget_findings(budget, run: Path, alliance, chain) -> list[dict]:
    """Rules of presupuesto.json (odd/tasks/sgr-presupuesto-gantt.md, Contracts)."""
    if not isinstance(budget, dict) or budget.get("schema") != SCHEMA:
        return [_finding("error", "presupuesto-esquema", "presupuesto", f"El archivo no declara el esquema {SCHEMA}.")]
    out: list[dict] = []
    for field in ("duracion_meses", "tope_sgr", "semanas_por_mes", "factor_prestacional"):
        value = budget.get(field)
        if value is None:
            continue
        if _number(value) is None:
            out.append(_finding("error", "presupuesto-valor-invalido", "presupuesto",
                                f"{field} no es un número."))
        elif value < 0:
            out.append(_finding("error", "presupuesto-valor-negativo", "presupuesto", f"{field} es negativo."))
    entity_ids = {_text(e.get("id")) for e in _entities(alliance)} if isinstance(alliance, dict) else None
    if entity_ids is None:
        out.append(_finding("warning", "presupuesto-alianza-faltante", "presupuesto",
                            f"No se encontró {ALLIANCE_FILE.as_posix()}: no se cotejan las entidades ni sus aportes."))
    activities = _chain_activities(chain)
    known = {_text(a.get("codigo")) for a in activities} if activities is not None else None
    if known is None:
        out.append(_finding("warning", "presupuesto-cadena-faltante", "presupuesto",
                            f"No se encontró {CHAIN_FILE.as_posix()}: no se cotejan los códigos de actividad."))
    seen: set[str] = set()
    for n, item in enumerate(_items(budget), start=1):
        iid = _text(item.get("id")) or f"ítem {n}"
        if iid in seen:
            out.append(_finding("error", "presupuesto-id-duplicado", iid, f"El id de ítem {iid} está repetido."))
        seen.add(iid)
        for field, allowed, code in (("rubro", RUBROS, "presupuesto-rubro-invalido"),
                                     ("insumo_mga", INSUMOS_MGA, "presupuesto-insumo-invalido"),
                                     ("fuente", SOURCES, "presupuesto-fuente-invalida")):
            if item.get(field) not in allowed:
                out.append(_finding("error", code, iid, f"El ítem {iid} tiene {field} «{item.get(field)}»; los "
                                                        f"valores válidos son {', '.join(allowed)}."))
        component = item.get("componente")
        if component is not None and component not in COMPONENTS:
            out.append(_finding("error", "presupuesto-componente-invalido", iid,
                                f"El ítem {iid} tiene componente «{component}»; los valores válidos son "
                                f"{', '.join(COMPONENTS)} o null."))
        out += _value_findings(item, iid)
        if entity_ids is not None and _text(item.get("entidad")) not in entity_ids:
            out.append(_finding("error", "presupuesto-entidad-desconocida", iid,
                                f"El ítem {iid} cita la entidad «{item.get('entidad')}», que no está en "
                                f"{ALLIANCE_FILE.as_posix()}."))
        codes = _codes(item)
        if not codes:
            out.append(_finding("error", "presupuesto-sin-actividades", iid,
                                f"El ítem {iid} no financia ninguna actividad de la cadena de valor."))
        elif known is not None:
            unknown = [c for c in codes if c not in known]
            if unknown:
                out.append(_finding("error", "presupuesto-actividad-desconocida", iid,
                                    f"El ítem {iid} cita actividades que no están en la cadena de valor: "
                                    f"{', '.join(unknown)}."))
        if item.get("rubro") in QUOTED_RUBROS and _quotes(item) < MIN_QUOTES:
            out.append(_finding("warning", "presupuesto-cotizaciones", iid,
                                f"El ítem {iid} ({RUBROS[item['rubro']].lower()}) tiene {_quotes(item)} "
                                f"cotizaciones; la rúbrica de coherencia presupuestal pide al menos {MIN_QUOTES}."))
    totals = _totals(budget)
    total_sgr = totals["fuentes"]["sgr"]
    cap, origin = effective_cap(run, budget)
    if cap is not None and total_sgr > cap + TOLERANCE:
        out.append(_finding("error", "presupuesto-tope-superado", "presupuesto",
                            f"El total solicitado al SGR ({_plain_money(total_sgr)}) supera el tope "
                            f"({_plain_money(cap)}, {origin})."))
    if totals["seguimiento"] <= 0:
        out.append(_finding("error", "presupuesto-seguimiento-faltante", "presupuesto",
                            "El rubro Seguimiento con recursos del SGR es obligatorio y no tiene valor."))
    if total_sgr > 0:
        mobility = _pct(totals["movilidad"], total_sgr)
        if mobility > MOBILITY_MAX_PCT:
            out.append(_finding("warning", "presupuesto-movilidad-alta", "gastos_viaje",
                                f"Los gastos de viaje con recursos del SGR son el {_plain_pct(mobility)} del total "
                                f"SGR; el tope de la convocatoria es {_plain_pct(MOBILITY_MAX_PCT)}."))
        transfer = _pct(totals["transferencia"], total_sgr)
        if transfer < TRANSFER_MIN_PCT:
            out.append(_finding("warning", "presupuesto-transferencia-baja", "transferencia",
                                f"El componente de transferencia suma el {_plain_pct(transfer)} del total SGR; "
                                f"el mínimo es {_plain_pct(TRANSFER_MIN_PCT)}."))
    for entity in _entities(alliance):
        eid = _text(entity.get("id"))
        own = totals["por_entidad"].get(eid, {"especie": 0, "efectivo": 0})
        for source in ("especie", "efectivo"):
            declared = _number(entity.get(f"aporte_{source}"))
            if declared is not None and abs(own[source] - declared) > TOLERANCE:
                out.append(_finding("error", "presupuesto-contrapartida-no-cuadra", eid,
                                    f"Los ítems en {source} de {eid} suman {_plain_money(own[source])}; "
                                    f"alianza.json declara un aporte en {source} de {_plain_money(declared)}."))
    out += _drift_findings(budget, activities)
    return out


def _value_findings(item: dict, iid: str) -> list[dict]:
    talent = item.get("talento")
    if talent is not None and not isinstance(talent, dict):
        return [_finding("error", "presupuesto-valor-invalido", iid, f"El talento del ítem {iid} no es un objeto.")]
    fields = (("horas_semana", "valor_hora", "meses") if isinstance(talent, dict) else ("cantidad", "valor_unitario"))
    source = talent if isinstance(talent, dict) else item
    out = []
    for field in fields:
        value = source.get(field)
        if _number(value) is None:
            out.append(_finding("error", "presupuesto-valor-invalido", iid,
                                f"El campo {field} del ítem {iid} no es un número."))
        elif value < 0:
            out.append(_finding("error", "presupuesto-valor-negativo", iid,
                                f"El campo {field} del ítem {iid} es negativo."))
    quotes = item.get("cotizaciones")
    if quotes is not None and (not isinstance(quotes, int) or isinstance(quotes, bool)):
        out.append(_finding("error", "presupuesto-valor-invalido", iid,
                            f"Las cotizaciones del ítem {iid} no son un número entero."))
    elif isinstance(quotes, int) and quotes < 0:
        out.append(_finding("error", "presupuesto-valor-negativo", iid, f"Las cotizaciones del ítem {iid} son negativas."))
    return out


def _drift_findings(budget: dict, activities: list[dict] | None) -> list[dict]:
    """Once sync-cadena wrote the costs, each activity's costo is the sum of its shares."""
    if not activities:
        return []
    if not any(_number(a.get("costo")) is not None for a in activities):
        return [_finding("warning", "presupuesto-cadena-sin-sincronizar", "cadena",
                         "La cadena de valor todavía no tiene los costos del presupuesto: corré "
                         "python3 scripts/presupuesto_sgr.py sync-cadena <RUN_ROOT>.")]
    shares = activity_shares(budget)
    out = []
    for activity in activities:
        code = _text(activity.get("codigo"))
        expected = shares.get(code, 0)
        cost = _number(activity.get("costo"))
        if cost is None or abs(cost - expected) > TOLERANCE:
            shown = "sin costo" if cost is None else _plain_money(cost)
            out.append(_finding("error", "presupuesto-costo-desincronizado", code,
                                f"La actividad {code} tiene {shown} en la cadena de valor y el presupuesto le "
                                f"asigna {_plain_money(expected)}: corré python3 scripts/presupuesto_sgr.py "
                                "sync-cadena <RUN_ROOT>."))
    return out


def _load(run: Path) -> dict:
    out: dict = {"errores": []}
    budget, error = _read_json(run / BUDGET_FILE)
    if error:
        out["errores"].append(_finding("error", "presupuesto-json-invalido", "presupuesto",
                                       f"{BUDGET_FILE.as_posix()} no es JSON válido: {error}"))
    out["presupuesto"] = budget
    out["alianza"], _ = _read_json(run / ALLIANCE_FILE)
    out["cadena"], _ = _read_json(run / CHAIN_FILE)
    return out


def findings(run_root: Path) -> list[dict]:
    """Findings of presupuesto.json; [] when it does not exist."""
    run = Path(run_root)
    if not (run / BUDGET_FILE).is_file():
        return []
    data = _load(run)
    if data["errores"]:
        return data["errores"]
    return budget_findings(data["presupuesto"], run, data["alianza"], data["cadena"])


def check_findings(run_root: Path) -> list[dict]:
    """findings() plus an error when the file is missing (the CLI `check` and `render`)."""
    run = Path(run_root)
    if not (run / BUDGET_FILE).is_file():
        return [_finding("error", "presupuesto-archivo-faltante", "presupuesto", f"No existe {BUDGET_FILE.as_posix()}.")]
    return findings(run)


# --- Summary and judge facts ----------------------------------------------------

def resumen(run_root: Path) -> dict | None:
    """Totals and live-check percentages of presupuesto.json; None when it is missing or unreadable."""
    run = Path(run_root)
    budget, _ = _read_json(run / BUDGET_FILE)
    if not isinstance(budget, dict):
        return None
    alliance, _ = _read_json(run / ALLIANCE_FILE)
    chain, _ = _read_json(run / CHAIN_FILE)
    totals = _totals(budget)
    src = totals["fuentes"]
    counterpart = src["especie"] + src["efectivo"]
    shares = activity_shares(budget)
    order = [_text(a.get("codigo")) for a in _chain_activities(chain) or []]
    cap, _ = effective_cap(run, budget)
    return {
        "total_sgr": src["sgr"], "total_especie": src["especie"], "total_efectivo": src["efectivo"],
        "total": src["sgr"] + counterpart,
        "tope_sgr": cap,
        "por_rubro": _ordered(totals["por_rubro"], RUBROS),
        "por_insumo": _ordered(totals["por_insumo"], INSUMOS_MGA),
        "por_entidad": _ordered(totals["por_entidad"], [_text(e.get("id")) for e in _entities(alliance)]),
        "cofinanciacion_pct": _pct(counterpart, src["sgr"]),
        "transferencia_pct": _pct(totals["transferencia"], src["sgr"]),
        "movilidad_pct": _pct(totals["movilidad"], src["sgr"]),
        "seguimiento": totals["seguimiento"] > 0,
        "cotizaciones_faltantes": totals["cotizaciones_faltantes"],
        "por_actividad": _ordered({**{c: 0 for c in order}, **shares}, order),
    }


def datos(run_root: Path) -> dict:
    """The money part of morfeo.datos-sgr/v1, taken from presupuesto.json."""
    run = Path(run_root)
    source = BUDGET_FILE.as_posix()
    out: dict = {"schema": DATA_SCHEMA, "monto_sgr": None, "aportes_entidades": None, "transferencia_valor": None,
                 "totales_declarados": None, "fuente": []}
    summary = resumen(run)
    if summary is None:
        return out
    out["fuente"].append(source)
    out["monto_sgr"] = {"valor": summary["total_sgr"], "fuente": f"{source} (ítems con fuente sgr)"}
    out["aportes_entidades"] = [
        {"entidad": eid, "sgr": v["sgr"], "contrapartida_especie": v["especie"],
         "contrapartida_efectivo": v["efectivo"], "fuente": f"{source} (ítems de {eid})"}
        for eid, v in summary["por_entidad"].items()]
    budget, _ = _read_json(run / BUDGET_FILE)
    out["transferencia_valor"] = _totals(budget)["transferencia"]
    counterpart = summary["total_especie"] + summary["total_efectivo"]
    out["totales_declarados"] = [
        {"documento": "presupuesto", "concepto": "sgr", "valor": summary["total_sgr"], "fuente": source},
        {"documento": "presupuesto", "concepto": "contrapartida", "valor": counterpart, "fuente": source},
        {"documento": "presupuesto", "concepto": "total", "valor": summary["total"], "fuente": source},
    ]
    return out


# --- Sync to the value chain --------------------------------------------------------

def sync_cadena(run_root: Path) -> Path:
    """Write each activity's costo into cadena_valor.json; every other field and key stays as it was."""
    run = Path(run_root)
    for rel in (BUDGET_FILE, CHAIN_FILE):
        if not (run / rel).is_file():
            raise InputError(f"no existe {rel.as_posix()}")
    blockers = [f for f in findings(run) if f["severity"] == "error" and f["code"] in SPLIT_BLOCKERS]
    if blockers:
        raise RenderRefused(blockers)
    budget, _ = _read_json(run / BUDGET_FILE)
    chain, error = _read_json(run / CHAIN_FILE)
    if not isinstance(chain, dict):
        raise InputError(f"{CHAIN_FILE.as_posix()} no es JSON válido: {error}")
    shares = activity_shares(budget)
    for activity in _chain_activities(chain):
        activity["costo"] = shares.get(_text(activity.get("codigo")), 0)
    path = run / CHAIN_FILE
    path.write_text(json.dumps(chain, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


# --- Render -----------------------------------------------------------------------

def _escape(text) -> str:
    return _sibling("cadena_valor_sgr").escape(text)


def _money(value) -> str:
    return r"\$\," + f"{pesos(value):,}".replace(",", ".")


def _plain_money(value) -> str:
    return "$ " + f"{pesos(value):,}".replace(",", ".")


def _plain_pct(value) -> str:
    return f"{value:.2f}".replace(".", ",") + " %"


def _tex_pct(value) -> str:
    return f"{value:.2f}".replace(".", ",") + r"\,\%"


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


def _open(run: Path, stem: str, default_title: str, label: str, sources: str) -> list[str]:
    mode, title = _heading_mode(run, stem)
    lines = [
        GENERATED_HEADER,
        f"% Fuente: {sources}. No se edita a mano: se regenera con",
        "% python3 scripts/presupuesto_sgr.py render <RUN_ROOT>.",
    ]
    if mode == "section":
        lines += [rf"\section{{{_escape(title or default_title)}}}", rf"\label{{sec:{label}}}"]
    return lines


def _col(width: str, align: str = "raggedright") -> str:
    return rf">{{\{align}\arraybackslash}}p{{{width}\textwidth}}"


_X = r">{\raggedright\arraybackslash}X"
_NUM = _col("0.13", "raggedleft")


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
    lines += [row if isinstance(row, str) else " & ".join(row) + r" \\" for row in rows]
    lines += [r"\end{xltabular}", "}"]
    return lines


def _amounts(values: dict, bold: bool = False) -> list[str]:
    cells = [_money(values[s]) for s in SOURCES] + [_money(sum(values[s] for s in SOURCES))]
    return [rf"\textbf{{{c}}}" for c in cells] if bold else cells


def _entity_name(entities: dict, eid: str) -> str:
    return _escape(entities.get(eid) or eid)


def render_budget(run: Path, budget: dict, alliance) -> tuple[str, str | None]:
    """(text of 13_presupuesto.tex, note when the annual projection is unavailable)."""
    lines = _open(run, BUDGET_STEM, "Presupuesto", "presupuesto",
                  f"{BUDGET_FILE.as_posix()}, {ALLIANCE_FILE.as_posix()} y {CHAIN_FILE.as_posix()}")
    entities = {_text(e.get("id")): _text(e.get("nombre")) for e in _entities(alliance)}
    totals = _totals(budget)
    items = _items(budget)
    lines += ["", r"La tabla~\ref{tab:presupuesto} presenta el presupuesto por rubro y por fuente de recursos, con el "
                  r"aporte de cada entidad; la tabla~\ref{tab:presupuesto_mga} agrupa los mismos valores por "
                  r"categoría de insumo de la MGA."]

    lines += ["", r"\subsection{Presupuesto por rubro y fuente de recursos}"]
    rows: list = []
    for rubro, values in _ordered(totals["por_rubro"], RUBROS).items():
        rows.append([rf"\textbf{{{_escape(RUBROS.get(rubro, rubro))}}}"] + _amounts(values, bold=True))
        per_entity: dict[str, dict] = {}
        for item in items:
            if str(item.get("rubro")) == rubro and item.get("fuente") in SOURCES:
                bucket = per_entity.setdefault(_text(item.get("entidad")), {s: 0 for s in SOURCES})
                bucket[item["fuente"]] += item_value(item, budget)
        for eid, values_e in _ordered(per_entity, entities).items():
            rows.append([rf"\hspace{{1em}}{_entity_name(entities, eid)}"] + _amounts(values_e))
    rows += [r"\midrule", [r"\textbf{Total}"] + _amounts(totals["fuentes"], bold=True)]
    lines += _table(f"{_X} {_NUM} {_NUM} {_NUM} {_NUM}", ["Rubro", "SGR", "Especie", "Efectivo", "Total"], rows,
                    "Presupuesto por rubro de Minciencias, fuente de recursos y entidad.", "presupuesto")

    rows = [[_entity_name(entities, eid)] + _amounts(values)
            for eid, values in _ordered(totals["por_entidad"], entities).items()]
    rows += [r"\midrule", [r"\textbf{Total}"] + _amounts(totals["fuentes"], bold=True)]
    lines += _table(f"{_X} {_NUM} {_NUM} {_NUM} {_NUM}", ["Entidad", "SGR", "Especie", "Efectivo", "Total"], rows,
                    "Aportes por entidad y fuente de recursos.", "presupuesto_entidades")

    lines += ["", r"\subsection{Presupuesto por insumo de la MGA}"]
    rows = [[_escape(INSUMOS_MGA.get(key, key))] + _amounts(values)
            for key, values in _ordered(totals["por_insumo"], INSUMOS_MGA).items()]
    rows += [r"\midrule", [r"\textbf{Total}"] + _amounts(totals["fuentes"], bold=True)]
    lines += _table(f"{_X} {_NUM} {_NUM} {_NUM} {_NUM}", ["Insumo de la MGA", "SGR", "Especie", "Efectivo", "Total"],
                    rows, "Presupuesto por categoría de insumo de la MGA (Instructivo MGA 2023).", "presupuesto_mga")

    lines += ["", r"\subsection{Justificación de los ítems}"]
    order = {key: n for n, key in enumerate(RUBROS)}
    rows = []
    for item in sorted(items, key=lambda i: order.get(i.get("rubro"), len(order))):
        description = rf"\textbf{{{_escape(item.get('id'))}}} {_escape(item.get('descripcion'))}"
        if _text(item.get("justificacion")):
            description += rf"\newline {_escape(item.get('justificacion'))}"
        talent = item.get("talento")
        if isinstance(talent, dict):
            description += (rf"\newline Perfil: {_escape(talent.get('perfil'))}; {_escape(talent.get('horas_semana'))} "
                            rf"horas por semana durante {_escape(talent.get('meses'))} meses.")
        rows.append([
            _escape(RUBROS.get(item.get("rubro"), item.get("rubro"))),
            description,
            _entity_name(entities, _text(item.get("entidad"))),
            ", ".join(_escape(c) for c in _codes(item)) or "Por definir",
            rf"{_money(item_value(item, budget))}\newline {SOURCES.get(item.get('fuente'), _escape(item.get('fuente')))}",
            str(_quotes(item)),
        ])
    lines += _table(f"{_col('0.14')} {_X} {_col('0.14')} {_col('0.1')} {_NUM} {_col('0.08', 'centering')}",
                    ["Rubro", "Descripción y justificación", "Entidad", "Actividades", "Valor", "Cotizaciones"],
                    rows, "Justificación de los ítems del presupuesto y actividades que financian.",
                    "presupuesto_items")

    projection, note = _projection(run)
    lines += ["", r"\subsection{Proyección financiera anual}"]
    if projection is None:
        lines += [f"% {note}"]
    else:
        total = sum(row["valor"] for row in projection) or 0
        rows = [[f"Año {_escape(row['anio'])}", _money(row["valor"]), _tex_pct(row["pct"])] for row in projection]
        rows += [r"\midrule", [r"\textbf{Total}", rf"\textbf{{{_money(total)}}}", rf"\textbf{{{_tex_pct(100)}}}"]]
        lines += _table(f"{_X} {_col('0.2', 'raggedleft')} {_col('0.15', 'raggedleft')}",
                        ["Año", "Valor", "Porcentaje"], rows,
                        "Proyección financiera anual del proyecto, según el cronograma de actividades.",
                        "presupuesto_proyeccion")
    return "\n".join(lines + [""]), note


def _projection(run: Path) -> tuple[list[dict] | None, str | None]:
    """([{anio, valor, pct}], None) from cronograma_sgr.proyeccion, or (None, note)."""
    try:
        module = _sibling("cronograma_sgr")
        if module is None or not hasattr(module, "proyeccion"):
            return None, "La proyección anual se genera con scripts/cronograma_sgr.py, que no está disponible."
        data = module.proyeccion(run)
    except Exception as exc:  # the projection is optional: the budget still renders
        return None, f"No se pudo calcular la proyección anual con scripts/cronograma_sgr.py: {exc!r}."
    rows = []
    for row in _list(data.get("anios") if isinstance(data, dict) else None):
        if isinstance(row, dict) and _number(row.get("valor")) is not None:
            rows.append(row)
    if not rows:
        return None, "scripts/cronograma_sgr.py no devolvió años con valor (faltan meses o costos en la cadena)."
    total = sum(r["valor"] for r in rows)
    return [{"anio": r.get("anio"), "valor": r["valor"],
             "pct": r["pct"] if _number(r.get("pct")) is not None else (_pct(r["valor"], total) or 0)}
            for r in rows], None


def render_sources(run: Path, budget: dict, alliance) -> str:
    lines = _open(run, SOURCES_STEM, "Resumen de fuentes de financiación", "fuentes_financiacion",
                  f"{BUDGET_FILE.as_posix()} y {ALLIANCE_FILE.as_posix()}")
    entities = {_text(e.get("id")): _text(e.get("nombre")) for e in _entities(alliance)}
    totals = _totals(budget)
    rows = []
    for eid, values in _ordered(totals["por_entidad"], entities).items():
        for source, label in SOURCE_NAMES.items():
            if values[source]:
                rows.append([_entity_name(entities, eid), label, _money(values[source])])
    rows += [r"\midrule", [r"\multicolumn{2}{r}{\textbf{Total}}",
                           rf"\textbf{{{_money(sum(totals['fuentes'].values()))}}}"]]
    lines += _table(f"{_X} {_col('0.3')} {_col('0.18', 'raggedleft')}", ["Entidad", "Fuente de recursos", "Valor"],
                    rows, "Resumen de fuentes de financiación por entidad.", "fuentes_financiacion")
    src = totals["fuentes"]
    counterpart = src["especie"] + src["efectivo"]
    for text, value in ((SRC_LINE, src["sgr"]), (COUNTERPART_LINE, counterpart), (TOTAL_LINE, src["sgr"] + counterpart)):
        lines += ["", rf"\noindent {_escape(text)} {pesos_en_letras(pesos(value))} ({_money(value)})."]
    return "\n".join(lines + [""])


def _flujo(run: Path) -> str:
    module = _sibling("check_run")
    return module.detect_flujo(run) if module is not None else "base"


def render_sections(run_root: Path) -> tuple[list[Path], str | None]:
    """Write 13_presupuesto.tex and 30_fuentes_financiacion.tex; (paths, projection note)."""
    run = Path(run_root)
    if _flujo(run) != "sgr":
        raise InputError("el presupuesto como datos es solo del flujo SGR; en el flujo base §13 no se genera")
    if not (run / BUDGET_FILE).is_file():
        raise InputError(f"no existe {BUDGET_FILE.as_posix()}: el presupuestador lo escribe en la Fase 6.4")
    errors = [f for f in check_findings(run) if f["severity"] == "error"]
    if errors:
        raise RenderRefused(errors)
    budget, _ = _read_json(run / BUDGET_FILE)
    alliance, _ = _read_json(run / ALLIANCE_FILE)
    budget_text, note = render_budget(run, budget, alliance)
    texts = {BUDGET_STEM: budget_text, SOURCES_STEM: render_sources(run, budget, alliance)}
    out_dir = run / SECTIONS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for stem, text in texts.items():
        path = out_dir / f"{stem}.tex"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written, note


# --- CLI ------------------------------------------------------------------------

def _print_findings(found: list[dict], stream) -> None:
    for f in found:
        print(f"[{f['severity'].upper()}] {f['code']} [{f['node']}] {f['message']}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("check", "validate presupuesto.json"),
                       ("sync-cadena", "write each activity's costo into cadena_valor.json"),
                       ("render", "write sections 13 and 30"),
                       ("resumen", "totals and live-check percentages"),
                       ("datos", "money part of datos_sgr")):
        p = sub.add_parser(name, help=text)
        p.add_argument("run_root", type=Path)
        if name in ("check", "resumen", "datos"):
            p.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)
    run = args.run_root.resolve()

    try:
        if args.command == "render":
            written, note = render_sections(run)
            for path in written:
                print(f"SECCION: {path}")
            if note:
                print(f"nota: {note}", file=sys.stderr)
            return 0
        if args.command == "sync-cadena":
            print(f"CADENA: {sync_cadena(run)}")
            return 0
    except RenderRefused as exc:
        what = "no se generan las secciones" if args.command == "render" else "no se sincroniza la cadena de valor"
        print(f"error: presupuesto.json tiene hallazgos de error; {what}.", file=sys.stderr)
        _print_findings(exc.errors, sys.stderr)
        return 1
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "datos":
        print(json.dumps(datos(run), ensure_ascii=False, indent=2))
        return 0
    if not (run / BUDGET_FILE).is_file():
        print(f"error: no existe {BUDGET_FILE.as_posix()}", file=sys.stderr)
        return 2
    if args.command == "resumen":
        summary = resumen(run)
        if summary is None:
            print(f"error: {BUDGET_FILE.as_posix()} no es JSON válido", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(f"Total SGR: {_plain_money(summary['total_sgr'])}")
            print(f"Contrapartida en especie: {_plain_money(summary['total_especie'])}")
            print(f"Contrapartida en efectivo: {_plain_money(summary['total_efectivo'])}")
            print(f"Total del proyecto: {_plain_money(summary['total'])}")
            for key, label in (("cofinanciacion_pct", "Cofinanciación"), ("transferencia_pct", "Transferencia"),
                               ("movilidad_pct", "Movilidad")):
                value = summary[key]
                print(f"{label}: {'n/a' if value is None else _plain_pct(value)}")
        return 0
    found = check_findings(run)
    errors = sum(1 for f in found if f["severity"] == "error")
    if args.json:
        print(json.dumps({"findings": found}, ensure_ascii=False, indent=2))
    else:
        _print_findings(found, sys.stdout)
        print(f"presupuesto: {errors} errores, {len(found) - errors} avisos")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
