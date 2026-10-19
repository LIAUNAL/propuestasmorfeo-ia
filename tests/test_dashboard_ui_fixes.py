"""Status data behind the dashboard fixes of T6 (S9).

F3: the "Figuras" column read only the section file, while the diagrams are
included from `redaccion/main.tex` right after the section that owns them.
F5: the footer hard-coded "Morfeo IA v0.5.0"; the status envelope now carries
the running package version next to the workspace kit stamp.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import morfeo
from morfeo.core.status import get_project_status

MAIN_TEX = r"""\documentclass[11pt,a4paper]{article}
\begin{document}
\setcounter{section}{1}
\input{sections/02_justificacion}
\input{sections/03_problema}
\begin{figure}[H]
  \input{sections/diag_arbol_problemas}
\end{figure}
\input{sections/04_estado_arte}
% \input{sections/diag_estado_arte}
\input{sections/10_metodologia}
\includegraphics[width=\linewidth]{figures/fig_metodologico}
\input{sections/11_resultados}
\end{document}
"""

BODY = "Texto de relleno con suficientes palabras para la sección. " * 3


class _RunFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.run = self.repo / "proposals" / "2026-01-demo"
        sections = self.run / "redaccion" / "sections"
        sections.mkdir(parents=True)
        (self.repo / "proposals" / ".current-run").write_text("2026-01-demo\n", encoding="utf-8")
        (self.run / "_run.md").write_text("| Idea | demo |\n", encoding="utf-8")
        for stem in ("02_justificacion", "03_problema", "04_estado_arte", "10_metodologia", "11_resultados"):
            (sections / f"{stem}.tex").write_text(BODY, encoding="utf-8")
        (sections / "12_etica.tex").write_text(
            BODY + "\n% \\includegraphics{x}\n\\input{sections/diag_etica}\n", encoding="utf-8"
        )
        (sections / "diag_arbol_problemas.tex").write_text("% tikz\n", encoding="utf-8")
        (self.run / "redaccion" / "main.tex").write_text(MAIN_TEX, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def status(self) -> dict:
        return get_project_status(self.repo, force_refresh=True)


class TestSectionFigures(_RunFixture):
    def figures(self) -> dict[str, bool]:
        return {s["id"]: s["has_figures"] for s in self.status()["sections"]}

    def test_a_diagram_included_from_main_tex_belongs_to_the_preceding_section(self):
        figs = self.figures()
        self.assertTrue(figs["03_problema"])
        self.assertTrue(figs["10_metodologia"])

    def test_sections_without_a_following_figure_report_none(self):
        figs = self.figures()
        self.assertFalse(figs["02_justificacion"])
        self.assertFalse(figs["11_resultados"])

    def test_a_commented_out_include_is_ignored(self):
        self.assertFalse(self.figures()["04_estado_arte"])

    def test_a_figure_inside_the_section_file_still_counts(self):
        """Previous behavior: an include in the section file itself is a figure."""
        self.assertTrue(self.figures()["12_etica"])

    def test_figure_count_is_reported_per_section(self):
        counts = {s["id"]: s["figures_count"] for s in self.status()["sections"]}
        self.assertEqual(counts["03_problema"], 1)
        self.assertEqual(counts["02_justificacion"], 0)

    def test_without_main_tex_detection_falls_back_to_the_section_file(self):
        (self.run / "redaccion" / "main.tex").unlink()
        figs = self.figures()
        self.assertFalse(figs["03_problema"])
        self.assertTrue(figs["12_etica"])


class TestTemplateRun(unittest.TestCase):
    """Runs created from plantilla/main.tex place diagrams through macros."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.run = self.repo / "proposals" / "2026-01-plantilla"
        sections = self.run / "redaccion" / "sections"
        sections.mkdir(parents=True)
        (self.repo / "proposals" / ".current-run").write_text("2026-01-plantilla\n", encoding="utf-8")
        (self.run / "_run.md").write_text("| Idea | idea corta |\n", encoding="utf-8")
        plantilla = Path(__file__).resolve().parent.parent / "plantilla"
        (self.run / "redaccion" / "main.tex").write_text((plantilla / "main.tex").read_text(encoding="utf-8"))
        (self.run / "redaccion" / "datos_proyecto.tex").write_text(
            "\\newcommand{\\TituloProyecto}{Sistema de prueba con plantilla}\n", encoding="utf-8")
        for stem in ("03_descripcion_problema", "04_estado_arte", "05_hipotesis"):
            (sections / f"{stem}.tex").write_text(BODY, encoding="utf-8")
        for diag in ("diag_arbol_problemas", "diag_estado_arte_a", "diag_estado_arte_b"):
            (sections / f"{diag}.tex").write_text("% tikz\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_diagrams_placed_by_the_template_macros_are_counted(self):
        status = get_project_status(self.repo, force_refresh=True)
        sections = (status.get("run_details") or {}).get("sections") or status.get("sections") or []
        counts = {s["id"]: s.get("figures_count", 0) for s in sections}
        self.assertEqual(counts.get("03_descripcion_problema"), 1, counts)
        self.assertEqual(counts.get("04_estado_arte"), 2, counts)
        self.assertEqual(counts.get("05_hipotesis"), 0, counts)

    def test_title_comes_from_datos_proyecto(self):
        status = get_project_status(self.repo, force_refresh=True)
        details = status.get("run_details") or {}
        self.assertEqual(details.get("title"), "Sistema de prueba con plantilla", details)


class TestPackageVersion(_RunFixture):
    def test_status_reports_the_running_package_version(self):
        self.assertEqual(self.status()["package_version"], morfeo.__version__)

    def test_version_keeps_reporting_the_workspace_kit_stamp(self):
        """Previous behavior: `version` is the `.marco/version` stamp."""
        marker = self.repo / ".marco"
        marker.mkdir()
        (marker / "version").write_text("0.5.0\n", encoding="utf-8")
        status = self.status()
        self.assertEqual(status["version"], "0.5.0")
        self.assertEqual(status["package_version"], morfeo.__version__)


if __name__ == "__main__":
    unittest.main()
