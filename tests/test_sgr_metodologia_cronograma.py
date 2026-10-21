"""SGR methodology figure and schedule (odd/tasks/sgr-figuras-estructura.md, S4).

Guía SGR §10: the methodology is a value chain, each product answers a specific
objective and each phase names its activities by stage (preinversión,
inversión, operación). §14: the schedule groups activities by stage and marks
the critical path. check_run warns (never blocks a running gate) when the
methodology spec or §14 misses them; the renderer prints the stage in the box.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))

from test_trees import make_run, write_agent_objectives  # noqa: E402

CHECK = REPO / "scripts" / "check_run.py"


def _load_renderer():
    spec = importlib.util.spec_from_file_location("render_tikz_sgr", REPO / "plantilla" / "scripts" / "render_tikz.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RENDER = _load_renderer()

METODO = {
    "kind": "metodologico",
    "phases": [
        {"id": "F1", "title": "Fase 1", "text": "Diagnóstico", "etapa": "preinversion", "oe": ["OE1"]},
        {"id": "F2", "title": "Fase 2", "text": "Desarrollo", "etapa": "inversion", "oe": ["OE2"]},
        {"id": "F3", "title": "Fase 3", "text": "Transferencia", "etapa": "operacion", "oe": ["OE2"]},
    ],
}

GANTT_OK = r"""\section{Cronograma de actividades}
Etapa de preinversión, etapa de inversión y etapa de operación. Las actividades
marcadas con $\star$ están en la ruta crítica.
"""


class _Run(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.run_dir = make_run(self.tmp)
        write_agent_objectives(self.run_dir)

    def write_spec(self, spec: dict) -> None:
        (self.run_dir / "redaccion" / "specs" / "metodologico.spec.json").write_text(json.dumps(spec, ensure_ascii=False))

    def write_gantt(self, text: str) -> None:
        (self.run_dir / "redaccion" / "sections" / "14_cronograma_actividades.tex").write_text(text)

    def codes(self, flujo: str = "sgr") -> dict[str, str]:
        out = subprocess.run([sys.executable, str(CHECK), str(self.run_dir), "--json", "--flujo", flujo],
                             capture_output=True, text=True)
        return {f["code"]: f["severity"] for f in json.loads(out.stdout)["findings"]}


class Methodology(_Run):
    def test_value_chain_by_stage_covering_every_oe_is_clean(self) -> None:
        self.write_spec(METODO)
        codes = self.codes()
        self.assertNotIn("sgr-metodologia-sin-etapa", codes)
        self.assertNotIn("sgr-metodologia-sin-oe", codes)

    def test_phase_without_stage_warns(self) -> None:
        spec = json.loads(json.dumps(METODO))
        del spec["phases"][1]["etapa"]
        self.write_spec(spec)
        self.assertEqual(self.codes().get("sgr-metodologia-sin-etapa"), "warning")

    def test_unknown_stage_warns(self) -> None:
        spec = json.loads(json.dumps(METODO))
        spec["phases"][0]["etapa"] = "ejecución"
        self.write_spec(spec)
        self.assertEqual(self.codes().get("sgr-metodologia-sin-etapa"), "warning")

    def test_accented_stage_names_are_accepted(self) -> None:
        spec = json.loads(json.dumps(METODO))
        spec["phases"][1]["etapa"] = "Inversión"
        spec["phases"][2]["etapa"] = "operación"
        self.write_spec(spec)
        self.assertNotIn("sgr-metodologia-sin-etapa", self.codes())

    def test_uncovered_specific_objective_warns(self) -> None:
        spec = json.loads(json.dumps(METODO))
        for phase in spec["phases"]:
            phase["oe"] = ["OE1"]
        self.write_spec(spec)
        self.assertEqual(self.codes().get("sgr-metodologia-sin-oe"), "warning")

    def test_base_flow_ignores_stages(self) -> None:
        self.write_spec({"kind": "metodologico", "phases": [{"id": "F1", "title": "Fase 1", "text": "x"}]})
        codes = self.codes("base")
        self.assertNotIn("sgr-metodologia-sin-etapa", codes)
        self.assertNotIn("sgr-metodologia-sin-oe", codes)

    def test_renderer_prints_the_stage_in_the_phase_box(self) -> None:
        text, _ = RENDER.render(METODO, {})
        self.assertIn("Preinversión", text)
        self.assertIn("Operación", text)

    def test_renderer_output_without_stage_is_unchanged(self) -> None:
        plain = {"kind": "metodologico", "phases": [{"id": "F1", "title": "Fase 1", "text": "Diagnóstico"}]}
        with_none = json.loads(json.dumps(plain))
        self.assertEqual(RENDER.render(plain, {})[0], RENDER.render(with_none, {})[0])
        self.assertNotIn("Preinversión", RENDER.render(plain, {})[0])


class Schedule(_Run):
    def test_stages_and_critical_path_are_clean(self) -> None:
        self.write_gantt(GANTT_OK)
        codes = self.codes()
        self.assertNotIn("sgr-cronograma-sin-etapas", codes)
        self.assertNotIn("sgr-cronograma-sin-ruta-critica", codes)

    def test_missing_stages_warn(self) -> None:
        self.write_gantt("\\section{Cronograma de actividades}\nFase 1 y fase 2; ruta crítica marcada.\n")
        self.assertEqual(self.codes().get("sgr-cronograma-sin-etapas"), "warning")

    def test_missing_critical_path_warns(self) -> None:
        self.write_gantt("\\section{Cronograma de actividades}\nEtapa de inversión.\n")
        self.assertEqual(self.codes().get("sgr-cronograma-sin-ruta-critica"), "warning")

    def test_commented_out_mentions_do_not_count(self) -> None:
        self.write_gantt("\\section{Cronograma de actividades}\n% etapa de inversión, ruta crítica\nNada.\n")
        codes = self.codes()
        self.assertIn("sgr-cronograma-sin-etapas", codes)
        self.assertIn("sgr-cronograma-sin-ruta-critica", codes)

    def test_base_flow_has_no_schedule_rules(self) -> None:
        self.write_gantt("\\section{Cronograma de actividades}\nNada.\n")
        codes = self.codes("base")
        self.assertNotIn("sgr-cronograma-sin-etapas", codes)
        self.assertNotIn("sgr-cronograma-sin-ruta-critica", codes)


if __name__ == "__main__":
    unittest.main()
