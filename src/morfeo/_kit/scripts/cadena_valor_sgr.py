#!/usr/bin/env python3
"""SGR value chain as data: seed, check and render annex A23 (flujo SGR only).

`artefactos/sgr/cadena_valor.json` (schema `morfeo.cadena-valor-sgr/v1`) holds
the value chain of an SGR project: one entry per specific objective of the
approved objective tree, its products (DNP catalogue code, indicator, goal) and
the activities that produce them, each with one code used by the methodology,
the budget and the schedule:

    {schema, duracion_meses|null, arbol_hash,
     objetivos:[{id:"OE1", texto,
       productos:[{codigo:"1.1", codigo_dnp|null, nombre, medido_a_traves_de,
                   indicador, unidad, meta|null,
         actividades:[{codigo:"1.1.1", nombre,
                       tipo:"tecnica"|"administracion"|"supervision",
                       ruta_critica, mes_inicio|null, mes_fin|null,
                       costo|null, medio|null,
                       etapa?:"preinversion"|"inversion"|"operacion"}]}]}]}

`etapa` is optional (MGA stage of the activity, «inversion» when absent);
scripts/cronograma_sgr.py groups the schedule (§14) by it.

Commands:
  init RUN_ROOT [--force] [--duracion-meses N]
      Seed the file from artefactos/arboles/arbol_objetivos.json: one objective
      per tree group with its verbatim text, one placeholder product per
      objective, one technical activity candidate per means (with `medio`), and
      the administration and supervision activities under the last product.
      Refuses to overwrite an existing file without --force.
  check RUN_ROOT [--json]
      Findings with check_run's shape {severity, code, message, node}, codes
      prefixed `cadena-`; also reports the sum of the costs.
  render RUN_ROOT
      Write redaccion/sections/23_cadena_valor.tex deterministically. Refuses
      while there are error findings.

Exit codes: 0 ok, 1 error findings (check, render), 2 bad input.
Standard library only. Text helpers come from check_run.py (same folder),
which imports `findings` from here for its SGR checks.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

SCHEMA = "morfeo.cadena-valor-sgr/v1"
CHAIN_FILE = Path("artefactos") / "sgr" / "cadena_valor.json"
TREE_FILE = Path("artefactos") / "arboles" / "arbol_objetivos.json"
SECTION_FILE = Path("redaccion") / "sections" / "23_cadena_valor.tex"
BUDGET_SECTION = Path("redaccion") / "sections" / "13_presupuesto.tex"
GENERATED_HEADER = "% GENERADO por scripts/cadena_valor_sgr.py"

ACTIVITY_TYPES = ("tecnica", "administracion", "supervision")
# MGA stages of an activity (optional field `etapa`; «inversion» when absent).
ACTIVITY_STAGES = ("preinversion", "inversion", "operacion")
MANAGEMENT_TYPES = {"administracion": "administración", "supervision": "supervisión"}
# Verbs the MGA forbids at the start of an activity name (Manual MGA 2015,
# p. 81; guía SGR, A23). They apply to activity names only, never to products.
MGA_BANNED_ACTIVITY_VERBS = frozenset({
    "apropiar", "asegurar", "colaborar", "consolidar", "desarrollar", "fomentar", "fortalecer",
    "garantizar", "implementar", "impulsar", "mejorar", "movilizar", "proponer", "promover",
})
DNP_CODE_RE = re.compile(r"^39\d{5}$")
MGA_RULE = "Manual MGA 2015, p. 81"

ADMIN_NAME = "Realizar la gestión administrativa y financiera del proyecto"
SUPERVISION_NAME = "Realizar la supervisión técnica del proyecto"

_CHECK_RUN_PATH = Path(__file__).resolve().parent / "check_run.py"


def _check_run():
    """check_run.py of this folder, reusing the loaded module when it is the caller."""
    for name in ("check_run", "__main__"):
        module = sys.modules.get(name)
        file = getattr(module, "__file__", None)
        if file and Path(file).resolve() == _CHECK_RUN_PATH and hasattr(module, "normalize_tree_text"):
            return module
    spec = importlib.util.spec_from_file_location("_cadena_check_run", _CHECK_RUN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InputError(Exception):
    pass


# --- Seed -----------------------------------------------------------------

def _activity(code: str, name: str, tipo: str, medio: str | None = None) -> dict:
    return {"codigo": code, "nombre": name, "tipo": tipo, "ruta_critica": tipo == "tecnica",
            "mes_inicio": None, "mes_fin": None, "costo": None, "medio": medio}


def seed(tree: dict, tree_hash: str, duracion_meses: int | None = None) -> dict:
    objectives = []
    for n, group in enumerate(tree.get("groups") or [], start=1):
        means = [m for m in group.get("means") or [] if isinstance(m, dict)]
        activities = [_activity(f"{n}.1.{a}", str(m.get("text") or ""), "tecnica", m.get("id"))
                      for a, m in enumerate(means, start=1)]
        a = len(activities)
        activities.append(_activity(f"{n}.1.{a + 1}", ADMIN_NAME, "administracion"))
        activities.append(_activity(f"{n}.1.{a + 2}", SUPERVISION_NAME, "supervision"))
        objectives.append({
            "id": f"OE{n}",
            "texto": str(group.get("objective") or ""),
            "productos": [{
                "codigo": f"{n}.1", "codigo_dnp": None, "nombre": "", "medido_a_traves_de": "",
                "indicador": "", "unidad": "", "meta": None, "actividades": activities,
            }],
        })
    return {"schema": SCHEMA, "duracion_meses": duracion_meses, "arbol_hash": tree_hash, "objetivos": objectives}


def _tree_hash(run: Path) -> str | None:
    path = run / TREE_FILE
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _read_tree(run: Path) -> dict | None:
    path = run / TREE_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def init(run: Path, force: bool = False, duracion_meses: int | None = None) -> Path:
    tree_path = run / TREE_FILE
    if not tree_path.is_file():
        raise InputError(f"no existe {TREE_FILE.as_posix()}: la cadena de valor parte del árbol de objetivos "
                         "aprobado en G1b")
    tree = _read_tree(run)
    if tree is None or not tree.get("groups"):
        raise InputError(f"{TREE_FILE.as_posix()} no es JSON válido o no tiene objetivos específicos (groups)")
    out = run / CHAIN_FILE
    if out.exists() and not force:
        raise InputError(f"{CHAIN_FILE.as_posix()} ya existe; usá --force para reemplazarlo")
    chain = seed(tree, _tree_hash(run), duracion_meses)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(chain, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


# --- Check ----------------------------------------------------------------

def _finding(severity: str, code: str, node: str, message: str) -> dict:
    return {"severity": severity, "code": code, "message": message, "node": node}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _first_word(text: str) -> str:
    cr = _check_run()
    match = re.match(r"[^\W\d_]+", cr.normalize_tree_text(text))
    return cr._fold(match.group(0).lower()) if match else ""


def _same_text(a, b) -> bool:
    cr = _check_run()
    return cr.normalize_tree_text(a).rstrip(" .;:") == cr.normalize_tree_text(b).rstrip(" .;:")


def _check_activity(act: dict, expected: str, duration, budget_phase: bool, means_ids: set[str]) -> list[dict]:
    out: list[dict] = []
    code = str(act.get("codigo") or expected)
    name = str(act.get("nombre") or "").strip()
    if not name:
        out.append(_finding("error", "cadena-nombre-vacio", code, f"La actividad {code} no tiene nombre."))
    elif _first_word(name) in MGA_BANNED_ACTIVITY_VERBS:
        out.append(_finding("error", "cadena-verbo-prohibido", code,
                            f"La actividad {code} abre con «{name.split()[0]}», un verbo que la MGA no admite en "
                            f"actividades ({MGA_RULE}): nombrá la acción concreta que se ejecuta."))
    if act.get("tipo") not in ACTIVITY_TYPES:
        out.append(_finding("error", "cadena-tipo-invalido", code,
                            f"La actividad {code} tiene tipo «{act.get('tipo')}»; los tipos válidos son "
                            "tecnica, administracion y supervision."))
    stage = act.get("etapa")
    if stage is not None and stage not in ACTIVITY_STAGES:
        out.append(_finding("error", "cadena-etapa-invalida", code,
                            f"La actividad {code} tiene etapa «{stage}»; las etapas válidas son preinversion, "
                            "inversion y operacion."))
    start, end = act.get("mes_inicio"), act.get("mes_fin")
    if start is None or end is None:
        out.append(_finding("warning", "cadena-meses-faltantes", code,
                            f"La actividad {code} no declara mes de inicio y de fin."))
    for month in (start, end):
        if month is None:
            continue
        if _number(month) is None or month < 1 or (duration is not None and month > duration):
            limit = f"1 a {duration}" if duration is not None else "desde 1"
            out.append(_finding("error", "cadena-mes-fuera-de-rango", code,
                                f"La actividad {code} declara el mes {month}, fuera de la duración ({limit})."))
            break
    else:
        if _number(start) is not None and _number(end) is not None and start > end:
            out.append(_finding("error", "cadena-meses-invertidos", code,
                                f"La actividad {code} empieza en el mes {start} y termina en el {end}."))
    cost = act.get("costo")
    if cost is None:
        if budget_phase:
            out.append(_finding("warning", "cadena-costo-faltante", code,
                                f"La actividad {code} no tiene costo; el presupuestador lo asigna desde la Fase 6.4."))
    elif _number(cost) is None:
        out.append(_finding("error", "cadena-costo-invalido", code, f"El costo de la actividad {code} no es un número."))
    elif cost < 0:
        out.append(_finding("error", "cadena-costo-negativo", code, f"El costo de la actividad {code} es negativo."))
    medio = act.get("medio")
    if medio is not None and means_ids and medio not in means_ids:
        out.append(_finding("warning", "cadena-medio-desconocido", code,
                            f"La actividad {code} cita el medio «{medio}», que no está en su objetivo del árbol."))
    return out


def _check_product(prod: dict, expected: str, duration, budget_phase: bool, means_ids: set[str],
                   seen: set[str], out: list[dict]) -> None:
    code = str(prod.get("codigo") or expected)
    if not str(prod.get("nombre") or "").strip():
        out.append(_finding("error", "cadena-nombre-vacio", code, f"El producto {code} no tiene nombre."))
    dnp = prod.get("codigo_dnp")
    if dnp is None or dnp == "":
        out.append(_finding("warning", "cadena-codigo-dnp-faltante", code,
                            f"El producto {code} no tiene código del catálogo de productos DNP."))
    elif not DNP_CODE_RE.match(str(dnp)):
        out.append(_finding("error", "cadena-codigo-dnp-invalido", code,
                            f"El código DNP «{dnp}» del producto {code} no es un código del sector Ciencia, "
                            "Tecnología e Innovación (39 y cinco dígitos)."))
    missing = [label for key, label in (("medido_a_traves_de", "medido a través de"), ("indicador", "indicador"),
                                        ("unidad", "unidad")) if not str(prod.get(key) or "").strip()]
    if missing:
        out.append(_finding("warning", "cadena-producto-incompleto", code,
                            f"Al producto {code} le falta: {', '.join(missing)}."))
    if prod.get("meta") is None:
        out.append(_finding("warning", "cadena-meta-faltante", code, f"El producto {code} no declara meta."))
    activities = [a for a in prod.get("actividades") or [] if isinstance(a, dict)]
    technical = sum(1 for a in activities if a.get("tipo") == "tecnica")
    if technical < 2:
        out.append(_finding("error", "cadena-producto-pocas-actividades", code,
                            f"El producto {code} tiene {technical} actividad(es) técnica(s); la guía SGR (A23) "
                            "pide dos o más por producto."))
    for a, act in enumerate(activities, start=1):
        want = f"{expected}.{a}"
        act_code = str(act.get("codigo") or "")
        _register_code(act_code, want, "actividad", seen, out)
        out.extend(_check_activity(act, want, duration, budget_phase, means_ids))


def _register_code(code: str, expected: str, what: str, seen: set[str], out: list[dict]) -> None:
    if code != expected:
        out.append(_finding("error", "cadena-codigo-inconsistente", code or expected,
                            f"La {what} en la posición {expected} tiene el código «{code}»: los códigos siguen "
                            "<oe>.<producto>.<actividad>, desde 1 y en orden."))
    if code in seen:
        out.append(_finding("error", "cadena-codigo-duplicado", code, f"El código {code} está repetido."))
    seen.add(code)


def chain_findings(chain, tree: dict | None, budget_phase: bool = False, tree_hash: str | None = None) -> list[dict]:
    """Pure rules of the contract (odd/tasks/sgr-cadena-estilo.md, Contracts)."""
    if not isinstance(chain, dict) or chain.get("schema") != SCHEMA:
        return [_finding("error", "cadena-esquema", "cadena", f"El archivo no declara el esquema {SCHEMA}.")]
    out: list[dict] = []
    if tree is None:
        out.append(_finding("warning", "cadena-arbol-faltante", "cadena",
                            f"No se encontró {TREE_FILE.as_posix()}; no se puede cotejar el texto de los objetivos."))
    elif tree_hash and chain.get("arbol_hash") and chain.get("arbol_hash") != tree_hash:
        out.append(_finding("warning", "cadena-arbol-modificado", "cadena",
                            "El árbol de objetivos cambió después de sembrar la cadena de valor: revisá que los "
                            "objetivos, medios y actividades sigan alineados."))
    evaluation = chain.get("evaluacion_mga")
    if evaluation is not None and not isinstance(evaluation, str):
        out.append(_finding("error", "cadena-evaluacion-mga", "cadena",
                            "«evaluacion_mga» debe ser texto: la evaluación MGA del tipo que declaró A22, "
                            "en párrafos separados por una línea en blanco."))
    duration = _number(chain.get("duracion_meses"))
    groups = (tree or {}).get("groups") or []
    objectives = [o for o in chain.get("objetivos") or [] if isinstance(o, dict)]
    if tree is not None and len(objectives) != len(groups):
        out.append(_finding("error", "cadena-objetivos-numero", "cadena",
                            f"La cadena tiene {len(objectives)} objetivos específicos y el árbol {len(groups)}."))
    seen: set[str] = set()
    for n, objective in enumerate(objectives, start=1):
        oe = f"OE{n}"
        if objective.get("id") != oe:
            out.append(_finding("error", "cadena-codigo-inconsistente", str(objective.get("id") or oe),
                                f"El objetivo en la posición {n} se llama «{objective.get('id')}»; debe ser {oe}."))
        group = groups[n - 1] if n <= len(groups) and isinstance(groups[n - 1], dict) else None
        if group is not None and not _same_text(objective.get("texto"), group.get("objective")):
            out.append(_finding("error", "cadena-objetivo-distinto", oe,
                                f"El texto de {oe} no es literalmente el objetivo específico del árbol de objetivos."))
        means_ids = {str(m.get("id")) for m in (group or {}).get("means") or [] if isinstance(m, dict)}
        products = [p for p in objective.get("productos") or [] if isinstance(p, dict)]
        for p, prod in enumerate(products, start=1):
            want = f"{n}.{p}"
            _register_code(str(prod.get("codigo") or ""), want, "producto", seen, out)
            _check_product(prod, want, duration, budget_phase, means_ids, seen, out)
        for tipo, label in MANAGEMENT_TYPES.items():
            places = [p for p, prod in enumerate(products, start=1)
                      for a in prod.get("actividades") or [] if isinstance(a, dict) and a.get("tipo") == tipo]
            if not places:
                out.append(_finding("error", "cadena-gestion-faltante", oe,
                                    f"{oe} no tiene la actividad de {label} bajo su último producto."))
            elif len(places) > 1:
                out.append(_finding("error", "cadena-gestion-repetida", oe,
                                    f"{oe} tiene {len(places)} actividades de {label}; va una sola."))
            elif places[0] != len(products):
                out.append(_finding("error", "cadena-gestion-fuera-de-lugar", oe,
                                    f"La actividad de {label} de {oe} va bajo su último producto."))
    return out


def total_cost(chain: dict) -> float:
    total = 0
    for objective in chain.get("objetivos") or []:
        for prod in objective.get("productos") or []:
            for act in prod.get("actividades") or []:
                cost = _number(act.get("costo"))
                if cost is not None:
                    total += cost
    return total


def load_chain(run: Path):
    """(chain, findings): the parsed file, or None with the finding that explains why."""
    path = run / CHAIN_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except ValueError as exc:
        return None, [_finding("error", "cadena-json-invalido", "cadena",
                               f"{CHAIN_FILE.as_posix()} no es JSON válido: {exc}")]


def findings(run_root: Path) -> list[dict]:
    """Findings of the run's value chain; [] when the file does not exist."""
    run = Path(run_root)
    if not (run / CHAIN_FILE).is_file():
        return []
    chain, errors = load_chain(run)
    if errors:
        return errors
    return chain_findings(chain, _read_tree(run), budget_phase=(run / BUDGET_SECTION).is_file(),
                          tree_hash=_tree_hash(run))


# --- Render ---------------------------------------------------------------

_LATEX_SPECIALS = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def escape(text) -> str:
    return "".join(_LATEX_SPECIALS.get(c, c) for c in " ".join(str(text).split()))


def money(value) -> str:
    number = _number(value)
    if number is None:
        return "Por asignar"
    return r"\$\," + f"{round(number):,}".replace(",", ".")


def _months(act: dict) -> str:
    start, end = act.get("mes_inicio"), act.get("mes_fin")
    if start is None or end is None:
        return "Meses: por definir"
    return f"Meses: {start}" if start == end else f"Meses: {start} a {end}"


def _product_cell(prod: dict) -> str:
    dnp = prod.get("codigo_dnp")
    meta = prod.get("meta")
    unit = str(prod.get("unidad") or "").strip()
    parts = [
        rf"\textbf{{{escape(prod.get('codigo'))}}} {escape(prod.get('nombre'))}",
        f"Código DNP: {escape(dnp) if dnp else 'por definir'}",
        f"Medido a través de: {escape(prod.get('medido_a_traves_de') or 'por definir')}",
        f"Meta: {escape(meta) if meta is not None else 'por definir'}" + (f" ({escape(unit)})" if unit and meta is not None else ""),
    ]
    return r"\newline ".join(parts)


def _activity_cell(act: dict) -> str:
    critical = "sí" if act.get("ruta_critica") else "no"
    return (rf"{escape(act.get('codigo'))} {escape(act.get('nombre'))}\newline "
            rf"Ruta crítica: {critical}. {_months(act)}")


HEADER_ROW = r"\textbf{Objetivo específico} & \textbf{Producto} & \textbf{Actividades} & \textbf{Costo} \\"


def render_tex(chain: dict) -> str:
    lines = [
        GENERATED_HEADER,
        f"% Fuente: {CHAIN_FILE.as_posix()}. No se edita a mano: se regenera con",
        "% python3 scripts/cadena_valor_sgr.py render <RUN_ROOT>.",
        r"\section{Cadena de valor}",
        r"\label{sec:cadena_valor}",
        "",
        "{\\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{xltabular}{\textwidth}{>{\raggedright\arraybackslash}p{0.22\textwidth} "
        r">{\raggedright\arraybackslash}X >{\raggedright\arraybackslash}X >{\raggedleft\arraybackslash}p{0.12\textwidth}}",
        r"\caption{Cadena de valor: objetivos específicos, productos y actividades.}\label{tab:cadena_valor}\\",
        r"\toprule", HEADER_ROW, r"\midrule", r"\endfirsthead",
        r"\toprule", HEADER_ROW, r"\midrule", r"\endhead",
        r"\bottomrule", r"\endlastfoot",
    ]
    objectives = chain.get("objetivos") or []
    for i, objective in enumerate(objectives):
        first_of_objective = True
        for prod in objective.get("productos") or []:
            first_of_product = True
            for act in prod.get("actividades") or [{}]:
                cells = [
                    rf"\textbf{{{escape(objective.get('id'))}}} {escape(objective.get('texto'))}" if first_of_objective else "",
                    _product_cell(prod) if first_of_product else "",
                    _activity_cell(act),
                    money(act.get("costo")),
                ]
                lines.append(" & ".join(cells) + r" \\")
                first_of_objective = first_of_product = False
        if i < len(objectives) - 1:
            lines.append(r"\midrule")
    lines += [
        r"\midrule",
        rf"\multicolumn{{3}}{{r}}{{\textbf{{Total}}}} & \textbf{{{money(total_cost(chain))}}} \\",
        r"\end{xltabular}",
        "}",
        "",
    ]
    # Optional MGA evaluation prose (guide A23, «Evaluación MGA»), after the table.
    evaluation = chain.get("evaluacion_mga")
    paragraphs = [escape(p) for p in str(evaluation or "").split("\n\n") if p.strip()] if isinstance(evaluation, str) else []
    if paragraphs:
        lines += [r"\subsection*{Evaluación MGA}", "\n\n".join(paragraphs), ""]
    return "\n".join(lines)


def render(run: Path) -> Path:
    if not (run / CHAIN_FILE).is_file():
        raise InputError(f"no existe {CHAIN_FILE.as_posix()}: corré primero `init`")
    found = findings(run)
    errors = [f for f in found if f["severity"] == "error"]
    if errors:
        raise RenderRefused(errors)
    chain, _ = load_chain(run)
    out = run / SECTION_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_tex(chain), encoding="utf-8")
    return out


class RenderRefused(Exception):
    def __init__(self, errors: list[dict]) -> None:
        super().__init__("hallazgos de error")
        self.errors = errors


# --- CLI ------------------------------------------------------------------

def _print_findings(found: list[dict], stream) -> None:
    for f in found:
        print(f"[{f['severity'].upper()}] {f['code']} [{f['node']}] {f['message']}", file=stream)


def _format_total(value) -> str:
    return f"{round(value):,}".replace(",", ".")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init", help="seed cadena_valor.json from the objective tree")
    p_init.add_argument("run_root", type=Path)
    p_init.add_argument("--force", action="store_true", help="replace an existing cadena_valor.json")
    p_init.add_argument("--duracion-meses", type=int, default=None, help="project duration in months")
    p_check = sub.add_parser("check", help="validate cadena_valor.json")
    p_check.add_argument("run_root", type=Path)
    p_check.add_argument("--json", action="store_true", help="print {findings, costo_total} as JSON")
    p_render = sub.add_parser("render", help="write redaccion/sections/23_cadena_valor.tex")
    p_render.add_argument("run_root", type=Path)
    args = parser.parse_args(argv)
    run = args.run_root.resolve()

    try:
        if args.command == "init":
            out = init(run, args.force, args.duracion_meses)
            print(f"CADENA: {out}")
            return 0
        if args.command == "render":
            out = render(run)
            print(f"ANEXO: {out}")
            return 0
        if not (run / CHAIN_FILE).is_file():
            raise InputError(f"no existe {CHAIN_FILE.as_posix()}: corré primero `init`")
    except RenderRefused as exc:
        print("error: la cadena de valor tiene hallazgos de error; no se genera el anexo A23.", file=sys.stderr)
        _print_findings(exc.errors, sys.stderr)
        return 1
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    found = findings(run)
    chain, _ = load_chain(run)
    total = total_cost(chain) if isinstance(chain, dict) else 0
    errors = sum(1 for f in found if f["severity"] == "error")
    if args.json:
        print(json.dumps({"findings": found, "costo_total": total}, ensure_ascii=False, indent=2))
    else:
        _print_findings(found, sys.stdout)
        print(f"Costo total de las actividades: {_format_total(total)}")
        print(f"cadena_valor: {errors} errores, {len(found) - errors} avisos")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
