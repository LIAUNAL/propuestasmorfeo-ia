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

    def test_sgr_annexes_sit_between_section_18_and_the_bibliography(self) -> None:
        # Only SGR runs write these files; \SeccionSiExiste keeps them out of a base run.
        annexes = [
            "19_alineacion_planes", "20_participantes", "21_poblacion", "22_alternativas",
            "23_cadena_valor", "24_riesgos", "25_marco_logico",
        ]
        order = ["18_apropiacion_social", *annexes, "16_bibliografia"]
        positions = [self.tex.find("\\SeccionSiExiste{" + name + "}") for name in order]
        self.assertNotIn(-1, positions, dict(zip(order, positions)))
        self.assertEqual(positions, sorted(positions), "SGR annexes are out of order")


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


def _load_language():
    import importlib.util
    spec = importlib.util.spec_from_file_location("kit_language", REPO / "scripts" / "language.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _english_workspace(root: Path) -> Path:
    for marker in (".morfeo", ".marco"):
        (root / marker).mkdir()
        (root / marker / "config.json").write_text('{"lang": "en"}', encoding="utf-8")
    return root


class TemplateLanguageTest(unittest.TestCase):
    """S3: a run created in English gets an English main.tex and cover."""

    def setUp(self) -> None:
        self.language = _load_language()
        self.tex = MAIN.read_text(encoding="utf-8")

    def test_every_spanish_anchor_exists_once_in_the_template(self) -> None:
        for spanish, _ in self.language.MAIN_TEX_EN:
            with self.subTest(anchor=spanish):
                self.assertEqual(self.tex.count(spanish), 1)

    def test_the_english_template_switches_babel_captions_and_cref(self) -> None:
        english = self.language.localize_main_tex(self.tex, "en")
        for needle in (r"\usepackage[english]{babel}", r"\addto\captionsenglish{\renewcommand{\tablename}{Table}}",
                       r"\crefname{section}{section}{sections}", r"\crefname{figure}{figure}{figures}",
                       r"\crefname{table}{table}{tables}", r"\crefname{equation}{equation}{equations}",
                       "Principal investigator:", r"\section*{References}", "[Missing caption: #1]"):
            with self.subTest(needle=needle):
                self.assertIn(needle, english)
        code = "\n".join(line.split("%")[0] for line in english.splitlines())
        for spanish in ("spanish", "Tabla", "sección", "figura", "ecuación", "Investigador principal",
                        "{Referencias}", "Falta caption"):
            with self.subTest(spanish=spanish):
                self.assertNotIn(spanish, code)

    def test_spanish_is_the_template_unchanged(self) -> None:
        self.assertEqual(self.language.localize_main_tex(self.tex, "es"), self.tex)

    def test_a_drifted_template_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.language.localize_main_tex(self.tex.replace(r"\usepackage[spanish,es-noindentfirst]{babel}", ""),
                                            "en")

    def test_the_english_cover_keeps_a_placeholder_check_run_reads(self) -> None:
        cover = (REPO / "plantilla" / "datos_proyecto.tex").read_text(encoding="utf-8")
        english = self.language.localize_cover(cover, "en")
        self.assertIn("[To be defined: project title]", english)
        self.assertNotIn("[Por definir", english)
        self.assertEqual(self.language.localize_cover(cover, "es"), cover)

    def test_init_run_seeds_english_files_for_an_english_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            red = _make_run(_english_workspace(Path(tmp))) / "redaccion"
            self.assertIn(r"\usepackage[english]{babel}", (red / "main.tex").read_text(encoding="utf-8"))
            self.assertIn("[To be defined", (red / "datos_proyecto.tex").read_text(encoding="utf-8"))

    def test_init_run_keeps_the_spanish_template_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            red = _make_run(Path(tmp)) / "redaccion"
            self.assertEqual((red / "main.tex").read_bytes(), MAIN.read_bytes())
            self.assertEqual((red / "datos_proyecto.tex").read_bytes(),
                             (REPO / "plantilla" / "datos_proyecto.tex").read_bytes())


@unittest.skipUnless(HAS_TEX and shutil.which("pdftotext"), "latexmk/pdflatex/pdftotext not installed")
class EnglishTemplateCompilesTest(unittest.TestCase):
    def test_an_english_run_names_tables_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            red = _make_run(_english_workspace(Path(tmp))) / "redaccion"
            (red / "sections" / "05_hipotesis.tex").write_text(
                "\\section{Hypothesis}\nSee \\cref{tab:demo}.\n\\begin{table}[h]\\centering"
                "\\begin{tabular}{c}x\\end{tabular}\\caption{Demo table}\\label{tab:demo}\\end{table}\n",
                encoding="utf-8")
            env = dict(os.environ, SKIP_DOI_REPAIR="1")
            build = subprocess.run(["bash", "build.sh"], cwd=red, capture_output=True, text=True, env=env,
                                   input="s\n", timeout=240)
            self.assertTrue((red / "main.pdf").is_file(), build.stdout[-2000:] + build.stderr[-2000:])
            text = subprocess.run(["pdftotext", str(red / "main.pdf"), "-"], capture_output=True, text=True).stdout
            self.assertIn("Table 1", text)
            self.assertIn("table 1", text)
            self.assertIn("Principal investigator", text)
            for spanish in ("Tabla", "Cuadro", "tabla 1"):
                self.assertNotIn(spanish, text)


if __name__ == "__main__":
    unittest.main()
