"""Pestaña «Convocatorias» (odd/tasks/convocatorias-explorador.md, S6).

El script del kit `convocatorias.py` se sustituye por un doble escrito en una
carpeta temporal y se carga por la misma importación dinámica que usa el
tablero para los demás scripts. La vista es de nivel de espacio de trabajo:
funciona sin corrida activa, es de solo lectura y los botones solo devuelven
el prompt que el tablero entrega a la terminal.
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
from morfeo.core.opportunities import (
    OPPORTUNITIES_SCHEMA,
    SEARCH_COMMAND,
    build_search_prompt,
    build_start_prompt,
    load_opportunities,
)

# Doble del script con el contrato `morfeo.convocatorias-vista/v1`: `vista(dir)`
# devuelve la vista y anota la carpeta y los argumentos de palabra que recibió
# (`alcance` solo llega cuando la petición lo trae).
OPPORTUNITIES_STUB = '''
from pathlib import Path


def vista(workspace, **kwargs):
    workspace = Path(workspace)
    if (workspace / "fallar").exists():
        raise RuntimeError("oportunidades.json ilegible")
    if (workspace / "salir").exists():
        raise SystemExit(2)
    return {
        "schema": "morfeo.convocatorias-vista/v1", "hoy": "2026-11-20", "workspace": str(workspace),
        "kwargs": sorted(kwargs), "alcance": kwargs.get("alcance", "proyecto"),
        "perfil": {"existe": True, "aplicantes": ["investigador"], "idiomas": ["es", "en"],
                   "ambitos": ["colombia"], "n_palabras_clave": 3},
        "resumen": {"total": 1, "vigentes": 1, "por_ambito": {"colombia": 1, "latam": 0, "internacional": 0},
                    "por_rol": {"lider": 1, "socio": 0, "coaplicante": 0, "anfitrion_exterior": 0,
                                "no_elegible": 0, "desconocido": 0}, "por_idioma": {"es": 1}},
        "fuentes_consultadas": [],
        "oportunidades": [{"id": "minciencias-ia-2026", "titulo": "Convocatoria IA", "rol_colombia": "lider",
                           "dias_restantes": 10, "vigente": True, "puntaje": 70}],
        "hallazgos": [],
    }
'''


def snapshot(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


class StubScripts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        scripts = self.tmp / "kit-scripts"
        scripts.mkdir()
        (scripts / "convocatorias.py").write_text(OPPORTUNITIES_STUB, encoding="utf-8")
        self.scripts = scripts
        patcher = mock.patch.object(value_chain, "_script_candidates", lambda name: [scripts / name])
        patcher.start()
        self.addCleanup(patcher.stop)
        # Espacio de trabajo sin corrida activa: la pestaña no depende de proposals/.
        self.ws = self.tmp / "ws"
        (self.ws / ".morfeo").mkdir(parents=True)
        (self.ws / ".morfeo" / "config.json").write_text(json.dumps({"titulo": "Demo"}), encoding="utf-8")


class TestLoadOpportunities(StubScripts):
    def test_returns_the_script_view_for_the_workspace_without_writing(self):
        before = snapshot(self.ws)
        data = load_opportunities(self.ws)
        self.assertTrue(data["disponible"])
        self.assertIsNone(data["error"])
        self.assertEqual(data["vista"]["schema"], OPPORTUNITIES_SCHEMA)
        self.assertEqual(data["vista"]["workspace"], str(self.ws))
        self.assertEqual(data["vista"]["oportunidades"][0]["id"], "minciencias-ia-2026")
        self.assertEqual(snapshot(self.ws), before)

    def test_missing_script_is_reported(self):
        (self.scripts / "convocatorias.py").unlink()
        data = load_opportunities(self.ws)
        self.assertEqual((data["disponible"], data["vista"]), (False, None))
        self.assertIn("convocatorias.py", data["error"])

    def test_failing_script_becomes_an_error_payload(self):
        (self.ws / "fallar").write_text("", encoding="utf-8")
        data = load_opportunities(self.ws)
        self.assertEqual((data["disponible"], data["vista"]), (False, None))
        self.assertIn("convocatorias.py", data["error"])
        self.assertIn("oportunidades.json ilegible", data["error"])

    def test_script_exit_becomes_an_error_payload(self):
        (self.ws / "salir").write_text("", encoding="utf-8")
        data = load_opportunities(self.ws)
        self.assertFalse(data["disponible"])
        self.assertIn("convocatorias.py", data["error"])

    def test_alcance_is_passed_to_the_script_only_when_given(self):
        data = load_opportunities(self.ws)
        self.assertEqual(data["vista"]["kwargs"], [])
        for alcance in ("proyecto", "banco"):
            data = load_opportunities(self.ws, alcance=alcance)
            self.assertEqual(data["vista"]["kwargs"], ["alcance"])
            self.assertEqual(data["vista"]["alcance"], alcance)

    def test_a_script_without_alcance_still_answers_without_it(self):
        (self.scripts / "convocatorias.py").write_text(
            "def vista(ws):\n    return {'schema': 'morfeo.convocatorias-vista/v1', 'oportunidades': []}\n",
            encoding="utf-8")
        self.assertTrue(load_opportunities(self.ws)["disponible"])

    def test_invalid_alcance_is_rejected(self):
        for bad in ("", "todo", "Banco", "banco ", 3):
            with self.assertRaises(ValueError, msg=repr(bad)):
                load_opportunities(self.ws, alcance=bad)

    def test_foreign_view_is_rejected(self):
        (self.scripts / "convocatorias.py").write_text("def vista(ws):\n    return {'schema': 'otro/v1'}\n",
                                                       encoding="utf-8")
        data = load_opportunities(self.ws)
        self.assertEqual((data["disponible"], data["vista"]), (False, None))
        self.assertIn(OPPORTUNITIES_SCHEMA, data["error"])


class TestStartPrompt(unittest.TestCase):
    def test_valid_slug_builds_the_command(self):
        self.assertEqual(build_start_prompt("horizon-cl4-2026"), f"{SEARCH_COMMAND} iniciar horizon-cl4-2026")

    def test_invalid_ids_are_rejected(self):
        for bad in ("", "  ", "Horizon", "a b", "x;rm -rf", "a/b", "ñandú", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                build_start_prompt(bad)


class TestSearchPrompt(unittest.TestCase):
    def test_without_alcance_keeps_the_plain_command(self):
        self.assertEqual(build_search_prompt(None), SEARCH_COMMAND)

    def test_alcance_builds_the_buscar_command(self):
        self.assertEqual(build_search_prompt("proyecto"), f"{SEARCH_COMMAND} buscar --alcance proyecto")
        self.assertEqual(build_search_prompt("banco"), f"{SEARCH_COMMAND} buscar --alcance banco")

    def test_invalid_alcance_is_rejected(self):
        for bad in ("", "todo", "banco; rm -rf", "x\n/clear", 1, ["banco"]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                build_search_prompt(bad)


class TestOpportunitiesHttpApi(StubScripts):
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

    def test_get_without_an_active_run_returns_the_view(self):
        before = snapshot(self.ws)
        code, data = self._request(self._serve(self.ws) + "/api/convocatorias")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertTrue(data["disponible"])
        self.assertIsNone(data["error"])
        self.assertEqual(data["vista"]["schema"], OPPORTUNITIES_SCHEMA)
        self.assertEqual(data["vista"]["workspace"], str(self.ws))
        self.assertEqual(snapshot(self.ws), before)

    def test_a_progress_file_does_not_change_the_view_payload(self):
        base = self._serve(self.ws)
        _, before = self._request(base + "/api/convocatorias")
        (self.ws / "convocatorias").mkdir()
        (self.ws / "convocatorias" / "progreso.json").write_text(
            json.dumps({"schema": "morfeo.convocatorias-progreso/v1", "started_at": "2026-11-22T10:00:00+00:00",
                        "phases": [], "historial": []}), encoding="utf-8")
        code, after = self._request(base + "/api/convocatorias")
        self.assertEqual(code, 200)
        self.assertEqual(sorted(after), ["disponible", "error", "ok", "vista"])
        self.assertEqual(after, before)

    def test_get_with_an_active_run_still_reads_the_workspace(self):
        run = self.ws / "proposals" / "run-x"
        run.mkdir(parents=True)
        (self.ws / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
        code, data = self._request(self._serve(self.ws) + "/api/convocatorias")
        self.assertEqual(code, 200)
        self.assertEqual(data["vista"]["workspace"], str(self.ws))

    def test_missing_script_answers_200_with_the_error(self):
        (self.scripts / "convocatorias.py").unlink()
        code, data = self._request(self._serve(self.ws) + "/api/convocatorias")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertFalse(data["disponible"])
        self.assertIsNone(data["vista"])
        self.assertIn("convocatorias.py", data["error"])

    def test_post_buscar_returns_the_search_command(self):
        before = snapshot(self.ws)
        code, data = self._request(self._serve(self.ws) + "/api/convocatorias/buscar", {})
        self.assertEqual(code, 200)
        self.assertEqual(data, {"ok": True, "prompt": "/propuesta-convocatorias"})
        self.assertEqual(snapshot(self.ws), before)

    def test_get_passes_the_alcance_query_to_the_script(self):
        base = self._serve(self.ws)
        code, data = self._request(base + "/api/convocatorias")
        self.assertEqual((code, data["vista"]["kwargs"]), (200, []))
        for alcance in ("proyecto", "banco"):
            code, data = self._request(base + f"/api/convocatorias?alcance={alcance}")
            self.assertEqual(code, 200)
            self.assertEqual(data["vista"]["kwargs"], ["alcance"])
            self.assertEqual(data["vista"]["alcance"], alcance)

    def test_get_rejects_an_invalid_alcance_with_400_json(self):
        base = self._serve(self.ws)
        for query in ("alcance=todo", "alcance=", "alcance=BANCO", "alcance=banco&alcance=proyecto"):
            code, data = self._request(base + f"/api/convocatorias?{query}")
            self.assertEqual(code, 400, query)
            self.assertFalse(data["ok"])
            self.assertIn("alcance", data["error"])
            self.assertNotIn("vista", data)

    def test_post_buscar_with_alcance_returns_the_buscar_command(self):
        base = self._serve(self.ws)
        before = snapshot(self.ws)
        for alcance in ("proyecto", "banco"):
            code, data = self._request(base + "/api/convocatorias/buscar", {"alcance": alcance})
            self.assertEqual(code, 200)
            self.assertEqual(data, {"ok": True, "prompt": f"/propuesta-convocatorias buscar --alcance {alcance}"})
        code, data = self._request(base + "/api/convocatorias/buscar", {"alcance": None})
        self.assertEqual(data, {"ok": True, "prompt": "/propuesta-convocatorias"})
        self.assertEqual(snapshot(self.ws), before)

    def test_post_buscar_rejects_an_invalid_alcance(self):
        base = self._serve(self.ws)
        for payload in ({"alcance": "todo"}, {"alcance": ""}, {"alcance": "banco\n/clear"}, {"alcance": 2}):
            code, data = self._request(base + "/api/convocatorias/buscar", payload)
            self.assertEqual(code, 400, payload)
            self.assertFalse(data["ok"])
            self.assertNotIn("prompt", data)
        req = urllib.request.Request(base + "/api/convocatorias/buscar", data=b"{no",
                                     headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_the_map_script_is_served_without_cache(self):
        with urllib.request.urlopen(self._serve(self.ws) + "/static/convocatorias-map.js") as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers["Cache-Control"], "no-cache")
            self.assertIn("javascript", resp.headers["Content-Type"])

    def test_post_iniciar_with_a_valid_id_returns_the_start_command(self):
        before = snapshot(self.ws)
        code, data = self._request(self._serve(self.ws) + "/api/convocatorias/iniciar", {"id": "erasmus-cbhe-2027"})
        self.assertEqual(code, 200)
        self.assertEqual(data, {"ok": True, "prompt": "/propuesta-convocatorias iniciar erasmus-cbhe-2027"})
        self.assertEqual(snapshot(self.ws), before)

    def test_post_iniciar_rejects_empty_and_non_slug_ids(self):
        base = self._serve(self.ws)
        for payload in ({}, {"id": ""}, {"id": "Erasmus CBHE"}, {"id": "x\n/clear"}, {"id": 12}):
            code, data = self._request(base + "/api/convocatorias/iniciar", payload)
            self.assertEqual(code, 400, payload)
            self.assertFalse(data["ok"])
            self.assertNotIn("prompt", data)

    def test_post_iniciar_rejects_an_invalid_json_body(self):
        req = urllib.request.Request(self._serve(self.ws) + "/api/convocatorias/iniciar", data=b"{no",
                                     headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_get_on_the_post_routes_is_not_found(self):
        base = self._serve(self.ws)
        for route in ("/api/convocatorias/buscar", "/api/convocatorias/iniciar"):
            code, _ = self._request(base + route)
            self.assertEqual(code, 404, route)

    def test_annex2_route_keeps_answering_404_without_a_run(self):
        code, data = self._request(self._serve(self.ws) + "/api/anexo2")
        self.assertEqual(code, 404)
        self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()
