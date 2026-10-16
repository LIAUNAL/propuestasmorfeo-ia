"""Tests for PDF Annotator and editorial execution engine."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import json

from morfeo.core.pdf_annotator import (
    _build_fuzzy_regex,
    _humanize_text_span,
    _normalize_words,
    apply_pdf_annotations,
)


class TestPdfAnnotator(unittest.TestCase):
    def _workspace(self, tmpdir: str) -> tuple[Path, Path]:
        run_dir = Path(tmpdir) / "run_01"
        sections = run_dir / "redaccion" / "sections"
        sections.mkdir(parents=True)
        sec = sections / "00_frontmatter.tex"
        sec.write_text(
            "El entrenamiento externo se apoya en los corpus DAIC-WOZ.\n"
            "El acompañamiento corre por cuenta de la psicóloga Camila.\n",
            encoding="utf-8",
        )
        return run_dir, sec

    def _pendientes(self, run_dir: Path) -> Path:
        return run_dir / "artefactos" / "pipeline" / "instrucciones_revisor_pdf.md"

    def test_comment_registers_an_instruction_and_leaves_the_source_untouched(self):
        """Un comentario no puede reescribir prosa: insertaba una línea `%` que
        LaTeX ignora, y el informe lo presentaba como cambio aplicado. El
        operador pidió que la instrucción viaje al agente del pipeline en lugar
        de ensuciar la fuente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, sec = self._workspace(tmpdir)
            antes = sec.read_text(encoding="utf-8")

            res = apply_pdf_annotations(run_dir, [{
                "id": "ann1",
                "type": "comment",
                "text": "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                "comment": "reescribir en general, sin nombrar a la psicóloga",
                "page": 1,
            }])

            self.assertTrue(res["ok"])
            self.assertEqual(
                sec.read_text(encoding="utf-8"), antes, "la fuente no se toca"
            )
            self.assertNotIn("COMENTARIO REVISOR PDF", antes)
            self.assertEqual(res["summary"]["comments_applied"], 0)
            self.assertEqual(res["summary"]["comments_registered"], 1)
            self.assertEqual(res["summary"]["files_modified"], [])

            pendientes = self._pendientes(run_dir)
            self.assertTrue(pendientes.is_file())
            texto = pendientes.read_text(encoding="utf-8")
            self.assertIn("reescribir en general, sin nombrar a la psicóloga", texto)
            self.assertIn("Pág. 1", texto)
            self.assertIn("00_frontmatter.tex", texto)
            self.assertIn("- [ ]", texto, "la instrucción queda pendiente de marcar")

    def test_pending_instructions_accumulate_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, _ = self._workspace(tmpdir)
            base = {
                "type": "comment",
                "text": "El acompañamiento corre por cuenta de la psicóloga Camila.",
                "comment": "generalizar la mención",
                "page": 2,
            }
            apply_pdf_annotations(run_dir, [dict(base, id="ann1")])
            apply_pdf_annotations(run_dir, [dict(base, id="ann2")])
            texto = self._pendientes(run_dir).read_text(encoding="utf-8")
            self.assertEqual(texto.count("generalizar la mención"), 1)

            apply_pdf_annotations(
                run_dir, [dict(base, id="ann3", comment="otra instrucción")]
            )
            texto = self._pendientes(run_dir).read_text(encoding="utf-8")
            self.assertEqual(texto.count("generalizar la mención"), 1)
            self.assertEqual(texto.count("otra instrucción"), 1)

    def test_an_unlocated_comment_still_reaches_the_agent(self):
        """La instrucción sigue siendo válida aunque el ancla no se localice: la
        localización era un requisito de las marcas que modifican el texto, no
        de las que lo instruyen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, _ = self._workspace(tmpdir)
            res = apply_pdf_annotations(run_dir, [{
                "id": "ann1",
                "type": "comment",
                "text": "Un párrafo que no existe en ninguna sección fuente.",
                "comment": "revisar el tono de este pasaje",
                "page": 7,
            }])
            self.assertEqual(res["summary"]["comments_registered"], 1)
            self.assertEqual(res["summary"]["comments_failed"], 0)
            texto = self._pendientes(run_dir).read_text(encoding="utf-8")
            self.assertIn("revisar el tono de este pasaje", texto)
            self.assertIn("sin ubicar", texto)

    def test_replacement_changes_the_anchored_span_literally(self):
        """Un reemplazo no pasa por el agente: el panel sustituye el pasaje
        anclado por el texto literal y recompila. Sin modelo de por medio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, sec = self._workspace(tmpdir)
            res = apply_pdf_annotations(run_dir, [{
                "id": "ann1",
                "type": "replace",
                "text": "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                "replacement": "El entrenamiento se apoya en corpus clínicos externos.",
                "page": 1,
            }])

            self.assertTrue(res["ok"])
            self.assertEqual(res["summary"]["replace_applied"], 1)
            self.assertEqual(res["summary"]["replace_failed"], 0)
            texto = sec.read_text(encoding="utf-8")
            self.assertIn("El entrenamiento se apoya en corpus clínicos externos.", texto)
            self.assertNotIn("DAIC-WOZ", texto)
            self.assertIn(
                "redaccion/sections/00_frontmatter.tex", res["summary"]["files_modified"]
            )
            self.assertFalse(res["summary"]["pdf_recompile_skipped"])

    def test_replacement_without_a_located_anchor_changes_nothing(self):
        """El ancla es la única garantía de que se reemplaza el pasaje correcto:
        sin ella no se toca la fuente y el operador recibe el motivo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, sec = self._workspace(tmpdir)
            antes = sec.read_text(encoding="utf-8")
            res = apply_pdf_annotations(run_dir, [{
                "id": "ann1",
                "type": "replace",
                "text": "Un pasaje que no existe en ninguna sección fuente.",
                "replacement": "texto que nunca debería escribirse",
                "page": 9,
            }])

            self.assertTrue(res["ok"])
            self.assertEqual(res["summary"]["replace_applied"], 0)
            self.assertEqual(res["summary"]["replace_failed"], 1)
            self.assertEqual(sec.read_text(encoding="utf-8"), antes, "la fuente no se toca")
            reasons = [u["reason"] for u in res["summary"]["unmatched"]]
            self.assertTrue(
                any("no localizado" in reason.lower() for reason in reasons),
                f"el motivo debe decir que el ancla no se localizó: {reasons}",
            )

    def test_empty_replacement_needs_a_deliberate_deletion(self):
        """Un reemplazo vacío es un borrado: solo se aplica si el operador lo
        confirmó, nunca porque el campo viaje vacío por descuido."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, sec = self._workspace(tmpdir)
            antes = sec.read_text(encoding="utf-8")

            accidental = apply_pdf_annotations(run_dir, [{
                "id": "ann1",
                "type": "replace",
                "text": "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                "replacement": "",
                "page": 1,
            }])
            self.assertEqual(accidental["summary"]["replace_applied"], 0)
            self.assertEqual(accidental["summary"]["replace_failed"], 1)
            self.assertEqual(sec.read_text(encoding="utf-8"), antes, "no se borra por descuido")

            deliberate = apply_pdf_annotations(run_dir, [{
                "id": "ann2",
                "type": "replace",
                "text": "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                "replacement": "",
                "delete_intent": True,
                "page": 1,
            }])
            self.assertEqual(deliberate["summary"]["replace_applied"], 1)
            self.assertNotIn(
                "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                sec.read_text(encoding="utf-8"),
            )

    def test_replacement_metric_is_persisted_with_the_other_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, _ = self._workspace(tmpdir)
            apply_pdf_annotations(run_dir, [{
                "id": "ann1",
                "type": "replace",
                "text": "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                "replacement": "El entrenamiento se apoya en corpus clínicos externos.",
                "page": 1,
            }])
            payload = json.loads(
                (run_dir / "artefactos" / "pipeline" / "anotaciones_pdf.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["applied"]["replace"], 1)

    def test_comment_only_run_does_not_claim_a_recompilation(self):
        """Recompilar sin cambios en el manuscrito produce un PDF idéntico y
        refuerza la ilusión de que algo se aplicó."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, _ = self._workspace(tmpdir)
            res = apply_pdf_annotations(run_dir, [{
                "id": "ann1",
                "type": "comment",
                "text": "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                "comment": "aclarar el alcance de los corpus",
                "page": 1,
            }])
            self.assertFalse(res["summary"]["pdf_recompiled"])
            self.assertIn("sin cambios", res["summary"]["pdf_recompile_reason"])
            self.assertTrue(res["summary"]["pdf_recompile_skipped"])

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
            self.assertEqual(summary["comments_applied"], 0)
            self.assertEqual(summary["comments_registered"], 1)
            self.assertEqual(summary["humanize_applied"], 1)

            # Check modified content
            modified_text = sec_tex.read_text(encoding="utf-8")
            self.assertNotIn("Es importante destacar que", modified_text)
            self.assertNotIn("Este texto será tachado y eliminado completamente.", modified_text)
            # Comportamiento cambiado a propósito: un comentario ya no inserta
            # una línea `%` en la fuente, porque LaTeX la ignora y el informe
            # afirmaba un cambio que el documento no podía mostrar.
            self.assertNotIn("COMENTARIO REVISOR PDF", modified_text)
            self.assertNotIn("Aclarar detalles de la muestra territorial", modified_text)
            self.assertEqual(summary["comments_applied"], 0)
            self.assertEqual(summary["comments_registered"], 1)

            # Check report persistence
            rep_json = run_dir / "artefactos" / "pipeline" / "anotaciones_pdf.json"
            rep_md = run_dir / "artefactos" / "anotaciones_pdf.md"
            self.assertTrue(rep_json.is_file())
            self.assertTrue(rep_md.is_file())


if __name__ == "__main__":
    unittest.main()
