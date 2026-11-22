"""The paper summary side panel of the SOTA constellation (render_atlas.py).

A click on any planet of a paper opens a side panel (papersmith's ``#side``)
with the paper's metadata, read at build time from the sibling
``papers/paper-N.md`` files, instead of the old evidence modal. These tests
pin the Python half: which metadata is embedded, how missing files degrade,
that nothing hostile reaches the page unescaped, and that the dashboard's
builder hands the papers directory over. The click behavior itself is pinned
under jsdom in ``tests/js/atlas.side.test.mjs``.

Stdlib only, offline.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RENDERER = REPO / "scripts" / "render_atlas.py"
BUILDER = REPO / "scripts" / "build_manuscript_graph.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "constelacion"
FIXTURE_ATLAS = FIXTURES / "atlas.json"
FIXTURE_PAPERS = FIXTURES / "papers"
DATA_OPEN = '<script type="application/json" id="atlas-data">'


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scene_of(page: str) -> dict:
    start = page.index(DATA_OPEN) + len(DATA_OPEN)
    return json.loads(page[start:page.index("</script>", start)])


HOSTILE_PAPER = """# <img src=x onerror="window.__pwned=1">

- Autores: <b>Mallory</b> </script><script>alert(1)</script>
- Año: 2025
- Venue: <i>Venue</i>
- Cuartil: Q1
- DOI/URL: javascript:alert(1)
- Clave: evil2025

## Abstract

<img src=x onerror="window.__pwned=1"> An abstract that must never be embedded.
"""


class SidePanelRenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="atlas-side-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.out = self.tmp / "atlas.html"

    def render(self, source: Path, *extra: str) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(RENDERER), str(source), "--out",
                               str(self.out), *extra], capture_output=True, text=True,
                              cwd=self.tmp)
        return proc.returncode, proc.stdout + proc.stderr

    def page(self, source: Path = FIXTURE_ATLAS, *extra: str) -> str:
        code, out = self.render(source, *extra)
        self.assertEqual(code, 0, out)
        return self.out.read_text(encoding="utf-8")

    def lone_atlas(self) -> Path:
        """The fixture atlas copied alone: no sibling papers/ directory."""
        lone = self.tmp / "lone"
        lone.mkdir()
        shutil.copy(FIXTURE_ATLAS, lone / "atlas.json")
        return lone / "atlas.json"

    def test_page_carries_the_side_panel_instead_of_the_modal(self):
        page = self.page()
        self.assertIn('<aside id="side" aria-label="Resumen del paper" hidden>', page)
        self.assertIn('<button id="sideclose" type="button" aria-label="Cerrar">✕</button>', page)
        self.assertIn('<div id="sidebody"></div>', page)
        for gone in ('id="overlay"', 'id="modal"', "openModal", "showPlanet"):
            self.assertNotIn(gone, page)
        self.assertIn("function showSide(", page)
        self.assertIn("function select(", page)
        self.assertIn("function clearSelection(", page)
        self.assertIn("haz clic para abrir el resumen del paper", page)
        self.assertNotIn("haz clic para leer su evidencia", page)

    def test_side_panel_stays_inside_narrow_screens(self):
        page = self.page()
        narrow = page[page.index("@media (max-width:820px)"):]
        narrow = narrow[:narrow.index("\n")]
        self.assertIn("#side{position:fixed;left:0;right:0;bottom:0", narrow)
        self.assertIn("max-width:none", narrow)
        self.assertIn("overflow-wrap:anywhere", page)

    def test_metadata_is_read_from_the_sibling_papers_directory(self):
        scene = scene_of(self.page())
        self.assertEqual(scene["papers"]["paper-1"], {
            "authors": "Ana Pérez, Luis Gómez",
            "year": "2025",
            "venue": "Scientific Reports",
            "quartile": "Q1",
            "link": "https://doi.org/10.1000/fixture.1",
            "bibkey": "perez2025_mil",
        })
        self.assertEqual(sorted(scene["papers"]), ["paper-1", "paper-2", "paper-3"])

    def test_only_the_metadata_lines_are_embedded(self):
        # The fixture's quotes already cover its abstracts verbatim, so the
        # abstract-never-embedded rule is pinned by the hostile test below.
        page = self.page()
        self.assertNotIn("Herramienta:", page)
        allowed = {"authors", "year", "venue", "quartile", "link", "bibkey"}
        for meta in scene_of(page)["papers"].values():
            self.assertLessEqual(set(meta), allowed)

    def test_explicit_papers_flag_wins_over_the_sibling_directory(self):
        papers = self.tmp / "otros"
        papers.mkdir()
        (papers / "paper-2.md").write_text(
            "# T\n\n- Autores: Solo Explícito\n- Clave: explicito2024\n", encoding="utf-8")
        scene = scene_of(self.page(FIXTURE_ATLAS, "--papers", str(papers)))
        self.assertEqual(scene["papers"], {"paper-2": {"authors": "Solo Explícito",
                                                       "bibkey": "explicito2024"}})

    def test_missing_papers_degrade_to_no_metadata(self):
        scene = scene_of(self.page(self.lone_atlas()))
        self.assertEqual(scene["papers"], {})
        code, out = self.render(FIXTURE_ATLAS, "--papers", str(self.tmp / "absent"))
        self.assertEqual(code, 0, out)
        self.assertEqual(scene_of(self.out.read_text(encoding="utf-8"))["papers"], {})

    def test_only_paper_n_ids_are_read_from_disk(self):
        module = load(RENDERER, "render_atlas_side_ids")
        (self.tmp / "papers").mkdir()
        (self.tmp / "secret.md").write_text("- Autores: Fuera\n", encoding="utf-8")
        atlas = {"systems": [{"id": "../secret", "planets": []}], "links": []}
        self.assertEqual(module.papers_meta(atlas, self.tmp / "papers"), {})

    def test_hostile_metadata_is_escaped_in_the_data_island(self):
        run = self.tmp / "hostile"
        (run / "papers").mkdir(parents=True)
        doc = json.loads(FIXTURE_ATLAS.read_text(encoding="utf-8"))
        (run / "atlas.json").write_text(json.dumps(doc), encoding="utf-8")
        (run / "papers" / "paper-1.md").write_text(HOSTILE_PAPER, encoding="utf-8")
        page = self.page(run / "atlas.json")
        self.assertNotIn("<b>Mallory", page)
        self.assertNotIn("<i>Venue", page)
        self.assertNotIn("<script>alert(1)", page)
        self.assertNotIn("An abstract that must never be embedded", page)
        meta = scene_of(page)["papers"]["paper-1"]
        self.assertEqual(meta["authors"], "<b>Mallory</b> </script><script>alert(1)</script>")
        self.assertEqual(meta["link"], "javascript:alert(1)")

    def test_same_atlas_and_papers_draw_the_same_bytes(self):
        first = self.page()
        second = self.page()
        self.assertEqual(first, second)

    def test_read_paper_meta_keeps_only_the_metadata_block(self):
        module = load(RENDERER, "render_atlas_side_meta")
        text = ("# Title\n\n- Autores: A\n- Año: 2024\n\n## Verificación\n"
                "- Autores: not this one\n\n## Abstract\n\n- Clave: nor this\n")
        self.assertEqual(module.read_paper_meta(text), {"authors": "A", "year": "2024"})
        self.assertEqual(module.read_paper_meta("- Clave: " + "x" * 900)["bibkey"], "x" * 300)


class BuilderHandsPapersOverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="atlas-side-build-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_dashboard_constellation_carries_paper_metadata(self):
        run = self.tmp / "2026-10-demo"
        scoping = run / "artefactos" / "scoping"
        shutil.copytree(FIXTURE_PAPERS, scoping / "papers")
        shutil.copy(FIXTURE_ATLAS, scoping / "atlas.json")
        (run / "grafos").mkdir(parents=True)
        builder = load(BUILDER, "build_manuscript_graph_side")
        calls = []
        real_run = builder.subprocess.run

        def spy(args, *rest, **kw):
            calls.append(list(args))
            return real_run(args, *rest, **kw)

        builder.subprocess.run = spy
        try:
            result = builder.build_papers_graph(run)
        finally:
            builder.subprocess.run = real_run
        self.assertEqual(result.get("source"), "atlas")
        renderer_call = next(c for c in calls if c[1].endswith("render_atlas.py"))
        at = renderer_call.index("--papers")
        self.assertEqual(Path(renderer_call[at + 1]), scoping / "papers")
        page = (run / "grafos" / "papers-graph.html").read_text(encoding="utf-8")
        papers = scene_of(page)["papers"]
        self.assertEqual(papers["paper-3"]["authors"], "Jorge Díaz, Elena Mora")
        self.assertNotIn("bibkey", papers["paper-2"])
        self.assertIn('<aside id="side"', page)


if __name__ == "__main__":
    unittest.main()
