"""Pestaña «Anexo 2» (odd/tasks/sgr-anexo2.md, S1 y S4).

El script del kit `anexo2_sgr.py` se sustituye por un doble escrito en una
carpeta temporal y se carga por la misma importación dinámica que usa el
tablero para `requisitos_sgr.py`. La vista es de solo lectura: ni la carga ni
la ruta escriben en la corrida.
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
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from morfeo.core import value_chain
from morfeo.core.annex2 import ANNEX2_SCHEMA, load_annex2

# Doble del script del kit con el contrato de la feature: `vista(run)` devuelve
# la vista `morfeo.anexo2-sgr/v1` y anota la corrida que recibió.
ANNEX2_STUB = '''
import json
from pathlib import Path

VIEW = {
    "schema": "morfeo.anexo2-sgr/v1", "flujo": "sgr",
    "fuente_capitulos": "scripts/sgr/lexico_sgr.json", "fuente_reglas": "docs/sgr/patrones_redaccion_sgr.md",
    "rubrica": None,
    "resumen": {"capitulos": 1, "por_estado": {"falta": 0, "incompleto": 1, "desactualizado": 0, "listo": 0},
                "palabras": 120},
    "capitulos": [{
        "numero": 3, "titulo": "Planteamiento del problema", "estado": "incompleto", "palabras": 120,
        "secciones": [{"stem": "03_descripcion_problema", "existe": True, "palabras": 120, "origen": "manual",
                       "script": None, "estado": "redactado", "hallazgos": {"error": 0, "warning": 1, "info": 0},
                       "guia": "\\u00a73"}],
        "regla": None, "lexico": {"favorecida": 2, "desaconsejada": 1, "prohibida": 0}, "criterios": [],
        "hallazgos": [],
    }],
}


def vista(run):
    run = Path(run)
    if (run / "fallar").exists():
        raise RuntimeError("no se pudo leer estructura_tdr.json")
    if (run / "salir").exists():
        raise SystemExit(2)
    return json.loads(json.dumps(VIEW))
'''


def make_workspace(tmp: Path, flujo: str | None = "sgr") -> tuple[Path, Path]:
    workspace = Path(tmp)
    if flujo:
        (workspace / ".morfeo").mkdir()
        (workspace / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = workspace / "proposals" / "run-anexo2"
    (run / "artefactos").mkdir(parents=True)
    (workspace / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
    return workspace, run


def snapshot(run: Path) -> list[str]:
    return sorted(p.relative_to(run).as_posix() for p in run.rglob("*"))


class StubScripts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        scripts = self.tmp / "kit-scripts"
        scripts.mkdir()
        (scripts / "anexo2_sgr.py").write_text(ANNEX2_STUB, encoding="utf-8")
        self.scripts = scripts
        patcher = mock.patch.object(value_chain, "_script_candidates", lambda name: [scripts / name])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ws = self.new_dir("ws")

    def new_dir(self, name: str) -> Path:
        path = self.tmp / name
        path.mkdir()
        return path


class TestLoadAnnex2(StubScripts):
    def test_sgr_returns_the_script_view_without_writing(self):
        _, run = make_workspace(self.ws)
        before = snapshot(run)
        data = load_annex2(run)
        self.assertEqual(data["flujo"], "sgr")
        self.assertTrue(data["disponible"])
        self.assertIsNone(data["error"])
        self.assertEqual(data["vista"]["schema"], ANNEX2_SCHEMA)
        self.assertEqual(data["vista"]["capitulos"][0]["secciones"][0]["guia"], "§3")
        self.assertEqual(snapshot(run), before)

    def test_base_flow_returns_the_sgr_only_error_and_never_calls_the_script(self):
        _, run = make_workspace(self.ws, flujo=None)
        (run / "fallar").write_text("", encoding="utf-8")
        data = load_annex2(run)
        self.assertEqual((data["flujo"], data["disponible"], data["vista"]), ("base", False, None))
        self.assertIn("solo existe en el flujo SGR", data["error"])

    def test_failing_script_becomes_an_error_payload(self):
        _, run = make_workspace(self.ws)
        (run / "fallar").write_text("", encoding="utf-8")
        data = load_annex2(run)
        self.assertEqual((data["flujo"], data["disponible"], data["vista"]), ("sgr", False, None))
        self.assertIn("anexo2_sgr.py", data["error"])
        self.assertIn("estructura_tdr.json", data["error"])

    def test_script_exit_becomes_an_error_payload(self):
        _, run = make_workspace(self.ws)
        (run / "salir").write_text("", encoding="utf-8")
        data = load_annex2(run)
        self.assertFalse(data["disponible"])
        self.assertIn("anexo2_sgr.py", data["error"])

    def test_missing_script_is_reported(self):
        _, run = make_workspace(self.ws)
        (self.scripts / "anexo2_sgr.py").unlink()
        data = load_annex2(run)
        self.assertEqual((data["disponible"], data["vista"]), (False, None))
        self.assertIn("anexo2_sgr.py", data["error"])

    def test_foreign_view_is_rejected(self):
        _, run = make_workspace(self.ws)
        (self.scripts / "anexo2_sgr.py").write_text("def vista(run):\n    return {'schema': 'otro/v1'}\n",
                                                   encoding="utf-8")
        data = load_annex2(run)
        self.assertFalse(data["disponible"])
        self.assertIn(ANNEX2_SCHEMA, data["error"])


class TestAnnex2HttpApi(StubScripts):
    def _serve(self, workspace: Path):
        from morfeo.dashboard.server import MorfeoDashboardHandler

        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": workspace})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    @staticmethod
    def _request(url: str, payload=None) -> tuple[int, dict]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                     method="POST" if data is not None else "GET")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            body = err.read()
            try:
                return err.code, json.loads(body)
            except ValueError:
                return err.code, {}

    def test_get_returns_the_view_on_sgr_runs(self):
        workspace, run = make_workspace(self.ws)
        before = snapshot(run)
        base = self._serve(workspace)
        code, data = self._request(base + "/api/anexo2")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["run"], run.name)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["vista"]["resumen"]["capitulos"], 1)
        self.assertEqual(snapshot(run), before)

    def test_script_failure_answers_200_with_the_error(self):
        workspace, run = make_workspace(self.ws)
        (run / "fallar").write_text("", encoding="utf-8")
        code, data = self._request(self._serve(workspace) + "/api/anexo2")
        self.assertEqual(code, 200)
        self.assertFalse(data["disponible"])
        self.assertIn("anexo2_sgr.py", data["error"])

    def test_base_flow_answers_409(self):
        workspace, _ = make_workspace(self.ws, flujo=None)
        code, data = self._request(self._serve(workspace) + "/api/anexo2")
        self.assertEqual(code, 409)
        self.assertFalse(data["ok"])
        self.assertEqual(data["flujo"], "base")
        self.assertIn("solo existe en el flujo SGR", data["error"])

    def test_no_active_run_answers_404(self):
        workspace = self.new_dir("vacio")
        code, data = self._request(self._serve(workspace) + "/api/anexo2")
        self.assertEqual(code, 404)
        self.assertFalse(data["ok"])

    def test_post_is_not_a_route(self):
        workspace, _ = make_workspace(self.ws)
        code, _ = self._request(self._serve(workspace) + "/api/anexo2", {"x": 1})
        self.assertEqual(code, 404)

    def test_requirements_route_keeps_its_behaviour(self):
        workspace, run = make_workspace(self.ws, flujo=None)
        base = self._serve(workspace)
        code, data = self._request(base + "/api/requirements")
        self.assertEqual(code, 200)
        self.assertEqual((data["flujo"], data["disponible"], data["vista"]), ("base", False, None))
        workspace2, run2 = make_workspace(self.new_dir("ws2"))
        code, data = self._request(self._serve(workspace2) + "/api/requirements")
        self.assertEqual(code, 200)
        self.assertEqual((data["flujo"], data["run"]), ("sgr", run2.name))


if __name__ == "__main__":
    unittest.main()
