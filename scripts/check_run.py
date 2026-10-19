#!/usr/bin/env python3
"""Deterministic checks for a proposal run, run by the dispatcher before each gate.

The revisor agent judges coherence and quality; this script covers what a
regular expression can prove, so the agent does not spend tokens re-deriving
it and a violation cannot slip through a gate (two em dashes in §10 of the
reference run did). Standard library only: every runtime (Claude Code, Pi,
OpenCode, Antigravity) runs it the same way.

Usage:
  python3 scripts/check_run.py [RUN_ROOT] [--final] [--json]

RUN_ROOT defaults to the run named in proposals/.current-run. Without --final,
only files that already exist are checked (a mid-pipeline gate); --final also
requires every canonical section, a filled cover and the total reference
floor. Exit code 1 when any error is found.

Reference floors come from guiaProyectosIA_Agente.md (§2 "al menos 13
referencias", §4 "al menos 39 referencias", §16 total of 65); a test keeps
these constants and the guide in step.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FLOOR_JUSTIFICACION = 13
FLOOR_ESTADO_ARTE = 39
FLOOR_TOTAL = 65
MAX_KEYS_PER_CALL = 3
MAX_USES_PER_KEY = 3

CANONICAL_SECTIONS = (
    "00_frontmatter", "02_justificacion", "03_descripcion_problema", "04_estado_arte",
    "05_hipotesis", "06_objetivo_general", "07_objetivos_especificos", "08_marco_conceptual",
    "09_equipo_trabajo", "10_metodologia", "11_resultados_esperados", "12_consideraciones_eticas",
    "13_presupuesto", "14_cronograma_actividades", "15_productos_esperados", "16_bibliografia",
    "17_articulacion_comunidades", "18_apropiacion_social",
)

# Environments whose content is not narrative prose (tables, drawings, code, math)
NON_PROSE_ENVS = (
    "tabular", "tabularx", "xltabular", "longtable", "tikzpicture", "ganttchart",
    "verbatim", "lstlisting", "equation", "align", "math", "displaymath",
)
CITE_RE = re.compile(
    r"\\(cite|citep|citet|citealp|citealt|citeauthor|citeyear|citeyearpar|nocite)\*?"
    r"(?:\[[^\]]*\]){0,2}\{([^}]*)\}",
    re.S,
)
BEGIN_RE = re.compile(r"\\begin\{(" + "|".join(NON_PROSE_ENVS) + r")\*?\}")
END_RE = re.compile(r"\\end\{(" + "|".join(NON_PROSE_ENVS) + r")\*?\}")


def strip_comment(line: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", line)


class Report:
    def __init__(self, run_root: Path) -> None:
        self.run_root = run_root
        self.findings: list[dict] = []

    def add(self, severity: str, code: str, message: str, path: Path | None = None, line: int | None = None) -> None:
        rel = ""
        if path is not None:
            try:
                rel = path.relative_to(self.run_root).as_posix()
            except ValueError:
                rel = str(path)
        self.findings.append({"severity": severity, "code": code, "file": rel, "line": line, "message": message})

    def errors(self) -> int:
        return sum(1 for f in self.findings if f["severity"] == "error")


def prose_lines(text: str):
    """Yield (line number, text) for narrative lines: no comments, tables, drawings or math."""
    depth = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = strip_comment(raw)
        opens, closes = len(BEGIN_RE.findall(line)), len(END_RE.findall(line))
        if depth == 0 and opens == 0:
            prose = re.sub(r"\\url\{[^}]*\}|\\href\{[^}]*\}", "", line)
            prose = re.sub(r"\$[^$]*\$", "", prose)
            yield number, prose
        depth = max(0, depth + opens - closes)


def cite_calls(text: str):
    """Yield (line number, keys) for each logical citation call, comments removed."""
    clean = "\n".join(strip_comment(l) for l in text.splitlines())
    for match in CITE_RE.finditer(clean):
        keys = [k.strip() for k in match.group(2).split(",") if k.strip()]
        yield clean.count("\n", 0, match.start()) + 1, match.group(1), keys


def check_prose(report: Report, path: Path, text: str) -> None:
    for number, line in prose_lines(text):
        if "—" in line or "---" in line:
            report.add("error", "raya-en-prosa", "Raya (— o ---) en prosa: usar coma, punto y coma o paréntesis.",
                       path, number)
        if "--" in line.replace("---", ""):
            report.add("error", "doble-guion-en-prosa", "Doble guion (--) en prosa.", path, number)


def check_citations(report: Report, sections: dict[str, Path], texts: dict[str, str]) -> dict[str, set[str]]:
    keys_by_section: dict[str, set[str]] = {}
    total_uses: dict[str, int] = {}
    first_seen: dict[str, tuple[Path, int]] = {}
    for name, path in sections.items():
        seen_here: set[str] = set()
        keys_by_section[name] = set()
        for number, command, keys in cite_calls(texts[name]):
            if command == "cite":
                report.add("error", "cite-generico", "\\cite{} genérico: usar \\citep{} o \\citet{} (APA autor-año).",
                           path, number)
            if command != "nocite" and len(keys) > MAX_KEYS_PER_CALL:
                report.add("error", "cita-mas-de-3-claves",
                           f"Llamada con {len(keys)} claves (máximo {MAX_KEYS_PER_CALL}).", path, number)
            for key in keys:
                if command == "nocite":
                    continue
                keys_by_section[name].add(key)
                if key in seen_here:
                    report.add("error", "clave-repetida-en-seccion",
                               f"La clave {key} se cita dos veces en la misma sección.", path, number)
                seen_here.add(key)
                total_uses[key] = total_uses.get(key, 0) + 1
                first_seen.setdefault(key, (path, number))
    for key, uses in sorted(total_uses.items()):
        if uses > MAX_USES_PER_KEY:
            path, number = first_seen[key]
            report.add("error", "clave-sobreusada",
                       f"La clave {key} se usa {uses} veces (máximo {MAX_USES_PER_KEY}).", path, number)
    return keys_by_section


def check_floors(report: Report, sections: dict[str, Path], keys_by_section: dict[str, set[str]], final: bool) -> None:
    for name, floor in (("02_justificacion", FLOOR_JUSTIFICACION), ("04_estado_arte", FLOOR_ESTADO_ARTE)):
        if name in keys_by_section and len(keys_by_section[name]) < floor:
            report.add("error", "piso-referencias",
                       f"{name} cita {len(keys_by_section[name])} referencias distintas (mínimo {floor}).",
                       sections[name])
    if final:
        total = set().union(*keys_by_section.values()) if keys_by_section else set()
        if len(total) < FLOOR_TOTAL:
            report.add("error", "piso-referencias",
                       f"El documento cita {len(total)} referencias distintas (mínimo {FLOOR_TOTAL}).")


def check_trl(report: Report, sections: dict[str, Path], texts: dict[str, str]) -> None:
    trl = re.compile(r"\bTRL\b")
    for name in ("06_objetivo_general", "07_objetivos_especificos"):
        if name in texts:
            for number, line in prose_lines(texts[name]):
                if trl.search(line):
                    report.add("error", "trl-en-objetivos",
                               "TRL nombrado en un objetivo: expresar el nivel de forma funcional.",
                               sections[name], number)
    for name in ("02_justificacion", "11_resultados_esperados"):
        if name in texts and not any(trl.search(l) for _, l in prose_lines(texts[name])):
            report.add("error", "trl-ausente", "TRL 6 o 7 debe ser explícito en esta sección.", sections[name])
    if "10_metodologia" in texts and not trl.search(texts["10_metodologia"]):
        report.add("warning", "trl-ausente", "El revisor espera la trayectoria TRL en la metodología.",
                   sections["10_metodologia"])


def check_objectives(report: Report, sections: dict[str, Path], texts: dict[str, str]) -> None:
    name = "07_objetivos_especificos"
    if name not in texts:
        return
    match = re.search(r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}", texts[name], re.S)
    items = len(re.findall(r"^\s*\\item\b", match.group(1), re.M)) if match else 0
    if items != 3:
        report.add("error", "objetivos-no-son-3",
                   f"§7 enumera {items} objetivos específicos; el mapeo 1:1 exige 3.", sections[name])


def check_main(report: Report, red: Path, final: bool) -> None:
    main = red / "main.tex"
    if not main.is_file():
        if final:
            report.add("error", "main-ausente", "No existe redaccion/main.tex.")
        return
    text = main.read_text(encoding="utf-8", errors="replace")
    clean = "\n".join(strip_comment(l) for l in text.splitlines())
    if r"\setcounter{section}{1}" not in clean:
        report.add("error", "setcounter-ausente", "main.tex debe fijar \\setcounter{section}{1} (el cuerpo arranca en §2).",
                   main)
    if re.search(r"\\input\{sections/01_", clean):
        report.add("error", "seccion-1-en-cuerpo", "main.tex incluye una sección §1; el título va solo en la portada.",
                   main)
    for number, line in enumerate(text.splitlines(), start=1):
        line = strip_comment(line)
        for logo in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{(logos/[^}]+)\}", line):
            if "IfFileExists" in line:
                continue
            if not (red / logo).is_file():
                report.add("error", "logo-inexistente", f"{logo} no existe en redaccion/.", main, number)
    if r"\DiagramaSiExiste" in clean:
        for diag in sorted((red / "sections").glob("diag_*.tex")):
            if diag.stem.endswith("_caption"):
                continue
            if not (red / "sections" / f"{diag.stem}_caption.tex").is_file():
                report.add("error" if final else "warning", "caption-faltante",
                           f"{diag.name} no tiene {diag.stem}_caption.tex (caption concreto y \\label).", diag)


def check_cover(report: Report, red: Path, final: bool) -> None:
    datos = red / "datos_proyecto.tex"
    if datos.is_file() and "[Por definir" in datos.read_text(encoding="utf-8", errors="replace"):
        report.add("error" if final else "warning", "portada-sin-completar",
                   "datos_proyecto.tex conserva campos [Por definir: ...].", datos)


def check_bibliography(report: Report, sections: dict[str, Path], texts: dict[str, str]) -> None:
    name = "16_bibliografia"
    if name not in texts:
        return
    clean = "\n".join(strip_comment(l) for l in texts[name].splitlines())
    if r"\renewcommand{\bibsection}{}" not in clean:
        report.add("error", "bibsection-ausente", "Falta \\renewcommand{\\bibsection}{} (título duplicado).",
                   sections[name])
    if r"\clearpage" not in clean:
        report.add("warning", "clearpage-ausente", "La bibliografía debe abrir con \\clearpage.", sections[name])


def check_pdf(report: Report, red: Path) -> None:
    pdf = red / "main.pdf"
    if not pdf.is_file() or shutil.which("pdftotext") is None:
        return
    result = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True)
    for match in re.finditer(r"\bCuadro \d+", result.stdout):
        report.add("error", "cuadro-en-pdf", f"El PDF dice «{match.group(0)}»: las tablas se llaman «Tabla».", pdf)
        break


def run_checks(run_root: Path, final: bool) -> Report:
    report = Report(run_root)
    red = run_root / "redaccion"
    sec_dir = red / "sections"
    if not sec_dir.is_dir():
        report.add("error", "corrida-invalida", f"No existe {sec_dir}.")
        return report

    for stray in sorted(sec_dir.glob("01_titulo*.tex")):
        report.add("error", "seccion-1-en-cuerpo",
                   "No debe existir un archivo de §1: el título va solo en la portada de main.tex.", stray)

    sections = {name: sec_dir / f"{name}.tex" for name in CANONICAL_SECTIONS if (sec_dir / f"{name}.tex").is_file()}
    texts = {name: path.read_text(encoding="utf-8", errors="replace") for name, path in sections.items()}
    if final:
        for name in CANONICAL_SECTIONS:
            if name not in sections:
                report.add("error", "seccion-faltante", f"Falta sections/{name}.tex.")

    prose_files = list(sections.items()) + [(p.stem, p) for p in sorted(sec_dir.glob("diag_*_caption.tex"))]
    for name, path in prose_files:
        check_prose(report, path, texts.get(name) or path.read_text(encoding="utf-8", errors="replace"))

    keys_by_section = check_citations(report, sections, texts)
    check_floors(report, sections, keys_by_section, final)
    check_trl(report, sections, texts)
    check_objectives(report, sections, texts)
    check_main(report, red, final)
    check_cover(report, red, final)
    check_bibliography(report, sections, texts)
    check_pdf(report, red)
    return report


def resolve_run_root(arg: str | None) -> Path:
    if arg:
        return Path(arg).resolve()
    pointer = Path("proposals/.current-run")
    if not pointer.is_file():
        raise SystemExit("error: no RUN_ROOT given and proposals/.current-run does not exist")
    return Path("proposals", pointer.read_text(encoding="utf-8").strip()).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_root", nargs="?", help="run folder (default: the active run)")
    parser.add_argument("--final", action="store_true", help="also require every section, the cover and total floor")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    args = parser.parse_args()

    report = run_checks(resolve_run_root(args.run_root), args.final)
    if args.json:
        print(json.dumps(report.findings, ensure_ascii=False, indent=2))
    else:
        for f in report.findings:
            where = f["file"] + (f":{f['line']}" if f["line"] else "")
            print(f"[{f['severity'].upper()}] {f['code']} {where} {f['message']}".rstrip())
        warnings = len(report.findings) - report.errors()
        print(f"check_run: {report.errors()} errores, {warnings} avisos")
    return 1 if report.errors() else 0


if __name__ == "__main__":
    sys.exit(main())
