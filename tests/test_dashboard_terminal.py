"""Tests for Morfeo Dashboard PTY and WebSocket Terminal bridge."""

import json
import socket
import struct
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer

from src.morfeo.dashboard.server import MorfeoDashboardHandler
from src.morfeo.dashboard.terminal import (
    ws_handshake_accept,
    encode_ws_frame,
    decode_ws_client_frame,
    get_available_agents,
    build_agent_command,
)


class TestDashboardTerminalBridge(unittest.TestCase):
    def test_ws_handshake_accept(self):
        # RFC 6455 test vector
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        expected = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
        self.assertEqual(ws_handshake_accept(key), expected)

    def test_encode_and_decode_ws_frames(self):
        # Test short payload
        short_data = b"Hello Morfeo!"
        frame = encode_ws_frame(short_data, opcode=0x1)
        self.assertEqual(frame[0], 0x81)
        self.assertEqual(frame[1], len(short_data))
        self.assertEqual(frame[2:], short_data)

        # Simulate client masked frame
        mask = b"\x11\x22\x33\x44"
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(short_data))
        client_buf = bytes([0x81, 0x80 | len(short_data)]) + mask + masked

        res, consumed = decode_ws_client_frame(client_buf)
        self.assertIsNotNone(res)
        self.assertEqual(consumed, len(client_buf))
        opcode, payload = res
        self.assertEqual(opcode, 0x1)
        self.assertEqual(payload, short_data)

    def test_decode_medium_length_frame(self):
        # Medium payload (between 126 and 65535 bytes)
        medium_data = b"x" * 500
        mask = b"\xaa\xbb\xcc\xdd"
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(medium_data))
        client_buf = bytes([0x82, 0x80 | 126]) + struct.pack("!H", 500) + mask + masked

        res, consumed = decode_ws_client_frame(client_buf)
        self.assertIsNotNone(res)
        self.assertEqual(consumed, len(client_buf))
        opcode, payload = res
        self.assertEqual(opcode, 0x2)
        self.assertEqual(payload, medium_data)

    def test_get_available_agents(self):
        agents = get_available_agents()
        self.assertTrue(len(agents) >= 5)
        agent_ids = [a["id"] for a in agents]
        self.assertIn("herdr", agent_ids)
        self.assertIn("claude", agent_ids)
        self.assertIn("opencode", agent_ids)
        self.assertIn("pi", agent_ids)
        self.assertIn("agy", agent_ids)
        self.assertIn("shell", agent_ids)

        for a in agents:
            self.assertIn("name", a)
            self.assertIn("installed", a)
            self.assertIsInstance(a["installed"], bool)

    def test_build_agent_command(self):
        cmd, name, banner = build_agent_command("shell")
        self.assertTrue(len(cmd) >= 1)
        self.assertIn("shell", name.lower())

        cmd_claude, name_claude, banner_claude = build_agent_command("claude")
        self.assertTrue(len(cmd_claude) >= 1)

        cmd_herdr, name_herdr, banner_herdr = build_agent_command("herdr")
        self.assertTrue(len(cmd_herdr) >= 1)
        self.assertIn("herdr", name_herdr.lower())

    def test_detect_terminal_tools(self):
        from src.morfeo.dashboard.terminal import detect_terminal_tools
        tools = detect_terminal_tools()
        self.assertIn("ready", tools)
        self.assertIn("preferred_terminal", tools)
        self.assertIn("missing", tools)
        self.assertIn("herdr", tools)
        self.assertIn("ghostty", tools)
        self.assertIn("wezterm", tools)
        self.assertIsInstance(tools["ready"], bool)
        self.assertIsInstance(tools["missing"], list)
        if tools["ghostty"]["installed"]:
            self.assertEqual(tools["preferred_terminal"], "ghostty")

    def test_http_api_terminal_agents(self):
        workspace_dir = Path(__file__).resolve().parent.parent
        handler_cls = type("ConfiguredHandler", (MorfeoDashboardHandler,), {"workspace_dir": workspace_dir})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        port = server.server_address[1]

        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        try:
            import urllib.request
            url = f"http://127.0.0.1:{port}/api/terminal/agents"
            with urllib.request.urlopen(url) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data.get("ok"))
                self.assertTrue(isinstance(data.get("agents"), list))

            tools_url = f"http://127.0.0.1:{port}/api/terminal/tools"
            with urllib.request.urlopen(tools_url) as resp:
                self.assertEqual(resp.status, 200)
                tdata = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(tdata.get("ok"))
                self.assertIn("tools", tdata)
                self.assertIn("monitored_path", tdata["tools"])
        finally:
            server.shutdown()
            server.server_close()

    def test_live_pty_websocket_session(self):
        import select
        workspace_dir = Path(__file__).resolve().parent.parent
        handler_cls = type("ConfiguredHandler", (MorfeoDashboardHandler,), {"workspace_dir": workspace_dir})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        port = server.server_address[1]

        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        s = None
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=2.0)
            key = "dGhlIHNhbXBsZSBub25jZQ=="
            req = (
                f"GET /ws/terminal?agent=shell HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n"
            )
            s.sendall(req.encode("ascii"))
            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = s.recv(1024)
                if not chunk:
                    break
                resp += chunk

            self.assertIn(b"101 Switching Protocols", resp)
            self.assertIn(b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", resp)

            # Send command frame
            cmd = b"echo 'PTY_VERIFIED'\n"
            mask = b"\x01\x02\x03\x04"
            masked = bytes(b ^ mask[i % 4] for i, b in enumerate(cmd))
            frame = bytes([0x81, 0x80 | len(cmd)]) + mask + masked
            s.sendall(frame)

            # Read frames until PTY_VERIFIED is found in decoded output
            found = False
            buf = bytearray()
            for _ in range(40):
                r, _, _ = select.select([s], [], [], 0.1)
                if r:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buf.extend(chunk)
                    if b"PTY_VERIFIED" in buf:
                        found = True
                        break

            self.assertTrue(found, "PTY_VERIFIED was not received from PTY shell stream")

            # Clean exit
            exit_cmd = b"exit\n"
            masked_exit = bytes(b ^ mask[i % 4] for i, b in enumerate(exit_cmd))
            s.sendall(bytes([0x81, 0x80 | len(exit_cmd)]) + mask + masked_exit)
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
