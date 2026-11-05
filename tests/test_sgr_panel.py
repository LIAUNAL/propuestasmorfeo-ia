"""Panel data for TDR chapters and the style report (S9 of sgr-flujo-convocatorias)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from morfeo.core.sgr_panel import load_style_report, load_tdr_chapters  # noqa: E402


class PanelData(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = Path(self.tmp.name)
        (self.run_dir / "artefactos" / "estilo").mkdir(parents=True)
        (self.run_dir / "redaccion" / "sections").mkdir(parents=True)

    def write_structure(self, data):
        (self.run_dir / "artefactos" / "estructura_tdr.json").write_text(json.dumps(data), encoding="utf-8")

    def test_no_structure_gives_no_chapters(self):
        self.assertEqual(load_tdr_chapters(self.run_dir)["capitulos"], [])

    def test_invalid_structure_gives_no_chapters(self):
        (self.run_dir / "artefactos" / "estructura_tdr.json").write_text("{", encoding="utf-8")
        self.assertEqual(load_tdr_chapters(self.run_dir)["capitulos"], [])

    def test_chapter_state_follows_its_files(self):
        (self.run_dir / "redaccion" / "sections" / "tdr01_a.tex").write_text("uno dos tres", encoding="utf-8")
        (self.run_dir / "redaccion" / "sections" / "tdr02_a.tex").write_text("uno", encoding="utf-8")
        self.write_structure({"fuente": "Anexo 2", "capitulos": [
            {"numero": 1, "titulo": "A", "archivos": ["tdr01_a", "diag_x"]},
            {"numero": 2, "titulo": "B", "archivos": ["tdr02_a", "tdr02_b"]},
            {"numero": 3, "titulo": "C", "archivos": ["tdr03_a"]},
        ]})
        data = load_tdr_chapters(self.run_dir)
        self.assertEqual(data["fuente"], "Anexo 2")
        self.assertEqual([c["estado"] for c in data["capitulos"]], ["escrito", "parcial", "vacio"])
        self.assertEqual(data["capitulos"][0]["archivos"][0]["palabras"], 3)

    def test_no_report_is_not_available(self):
        self.assertEqual(load_style_report(self.run_dir), {"disponible": False})

    def test_report_is_returned(self):
        path = self.run_dir / "artefactos" / "estilo" / "reporte.json"
        path.write_text(json.dumps({"indice": 80}), encoding="utf-8")
        self.assertEqual(load_style_report(self.run_dir), {"disponible": True, "indice": 80})

    def test_broken_report_is_not_available(self):
        (self.run_dir / "artefactos" / "estilo" / "reporte.json").write_text("{", encoding="utf-8")
        self.assertFalse(load_style_report(self.run_dir)["disponible"])


if __name__ == "__main__":
    unittest.main()
