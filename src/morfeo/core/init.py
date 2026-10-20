"""Implementation of 'morfeo init'."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..errors import UserError
from ..kit import get_kit_root, load_kit_manifest
from .manifest import (
    MODEL_PRESETS,
    VALID_PRESETS,
    compute_sha256,
    copy_kit_entry,
    decisions_template,
    idea_template,
    journal_readme,
    project_readme,
)


# Flujo del proyecto: `base` es el pipeline de siempre; `sgr` agrega lo que pide
# el Sistema General de Regalías (metodología MGA). Se guarda en config.json.
FLUJO_LABELS = {
    "base": "base",
    "sgr": "SGR (Sistema General de Regalías, MGA)",
}


def init_project(
    target_dir: Path,
    tools: set[str],
    lang: str = "es",
    preset_name: str = "claude",
    title: str | None = None,
    force: bool = False,
    quiet: bool = False,
    flujo: str = "base",
) -> int:
    if flujo not in FLUJO_LABELS:
        raise UserError(f"Flujo desconocido: {flujo} (válidos: {', '.join(FLUJO_LABELS)})")
    target_dir = target_dir.resolve()
    if target_dir.exists() and not force:
        existing = [p for p in target_dir.iterdir() if p.name != ".DS_Store"]
        if existing:
            raise UserError(
                f"Directorio de destino no está vacío: {target_dir}\n"
                "Usa --force para inicializar en un directorio existente."
            )

    target_dir.mkdir(parents=True, exist_ok=True)
    kit_root = get_kit_root()
    manifest_data = load_kit_manifest(kit_root)
    kit_version = manifest_data.get("version", "0.5.0")
    kit_paths = manifest_data.get("kit_paths", [])

    if not quiet:
        print(f"==> Inicializando espacio de trabajo Morfeo en {target_dir}")
        print(f"    Versión del kit: {kit_version} (desde {kit_root})")

    installed_files: list[dict] = []
    for kit_path in kit_paths:
        src = kit_root / kit_path
        if not src.exists():
            continue
        entries = copy_kit_entry(kit_root, target_dir, kit_path)
        installed_files.extend(entries)

    # Marcadores de framework (.morfeo y retrocompatibilidad .marco)
    for marker_name in [".morfeo", ".marco"]:
        marker_dir = target_dir / marker_name
        marker_dir.mkdir(parents=True, exist_ok=True)

        (marker_dir / "version").write_text(kit_version + "\n", encoding="utf-8")

        manifest_record = {
            "version": kit_version,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "kit_source": str(kit_root),
            "files": installed_files,
        }
        with (marker_dir / "manifest.json").open("w", encoding="utf-8") as f:
            json.dump(manifest_record, f, indent=2)

        config_record = {
            "version": kit_version,
            "lang": lang,
            "preset": preset_name,
            "tools": sorted(tools),
            "title": title,
            "flujo": flujo,
        }
        with (marker_dir / "config.json").open("w", encoding="utf-8") as f:
            json.dump(config_record, f, indent=2)

    # Generación de superficies de runtime adicionales
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

    # Scaffolding de contenido de usuario
    idea_path = target_dir / "idea.md"
    if not idea_path.exists():
        idea_path.write_text(idea_template(lang), encoding="utf-8")

    decisions_path = target_dir / "DECISIONS.md"
    if not decisions_path.exists():
        decisions_path.write_text(decisions_template(lang), encoding="utf-8")

    journal_dir = target_dir / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal_readme_path = journal_dir / "README.md"
    if not journal_readme_path.exists():
        journal_readme_path.write_text(journal_readme(lang), encoding="utf-8")

    readme_path = target_dir / "README.md"
    if not readme_path.exists() or force:
        readme_path.write_text(
            project_readme(title, tools, lang, preset_name, kit_version),
            encoding="utf-8",
        )

    # Carpeta proposals local con .gitkeep
    (target_dir / "proposals").mkdir(parents=True, exist_ok=True)
    gitkeep = target_dir / "proposals" / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()

    if not quiet:
        print("\n[OK] Espacio de trabajo Morfeo creado exitosamente.")
        print(f"     Directorio: {target_dir}")
        print(f"     Flujo: {FLUJO_LABELS[flujo]}")
        print("     Para comenzar:")
        print(f"       cd {target_dir}")
        print("       morfeo status .")
        print("       morfeo ui .   # (Abre el tablero visual)")

    return 0
