"""Implementation of 'morfeo compile'."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ..errors import UserError


def compile_proposal(
    target_dir: Path,
    docx: bool = False,
    run_id: str | None = None,
) -> int:
    target_dir = target_dir.resolve()
    current_run_pointer = target_dir / "proposals" / ".current-run"

    active_run = run_id
    if not active_run and current_run_pointer.is_file():
        active_run = current_run_pointer.read_text(encoding="utf-8").strip()

    if not active_run:
        raise UserError("No hay una corrida activa para compilar. Pasa --run <id> o activa una con /propuesta-init.")

    redaccion_dir = target_dir / "proposals" / active_run / "redaccion"
    build_script = redaccion_dir / "build.sh"

    if not build_script.is_file():
        raise UserError(f"No se encontró el script de compilación en {build_script}")

    cmd = [str(build_script)]
    if docx:
        cmd.append("--docx")

    print(f"==> Compilando {'DOCX' if docx else 'PDF'} para corrida {active_run}...")
    proc = subprocess.run(cmd, cwd=redaccion_dir)
    return proc.returncode
