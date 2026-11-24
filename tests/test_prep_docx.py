"""plantilla/scripts/prep_docx.py names cross-references in the run's language (S3).

Pandoc does not know cleveref, so prep_docx rewrites `\\cref{fig:x}` into
`<noun>~\\ref{fig:x}` before the conversion. The noun follows the babel
language of main.tex: Spanish nouns for a Spanish run (unchanged), English
nouns for a run created in English.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "plantilla" / "scripts" / "prep_docx.py"


def _load():
    spec = importlib.util.spec_from_file_location("prep_docx_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CrefNounTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.m = _load()

    TEXT = r"See \Cref{fig:a}, \cref{tab:b} and \cref{sec:c}."

    def test_spanish_nouns_stay_the_default(self) -> None:
        self.assertEqual(self.m.resolve_cref(self.TEXT),
                         r"See Figura~\ref{fig:a}, tabla~\ref{tab:b} and sección~\ref{sec:c}.")
        self.assertEqual(self.m.resolve_cref(self.TEXT, "es"), self.m.resolve_cref(self.TEXT))

    def test_english_nouns(self) -> None:
        self.assertEqual(self.m.resolve_cref(self.TEXT, "en"),
                         r"See Figure~\ref{fig:a}, table~\ref{tab:b} and section~\ref{sec:c}.")

    def test_the_language_comes_from_babel(self) -> None:
        self.assertEqual(self.m.document_language(r"\usepackage[english]{babel}"), "en")
        self.assertEqual(self.m.document_language(r"\usepackage[spanish,es-noindentfirst]{babel}"), "es")
        self.assertEqual(self.m.document_language(r"% \usepackage[english]{babel}" "\n"), "es")
        self.assertEqual(self.m.document_language(""), "es")


if __name__ == "__main__":
    unittest.main()
