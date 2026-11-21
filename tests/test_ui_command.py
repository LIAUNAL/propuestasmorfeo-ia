"""`morfeo ui`: bind first, then open the browser on the CLI activation link.

The HTTP server, the board refresh, the start-up version record and the
browser are replaced, so nothing listens, nothing is regenerated and no
browser opens; `serve_forever` returns at once.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from morfeo import cli  # noqa: E402
from morfeo.core import ui  # noqa: E402
from morfeo.dashboard import terminal_auth  # noqa: E402


class _FakeServer:
    """Stands in for ThreadingHTTPServer and records the order of events."""

    events: list[tuple[str, object]] = []
    instances: list["_FakeServer"] = []

    def __init__(self, address, handler) -> None:
        self.server_address = address
        self.handler = handler
        _FakeServer.instances.append(self)
        _FakeServer.events.append(("bind", address))

    def serve_forever(self) -> None:
        _FakeServer.events.append(("serve", None))

    def server_close(self) -> None:
        _FakeServer.events.append(("close", None))


class StartUiTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = Path(tmp.name)
        (self.workspace / ".morfeo").mkdir()
        _FakeServer.events = []
        _FakeServer.instances = []
        self.refreshes: list[Path] = []

        def fake_open(url: str) -> bool:
            _FakeServer.events.append(("open", url))
            return True

        def fake_refresh(workspace: Path) -> None:
            self.refreshes.append(workspace)

        for patcher in (
            mock.patch.object(ui, "ThreadingHTTPServer", _FakeServer),
            mock.patch.object(ui, "open_browser", fake_open),
            mock.patch.object(ui, "_start_board_refresh", fake_refresh),
            mock.patch.object(ui, "record_server_start", lambda: "0"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _start(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["ui", str(self.workspace), *argv])
        return code, out.getvalue()

    @property
    def server(self) -> _FakeServer:
        self.assertEqual(len(_FakeServer.instances), 1)
        return _FakeServer.instances[0]

    def test_the_browser_opens_after_binding_on_the_login_url(self) -> None:
        code, _ = self._start("--port", "9311")
        self.assertEqual(code, 0)
        kinds = [kind for kind, _ in _FakeServer.events]
        self.assertEqual(kinds, ["bind", "open", "serve", "close"])
        self.assertEqual(_FakeServer.events[0][1], ("127.0.0.1", 9311))
        opened = _FakeServer.events[1][1]
        self.assertEqual(opened, terminal_auth.login_url(None, self.server))
        self.assertTrue(opened.startswith("http://127.0.0.1:9311/api/terminal/login?token="))

    def test_the_dashboard_url_and_the_activation_link_are_printed(self) -> None:
        _, out = self._start("--port", "9312", "--no-open")
        login = terminal_auth.login_url(None, self.server)
        self.assertIn("Abre el tablero: http://127.0.0.1:9312/", out)
        self.assertIn(f"Activa el CLI: {login}", out)

    def test_port_and_no_open_still_work(self) -> None:
        code, out = self._start("--port", "9313", "--no-open")
        self.assertEqual(code, 0)
        self.assertEqual(_FakeServer.events[0], ("bind", ("127.0.0.1", 9313)))
        self.assertNotIn("open", [kind for kind, _ in _FakeServer.events])
        self.assertIn("Presiona Ctrl+C", out)

    def test_the_start_up_refresh_runs_unless_no_refresh(self) -> None:
        self._start("--port", "9314", "--no-open")
        self.assertEqual(self.refreshes, [self.workspace.resolve()])
        self.refreshes.clear()
        _FakeServer.instances = []
        self._start("--port", "9315", "--no-open", "--no-refresh")
        self.assertEqual(self.refreshes, [])

    def test_no_terminal_marks_the_cli_disabled_and_skips_the_activation_link(self) -> None:
        _, out = self._start("--port", "9316", "--no-terminal")
        self.assertIs(self.server.morfeo_terminal_enabled, False)
        self.assertNotIn("Activa el CLI", out)
        self.assertIn("Abre el tablero: http://127.0.0.1:9316/", out)
        # Without the CLI there is nothing to activate: the plain board opens.
        self.assertIn(("open", "http://127.0.0.1:9316/"), _FakeServer.events)

    def test_the_terminal_is_enabled_by_default(self) -> None:
        self._start("--port", "9317", "--no-open")
        self.assertIs(self.server.morfeo_terminal_enabled, True)

    def test_allowed_hosts_reach_the_server_and_its_guard(self) -> None:
        self._start("--port", "9318", "--no-open",
                    "--allowed-host", "Morfeo.Local", "--allowed-host", "tunel.example:443")
        self.assertEqual(self.server.morfeo_allowed_hosts,
                         ("morfeo.local:9318", "tunel.example:443"))
        allowed = terminal_auth.auth_for(self.server).allowed_hosts
        self.assertIn("morfeo.local:9318", allowed)
        self.assertIn("tunel.example:443", allowed)
        self.assertIn("127.0.0.1:9318", allowed)

    def test_without_allowed_hosts_only_loopback_names_are_accepted(self) -> None:
        self._start("--port", "9319", "--no-open")
        self.assertEqual(self.server.morfeo_allowed_hosts, ())
        self.assertEqual(terminal_auth.auth_for(self.server).allowed_hosts,
                         frozenset({"127.0.0.1:9319", "localhost:9319", "[::1]:9319"}))

    def test_a_busy_port_prints_the_hint_and_serves_nothing(self) -> None:
        busy = OSError(98, "Address already in use")
        with mock.patch.object(ui, "ThreadingHTTPServer", side_effect=busy):
            code, out = self._start("--port", "9320")
        self.assertEqual(code, 0)
        self.assertIn("El puerto 9320 ya está en uso", out)
        self.assertEqual(_FakeServer.events, [])


class CliParsingTests(unittest.TestCase):
    def test_ui_options_reach_start_ui(self) -> None:
        with mock.patch.object(cli, "start_ui", return_value=0) as start:
            cli.main(["ui", "ws", "--port", "9000", "--no-open", "--no-refresh",
                      "--no-terminal", "--allowed-host", "a.local", "--allowed-host", "b:1"])
        start.assert_called_once_with(target_dir=Path("ws"), port=9000, no_open=True,
                                      refresh=False, terminal=False,
                                      allowed_hosts=["a.local", "b:1"])

    def test_ui_defaults(self) -> None:
        with mock.patch.object(cli, "start_ui", return_value=0) as start:
            cli.main(["ui"])
        start.assert_called_once_with(target_dir=Path("."), port=None, no_open=False,
                                      refresh=True, terminal=True, allowed_hosts=[])

    def test_ui_help_lists_the_new_options(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            cli.main(["ui", "--help"])
        for flag in ("--no-refresh", "--no-terminal", "--allowed-host", "--port", "--no-open"):
            self.assertIn(flag, out.getvalue())


if __name__ == "__main__":
    unittest.main()
