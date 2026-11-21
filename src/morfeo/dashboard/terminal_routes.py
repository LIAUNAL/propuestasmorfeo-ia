"""HTTP and WebSocket routes of the dashboard's embedded terminal, and the
access guard of every dashboard request.

The request handler (`server.MorfeoDashboardHandler`) calls `dispatch` first
for every GET, POST and DELETE. Before any routing, `dispatch` applies the
checks of `terminal_auth`: a Host header outside the allow-list gets 421 (DNS
rebinding) and a state-changing request from a foreign origin gets 403, on
every path (the terminal's own routes also require the Origin header). It then serves the `/api/terminal/*` routes and the
`/ws/terminal` upgrade, which require the terminal session cookie. The
handlers write through the handler object, reusing its helpers (`_send_json`,
`send_response`, `wfile`, `workspace_dir`).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

from . import terminal_auth

SESSIONS_PREFIX = "/api/terminal/sessions/"
#: Quick commands offered by the CLI footer, at most.
MAX_QUICK_COMMANDS = 24

_NOT_ACTIVATED = "El CLI del tablero no está activado: usa «Activar CLI» o el enlace que imprimió morfeo ui"


def dispatch(handler: Any, method: str, path: str) -> bool:
    """Guard every request, then serve a terminal route.

    Returns True when this function answered (a refusal or a terminal route),
    False when the server should route `path` itself.
    """
    # Redact the login secret before any response, so a request refused by the
    # guards below never writes it to the access log either.
    handler.requestline = re.sub(r"token=[^&\s]*", "token=***", getattr(handler, "requestline", ""))
    if not terminal_auth.host_allowed(handler):
        _refuse(handler, 421, "Host no permitido: abre el tablero en 127.0.0.1 o localhost")
        return True
    if method in terminal_auth.MUTATING_METHODS:
        # Any route refuses a foreign (or `null`) Origin or Referer; the
        # terminal's routes, which reach a shell, require the Origin itself
        # (a Referer does not stand in for it).
        terminal = path.startswith("/api/terminal/")
        reason = terminal_auth.origin_refusal(
            handler, allow_referer=not terminal, require_origin=terminal)
        if reason is not None:
            _refuse(handler, 403, f"Solicitud rechazada: {reason}")
            return True

    if method == "GET":
        if path == "/api/terminal/agents":
            serve_terminal_agents(handler)
        elif path == "/api/terminal/login":
            handle_terminal_login(handler)
        elif path == "/api/terminal/tools":
            if _require_session(handler):
                serve_terminal_tools(handler)
        elif path == "/ws/terminal":
            handle_terminal_ws(handler)
        elif path.startswith(SESSIONS_PREFIX):
            if _require_session(handler):
                handle_terminal_session(handler, "GET", path)
        elif path.startswith("/api/terminal/"):
            _refuse(handler, 404, "Ruta del CLI desconocida")
        else:
            return False
        return True
    if method == "POST":
        if path == "/api/terminal/activate":
            handle_terminal_activate(handler)
        elif path == "/api/terminal/launch-external":
            if _require_session(handler):
                handle_launch_external_terminal(handler)
        elif path.startswith(SESSIONS_PREFIX):
            if _require_session(handler):
                handle_terminal_session(handler, "POST", path)
        else:
            return False
        return True
    if method == "DELETE":
        if path.startswith(SESSIONS_PREFIX):
            if _require_session(handler):
                handle_terminal_session(handler, "DELETE", path)
            return True
        return False
    return False


def _refuse(handler: Any, status: int, error: str) -> None:
    # The body of a refused request is never read: close the connection so it
    # is not parsed as the next request.
    handler.close_connection = True
    handler._send_json(status, {"ok": False, "error": error})


def _require_session(handler: Any) -> bool:
    if terminal_auth.has_session(handler):
        return True
    _refuse(handler, 401, _NOT_ACTIVATED)
    return False


def open_browser(url: str) -> bool:
    """Open `url` in the desktop browser; never raises."""
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False


def handle_terminal_login(handler: Any) -> None:
    """Exchange the login secret (`?token=`) for the session cookie, then go to `/`."""
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(handler.path).query)
    presented = (query.get("token") or [""])[0]
    # The access log prints the request line: never with the secret in it.
    handler.requestline = re.sub(r"token=[^&\s]*", "token=***", getattr(handler, "requestline", ""))
    auth = terminal_auth.auth_for(handler.server)
    if not auth.accepts_login(presented):
        _refuse(handler, 403, "Enlace de activación inválido o vencido")
        return
    token = auth.issue_session()
    handler.send_response(303)
    handler.send_header("Location", "/")
    handler.send_header("Set-Cookie", auth.set_cookie_value(token))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def handle_terminal_activate(handler: Any) -> None:
    """Open the login URL in the desktop browser (on a click of «Activar CLI»).

    `dispatch` already checked that the request is same-origin. The secret goes
    only to the browser the OS opens, never to the caller, and only to the
    socket this server listens on, never to a name taken from the request. The
    page is told that origin: a tab reached under another name (localhost for
    127.0.0.1) does not receive the cookie.
    """
    auth = terminal_auth.auth_for(handler.server)
    if auth.origin is None:
        _refuse(handler, 403, "El servidor no escucha en una dirección local: abre el enlace que imprimió morfeo ui")
        return
    if not auth.claim_activation():
        handler._send_json(429, {"ok": False, "throttled": True, "origin": auth.origin,
                                 "error": "Ya se abrió el enlace de activación: espera unos segundos"})
        return
    opened = open_browser(auth.login_url(auth.origin))
    handler._send_json(200, {"ok": True, "opened": opened, "origin": auth.origin})


def _terminal_enabled() -> bool:
    try:
        import fcntl  # noqa: F401
        import pty  # noqa: F401
    except ImportError:
        return False
    return True


def _frontmatter_description(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(4096)
    except OSError:
        return ""
    lines = head.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep and key.strip() == "description":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value.strip()
    return ""


def quick_commands(workspace_dir: Path) -> list[dict[str, str]]:
    """The workspace's slash commands (`.claude/commands/*.md`), at most 24."""
    commands_dir = Path(workspace_dir) / ".claude" / "commands"
    if not commands_dir.is_dir():
        return []
    files = sorted(p for p in commands_dir.glob("*.md") if p.is_file() and not p.name.startswith("_"))
    return [{"name": f"/{p.stem}", "description": _frontmatter_description(p)}
            for p in files[:MAX_QUICK_COMMANDS]]


def handle_terminal_session(handler: Any, method: str, path: str) -> None:
    """GET describes, POST …/interrupt stops the agent's turn, DELETE closes the session."""
    from .terminal import SESSIONS

    parts = path[len(SESSIONS_PREFIX):].strip("/").split("/")
    session = SESSIONS.get(parts[0])
    action = parts[1] if len(parts) > 1 else ""
    if session is None or not session.alive:
        handler._send_json(404, {"ok": False, "error": "La sesión ya no existe"})
        return
    if method == "GET" and not action:
        handler._send_json(200, session.describe())
    elif method == "POST" and action == "interrupt":
        key = session.interrupt()
        handler._send_json(200, {"ok": True, "id": session.id, "key": "esc" if key == b"\x1b" else "ctrl-c"})
    elif method == "DELETE" and not action:
        SESSIONS.remove(session.id)
        handler._send_json(200, {"ok": True, "id": session.id})
    else:
        handler._send_json(404, {"ok": False, "error": "Operación desconocida"})


def serve_terminal_agents(handler: Any) -> None:
    """Whether the CLI is enabled and this browser activated, its agents and quick commands.

    The agents (and where their CLIs live) are withheld until the browser holds
    the session cookie; an agent whose CLI is not installed is `available: false`.
    """
    from .terminal import get_available_agents

    enabled = _terminal_enabled()
    authorized = terminal_auth.has_session(handler)
    agents = []
    if authorized:
        agents = [{**a, "available": bool(a.get("installed"))} for a in get_available_agents()]
    default = next((a["id"] for a in agents if a["available"]), "shell")
    handler._send_json(200, {
        "ok": True,
        "enabled": enabled,
        "authorized": authorized,
        "agents": agents,
        "default": default,
        "quick": quick_commands(handler.workspace_dir),
    })


def serve_terminal_tools(handler: Any) -> None:
    from .terminal import detect_terminal_tools, get_current_agent_pane_id
    tools = detect_terminal_tools(handler.workspace_dir)
    tools["monitored_path"] = str(handler.workspace_dir.resolve())
    tools["active_pane"] = get_current_agent_pane_id(handler.workspace_dir)
    body = json.dumps({"ok": True, "tools": tools}, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_launch_external_terminal(handler: Any) -> None:
    from .terminal import launch_external_terminal
    res = launch_external_terminal(handler.workspace_dir)
    body = json.dumps(res, ensure_ascii=False).encode("utf-8")
    handler.send_response(200 if res.get("ok") else 400)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_terminal_ws(handler: Any) -> None:
    upgrade = handler.headers.get("Upgrade", "").strip().lower()
    if upgrade != "websocket":
        handler.send_error(400, "WebSocket Upgrade required")
        return

    key = handler.headers.get("Sec-WebSocket-Key", "")
    if not key:
        handler.send_error(400, "Missing Sec-WebSocket-Key")
        return

    # Browsers apply no CORS to WebSockets: the upgrade itself must prove it
    # comes from the dashboard's page (Origin, no Referer fallback) of an
    # activated browser (the session cookie).
    reason = terminal_auth.origin_refusal(handler, allow_referer=False)
    if reason is not None:
        _refuse(handler, 403, f"Conexión rechazada: {reason}")
        return
    if not _require_session(handler):
        return

    from .terminal import run_pty_session, ws_handshake_accept

    accept_token = ws_handshake_accept(key)
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_token}\r\n\r\n"
    )
    handler.wfile.write(response.encode("ascii"))
    handler.wfile.flush()

    parsed = urllib.parse.urlparse(handler.path)
    qs = urllib.parse.parse_qs(parsed.query)
    agent = qs.get("agent", ["herdr"])[0]
    session_id = qs.get("session", [None])[0]
    try:
        cols = int(qs.get("cols", [80])[0])
    except (ValueError, TypeError):
        cols = 80
    try:
        rows = int(qs.get("rows", [24])[0])
    except (ValueError, TypeError):
        rows = 24

    handler.close_connection = True

    run_pty_session(
        sock=handler.request,
        workspace_dir=handler.workspace_dir,
        agent_id=agent,
        init_rows=rows,
        init_cols=cols,
        session_id=session_id,
    )
