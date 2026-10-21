"""Interactive Pseudo-Terminal (PTY) and WebSocket bridge for Morfeo.

Provides real-time interactive terminal streaming for coding agents
(Claude Code, OpenCode, Pi, Antigravity CLI, or shell) directly within
the Morfeo Command Center web dashboard. Zero external dependencies.
"""

from __future__ import annotations

import atexit
import base64
import fcntl
import hashlib
import json
import os
import pty
import re
import secrets
import select
import shutil
import signal
import socket
import struct
import subprocess
import termios
import threading
import time
from pathlib import Path
from typing import Any, Optional


WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Strip terminal capability queries that the server answers directly on master_fd
# so xterm.js does not echo 256 palette/color reports or mutate theme colors.
_ANSI_QUERY_STRIP_RE = re.compile(
    rb"\x1b\]1[01];\?(?:\x1b\\|\x07)"
    rb"|\x1b\]4;\d+;\?(?:\x1b\\|\x07)"
    rb"|\x1b\[\?u"
    rb"|\x1b\[\?996n"
    rb"|\x1b\[1[468]t"
)


def split_complete_utf8(data: bytes) -> tuple[bytes, bytes]:
    """Split a byte chunk into (valid_utf8_prefix, incomplete_trailing_bytes)."""
    if not data:
        return b"", b""
    n = len(data)
    for i in range(1, min(4, n + 1)):
        b = data[n - i]
        if (b & 0xC0) == 0x80:
            continue
        if b < 0x80:
            return data, b""
        if (b & 0xE0) == 0xC0:
            expected = 2
        elif (b & 0xF0) == 0xE0:
            expected = 3
        elif (b & 0xF8) == 0xF0:
            expected = 4
        else:
            return data, b""
        if i < expected:
            return data[: n - i], data[n - i :]
        return data, b""
    return data, b""

# Standard paths where user CLI tools are typically installed
CLI_SEARCH_DIRS = [
    Path.home() / ".local" / "bin",
    Path.home() / ".npm-global" / "bin",
    Path("/opt/homebrew/bin"),
    Path("/usr/local/bin"),
    Path.home() / ".cargo" / "bin",
]


def ws_handshake_accept(key: str) -> str:
    """Calculate RFC 6455 Sec-WebSocket-Accept token."""
    source = (key.strip() + WS_GUID).encode("utf-8")
    return base64.b64encode(hashlib.sha1(source).digest()).decode("ascii")


def encode_ws_frame(data: bytes, opcode: int = 0x1) -> bytes:
    """Encode an unmasked WebSocket frame from server to client."""
    length = len(data)
    if length <= 125:
        header = bytes([0x80 | (opcode & 0x0F), length])
    elif length <= 65535:
        header = bytes([0x80 | (opcode & 0x0F), 126]) + struct.pack("!H", length)
    else:
        header = bytes([0x80 | (opcode & 0x0F), 127]) + struct.pack("!Q", length)
    return header + data


def decode_ws_client_frame(buf: bytes | bytearray) -> tuple[Optional[tuple[int, bytes]], int]:
    """Decode a masked WebSocket frame received from the client.

    Returns ((opcode, payload), bytes_consumed) or (None, 0) if incomplete.
    """
    if len(buf) < 2:
        return None, 0

    b1, b2 = buf[0], buf[1]
    opcode = b1 & 0x0F
    masked = bool(b2 & 0x80)
    length = b2 & 0x7F
    offset = 2

    if length == 126:
        if len(buf) < 4:
            return None, 0
        length = struct.unpack("!H", buf[2:4])[0]
        offset = 4
    elif length == 127:
        if len(buf) < 10:
            return None, 0
        length = struct.unpack("!Q", buf[2:10])[0]
        offset = 10

    if masked:
        if len(buf) < offset + 4 + length:
            return None, 0
        mask = buf[offset : offset + 4]
        offset += 4
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(buf[offset : offset + length]))
    else:
        if len(buf) < offset + length:
            return None, 0
        payload = bytes(buf[offset : offset + length])

    return (opcode, payload), offset + length


def set_terminal_size(fd: int, rows: int = 24, cols: int = 80) -> None:
    """Update window size (TIOCSWINSZ) on the master PTY file descriptor."""
    try:
        winsize = struct.pack("HHHH", max(1, rows), max(2, cols), 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    except Exception:
        pass


def find_executable(name: str) -> Optional[str]:
    """Find executable path in system PATH or standard tool directories."""
    found = shutil.which(name)
    if found:
        return found

    for d in CLI_SEARCH_DIRS:
        candidate = d / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    return None


def get_current_agent_pane_id(workspace_dir: Optional[Path] = None) -> Optional[str]:
    """Find the pane ID of the active agent session currently executing."""
    herdr_bin = find_executable("herdr")
    if not herdr_bin:
        return None

    # 1. Environment variable inherited by server or agent process
    env_pane = os.environ.get("HERDR_PANE_ID")
    if env_pane:
        try:
            v_res = subprocess.run([herdr_bin, "pane", "get", env_pane.strip()], capture_output=True, text=True, timeout=1.5)
            if v_res.returncode == 0:
                return env_pane.strip()
        except Exception:
            pass

    # 2. Query herdr pane list
    try:
        res = subprocess.run([herdr_bin, "pane", "list"], capture_output=True, text=True, timeout=2.0)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            panes = data.get("result", {}).get("panes", [])
            if not panes:
                return None

            resolved_ws = str(workspace_dir.resolve()) if workspace_dir else None

            # Best candidate: matching workspace cwd and active agent
            if resolved_ws:
                for p in panes:
                    p_cwd = p.get("cwd") or p.get("foreground_cwd")
                    if p_cwd == resolved_ws and p.get("agent_status") == "working":
                        return p.get("pane_id")

                for p in panes:
                    p_cwd = p.get("cwd") or p.get("foreground_cwd")
                    if p_cwd == resolved_ws and p.get("agent"):
                        return p.get("pane_id")

                for p in panes:
                    p_cwd = p.get("cwd") or p.get("foreground_cwd")
                    if p_cwd == resolved_ws:
                        return p.get("pane_id")

            # Fallback across all panes: active working agent
            for p in panes:
                if p.get("agent_status") == "working" and p.get("agent"):
                    return p.get("pane_id")

            # Fallback: focused pane
            for p in panes:
                if p.get("focused"):
                    return p.get("pane_id")

            # Fallback: first pane
            return panes[0].get("pane_id")
    except Exception:
        pass

    return None


def detect_terminal_tools(workspace_dir: Optional[Path] = None) -> dict[str, Any]:
    """Inspect availability of Herdr and terminal emulators (Ghostty priority over WezTerm)."""
    herdr_bin = find_executable("herdr")
    herdr_socket = Path.home() / ".config" / "herdr" / "herdr.sock"
    herdr_server_running = False
    herdr_client_running = False

    if herdr_bin:
        try:
            status_res = subprocess.run([herdr_bin, "status", "server"], capture_output=True, text=True, timeout=1.5)
            if status_res.returncode == 0 and "status: running" in status_res.stdout:
                herdr_server_running = True
        except Exception:
            herdr_server_running = herdr_socket.exists()

        try:
            pgrep_res = subprocess.run(["pgrep", "-x", "herdr"], capture_output=True, text=True, timeout=1.5)
            herdr_client_running = pgrep_res.returncode == 0 and bool(pgrep_res.stdout.strip())
        except Exception:
            herdr_client_running = False

    # Ghostty detection (priority)
    ghostty_bin = find_executable("ghostty")
    ghostty_app = Path("/Applications/Ghostty.app")
    ghostty_user_app = Path.home() / "Applications" / "Ghostty.app"
    ghostty_installed = bool(ghostty_bin or ghostty_app.exists() or ghostty_user_app.exists())
    ghostty_path = ghostty_bin or (str(ghostty_app) if ghostty_app.exists() else (str(ghostty_user_app) if ghostty_user_app.exists() else None))

    # WezTerm detection
    wezterm_bin = find_executable("wezterm")
    wezterm_app = Path("/Applications/WezTerm.app")
    wezterm_user_app = Path.home() / "Applications" / "WezTerm.app"
    wezterm_installed = bool(wezterm_bin or wezterm_app.exists() or wezterm_user_app.exists())
    wezterm_path = wezterm_bin or (str(wezterm_app) if wezterm_app.exists() else (str(wezterm_user_app) if wezterm_user_app.exists() else None))

    # Preferred terminal emulator: Ghostty priority over WezTerm
    preferred_terminal = "ghostty" if ghostty_installed else ("wezterm" if wezterm_installed else None)

    herdr_installed = herdr_bin is not None
    ready = bool(herdr_installed and preferred_terminal)

    active_pane_id = get_current_agent_pane_id(workspace_dir) if herdr_installed else None

    missing = []
    if not herdr_installed:
        missing.append("herdr")
    if not preferred_terminal:
        missing.append("terminal")

    return {
        "ready": ready,
        "preferred_terminal": preferred_terminal,
        "missing": missing,
        "active_pane": active_pane_id,
        "herdr": {
            "installed": herdr_installed,
            "path": herdr_bin,
            "server_running": herdr_server_running,
            "client_running": herdr_client_running,
            "active_pane": active_pane_id,
        },
        "ghostty": {
            "installed": ghostty_installed,
            "path": ghostty_path,
        },
        "wezterm": {
            "installed": wezterm_installed,
            "path": wezterm_path,
        },
    }


def ensure_herdr_workspace(workspace_dir: Path) -> dict[str, Any]:
    """Ensure Herdr workspace exists for the monitored project path and is focused."""
    herdr_bin = find_executable("herdr")
    if not herdr_bin:
        return {"ok": False, "error": "Herdr no está instalado en el sistema"}

    resolved_path = workspace_dir.resolve()
    target_label = resolved_path.name

    try:
        res = subprocess.run([herdr_bin, "workspace", "list"], capture_output=True, text=True, timeout=3.0)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            workspaces = data.get("result", {}).get("workspaces", [])
            for ws in workspaces:
                ws_id = ws.get("workspace_id")
                if ws.get("label") == target_label:
                    if not ws.get("focused"):
                        subprocess.run([herdr_bin, "workspace", "focus", ws_id], capture_output=True, text=True, timeout=2.0)
                    return {"ok": True, "workspace_id": ws_id, "action": "focused", "label": target_label}

            create_res = subprocess.run(
                [herdr_bin, "workspace", "create", "--cwd", str(resolved_path), "--label", target_label, "--focus"],
                capture_output=True, text=True, timeout=3.0
            )
            if create_res.returncode == 0:
                cdata = json.loads(create_res.stdout)
                ws_id = cdata.get("result", {}).get("workspace_id")
                return {"ok": True, "workspace_id": ws_id, "action": "created", "label": target_label}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {"ok": True, "action": "noop"}


def launch_external_terminal(workspace_dir: Path) -> dict[str, Any]:
    """Launch or focus external terminal (Ghostty priority over WezTerm) with Herdr at workspace_dir."""
    tools = detect_terminal_tools(workspace_dir)
    if not tools["ready"]:
        return {
            "ok": False,
            "error": "missing_tools",
            "missing": tools["missing"],
            "tools": tools,
        }

    resolved_path = workspace_dir.resolve()
    ensure_herdr_workspace(resolved_path)

    preferred = tools["preferred_terminal"]
    herdr_bin = tools["herdr"]["path"] or "herdr"
    client_running = tools["herdr"]["client_running"]

    try:
        if preferred == "ghostty":
            if client_running:
                subprocess.run(["open", "-a", "Ghostty"], capture_output=True, text=True, timeout=3.0)
                action = "activated"
            else:
                subprocess.run(
                    ["open", "-a", "Ghostty", "--args", f"--working-directory={resolved_path}", "-e", herdr_bin],
                    capture_output=True, text=True, timeout=3.0
                )
                action = "launched"
            return {"ok": True, "terminal": "ghostty", "action": action, "cwd": str(resolved_path)}

        elif preferred == "wezterm":
            wezterm_bin = tools["wezterm"]["path"]
            if client_running:
                subprocess.run(["open", "-a", "WezTerm"], capture_output=True, text=True, timeout=3.0)
                action = "activated"
            else:
                if wezterm_bin and shutil.which("wezterm"):
                    subprocess.Popen([wezterm_bin, "start", "--cwd", str(resolved_path), herdr_bin])
                else:
                    subprocess.run(["open", "-a", "WezTerm"], capture_output=True, text=True, timeout=3.0)
                action = "launched"
            return {"ok": True, "terminal": "wezterm", "action": action, "cwd": str(resolved_path)}

    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {"ok": False, "error": "No hay emulador de terminal disponible"}


def get_available_agents() -> list[dict[str, Any]]:
    """Inspect and return the status of all supported CLI coding agents."""
    agents_spec = [
        {"id": "herdr", "name": "Herdr (Workspace Manager)", "bin": "herdr", "desc": "Terminal Workspace Manager con Spaces y Agents"},
        {"id": "claude", "name": "Claude Code", "bin": "claude", "desc": "Asistente primario canónico"},
        {"id": "opencode", "name": "OpenCode", "bin": "opencode", "desc": "Agente CLI multi-modelo OpenCode"},
        {"id": "pi", "name": "Pi", "desc": "Agente autónomo Pi CLI", "bin": "pi"},
        {"id": "agy", "name": "Antigravity CLI", "bin": "agy", "desc": "Google Antigravity CLI"},
        {"id": "shell", "name": "Shell Zsh / Bash", "bin": "zsh", "desc": "Consola del workspace"},
    ]

    result = []
    for spec in agents_spec:
        bin_name = spec["bin"]
        exec_path = find_executable(bin_name)
        if not exec_path and spec["id"] == "shell":
            exec_path = find_executable("bash") or "/bin/sh"

        result.append({
            "id": spec["id"],
            "name": spec["name"],
            "desc": spec["desc"],
            "installed": exec_path is not None,
            "path": exec_path,
        })
    return result


def build_agent_command(agent_id: str) -> tuple[list[str], str, Optional[str]]:
    """Determine the command args and friendly banner for the requested agent.

    Returns (cmd_args, resolved_name, banner_warning).
    """
    agent_id = (agent_id or "herdr").lower().strip()
    system_shell = os.environ.get("SHELL") or find_executable("zsh") or find_executable("bash") or "/bin/sh"

    if agent_id == "herdr":
        path = find_executable("herdr")
        if path:
            return [path], "Herdr (Workspace Manager)", None
        return [system_shell], "Shell (Herdr no instalado)", "\r\n\x1b[33m[Morfeo] Herdr ('herdr') no se encontró en el PATH. Iniciando shell interactivo...\x1b[0m\r\n"

    elif agent_id == "claude":
        path = find_executable("claude")
        if path:
            return [path], "Claude Code", None
        return [system_shell], "Shell (Claude Code no instalado)", "\r\n\x1b[33m[Morfeo] Claude Code ('claude') no se encontró en el PATH. Iniciando shell interactivo...\x1b[0m\r\n"

    elif agent_id == "opencode":
        path = find_executable("opencode")
        if path:
            return [path], "OpenCode", None
        return [system_shell], "Shell (OpenCode no instalado)", "\r\n\x1b[33m[Morfeo] OpenCode ('opencode') no se encontró en el PATH. Iniciando shell interactivo...\x1b[0m\r\n"

    elif agent_id == "pi":
        path = find_executable("pi")
        if path:
            return [path], "Pi", None
        return [system_shell], "Shell (Pi no instalado)", "\r\n\x1b[33m[Morfeo] Pi ('pi') no se encontró en el PATH. Iniciando shell interactivo...\x1b[0m\r\n"

    elif agent_id in ("agy", "antigravity"):
        path = find_executable("agy") or find_executable("antigravity")
        if path:
            return [path, "--dangerously-skip-permissions"], "Antigravity CLI", None
        return [system_shell], "Shell (Antigravity no instalado)", "\r\n\x1b[33m[Morfeo] Antigravity CLI ('agy') no se encontró en el PATH. Iniciando shell interactivo...\x1b[0m\r\n"

    else:
        # Default shell
        return [system_shell], "Shell interactivo", None


def forward_input_to_pane(herdr_bin: str, pane_id: str, payload: bytes) -> None:
    """Forward client keyboard input to Herdr pane."""
    if not payload:
        return

    # Check common single and control sequences
    if payload in (b"\r", b"\n"):
        subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "enter"], capture_output=True, timeout=1.0)
        return
    if payload == b"\x1b":
        subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "esc"], capture_output=True, timeout=1.0)
        return
    if payload == b"\x03":
        subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "ctrl+c"], capture_output=True, timeout=1.0)
        return
    if payload in (b"\x7f", b"\x08"):
        subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "backspace"], capture_output=True, timeout=1.0)
        return
    if payload == b"\t":
        subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "tab"], capture_output=True, timeout=1.0)
        return
    if payload == b"\x1b[A":
        subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "up"], capture_output=True, timeout=1.0)
        return
    if payload == b"\x1b[B":
        subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "down"], capture_output=True, timeout=1.0)
        return
    if payload == b"\x1b[C":
        subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "right"], capture_output=True, timeout=1.0)
        return
    if payload == b"\x1b[D":
        subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "left"], capture_output=True, timeout=1.0)
        return

    # Decode as UTF-8 text
    try:
        text = payload.decode("utf-8")
        if text.endswith("\r") or text.endswith("\n"):
            trimmed = text.rstrip("\r\n")
            if trimmed:
                subprocess.run([herdr_bin, "pane", "send-text", pane_id, trimmed], capture_output=True, timeout=1.0)
            subprocess.run([herdr_bin, "pane", "send-keys", pane_id, "enter"], capture_output=True, timeout=1.0)
        else:
            subprocess.run([herdr_bin, "pane", "send-text", pane_id, text], capture_output=True, timeout=1.0)
    except Exception:
        pass


def run_pane_mirror_session(
    sock: socket.socket,
    pane_id: str,
    herdr_bin: str,
    init_rows: int = 24,
    init_cols: int = 80,
) -> None:
    """Stream a live interactive mirror of an active Herdr pane to a WebSocket client."""
    sock.settimeout(2.0)

    # Initial visible screen fetch
    try:
        r0 = subprocess.run(
            [herdr_bin, "pane", "read", pane_id, "--format", "ansi", "--source", "visible"],
            capture_output=True,
            text=False,
            timeout=2.0,
        )
        if r0.returncode == 0:
            initial_screen = b"\x1b[2J\x1b[H" + r0.stdout
            sock.sendall(encode_ws_frame(initial_screen, 0x2))
    except Exception:
        pass

    # Initial revision
    last_revision = None
    try:
        r_get = subprocess.run([herdr_bin, "pane", "get", pane_id], capture_output=True, text=True, timeout=1.5)
        if r_get.returncode == 0:
            data = json.loads(r_get.stdout)
            last_revision = data.get("result", {}).get("pane", {}).get("revision")
    except Exception:
        pass

    in_buffer = bytearray()
    last_check_time = 0.0
    check_interval = 0.15

    while True:
        # Check socket for incoming client frames or disconnect
        try:
            rlist, _, _ = select.select([sock.fileno()], [], [], 0.05)
        except (select.error, OSError):
            break

        if sock.fileno() in rlist:
            try:
                raw_data = sock.recv(8192)
            except (BlockingIOError, socket.timeout):
                raw_data = None
            except (OSError, socket.error):
                break

            if raw_data is not None:
                if not raw_data:
                    break
                in_buffer.extend(raw_data)

                while True:
                    frame_res, consumed = decode_ws_client_frame(in_buffer)
                    if frame_res is None:
                        break
                    del in_buffer[:consumed]
                    opcode, payload = frame_res

                    if opcode == 0x8:  # WS Close
                        return
                    elif opcode == 0x9:  # WS Ping -> Pong
                        try:
                            sock.sendall(encode_ws_frame(payload, 0xA))
                        except Exception:
                            pass
                    elif opcode in (0x1, 0x2):
                        # Control message check
                        handled_control = False
                        if payload.startswith(b'{"type"') or payload.startswith(b'{"type "'):
                            try:
                                msg = json.loads(payload.decode("utf-8"))
                                mtype = msg.get("type")
                                if mtype == "ping":
                                    try:
                                        sock.sendall(encode_ws_frame(b"pong", 0xA))
                                    except Exception:
                                        pass
                                    handled_control = True
                                elif mtype == "resize":
                                    handled_control = True
                            except Exception:
                                pass

                        if not handled_control:
                            forward_input_to_pane(herdr_bin, pane_id, payload)

        # Check revision update
        now = time.time()
        if now - last_check_time >= check_interval:
            last_check_time = now
            try:
                g_res = subprocess.run([herdr_bin, "pane", "get", pane_id], capture_output=True, text=True, timeout=1.2)
                if g_res.returncode != 0:
                    break
                g_data = json.loads(g_res.stdout)
                curr_rev = g_data.get("result", {}).get("pane", {}).get("revision")
                if curr_rev is not None and curr_rev != last_revision:
                    last_revision = curr_rev
                    read_res = subprocess.run(
                        [herdr_bin, "pane", "read", pane_id, "--format", "ansi", "--source", "visible"],
                        capture_output=True,
                        text=False,
                        timeout=1.5,
                    )
                    if read_res.returncode == 0:
                        sock.sendall(encode_ws_frame(b"\x1b[H" + read_res.stdout + b"\x1b[J", 0x2))
            except (socket.error, OSError):
                break
            except Exception:
                pass



# --- Persistent agent sessions --------------------------------------------------
# The agent process belongs to a session, not to the WebSocket that opened it. A
# reload, a closed CLI window or a dropped connection only detaches the browser;
# the agent keeps working, and the dashboard reattaches with `?session=<id>` and
# receives the recent output once.

# Recent output kept per session and replayed on reattach.
SESSION_BUFFER_BYTES = 256 * 1024
# Live agent processes at once; the oldest detached one is closed first.
MAX_SESSIONS = 4
# A session nobody reattached to in this time is closed.
DETACHED_SESSION_TTL_S = 12 * 3600

# Esc interrupts the turn of a TUI agent without closing it; Ctrl-C would quit it.
_ESC_INTERRUPT_AGENTS = {"claude", "opencode", "pi", "agy", "antigravity"}


def interrupt_key(agent_id: str) -> bytes:
    """The keystroke that stops the agent's current turn but keeps the session."""
    return b"\x1b" if (agent_id or "").lower() in _ESC_INTERRUPT_AGENTS else b"\x03"


def _agent_env(workspace_dir: Path, agent_id: str) -> dict[str, str]:
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    env["LANG"] = env.get("LANG", "en_US.UTF-8")

    # Add tool dirs to PATH
    existing_path = env.get("PATH", "")
    paths_to_add = [str(d) for d in CLI_SEARCH_DIRS if str(d) not in existing_path]
    if paths_to_add:
        env["PATH"] = ":".join(paths_to_add) + ":" + existing_path

    # Clean any parent Herdr environment variables so child Herdr attaches cleanly
    for k in list(env.keys()):
        if "HERDR" in k or k == "TERM_PROGRAM":
            del env[k]

    # Ensure Herdr workspace is configured for the monitored project path
    if agent_id == "herdr":
        ensure_herdr_workspace(workspace_dir)

    # Point to active proposal if present
    current_run_file = workspace_dir / "proposals" / ".current-run"
    if current_run_file.is_file():
        active_run = current_run_file.read_text(encoding="utf-8").strip()
        if active_run:
            env["RUN_ROOT"] = f"proposals/{active_run}"
            env["ACTIVE_RUN"] = active_run
    return env


def _answer_terminal_queries(master_fd: int, chunk: bytes) -> bytes:
    """Answer the capability queries crossterm and ratatui TUIs send, and strip them."""
    replies = (
        (b"]11;?", b"\x1b]11;rgb:0808/0c0c/1414\x1b\\"),
        (b"]10;?", b"\x1b]10;rgb:f1f1/f5f5/f9f9\x1b\\"),
        (b"[?u", b"\x1b[?0u"),
        (b"[?996n", b"\x1b[?996;1n"),
        (b"[16t", b"\x1b[6;16;8t"),
    )
    if b"\x1b[c" in chunk:
        try:
            os.write(master_fd, b"\x1b[?62;22c")
        except Exception:
            pass
        chunk = chunk.replace(b"\x1b[c", b"")
    for query, reply in replies:
        if query in chunk:
            try:
                os.write(master_fd, reply)
            except Exception:
                pass
    if b"\x1b" in chunk:
        chunk = _ANSI_QUERY_STRIP_RE.sub(b"", chunk)
    return chunk


def _is_capability_echo(payload: bytes) -> bool:
    """xterm.js answers to capability queries, which TUIs would read as keypresses."""
    if payload.startswith(b"\x1b[?") and payload.endswith((b"c", b"u", b"n")):
        return True
    if payload.startswith((b"\x1b[6;", b"\x1b[4;")) and payload.endswith(b"t"):
        return True
    return payload.startswith((b"\x1b]>", b"\x1b]11;", b"\x1b]10;", b"\x1b]4;"))


class _WsClient:
    """One browser connection; sends are serialized between the reader and the socket loop."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._lock = threading.Lock()

    def send(self, payload: bytes, opcode: int = 0x2) -> bool:
        frame = encode_ws_frame(payload, opcode)
        with self._lock:
            for _ in range(2):
                try:
                    self.sock.sendall(frame)
                    return True
                except (socket.timeout, BlockingIOError):
                    time.sleep(0.005)
                except (OSError, socket.error):
                    return False
        return False


class TerminalSession:
    """An agent process on a PTY, with its recent output and at most one viewer."""

    def __init__(self, workspace_dir: Path, agent_id: str, rows: int, cols: int) -> None:
        self.id = secrets.token_hex(8)
        self.agent = agent_id
        self.workspace_dir = workspace_dir
        self.rows, self.cols = max(1, rows), max(2, cols)
        self.created_at = time.time()
        self.detached_at: float | None = time.time()
        self.ended = False
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._client: _WsClient | None = None

        cmd_args, self.resolved_name, warning_banner = build_agent_command(agent_id)
        env = _agent_env(workspace_dir, agent_id)
        self.master_fd, slave_fd = pty.openpty()
        set_terminal_size(self.master_fd, rows=self.rows, cols=self.cols)
        try:
            self.proc = subprocess.Popen(
                cmd_args,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=str(workspace_dir),
                env=env,
                close_fds=True,
                preexec_fn=os.setsid,
            )
        finally:
            os.close(slave_fd)

        # Startup banner only for plain shell, to avoid TUI artifacts
        if agent_id == "shell":
            self._record((
                f"\r\n\x1b[1;36m┌──────────────────────────────────────────────────────────────┐\x1b[0m\r\n"
                f"\x1b[1;36m│\x1b[0m  \x1b[1;35mMorfeo Command Center\x1b[0m: Terminal interactivo activo         \x1b[1;36m│\x1b[0m\r\n"
                f"\x1b[1;36m│\x1b[0m  Agente: \x1b[1;32m{self.resolved_name:<49}\x1b[0m \x1b[1;36m│\x1b[0m\r\n"
                f"\x1b[1;36m│\x1b[0m  Directorio: \x1b[90m{str(workspace_dir)[-45:]:<45}\x1b[0m \x1b[1;36m│\x1b[0m\r\n"
                f"\x1b[1;36m└──────────────────────────────────────────────────────────────┘\x1b[0m\r\n\r\n"
            ).encode("utf-8"))
        elif warning_banner:
            self._record(warning_banner.encode("utf-8"))

        self._reader = threading.Thread(target=self._read_loop, name=f"pty-{self.id}", daemon=True)
        self._reader.start()

    @property
    def alive(self) -> bool:
        return not self.ended and self.proc.poll() is None

    @property
    def attached(self) -> bool:
        return self._client is not None

    def describe(self) -> dict[str, Any]:
        return {"ok": True, "id": self.id, "agent": self.agent, "alive": self.alive, "attached": self.attached}

    def _record(self, data: bytes) -> None:
        """Keep `data` for the replay and forward it to the viewer, if any.

        The send happens under the lock `attach` holds while it replays, so a
        live chunk never reaches the viewer before the replay of older output.
        """
        with self._lock:
            self._buffer.extend(data)
            if len(self._buffer) > SESSION_BUFFER_BYTES:
                cut = len(self._buffer) - SESSION_BUFFER_BYTES
                # Start the replay at a line so it does not open mid escape sequence.
                newline = self._buffer.find(b"\n", cut)
                del self._buffer[: newline + 1 if 0 <= newline < cut + 4096 else cut]
            if self._client is not None:
                self._client.send(data)

    def _read_loop(self) -> None:
        remainder = b""
        while True:
            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.2)
            except (select.error, OSError, ValueError):
                break
            if self.master_fd in r:
                try:
                    raw = os.read(self.master_fd, 16384)
                except OSError:
                    raw = b""
                if not raw:
                    break
                chunk = _answer_terminal_queries(self.master_fd, remainder + raw)
                complete, remainder = split_complete_utf8(chunk)
                if complete:
                    self._record(complete)
            elif self.proc.poll() is not None:
                break
        if remainder:
            self._record(remainder)
        try:
            self.proc.wait(timeout=1.0)
        except Exception:
            pass
        self.ended = True
        self._record((
            f"\r\n\x1b[33m[Morfeo] Sesión finalizada (código de salida: {self.proc.returncode}).\x1b[0m\r\n"
            f"\x1b[90mPuedes reiniciar la sesión desde el selector de agente o cerrar el panel.\x1b[0m\r\n"
        ).encode("utf-8"))
        with self._lock:
            client = self._client
        if client is not None:
            client.send(b"", 0x8)  # WebSocket close

    def attach(self, client: _WsClient, reattached: bool) -> None:
        """Make `client` the viewer: announce the session, then replay its output."""
        hello = {"type": "session", "id": self.id, "agent": self.agent, "reattached": reattached}
        with self._lock:
            previous = self._client
            self._client = client
            self.detached_at = None
            if previous is not None and previous is not client:
                # One viewer at a time: the newer tab takes the session, and the
                # older one is told so it does not reconnect and take it back.
                previous.send(b'{"type":"detached","reason":"taken"}', 0x1)
                previous.send(b"", 0x8)
            # Hello and replay go out before any newer output (see `_record`).
            client.send(json.dumps(hello).encode("utf-8"), 0x1)
            if self._buffer:
                client.send(bytes(self._buffer))

    def detach(self, client: _WsClient) -> None:
        with self._lock:
            if self._client is client:
                self._client = None
                self.detached_at = time.time()

    def write(self, data: bytes) -> bool:
        try:
            os.write(self.master_fd, data)
            return True
        except OSError:
            return False

    def interrupt(self) -> bytes:
        key = interrupt_key(self.agent)
        self.write(key)
        return key

    def resize(self, rows: int, cols: int, redraw: bool) -> None:
        size_changed = (rows, cols) != (self.rows, self.cols)
        self.rows, self.cols = rows, cols
        set_terminal_size(self.master_fd, rows=rows, cols=cols)
        if redraw and not size_changed and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGWINCH)
            except Exception:
                pass

    def close(self) -> None:
        """Terminate the agent's process group and release the PTY."""
        try:
            if self.proc.poll() is None:
                # SIGHUP as a closed terminal would; interactive shells ignore SIGTERM.
                for sig in (signal.SIGHUP, signal.SIGTERM):
                    try:
                        os.killpg(os.getpgid(self.proc.pid), sig)
                    except (ProcessLookupError, PermissionError):
                        pass
                try:
                    self.proc.wait(timeout=1.0)
                except Exception:
                    try:
                        os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                    except Exception:
                        pass
        except Exception:
            pass
        self.ended = True
        with self._lock:
            client, self._client = self._client, None
        if client is not None:
            # Told explicitly, the viewer forgets the session instead of reconnecting to it.
            client.send(b'{"type":"ended"}', 0x1)
            client.send(b"", 0x8)
        # The reader owns reads on the fd: let it finish before the fd number can be reused.
        if threading.current_thread() is not self._reader:
            self._reader.join(timeout=1.5)
        try:
            os.close(self.master_fd)
        except OSError:
            pass


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, TerminalSession] = {}
        self._lock = threading.Lock()

    def ids(self) -> list[str]:
        with self._lock:
            return list(self._sessions)

    def get(self, session_id: str | None) -> TerminalSession | None:
        if not session_id:
            return None
        with self._lock:
            return self._sessions.get(session_id)

    def _reap(self) -> list[TerminalSession]:
        """Drop ended sessions and detached ones past their TTL; call with the lock held."""
        now = time.time()
        gone = [s for s in self._sessions.values()
                if not s.alive or (s.detached_at is not None and now - s.detached_at > DETACHED_SESSION_TTL_S)]
        for s in gone:
            del self._sessions[s.id]
        return gone

    def create(self, workspace_dir: Path, agent_id: str, rows: int, cols: int) -> TerminalSession:
        with self._lock:
            evicted = self._reap()
            while len(self._sessions) >= MAX_SESSIONS:
                pool = [s for s in self._sessions.values() if not s.attached] or list(self._sessions.values())
                oldest = min(pool, key=lambda s: s.detached_at or s.created_at)
                del self._sessions[oldest.id]
                evicted.append(oldest)
        for s in evicted:
            s.close()
        session = TerminalSession(workspace_dir, agent_id, rows, cols)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def remove(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        session.close()
        return True

    def close_all(self) -> None:
        with self._lock:
            sessions, self._sessions = list(self._sessions.values()), {}
        for s in sessions:
            s.close()


SESSIONS = SessionRegistry()
atexit.register(SESSIONS.close_all)


def run_pty_session(
    sock: socket.socket,
    workspace_dir: Path,
    agent_id: str = "claude",
    init_rows: int = 24,
    init_cols: int = 80,
    session_id: str | None = None,
) -> None:
    """Attach an xterm.js WebSocket to an agent session, reusing `session_id` when it is live.

    A session is reused only for the same workspace and agent. Closing the socket
    detaches it; the agent keeps running until it exits, is closed over HTTP, or
    the registry evicts it.
    """
    session = SESSIONS.get(session_id)
    reattached = bool(session and session.alive and session.agent == agent_id
                      and session.workspace_dir == workspace_dir)
    if not reattached:
        session = SESSIONS.create(workspace_dir, agent_id, init_rows, init_cols)
    assert session is not None
    client = _WsClient(sock)
    sock.settimeout(2.0)
    session.attach(client, reattached)

    in_buffer = bytearray()
    try:
        while session.alive:
            try:
                rlist, _, _ = select.select([sock.fileno()], [], [], 0.2)
            except (select.error, OSError, ValueError):
                break
            if not rlist:
                continue
            try:
                raw_data = sock.recv(8192)
            except (BlockingIOError, socket.timeout):
                continue
            except (OSError, socket.error):
                break
            if not raw_data:
                break  # Client disconnected
            in_buffer.extend(raw_data)

            closing = False
            while True:
                frame_res, consumed = decode_ws_client_frame(in_buffer)
                if frame_res is None:
                    break
                del in_buffer[:consumed]
                opcode, payload = frame_res
                if opcode == 0x8:  # WS Close
                    closing = True
                    break
                if opcode == 0x9:  # WS Ping -> Pong
                    client.send(payload, 0xA)
                    continue
                if opcode not in (0x1, 0x2):
                    continue
                # Inspect for control JSON (resize / ping)
                if payload.startswith(b'{"type"'):
                    try:
                        msg = json.loads(payload.decode("utf-8"))
                    except Exception:
                        msg = None
                    if isinstance(msg, dict) and msg.get("type") == "resize":
                        try:
                            cols = max(2, int(msg.get("cols", 80)))
                            rows = max(1, int(msg.get("rows", 24)))
                        except (TypeError, ValueError):
                            continue
                        session.resize(rows, cols, bool(msg.get("redraw")))
                        continue
                    if isinstance(msg, dict) and msg.get("type") == "ping":
                        client.send(b"pong", 0xA)
                        continue
                if _is_capability_echo(payload):
                    continue
                if not session.write(payload):
                    closing = True
                    break
            if closing:
                break
    finally:
        session.detach(client)
