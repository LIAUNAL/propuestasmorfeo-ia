"""Implementation of 'morfeo status' with comprehensive workspace introspection."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..errors import UserError


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
}

CANONICAL_GATES = [
    {"id": "G0.5", "name": "Ajuste de Guía al TDR", "phase": "Fase 0", "reviewer": "Usuario", "criteria": "Tabla de secciones del TDR aprobada y ajustada."},
    {"id": "G1", "name": "Árbol de Problemas y Pregunta", "phase": "Fase 1", "reviewer": "Revisor", "criteria": "Subproblemas mutuamente excluyentes y árbol TikZ verificado."},
    {"id": "G2", "name": "Estado del Arte e Hipótesis", "phase": "Fase 2", "reviewer": "Revisor", "criteria": "≥30 referencias Q1/Q2 recientes e hipótesis falsable."},
    {"id": "G3", "name": "Justificación y Pertinencia", "phase": "Fase 3", "reviewer": "Revisor", "criteria": "Alineación ODS, PND y pertinencia tecnológica con TRL 6 o 7."},
    {"id": "G4", "name": "Objetivos General y Específicos", "phase": "Fase 4", "reviewer": "Revisor", "criteria": "Correspondencia biyectiva 1:1 entre subproblemas y objetivos."},
    {"id": "G5", "name": "Marco Conceptual y Equipo", "phase": "Fase 5", "reviewer": "Revisor", "criteria": "Teoría fundamental y roles de equipo derivados de objetivos."},
    {"id": "G5.5", "name": "Metodología y Diagrama TikZ", "phase": "Fase 5.5", "reviewer": "Revisor", "criteria": "Cadena de valor por fase, causalidad y esquema metodológico."},
    {"id": "G6.4", "name": "Presupuesto Financiero", "phase": "Fase 6.4", "reviewer": "Revisor", "criteria": "Aritmética exacta de rubros, topes y cofinanciación institucional."},
    {"id": "G6.5", "name": "Front-Matter y Síntesis", "phase": "Fase 6.5", "reviewer": "Revisor", "criteria": "Resumen ejecutivo, palabras clave y unicidad del título."},
    {"id": "G7", "name": "Auditoría Final y Ensamble", "phase": "Fase 7", "reviewer": "Revisor & Coordinador", "criteria": "Auditoría cruzada integral, 0 errores en LaTeX y compilación PDF."},
]


def _count_pdf_pages(pdf_path: Path) -> int:
    """Best-effort page count for PDF using pdfinfo or binary inspection."""
    if not pdf_path.is_file():
        return 0
    try:
        import subprocess
        res = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if line.startswith("Pages:"):
                    return int(line.split(":")[1].strip())
    except Exception:
        pass

    try:
        data = pdf_path.read_bytes()
        pages = len(re.findall(b"/Type\\s*/Page\\b", data))
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
        m = re.search(r"\\LARGE\\bfseries\s+([^}\\]+)", main_tex.read_text(encoding="utf-8", errors="replace"))
        if m:
            meta["title"] = m.group(1).strip()
    if not meta["title"]:
        meta["title"] = meta["idea"]

    return meta


def parse_sections_info(run_dir: Path) -> list[dict[str, Any]]:
    sections_dir = run_dir / "redaccion" / "sections"
    if not sections_dir.is_dir():
        return []

    sections: list[dict[str, Any]] = []
    for f in sorted(sections_dir.glob("*.tex")):
        if f.name.startswith("diag_"):
            continue

        raw = f.read_text(encoding="utf-8", errors="replace")
        clean = re.sub(r"%.*", "", raw)
        words = len(clean.split())
        cites = len(re.findall(r"\\cite[pt]?\{([^}]+)\}", raw))
        has_tikz = ("\\input{sections/diag_" in raw) or ("\\includegraphics" in raw)

        stem = f.stem
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
            "status": status,
        })

    return sections


def parse_gates_info(run_dir: Path) -> list[dict[str, Any]]:
    estado_file = run_dir / "artefactos" / "estado_propuesta.md"
    pipeline_file = run_dir / "artefactos" / "pipeline" / "_estado.md"

    recorded_gates: dict[str, str] = {}
    if pipeline_file.is_file():
        for line in pipeline_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if "|" in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 3 and parts[1] != "Gate":
                    gate_id = parts[1].strip()
                    verdict = parts[2].strip()
                    if gate_id and gate_id != "none" and gate_id != "—":
                        recorded_gates[gate_id] = verdict

    if estado_file.is_file() and not recorded_gates:
        for line in estado_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if "|" in line:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 2 and parts[0].startswith("G"):
                    recorded_gates[parts[0]] = parts[1]

    result: list[dict[str, Any]] = []
    for g in CANONICAL_GATES:
        status = "PENDING"
        # Match gate id or aliases
        for rk, rv in recorded_gates.items():
            if g["id"].lower() in rk.lower() or (g["id"] == "G6.4" and "presupuesto" in rk.lower()) or (g["id"] == "G6.5" and "front" in rk.lower()) or (g["id"] == "G7" and "final" in rk.lower()):
                if "pass" in rv.lower():
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


def get_project_status(target_dir: Path) -> dict:
    target_dir = target_dir.resolve()
    version = "0.5.0"
    marker = target_dir / ".morfeo"
    if not marker.is_dir():
        marker = target_dir / ".marco"
    if marker.is_dir():
        vfile = marker / "version"
        if vfile.is_file():
            version = vfile.read_text(encoding="utf-8").strip()
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
    totals: dict[str, Any] = {
        "sections_count": 0,
        "total_words": 0,
        "total_citations": 0,
        "bibtex_entries": 0,
        "gates_passed": 0,
        "gates_total": len(CANONICAL_GATES),
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
            gates = parse_gates_info(run_dir)
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
                "gates_total": len(CANONICAL_GATES),
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

    archify_flow_ready = (target_dir / "docs" / "diagrams" / "morfeo-pipeline-flow.html").is_file()

    return {
        "workspace": str(target_dir),
        "version": version,
        "active_run": active_run,
        "run_details": run_info,
        "all_runs": all_runs,
        "sections": sections,
        "gates": gates,
        "telemetria": telemetria,
        "totals": totals,
        "artifacts": artifacts,
        "archify_flow_ready": archify_flow_ready,
        "decisions_exists": (target_dir / "DECISIONS.md").is_file(),
        "idea_exists": (target_dir / "idea.md").is_file(),
    }


def status_project(target_dir: Path, as_json: bool = False) -> int:
    status = get_project_status(target_dir)
    if as_json:
        print(json.dumps(status, indent=2))
        return 0

    print("======================================================================")
    print(f" MORFEO IA — Estado del Espacio de Trabajo ({status['version']})")
    print("======================================================================")
    print(f"Directorio: {status['workspace']}")
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
