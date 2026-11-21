"""Implementation of 'morfeo ui'."""

from __future__ import annotations

import socket
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Iterable

from .browser import open_browser
from .status import record_server_start
from ..dashboard import terminal_auth
from ..dashboard.server import bind_dashboard, start_board_refresh
from ..errors import UserError

#: The dashboard listens on loopback only; there is no network bind option.
HOST = "127.0.0.1"


def find_free_port(start_port: int = 8080, max_attempts: int = 20) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    return start_port


def normalize_allowed_hosts(hosts: Iterable[str], port: int) -> tuple[str, ...]:
    """Host headers to accept besides the loopback names, as `host:port`.

    The guard compares the whole Host header, port included, so a bare host
    gets the dashboard's port.
    """
    normalized: list[str] = []
    for raw in hosts:
        host = (raw or "").strip().lower()
        if not host:
            continue
        # "[::1]" or "name" carry no port; "[::1]:8080" or "name:8080" do.
        if ":" not in host.rsplit("]", 1)[-1]:
            host = f"{host}:{port}"
        if host not in normalized:
            normalized.append(host)
    return tuple(normalized)


def _start_board_refresh(workspace: Path) -> None:
    """Run the board refresh once in the background (shared with `run_server`)."""
    start_board_refresh(workspace)


def start_ui(
    target_dir: Path,
    port: int | None = None,
    no_open: bool = False,
    *,
    refresh: bool = True,
    terminal: bool = True,
    allowed_hosts: Iterable[str] = (),
) -> int:
    target_dir = target_dir.resolve()
    marker = target_dir / ".morfeo"
    if not marker.is_dir():
        marker = target_dir / ".marco"
    if not marker.is_dir():
        raise UserError(f"No es un espacio de trabajo Morfeo válido: {target_dir}")

    active_port = port or find_free_port()

    # Bind before anything else: the activation link carries a secret of this
    # very server, and a browser opened earlier would hit a closed port.
    server = bind_dashboard(target_dir, active_port, HOST, server_cls=ThreadingHTTPServer)
    if server is None:
        return 0
    # Read by terminal_auth when it first builds the guard of this server.
    server.morfeo_allowed_hosts = normalize_allowed_hosts(allowed_hosts, active_port)
    server.morfeo_terminal_enabled = bool(terminal)
    record_server_start()
    if refresh:
        _start_board_refresh(target_dir)

    url = f"http://{HOST}:{active_port}/"
    login = terminal_auth.login_url(None, server) if terminal else None
    print("==> Morfeo Command Center UI activo.")
    print(f"    Abre el tablero: {url}")
    if login:
        print(f"    Activa el CLI: {login}")
    print("    Presiona Ctrl+C para detener el servidor.", flush=True)

    if not no_open:
        # The login URL sets the CLI cookie and redirects to the board, so the
        # opened tab can use the embedded terminal at once.
        open_browser(login or url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor Morfeo UI detenido.")
    finally:
        server.server_close()
    return 0
