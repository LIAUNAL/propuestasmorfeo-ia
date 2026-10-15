"""Implementation of 'morfeo export'.

Packages a self-contained Morfeo workspace or proposal run with all its
artifacts, inputs, graphs, LaTeX sources, compiled documents, and
change control records for sharing or continuation on another machine.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tarfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..errors import MorfeoError, UserError
from .. import __version__
from .status import get_project_status


# Files and directories to unconditionally exclude from exports
EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "node_modules",
}

EXCLUDE_FILE_PATTERNS = {
    ".DS_Store",
    "Thumbs.db",
    "*.pyc",
    "*.pyo",
}

# Ephemeral LaTeX build artifacts to exclude from redaccion/
LATEX_AUX_EXTENSIONS = {
    ".aux",
    ".log",
    ".out",
    ".toc",
    ".fls",
    ".fdb_latexmk",
    ".synctex.gz",
    ".bbl",
    ".blg",
    ".nav",
    ".snm",
    ".vrb",
}


def should_exclude_path(rel_path: Path, is_dir: bool = False) -> bool:
    """Check if a relative path matches any exclusion criteria."""
    parts = rel_path.parts
    # Check directory names anywhere in path
    for p in parts:
        if p in EXCLUDE_DIR_NAMES:
            return True

    name = rel_path.name
    if name in EXCLUDE_FILE_PATTERNS or name.startswith(".git"):
        return True

    if not is_dir:
        # Check extensions
        if name.endswith((".pyc", ".pyo")):
            return True
        # If inside a redaccion/ folder, filter LaTeX auxiliary build files
        if "redaccion" in parts:
            suffix = rel_path.suffix.lower()
            if suffix in LATEX_AUX_EXTENSIONS:
                return True
            if name.endswith(".synctex.gz"):
                return True

    return False


def collect_export_files(
    target_dir: Path,
    selected_runs: list[str],
) -> list[tuple[Path, Path]]:
    """Gather all (absolute_path, relative_archive_path) pairs to package."""
    pairs: list[tuple[Path, Path]] = []
    project_name = target_dir.name

    # 1. Base project markers and configuration
    for marker in [".morfeo", ".marco"]:
        marker_path = target_dir / marker
        if marker_path.is_dir():
            for p in sorted(marker_path.rglob("*")):
                if p.is_file() and not should_exclude_path(p.relative_to(target_dir)):
                    rel = Path(project_name) / p.relative_to(target_dir)
                    pairs.append((p, rel))

    # 2. Key top-level documents
    top_candidates = [
        "idea.md",
        "DECISIONS.md",
        "README.md",
        "LICENSE",
        "AGENTS.md",
        "REQUIREMENTS.md",
        "guiaProyectosIA_Agente.md",
        "guiaProyectosIA_Agente_Regalias.md",
        "prompt_plantilla.md",
        "pyproject.toml",
    ]
    for name in top_candidates:
        f = target_dir / name
        if f.is_file():
            pairs.append((f, Path(project_name) / name))

    # 3. Base framework folders (plantilla/, scripts/, docs/)
    for folder_name in ["plantilla", "scripts", "docs"]:
        f_dir = target_dir / folder_name
        if f_dir.is_dir():
            for p in sorted(f_dir.rglob("*")):
                if p.is_file():
                    rel_to_proj = p.relative_to(target_dir)
                    if not should_exclude_path(rel_to_proj):
                        pairs.append((p, Path(project_name) / rel_to_proj))

    # 4. Runtime agent/prompt ports (.claude/, .agent/, .pi/, .opencode/)
    for tool_name in [".claude", ".agent", ".pi", ".opencode"]:
        t_dir = target_dir / tool_name
        if t_dir.is_dir():
            for p in sorted(t_dir.rglob("*")):
                if p.is_file():
                    rel_to_proj = p.relative_to(target_dir)
                    if not should_exclude_path(rel_to_proj):
                        pairs.append((p, Path(project_name) / rel_to_proj))

    # 5. Proposals pointer and registry
    props_dir = target_dir / "proposals"
    if props_dir.is_dir():
        for meta_name in [".current-run", "registry.md"]:
            f = props_dir / meta_name
            if f.is_file():
                pairs.append((f, Path(project_name) / "proposals" / meta_name))

        # 6. Selected proposal run folders
        for r_id in selected_runs:
            run_folder = props_dir / r_id
            if run_folder.is_dir():
                for p in sorted(run_folder.rglob("*")):
                    if p.is_file():
                        rel_to_proj = p.relative_to(target_dir)
                        if not should_exclude_path(rel_to_proj):
                            pairs.append((p, Path(project_name) / rel_to_proj))

    return pairs


def export_project(
    target_dir: Path,
    output_path: Path | None = None,
    run_id: str | None = None,
    all_runs: bool = False,
    archive_format: str = "tar.gz",
    quiet: bool = False,
) -> Path:
    """Package and export a Morfeo project to a compressed archive."""
    target_dir = target_dir.resolve()
    if not target_dir.exists():
        raise UserError(f"El directorio no existe: {target_dir}")

    status = get_project_status(target_dir, force_refresh=True)
    project_name = target_dir.name
    props_dir = target_dir / "proposals"

    # Determine which runs to export
    available_runs = []
    if props_dir.is_dir():
        available_runs = [d.name for d in props_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

    selected_runs: list[str] = []
    if run_id:
        if (props_dir / run_id).is_dir():
            selected_runs = [run_id]
        else:
            raise UserError(f"La corrida '{run_id}' no existe en {props_dir}")
    elif all_runs:
        selected_runs = sorted(available_runs)
    else:
        active_run = status.get("active_run")
        if active_run and (props_dir / active_run).is_dir():
            selected_runs = [active_run]
        elif len(available_runs) == 1:
            selected_runs = [available_runs[0]]
        elif len(available_runs) > 1:
            selected_runs = [available_runs[0]]  # default to first available
        else:
            selected_runs = []

    primary_run = selected_runs[0] if selected_runs else "empty"

    # Determine default output filename
    if output_path is None:
        ext = ".zip" if archive_format.lower() == "zip" else ".tar.gz"
        safe_proj = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project_name)
        safe_run = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in primary_run)
        filename = f"{safe_proj}-{safe_run}{ext}"
        output_path = Path.cwd() / filename
    else:
        output_path = output_path.resolve()
        if output_path.suffix.lower() == ".zip":
            archive_format = "zip"
        elif output_path.name.endswith((".tar.gz", ".tgz")):
            archive_format = "tar.gz"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not quiet:
        print(f"==> Exportando proyecto Morfeo: {project_name}")
        print(f"    Directorio base: {target_dir}")
        if selected_runs:
            print(f"    Corridas incluidas: {', '.join(selected_runs)}")
            if status.get("run"):
                meta = status["run"]
                if meta.get("title"):
                    print(f"    Título: {meta['title']}")
                print(f"    Fases completadas: {status['totals']['gates_passed']}/{status['totals']['gates_total']}")
        else:
            print("    Aviso: No se encontraron corridas en proposals/, exportando estructura base.")

    # Collect files
    file_pairs = collect_export_files(target_dir, selected_runs)
    if not file_pairs:
        raise UserError(f"No se encontraron archivos exportables en {target_dir}")

    # Build manifest
    export_manifest = {
        "export_version": "1.0",
        "morfeo_version": status.get("version", __version__),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "project_name": project_name,
        "selected_runs": selected_runs,
        "active_run": status.get("active_run"),
        "totals": status.get("totals", {}),
        "run_metadata": status.get("run", {}),
        "files_count": len(file_pairs),
    }
    manifest_bytes = json.dumps(export_manifest, indent=2, ensure_ascii=False).encode("utf-8")

    # Write archive
    if archive_format == "zip":
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # write manifest at root of project folder inside zip
            manifest_arc_path = f"{project_name}/export_manifest.json"
            zf.writestr(manifest_arc_path, manifest_bytes)

            for abs_path, rel_arc in file_pairs:
                zf.write(abs_path, str(rel_arc))
    else:
        with tarfile.open(output_path, "w:gz") as tf:
            # write manifest
            tarinfo = tarfile.TarInfo(name=f"{project_name}/export_manifest.json")
            tarinfo.size = len(manifest_bytes)
            tarinfo.mtime = int(time.time())
            tarinfo.mode = 0o644
            import io
            tf.addfile(tarinfo, io.BytesIO(manifest_bytes))

            for abs_path, rel_arc in file_pairs:
                arc_name = str(rel_arc)
                tf.add(abs_path, arcname=arc_name, recursive=False)

    size_bytes = output_path.stat().st_size
    size_str = (
        f"{size_bytes / (1024 * 1024):.1f} MB"
        if size_bytes >= 1024 * 1024
        else f"{size_bytes / 1024:.1f} KB"
    )

    if not quiet:
        print("\n[OK] Archivo exportado exitosamente:")
        print(f"     Archivo: {output_path} ({size_str})")
        print(f"     Elementos empaquetados: {len(file_pairs)} archivos")
        print("\nPara compartir y continuar este proyecto en otro computador:")
        print(f"  1. Copia o transfiere el archivo: {output_path.name}")
        print("  2. En el computador de destino ejecuta:")
        print(f"     morfeo import {output_path.name} mi-propuesta")
        print("     (o descomprime manualmente: tar -xzf " + output_path.name + ")")
        print("  3. Entra a la carpeta y abre el panel de control:")
        print("     cd mi-propuesta && morfeo ui")
        print("  4. Para avanzar la propuesta con un agente IA:")
        print("     /propuesta-continuar")

    return output_path
