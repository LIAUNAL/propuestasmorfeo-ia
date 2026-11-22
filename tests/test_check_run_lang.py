"""scripts/check_run.py follows the run's writing language (S3).

The language comes from the run (`_run.md` row `| idioma | en |`, else the
project config) and `--lang` overrides it. Spanish runs keep their exact output;
English runs get the English wording of the language rules: TRL message,
cover placeholder, table name in the PDF and the problem and objective tree
rules (absence of a solution, infinitive objectives, means and ends in the
general objective, negative qualifiers, the shared variable).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_check_run import _cites, _clean_run, _codes, _keys, _run_json

REPO = Path(__file__).resolve().parent.parent


def _load_check_run():
    spec = importlib.util.spec_from_file_location("check_run_lang_test", REPO / "scripts" / "check_run.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _english(root: Path) -> Path:
    for marker in (".morfeo", ".marco"):
        (root / marker).mkdir(exist_ok=True)
        (root / marker / "config.json").write_text('{"lang": "en", "flujo": "base"}', encoding="utf-8")
    return root


def _english_run(root: Path) -> Path:
    run = _clean_run(_english(root))
    s = run / "redaccion" / "sections"
    (s / "02_justificacion.tex").write_text(
        "\\section{Rationale}\nIt reaches TRL 6 in the field. " + " ".join(
            f"Fact \\citep{{{k}}}." for k in _keys("j", 13)) + "\n")
    (s / "06_objetivo_general.tex").write_text("\\section{General objective}\nTo develop a system.\n")
    (s / "11_resultados_esperados.tex").write_text(
        "\\section{Expected results}\nPrototype at TRL 7. " + _cites(_keys("r", 13)) + "\n")
    return run


PROBLEM = {
    "trunk": {"text": "Low adoption of irrigation scheduling among smallholders",
              "magnitude": {"indicador": "share", "valor": "12%", "fuente": "census"}},
    "crown": {"text": "Lower farm income"},
    "groups": [{"id": "CD1", "title": "Limited access to soil moisture data",
                "causes": [{"id": "C1", "text": "Few sensors installed in the region"}]}],
    "branches": [{"id": "E1", "text": "Water waste in dry seasons"}],
}
OBJECTIVES = {
    "trunk": {"text": "To increase the adoption of irrigation scheduling among smallholders"},
    "crown": {"text": "To raise farm income"},
    "groups": [{"id": "OE1", "title": "OE1", "from": "CD1", "objective": "To expand access to soil moisture data",
                "means": [{"id": "M1", "from": "C1", "text": "Install sensors in the region"}]}],
    "branches": [{"id": "F1", "from": "E1", "text": "Reduce water waste in dry seasons"}],
}


class LanguageDetectionTest(unittest.TestCase):
    def test_an_english_run_reports_its_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, data = _run_json(_english_run(Path(tmp)))
            self.assertEqual(data["lang"], "en")
            self.assertEqual(_codes(data["findings"], "error"), set(), data["findings"])
            self.assertEqual(code, 0)

    def test_a_spanish_run_keeps_its_previous_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, data = _run_json(_clean_run(Path(tmp)))
            self.assertEqual(set(data), {"flujo", "findings"})

    def test_the_run_row_wins_over_the_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _clean_run(_english(Path(tmp)))
            (root / "_run.md").write_text("| flujo | base |\n", encoding="utf-8")
            _, data = _run_json(root)
            self.assertNotIn("lang", data)

    def test_the_flag_overrides_the_detected_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, data = _run_json(_clean_run(Path(tmp)), "--lang", "en")
            self.assertEqual(data["lang"], "en")


class EnglishMessagesTest(unittest.TestCase):
    def test_missing_trl_names_the_english_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _english_run(Path(tmp))
            (run / "redaccion" / "sections" / "11_resultados_esperados.tex").write_text(
                "\\section{Expected results}\nNo level.\n")
            _, data = _run_json(run)
            message = next(f["message"] for f in data["findings"] if f["code"] == "trl-ausente")
            self.assertIn("TRL 6 or 7", message)

    def test_the_english_cover_placeholder_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _english_run(Path(tmp))
            (run / "redaccion" / "datos_proyecto.tex").write_text(
                "\\newcommand{\\TituloProyecto}{[To be defined: project title]}\n")
            _, data = _run_json(run, "--final")
            finding = next(f for f in data["findings"] if f["code"] == "portada-sin-completar")
            self.assertIn("[To be defined", finding["message"])

    def test_the_spanish_cover_placeholder_keeps_its_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _clean_run(Path(tmp))
            (run / "redaccion" / "datos_proyecto.tex").write_text(
                "\\newcommand{\\TituloProyecto}{[Por definir: título]}\n")
            _, data = _run_json(run, "--final")
            finding = next(f for f in data["findings"] if f["code"] == "portada-sin-completar")
            self.assertEqual(finding["message"], "datos_proyecto.tex conserva campos [Por definir: ...].")


class TableNameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.m = _load_check_run()

    def test_spanish_flags_cuadro(self) -> None:
        self.assertEqual(self.m.pdf_table_name_problem("Cuadro 2: datos", "es"), "Cuadro 2")
        self.assertIsNone(self.m.pdf_table_name_problem("Tabla 2: datos", "es"))

    def test_english_flags_spanish_names(self) -> None:
        for text, found in (("Tabla 2: data", "Tabla 2"), ("Cuadro 1", "Cuadro 1"), ("Figura 3", "Figura 3")):
            self.assertEqual(self.m.pdf_table_name_problem(text, "en"), found)
        self.assertIsNone(self.m.pdf_table_name_problem("Table 2 and Figure 3", "en"))


class EnglishTreeRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.m = _load_check_run()

    def problem_codes(self, **changes) -> set:
        spec = json.loads(json.dumps(PROBLEM))
        for path, value in changes.items():
            node, key = path.split("__")
            target = spec[node] if node in ("trunk", "crown") else spec[node][0]
            target[key] = value
        return {f["code"] for f in self.m.problem_tree_findings(spec, "en")}

    def objective_codes(self, objectives: dict) -> set:
        return {f["code"] for f in self.m.objective_tree_findings(objectives, PROBLEM, "en")}

    def test_a_clean_english_tree_has_no_error(self) -> None:
        errors = {f["code"] for f in self.m.problem_tree_findings(PROBLEM, "en") if f["severity"] == "error"}
        errors |= {f["code"] for f in self.m.objective_tree_findings(OBJECTIVES, PROBLEM, "en")
                   if f["severity"] == "error"}
        self.assertEqual(errors, set())

    def test_absence_of_a_solution_is_an_error(self) -> None:
        for text in ("Lack of irrigation sensors", "There are no soil moisture data", "Need for training"):
            with self.subTest(text=text):
                self.assertIn("arbol-ausencia-de-solucion", self.problem_codes(groups__title=text))

    def test_a_solution_in_the_problem_tree_is_an_error(self) -> None:
        for text in ("To develop a platform", "Develop a platform"):
            with self.subTest(text=text):
                self.assertIn("arbol-solucion-en-problema", self.problem_codes(groups__title=text))
        self.assertNotIn("arbol-solucion-en-problema", self.problem_codes(groups__title="Increase in pest outbreaks"))

    def test_the_central_problem_opens_with_a_negative_qualifier(self) -> None:
        self.assertIn("arbol-problema-sin-calificativo-negativo",
                      self.problem_codes(trunk__text="Adoption of irrigation scheduling among smallholders"))
        self.assertNotIn("arbol-problema-sin-calificativo-negativo",
                         self.problem_codes(trunk__text="Insufficient adoption of irrigation scheduling"))

    def test_objectives_start_with_a_verb(self) -> None:
        objectives = json.loads(json.dumps(OBJECTIVES))
        objectives["groups"][0]["objective"] = "Access to soil moisture data"
        self.assertIn("arbol-objetivos-no-infinitivo", self.objective_codes(objectives))

    def test_the_general_objective_carries_no_means_end_or_target(self) -> None:
        for text, code in (
            ("To increase the adoption of irrigation scheduling among smallholders by means of sensors",
             "objetivo-general-con-medio"),
            ("To increase the adoption of irrigation scheduling among smallholders through sensors",
             "objetivo-general-con-medio"),
            ("To increase the adoption of irrigation scheduling among smallholders in order to improve income",
             "objetivo-general-con-fin"),
            ("To increase the adoption of irrigation scheduling among smallholders to improve income",
             "objetivo-general-con-fin"),
            ("To increase by 20% the adoption of irrigation scheduling among smallholders", "objetivo-general-con-meta"),
        ):
            with self.subTest(code=code, text=text):
                objectives = json.loads(json.dumps(OBJECTIVES))
                objectives["trunk"]["text"] = text
                self.assertIn(code, self.objective_codes(objectives))

    def test_a_changed_variable_is_reported(self) -> None:
        objectives = json.loads(json.dumps(OBJECTIVES))
        objectives["trunk"]["text"] = "To strengthen tourism in coastal towns"
        self.assertIn("arbol-variable-cambiada", self.objective_codes(objectives))

    def test_english_messages_quote_english_examples(self) -> None:
        objectives = json.loads(json.dumps(OBJECTIVES))
        objectives["trunk"]["text"] = "To increase adoption among smallholders by means of sensors"
        message = next(f["message"] for f in self.m.objective_tree_findings(objectives, PROBLEM, "en")
                       if f["code"] == "objetivo-general-con-medio")
        self.assertIn("by means of", message)

    def test_spanish_stays_the_default(self) -> None:
        spec = {"trunk": {"text": "Bajo nivel de adopción"}, "branches": [{"id": "E1", "text": "Pérdidas"}],
                "crown": {"text": "Menor ingreso"}, "groups": [{"id": "CD1", "title": "Falta de sensores",
                                                                "causes": [{"id": "C1", "text": "Pocos equipos"}]}]}
        self.assertEqual(self.m.problem_tree_findings(spec), self.m.problem_tree_findings(spec, "es"))
        self.assertIn("arbol-ausencia-de-solucion", {f["code"] for f in self.m.problem_tree_findings(spec)})


if __name__ == "__main__":
    unittest.main()
