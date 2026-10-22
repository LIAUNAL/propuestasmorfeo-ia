"""Objective-tree figure: audit counts and MGA level labels (odd/tasks/sgr-arboles-redaccion.md, S2-S3).

`scripts/arbol_objetivos.py` keeps the panel ids (means `m<n>`, ends `f<n>`) in the
`kind: arbol` spec. The audit must count them like the problem tree's `r<n>`/`b<n>`,
and the renderer must print the MGA objective levels on the side, not the
problem-tree ones.
"""

from __future__ import annotations

import copy
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RENDER = _load(REPO / "plantilla" / "scripts" / "render_tikz.py", "render_tikz_obj_under_test")
AUDIT = _load(REPO / "plantilla" / "scripts" / "audit_tikz.py", "audit_tikz_obj_under_test")
CONVERT = _load(REPO / "scripts" / "arbol_objetivos.py", "arbol_objetivos_under_test")

PROBLEM_SPEC = {
    "kind": "arbol",
    "header": "ÁRBOL DE PROBLEMAS",
    "caption": "Árbol de problemas de prueba.",
    "groups": [
        {"id": "SP1", "title": "Insuficiente información sobre la salud mental",
         "causes": [{"id": "r1", "text": "Escaso registro de casos"}, {"id": "r2", "text": "Pocos tamizajes"}]},
        {"id": "SP2", "title": "Limitada capacidad de atención",
         "causes": [{"id": "r3", "text": "Pocos profesionales disponibles"}]},
    ],
    "trunk": {"label": "PROBLEMA CENTRAL", "text": "Alta prevalencia de estrés postraumático en estudiantes"},
    "branches": [{"id": "b1", "text": "Mayor deserción escolar"}, {"id": "b2", "text": "Bajo rendimiento académico"}],
    "crown": {"label": "EFECTO FINAL", "text": "Deterioro del bienestar de la comunidad educativa"},
}

OBJECTIVE_TREE = {
    "groups": [
        {"id": "OE1", "from": "SP1", "title": "OE1", "objective": "Aumentar la información sobre la salud mental",
         "means": [{"id": "m1", "from": "r1", "text": "Ampliar el registro de casos"},
                   {"id": "m2", "from": "r2", "text": "Aumentar los tamizajes"}]},
        {"id": "OE2", "from": "SP2", "title": "OE2", "objective": "Fortalecer la capacidad de atención",
         "means": [{"id": "m3", "from": "r3", "text": "Ampliar los profesionales disponibles"}]},
    ],
    "trunk": {"label": "OBJETIVO GENERAL", "text": "Reducir la prevalencia de estrés postraumático en estudiantes"},
    "branches": [{"id": "f1", "from": "b1", "text": "Reducir la deserción escolar"},
                 {"id": "f2", "from": "b2", "text": "Mejorar el rendimiento académico"}],
    "crown": {"label": "FIN ÚLTIMO", "text": "Mejorar el bienestar de la comunidad educativa"},
}

TREE_CHECKS = ("block_counts", "every_branch_reaches_crown", "crown_never_touches_roots")


def objective_spec() -> dict:
    return CONVERT.to_spec(copy.deepcopy(OBJECTIVE_TREE), PROBLEM_SPEC)


def level_labels(tex: str) -> list[str]:
    return [line for line in tex.splitlines() if line.startswith(r"\node[nivel")]


class _Audit(unittest.TestCase):
    def setUp(self) -> None:
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project)
        (self.project / "sections" / "figuras").mkdir(parents=True)

    def audit_checks(self, name: str, spec: dict) -> dict[str, dict]:
        tex, _ = RENDER.render(spec, {})
        (self.project / "sections" / f"diag_{name}.tex").write_text(tex, encoding="utf-8")
        result = AUDIT.audit(name, self.project, spec, f"OVERFULL: {name} 0 occurrence(s)")
        return {c["id"]: c for c in result["checks"]}


class ObjectiveTreeAuditTest(_Audit):
    def test_the_objective_tree_counts_means_and_ends(self) -> None:
        checks = self.audit_checks("arbol_objetivos", objective_spec())
        for check in TREE_CHECKS:
            self.assertTrue(checks[check]["ok"], f"{check}: {checks[check]['detail']}")

    def test_the_problem_tree_audit_still_passes(self) -> None:
        checks = self.audit_checks("arbol_problemas", copy.deepcopy(PROBLEM_SPEC))
        for check in TREE_CHECKS:
            self.assertTrue(checks[check]["ok"], f"{check}: {checks[check]['detail']}")

    def test_a_missing_mean_is_still_caught(self) -> None:
        spec = objective_spec()
        tex, _ = RENDER.render(spec, {})
        spec["groups"][0]["causes"].append({"id": "m9", "text": "Medio que no se dibujó"})
        (self.project / "sections" / "diag_arbol_objetivos.tex").write_text(tex, encoding="utf-8")
        checks = {c["id"]: c for c in AUDIT.audit("arbol_objetivos", self.project, spec,
                                                   "OVERFULL: arbol_objetivos 0 occurrence(s)")["checks"]}
        self.assertFalse(checks["block_counts"]["ok"])
        self.assertIn("causes: esperado 4, encontrado 3", checks["block_counts"]["detail"])

    def test_a_crown_wired_to_a_mean_is_caught(self) -> None:
        spec = objective_spec()
        tex, _ = RENDER.render(spec, {})
        tex = tex.replace(r"\end{tikzpicture}", "\\draw[flecha] (copa.south) -- (m1.north);\n\\end{tikzpicture}")
        (self.project / "sections" / "diag_arbol_objetivos.tex").write_text(tex, encoding="utf-8")
        checks = {c["id"]: c for c in AUDIT.audit("arbol_objetivos", self.project, spec,
                                                   "OVERFULL: arbol_objetivos 0 occurrence(s)")["checks"]}
        self.assertFalse(checks["crown_never_touches_roots"]["ok"])


class OverfullRoleTest(unittest.TestCase):
    def test_objective_ids_map_to_the_tree_roles(self) -> None:
        self.assertEqual(RENDER.role_for_node("m1"), "raiz")
        self.assertEqual(RENDER.role_for_node("f2", "arbol"), "rama")
        self.assertEqual(RENDER.role_for_node("f2"), "fase", "the methodology phases keep their role")
        self.assertEqual(RENDER.role_for_node("f2", "metodologico"), "fase")


class LevelLabelsTest(unittest.TestCase):
    def test_the_objective_tree_prints_the_mga_objective_levels(self) -> None:
        tex, _ = RENDER.render(objective_spec(), {})
        labels = "\n".join(level_labels(tex))
        for expected in (r"FIN\\ÚLTIMO", r"FINES\\DIRECTOS", r"OBJETIVO\\GENERAL", r"MEDIOS\\(RAÍCES)"):
            self.assertIn(expected, labels)
        for problem_label in ("PROBLEMA", "CAUSAS", "EFECTO"):
            self.assertNotIn(problem_label, labels)

    def test_the_problem_tree_keeps_its_labels(self) -> None:
        tex, _ = RENDER.render(copy.deepcopy(PROBLEM_SPEC), {})
        labels = "\n".join(level_labels(tex))
        for expected in (r"EFECTO\\FINAL", r"EFECTOS\\DIRECTOS", r"PROBLEMA\\CENTRAL", r"CAUSAS\\(RAÍCES)"):
            self.assertIn(expected, labels)


if __name__ == "__main__":
    unittest.main()
