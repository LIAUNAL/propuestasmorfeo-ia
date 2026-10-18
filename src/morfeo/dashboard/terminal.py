"""Interactive Pseudo-Terminal (PTY) and WebSocket bridge for Morfeo.

Provides real-time interactive terminal streaming for coding agents
(Claude Code, OpenCode, Pi, Antigravity CLI, or shell) directly within
the Morfeo Command Center web dashboard. Zero external dependencies.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import pty
import select
import shutil
import signal
import socket
import struct
import subprocess
import termios
from pathlib import Path
from typing import Any, Optional


WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

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


def get_available_agents() -> list[dict[str, Any]]:
    """Inspect and return the status of all supported CLI coding agents."""
    agents_spec = [
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
    agent_id = (agent_id or "claude").lower().strip()
    system_shell = os.environ.get("SHELL") or find_executable("zsh") or find_executable("bash") or "/bin/sh"

    if agent_id == "claude":
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
            return [path], "Antigravity CLI", None
        return [system_shell], "Shell (Antigravity no instalado)", "\r\n\x1b[33m[Morfeo] Antigravity CLI ('agy') no se encontró en el PATH. Iniciando shell interactivo...\x1b[0m\r\n"

    else:
        # Default shell
        return [system_shell], "Shell interactivo", None


def run_pty_session(
    sock: socket.socket,
    workspace_dir: Path,
    agent_id: str = "claude",
    init_rows: int = 24,
    init_cols: int = 80,
) -> None:
    """Stream bidirectional I/O between an xterm.js WebSocket and a child process PTY."""
    cmd_args, resolved_name, warning_banner = build_agent_command(agent_id)

    # Set up child environment
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    env["LANG"] = env.get("LANG", "en_US.UTF-8")

    # Add tool dirs to PATH
    existing_path = env.get("PATH", "")
    paths_to_add = [str(d) for d in CLI_SEARCH_DIRS if str(d) not in existing_path]
    if paths_to_add:
        env["PATH"] = ":".join(paths_to_add) + ":" + existing_path

    # Point to active proposal if present
    current_run_file = workspace_dir / "proposals" / ".current-run"
    if current_run_file.is_file():
        active_run = current_run_file.read_text(encoding="utf-8").strip()
        if active_run:
            env["RUN_ROOT"] = f"proposals/{active_run}"
            env["ACTIVE_RUN"] = active_run

    master_fd, slave_fd = pty.openpty()
    set_terminal_size(master_fd, rows=init_rows, cols=init_cols)

    try:
        proc = subprocess.Popen(
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

    # Send startup message / banner to client
    welcome_banner = (
        f"\r\n\x1b[1;36m┌──────────────────────────────────────────────────────────────┐\x1b[0m\r\n"
        f"\x1b[1;36m│\x1b[0m  \x1b[1;35mMorfeo Command Center\x1b[0m — Terminal interactivo activo        \x1b[1;36m│\x1b[0m\r\n"
        f"\x1b[1;36m│\x1b[0m  Agente: \x1b[1;32m{resolved_name:<49}\x1b[0m \x1b[1;36m│\x1b[0m\r\n"
        f"\x1b[1;36m│\x1b[0m  Directorio: \x1b[90m{str(workspace_dir)[-45:]:<45}\x1b[0m \x1b[1;36m│\x1b[0m\r\n"
        f"\x1b[1;36m└──────────────────────────────────────────────────────────────┘\x1b[0m\r\n\r\n"
    )
    try:
        sock.sendall(encode_ws_frame(welcome_banner.encode("utf-8"), 0x1))
        if warning_banner:
            sock.sendall(encode_ws_frame(warning_banner.encode("utf-8"), 0x1))
    except Exception:
        pass

    sock.setblocking(False)
    in_buffer = bytearray()
    should_exit = False

    while not should_exit:
        # Check child process lifecycle
        if proc.poll() is not None:
            # Drain remaining PTY output
            try:
                r, _, _ = select.select([master_fd], [], [], 0.05)
                if master_fd in r:
                    leftover = os.read(master_fd, 8192)
                    if leftover:
                        sock.sendall(encode_ws_frame(leftover, 0x1))
            except Exception:
                pass

            exit_msg = (
                f"\r\n\x1b[33m[Morfeo] Sesión finalizada (código de salida: {proc.returncode}).\x1b[0m\r\n"
                f"\x1b[90mPuedes reiniciar la sesión desde el selector de agente o cerrar el panel.\x1b[0m\r\n"
            )
            try:
                sock.sendall(encode_ws_frame(exit_msg.encode("utf-8"), 0x1))
                sock.sendall(encode_ws_frame(b"", 0x8))  # WebSocket close
            except Exception:
                pass
            break

        # Wait for either PTY output or WebSocket input
        try:
            rlist, _, _ = select.select([master_fd, sock.fileno()], [], [], 0.1)
        except (select.error, OSError):
            break

        # Process PTY output -> send to WebSocket client
        if master_fd in rlist:
            try:
                chunk = os.read(master_fd, 8192)
                if not chunk:
                    break
                sock.sendall(encode_ws_frame(chunk, 0x1))
            except (OSError, socket.error):
                break

        # Process WebSocket input from client -> write to PTY
        if sock.fileno() in rlist:
            try:
                raw_data = sock.recv(8192)
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
                        should_exit = True
                        break
                    elif opcode == 0x9:  # WS Ping -> Pong
                        sock.sendall(encode_ws_frame(payload, 0xA))
                    elif opcode in (0x1, 0x2):
                        # Inspect for control JSON (resize / switch)
                        handled_control = False
                        if payload.startswith(b'{"type"') or payload.startswith(b'{"type "'):
                            try:
                                msg = json.loads(payload.decode("utf-8"))
                                mtype = msg.get("type")
                                if mtype == "resize":
                                    cols = int(msg.get("cols", 80))
                                    rows = int(msg.get("rows", 24))
                                    set_terminal_size(master_fd, rows=rows, cols=cols)
                                    handled_control = True
                            except Exception:
                                pass

                        if not handled_control:
                            os.write(master_fd, payload)
            except (BlockingIOError, ssl_error if "ssl_error" in locals() else ()):
                pass
            except (OSError, socket.error):
                break

    # Cleanup subprocess and descriptors
    try:
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
    except Exception:
        pass

    try:
        os.close(master_fd)
    except OSError:
        pass
