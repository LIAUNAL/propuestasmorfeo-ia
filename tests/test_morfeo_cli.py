"""Tests for Morfeo IA package and CLI."""

from __future__ import annotations

import json
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
        self.assertEqual(morfeo.__version__, "0.5.3")

    def test_status_without_a_version_marker_reports_the_package_version(self):
        """A workspace with no `.morfeo/version` marker (this framework
        repository is one) printed the frozen literal `0.5.0` while the package
        was already several releases ahead."""
        repo = Path(__file__).resolve().parent.parent
        status = get_project_status(repo, force_refresh=True)
        self.assertEqual(status["version"], morfeo.__version__)

    def test_status_reports_the_unit_in_progress(self):
        """El latido `_en_curso.json` es lo unico que permite mostrar que agente
        se esta levantando mientras ocurre; sin el solo se puede contar el
        pasado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            run = repo / "proposals" / "2026-01-demo"
            (run / "artefactos" / "pipeline").mkdir(parents=True)
            (repo / "proposals" / ".current-run").write_text(
                "2026-01-demo\n", encoding="utf-8"
            )
            (run / "artefactos" / "pipeline" / "_en_curso.json").write_text(
                json.dumps(
                    {
                        "fase": "fase5",
                        "agentes": ["redactor"],
                        "skill": "estilo-natural-es",
                        "artefacto_esperado": "sections/10_metodologia.tex",
                        "inicio": "2026-01-02T10:00:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            status = get_project_status(repo, force_refresh=True)
            self.assertIsNotNone(status["en_curso"])
            self.assertEqual(status["en_curso"]["fase"], "fase5")
            self.assertEqual(status["en_curso"]["agentes"], ["redactor"])
            self.assertEqual(status["en_curso"]["skill"], "estilo-natural-es")

    def test_status_reports_the_execution_control_block(self):
        """El botón «Ejecutar» del tablero solo habilita la unidad que
        `/propuesta-continuar` va a correr; esa unidad es `next_step` del bloque
        de control, no la que el tablero deduzca de los veredictos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            run = repo / "proposals" / "2026-01-demo"
            (run / "artefactos").mkdir(parents=True)
            (run / "insumos" / "tdr").mkdir(parents=True)
            (run / "insumos" / "README.md").write_text("zonas", encoding="utf-8")
            (run / "insumos" / "tdr" / "tdr.pdf").write_bytes(b"%PDF")
            (repo / "proposals" / ".current-run").write_text(
                "2026-01-demo\n", encoding="utf-8"
            )
            (run / "artefactos" / "estado_propuesta.md").write_text(
                "# Estado\n\n## Control de ejecución\n\n"
                "- mode: stepped\n- next_step: fase2\n"
                "- next_command: /propuesta-continuar\n"
                "- last_completed: fase1\n- intake_complete: true\n",
                encoding="utf-8",
            )

            status = get_project_status(repo, force_refresh=True)
            self.assertEqual(status["control"]["next_step"], "fase2")
            self.assertEqual(status["control"]["last_completed"], "fase1")
            self.assertIs(status["control"]["intake_complete"], True)
            # README.md lo siembra /propuesta-insumos: no es un insumo del usuario.
            self.assertEqual(status["run_details"]["insumos_count"], 1)

    def test_status_without_a_control_block_reports_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            run = repo / "proposals" / "2026-01-demo"
            (run / "artefactos").mkdir(parents=True)
            (repo / "proposals" / ".current-run").write_text(
                "2026-01-demo\n", encoding="utf-8"
            )
            status = get_project_status(repo, force_refresh=True)
            self.assertIsNone(status["control"])
            self.assertEqual(status["run_details"]["insumos_count"], 0)

    def test_status_without_a_heartbeat_reports_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            run = repo / "proposals" / "2026-01-demo"
            (run / "artefactos" / "pipeline").mkdir(parents=True)
            (repo / "proposals" / ".current-run").write_text(
                "2026-01-demo\n", encoding="utf-8"
            )
            status = get_project_status(repo, force_refresh=True)
            self.assertIsNone(status["en_curso"])

    def test_a_corrupt_heartbeat_does_not_break_status(self):
        """Un latido a medio escribir no puede tumbar el tablero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            run = repo / "proposals" / "2026-01-demo"
            (run / "artefactos" / "pipeline").mkdir(parents=True)
            (repo / "proposals" / ".current-run").write_text(
                "2026-01-demo\n", encoding="utf-8"
            )
            (run / "artefactos" / "pipeline" / "_en_curso.json").write_text(
                "{no es json", encoding="utf-8"
            )
            status = get_project_status(repo, force_refresh=True)
            self.assertIsNone(status["en_curso"])

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
            self.assertEqual(status_dict["version"], "0.5.3")
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
