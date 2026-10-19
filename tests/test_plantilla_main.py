"""The LaTeX skeleton carries a canonical main.tex that compiles from day one.

There was no plantilla/main.tex: the preamble rules (AGENTS.md rules 4, 5, 6 and
8) lived only as prose for the Fase 7 assembler, so a fresh run could not
compile and each gate rewrote main.tex by hand. The UTP logo is not part of
every proposal, so it is optional: present in the run's logos/ or absent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAIN = REPO / "plantilla" / "main.tex"
INIT_RUN = REPO / "scripts" / "init-run.sh"
HAS_TEX = shutil.which("latexmk") is not None and shutil.which("pdflatex") is not None


def _make_run(root: Path, run_id: str = "2026-01-plantilla") -> Path:
    """Run init-run.sh inside a throwaway copy of the framework skeleton."""
    for rel in ("plantilla", "scripts"):
        shutil.copytree(REPO / rel, root / rel, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    result = subprocess.run(["bash", "scripts/init-run.sh", run_id, "idea"], cwd=root,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    return root / "proposals" / run_id


class TemplateContentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(MAIN.is_file(), "plantilla/main.tex is missing")
        self.tex = MAIN.read_text(encoding="utf-8")

    def test_preamble_follows_the_document_invariants(self) -> None:
        for needle in (
            r"\documentclass[11pt,a4paper]{article}",
            r"\usepackage{xltabular}",
            r"\usepackage[round,authoryear]{natbib}",
            r"\sectionfont{\large\bfseries}",
            r"\subsectionfont{\normalsize\bfseries}",
            r"\subsubsectionfont{\normalsize\bfseries}",
            r"\setcounter{section}{1}",
            r"\fancyhead[R]{\includegraphics[height=1.1cm]{logos/logo_unal.png}}",
            r"\fancyfoot[L]{\includegraphics[height=1.0cm]{logos/logogcpds.png}}",
            r"\fancyfoot[R]{\includegraphics[height=1.0cm]{logos/logo_labIA.png}}",
            r"\IfFileExists{logos/logo_utp.png}",
        ):
            self.assertIn(needle, self.tex)

    def test_body_has_no_numbered_title_section(self) -> None:
        self.assertNotIn("01_titulo", self.tex)

    def test_every_canonical_section_is_wired_in_order(self) -> None:
        order = [
            "00_frontmatter", "02_justificacion", "03_descripcion_problema", "04_estado_arte",
            "05_hipotesis", "06_objetivo_general", "07_objetivos_especificos", "08_marco_conceptual",
            "09_equipo_trabajo", "10_metodologia", "11_resultados_esperados",
            "12_consideraciones_eticas", "13_presupuesto", "14_cronograma_actividades",
            "15_productos_esperados", "17_articulacion_comunidades", "18_apropiacion_social",
            "16_bibliografia",
        ]
        positions = [self.tex.find("\\SeccionSiExiste{" + name + "}") for name in order]
        self.assertNotIn(-1, positions, dict(zip(order, positions)))
        self.assertEqual(positions, sorted(positions), "sections are out of the canonical order")


class TemplateInRunTest(unittest.TestCase):
    def test_init_run_seeds_main_tex_without_the_optional_logo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _make_run(Path(tmp))
            red = run / "redaccion"
            self.assertTrue((red / "main.tex").is_file())
            self.assertTrue((red / "datos_proyecto.tex").is_file())
            self.assertFalse((red / "logos" / "logo_utp.png").exists(), "UTP logo must be opt-in")
            self.assertTrue((REPO / "plantilla" / "logos-opcionales" / "logo_utp.png").is_file())

    def test_init_run_never_overwrites_an_assembled_main_tex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _make_run(Path(tmp))
            (run / "redaccion" / "main.tex").write_text("% edited\n")
            subprocess.run(["bash", "scripts/init-run.sh", run.name, "idea"], cwd=tmp, check=True,
                           capture_output=True)
            self.assertEqual((run / "redaccion" / "main.tex").read_text(), "% edited\n")


@unittest.skipUnless(HAS_TEX, "latexmk/pdflatex not installed")
class TemplateCompilesTest(unittest.TestCase):
    def _build(self, red: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ, SKIP_DOI_REPAIR="1")
        return subprocess.run(["bash", "build.sh"], cwd=red, capture_output=True, text=True,
                              env=env, input="s\n", timeout=240)

    def test_fresh_run_compiles_with_and_without_the_utp_logo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _make_run(Path(tmp))
            red = run / "redaccion"
            (red / "sections" / "02_justificacion.tex").write_text(
                "\\section{Justificación y pertinencia}\nTexto de prueba \\citep{demo2024}.\n")
            (red / "refs.bib").write_text(
                "@article{demo2024, author={Demo, Ana}, title={Prueba}, journal={J}, year={2024}}\n")
            (red / "sections" / "16_bibliografia.tex").write_text(
                "\\clearpage\n\\section{Bibliografía}\n\\renewcommand{\\bibsection}{}\n"
                "\\bibliographystyle{apalike}\n\\bibliography{refs}\n")

            first = self._build(red)
            self.assertTrue((red / "main.pdf").is_file(), first.stdout[-2000:] + first.stderr[-2000:])

            shutil.copyfile(REPO / "plantilla" / "logos-opcionales" / "logo_utp.png", red / "logos" / "logo_utp.png")
            (red / "main.pdf").unlink()
            second = self._build(red)
            self.assertTrue((red / "main.pdf").is_file(), second.stdout[-2000:] + second.stderr[-2000:])

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext not installed")
    def test_a_rebuild_picks_up_a_section_added_after_the_first_compile(self) -> None:
        # \IfFileExists hides files that did not exist at the last compile from
        # latexmk's dependency list; without a forced run the PDF stays stale.
        with tempfile.TemporaryDirectory() as tmp:
            red = _make_run(Path(tmp)) / "redaccion"
            self._build(red)
            self.assertTrue((red / "main.pdf").is_file(), "the first build produced no PDF")
            (red / "sections" / "05_hipotesis.tex").write_text("\\section{Hipótesis}\nTextoNuevoDePrueba.\n")
            self._build(red)
            text = subprocess.run(["pdftotext", str(red / "main.pdf"), "-"], capture_output=True, text=True).stdout
            self.assertIn("TextoNuevoDePrueba", text, "the PDF is stale after adding a section")


if __name__ == "__main__":
    unittest.main()
