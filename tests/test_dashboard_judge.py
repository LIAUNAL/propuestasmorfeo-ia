"""Pestaña «Juez final» del tablero (odd/tasks/juez-sgr.md, S7 y S8)."""

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

from morfeo.core.judge import build_action_prompt, load_judge

RUBRICA = {
    "schema": "morfeo.rubrica-sgr/v1",
    "id": "conv54",
    "convocatoria": "Convocatoria 54 SGR",
    "fuente": "TdR numeral 16, Tabla 10",
    "total": 100,
    "elegibilidad": {"umbral_total": 75, "minimos": [{"criterio": "1", "minimo": 24}]},
    "criterios": [
        {"id": "1", "nombre": "Calidad técnica", "max": 40, "subcriterios": [
            {"id": "1.1", "nombre": "Coherencia", "descripcion": "…", "max": 20, "modo": "niveles",
             "niveles": [{"puntos": 20, "descriptor": "Alta"}, {"puntos": 10, "descriptor": "Media"}]},
            {"id": "1.2", "nombre": "Trayectoria", "descripcion": "…", "max": 20, "modo": "conteo",
             "regla_conteo": {"tipo": "trayectoria"}},
        ]},
        {"id": "2", "nombre": "Impacto", "max": 60, "subcriterios": [
            {"id": "2", "nombre": "Impacto", "descripcion": "…", "max": 60, "modo": "acumulable",
             "componentes": [{"id": "a", "nombre": "A", "max": 60, "descriptor": "…"}]},
        ]},
    ],
}

EVALUACION = {
    "schema": "morfeo.evaluacion-sgr-consolidada/v1",
    "ronda": 2,
    "fecha": "2026-11-19",
    "rubrica": "conv54",
    "criterios": [
        {"id": "1.1", "puntaje": 10, "componentes": None, "nivel_descriptor": "Media",
         "justificacion": "Falta la clave de actividad.", "evidencia": [{"ubicacion": "§10", "cita": "texto"}],
         "para_subir": {"puntaje_objetivo": 20, "que_falta": "Unificar la clave."}},
        {"id": "1.2", "puntaje": 15, "componentes": None, "nivel_descriptor": "", "justificacion": "Conteo.",
         "evidencia": [], "para_subir": None},
        {"id": "2", "puntaje": 45, "componentes": {"a": 45}, "nivel_descriptor": "", "justificacion": "Bien.",
         "evidencia": [], "para_subir": None},
    ],
    "alertas": [{"id": "A1", "severidad": "error", "tipo": "inconsistencia", "mensaje": "Totales distintos",
                 "ubicacion": "§29", "criterios": ["2"]}],
    "acciones": [
        {"id": "X1", "criterios": ["1.1"], "agente": "redactor", "secciones": ["§10", "§14"],
         "instruccion": "Usa la clave OE.Producto.Actividad en la metodología y el cronograma.",
         "impacto_estimado": 10, "prioridad": 1},
        {"id": "X2", "criterios": ["2"], "agente": "usuario", "secciones": [],
         "instruccion": "Aporta las cotizaciones.", "impacto_estimado": 3, "prioridad": 2},
    ],
    "concepto": "Concepto.",
    "recomienda": False,
    "subtotales": {"1": 25, "2": 45},
    "total": 70,
    "elegible": False,
    "motivos_no_elegible": ["Total 70 < 75"],
    "incompleto": False,
    "verificaciones": [{"id": "V1", "severidad": "advertencia", "tipo": "forma", "mensaje": "Título distinto",
                        "ubicacion": "§1", "criterios": []}],
    "historial": [{"ronda": 1, "fecha": "2026-11-18", "total": 62, "elegible": False},
                  {"ronda": 2, "fecha": "2026-11-19", "total": 70, "elegible": False}],
    "errores_validacion": [],
}


def make_workspace(tmp: Path, flujo: str | None = "sgr") -> tuple[Path, Path]:
    workspace = Path(tmp)
    if flujo:
        (workspace / ".morfeo").mkdir()
        (workspace / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = workspace / "proposals" / "run-juez"
    (run / "artefactos").mkdir(parents=True)
    (workspace / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
    return workspace, run


def write_judge(run: Path, evaluacion: dict | str | None = EVALUACION, rubrica: dict | str | None = RUBRICA) -> None:
    juez = run / "artefactos" / "juez"
    juez.mkdir(parents=True, exist_ok=True)
    for name, data in (("evaluacion.json", evaluacion), ("rubrica.json", rubrica)):
        if data is None:
            continue
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        (juez / name).write_text(text, encoding="utf-8")


class TestLoadJudge(unittest.TestCase):
    def test_base_flow_is_not_available_and_carries_no_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp), flujo=None)
            write_judge(run)
            data = load_judge(run)
            self.assertEqual(data["flujo"], "base")
            self.assertFalse(data["disponible"])
            self.assertIsNone(data["evaluacion"])
            self.assertIsNone(data["rubrica"])
            self.assertEqual(data["errores"], [])

    def test_sgr_without_evaluation_is_not_available_and_has_no_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            data = load_judge(run)
            self.assertEqual(data["flujo"], "sgr")
            self.assertFalse(data["disponible"])
            self.assertIsNone(data["evaluacion"])
            self.assertIsNone(data["rubrica"])
            self.assertEqual(data["errores"], [])

    def test_sgr_with_evaluation_returns_it_with_the_rubric_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            write_judge(run)
            data = load_judge(run)
            self.assertTrue(data["disponible"])
            self.assertEqual(data["evaluacion"]["total"], 70)
            self.assertEqual(data["evaluacion"]["historial"][0]["total"], 62)
            rub = data["rubrica"]
            self.assertEqual(rub["id"], "conv54")
            self.assertEqual(rub["convocatoria"], "Convocatoria 54 SGR")
            self.assertEqual(rub["umbral_total"], 75)
            self.assertEqual(rub["minimos"], [{"criterio": "1", "minimo": 24}])
            self.assertEqual([c["id"] for c in rub["criterios"]], ["1", "2"])
            self.assertEqual(rub["criterios"][0]["subcriterios"][1],
                             {"id": "1.2", "nombre": "Trayectoria", "max": 20, "modo": "conteo"})
            self.assertEqual(data["errores"], [])

    def test_corrupt_json_returns_errors_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            write_judge(run, evaluacion="{no es json", rubrica="[1, 2]")
            data = load_judge(run)
            self.assertFalse(data["disponible"])
            self.assertIsNone(data["evaluacion"])
            self.assertIsNone(data["rubrica"])
            joined = " ".join(data["errores"])
            self.assertIn("evaluacion.json", joined)
            self.assertIn("rubrica.json", joined)

    def test_an_evaluation_with_another_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, run = make_workspace(Path(tmp))
            write_judge(run, evaluacion={**EVALUACION, "schema": "morfeo.evaluacion-sgr/v1"})
            data = load_judge(run)
            self.assertFalse(data["disponible"])
            self.assertIn("morfeo.evaluacion-sgr-consolidada/v1", " ".join(data["errores"]))


class TestBuildActionPrompt(unittest.TestCase):
    def test_prompt_names_agent_sections_criteria_instruction_and_asks_to_rerun(self):
        prompt = build_action_prompt(EVALUACION, "X1")
        self.assertIn("redactor", prompt)
        self.assertIn("§10", prompt)
        self.assertIn("§14", prompt)
        self.assertIn("1.1", prompt)
        self.assertIn("OE.Producto.Actividad", prompt)
        self.assertIn("grant-flow-auditor", prompt)
        self.assertTrue(prompt.rstrip().endswith("/propuesta-juez."), prompt)
        self.assertNotIn("\n", prompt)

    def test_user_actions_ask_the_assistant_to_guide_the_user(self):
        prompt = build_action_prompt(EVALUACION, "X2")
        self.assertIn("usuario", prompt)
        self.assertIn("cotizaciones", prompt)
        self.assertIn("/propuesta-juez", prompt)

    def test_unknown_action_raises_value_error(self):
        with self.assertRaises(ValueError):
            build_action_prompt(EVALUACION, "NOPE")
        with self.assertRaises(ValueError):
            build_action_prompt({}, "X1")


class TestJudgeHttpApi(unittest.TestCase):
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

    def test_get_send_and_run_over_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, run = make_workspace(Path(tmp))
            write_judge(run)
            base = self._serve(workspace)

            code, data = self._request(base + "/api/judge")
            self.assertEqual(code, 200)
            self.assertTrue(data["ok"])
            self.assertEqual(data["run"], run.name)
            self.assertEqual(data["flujo"], "sgr")
            self.assertTrue(data["disponible"])
            self.assertEqual(data["evaluacion"]["total"], 70)

            code, sent = self._request(base + "/api/judge/send", {"accion_id": "X1"})
            self.assertEqual(code, 200)
            self.assertTrue(sent["ok"])
            self.assertEqual(sent["prompt"], build_action_prompt(EVALUACION, "X1",
                                                                 fuente=f"proposals/{run.name}/artefactos/juez/evaluacion.json"))

            code, bad = self._request(base + "/api/judge/send", {"accion_id": "NOPE"})
            self.assertEqual(code, 400)
            self.assertFalse(bad["ok"])
            self.assertIn("NOPE", bad["error"])

            code, bad = self._request(base + "/api/judge/send", raw=b"{roto")
            self.assertEqual(code, 400)
            self.assertFalse(bad["ok"])

            code, ran = self._request(base + "/api/judge/run", {})
            self.assertEqual(code, 200)
            self.assertEqual(ran, {"ok": True, "prompt": "/propuesta-juez"})

    def test_send_without_evaluation_is_a_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _ = make_workspace(Path(tmp))
            base = self._serve(workspace)
            code, bad = self._request(base + "/api/judge/send", {"accion_id": "X1"})
            self.assertEqual(code, 409)
            self.assertFalse(bad["ok"])

    def test_without_active_run_the_routes_answer_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "proposals").mkdir()
            base = self._serve(workspace)
            for path, payload in (("/api/judge", None), ("/api/judge/send", {"accion_id": "X1"}),
                                  ("/api/judge/run", {})):
                code, bad = self._request(base + path, payload)
                self.assertEqual(code, 404, path)
                self.assertFalse(bad["ok"])


if __name__ == "__main__":
    unittest.main()
