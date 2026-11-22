"""Stage judge of the dashboard: core loader and HTTP routes (odd/tasks/tablero-juez-novedad.md, S2).

GET /api/judge-avance?etapa=<arbol|novedad> returns the recorded round of
artefactos/juez/avance_<etapa>.json; POST /api/judge-avance/run returns the
slash command the dashboard types into the terminal. The SGR judge routes keep
answering as before.
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

from morfeo.core.judge_avance import (  # noqa: E402
    AVANCE_SCHEMA,
    JUDGE_AVANCE_COMMAND,
    build_run_command,
    load_judge_avance,
)

ROUND = {
    "schema": "morfeo.juez-avance/v1",
    "etapa": "arbol",
    "ronda": 2,
    "fecha": "2026-11-22",
    "puntaje": 74,
    "veredicto": "Árbol coherente; falta la fuente de la magnitud.",
    "resumen_idea": "Monitoreo hídrico con IA para Caldas, con sensores comunitarios.",
    "fortalezas": [{"texto": "Problema central medible.", "evidencia": "tronco del árbol"}],
    "debilidades": [{"texto": "Magnitud sin fuente.", "evidencia": "mga_resumido.md", "accion": "Citar el IDEAM."}],
    "alertas": [{"nivel": "media", "texto": "SP2 se parece a SP1.", "donde": "árbol, SP2"}],
    "historial": [{"ronda": 1, "fecha": "2026-11-21", "puntaje": 60, "veredicto": "Inicial.",
                   "resumen_idea": "Monitoreo hídrico con IA para Caldas.", "fortalezas": [], "debilidades": [],
                   "alertas": []}],
}


def make_workspace(tmp: Path) -> tuple[Path, Path]:
    run = tmp / "proposals" / "run-avance"
    (run / "artefactos").mkdir(parents=True)
    (tmp / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
    return tmp, run


def write_round(run: Path, data, etapa: str = "arbol") -> None:
    folder = run / "artefactos" / "juez"
    folder.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    (folder / f"avance_{etapa}.json").write_text(text, encoding="utf-8")


class TestLoadJudgeAvance(unittest.TestCase):
    def test_without_file_it_is_not_available_and_has_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            data = load_judge_avance(run, "arbol")
            self.assertEqual(data, {"etapa": "arbol", "disponible": False, "evaluacion": None,
                                    "archivo": "artefactos/juez/avance_arbol.json", "errores": []})

    def test_a_recorded_round_is_returned_whole(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            write_round(run, ROUND)
            data = load_judge_avance(run, "arbol")
            self.assertTrue(data["disponible"])
            self.assertEqual(data["evaluacion"], ROUND)
            self.assertEqual(data["errores"], [])

    def test_corrupt_wrong_schema_or_wrong_stage_are_errors_not_exceptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            for content, needle in (("{roto", "JSON"), (json.dumps({**ROUND, "schema": "otro/v1"}), AVANCE_SCHEMA),
                                    (json.dumps({**ROUND, "etapa": "novedad"}), "novedad"), ("[1]", "objeto")):
                with self.subTest(needle=needle):
                    write_round(run, content)
                    data = load_judge_avance(run, "arbol")
                    self.assertFalse(data["disponible"])
                    self.assertIsNone(data["evaluacion"])
                    self.assertTrue(any(needle in e for e in data["errores"]), data["errores"])

    def test_unknown_stage_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            with self.assertRaises(ValueError):
                load_judge_avance(run, "final")
            with self.assertRaises(ValueError):
                build_run_command("../x")

    def test_the_command_names_the_stage(self):
        self.assertEqual(build_run_command("arbol"), "/propuesta-juez-avance arbol")
        self.assertEqual(build_run_command("novedad"), f"{JUDGE_AVANCE_COMMAND} novedad")


class TestJudgeAvanceHttpApi(unittest.TestCase):
    def _serve(self, workspace: Path):
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
            code, data = self._request(base + "/api/judge-avance?etapa=arbol")
            self.assertEqual(code, 200)
            self.assertEqual((data["ok"], data["run"], data["etapa"], data["disponible"]), (True, run.name, "arbol", False))
            self.assertIsNone(data["evaluacion"])
            write_round(run, ROUND)
            code, data = self._request(base + "/api/judge-avance?etapa=arbol")
            self.assertEqual(code, 200)
            self.assertTrue(data["disponible"])
            self.assertEqual(data["evaluacion"]["puntaje"], 74)
            self.assertEqual(data["evaluacion"]["historial"][0]["ronda"], 1)

    def test_get_defaults_to_the_tree_stage_and_rejects_unknown_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _ = make_workspace(Path(tmp))
            base = self._serve(workspace)
            code, data = self._request(base + "/api/judge-avance")
            self.assertEqual((code, data["etapa"]), (200, "arbol"))
            code, data = self._request(base + "/api/judge-avance?etapa=final")
            self.assertEqual(code, 400)
            self.assertFalse(data["ok"])

    def test_run_returns_the_slash_command_for_the_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _ = make_workspace(Path(tmp))
            base = self._serve(workspace)
            code, data = self._request(base + "/api/judge-avance/run", {"etapa": "arbol"})
            self.assertEqual((code, data), (200, {"ok": True, "etapa": "arbol", "prompt": "/propuesta-juez-avance arbol"}))
            code, data = self._request(base + "/api/judge-avance/run", {"etapa": "novedad"})
            self.assertEqual(data["prompt"], "/propuesta-juez-avance novedad")
            code, data = self._request(base + "/api/judge-avance/run", {"etapa": "final"})
            self.assertEqual(code, 400)
            code, data = self._request(base + "/api/judge-avance/run", raw=b"{roto")
            self.assertEqual(code, 400)

    def test_without_active_run_the_routes_answer_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "proposals").mkdir()
            base = self._serve(workspace)
            for path, payload in (("/api/judge-avance?etapa=arbol", None), ("/api/judge-avance/run", {"etapa": "arbol"})):
                code, data = self._request(base + path, payload)
                self.assertEqual(code, 404, path)
                self.assertFalse(data["ok"])

    def test_the_sgr_judge_routes_keep_answering(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, run = make_workspace(Path(tmp))
            base = self._serve(workspace)
            code, data = self._request(base + "/api/judge")
            self.assertEqual((code, data["ok"], data["flujo"], data["disponible"]), (200, True, "base", False))
            code, data = self._request(base + "/api/judge/run", {})
            self.assertEqual((code, data), (200, {"ok": True, "prompt": "/propuesta-juez"}))


if __name__ == "__main__":
    unittest.main()
