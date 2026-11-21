"""«⟳ Actualizar tablero» and the status report (odd/tasks/ui-smith-responsive.md, S3, T3).

Port of papersmith-ai's board refresh: `refresh_artifacts` runs only local,
keyless generators, each isolated; `summarize` says where the project stands
from the `/api/status` payload; the server exposes `POST /api/board/refresh`
(same origin, one at a time) and `GET /api/board/summary`, refreshes once when
it starts, serves the page with `Cache-Control: no-cache` and reports a server
older than the package installed on disk.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from morfeo.core import board, status as status_module
from morfeo.core.status import get_project_status
from morfeo.dashboard import server as server_module
from morfeo.dashboard.server import MorfeoDashboardHandler, run_server


def unit(uid: str, name: str, gate: str | None = None, kind: str = "step") -> dict:
    return {"id": uid, "name": name, "gate": gate, "kind": kind}


def progress(state: str, missing: list[str] | None = None) -> dict:
    missing = missing or []
    checks = [{"id": "file", "label": label, "ok": False} for label in missing]
    return {"state": state, "missing": missing, "checks": checks}


def payload(**overrides) -> dict:
    """A `/api/status` payload with three units: the first passed, the second
    half done, the third pending."""
    data = {
        "active_run": "2026-01-demo",
        "control": {"next_step": "fase1a", "next_command": "/propuesta-continuar"},
        "gates": [
            {"id": "G0.5", "name": "Ajuste de Guía al TDR", "phase": "Fase 0", "status": "PASS"},
            {"id": "G1a", "name": "Scoping Temprano", "phase": "Fase 1a", "status": "PENDING"},
        ],
        "pipeline_units": [
            unit("fase0", "Intake", "G0.5", kind="pre"),
            unit("fase1a", "Scoping temprano", "G1a"),
            unit("fase1b", "Árboles", "G1b"),
        ],
        "unit_progress": {
            "fase0": progress("verified"),
            "fase1a": progress("partial", ["Compuerta G1a en PASS", "artefactos/scoping/papers/* existe"]),
            "fase1b": progress("pending", ["Compuerta G1b en PASS"]),
        },
    }
    data.update(overrides)
    return data


def write_run(workspace: Path, *, gate_g1a: str = "PENDING") -> Path:
    """A workspace with an active run, its control block and gate table."""
    (workspace / ".morfeo").mkdir(parents=True, exist_ok=True)
    run = workspace / "proposals" / "2026-01-demo"
    (run / "artefactos").mkdir(parents=True)
    (workspace / "proposals" / ".current-run").write_text("2026-01-demo\n", encoding="utf-8")
    # The intake's artefact: without it fase0 would be the current unit.
    (run / "artefactos" / "insumos.md").write_text("# Insumos\n", encoding="utf-8")
    (run / "artefactos" / "estado_propuesta.md").write_text(
        "# Estado\n\n| Gate | Estado |\n|---|---|\n"
        f"| G0.5 | PASS |\n| G1a | {gate_g1a} |\n\n"
        "## Control de ejecución\n\n"
        "- mode: stepped\n- next_step: fase1a\n"
        "- next_command: /propuesta-continuar\n"
        "- last_completed: fase0\n- intake_complete: true\n",
        encoding="utf-8",
    )
    return run


class SummarizeTests(unittest.TestCase):
    def test_the_current_unit_is_the_first_not_passed_with_its_missing_checks(self):
        summary = board.summarize(payload())
        self.assertEqual(summary["current"]["id"], "fase1a")
        self.assertEqual(summary["current"]["name"], "Scoping temprano")
        self.assertEqual(
            summary["missing"],
            ["Compuerta G1a en PASS", "artefactos/scoping/papers/* existe"],
        )
        self.assertEqual(summary["next_command"], "/propuesta-continuar")
        self.assertEqual(summary["units_completed"], 1)
        self.assertEqual(summary["units_total"], 3)
        self.assertEqual(summary["gates_passed"], 1)
        self.assertEqual(summary["gates_total"], 2)
        self.assertEqual([g["id"] for g in summary["open_gates"]], ["G1a"])
        self.assertEqual(summary["failed_gates"], [])
        self.assertEqual(summary["tone"], "info")

    def test_a_skipped_unit_counts_as_passed(self):
        data = payload()
        data["unit_progress"]["fase1a"] = progress("skipped")
        summary = board.summarize(data)
        self.assertEqual(summary["current"]["id"], "fase1b")
        self.assertEqual(summary["units_completed"], 2)

    def test_a_failed_gate_gives_an_alert(self):
        data = payload()
        data["gates"][1]["status"] = "FAIL"
        summary = board.summarize(data, [{"id": "grafos", "label": "Grafos", "state": "failed", "detail": "x"}])
        self.assertEqual(summary["tone"], "alert")
        self.assertEqual([g["id"] for g in summary["failed_gates"]], ["G1a"])
        self.assertEqual(summary["open_gates"], [])

    def test_a_failed_artifact_gives_a_warning(self):
        artifacts = [
            {"id": "grafos", "label": "Grafos de la corrida", "state": "failed", "detail": "RuntimeError: boom"},
            {"id": "estado", "label": "Estado del proyecto", "state": "ok", "detail": ""},
        ]
        summary = board.summarize(payload(), artifacts)
        self.assertEqual(summary["tone"], "warn")
        self.assertEqual(
            summary["failed_artifacts"],
            [{"id": "grafos", "label": "Grafos de la corrida", "detail": "RuntimeError: boom"}],
        )

    def test_every_unit_passed_is_done(self):
        data = payload(control={"next_step": "done", "next_command": ""})
        for uid in data["unit_progress"]:
            data["unit_progress"][uid] = progress("verified")
        data["gates"][1]["status"] = "PASS"
        summary = board.summarize(data)
        self.assertIsNone(summary["current"])
        self.assertEqual(summary["missing"], [])
        self.assertEqual(summary["tone"], "done")
        self.assertIsNone(summary["next_command"])

    def test_without_an_active_run_it_points_to_propuesta_init(self):
        summary = board.summarize({"active_run": None, "gates": [], "pipeline_units": [unit("fase0", "Intake")],
                                   "unit_progress": {}, "control": None})
        self.assertIsNone(summary["current"])
        self.assertEqual(summary["tone"], "info")
        self.assertEqual(summary["next_command"], "/propuesta-init")

    def test_the_summary_carries_the_last_refresh(self):
        last = {"started_at": "2026-11-20T10:00:00Z", "finished_at": "2026-11-20T10:00:01Z", "artifacts": []}
        summary = board.summarize(payload(), last_refresh=last)
        self.assertEqual(summary["last_refresh"], {"started_at": "2026-11-20T10:00:00Z",
                                                    "finished_at": "2026-11-20T10:00:01Z"})
        self.assertIsNone(board.summarize(payload())["last_refresh"])


class RefreshArtifactsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)
        (self.ws / ".morfeo").mkdir()

    def test_an_empty_workspace_skips_what_has_no_input(self):
        results = board.refresh_artifacts(self.ws)
        by_id = {item["id"]: item for item in results}
        self.assertEqual(set(by_id), {"grafos", "estado"})
        self.assertEqual(by_id["grafos"]["state"], "skipped")
        self.assertIn("corrida activa", by_id["grafos"]["detail"])
        self.assertEqual(by_id["estado"]["state"], "ok")
        for item in results:
            self.assertEqual(set(item), {"id", "label", "state", "detail"})

    def test_a_generator_that_raises_is_reported_and_the_rest_still_run(self):
        calls = []

        def boom(_ws):
            calls.append("boom")
            raise RuntimeError("generador roto")

        def fine(_ws):
            calls.append("fine")
            return "ok", "listo"

        steps = (("roto", "Roto", boom), ("sano", "Sano", fine))
        with mock.patch.object(board, "GENERATORS", steps):
            results = board.refresh_artifacts(self.ws)
        self.assertEqual(calls, ["boom", "fine"])
        self.assertEqual(results[0], {"id": "roto", "label": "Roto", "state": "failed",
                                      "detail": "RuntimeError: generador roto"})
        self.assertEqual(results[1], {"id": "sano", "label": "Sano", "state": "ok", "detail": "listo"})

    def test_the_graphs_run_with_an_active_run(self):
        write_run(self.ws)
        built = []
        fake = mock.Mock()
        fake.build_all_graphs = lambda run_dir: built.append(run_dir) or {"papers": {"nodes": [1, 2], "edges": []}}
        with mock.patch.object(board, "_graph_builder", lambda ws: fake):
            results = board.refresh_artifacts(self.ws)
        graphs = next(item for item in results if item["id"] == "grafos")
        self.assertEqual(graphs["state"], "ok")
        self.assertIn("papers: 2 nodos", graphs["detail"])
        self.assertEqual(built, [self.ws.resolve() / "proposals" / "2026-01-demo"])


class BoardServerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)
        write_run(self.ws)
        # Graphs are the slow generator; their own test covers them.
        patcher = mock.patch.object(board, "_graph_builder", lambda ws: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": self.ws})
        handler.log_message = lambda *a, **k: None
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(board.forget, self.ws)

    def request(self, path: str, method: str = "GET", headers: dict | None = None):
        # The dashboard's own page sends its Origin on every POST.
        if method == "POST":
            headers = {"Origin": f"http://127.0.0.1:{self.port}", **(headers or {})}
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                     headers=headers or {}, data=b"" if method == "POST" else None)
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status, dict(res.headers), json.loads(res.read() or b"null") if path.startswith("/api/") else None
        except urllib.error.HTTPError as err:
            body = err.read()
            return err.code, dict(err.headers), json.loads(body) if body.startswith(b"{") else None

    def test_the_refresh_regenerates_and_reports_the_status(self):
        code, headers, data = self.request("/api/board/refresh", "POST",
                                           {"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual([a["id"] for a in data["artifacts"]], ["grafos", "estado"])
        self.assertEqual(data["summary"]["current"]["id"], "fase1a")
        self.assertEqual(data["summary"]["next_command"], "/propuesta-continuar")
        self.assertIn("no-store", headers.get("Cache-Control", ""))

    def test_localhost_counts_as_the_same_origin(self):
        code, _h, _d = self.request("/api/board/refresh", "POST", {"Origin": f"http://localhost:{self.port}"})
        self.assertEqual(code, 200)

    def test_a_cross_origin_refresh_is_refused(self):
        for origin in ("http://evil.example", f"http://evil.example:{self.port}", "null",
                       "http://127.0.0.1:1"):
            code, _h, data = self.request("/api/board/refresh", "POST", {"Origin": origin})
            self.assertEqual(code, 403, origin)
            self.assertFalse(data["ok"])
        self.assertIsNone(board.refresher_for(self.ws).last)

    def test_a_refresh_already_running_answers_busy(self):
        refresher = board.refresher_for(self.ws)
        self.assertTrue(refresher.lock.acquire(blocking=False))
        try:
            code, _h, data = self.request("/api/board/refresh", "POST")
        finally:
            refresher.lock.release()
        self.assertEqual(code, 409)
        self.assertTrue(data["busy"])

    def test_the_summary_reports_the_last_refresh(self):
        code, _h, data = self.request("/api/board/summary")
        self.assertEqual(code, 200)
        self.assertIsNone(data["last_refresh"])
        self.assertFalse(data["refreshing"])
        self.assertEqual(data["summary"]["current"]["id"], "fase1a")

        _c, _h, refreshed = self.request("/api/board/refresh", "POST")
        _c, _h, data = self.request("/api/board/summary")
        self.assertEqual(data["last_refresh"]["finished_at"], refreshed["finished_at"])
        self.assertEqual(data["summary"]["last_refresh"]["finished_at"], refreshed["finished_at"])

    def test_the_page_is_served_no_cache(self):
        code, headers, _d = self.request("/")
        self.assertEqual(code, 200)
        self.assertEqual(headers.get("Cache-Control"), "no-cache")
        _c, headers, _d = self.request("/static/board-refresh.js")
        self.assertEqual(headers.get("Cache-Control"), "no-cache")

    def test_the_existing_status_route_still_answers(self):
        code, _h, data = self.request("/api/status")
        self.assertEqual(code, 200)
        self.assertEqual(data["active_run"], "2026-01-demo")


class StartupRefreshTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)
        write_run(self.ws)
        self.addCleanup(board.forget, self.ws)
        self.addCleanup(status_module.reset_server_start)
        patcher = mock.patch.object(board, "_graph_builder", lambda ws: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def start(self, **kwargs) -> None:
        # serve_forever returns at once, as on Ctrl+C.
        with mock.patch.object(server_module.ThreadingHTTPServer, "serve_forever",
                               side_effect=KeyboardInterrupt), contextlib.redirect_stdout(io.StringIO()):
            run_server(self.ws, port=0, **kwargs)

    def test_the_server_refreshes_the_board_when_it_starts(self):
        self.start()
        refresher = board.refresher_for(self.ws)
        deadline = time.time() + 10
        while refresher.last is None and time.time() < deadline:
            time.sleep(0.05)
        self.assertIsNotNone(refresher.last)
        self.assertEqual([a["id"] for a in refresher.last["artifacts"]], ["grafos", "estado"])

    def test_refresh_false_skips_the_startup_refresh(self):
        self.start(refresh=False)
        time.sleep(0.3)
        self.assertIsNone(board.refresher_for(self.ws).last)
        self.assertFalse(any(t.name == "board-refresh" for t in threading.enumerate()))


class StaleServerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)
        (self.ws / ".morfeo").mkdir()
        self.addCleanup(status_module.reset_server_start)

    def test_a_server_matching_the_installed_package_is_not_stale(self):
        status_module.record_server_start()
        data = get_project_status(self.ws, force_refresh=True)
        self.assertIs(data["stale_server"], False)
        self.assertEqual(data["server_version"], data["installed_version"])

    def test_an_upgrade_on_disk_marks_the_server_stale(self):
        status_module.record_server_start()
        with mock.patch.object(status_module, "installed_package_version", return_value="99.0.0"):
            data = get_project_status(self.ws, force_refresh=True)
        self.assertIs(data["stale_server"], True)
        self.assertEqual(data["installed_version"], "99.0.0")
        self.assertEqual(data["server_version"], status_module.installed_package_version())

    def test_without_a_recorded_start_nothing_is_stale(self):
        data = get_project_status(self.ws, force_refresh=True)
        self.assertIs(data["stale_server"], False)

    def test_the_installed_version_is_read_from_disk(self):
        import morfeo

        self.assertEqual(status_module.installed_package_version(), morfeo.__version__)


if __name__ == "__main__":
    unittest.main()
