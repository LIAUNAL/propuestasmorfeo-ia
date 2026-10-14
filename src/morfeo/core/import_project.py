"""Implementation of 'morfeo import'.

Unpacks and restores a shared Morfeo project archive (.tar.gz or .zip),
validating file safety, restoring permissions, and verifying project integrity.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any

from ..errors import MorfeoError, UserError
from .status import get_project_status


def _is_safe_path(base_dir: Path, target_path: Path) -> bool:
    """Check against zip-slip / directory traversal."""
    try:
        resolved_base = base_dir.resolve()
        resolved_target = target_path.resolve()
        return resolved_target == resolved_base or resolved_base in resolved_target.parents
    except Exception:
        return False


def _detect_top_level_dir(names: list[str]) -> str | None:
    """If all paths share a single top-level directory, return its name."""
    top_levels = set()
    for name in names:
        parts = [p for p in Path(name).parts if p not in (".", "")]
        if parts:
            top_levels.add(parts[0])
    if len(top_levels) == 1:
        return next(iter(top_levels))
    return None


def import_project(
    archive_path: Path,
    target_dir: Path | None = None,
    force: bool = False,
    quiet: bool = False,
) -> Path:
    """Extract and initialize a shared Morfeo project archive."""
    archive_path = archive_path.resolve()
    if not archive_path.is_file():
        raise UserError(f"El archivo comprimido no existe: {archive_path}")

    is_zip = archive_path.suffix.lower() == ".zip" or zipfile.is_zipfile(archive_path)
    is_tar = False
    if not is_zip:
        try:
            with tarfile.open(archive_path, "r:*"):
                is_tar = True
        except Exception:
            raise UserError(f"Formato de archivo no soportado o dañado: {archive_path}")

    # Inspect contents
    member_names: list[str] = []
    manifest_data: dict[str, Any] | None = None

    if is_zip:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                name = info.filename.strip()
                if name:
                    member_names.append(name)
                    if Path(name).name == "export_manifest.json":
                        try:
                            manifest_data = json.loads(zf.read(info).decode("utf-8"))
                        except Exception:
                            pass
    else:
        with tarfile.open(archive_path, "r:*") as tf:
            for member in tf.getmembers():
                name = member.name.strip()
                if name:
                    member_names.append(name)
                    if Path(name).name == "export_manifest.json":
                        try:
                            f = tf.extractfile(member)
                            if f:
                                manifest_data = json.loads(f.read().decode("utf-8"))
                        except Exception:
                            pass

    if not member_names:
        raise UserError(f"El archivo está vacío: {archive_path}")

    top_dir = _detect_top_level_dir(member_names)

    # Determine destination directory
    if target_dir is None:
        if manifest_data and manifest_data.get("project_name"):
            dir_name = manifest_data["project_name"]
        elif top_dir:
            dir_name = top_dir
        else:
            base_stem = archive_path.name
            for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tar", ".tgz", ".zip"):
                if base_stem.endswith(ext):
                    base_stem = base_stem[: -len(ext)]
                    break
            dir_name = base_stem
        target_dir = (Path.cwd() / dir_name).resolve()
    else:
        target_dir = target_dir.resolve()

    # Safety checks
    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        # Check if it is an existing Morfeo project where we could merge
        is_existing_morfeo = (
            (target_dir / ".morfeo").is_dir()
            or (target_dir / ".marco").is_dir()
            or (target_dir / "proposals").is_dir()
        )
        if not is_existing_morfeo:
            raise UserError(
                f"El directorio de destino ya existe y no está vacío: {target_dir}\n"
                "Especifica otro directorio o usa --force para sobrescribir."
            )

    target_dir.mkdir(parents=True, exist_ok=True)

    if not quiet:
        print(f"==> Importando proyecto Morfeo desde: {archive_path.name}")
        print(f"    Destino: {target_dir}")
        if manifest_data:
            proj = manifest_data.get("project_name", "Desconocido")
            run = manifest_data.get("active_run", "Ninguna")
            print(f"    Proyecto empaquetado: {proj} (Corrida: {run})")

    # Safe extraction
    prefix_to_strip = f"{top_dir}/" if top_dir else ""

    if is_zip:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                rel_name = info.filename
                if prefix_to_strip and rel_name.startswith(prefix_to_strip):
                    rel_name = rel_name[len(prefix_to_strip) :]
                if not rel_name or rel_name.endswith("/"):
                    continue

                dest_file = target_dir / rel_name
                if not _is_safe_path(target_dir, dest_file):
                    raise UserError(f"Ruta no segura detectada en el archivo: {info.filename}")

                dest_file.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(dest_file, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                # Preserve basic permissions if available
                attr = info.external_attr >> 16
                if attr & 0o111:
                    dest_file.chmod(dest_file.stat().st_mode | 0o755)
    else:
        with tarfile.open(archive_path, "r:*") as tf:
            for member in tf.getmembers():
                if not member.isreg():
                    continue

                rel_name = member.name
                if prefix_to_strip and rel_name.startswith(prefix_to_strip):
                    rel_name = rel_name[len(prefix_to_strip) :]
                if not rel_name:
                    continue

                dest_file = target_dir / rel_name
                if not _is_safe_path(target_dir, dest_file):
                    raise UserError(f"Ruta no segura detectada en el archivo: {member.name}")

                dest_file.parent.mkdir(parents=True, exist_ok=True)
                f_in = tf.extractfile(member)
                if f_in:
                    with open(dest_file, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)

                if member.mode & 0o111:
                    dest_file.chmod(dest_file.stat().st_mode | 0o755)

    # Make all shell scripts and Python scripts executable
    for pattern in ["**/*.sh", "scripts/*.py", "plantilla/scripts/*.py"]:
        for p in target_dir.glob(pattern):
            if p.is_file():
                try:
                    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                except Exception:
                    pass

    # Ensure proposals/.current-run is set if active run known
    props_dir = target_dir / "proposals"
    if manifest_data and manifest_data.get("active_run"):
        active_run = manifest_data["active_run"]
        if (props_dir / active_run).is_dir():
            (props_dir / ".current-run").write_text(active_run + "\n", encoding="utf-8")

    # Validate project status
    try:
        status = get_project_status(target_dir, force_refresh=True)
    except Exception as e:
        status = {"version": "0.5.1", "totals": {}, "run": {}}

    if not quiet:
        print("\n[OK] Proyecto importado exitosamente:")
        print(f"     Directorio: {target_dir}")
        if status.get("run"):
            run_meta = status["run"]
            if run_meta.get("title"):
                print(f"     Título: {run_meta['title']}")
            print(f"     Corrida activa: {status.get('active_run', 'N/A')}")
            totals = status.get("totals", {})
            print(
                f"     Estado: {totals.get('sections_count', 0)} secciones | "
                f"{totals.get('gates_passed', 0)}/{totals.get('gates_total', 13)} compuertas | "
                f"{totals.get('bibtex_entries', 0)} citas BibTeX | "
                f"{totals.get('pdf_pages', 0)} págs. PDF"
            )

        print("\nPara comenzar a trabajar en este proyecto:")
        print(f"  1. Entra al directorio:")
        print(f"     cd {target_dir}")
        print("  2. Inicia el tablero interactivo de seguimiento:")
        print("     morfeo ui")
        print("  3. O compila directamente a PDF:")
        print("     morfeo compile")
        print("  4. Para avanzar en el flujo con un agente (Claude Code / OpenCode / Pi / Antigravity):")
        print("     /propuesta-continuar")

    return target_dir
