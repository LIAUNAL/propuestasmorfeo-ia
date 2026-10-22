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


class GateStatus(unittest.TestCase):
    def status(self, rows: str) -> dict[str, str]:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "artefactos").mkdir()
        (tmp / "artefactos" / "estado_propuesta.md").write_text(f"| Compuerta | Estado |\n|---|---|\n{rows}")
        return {g["id"]: g["status"] for g in parse_gates_info(tmp, "sgr")}

    def test_approving_g1a_does_not_approve_the_causes_gate(self) -> None:
        status = self.status("| G1a | APROBADA |\n")
        self.assertEqual(status["G1a"], "PASS")
        self.assertEqual(status["GCausas"], "PENDING")

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

    def test_base_flow_keeps_cause_magnitude_optional(self) -> None:
        found = self.codes(SPEC, "base")
        self.assertNotIn("sgr-causa-sin-magnitud", found)
        self.assertNotIn("sgr-efecto-sin-magnitud", found)


if __name__ == "__main__":
    unittest.main()
