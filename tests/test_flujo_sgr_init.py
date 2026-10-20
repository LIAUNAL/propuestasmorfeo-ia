"""Tests for the SGR flow flag: `morfeo init --sgr` (spec S4 of flujo-sgr).

The flag records `"flujo": "sgr"` in both project configs; without it the flow
is `"base"`. `morfeo upgrade` keeps the value, the dashboard status reports it,
and every new run records it in its `_run.md`.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from morfeo.cli import main  # noqa: E402
from morfeo.core.status import SECTION_TITLES, get_project_status  # noqa: E402
from morfeo.core.upgrade import upgrade_project  # noqa: E402


def _init(target: Path, *extra: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(["init", str(target), "--tools", "claude", "--title", "Demo", *extra])
    return code, out.getvalue()


def _configs(target: Path) -> list[dict]:
    return [
        json.loads((target / marker / "config.json").read_text(encoding="utf-8"))
        for marker in (".morfeo", ".marco")
    ]


class TestInitSgrFlag(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_init_with_sgr_writes_flujo_sgr_in_both_configs(self):
        target = self.tmp / "ws"
        code, out = _init(target, "--sgr")
        self.assertEqual(code, 0)
        for cfg in _configs(target):
            self.assertEqual(cfg["flujo"], "sgr")
        self.assertIn("Flujo: SGR (Sistema General de Regalías, MGA)", out)

    def test_init_without_flag_writes_flujo_base_and_keeps_other_keys(self):
        target = self.tmp / "ws"
        code, out = _init(target)
        self.assertEqual(code, 0)
        for cfg in _configs(target):
            self.assertEqual(cfg["flujo"], "base")
            self.assertEqual(cfg["lang"], "es")
            self.assertEqual(cfg["preset"], "claude")
            self.assertEqual(cfg["tools"], ["claude"])
            self.assertEqual(cfg["title"], "Demo")
            self.assertIn("version", cfg)
        self.assertIn("Flujo: base", out)

    def test_reinit_with_force_sets_the_flow_accordingly(self):
        target = self.tmp / "ws"
        _init(target, "--sgr")
        code, _ = _init(target, "--force")
        self.assertEqual(code, 0)
        self.assertEqual([c["flujo"] for c in _configs(target)], ["base", "base"])
        _init(target, "--force", "--sgr")
        self.assertEqual([c["flujo"] for c in _configs(target)], ["sgr", "sgr"])

    def test_upgrade_keeps_flujo_sgr(self):
        target = self.tmp / "ws"
        _init(target, "--sgr")
        before = _configs(target)
        self.assertEqual(upgrade_project(target, quiet=True), 0)
        after = _configs(target)
        self.assertEqual([c["flujo"] for c in after], ["sgr", "sgr"])
        self.assertEqual(before, after)


class TestStatusFlujo(unittest.TestCase):
    def _workspace(self, root: Path, cfg: dict) -> Path:
        for marker in (".morfeo", ".marco"):
            (root / marker).mkdir(parents=True)
            (root / marker / "version").write_text("0.5.6\n", encoding="utf-8")
            (root / marker / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        (root / "proposals").mkdir()
        return root

    def test_config_without_flujo_reports_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._workspace(Path(tmp), {"version": "0.5.6", "title": "Viejo"})
            status = get_project_status(ws, force_refresh=True)
            self.assertEqual(status["flujo"], "base")
            self.assertEqual(status["workspace_title"], "Viejo")

    def test_config_with_sgr_reports_sgr(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._workspace(Path(tmp), {"version": "0.5.6", "flujo": "sgr"})
            status = get_project_status(ws, force_refresh=True)
            self.assertEqual(status["flujo"], "sgr")

    def test_marco_config_is_the_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".marco").mkdir()
            (root / ".marco" / "config.json").write_text(
                json.dumps({"flujo": "sgr"}), encoding="utf-8"
            )
            status = get_project_status(root, force_refresh=True)
            self.assertEqual(status["flujo"], "sgr")

    def _status_with_run(self, root: Path, flujo: str | None) -> dict:
        cfg = {"version": "0.5.6"} if flujo is None else {"version": "0.5.6", "flujo": flujo}
        ws = self._workspace(root, cfg)
        (ws / "proposals" / "2026-10-demo" / "artefactos").mkdir(parents=True)
        (ws / "proposals" / "2026-10-demo" / "_run.md").write_text("# demo\n", encoding="utf-8")
        (ws / "proposals" / ".current-run").write_text("2026-10-demo\n", encoding="utf-8")
        return get_project_status(ws, force_refresh=True)

    def test_base_payload_drops_the_sgr_unit_and_gate(self):
        for flujo in (None, "base"):
            with tempfile.TemporaryDirectory() as tmp:
                status = self._status_with_run(Path(tmp), flujo)
                unit_ids = [u["id"] for u in status["pipeline_units"]]
                gate_ids = [g["id"] for g in status["gates"]]
                self.assertNotIn("fase6_47", unit_ids)
                self.assertIn("fase6_46", unit_ids)
                self.assertNotIn("G6.47", gate_ids)
                self.assertEqual(status["totals"]["gates_total"], len(gate_ids))

    def test_sgr_payload_keeps_the_sgr_unit_and_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = self._status_with_run(Path(tmp), "sgr")
            unit_ids = [u["id"] for u in status["pipeline_units"]]
            gate_ids = [g["id"] for g in status["gates"]]
            self.assertIn("fase6_47", unit_ids)
            self.assertIn("G6.47", gate_ids)
            self.assertEqual(status["totals"]["gates_total"], len(gate_ids))

    def test_section_titles_cover_the_sgr_annexes(self):
        expected = {
            "19_alineacion_planes": "Alineación con los planes de desarrollo",
            "20_participantes": "Análisis de participantes",
            "21_poblacion": "Población afectada y objetivo",
            "22_alternativas": "Alternativas de solución",
            "23_cadena_valor": "Cadena de valor",
            "24_riesgos": "Análisis de riesgos",
            "25_marco_logico": "Matriz de marco lógico",
        }
        for stem, title in expected.items():
            self.assertIn(stem, SECTION_TITLES)
            self.assertIn(title, SECTION_TITLES[stem])


class TestInitRunFlujo(unittest.TestCase):
    """init-run.sh records the project flow in each new `_run.md`.

    The portable project is created by `morfeo init`, then its
    `scripts/init-run.sh` is replaced by the repository source so the test
    exercises the script under change even before the packaged kit is rebuilt.
    """

    def _run(self, *extra: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / "ws"
        code, _ = _init(target, *extra)
        self.assertEqual(code, 0)
        shutil.copy2(REPO / "scripts" / "init-run.sh", target / "scripts" / "init-run.sh")
        result = subprocess.run(
            ["bash", str(target / "scripts" / "init-run.sh"), "2026-10-demo", "idea"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return target / "proposals" / "2026-10-demo"

    def test_sgr_project_run_records_flujo_sgr(self):
        run = self._run("--sgr")
        self.assertIn("| flujo | sgr |", (run / "_run.md").read_text(encoding="utf-8"))

    def test_base_project_run_records_flujo_base_and_keeps_layout(self):
        run = self._run()
        self.assertIn("| flujo | base |", (run / "_run.md").read_text(encoding="utf-8"))
        for sub in ("insumos", "artefactos", "grafos", "redaccion"):
            self.assertTrue((run / sub).is_dir(), sub)

    def test_missing_config_falls_back_to_base(self):
        run = self._run()
        ws = run.parent.parent
        for marker in (".morfeo", ".marco"):
            (ws / marker / "config.json").unlink()
        result = subprocess.run(
            ["bash", str(ws / "scripts" / "init-run.sh"), "2026-10-otra"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (ws / "proposals" / "2026-10-otra" / "_run.md").read_text(encoding="utf-8")
        self.assertIn("| flujo | base |", text)


if __name__ == "__main__":
    unittest.main()
