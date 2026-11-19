#!/usr/bin/env python3
"""SGR schedule from the value chain: check, render §14 and the annual projection (flujo SGR only).

The schedule of an SGR project is never hand-written: it comes from
`artefactos/sgr/cadena_valor.json` (activities with code, verbatim name, months,
`etapa`, `ruta_critica` and `costo`) and the optional
`artefactos/sgr/hitos.json` (schema `morfeo.hitos-sgr/v1`):

    {schema, hitos:[{codigo:"H1", nombre, mes, actividades:["1.1.1"], verificacion}]}

The project duration is `duracion_meses` of the value chain, else that of
`artefactos/sgr/presupuesto.json`, else the last month of any activity.

Commands:
  check RUN_ROOT [--json]
      Findings with check_run's shape {severity, code, message, node}, codes
      prefixed `cronograma-`: activity without months, months outside
      1..duracion, start after end, unknown stage, product without a
      critical-path activity (warning), milestone problems and more than 3
      consecutive months without a milestone after month 3 (warning). Whether
      a training activity starts before the platform it depends on cannot be
      inferred from the data and is left to the judge.
  render RUN_ROOT [--json]
      Write redaccion/sections/14_cronograma_actividades.tex (Anexo 2 cap. 22)
      deterministically, in the `ganttchart` convention of the base §14, only
      for SGR runs. Refuses while there are error findings.
  proyeccion RUN_ROOT [--json]
      {anios:[{anio, valor, pct}], por_actividad:{codigo:[valor por año]}}:
      each activity's `costo` spread evenly across its months (the remainder on
      its last month, so totals are exact) and grouped by 12-month years.

Exit codes: 0 ok, 1 error findings (check, render), 2 bad input.
Standard library only. The value chain loader and the LaTeX escaping come
from cadena_valor_sgr.py and the flow detection from check_run.py (same folder).
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MILESTONES_SCHEMA = "morfeo.hitos-sgr/v1"
CHAIN_FILE = Path("artefactos") / "sgr" / "cadena_valor.json"
MILESTONES_FILE = Path("artefactos") / "sgr" / "hitos.json"
BUDGET_FILE = Path("artefactos") / "sgr" / "presupuesto.json"
SECTION_FILE = Path("redaccion") / "sections" / "14_cronograma_actividades.tex"
GENERATED_HEADER = "% GENERADO por scripts/cronograma_sgr.py"

STAGES = {"preinversion": "Preinversión", "inversion": "Inversión", "operacion": "Operación"}
DEFAULT_STAGE = "inversion"
STAGE_COLORS = {"preinversion": "grisLabIA!55", "inversion": "azulUNAL!75", "operacion": "verdeGCPDS!75"}
# Rubric pitfall (Conv 56): a schedule without verifiable milestones for more
# than a quarter. Months 1..3 are the start-up window.
MAX_MONTHS_WITHOUT_MILESTONE = 3


@functools.lru_cache(maxsize=None)
def _sibling(name: str):
    """scripts/<name>.py of this folder, loaded under a private module name."""
    spec = importlib.util.spec_from_file_location(f"_cronograma_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InputError(Exception):
    pass


class RenderRefused(Exception):
    def __init__(self, errors: list[dict]) -> None:
        super().__init__("hallazgos de error")
        self.errors = errors


def _finding(severity: str, code: str, node: str, message: str) -> dict:
    return {"severity": severity, "code": code, "message": message, "node": node}


def _int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _read_json(path: Path):
    """(data, error message); (None, None) when the file does not exist."""
    if not path.is_file():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except ValueError as exc:
        return None, str(exc)


# --- Model ----------------------------------------------------------------

def _products(chain: dict):
    """(objective, product, [activities]) in chain order, dicts only."""
    for objective in chain.get("objetivos") or []:
        if not isinstance(objective, dict):
            continue
        for prod in objective.get("productos") or []:
            if isinstance(prod, dict):
                yield objective, prod, [a for a in prod.get("actividades") or [] if isinstance(a, dict)]


def _activities(chain: dict) -> list[dict]:
    return [act for _, _, acts in _products(chain) for act in acts]


def _months(act: dict):
    """(start, end) as ints, or None when either is missing or not an integer."""
    start, end = _int(act.get("mes_inicio")), _int(act.get("mes_fin"))
    return (start, end) if start is not None and end is not None else None


def duration(run: Path, chain: dict) -> int | None:
    """Months of execution: the value chain's, else the budget's, else the last activity month."""
    value = _int(chain.get("duracion_meses"))
    if value and value > 0:
        return value
    budget, _ = _read_json(run / BUDGET_FILE)
    value = _int(budget.get("duracion_meses")) if isinstance(budget, dict) else None
    if value and value > 0:
        return value
    ends = [m[1] for m in (_months(a) for a in _activities(chain)) if m]
    return max(ends) if ends else None


def _load(run: Path):
    """(chain, findings); chain is None when it cannot be used."""
    cadena = _sibling("cadena_valor_sgr")
    chain, errors = _read_json(run / CHAIN_FILE)
    if errors or not isinstance(chain, dict) or chain.get("schema") != cadena.SCHEMA:
        detail = f": {errors}" if errors else f": no declara el esquema {cadena.SCHEMA}"
        return None, [_finding("error", "cronograma-cadena-invalida", "cadena",
                               f"{CHAIN_FILE.as_posix()} no se puede leer{detail}.")]
    return chain, []


def _milestones(run: Path):
    """(milestones, findings): the list of dict milestones, [] when the file is missing."""
    data, error = _read_json(run / MILESTONES_FILE)
    if data is None and error is None:
        return [], []
    if error or not isinstance(data, dict) or data.get("schema") != MILESTONES_SCHEMA \
            or not isinstance(data.get("hitos"), list):
        detail = error or f"no declara el esquema {MILESTONES_SCHEMA} con la lista «hitos»"
        return [], [_finding("error", "cronograma-hitos-invalido", "hitos",
                             f"{MILESTONES_FILE.as_posix()} no es válido: {detail}.")]
    return [h for h in data["hitos"] if isinstance(h, dict)], []


# --- Check ----------------------------------------------------------------

def _activity_findings(act: dict, total: int | None) -> list[dict]:
    code = str(act.get("codigo") or "?")
    out: list[dict] = []
    stage = act.get("etapa")
    if stage is not None and stage not in STAGES:
        out.append(_finding("error", "cronograma-etapa-invalida", code,
                            f"La actividad {code} tiene etapa «{stage}»; las etapas válidas son preinversion, "
                            "inversion y operacion."))
    months = _months(act)
    if months is None:
        out.append(_finding("error", "cronograma-meses-faltantes", code,
                            f"La actividad {code} no declara mes de inicio y de fin enteros: el cronograma no "
                            "puede ubicarla."))
        return out
    start, end = months
    limit = total if total is not None else max(start, end)
    if start < 1 or end < 1 or start > limit or end > limit:
        out.append(_finding("error", "cronograma-mes-fuera-de-rango", code,
                            f"La actividad {code} va del mes {start} al {end}, fuera de la duración del proyecto "
                            f"(1 a {limit})."))
    elif start > end:
        out.append(_finding("error", "cronograma-meses-invertidos", code,
                            f"La actividad {code} empieza en el mes {start} y termina en el {end}."))
    return out


def _milestone_findings(milestones: list[dict], codes: set[str], total: int | None) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for n, milestone in enumerate(milestones, start=1):
        code = str(milestone.get("codigo") or f"hito {n}")
        if code in seen:
            out.append(_finding("error", "cronograma-hito-codigo-duplicado", code, f"El hito {code} está repetido."))
        seen.add(code)
        if not str(milestone.get("nombre") or "").strip():
            out.append(_finding("error", "cronograma-hito-sin-nombre", code, f"El hito {code} no tiene nombre."))
        month = _int(milestone.get("mes"))
        if month is None or month < 1 or (total is not None and month > total):
            limit = f"1 a {total}" if total is not None else "desde 1"
            out.append(_finding("error", "cronograma-hito-mes-fuera-de-rango", code,
                                f"El hito {code} declara el mes {milestone.get('mes')}, fuera de la duración "
                                f"({limit})."))
        unknown = [str(c) for c in milestone.get("actividades") or [] if str(c) not in codes]
        if unknown:
            out.append(_finding("error", "cronograma-hito-actividad-desconocida", code,
                                f"El hito {code} cita actividades que no están en la cadena de valor: "
                                f"{', '.join(unknown)}."))
        if not str(milestone.get("verificacion") or "").strip():
            out.append(_finding("warning", "cronograma-hito-sin-verificacion", code,
                                f"El hito {code} no declara su medio de verificación."))
    return out


def _spacing_findings(milestones: list[dict], total: int | None) -> list[dict]:
    """More than MAX_MONTHS_WITHOUT_MILESTONE consecutive months without a milestone after month 3."""
    if total is None:
        return []
    marked = {m for m in (_int(h.get("mes")) for h in milestones) if m is not None}
    gaps, run_start = [], None
    for month in range(MAX_MONTHS_WITHOUT_MILESTONE + 1, total + 2):
        empty = month <= total and month not in marked
        if empty and run_start is None:
            run_start = month
        elif not empty and run_start is not None:
            if month - run_start > MAX_MONTHS_WITHOUT_MILESTONE:
                gaps.append((run_start, month - 1))
            run_start = None
    return [_finding("warning", "cronograma-hitos-espaciados", "hitos",
                     f"Entre los meses {a} y {b} pasan {b - a + 1} meses sin un hito verificable; la rúbrica "
                     f"penaliza un cronograma sin hitos al menos cada {MAX_MONTHS_WITHOUT_MILESTONE} meses.")
            for a, b in gaps]


def schedule_findings(run: Path, chain: dict) -> list[dict]:
    total = duration(run, chain)
    out: list[dict] = []
    codes: set[str] = set()
    for _, prod, acts in _products(chain):
        for act in acts:
            codes.add(str(act.get("codigo") or ""))
            out.extend(_activity_findings(act, total))
        if acts and not any(a.get("ruta_critica") for a in acts):
            code = str(prod.get("codigo") or "?")
            out.append(_finding("warning", "cronograma-sin-ruta-critica", code,
                                f"El producto {code} no tiene ninguna actividad en la ruta crítica."))
    if not (run / MILESTONES_FILE).is_file():
        out.append(_finding("warning", "cronograma-hitos-faltantes", "hitos",
                            f"No existe {MILESTONES_FILE.as_posix()}: el cronograma no tiene hitos verificables "
                            "(el investigador los escribe en la Fase 6.45)."))
        return out
    milestones, errors = _milestones(run)
    out.extend(errors)
    out.extend(_milestone_findings(milestones, codes, total))
    if not errors:
        out.extend(_spacing_findings(milestones, total))
    return out


def findings(run_root: Path) -> list[dict]:
    """Findings of the run's schedule; [] when the value chain does not exist."""
    run = Path(run_root)
    if not (run / CHAIN_FILE).is_file():
        return []
    chain, errors = _load(run)
    return errors if chain is None else schedule_findings(run, chain)


# --- Annual projection ----------------------------------------------------

def _spread(cost, months: int) -> list:
    """`cost` split evenly over `months`; the remainder goes on the last month."""
    whole = _int(cost)
    if whole is not None:
        base = whole // months
        return [base] * (months - 1) + [whole - base * (months - 1)]
    cents = round(cost * 100)
    base = cents // months
    return [base / 100] * (months - 1) + [(cents - base * (months - 1)) / 100]


def proyeccion(run_root: Path) -> dict:
    """{anios:[{anio, valor, pct}], por_actividad:{codigo:[valor por año]}}."""
    run = Path(run_root)
    if not (run / CHAIN_FILE).is_file():
        raise InputError(f"no existe {CHAIN_FILE.as_posix()}: la proyección parte de la cadena de valor")
    chain, errors = _load(run)
    if chain is None:
        raise InputError(errors[0]["message"])
    activities = _activities(chain)
    last = max([duration(run, chain) or 0] + [m[1] for m in (_months(a) for a in activities) if m])
    years = max(1, -(-last // 12))
    per_activity: dict[str, list] = {}
    for act in activities:
        row = [0] * years
        cost, months = _number(act.get("costo")), _months(act)
        if cost is not None and months and 1 <= months[0] <= months[1]:
            for month, value in zip(range(months[0], months[1] + 1), _spread(cost, months[1] - months[0] + 1)):
                row[(month - 1) // 12] += value
        per_activity[str(act.get("codigo"))] = [round(v, 2) if isinstance(v, float) else v for v in row]
    totals = [sum(row[y] for row in per_activity.values()) for y in range(years)]
    totals = [round(v, 2) if isinstance(v, float) else v for v in totals]
    grand = sum(totals)
    return {
        "anios": [{"anio": y + 1, "valor": totals[y], "pct": round(totals[y] * 100 / grand, 2) if grand else 0}
                  for y in range(years)],
        "por_actividad": per_activity,
    }


# --- Render ---------------------------------------------------------------

def _stage(act: dict) -> str:
    stage = act.get("etapa")
    return stage if stage in STAGES else DEFAULT_STAGE


def _span(acts: list[dict]) -> tuple[int, int]:
    months = [m for m in (_months(a) for a in acts) if m]
    return min(m[0] for m in months), max(m[1] for m in months)


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _gantt(chain: dict, milestones: list[dict], total: int, esc) -> list[str]:
    rows = sum(1 + len(acts) for _, _, acts in _products(chain)) + len(chain.get("objetivos") or []) + len(milestones)
    x_unit = round(min(0.6, 8.4 / total), 3)
    y_unit = round(max(0.32, min(0.55, 19.0 / max(rows, 1))), 3)
    # The caption goes after the chart: prep_docx.swap_figure_graphics keeps everything from \caption{ on
    # and replaces what comes before it with the rasterized PNG.
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"  \begin{ganttchart}[",
        f"    x unit={x_unit}cm,",
        f"    y unit chart={y_unit}cm,",
        r"    y unit title=0.42cm,",
        r"    title/.append style={fill=azulUNAL!15, draw=azulUNAL!50},",
        r"    title label font=\tiny\bfseries,",
        r"    bar/.append style={fill=azulUNAL!75, draw=azulUNAL!85},",
        r"    bar height=0.5,",
        r"    group/.append style={fill=grisLabIA!80, draw=grisLabIA!90},",
        r"    group height=0.3,",
        r"    milestone/.append style={fill=rojoLimitante, draw=rojoLimitante!80},",
        r"    milestone height=0.6,",
        r"    bar label font=\tiny,",
        r"    milestone label font=\tiny,",
        r"    group label font=\tiny\bfseries,",
        r"    bar label node/.append style={text width=7cm, align=flush right},",
        r"    milestone label node/.append style={text width=7cm, align=flush right},",
        r"    group label node/.append style={text width=7cm, align=flush right},",
        r"    vgrid={draw=azulUNAL!25},",
        r"    hgrid={draw=grisLabIA!25}",
        f"  ]{{1}}{{{total}}}",
    ]
    body: list[str] = []
    if total > 12:
        years = -(-total // 12)
        body.append(" ".join(rf"\gantttitle{{Año {y + 1}}}{{{min(12, total - 12 * y)}}}" for y in range(years)))
    else:
        body.append(rf"\gantttitle{{Meses de ejecución}}{{{total}}}")
    body.append(rf"\gantttitlelist{{1,...,{total}}}{{1}}")
    current = None
    for objective, prod, acts in _products(chain):
        if not acts:
            continue
        if objective is not current:
            current = objective
            all_acts = [a for o, _, a_list in _products(chain) if o is objective for a in a_list]
            start, end = _span(all_acts)
            body.append(rf"\ganttgroup{{{esc(objective.get('id'))}}}{{{start}}}{{{end}}}")
        start, end = _span(acts)
        body.append(rf"\ganttgroup[group/.append style={{fill=grisLabIA!35, draw=grisLabIA!60}}]"
                    rf"{{{esc(prod.get('codigo'))} $\cdot$ {esc(prod.get('nombre'))}}}{{{start}}}{{{end}}}")
        for act in acts:
            a_start, a_end = _months(act)
            style = f"fill={STAGE_COLORS[_stage(act)]}"
            mark = ""
            if act.get("ruta_critica"):
                style += ", draw=rojoLimitante, line width=0.8pt"
                mark = r" $\star$"
            body.append(rf"\ganttbar[bar/.append style={{{style}}}]"
                        rf"{{{esc(act.get('codigo'))} $\cdot$ {esc(act.get('nombre'))}{mark}}}{{{a_start}}}{{{a_end}}}")
    for milestone in milestones:
        body.append(rf"\ganttmilestone{{\textbf{{{esc(milestone.get('codigo'))}}} $\cdot$ "
                    rf"{esc(milestone.get('nombre'))}}}{{{_int(milestone.get('mes'))}}}")
    lines += [f"    {row}\\\\" for row in body[:-1]] + [f"    {body[-1]}"]
    lines += [
        r"  \end{ganttchart}",
        r"\caption{Cronograma de actividades por objetivo específico y producto. Las columnas son los meses de "
        r"ejecución; las barras grises son actividades de preinversión, las azules de inversión y las verdes de "
        r"operación; $\star$ marca la ruta crítica y los rombos rojos, los hitos de verificación.}",
        r"\label{tab:cronograma}",
        r"\end{table}",
        "",
    ]
    return lines


def _table_head(spec: str, caption: str, label: str, header: str) -> list[str]:
    return [
        "{\\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        rf"\begin{{xltabular}}{{\textwidth}}{{{spec}}}",
        rf"\caption{{{caption}}}\label{{{label}}}\\",
        r"\toprule", header, r"\midrule", r"\endfirsthead",
        r"\toprule", header, r"\midrule", r"\endhead",
        r"\bottomrule", r"\endlastfoot",
    ]


def _activity_table(chain: dict, esc) -> list[str]:
    col = r">{\raggedright\arraybackslash}"
    lines = _table_head(
        f"{col}p{{0.08\\textwidth}} {col}X {col}p{{0.12\\textwidth}} {col}p{{0.1\\textwidth}} {col}p{{0.1\\textwidth}}",
        "Actividades del cronograma con su etapa, sus meses y la ruta crítica.", "tab:cronograma_actividades",
        r"\textbf{Código} & \textbf{Actividad} & \textbf{Etapa} & \textbf{Meses} & \textbf{Ruta crítica} \\")
    current = None
    for objective, prod, acts in _products(chain):
        if objective is not current:
            current = objective
            lines.append(rf"\multicolumn{{5}}{{p{{0.95\textwidth}}}}{{\textbf{{{esc(objective.get('id'))}}} "
                         rf"{esc(objective.get('texto'))}}} \\")
        lines.append(rf"\multicolumn{{5}}{{p{{0.95\textwidth}}}}{{\textit{{Producto {esc(prod.get('codigo'))}: "
                     rf"{esc(prod.get('nombre'))}}}}} \\")
        for act in acts:
            start, end = _months(act)
            months = str(start) if start == end else f"{start} a {end}"
            critical = "Sí" if act.get("ruta_critica") else "No"
            lines.append(f"{esc(act.get('codigo'))} & {esc(act.get('nombre'))} & {STAGES[_stage(act)]} & "
                         rf"{months} & {critical} \\")
    return lines + [r"\end{xltabular}", "}", ""]


def _milestone_table(milestones: list[dict], esc) -> list[str]:
    col = r">{\raggedright\arraybackslash}"
    lines = _table_head(
        f"{col}p{{0.06\\textwidth}} {col}X {col}p{{0.06\\textwidth}} {col}p{{0.14\\textwidth}} {col}X",
        "Hitos de verificación del cronograma.", "tab:cronograma_hitos",
        r"\textbf{Hito} & \textbf{Descripción} & \textbf{Mes} & \textbf{Actividades} & "
        r"\textbf{Medio de verificación} \\")
    for milestone in milestones:
        activities = ", ".join(esc(c) for c in milestone.get("actividades") or []) or "No aplica"
        verification = esc(milestone.get("verificacion") or "Por definir")
        lines.append(f"{esc(milestone.get('codigo'))} & {esc(milestone.get('nombre'))} & "
                     rf"{_int(milestone.get('mes'))} & {activities} & {verification} \\")
    return lines + [r"\end{xltabular}", "}", ""]


def render_section(run_root: Path) -> str:
    """The text of 14_cronograma_actividades.tex; the caller checks there are no error findings."""
    run = Path(run_root)
    esc = _sibling("cadena_valor_sgr").escape
    chain, _ = _load(run)
    milestones, _ = _milestones(run)
    milestones = sorted(milestones, key=lambda h: (_int(h.get("mes")) or 0, str(h.get("codigo"))))
    total = duration(run, chain)
    activities = _activities(chain)
    by_stage = {stage: sum(1 for a in activities if _stage(a) == stage) for stage in STAGES}
    critical = sum(1 for a in activities if a.get("ruta_critica"))
    stage_text = "; ".join(f"la etapa de {STAGES[s].lower()}, {_plural(n, 'actividad', 'actividades')}"
                           for s, n in by_stage.items() if n)
    lines = [
        GENERATED_HEADER,
        f"% Fuente: {CHAIN_FILE.as_posix()} y {MILESTONES_FILE.as_posix()}. No se edita a mano: se regenera con",
        "% python3 scripts/cronograma_sgr.py render <RUN_ROOT>.",
        r"\section{Cronograma de actividades}",
        r"\label{sec:cronograma-actividades}",
        "",
        f"El cronograma ubica en los {total} meses de ejecución las {_plural(len(activities), 'actividad', 'actividades')} "
        "de la cadena de valor, agrupadas por objetivo específico y producto, con el mismo código y el mismo nombre. "
        "Cada actividad se marca con su etapa (preinversión, inversión u operación): "
        f"{stage_text}. Las actividades marcadas con $\\star$ están en la ruta crítica "
        f"({_plural(critical, 'actividad', 'actividades')}).",
        "",
    ]
    if milestones:
        lines += [f"El proyecto verificará su avance con {_plural(len(milestones), 'hito', 'hitos')}, cada uno con "
                  "su mes, las actividades que lo producen y su medio de verificación.", ""]
    lines += _gantt(chain, milestones, total, esc)
    lines += _activity_table(chain, esc)
    if milestones:
        lines += _milestone_table(milestones, esc)
    return "\n".join(lines)


def render(run_root: Path) -> Path:
    run = Path(run_root)
    if _sibling("check_run").detect_flujo(run) != "sgr":
        raise InputError("la corrida no es del flujo sgr: en el flujo base §14 lo escribe el redactor")
    if not (run / CHAIN_FILE).is_file():
        raise InputError(f"no existe {CHAIN_FILE.as_posix()}: el cronograma parte de la cadena de valor")
    errors = [f for f in findings(run) if f["severity"] == "error"]
    if errors:
        raise RenderRefused(errors)
    out = run / SECTION_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_section(run), encoding="utf-8")
    return out


# --- CLI ------------------------------------------------------------------

def _print_findings(found: list[dict], stream) -> None:
    for f in found:
        print(f"[{f['severity'].upper()}] {f['code']} [{f['node']}] {f['message']}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("check", "validate the schedule data"),
                       ("render", "write redaccion/sections/14_cronograma_actividades.tex"),
                       ("proyeccion", "annual financial projection of the activity costs")):
        p = sub.add_parser(name, help=text)
        p.add_argument("run_root", type=Path)
        p.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)
    run = args.run_root.resolve()

    try:
        if args.command == "render":
            out = render(run)
            print(json.dumps({"seccion": str(out)}, ensure_ascii=False) if args.json else f"SECCION: {out}")
            return 0
        if args.command == "proyeccion":
            data = proyeccion(run)
            if args.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                for year in data["anios"]:
                    print(f"Año {year['anio']}: {year['valor']} ({year['pct']} %)")
            return 0
        if not (run / CHAIN_FILE).is_file():
            raise InputError(f"no existe {CHAIN_FILE.as_posix()}: el cronograma parte de la cadena de valor")
    except RenderRefused as exc:
        print("error: el cronograma tiene hallazgos de error; no se genera §14.", file=sys.stderr)
        _print_findings(exc.errors, sys.stderr)
        return 1
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    found = findings(run)
    errors = sum(1 for f in found if f["severity"] == "error")
    if args.json:
        print(json.dumps({"findings": found}, ensure_ascii=False, indent=2))
    else:
        _print_findings(found, sys.stdout)
        print(f"cronograma: {errors} errores, {len(found) - errors} avisos")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
