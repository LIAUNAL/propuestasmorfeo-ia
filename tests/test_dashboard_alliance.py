"""Pestaña «Alianza y territorio» (odd/tasks/sgr-alianza-territorio.md, S1 y S6).

El script del kit `alianza_territorio_sgr.py` se sustituye por un doble escrito
en una carpeta temporal y se carga por la misma importación dinámica que usa el
tablero para `cadena_valor_sgr.py`.
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
from morfeo.core.alliance import approve, build_adjust_prompt, load_alliance

ALIANZA = {
    "schema": "morfeo.alianza-sgr/v1",
    "monto_sgr_solicitado": 3000000000,
    "duracion_meses": 24,
    "entidades": [
        {"id": "E1", "nombre": "Universidad Nacional de Colombia", "nit": "899999063", "tipo": "IES",
         "proponente": True, "departamento": "Caldas", "rol": "Ejecutor", "posicion": "cooperante",
         "interes": "Investigar", "responsabilidades": ["Dirigir el proyecto"], "actividades": ["1.1.1"],
         "aporte_especie": 200000000, "aporte_efectivo": 0, "domicilio_en_region": True, "tipo_diverso": None,
         "grupos": [{"nombre": "LIA", "codigo_gruplac": "COL0001", "clasificacion": "A1", "lineas": ["IA"]}],
         "trayectoria": [{"nombre": "Proyecto A", "codigo": "BPIN1", "financiador": "SGR", "anio": 2022,
                          "sgr_o_elegible": True}]},
        {"id": "E2", "nombre": "Gobernación de Caldas", "nit": None, "tipo": "entidad_territorial",
         "proponente": False, "departamento": "Caldas", "rol": "Aliado", "posicion": "beneficiario",
         "interes": None, "responsabilidades": [], "actividades": [], "aporte_especie": None,
         "aporte_efectivo": 50000000, "domicilio_en_region": True, "tipo_diverso": None, "grupos": [],
         "trayectoria": []},
    ],
    "gobernanza": {"toma_decisiones": "Comité técnico", "instancias": ["Comité"], "propiedad_intelectual": "Pactada",
                   "seguimiento": "Trimestral"},
}

TERRITORIO = {
    "schema": "morfeo.territorio-sgr/v1",
    "region_sgr": "Eje Cafetero",
    "departamentos": [{"nombre": "Caldas", "municipios": ["Manizales", "Chinchiná"]}],
    "demandas": [{"codigo": "D1", "texto": "Fortalecer la gestión del agua", "departamento": "Caldas",
                  "fuente": "TdR §5", "causas": ["C1"], "objetivos": ["OE1"], "actividades": ["1.1.1"],
                  "productos": ["1.1"], "articulacion": "El proyecto mide la calidad del agua."}],
    "configuracion_regional": [{"actor": "Corpocaldas", "departamento": "Caldas", "pertinencia": "Autoridad ambiental"}],
}

PUNTAJE = [
    {"subcriterio": "2.2", "nombre": "Alcance regional", "puntaje": 3, "max": 6, "incompleto": False,
     "calculo": "1 departamento(s) de ejecución."},
    {"subcriterio": "3.2", "nombre": "Composición de la alianza", "puntaje": 0, "max": 5, "incompleto": True,
     "calculo": "aliados es null."},
]

STUB = '''
import json
from pathlib import Path

def _read(run_root, name):
    path = Path(run_root) / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []

def findings(run_root):
    if (Path(run_root) / "stub_falla").exists():
        raise RuntimeError("territorio ilegible")
    return _read(run_root, "stub_findings.json")

def puntaje(run_root):
    return _read(run_root, "stub_puntaje.json")
'''


def make_workspace(tmp: Path, flujo: str | None = "sgr") -> tuple[Path, Path]:
    workspace = Path(tmp)
    if flujo:
        (workspace / ".morfeo").mkdir()
        (workspace / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = workspace / "proposals" / "run-alianza"
    (run / "artefactos").mkdir(parents=True)
    (workspace / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
    return workspace, run


def write_file(run: Path, name: str, data: dict | str) -> None:
    folder = run / "artefactos" / "sgr"
    folder.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    (folder / name).write_text(text, encoding="utf-8")


def write_both(run: Path) -> None:
    write_file(run, "alianza.json", ALIANZA)
    write_file(run, "territorio.json", TERRITORIO)


def write_findings(run: Path, findings: list[dict]) -> None:
    (run / "stub_findings.json").write_text(json.dumps(findings), encoding="utf-8")


def write_puntaje(run: Path, puntaje: list[dict] = PUNTAJE) -> None:
    (run / "stub_puntaje.json").write_text(json.dumps(puntaje), encoding="utf-8")


class StubScript(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        scripts = self.tmp / "kit-scripts"
        scripts.mkdir()
        (scripts / "alianza_territorio_sgr.py").write_text(STUB, encoding="utf-8")
        self.scripts = scripts
        patcher = mock.patch.object(value_chain, "_script_candidates", lambda name: [scripts / name])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ws = self.new_dir("ws")

    def new_dir(self, name: str) -> Path:
        path = self.tmp / name
        path.mkdir()
        return path


class TestLoadAlliance(StubScript):
    def test_base_flow_is_not_available_and_loads_nothing(self):
        _, run = make_workspace(self.ws, flujo=None)
        write_both(run)
        write_findings(run, [{"severity": "error", "code": "alianza-x", "message": "m", "node": "E1"}])
        write_puntaje(run)
        data = load_alliance(run)
        self.assertEqual(data["flujo"], "base")
        self.assertFalse(data["disponible"])
        self.assertIsNone(data["alianza"])
        self.assertIsNone(data["territorio"])
        self.assertEqual(data["hallazgos"], [])
        self.assertEqual(data["puntaje"], [])
        self.assertIsNone(data["hash"])
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["errores"], [])

    def test_sgr_without_files_is_not_available_and_has_no_errors(self):
        _, run = make_workspace(self.ws)
        data = load_alliance(run)
        self.assertEqual(data["flujo"], "sgr")
        self.assertFalse(data["disponible"])
        self.assertEqual(data["errores"], [])

    def test_sgr_returns_both_files_findings_score_and_hash(self):
        _, run = make_workspace(self.ws)
        write_both(run)
        finding = {"severity": "warning", "code": "alianza-departamento", "message": "Fuera", "node": "E2"}
        write_findings(run, [finding])
        write_puntaje(run)
        data = load_alliance(run)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["alianza"]["entidades"][0]["nombre"], "Universidad Nacional de Colombia")
        self.assertEqual(data["territorio"]["demandas"][0]["texto"], "Fortalecer la gestión del agua")
        self.assertEqual(data["hallazgos"], [finding])
        self.assertEqual(data["puntaje"], PUNTAJE)
        self.assertRegex(data["hash"], r"^[0-9a-f]{16}$")
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["errores"], [])

    def test_the_hash_covers_both_files(self):
        _, run = make_workspace(self.ws)
        write_both(run)
        first = load_alliance(run)["hash"]
        changed = json.loads(json.dumps(TERRITORIO))
        changed["demandas"][0]["articulacion"] = "Otro texto"
        write_file(run, "territorio.json", changed)
        second = load_alliance(run)["hash"]
        self.assertNotEqual(first, second)
        changed_alliance = json.loads(json.dumps(ALIANZA))
        changed_alliance["entidades"][1]["rol"] = "Cofinanciador"
        write_file(run, "alianza.json", changed_alliance)
        self.assertNotEqual(load_alliance(run)["hash"], second)

    def test_missing_rules_script_shows_the_data_without_findings_or_score(self):
        _, run = make_workspace(self.ws)
        write_both(run)
        (self.scripts / "alianza_territorio_sgr.py").unlink()
        data = load_alliance(run)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["hallazgos"], [])
        self.assertEqual(data["puntaje"], [])
        self.assertEqual(data["errores"], [])

    def test_failing_script_is_reported_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_both(run)
        (run / "stub_falla").write_text("", encoding="utf-8")
        data = load_alliance(run)
        self.assertTrue(data["disponible"])
        self.assertIn("territorio ilegible", " ".join(data["errores"]))

    def test_corrupt_or_foreign_files_return_errors_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_file(run, "alianza.json", "{roto")
        write_file(run, "territorio.json", TERRITORIO)
        data = load_alliance(run)
        self.assertIsNone(data["alianza"])
        self.assertEqual(data["territorio"]["region_sgr"], "Eje Cafetero")
        self.assertIn("alianza.json", " ".join(data["errores"]))
        write_file(run, "alianza.json", ALIANZA)
        write_file(run, "territorio.json", {**TERRITORIO, "schema": "otro/v1"})
        data = load_alliance(run)
        self.assertIsNone(data["territorio"])
        self.assertIn("morfeo.territorio-sgr/v1", " ".join(data["errores"]))


class TestApprove(StubScript):
    def test_error_findings_block_the_approval(self):
        _, run = make_workspace(self.ws)
        write_both(run)
        write_findings(run, [{"severity": "error", "code": "alianza-composicion", "message": "m", "node": ""}])
        result = approve(run)
        self.assertFalse(result["ok"])
        self.assertIn("alianza-composicion", result["error"])
        self.assertFalse((run / "artefactos" / "sgr" / "revision.json").exists())

    def test_approval_preserves_the_value_chain_key_and_expires_when_a_file_changes(self):
        _, run = make_workspace(self.ws)
        write_both(run)
        review = run / "artefactos" / "sgr" / "revision.json"
        chain_entry = {"aprobado": True, "hash": "cafe", "fecha": "2026-11-18T10:00:00"}
        review.write_text(json.dumps({"cadena_valor": chain_entry}), encoding="utf-8")
        current = load_alliance(run)["hash"]
        result = approve(run, current)
        self.assertTrue(result["ok"])
        saved = json.loads(review.read_text(encoding="utf-8"))
        self.assertEqual(saved["cadena_valor"], chain_entry)
        self.assertEqual(set(saved["alianza_territorio"]), {"aprobado", "hash", "fecha"})
        self.assertEqual(saved["alianza_territorio"]["hash"], current)
        self.assertTrue(load_alliance(run)["aprobado"])

        changed = json.loads(json.dumps(TERRITORIO))
        changed["region_sgr"] = "Pacífico"
        write_file(run, "territorio.json", changed)
        data = load_alliance(run)
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["revision"]["hash"], current)

    def test_a_stale_hash_is_refused(self):
        _, run = make_workspace(self.ws)
        write_both(run)
        result = approve(run, "0000000000000000")
        self.assertFalse(result["ok"])
        self.assertIn("cambi", result["error"])

    def test_both_files_are_required_and_base_flow_cannot_approve(self):
        _, run = make_workspace(self.ws)
        write_file(run, "alianza.json", ALIANZA)
        result = approve(run)
        self.assertFalse(result["ok"])
        self.assertIn("territorio.json", result["error"])
        _, empty = make_workspace(self.new_dir("ws2"))
        result = approve(empty)
        self.assertFalse(result["ok"])
        self.assertIn("fase1b_sgr", result["error"])
        _, base = make_workspace(self.new_dir("base"), flujo=None)
        write_both(base)
        self.assertFalse(approve(base)["ok"])

    def test_corrupt_review_is_never_overwritten(self):
        _, run = make_workspace(self.ws)
        write_both(run)
        review = run / "artefactos" / "sgr" / "revision.json"
        review.write_text("{roto", encoding="utf-8")
        data = load_alliance(run)
        self.assertIn("revision.json", " ".join(data["errores"]))
        self.assertFalse(approve(run, data["hash"])["ok"])
        self.assertEqual(review.read_text(encoding="utf-8"), "{roto")


class TestAdjustPrompt(StubScript):
    def test_prompt_carries_the_note_both_files_the_agents_and_the_check_command(self):
        _, run = make_workspace(self.ws)
        prompt = build_adjust_prompt(run, "Agrega la Alcaldía\nde Manizales")
        self.assertIn("«Agrega la Alcaldía de Manizales»", prompt)
        self.assertIn("investigador", prompt)
        self.assertIn("insumos-observador", prompt)
        self.assertIn("proposals/run-alianza/artefactos/sgr/alianza.json", prompt)
        self.assertIn("proposals/run-alianza/artefactos/sgr/territorio.json", prompt)
        self.assertIn("alianza_territorio_sgr.py check proposals/run-alianza", prompt)
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


class TestAllianceHttpApi(StubScript):
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
        write_both(run)
        write_puntaje(run)
        base = self._serve(workspace)

        code, data = self._request(base + "/api/alliance")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["run"], run.name)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["puntaje"], PUNTAJE)

        code, bad = self._request(base + "/api/alliance/approve", {"hash": "0000000000000000"})
        self.assertEqual(code, 409)
        self.assertFalse(bad["ok"])

        code, ok = self._request(base + "/api/alliance/approve", {"hash": data["hash"]})
        self.assertEqual(code, 200)
        self.assertTrue(ok["ok"])
        self.assertTrue(self._request(base + "/api/alliance")[1]["aprobado"])

        code, adj = self._request(base + "/api/alliance/adjust", {"nota": "Agrega un aliado"})
        self.assertEqual(code, 200)
        self.assertEqual(adj, {"ok": True, "prompt": build_adjust_prompt(run, "Agrega un aliado")})

        code, bad = self._request(base + "/api/alliance/adjust", {"nota": ""})
        self.assertEqual(code, 400)
        code, bad = self._request(base + "/api/alliance/adjust", raw=b"{roto")
        self.assertEqual(code, 400)
        self.assertFalse(bad["ok"])

    def test_error_findings_answer_409_on_approve(self):
        workspace, run = make_workspace(self.ws)
        write_both(run)
        write_findings(run, [{"severity": "error", "code": "territorio-demanda-objetivo", "message": "m", "node": "D1"}])
        base = self._serve(workspace)
        code, bad = self._request(base + "/api/alliance/approve", {})
        self.assertEqual(code, 409)
        self.assertIn("territorio-demanda-objetivo", bad["error"])

    def test_base_flow_routes_report_unavailable(self):
        workspace, run = make_workspace(self.ws, flujo=None)
        write_both(run)
        base = self._serve(workspace)
        code, data = self._request(base + "/api/alliance")
        self.assertEqual(code, 200)
        self.assertEqual((data["flujo"], data["disponible"], data["alianza"]), ("base", False, None))
        code, _ = self._request(base + "/api/alliance/adjust", {"nota": "x"})
        self.assertEqual(code, 400)

    def test_without_active_run_the_routes_answer_404(self):
        (self.ws / "proposals").mkdir()
        base = self._serve(self.ws)
        for path, payload in (("/api/alliance", None), ("/api/alliance/approve", {}),
                              ("/api/alliance/adjust", {"nota": "x"})):
            code, bad = self._request(base + path, payload)
            self.assertEqual(code, 404, path)
            self.assertFalse(bad["ok"])


if __name__ == "__main__":
    unittest.main()
