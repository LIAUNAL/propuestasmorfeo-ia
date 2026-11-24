"""scripts/init-run.sh records the run's writing language (S3).

An English project gets English runs: `_run.md` carries `| idioma | en |`. A
Spanish project, an SGR project or a project without config gets runs exactly
as before (no `idioma` row), so a Spanish run is byte-identical to one created
before the setting existed and a later project change never re-labels it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _workspace(root: Path, config: dict | None) -> Path:
    for rel in ("plantilla", "scripts"):
        shutil.copytree(REPO / rel, root / rel, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
    if config is not None:
        for marker in (".morfeo", ".marco"):
            (root / marker).mkdir()
            (root / marker / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return root


def _init_run(root: Path, run_id: str = "2026-11-demo") -> tuple[Path, str]:
    result = subprocess.run(["bash", "scripts/init-run.sh", run_id, "idea"], cwd=root, capture_output=True,
                            text=True)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    return root / "proposals" / run_id, result.stdout


class InitRunLanguageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_an_english_project_records_english_runs(self) -> None:
        run, out = _init_run(_workspace(self.root, {"lang": "en", "flujo": "base"}))
        self.assertIn("| idioma | en |", (run / "_run.md").read_text(encoding="utf-8"))
        self.assertIn("idioma: en", out)

    def test_a_spanish_project_records_no_row(self) -> None:
        run, out = _init_run(_workspace(self.root, {"lang": "es", "flujo": "base"}))
        self.assertNotIn("idioma", (run / "_run.md").read_text(encoding="utf-8"))
        self.assertNotIn("idioma", out)

    def test_an_sgr_project_stays_spanish(self) -> None:
        run, _ = _init_run(_workspace(self.root, {"lang": "en", "flujo": "sgr"}))
        self.assertNotIn("idioma", (run / "_run.md").read_text(encoding="utf-8"))

    def test_a_project_without_config_stays_spanish(self) -> None:
        run, _ = _init_run(_workspace(self.root, None))
        self.assertNotIn("idioma", (run / "_run.md").read_text(encoding="utf-8"))

    def test_refreshing_a_spanish_run_after_switching_keeps_it_spanish(self) -> None:
        root = _workspace(self.root, {"lang": "es"})
        run, _ = _init_run(root)
        for marker in (".morfeo", ".marco"):
            (root / marker / "config.json").write_text('{"lang": "en"}', encoding="utf-8")
        _init_run(root)
        self.assertNotIn("idioma", (run / "_run.md").read_text(encoding="utf-8"))
        self.assertNotIn("english", (run / "redaccion" / "main.tex").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
