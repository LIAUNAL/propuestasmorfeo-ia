"""Server-built display text of the JSON API in English (S2 of
odd/tasks/idioma-tablero-traduccion.md, task T3).

Port of papersmith-ai's ``LocalizeMiddleware`` with the direction reversed:
Morfeo's server writes its labels in Spanish, and a request with ``?lang=en``
gets the allowlisted display fields (``localize.DISPLAY_FIELDS``) translated
through ``static/i18n/server-en.json``. Everything else (ids, states, commands,
file names, what an agent wrote) is untouched, and a Spanish request answers
the very bytes it answered before.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from morfeo.core import board
from morfeo.core.pipeline_units import GATE_INFO, PIPELINE_UNITS
from morfeo.core.status import SECTION_TITLES
from morfeo.dashboard import localize
from morfeo.dashboard.server import MorfeoDashboardHandler

CATALOGUE = json.loads(localize.CATALOGUE.read_text(encoding="utf-8"))
SPANISH_ACCENTS = re.compile(r"[áéíóúñÁÉÍÓÚÑ¿¡]")


def write_run(workspace: Path) -> Path:
    """A workspace with an active run, its control block and gate table."""
    (workspace / ".morfeo").mkdir(parents=True, exist_ok=True)
    (workspace / ".morfeo" / "config.json").write_text('{"flujo": "base"}', encoding="utf-8")
    run = workspace / "proposals" / "2026-01-demo"
    (run / "artefactos").mkdir(parents=True)
    (run / "redaccion" / "sections").mkdir(parents=True)
    (workspace / "proposals" / ".current-run").write_text("2026-01-demo\n", encoding="utf-8")
    (run / "artefactos" / "insumos.md").write_text("# Insumos\n", encoding="utf-8")
    (run / "redaccion" / "sections" / "06_objetivo_general.tex").write_text("Texto.\n", encoding="utf-8")
    (run / "artefactos" / "estado_propuesta.md").write_text(
        "# Estado\n\n| Gate | Estado |\n|---|---|\n| G0.5 | PASS |\n| G1a | PENDING |\n\n"
        "## Control de ejecución\n\n- mode: stepped\n- next_step: fase1a\n"
        "- next_command: /propuesta-continuar\n- last_completed: fase0\n- intake_complete: true\n",
        encoding="utf-8",
    )
    return run


class Server:
    def __init__(self, test: unittest.TestCase, workspace: Path) -> None:
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": workspace})
        handler.log_message = lambda *a, **k: None
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        test.addCleanup(self.httpd.server_close)
        test.addCleanup(self.httpd.shutdown)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def get(self, path: str) -> bytes:
        with urllib.request.urlopen(self.base + path) as res:
            return res.read()

    def json(self, path: str) -> dict:
        return json.loads(self.get(path))


class CatalogueTests(unittest.TestCase):
    def test_every_framework_label_of_the_pipeline_has_an_english_entry(self) -> None:
        texts = {value for gate in GATE_INFO.values() for value in gate.values()}
        texts |= {unit[key] for unit in PIPELINE_UNITS for key in ("name", "desc") if unit.get(key)}
        texts |= set(SECTION_TITLES.values())
        texts |= {label for _, label, _ in board.GENERATORS}
        missing = sorted(text for text in texts if localize.lookup(text) is None)
        self.assertEqual(missing, [])

    def test_the_english_is_english_and_keeps_the_machine_tokens(self) -> None:
        placeholder = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
        quoted = {"El alcance debe ser «proyecto» o «banco».", "Fase {n}/{total} · {name}"}
        for spanish, english in CATALOGUE.items():
            with self.subTest(spanish=spanish):
                self.assertTrue(english.strip())
                self.assertEqual(set(placeholder.findall(spanish)), set(placeholder.findall(english)))
                if spanish not in quoted:
                    self.assertIsNone(SPANISH_ACCENTS.search(english), english)
                for token in re.findall(r"`[^`]+`|\b\w+_sgr\.py\b|§\d+|artefactos/[\w/.*-]+", spanish):
                    self.assertIn(token, english)

    def test_templates_fill_their_values_and_translate_a_known_value(self) -> None:
        self.assertEqual(localize.lookup("Compuerta G1a en PASS"), "Gate G1a at PASS")
        self.assertEqual(localize.lookup("Fase 1b SGR"), "Phase 1b SGR")
        self.assertEqual(localize.lookup("Fase 2/5 · Fuentes fijas"), "Phase 2/5 · Fixed sources")
        self.assertEqual(localize.lookup("redaccion/sections/04_estado_arte.tex existe"),
                         "redaccion/sections/04_estado_arte.tex exists")
        self.assertIsNone(localize.lookup("Texto que escribió un agente"))
        self.assertEqual(localize.translate("Texto que escribió un agente", "en"), "Texto que escribió un agente")
        self.assertEqual(localize.translate("Presupuesto", "es"), "Presupuesto")


class LocalizeTests(unittest.TestCase):
    def test_only_the_allowlisted_fields_are_translated(self) -> None:
        payload = {
            "gates": [{"id": "G0.5", "name": "Ajuste de Guía al TDR", "phase": "Fase 0", "status": "PASS",
                       "reviewer": "Usuario", "criteria": "Tabla de secciones del TDR aprobada y ajustada."}],
            "pipeline_units": [{"id": "fase6_4", "name": "Presupuesto", "kind": "step", "gate": "G6.4",
                                "agents": ["presupuestador"], "artifacts": ["Presupuesto"]}],
            "unit_progress": {"fase1a": {"state": "partial", "missing": ["Compuerta G1a en PASS"],
                                         "checks": [{"id": "gate", "label": "Compuerta G1a en PASS", "ok": False}]}},
            "run_details": {"title": "Presupuesto", "idea": "Presupuesto"},
            "control": {"next_step": "fase1a", "next_command": "/propuesta-continuar"},
            "error": "No hay una corrida activa seleccionada",
        }
        out = localize.localize_response("/api/status?lang=en", payload)
        self.assertEqual(out["gates"][0], {"id": "G0.5", "name": "Guide Adjusted to the Call Terms", "phase": "Phase 0",
                                           "status": "PASS", "reviewer": "User",
                                           "criteria": "Call terms section table approved and adjusted."})
        self.assertEqual(out["pipeline_units"][0]["name"], "Budget")
        # Machine values and project data equal to a catalogue entry stay as they are.
        self.assertEqual(out["pipeline_units"][0]["artifacts"], ["Presupuesto"])
        self.assertEqual(out["pipeline_units"][0]["agents"], ["presupuestador"])
        self.assertEqual(out["run_details"], {"title": "Presupuesto", "idea": "Presupuesto"})
        self.assertEqual(out["control"], payload["control"])
        self.assertEqual(out["unit_progress"]["fase1a"]["missing"], ["Gate G1a at PASS"])
        self.assertEqual(out["unit_progress"]["fase1a"]["checks"][0],
                         {"id": "gate", "label": "Gate G1a at PASS", "ok": False})
        self.assertEqual(out["unit_progress"]["fase1a"]["state"], "partial")
        self.assertEqual(out["error"], "No active run is selected")

    def test_spanish_and_unknown_languages_get_the_payload_itself(self) -> None:
        payload = {"gates": [{"name": "Ajuste de Guía al TDR"}], "error": "JSON payload inválido"}
        for path in ("/api/status", "/api/status?lang=es", "/api/status?lang=fr", "/api/status?x=1"):
            with self.subTest(path=path):
                self.assertIs(localize.localize_response(path, payload), payload)

    def test_a_route_without_display_fields_only_translates_its_messages(self) -> None:
        payload = {"ok": False, "error": "JSON payload inválido", "name": "Presupuesto"}
        out = localize.localize_response("/api/budget/approve?lang=en", payload)
        self.assertEqual(out, {"ok": False, "error": "Invalid JSON payload", "name": "Presupuesto"})


class ServingTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = Path(tmp.name)
        write_run(self.workspace)
        board.forget(self.workspace)
        self.addCleanup(board.forget, self.workspace)
        self.server = Server(self, self.workspace)

    def test_status_in_english_translates_gates_units_checks_and_section_titles(self) -> None:
        es = self.server.json("/api/status")
        en = self.server.json("/api/status?lang=en")
        gate = next(g for g in en["gates"] if g["id"] == "G0.5")
        self.assertEqual(gate["name"], "Guide Adjusted to the Call Terms")
        self.assertEqual(gate["phase"], "Phase 0")
        unit = next(u for u in en["pipeline_units"] if u["id"] == "fase6_4")
        self.assertEqual(unit["name"], "Budget")
        self.assertIn("Gate G1a at PASS", en["unit_progress"]["fase1a"]["missing"])
        section = next(s for s in en["sections"] if s["id"] == "06_objetivo_general")
        self.assertEqual(section["title"], "§6 General objective")
        # Same shape, same machine values.
        self.assertEqual([g["id"] for g in en["gates"]], [g["id"] for g in es["gates"]])
        self.assertEqual([g["status"] for g in en["gates"]], [g["status"] for g in es["gates"]])
        self.assertEqual({k: v["state"] for k, v in en["unit_progress"].items()},
                         {k: v["state"] for k, v in es["unit_progress"].items()})
        self.assertEqual(en["control"], es["control"])
        self.assertEqual(en["active_run"], es["active_run"])

    def test_a_spanish_request_answers_the_same_bytes_with_or_without_lang(self) -> None:
        for route in ("/api/status", "/api/board/summary", "/api/trees", "/api/novedad",
                      "/api/judge-avance?etapa=arbol", "/api/convocatorias/progreso"):
            with self.subTest(route=route):
                joiner = "&" if "?" in route else "?"
                self.assertEqual(self.server.get(route), self.server.get(route + joiner + "lang=es"))

    def test_board_summary_in_english(self) -> None:
        en = self.server.json("/api/board/summary?lang=en")
        self.assertEqual(en["summary"]["current"]["name"], "Early scoping and subproblems")
        self.assertIn("Gate G1a at PASS", en["summary"]["missing"])
        self.assertEqual(en["summary"]["current"]["id"], "fase1a")

    def test_trees_in_english_translate_the_framework_labels_only(self) -> None:
        specs = self.workspace / "proposals" / "2026-01-demo" / "redaccion" / "specs"
        specs.mkdir(parents=True)
        (specs / "arbol_problemas.spec.json").write_text(json.dumps({
            "groups": [{"id": "c1", "title": "PROBLEMA CENTRAL", "causes": [{"id": "i1", "text": "Causa"}]}],
        }), encoding="utf-8")
        en = self.server.json("/api/trees?lang=en")
        # A title an agent wrote stays as it is, even when it equals a label.
        self.assertEqual(en["problem"]["tree"]["groups"][0]["title"], "PROBLEMA CENTRAL")
        es = self.server.json("/api/trees")
        self.assertEqual(en["problem"]["tree"]["trunk"]["label"], "CENTRAL PROBLEM")
        self.assertEqual(en["objectives"]["tree"]["crown"]["label"], "ULTIMATE END")
        self.assertEqual(en["run"], es["run"])

    def test_the_presentation_is_written_in_the_requested_language(self) -> None:
        es = self.server.get("/presentacion").decode("utf-8")
        en = self.server.get("/presentacion?lang=en").decode("utf-8")
        self.assertEqual(es, self.server.get("/presentacion?lang=es").decode("utf-8"))
        self.assertIn('<html lang="es">', es)
        self.assertIn('<html lang="en">', en)
        self.assertIn('aria-label="Diapositiva anterior"', es)
        self.assertIn('aria-label="Previous slide"', en)
        self.assertIn("2. Alliance</button>", en)
        self.assertIn("[Title to be defined]", en)
        self.assertNotIn("Metodología", en)

    def test_the_papers_graph_is_drawn_again_with_english_chrome(self) -> None:
        fixtures = Path(__file__).resolve().parent / "fixtures" / "constelacion"
        run = self.workspace / "proposals" / "2026-01-demo"
        scoping = run / "artefactos" / "scoping"
        scoping.mkdir(parents=True)
        (scoping / "atlas.json").write_bytes((fixtures / "atlas.json").read_bytes())
        (scoping / "papers").mkdir()
        for paper in (fixtures / "papers").glob("*.md"):
            (scoping / "papers" / paper.name).write_bytes(paper.read_bytes())
        (run / "grafos").mkdir()
        spanish = "<!DOCTYPE html>\n<html lang=\"es\"><title>Constelación SOTA</title></html>\n".encode("utf-8")
        (run / "grafos" / "papers-graph.html").write_bytes(spanish)
        self.assertEqual(self.server.get("/api/graph/papers"), spanish, "Spanish serves the page on disk")
        en = self.server.get("/api/graph/papers?lang=en").decode("utf-8")
        self.assertIn('<html lang="en">', en)
        self.assertIn("<title>SOTA constellation</title>", en)
        self.assertIn('id="atlas-data"', en)
        # Without an atlas the English request still gets the page on disk.
        (scoping / "atlas.json").unlink()
        self.assertEqual(self.server.get("/api/graph/papers?lang=en"), spanish)

    def test_a_missing_graph_says_so_in_english(self) -> None:
        en = self.server.get("/api/graph/nope?lang=en").decode("utf-8")
        self.assertIn("Graph unavailable for this run", en)
        self.assertIn("Grafo no disponible para esta corrida", self.server.get("/api/graph/nope").decode("utf-8"))

    def test_errors_in_english(self) -> None:
        req = urllib.request.Request(self.server.base + "/api/trees/feedback?lang=en", data=b"{nope",
                                     method="POST", headers={"Content-Type": "application/json",
                                                             "Origin": self.server.base})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req)
        self.assertEqual(json.loads(caught.exception.read())["error"], "Invalid JSON payload")


if __name__ == "__main__":
    unittest.main()
