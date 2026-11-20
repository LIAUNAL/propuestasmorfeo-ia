#!/usr/bin/env python3
"""SGR products, human talent and indicators as data: check, render and judge facts (flujo SGR only).

`artefactos/sgr/productos.json` (schema `morfeo.productos-sgr/v1`) holds the
human talent to be linked, the CTeI products (the call minimum and the
additional ones), the public science dissemination strategy and the
management indicators of an SGR project:

    {schema,
     talento:[{categoria:"joven_investigador"|"maestria"|"doctorado"|"posdoctorado"|"profesional"|"tecnico"|"otro",
               cantidad:int, entidad:"E1", perfil, formacion, actividades:["1.1.1"], duracion_meses:int|null,
               valor_mensual:number|null, producto_final}],
     productos_ctei:[{tipo:"nuevo_conocimiento"|"desarrollo_tecnologico"|"apropiacion_social"|"formacion",
                      subtipo, categoria:"TOP"|"A"|"B"|"otro"|null, cantidad:int, adicional:bool,
                      producto_cadena:"1.1"|null, descripcion}],
     divulgacion:{introduccion, publicos:[str], medios:[str], productos:[str], responsable:"E1"|null,
                  cronograma:[{mes, accion}], costeada:bool}|null,
     indicadores_gestion:[{indicador, codigo|null, meta, unidad, formula, tipo_fuente, periodicidad}]}

The product indicators are read from artefactos/sgr/cadena_valor.json
(`codigo_dnp`, `indicador`, `unidad`, `meta` of each product), never duplicated
here. The call minimums come from the rubric of the run (juez_sgr.resolve_rubric):
`minimos_talento` [{categoria, cantidad, texto}] is the minimum number of people
per talent category, and `minimo_productos` [{categoria, cantidad, texto}] the
number of CTeI products (new knowledge or technological development) each
person of that category delivers; `texto` is the TdR sentence, verbatim. The
CTeI minimum is the sum, over `minimo_productos`, of `cantidad` times the
people linked in that category (never fewer than its minimum). Only new
knowledge and technological development products count for the minimum and
for the Conv 54 criterion 2.5 (social appropriation products are scored in
2.4).

Commands:
  check RUN_ROOT [--json]
      Findings with check_run's shape {severity, code, message, node}, codes
      prefixed `productos-`, and the criterion 2.5 preview; a missing file is
      an error here. --json prints {"findings": [...], "vista_2_5": {...}}.
  render RUN_ROOT
      Write redaccion/sections/36_talento_humano.tex (Anexo 2 caps. 20 and
      12.4), 37_indicadores.tex (caps. 24 and 25) and 15_productos_esperados.tex
      (cap. 21: products by objective with their DNP code, CTeI products and
      the dissemination strategy) deterministically. SGR runs only (a base
      run's §15 is never touched); refuses while there are error findings.
  datos RUN_ROOT [--json]
      {productos_adicionales:{total, top_o_a, fuente}|null, talento:{categoria: cantidad}|null, fuente}:
      the facts the judge copies into datos_sgr.json.

Rules (codes): productos-esquema, productos-json-invalido, productos-bloque-faltante,
productos-entidad-desconocida, productos-actividad-desconocida,
productos-producto-desconocido, productos-talento-categoria, productos-ctei-tipo,
productos-valor-invalido, productos-mes-fuera (errors); productos-cadena-incompleta
(a value-chain product without a DNP code `^39\\d{5}$`, indicator, unit or goal),
productos-cadena-faltante, productos-alianza-faltante (warnings);
productos-talento-minimo and productos-minimo-ctei (errors, with a rubric);
productos-talento-presupuesto (warning: a talent entry with value and duration
has no `talento_humano` item of the same entity and value in presupuesto.json,
when the budget exists); productos-divulgacion-faltante and
productos-divulgacion-incompleta (warnings); productos-indicadores-gestion
(warning: no supervision or technical and financial report indicator with
its periodicity).

Criterion 2.5 preview (Conv 54): A is 3 with three or more additional products,
two of them TOP or A; 2 with two additional, one TOP or A; 1 with one
additional of any type. B is 2 for a dissemination strategy with audiences,
media, products, responsible and schedule, costed; 1 when it is incomplete;
0 without it.

Exit codes: 0 ok, 1 error findings (check, render), 2 bad input.
Standard library only. The value chain comes from
artefactos/sgr/cadena_valor.json, the entities from artefactos/sgr/alianza.json,
the budget items from presupuesto_sgr.py, the LaTeX escaping from
cadena_valor_sgr.py, the flow from check_run.py, the TdR chapters from
ensamblar_main.py and the call's rubric from juez_sgr.py (all in this folder,
imported defensively). check_run imports `findings`; the dashboard imports
`findings` and `datos`.
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SCHEMA = "morfeo.productos-sgr/v1"
PRODUCTS_FILE = Path("artefactos") / "sgr" / "productos.json"
CHAIN_FILE = Path("artefactos") / "sgr" / "cadena_valor.json"
ALLIANCE_FILE = Path("artefactos") / "sgr" / "alianza.json"
BUDGET_FILE = Path("artefactos") / "sgr" / "presupuesto.json"
STRUCTURE_FILE = Path("artefactos") / "estructura_tdr.json"
SECTIONS_DIR = Path("redaccion") / "sections"
GENERATED_HEADER = "% GENERADO por scripts/productos_sgr.py"
HERE = Path(__file__).resolve().parent

TALENT_STEM = "36_talento_humano"
INDICATORS_STEM = "37_indicadores"
PRODUCTS_STEM = "15_productos_esperados"

CATEGORIES = {
    "joven_investigador": "Jóvenes Investigadores e Innovadores",
    "maestria": "Estudiantes de maestría",
    "doctorado": "Estudiantes de doctorado",
    "posdoctorado": "Doctor en estancia posdoctoral",
    "profesional": "Profesional",
    "tecnico": "Técnico",
    "otro": "Otro",
}
TYPES = {
    "nuevo_conocimiento": "Generación de nuevo conocimiento",
    "desarrollo_tecnologico": "Desarrollo tecnológico e innovación",
    "apropiacion_social": "Apropiación social del conocimiento",
    "formacion": "Formación de recurso humano",
}
SCORED_TYPES = ("nuevo_conocimiento", "desarrollo_tecnologico")
CTEI_CATEGORIES = ("TOP", "A", "B", "otro")
TOP_OR_A = ("TOP", "A")
DNP_RE = re.compile(r"^39\d{5}$")
SUPERVISION_RE = re.compile(r"\bsupervisi[óo]n\b", re.I)
REPORTS_RE = re.compile(r"\bt[ée]cnic\w*\b.{0,40}\bfinancier\w*|\bfinancier\w*\b.{0,40}\bt[ée]cnic\w*", re.I)
PRODUCT_INDICATORS_RE = re.compile(r"indicadores\s+de\s+producto", re.I)


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
    spec = importlib.util.spec_from_file_location(f"_productos_{name}", path)
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


def _plain_money(value) -> str:
    return "$" + f"{round(value):,}".replace(",", ".")


def _plain(value) -> str:
    """A goal or quantity as written: integers without decimals, a decimal comma otherwise."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, float):
        return f"{value:g}".replace(".", ",")
    return _text(value)


# --- Context: value chain, alliance, rubric ---------------------------------------

def _chain_objectives(chain) -> list[dict]:
    return _dicts(chain.get("objetivos")) if isinstance(chain, dict) else []


def _chain_products(chain) -> dict[str, dict] | None:
    """{product code: product} of the value chain in its order, or None without it."""
    if not isinstance(chain, dict):
        return None
    return {_text(p.get("codigo")): p for o in _chain_objectives(chain) for p in _dicts(o.get("productos"))
            if _text(p.get("codigo"))}


def _chain_activities(chain) -> dict[str, dict] | None:
    if not isinstance(chain, dict):
        return None
    return {_text(a.get("codigo")): a for o in _chain_objectives(chain) for p in _dicts(o.get("productos"))
            for a in _dicts(p.get("actividades")) if _text(a.get("codigo"))}


def _entities(alliance) -> dict[str, dict] | None:
    if not isinstance(alliance, dict):
        return None
    return {_text(e.get("id")): e for e in _dicts(alliance.get("entidades")) if _text(e.get("id"))}


def _duration(chain, alliance, budget):
    for source in (chain, alliance, budget):
        if isinstance(source, dict) and _int(source.get("duracion_meses")) and source["duracion_meses"] > 0:
            return source["duracion_meses"]
    return None


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


def _minimums(rubric, key: str) -> list[dict]:
    """[{categoria, cantidad, texto}] of the rubric's `key`, skipping malformed entries."""
    if not isinstance(rubric, dict):
        return []
    return [m for m in _dicts(rubric.get(key)) if _text(m.get("categoria")) and _int(m.get("cantidad")) is not None]


def _talent_counts(data: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in _dicts(data.get("talento")):
        category, quantity = _text(entry.get("categoria")), _int(entry.get("cantidad"))
        if category and quantity is not None and quantity > 0:
            counts[category] = counts.get(category, 0) + quantity
    return counts


def _ctei_counts(data: dict) -> dict[str, int]:
    """Minimum and additional new-knowledge and technological-development products, and the TOP/A ones."""
    out = {"minimo": 0, "adicionales": 0, "top_o_a": 0}
    for product in _dicts(data.get("productos_ctei")):
        quantity = _int(product.get("cantidad"))
        if product.get("tipo") not in SCORED_TYPES or quantity is None or quantity < 1:
            continue
        if product.get("adicional") is True:
            out["adicionales"] += quantity
            if product.get("categoria") in TOP_OR_A:
                out["top_o_a"] += quantity
        elif product.get("adicional") is False:
            out["minimo"] += quantity
    return out


def _dissemination_gaps(block) -> list[str]:
    """What a dissemination strategy lacks to be complete and costed (rubric 2.5 B)."""
    missing = [label for key, label in (("publicos", "públicos"), ("medios", "medios"), ("productos", "productos"))
               if not _texts(block.get(key))]
    if not _text(block.get("responsable")):
        missing.append("responsable")
    if not any(_text(item.get("accion")) and item.get("mes") is not None for item in _dicts(block.get("cronograma"))):
        missing.append("cronograma")
    if block.get("costeada") is not True:
        missing.append("costeada")
    return missing


def _load(run: Path) -> dict:
    out: dict = {"errores": []}
    data, error = _read_json(run / PRODUCTS_FILE)
    if error:
        out["errores"].append(_finding("error", "productos-json-invalido", "productos",
                                       f"{PRODUCTS_FILE.as_posix()} no es JSON válido: {error}"))
    out["productos"] = data
    out["cadena"], _ = _read_json(run / CHAIN_FILE)
    out["alianza"], _ = _read_json(run / ALLIANCE_FILE)
    out["presupuesto"], _ = _read_json(run / BUDGET_FILE)
    return out


# --- Check ----------------------------------------------------------------------

class _Rules:
    """The rules of productos.json (odd/tasks/sgr-productos-indicadores.md, Contracts)."""

    def __init__(self, run: Path, data: dict, chain, alliance, budget) -> None:
        self.run = run
        self.data = data
        self.chain = chain if isinstance(chain, dict) else None
        self.products = _chain_products(chain)
        self.activity_index = _chain_activities(chain)
        self.entities = _entities(alliance)
        self.budget = budget if isinstance(budget, dict) else None
        self.duration = _duration(chain, alliance, budget)
        self.out: list[dict] = []

    def add(self, severity: str, code: str, node: str, message: str) -> None:
        self.out.append(_finding(severity, code, node, message))

    def activities(self, node: str, codes) -> None:
        if self.activity_index is None:
            return
        unknown = [c for c in _codes(codes) if c not in self.activity_index]
        if unknown:
            self.add("error", "productos-actividad-desconocida", node,
                     f"{node} cita actividades que no están en la cadena de valor: {', '.join(unknown)}.")

    def entity(self, node: str, eid) -> None:
        if self.entities is None or not _text(eid):
            return
        if _text(eid) not in self.entities:
            self.add("error", "productos-entidad-desconocida", node,
                     f"{node} cita la entidad «{eid}», que no está en {ALLIANCE_FILE.as_posix()}.")

    def month(self, node: str, value) -> None:
        month = _int(value)
        if month is None or month < 1 or (self.duration is not None and month > self.duration):
            limit = f"entre 1 y {self.duration}" if self.duration is not None else "un entero mayor que 0"
            self.add("error", "productos-mes-fuera", node,
                     f"{node} tiene el mes «{value}»; debe ser {limit} (duración del proyecto).")

    def run_all(self) -> list[dict]:
        if self.chain is None:
            self.add("warning", "productos-cadena-faltante", "productos",
                     f"No se encontró {CHAIN_FILE.as_posix()}: no se cotejan actividades, productos ni indicadores "
                     "de producto.")
        if self.entities is None:
            self.add("warning", "productos-alianza-faltante", "productos",
                     f"No se encontró {ALLIANCE_FILE.as_posix()}: no se cotejan las entidades.")
        blocks_ok = True
        for key in ("talento", "productos_ctei", "indicadores_gestion"):
            if not isinstance(self.data.get(key), list):
                self.add("error", "productos-bloque-faltante", key, f"productos.json no tiene la lista «{key}».")
                blocks_ok = False
        if "divulgacion" not in self.data or not (self.data["divulgacion"] is None
                                                  or isinstance(self.data["divulgacion"], dict)):
            self.add("error", "productos-bloque-faltante", "divulgacion",
                     "productos.json necesita «divulgacion» (un objeto, o null mientras no exista la estrategia).")
        self.chain_products()
        self.talent()
        self.ctei()
        self.dissemination()
        self.management()
        if blocks_ok:
            self.minimums()
            self.budget_match()
        return self.out

    # Value chain products ------------------------------------------------------------
    def chain_products(self) -> None:
        for code, product in (self.products or {}).items():
            missing = []
            if not DNP_RE.match(_text(product.get("codigo_dnp"))):
                missing.append("código DNP (39 y cinco dígitos)")
            missing += [label for key, label in (("indicador", "indicador"), ("unidad", "unidad"))
                        if not _text(product.get(key))]
            if product.get("meta") is None or not _text(product.get("meta")):
                missing.append("meta")
            if missing:
                self.add("warning", "productos-cadena-incompleta", code,
                         f"El producto {code} de la cadena de valor no tiene {', '.join(missing)}; los indicadores de "
                         "producto (§37) y §15 salen de la cadena de valor.")

    # Talent ------------------------------------------------------------------------
    def talent(self) -> None:
        for n, entry in enumerate(_list(self.data.get("talento")), start=1):
            node = f"talento[{n}]"
            if not isinstance(entry, dict):
                self.add("error", "productos-valor-invalido", node, f"{node} no es un objeto.")
                continue
            category = entry.get("categoria")
            if category not in CATEGORIES:
                self.add("error", "productos-talento-categoria", node,
                         f"La categoría «{category}» no es válida; las categorías son {', '.join(CATEGORIES)}.")
            invalid = []
            quantity = _int(entry.get("cantidad"))
            if quantity is None or quantity < 1:
                invalid.append("cantidad (entero mayor que 0)")
            months = entry.get("duracion_meses")
            if months is not None and (_int(months) is None or months < 1):
                invalid.append("duracion_meses (entero mayor que 0 o null)")
            value = entry.get("valor_mensual")
            if value is not None and (_number(value) is None or value < 0):
                invalid.append("valor_mensual (número mayor o igual que 0 o null)")
            if invalid:
                self.add("error", "productos-valor-invalido", node, f"{node} tiene valores inválidos: {', '.join(invalid)}.")
            elif _int(months) and self.duration is not None and months > self.duration:
                self.add("error", "productos-mes-fuera", node,
                         f"{node} dura {months} meses; la vinculación no puede exceder el plazo del proyecto "
                         f"({self.duration} meses).")
            self.entity(node, entry.get("entidad"))
            self.activities(node, entry.get("actividades"))

    # CTeI products -------------------------------------------------------------------
    def ctei(self) -> None:
        for n, product in enumerate(_list(self.data.get("productos_ctei")), start=1):
            node = f"productos_ctei[{n}]"
            if not isinstance(product, dict):
                self.add("error", "productos-valor-invalido", node, f"{node} no es un objeto.")
                continue
            if product.get("tipo") not in TYPES:
                self.add("error", "productos-ctei-tipo", node,
                         f"El tipo «{product.get('tipo')}» no es válido; los tipos son {', '.join(TYPES)}.")
            category = product.get("categoria")
            if category is not None and category not in CTEI_CATEGORIES:
                self.add("error", "productos-ctei-tipo", node,
                         f"La categoría «{category}» no es válida; las categorías son {', '.join(CTEI_CATEGORIES)} "
                         "o null.")
            invalid = []
            quantity = _int(product.get("cantidad"))
            if quantity is None or quantity < 1:
                invalid.append("cantidad (entero mayor que 0)")
            if not isinstance(product.get("adicional"), bool):
                invalid.append("adicional (true o false)")
            if invalid:
                self.add("error", "productos-valor-invalido", node, f"{node} tiene valores inválidos: {', '.join(invalid)}.")
            code = _text(product.get("producto_cadena"))
            if code and self.products is not None and code not in self.products:
                self.add("error", "productos-producto-desconocido", node,
                         f"{node} cita el producto «{code}», que no está en la cadena de valor.")

    # Dissemination ---------------------------------------------------------------------
    def dissemination(self) -> None:
        block = self.data.get("divulgacion")
        if block is None:
            self.add("warning", "productos-divulgacion-faltante", "divulgacion",
                     "No hay estrategia de divulgación pública de la ciencia; sin ella el componente B del criterio "
                     "2.5 vale 0 puntos.")
            return
        if not isinstance(block, dict):
            return
        self.entity("divulgacion", block.get("responsable"))
        for n, item in enumerate(_dicts(block.get("cronograma")), start=1):
            self.month(f"divulgacion.cronograma[{n}]", item.get("mes"))
        missing = _dissemination_gaps(block)
        if missing:
            self.add("warning", "productos-divulgacion-incompleta", "divulgacion",
                     f"A la estrategia de divulgación le falta: {', '.join(missing)}; solo una estrategia «con "
                     "públicos, medios, productos, responsable y cronograma definidos y costeados» vale 2 puntos "
                     "(criterio 2.5 B); incompleta vale 1.")

    # Management indicators ---------------------------------------------------------------
    def management(self) -> None:
        indicators = _dicts(self.data.get("indicadores_gestion"))
        missing = []
        for pattern, label in ((SUPERVISION_RE, "informes de supervisión"),
                               (REPORTS_RE, "informes técnicos y financieros")):
            if not any(pattern.search(_text(i.get("indicador"))) and _text(i.get("periodicidad")) for i in indicators):
                missing.append(label)
        if missing:
            self.add("warning", "productos-indicadores-gestion", "indicadores_gestion",
                     f"Faltan indicadores de gestión con su periodicidad: {'; '.join(missing)} (la plantilla pide "
                     "informes de gestión trimestrales).")

    # Call minimums and budget ---------------------------------------------------------------
    def minimums(self) -> None:
        rubric = _rubric(self.run)
        talent_minimums = _minimums(rubric, "minimos_talento")
        counts = _talent_counts(self.data)
        for minimum in talent_minimums:
            category = _text(minimum["categoria"])
            have = counts.get(category, 0)
            if have < minimum["cantidad"]:
                label = CATEGORIES.get(category, category)
                self.add("error", "productos-talento-minimo", "talento",
                         f"El talento vincula {have} en la categoría «{label}»; la convocatoria exige como mínimo: "
                         f"«{_text(minimum.get('texto'))}»")
        floor = {_text(m["categoria"]): m["cantidad"] for m in talent_minimums}
        required = sum(m["cantidad"] * max(counts.get(_text(m["categoria"]), 0), floor.get(_text(m["categoria"]), 0))
                       for m in _minimums(rubric, "minimo_productos"))
        have = _ctei_counts(self.data)["minimo"]
        if required and have < required:
            self.add("error", "productos-minimo-ctei", "productos_ctei",
                     f"Los productos de CTeI del mínimo de la convocatoria (nuevo conocimiento o desarrollo "
                     f"tecnológico, adicional: false) suman {have}; el talento vinculado exige {required} según "
                     "las orientaciones de vinculación de talento humano del TdR.")

    def budget_match(self) -> None:
        if self.budget is None:
            return
        try:
            module = _sibling("presupuesto_sgr")
            if module is None:
                return
            items = [(_text(item.get("entidad")), module.item_value(item, self.budget))
                     for item in _dicts(self.budget.get("items")) if item.get("rubro") == "talento_humano"]
        except Exception:  # the budget is optional context: its own checks report its problems
            return
        for n, entry in enumerate(_list(self.data.get("talento")), start=1):
            if not isinstance(entry, dict):
                continue
            quantity, value, months = _int(entry.get("cantidad")), _number(entry.get("valor_mensual")), \
                _int(entry.get("duracion_meses"))
            if not quantity or quantity < 1 or value is None or value < 0 or not months or months < 1:
                continue
            expected = int((Decimal(quantity) * Decimal(str(value)) * Decimal(months))
                           .quantize(Decimal(1), rounding=ROUND_HALF_UP))
            eid = _text(entry.get("entidad"))
            if any(entity == eid and abs(amount - expected) <= 1 for entity, amount in items):
                continue
            label = CATEGORIES.get(entry.get("categoria"), _text(entry.get("categoria")))
            self.add("warning", "productos-talento-presupuesto", f"talento[{n}]",
                     f"El talento «{label}» de {eid} vale {_plain_money(expected)} ({quantity} × "
                     f"{_plain_money(value)} × {months} meses) y ningún ítem de talento humano de esa entidad en "
                     f"{BUDGET_FILE.as_posix()} tiene ese valor (Fase 6.4).")


def products_findings(data, run: Path, chain, alliance, budget) -> list[dict]:
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return [_finding("error", "productos-esquema", "productos", f"El archivo no declara el esquema {SCHEMA}.")]
    return _Rules(run, data, chain, alliance, budget).run_all()


def findings(run_root: Path) -> list[dict]:
    """Findings of productos.json; [] when it does not exist."""
    run = Path(run_root)
    if not (run / PRODUCTS_FILE).is_file():
        return []
    data = _load(run)
    if data["errores"]:
        return data["errores"]
    return products_findings(data["productos"], run, data["cadena"], data["alianza"], data["presupuesto"])


def check_findings(run_root: Path) -> list[dict]:
    """findings() plus an error when the file is missing (the CLI `check` and `render`)."""
    run = Path(run_root)
    if not (run / PRODUCTS_FILE).is_file():
        return [_finding("error", "productos-archivo-faltante", "productos", f"No existe {PRODUCTS_FILE.as_posix()}.")]
    return findings(run)


# --- Preview and judge facts -------------------------------------------------------

def _products_data(run: Path) -> dict | None:
    data, _ = _read_json(run / PRODUCTS_FILE)
    return data if isinstance(data, dict) else None


def vista_2_5(run_root: Path) -> dict:
    """{A, B, total, adicionales, top_o_a}: the Conv 54 criterion 2.5 preview (advisory, never a score)."""
    data = _products_data(Path(run_root)) or {}
    counts = _ctei_counts(data)
    extra, top = counts["adicionales"], counts["top_o_a"]
    a = 3 if extra >= 3 and top >= 2 else 2 if extra >= 2 and top >= 1 else 1 if extra >= 1 else 0
    block = data.get("divulgacion")
    b = 0 if not isinstance(block, dict) else 1 if _dissemination_gaps(block) else 2
    return {"A": a, "B": b, "total": a + b, "adicionales": extra, "top_o_a": top}


def datos(run_root: Path) -> dict:
    """{productos_adicionales, talento, fuente}: the products and talent facts of datos_sgr."""
    out: dict = {"productos_adicionales": None, "talento": None, "fuente": []}
    data = _products_data(Path(run_root))
    if data is None:
        return out
    source = PRODUCTS_FILE.as_posix()
    counts = _ctei_counts(data)
    out["productos_adicionales"] = {"total": counts["adicionales"], "top_o_a": counts["top_o_a"],
                                    "fuente": f"{source} (productos_ctei)"}
    out["talento"] = _talent_counts(data)
    out["fuente"].append(source)
    return out


# --- Render -------------------------------------------------------------------------

def _escape(text) -> str:
    return _sibling("cadena_valor_sgr").escape(text)


def _money(value) -> str:
    return r"\$\," + f"{round(value):,}".replace(",", ".")


def _placement(run: Path, stem: str) -> tuple[str, str | None, dict | None]:
    """("section", TdR title|None, next chapter|None) when the file opens its TdR chapter or no structure
    applies; ("sub", None, next chapter|None) when another file of the chapter opens it (ensamblar_main)."""
    structure, _ = _read_json(run / STRUCTURE_FILE)
    assembler = _sibling("ensamblar_main")
    if not isinstance(structure, dict) or assembler is None:
        return "section", None, None
    try:
        assembler.validate(structure)
    except assembler.InputError:
        return "section", None, None
    chapters = assembler.placed_chapters(structure, "sgr")
    for n, chapter in enumerate(chapters):
        files = [f for f in chapter["archivos"] if not f.startswith("diag_")]
        if stem in files:
            following = chapters[n + 1] if n + 1 < len(chapters) else None
            mode = ("section", chapter.get("titulo")) if files[0] == stem else ("sub", None)
            return mode[0], mode[1], following
    return "section", None, None


def _header(sources: str) -> list[str]:
    return [
        GENERATED_HEADER,
        f"% Fuente: {sources}. No se edita a mano: se regenera con",
        "% python3 scripts/productos_sgr.py render <RUN_ROOT>.",
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


def _paragraph(text) -> list[str]:
    return ["", _escape(text)] if _text(text) else []


def _cell(value, empty: str = "Por definir") -> str:
    return _escape(_plain(value)) if _text(value) else empty


def _items(values, empty: str = "Por definir") -> str:
    items = [_escape(v) for v in _texts(values)]
    return r"\newline ".join(items) if items else empty


def _months(start, end) -> str:
    start, end = _int(start), _int(end)
    if start is None or end is None:
        return ""
    return f" (mes {start})" if start == end else f" (meses {start} a {end})"


class _Renderer:
    def __init__(self, run: Path, data: dict, chain, alliance) -> None:
        self.run = run
        self.data = data
        self.chain = chain if isinstance(chain, dict) else {}
        self.products = _chain_products(chain) or {}
        self.activity_index = _chain_activities(chain) or {}
        self.entities = _entities(alliance) or {}

    def entity(self, eid) -> str:
        if not _text(eid):
            return "Por definir"
        entity = self.entities.get(_text(eid))
        return _escape(_text(entity.get("nombre")) if entity and _text(entity.get("nombre")) else eid)

    def activities_with_months(self, codes) -> str:
        names = []
        for code in _codes(codes):
            activity = self.activity_index.get(code) or {}
            name = _text(activity.get("nombre"))
            names.append(_escape(f"{code} {name}" if name else code)
                         + _months(activity.get("mes_inicio"), activity.get("mes_fin")))
        return r"\newline ".join(names) if names else "Por definir"

    def product_name(self, code) -> str:
        product = self.products.get(_text(code))
        if product is None:
            return _escape(code) if _text(code) else "No aplica"
        return _escape(" ".join(v for v in (_text(code), _text(product.get("nombre"))) if v))

    # 36 --------------------------------------------------------------------------
    def talent(self) -> str:
        mode, title, _ = _placement(self.run, TALENT_STEM)
        lines = _header(f"{PRODUCTS_FILE.as_posix()}, {CHAIN_FILE.as_posix()} y {ALLIANCE_FILE.as_posix()}")
        default = "Vinculación de talento humano"
        if mode == "section":
            lines += [rf"\section{{{_escape(title or default)}}}", r"\label{sec:talento_humano}"]
        else:
            lines += [rf"\subsection{{{default}}}", r"\label{sec:talento_humano}"]
        talent = _dicts(self.data.get("talento"))
        rows = []
        for entry in talent:
            months = _int(entry.get("duracion_meses"))
            value = _number(entry.get("valor_mensual"))
            rows.append([_escape(CATEGORIES.get(entry.get("categoria"), _text(entry.get("categoria")))),
                         _cell(entry.get("cantidad")), self.entity(entry.get("entidad")),
                         ("1 mes" if months == 1 else f"{months} meses") if months else "Por definir",
                         _money(value) if value is not None else "Por definir", _cell(entry.get("producto_final"))])
        lines += _table(f"{_col('0.17')} {_col('0.07', 'centering')} {_col('0.18')} {_col('0.09')} "
                        f"{_col('0.11', 'raggedleft')} {_X}",
                        ["Categoría", "Cantidad", "Entidad que vincula", "Duración", "Valor mensual", "Producto final"],
                        rows, "Talento humano a vincular: categoría, cantidad, entidad, duración, valor mensual y "
                              "producto final.", "talento_humano")
        minimums = _minimums(_rubric(self.run), "minimos_talento")
        if minimums:
            counts = _talent_counts(self.data)
            parts = [f"{_escape(CATEGORIES.get(_text(m['categoria']), _text(m['categoria'])))}: "
                     f"{counts.get(_text(m['categoria']), 0)} de {m['cantidad']} exigidos" for m in minimums]
            met = all(counts.get(_text(m["categoria"]), 0) >= m["cantidad"] for m in minimums)
            lines += ["", rf"\noindent Mínimos de la convocatoria: {'; '.join(parts)}. "
                          + ("Se cumplen todos." if met else "No se cumplen todos.")]
        lines += ["", r"\subsection{Descripción de perfiles, actividades y plan de trabajo del talento humano a "
                      r"vincular}"]
        rows = [[_cell(e.get("perfil")), self.entity(e.get("entidad")), _cell(e.get("formacion")),
                 self.activities_with_months(e.get("actividades")), _cell(e.get("producto_final"))] for e in talent]
        lines += _table(f"{_col('0.17')} {_col('0.15')} {_X} {_X} {_col('0.17')}",
                        ["Perfil", "Entidad que lo vincula", "Formación y experiencia", "Actividades y meses",
                         "Producto final"], rows,
                        "Perfiles, actividades y plan de trabajo del talento humano a vincular.", "talento_perfiles")
        return "\n".join(lines + [""])

    # 37 --------------------------------------------------------------------------
    def indicators(self) -> str:
        mode, title, following = _placement(self.run, INDICATORS_STEM)
        lines = _header(f"{PRODUCTS_FILE.as_posix()} y {CHAIN_FILE.as_posix()}")
        if mode == "section" and title:
            lines += [rf"\section{{{_escape(title)}}}", r"\label{sec:indicadores}"]
        elif mode == "section":
            lines += [r"\section{Indicadores de gestión y de producto}", r"\label{sec:indicadores}", "",
                      r"\subsection{Indicadores de gestión}"]
        else:
            lines += [r"\subsection{Indicadores de gestión}", r"\label{sec:indicadores}"]
        rows = []
        for indicator in _dicts(self.data.get("indicadores_gestion")):
            goal = " / ".join(v for v in (_text(indicator.get("unidad")), _plain(indicator.get("meta"))) if v)
            rows.append([_cell(indicator.get("indicador")), _escape(goal) if goal else "Por definir",
                         _cell(indicator.get("codigo"), "No aplica"), _cell(indicator.get("formula")),
                         _cell(indicator.get("tipo_fuente")), _cell(indicator.get("periodicidad"))])
        lines += _table(f"{_X} {_col('0.11')} {_col('0.09')} {_col('0.2')} {_col('0.13')} {_col('0.11')}",
                        ["Indicador", "Medida/Meta", "Código", "Fórmula", "Tipo de fuente", "Periodicidad"], rows,
                        "Indicadores de gestión del proyecto.", "indicadores_gestion")
        files = [f for f in (following or {}).get("archivos", []) if not f.startswith("diag_")]
        if following and not files and PRODUCT_INDICATORS_RE.search(following.get("titulo") or ""):
            lines += ["", rf"\section{{{_escape(following['titulo'])}}}", r"\label{sec:indicadores_producto}"]
        else:
            lines += ["", r"\subsection{Indicadores de producto}"]
        rows = [[self.product_name(code), _cell(p.get("codigo_dnp")), _cell(p.get("indicador")),
                 _cell(p.get("unidad")), _cell(p.get("meta"))] for code, p in self.products.items()]
        lines += _table(f"{_col('0.25')} {_col('0.1')} {_X} {_col('0.12')} {_col('0.08', 'centering')}",
                        ["Producto", "Código DNP", "Indicador de producto", "Unidad de medida", "Meta"], rows,
                        "Indicadores de producto de la cadena de valor.", "indicadores_producto")
        return "\n".join(lines + [""])

    # 15 --------------------------------------------------------------------------
    def products_section(self) -> str:
        mode, title, _ = _placement(self.run, PRODUCTS_STEM)
        lines = _header(f"{PRODUCTS_FILE.as_posix()}, {CHAIN_FILE.as_posix()} y {ALLIANCE_FILE.as_posix()}")
        default = "Productos esperados"
        if mode == "section":
            lines += [rf"\section{{{_escape(title or default)}}}", r"\label{sec:productos_esperados}"]
        else:
            lines += [rf"\subsection{{{default}}}", r"\label{sec:productos_esperados}"]
        ctei = _dicts(self.data.get("productos_ctei"))
        lines += ["", r"\subsection{Productos por objetivo específico}"]
        rows: list = []
        for objective in _chain_objectives(self.chain):
            label = ": ".join(v for v in (_text(objective.get("id")), _text(objective.get("texto"))) if v)
            rows.append(rf"\multicolumn{{6}}{{p{{0.95\textwidth}}}}{{\textbf{{{_escape(label)}}}}} \\")
            for product in _dicts(objective.get("productos")):
                code, dnp = _text(product.get("codigo")), _text(product.get("codigo_dnp"))
                linked = [_escape(p.get("descripcion")) for p in ctei
                          if _text(p.get("producto_cadena")) == code and _text(p.get("descripcion"))]
                description = r"\newline ".join(linked) if linked else (
                    f"Meta: {_escape(_plain(product.get('meta')))}" if _text(product.get("meta")) else "Por definir")
                valid = bool(DNP_RE.match(dnp))
                rows.append([dnp[:4] if valid else "Por definir",
                             _escape(f"{dnp} {_text(product.get('nombre'))}" if valid else product.get("nombre") or ""),
                             _cell(product.get("medido_a_traves_de")), _cell(product.get("indicador")),
                             _cell(product.get("unidad")), description])
        lines += _table(f"{_col('0.07')} {_col('0.2')} {_col('0.15')} {_col('0.17')} {_col('0.09')} {_X}",
                        ["Programa", "Producto", "Medido a través de", "Indicador de producto", "Unidad de medida",
                         "Descripción"], rows,
                        "Productos por objetivo específico, del catálogo de productos del DNP.", "productos_cadena")
        if ctei:
            lines += ["", r"\subsection{Productos de ciencia, tecnología e innovación}"]
            rows = [[_escape(TYPES.get(p.get("tipo"), _text(p.get("tipo")))), _cell(p.get("subtipo")),
                     _cell(p.get("categoria"), "Sin categoría"), _cell(p.get("cantidad")),
                     self.product_name(p.get("producto_cadena")),
                     "Adicional" if p.get("adicional") is True else "Mínimo de la convocatoria",
                     _cell(p.get("descripcion"))] for p in ctei]
            lines += _table(f"{_col('0.14')} {_col('0.16')} {_col('0.08', 'centering')} {_col('0.07', 'centering')} "
                            f"{_col('0.15')} {_col('0.11')} {_X}",
                            ["Tipo", "Subtipo", "Categoría", "Cantidad", "Producto de la cadena", "Compromiso",
                             "Descripción"], rows,
                            "Productos de ciencia, tecnología e innovación: mínimo de la convocatoria y adicionales.",
                            "productos_ctei")
            counts = _ctei_counts(self.data)
            lines += ["", rf"\noindent Total de productos adicionales al mínimo de la convocatoria: "
                          rf"{counts['adicionales']}, de ellos {counts['top_o_a']} de tipo TOP o A."]
        block = self.data.get("divulgacion")
        if isinstance(block, dict):
            lines += ["", r"\subsection{Estrategia de divulgación pública de la ciencia}"]
            lines += _paragraph(block.get("introduccion"))
            rows = [[_items(block.get("publicos")), _items(block.get("medios")), _items(block.get("productos")),
                     self.entity(block.get("responsable")), "Sí" if block.get("costeada") is True else "No"]]
            lines += _table(f"{_X} {_X} {_X} {_col('0.17')} {_col('0.08', 'centering')}",
                            ["Públicos", "Medios", "Productos", "Responsable", "Costeada"], rows,
                            "Estrategia de divulgación pública de la ciencia.", "divulgacion")
            rows = [[_cell(item.get("mes")), _cell(item.get("accion"))] for item in _dicts(block.get("cronograma"))]
            lines += _table(f"{_col('0.08', 'centering')} {_X}", ["Mes", "Acción"], rows,
                            "Cronograma de la estrategia de divulgación pública de la ciencia.", "divulgacion_cronograma")
        return "\n".join(lines + [""])


def _flujo(run: Path) -> str:
    module = _sibling("check_run")
    return module.detect_flujo(run) if module is not None else "base"


def render_sections(run_root: Path) -> list[Path]:
    """Write sections 36, 37 and §15; refuses outside the SGR flow and while there are error findings."""
    run = Path(run_root)
    if _flujo(run) != "sgr":
        raise InputError("los productos como datos son solo del flujo SGR; en el flujo base §15 se redacta a mano")
    if not (run / PRODUCTS_FILE).is_file():
        raise InputError(f"no existe {PRODUCTS_FILE.as_posix()}: la unidad «Productos, talento e indicadores» "
                         "lo escribe")
    errors = [f for f in check_findings(run) if f["severity"] == "error"]
    if errors:
        raise RenderRefused(errors)
    data, _ = _read_json(run / PRODUCTS_FILE)
    chain, _ = _read_json(run / CHAIN_FILE)
    alliance, _ = _read_json(run / ALLIANCE_FILE)
    renderer = _Renderer(run, data, chain, alliance)
    texts = {
        TALENT_STEM: renderer.talent(),
        INDICATORS_STEM: renderer.indicators(),
        PRODUCTS_STEM: renderer.products_section(),
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
    for name, text in (("check", "validate productos.json"),
                       ("render", "write sections 36, 37 and 15"),
                       ("datos", "products and talent facts of datos_sgr")):
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
            print("error: productos.json tiene hallazgos de error; no se generan las secciones.", file=sys.stderr)
            _print_findings(exc.errors, sys.stderr)
            return 1
        except InputError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.command == "datos":
        print(json.dumps(datos(run), ensure_ascii=False, indent=2))
        return 0

    if not (run / PRODUCTS_FILE).is_file():
        print(f"error: no existe {PRODUCTS_FILE.as_posix()}", file=sys.stderr)
        return 2
    found = check_findings(run)
    errors = sum(1 for f in found if f["severity"] == "error")
    preview = vista_2_5(run)
    if args.json:
        print(json.dumps({"findings": found, "vista_2_5": preview}, ensure_ascii=False, indent=2))
    else:
        _print_findings(found, sys.stdout)
        print(f"productos: {errors} errores, {len(found) - errors} avisos; vista previa del criterio 2.5: "
              f"{preview['total']} de 5 (A {preview['A']}, B {preview['B']})")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
