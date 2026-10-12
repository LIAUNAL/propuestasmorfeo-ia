"""Implementation of 'morfeo status'."""

from __future__ import annotations

import json
from pathlib import Path

from ..errors import UserError


def get_project_status(target_dir: Path) -> dict:
    target_dir = target_dir.resolve()
    marker = target_dir / ".morfeo"
    if not marker.is_dir():
        marker = target_dir / ".marco"
    if not marker.is_dir():
        raise UserError(f"No es un espacio de trabajo Morfeo válido: {target_dir}")

    version = (marker / "version").read_text(encoding="utf-8").strip() if (marker / "version").is_file() else "unknown"

    current_run_pointer = target_dir / "proposals" / ".current-run"
    active_run = None
    if current_run_pointer.is_file():
        active_run = current_run_pointer.read_text(encoding="utf-8").strip()

    run_info = {}
    if active_run:
        run_dir = target_dir / "proposals" / active_run
        if run_dir.is_dir():
            run_info["id"] = active_run
            run_info["dir"] = str(run_dir)
            run_info["run_md"] = (run_dir / "_run.md").is_file()

            # Estado propuesta
            estado_file = run_dir / "artefactos" / "estado_propuesta.md"
            run_info["estado_propuesta_exists"] = estado_file.is_file()

            # Compilaciones
            main_pdf = run_dir / "redaccion" / "main.pdf"
            main_docx = run_dir / "redaccion" / "main.docx"
            run_info["pdf_ready"] = main_pdf.is_file()
            run_info["pdf_size"] = main_pdf.stat().st_size if main_pdf.is_file() else 0
            run_info["docx_ready"] = main_docx.is_file()
            run_info["docx_size"] = main_docx.stat().st_size if main_docx.is_file() else 0

            # Grafos
            papers_graph = run_dir / "grafos" / "papers-graph.html"
            vault_graph = run_dir / "grafos" / "vault-graph.html"
            run_info["papers_graph"] = papers_graph.is_file()
            run_info["vault_graph"] = vault_graph.is_file()

    # List all runs
    proposals_dir = target_dir / "proposals"
    all_runs = []
    if proposals_dir.is_dir():
        for item in sorted(proposals_dir.iterdir()):
            if item.is_dir() and (item / "_run.md").is_file():
                all_runs.append(item.name)

    return {
        "workspace": str(target_dir),
        "version": version,
        "active_run": active_run,
        "run_details": run_info,
        "all_runs": all_runs,
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
        print(f"Corrida activa: {status['active_run']}")
        details = status['run_details']
        pdf_str = f"Sí ({details['pdf_size'] // 1024} KB)" if details.get('pdf_ready') else "No"
        docx_str = f"Sí ({details['docx_size'] // 1024} KB)" if details.get('docx_ready') else "No"
        print(f"  • PDF compilado:  {pdf_str}")
        print(f"  • DOCX exportado: {docx_str}")
        print(f"  • Grafo papers:   {'Generado' if details.get('papers_graph') else 'Pendiente'}")
        print(f"  • Grafo vault:    {'Generado' if details.get('vault_graph') else 'Pendiente'}")
    else:
        print("Corrida activa: Ninguna (Usa '/propuesta-init <idea>' para iniciar)")

    print(f"\nCorridas en este proyecto ({len(status['all_runs'])}):")
    for r in status['all_runs']:
        mark = " (activa)" if r == status['active_run'] else ""
        print(f"  - {r}{mark}")

    return 0
