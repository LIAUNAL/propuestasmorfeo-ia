"""Reglas de la guía SGR (MGA del DNP) para los árboles de problemas y objetivos.

Las funciones viven en scripts/check_run.py (solo biblioteca estándar) para que
el verificador de la corrida y el tablero apliquen exactamente las mismas reglas.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_run  # noqa: E402

RESIDUOS_PROBLEMA = "Bajo aprovechamiento de los residuos sólidos domiciliarios de la zona urbana de X"
RESIDUOS_OBJETIVO = "Aumentar el aprovechamiento de los residuos sólidos domiciliarios de la zona urbana del Municipio X"

PROBLEM = {
    "kind": "arbol",
    "caption": "Árbol de problemas.",
    "groups": [
        {"id": "SP1", "title": "SP1 · Baja separación de los residuos en la fuente",
         "causes": [{"id": "r1", "text": "Escaso conocimiento de los hogares sobre la separación"},
                    {"id": "r2", "text": "Pocos recipientes diferenciados en las viviendas"}]},
        {"id": "SP2", "title": "SP2 · Deficiente recolección selectiva de residuos",
         "causes": [{"id": "r3", "text": "Rutas de recolección selectiva incompletas"}]},
    ],
    "trunk": {"label": "PROBLEMA CENTRAL", "text": RESIDUOS_PROBLEMA,
              "magnitude": {"indicador": "Porcentaje de residuos aprovechados", "valor": "8 %", "fuente": "SUI 2024"}},
    "branches": [{"id": "b1", "text": "Mayor volumen de residuos dispuestos en el relleno"}],
    "crown": {"label": "EFECTO FINAL", "text": "Deterioro ambiental de la zona urbana"},
}

OBJECTIVES = {
    "groups": [
        {"id": "OE1", "from": "SP1", "title": "OE1", "objective": "Aumentar la separación de los residuos en la fuente",
         "means": [{"id": "m1", "from": "r1", "text": "Fortalecer el conocimiento de los hogares sobre la separación"},
                   {"id": "m2", "from": "r2", "text": "Dotar las viviendas de recipientes diferenciados"}]},
        {"id": "OE2", "from": "SP2", "title": "OE2", "objective": "Mejorar la recolección selectiva de residuos",
         "means": [{"id": "m3", "from": "r3", "text": "Completar las rutas de recolección selectiva"}]},
    ],
    "trunk": {"label": "OBJETIVO GENERAL", "text": RESIDUOS_OBJETIVO},
    "branches": [{"id": "f1", "from": "b1", "text": "Reducir el volumen de residuos dispuestos en el relleno"}],
    "crown": {"label": "FIN ÚLTIMO", "text": "Mejorar la calidad ambiental de la zona urbana"},
}


def codes(findings: list[dict], severity: str | None = None) -> set[str]:
    return {f["code"] for f in findings if severity is None or f["severity"] == severity}


def nodes(findings: list[dict], code: str) -> set[str]:
    return {f["node"] for f in findings if f["code"] == code}


def problem(**changes) -> dict:
    spec = copy.deepcopy(PROBLEM)
    spec.update(changes)
    return spec


def objectives(**changes) -> dict:
    tree = copy.deepcopy(OBJECTIVES)
    tree.update(changes)
    return tree


class ProblemTreeRulesTest(unittest.TestCase):
    def test_adjectives_ending_like_an_infinitive_are_not_solutions(self) -> None:
        for text in ("Irregular acceso al agua potable en Caldas", "Malestar social en la zona rural",
                     "Insular aislamiento de los productores"):
            spec = problem(trunk={"label": "PROBLEMA CENTRAL", "text": text})
            codes = {f["code"] for f in check_run.problem_tree_findings(spec)}
            self.assertNotIn("arbol-solucion-en-problema", codes, text)

    def test_a_well_formed_problem_tree_has_no_findings(self) -> None:
        self.assertEqual(check_run.problem_tree_findings(PROBLEM), [])

    def test_findings_have_the_documented_shape(self) -> None:
        spec = problem(trunk={"label": "PROBLEMA CENTRAL", "text": "Falta de un sistema de reciclaje"})
        finding = next(f for f in check_run.problem_tree_findings(spec) if f["code"] == "arbol-ausencia-de-solucion")
        self.assertEqual(set(finding), {"severity", "code", "node", "message"})
        self.assertEqual(finding["severity"], "error")
        self.assertEqual(finding["node"], "trunk")
        self.assertIn("estado existente negativo", finding["message"])

    def test_absence_of_the_solution_is_an_error_in_any_node(self) -> None:
        spec = problem()
        spec["trunk"]["text"] = "Ausencia de una plataforma de monitoreo"
        spec["groups"][0]["title"] = "SP1 · No existen campañas de separación"
        spec["groups"][0]["causes"][0]["text"] = "Carencia de recipientes"
        spec["groups"][1]["causes"][0]["text"] = "Se requiere una nueva ruta"
        spec["branches"][0]["text"] = "Necesidad de\\nampliar el relleno"
        spec["crown"]["text"] = "No hay inexistencia de datos"
        found = nodes(check_run.problem_tree_findings(spec), "arbol-ausencia-de-solucion")
        self.assertEqual(found, {"trunk", "SP1", "r1", "r3", "b1", "crown"})

    def test_a_solution_written_as_an_infinitive_is_an_error(self) -> None:
        spec = problem()
        spec["groups"][1]["causes"][0]["text"] = "Implementar rutas de recolección"
        spec["crown"]["text"] = "Desarrollar un sistema de IA"
        findings = check_run.problem_tree_findings(spec)
        self.assertEqual(nodes(findings, "arbol-solucion-en-problema"), {"r3", "crown"})
        self.assertIn("árbol de objetivos", next(f["message"] for f in findings if f["code"] == "arbol-solucion-en-problema"))

    def test_nouns_ending_like_infinitives_are_not_solutions(self) -> None:
        spec = problem()
        spec["groups"][0]["causes"][0]["text"] = "Hogar sin recipientes diferenciados"
        spec["groups"][0]["causes"][1]["text"] = "Lugar de acopio insuficiente"
        spec["branches"][0]["text"] = "Poder adquisitivo reducido de las familias"
        self.assertNotIn("arbol-solucion-en-problema", codes(check_run.problem_tree_findings(spec)))

    def test_a_central_problem_without_magnitude_is_a_warning(self) -> None:
        for trunk in ({"label": "PROBLEMA CENTRAL", "text": RESIDUOS_PROBLEMA},
                      {"label": "PROBLEMA CENTRAL", "text": RESIDUOS_PROBLEMA,
                       "magnitude": {"indicador": "Porcentaje", "valor": "8 %", "fuente": ""}}):
            findings = check_run.problem_tree_findings(problem(trunk=trunk))
            self.assertIn("arbol-sin-magnitud", codes(findings, "warning"))

    def test_a_tree_without_effects_is_an_error(self) -> None:
        self.assertIn("arbol-sin-efectos", codes(check_run.problem_tree_findings(problem(branches=[])), "error"))

    def test_a_direct_cause_without_indirect_causes_is_a_warning(self) -> None:
        spec = problem()
        spec["groups"][1]["causes"] = []
        findings = check_run.problem_tree_findings(spec)
        self.assertEqual(nodes(findings, "arbol-causa-directa-sin-indirectas"), {"SP2"})
        self.assertIn("arbol-causa-directa-sin-indirectas", codes(findings, "warning"))

    def test_an_empty_crown_is_a_warning(self) -> None:
        findings = check_run.problem_tree_findings(problem(crown={"label": "EFECTO FINAL", "text": ""}))
        self.assertIn("arbol-sin-efecto-final", codes(findings, "warning"))


class ObjectiveTreeRulesTest(unittest.TestCase):
    def test_a_correct_mirror_has_no_findings(self) -> None:
        self.assertEqual(check_run.objective_tree_findings(OBJECTIVES, PROBLEM), [])

    def test_every_positive_text_starts_with_an_infinitive(self) -> None:
        tree = objectives()
        tree["groups"][0]["means"][1]["text"] = "Recipientes diferenciados en las viviendas"
        tree["branches"][0]["text"] = "Menor volumen de residuos dispuestos en el relleno"
        tree["crown"]["text"] = "Calidad ambiental de la zona urbana"
        found = nodes(check_run.objective_tree_findings(tree, PROBLEM), "arbol-objetivos-no-infinitivo")
        self.assertEqual(found, {"m2", "f1", "crown"})

    def test_empty_texts_are_not_findings(self) -> None:
        tree = objectives()
        tree["trunk"]["text"] = None
        tree["crown"]["text"] = ""
        tree["groups"][0]["means"][0]["text"] = None
        self.assertEqual(check_run.objective_tree_findings(tree, PROBLEM), [])

    def test_the_general_objective_does_not_name_the_means(self) -> None:
        for suffix in (" mediante un sistema de IA", " a través de sensores", " por medio de una app",
                       " por intermedio de la alcaldía"):
            tree = objectives(trunk={"label": "OBJETIVO GENERAL", "text": RESIDUOS_OBJETIVO + suffix})
            self.assertIn("objetivo-general-con-medio", codes(check_run.objective_tree_findings(tree, PROBLEM), "error"), suffix)

    def test_the_general_objective_does_not_name_the_ends(self) -> None:
        for suffix in (" para mejorar la calidad de vida", " con el fin de reducir costos", " con el propósito de cumplir"):
            tree = objectives(trunk={"label": "OBJETIVO GENERAL", "text": RESIDUOS_OBJETIVO + suffix})
            self.assertIn("objetivo-general-con-fin", codes(check_run.objective_tree_findings(tree, PROBLEM), "error"), suffix)

    def test_the_general_objective_does_not_carry_targets(self) -> None:
        tree = objectives(trunk={"label": "OBJETIVO GENERAL", "text": RESIDUOS_OBJETIVO + " en un 30 %"})
        self.assertIn("objetivo-general-con-meta", codes(check_run.objective_tree_findings(tree, PROBLEM), "error"))

    def test_a_broken_mirror_is_an_error(self) -> None:
        cases = []
        tree = objectives()
        tree["groups"] = tree["groups"][:1]
        cases.append(tree)
        tree = objectives()
        tree["groups"][0]["means"] = tree["groups"][0]["means"][:1]
        cases.append(tree)
        cases.append(objectives(branches=[]))
        tree = objectives()
        tree["groups"][1]["means"][0]["from"] = "r99"
        cases.append(tree)
        for tree in cases:
            self.assertIn("arbol-espejo-roto", codes(check_run.objective_tree_findings(tree, PROBLEM), "error"))

    def test_a_changed_variable_is_an_error_in_the_trunk_and_a_warning_in_a_group(self) -> None:
        spec = problem(trunk={"label": "PROBLEMA CENTRAL", "text": "Altos niveles de deserción educativa en la zona rural",
                              "magnitude": PROBLEM["trunk"]["magnitude"]})
        tree = objectives(trunk={"label": "OBJETIVO GENERAL", "text": "Garantizar la cobertura escolar en la zona rural"})
        tree["groups"][1]["objective"] = "Construir nuevas aulas digitales"
        findings = check_run.objective_tree_findings(tree, spec)
        trunk = [f for f in findings if f["code"] == "arbol-variable-cambiada" and f["node"] == "trunk"]
        group = [f for f in findings if f["code"] == "arbol-variable-cambiada" and f["node"] == "OE2"]
        self.assertEqual([f["severity"] for f in trunk], ["error"])
        self.assertEqual([f["severity"] for f in group], ["warning"])


class SharedVariableTest(unittest.TestCase):
    def test_the_dts_mistake_changes_the_variable(self) -> None:
        ratio = check_run.shared_variable("Altos niveles de deserción educativa en la zona rural",
                                          "Garantizar la cobertura escolar en la zona rural")
        self.assertLess(ratio, 0.5)

    def test_the_mga_example_keeps_the_variable(self) -> None:
        self.assertGreaterEqual(check_run.shared_variable(RESIDUOS_PROBLEMA, RESIDUOS_OBJETIVO), 0.5)

    def test_accents_and_latex_do_not_change_the_ratio(self) -> None:
        self.assertEqual(check_run.shared_variable("Bajo aprovechamiento de residuos sólidos",
                                                   "Aumentar el \\textbf{aprovechamiento} de residuos solidos"), 1.0)


class DetectFlujoTest(unittest.TestCase):
    def _config(self, root: Path, folder: str, data) -> None:
        (root / folder).mkdir(parents=True, exist_ok=True)
        text = data if isinstance(data, str) else json.dumps(data)
        (root / folder / "config.json").write_text(text, encoding="utf-8")

    def test_without_config_the_flow_is_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(check_run.detect_flujo(Path(tmp)), "base")

    def test_the_flow_is_read_from_an_ancestor_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "proposals" / "r1"
            run.mkdir(parents=True)
            self._config(root, ".marco", {"flujo": "sgr"})
            self.assertEqual(check_run.detect_flujo(run), "sgr")

    def test_morfeo_wins_over_marco(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config(root, ".morfeo", {"flujo": "base"})
            self._config(root, ".marco", {"flujo": "sgr"})
            self.assertEqual(check_run.detect_flujo(root), "base")
            self._config(root, ".morfeo", {"flujo": "sgr"})
            self._config(root, ".marco", {"flujo": "base"})
            self.assertEqual(check_run.detect_flujo(root), "sgr")

    def test_an_invalid_value_is_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._config(root, ".morfeo", {"flujo": "regalias"})
            self.assertEqual(check_run.detect_flujo(root), "base")
            self._config(root, ".morfeo", "{no es json")
            self.assertEqual(check_run.detect_flujo(root), "base")


if __name__ == "__main__":
    unittest.main()
