"""Call-specific rules of the SGR flow (odd/tasks/sgr-flujo-convocatorias.md, S1-S4, S6).

The rules of a call live in artefactos/convocatoria.json, not in the code: the
reference floors, the number of specific objectives, the TRL level and the
scoring rubric. When the call fixes its own chapters, --final requires the files
of artefactos/estructura_tdr.json. Every test that names the base flow pins that
none of this reaches it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "src"))

from test_check_run import _cites, _clean_run, _codes, _keys, _run  # noqa: E402

from morfeo.core.sgr_rules import parse_sgr_blocks  # noqa: E402

GUIDE = REPO / "guiaProyectosIA_Agente_Regalias.md"
SGR = ("--flujo", "sgr")
FINAL = ("--flujo", "sgr", "--final")


def _load_check_run():
    spec = importlib.util.spec_from_file_location("check_run_convocatoria", REPO / "scripts" / "check_run.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CHECK_RUN = _load_check_run()


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _convocatoria(root: Path, data: dict) -> None:
    _write(root, "artefactos/convocatoria.json", json.dumps(data, ensure_ascii=False))


def _structure(root: Path, chapters: list[dict]) -> None:
    _write(root, "artefactos/estructura_tdr.json", json.dumps({"capitulos": chapters}, ensure_ascii=False))


def _section(root: Path, name: str, text: str) -> None:
    _write(root, f"redaccion/sections/{name}.tex", text)


def _objectives(root: Path, count: int) -> None:
    items = "".join(f"\\item Objetivo {i}.\n" for i in range(count))
    _section(root, "07_objetivos_especificos", f"\\section{{Objetivos}}\n\\begin{{enumerate}}\n{items}\\end{{enumerate}}\n")


def _with(findings: list[dict], code: str, severity: str | None = None) -> list[dict]:
    return [f for f in findings if f["code"] == code and (severity is None or f["severity"] == severity)]


class RunCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = _clean_run(Path(tmp.name))


class LoadConvocatoria(RunCase):
    def test_an_absent_file_declares_nothing_and_is_no_finding(self) -> None:
        self.assertEqual(CHECK_RUN.load_convocatoria(self.root), {})
        _, findings = _run(self.root, *SGR)
        self.assertNotIn("convocatoria-invalida", _codes(findings))

    def test_a_valid_file_is_returned(self) -> None:
        data = {"nombre": "Convocatoria 56", "objetivos_especificos": 4,
                "pisos_referencias": {"total": 30}, "trl": {"tipologia": "DT", "entrada": 3, "salida": 6},
                "rubrica": [{"id": "1", "criterio": "Calidad", "puntos": 100, "capitulos": [1], "evidencia": "x"}]}
        _convocatoria(self.root, data)
        self.assertEqual(CHECK_RUN.load_convocatoria(self.root), data)

    def test_a_broken_file_gives_one_error_and_declares_nothing(self) -> None:
        _write(self.root, "artefactos/convocatoria.json", "{no es json")
        code, findings = _run(self.root, *SGR)
        self.assertEqual(len(_with(findings, "convocatoria-invalida", "error")), 1, findings)
        self.assertEqual(code, 1)
        self.assertEqual(_with(findings, "convocatoria-invalida")[0]["file"], "artefactos/convocatoria.json")

    def test_a_json_that_is_not_an_object_gives_one_error(self) -> None:
        _write(self.root, "artefactos/convocatoria.json", "[1, 2]")
        _, findings = _run(self.root, *SGR)
        self.assertEqual(len(_with(findings, "convocatoria-invalida", "error")), 1, findings)

    def test_wrong_types_give_one_error_however_many_they_are(self) -> None:
        _convocatoria(self.root, {"objetivos_especificos": "cuatro", "pisos_referencias": {"total": "65"},
                                  "trl": {"salida": "seis"}, "rubrica": {"id": "1"}})
        _, findings = _run(self.root, *SGR)
        self.assertEqual(len(_with(findings, "convocatoria-invalida", "error")), 1, findings)

    def test_the_base_flow_never_reads_the_file(self) -> None:
        _write(self.root, "artefactos/convocatoria.json", "{no es json")
        code, findings = _run(self.root)
        self.assertNotIn("convocatoria-invalida", _codes(findings))
        self.assertEqual(code, 0)


class Floors(RunCase):
    def setUp(self) -> None:
        super().setUp()
        _section(self.root, "02_justificacion",
                 "\\section{Justificación}\nAlcanza TRL 6. " + _cites(_keys("j", 5)) + "\n")

    def test_sgr_without_declared_floors_only_warns_with_the_base_numbers(self) -> None:
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(_with(findings, "piso-referencias", "error"), [], findings)
        warnings = _with(findings, "piso-referencias", "warning")
        self.assertEqual(len(warnings), 2, warnings)
        self.assertIn("mínimo 13", warnings[0]["message"])
        self.assertIn("mínimo 65", warnings[1]["message"])

    def test_sgr_declared_floors_are_errors_with_the_declared_number(self) -> None:
        _convocatoria(self.root, {"pisos_referencias": {"justificacion": 8, "total": 500}})
        code, findings = _run(self.root, *FINAL)
        errors = _with(findings, "piso-referencias", "error")
        self.assertEqual(len(errors), 2, errors)
        self.assertIn("mínimo 8", errors[0]["message"])
        self.assertIn("mínimo 500", errors[1]["message"])
        self.assertEqual(code, 1)

    def test_a_declared_floor_lower_than_the_base_one_is_enough(self) -> None:
        _convocatoria(self.root, {"pisos_referencias": {"justificacion": 5, "estado_arte": 39, "total": 40}})
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(_with(findings, "piso-referencias"), [], findings)

    def test_a_floor_left_undeclared_stays_a_warning_next_to_a_declared_one(self) -> None:
        _convocatoria(self.root, {"pisos_referencias": {"total": 40}})
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(_with(findings, "piso-referencias", "error"), [], findings)
        self.assertEqual(len(_with(findings, "piso-referencias", "warning")), 1, findings)

    def test_the_total_floor_still_waits_for_final(self) -> None:
        _convocatoria(self.root, {"pisos_referencias": {"total": 500}})
        _, findings = _run(self.root, *SGR)
        self.assertEqual(_with(findings, "piso-referencias", "error"), [], findings)

    def test_the_base_flow_keeps_its_fixed_floors_as_errors(self) -> None:
        _convocatoria(self.root, {"pisos_referencias": {"justificacion": 2}})
        code, findings = _run(self.root)
        self.assertIn("mínimo 13", _with(findings, "piso-referencias", "error")[0]["message"])
        self.assertEqual(code, 1)


class Objectives(RunCase):
    def test_the_declared_number_is_the_rule(self) -> None:
        _convocatoria(self.root, {"objetivos_especificos": 4})
        _objectives(self.root, 4)
        _, findings = _run(self.root, *SGR)
        self.assertEqual(_with(findings, "objetivos-no-son-3"), [], findings)

    def test_a_different_number_than_the_declared_one_is_an_error(self) -> None:
        _convocatoria(self.root, {"objetivos_especificos": 4})
        code, findings = _run(self.root, *SGR)
        errors = _with(findings, "objetivos-no-son-3", "error")
        self.assertEqual(len(errors), 1, findings)
        self.assertIn("3 objetivos", errors[0]["message"])
        self.assertIn("exige 4", errors[0]["message"])
        self.assertEqual(code, 1)

    def test_sgr_without_a_declared_number_warns_below_three(self) -> None:
        _objectives(self.root, 2)
        _, findings = _run(self.root, *SGR)
        self.assertEqual(_with(findings, "objetivos-no-son-3", "error"), [], findings)
        self.assertEqual(len(_with(findings, "objetivos-no-son-3", "warning")), 1, findings)

    def test_sgr_without_a_declared_number_accepts_more_than_three(self) -> None:
        _objectives(self.root, 5)
        _, findings = _run(self.root, *SGR)
        self.assertEqual(_with(findings, "objetivos-no-son-3"), [], findings)

    def test_the_base_flow_keeps_exactly_three(self) -> None:
        _convocatoria(self.root, {"objetivos_especificos": 4})
        _objectives(self.root, 4)
        code, findings = _run(self.root)
        self.assertIn("el mapeo 1:1 exige 3", _with(findings, "objetivos-no-son-3", "error")[0]["message"])
        self.assertEqual(code, 1)


class Trl(RunCase):
    def test_the_message_names_the_declared_level(self) -> None:
        _convocatoria(self.root, {"trl": {"entrada": 3, "salida": 5}})
        _section(self.root, "02_justificacion", "\\section{Justificación}\nSin nivel.\n")
        _, findings = _run(self.root, *SGR)
        missing = [f for f in _with(findings, "trl-ausente", "error") if f["file"].endswith("02_justificacion.tex")]
        self.assertEqual(len(missing), 1, findings)
        self.assertIn("TRL 5", missing[0]["message"])
        self.assertNotIn("6 o 7", missing[0]["message"])

    def test_another_level_does_not_satisfy_the_declared_one(self) -> None:
        _convocatoria(self.root, {"trl": {"salida": 5}})
        _, findings = _run(self.root, *SGR)
        self.assertEqual(len(_with(findings, "trl-ausente", "error")), 2, findings)

    def test_the_declared_level_passes_in_any_usual_spelling(self) -> None:
        _convocatoria(self.root, {"trl": {"salida": 5}})
        _section(self.root, "02_justificacion", "\\section{J}\nLlega a TRL~5.\n" + _cites(_keys("j", 13)) + "\n")
        _section(self.root, "11_resultados_esperados", "\\section{R}\nAvanza de TRL 3 a 5.\n")
        _, findings = _run(self.root, *SGR)
        self.assertEqual(_with(findings, "trl-ausente", "error"), [], findings)

    def test_without_a_declared_level_the_message_drops_the_fixed_range(self) -> None:
        _section(self.root, "02_justificacion", "\\section{Justificación}\nSin nivel.\n")
        _, findings = _run(self.root, *SGR)
        missing = _with(findings, "trl-ausente", "error")
        self.assertEqual(len(missing), 1, findings)
        self.assertNotIn("6 o 7", missing[0]["message"])
        self.assertIn("convocatoria.json", missing[0]["message"])

    def test_the_trl_stays_out_of_the_objectives(self) -> None:
        _convocatoria(self.root, {"trl": {"salida": 5}})
        _section(self.root, "06_objetivo_general", "\\section{Objetivo}\nLlegar a TRL 5.\n")
        _, findings = _run(self.root, *SGR)
        self.assertEqual(len(_with(findings, "trl-en-objetivos", "error")), 1, findings)

    def test_an_exit_level_below_the_entry_level_is_an_error(self) -> None:
        _convocatoria(self.root, {"trl": {"entrada": 6, "salida": 4}})
        code, findings = _run(self.root, *SGR)
        self.assertEqual(len(_with(findings, "convocatoria-trl-invertido", "error")), 1, findings)
        self.assertEqual(code, 1)

    def test_the_base_flow_keeps_its_message(self) -> None:
        _convocatoria(self.root, {"trl": {"entrada": 6, "salida": 4}})
        _section(self.root, "02_justificacion", "\\section{Justificación}\nSin nivel.\n")
        _, findings = _run(self.root)
        self.assertEqual(_with(findings, "trl-ausente", "error")[0]["message"],
                         "TRL 6 o 7 debe ser explícito en esta sección.")
        self.assertNotIn("convocatoria-trl-invertido", _codes(findings))


class TdrChapters(RunCase):
    """A correct mapping absorbs 17_ and 19_ into tdr* files and must pass --final."""

    def setUp(self) -> None:
        super().setUp()
        _section(self.root, "tdr01_identificacion", "\\section{Identificación}\nTexto del capítulo.\n")
        _section(self.root, "tdr02_comunidades", "\\section{Comunidades}\nTexto del capítulo.\n")
        self.chapters = [
            {"numero": 1, "titulo": "Identificación", "archivos": ["tdr01_identificacion", "diag_arbol_problemas"]},
            {"numero": 2, "titulo": "Comunidades", "archivos": ["tdr02_comunidades"]},
            {"numero": 3, "titulo": "Justificación", "archivos": ["02_justificacion"]},
        ]
        _structure(self.root, self.chapters)

    def test_final_requires_the_chapter_files_instead_of_the_canonical_lists(self) -> None:
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(_with(findings, "seccion-faltante"), [], findings)
        self.assertEqual(_with(findings, "sgr-anexo-faltante"), [], findings)

    def test_final_requires_the_sgr_sections_placed_in_a_matching_chapter(self) -> None:
        # ensamblar_main.placed_chapters appends 30_fuentes_financiacion to the chapter
        # titled «Fuentes de financiación»; --final then needs that file too.
        self.chapters.append({"numero": 4, "titulo": "Fuentes de financiación", "archivos": ["tdr04_fuentes"]})
        _structure(self.root, self.chapters)
        _section(self.root, "tdr04_fuentes", "\\section{Fuentes de financiación}\nTexto del capítulo.\n")
        code, findings = _run(self.root, *FINAL)
        missing = _with(findings, "seccion-faltante", "error")
        self.assertEqual([f["message"] for f in missing],
                         ["Falta sections/30_fuentes_financiacion.tex (capítulo 4)."], findings)
        self.assertEqual(code, 1)
        _section(self.root, "30_fuentes_financiacion", "% GENERADO por scripts/presupuesto_sgr.py\nTabla.\n")
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(_with(findings, "seccion-faltante"), [], findings)

    def test_a_missing_chapter_file_is_an_error(self) -> None:
        (self.root / "redaccion/sections/tdr01_identificacion.tex").unlink()
        code, findings = _run(self.root, *FINAL)
        missing = _with(findings, "seccion-faltante", "error")
        self.assertEqual(len(missing), 1, findings)
        self.assertIn("tdr01_identificacion", missing[0]["message"])
        self.assertEqual(code, 1)

    def test_a_chapter_figure_is_optional(self) -> None:
        _, findings = _run(self.root, *FINAL)
        self.assertFalse([f for f in findings if "diag_arbol_problemas" in f["message"]], findings)

    def test_a_chapter_with_all_its_files_missing_is_an_error_in_final(self) -> None:
        (self.root / "redaccion/sections/tdr02_comunidades.tex").unlink()
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(len(_with(findings, "tdr-capitulo-vacio", "error")), 1, findings)
        self.assertIn("capítulo 2", _with(findings, "tdr-capitulo-vacio")[0]["message"])

    def test_a_chapter_with_only_a_heading_or_comments_is_empty(self) -> None:
        _section(self.root, "tdr02_comunidades", "% pendiente\n\\section{Comunidades}\n\\label{sec:c}\n\n")
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(len(_with(findings, "tdr-capitulo-vacio", "error")), 1, findings)
        self.assertEqual(_with(findings, "seccion-faltante"), [], findings)

    def test_a_chapter_without_files_is_empty(self) -> None:
        self.chapters.append({"numero": 4, "titulo": "Otro", "archivos": []})
        _structure(self.root, self.chapters)
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(len(_with(findings, "tdr-capitulo-vacio", "error")), 1, findings)

    def test_a_chapter_with_only_its_figure_has_content(self) -> None:
        self.chapters.append({"numero": 4, "titulo": "Figura", "archivos": ["diag_mapa"]})
        _structure(self.root, self.chapters)
        _section(self.root, "diag_mapa", "\\begin{tikzpicture}\\end{tikzpicture}\n")
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(_with(findings, "tdr-capitulo-vacio"), [], findings)

    def test_empty_chapters_wait_for_final(self) -> None:
        (self.root / "redaccion/sections/tdr02_comunidades.tex").unlink()
        _, findings = _run(self.root, *SGR)
        self.assertNotIn("tdr-capitulo-vacio", _codes(findings))
        self.assertNotIn("seccion-faltante", _codes(findings))

    def test_tdr_files_go_through_the_prose_and_citation_checks(self) -> None:
        _section(self.root, "tdr01_identificacion", "\\section{I}\nUna raya — aquí. Ver \\cite{a1}.\n")
        _, findings = _run(self.root, *SGR)
        self.assertEqual(_with(findings, "raya-en-prosa")[0]["file"], "redaccion/sections/tdr01_identificacion.tex")
        self.assertIn("cite-generico", _codes(findings, "error"))

    def test_tdr_citations_count_towards_the_total_floor(self) -> None:
        _convocatoria(self.root, {"pisos_referencias": {"total": 70}})
        _section(self.root, "tdr01_identificacion", "\\section{I}\n" + _cites(_keys("t", 10)) + "\n")
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(_with(findings, "piso-referencias", "error"), [], findings)

    def test_a_structure_that_cannot_be_read_is_an_error_in_final(self) -> None:
        _write(self.root, "artefactos/estructura_tdr.json", "{no es json")
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(len(_with(findings, "tdr-estructura-invalida", "error")), 1, findings)

    def test_the_base_flow_keeps_the_canonical_sections_and_skips_tdr_files(self) -> None:
        _section(self.root, "tdr01_identificacion", "\\section{I}\nUna raya — aquí.\n")
        _, findings = _run(self.root, "--final")
        self.assertIn("17_articulacion_comunidades", " ".join(f["message"] for f in _with(findings, "seccion-faltante")))
        self.assertNotIn("raya-en-prosa", _codes(findings))
        self.assertNotIn("tdr-capitulo-vacio", _codes(findings))


class MissingStructure(RunCase):
    TABLE = ("| Cap. Anexo 2 | Sección | Archivo(s) |\n|---|---|---|\n"
             "| 1 | Identificación | `tdr01_identificacion.tex` |\n")

    def test_final_without_structure_errors_when_the_guide_has_a_chapter_table(self) -> None:
        _write(self.root, "artefactos/guia_ajustada_TDR.md", self.TABLE)
        code, findings = _run(self.root, *FINAL)
        self.assertEqual(len(_with(findings, "tdr-estructura-faltante", "error")), 1, findings)
        self.assertEqual(code, 1)

    def test_without_final_it_is_no_finding(self) -> None:
        _write(self.root, "artefactos/guia_ajustada_TDR.md", self.TABLE)
        _, findings = _run(self.root, *SGR)
        self.assertNotIn("tdr-estructura-faltante", _codes(findings))

    def test_a_guide_without_a_chapter_table_keeps_the_canonical_requirement(self) -> None:
        _write(self.root, "artefactos/guia_ajustada_TDR.md", "# Guía\n\nSin tabla de capítulos.\n")
        _, findings = _run(self.root, *FINAL)
        self.assertNotIn("tdr-estructura-faltante", _codes(findings))
        self.assertIn("seccion-faltante", _codes(findings, "error"))
        self.assertIn("sgr-anexo-faltante", _codes(findings, "error"))

    def test_a_numbered_table_without_files_is_not_a_chapter_table(self) -> None:
        _write(self.root, "artefactos/guia_ajustada_TDR.md", "| 1 | Pertinencia | 20 |\n| 2 | Calidad | 80 |\n")
        _, findings = _run(self.root, *FINAL)
        self.assertNotIn("tdr-estructura-faltante", _codes(findings))

    def test_the_base_flow_ignores_the_table(self) -> None:
        _write(self.root, "artefactos/guia_ajustada_TDR.md", self.TABLE)
        _, findings = _run(self.root, "--final")
        self.assertNotIn("tdr-estructura-faltante", _codes(findings))


class WorkMarks(RunCase):
    TEXT = ("\\section{Riesgos}\nCifra [PENDIENTE: dato].\n% [VERIFICAR] en un comentario no cuenta\n"
            "Otra [VERIFICAR fuente] y [CONFIRMAR].\n"
            "\\begin{tabular}{l}\n[PROPUESTA de rubro] \\\\\n\\end{tabular}\n")

    def setUp(self) -> None:
        super().setUp()
        _section(self.root, "24_riesgos", self.TEXT)

    def test_each_mark_is_a_warning_with_file_and_line(self) -> None:
        code, findings = _run(self.root, *SGR)
        marks = _with(findings, "sgr-marca-trabajo")
        self.assertEqual({f["severity"] for f in marks}, {"warning"})
        self.assertEqual([(f["file"], f["line"]) for f in marks],
                         [("redaccion/sections/24_riesgos.tex", n) for n in (2, 4, 4, 6)])
        self.assertEqual(code, 0)

    def test_final_turns_them_into_errors(self) -> None:
        _, findings = _run(self.root, *FINAL)
        self.assertEqual(len(_with(findings, "sgr-marca-trabajo", "error")), 4, findings)

    def test_the_base_flow_ignores_them(self) -> None:
        _section(self.root, "05_hipotesis", self.TEXT)
        _, findings = _run(self.root, "--final")
        self.assertNotIn("sgr-marca-trabajo", _codes(findings))


class Rubrica(RunCase):
    def test_a_chapter_outside_the_structure_is_an_error(self) -> None:
        _structure(self.root, [{"numero": 1, "titulo": "Uno", "archivos": []}])
        _convocatoria(self.root, {"rubrica": [{"id": "2.1", "puntos": 100, "capitulos": [1, 9]}]})
        code, findings = _run(self.root, *SGR)
        errors = _with(findings, "rubrica-capitulo-inexistente", "error")
        self.assertEqual(len(errors), 1, findings)
        self.assertIn("2.1", errors[0]["message"])
        self.assertIn("9", errors[0]["message"])
        self.assertEqual(code, 1)

    def test_existing_chapters_are_no_finding(self) -> None:
        _structure(self.root, [{"numero": 1, "titulo": "Uno", "archivos": []}])
        _convocatoria(self.root, {"rubrica": [{"id": "2.1", "puntos": 100, "capitulos": [1]}]})
        _, findings = _run(self.root, *SGR)
        self.assertNotIn("rubrica-capitulo-inexistente", _codes(findings))
        self.assertNotIn("rubrica-puntos", _codes(findings))

    def test_without_a_structure_the_chapters_are_not_checked(self) -> None:
        _convocatoria(self.root, {"rubrica": [{"id": "2.1", "puntos": 100, "capitulos": [9]}]})
        _, findings = _run(self.root, *SGR)
        self.assertNotIn("rubrica-capitulo-inexistente", _codes(findings))

    def test_points_that_do_not_add_up_to_100_are_reported_in_a_warning(self) -> None:
        _convocatoria(self.root, {"rubrica": [{"id": "1", "puntos": 60}, {"id": "2", "puntos": 25.5}]})
        code, findings = _run(self.root, *SGR)
        warnings = _with(findings, "rubrica-puntos", "warning")
        self.assertEqual(len(warnings), 1, findings)
        self.assertIn("85.5", warnings[0]["message"])
        self.assertEqual(code, 0)

    def test_the_base_flow_ignores_the_rubric(self) -> None:
        _structure(self.root, [{"numero": 1, "titulo": "Uno", "archivos": ["02_justificacion"]}])
        _convocatoria(self.root, {"rubrica": [{"id": "1", "puntos": 7, "capitulos": [9]}]})
        _, findings = _run(self.root)
        self.assertNotIn("rubrica-capitulo-inexistente", _codes(findings))
        self.assertNotIn("rubrica-puntos", _codes(findings))


class Guide(unittest.TestCase):
    def setUp(self) -> None:
        self.text = GUIDE.read_text(encoding="utf-8")
        self.blocks = parse_sgr_blocks(self.text)

    def test_the_block_convention_survives(self) -> None:
        for key in ("§2", "§3", "§6", "§7", "§10", "§11", "§12", "§13", "§14", "§15", "§17", "§18",
                    "A19", "A20", "A21", "A22", "A23", "A24", "A25"):
            self.assertIn(key, self.blocks)

    def test_the_style_block_lists_the_writing_rules(self) -> None:
        start = self.text.index("## Estilo de redacción SGR\n")
        style = self.text[start:self.text.index("\n## ", start + 1)]
        for rule in ("Tercera persona impersonal", "Infinitivo, objeto y propósito", "Nombre: definición",
                     "medio de verificación", "uno o dos párrafos", "Regla de decisión", "Si no se cumple",
                     "plan B", "escenarios condicionados"):
            self.assertIn(rule, style)

    def test_the_new_blocks_land_in_the_section_they_feed(self) -> None:
        self.assertIn("Sostenibilidad", self.blocks["§18"])
        self.assertIn("indicador de gestión", self.blocks["§11"])
        self.assertIn("Licencias y permisos", self.blocks["§12"])
        self.assertIn("Resumen de fuentes de financiación", self.blocks["§13"])
        self.assertIn("Poder-Interés", self.blocks["A20"])
        self.assertIn("Evaluación MGA", self.blocks["A23"])
        self.assertIn("RPC", self.blocks["A23"])
        self.assertIn("9 %", self.blocks["A23"])

    def test_the_call_fixes_the_number_of_objectives_and_chapters(self) -> None:
        self.assertIn("artefactos/convocatoria.json", self.blocks["§3"])
        self.assertIn("objetivos_especificos", self.text)
        start = self.text.index("## Reglas de la convocatoria")
        section = self.text[start:self.text.index("\n## ", start + 1)]
        example = section[section.index("```json") + 7:section.index("```", section.index("```json") + 7)]
        data = json.loads(example)
        self.assertEqual(sum(item["puntos"] for item in data["rubrica"]), 100)
        self.assertIn("estructura_tdr.json", section)

    def test_the_annexes_name_their_phase(self) -> None:
        self.assertIn("Fase 6.3", self.text)
        self.assertNotIn("`### SGR A25` se inyectan en la Fase 6.47", self.text)

    def test_no_em_dash_in_the_guide(self) -> None:
        self.assertNotIn("—", self.text)


if __name__ == "__main__":
    unittest.main()
