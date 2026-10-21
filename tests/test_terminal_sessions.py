"""The agent session outlives the WebSocket that opened it.

A reload, a closed CLI window or a dropped connection detaches the browser from
the session; the agent keeps running on the server and the dashboard reattaches
with `?session=<id>`, receiving the recent output once. The session can be
queried, interrupted (Esc or Ctrl-C, by agent) and closed over HTTP.
"""

from __future__ import annotations

import json
import os
import select
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from src.morfeo.dashboard.server import MorfeoDashboardHandler
from src.morfeo.dashboard.terminal import SESSIONS, interrupt_key

MASK = b"\x01\x02\x03\x04"


def ws_frame(payload: bytes) -> bytes:
    masked = bytes(b ^ MASK[i % 4] for i, b in enumerate(payload))
    return bytes([0x81, 0x80 | len(payload)]) + MASK + masked


def read_frames(buf: bytearray) -> list[tuple[int, bytes]]:
    """Decode the complete unmasked server frames at the head of `buf`."""
    frames = []
    while len(buf) >= 2:
        opcode, length, head = buf[0] & 0x0F, buf[1] & 0x7F, 2
        if length == 126:
            if len(buf) < 4:
                break
            length, head = int.from_bytes(buf[2:4], "big"), 4
        elif length == 127:
            if len(buf) < 10:
                break
            length, head = int.from_bytes(buf[2:10], "big"), 10
        if len(buf) < head + length:
            break
        frames.append((opcode, bytes(buf[head:head + length])))
        del buf[:head + length]
    return frames


class Client:
    def __init__(self, port: int, query: str) -> None:
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=2.0)
        self.sock.sendall((
            f"GET /ws/terminal?{query} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii"))
        resp = b""
        while b"\r\n\r\n" not in resp:
            resp += self.sock.recv(1024)
        self.buf = bytearray(resp.split(b"\r\n\r\n", 1)[1])
        self.output = bytearray()
        self.texts: list[dict] = []

    def pump(self, until: bytes | None = None, seconds: float = 4.0) -> None:
        end = time.time() + seconds
        while time.time() < end:
            for opcode, payload in read_frames(self.buf):
                if opcode == 0x1 and payload.startswith(b"{"):
                    self.texts.append(json.loads(payload))
                elif opcode == 0x2:
                    self.output.extend(payload)
            if until and until in self.output:
                return
            if until is None and self.texts:
                return
            r, _, _ = select.select([self.sock], [], [], 0.05)
            if r:
                chunk = self.sock.recv(65536)
                if not chunk:
                    return
                self.buf.extend(chunk)

    def send(self, text: str) -> None:
        self.sock.sendall(ws_frame(text.encode("utf-8")))

    def close(self) -> None:
        self.sock.close()


class TerminalSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        # A plain sh starts at once; a user zsh with a heavy prompt makes timing flaky.
        previous_shell = os.environ.get("SHELL")
        os.environ["SHELL"] = "/bin/sh"
        self.addCleanup(lambda: os.environ.__setitem__("SHELL", previous_shell) if previous_shell else os.environ.pop("SHELL", None))
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": Path(__file__).resolve().parent.parent})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        SESSIONS.close_all()  # sessions other tests left behind
        self.addCleanup(SESSIONS.close_all)

    def http(self, method: str, path: str) -> tuple[int, dict]:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method)
        try:
            with urllib.request.urlopen(req, timeout=3) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def open_shell(self) -> tuple[Client, str]:
        client = Client(self.port, "agent=shell&cols=80&rows=24")
        client.pump()
        self.assertTrue(client.texts, "the server announces the session")
        hello = client.texts[0]
        self.assertEqual(hello["type"], "session")
        self.assertEqual(hello["agent"], "shell")
        self.assertFalse(hello["reattached"])
        return client, hello["id"]

    def test_a_dropped_connection_keeps_the_session_and_a_reattach_replays_it_once(self) -> None:
        first, sid = self.open_shell()
        first.send("echo MARK_$((40+2))\n")
        first.pump(until=b"MARK_42")
        self.assertIn(b"MARK_42", first.output)
        first.close()
        time.sleep(0.3)

        status, body = self.http("GET", f"/api/terminal/sessions/{sid}")
        self.assertEqual(status, 200)
        self.assertEqual(body["alive"], True)
        self.assertEqual(body["attached"], False)

        second = Client(self.port, f"agent=shell&session={sid}")
        second.pump(until=b"MARK_42")
        self.addCleanup(second.close)
        self.assertEqual(second.texts[0], {"type": "session", "id": sid, "agent": "shell", "reattached": True})
        self.assertEqual(bytes(second.output).count(b"MARK_42"), 1, "the replay is sent once")
        second.send("echo SAME_$$\n")
        second.pump(until=b"SAME_")
        self.assertEqual(len(SESSIONS.ids()), 1, "no second agent was spawned")

    def test_a_second_viewer_takes_the_session_and_the_first_is_told(self) -> None:
        first, sid = self.open_shell()
        self.addCleanup(first.close)
        second = Client(self.port, f"agent=shell&session={sid}")
        self.addCleanup(second.close)
        second.pump()
        self.assertTrue(second.texts[0]["reattached"])
        first.pump(until=b"<no such output>", seconds=1.5)
        self.assertIn({"type": "detached", "reason": "taken"}, first.texts)

    def test_an_unknown_session_id_opens_a_new_session(self) -> None:
        client = Client(self.port, "agent=shell&session=deadbeef")
        self.addCleanup(client.close)
        client.pump()
        self.assertFalse(client.texts[0]["reattached"])
        self.assertNotEqual(client.texts[0]["id"], "deadbeef")

    def test_a_session_of_another_agent_is_not_reattached(self) -> None:
        first, sid = self.open_shell()
        first.close()
        other = Client(self.port, f"agent=claude-missing&session={sid}")
        self.addCleanup(other.close)
        other.pump()
        self.assertNotEqual(other.texts[0]["id"], sid)

    def test_interrupt_stops_the_running_command_and_keeps_the_session(self) -> None:
        client, sid = self.open_shell()
        self.addCleanup(client.close)
        client.send("echo START_$((3+3)); sleep 30\n")
        client.pump(until=b"START_6")
        time.sleep(0.3)
        status, body = self.http("POST", f"/api/terminal/sessions/{sid}/interrupt")
        self.assertEqual(status, 200)
        self.assertEqual(body["key"], "ctrl-c")
        client.send("echo AFTER_$((1+1))\n")
        client.pump(until=b"AFTER_2", seconds=5)
        # Without the interrupt the shell would only answer after the 30 s sleep.
        self.assertIn(b"AFTER_2", client.output)
        self.assertTrue(self.http("GET", f"/api/terminal/sessions/{sid}")[1]["alive"])

    def test_delete_closes_the_session(self) -> None:
        client, sid = self.open_shell()
        client.close()
        status, body = self.http("DELETE", f"/api/terminal/sessions/{sid}")
        self.assertEqual((status, body["ok"]), (200, True))
        self.assertNotIn(sid, SESSIONS.ids())
        status, body = self.http("GET", f"/api/terminal/sessions/{sid}")
        self.assertEqual((status, body["ok"]), (404, False))

    def test_unknown_sessions_answer_404(self) -> None:
        self.assertEqual(self.http("GET", "/api/terminal/sessions/nope")[0], 404)
        self.assertEqual(self.http("POST", "/api/terminal/sessions/nope/interrupt")[0], 404)
        self.assertEqual(self.http("DELETE", "/api/terminal/sessions/nope")[0], 404)

    def test_a_reattach_replays_before_any_newer_output(self) -> None:
        import re
        from src.morfeo.dashboard import terminal

        class Recorder(terminal._WsClient):
            def __init__(self) -> None:
                self.frames: list[tuple[int, bytes]] = []
                self._lock = threading.Lock()

            def send(self, payload: bytes, opcode: int = 0x2) -> bool:
                if opcode == 0x1:
                    time.sleep(0.01)  # a slow socket widens the hello-to-replay gap
                with self._lock:
                    self.frames.append((opcode, payload))
                return True

        session = SESSIONS.create(Path(__file__).resolve().parent.parent, "shell", 24, 80)
        session.write(b"i=0; while :; do echo L$i; i=$((i+1)); done\n")
        time.sleep(0.3)
        for _ in range(15):
            viewer = Recorder()
            session.attach(viewer, True)
            time.sleep(0.02)
            session.detach(viewer)
            self.assertEqual(viewer.frames[0][0], 0x1, "the hello comes first")
            text = b"".join(p for op, p in viewer.frames[1:] if op == 0x2).decode("utf-8", "replace")
            numbers = [int(n) for n in re.findall(r"^L(\d+)\r?$", text, re.M)]
            self.assertEqual(numbers, sorted(numbers), "live output never precedes the replay")

    def test_the_interrupt_key_depends_on_the_agent(self) -> None:
        self.assertEqual(interrupt_key("claude"), b"\x1b")
        self.assertEqual(interrupt_key("opencode"), b"\x1b")
        self.assertEqual(interrupt_key("pi"), b"\x1b")
        self.assertEqual(interrupt_key("shell"), b"\x03")
        self.assertEqual(interrupt_key("herdr"), b"\x03")

    def test_the_session_cap_closes_the_oldest_detached_session(self) -> None:
        from src.morfeo.dashboard import terminal
        ids = []
        for _ in range(terminal.MAX_SESSIONS + 1):
            client, sid = self.open_shell()
            client.close()
            ids.append(sid)
            time.sleep(0.05)
        self.assertEqual(len(SESSIONS.ids()), terminal.MAX_SESSIONS)
        self.assertNotIn(ids[0], SESSIONS.ids())


if __name__ == "__main__":
    unittest.main()
