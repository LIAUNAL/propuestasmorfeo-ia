"""Tests for 'morfeo export' and 'morfeo import' functionality."""

from __future__ import annotations

import json
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from morfeo.cli import main
from morfeo.core.export import export_project, should_exclude_path
from morfeo.core.import_project import import_project
from morfeo.core.init import init_project
from morfeo.core.status import get_project_status
from morfeo.errors import UserError


class TestExportImport(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _setup_mock_workspace(self, name: str = "workspace_test") -> tuple[Path, str]:
        target = self.root / name
        init_project(target, tools={"claude", "pi"}, preset_name="claude", quiet=True)

        run_id = "2026-10-salud-mental"
        run_dir = target / "proposals" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Set active run pointer
        (target / "proposals" / ".current-run").write_text(f"{run_id}\n", encoding="utf-8")
        (target / "proposals" / "registry.md").write_text(f"- `{run_id}`: active\n", encoding="utf-8")

        # Run metadata
        (run_dir / "_run.md").write_text(f"# Run {run_id}\nEstado: completada\n", encoding="utf-8")

        # Insumos
        insumos_dir = run_dir / "insumos"
        insumos_dir.mkdir(parents=True, exist_ok=True)
        (insumos_dir / "tdr.pdf").write_bytes(b"%PDF-1.4 dummy tdr")

        # Artefactos
        artefactos_dir = run_dir / "artefactos"
        artefactos_dir.mkdir(parents=True, exist_ok=True)
        (artefactos_dir / "estado_propuesta.md").write_text("# Estado\nFase: 7\n", encoding="utf-8")

        # Grafos
        grafos_dir = run_dir / "grafos"
        grafos_dir.mkdir(parents=True, exist_ok=True)
        (grafos_dir / "papers-graph-report.md").write_text("# Graph report\n", encoding="utf-8")

        # Redaccion
        redaccion_dir = run_dir / "redaccion"
        sections_dir = redaccion_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        (redaccion_dir / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nTest\n\\end{document}\n", encoding="utf-8")
        (redaccion_dir / "refs.bib").write_text("@article{test2026, title={Test}}\n", encoding="utf-8")
        (redaccion_dir / "main.pdf").write_bytes(b"%PDF-1.4 dummy compiled pdf")
        (sections_dir / "02_justificacion.tex").write_text("Justificacion del proyecto.", encoding="utf-8")

        # Ephemeral files that must be excluded
        (redaccion_dir / "main.aux").write_text("dummy aux", encoding="utf-8")
        (redaccion_dir / "main.log").write_text("dummy log", encoding="utf-8")
        (redaccion_dir / "main.fls").write_text("dummy fls", encoding="utf-8")
        pycache = redaccion_dir / "__pycache__"
        pycache.mkdir(parents=True, exist_ok=True)
        (pycache / "junk.pyc").write_bytes(b"dummy pyc")

        return target, run_id

    def test_exclusion_patterns(self):
        self.assertTrue(should_exclude_path(Path("redaccion/main.aux")))
        self.assertTrue(should_exclude_path(Path("redaccion/main.log")))
        self.assertTrue(should_exclude_path(Path("redaccion/main.fls")))
        self.assertTrue(should_exclude_path(Path("redaccion/sections/test.synctex.gz")))
        self.assertTrue(should_exclude_path(Path("redaccion/__pycache__/something.pyc")))
        self.assertTrue(should_exclude_path(Path(".DS_Store")))

        # Valid files must NOT be excluded
        self.assertFalse(should_exclude_path(Path("redaccion/main.tex")))
        self.assertFalse(should_exclude_path(Path("redaccion/main.pdf")))
        self.assertFalse(should_exclude_path(Path("redaccion/main.docx")))
        self.assertFalse(should_exclude_path(Path("redaccion/sections/02_justificacion.tex")))
        self.assertFalse(should_exclude_path(Path("insumos/tdr.pdf")))
        self.assertFalse(should_exclude_path(Path("artefactos/estado_propuesta.md")))

    def test_export_tar_gz(self):
        ws, run_id = self._setup_mock_workspace("ws_tar")
        out_archive = (self.root / "export_test.tar.gz").resolve()

        res = export_project(ws, output_path=out_archive, archive_format="tar.gz", quiet=True)
        self.assertEqual(res, out_archive)
        self.assertTrue(out_archive.is_file())
        self.assertGreater(out_archive.stat().st_size, 1000)

        # Inspect tar members
        with tarfile.open(out_archive, "r:gz") as tf:
            names = tf.getnames()
            # Manifest check
            manifest_name = f"{ws.name}/export_manifest.json"
            self.assertIn(manifest_name, names)
            manifest_file = tf.extractfile(manifest_name)
            self.assertIsNotNone(manifest_file)
            manifest_data = json.loads(manifest_file.read().decode("utf-8"))
            self.assertEqual(manifest_data["project_name"], ws.name)
            self.assertIn(run_id, manifest_data["selected_runs"])

            # Proposals content check
            self.assertTrue(any(f"proposals/{run_id}/insumos/tdr.pdf" in n for n in names))
            self.assertTrue(any(f"proposals/{run_id}/redaccion/main.tex" in n for n in names))
            self.assertTrue(any(f"proposals/{run_id}/redaccion/main.pdf" in n for n in names))
            self.assertTrue(any(f"proposals/{run_id}/artefactos/estado_propuesta.md" in n for n in names))

            # Exclusions check
            self.assertFalse(any("main.aux" in n for n in names))
            self.assertFalse(any("main.log" in n for n in names))
            self.assertFalse(any("__pycache__" in n for n in names))

    def test_export_zip(self):
        ws, run_id = self._setup_mock_workspace("ws_zip")
        out_archive = (self.root / "export_test.zip").resolve()

        res = export_project(ws, output_path=out_archive, archive_format="zip", quiet=True)
        self.assertEqual(res, out_archive)
        self.assertTrue(out_archive.is_file())

        with zipfile.ZipFile(out_archive, "r") as zf:
            names = zf.namelist()
            self.assertIn(f"{ws.name}/export_manifest.json", names)
            self.assertTrue(any(f"proposals/{run_id}/redaccion/main.pdf" in n for n in names))

    def test_import_project_roundtrip(self):
        ws, run_id = self._setup_mock_workspace("ws_origin")
        archive = (self.root / "exported.tar.gz").resolve()
        export_project(ws, output_path=archive, quiet=True)

        imported_target = (self.root / "ws_imported").resolve()
        res_dir = import_project(archive, target_dir=imported_target, quiet=True)
        self.assertEqual(res_dir, imported_target)
        self.assertTrue((imported_target / ".morfeo" / "version").is_file())
        self.assertTrue((imported_target / "proposals" / run_id / "redaccion" / "main.pdf").is_file())
        self.assertTrue((imported_target / "proposals" / run_id / "insumos" / "tdr.pdf").is_file())

        # Check status passes on imported directory
        status = get_project_status(imported_target, force_refresh=True)
        self.assertEqual(status["active_run"], run_id)

    def test_import_zip_slip_protection(self):
        # Craft a malicious zip containing a path traversal
        bad_zip_path = self.root / "evil.zip"
        with zipfile.ZipFile(bad_zip_path, "w") as zf:
            zf.writestr("../../evil_escape.txt", "malicious payload")

        dest = self.root / "safe_dir"
        with self.assertRaises(UserError) as cm:
            import_project(bad_zip_path, target_dir=dest, quiet=True)
        self.assertIn("Ruta no segura", str(cm.exception))

    def test_cli_export_import(self):
        ws, run_id = self._setup_mock_workspace("ws_cli")
        archive = self.root / "cli_pkg.tar.gz"

        exit_code = main(["export", str(ws), "-o", str(archive)])
        self.assertEqual(exit_code, 0)
        self.assertTrue(archive.is_file())

        dest = self.root / "imported_cli"
        exit_code_import = main(["import", str(archive), str(dest)])
        self.assertEqual(exit_code_import, 0)
        self.assertTrue((dest / "proposals" / run_id).is_dir())


if __name__ == "__main__":
    unittest.main()
