"""Tests for PDF Annotator and editorial execution engine."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from morfeo.core.pdf_annotator import (
    _build_fuzzy_regex,
    _humanize_text_span,
    _normalize_words,
    apply_pdf_annotations,
)


class TestPdfAnnotator(unittest.TestCase):
    def test_normalize_words(self):
        text = "  Hola,   mundo   con \n saltos de \t línea. "
        words = _normalize_words(text)
        self.assertEqual(words, ["Hola,", "mundo", "con", "saltos", "de", "línea."])

    def test_fuzzy_regex_matching(self):
        import re
        words = ["depresión", "asociado", "a", "estrés"]
        pattern = _build_fuzzy_regex(words)
        sample = "depresión\n   asociado   a\t\n  estrés"
        self.assertTrue(re.search(pattern, sample))

    def test_humanize_text_span_removes_fillers(self):
        sample = "Es importante destacar que el modelo de aprendizaje profundo alcanza un 89.4% de F1-score."
        result = _humanize_text_span(sample)
        self.assertNotIn("Es importante destacar que", result)
        self.assertIn("89.4%", result)
        self.assertIn("F1-score", result)

    def test_apply_pdf_annotations_mock_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run_01"
            redaccion = run_dir / "redaccion"
            sections = redaccion / "sections"
            sections.mkdir(parents=True)

            sec_tex = sections / "02_justificacion.tex"
            sec_tex.write_text(
                "Es importante destacar que el sistema evalúa la cohorte.\n"
                "Este texto será tachado y eliminado completamente.\n"
                "Este tercer párrafo recibirá un comentario explicativo.\n",
                encoding="utf-8"
            )

            annotations = [
                {
                    "id": "ann1",
                    "type": "humanize",
                    "text": "Es importante destacar que el sistema evalúa la cohorte.",
                    "page": 2
                },
                {
                    "id": "ann2",
                    "type": "strikethrough",
                    "text": "Este texto será tachado y eliminado completamente.",
                    "page": 2
                },
                {
                    "id": "ann3",
                    "type": "comment",
                    "text": "Este tercer párrafo recibirá un comentario explicativo.",
                    "comment": "Aclarar detalles de la muestra territorial",
                    "page": 2
                }
            ]

            res = apply_pdf_annotations(run_dir, annotations)
            self.assertTrue(res["ok"])
            summary = res["summary"]
            self.assertEqual(summary["total_submitted"], 3)
            self.assertEqual(summary["strikethrough_applied"], 1)
            self.assertEqual(summary["comments_applied"], 1)
            self.assertEqual(summary["humanize_applied"], 1)

            # Check modified content
            modified_text = sec_tex.read_text(encoding="utf-8")
            self.assertNotIn("Es importante destacar que", modified_text)
            self.assertNotIn("Este texto será tachado y eliminado completamente.", modified_text)
            self.assertIn("COMENTARIO REVISOR PDF", modified_text)
            self.assertIn("Aclarar detalles de la muestra territorial", modified_text)

            # Check report persistence
            rep_json = run_dir / "artefactos" / "pipeline" / "anotaciones_pdf.json"
            rep_md = run_dir / "artefactos" / "anotaciones_pdf.md"
            self.assertTrue(rep_json.is_file())
            self.assertTrue(rep_md.is_file())


if __name__ == "__main__":
    unittest.main()
