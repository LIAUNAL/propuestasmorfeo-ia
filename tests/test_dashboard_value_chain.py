"""Pestaña «Cadena de valor» y columna «Estilo SGR» (odd/tasks/sgr-cadena-estilo.md, S1 y S7).

Los scripts del kit (`cadena_valor_sgr.py`, `estilo_sgr.py`) se sustituyen por
dobles escritos en una carpeta temporal y se cargan por la misma importación
dinámica que usa el tablero.
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
from morfeo.core.style_sgr import load_style
from morfeo.core.value_chain import approve, build_adjust_prompt, load_value_chain

CADENA = {
    "schema": "morfeo.cadena-valor-sgr/v1",
    "duracion_meses": 24,
    "arbol_hash": "abc",
    "objetivos": [
        {"id": "OE1", "texto": "Caracterizar la calidad del agua", "productos": [
            {"codigo": "1.1", "codigo_dnp": "3906001", "nombre": "Documentos de investigación",
             "medido_a_traves_de": "Número de documentos", "indicador": "Documentos elaborados",
             "unidad": "Número", "meta": 2, "actividades": [
                 {"codigo": "1.1.1", "nombre": "Muestreo de campo", "tipo": "tecnica", "ruta_critica": True,
                  "mes_inicio": 1, "mes_fin": 6, "costo": 1000, "medio": "m1"},
                 {"codigo": "1.1.2", "nombre": "Análisis de laboratorio", "tipo": "tecnica", "ruta_critica": False,
                  "mes_inicio": 2, "mes_fin": 8, "costo": 500.5, "medio": "m1"},
                 {"codigo": "1.1.3", "nombre": "Administración del objetivo", "tipo": "administracion",
                  "ruta_critica": False, "mes_inicio": 1, "mes_fin": 24, "costo": None, "medio": None},
             ]},
        ]},
    ],
}

CADENA_STUB = '''
import json
from pathlib import Path

def findings(run_root):
    path = Path(run_root) / "stub_findings.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
'''

ESTILO_STUB = '''
import json
from pathlib import Path

def findings(run_root, section=None):
    path = Path(run_root) / "stub_estilo.json"
    if (Path(run_root) / "stub_estilo_falla").exists():
        raise RuntimeError("léxico ilegible")
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
'''

ESTILO = [
    {"severity": "advertencia", "code": "sgr-estilo-primera-persona", "message": "Primera persona",
     "archivo": "redaccion/sections/02_justificacion.tex", "linea": 12, "extracto": "proponemos", "regla": "primera-persona"},
    {"severity": "info", "code": "sgr-estilo-falta-de", "message": "Evita «falta de»",
     "archivo": "redaccion/sections/02_justificacion.tex", "linea": 30, "extracto": "falta de", "regla": "falta-de"},
    {"severity": "advertencia", "code": "sgr-estilo-verbo-mga", "message": "Verbo vetado",
     "archivo": "redaccion/sections/10_metodologia.tex", "linea": 4, "extracto": "Realizar", "regla": "verbo-mga"},
]


def make_workspace(tmp: Path, flujo: str | None = "sgr") -> tuple[Path, Path]:
    workspace = Path(tmp)
    if flujo:
        (workspace / ".morfeo").mkdir()
        (workspace / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = workspace / "proposals" / "run-cadena"
    (run / "artefactos").mkdir(parents=True)
    (workspace / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
    return workspace, run


def write_cadena(run: Path, data: dict | str = CADENA) -> None:
    folder = run / "artefactos" / "sgr"
    folder.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    (folder / "cadena_valor.json").write_text(text, encoding="utf-8")


def write_findings(run: Path, findings: list[dict]) -> None:
    (run / "stub_findings.json").write_text(json.dumps(findings), encoding="utf-8")


class StubScripts(unittest.TestCase):
    """Cada prueba carga los dobles de los scripts desde su propia carpeta."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        scripts = self.tmp / "kit-scripts"
        scripts.mkdir()
        (scripts / "cadena_valor_sgr.py").write_text(CADENA_STUB, encoding="utf-8")
        (scripts / "estilo_sgr.py").write_text(ESTILO_STUB, encoding="utf-8")
        self.scripts = scripts
        patcher = mock.patch.object(value_chain, "_script_candidates", lambda name: [scripts / name])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ws = self.new_dir("ws")

    def new_dir(self, name: str) -> Path:
        path = self.tmp / name
        path.mkdir()
        return path


class TestLoadValueChain(StubScripts):
    def test_base_flow_is_not_available_and_loads_nothing(self):
        _, run = make_workspace(self.ws, flujo=None)
        write_cadena(run)
        write_findings(run, [{"severity": "error", "code": "cadena-x", "message": "m", "node": "1.1"}])
        data = load_value_chain(run)
        self.assertEqual(data["flujo"], "base")
        self.assertFalse(data["disponible"])
        self.assertIsNone(data["cadena"])
        self.assertEqual(data["hallazgos"], [])
        self.assertIsNone(data["hash"])
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["errores"], [])

    def test_sgr_without_chain_is_not_available_and_has_no_errors(self):
        _, run = make_workspace(self.ws)
        data = load_value_chain(run)
        self.assertEqual(data["flujo"], "sgr")
        self.assertFalse(data["disponible"])
        self.assertIsNone(data["cadena"])
        self.assertEqual(data["errores"], [])

    def test_sgr_chain_returns_the_data_findings_hash_and_cost_total(self):
        _, run = make_workspace(self.ws)
        write_cadena(run)
        finding = {"severity": "warning", "code": "cadena-codigo-dnp-nulo", "message": "Sin código", "node": "1.1"}
        write_findings(run, [finding])
        data = load_value_chain(run)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["cadena"]["objetivos"][0]["texto"], "Caracterizar la calidad del agua")
        self.assertEqual(data["hallazgos"], [finding])
        self.assertEqual(data["total_costos"], 1500.5)
        self.assertRegex(data["hash"], r"^[0-9a-f]{16}$")
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["errores"], [])

    def test_missing_rules_script_shows_the_chain_without_findings(self):
        _, run = make_workspace(self.ws)
        write_cadena(run)
        (self.scripts / "cadena_valor_sgr.py").unlink()
        data = load_value_chain(run)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["hallazgos"], [])
        self.assertEqual(data["errores"], [])

    def test_corrupt_or_foreign_chain_returns_errors_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_cadena(run, "{roto")
        data = load_value_chain(run)
        self.assertFalse(data["disponible"])
        self.assertIn("cadena_valor.json", " ".join(data["errores"]))
        write_cadena(run, {**CADENA, "schema": "otro/v1"})
        data = load_value_chain(run)
        self.assertFalse(data["disponible"])
        self.assertIn("morfeo.cadena-valor-sgr/v1", " ".join(data["errores"]))

    def test_corrupt_review_is_reported_and_never_overwritten(self):
        _, run = make_workspace(self.ws)
        write_cadena(run)
        review = run / "artefactos" / "sgr" / "revision.json"
        review.write_text("{roto", encoding="utf-8")
        data = load_value_chain(run)
        self.assertTrue(data["disponible"])
        self.assertIn("revision.json", " ".join(data["errores"]))
        result = approve(run, data["hash"])
        self.assertFalse(result["ok"])
        self.assertEqual(review.read_text(encoding="utf-8"), "{roto")


class TestApprove(StubScripts):
    def test_error_findings_block_the_approval(self):
        _, run = make_workspace(self.ws)
        write_cadena(run)
        write_findings(run, [{"severity": "error", "code": "cadena-texto-objetivo", "message": "m", "node": "OE1"}])
        result = approve(run)
        self.assertFalse(result["ok"])
        self.assertIn("cadena-texto-objetivo", result["error"])
        self.assertFalse((run / "artefactos" / "sgr" / "revision.json").exists())

    def test_approval_writes_the_review_and_expires_when_the_file_changes(self):
        _, run = make_workspace(self.ws)
        write_cadena(run)
        write_findings(run, [{"severity": "warning", "code": "cadena-costo-nulo", "message": "m", "node": "1.1.3"}])
        current = load_value_chain(run)["hash"]
        result = approve(run, current)
        self.assertTrue(result["ok"])
        saved = json.loads((run / "artefactos" / "sgr" / "revision.json").read_text(encoding="utf-8"))
        self.assertEqual(set(saved["cadena_valor"]), {"aprobado", "hash", "fecha"})
        self.assertTrue(saved["cadena_valor"]["aprobado"])
        self.assertEqual(saved["cadena_valor"]["hash"], current)
        self.assertTrue(load_value_chain(run)["aprobado"])

        changed = json.loads(json.dumps(CADENA))
        changed["objetivos"][0]["productos"][0]["meta"] = 3
        write_cadena(run, changed)
        data = load_value_chain(run)
        self.assertFalse(data["aprobado"])
        self.assertNotEqual(data["hash"], current)
        self.assertEqual(data["revision"]["hash"], current)

    def test_a_stale_hash_is_refused(self):
        _, run = make_workspace(self.ws)
        write_cadena(run)
        result = approve(run, "0000000000000000")
        self.assertFalse(result["ok"])
        self.assertIn("cambió", result["error"])

    def test_base_flow_and_missing_chain_cannot_be_approved(self):
        _, run = make_workspace(self.ws, flujo=None)
        write_cadena(run)
        self.assertFalse(approve(run)["ok"])
        _, run2 = make_workspace(self.new_dir("ws2"))
        result = approve(run2)
        self.assertFalse(result["ok"])
        self.assertIn("cadena_valor_sgr.py init", result["error"])


class TestAdjustPrompt(StubScripts):
    def test_prompt_carries_the_note_the_file_and_the_check_command(self):
        _, run = make_workspace(self.ws)
        prompt = build_adjust_prompt(run, "Agrega una actividad\nde socialización en 1.2")
        self.assertIn("«Agrega una actividad de socialización en 1.2»", prompt)
        self.assertIn("investigador", prompt)
        self.assertIn("proposals/run-cadena/artefactos/sgr/cadena_valor.json", prompt)
        self.assertIn("cadena_valor_sgr.py check proposals/run-cadena", prompt)
        self.assertNotIn("\n", prompt)

    def test_empty_note_or_base_flow_raise_value_error(self):
        _, run = make_workspace(self.ws)
        with self.assertRaises(ValueError):
            build_adjust_prompt(run, "   ")
        with self.assertRaises(ValueError):
            build_adjust_prompt(run, None)
        _, base = make_workspace(self.new_dir("base"), flujo=None)
        with self.assertRaises(ValueError):
            build_adjust_prompt(base, "algo")


class TestLoadStyle(StubScripts):
    def test_base_flow_is_not_available(self):
        _, run = make_workspace(self.ws, flujo=None)
        (run / "stub_estilo.json").write_text(json.dumps(ESTILO), encoding="utf-8")
        data = load_style(run)
        self.assertEqual(data, {"flujo": "base", "disponible": False, "por_seccion": {}, "errores": []})

    def test_sgr_groups_the_findings_by_section(self):
        _, run = make_workspace(self.ws)
        (run / "stub_estilo.json").write_text(json.dumps(ESTILO), encoding="utf-8")
        data = load_style(run)
        self.assertTrue(data["disponible"])
        just = data["por_seccion"]["02_justificacion"]
        self.assertEqual((just["total"], just["advertencias"], just["info"]), (2, 1, 1))
        self.assertEqual(just["hallazgos"][0], {"severity": "advertencia", "code": "sgr-estilo-primera-persona",
                                                "regla": "primera-persona", "linea": 12, "extracto": "proponemos",
                                                "message": "Primera persona"})
        self.assertEqual(data["por_seccion"]["10_metodologia"]["total"], 1)
        self.assertEqual(data["errores"], [])

    def test_missing_or_failing_script_never_raises(self):
        _, run = make_workspace(self.ws)
        (run / "stub_estilo_falla").write_text("", encoding="utf-8")
        data = load_style(run)
        self.assertFalse(data["disponible"])
        self.assertIn("léxico ilegible", " ".join(data["errores"]))
        (self.scripts / "estilo_sgr.py").unlink()
        data = load_style(run)
        self.assertFalse(data["disponible"])
        self.assertEqual(data["errores"], [])


class TestValueChainHttpApi(StubScripts):
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

    def test_get_approve_adjust_and_style_over_http(self):
        workspace, run = make_workspace(self.ws)
        write_cadena(run)
        (run / "stub_estilo.json").write_text(json.dumps(ESTILO), encoding="utf-8")
        base = self._serve(workspace)

        code, data = self._request(base + "/api/value-chain")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["run"], run.name)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["total_costos"], 1500.5)

        code, bad = self._request(base + "/api/value-chain/approve", {"hash": "0000000000000000"})
        self.assertEqual(code, 409)
        self.assertFalse(bad["ok"])

        code, ok = self._request(base + "/api/value-chain/approve", {"hash": data["hash"]})
        self.assertEqual(code, 200)
        self.assertTrue(ok["ok"])
        self.assertTrue(self._request(base + "/api/value-chain")[1]["aprobado"])

        code, adj = self._request(base + "/api/value-chain/adjust", {"nota": "Divide 1.1"})
        self.assertEqual(code, 200)
        self.assertEqual(adj, {"ok": True, "prompt": build_adjust_prompt(run, "Divide 1.1")})

        code, bad = self._request(base + "/api/value-chain/adjust", {"nota": ""})
        self.assertEqual(code, 400)
        self.assertFalse(bad["ok"])

        code, bad = self._request(base + "/api/value-chain/adjust", raw=b"{roto")
        self.assertEqual(code, 400)
        self.assertFalse(bad["ok"])

        code, style = self._request(base + "/api/style-sgr")
        self.assertEqual(code, 200)
        self.assertTrue(style["ok"])
        self.assertEqual(style["por_seccion"]["02_justificacion"]["total"], 2)

    def test_error_findings_answer_409_on_approve(self):
        workspace, run = make_workspace(self.ws)
        write_cadena(run)
        write_findings(run, [{"severity": "error", "code": "cadena-actividades-tecnicas", "message": "m", "node": "1.1"}])
        base = self._serve(workspace)
        code, bad = self._request(base + "/api/value-chain/approve", {})
        self.assertEqual(code, 409)
        self.assertIn("cadena-actividades-tecnicas", bad["error"])

    def test_base_flow_routes_report_unavailable(self):
        workspace, run = make_workspace(self.ws, flujo=None)
        write_cadena(run)
        base = self._serve(workspace)
        code, data = self._request(base + "/api/value-chain")
        self.assertEqual(code, 200)
        self.assertEqual((data["flujo"], data["disponible"], data["cadena"]), ("base", False, None))
        code, style = self._request(base + "/api/style-sgr")
        self.assertEqual(code, 200)
        self.assertFalse(style["disponible"])
        code, bad = self._request(base + "/api/value-chain/adjust", {"nota": "x"})
        self.assertEqual(code, 400)

    def test_without_active_run_the_routes_answer_404(self):
        workspace = self.ws
        (workspace / "proposals").mkdir()
        base = self._serve(workspace)
        for path, payload in (("/api/value-chain", None), ("/api/value-chain/approve", {}),
                              ("/api/value-chain/adjust", {"nota": "x"}), ("/api/style-sgr", None)):
            code, bad = self._request(base + path, payload)
            self.assertEqual(code, 404, path)
            self.assertFalse(bad["ok"])


if __name__ == "__main__":
    unittest.main()
