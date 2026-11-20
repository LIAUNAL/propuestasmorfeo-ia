"""scripts/anexo2_sgr.py: read-only view of the Anexo 2 chapters of an SGR run (odd/tasks/sgr-anexo2.md,
S2 and S3, schema `morfeo.anexo2-sgr/v1` of the Contracts section).

Every chapter lists the Morfeo sections that fill it with their state, the
writing rule parsed from docs/sgr/patrones_redaccion_sgr.md, the lexicon
counts of scripts/sgr/lexico_sgr.json, the rubric subcriteria that read it and
the check_run and estilo_sgr findings of its sections. A base run is refused
(S1) and nothing is ever written.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "anexo2_sgr.py"
LEXICON = REPO / "scripts" / "sgr" / "lexico_sgr.json"
RUBRICS = REPO / "scripts" / "rubricas_sgr"

SECTION_STATES = {"falta", "borrador", "redactado", "generado", "desactualizado"}
CHAPTER_STATES = {"falta", "incompleto", "desactualizado", "listo"}
SEVERITIES = {"error", "warning", "info"}


def _load():
    spec = importlib.util.spec_from_file_location("_test_anexo2_sgr", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prose(tag: str, words: int) -> str:
    """Neutral prose of `words` distinct tokens, unique per tag (no lexicon or redundancy hits)."""
    return " ".join(f"{tag}x{i}" for i in range(words)) + "\n"


def _make_run(tmp: Path, flujo: str | None = "sgr", rubric: str | None = "conv54", sections_dir: bool = True) -> Path:
    if flujo:
        (tmp / ".morfeo").mkdir(exist_ok=True)
        (tmp / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = tmp / "run"
    (run / "artefactos").mkdir(parents=True, exist_ok=True)
    if sections_dir:
        (run / "redaccion" / "sections").mkdir(parents=True, exist_ok=True)
    if rubric is not None:
        juez = run / "artefactos" / "juez"
        juez.mkdir(parents=True, exist_ok=True)
        (juez / "rubrica.json").write_text((RUBRICS / f"{rubric}.json").read_text(encoding="utf-8"),
                                           encoding="utf-8")
    return run


def _section(run: Path, stem: str, text: str) -> Path:
    path = run / "redaccion" / "sections" / f"{stem}.tex"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _structure(run: Path, chapters: list[dict]) -> None:
    (run / "artefactos" / "estructura_tdr.json").write_text(
        json.dumps({"fuente": "test", "capitulos": chapters}, ensure_ascii=False), encoding="utf-8")


def _chapter(view: dict, numero: int) -> dict:
    return next(c for c in view["capitulos"] if c["numero"] == numero)


def _sec(chapter: dict, stem: str) -> dict:
    return next(s for s in chapter["secciones"] if s["stem"] == stem)


def _snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): (p.stat().st_mtime_ns, p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()}


def _main(module, *args) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main([str(a) for a in args])
    return code, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load()
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class Contract(Base):
    """S2: the JSON follows the Contracts schema, keys and vocabularies included."""

    def test_shape_and_vocabularies(self) -> None:
        run = _make_run(self.tmp)
        _section(run, "26_identificacion", _prose("ide", 80))
        view = self.module.vista(run)
        self.assertEqual(set(view), {"schema", "flujo", "fuente_capitulos", "fuente_reglas", "rubrica", "resumen",
                                     "capitulos"})
        self.assertEqual(view["schema"], "morfeo.anexo2-sgr/v1")
        self.assertEqual(view["flujo"], "sgr")
        self.assertEqual(view["fuente_reglas"], "docs/sgr/patrones_redaccion_sgr.md")
        self.assertEqual(view["rubrica"], "conv54")
        self.assertEqual(set(view["resumen"]), {"capitulos", "por_estado", "palabras"})
        self.assertEqual(set(view["resumen"]["por_estado"]), CHAPTER_STATES)
        self.assertEqual(view["resumen"]["capitulos"], len(view["capitulos"]))
        self.assertEqual(sum(view["resumen"]["por_estado"].values()), len(view["capitulos"]))
        self.assertEqual(view["resumen"]["palabras"], 80)
        for chapter in view["capitulos"]:
            self.assertEqual(set(chapter), {"numero", "titulo", "estado", "palabras", "secciones", "regla", "lexico",
                                            "criterios", "hallazgos"})
            self.assertIsInstance(chapter["numero"], int)
            self.assertIsInstance(chapter["titulo"], str)
            self.assertIn(chapter["estado"], CHAPTER_STATES)
            self.assertEqual(set(chapter["lexico"]), {"favorecida", "desaconsejada", "prohibida"})
            for section in chapter["secciones"]:
                self.assertEqual(set(section), {"stem", "existe", "palabras", "origen", "script", "estado",
                                                "hallazgos", "guia"})
                self.assertIn(section["estado"], SECTION_STATES)
                self.assertIn(section["origen"], {"generado", "manual", None})
                self.assertEqual(set(section["hallazgos"]), SEVERITIES)
            if chapter["regla"] is not None:
                self.assertEqual(set(chapter["regla"]), {"proposito", "estructura", "extension", "aperturas",
                                                         "evitar", "fuente"})
            for criterion in chapter["criterios"]:
                self.assertEqual(set(criterion), {"id", "nombre", "max"})
            for finding in chapter["hallazgos"]:
                self.assertEqual(set(finding), {"severidad", "codigo", "mensaje", "seccion"})
                self.assertIn(finding["severidad"], SEVERITIES)


class Chapters(Base):
    """S2: chapters from estructura_tdr.json placed for the SGR flow, else from the lexicon map."""

    def test_lexicon_fallback_has_31_chapters(self) -> None:
        view = self.module.vista(_make_run(self.tmp))
        self.assertEqual(view["fuente_capitulos"], "scripts/sgr/lexico_sgr.json")
        lexicon = json.loads(LEXICON.read_text(encoding="utf-8"))["mapa_capitulos"]
        self.assertEqual(len(view["capitulos"]), 31)
        self.assertEqual([c["numero"] for c in view["capitulos"]], list(range(1, 32)))
        self.assertEqual([c["titulo"] for c in view["capitulos"]], [c["titulo"] for c in lexicon])
        self.assertEqual([s["stem"] for s in _chapter(view, 12)["secciones"]],
                         ["06_objetivo_general", "07_objetivos_especificos", "09_equipo_trabajo", "36_talento_humano"])

    def test_structure_placed_with_sgr_sections(self) -> None:
        run = _make_run(self.tmp)
        _structure(run, [
            {"numero": 1, "titulo": "IDENTIFICACIÓN DEL PROYECTO", "archivos": []},
            {"numero": 2, "titulo": "Resumen ejecutivo", "archivos": ["00_frontmatter"]},
        ])
        view = self.module.vista(run)
        self.assertEqual(view["fuente_capitulos"], "artefactos/estructura_tdr.json")
        self.assertEqual([c["numero"] for c in view["capitulos"]], [1, 2])
        # placed_chapters appends 26_identificacion to the chapter whose title matches.
        self.assertEqual([s["stem"] for s in _chapter(view, 1)["secciones"]], ["26_identificacion"])
        self.assertEqual(_chapter(view, 2)["titulo"], "Resumen ejecutivo")

    def test_invalid_structure_falls_back_to_lexicon(self) -> None:
        run = _make_run(self.tmp)
        (run / "artefactos" / "estructura_tdr.json").write_text('{"capitulos": []}', encoding="utf-8")
        view = self.module.vista(run)
        self.assertEqual(view["fuente_capitulos"], "scripts/sgr/lexico_sgr.json")
        self.assertEqual(len(view["capitulos"]), 31)

    def test_diag_files_are_not_sections(self) -> None:
        run = _make_run(self.tmp)
        _structure(run, [{"numero": 5, "titulo": "IDENTIFICACIÓN Y DESCRIPCIÓN DEL PROBLEMA",
                          "archivos": ["diag_arbol_problemas", "03_descripcion_problema"]}])
        _section(run, "diag_arbol_problemas", _prose("dia", 80))
        view = self.module.vista(run)
        self.assertEqual([s["stem"] for s in _chapter(view, 5)["secciones"]], ["03_descripcion_problema"])


class SectionStates(Base):
    """Contracts: falta, borrador, redactado, generado and desactualizado, with origin and script."""

    def test_falta(self) -> None:
        section = _sec(_chapter(self.module.vista(_make_run(self.tmp)), 9), "08_marco_conceptual")
        self.assertEqual((section["existe"], section["palabras"], section["origen"], section["script"],
                          section["estado"]), (False, 0, None, None, "falta"))

    def test_borrador_counts_words_without_comments(self) -> None:
        run = _make_run(self.tmp)
        _section(run, "08_marco_conceptual", "% " + _prose("com", 200) + _prose("mar", 50))
        section = _sec(_chapter(self.module.vista(run), 9), "08_marco_conceptual")
        self.assertEqual((section["existe"], section["palabras"], section["origen"], section["estado"]),
                         (True, 50, "manual", "borrador"))

    def test_redactado(self) -> None:
        run = _make_run(self.tmp)
        _section(run, "08_marco_conceptual", _prose("mar", 51))
        section = _sec(_chapter(self.module.vista(run), 9), "08_marco_conceptual")
        self.assertEqual((section["palabras"], section["origen"], section["script"], section["estado"]),
                         (51, "manual", None, "redactado"))

    def test_bibliography_is_never_a_draft(self) -> None:
        run = _make_run(self.tmp)
        _section(run, "16_bibliografia", "\\bibliography{refs}\n")
        section = _sec(_chapter(self.module.vista(run), 30), "16_bibliografia")
        self.assertEqual((section["palabras"], section["estado"]), (1, "redactado"))

    def test_generado(self) -> None:
        run = _make_run(self.tmp)
        _section(run, "39_anexos", "% GENERADO por scripts/requisitos_sgr.py\n% Fuente: x.\n" + _prose("anx", 10))
        section = _sec(_chapter(self.module.vista(run), 31), "39_anexos")
        self.assertEqual((section["origen"], section["script"], section["estado"]),
                         ("generado", "scripts/requisitos_sgr.py", "generado"))

    def test_desactualizado_when_check_run_reports_stale(self) -> None:
        run = _make_run(self.tmp)
        tex = _section(run, "39_anexos", "% GENERADO por scripts/requisitos_sgr.py\n" + _prose("anx", 80))
        data = run / "artefactos" / "sgr" / "requisitos.json"
        data.parent.mkdir(parents=True, exist_ok=True)
        data.write_text("{}", encoding="utf-8")
        os.utime(tex, (data.stat().st_mtime - 100, data.stat().st_mtime - 100))
        view = self.module.vista(run)
        section = _sec(_chapter(view, 31), "39_anexos")
        self.assertEqual((section["origen"], section["estado"]), ("generado", "desactualizado"))
        self.assertIn("requisitos-anexo-desactualizado", [f["codigo"] for f in _chapter(view, 31)["hallazgos"]])

    def test_guide_key(self) -> None:
        view = self.module.vista(_make_run(self.tmp))
        self.assertEqual(_sec(_chapter(view, 1), "26_identificacion")["guia"], "A26")
        self.assertEqual(_sec(_chapter(view, 4), "19_alineacion_planes")["guia"], "A19")
        self.assertEqual(_sec(_chapter(view, 19), "18_apropiacion_social")["guia"], "§18")
        self.assertEqual(_sec(_chapter(view, 7), "02_justificacion")["guia"], "§2")


class ChapterStates(Base):
    """Contracts: falta, incompleto, desactualizado and listo, and the summary by state."""

    def test_states(self) -> None:
        run = _make_run(self.tmp)
        # 9: single section written -> listo; 12: one of four sections -> incompleto;
        # 10: every section a draft -> incompleto; 31: generated and stale -> desactualizado; 6: none -> falta.
        _section(run, "08_marco_conceptual", _prose("mar", 80))
        _section(run, "06_objetivo_general", _prose("obj", 80))
        _section(run, "20_participantes", _prose("par", 5))
        _section(run, "28_matriz_responsabilidades", _prose("mat", 5))
        tex = _section(run, "39_anexos", "% GENERADO por scripts/requisitos_sgr.py\n" + _prose("anx", 80))
        data = run / "artefactos" / "sgr" / "requisitos.json"
        data.parent.mkdir(parents=True, exist_ok=True)
        data.write_text("{}", encoding="utf-8")
        os.utime(tex, (data.stat().st_mtime - 100, data.stat().st_mtime - 100))
        view = self.module.vista(run)
        states = {c["numero"]: c["estado"] for c in view["capitulos"]}
        self.assertEqual(states[9], "listo")
        self.assertEqual(states[12], "incompleto")
        self.assertEqual(states[10], "incompleto")
        self.assertEqual(states[31], "desactualizado")
        self.assertEqual(states[6], "falta")
        self.assertEqual(_chapter(view, 12)["palabras"], 80)
        counts = view["resumen"]["por_estado"]
        self.assertEqual(counts, {"listo": 1, "incompleto": 2, "desactualizado": 1, "falta": 27})
        self.assertEqual(view["resumen"]["palabras"], 80 + 80 + 5 + 5 + 80)

    def test_generated_fresh_section_is_listo(self) -> None:
        run = _make_run(self.tmp)
        _section(run, "39_anexos", "% GENERADO por scripts/requisitos_sgr.py\n" + _prose("anx", 3))
        self.assertEqual(_chapter(self.module.vista(run), 31)["estado"], "listo")


class Rules(Base):
    """S3: the rule of each chapter, parsed from section «## 2.» and matched by title or number."""

    def test_rule_parsed_from_the_patterns_document(self) -> None:
        view = self.module.vista(_make_run(self.tmp))
        rule = _chapter(view, 1)["regla"]
        self.assertTrue(rule["proposito"].startswith("Ficha: nombre, entidades y aspa"))
        self.assertTrue(rule["estructura"].startswith("Campos rotulados de la plantilla + dos tablas."))
        self.assertIn("Demandas (referencia)", rule["estructura"])
        self.assertTrue(rule["extension"].startswith("1.076 palabras de prosa"))
        self.assertEqual(len(rule["aperturas"]), 5)
        self.assertTrue(rule["aperturas"][0].startswith("«La propuesta se enmarca en el Desafío"))
        self.assertEqual(len(rule["evitar"]), 4)
        self.assertEqual(rule["fuente"], "Anexo 2 Conv 54/56 cap. 1; Directriz SGR 6 de Morfeo.")
        # Label variants: «Propósito (plantilla)», «Aperturas y expresiones favorecidas».
        rule2 = _chapter(view, 2)["regla"]
        self.assertTrue(rule2["proposito"].startswith("«Información mínima necesaria"))
        self.assertEqual(len(rule2["aperturas"]), 7)

    def test_title_match_ignores_accents_case_and_takes_prefixes(self) -> None:
        run = _make_run(self.tmp)
        _structure(run, [
            {"numero": 40, "titulo": "articulacion del proyecto con las demandas territoriales", "archivos": []},
            {"numero": 5, "titulo": "Capítulo inventado", "archivos": []},
            {"numero": 7, "titulo": "Justificación.", "archivos": []},
        ])
        view = self.module.vista(run)
        self.assertTrue(_chapter(view, 40)["regla"]["proposito"])
        self.assertIsNone(_chapter(view, 5)["regla"])  # no number fallback for structure chapters
        self.assertIsNotNone(_chapter(view, 7)["regla"])

    def test_number_fallback_for_lexicon_chapters_and_missing_file(self) -> None:
        doc = self.tmp / "patrones.md"
        doc.write_text("# P\n\n## 1. Voz\n\n### 1. NO ES CAPITULO\n\n- **Propósito.** No.\n\n"
                       "## 2. Patrones\n\n### 7. OTRO TÍTULO\n\n- **Propósito.** Justificar.\n"
                       "- **Evitar.** Una sola cosa.\n\n## 3. Léxico\n\n### 8. TAMPOCO\n", encoding="utf-8")
        run = _make_run(self.tmp)
        with mock.patch.object(self.module, "RULES_FILE", doc):
            view = self.module.vista(run)
        self.assertEqual(_chapter(view, 7)["regla"], {"proposito": "Justificar.", "estructura": None,
                                                      "extension": None, "aperturas": [],
                                                      "evitar": ["Una sola cosa."], "fuente": None})
        self.assertIsNone(_chapter(view, 1)["regla"])
        self.assertIsNone(_chapter(view, 8)["regla"])
        with mock.patch.object(self.module, "RULES_FILE", self.tmp / "missing.md"):
            view = self.module.vista(run)
        self.assertIsNone(view["fuente_reglas"])
        self.assertTrue(all(c["regla"] is None for c in view["capitulos"]))


class LexiconAndRubric(Base):
    """S3: lexicon counts per chapter and the rubric subcriteria that read its stems."""

    def test_lexicon_counts(self) -> None:
        sections = json.loads(LEXICON.read_text(encoding="utf-8"))["secciones"]
        view = self.module.vista(_make_run(self.tmp))
        for numero in (1, 12, 29):
            chapter = _chapter(view, numero)
            expected = {"favorecida": 0, "desaconsejada": 0, "prohibida": 0}
            for section in chapter["secciones"]:
                for entry in sections.get(section["stem"]) or []:
                    expected[entry["tipo"]] += 1
            self.assertEqual(chapter["lexico"], expected)
        self.assertGreater(sum(_chapter(view, 1)["lexico"].values()), 0)

    def test_rubric_criteria_by_evidence(self) -> None:
        view = self.module.vista(_make_run(self.tmp))
        self.assertEqual([c["id"] for c in _chapter(view, 1)["criterios"]], ["2.1", "2.2", "3.2", "3.3"])
        first = _chapter(view, 1)["criterios"][0]
        self.assertEqual(first["max"], 7)
        self.assertTrue(first["nombre"])
        self.assertEqual(_chapter(view, 30)["criterios"], [])

    def test_no_rubric(self) -> None:
        view = self.module.vista(_make_run(self.tmp, rubric=None))
        self.assertIsNone(view["rubrica"])
        self.assertTrue(all(c["criterios"] == [] for c in view["capitulos"]))


class Findings(Base):
    """Contracts: check_run and estilo_sgr findings mapped by stem; at most 20 per chapter, errors first."""

    def test_findings_mapped_and_capped(self) -> None:
        run = _make_run(self.tmp)
        lines = [f"Linea{i} del marco — con raya.\n" for i in range(15)]
        lines += [f"Nosotros revisamos{i} el marco.\n" for i in range(10)]
        _section(run, "08_marco_conceptual", "".join(lines) + _prose("mar", 60))
        _section(run, "06_objetivo_general", "Objetivo — con raya.\n" + _prose("obj", 60))
        view = self.module.vista(run)
        chapter = _chapter(view, 9)
        counts = _sec(chapter, "08_marco_conceptual")["hallazgos"]
        self.assertGreaterEqual(counts["error"], 15)
        self.assertGreaterEqual(counts["warning"], 10)
        self.assertEqual(len(chapter["hallazgos"]), 20)
        order = {"error": 0, "warning": 1, "info": 2}
        ranks = [order[f["severidad"]] for f in chapter["hallazgos"]]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(sum(1 for f in chapter["hallazgos"] if f["severidad"] == "error"), min(20, counts["error"]))
        self.assertIn("raya-en-prosa", [f["codigo"] for f in chapter["hallazgos"]])
        self.assertTrue(all(f["seccion"] == "08_marco_conceptual" for f in chapter["hallazgos"]))
        # The objective's raya stays in chapter 12, never in chapter 9.
        other = _chapter(view, 12)
        self.assertEqual(_sec(other, "06_objetivo_general")["hallazgos"]["error"], 1)
        self.assertEqual([f["seccion"] for f in other["hallazgos"] if f["codigo"] == "raya-en-prosa"],
                         ["06_objetivo_general"])

    def test_style_findings_counted_once_with_their_severity(self) -> None:
        run = _make_run(self.tmp)
        _section(run, "08_marco_conceptual", "Nosotros revisamos el marco.\n" + _prose("mar", 60))
        chapter = _chapter(self.module.vista(run), 9)
        style = [f for f in chapter["hallazgos"] if f["codigo"] == "sgr-estilo-primera-persona"]
        self.assertEqual(len(style), 1)
        self.assertEqual(style[0]["severidad"], "warning")


class Cli(Base):
    """S2: text and --json outputs, the base-run refusal and no writes."""

    def test_base_run_exits_2_and_writes_nothing(self) -> None:
        run = _make_run(self.tmp, flujo=None)
        before = _snapshot(self.tmp)
        code, out, err = _main(self.module, "datos", run, "--json")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("flujo SGR", err)
        self.assertEqual(_snapshot(self.tmp), before)
        with self.assertRaises(self.module.InputError):
            self.module.vista(run)

    def test_sgr_run_writes_nothing(self) -> None:
        run = _make_run(self.tmp)
        _section(run, "08_marco_conceptual", _prose("mar", 80))
        before = _snapshot(self.tmp)
        self.assertEqual(_main(self.module, "datos", run)[0], 0)
        self.assertEqual(_main(self.module, "datos", run, "--json")[0], 0)
        self.assertEqual(_snapshot(self.tmp), before)

    def test_missing_sections_dir_is_all_falta(self) -> None:
        run = _make_run(self.tmp, sections_dir=False)
        view = self.module.vista(run)
        self.assertEqual(view["resumen"]["por_estado"]["falta"], 31)

    def test_missing_run_exits_2(self) -> None:
        code, out, err = _main(self.module, "datos", self.tmp / "nope")
        self.assertEqual(code, 2)
        self.assertIn("error:", err)

    def test_text_output_one_line_per_chapter(self) -> None:
        run = _make_run(self.tmp)
        _section(run, "08_marco_conceptual", _prose("mar", 80))
        code, out, _ = _main(self.module, "datos", run)
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(len(lines), 31)
        self.assertTrue(lines[8].startswith("9."))
        self.assertIn("listo", lines[8])
        self.assertIn("MARCO CONCEPTUAL", lines[8])
        self.assertIn("08_marco_conceptual (redactado)", lines[8])

    def test_json_output_equals_vista(self) -> None:
        run = _make_run(self.tmp)
        _section(run, "08_marco_conceptual", _prose("mar", 80))
        code, out, _ = _main(self.module, "datos", run, "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), self.module.vista(run))


if __name__ == "__main__":
    unittest.main()
