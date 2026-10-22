"""Implementation of 'morfeo compile'."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

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


_PAGES_RE = re.compile(r"Compilación exitosa: \S+ \((\d+) páginas")


def pdf_version(pdf_path: Path) -> str | None:
    """Version of a compiled PDF: changes on every rewrite, even within one second."""
    try:
        st = pdf_path.stat()
    except OSError:
        return None
    return f"{st.st_mtime_ns}-{st.st_size}"


def compile_run_pdf(redaccion_dir: Path, timeout: int = 900) -> dict[str, Any]:
    """Run the run's build.sh without a terminal and report the outcome.

    The dashboard uses it: stdin is closed so build.sh skips its interactive DOI
    repair, and the output is captured to report pages or the failing log tail.
    """
    started = time.monotonic()
    try:
        proc = subprocess.run(
            ["bash", "build.sh"],
            cwd=redaccion_dir,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output, returncode = (proc.stdout or "") + (proc.stderr or ""), proc.returncode
    except subprocess.TimeoutExpired as exc:
        # TimeoutExpired carries bytes even with text=True.
        output = "".join(
            part.decode("utf-8", "replace") if isinstance(part, bytes) else (part or "")
            for part in (exc.stdout, exc.stderr)
        )
        returncode = None
    ms = int((time.monotonic() - started) * 1000)
    match = _PAGES_RE.search(output)
    tail = "\n".join(output.strip().splitlines()[-40:])
    result: dict[str, Any] = {
        "ok": returncode == 0,
        "returncode": returncode,
        "pages": int(match.group(1)) if match else None,
        "ms": ms,
        "log_tail": tail,
        "version": pdf_version(redaccion_dir / "main.pdf"),
    }
    if returncode is None:
        result["error"] = f"La compilación superó el tiempo límite de {timeout} s"
    elif returncode != 0:
        result["error"] = f"build.sh terminó con código {returncode}"
    return result
