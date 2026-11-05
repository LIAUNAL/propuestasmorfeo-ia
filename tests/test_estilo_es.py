"""Readability and redundancy scoring in Spanish (odd/tasks/sgr-flujo-convocatorias.md, S7 and S8).

`scripts/estilo_es.py auditar` scores a run, a .docx or a text file and writes
`artefactos/estilo/reporte.json` and `.md`; `verificar` is the only command that
fails, when a rewrite changes a fact. The tests go through the CLI, except for
the tokenizer, the sentence splitter and MATTR, which are checked directly.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "estilo_es.py"
ESTILO_SKILL = REPO / ".claude" / "skills" / "estilo-natural-es" / "SKILL.md"
DEPURACION_SKILL = REPO / ".claude" / "skills" / "depuracion-redundancias-es" / "SKILL.md"
AUDITOR = REPO / ".claude" / "agents" / "grant-flow-auditor.md"
REVISOR = REPO / ".claude" / "agents" / "revisor-redundancia.md"


def load_module():
    spec = importlib.util.spec_from_file_location("estilo_es", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["estilo_es"] = module
    spec.loader.exec_module(module)
    return module


def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def filler(sentences: int, start: int = 0) -> str:
    """Sentences of twelve invented words that never repeat, so no rule fires on them."""
    syllables = ("ba", "ce", "di", "fo", "gu", "la", "me", "ni", "po", "ru", "sa", "te", "vi", "zo")
    out, n = [], start
    for _ in range(sentences):
        words = []
        for _ in range(12):
            a, b = divmod(n, len(syllables))
            b2, c = divmod(a, len(syllables))
            words.append(syllables[b] + syllables[c] + syllables[b2 % len(syllables)] + "n")
            n += 1
        out.append(" ".join(words).capitalize() + ".")
    return " ".join(out)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def audit_text(self, text: str) -> dict:
        path = self.tmp / "texto.txt"
        path.write_text(text, encoding="utf-8")
        result = cli("auditar", "--txt", path, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def categories(self, text: str) -> set:
        return {f["categoria"] for f in self.audit_text(text)["hallazgos"]}

    def make_run(self, sections: dict, flujo: str | None = None) -> Path:
        run = self.tmp / "corrida"
        (run / "redaccion" / "sections").mkdir(parents=True)
        (run / "artefactos").mkdir()
        for name, text in sections.items():
            (run / "redaccion" / "sections" / f"{name}.tex").write_text(text, encoding="utf-8")
        if flujo:
            (self.tmp / ".morfeo").mkdir()
            (self.tmp / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
        return run

    def audit_run(self, run: Path, *flags: str) -> dict:
        result = cli("auditar", run, *flags, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class TokenizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.m = load_module()

    def test_accented_words_stay_whole(self) -> None:
        self.assertEqual(self.m.tokenize("La investigación de Ángel en Ñuñoa, ¿sí?"),
                         ["la", "investigación", "de", "ángel", "en", "ñuñoa", "sí"])

    def test_accented_capitals_and_inverted_marks_open_sentences(self) -> None:
        text = "El equipo midió. Él repitió la medida. ¿Qué cambió? Ángel lo anotó. Ñame fue la muestra. ¡Bien hecho!"
        self.assertEqual(len(self.m.split_sentences(text)), 6)

    def test_abbreviations_do_not_end_sentences(self) -> None:
        text = "Según Pérez et al. la tasa creció. El efecto, p. ej. en la fig. 3 y en la p. 12, fue claro."
        self.assertEqual(len(self.m.split_sentences(text)), 2)

    def test_emphasis_keeps_its_content_and_citations_go(self) -> None:
        tex = r"Se evaluó el \emph{aprendizaje profundo} con \textbf{datos locales} \citep{perez2020}."
        paragraphs = self.m.latex_paragraphs(tex)
        self.assertEqual(len(paragraphs), 1)
        words = self.m.tokenize(paragraphs[0].text)
        self.assertIn("aprendizaje", words)
        self.assertIn("locales", words)
        self.assertNotIn("perez2020", words)

    def test_escaped_dollar_amounts_are_not_math(self) -> None:
        tex = r"El rubro cuesta \$1.000 y el segundo rubro \$2.000 en total; la tasa $x^2$ se omite."
        words = self.m.tokenize(self.m.latex_paragraphs(tex)[0].text)
        self.assertIn("rubro", words)
        self.assertIn("segundo", words)
        self.assertNotIn("x", words)

    def test_comment_lines_do_not_break_a_paragraph(self) -> None:
        tex = "Primera línea del párrafo\n% nota interna\nsegunda línea del párrafo.\n\nOtro párrafo."
        self.assertEqual(len(self.m.latex_paragraphs(tex)), 2)

    def test_mattr_does_not_depend_on_length(self) -> None:
        cycle = [f"palabra{i}" for i in range(100)]
        self.assertAlmostEqual(self.m.mattr(cycle * 2, 200), 0.5)
        self.assertAlmostEqual(self.m.mattr(cycle * 50, 200), 0.5)

    def test_mattr_needs_one_full_window(self) -> None:
        self.assertIsNone(self.m.mattr(["uno", "dos"], 200))


class CategoryTests(Base):
    CASES = {
        "cliche": ("La plataforma juega un papel fundamental en la región.",
                   "La plataforma reduce el error en la región."),
        "comodin": ("El ecosistema de datos crece.", "El conjunto de datos crece."),
        "promocional": ("Es un enfoque revolucionario.", "Es un enfoque nuevo."),
        "atribucion_vaga": ("Estudios recientes señalan una mejora del tres por ciento.",
                            r"Pérez mide una mejora del tres por ciento."),
        "perifrasis": ("Debido al hecho de que falla, se reinicia.", "Dado que falla, se reinicia."),
        "copula_evitada": ("El grupo se posiciona como referente.", "El grupo es referente."),
        "calco": ("Esa hipótesis es consistente con los datos.", "Esa hipótesis es coherente con los datos."),
        "plantilla": ("Cabe destacar que el sistema opera sin red.", "El sistema opera sin red."),
        "paralelismo_negativo": ("El sistema no solo clasifica, sino que explica.",
                                 "El sistema clasifica y explica."),
        "falso_rango": ("Abarca desde la captura de señales hasta la inclusión territorial.",
                        "Abarca desde 2020 hasta 2024."),
        "gerundio_cierre": ("El modelo mejora la precisión, garantizando un impacto duradero.",
                            "El modelo mejora la precisión y el impacto dura."),
        "raya": ("El modelo — entrenado en campo — mejora.", "El modelo, entrenado en campo, mejora."),
        "oracion_larga": (" ".join(["palabra"] * 46) + ".", " ".join(["palabra"] * 45) + "."),
        "triada": ("Exige innovación, rigor y pertinencia. Mide captura, proceso y evaluación.",
                   "Exige innovación y rigor. Mide captura y evaluación."),
        "conector_repeticion": ("Asimismo, el equipo mide. El grupo anota. Asimismo, el panel revisa.",
                                "Asimismo, el equipo mide. El grupo anota. Luego el panel revisa."),
        "apertura_repetida": ("El equipo mide la voz. El equipo anota la voz.",
                              "El equipo mide la voz. Luego anota la voz."),
        "demostrativo": ("Este modelo mide. Esta tarea anota. Estos datos suman. Dicho panel revisa.",
                         "El modelo mide. La tarea anota. Los datos suman. El panel revisa."),
        "causal_densidad": ("Falla porque hay ruido. Cae, ya que hay polvo. Para porque hay calor.",
                            "Falla por el ruido. Cae con polvo. Para con calor."),
        "cola_relativa": ("Mide la voz, lo cual ayuda. Anota el ritmo, lo que sirve.",
                          "Mide la voz y ayuda. Anota el ritmo y sirve."),
    }

    def test_each_category_fires_and_stays_silent(self) -> None:
        for category, (firing, silent) in self.CASES.items():
            with self.subTest(category=category):
                self.assertIn(category, self.categories(firing))
                self.assertNotIn(category, self.categories(silent))

    def test_finding_has_location_category_and_guidance(self) -> None:
        finding = self.audit_text("Primera oración sin problema.\n\nOtra oración clara. Cabe destacar que falla.")["hallazgos"][0]
        self.assertEqual((finding["parrafo"], finding["oracion"], finding["categoria"]), (2, 3, "plantilla"))
        self.assertTrue(finding["seccion"])
        self.assertTrue(finding["orientacion"])
        self.assertIn("Cabe destacar que", finding["fragmento"])

    def test_quotes_show_no_internal_markers(self) -> None:
        long_text = r"\citet{perez2020} mide " + " ".join(["palabra"] * 50) + r" \citep{gomez2021}."
        run = self.make_run({"02_justificacion": long_text})
        found = [f for f in self.audit_run(run)["hallazgos"] if f["categoria"] == "oracion_larga"]
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["fragmento"].startswith("(cita) mide palabra"))

    def test_cited_attribution_is_not_vague(self) -> None:
        run = self.make_run({"02_justificacion": r"Estudios recientes señalan una mejora \citep{perez2020}."})
        self.assertNotIn("atribucion_vaga", {f["categoria"] for f in self.audit_run(run)["hallazgos"]})

    def test_repeated_phrase_counts_once_however_long(self) -> None:
        phrase = "acompañamiento y asesoría de personal especializado en territorio rural"
        text = (f"El plan ofrece {phrase} desde enero. Luego hay {phrase} en marzo.\n\n"
                f"La sede pide {phrase} para mayo.")
        found = [f for f in self.audit_text(text)["hallazgos"] if f["categoria"] == "frase_repetida"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["fragmento"], phrase)
        self.assertEqual(len(found[0]["ubicaciones"]), 3)

    def test_phrase_in_two_sentences_is_silent(self) -> None:
        phrase = "acompañamiento y asesoría de personal especializado"
        self.assertNotIn("frase_repetida", self.categories(f"Hay {phrase} aquí.\n\nHay {phrase} allá."))

    def test_near_duplicate_sentences(self) -> None:
        one = "El sistema portable procesa señales acústicas clínicas locales durante entrevistas universitarias."
        two = "Durante entrevistas universitarias locales, el sistema portable procesa señales acústicas clínicas."
        self.assertIn("casi_duplicado", self.categories(f"{one}\n\n{two}"))
        self.assertNotIn("casi_duplicado", self.categories(f"{one}\n\nLa sede rural guarda muestras anónimas cifradas todos los lunes."))

    def test_overused_word_stands_out_from_the_document(self) -> None:
        parts = [filler(1, start=i * 24)[:-1] + " mediante " + filler(1, start=i * 24 + 12).lower() for i in range(100)]
        found = [f for f in self.audit_text(" ".join(parts))["hallazgos"] if f["categoria"] == "sobreuso"]
        self.assertEqual([f["fragmento"] for f in found], ["mediante"])
        self.assertGreater(found[0]["por_1000"], 5)

    def test_even_vocabulary_has_no_overused_word(self) -> None:
        self.assertNotIn("sobreuso", self.categories(filler(120)))


class ScoreTests(Base):
    CLEAN = "El equipo mide la voz en la sede. Luego anota el ritmo de cada entrevista. La tasa baja con el tiempo."
    BAD = ("Cabe destacar que la plataforma juega un papel fundamental, garantizando un impacto duradero. "
           "Cabe destacar que el ecosistema se erige como un entramado robusto, reflejando su profundo impacto. ") * 3

    def test_higher_index_is_better_and_derives_from_both_scores(self) -> None:
        clean, bad = self.audit_text(self.CLEAN), self.audit_text(self.BAD)
        self.assertGreater(clean["indice"], bad["indice"])
        for report in (clean, bad):
            self.assertEqual(report["indice"],
                             round(100 * (1 - (report["puntaje_estilo"] + report["puntaje_flujo"]) / 2)))
            self.assertIn(report["veredicto"], ("clara", "irregular", "requiere_revision"))
        self.assertEqual(clean["veredicto"], "clara")

    def test_a_bad_score_never_fails_the_run(self) -> None:
        path = self.tmp / "malo.txt"
        path.write_text(self.BAD * 4, encoding="utf-8")
        result = cli("auditar", "--txt", path, "--json")
        self.assertEqual(result.returncode, 0)
        self.assertNotEqual(json.loads(result.stdout)["veredicto"], "clara")

    def test_long_sentence_share_is_scored(self) -> None:
        long_one = " ".join(filler(4).replace(".", "").split()) + "."
        report = self.audit_text(f"{long_one} {filler(1, start=500)}")
        self.assertEqual(report["metricas"]["oraciones_largas_proporcion"], 0.5)
        self.assertGreater(report["familias"]["oraciones_largas"], 0)

    def test_counts_are_normalized_so_long_documents_do_not_saturate(self) -> None:
        def document(blocks: int) -> str:
            return " ".join(filler(10, start=i * 120) + " La plataforma se erige como referente."
                            for i in range(blocks))
        small, large = self.audit_text(document(4)), self.audit_text(document(40))
        self.assertAlmostEqual(small["familias"]["catalogo"], large["familias"]["catalogo"], delta=0.02)
        self.assertLess(large["familias"]["catalogo"], 1)

    def test_sentence_variation_and_se_density_are_reported_but_not_scored(self) -> None:
        with_se = self.audit_text("La voz se mide. El ritmo se anota. La tasa se calcula. El panel se revisa.")
        without = self.audit_text("La voz la mide. El ritmo lo anota. La tasa la calcula. El panel lo revisa.")
        self.assertGreater(with_se["metricas"]["densidad_se_por_1000"], 0)
        self.assertIn("cv_longitud", with_se["metricas"])
        self.assertEqual(with_se["puntaje_estilo"], without["puntaje_estilo"])
        self.assertEqual(with_se["puntaje_flujo"], without["puntaje_flujo"])

    def test_report_exposes_thresholds_and_the_readability_notice(self) -> None:
        report = self.audit_text(self.CLEAN)
        self.assertEqual(report["umbrales"]["oracion_larga_palabras"], 45)
        self.assertEqual(report["umbrales"]["mattr_ventana"], 200)
        self.assertEqual(report["umbrales"]["bandas"], {"clara": 0.20, "irregular": 0.45})
        self.assertIn("legibilidad", report["aviso"])

    def test_same_input_gives_the_same_report(self) -> None:
        run = self.make_run({"02_justificacion": self.BAD})
        cli("auditar", run)
        first = (run / "artefactos" / "estilo" / "reporte.json").read_bytes()
        cli("auditar", run)
        self.assertEqual(first, (run / "artefactos" / "estilo" / "reporte.json").read_bytes())


class RunTests(Base):
    def test_writes_json_and_markdown_inside_the_run(self) -> None:
        run = self.make_run({"02_justificacion": "El sistema se erige como referente."})
        result = cli("auditar", run)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((run / "artefactos" / "estilo" / "reporte.json").read_text(encoding="utf-8"))
        self.assertEqual(report["hallazgos"][0]["seccion"], "02_justificacion")
        markdown = (run / "artefactos" / "estilo" / "reporte.md").read_text(encoding="utf-8")
        self.assertIn("02_justificacion", markdown)
        self.assertIn("se erige como", markdown)

    def test_a_run_with_no_sections_is_handled(self) -> None:
        run = self.make_run({})
        report = self.audit_run(run)
        self.assertIsNone(report["indice"])
        self.assertIsNone(report["veredicto"])
        self.assertEqual(report["hallazgos"], [])
        self.assertTrue((run / "artefactos" / "estilo" / "reporte.json").is_file())

    def test_a_missing_run_is_an_input_error(self) -> None:
        self.assertEqual(cli("auditar", self.tmp / "no-existe").returncode, 2)

    def test_tdr_sections_are_scored_like_any_other(self) -> None:
        run = self.make_run({"02_justificacion": "El sistema mide la voz.",
                             "tdr05_riesgos": "El sistema se erige como referente."})
        sections = {s["seccion"] for s in self.audit_run(run)["secciones"]}
        self.assertEqual(sections, {"02_justificacion", "tdr05_riesgos"})
        only = self.audit_run(run, "--seccion", "tdr05")
        self.assertEqual([s["seccion"] for s in only["secciones"]], ["tdr05_riesgos"])
        self.assertEqual(only["hallazgos"][0]["categoria"], "cliche")

    def test_section_by_number_and_canonical_order(self) -> None:
        run = self.make_run({"10_metodologia": "La sede mide.", "03_descripcion_problema": "El grupo anota.",
                             "00_frontmatter": "El proyecto mide la voz.", "diag_arbol_problemas": "No es prosa."})
        order = [s["seccion"] for s in self.audit_run(run)["secciones"]]
        self.assertEqual(order, ["00_frontmatter", "03_descripcion_problema", "10_metodologia"])
        self.assertEqual([s["seccion"] for s in self.audit_run(run, "--seccion", "3")["secciones"]],
                         ["03_descripcion_problema"])

    def test_cross_section_redundancy_needs_todo(self) -> None:
        phrase = "acompañamiento y asesoría de personal especializado"
        run = self.make_run({"02_justificacion": f"Se ofrece {phrase} aquí.\n\nSe ofrece {phrase} allá.",
                             "10_metodologia": f"El plan incluye {phrase} siempre."})
        self.assertNotIn("frase_repetida", {f["categoria"] for f in self.audit_run(run)["hallazgos"]})
        found = [f for f in self.audit_run(run, "--todo")["hallazgos"] if f["categoria"] == "frase_repetida"]
        self.assertEqual(len(found), 1)
        self.assertEqual({u["seccion"] for u in found[0]["ubicaciones"]}, {"02_justificacion", "10_metodologia"})


class ProtectedTermTests(Base):
    TRUNK = "Identificación tardía de patrones de depresión en estudiantes universitarios afectados por el sismo"
    OBJECTIVE = ("Desarrollar un sistema portable de inteligencia artificial para identificar oportunamente "
                 "patrones de depresión en estudiantes universitarios afectados por el sismo")
    OE = "Diseñar una estrategia multimodal de análisis del habla en entrevistas clínicas semiestructuradas locales"
    REPEAT = "acompañamiento y asesoría de personal especializado"

    def sgr_run(self, with_trees: bool = True) -> Path:
        sections = {
            "03_descripcion_problema": (f"{self.TRUNK}.\n\nLa región exige {self.REPEAT} urgente.\n\n"
                                        f"La sede pide {self.REPEAT} cercano."),
            "06_objetivo_general": f"{self.OBJECTIVE}.\n\n{self.OE}.",
            "07_objetivos_especificos": f"{self.OE}.\n\nLa red reclama {self.REPEAT} formado.",
            "10_metodologia": f"{self.OBJECTIVE}.\n\n{self.OE}.",
            "11_resultados_esperados": f"{self.OBJECTIVE}.",
        }
        run = self.make_run(sections, flujo="sgr")
        if with_trees:
            (run / "artefactos" / "arboles").mkdir()
            (run / "redaccion" / "specs").mkdir()
            (run / "artefactos" / "arboles" / "arbol_objetivos.json").write_text(json.dumps(
                {"trunk": {"text": self.OBJECTIVE}, "groups": [{"id": "OE1", "objective": self.OE}]}), encoding="utf-8")
            (run / "redaccion" / "specs" / "arbol_problemas.spec.json").write_text(json.dumps(
                {"trunk": {"text": self.TRUNK}, "groups": [{"id": "SP1", "title": "SP1 · Procesado\nmultimodal"}]}),
                encoding="utf-8")
        return run

    def redundancy(self, report: dict) -> list:
        return [f for f in report["hallazgos"] if f["categoria"] in ("frase_repetida", "casi_duplicado")]

    def test_sgr_literal_copy_is_exempt_and_a_real_repeat_is_not(self) -> None:
        report = self.audit_run(self.sgr_run(), "--todo")
        found = self.redundancy(report)
        self.assertEqual([f["fragmento"] for f in found], [self.REPEAT])
        exempt = [e for e in report["exentos"] if e["termino"].startswith("Desarrollar un sistema")]
        self.assertEqual(len(exempt), 1)
        self.assertEqual(exempt[0]["ocurrencias"], 3)
        self.assertEqual(exempt[0]["fuente"], "arbol_objetivos")
        self.assertIn("06_objetivo_general", exempt[0]["secciones"])
        self.assertIn("SGR", exempt[0]["motivo"])

    def test_without_the_trees_the_same_copy_is_a_finding(self) -> None:
        found = self.redundancy(self.audit_run(self.sgr_run(with_trees=False), "--todo"))
        self.assertGreater(len(found), 1)

    def test_a_long_literal_copy_is_not_a_long_sentence(self) -> None:
        objective = " ".join(filler(5).replace(".", "").split())
        run = self.make_run({"06_objetivo_general": f"{objective}."}, flujo="sgr")
        (run / "artefactos" / "arboles").mkdir()
        (run / "artefactos" / "arboles" / "arbol_objetivos.json").write_text(
            json.dumps({"trunk": {"text": objective}}), encoding="utf-8")
        self.assertNotIn("oracion_larga", {f["categoria"] for f in self.audit_run(run)["hallazgos"]})

    def test_mga_vocabulary_title_tdr_titles_and_institutions_are_protected(self) -> None:
        title = "Sistema portable para la salud mental universitaria en la región andina"
        chapter = "Consideraciones especiales de sostenibilidad técnica del proyecto financiado"
        body = (f"La Universidad Tecnológica de Pereira publica {title} hoy. "
                f"El árbol de problemas ordena {chapter} ahora.")
        run = self.make_run({"02_justificacion": f"{body}\n\n{body}\n\n{body}"})
        (run / "redaccion" / "datos_proyecto.tex").write_text(
            "\\newcommand{\\TituloProyecto}{" + title + "}\n", encoding="utf-8")
        (run / "artefactos" / "estructura_tdr.json").write_text(json.dumps(
            {"capitulos": [{"numero": 1, "titulo": chapter, "archivos": ["02_justificacion"]}]}), encoding="utf-8")
        report = self.audit_run(run)
        self.assertEqual(self.redundancy(report), [])
        sources = {e["fuente"] for e in report["exentos"]}
        self.assertEqual(sources, {"institucion", "titulo", "vocabulario_mga", "estructura_tdr"})

    def test_protected_term_does_not_fire_the_catalog(self) -> None:
        run = self.make_run({"02_justificacion": "El sistema se erige como referente."})
        (run / "redaccion" / "datos_proyecto.tex").write_text(
            "\\newcommand{\\TituloProyecto}{El sistema se erige como referente}\n", encoding="utf-8")
        self.assertEqual(self.audit_run(run)["hallazgos"], [])

    def test_topic_word_of_the_trees_is_not_overused(self) -> None:
        text = " ".join(filler(1, start=i * 24)[:-1] + " portable " + filler(1, start=i * 24 + 12).lower() for i in range(40))
        run = self.make_run({"02_justificacion": text})
        self.assertIn("sobreuso", {f["categoria"] for f in self.audit_run(run)["hallazgos"]})
        (run / "artefactos" / "arboles").mkdir()
        (run / "artefactos" / "arboles" / "arbol_objetivos.json").write_text(json.dumps(
            {"groups": [{"objective": "Diseñar un sistema portable"}, {"objective": "Probar el equipo portable"}]}),
            encoding="utf-8")
        report = self.audit_run(run)
        self.assertNotIn("sobreuso", {f["categoria"] for f in report["hallazgos"]})
        self.assertIn(("portable", "dominio"), {(e["termino"], e["fuente"]) for e in report["exentos"]})

    def test_summary_against_body_is_exempt_and_logged(self) -> None:
        sentence = "El sistema portable procesa señales acústicas clínicas locales durante entrevistas universitarias."
        run = self.make_run({"00_frontmatter": sentence, "10_metodologia": sentence})
        report = self.audit_run(run, "--todo")
        self.assertEqual(self.redundancy(report), [])
        self.assertTrue(any("resumen" in e["motivo"] for e in report["exentos"]))

    def test_body_against_body_is_not_exempt(self) -> None:
        sentence = "El sistema portable procesa señales acústicas clínicas locales durante entrevistas universitarias."
        run = self.make_run({"02_justificacion": sentence, "10_metodologia": sentence})
        self.assertEqual(len(self.redundancy(self.audit_run(run, "--todo"))), 1)


class VerifyTests(Base):
    BASE = (r"La muestra de 120 estudiantes (EST-MZ-001) inició el 12 de marzo de 2026 con \$1.500.000 "
            "y alcanza TRL 6 \\citep{perez2020} en la Tabla~\\ref{tab:a}.\\label{sec:a}\n\nSegundo párrafo.")

    def check(self, before: str, after: str) -> subprocess.CompletedProcess:
        a, b = self.tmp / "antes.tex", self.tmp / "despues.tex"
        a.write_text(before, encoding="utf-8")
        b.write_text(after, encoding="utf-8")
        return cli("verificar", a, b, "--json")

    def test_a_change_of_style_only_passes(self) -> None:
        after = self.BASE.replace("La muestra de", "La muestra reúne a").replace("inició", "empezó")
        result = self.check(self.BASE, after)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(json.loads(result.stdout)["fiel"])

    def test_each_fact_change_fails_and_names_its_class(self) -> None:
        cases = {
            "numeros": ("120 estudiantes", "121 estudiantes"),
            "fechas": ("12 de marzo", "12 de abril"),
            "dinero": (r"\$1.500.000", r"\$1.600.000"),
            "citas": ("perez2020", "perez2021"),
            "etiquetas": (r"\label{sec:a}", r"\label{sec:b}"),
            "referencias": (r"\ref{tab:a}", r"\ref{tab:b}"),
            "cohortes": ("EST-MZ-001", "EST-MZ-002"),
            "trl": ("TRL 6", "TRL 7"),
        }
        for kind, (old, new) in cases.items():
            with self.subTest(kind=kind):
                result = self.check(self.BASE, self.BASE.replace(old, new))
                self.assertEqual(result.returncode, 1, result.stdout)
                classes = {d["clase"] for d in json.loads(result.stdout)["archivos"][0]["diferencias"]}
                self.assertIn(kind, classes)

    def test_paragraph_count_change_fails(self) -> None:
        result = self.check(self.BASE, self.BASE.replace("\n\nSegundo", " Segundo"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("parrafos", {d["clase"] for d in json.loads(result.stdout)["archivos"][0]["diferencias"]})

    def test_two_amounts_are_not_one_formula(self) -> None:
        result = self.check(r"Cuesta \$1.000 o \$2.000 según $x$.", r"Cuesta \$1.000 o \$3.000 según $x$.")
        self.assertEqual(result.returncode, 1)
        classes = {d["clase"]: d for d in json.loads(result.stdout)["archivos"][0]["diferencias"]}
        self.assertEqual(classes["dinero"]["faltan"], [r"\$2.000"])
        self.assertNotIn("formulas", classes)

    def test_a_changed_formula_fails(self) -> None:
        self.assertEqual(self.check("Sea $x^2$ el valor.", "Sea $x^3$ el valor.").returncode, 1)

    def test_a_removed_repeated_figure_fails(self) -> None:
        self.assertEqual(self.check("Son 30 casos. Otros 30 casos.", "Son 30 casos.").returncode, 1)

    def test_comments_and_layout_arguments_do_not_count(self) -> None:
        before = "% versión 3 del 2024\n\\vspace{2mm}Son 30 casos."
        self.assertEqual(self.check(before, "% versión 4\n\\vspace{5mm}Son 30 casos.").returncode, 0)

    def test_directories_compare_file_by_file(self) -> None:
        a, b = self.tmp / "a", self.tmp / "b"
        a.mkdir()
        b.mkdir()
        (a / "02.tex").write_text("Son 30 casos.", encoding="utf-8")
        (b / "02.tex").write_text("Son 30 casos.", encoding="utf-8")
        (a / "03.tex").write_text("Son 40 casos.", encoding="utf-8")
        (b / "03.tex").write_text("Son 40 casos.", encoding="utf-8")
        self.assertEqual(cli("verificar", a, b).returncode, 0)
        (b / "03.tex").write_text("Son 41 casos.", encoding="utf-8")
        self.assertEqual(cli("verificar", a, b).returncode, 1)
        (b / "03.tex").unlink()
        result = cli("verificar", a, b, "--json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("archivo", {d["clase"] for f in json.loads(result.stdout)["archivos"] for d in f["diferencias"]})

    def test_missing_input_is_an_input_error(self) -> None:
        self.assertEqual(cli("verificar", self.tmp / "x", self.tmp / "y").returncode, 2)


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def paragraph(text: str, style: str = "", color: str = "") -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    rpr = f'<w:rPr><w:color w:val="{color}"/></w:rPr>' if color else ""
    return f"<w:p>{ppr}<w:r>{rpr}<w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"


class DocxTests(Base):
    def docx(self, body: str) -> Path:
        path = self.tmp / "entregable.docx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", f"<w:document {W}><w:body>{body}</w:body></w:document>")
        return path

    def audit(self, path: Path, *flags: str) -> dict:
        result = cli("auditar", "--docx", path, "--json", *flags)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_placeholders_tables_and_markers_are_dropped(self) -> None:
        table = ("<w:tbl><w:tr><w:tc>" + paragraph("La tabla se erige como referente.") + "</w:tc></w:tr></w:tbl>")
        body = (paragraph("La sede mide la voz.") + table
                + paragraph("Escriba aquí: el proyecto se erige como referente.", color="808080")
                + paragraph("[ ] Cabe destacar que el formato pide marcar. [X]", color="A6A6A6")
                + paragraph("[ ] El grupo anota el ritmo."))
        report = self.audit(self.docx(body))
        self.assertEqual(report["hallazgos"], [])
        self.assertEqual(report["metricas"]["oraciones"], 2)
        self.assertEqual(report["metricas"]["parrafos"], 2)

    def test_coloured_text_that_is_not_grey_stays(self) -> None:
        report = self.audit(self.docx(paragraph("El sistema se erige como referente.", color="1F3864")))
        self.assertEqual(report["hallazgos"][0]["categoria"], "cliche")

    def test_heading_styles_split_sections(self) -> None:
        body = (paragraph("Justificación", "Heading1") + paragraph("La sede mide la voz.")
                + paragraph("Metodología", "Ttulo1") + paragraph("El grupo anota el ritmo."))
        self.assertEqual([s["seccion"] for s in self.audit(self.docx(body))["secciones"]],
                         ["Justificación", "Metodología"])

    def test_numbering_stands_in_for_missing_headings(self) -> None:
        body = (paragraph("1. Justificación") + paragraph("La sede mide la voz.")
                + paragraph("1.1 Contexto") + paragraph("El equipo sigue.")
                + paragraph("2. Metodología") + paragraph("El grupo anota el ritmo."))
        report = self.audit(self.docx(body))
        self.assertEqual([s["seccion"] for s in report["secciones"]], ["1. Justificación", "2. Metodología"])
        self.assertEqual(report["metricas"]["oraciones"], 3)

    def test_section_filter_on_a_file(self) -> None:
        body = (paragraph("1. Justificación") + paragraph("La sede mide la voz.")
                + paragraph("2. Metodología") + paragraph("El sistema se erige como referente."))
        report = self.audit(self.docx(body), "--seccion", "2")
        self.assertEqual([s["seccion"] for s in report["secciones"]], ["2. Metodología"])

    def test_a_file_with_a_run_uses_its_terms_and_writes_there(self) -> None:
        run = self.make_run({})
        (run / "redaccion" / "datos_proyecto.tex").write_text(
            "\\newcommand{\\TituloProyecto}{El sistema se erige como referente}\n", encoding="utf-8")
        path = self.docx(paragraph("El sistema se erige como referente."))
        result = cli("auditar", run, "--docx", path, "--json")
        self.assertEqual(json.loads(result.stdout)["hallazgos"], [])
        self.assertTrue((run / "artefactos" / "estilo" / "reporte.json").is_file())

    def test_a_file_alone_writes_nothing_beside_it(self) -> None:
        path = self.docx(paragraph("La sede mide la voz."))
        self.audit(path)
        self.assertEqual([p.name for p in self.tmp.iterdir()], [path.name])

    def test_a_bad_docx_is_an_input_error(self) -> None:
        path = self.tmp / "roto.docx"
        path.write_text("no es zip", encoding="utf-8")
        self.assertEqual(cli("auditar", "--docx", path).returncode, 2)


class FramingTests(unittest.TestCase):
    BANNED = (
        "detección de ia", "detector", "detectabilidad", "detectability", "ai detection", "riesgo de ia", "ai risk",
        "evasión", "evasion", "evadir", "perplejidad", "perplexity", "burstiness", "generación por",
        "generado por ia", "patrones de ia", "patrones de escritura de ia", "vicios de ia", "comodines de ia",
        "signs of ai", "ai cleanup", "ai clichés", "la ia tiende", "alta frecuencia en ia",
    )

    def test_no_ai_detection_framing(self) -> None:
        for path in (SCRIPT, ESTILO_SKILL, DEPURACION_SKILL, AUDITOR, REVISOR):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in self.BANNED:
                with self.subTest(path=path.name, phrase=phrase):
                    self.assertNotIn(phrase, text)


class SkillRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.estilo = ESTILO_SKILL.read_text(encoding="utf-8")
        cls.depuracion = DEPURACION_SKILL.read_text(encoding="utf-8")
        cls.auditor = AUDITOR.read_text(encoding="utf-8")

    def test_one_sentence_length_rule(self) -> None:
        for text in (self.estilo, self.depuracion, self.auditor):
            self.assertRegex(text, r"8\D{1,6}15")
            self.assertRegex(text, r"25\D{1,6}40")
            self.assertIn("45", text)
        for stale in ("5–10", "15–22", "35 words", "(>35", "25–38", "10–18"):
            self.assertNotIn(stale, self.auditor + self.depuracion)

    def test_70_30_means_vocabulary_only(self) -> None:
        self.assertNotIn("70/30 de longitud", self.depuracion)

    def test_technical_terms_repeat(self) -> None:
        self.assertNotIn("evita repetir la misma palabra clave", self.depuracion)
        self.assertRegex(self.depuracion, r"(?i)t[ée]rminos? (protegidos?|t[ée]cnicos?).{0,120}repit")

    def test_constituye_is_no_longer_recommended(self) -> None:
        self.assertNotIn("*constituye*, *facilita*", self.estilo)
        self.assertNotIn("borde constituye", self.estilo)

    def test_passive_se_stays_allowed(self) -> None:
        self.assertNotIn("Convert passive voice into active voice", self.auditor)
        self.assertRegex(self.auditor, r"(?i)pasiva refleja")

    def test_no_bold_for_scannability(self) -> None:
        self.assertNotIn("bolded key terms", self.auditor)

    def test_no_self_assigned_scores(self) -> None:
        self.assertNotIn("[X/10]", self.auditor)
        self.assertNotIn("0-100", self.auditor)
        self.assertNotIn("Índice de Naturalidad", self.estilo)
        self.assertIsNone(re.search(r"\d+ pts", self.estilo))

    def test_auditor_works_from_the_findings(self) -> None:
        self.assertIn("estilo_es.py", self.auditor)
        self.assertIn("hallazgos", self.auditor)
        self.assertRegex(self.auditor, r"(?i)logical relation")
        self.assertIn("Antes:", self.auditor)
        self.assertIn("Después:", self.auditor)

    def test_both_skills_point_to_the_deterministic_tools(self) -> None:
        self.assertIn("estilo_es.py verificar", self.estilo)
        self.assertIn("estilo_es.py verificar", self.depuracion)
        self.assertIn("estilo_es.py auditar", self.estilo)

    def test_redundancy_reviewer_is_read_only_and_chooses_no_copy(self) -> None:
        text = REVISOR.read_text(encoding="utf-8")
        front = text.split("---")[1]
        self.assertIn("name: revisor-redundancia", front)
        self.assertIn("model: sonnet", front)
        self.assertRegex(front, r"tools: Read, Grep, Glob\n")
        self.assertIn("auditar", text)
        self.assertIn("--todo", text)
        self.assertRegex(text, r"(?i)every location")
        self.assertRegex(text, r"(?i)never (choose|pick|recommend)")


if __name__ == "__main__":
    unittest.main()
