"""HTTP and WebSocket routes of the dashboard's embedded terminal.

The request handler (`server.MorfeoDashboardHandler`) delegates every
`/api/terminal/*` request and the `/ws/terminal` upgrade to `dispatch`. The
handlers below write the response through the handler object, reusing its
helpers (`_send_json`, `send_response`, `wfile`, `workspace_dir`), so the
responses are the same as when they lived in `server.py`.
"""

from __future__ import annotations

import json
from typing import Any

SESSIONS_PREFIX = "/api/terminal/sessions/"


def dispatch(handler: Any, method: str, path: str) -> bool:
    """Serve a terminal route; return True when `path` is one of them."""
    if method == "GET":
        if path == "/api/terminal/agents":
            serve_terminal_agents(handler)
        elif path == "/api/terminal/tools":
            serve_terminal_tools(handler)
        elif path == "/ws/terminal":
            handle_terminal_ws(handler)
        elif path.startswith(SESSIONS_PREFIX):
            handle_terminal_session(handler, "GET", path)
        else:
            return False
        return True
    if method == "POST":
        if path == "/api/terminal/launch-external":
            handle_launch_external_terminal(handler)
        elif path.startswith(SESSIONS_PREFIX):
            handle_terminal_session(handler, "POST", path)
        else:
            return False
        return True
    if method == "DELETE":
        if path.startswith(SESSIONS_PREFIX):
            handle_terminal_session(handler, "DELETE", path)
            return True
        return False
    return False


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
    from .terminal import get_available_agents
    agents = get_available_agents()
    body = json.dumps({"ok": True, "agents": agents}, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


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

    import urllib.parse
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
