"""Pestaña «Presupuesto y cronograma» (odd/tasks/sgr-presupuesto-gantt.md, S1 y S6).

Los scripts del kit `presupuesto_sgr.py` y `cronograma_sgr.py` se sustituyen por
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
from morfeo.core.budget import approve, build_adjust_prompt, load_budget

PRESUPUESTO = {
    "schema": "morfeo.presupuesto-sgr/v1",
    "duracion_meses": 24,
    "tope_sgr": 3000000000,
    "semanas_por_mes": 4,
    "factor_prestacional": None,
    "items": [
        {"id": "P1", "rubro": "talento_humano", "insumo_mga": "mano_obra_calificada", "descripcion": "Investigador",
         "justificacion": "Dirige el OE1", "entidad": "E1", "fuente": "sgr", "componente": None, "cantidad": 1,
         "valor_unitario": 0, "talento": {"perfil": "PhD", "horas_semana": 20, "valor_hora": 100000, "meses": 12},
         "actividades": ["1.1.1"], "cotizaciones": 0, "soporte": None},
        {"id": "P2", "rubro": "seguimiento", "insumo_mga": "servicios_empresas", "descripcion": "Seguimiento",
         "justificacion": "Obligatorio", "entidad": "E1", "fuente": "sgr", "componente": "seguimiento",
         "cantidad": 1, "valor_unitario": 30000000, "talento": None, "actividades": ["1.1.2"], "cotizaciones": 0,
         "soporte": None},
    ],
}

HITOS = {
    "schema": "morfeo.hitos-sgr/v1",
    "hitos": [{"codigo": "H1", "nombre": "Línea base", "mes": 3, "actividades": ["1.1.1"],
               "verificacion": "Informe de línea base"}],
}

CADENA = {
    "schema": "morfeo.cadena-valor-sgr/v1",
    "duracion_meses": 24,
    "arbol_hash": "abc",
    "objetivos": [{
        "id": "OE1", "texto": "Medir la calidad del agua",
        "productos": [{
            "codigo": "1.1", "codigo_dnp": None, "nombre": "Servicio de información", "medido_a_traves_de": "",
            "indicador": "", "unidad": "", "meta": None,
            "actividades": [
                {"codigo": "1.1.1", "nombre": "Levantar datos", "tipo": "tecnica", "ruta_critica": True,
                 "mes_inicio": 1, "mes_fin": 6, "costo": None, "medio": None, "etapa": "preinversion"},
                {"codigo": "1.1.2", "nombre": "Supervisar", "tipo": "supervision", "ruta_critica": False,
                 "mes_inicio": None, "mes_fin": None, "costo": None, "medio": None},
            ],
        }],
    }],
}

RESUMEN = {"total_sgr": 126000000, "total_especie": 0, "total_efectivo": 0, "total": 126000000,
           "por_rubro": {"talento_humano": {"sgr": 96000000, "especie": 0, "efectivo": 0}},
           "cofinanciacion_pct": 0, "transferencia_pct": 0, "movilidad_pct": 0, "seguimiento": True,
           "cotizaciones_faltantes": 0}

PROYECCION = {"anios": [{"anio": 1, "valor": 126000000, "pct": 100}], "por_actividad": {"1.1.1": [96000000]}}

BUDGET_STUB = '''
import json
from pathlib import Path

def _read(run_root, name, default):
    path = Path(run_root) / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default

def findings(run_root):
    if (Path(run_root) / "stub_falla").exists():
        raise RuntimeError("presupuesto ilegible")
    return _read(run_root, "stub_presupuesto_findings.json", [])

def resumen(run_root):
    return _read(run_root, "stub_resumen.json", None)

def datos(run_root):
    return {}
'''

SCHEDULE_STUB = '''
import json
from pathlib import Path

def _read(run_root, name, default):
    path = Path(run_root) / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default

def findings(run_root):
    return _read(run_root, "stub_cronograma_findings.json", [])

def proyeccion(run_root):
    return _read(run_root, "stub_proyeccion.json", None)
'''


def make_workspace(tmp: Path, flujo: str | None = "sgr") -> tuple[Path, Path]:
    workspace = Path(tmp)
    if flujo:
        (workspace / ".morfeo").mkdir()
        (workspace / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = workspace / "proposals" / "run-presupuesto"
    (run / "artefactos").mkdir(parents=True)
    (workspace / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
    return workspace, run


def write_file(run: Path, name: str, data: dict | str) -> None:
    folder = run / "artefactos" / "sgr"
    folder.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    (folder / name).write_text(text, encoding="utf-8")


def write_all(run: Path) -> None:
    write_file(run, "presupuesto.json", PRESUPUESTO)
    write_file(run, "hitos.json", HITOS)
    write_file(run, "cadena_valor.json", CADENA)


def write_stub(run: Path, name: str, data) -> None:
    (run / name).write_text(json.dumps(data), encoding="utf-8")


class StubScripts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        scripts = self.tmp / "kit-scripts"
        scripts.mkdir()
        (scripts / "presupuesto_sgr.py").write_text(BUDGET_STUB, encoding="utf-8")
        (scripts / "cronograma_sgr.py").write_text(SCHEDULE_STUB, encoding="utf-8")
        self.scripts = scripts
        patcher = mock.patch.object(value_chain, "_script_candidates", lambda name: [scripts / name])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ws = self.new_dir("ws")

    def new_dir(self, name: str) -> Path:
        path = self.tmp / name
        path.mkdir()
        return path


class TestLoadBudget(StubScripts):
    def test_base_flow_is_not_available_and_loads_nothing(self):
        _, run = make_workspace(self.ws, flujo=None)
        write_all(run)
        write_stub(run, "stub_presupuesto_findings.json", [{"severity": "error", "code": "presupuesto-x"}])
        write_stub(run, "stub_resumen.json", RESUMEN)
        data = load_budget(run)
        self.assertEqual(data["flujo"], "base")
        self.assertFalse(data["disponible"])
        for key in ("presupuesto", "resumen", "proyeccion", "hash", "revision"):
            self.assertIsNone(data[key], key)
        for key in ("cadena_meses", "hitos", "hallazgos", "errores"):
            self.assertEqual(data[key], [], key)
        self.assertFalse(data["aprobado"])

    def test_sgr_without_files_is_not_available_and_has_no_errors(self):
        _, run = make_workspace(self.ws)
        data = load_budget(run)
        self.assertEqual(data["flujo"], "sgr")
        self.assertFalse(data["disponible"])
        self.assertIsNone(data["hash"])
        self.assertEqual(data["errores"], [])

    def test_sgr_returns_budget_summary_projection_months_milestones_and_findings(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        f_budget = {"severity": "warning", "code": "presupuesto-cotizaciones", "message": "Faltan", "node": "P1"}
        f_schedule = {"severity": "warning", "code": "cronograma-sin-hito", "message": "Hueco", "node": "7"}
        write_stub(run, "stub_presupuesto_findings.json", [f_budget])
        write_stub(run, "stub_cronograma_findings.json", [f_schedule])
        write_stub(run, "stub_resumen.json", RESUMEN)
        write_stub(run, "stub_proyeccion.json", PROYECCION)
        data = load_budget(run)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["presupuesto"]["items"][0]["id"], "P1")
        self.assertEqual(data["resumen"], RESUMEN)
        self.assertEqual(data["proyeccion"], PROYECCION)
        self.assertEqual(data["hallazgos"], [f_budget, f_schedule])
        self.assertEqual(data["duracion_meses"], 24)
        self.assertEqual(data["hitos"], HITOS["hitos"])
        first, second = data["cadena_meses"]
        self.assertEqual({k: first[k] for k in ("codigo", "nombre", "oe", "producto", "mes_inicio", "mes_fin",
                                               "ruta_critica", "etapa")},
                         {"codigo": "1.1.1", "nombre": "Levantar datos", "oe": "OE1", "producto": "1.1",
                          "mes_inicio": 1, "mes_fin": 6, "ruta_critica": True, "etapa": "preinversion"})
        self.assertEqual(first["producto_nombre"], "Servicio de información")
        self.assertEqual((second["mes_inicio"], second["mes_fin"], second["ruta_critica"], second["etapa"]),
                         (None, None, False, "inversion"))
        self.assertRegex(data["hash"], r"^[0-9a-f]{16}$")
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["errores"], [])

    def test_the_hash_covers_budget_and_milestones_but_not_the_chain(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        first = load_budget(run)["hash"]
        changed = json.loads(json.dumps(HITOS))
        changed["hitos"][0]["mes"] = 4
        write_file(run, "hitos.json", changed)
        second = load_budget(run)["hash"]
        self.assertNotEqual(first, second)
        budget = json.loads(json.dumps(PRESUPUESTO))
        budget["items"][1]["valor_unitario"] = 31000000
        write_file(run, "presupuesto.json", budget)
        third = load_budget(run)["hash"]
        self.assertNotEqual(third, second)
        chain = json.loads(json.dumps(CADENA))
        chain["objetivos"][0]["productos"][0]["actividades"][0]["costo"] = 5
        write_file(run, "cadena_valor.json", chain)
        self.assertEqual(load_budget(run)["hash"], third)

    def test_chain_without_budget_shows_the_months_but_is_not_available(self):
        _, run = make_workspace(self.ws)
        write_file(run, "cadena_valor.json", CADENA)
        data = load_budget(run)
        self.assertFalse(data["disponible"])
        self.assertIsNone(data["hash"])
        self.assertEqual([a["codigo"] for a in data["cadena_meses"]], ["1.1.1", "1.1.2"])

    def test_missing_scripts_show_the_data_without_findings_summary_or_projection(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        (self.scripts / "presupuesto_sgr.py").unlink()
        (self.scripts / "cronograma_sgr.py").unlink()
        data = load_budget(run)
        self.assertTrue(data["disponible"])
        self.assertIsNone(data["resumen"])
        self.assertIsNone(data["proyeccion"])
        self.assertEqual(data["hallazgos"], [])
        self.assertEqual(data["errores"], [])

    def test_failing_script_is_reported_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        (run / "stub_falla").write_text("", encoding="utf-8")
        data = load_budget(run)
        self.assertTrue(data["disponible"])
        self.assertIn("presupuesto ilegible", " ".join(data["errores"]))

    def test_corrupt_or_foreign_files_return_errors_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_file(run, "presupuesto.json", "{roto")
        write_file(run, "hitos.json", HITOS)
        data = load_budget(run)
        self.assertIsNone(data["presupuesto"])
        self.assertEqual(data["hitos"], HITOS["hitos"])
        self.assertIn("presupuesto.json", " ".join(data["errores"]))
        write_file(run, "presupuesto.json", PRESUPUESTO)
        write_file(run, "hitos.json", {**HITOS, "schema": "otro/v1"})
        data = load_budget(run)
        self.assertEqual(data["hitos"], [])
        self.assertIn("morfeo.hitos-sgr/v1", " ".join(data["errores"]))


class TestApprove(StubScripts):
    def test_error_findings_block_the_approval(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        write_stub(run, "stub_cronograma_findings.json",
                   [{"severity": "error", "code": "cronograma-meses-invertidos", "message": "m", "node": "1.1.1"}])
        result = approve(run)
        self.assertFalse(result["ok"])
        self.assertIn("cronograma-meses-invertidos", result["error"])
        self.assertFalse((run / "artefactos" / "sgr" / "revision.json").exists())

    def test_approval_preserves_other_keys_and_expires_when_a_file_changes(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        review = run / "artefactos" / "sgr" / "revision.json"
        others = {"cadena_valor": {"aprobado": True, "hash": "cafe", "fecha": "2026-11-18T10:00:00"},
                  "alianza_territorio": {"aprobado": True, "hash": "beef", "fecha": "2026-11-18T11:00:00"}}
        review.write_text(json.dumps(others), encoding="utf-8")
        current = load_budget(run)["hash"]
        result = approve(run, current)
        self.assertTrue(result["ok"])
        saved = json.loads(review.read_text(encoding="utf-8"))
        self.assertEqual(saved["cadena_valor"], others["cadena_valor"])
        self.assertEqual(saved["alianza_territorio"], others["alianza_territorio"])
        self.assertEqual(set(saved["presupuesto"]), {"aprobado", "hash", "fecha"})
        self.assertEqual(saved["presupuesto"]["hash"], current)
        self.assertTrue(load_budget(run)["aprobado"])

        changed = json.loads(json.dumps(HITOS))
        changed["hitos"][0]["verificacion"] = "Acta"
        write_file(run, "hitos.json", changed)
        data = load_budget(run)
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["revision"]["hash"], current)

    def test_a_stale_hash_is_refused(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        result = approve(run, "0000000000000000")
        self.assertFalse(result["ok"])
        self.assertIn("cambi", result["error"])

    def test_milestones_are_optional_but_the_budget_is_required(self):
        _, run = make_workspace(self.ws)
        write_file(run, "presupuesto.json", PRESUPUESTO)
        self.assertTrue(approve(run)["ok"])
        _, only_hitos = make_workspace(self.new_dir("ws2"))
        write_file(only_hitos, "hitos.json", HITOS)
        result = approve(only_hitos)
        self.assertFalse(result["ok"])
        self.assertIn("presupuesto.json", result["error"])
        _, empty = make_workspace(self.new_dir("ws3"))
        result = approve(empty)
        self.assertFalse(result["ok"])
        self.assertIn("fase6_4", result["error"])
        self.assertIn("presupuesto_sgr.py check", result["error"])
        _, base = make_workspace(self.new_dir("base"), flujo=None)
        write_all(base)
        self.assertFalse(approve(base)["ok"])

    def test_unreadable_milestones_block_the_approval(self):
        _, run = make_workspace(self.ws)
        write_file(run, "presupuesto.json", PRESUPUESTO)
        write_file(run, "hitos.json", "{roto")
        result = approve(run)
        self.assertFalse(result["ok"])
        self.assertIn("hitos.json", result["error"])

    def test_corrupt_review_is_never_overwritten(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        review = run / "artefactos" / "sgr" / "revision.json"
        review.write_text("{roto", encoding="utf-8")
        data = load_budget(run)
        self.assertIn("revision.json", " ".join(data["errores"]))
        self.assertFalse(approve(run, data["hash"])["ok"])
        self.assertEqual(review.read_text(encoding="utf-8"), "{roto")


class TestAdjustPrompt(StubScripts):
    def test_prompt_carries_the_note_files_agents_and_the_three_commands_in_order(self):
        _, run = make_workspace(self.ws)
        prompt = build_adjust_prompt(run, "Sube la movilidad\nal 2 %")
        self.assertIn("«Sube la movilidad al 2 %»", prompt)
        self.assertIn("presupuestador", prompt)
        self.assertIn("investigador", prompt)
        self.assertIn("proposals/run-presupuesto/artefactos/sgr/presupuesto.json", prompt)
        self.assertIn("proposals/run-presupuesto/artefactos/sgr/hitos.json", prompt)
        self.assertIn("proposals/run-presupuesto/artefactos/sgr/cadena_valor.json", prompt)
        commands = ["presupuesto_sgr.py check proposals/run-presupuesto",
                    "presupuesto_sgr.py sync-cadena proposals/run-presupuesto",
                    "cronograma_sgr.py check proposals/run-presupuesto"]
        positions = [prompt.index(c) for c in commands]
        self.assertEqual(positions, sorted(positions))
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


class TestBudgetHttpApi(StubScripts):
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
        write_stub(run, "stub_resumen.json", RESUMEN)
        base = self._serve(workspace)

        code, data = self._request(base + "/api/budget")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["run"], run.name)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["resumen"], RESUMEN)

        code, bad = self._request(base + "/api/budget/approve", {"hash": "0000000000000000"})
        self.assertEqual(code, 409)
        self.assertFalse(bad["ok"])

        code, ok = self._request(base + "/api/budget/approve", {"hash": data["hash"]})
        self.assertEqual(code, 200)
        self.assertTrue(ok["ok"])
        self.assertTrue(self._request(base + "/api/budget")[1]["aprobado"])

        code, adj = self._request(base + "/api/budget/adjust", {"nota": "Agrega una cotización"})
        self.assertEqual(code, 200)
        self.assertEqual(adj, {"ok": True, "prompt": build_adjust_prompt(run, "Agrega una cotización")})

        code, bad = self._request(base + "/api/budget/adjust", {"nota": ""})
        self.assertEqual(code, 400)
        code, bad = self._request(base + "/api/budget/adjust", raw=b"{roto")
        self.assertEqual(code, 400)
        self.assertFalse(bad["ok"])

    def test_error_findings_answer_409_on_approve(self):
        workspace, run = make_workspace(self.ws)
        write_all(run)
        write_stub(run, "stub_presupuesto_findings.json",
                   [{"severity": "error", "code": "presupuesto-tope", "message": "m", "node": ""}])
        base = self._serve(workspace)
        code, bad = self._request(base + "/api/budget/approve", {})
        self.assertEqual(code, 409)
        self.assertIn("presupuesto-tope", bad["error"])

    def test_base_flow_routes_report_unavailable(self):
        workspace, run = make_workspace(self.ws, flujo=None)
        write_all(run)
        base = self._serve(workspace)
        code, data = self._request(base + "/api/budget")
        self.assertEqual(code, 200)
        self.assertEqual((data["flujo"], data["disponible"], data["presupuesto"]), ("base", False, None))
        code, _ = self._request(base + "/api/budget/adjust", {"nota": "x"})
        self.assertEqual(code, 400)
        code, _ = self._request(base + "/api/budget/approve", {})
        self.assertEqual(code, 409)

    def test_without_active_run_the_routes_answer_404(self):
        (self.ws / "proposals").mkdir()
        base = self._serve(self.ws)
        for path, payload in (("/api/budget", None), ("/api/budget/approve", {}),
                              ("/api/budget/adjust", {"nota": "x"})):
            code, bad = self._request(base + path, payload)
            self.assertEqual(code, 404, path)
            self.assertFalse(bad["ok"])


if __name__ == "__main__":
    unittest.main()
