"""Data for the dashboard panels: TDR chapters and the style report.

Both read artefacts of the active run and tolerate their absence, so a run
that has not reached them shows an empty panel instead of an error.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _file_state(sections_dir: Path, name: str) -> dict[str, Any]:
    path = sections_dir / f"{name}.tex"
    if not path.is_file():
        return {"nombre": name, "existe": False, "palabras": 0}
    words = len(path.read_text(encoding="utf-8", errors="replace").split())
    return {"nombre": name, "existe": True, "palabras": words}


def _chapter_state(files: list[dict[str, Any]]) -> str:
    # Figures are optional: a chapter is judged by its text files.
    text_files = [item for item in files if not item["nombre"].startswith("diag_")]
    written = [item for item in text_files if item["palabras"] > 0]
    if not written:
        return "vacio"
    return "escrito" if len(written) == len(text_files) else "parcial"


def load_tdr_chapters(run_dir: Path) -> dict[str, Any]:
    """Chapters of artefactos/estructura_tdr.json with how far each one got."""
    data = _read_json(run_dir / "artefactos" / "estructura_tdr.json")
    if not isinstance(data, dict) or not isinstance(data.get("capitulos"), list):
        return {"fuente": None, "capitulos": []}
    sections_dir = run_dir / "redaccion" / "sections"
    chapters = []
    for chapter in data["capitulos"]:
        if not isinstance(chapter, dict):
            continue
        files = [_file_state(sections_dir, str(name)) for name in chapter.get("archivos") or []]
        chapters.append({
            "numero": chapter.get("numero"),
            "titulo": chapter.get("titulo"),
            "archivos": files,
            "estado": _chapter_state(files),
        })
    return {"fuente": data.get("fuente"), "capitulos": chapters}


def load_style_report(run_dir: Path) -> dict[str, Any]:
    """artefactos/estilo/reporte.json, the output of scripts/estilo_es.py."""
    report = _read_json(run_dir / "artefactos" / "estilo" / "reporte.json")
    if not isinstance(report, dict):
        return {"disponible": False}
    return {"disponible": True, **report}
