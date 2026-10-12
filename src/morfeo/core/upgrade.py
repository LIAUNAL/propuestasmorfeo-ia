"""Implementation of 'morfeo upgrade'."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..errors import UserError
from ..kit import get_kit_root, load_kit_manifest
from .manifest import compute_sha256, copy_kit_entry, matches_preserve


def upgrade_project(
    target_dir: Path,
    force: bool = False,
    quiet: bool = False,
) -> int:
    target_dir = target_dir.resolve()
    marker = target_dir / ".morfeo"
    if not marker.is_dir():
        marker = target_dir / ".marco"
    if not marker.is_dir():
        raise UserError(f"El directorio no es un proyecto Morfeo válido (falta .morfeo/ o .marco/): {target_dir}")

    config_file = marker / "config.json"
    tools = {"claude"}
    if config_file.is_file():
        try:
            with config_file.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
                tools = set(cfg.get("tools", ["claude"]))
        except Exception:
            pass

    kit_root = get_kit_root()
    kit_manifest = load_kit_manifest(kit_root)
    new_version = kit_manifest.get("version", "0.5.0")
    kit_paths = kit_manifest.get("kit_paths", [])
    preserve_patterns = kit_manifest.get("preserve_paths", ["proposals/**", "DECISIONS.md", "journal/**", "idea.md"])

    if not quiet:
        print(f"==> Actualizando proyecto Morfeo en {target_dir}")
        print(f"    Nueva versión del kit: {new_version}")

    updated_files: list[dict] = []
    for kit_path in kit_paths:
        if matches_preserve(kit_path, preserve_patterns):
            continue
        src = kit_root / kit_path
        if not src.exists():
            continue
        entries = copy_kit_entry(kit_root, target_dir, kit_path)
        updated_files.extend(entries)

    # Actualizar registros de versión
    for marker_name in [".morfeo", ".marco"]:
        m_dir = target_dir / marker_name
        if m_dir.is_dir():
            (m_dir / "version").write_text(new_version + "\n", encoding="utf-8")
            record = {
                "version": new_version,
                "upgraded_at": datetime.now(timezone.utc).isoformat(),
                "kit_source": str(kit_root),
                "files": updated_files,
            }
            with (m_dir / "manifest.json").open("w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)

    # Regenerar proyecciones de runtime
    for tool in tools:
        if tool == "opencode":
            script = target_dir / "scripts" / "gen-opencode.py"
            if script.is_file():
                subprocess.run([sys.executable, str(script)], cwd=target_dir, check=False)
        elif tool == "pi":
            script = target_dir / "scripts" / "gen-pi.py"
            if script.is_file():
                subprocess.run([sys.executable, str(script)], cwd=target_dir, check=False)
        elif tool in ("antigravity", "agent"):
            script = target_dir / "scripts" / "gen-antigravity.py"
            if script.is_file():
                subprocess.run([sys.executable, str(script)], cwd=target_dir, check=False)

    if not quiet:
        print(f"[OK] Proyecto actualizado exitosamente a Morfeo {new_version}.")

    return 0
