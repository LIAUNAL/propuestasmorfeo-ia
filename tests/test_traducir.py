"""Manuscript translation, Spanish to English and English to Spanish (S4 of
odd/tasks/idioma-tablero-traduccion.md).

`scripts/traducir.py` keeps the run's manuscript canonical and builds the
translation as a derived artifact under `redaccion/traducciones/<lang>/`:
paragraph blocks and title/caption fragments with staleness by digest, a
fidelity gate on every store, the target language's style check and a built
`main.tex` whose babel, captions and cleveref names follow the target.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "traducir.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tr = _load("kit_traducir", SCRIPT)
language = _load("kit_language_for_traducir", REPO / "scripts" / "language.py")

SPANISH_SECTION = r"""% Comentario del redactor: no se traduce.
\section{Justificación y pertinencia}
\label{sec:justificacion}

La depresión afecta al 15,5 \% de los estudiantes universitarios del Eje Cafetero, según \citet{li2026}. El sistema propuesto alcanza un TRL 6 y se valida con $n = 120$ participantes de la Universidad Nacional de Colombia.

Los modelos de lenguaje permiten detectar patrones tempranos en el habla \citep{smith2024,doe2025}, como muestra la \cref{fig:arbol}.

\begin{itemize}
  \item Primer resultado esperado del proyecto con la comunidad.
  \item Segundo resultado con 3 talleres en el territorio.
\end{itemize}
"""
SPANISH_CAPTION = (r"\caption[Árbol de problemas]{Causas y efectos de la depresión en los estudiantes universitarios}"
                   "\\label{fig:arbol}\n")
BIBLIOGRAPHY = "\\clearpage\n\\renewcommand{\\bibsection}{}\n\\section*{Referencias}\n" \
               "\\bibliographystyle{apalike}\n\\bibliography{refs}\n"
SPANISH_COVER = (
    "\\newcommand{\\TituloProyecto}{Sistema portable de inteligencia artificial para la depresión}\n"
    "\\newcommand{\\InvestigadorPrincipal}{Ana Pérez}\n"
    "\\newcommand{\\AfiliacionProyecto}{Grupo GCPDS, Facultad de Ingeniería y Arquitectura, "
    "Universidad Nacional de Colombia, Sede Manizales}\n")
REFS = """@article{li2026, author={Li, Wei}, title={Speech and depression}, journal={J}, year={2026}}
@article{smith2024, author={Smith, John}, title={Language models}, journal={J}, year={2024}}
@article{doe2025, author={Doe, Jane}, title={Early patterns}, journal={J}, year={2025}}
"""

ENGLISH = {
    "02_justificacion-b01": r"Depression affects 15.5 \% of university students in the Eje Cafetero, according to "
                            r"\citet{li2026}. The proposed system reaches TRL 6 and is validated with $n = 120$ "
                            r"participants of the Universidad Nacional de Colombia.",
    "02_justificacion-b02": r"Language models make it possible to detect early patterns in speech "
                            r"\citep{smith2024,doe2025}, as \cref{fig:arbol} shows.",
    "02_justificacion-b03": "\\begin{itemize}\n  \\item First expected result of the project with the community.\n"
                            "  \\item Second result with 3 workshops in the territory.\n\\end{itemize}",
}
ENGLISH_FRAGMENTS = {
    "Justificación y pertinencia": "Justification and relevance",
    "Árbol de problemas": "Problem tree",
    "Causas y efectos de la depresión en los estudiantes universitarios":
        "Causes and effects of depression among university students",
    "Referencias": "References",
    "Sistema portable de inteligencia artificial para la depresión":
        "Portable artificial intelligence system for depression",
    "Grupo GCPDS, Facultad de Ingeniería y Arquitectura, Universidad Nacional de Colombia, Sede Manizales":
        "GCPDS group, Faculty of Engineering and Architecture, Universidad Nacional de Colombia, Sede Manizales",
}


def make_run(root: Path, lang: str = "es") -> Path:
    """A tiny project with one run written in `lang` (Spanish fixture text,
    or its English translation for an English run)."""
    (root / ".morfeo").mkdir(parents=True)
    (root / ".morfeo" / "config.json").write_text(json.dumps({"lang": lang}), encoding="utf-8")
    run = root / "proposals" / "demo"
    redaccion = run / "redaccion"
    (redaccion / "sections").mkdir(parents=True)
    shutil.copytree(REPO / "plantilla" / "logos", redaccion / "logos")
    manifest = "# Corrida `demo`\n\n| Campo | Valor |\n|---|---|\n| run-id | `demo` |\n"
    if lang == "en":
        manifest += "| idioma | en |\n"
    (run / "_run.md").write_text(manifest, encoding="utf-8")
    main = (REPO / "plantilla" / "main.tex").read_text(encoding="utf-8")
    section, caption, cover, bibliography = SPANISH_SECTION, SPANISH_CAPTION, SPANISH_COVER, BIBLIOGRAPHY
    if lang == "en":
        main = language.localize_main_tex(main, "en")
        section = english_section()
        for es, en in ENGLISH_FRAGMENTS.items():
            caption, cover, bibliography = (caption.replace(es, en), cover.replace(es, en),
                                            bibliography.replace(es, en))
    (redaccion / "main.tex").write_text(main, encoding="utf-8")
    (redaccion / "datos_proyecto.tex").write_text(cover, encoding="utf-8")
    (redaccion / "refs.bib").write_text(REFS, encoding="utf-8")
    (redaccion / "sections" / "02_justificacion.tex").write_text(section, encoding="utf-8")
    (redaccion / "sections" / "diag_arbol_problemas.tex").write_text(
        "\\begin{tikzpicture}\\node {Problema central};\\end{tikzpicture}\n", encoding="utf-8")
    (redaccion / "sections" / "diag_arbol_problemas_caption.tex").write_text(caption, encoding="utf-8")
    (redaccion / "sections" / "16_bibliografia.tex").write_text(bibliography, encoding="utf-8")
    return run


def english_section() -> str:
    text = SPANISH_SECTION.replace("% Comentario del redactor: no se traduce.", "% Writer's note.")
    text = text.replace("Justificación y pertinencia", "Justification and relevance")
    blocks = [p for p in text.split("\n\n")]
    return "\n\n".join([blocks[0]] + list(ENGLISH.values())) + "\n"


def digests(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file() and "traducciones" not in p.parts}


class Base(unittest.TestCase):
    lang = "es"

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.run_root = make_run(self.tmp / "proyecto", self.lang)
        self.drafts = self.tmp / "borradores"
        self.drafts.mkdir()

    def draft(self, name: str, text: str) -> Path:
        path = self.drafts / f"{name}.tex"
        path.write_text(text, encoding="utf-8")
        return path

    def refused(self, code: str, call, *args, **kwargs) -> str:
        with self.assertRaises(tr.Refused) as ctx:
            call(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code, ctx.exception.message)
        return ctx.exception.message

    def store_all(self, target: str, blocks: dict[str, str], fragments: dict[str, str]) -> dict:
        planned = tr.plan(self.run_root, target)
        for block_id, text in blocks.items():
            tr.store(self.run_root, target, block_id, self.draft(block_id, text))
        for fragment in planned["fragments"]:
            tr.store_fragment(self.run_root, target, fragment["id"],
                              self.draft(fragment["id"], fragments[fragment["source"]]))
        return planned


class PlanTests(Base):
    def test_the_target_must_differ_from_the_writing_language(self) -> None:
        message = self.refused("TRANSLATION_SAME_LANGUAGE", tr.plan, self.run_root, "es")
        self.assertIn("(es)", message)
        self.assertFalse((self.run_root / "redaccion" / "traducciones").exists())

    def test_plan_lists_paragraph_blocks_and_title_and_caption_fragments(self) -> None:
        result = tr.plan(self.run_root, "en")
        self.assertEqual(result["source_language"], "es")
        self.assertEqual([b["id"] for b in result["blocks"]],
                         ["02_justificacion-b01", "02_justificacion-b02", "02_justificacion-b03"])
        self.assertEqual(result["counts"], {"total": 3, "missing": 3, "current": 0, "stale": 0})
        kinds = sorted((f["file"], f["kind"], f["source"]) for f in result["fragments"])
        self.assertEqual(kinds, sorted([
            ("datos_proyecto.tex", "title", "Sistema portable de inteligencia artificial para la depresión"),
            ("datos_proyecto.tex", "affiliation",
             "Grupo GCPDS, Facultad de Ingeniería y Arquitectura, Universidad Nacional de Colombia, Sede Manizales"),
            ("sections/02_justificacion.tex", "section", "Justificación y pertinencia"),
            ("sections/16_bibliografia.tex", "section", "Referencias"),
            ("sections/diag_arbol_problemas_caption.tex", "caption", "Árbol de problemas"),
            ("sections/diag_arbol_problemas_caption.tex", "caption",
             "Causas y efectos de la depresión en los estudiantes universitarios"),
        ]))
        record = json.loads((self.run_root / "redaccion/traducciones/en/traduccion.json").read_text(encoding="utf-8"))
        self.assertEqual(record["schema"], "morfeo.traduccion/v1")
        self.assertEqual((record["source_language"], record["language"]), ("es", "en"))
        self.assertIn("sections/diag_arbol_problemas.tex", record["files"])
        self.assertIn({"term": "Universidad Nacional de Colombia", "target": "Universidad Nacional de Colombia",
                       "origin": "institution"}, record["glossary"])

    def test_plan_never_writes_the_canonical_manuscript(self) -> None:
        before = digests(self.run_root / "redaccion")
        tr.plan(self.run_root, "en")
        tr.store(self.run_root, "en", "02_justificacion-b01", self.draft("b1", ENGLISH["02_justificacion-b01"]))
        self.assertEqual(digests(self.run_root / "redaccion"), before)

    def test_user_terms_join_the_glossary_and_bind_the_gate(self) -> None:
        tr.plan(self.run_root, "en", terms=["Eje Cafetero=Coffee Axis"])
        message = self.refused("TRANSLATION_FIDELITY", tr.store, self.run_root, "en", "02_justificacion-b01",
                               self.draft("b1", ENGLISH["02_justificacion-b01"]))
        self.assertIn("glossary: 'Eje Cafetero' must appear as 'Coffee Axis'", message)
        text = ENGLISH["02_justificacion-b01"].replace("Eje Cafetero", "Coffee Axis")
        self.assertEqual(tr.store(self.run_root, "en", "02_justificacion-b01", self.draft("b1", text))["state"],
                         "current")
        again = tr.plan(self.run_root, "en")
        self.assertIn({"term": "Eje Cafetero", "target": "Coffee Axis", "origin": "user"}, again["glossary"])


class GateTests(Base):
    def setUp(self) -> None:
        super().setUp()
        tr.plan(self.run_root, "en")

    def store_b1(self, text: str) -> dict:
        return tr.store(self.run_root, "en", "02_justificacion-b01", self.draft("b1", text))

    def fidelity(self, text: str) -> str:
        return self.refused("TRANSLATION_FIDELITY", self.store_b1, text)

    def test_a_faithful_translation_is_stored_current_with_its_style_summary(self) -> None:
        result = self.store_b1(ENGLISH["02_justificacion-b01"])
        self.assertEqual(result["state"], "current")
        self.assertIsInstance(result["style"]["indice"], (int, float))
        status = tr.status(self.run_root, "en")
        self.assertEqual(status["counts"], {"total": 3, "missing": 2, "current": 1, "stale": 0})

    def test_a_text_left_in_spanish_is_refused(self) -> None:
        self.refused("TRANSLATION_NOT_ENGLISH", self.store_b1, SPANISH_SECTION.split("\n\n")[1])
        half = ENGLISH["02_justificacion-b01"].split(". The")[0] + (
            ". El sistema propuesto alcanza un TRL 6 y se valida con $n = 120$ participantes de la "
            "Universidad Nacional de Colombia.")
        self.refused("TRANSLATION_NOT_ENGLISH", self.store_b1, half.replace("in the Eje", "del Eje"))

    def test_each_fact_category_is_checked(self) -> None:
        good = ENGLISH["02_justificacion-b01"]
        cases = {
            "citations": good.replace(r"\citet{li2026}", r"\citet{li2025}"),
            "citations ": good.replace(r"\citet{li2026}", r"\citep{li2026}"),
            "math": good.replace("$n = 120$", "$n = 121$"),
            "numbers": good.replace("15.5", "16.5"),
            "paragraphs": good.replace(". The proposed", ".\n\nThe proposed"),
        }
        for kind, text in cases.items():
            with self.subTest(kind=kind):
                self.assertIn(kind.strip() + ":", self.fidelity(text))
        b2 = ENGLISH["02_justificacion-b02"]
        refs = self.refused("TRANSLATION_FIDELITY", tr.store, self.run_root, "en", "02_justificacion-b02",
                            self.draft("b2", b2.replace(r"\cref{fig:arbol}", r"\cref{fig:arboles}")))
        self.assertIn("references:", refs)
        b3 = ENGLISH["02_justificacion-b03"]
        items = self.refused("TRANSLATION_FIDELITY", tr.store, self.run_root, "en", "02_justificacion-b03",
                             self.draft("b3", b3.replace("  \\item Second", "  Second")))
        self.assertIn("items:", items)

    def test_labels_and_placeholders_and_markers_are_checked(self) -> None:
        self.assertIn("labels:", self.fidelity(ENGLISH["02_justificacion-b01"] + r" \label{sec:extra}"))
        self.refused("TRANSLATION_PLACEHOLDER_TEXT", self.store_b1, ENGLISH["02_justificacion-b01"] + " TODO")
        self.refused("CONTENT_CARRIES_MARKER", self.store_b1,
                     "% morfeo-traduccion: built\n" + ENGLISH["02_justificacion-b01"])

    def test_decimal_commas_and_points_are_one_number(self) -> None:
        self.assertEqual(tr.extract_facts("15,5 y 1.500 y 120 000")["numbers"],
                         tr.extract_facts("15.5 and 1,500 and 120,000")["numbers"])

    def test_fragments_keep_one_paragraph_and_balanced_braces(self) -> None:
        planned = tr.plan(self.run_root, "en")
        title = next(f["id"] for f in planned["fragments"] if f["source"] == "Justificación y pertinencia")
        self.refused("TRANSLATION_NOT_ENGLISH", tr.store_fragment, self.run_root, "en", title,
                     self.draft("t", "Justificación y pertinencia"))
        self.assertIn("braces", self.refused("TRANSLATION_FIDELITY", tr.store_fragment, self.run_root, "en", title,
                                             self.draft("t", "Justification {and relevance")))
        self.assertIn("one paragraph", self.refused("TRANSLATION_FIDELITY", tr.store_fragment, self.run_root, "en",
                                                    title, self.draft("t", "Justification\n\nand relevance")))
        result = tr.store_fragment(self.run_root, "en", title, self.draft("t", "Justification and relevance"))
        self.assertEqual(result["state"], "current")

    def test_unknown_ids_and_empty_files_are_refused(self) -> None:
        self.refused("BLOCK_UNKNOWN", tr.store, self.run_root, "en", "02_justificacion-b09", self.draft("x", "Text."))
        self.refused("FRAGMENT_UNKNOWN", tr.store_fragment, self.run_root, "en", "nope", self.draft("x", "Text."))
        self.refused("TRANSLATION_EMPTY", self.store_b1, "  \n")

    def test_store_before_plan_is_refused(self) -> None:
        shutil.rmtree(self.run_root / "redaccion" / "traducciones")
        self.refused("TRANSLATION_NOT_PLANNED", self.store_b1, ENGLISH["02_justificacion-b01"])


class StalenessTests(Base):
    def test_a_source_edit_makes_the_block_stale_and_a_moved_paragraph_keeps_its_translation(self) -> None:
        tr.plan(self.run_root, "en")
        for block_id, text in ENGLISH.items():
            tr.store(self.run_root, "en", block_id, self.draft(block_id, text))
        section = self.run_root / "redaccion" / "sections" / "02_justificacion.tex"
        text = section.read_text(encoding="utf-8")
        section.write_text(text.replace("patrones tempranos", "patrones muy tempranos"), encoding="utf-8")
        states = {r["id"]: r["state"] for r in tr.status(self.run_root, "en")["blocks"]}
        self.assertEqual(states, {"02_justificacion-b01": "current", "02_justificacion-b02": "stale",
                                  "02_justificacion-b03": "current"})
        self.assertFalse(tr.status(self.run_root, "en")["built"])
        # A new first paragraph shifts every id: plan re-keys the translations by digest.
        section.write_text(text.replace("\\label{sec:justificacion}\n",
                                        "\\label{sec:justificacion}\n\nUn párrafo nuevo sobre la salud mental.\n"),
                           encoding="utf-8")
        result = tr.plan(self.run_root, "en")
        states = {b["id"]: b["state"] for b in result["blocks"]}
        self.assertEqual(states, {"02_justificacion-b01": "missing", "02_justificacion-b02": "current",
                                  "02_justificacion-b03": "current", "02_justificacion-b04": "current"})
        moved = (self.run_root / "redaccion/traducciones/en/bloques/02_justificacion-b02.tex").read_text("utf-8")
        self.assertIn("Depression affects", moved)


class BuildTests(Base):
    def test_build_refuses_while_anything_is_missing(self) -> None:
        tr.plan(self.run_root, "en")
        tr.store(self.run_root, "en", "02_justificacion-b01", self.draft("b1", ENGLISH["02_justificacion-b01"]))
        message = self.refused("TRANSLATION_INCOMPLETE", tr.build, self.run_root, "en")
        self.assertIn("02_justificacion-b02 (missing)", message)
        self.assertFalse((self.run_root / "redaccion/traducciones/en/main.tex").exists())

    def test_build_switches_the_language_and_resolves_paths_from_redaccion(self) -> None:
        before = digests(self.run_root / "redaccion")
        self.store_all("en", ENGLISH, ENGLISH_FRAGMENTS)
        result = tr.build(self.run_root, "en")
        self.assertTrue(result["ok"])
        folder = self.run_root / "redaccion" / "traducciones" / "en"
        main = (folder / "main.tex").read_text(encoding="utf-8")
        self.assertIn(r"\usepackage[english]{babel}", main)
        self.assertNotIn("spanish", main.split("\\begin{document}")[0].replace("% ", ""))
        self.assertIn(r"\crefname{section}{section}{sections}", main)
        self.assertIn(r"\addto\captionsenglish{\renewcommand{\tablename}{Table}}", main)
        self.assertIn("Principal investigator: \\InvestigadorPrincipal", main)
        self.assertIn(r"\def\input@path{{../../}}", main)
        self.assertIn(r"\bibliography{../../refs}", main)
        section = (folder / "sections" / "02_justificacion.tex").read_text(encoding="utf-8")
        self.assertIn(r"\section{Justification and relevance}", section)
        self.assertIn("\\label{sec:justificacion}\n\nDepression affects", section)
        self.assertIn("% Comentario del redactor: no se traduce.", section)
        caption = (folder / "sections" / "diag_arbol_problemas_caption.tex").read_text(encoding="utf-8")
        self.assertIn(r"\caption[Problem tree]{Causes and effects of depression among university students}", caption)
        self.assertIn(r"\bibliography{../../refs}", (folder / "sections" / "16_bibliografia.tex").read_text("utf-8"))
        self.assertIn("Problema central", (folder / "sections" / "diag_arbol_problemas.tex").read_text("utf-8"))
        self.assertIn("Portable artificial intelligence", (folder / "datos_proyecto.tex").read_text("utf-8"))
        self.assertTrue(tr.status(self.run_root, "en")["built"])
        self.assertEqual(digests(self.run_root / "redaccion"), before)

    @unittest.skipUnless(shutil.which("latexmk") or shutil.which("pdflatex"), "LaTeX is not installed")
    def test_compile_produces_the_translated_pdf(self) -> None:
        self.store_all("en", ENGLISH, ENGLISH_FRAGMENTS)
        self.refused("TRANSLATION_NOT_BUILT", tr.compile_translation, self.run_root, "en")
        tr.build(self.run_root, "en")
        result = tr.compile_translation(self.run_root, "en")
        self.assertEqual(result["pdf"], "redaccion/traducciones/en/main.pdf")
        self.assertTrue(tr.status(self.run_root, "en")["pdf_current"])
        if shutil.which("pdftotext"):
            text = subprocess.run(["pdftotext", str(self.run_root / result["pdf"]), "-"], capture_output=True,
                                  text=True).stdout
            self.assertIn("Depression affects", text)
            self.assertIn("References", text)
            self.assertIn("Principal investigator", text)


class EnglishToSpanishTests(Base):
    lang = "en"

    def test_an_english_run_translates_to_spanish_with_spanish_babel(self) -> None:
        self.refused("TRANSLATION_SAME_LANGUAGE", tr.plan, self.run_root, "en")
        spanish = {"02_justificacion-b01": SPANISH_SECTION.split("\n\n")[1],
                   "02_justificacion-b02": SPANISH_SECTION.split("\n\n")[2],
                   "02_justificacion-b03": SPANISH_SECTION.split("\n\n")[3].rstrip("\n")}
        fragments = {en: es for es, en in ENGLISH_FRAGMENTS.items()}
        tr.plan(self.run_root, "es")
        self.refused("TRANSLATION_NOT_SPANISH", tr.store, self.run_root, "es", "02_justificacion-b01",
                     self.draft("b1", ENGLISH["02_justificacion-b01"]))
        self.store_all("es", spanish, fragments)
        tr.build(self.run_root, "es")
        main = (self.run_root / "redaccion/traducciones/es/main.tex").read_text(encoding="utf-8")
        self.assertIn(r"\usepackage[spanish,es-noindentfirst]{babel}", main)
        self.assertIn(r"\crefname{section}{sección}{secciones}", main)
        self.assertIn(r"\addto\captionsspanish{\renewcommand{\tablename}{Tabla}}", main)
        self.assertIn("Investigador principal: \\InvestigadorPrincipal", main)
        audit = tr.audit(self.run_root, "es")
        self.assertEqual(audit["checker"], "scripts/estilo_es.py")
        self.assertIn("legibilidad", audit["notice"])


class AuditTests(Base):
    def test_audit_needs_a_stored_block(self) -> None:
        tr.plan(self.run_root, "en")
        self.refused("TRANSLATION_NOTHING_STORED", tr.audit, self.run_root, "en")

    def test_audit_runs_the_target_languages_checker_and_tracks_freshness(self) -> None:
        tr.plan(self.run_root, "en")
        tr.store(self.run_root, "en", "02_justificacion-b01", self.draft("b1", ENGLISH["02_justificacion-b01"]))
        result = tr.audit(self.run_root, "en")
        self.assertEqual(result["checker"], "scripts/estilo_en.py")
        self.assertIn("readability", result["notice"])
        self.assertEqual([b["id"] for b in result["blocks"]], ["02_justificacion-b01"])
        self.assertEqual(result["fidelity"][0], {"id": "02_justificacion-b01", "state": "current",
                                                 "differences": [], "ok": True})
        saved = json.loads((self.run_root / "redaccion/traducciones/en/auditoria.json").read_text("utf-8"))
        self.assertEqual(saved["schema"], "morfeo.traduccion-auditoria/v1")
        self.assertTrue(tr.status(self.run_root, "en")["audit"]["fresh"])
        tr.store(self.run_root, "en", "02_justificacion-b02", self.draft("b2", ENGLISH["02_justificacion-b02"]))
        self.assertFalse(tr.status(self.run_root, "en")["audit"]["fresh"])


class SwitchMainTexTests(unittest.TestCase):
    def test_both_directions_round_trip_on_the_template(self) -> None:
        spanish = (REPO / "plantilla" / "main.tex").read_text(encoding="utf-8")
        english = language.switch_main_tex(spanish, "es", "en")
        self.assertEqual(english, language.localize_main_tex(spanish, "en"))
        self.assertEqual(language.switch_main_tex(english, "en", "es"), spanish)

    def test_an_edited_main_tex_keeps_working_and_needs_a_babel_line(self) -> None:
        edited = "\\documentclass{article}\n\\usepackage[spanish]{babel}\n\\begin{document}\\end{document}\n"
        self.assertIn(r"\usepackage[english]{babel}", language.switch_main_tex(edited, "es", "en"))
        with self.assertRaises(ValueError):
            language.switch_main_tex("\\documentclass{article}\n", "es", "en")


class CliTests(Base):
    def run_cli(self, *args: str) -> tuple[int, dict]:
        proc = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)

    def test_refusals_print_their_code_and_exit_1(self) -> None:
        code, payload = self.run_cli("build", str(self.run_root), "--lang", "en")
        self.assertEqual((code, payload["ok"], payload["code"]), (1, False, "TRANSLATION_NOT_PLANNED"))
        code, payload = self.run_cli("plan", str(self.run_root), "--lang", "en")
        self.assertEqual((code, payload["counts"]["missing"]), (0, 3))
        code, payload = self.run_cli("show", str(self.run_root), "--lang", "en", "--block", "02_justificacion-b02")
        self.assertEqual(code, 0)
        self.assertIn(r"\citep{smith2024,doe2025}", payload["source"])
        self.assertIsNone(payload["translation"])


if __name__ == "__main__":
    unittest.main()
