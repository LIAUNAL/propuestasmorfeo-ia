#!/usr/bin/env python3
"""One-shot, deterministic figure pipeline: render -> compile -> audit.

This replaces the three-dispatch LLM loop (`disenador-tikz` → `tikz-optimizer`
→ `revisor-figuras`, measured at ~28.8 minutes per figure on run
`2026-09-tept-depresion-ia-portable`) with a single command whose whole cost is
LaTeX plus two short Python passes.

What it does, in order:

  1. `render_tikz.py` builds `diag_<name>.tex` from the JSON spec.
  2. `compile_tikz.py` compiles it to `fig_<name>-1.png` + `fig_<name>.svg` and
     prints the deterministic `OVERFULL:` token.
  3. If the token reports overflow, the node that actually overflowed is widened
     by exactly the measured amount (`render_tikz.py --fix-overfull`) and the
     compile repeats. This is the loop the LLM used to run — but every iteration
     is ~1 s instead of ~7 minutes, and the widening is measured, not guessed.
  4. `audit_tikz.py` answers the mechanical half of the old visual review.
  5. The wall-clock budget is checked and reported.

The 3-minute ceiling is a hard contract: `--budget-s` defaults to 180 and the
command exits non-zero if the pipeline exceeds it, so a regression can never
pass silently.

Usage
-----
    figura.py <name> --spec specs/<name>.spec.json [--project DIR] [--budget-s 180]
    figura.py arbol_problemas --spec specs/arbol_problemas.spec.json --json

`<name>` is the diagram id used everywhere else in the framework
(`arbol_problemas`, `estado_arte`, `metodologico`).
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import time


@contextlib.contextmanager
def _quiet_stdout(enabled: bool):
    """Keep `--json` stdout machine-readable by routing progress to stderr.

    `render_tikz.main` and `compile_tikz.py` print human progress lines
    (`RENDER: …`, `OK: …`). In `--json` mode those must not pollute stdout, or
    every caller that parses the report breaks -- which is exactly how this was
    found.
    """
    if not enabled:
        yield
        return
    with contextlib.redirect_stdout(sys.stderr):
        yield

MAX_FIX_ITERATIONS = 12

OVERFULL_LINE_RE = re.compile(
    rf"OVERFULL:\s*(?P<name>\S+)\s+(?P<count>\d+)\s+occurrence\(s\)"
    rf"(?:\s*\(first:\s*(?P<pt>[0-9.]+)pt too wide(?:,\s*line unavailable)?"
    rf"(?:\s+at\s+\S+:(?P<line>\d+))?\))?"
)


def _load_sibling(module_name: str):
    """Import a sibling script by path (they are copied into each run's scripts/)."""
    here = pathlib.Path(__file__).resolve().parent
    path = here / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_compile(project: pathlib.Path, name: str, kind: str = "tikz") -> tuple[int, str]:
    script = project / "scripts" / "compile_tikz.py"
    if not script.is_file():
        raise SystemExit(f"no existe {script}")
    proc = subprocess.run(
        [sys.executable, str(script), f"{name}:{kind}"],
        capture_output=True,
        text=True,
        cwd=str(project),
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def parse_overfull(stdout: str, name: str) -> tuple[int, float | None, int | None]:
    for match in OVERFULL_LINE_RE.finditer(stdout):
        if match.group("name") != name:
            continue
        count = int(match.group("count"))
        pt = float(match.group("pt")) if match.group("pt") else None
        line = int(match.group("line")) if match.group("line") else None
        return count, pt, line
    return -1, None, None


def _rel(path: pathlib.Path, project: pathlib.Path) -> str:
    """Project-relative path for reporting; the raw path when it is outside."""
    try:
        return str(path.resolve().relative_to(project))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "name",
        help="id del diagrama: coincide con specs/<name>.spec.json y produce "
             "sections/diag_<name>.tex + figuras/fig_<name>-*.png. Convención: "
             "arbol_problemas, estado_arte[_a|_b], metodologico",
    )
    ap.add_argument("--spec", type=pathlib.Path, required=False, help="spec JSON de la figura")
    ap.add_argument("--project", type=pathlib.Path, help="raíz del proyecto LaTeX (por defecto: cwd)")
    ap.add_argument("--kind", default="tikz", help="kind del compilador: tikz (por defecto) o gantt")
    ap.add_argument("--budget-s", type=float, default=180.0, help="presupuesto de reloj en segundos")
    ap.add_argument(
        "--page-fit",
        metavar="WxH",
        default="none",
        help="presupuesto de página en cm, p. ej. '16x22' para A4 con márgenes de 2.5 cm. "
             "Por defecto 'none': el tamaño se REPORTA siempre, pero solo se exige cuando "
             "el operador pide que la figura quepa a tamaño natural (si main.tex la escala "
             "con resizebox, un FAIL aquí sería un falso positivo)",
    )
    ap.add_argument("--json", action="store_true", help="imprime el reporte JSON en stdout")
    args = ap.parse_args(argv)

    started = time.monotonic()
    project = (args.project or pathlib.Path.cwd()).resolve()
    spec_path = (args.spec or (project / "specs" / f"{args.name}.spec.json")).resolve()
    if not spec_path.is_file():
        raise SystemExit(f"no existe la spec {spec_path}")

    render_mod = _load_sibling("render_tikz")
    audit_mod = _load_sibling("audit_tikz")

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    out_tex = project / "sections" / f"diag_{args.name}.tex"
    over_path = spec_path.with_name(f"{args.name}.overrides.json")

    steps: list[dict] = []
    iterations = 0
    compile_stdout = ""

    # ---- render + compile + autofix -------------------------------------
    render_argv = [str(spec_path), "-o", str(out_tex)]
    if over_path.is_file():
        render_argv += ["--overrides", str(over_path)]
    with _quiet_stdout(args.json):
        render_mod.main(render_argv)

    while True:
        iterations += 1
        t0 = time.monotonic()
        with _quiet_stdout(args.json):
            rc, compile_stdout = run_compile(project, args.name, args.kind)
        steps.append(
            {
                "step": f"compile#{iterations}",
                "s": round(time.monotonic() - t0, 3),
                "rc": rc,
            }
        )
        if rc != 0:
            tail = "\n".join(compile_stdout.strip().splitlines()[-12:])
            print(f"COMPILE FAILED ({args.name}); últimas líneas:\n{tail}", file=sys.stderr)
            return 1

        count, pt, line = parse_overfull(compile_stdout, args.name)
        if count <= 0:
            break
        if line is None or pt is None:
            print(
                f"OVERFULL sin línea mapeada ({count} occurrence(s)); no se puede "
                "aplicar el autofix determinista. Revisa la spec a mano.",
                file=sys.stderr,
            )
            return 1
        if iterations >= MAX_FIX_ITERATIONS:
            print(
                f"autofix no convergió en {MAX_FIX_ITERATIONS} iteraciones "
                f"({count} occurrence(s) restantes). Revisa la spec.",
                file=sys.stderr,
            )
            return 1

        t0 = time.monotonic()
        fix_argv = [str(spec_path), "-o", str(out_tex), "--overrides", str(over_path),
                    "--fix-overfull", f"{line}:{pt}"]
        with _quiet_stdout(args.json):
            render_mod.main(fix_argv)
        steps.append({"step": f"autofix#{iterations}", "s": round(time.monotonic() - t0, 3)})

    # ---- audit -----------------------------------------------------------
    page_fit = None
    if args.page_fit and args.page_fit.lower() not in ("none", "0x0"):
        m = re.match(r"^\s*([0-9.]+)\s*x\s*([0-9.]+)\s*$", args.page_fit)
        if not m:
            raise SystemExit("--page-fit espera 'WxH' en cm, p. ej. 16x22")
        page_fit = (float(m.group(1)), float(m.group(2)))

    t0 = time.monotonic()
    report = audit_mod.audit(args.name, project, spec, compile_stdout, page_fit)
    steps.append({"step": "audit", "s": round(time.monotonic() - t0, 3)})

    elapsed = time.monotonic() - started
    within_budget = elapsed <= args.budget_s
    result = {
        "name": args.name,
        "verdict": report["verdict"],
        "iterations": iterations,
        "elapsed_s": round(elapsed, 2),
        "budget_s": args.budget_s,
        "within_budget": within_budget,
        "steps": steps,
        "audit": report,
        "outputs": {
            "tex": _rel(out_tex, project),
            "png": f"sections/figuras/fig_{args.name}-1.png",
            "svg": f"sections/figuras/fig_{args.name}.svg",
            "overrides": _rel(over_path, project) if over_path.is_file() else None,
        },
        "page_fit_cm": page_fit,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            f"FIGURA {result['verdict']}: {args.name} "
            f"({elapsed:.2f}s, {iterations} compilación(es), "
            f"presupuesto {args.budget_s:.0f}s {'OK' if within_budget else 'EXCEDIDO'})"
        )
        for check in report["checks"]:
            if not check["ok"]:
                print(f"  [FAIL] {check['id']}: {check['detail']}")
        for output in result["outputs"].values():
            if output:
                print(f"  -> {output}")

    if not within_budget:
        print(
            f"PRESUPUESTO EXCEDIDO: {elapsed:.1f}s > {args.budget_s:.0f}s",
            file=sys.stderr,
        )
        return 1
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
