"""Presentación de la corrida activa con el estilo de LIAUNAL/AgentPt.

Cinco diapositivas: convocatoria, título y línea temática; entidad proponente
y aliados con sus escudos; árbol de problemas; árbol de objetivos; y
metodología (preliminar, derivada del árbol de objetivos, mientras no exista
sections/10_metodologia.tex). El tablero la sirve en /presentacion y sus
imágenes en /api/presentation/asset, limitado a logos y figuras de redaccion/.
"""

from __future__ import annotations

import json
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from morfeo.core.presentation import build_presentation
from morfeo.dashboard.server import MorfeoDashboardHandler

RUN = "2026-01-demo"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16

ESTADO = """# Estado de la propuesta

| Campo | Valor |
|---|---|
| Línea temática principal | **5.3.1** (decisión del usuario) |
"""

GUIA = """# Guía ajustada al TDR: Convocatoria 56 del SGR (emergencia, Decreto 1414 de 2026)

**Decisiones del usuario.** Línea temática principal **5.3.1** («Desarrollo, adaptación y validación de tecnologías para la salud mental»). Otra cosa.
"""

DATOS = r"""\newcommand{\TituloProyecto}{Reducción de la prevalencia de depresión en estudiantes}
\newcommand{\EntidadProponente}{Universidad Nacional de Colombia, Sede Manizales}
\newcommand{\InvestigadorPrincipal}{Andrés Marino Álvarez Meza}
\newcommand{\AfiliacionProyecto}{LabIA y GCPDS}
"""

MAIN = r"""\begin{center}
  \LogoAliado{logo_utp}\LogoAliado{logo_udea}\LogoAliado{logo_falta}
\end{center}
"""

OBJETIVOS = {
    "groups": [
        {"id": "OE1", "title": "OE1", "objective": "Aumentar la información oportuna.", "means": [{"id": "m1", "text": "Aumentar el seguimiento."}]},
        {"id": "OE2", "title": "OE2", "objective": "Fortalecer la capacidad tecnológica.", "means": [{"id": "m4", "text": "Aumentar la precisión."}]},
    ],
    "trunk": {"text": "Reducir la prevalencia de depresión."},
}


def make_run(root: Path) -> Path:
    run = root / "proposals" / RUN
    (run / "artefactos" / "arboles").mkdir(parents=True)
    (run / "redaccion" / "logos").mkdir(parents=True)
    (run / "redaccion" / "sections" / "figuras").mkdir(parents=True)
    (root / "proposals" / ".current-run").write_text(RUN, encoding="utf-8")
    (run / "artefactos" / "estado_propuesta.md").write_text(ESTADO, encoding="utf-8")
    (run / "artefactos" / "guia_ajustada_TDR.md").write_text(GUIA, encoding="utf-8")
    (run / "artefactos" / "arboles" / "arbol_objetivos.json").write_text(json.dumps(OBJETIVOS), encoding="utf-8")
    (run / "redaccion" / "datos_proyecto.tex").write_text(DATOS, encoding="utf-8")
    (run / "redaccion" / "main.tex").write_text(MAIN, encoding="utf-8")
    for logo in ("logo_unal", "logo_utp", "logo_udea"):
        (run / "redaccion" / "logos" / f"{logo}.png").write_bytes(PNG)
    for fig in ("fig_arbol_problemas", "fig_arbol_objetivos"):
        (run / "redaccion" / "sections" / "figuras" / f"{fig}-preview-1.png").write_bytes(PNG)
    return run


def slides(html: str) -> list[str]:
    parts = html.split("<article")[1:]
    return [p.split("</article>")[0] for p in parts]


class BuildPresentationTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_dir = make_run(Path(tmp.name))

    def test_five_slides_in_the_requested_order(self) -> None:
        deck = slides(build_presentation(self.run_dir))
        self.assertEqual(len(deck), 5)
        cover, alliance, problems, objectives, method = deck
        self.assertIn("Convocatoria 56 del SGR", cover)
        self.assertIn("Reducción de la prevalencia de depresión en estudiantes", cover)
        self.assertIn("5.3.1", cover)
        self.assertIn("Desarrollo, adaptación y validación de tecnologías para la salud mental", cover)
        self.assertIn("Universidad Nacional de Colombia, Sede Manizales", alliance)
        self.assertIn("Árbol de problemas", problems)
        self.assertIn("Árbol de objetivos", objectives)
        self.assertIn("Metodología", method)

    def test_each_rail_title_opens_the_first_slide_of_its_module(self) -> None:
        html = build_presentation(self.run_dir)
        firsts = re.findall(r'data-first="(\d+)"', html)
        indexes = re.findall(r'<article class="slide[^"]*" data-index="(\d+)"', html)
        self.assertEqual(firsts, indexes)

    def test_alliance_slide_shows_proponent_and_existing_ally_logos_only(self) -> None:
        alliance = slides(build_presentation(self.run_dir))[1]
        for logo in ("logo_unal", "logo_utp", "logo_udea"):
            self.assertIn(f"/api/presentation/asset?path=logos/{logo}.png", alliance)
        self.assertNotIn("logo_falta", alliance)

    def test_tree_slides_use_the_rendered_figures(self) -> None:
        deck = slides(build_presentation(self.run_dir))
        self.assertIn("path=sections/figuras/fig_arbol_problemas-preview-1.png", deck[2])
        self.assertIn("path=sections/figuras/fig_arbol_objetivos-preview-1.png", deck[3])

    def test_methodology_is_preliminary_from_the_objective_tree(self) -> None:
        method = slides(build_presentation(self.run_dir))[4]
        self.assertIn("preliminar", method.lower())
        self.assertIn("Aumentar la información oportuna.", method)
        self.assertIn("Fortalecer la capacidad tecnológica.", method)
        self.assertIn("Aumentar la precisión.", method)

    def test_methodology_uses_section_10_phases_when_written(self) -> None:
        (self.run_dir / "redaccion" / "sections" / "10_metodologia.tex").write_text(
            "\\section{Metodología}\n\\subsection{Fase 1: Levantamiento de datos}\ntexto\n\\subsection{Fase 2: Modelos}\n",
            encoding="utf-8",
        )
        method = slides(build_presentation(self.run_dir))[4]
        self.assertIn("Fase 1: Levantamiento de datos", method)
        self.assertIn("Fase 2: Modelos", method)
        self.assertNotIn("preliminar", method.lower())

    def test_missing_data_is_marked_not_invented(self) -> None:
        (self.run_dir / "artefactos" / "guia_ajustada_TDR.md").unlink()
        (self.run_dir / "redaccion" / "sections" / "figuras" / "fig_arbol_problemas-preview-1.png").unlink()
        deck = slides(build_presentation(self.run_dir))
        self.assertIn("[Convocatoria por definir]", deck[0])
        self.assertIn("pendiente", deck[2].lower())

    def test_text_is_html_escaped(self) -> None:
        (self.run_dir / "redaccion" / "datos_proyecto.tex").write_text(
            DATOS.replace("en estudiantes", "en <script>alert(1)</script>"), encoding="utf-8"
        )
        html = build_presentation(self.run_dir)
        self.assertNotIn("<script>alert(1)</script>", html)


class PresentationEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        make_run(self.root)
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": self.root})
        handler.log_message = lambda *a, **k: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.base = f"http://127.0.0.1:{server.server_address[1]}"

    def _status(self, path: str) -> int:
        try:
            with urllib.request.urlopen(self.base + path) as res:
                return res.status
        except urllib.error.HTTPError as err:
            return err.code

    def test_presentation_page_is_served_as_html(self) -> None:
        with urllib.request.urlopen(self.base + "/presentacion") as res:
            self.assertEqual(res.status, 200)
            self.assertIn("text/html", res.headers.get("Content-Type"))
            body = res.read().decode("utf-8")
        self.assertIn("/static/presentacion/styles.css", body)
        self.assertIn("/static/presentacion/app.js", body)

    def test_vendored_agentpt_assets_are_served(self) -> None:
        self.assertEqual(self._status("/static/presentacion/styles.css"), 200)
        self.assertEqual(self._status("/static/presentacion/app.js"), 200)

    def test_asset_endpoint_serves_logos_and_figures_only(self) -> None:
        with urllib.request.urlopen(self.base + "/api/presentation/asset?path=logos/logo_utp.png") as res:
            self.assertEqual(res.status, 200)
            self.assertEqual(res.headers.get("Content-Type"), "image/png")
            self.assertEqual(res.read(), PNG)
        self.assertEqual(self._status("/api/presentation/asset?path=../artefactos/estado_propuesta.md"), 403)
        self.assertEqual(self._status("/api/presentation/asset?path=main.tex"), 403)
        self.assertEqual(self._status("/api/presentation/asset?path=logos/nada.png"), 404)

    def test_without_active_run_is_404(self) -> None:
        (self.root / "proposals" / ".current-run").unlink()
        self.assertEqual(self._status("/presentacion"), 404)


if __name__ == "__main__":
    unittest.main()
