"""Verificación de las unidades del pipeline en el sobre de `/api/status`.

Una unidad cuenta como cumplida solo si su compuerta está en PASS (o, sin
compuerta, si su evento `artefactos/pipeline/NN-<id>.md` existe), si el control
de ejecución ya la dejó atrás y si existen sus artefactos y secciones. El
tablero ilumina la caja con ese veredicto, no con el PASS a secas.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from morfeo.core.pipeline_units import PIPELINE_UNITS
from morfeo.core.status import get_project_status

CONTROL = (
    "# Estado\n\n## Control de ejecución\n\n"
    "- mode: stepped\n- next_step: {next}\n"
    "- next_command: /propuesta-continuar\n"
    "- last_completed: {last}\n- intake_complete: true\n"
)
ESTADO = "| fase | gate | veredicto |\n|---|---|---|\n{rows}"


class UnitProgressTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.run = self.repo / "proposals" / "2026-01-demo"
        (self.run / "artefactos" / "pipeline").mkdir(parents=True)
        (self.run / "redaccion" / "sections").mkdir(parents=True)
        (self.repo / "proposals" / ".current-run").write_text("2026-01-demo\n", encoding="utf-8")

    def write(self, rel: str, text: str = "x") -> Path:
        path = self.run / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def control(self, next_step: str, last: str) -> None:
        self.write("artefactos/estado_propuesta.md", CONTROL.format(next=next_step, last=last))

    def gates(self, *rows: tuple[str, str, str]) -> None:
        body = "".join(f"| {f} | {g} | {v} |\n" for f, g, v in rows)
        self.write("artefactos/pipeline/_estado.md", ESTADO.format(rows=body))

    def status(self) -> dict:
        return get_project_status(self.repo, force_refresh=True)

    def test_every_unit_declares_the_artifacts_it_produces(self) -> None:
        for unit in PIPELINE_UNITS:
            self.assertIsInstance(unit.get("artifacts"), list, unit["id"])
        by_id = {u["id"]: u for u in PIPELINE_UNITS}
        self.assertIn("artefactos/mga_resumido.md", by_id["fase1"]["artifacts"])
        self.assertIn("artefactos/arboles/arbol_objetivos.json", by_id["fase1b"]["artifacts"])
        self.assertIn("artefactos/insumos.md", by_id["fase0"]["artifacts"])

    def test_a_unit_with_pass_control_past_it_and_its_files_is_verified(self) -> None:
        self.control("fase2", "fase1")
        self.gates(("fase1", "G1", "PASS"))
        self.write("artefactos/mga_resumido.md")
        self.write("artefactos/pipeline/20-fase1.md")
        self.write("redaccion/sections/03_descripcion_problema.tex")
        progress = self.status()["unit_progress"]["fase1"]
        self.assertEqual(progress["state"], "verified")
        self.assertTrue(all(c["ok"] for c in progress["checks"]))
        self.assertEqual(progress["missing"], [])

    def test_pass_without_its_artifacts_is_partial_and_names_what_is_missing(self) -> None:
        self.control("fase2", "fase1")
        self.gates(("fase1", "G1", "PASS"))
        self.write("redaccion/sections/03_descripcion_problema.tex")
        progress = self.status()["unit_progress"]["fase1"]
        self.assertEqual(progress["state"], "partial")
        self.assertTrue(any("mga_resumido.md" in m for m in progress["missing"]), progress["missing"])

    def test_pass_while_control_has_not_moved_on_is_not_verified(self) -> None:
        self.control("fase1", "fase1c")
        self.gates(("fase1", "G1", "PASS"))
        self.write("artefactos/mga_resumido.md")
        self.write("redaccion/sections/03_descripcion_problema.tex")
        progress = self.status()["unit_progress"]["fase1"]
        self.assertEqual(progress["state"], "partial")
        self.assertTrue(any("control" in m.lower() for m in progress["missing"]), progress["missing"])

    def test_a_failed_gate_is_reported_as_failed(self) -> None:
        self.control("fase1", "fase1c")
        self.gates(("fase1", "G1", "FAIL"))
        self.assertEqual(self.status()["unit_progress"]["fase1"]["state"], "failed")

    def test_a_gateless_unit_is_verified_by_its_event_file(self) -> None:
        self.control("fase6_4", "fase6")
        self.write("redaccion/sections/11_resultados_esperados.tex")
        self.write("redaccion/sections/12_consideraciones_eticas.tex")
        self.assertEqual(self.status()["unit_progress"]["fase6"]["state"], "partial")
        self.write("artefactos/pipeline/70-fase6.md")
        self.assertEqual(self.status()["unit_progress"]["fase6"]["state"], "verified")

    def test_a_later_unit_is_pending(self) -> None:
        self.control("fase2", "fase1")
        self.assertEqual(self.status()["unit_progress"]["fase4"]["state"], "pending")

    def test_the_intake_is_verified_by_intake_complete_and_insumos_md(self) -> None:
        self.control("fase1a", "fase0")
        self.write("artefactos/insumos.md")
        self.write("artefactos/pipeline/00-fase0.md")
        self.gates(("fase0", "G0.5", "PASS"))
        self.assertEqual(self.status()["unit_progress"]["fase0"]["state"], "verified")

    def test_an_intake_without_tdr_is_verified_although_g0_5_was_omitted(self) -> None:
        self.control("fase1a", "fase0")
        self.write("artefactos/insumos.md")
        self.assertEqual(self.status()["unit_progress"]["fase0"]["state"], "verified")

    def test_the_optional_tdr_guide_is_skipped_when_the_intake_closed_without_it(self) -> None:
        self.control("fase1a", "fase0")
        self.assertEqual(self.status()["unit_progress"]["g0_5"]["state"], "skipped")

    def test_artifacts_carry_their_modification_time(self) -> None:
        self.control("fase2", "fase1")
        path = self.write("artefactos/mga_resumido.md")
        status = self.status()
        listed = {a["rel_path"]: a for a in status["artifacts"]}
        self.assertAlmostEqual(listed["artefactos/mga_resumido.md"]["mtime"], path.stat().st_mtime, places=3)
        files = {a["path"]: a for a in status["unit_progress"]["fase1"]["artifacts"]}
        self.assertTrue(files["artefactos/mga_resumido.md"]["exists"])
        self.assertIsNotNone(files["artefactos/mga_resumido.md"]["mtime"])

    def test_a_running_unit_is_reported_as_running(self) -> None:
        self.control("fase2", "fase1")
        beat = {"fase": "fase2", "agentes": ["bibliografo-propuesta"], "inicio": datetime.now().isoformat(timespec="seconds")}
        self.write("artefactos/pipeline/_en_curso.json", json.dumps(beat))
        status = self.status()
        self.assertFalse(status["en_curso"]["stale"])
        self.assertEqual(status["unit_progress"]["fase2"]["state"], "running")

    def test_a_heartbeat_of_an_already_completed_unit_is_stale(self) -> None:
        self.control("fase2", "fase1")
        beat = {"fase": "fase1", "inicio": datetime.now().isoformat(timespec="seconds")}
        self.write("artefactos/pipeline/_en_curso.json", json.dumps(beat))
        self.assertTrue(self.status()["en_curso"]["stale"])

    def test_a_heartbeat_older_than_six_hours_is_stale(self) -> None:
        self.control("fase2", "fase1")
        old = (datetime.now() - timedelta(hours=7)).isoformat(timespec="seconds")
        self.write("artefactos/pipeline/_en_curso.json", json.dumps({"fase": "fase2", "inicio": old}))
        status = self.status()
        self.assertTrue(status["en_curso"]["stale"])
        self.assertNotEqual(status["unit_progress"]["fase2"]["state"], "running")


if __name__ == "__main__":
    unittest.main()
