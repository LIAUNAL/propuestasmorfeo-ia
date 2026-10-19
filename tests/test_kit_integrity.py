"""The bundled kit must arrive runnable and stay in step with its sources.

A portable project got every kit file with mode 0644: ``shutil.copyfile`` drops
the executable bit, so ``scripts/init-run.sh`` and ``plantilla/build.sh`` failed
with exit 126 right after ``morfeo init``. Wheels do not reliably carry file
modes either, so the copy into a project marks scripts executable on its own.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from morfeo.core.init import init_project
from morfeo.core.manifest import copy_kit_entry

REPO = Path(__file__).resolve().parent.parent
BUILD_KIT = REPO / "scripts" / "build-kit.py"


def _load_build_kit():
    spec = importlib.util.spec_from_file_location("build_kit", BUILD_KIT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _executable(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_IXUSR)


class InitShipsRunnableScriptsTest(unittest.TestCase):
    def test_init_marks_kit_scripts_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "proj"
            self.assertEqual(init_project(target, tools={"claude"}, preset_name="claude", quiet=True), 0)

            for rel in ("scripts/init-run.sh", "plantilla/build.sh"):
                self.assertTrue(os.access(target / rel, os.X_OK), f"{rel} is not executable")

    def test_a_portable_project_can_create_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "proj"
            init_project(target, tools={"claude"}, preset_name="claude", quiet=True)

            result = subprocess.run(
                ["./scripts/init-run.sh", "2026-01-prueba", "idea de prueba"],
                cwd=target, capture_output=True, text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            run = target / "proposals" / "2026-01-prueba"
            for sub in ("insumos", "artefactos", "grafos", "redaccion"):
                self.assertTrue((run / sub).is_dir(), f"run is missing {sub}/")
            self.assertTrue(os.access(run / "redaccion" / "build.sh", os.X_OK), "run build.sh is not executable")

    def test_copy_marks_shebang_files_executable_even_from_a_0644_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "src", Path(tmp) / "dst"
            (src / "scripts").mkdir(parents=True)
            (src / "scripts" / "tool.py").write_text("#!/usr/bin/env python3\nprint(1)\n")
            (src / "scripts" / "data.json").write_text("{}\n")
            for f in (src / "scripts").iterdir():
                f.chmod(0o644)

            copy_kit_entry(src, dst, "scripts")

            self.assertTrue(_executable(dst / "scripts" / "tool.py"))
            self.assertFalse(_executable(dst / "scripts" / "data.json"))


class BuildKitCheckTest(unittest.TestCase):
    def test_committed_kit_is_in_step_with_its_sources(self) -> None:
        result = subprocess.run([sys.executable, str(BUILD_KIT), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_check_reports_content_and_mode_drift_without_rewriting(self) -> None:
        build_kit = _load_build_kit()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "run.sh").write_text("#!/bin/sh\necho hi\n")
            (root / "scripts" / "run.sh").chmod(0o755)
            (root / "scripts" / "notes.txt").write_text("v1\n")
            manifest = {"kit_paths": ["scripts/run.sh", "scripts/notes.txt"]}
            kit = root / "kit"
            build_kit.assemble(root=root, kit=kit, manifest=manifest, quiet=True)
            self.assertEqual(build_kit.check(root=root, kit=kit, manifest=manifest), [])

            (kit / "scripts" / "run.sh").chmod(0o644)
            (root / "scripts" / "notes.txt").write_text("v2\n")
            problems = build_kit.check(root=root, kit=kit, manifest=manifest)

            self.assertEqual(len(problems), 2, problems)
            self.assertEqual((kit / "scripts" / "notes.txt").read_text(), "v1\n", "check rewrote the kit")


if __name__ == "__main__":
    unittest.main()
