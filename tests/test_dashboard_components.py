"""Pestaña «TRL y componentes» (odd/tasks/sgr-trl-componentes.md, S1 y S6).

Los scripts del kit `componentes_sgr.py` y `presupuesto_sgr.py` se sustituyen por
dobles escritos en una carpeta temporal y se cargan por la misma importación
dinámica que usa el tablero para `cadena_valor_sgr.py`.
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
from morfeo.core.components import approve, build_adjust_prompt, load_components

COMPONENTES = {
    "schema": "morfeo.componentes-sgr/v1",
    "trl": {"introduccion": "El proyecto madura la tecnología.", "tipologia": "B", "entrada": 4, "salida": 7,
            "evidencia_entrada": ["Prototipo validado en laboratorio"],
            "ruta": [{"hito": "Prototipo en entorno relevante", "mes": 12, "trl": 6, "actividades": ["1.1.1"],
                      "evidencia": "Informe de pruebas"}],
            "verificacion": {"escenario": "Planta piloto", "responsables": ["E1"], "criterios_aceptacion": ["Error < 5 %"],
                             "evidencias": ["Acta"], "actor_usuario": "E2"}},
    "transferencia": {"introduccion": "", "resultados": [{"resultado": "Modelo", "usuarios": ["Acueducto"], "proteccion_pi": None}],
                      "ruta": [{"etapa": "Piloto", "mecanismo": "Licencia", "barreras": "Costos", "acciones": "Capacitar"}],
                      "actividades": ["1.1.1"], "continuidad": "Convenio"},
    "asc": {"introduccion": "", "actores": [], "ruta": [], "productos": []},
    "sostenibilidad": {"introduccion": "", "ods": [], "actores": [], "ambiental": []},
    "uso_posterior": {"introduccion": "", "bienes": [], "adopcion": []},
    "diferencial": {"introduccion": "", "barreras": [], "justificacion_sin_barreras": "No aplica"},
}

CADENA = {
    "schema": "morfeo.cadena-valor-sgr/v1",
    "duracion_meses": 24,
    "objetivos": [{"id": "OE1", "texto": "Medir", "productos": [{"codigo": "1.1", "nombre": "Servicio", "actividades": [
        {"codigo": "1.1.1", "nombre": "Levantar datos"}, {"codigo": "1.1.2", "nombre": "Transferir"}]}]}],
}

ALIANZA = {"schema": "morfeo.alianza-sgr/v1", "entidades": [
    {"id": "E1", "nombre": "Universidad Nacional"}, {"id": "E2", "nombre": "Acueducto"}]}

COMPONENTS_STUB = '''
import json
from pathlib import Path

def findings(run_root):
    if (Path(run_root) / "stub_falla").exists():
        raise RuntimeError("componentes ilegibles")
    path = Path(run_root) / "stub_componentes_findings.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []

def datos(run_root):
    return {}
'''

BUDGET_STUB = '''
def findings(run_root):
    return []

def resumen(run_root):
    return {"total_sgr": 100, "transferencia_pct": 1.5}
'''


def make_workspace(tmp: Path, flujo: str | None = "sgr") -> tuple[Path, Path]:
    workspace = Path(tmp)
    if flujo:
        (workspace / ".morfeo").mkdir()
        (workspace / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = workspace / "proposals" / "run-componentes"
    (run / "artefactos").mkdir(parents=True)
    (workspace / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
    return workspace, run


def write_file(run: Path, name: str, data: dict | str) -> None:
    folder = run / "artefactos" / "sgr"
    folder.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    (folder / name).write_text(text, encoding="utf-8")


def write_all(run: Path) -> None:
    write_file(run, "componentes.json", COMPONENTES)
    write_file(run, "cadena_valor.json", CADENA)
    write_file(run, "alianza.json", ALIANZA)


def write_stub(run: Path, name: str, data) -> None:
    (run / name).write_text(json.dumps(data), encoding="utf-8")


class StubScripts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        scripts = self.tmp / "kit-scripts"
        scripts.mkdir()
        (scripts / "componentes_sgr.py").write_text(COMPONENTS_STUB, encoding="utf-8")
        (scripts / "presupuesto_sgr.py").write_text(BUDGET_STUB, encoding="utf-8")
        self.scripts = scripts
        patcher = mock.patch.object(value_chain, "_script_candidates", lambda name: [scripts / name])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ws = self.new_dir("ws")

    def new_dir(self, name: str) -> Path:
        path = self.tmp / name
        path.mkdir()
        return path


class TestLoadComponents(StubScripts):
    def test_base_flow_is_not_available_and_loads_nothing(self):
        _, run = make_workspace(self.ws, flujo=None)
        write_all(run)
        write_file(run, "presupuesto.json", {"schema": "morfeo.presupuesto-sgr/v1"})
        write_stub(run, "stub_componentes_findings.json", [{"severity": "error", "code": "componentes-x"}])
        data = load_components(run)
        self.assertEqual(data["flujo"], "base")
        self.assertFalse(data["disponible"])
        for key in ("componentes", "transferencia_pct", "hash", "revision"):
            self.assertIsNone(data[key], key)
        self.assertEqual((data["hallazgos"], data["errores"]), ([], []))
        self.assertEqual((data["cadena"], data["entidades"]), ({}, {}))
        self.assertFalse(data["aprobado"])

    def test_sgr_without_files_is_not_available_and_has_no_errors(self):
        _, run = make_workspace(self.ws)
        data = load_components(run)
        self.assertEqual(data["flujo"], "sgr")
        self.assertFalse(data["disponible"])
        self.assertIsNone(data["hash"])
        self.assertIsNone(data["transferencia_pct"])
        self.assertEqual(data["errores"], [])

    def test_sgr_returns_components_findings_names_and_transfer_percentage(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        write_file(run, "presupuesto.json", {"schema": "morfeo.presupuesto-sgr/v1"})
        finding = {"severity": "warning", "code": "componentes-asc-divulgacion", "message": "Solo divulgación", "node": "asc"}
        write_stub(run, "stub_componentes_findings.json", [finding])
        data = load_components(run)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["componentes"], COMPONENTES)
        self.assertEqual(data["hallazgos"], [finding])
        self.assertEqual(data["transferencia_pct"], 1.5)
        self.assertEqual(data["cadena"], {"1.1.1": "Levantar datos", "1.1.2": "Transferir"})
        self.assertEqual(data["entidades"], {"E1": "Universidad Nacional", "E2": "Acueducto"})
        self.assertIsInstance(data["hash"], str)
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["errores"], [])

    def test_transfer_percentage_needs_the_budget_file(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        self.assertIsNone(load_components(run)["transferencia_pct"])

    def test_the_hash_covers_the_components_but_not_the_chain_or_alliance(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        first = load_components(run)["hash"]
        write_file(run, "cadena_valor.json", {**CADENA, "duracion_meses": 36})
        write_file(run, "alianza.json", {**ALIANZA, "entidades": []})
        self.assertEqual(load_components(run)["hash"], first)
        changed = json.loads(json.dumps(COMPONENTES))
        changed["trl"]["salida"] = 8
        write_file(run, "componentes.json", changed)
        self.assertNotEqual(load_components(run)["hash"], first)

    def test_missing_scripts_show_the_data_without_findings_or_percentage(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        write_file(run, "presupuesto.json", {"schema": "morfeo.presupuesto-sgr/v1"})
        for name in ("componentes_sgr.py", "presupuesto_sgr.py"):
            (self.scripts / name).unlink()
        data = load_components(run)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["hallazgos"], [])
        self.assertIsNone(data["transferencia_pct"])
        self.assertEqual(data["errores"], [])

    def test_failing_script_is_reported_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        (run / "stub_falla").write_text("", encoding="utf-8")
        data = load_components(run)
        self.assertTrue(data["disponible"])
        self.assertIn("componentes ilegibles", " ".join(data["errores"]))

    def test_corrupt_or_foreign_files_return_errors_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_file(run, "componentes.json", "{roto")
        data = load_components(run)
        self.assertFalse(data["disponible"])
        self.assertIn("componentes.json", " ".join(data["errores"]))
        write_file(run, "componentes.json", {"schema": "otro/v1"})
        data = load_components(run)
        self.assertFalse(data["disponible"])
        self.assertIn("morfeo.componentes-sgr/v1", " ".join(data["errores"]))


class TestApprove(StubScripts):
    def test_error_findings_block_the_approval(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        write_stub(run, "stub_componentes_findings.json",
                   [{"severity": "error", "code": "componentes-asc-elemento", "message": "m", "node": "asc"}])
        result = approve(run)
        self.assertFalse(result["ok"])
        self.assertIn("componentes-asc-elemento", result["error"])
        self.assertFalse((run / "artefactos" / "sgr" / "revision.json").exists())

    def test_approval_preserves_other_keys_and_expires_when_the_file_changes(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        review = run / "artefactos" / "sgr" / "revision.json"
        others = {"cadena_valor": {"aprobado": True, "hash": "cafe", "fecha": "2026-11-18T10:00:00"},
                  "alianza_territorio": {"aprobado": True, "hash": "beef", "fecha": "2026-11-18T11:00:00"},
                  "presupuesto": {"aprobado": True, "hash": "f00d", "fecha": "2026-11-18T12:00:00"}}
        review.write_text(json.dumps(others), encoding="utf-8")
        current = load_components(run)["hash"]
        result = approve(run, current)
        self.assertTrue(result["ok"])
        saved = json.loads(review.read_text(encoding="utf-8"))
        for key, value in others.items():
            self.assertEqual(saved[key], value, key)
        self.assertEqual(set(saved["componentes"]), {"aprobado", "hash", "fecha"})
        self.assertEqual(saved["componentes"]["hash"], current)
        self.assertTrue(load_components(run)["aprobado"])

        changed = json.loads(json.dumps(COMPONENTES))
        changed["transferencia"]["continuidad"] = "Otra"
        write_file(run, "componentes.json", changed)
        data = load_components(run)
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["revision"]["hash"], current)

    def test_a_stale_hash_is_refused(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        result = approve(run, "0000000000000000")
        self.assertFalse(result["ok"])
        self.assertIn("cambi", result["error"])

    def test_missing_file_and_base_flow_are_refused(self):
        _, empty = make_workspace(self.ws)
        result = approve(empty)
        self.assertFalse(result["ok"])
        self.assertIn("fase5_5_sgr", result["error"])
        self.assertIn("componentes_sgr.py check", result["error"])
        _, base = make_workspace(self.new_dir("base"), flujo=None)
        write_all(base)
        result = approve(base)
        self.assertFalse(result["ok"])
        self.assertIn("SGR", result["error"])

    def test_corrupt_review_is_never_overwritten(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        review = run / "artefactos" / "sgr" / "revision.json"
        review.write_text("{roto", encoding="utf-8")
        data = load_components(run)
        self.assertIn("revision.json", " ".join(data["errores"]))
        self.assertFalse(approve(run, data["hash"])["ok"])
        self.assertEqual(review.read_text(encoding="utf-8"), "{roto")


class TestAdjustPrompt(StubScripts):
    def test_prompt_carries_the_note_file_agents_and_the_check(self):
        _, run = make_workspace(self.ws)
        prompt = build_adjust_prompt(run, "Sube el TRL\nde salida")
        self.assertIn("«Sube el TRL de salida»", prompt)
        self.assertIn("proposals/run-componentes/artefactos/sgr/componentes.json", prompt)
        self.assertIn("morfeo.componentes-sgr/v1", prompt)
        investigador = prompt.index("investigador")
        redactor = prompt.index("redactor")
        check = prompt.index("componentes_sgr.py check proposals/run-componentes")
        self.assertLess(investigador, check)
        self.assertLess(redactor, check)
        for block in ("trl", "transferencia", "uso_posterior", "asc", "sostenibilidad", "diferencial", "introduccion"):
            self.assertIn(block, prompt)
        self.assertIn("revisor-estilo-sgr", prompt)
        self.assertNotIn("\n", prompt)

    def test_empty_note_or_base_flow_raise_value_error(self):
        _, run = make_workspace(self.ws)
        with self.assertRaises(ValueError):
            build_adjust_prompt(run, "  ")
        with self.assertRaises(ValueError):
            build_adjust_prompt(run, None)
        _, base = make_workspace(self.new_dir("base"), flujo=None)
        with self.assertRaises(ValueError):
            build_adjust_prompt(base, "algo")


class TestComponentsHttpApi(StubScripts):
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

    def test_get_approve_and_adjust_over_http(self):
        workspace, run = make_workspace(self.ws)
        write_all(run)
        base = self._serve(workspace)

        code, data = self._request(base + "/api/components")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["run"], run.name)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["componentes"], COMPONENTES)

        code, bad = self._request(base + "/api/components/approve", {"hash": "0000000000000000"})
        self.assertEqual(code, 409)
        self.assertFalse(bad["ok"])

        code, ok = self._request(base + "/api/components/approve", {"hash": data["hash"]})
        self.assertEqual(code, 200)
        self.assertTrue(ok["ok"])
        self.assertTrue(self._request(base + "/api/components")[1]["aprobado"])

        code, adj = self._request(base + "/api/components/adjust", {"nota": "Agrega un ODS"})
        self.assertEqual(code, 200)
        self.assertEqual(adj, {"ok": True, "prompt": build_adjust_prompt(run, "Agrega un ODS")})

        code, bad = self._request(base + "/api/components/adjust", {"nota": ""})
        self.assertEqual(code, 400)
        code, bad = self._request(base + "/api/components/adjust", raw=b"{roto")
        self.assertEqual(code, 400)
        self.assertFalse(bad["ok"])

    def test_error_findings_answer_409_on_approve(self):
        workspace, run = make_workspace(self.ws)
        write_all(run)
        write_stub(run, "stub_componentes_findings.json",
                   [{"severity": "error", "code": "componentes-trl-salida", "message": "m", "node": "trl"}])
        base = self._serve(workspace)
        code, bad = self._request(base + "/api/components/approve", {})
        self.assertEqual(code, 409)
        self.assertIn("componentes-trl-salida", bad["error"])

    def test_base_flow_routes_report_unavailable(self):
        workspace, run = make_workspace(self.ws, flujo=None)
        write_all(run)
        base = self._serve(workspace)
        code, data = self._request(base + "/api/components")
        self.assertEqual(code, 200)
        self.assertEqual((data["flujo"], data["disponible"], data["componentes"]), ("base", False, None))
        code, _ = self._request(base + "/api/components/adjust", {"nota": "x"})
        self.assertEqual(code, 400)
        code, _ = self._request(base + "/api/components/approve", {})
        self.assertEqual(code, 409)

    def test_without_active_run_the_routes_answer_404(self):
        (self.ws / "proposals").mkdir()
        base = self._serve(self.ws)
        for path, payload in (("/api/components", None), ("/api/components/approve", {}),
                              ("/api/components/adjust", {"nota": "x"})):
            code, bad = self._request(base + path, payload)
            self.assertEqual(code, 404, path)
            self.assertFalse(bad["ok"])


if __name__ == "__main__":
    unittest.main()
