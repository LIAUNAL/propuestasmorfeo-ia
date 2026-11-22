"""Novelty panel of the dashboard: core loader and HTTP routes (odd/tasks/tablero-juez-novedad.md, T5: S4).

GET /api/novedad returns artefactos/novedad/novedad.json with the matrix that
scripts/novedad.py derives and its validation status (an empty state when the
file is absent); POST /api/novedad/run returns the slash command the dashboard
types into the terminal. The trees and stage judge routes keep answering.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from morfeo.core.novedad import NOVEDAD_COMMAND, build_run_command, load_novedad  # noqa: E402
from test_novedad import DRAFT, write_trees  # noqa: E402


def make_workspace(tmp: Path) -> tuple[Path, Path]:
    run = tmp / "proposals" / "run-novedad"
    (run / "artefactos").mkdir(parents=True)
    (tmp / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
    return tmp, run


def write_record(run: Path, data) -> None:
    folder = run / "artefactos" / "novedad"
    folder.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    (folder / "novedad.json").write_text(text, encoding="utf-8")


RECORD = {**DRAFT, "fecha": "2026-11-22"}


class TestLoadNovedad(unittest.TestCase):
    def test_without_file_it_is_an_empty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            data = load_novedad(run)
            self.assertEqual(data["disponible"], False)
            self.assertIsNone(data["novedad"])
            self.assertIsNone(data["matriz"])
            self.assertEqual(data["archivo"], "artefactos/novedad/novedad.json")
            self.assertEqual(data["errores"], [])
            self.assertIsNone(data["actualizado"])

    def test_a_recorded_file_comes_with_its_matrix_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            write_record(run, RECORD)
            data = load_novedad(run)
            self.assertTrue(data["disponible"])
            self.assertEqual(data["novedad"], RECORD)
            self.assertEqual(data["validacion"], {"ok": True, "errores": []})
            self.assertEqual([r["objetivo"]["id"] for r in data["matriz"]["filas"]], ["OE1", "OE2", "OE3"])
            self.assertEqual(data["matriz"]["totales"]["experimentos"], 4)
            self.assertIsInstance(data["actualizado"], str)

    def test_an_invalid_record_is_shown_with_its_errors_and_trees_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            write_trees(run, trunk="Otro problema central del árbol.")
            write_record(run, RECORD)
            data = load_novedad(run)
            self.assertTrue(data["disponible"])
            self.assertFalse(data["validacion"]["ok"])
            self.assertTrue(any("problema_central" in e for e in data["validacion"]["errores"]))
            self.assertEqual(data["matriz"]["fuente_efectos"], "arbol")

    def test_a_broken_file_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            write_record(run, "{roto")
            data = load_novedad(run)
            self.assertFalse(data["disponible"])
            self.assertTrue(data["errores"])

    def test_the_command(self):
        self.assertEqual(NOVEDAD_COMMAND, "/propuesta-novedad")
        self.assertEqual(build_run_command(), "/propuesta-novedad")


class TestNovedadRoutes(unittest.TestCase):
    def _serve(self, workspace: Path) -> str:
        from morfeo.dashboard.server import MorfeoDashboardHandler

        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": workspace})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    @staticmethod
    def _request(url: str, payload: dict | None = None, raw: bytes | None = None) -> tuple[int, dict]:
        data = raw if raw is not None else (json.dumps(payload).encode("utf-8") if payload is not None else None)
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                     method="POST" if data is not None else "GET")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_get_empty_then_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, run = make_workspace(Path(tmp))
            base = self._serve(workspace)
            code, data = self._request(base + "/api/novedad")
            self.assertEqual((code, data["ok"], data["run"], data["disponible"]), (200, True, run.name, False))
            self.assertIsNone(data["matriz"])
            write_record(run, RECORD)
            code, data = self._request(base + "/api/novedad")
            self.assertEqual(code, 200)
            self.assertTrue(data["disponible"])
            self.assertEqual(data["novedad"]["pilares"][0]["id"], "P1")
            self.assertEqual(data["matriz"]["filas"][2]["experimentos"][1]["tipo"], "intervencion")
            self.assertTrue(data["validacion"]["ok"])

    def test_run_returns_the_slash_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _ = make_workspace(Path(tmp))
            base = self._serve(workspace)
            code, data = self._request(base + "/api/novedad/run", {})
            self.assertEqual((code, data), (200, {"ok": True, "prompt": "/propuesta-novedad"}))
            code, data = self._request(base + "/api/novedad/run", raw=b"{roto")
            self.assertEqual(code, 400)

    def test_without_active_run_the_routes_answer_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "proposals").mkdir()
            base = self._serve(workspace)
            for path, payload in (("/api/novedad", None), ("/api/novedad/run", {})):
                code, data = self._request(base + path, payload)
                self.assertEqual(code, 404, path)
                self.assertFalse(data["ok"])

    def test_the_trees_and_stage_judge_routes_keep_answering(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, run = make_workspace(Path(tmp))
            write_trees(run)
            base = self._serve(workspace)
            code, data = self._request(base + "/api/trees")
            self.assertEqual(code, 200)
            self.assertTrue(data["problem"]["available"])
            code, data = self._request(base + "/api/judge-avance?etapa=novedad")
            self.assertEqual((code, data["etapa"], data["disponible"]), (200, "novedad", False))
            code, data = self._request(base + "/api/judge-avance/run", {"etapa": "novedad"})
            self.assertEqual(data["prompt"], "/propuesta-juez-avance novedad")

    def test_the_panel_script_is_served_without_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _ = make_workspace(Path(tmp))
            base = self._serve(workspace)
            with urllib.request.urlopen(base + "/static/novedad-panel.js") as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("Cache-Control"), "no-cache")
                self.assertIn(b"window.NovedadPanel", resp.read())


if __name__ == "__main__":
    unittest.main()
