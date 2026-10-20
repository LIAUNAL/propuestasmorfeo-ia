"""Implementation of 'morfeo status' with comprehensive workspace introspection."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from ..errors import UserError
from .pipeline_units import canonical_gates, normalise_gate, units_for_flujo


SECTION_TITLES = {
    "00_frontmatter": "§0 Front-matter (Resumen, Resumen ejecutivo, Palabras clave)",
    "02_justificacion": "§2 Justificación y pertinencia (TRL 6/7)",
    "03_descripcion_problema": "§3 Descripción del problema y pregunta de investigación",
    "04_estado_arte": "§4 Estado del arte (≥30 refs Q1/Q2)",
    "05_hipotesis": "§5 Hipótesis de investigación",
    "06_objetivo_general": "§6 Objetivo general",
    "07_objetivos_especificos": "§7 Objetivos específicos (mapeo 1:1 con subproblemas)",
    "08_marco_conceptual": "§8 Marco conceptual",
    "09_equipo_trabajo": "§9 Equipo de trabajo (roles derivados de §7)",
    "10_metodologia": "§10 Metodología articulada",
    "11_resultados_esperados": "§11 Resultados esperados",
    "12_consideraciones_eticas": "§12 Consideraciones éticas y protección de datos",
    "13_presupuesto": "§13 Presupuesto de rubros y cofinanciación",
    "14_cronograma_actividades": "§14 Cronograma de actividades (Gantt a 12 meses)",
    "15_productos_esperados": "§15 Productos entregables comprometidos",
    "16_bibliografia": "§16 Bibliografía consolidada (APA)",
    "17_articulacion_comunidades": "§17 Articulación con comunidades y actores territoriales",
    "18_apropiacion_social": "§18 Estrategia de acceso y apropiación social del conocimiento",
    # Anexos MGA del flujo SGR (solo existen cuando la corrida los produce).
    "19_alineacion_planes": "§19 Alineación con los planes de desarrollo",
    "20_participantes": "§20 Análisis de participantes",
    "21_poblacion": "§21 Población afectada y objetivo",
    "22_alternativas": "§22 Alternativas de solución",
    "23_cadena_valor": "§23 Cadena de valor",
    "24_riesgos": "§24 Análisis de riesgos",
    "25_marco_logico": "§25 Matriz de marco lógico",
}

VALID_FLUJOS = ("base", "sgr")


def read_flujo(target_dir: Path) -> str:
    """Return the project flow from `.morfeo/config.json`, then `.marco/config.json`.

    A project created before the flag existed has no `flujo` key and is `base`.
    """
    for marker in (".morfeo", ".marco"):
        cfile = target_dir / marker / "config.json"
        if not cfile.is_file():
            continue
        try:
            value = json.loads(cfile.read_text(encoding="utf-8")).get("flujo")
        except Exception:
            continue
        if value in VALID_FLUJOS:
            return value
    return "base"

# La lista canónica se deriva del inventario de unidades, no se escribe aquí. Antes
# este bloque la duplicaba y las dos copias se contradecían: faltaban G1a y G1b,
# que la corrida de referencia sí pasó, y sobraban G6 y G6.45, que la tabla de
# pasos declara sin compuerta.
CANONICAL_GATES: list[dict[str, Any]] = canonical_gates()

_PDF_PAGE_CACHE: dict[str, tuple[float, int, int]] = {}


def _count_pdf_pages(pdf_path: Path) -> int:
    """Best-effort page count for PDF using cached pdfinfo or binary inspection."""
    if not pdf_path.is_file():
        return 0
    try:
        stat = pdf_path.stat()
        mtime, size = stat.st_mtime, stat.st_size
        cache_key = str(pdf_path.resolve())
        cached = _PDF_PAGE_CACHE.get(cache_key)
        if cached and cached[0] == mtime and cached[1] == size:
            return cached[2]

        pages = 0
        try:
            import subprocess
            res = subprocess.run(
                ["pdfinfo", str(pdf_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1.5,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if line.startswith("Pages:"):
                        pages = int(line.split(":")[1].strip())
                        break
        except Exception:
            pass

        if pages == 0:
            data = pdf_path.read_bytes()
            pages = len(re.findall(b"/Type\\s*/Page\\b", data))

        if pages > 0:
            _PDF_PAGE_CACHE[cache_key] = (mtime, size, pages)
        return pages
    except Exception:
        return 0


def parse_run_metadata(run_dir: Path) -> dict[str, Any]:
    run_md = run_dir / "_run.md"
    meta: dict[str, Any] = {
        "idea": "",
        "created": "",
        "status": "activa",
        "title": "",
    }
    if not run_md.is_file():
        return meta

    text = run_md.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if "|" in line:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 2:
                key, val = parts[0].lower(), parts[1]
                if "idea" in key:
                    meta["idea"] = val
                elif "creada" in key:
                    meta["created"] = val
                elif "estado" in key:
                    meta["status"] = val

    # Attempt to extract title from main.tex if available
    main_tex = run_dir / "redaccion" / "main.tex"
    if main_tex.is_file():
        m = re.search(r"\\(?:LARGE|Large|large)\\bfseries\s+([^}\\]+)", main_tex.read_text(encoding="utf-8", errors="replace"))
        if m:
            meta["title"] = m.group(1).strip()
    # Runs created from plantilla/main.tex keep the title in datos_proyecto.tex
    datos = run_dir / "redaccion" / "datos_proyecto.tex"
    if not meta["title"] and datos.is_file():
        m = _TITLE_MACRO.search(datos.read_text(encoding="utf-8", errors="replace"))
        if m and not m.group(1).strip().startswith("[Por definir"):
            meta["title"] = m.group(1).strip()
    if not meta["title"]:
        meta["title"] = meta["idea"]

    return meta


_FIGURE_INCLUDE = re.compile(r"\\input\{sections/diag_[^}]*\}|\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}")
_SECTION_INPUT = re.compile(r"\\input\{sections/((?!diag_)[^}#]+?)(?:\.tex)?\}")
# plantilla/main.tex places sections and diagrams through these macros; a
# diagram only exists in the document when its file does.
_TEMPLATE_SECTION = re.compile(r"\\SeccionSiExiste\{([^}#]+)\}")
_TEMPLATE_FIGURE = re.compile(r"\\DiagramaSiExiste\{(diag_[^}#]+)\}")
_TITLE_MACRO = re.compile(r"\\newcommand\{\\TituloProyecto\}\{(.+)\}\s*$", re.M)


def _strip_tex_comments(raw: str) -> str:
    """Drop `%` comments, keeping escaped `\\%` literals."""
    return re.sub(r"(?<!\\)%.*", "", raw)


def _main_tex_figures(run_dir: Path) -> dict[str, int]:
    """Figures `main.tex` places after each section's `\\input`.

    The diagrams are not inside the section files: `main.tex` includes them
    right after the section that owns them, so a figure include belongs to the
    last section `\\input` that precedes it. Includes before the first section
    (header logos) belong to no section.
    """
    main_tex = run_dir / "redaccion" / "main.tex"
    if not main_tex.is_file():
        return {}
    text = _strip_tex_comments(main_tex.read_text(encoding="utf-8", errors="replace"))
    counts: dict[str, int] = {}
    current: str | None = None
    sections_dir = run_dir / "redaccion" / "sections"
    tokens = sorted(
        [(m.start(), "section", m.group(1)) for m in _SECTION_INPUT.finditer(text)]
        + [(m.start(), "section", m.group(1)) for m in _TEMPLATE_SECTION.finditer(text)]
        + [(m.start(), "figure", "") for m in _FIGURE_INCLUDE.finditer(text)]
        + [(m.start(), "figure", "") for m in _TEMPLATE_FIGURE.finditer(text)
           if (sections_dir / f"{m.group(1)}.tex").is_file()]
    )
    for _, kind, value in tokens:
        if kind == "section":
            current = Path(value).name
            counts.setdefault(current, 0)
        elif current is not None:
            counts[current] = counts.get(current, 0) + 1
    return counts


def parse_sections_info(run_dir: Path) -> list[dict[str, Any]]:
    sections_dir = run_dir / "redaccion" / "sections"
    if not sections_dir.is_dir():
        return []

    placed_figures = _main_tex_figures(run_dir)

    sections: list[dict[str, Any]] = []
    for f in sorted(sections_dir.glob("*.tex")):
        if f.name.startswith("diag_"):
            continue

        raw = f.read_text(encoding="utf-8", errors="replace")
        clean = re.sub(r"%.*", "", raw)
        words = len(clean.split())
        cites = len(re.findall(r"\\cite[pt]?\{([^}]+)\}", raw))
        stem = f.stem
        # A figure either lives in the section file or is placed by main.tex
        # right after the section's \\input (see _main_tex_figures).
        figures_count = len(_FIGURE_INCLUDE.findall(_strip_tex_comments(raw))) + placed_figures.get(stem, 0)
        has_tikz = figures_count > 0

        # Extract title from leading comment or fall back to map
        m = re.search(r"%\s*(§\d+[a-z]?\s+[^%\n]+)", raw)
        title = m.group(1).strip() if m else SECTION_TITLES.get(stem, stem)

        # Status heuristic
        status = "SEALED" if words > 50 else "DRAFTING"
        if stem == "16_bibliografia":
            status = "SEALED"  # typically just carries \bibliography{}

        sections.append({
            "id": stem,
            "filename": f.name,
            "title": title,
            "words": words,
            "citations": cites,
            "has_figures": has_tikz,
            "figures_count": figures_count,
            "status": status,
        })

    return sections


def parse_gates_info(run_dir: Path, flujo: str | None = None) -> list[dict[str, Any]]:
    """Gate verdicts of a run; with `flujo`, only that flow's gates are listed."""
    estado_file = run_dir / "artefactos" / "estado_propuesta.md"
    pipeline_file = run_dir / "artefactos" / "pipeline" / "_estado.md"

    recorded_gates: dict[str, str] = {}
    if pipeline_file.is_file():
        for line in pipeline_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if "|" in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3 and parts[1] != "Gate":
                    fase_id = parts[0].strip()
                    gate_id = parts[1].strip()
                    verdict = parts[2].strip()
                    if gate_id and gate_id != "none" and gate_id != "—":
                        recorded_gates[gate_id] = verdict
                    if fase_id and fase_id.startswith("fase"):
                        recorded_gates[fase_id] = verdict

    if estado_file.is_file():
        content_estado = estado_file.read_text(encoding="utf-8", errors="replace")
        for line in content_estado.splitlines():
            if "|" in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2 and parts[0].startswith("G") and parts[0] not in recorded_gates:
                    recorded_gates[parts[0]] = parts[1]
        # Check explicit G0.5 approval if missing
        if "G0.5" not in recorded_gates:
            if re.search(r"G0\.5\s*=\s*APROBADA", content_estado, re.IGNORECASE) or re.search(r"G0\.5[^\n]+PASS", content_estado, re.IGNORECASE):
                recorded_gates["G0.5"] = "PASS"

    result: list[dict[str, Any]] = []
    for g in (CANONICAL_GATES if flujo is None else canonical_gates(flujo)):
        status = "PENDING"
        gid_lower = g["id"].lower()
        phase_key = g["phase"].lower().replace(" ", "").replace(".", "_")

        for rk, rv in recorded_gates.items():
            rk_lower = rk.lower()
            matched = False
            if gid_lower in rk_lower or rk_lower in gid_lower:
                matched = True
            elif phase_key == rk_lower or phase_key.replace("_", "") == rk_lower:
                matched = True
            elif gid_lower == "g0.5" and ("0.5" in rk_lower or rk_lower == "fase0"):
                matched = True
            elif gid_lower == "g6" and rk_lower == "fase6":
                matched = True
            elif gid_lower == "g6.4" and ("presupuesto" in rk_lower or rk_lower == "fase6_4"):
                matched = True
            elif gid_lower == "g6.45" and rk_lower == "fase6_45":
                matched = True
            elif gid_lower in ("g6.46", "g comunidades") and ("comunidades" in rk_lower or rk_lower == "fase6_46"):
                matched = True
            elif gid_lower == "g6.5" and ("front" in rk_lower or rk_lower == "fase6_5"):
                matched = True
            elif gid_lower == "g7" and ("final" in rk_lower or rk_lower == "fase7"):
                matched = True

            if matched:
                if "pass" in rv.lower() or "aprobada" in rv.lower():
                    status = "PASS"
                elif "fail" in rv.lower():
                    status = "FAIL"
                elif "bloqueada" in rv.lower():
                    status = "BLOCKED"
                break

        result.append({
            **g,
            "status": status,
        })

    return result


def parse_telemetry_info(run_dir: Path) -> list[dict[str, Any]]:
    pipeline_file = run_dir / "artefactos" / "pipeline" / "_estado.md"
    if not pipeline_file.is_file():
        return []

    rows: list[dict[str, Any]] = []
    for line in pipeline_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if "|" in line:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 7 and not parts[0].startswith("---") and parts[0].lower() != "fase":
                rows.append({
                    "fase": parts[0],
                    "gate": parts[1],
                    "veredicto": parts[2],
                    "fecha": parts[3],
                    "tokens": parts[4],
                    "tool_uses": parts[5],
                    "duracion": parts[6],
                })
    return rows


def parse_in_progress(run_dir: Path) -> dict[str, Any] | None:
    """Latido de la unidad que el dispatcher está ejecutando ahora mismo.

    Lo escribe el dispatcher al abrir una unidad y lo borra al cerrarla. Es lo
    único que permite mostrar qué agente se está levantando **mientras** ocurre,
    porque `artefactos/pipeline/NN-fase*.md` se escribe por evento, es decir al
    terminar. Un latido a medio escribir se ignora en lugar de tumbar el tablero.
    """
    beat = run_dir / "artefactos" / "pipeline" / "_en_curso.json"
    if not beat.is_file():
        return None
    try:
        data = json.loads(beat.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("fase"):
        return None

    agentes = data.get("agentes") or []
    if isinstance(agentes, str):
        agentes = [agentes]
    return {
        "fase": str(data.get("fase")),
        "agentes": [str(a) for a in agentes],
        "skill": data.get("skill") or None,
        "artefacto_esperado": data.get("artefacto_esperado") or None,
        "inicio": data.get("inicio") or None,
        "nota": data.get("nota") or None,
    }


def parse_execution_control(run_dir: Path) -> dict[str, Any] | None:
    """Bloque «Control de ejecución» de `artefactos/estado_propuesta.md`.

    `next_step` es la unidad que `/propuesta-continuar` va a correr; el tablero
    lo usa para habilitar su botón «Ejecutar» solo sobre esa unidad. Sin bloque
    (corrida recién creada o limpiada) devuelve None.
    """
    estado = run_dir / "artefactos" / "estado_propuesta.md"
    if not estado.is_file():
        return None
    text = estado.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^##\s*Control de ejecuci[oó]n\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if not match:
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        item = re.match(r"^\s*[-*]\s*([a-z_]+)\s*:\s*(.*?)\s*$", line)
        if item:
            fields[item.group(1)] = item.group(2)
    if not fields:
        return None
    return {
        "mode": fields.get("mode") or None,
        "next_step": fields.get("next_step") or None,
        "next_command": fields.get("next_command") or None,
        "last_completed": fields.get("last_completed") or None,
        "intake_complete": fields.get("intake_complete", "").lower() == "true",
    }


def count_user_inputs(run_dir: Path) -> int:
    """Archivos que el usuario dejó en `insumos/`, sin el README que siembra
    `/propuesta-insumos` ni archivos ocultos."""
    insumos = run_dir / "insumos"
    if not insumos.is_dir():
        return 0
    return sum(
        1
        for f in insumos.rglob("*")
        if f.is_file() and not f.name.startswith(".") and f.name != "README.md"
    )


def list_artifacts_info(run_dir: Path) -> list[dict[str, Any]]:
    art_dir = run_dir / "artefactos"
    if not art_dir.is_dir():
        return []

    items: list[dict[str, Any]] = []
    for f in sorted(art_dir.glob("*.md")):
        items.append({
            "name": f.name,
            "rel_path": f"artefactos/{f.name}",
            "size": f.stat().st_size,
        })
    return items


_STATUS_CACHE: dict[str, tuple[float, dict]] = {}


def _package_version() -> str:
    """Version of the running package, the fallback for a workspace that carries
    no `.marco/version` marker (this framework repository is one). It used to be
    the frozen literal `0.5.0`, which `marco status` kept printing several
    releases later.
    """
    from .. import __version__

    return __version__


def get_project_status(target_dir: Path, force_refresh: bool = False) -> dict:
    target_dir = target_dir.resolve()
    cache_key = str(target_dir)
    now = time.time()
    if not force_refresh:
        cached = _STATUS_CACHE.get(cache_key)
        if cached and (now - cached[0] < 1.5):
            return cached[1]

    version = _package_version()
    # Flujo del proyecto (`base` o `sgr`): decide qué unidades y compuertas le tocan.
    flujo = read_flujo(target_dir)
    flow_gates = canonical_gates(flujo)
    workspace_title = None
    marker = target_dir / ".morfeo"
    if not marker.is_dir():
        marker = target_dir / ".marco"
    if marker.is_dir():
        vfile = marker / "version"
        if vfile.is_file():
            version = vfile.read_text(encoding="utf-8").strip()
        cfile = marker / "config.json"
        if cfile.is_file():
            try:
                cfg = json.loads(cfile.read_text(encoding="utf-8"))
                workspace_title = cfg.get("title")
            except Exception:
                pass
    elif not ((target_dir / "proposals").is_dir() or (target_dir / "guiaProyectosIA_Agente.md").is_file()):
        raise UserError(f"No es un espacio de trabajo Morfeo válido: {target_dir}")

    current_run_pointer = target_dir / "proposals" / ".current-run"
    active_run = None
    if current_run_pointer.is_file():
        active_run = current_run_pointer.read_text(encoding="utf-8").strip()

    run_info: dict[str, Any] = {}
    sections: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    telemetria: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    en_curso: dict[str, Any] | None = None
    control: dict[str, Any] | None = None
    totals: dict[str, Any] = {
        "sections_count": 0,
        "total_words": 0,
        "total_citations": 0,
        "bibtex_entries": 0,
        "gates_passed": 0,
        "gates_total": len(flow_gates),
        "total_tokens": "0",
        "total_tool_uses": 0,
        "pdf_pages": 0,
    }

    if active_run:
        run_dir = target_dir / "proposals" / active_run
        if run_dir.is_dir():
            run_meta = parse_run_metadata(run_dir)
            run_info["id"] = active_run
            run_info["dir"] = str(run_dir)
            run_info["title"] = run_meta["title"]
            run_info["idea"] = run_meta["idea"]
            run_info["created"] = run_meta["created"]
            run_info["status"] = run_meta["status"]
            en_curso = parse_in_progress(run_dir)
            control = parse_execution_control(run_dir)
            run_info["insumos_count"] = count_user_inputs(run_dir)
            run_info["run_md"] = (run_dir / "_run.md").is_file()

            # Files
            main_pdf = run_dir / "redaccion" / "main.pdf"
            main_docx = run_dir / "redaccion" / "main.docx"
            run_info["pdf_ready"] = main_pdf.is_file()
            run_info["pdf_size"] = main_pdf.stat().st_size if main_pdf.is_file() else 0
            run_info["pdf_pages"] = _count_pdf_pages(main_pdf)
            run_info["docx_ready"] = main_docx.is_file()
            run_info["docx_size"] = main_docx.stat().st_size if main_docx.is_file() else 0

            # Graphs
            run_info["papers_graph"] = (run_dir / "grafos" / "papers-graph.html").is_file()
            run_info["vault_graph"] = (run_dir / "grafos" / "vault-graph.html").is_file()

            # Sections, gates, telemetry, artifacts
            sections = parse_sections_info(run_dir)
            gates = parse_gates_info(run_dir, flujo)
            telemetria = parse_telemetry_info(run_dir)
            artifacts = list_artifacts_info(run_dir)

            # BibTeX entries
            bib_file = run_dir / "redaccion" / "refs.bib"
            bib_entries = 0
            if bib_file.is_file():
                bib_entries = len(re.findall(r"@\w+\{([^,]+),", bib_file.read_text(encoding="utf-8", errors="replace")))

            # Totals
            total_words = sum(s["words"] for s in sections)
            total_citations = sum(s["citations"] for s in sections)
            gates_passed = sum(1 for g in gates if g["status"] == "PASS")

            # Parse numeric tokens from telemetry
            tokens_sum = 0
            tool_uses_sum = 0
            for row in telemetria:
                tok_str = str(row["tokens"]).replace(" ", "")
                if tok_str.isdigit():
                    tokens_sum += int(tok_str)
                tu_str = str(row["tool_uses"]).replace(" ", "")
                if tu_str.isdigit():
                    tool_uses_sum += int(tu_str)

            token_display = f"{tokens_sum / 1_000_000:.1f}M" if tokens_sum >= 1_000_000 else f"{tokens_sum:,}"

            totals = {
                "sections_count": len(sections),
                "total_words": total_words,
                "total_citations": total_citations,
                "bibtex_entries": bib_entries,
                "gates_passed": gates_passed,
                "gates_total": len(flow_gates),
                "total_tokens": token_display,
                "total_tool_uses": tool_uses_sum,
                "pdf_pages": run_info["pdf_pages"],
            }

    # List all runs
    proposals_dir = target_dir / "proposals"
    all_runs = []
    if proposals_dir.is_dir():
        for item in sorted(proposals_dir.iterdir()):
            if item.is_dir() and (item / "_run.md").is_file():
                all_runs.append(item.name)

    archify_flow_ready = (
        target_dir / "docs" / "diagrams" / "morfeo-pipeline-flow.html"
    ).is_file() or (
        Path(__file__).resolve().parent.parent / "dashboard" / "static" / "morfeo-pipeline-flow.html"
    ).is_file()

    result_data = {
        "workspace": str(target_dir),
        "workspace_title": workspace_title,
        # Flujo del proyecto (`base` o `sgr`), fijado por `morfeo init [--sgr]`.
        "flujo": flujo,
        # `version` is the workspace kit stamp (`.marco/version`); the running
        # package can be newer, so the dashboard footer shows both.
        "version": version,
        "package_version": _package_version(),
        "active_run": active_run,
        "run_details": run_info,
        "all_runs": all_runs,
        "sections": sections,
        "gates": gates,
        "telemetria": telemetria,
        "totals": totals,
        "artifacts": artifacts,
        # El latido de la unidad en curso, cuando el dispatcher lo ha escrito.
        "en_curso": en_curso,
        # Control de ejecución: `next_step` decide qué unidad puede ejecutarse.
        "control": control,
        # El inventario de unidades viaja en el sobre para que el tablero deje de
        # mantener su propia lista de fases y derive de aquí.
        "pipeline_units": units_for_flujo(flujo),
        "archify_flow_ready": archify_flow_ready,
        "decisions_exists": (target_dir / "DECISIONS.md").is_file(),
        "idea_exists": (target_dir / "idea.md").is_file(),
    }
    _STATUS_CACHE[cache_key] = (now, result_data)
    return result_data


def status_project(target_dir: Path, as_json: bool = False) -> int:
    status = get_project_status(target_dir)
    if as_json:
        print(json.dumps(status, indent=2))
        return 0

    print("======================================================================")
    print(f" MORFEO IA — Estado del Espacio de Trabajo ({status['version']})")
    print("======================================================================")
    print(f"Directorio: {status['workspace']}")
    print(f"Flujo:      {status.get('flujo', 'base')}")
    if status['active_run']:
        details = status['run_details']
        totals = status['totals']
        print(f"Corrida activa: {status['active_run']}")
        if details.get("title"):
            print(f"Título:         {details['title']}")
        print(f"Compuertas:     {totals['gates_passed']}/{totals['gates_total']} aprobadas (PASS)")
        print(f"Secciones:      {totals['sections_count']} redactadas ({totals['total_words']:,} palabras)")
        print(f"Bibliografía:   {totals['bibtex_entries']} entradas ({totals['total_citations']} citas en texto)")
        pdf_str = f"Sí ({details['pdf_size'] // 1024} KB, {details['pdf_pages']} páginas)" if details.get('pdf_ready') else "No"
        docx_str = f"Sí ({details['docx_size'] // 1024} KB)" if details.get('docx_ready') else "No"
        print(f"PDF compilado:  {pdf_str}")
        print(f"DOCX exportado: {docx_str}")
        print(f"Grafo papers:   {'Generado' if details.get('papers_graph') else 'Pendiente'}")
        print(f"Grafo vault:    {'Generado' if details.get('vault_graph') else 'Pendiente'}")
        print(f"Flujo Archify:  {'Disponible' if status.get('archify_flow_ready') else 'Pendiente'}")
    else:
        print("Corrida activa: Ninguna (Usa '/propuesta-init <idea>' para iniciar)")

    print(f"\nCorridas en este proyecto ({len(status['all_runs'])}):")
    for r in status['all_runs']:
        mark = " (activa)" if r == status['active_run'] else ""
        print(f"  - {r}{mark}")

    return 0
