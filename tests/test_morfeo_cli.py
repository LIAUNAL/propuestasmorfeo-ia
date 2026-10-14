"""Tests for Morfeo IA package and CLI."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import morfeo
from morfeo.cli import main
from morfeo.core.audit import audit_project
from morfeo.core.init import init_project
from morfeo.core.status import get_project_status, status_project
from morfeo.core.upgrade import upgrade_project
from morfeo.kit import get_kit_root, load_kit_manifest


class TestMorfeoCLI(unittest.TestCase):
    def test_version(self):
        self.assertEqual(morfeo.__version__, "0.5.1")

    def test_kit_resolution(self):
        kit_root = get_kit_root()
        self.assertTrue(kit_root.is_dir())
        manifest = load_kit_manifest(kit_root)
        self.assertIn("version", manifest)
        self.assertIn("kit_paths", manifest)

    def test_init_audit_upgrade_status_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test_workspace"

            # 1. init
            exit_code = init_project(target, tools={"claude", "pi"}, preset_name="claude", quiet=True)
            self.assertEqual(exit_code, 0)
            self.assertTrue((target / ".morfeo" / "version").is_file())
            self.assertTrue((target / "idea.md").is_file())
            self.assertTrue((target / "DECISIONS.md").is_file())

            # 2. status
            status_dict = get_project_status(target)
            self.assertEqual(status_dict["version"], "0.5.1")
            self.assertIsNone(status_dict["active_run"])

            # 3. audit clean
            audit_exit = audit_project(target, as_json=True)
            self.assertEqual(audit_exit, 0)

            # 4. upgrade clean
            upgrade_exit = upgrade_project(target, quiet=True)
            self.assertEqual(upgrade_exit, 0)

    def test_cli_help(self):
        with self.assertRaises(SystemExit) as cm:
            main(["--help"])
        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
