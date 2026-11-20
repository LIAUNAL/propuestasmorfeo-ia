"""SGR gate on the direct causes, right after G1a (odd/tasks/sgr-figuras-estructura.md, S7).

After the 3 early subproblems, the SGR flow stops at GCausas: the operator
either fits them to the 3 template causes of an applied-AI SGR project (data
collection, platform and models, appropriation) or asks for the exploratory
mode, where the investigador proposes 3 root causes from the idea and the
subproblems. The base flow never sees this unit.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from test_trees import SPEC, make_run  # noqa: E402
from morfeo.core.pipeline_units import canonical_gates, normalise_gate, units_for_flujo  # noqa: E402
from morfeo.core.status import parse_gates_info  # noqa: E402


def _ids(units):
    return [u["id"] for u in units]


class Units(unittest.TestCase):
    def test_sgr_runs_the_causes_gate_between_g1a_and_the_trees(self) -> None:
        units = units_for_flujo("sgr")
        ids = _ids(units)
        self.assertLess(ids.index("fase1a"), ids.index("fase1a_sgr"))
        self.assertLess(ids.index("fase1a_sgr"), ids.index("fase1b"))
        nxt = {u["id"]: u.get("next") for u in units}
        self.assertEqual(nxt["fase1a"], "fase1a_sgr")
        self.assertEqual(nxt["fase1a_sgr"], "fase1b")
        unit = next(u for u in units if u["id"] == "fase1a_sgr")
        self.assertEqual(unit["gate"], "GCausas")
        self.assertIn("artefactos/arboles/causas_directas.md", unit["artifacts"])
        self.assertIn("GCausas", {g["id"] for g in canonical_gates("sgr")})

    def test_base_flow_goes_straight_from_g1a_to_the_trees(self) -> None:
        units = units_for_flujo("base")
        self.assertNotIn("fase1a_sgr", _ids(units))
        self.assertEqual({u["id"]: u.get("next") for u in units}["fase1a"], "fase1b")
        self.assertNotIn("GCausas", {g["id"] for g in canonical_gates("base")})

    def test_prose_alias_resolves(self) -> None:
        self.assertEqual(normalise_gate("G causas"), "GCausas")
        self.assertEqual(normalise_gate("G territorio"), "GTerritorio")
        self.assertEqual(normalise_gate("G componentes"), "GComponentes")
        self.assertEqual(normalise_gate("G productos"), "GProductos")

    def test_sgr_runs_the_alliance_gate_between_the_trees_and_the_corpus(self) -> None:
        units = units_for_flujo("sgr")
        nxt = {u["id"]: u.get("next") for u in units}
        self.assertEqual(nxt["fase1b"], "fase1b_sgr")
        self.assertEqual(nxt["fase1b_sgr"], "fase1c")
        unit = next(u for u in units if u["id"] == "fase1b_sgr")
        self.assertEqual(unit["gate"], "GTerritorio")

    def test_base_flow_goes_straight_from_the_trees_to_the_corpus(self) -> None:
        units = units_for_flujo("base")
        self.assertNotIn("fase1b_sgr", _ids(units))
        self.assertEqual({u["id"]: u.get("next") for u in units}["fase1b"], "fase1c")
        self.assertNotIn("GTerritorio", {g["id"] for g in canonical_gates("base")})

    def test_sgr_runs_the_components_gate_between_the_methodology_and_the_results(self) -> None:
        units = units_for_flujo("sgr")
        nxt = {u["id"]: u.get("next") for u in units}
        self.assertEqual(nxt["fase5_5"], "fase5_5_sgr")
        self.assertEqual(nxt["fase5_5_sgr"], "fase6")
        unit = next(u for u in units if u["id"] == "fase5_5_sgr")
        self.assertEqual(unit["gate"], "GComponentes")
        self.assertIn("artefactos/sgr/componentes.json", unit["artifacts"])

    def test_sgr_runs_the_products_gate_between_the_team_and_the_methodology(self) -> None:
        units = units_for_flujo("sgr")
        nxt = {u["id"]: u.get("next") for u in units}
        self.assertEqual(nxt["fase5"], "fase5_sgr")
        self.assertEqual(nxt["fase5_sgr"], "fase5_5")
        unit = next(u for u in units if u["id"] == "fase5_sgr")
        self.assertEqual(unit["gate"], "GProductos")
        self.assertIn("artefactos/sgr/productos.json", unit["artifacts"])

    def test_base_flow_goes_straight_from_the_team_to_the_methodology(self) -> None:
        units = units_for_flujo("base")
        self.assertNotIn("fase5_sgr", _ids(units))
        self.assertEqual({u["id"]: u.get("next") for u in units}["fase5"], "fase5_5")
        self.assertNotIn("GProductos", {g["id"] for g in canonical_gates("base")})

    def test_base_flow_goes_straight_from_the_methodology_to_the_results(self) -> None:
        units = units_for_flujo("base")
        self.assertNotIn("fase5_5_sgr", _ids(units))
        self.assertEqual({u["id"]: u.get("next") for u in units}["fase5_5"], "fase6")
        self.assertNotIn("GComponentes", {g["id"] for g in canonical_gates("base")})


class GateStatus(unittest.TestCase):
    def status(self, rows: str) -> dict[str, str]:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "artefactos").mkdir()
        (tmp / "artefactos" / "estado_propuesta.md").write_text(f"| Compuerta | Estado |\n|---|---|\n{rows}")
        return {g["id"]: g["status"] for g in parse_gates_info(tmp, "sgr")}

    def test_approving_g1a_does_not_approve_the_causes_gate(self) -> None:
        status = self.status("| G1a | APROBADA |\n")
        self.assertEqual(status["G1a"], "PASS")
        self.assertEqual(status["GCausas"], "PENDING")

    def test_approving_g4_does_not_approve_the_value_chain_gate(self) -> None:
        status = self.status("| G4 | APROBADA |\n")
        self.assertEqual(status["G4"], "PASS")
        self.assertEqual(status["G4.cv"], "PENDING")

    def test_the_value_chain_gate_does_not_approve_g4(self) -> None:
        status = self.status("| G4.cv | APROBADA |\n")
        self.assertEqual(status["G4.cv"], "PASS")
        self.assertEqual(status["G4"], "PENDING")

    def test_a_gate_with_a_suffix_is_not_its_prefix_gate(self) -> None:
        status = self.status("| G6.4 | APROBADA |\n| G1a | APROBADA |\n")
        self.assertEqual(status["G6.4"], "PASS")
        self.assertEqual(status["G1a"], "PASS")
        self.assertEqual(status["G1"], "PENDING")

    def test_a_gate_followed_by_a_label_still_matches(self) -> None:
        status = self.status("| G4 (objetivos) | APROBADA |\n")
        self.assertEqual(status["G4"], "PASS")
        self.assertEqual(status["G4.cv"], "PENDING")

    def test_approving_g1b_does_not_approve_the_alliance_gate(self) -> None:
        status = self.status("| G1b | APROBADA |\n")
        self.assertEqual(status["G1b"], "PASS")
        self.assertEqual(status["GTerritorio"], "PENDING")

    def test_the_alliance_gate_is_read_on_its_own(self) -> None:
        status = self.status("| G1b | APROBADA |\n| GTerritorio | APROBADA |\n")
        self.assertEqual(status["GTerritorio"], "PASS")
        self.assertEqual(status["G1c"], "PENDING")

    def test_approving_g5_5_does_not_approve_the_components_gate(self) -> None:
        status = self.status("| G5.5 | APROBADA |\n")
        self.assertEqual(status["G5.5"], "PASS")
        self.assertEqual(status["GComponentes"], "PENDING")

    def test_the_components_gate_is_read_on_its_own(self) -> None:
        status = self.status("| G5.5 | APROBADA |\n| GComponentes | APROBADA |\n")
        self.assertEqual(status["GComponentes"], "PASS")
        self.assertEqual(status["G6.4"], "PENDING")

    def test_approving_g5_does_not_approve_the_products_gate(self) -> None:
        status = self.status("| G5 | APROBADA |\n")
        self.assertEqual(status["G5"], "PASS")
        self.assertEqual(status["GProductos"], "PENDING")

    def test_the_products_gate_is_read_on_its_own(self) -> None:
        status = self.status("| G5 | APROBADA |\n| GProductos | APROBADA |\n")
        self.assertEqual(status["GProductos"], "PASS")
        self.assertEqual(status["G5.5"], "PENDING")

    def test_the_causes_gate_is_read_on_its_own(self) -> None:
        status = self.status("| G1a | APROBADA |\n| GCausas | APROBADA |\n")
        self.assertEqual(status["GCausas"], "PASS")
        self.assertEqual(status["G1b"], "PENDING")


class CauseMagnitude(unittest.TestCase):
    """Guía SGR §3: direct causes and direct effects carry their magnitude too."""

    def codes(self, spec: dict, flujo: str) -> dict[str, list[str]]:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        run = make_run(tmp, spec)
        out = subprocess.run([sys.executable, str(REPO / "scripts" / "check_run.py"), str(run), "--json",
                              "--flujo", flujo], capture_output=True, text=True)
        found: dict[str, list[str]] = {}
        for f in json.loads(out.stdout)["findings"]:
            found.setdefault(f["code"], []).append(f["severity"])
        return found

    def test_sgr_warns_for_each_cause_and_effect_without_magnitude(self) -> None:
        found = self.codes(SPEC, "sgr")
        self.assertEqual(found.get("sgr-causa-sin-magnitud"), ["warning", "warning"])
        self.assertEqual(found.get("sgr-efecto-sin-magnitud"), ["warning"])

    def test_sgr_magnitudes_present_are_clean(self) -> None:
        spec = json.loads(json.dumps(SPEC))
        m = {"indicador": "Tasa", "valor": "10 %", "fuente": "SPADIES"}
        for node in spec["groups"] + spec["branches"]:
            node["magnitude"] = m
        found = self.codes(spec, "sgr")
        self.assertNotIn("sgr-causa-sin-magnitud", found)
        self.assertNotIn("sgr-efecto-sin-magnitud", found)

    def test_sgr_magnitude_without_value_still_warns(self) -> None:
        spec = json.loads(json.dumps(SPEC))
        for node in spec["groups"] + spec["branches"]:
            node["magnitude"] = {"indicador": "Tasa", "fuente": "SPADIES"}
        found = self.codes(spec, "sgr")
        self.assertEqual(found.get("sgr-causa-sin-magnitud"), ["warning", "warning"])
        self.assertEqual(found.get("sgr-efecto-sin-magnitud"), ["warning"])

    def test_sgr_warns_when_a_cause_reuses_an_effect_or_trunk_indicator(self) -> None:
        spec = json.loads(json.dumps(SPEC))
        health = {"indicador": "Prevalencia de TEPT en estudiantes", "valor": "18 %", "fuente": "Tamizaje 2026"}
        spec["trunk"]["magnitude"] = health
        spec["groups"][0]["magnitude"] = {"indicador": " prevalencia de TEPT en  estudiantes", "valor": "18 %",
                                          "fuente": "Tamizaje 2026"}
        spec["groups"][1]["magnitude"] = {"indicador": "Tasa de deserción", "valor": "9 %", "fuente": "SPADIES"}
        spec["branches"][0]["magnitude"] = {"indicador": "Tasa de deserción", "valor": "9 %", "fuente": "SPADIES"}
        found = self.codes(spec, "sgr")
        self.assertEqual(found.get("sgr-magnitud-repetida"), ["warning", "warning"])

    def test_distinct_indicators_do_not_warn(self) -> None:
        spec = json.loads(json.dumps(SPEC))
        spec["trunk"]["magnitude"] = {"indicador": "Prevalencia de TEPT", "valor": "18 %", "fuente": "Tamizaje"}
        spec["groups"][0]["magnitude"] = {"indicador": "Cobertura de información", "valor": "20 %", "fuente": "SIVIGILA"}
        spec["groups"][1]["magnitude"] = {"indicador": "Profesionales por mil", "valor": "0,4", "fuente": "REPS"}
        spec["branches"][0]["magnitude"] = {"indicador": "Tasa de deserción", "valor": "9 %", "fuente": "SPADIES"}
        self.assertNotIn("sgr-magnitud-repetida", self.codes(spec, "sgr"))
        spec["groups"][1]["magnitude"] = spec["branches"][0]["magnitude"]
        self.assertNotIn("sgr-magnitud-repetida", self.codes(spec, "base"))

    def test_base_flow_keeps_cause_magnitude_optional(self) -> None:
        found = self.codes(SPEC, "base")
        self.assertNotIn("sgr-causa-sin-magnitud", found)
        self.assertNotIn("sgr-efecto-sin-magnitud", found)


class InFlightRuns(unittest.TestCase):
    """An SGR run that passed G1a before GCausas existed shows it as skipped."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        (self.repo / ".morfeo").mkdir()
        (self.repo / ".morfeo" / "config.json").write_text(json.dumps({"flujo": "sgr"}))
        self.run = self.repo / "proposals" / "2026-01-demo"
        (self.run / "artefactos" / "pipeline").mkdir(parents=True)
        (self.run / "redaccion" / "sections").mkdir(parents=True)
        (self.repo / "proposals" / ".current-run").write_text("2026-01-demo\n")

    def progress(self, next_step: str, estado_rows: str = "", unit: str = "fase1a_sgr") -> dict:
        from morfeo.core.status import get_project_status

        (self.run / "artefactos" / "estado_propuesta.md").write_text(
            "## Control de ejecución\n\n- mode: stepped\n"
            f"- next_step: {next_step}\n- last_completed: fase1a\n- intake_complete: true\n\n{estado_rows}")
        return get_project_status(self.repo, force_refresh=True)["unit_progress"][unit]

    def test_run_already_past_g1a_skips_the_gate(self) -> None:
        self.assertEqual(self.progress("fase1b", "| G1a | APROBADA |\n")["state"], "skipped")

    def test_run_at_the_gate_keeps_it_pending(self) -> None:
        self.assertEqual(self.progress("fase1a_sgr", "| G1a | APROBADA |\n")["state"], "pending")

    def test_gate_done_with_its_file_is_verified(self) -> None:
        arboles = self.run / "artefactos" / "arboles"
        arboles.mkdir(parents=True)
        (arboles / "causas_directas.md").write_text("| causa |")
        self.assertEqual(self.progress("fase1b", "| G1a | APROBADA |\n| GCausas | APROBADA |\n")["state"], "verified")

    def test_run_already_past_g4_skips_the_value_chain_gate(self) -> None:
        state = self.progress("fase5", "| G4 | APROBADA |\n", unit="fase4_sgr")["state"]
        self.assertEqual(state, "skipped")

    def test_run_at_the_value_chain_gate_keeps_it_pending(self) -> None:
        state = self.progress("fase4_sgr", "| G4 | APROBADA |\n", unit="fase4_sgr")["state"]
        self.assertEqual(state, "pending")

    def test_run_already_past_g1b_skips_the_alliance_gate(self) -> None:
        for next_step in ("fase1c", "fase1"):
            with self.subTest(next_step=next_step):
                state = self.progress(next_step, "| G1b | APROBADA |\n", unit="fase1b_sgr")["state"]
                self.assertEqual(state, "skipped")

    def test_run_at_the_alliance_gate_keeps_it_pending(self) -> None:
        state = self.progress("fase1b_sgr", "| G1b | APROBADA |\n", unit="fase1b_sgr")["state"]
        self.assertEqual(state, "pending")

    def test_past_run_with_one_alliance_file_is_not_skipped(self) -> None:
        sgr = self.run / "artefactos" / "sgr"
        sgr.mkdir(parents=True)
        (sgr / "alianza.json").write_text("{}")
        state = self.progress("fase1c", "| G1b | APROBADA |\n", unit="fase1b_sgr")["state"]
        self.assertEqual(state, "partial")

    def test_alliance_gate_done_with_both_files_is_verified(self) -> None:
        sgr = self.run / "artefactos" / "sgr"
        sgr.mkdir(parents=True)
        (sgr / "alianza.json").write_text("{}")
        (sgr / "territorio.json").write_text("{}")
        rows = "| G1b | APROBADA |\n| GTerritorio | APROBADA |\n"
        self.assertEqual(self.progress("fase1c", rows, unit="fase1b_sgr")["state"], "verified")

    def test_run_already_past_g5_5_skips_the_components_gate(self) -> None:
        for next_step in ("fase6", "fase6_4"):
            with self.subTest(next_step=next_step):
                state = self.progress(next_step, "| G5.5 | APROBADA |\n", unit="fase5_5_sgr")["state"]
                self.assertEqual(state, "skipped")

    def test_run_at_the_components_gate_keeps_it_pending(self) -> None:
        state = self.progress("fase5_5_sgr", "| G5.5 | APROBADA |\n", unit="fase5_5_sgr")["state"]
        self.assertEqual(state, "pending")

    def test_past_run_with_the_components_file_is_not_skipped(self) -> None:
        sgr = self.run / "artefactos" / "sgr"
        sgr.mkdir(parents=True)
        (sgr / "componentes.json").write_text("{}")
        state = self.progress("fase6", "| G5.5 | APROBADA |\n", unit="fase5_5_sgr")["state"]
        self.assertEqual(state, "partial")

    def test_components_gate_done_with_its_file_and_sections_is_verified(self) -> None:
        sgr = self.run / "artefactos" / "sgr"
        sgr.mkdir(parents=True)
        (sgr / "componentes.json").write_text("{}")
        sections = self.run / "redaccion" / "sections"
        for stem in ("31_trl", "32_sostenibilidad", "33_uso_posterior", "34_transferencia",
                     "35_medidas_diferenciales"):
            (sections / f"{stem}.tex").write_text("% rendered\n")
        rows = "| G5.5 | APROBADA |\n| GComponentes | APROBADA |\n"
        progress = self.progress("fase6", rows, unit="fase5_5_sgr")
        self.assertEqual(progress["state"], "verified", progress["missing"])

    def test_run_already_past_g5_skips_the_products_gate(self) -> None:
        for next_step in ("fase5_5", "fase5_5_sgr", "fase6"):
            with self.subTest(next_step=next_step):
                state = self.progress(next_step, "| G5 | APROBADA |\n", unit="fase5_sgr")["state"]
                self.assertEqual(state, "skipped")

    def test_run_at_the_products_gate_keeps_it_pending(self) -> None:
        state = self.progress("fase5_sgr", "| G5 | APROBADA |\n", unit="fase5_sgr")["state"]
        self.assertEqual(state, "pending")

    def test_past_run_with_the_products_file_is_not_skipped(self) -> None:
        sgr = self.run / "artefactos" / "sgr"
        sgr.mkdir(parents=True)
        (sgr / "productos.json").write_text("{}")
        state = self.progress("fase5_5", "| G5 | APROBADA |\n", unit="fase5_sgr")["state"]
        self.assertEqual(state, "partial")

    def test_products_gate_done_with_its_file_and_sections_is_verified(self) -> None:
        sgr = self.run / "artefactos" / "sgr"
        sgr.mkdir(parents=True)
        (sgr / "productos.json").write_text("{}")
        sections = self.run / "redaccion" / "sections"
        for stem in ("36_talento_humano", "37_indicadores"):
            (sections / f"{stem}.tex").write_text("% rendered\n")
        rows = "| G5 | APROBADA |\n| GProductos | APROBADA |\n"
        progress = self.progress("fase5_5", rows, unit="fase5_sgr")
        self.assertEqual(progress["state"], "verified", progress["missing"])


if __name__ == "__main__":
    unittest.main()
