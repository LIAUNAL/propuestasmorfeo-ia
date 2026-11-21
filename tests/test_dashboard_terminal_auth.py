"""Access control of the dashboard and its embedded terminal (terminal_auth.py).

Real HTTP requests and real WebSocket handshakes against a dashboard on an
ephemeral port: the Host allow-list (421), the same-origin guard on every
state-changing request (403), the terminal login that exchanges the login
secret for an HttpOnly SameSite=Strict cookie, the cookie and Origin the
WebSocket upgrade requires, the throttled activation and the agents endpoint.
"""

from __future__ import annotations

import http.client
import io
import json
import shutil
import socket
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from src.morfeo.dashboard import terminal, terminal_auth, terminal_routes
from src.morfeo.dashboard.server import MorfeoDashboardHandler
from src.morfeo.dashboard.terminal import SESSIONS


def make_workspace() -> Path:
    root = Path(tempfile.mkdtemp(prefix="morfeo-auth-"))
    commands = root / ".claude" / "commands"
    commands.mkdir(parents=True)
    (commands / "propuesta-continuar.md").write_text(
        "---\ndescription: Avanza una unidad del pipeline.\nargument-hint: \"\"\n---\n# x\n", encoding="utf-8")
    (commands / "compilar-pdf.md").write_text(
        "---\ndescription: \"Compila la propuesta a PDF.\"\n---\n", encoding="utf-8")
    (commands / "sin-frontmatter.md").write_text("# Solo un título\n", encoding="utf-8")
    (commands / "_interno.md").write_text("---\ndescription: oculto\n---\n", encoding="utf-8")
    (root / "proposals" / "run-1").mkdir(parents=True)
    (root / "proposals" / ".current-run").write_text("run-1\n", encoding="utf-8")
    return root


class DashboardAccessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = make_workspace()
        self.addCleanup(shutil.rmtree, self.workspace, True)
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": self.workspace})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.auth = terminal_auth.auth_for(self.server)
        self.origin = f"http://127.0.0.1:{self.port}"
        self.host = f"127.0.0.1:{self.port}"
        SESSIONS.close_all()
        self.addCleanup(SESSIONS.close_all)

    # -- helpers -----------------------------------------------------------
    def request(self, method: str, path: str, headers: dict | None = None,
                body: bytes | None = None) -> tuple[int, dict, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            hdrs = {"Host": self.host, **(headers or {})}
            if body is not None:
                hdrs.setdefault("Content-Type", "application/json")
                hdrs["Content-Length"] = str(len(body))
            for name, value in hdrs.items():
                if value is not None:
                    conn.putheader(name, value)
            conn.endheaders(body)
            res = conn.getresponse()
            data = res.read()
            return res.status, {k.lower(): v for k, v in res.getheaders()}, data
        finally:
            conn.close()

    def cookie(self) -> str:
        return f"{self.auth.cookie_name}={self.auth.issue_session()}"

    def handshake(self, headers: dict) -> bytes:
        headers = dict(headers)
        host = headers.pop("Host", self.host)
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=3)
        try:
            lines = [
                "GET /ws/terminal?agent=shell&cols=80&rows=24 HTTP/1.1",
                f"Host: {host}",
                "Upgrade: websocket",
                "Connection: Upgrade",
                "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==",
                "Sec-WebSocket-Version: 13",
            ] + [f"{k}: {v}" for k, v in headers.items()]
            sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("ascii"))
            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                resp += chunk
            return resp.split(b"\r\n", 1)[0]
        finally:
            sock.close()

    # -- Verifier probes (independent review of 7b5769f) --------------------
    def test_session_cookie_survives_other_apps_cookies(self) -> None:
        # Cookies ignore the port: any other dev server on 127.0.0.1 can add
        # cookies that SimpleCookie rejects as a whole header.
        token = self.auth.issue_session()
        for other in ['pref={"a":1,"b":2}', 'x[0]=1', 'x=a b', 'q="ab']:
            with self.subTest(other=other):
                status, _, _ = self.request("GET", "/api/terminal/tools", {
                    "Origin": self.origin, "Cookie": f"{other}; {self.auth.cookie_name}={token}"})
                self.assertEqual(status, 200)

    def test_terminal_post_refuses_a_referer_without_origin(self) -> None:
        status, _, _ = self.request("POST", "/api/terminal/activate",
                                    {"Referer": f"{self.origin}/", "Cookie": self.cookie()}, b"{}")
        self.assertEqual(status, 403)
        status, _, _ = self.request("DELETE", "/api/terminal/sessions/nope",
                                    {"Referer": f"{self.origin}/", "Cookie": self.cookie()})
        self.assertEqual(status, 403)

    def test_login_secret_never_reaches_the_log_on_refused_requests(self) -> None:
        secret = self.auth.login_secret
        captured = io.StringIO()
        with mock.patch("sys.stderr", captured):
            self.request("GET", f"/api/terminal/login?token={secret}", {"Host": f"evil.example:{self.port}"})
            self.request("GET", f"/api/terminal/login/?token={secret}")
            self.request("POST", f"/api/terminal/login?token={secret}", {"Origin": "http://evil.example"}, b"{}")
        self.assertIn("token=***", captured.getvalue())
        self.assertNotIn(secret, captured.getvalue())

    # -- WebSocket ---------------------------------------------------------
    def test_websocket_upgrade_without_cookie_is_refused(self) -> None:
        status = self.handshake({"Origin": self.origin})
        self.assertNotIn(b"101", status)
        self.assertIn(b"401", status)
        self.assertEqual(SESSIONS.ids(), [], "no session was opened")

    def test_websocket_upgrade_with_cookie_but_foreign_origin_is_refused(self) -> None:
        status = self.handshake({"Origin": "http://evil.example", "Cookie": self.cookie()})
        self.assertNotIn(b"101", status)
        self.assertIn(b"403", status)

    def test_websocket_upgrade_with_cookie_but_no_origin_is_refused(self) -> None:
        status = self.handshake({"Cookie": self.cookie()})
        self.assertIn(b"403", status)

    def test_websocket_upgrade_with_a_wrong_cookie_is_refused(self) -> None:
        status = self.handshake({"Origin": self.origin, "Cookie": f"{self.auth.cookie_name}=forged"})
        self.assertIn(b"401", status)

    def test_websocket_upgrade_with_cookie_and_same_origin_switches_protocols(self) -> None:
        status = self.handshake({"Origin": self.origin, "Cookie": self.cookie()})
        self.assertIn(b"101", status)

    # -- terminal HTTP routes ------------------------------------------------
    def test_terminal_routes_without_cookie_answer_401(self) -> None:
        for method, path in (("GET", "/api/terminal/tools"), ("GET", "/api/terminal/sessions/x"),
                             ("DELETE", "/api/terminal/sessions/x"),
                             ("POST", "/api/terminal/launch-external")):
            status, headers, body = self.request(method, path, {"Origin": self.origin},
                                                 b"{}" if method == "POST" else None)
            self.assertEqual(status, 401, path)
            payload = json.loads(body)
            self.assertFalse(payload["ok"])
            self.assertIn("activ", payload["error"].lower())

    def test_terminal_routes_with_cookie_answer(self) -> None:
        status, _, body = self.request("DELETE", "/api/terminal/sessions/nope",
                                       {"Origin": self.origin, "Cookie": self.cookie()})
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body), {"ok": False, "error": "La sesión ya no existe"})

    # -- login ---------------------------------------------------------------
    def test_login_with_a_wrong_token_sets_no_cookie(self) -> None:
        status, headers, _ = self.request("GET", "/api/terminal/login?token=nope")
        self.assertEqual(status, 403)
        self.assertNotIn("set-cookie", headers)
        status, headers, _ = self.request("GET", "/api/terminal/login")
        self.assertEqual(status, 403)
        self.assertNotIn("set-cookie", headers)

    def test_login_with_the_right_token_sets_the_cookie_and_redirects(self) -> None:
        url = self.auth.login_url(self.origin)
        self.assertTrue(url.startswith(f"{self.origin}/api/terminal/login?token="))
        path = url[len(self.origin):]
        status, headers, _ = self.request("GET", path)
        self.assertEqual(status, 303)
        self.assertEqual(headers["location"], "/")
        cookie = headers["set-cookie"]
        attrs = [part.strip() for part in cookie.split(";")]
        name, value = attrs[0].split("=", 1)
        self.assertEqual(name, self.auth.cookie_name)
        self.assertNotEqual(value, self.auth.login_secret, "the session token is not the login secret")
        self.assertIn("HttpOnly", attrs)
        self.assertIn("SameSite=Strict", attrs)
        self.assertIn("Path=/", attrs)
        self.assertTrue(self.auth.authorized(value))
        # The cookie it set opens the WebSocket.
        self.assertIn(b"101", self.handshake({"Origin": self.origin, "Cookie": attrs[0]}))

    def test_module_login_url_uses_the_bound_socket(self) -> None:
        self.assertEqual(terminal_auth.login_url(None, self.server), self.auth.login_url(self.origin))

    # -- same-origin guard on every POST ------------------------------------
    def test_post_to_a_non_terminal_route_needs_the_same_origin(self) -> None:
        status, _, body = self.request("POST", "/api/judge/run", {"Origin": "http://evil.example"}, b"{}")
        self.assertEqual(status, 403)
        payload = json.loads(body)
        self.assertFalse(payload["ok"])
        self.assertIn("origen", payload["error"].lower())

        status, _, body = self.request("POST", "/api/judge/run", {"Origin": "null"}, b"{}")
        self.assertEqual(status, 403, "an opaque origin is foreign")
        self.assertFalse(json.loads(body)["ok"])

        # No Origin and no Referer: not a browser's cross-site request, so the
        # route answers as before (a local process could forge any header).
        status, _, body = self.request("POST", "/api/judge/run", {}, b"{}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True, "prompt": json.loads(body)["prompt"]})

        status, _, body = self.request("POST", "/api/judge/run",
                                       {"Origin": self.origin, "Sec-Fetch-Site": "cross-site"}, b"{}")
        self.assertEqual(status, 403)

        status, _, body = self.request("POST", "/api/judge/run", {"Origin": self.origin}, b"{}")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

        status, _, body = self.request("POST", "/api/judge/run",
                                       {"Origin": f"http://localhost:{self.port}"}, b"{}")
        self.assertEqual(status, 200)

    def test_a_same_origin_referer_stands_in_for_a_missing_origin(self) -> None:
        status, _, _ = self.request("POST", "/api/judge/run", {"Referer": f"{self.origin}/#judge"}, b"{}")
        self.assertEqual(status, 200)
        status, _, _ = self.request("POST", "/api/judge/run", {"Referer": "http://evil.example/x"}, b"{}")
        self.assertEqual(status, 403)

    def test_terminal_post_routes_require_the_origin_header(self) -> None:
        cookie = self.cookie()
        status, _, body = self.request("POST", "/api/terminal/sessions/x/interrupt", {"Cookie": cookie}, b"{}")
        self.assertEqual(status, 403)
        self.assertIn("Origin", json.loads(body)["error"])
        status, _, _ = self.request("DELETE", "/api/terminal/sessions/x", {"Cookie": cookie})
        self.assertEqual(status, 403)
        status, _, _ = self.request("DELETE", "/api/terminal/sessions/x", {"Cookie": cookie, "Origin": self.origin})
        self.assertEqual(status, 404)

    def test_a_foreign_origin_on_delete_is_refused_on_any_path(self) -> None:
        status, _, _ = self.request("DELETE", "/api/anything", {"Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("DELETE", "/api/anything")
        self.assertEqual(status, 404, "unchanged: the server has no such route")

    def test_another_port_on_the_same_host_is_a_foreign_origin(self) -> None:
        status, _, _ = self.request("POST", "/api/judge/run", {"Origin": f"http://127.0.0.1:{self.port + 1}"}, b"{}")
        self.assertEqual(status, 403)

    def test_get_requests_keep_working_without_origin(self) -> None:
        status, _, _ = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        status, _, _ = self.request("GET", "/")
        self.assertEqual(status, 200)

    # -- Host allow-list -------------------------------------------------------
    def test_a_foreign_host_header_answers_421(self) -> None:
        for path in ("/", "/api/status", "/api/terminal/agents"):
            status, _, _ = self.request("GET", path, {"Host": f"evil.example:{self.port}"})
            self.assertEqual(status, 421, path)
        status, _, _ = self.request("POST", "/api/judge/run",
                                    {"Host": f"evil.example:{self.port}", "Origin": self.origin}, b"{}")
        self.assertEqual(status, 421)
        self.assertIn(b"421", self.handshake({"Host": f"evil.example:{self.port}", "Origin": self.origin,
                                               "Cookie": self.cookie()}))
        for host in (f"localhost:{self.port}", f"[::1]:{self.port}"):
            code, _, _ = self.request("GET", "/api/status", {"Host": host})
            self.assertEqual(code, 200, host)

    # -- activation ------------------------------------------------------------
    def test_activate_opens_the_login_url_once_per_window(self) -> None:
        with mock.patch.object(terminal_routes, "open_browser", return_value=True) as opener:
            status, _, body = self.request("POST", "/api/terminal/activate", {"Origin": self.origin}, b"{}")
            self.assertEqual(status, 200)
            payload = json.loads(body)
            self.assertEqual(payload["origin"], self.origin)
            self.assertTrue(payload["ok"])
            self.assertNotIn(self.auth.login_secret, body.decode("utf-8"), "the secret never reaches the page")
            opener.assert_called_once_with(self.auth.login_url(self.origin))

            status, _, body = self.request("POST", "/api/terminal/activate", {"Origin": self.origin}, b"{}")
            self.assertEqual(status, 429)
            self.assertFalse(json.loads(body)["ok"])
            opener.assert_called_once()

    def test_activate_needs_the_same_origin_and_never_runs_on_get(self) -> None:
        with mock.patch.object(terminal_routes, "open_browser", return_value=True) as opener:
            status, _, _ = self.request("POST", "/api/terminal/activate", {"Origin": "http://evil.example"}, b"{}")
            self.assertEqual(status, 403)
            status, _, _ = self.request("POST", "/api/terminal/activate", {}, b"{}")
            self.assertEqual(status, 403)
            status, _, _ = self.request("GET", "/api/terminal/activate", {"Origin": self.origin})
            self.assertNotEqual(status, 200)
            opener.assert_not_called()

    # -- agents and quick commands --------------------------------------------
    def test_agents_report_authorization_and_missing_clis(self) -> None:
        status, _, body = self.request("GET", "/api/terminal/agents")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["ok"])
        self.assertFalse(data["authorized"])
        self.assertIsInstance(data["enabled"], bool)
        self.assertEqual(data["agents"], [], "agents are withheld until the browser is activated")

        real = terminal.find_executable
        with mock.patch.object(terminal, "find_executable",
                               side_effect=lambda name: None if name == "claude" else real(name)):
            status, _, body = self.request("GET", "/api/terminal/agents", {"Cookie": self.cookie()})
        data = json.loads(body)
        self.assertTrue(data["authorized"])
        agents = {a["id"]: a for a in data["agents"]}
        self.assertIs(agents["claude"]["available"], False)
        self.assertIs(agents["shell"]["available"], True)

    def test_quick_commands_come_from_claude_commands(self) -> None:
        _, _, body = self.request("GET", "/api/terminal/agents")
        quick = json.loads(body)["quick"]
        self.assertEqual([q["name"] for q in quick],
                         ["/compilar-pdf", "/propuesta-continuar", "/sin-frontmatter"])
        self.assertEqual(quick[0]["description"], "Compila la propuesta a PDF.")
        self.assertEqual(quick[1]["description"], "Avanza una unidad del pipeline.")
        self.assertEqual(quick[2]["description"], "")

    def test_quick_commands_are_capped_at_24(self) -> None:
        commands = self.workspace / ".claude" / "commands"
        for i in range(30):
            (commands / f"cmd-{i:02d}.md").write_text("---\ndescription: x\n---\n", encoding="utf-8")
        _, _, body = self.request("GET", "/api/terminal/agents")
        self.assertEqual(len(json.loads(body)["quick"]), 24)


class GuardUnitTest(unittest.TestCase):
    """The checks on their own, with a fake handler."""

    class Headers(dict):
        def get_all(self, name, default=None):
            value = self.get(name)
            return [value] if value is not None else default

    def handler(self, headers: dict, address=("127.0.0.1", 8123)):
        server = type("S", (), {"server_address": address})()
        return type("Hd", (), {"server": server, "headers": self.Headers(headers)})()

    def test_bound_origin_is_loopback_only(self) -> None:
        self.assertEqual(terminal_auth.bound_origin(type("S", (), {"server_address": ("127.0.0.1", 9)})()),
                         "http://127.0.0.1:9")
        self.assertEqual(terminal_auth.bound_origin(type("S", (), {"server_address": ("::1", 9, 0, 0)})()),
                         "http://[::1]:9")
        self.assertIsNone(terminal_auth.bound_origin(type("S", (), {"server_address": ("0.0.0.0", 9)})()))

    def test_same_origin(self) -> None:
        self.assertTrue(terminal_auth.same_origin(self.handler({"Origin": "http://127.0.0.1:8123"})))
        self.assertTrue(terminal_auth.same_origin(self.handler({"Origin": "http://localhost:8123"})))
        self.assertFalse(terminal_auth.same_origin(self.handler({"Origin": "http://[::1]:8123"})))
        self.assertFalse(terminal_auth.same_origin(self.handler({"Origin": "null"})))
        self.assertFalse(terminal_auth.same_origin(self.handler({})))
        self.assertIsNone(terminal_auth.origin_refusal(self.handler({}), require_origin=False))
        self.assertIsNotNone(terminal_auth.origin_refusal(self.handler({"Origin": "null"}), require_origin=False))
        self.assertIsNotNone(terminal_auth.origin_refusal(
            self.handler({"Referer": "http://evil.example/"}), require_origin=False))
        self.assertFalse(terminal_auth.same_origin(self.handler({"Origin": "https://127.0.0.1:8123"})))

    def test_session_tokens_are_unguessable_and_checked(self) -> None:
        auth = terminal_auth.auth_for(self.handler({}).server)
        token = auth.issue_session()
        self.assertGreaterEqual(len(token), 40)
        self.assertNotEqual(token, auth.issue_session())
        self.assertTrue(auth.authorized(token))
        self.assertFalse(auth.authorized(token[:-1]))
        self.assertFalse(auth.authorized(""))
        self.assertFalse(auth.authorized(None))
        self.assertFalse(auth.accepts_login(token))

    def test_a_malformed_cookie_header_is_no_session(self) -> None:
        handler = self.handler({"Cookie": 'morfeo_terminal_8123="unterminated'})
        self.assertFalse(terminal_auth.has_session(handler))


if __name__ == "__main__":
    unittest.main()
