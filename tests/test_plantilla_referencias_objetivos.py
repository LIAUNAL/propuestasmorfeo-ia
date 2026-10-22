"""plantilla/main.tex: árbol de objetivos tras §7 y referencias provisionales.

Antes de la Fase 6 no existe sections/16_bibliografia.tex y las citas de las
secciones ya redactadas salían como «?» en el PDF. La plantilla agrega una
lista provisional desde refs.bib, solo cuando hubo citas, y la figura del árbol
de objetivos del flujo SGR, una sola vez, tras §7.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PlantillaMainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tex = (ROOT / "plantilla" / "main.tex").read_text(encoding="utf-8")

    def test_objective_tree_follows_specific_objectives(self) -> None:
        sec = self.tex.index(r"\SeccionSiExiste{07_objetivos_especificos}")
        fig = self.tex.index(r"\DiagramaSiExiste{diag_arbol_objetivos}")
        self.assertLess(sec, fig)
        self.assertLess(fig, self.tex.index(r"\SeccionSiExiste{08_marco_conceptual}"))
        self.assertEqual(self.tex.count(r"\DiagramaSiExiste{diag_arbol_objetivos}"), 1)

    def test_provisional_bibliography_only_without_file_16_and_with_citations(self) -> None:
        self.assertIn(r"\def\citation#1{\global\@HayCitastrue}", self.tex)
        hook = self.tex[self.tex.index(r"\AtEndDocument"):]
        self.assertIn(r"\IfFileExists{sections/16_bibliografia.tex}{}", hook)
        self.assertIn(r"\if@HayCitas", hook)
        self.assertIn(r"\bibliographystyle{apalike}", hook)
        self.assertIn(r"\bibliography{refs}", hook)

    def test_file_16_is_still_the_final_bibliography(self) -> None:
        self.assertIn(r"\SeccionSiExiste{16_bibliografia}", self.tex)

    def test_kit_copy_matches(self) -> None:
        kit = (ROOT / "src" / "morfeo" / "_kit" / "plantilla" / "main.tex").read_text(encoding="utf-8")
        self.assertEqual(kit, self.tex)


if __name__ == "__main__":
    unittest.main()
