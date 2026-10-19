"""Tests for PDF Annotator and editorial execution engine."""

from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

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
            self.assertEqual(res["summary"]["annotations_failed"], 0)
            texto = self._pendientes(run_dir).read_text(encoding="utf-8")
            self.assertIn("revisar el tono de este pasaje", texto)
            self.assertIn("sin ubicar", texto)

    def test_comment_without_anchor_is_failed_instead_of_vanishing(self):
        """Una anotación sin texto ancla no puede nombrar a qué se refiere; antes
        desaparecía en silencio: ni se registraba, ni se contaba como fallo, solo
        inflaba `total_submitted`. El operador debe ver el desenlace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, _ = self._workspace(tmpdir)
            res = apply_pdf_annotations(run_dir, [{
                "id": "ann1",
                "type": "comment",
                "text": "   ",
                "comment": "una instrucción que no nombra su ancla",
                "page": 4,
            }])
            summary = res["summary"]
            self.assertTrue(res["ok"])
            self.assertEqual(summary["total_submitted"], 1)
            self.assertEqual(summary["comments_registered"], 0)
            self.assertEqual(summary["comments_failed"], 1)
            self.assertEqual(summary["annotations_failed"], 1)

            fallos = res["details"]["unmatched"]
            self.assertEqual(len(fallos), 1)
            self.assertEqual(fallos[0]["type"], "comment")

            pendientes = self._pendientes(run_dir)
            if pendientes.is_file():
                self.assertNotIn(
                    "una instrucción que no nombra su ancla",
                    pendientes.read_text(encoding="utf-8"),
                    "una anotación sin ancla no deja una instrucción huérfana en la cola",
                )

    def test_unmatched_strikethrough_in_a_mixed_batch_is_counted_as_a_failure(self):
        """Un tachado que no se localiza no aparecía en ningún campo del resumen;
        solo quedaba en el detalle. El conteo agregado debe delatarlo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, _ = self._workspace(tmpdir)
            res = apply_pdf_annotations(run_dir, [
                {
                    "id": "a1",
                    "type": "strikethrough",
                    "text": "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                    "page": 1,
                },
                {
                    "id": "a2",
                    "type": "strikethrough",
                    "text": "Un texto que no existe en ninguna sección fuente.",
                    "page": 2,
                },
            ])
            summary = res["summary"]
            self.assertEqual(summary["strikethrough_applied"], 1)
            self.assertEqual(summary["annotations_failed"], 1)
            self.assertEqual(len(res["details"]["unmatched"]), 1)
            self.assertEqual(res["details"]["unmatched"][0]["type"], "strikethrough")

    def test_deduplicated_batch_is_reported_as_deduplicated_not_as_applied_work(self):
        """`comments_registered` contaba la lista en memoria aunque no se
        escribiera nada: reenviar el mismo lote decía «1 registrada» con el
        archivo intacto. Lo omitido por duplicado es su propio número."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, _ = self._workspace(tmpdir)
            base = {
                "type": "comment",
                "text": "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                "comment": "unificar la redacción de este pasaje",
                "page": 1,
            }
            first = apply_pdf_annotations(run_dir, [dict(base, id="ann1")])
            self.assertEqual(first["summary"]["comments_registered"], 1)
            self.assertEqual(first["summary"]["comments_duplicated"], 0)

            second = apply_pdf_annotations(run_dir, [dict(base, id="ann2")])
            self.assertEqual(
                second["summary"]["comments_registered"],
                0,
                "un lote duplicado no escribe nada y no puede reportarse como registrado",
            )
            self.assertEqual(second["summary"]["comments_duplicated"], 1)

            texto = self._pendientes(run_dir).read_text(encoding="utf-8")
            self.assertEqual(texto.count("unificar la redacción de este pasaje"), 1)

    def test_a_second_run_preserves_the_existing_queue_byte_for_byte(self):
        """La cola es el único registro de una instrucción sin ejecutar. Si se
        reescribe desde cero, un fallo a mitad de escritura la pierde. Conservar
        los bytes anteriores es la garantía mínima."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, _ = self._workspace(tmpdir)
            apply_pdf_annotations(run_dir, [{
                "id": "ann1",
                "type": "comment",
                "text": "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                "comment": "primera instrucción",
                "page": 1,
            }])
            pendientes = self._pendientes(run_dir)
            antes = pendientes.read_bytes()

            apply_pdf_annotations(run_dir, [{
                "id": "ann2",
                "type": "comment",
                "text": "El acompañamiento corre por cuenta de la psicóloga Camila.",
                "comment": "segunda instrucción",
                "page": 2,
            }])
            despues = pendientes.read_bytes()
            self.assertTrue(
                despues.startswith(antes),
                "la cola existente debe conservarse byte a byte tras una segunda corrida",
            )
            self.assertIn(b"segunda instrucci", despues)

    def test_a_crash_while_registering_does_not_lose_the_existing_queue(self):
        """La cola se reescribía entera con `write_text`, que primero trunca. Un
        fallo en esa escritura borraba las instrucciones que ya estaban, y no hay
        copia recuperable en otro sitio. Registrar no puede destruir lo previo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, _ = self._workspace(tmpdir)
            apply_pdf_annotations(run_dir, [{
                "id": "ann1",
                "type": "comment",
                "text": "El entrenamiento externo se apoya en los corpus DAIC-WOZ.",
                "comment": "primera instrucción",
                "page": 1,
            }])
            pendientes = self._pendientes(run_dir)
            antes = pendientes.read_bytes()

            original = Path.write_text

            def crashing_write_text(self, data, *args, **kwargs):
                if self == pendientes:
                    # Simula el truncado previo a la escritura y el fallo posterior.
                    with open(self, "w", encoding="utf-8"):
                        pass
                    raise OSError("fallo simulado durante el registro")
                return original(self, data, *args, **kwargs)

            with mock.patch.object(Path, "write_text", crashing_write_text):
                try:
                    apply_pdf_annotations(run_dir, [{
                        "id": "ann2",
                        "type": "comment",
                        "text": "El acompañamiento corre por cuenta de la psicóloga Camila.",
                        "comment": "segunda instrucción",
                        "page": 2,
                    }])
                except OSError:
                    pass

            self.assertTrue(
                pendientes.read_bytes().startswith(antes),
                "un fallo al registrar no puede borrar la cola que ya existía",
            )

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

    def test_comment_with_punctuation_removal_directive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, sec = self._workspace(tmpdir)
            # Add a passage with trailing period or punctuation
            sec.write_text("ante la demanda posdesastre. Frente a este panorama", encoding="utf-8")
            res = apply_pdf_annotations(run_dir, [{
                "id": "ann_punct",
                "type": "comment",
                "text": "posdesastre.",
                "comment": "quitar los dos puntos",
                "page": 1,
            }])
            self.assertTrue(res["ok"])
            content = sec.read_text(encoding="utf-8")
            self.assertIn("ante la demanda posdesastre Frente a este panorama", content)
            self.assertNotIn("posdesastre.", content)
            self.assertIn("redaccion/sections/00_frontmatter.tex", res["summary"]["files_modified"])

    def test_comment_with_humanize_directive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, sec = self._workspace(tmpdir)
            sec.write_text("Es importante destacar que el sistema opera con inferencia local.", encoding="utf-8")
            res = apply_pdf_annotations(run_dir, [{
                "id": "ann_hum",
                "type": "comment",
                "text": "Es importante destacar que el sistema opera con inferencia local.",
                "comment": "redactar de forma diferente",
                "page": 1,
            }])
            self.assertTrue(res["ok"])
            content = sec.read_text(encoding="utf-8")
            self.assertNotIn("Es importante destacar que", content)
            self.assertIn("El sistema opera con inferencia local.", content)

    def test_comment_with_replace_directive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, sec = self._workspace(tmpdir)
            sec.write_text("El prototipo alcanza TRL 4.", encoding="utf-8")
            res = apply_pdf_annotations(run_dir, [{
                "id": "ann_repl",
                "type": "comment",
                "text": "TRL 4",
                "comment": "cambiar por TRL 6",
                "page": 1,
            }])
            self.assertTrue(res["ok"])
            content = sec.read_text(encoding="utf-8")
            self.assertIn("El prototipo alcanza TRL 6.", content)

    def test_find_text_span_with_punctuation_variance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, sec = self._workspace(tmpdir)
            sec.write_text("ante la demanda posdesastre. Frente a este panorama", encoding="utf-8")
            # User selected "posdesastre. ." with double dot in PDF
            res = apply_pdf_annotations(run_dir, [{
                "id": "ann_pvar",
                "type": "strikethrough",
                "text": "posdesastre. .",
                "page": 1,
            }])
            self.assertTrue(res["ok"])
            content = sec.read_text(encoding="utf-8")
            # Anchor was found and struck out
            self.assertNotIn("posdesastre.", content)


    def test_strikethrough_returns_surrounding_sentences(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, sec = self._workspace(tmpdir)
            sec.write_text(
                "La primera oración introduce el problema. "
                "Esta segunda oración debe ser eliminada por completo. "
                "La tercera oración concluye el argumento.",
                encoding="utf-8"
            )
            res = apply_pdf_annotations(run_dir, [{
                "id": "ann_del",
                "type": "strikethrough",
                "text": "Esta segunda oración debe ser eliminada por completo.",
                "page": 1,
            }])
            self.assertTrue(res["ok"])
            applied = res["details"]["strikethrough"]
            self.assertEqual(len(applied), 1)
            self.assertIn("La primera oración introduce el problema", applied[0]["context_before"])
            self.assertIn("La tercera oración concluye el argumento", applied[0]["context_after"])

    def test_execute_button_applies_comments_humanize_and_strikethrough_with_strict_section_isolation(self):
        """Al pulsar 'Ejecutar cambios' (process_pending=True), el redactor y grant-flow-auditor
        aplican comentarios, tachados y humanización únicamente sobre los fragmentos pedidos
        sin alterar otras oraciones, otras secciones ni el preámbulo de main.tex.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir, sec0 = self._workspace(tmpdir)
            sections_dir = run_dir / "redaccion" / "sections"
            main_tex = run_dir / "redaccion" / "main.tex"
            main_original = (
                "\\documentclass[11pt,a4paper]{article}\n"
                "\\usepackage{natbib}\n"
                "\\begin{document}\n"
                "\\input{sections/00_frontmatter.tex}\n"
                "\\input{sections/02_justificacion_pertinencia.tex}\n"
                "\\input{sections/03_descripcion_problema.tex}\n"
                "\\end{document}\n"
            )
            main_tex.write_text(main_original, encoding="utf-8")

            sec0_original = sec0.read_text(encoding="utf-8")
            sec2 = sections_dir / "02_justificacion_pertinencia.tex"
            sec2_original = (
                "\\section{Justificación y pertinencia}\n"
                "Este párrafo de justificación permanece intacto de principio a fin.\n"
            )
            sec2.write_text(sec2_original, encoding="utf-8")

            sec3 = sections_dir / "03_descripcion_problema.tex"
            sec3.write_text(
                "\\section{Descripción del problema}\n"
                "Párrafo uno intacto sobre el contexto cafetero.\n\n"
                "El protocolo cuenta con el apoyo de la psicóloga Camila para las entrevistas.\n\n"
                "Es importante destacar que el módulo procesa señales con \\textbf{inferencia local} en campo.\n\n"
                "Esta frase redundante debe tacharse sin afectar el cierre. El cierre del capítulo permanece igual.\n",
                encoding="utf-8",
            )

            res = apply_pdf_annotations(
                run_dir,
                [
                    {
                        "id": "c_gen",
                        "type": "comment",
                        "text": "El protocolo cuenta con el apoyo de la psicóloga Camila para las entrevistas.",
                        "comment": "reescribir en general, sin nombrar a la psicóloga Camila",
                        "page": 3,
                    },
                    {
                        "id": "h_span",
                        "type": "humanize",
                        "text": "Es importante destacar que el módulo procesa señales con inferencia local en campo.",
                        "page": 3,
                    },
                    {
                        "id": "s_span",
                        "type": "strikethrough",
                        "text": "Esta frase redundante debe tacharse sin afectar el cierre.",
                        "page": 3,
                    },
                ],
                process_pending=True,
            )

            self.assertTrue(res["ok"])
            self.assertEqual(res["summary"]["comments_applied"], 1)
            self.assertEqual(res["summary"]["humanize_applied"], 1)
            self.assertEqual(res["summary"]["strikethrough_applied"], 1)
            self.assertIn("redactor", res["summary"]["agents_invoked"])
            self.assertIn("grant-flow-auditor", res["summary"]["agents_invoked"])
            self.assertEqual(res["summary"]["files_modified"], ["redaccion/sections/03_descripcion_problema.tex"])

            # Otras secciones y main.tex quedan 100% intactos byte a byte
            self.assertEqual(main_tex.read_text(encoding="utf-8"), main_original)
            self.assertEqual(sec0.read_text(encoding="utf-8"), sec0_original)
            self.assertEqual(sec2.read_text(encoding="utf-8"), sec2_original)

            # En la sección 03, solo cambiaron los fragmentos seleccionados
            updated_sec3 = sec3.read_text(encoding="utf-8")
            self.assertIn("Párrafo uno intacto sobre el contexto cafetero.", updated_sec3)
            self.assertNotIn("Camila", updated_sec3)
            self.assertNotIn("Es importante destacar que", updated_sec3)
            self.assertIn("\\textbf{inferencia local}", updated_sec3)
            self.assertNotIn("Esta frase redundante debe tacharse sin afectar el cierre.", updated_sec3)
            self.assertIn("El cierre del capítulo permanece igual.", updated_sec3)


if __name__ == "__main__":
    unittest.main()


