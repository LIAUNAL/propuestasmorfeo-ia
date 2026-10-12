"""Implementation of 'morfeo ui'."""

from __future__ import annotations

import socket
import webbrowser
from pathlib import Path

from ..dashboard.server import run_server
from ..errors import UserError


def find_free_port(start_port: int = 8080, max_attempts: int = 20) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def start_ui(
    target_dir: Path,
    port: int | None = None,
    no_open: bool = False,
) -> int:
    target_dir = target_dir.resolve()
    marker = target_dir / ".morfeo"
    if not marker.is_dir():
        marker = target_dir / ".marco"
    if not marker.is_dir():
        raise UserError(f"No es un espacio de trabajo Morfeo válido: {target_dir}")

    active_port = port or find_free_port()
    url = f"http://127.0.0.1:{active_port}/"

    if not no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    run_server(target_dir, port=active_port)
    return 0
