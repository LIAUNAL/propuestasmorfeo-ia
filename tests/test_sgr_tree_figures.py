"""SGR tree figures come from the trees panel (odd/tasks/sgr-figuras-estructura.md, S1-S2).

The panel shows `redaccion/specs/arbol_problemas.spec.json` and
`artefactos/arboles/arbol_objetivos.json`. The document figures must be drawn
from exactly those files: `scripts/arbol_objetivos.py` turns the objective tree
into an `arbol` spec without an agent, and `scripts/check_run.py` re-renders each
tree spec with the run's own renderer to catch a figure compiled from an older
spec, plus (SGR) a tree the panel has not approved.
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
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from morfeo.core import trees  # noqa: E402
from test_trees import SPEC, make_run, write_agent_objectives  # noqa: E402

CONVERT = REPO / "scripts" / "arbol_objetivos.py"
CHECK = REPO / "scripts" / "check_run.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RENDER = _load(REPO / "plantilla" / "scripts" / "render_tikz.py", "render_tikz_under_test")
CHECK_RUN = _load(CHECK, "check_run_under_test")


def _codes(run: Path, flujo: str) -> dict[str, str]:
    out = subprocess.run([sys.executable, str(CHECK), str(run), "--json", "--flujo", flujo],
                         capture_output=True, text=True)
    return {f["code"]: f["severity"] for f in json.loads(out.stdout)["findings"]}


class _Run(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.run_dir = make_run(self.tmp)
        scripts = self.run_dir / "redaccion" / "scripts"
        scripts.mkdir()
        shutil.copy(REPO / "plantilla" / "scripts" / "render_tikz.py", scripts / "render_tikz.py")

    def render_to_diag(self, name: str) -> Path:
        spec = json.loads((self.run_dir / "redaccion" / "specs" / f"{name}.spec.json").read_text())
        text, _ = RENDER.render(spec, {})
        diag = self.run_dir / "redaccion" / "sections" / f"diag_{name}.tex"
        diag.write_text(text, encoding="utf-8")
        return diag

    def convert(self) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(CONVERT), str(self.run_dir), "--json"],
                              capture_output=True, text=True)


class ObjectiveTreeSpec(_Run):
    def test_converts_the_panel_tree_into_an_arbol_spec(self) -> None:
        write_agent_objectives(self.run_dir)
        result = self.convert()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        spec_path = self.run_dir / "redaccion" / "specs" / "arbol_objetivos.spec.json"
        self.assertEqual(Path(report["spec"]), spec_path.resolve())
        spec = json.loads(spec_path.read_text())
        self.assertEqual(spec["kind"], "arbol")
        self.assertEqual(spec["header"], "ÁRBOL DE OBJETIVOS")
        self.assertEqual([g["title"] for g in spec["groups"]], ["Lograr el objetivo uno", "Lograr el objetivo dos"])
        self.assertEqual([c["text"] for c in spec["groups"][0]["causes"]],
                         ["Atender la causa uno", "Atender la causa dos"])
        self.assertEqual(spec["trunk"], {"label": "OBJETIVO GENERAL", "text": "Aumentar la cobertura del servicio de prueba"})
        self.assertEqual(spec["branches"], [{"id": "f1", "text": "Reducir el efecto uno"}])
        self.assertEqual(spec["crown"]["text"], "Mejorar el bienestar")
        RENDER.render(spec, {})  # the existing renderer accepts it as is

    def test_missing_texts_exit_2_and_write_nothing(self) -> None:
        write_agent_objectives(self.run_dir, trunk="")
        result = self.convert()
        self.assertEqual(result.returncode, 2)
        self.assertIn("objetivo general", json.loads(result.stdout)["missing"])
        self.assertFalse((self.run_dir / "redaccion" / "specs" / "arbol_objetivos.spec.json").exists())

    def test_corrupt_problem_spec_exits_2_without_traceback(self) -> None:
        write_agent_objectives(self.run_dir)
        (self.run_dir / "redaccion" / "specs" / "arbol_problemas.spec.json").write_text("{bad")
        result = self.convert()
        self.assertEqual(result.returncode, 2)
        self.assertIn("arbol_problemas.spec.json", json.loads(result.stdout)["error"])
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_objective_file_exits_2(self) -> None:
        result = self.convert()
        self.assertEqual(result.returncode, 2)
        self.assertIn("arbol_objetivos.json", json.loads(result.stdout)["error"])


class FigureMatchesPanel(_Run):
    def test_figure_rendered_from_current_spec_has_no_sync_finding(self) -> None:
        self.render_to_diag("arbol_problemas")
        self.assertNotIn("figura-desincronizada", _codes(self.run_dir, "base"))

    def test_spec_edited_after_render_is_an_error(self) -> None:
        self.render_to_diag("arbol_problemas")
        spec_path = self.run_dir / "redaccion" / "specs" / "arbol_problemas.spec.json"
        edited = json.loads(spec_path.read_text())
        edited["trunk"]["text"] = "Baja cobertura del servicio de prueba en Caldas."
        spec_path.write_text(json.dumps(edited, ensure_ascii=False))
        self.assertEqual(_codes(self.run_dir, "base").get("figura-desincronizada"), "error")

    def test_objective_figure_is_checked_too(self) -> None:
        write_agent_objectives(self.run_dir)
        self.assertEqual(self.convert().returncode, 0)
        diag = self.render_to_diag("arbol_objetivos")
        diag.write_text(diag.read_text().replace("Mejorar el bienestar", "Otro fin"))
        self.assertEqual(_codes(self.run_dir, "sgr").get("figura-desincronizada"), "error")

    def test_overrides_from_the_autofix_are_honoured(self) -> None:
        spec = json.loads((self.run_dir / "redaccion" / "specs" / "arbol_problemas.spec.json").read_text())
        widths = {"raiz": 5.5}
        (self.run_dir / "redaccion" / "specs" / "arbol_problemas.overrides.json").write_text(
            json.dumps({"widths": widths}))
        text, _ = RENDER.render(spec, widths)
        (self.run_dir / "redaccion" / "sections" / "diag_arbol_problemas.tex").write_text(text)
        self.assertNotIn("figura-desincronizada", _codes(self.run_dir, "base"))


class PanelApproval(_Run):
    def test_sgr_warns_when_the_problem_tree_is_not_approved(self) -> None:
        self.render_to_diag("arbol_problemas")
        self.assertEqual(_codes(self.run_dir, "sgr").get("arbol-sin-aprobar-panel"), "warning")

    def test_sgr_approved_tree_has_no_warning(self) -> None:
        self.render_to_diag("arbol_problemas")
        trees.approve_tree(self.run_dir, "problemas")
        self.assertNotIn("arbol-sin-aprobar-panel", _codes(self.run_dir, "sgr"))

    def test_sgr_approval_goes_stale_after_an_edit(self) -> None:
        trees.approve_tree(self.run_dir, "problemas")
        spec_path = self.run_dir / "redaccion" / "specs" / "arbol_problemas.spec.json"
        edited = json.loads(spec_path.read_text())
        edited["branches"][0]["text"] = "Efecto uno modificado"
        spec_path.write_text(json.dumps(edited, ensure_ascii=False))
        self.render_to_diag("arbol_problemas")
        self.assertEqual(_codes(self.run_dir, "sgr").get("arbol-sin-aprobar-panel"), "warning")

    def test_base_flow_does_not_require_panel_approval(self) -> None:
        self.render_to_diag("arbol_problemas")
        self.assertNotIn("arbol-sin-aprobar-panel", _codes(self.run_dir, "base"))

    def test_broken_run_renderer_still_reports_approval_and_says_why(self) -> None:
        self.render_to_diag("arbol_problemas")
        (self.run_dir / "redaccion" / "scripts" / "render_tikz.py").write_text("def broken(:\n")
        codes = _codes(self.run_dir, "sgr")
        self.assertEqual(codes.get("arbol-sin-aprobar-panel"), "warning")
        self.assertEqual(codes.get("figura-sin-verificar"), "warning")

    def test_check_run_hash_matches_the_panel_hash(self) -> None:
        self.assertEqual(CHECK_RUN.panel_tree_hash("problemas", SPEC),
                         trees._hash(trees._problem_tree(SPEC)))
        write_agent_objectives(self.run_dir)
        objectives = json.loads((self.run_dir / "artefactos" / "arboles" / "arbol_objetivos.json").read_text())
        self.assertEqual(CHECK_RUN.panel_tree_hash("objetivos", objectives), trees._hash(objectives))


if __name__ == "__main__":
    unittest.main()
