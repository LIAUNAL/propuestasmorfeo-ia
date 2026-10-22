"""The SOTA constellation, held executable: check_atlas.py, render_atlas.py and
the papers branch of build_manuscript_graph.py.

Ported from papersmith-ai (tests/test_sota_atlas.py, Apache License 2.0,
https://github.com/LIAUNAL/papersmith-ai) and adapted to Morfeo: system ids
are ``paper-N``, quote fidelity is checked against the ``## Abstract`` section
of ``artefactos/scoping/papers/paper-N.md``, the family band is 1..7, the UI is
in Spanish and the page carries the "Estudio de constelaciones" panel.

Stdlib only, offline.
"""

from __future__ import annotations

import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
CHECKER = SCRIPTS / "check_atlas.py"
RENDERER = SCRIPTS / "render_atlas.py"
BUILDER = SCRIPTS / "build_manuscript_graph.py"
BUNDLE = SCRIPTS / "assets" / "atlas3d.bundle.js"
NOTICES = SCRIPTS / "assets" / "THIRD_PARTY_NOTICES.md"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "constelacion"
FIXTURE_ATLAS = FIXTURES / "atlas.json"
FIXTURE_PAPERS = FIXTURES / "papers"
DATA_OPEN = '<script type="application/json" id="atlas-data">'

ORBITS = {"sun": 0, "branch": 1, "topic_app": 1, "topic_ai": 1,
          "problem": 1, "application": 1, "family": 2, "novelty": 1,
          "contribution": 1, "result": 3, "conclusion": 3}
BASE_SLOTS = ["sun", "topic_app", "topic_ai", "problem", "application",
              "novelty", "result", "conclusion"]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scene_of(page: str) -> dict:
    start = page.index(DATA_OPEN) + len(DATA_OPEN)
    return json.loads(page[start:page.index("</script>", start)])


def planet(pid, slot="result", **over):
    doc = {"id": pid, "slot": slot, "orbit": ORBITS[slot], "label": f"L{pid}",
           "detail": f"D{pid}", "provenance": "stated",
           "evidence": {"origin": "https://example.test/p", "quote": "q",
                        "retrieved": "2026-09-30"}}
    doc.update(over)
    return doc


def system(sid, fam):
    nodes = [planet(f"{sid}-{slot}", slot) for slot in BASE_SLOTS]
    nodes.append(planet(f"{sid}-family", "family", label=fam))
    return {"id": sid, "title": f"T{sid}", "planets": nodes}


def atlas(systems=None, links=None):
    if systems is None:
        systems = [system("paper-1", "F1"), system("paper-2", "F2"), system("paper-3", "F3")]
    return {"systems": systems, "links": links if links is not None else []}


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="constelacion-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))


class CheckAtlasTests(Tmp):
    def run_checker(self, payload, *extra):
        target = self.tmp / "atlas.json"
        target.write_text(payload if isinstance(payload, str) else json.dumps(payload),
                          encoding="utf-8")
        proc = subprocess.run([sys.executable, str(CHECKER), str(target), *extra],
                              capture_output=True, text=True, cwd=self.tmp)
        return proc.returncode, proc.stdout + proc.stderr

    def test_green_constellation_with_intra_and_family_links_passes(self):
        links = [{"from_system": "paper-1", "from": "paper-1-family", "to_system": "paper-2",
                  "to": "paper-2-family", "rel": "shares-family-with"},
                 {"from_system": "paper-1", "from": "paper-1-sun", "to_system": "paper-1",
                  "to": "paper-1-problem", "rel": "about"}]
        code, out = self.run_checker(atlas(links=links))
        self.assertEqual(code, 0, out)
        self.assertIn("ATLAS_WELL_FORMED", out)

    def test_family_link_on_non_family_is_named(self):
        links = [{"from_system": "paper-1", "from": "paper-1-topic_app", "to_system": "paper-2",
                  "to": "paper-2-family", "rel": "shares-family-with"}]
        code, out = self.run_checker(atlas(links=links))
        self.assertEqual(code, 1, out)
        self.assertIn("SHARED_FAMILY_LINK_ON_NON_FAMILY", out)

    def test_twenty_first_planet_exceeds_the_ceiling(self):
        doc = atlas()
        doc["systems"][0]["planets"].extend(planet(f"x{i}") for i in range(12))
        code, out = self.run_checker(doc)
        self.assertEqual(code, 1, out)
        self.assertIn("PLANET_BUDGET_EXCEEDED", out)

    def test_second_family_planet_breaks_membership(self):
        doc = atlas()
        doc["systems"][0]["planets"].append(planet("paper-1-family-2", "family", label="F2"))
        code, out = self.run_checker(doc)
        self.assertEqual(code, 1, out)
        self.assertIn("SLOT_COUNT_OUTSIDE_ROW", out)

    def test_orbit_must_follow_the_slot(self):
        doc = atlas()
        doc["systems"][0]["planets"][1]["orbit"] = 3
        code, out = self.run_checker(doc)
        self.assertEqual(code, 1, out)
        self.assertIn("ORBIT_MISMATCH", out)

    def test_one_family_is_enough_for_a_small_morfeo_corpus(self):
        """Fase 1a scopes five papers: one theme is a legitimate constellation."""
        systems = [system(f"paper-{i}", "F1") for i in range(1, 6)]
        code, out = self.run_checker(atlas(systems=systems))
        self.assertEqual(code, 0, out)

    def test_seven_families_pass_and_eight_are_refused(self):
        code, out = self.run_checker(atlas(systems=[system(f"paper-{i}", f"F{i}")
                                                    for i in range(1, 8)]))
        self.assertEqual(code, 0, out)
        code, out = self.run_checker(atlas(systems=[system(f"paper-{i}", f"F{i}")
                                                    for i in range(1, 9)]))
        self.assertEqual(code, 1, out)
        self.assertIn("POOL_FAMILIES_OUTSIDE_1_7", out)

    def test_system_id_must_name_a_paper_file(self):
        code, out = self.run_checker(atlas(systems=[system("a", "F1")]))
        self.assertEqual(code, 1, out)
        self.assertIn("SYSTEM_ID_NOT_PAPER_N", out)

    def test_link_to_no_planet_is_named(self):
        links = [{"from_system": "paper-1", "from": "paper-1-sun", "to_system": "paper-2",
                  "to": "ghost", "rel": "contradicts"}]
        code, out = self.run_checker(atlas(links=links))
        self.assertEqual(code, 1, out)
        self.assertIn("LINK_ENDPOINT_WITHOUT_PLANET", out)

    def test_link_to_no_system_is_named(self):
        links = [{"from_system": "paper-1", "from": "paper-1-sun", "to_system": "ghost",
                  "to": "paper-1-topic_app", "rel": "about"}]
        code, out = self.run_checker(atlas(links=links))
        self.assertEqual(code, 1, out)
        self.assertIn("LINK_SYSTEM_WITHOUT_SYSTEM", out)

    def test_rel_outside_the_closed_set_is_named(self):
        links = [{"from_system": "paper-1", "from": "paper-1-sun", "to_system": "paper-2",
                  "to": "paper-2-sun", "rel": "inspires"}]
        code, out = self.run_checker(atlas(links=links))
        self.assertEqual(code, 1, out)
        self.assertIn("REL_OUTSIDE_CLOSED_SET", out)

    def test_undated_evidence_is_named(self):
        doc = atlas()
        doc["systems"][0]["planets"][0]["evidence"]["retrieved"] = "someday"
        code, out = self.run_checker(doc)
        self.assertEqual(code, 1, out)
        self.assertIn("EVIDENCE_RETRIEVED_UNDATED", out)

    def test_contributions_are_admitted_up_to_five(self):
        doc = atlas()
        doc["systems"][0]["planets"].extend(planet(f"c{i}", "contribution") for i in range(5))
        code, out = self.run_checker(doc)
        self.assertEqual(code, 0, out)
        doc["systems"][0]["planets"].append(planet("c5", "contribution"))
        code, out = self.run_checker(doc)
        self.assertEqual(code, 1, out)
        self.assertIn("SLOT_COUNT_OUTSIDE_ROW", out)

    def test_every_violation_is_named_in_one_run(self):
        doc = atlas()
        doc["systems"][0]["planets"][0]["evidence"]["retrieved"] = "someday"
        doc["systems"][1]["planets"][0]["provenance"] = "guessed"
        code, out = self.run_checker(doc)
        self.assertEqual(code, 1, out)
        self.assertIn("EVIDENCE_RETRIEVED_UNDATED", out)
        self.assertIn("PROVENANCE_UNLABELED", out)

    def test_non_json_is_unjudged_not_refused(self):
        code, out = self.run_checker("{not json")
        self.assertEqual(code, 2, out)
        self.assertIn("ATLAS_NOT_JSON", out)

    def test_json_report_lists_structured_violations(self):
        doc = atlas()
        doc["systems"][0]["planets"][0]["evidence"]["retrieved"] = "someday"
        code, out = self.run_checker(doc, "--json")
        self.assertEqual(code, 1, out)
        report = json.loads(out)
        self.assertFalse(report["ok"])
        codes = [v["code"] for v in report["violations"]]
        self.assertIn("EVIDENCE_RETRIEVED_UNDATED", codes)
        undated = next(v for v in report["violations"] if v["code"] == "EVIDENCE_RETRIEVED_UNDATED")
        self.assertEqual(undated["where"], "paper-1.paper-1-sun")
        self.assertTrue(undated["message"])

    def test_limits_are_documented_constants(self):
        module = load(CHECKER, "check_atlas")
        self.assertEqual((module.MIN_FAMILIES, module.MAX_FAMILIES), (1, 7))
        self.assertEqual(module.MAX_PLANETS, 20)
        self.assertGreaterEqual(module.MAX_SYSTEMS, 45)


class QuoteFidelityTests(Tmp):
    """`--papers` holds every quote to the abstract of its paper-N.md."""

    def run_checker(self, atlas_path, papers_dir, *extra):
        proc = subprocess.run([sys.executable, str(CHECKER), str(atlas_path),
                               "--papers", str(papers_dir), *extra],
                              capture_output=True, text=True, cwd=self.tmp)
        return proc.returncode, proc.stdout + proc.stderr

    def fixture(self, mutate=None):
        doc = json.loads(FIXTURE_ATLAS.read_text(encoding="utf-8"))
        if mutate:
            mutate(doc)
        target = self.tmp / "atlas.json"
        target.write_text(json.dumps(doc), encoding="utf-8")
        return target

    def test_the_fixture_is_green_with_every_quote_verbatim(self):
        code, out = self.run_checker(FIXTURE_ATLAS, FIXTURE_PAPERS)
        self.assertEqual(code, 0, out)
        self.assertIn("ATLAS_WELL_FORMED", out)
        self.assertIn("paper-N.md", out)

    def test_json_report_on_the_green_fixture(self):
        code, out = self.run_checker(FIXTURE_ATLAS, FIXTURE_PAPERS, "--json")
        self.assertEqual(code, 0, out)
        report = json.loads(out)
        self.assertTrue(report["ok"])
        self.assertTrue(report["fidelity_checked"])
        self.assertEqual(report["systems"], 3)
        self.assertEqual(report["families"], 2)
        self.assertEqual(report["violations"], [])

    def test_a_paraphrase_fails(self):
        def mutate(doc):
            doc["systems"][0]["planets"][0]["evidence"]["quote"] = "We use MIL on transcripts."
        code, out = self.run_checker(self.fixture(mutate), FIXTURE_PAPERS)
        self.assertEqual(code, 1, out)
        self.assertIn("EVIDENCE_QUOTE_NOT_IN_ABSTRACT", out)

    def test_whitespace_is_layout_but_case_is_not(self):
        def across_lines(doc):
            doc["systems"][0]["planets"][0]["evidence"]["quote"] = (
                "loses information. We apply a multiple")
        code, out = self.run_checker(self.fixture(across_lines), FIXTURE_PAPERS)
        self.assertEqual(code, 0, out)

        def lowered(doc):
            doc["systems"][0]["planets"][0]["evidence"]["quote"] = "we apply a multiple"
        code, out = self.run_checker(self.fixture(lowered), FIXTURE_PAPERS)
        self.assertEqual(code, 1, out)

    def test_quotes_from_the_metadata_block_do_not_count(self):
        def mutate(doc):
            doc["systems"][0]["planets"][0]["evidence"]["quote"] = "Scientific Reports"
        code, out = self.run_checker(self.fixture(mutate), FIXTURE_PAPERS)
        self.assertEqual(code, 1, out)
        self.assertIn("EVIDENCE_QUOTE_NOT_IN_ABSTRACT", out)

    def test_origin_must_equal_the_doi_url_line(self):
        def mutate(doc):
            doc["systems"][1]["planets"][2]["evidence"]["origin"] = "https://elsewhere.example/x"
        code, out = self.run_checker(self.fixture(mutate), FIXTURE_PAPERS)
        self.assertEqual(code, 1, out)
        self.assertIn("EVIDENCE_ORIGIN_MISMATCH", out)
        self.assertIn("https://doi.org/10.1000/fixture.2", out)

    def test_a_system_without_its_paper_file_fails(self):
        def mutate(doc):
            doc["systems"][2]["id"] = "paper-9"
            for link in doc["links"]:
                for key in ("from_system", "to_system"):
                    if link[key] == "paper-3":
                        link[key] = "paper-9"
        code, out = self.run_checker(self.fixture(mutate), FIXTURE_PAPERS)
        self.assertEqual(code, 1, out)
        self.assertIn("EVIDENCE_PAPER_MISSING", out)

    def test_a_paper_without_an_abstract_cannot_be_quoted(self):
        papers = self.tmp / "papers"
        shutil.copytree(FIXTURE_PAPERS, papers)
        text = (papers / "paper-2.md").read_text(encoding="utf-8")
        (papers / "paper-2.md").write_text(text.split("## Abstract")[0], encoding="utf-8")
        code, out = self.run_checker(FIXTURE_ATLAS, papers)
        self.assertEqual(code, 1, out)
        self.assertIn("EVIDENCE_ABSTRACT_MISSING", out)

    def test_a_missing_papers_directory_judges_nothing(self):
        code, out = self.run_checker(FIXTURE_ATLAS, self.tmp / "nowhere")
        self.assertEqual(code, 2, out)
        self.assertIn("PAPERS_DIR_UNREADABLE", out)

    def test_without_papers_the_check_stays_shape_only(self):
        doc = json.loads(FIXTURE_ATLAS.read_text(encoding="utf-8"))
        doc["systems"][0]["planets"][0]["evidence"]["quote"] = "invented"
        target = self.tmp / "atlas.json"
        target.write_text(json.dumps(doc), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(CHECKER), str(target)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("paper-N.md", proc.stdout)


class RenderAtlasTests(Tmp):
    def setUp(self):
        super().setUp()
        self.out = self.tmp / "atlas.html"

    def render(self, *extra, source=FIXTURE_ATLAS):
        proc = subprocess.run([sys.executable, str(RENDERER), str(source), "--out",
                               str(self.out), *extra], capture_output=True, text=True,
                              cwd=self.tmp)
        return proc.returncode, proc.stdout + proc.stderr

    def page(self):
        code, out = self.render()
        self.assertEqual(code, 0, out)
        return self.out.read_text(encoding="utf-8")

    def page_script(self):
        page = self.page()
        bundle = BUNDLE.read_text(encoding="utf-8")
        return page[page.index(bundle) + len(bundle):]

    def test_green_atlas_renders_one_self_contained_sky(self):
        page = self.page()
        self.assertEqual(page.count('id="sky"'), 1)
        self.assertEqual(page.count(DATA_OPEN), 1)
        scene = scene_of(page)
        inter = sorted((e["from"], e["to"]) for e in scene["edges"] if e["inter"])
        self.assertIn(("paper-3.p3-novelty", "paper-1.p1-novelty"), inter)
        for needle in ('rellegend', 'id="zoomin"', 'id="zoomout"', 'id="zoomreset"',
                       'famchips', 'id="overlay"', 'openModal', 'AtlasViewer.mount',
                       '<html lang="es">'):
            self.assertIn(needle, page)
        self.assertNotIn("<script src", page)
        self.assertNotIn("<link ", page)
        self.assertNotIn("@import", page)

    def test_ui_text_is_spanish(self):
        page = self.page()
        for text in ("Familias:", "Relaciones:", "restablecer vista", "Vista 2D",
                     "cerrar", "Disposición de grupos"):
            self.assertIn(text, page)
        self.assertNotIn(">close<", page)
        self.assertNotIn("reset view", page)

    def test_slot_colors_are_papersmiths(self):
        scene = scene_of(self.page())
        self.assertEqual(scene["slot_colors"]["sun"], "#e8b339")
        self.assertEqual(scene["slot_colors"]["problem"], "#e65a5a")
        self.assertEqual(scene["slot_colors"]["result"], "#2ecc71")

    def test_title_is_escaped_and_used_twice(self):
        code, out = self.render("--title", "<img src=x> Corrida")
        self.assertEqual(code, 0, out)
        page = self.out.read_text(encoding="utf-8")
        self.assertNotIn("<img src=x", page)
        self.assertIn("<title>&lt;img src=x&gt; Corrida</title>", page)
        self.assertIn("<h1>&lt;img src=x&gt; Corrida</h1>", page)

    def test_vendored_viewer_is_inlined_verbatim_with_attribution(self):
        bundle = BUNDLE.read_text(encoding="utf-8")
        self.assertNotIn("</script", bundle.lower())
        self.assertIn("window.AtlasViewer", bundle)
        self.assertIn("papersmith-ai", bundle[:600])
        self.assertIn(bundle, self.page())
        notices = NOTICES.read_text(encoding="utf-8")
        for name in ("papersmith-ai", "three.js", "OrbitControls", "Apache"):
            self.assertIn(name, notices)
        for script in (CHECKER, RENDERER):
            head = script.read_text(encoding="utf-8")[:2500]
            self.assertIn("papersmith-ai", head)
            self.assertIn("Apache", head)

    def test_every_planet_has_a_point_in_three_dimensions(self):
        scene = scene_of(self.page())
        doc = json.loads(FIXTURE_ATLAS.read_text(encoding="utf-8"))
        keys = {f"{s['id']}.{p['id']}" for s in doc["systems"] for p in s["planets"]}
        self.assertEqual(set(scene["positions"]), keys)
        points = list(scene["positions"].values())
        self.assertTrue(all(len(p) == 3 for p in points))
        self.assertGreater(len({p[2] for p in points}), 1)

    def test_same_atlas_draws_the_same_bytes(self):
        first = self.page()
        second = self.page()
        self.assertEqual(first, second)
        report_a, report_b = self.tmp / "a.md", self.tmp / "b.md"
        self.render("--report", str(report_a))
        self.render("--report", str(report_b))
        self.assertEqual(report_a.read_bytes(), report_b.read_bytes())

    def test_red_shape_is_not_drawn(self):
        bad = self.tmp / "bad.json"
        bad.write_text(json.dumps({"systems": []}), encoding="utf-8")
        code, out = self.render("--report", str(self.tmp / "r.md"), source=bad)
        self.assertEqual(code, 1, out)
        self.assertFalse(self.out.exists())
        self.assertFalse((self.tmp / "r.md").exists())

    def test_missing_operand_is_usage(self):
        proc = subprocess.run([sys.executable, str(RENDERER)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_shared_family_name_draws_its_tie(self):
        scene = scene_of(self.page())
        self.assertEqual(scene["ties"], [{"family": "Detección multimodal de depresión",
                                          "from": "paper-1.p1-family",
                                          "to": "paper-3.p3-family"}])

    def test_systems_keep_clear_and_families_get_neighborhoods(self):
        module = load(RENDERER, "render_atlas")
        systems = [{"id": f"paper-{i}", "planets": []} for i in range(25)]
        pts = list(module._system_centers(systems).values())
        nearest = min(math.dist(a, b) for i, a in enumerate(pts) for b in pts[i + 1:])
        self.assertGreaterEqual(nearest, 600)
        owned = ([system(f"paper-{i}", "F1") for i in range(3)]
                 + [system(f"paper-{i}", "F2") for i in range(3, 6)])
        centers = module._system_centers(owned)
        groups: dict[str, list] = {}
        for sid, point in centers.items():
            groups.setdefault("F1" if int(sid.split("-")[1]) < 3 else "F2", []).append(point)
        cent = {f: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v))
                for f, v in groups.items()}
        self.assertGreater(math.dist(cent["F1"], cent["F2"]), 3000)

    def test_toolbar_carries_every_papersmith_control(self):
        page = self.page()
        toolbar = page[page.index('<div id="toolbar">'):]
        toolbar = toolbar[:toolbar.index("</div>")]
        for button in ('id="zoomin"', 'id="zoomout"', 'id="zoomreset"', 'id="grouplayout"',
                       'id="viewmode"', 'id="names"', 'id="autorotate"', 'id="spinleft"',
                       'id="spinright"', 'id="tiltup"', 'id="tiltdown"', 'id="studytoggle"'):
            self.assertIn(button, toolbar)
        script = self.page_script()
        self.assertIn("setLayout", script)
        self.assertIn("api.focus", script)

    def test_page_offers_the_2d_constellation_when_the_3d_sky_should_not_run(self):
        page = self.page()
        self.assertIn('<div id="gpunote" role="status" hidden></div>', page)
        script = self.page_script()
        for needle in ("failIfMajorPerformanceCaveat", "WEBGL_debug_renderer_info",
                       "navigator.deviceMemory", "navigator.hardwareConcurrency",
                       "get('view')", "const FlatViewer", "function watchFrameRate",
                       "< 20", "3000", "'view-2d'", "'view-3d'"):
            self.assertIn(needle, script)

    def test_page_stops_drawing_while_nobody_can_see_it(self):
        script = self.page_script()
        self.assertIn("addEventListener('visibilitychange'", script)
        self.assertIn("'pause': () => { dashboardPaused = true; applyVisibility(); }", script)
        self.assertIn("'resume': () => { dashboardPaused = false; applyVisibility(); }", script)
        self.assertIn("viewer.pause()", script)
        self.assertIn("dispose()", script)

    def test_page_answers_the_dashboard_atlas_control_message(self):
        script = self.page_script()
        self.assertIn("addEventListener('message'", script)
        self.assertIn("event.source === window.parent", script)
        self.assertIn("'atlas-control'", script)
        self.assertIn("data.cmd", script)
        # papersmith's own command channel keeps working
        self.assertIn("'atlas-command'", script)
        self.assertIn("data.command", script)
        self.assertIn("type: 'atlas-planet-selected'", script)

    def test_viewer_bundle_caps_pixel_ratio_and_draws_no_label_sprites(self):
        bundle = BUNDLE.read_text(encoding="utf-8")
        self.assertIn("Math.min(Math.max(window.devicePixelRatio||1,1),2)", bundle)
        self.assertNotIn(".title", bundle)
        for method in ("dispose(", "project(", "rotating(", "spin(", "tilt(", "refresh(",
                       "pause(", "resume(", "setLayout"):
            self.assertIn(method, bundle)


class ConstellationStudyTests(Tmp):
    def render(self, *extra):
        out = self.tmp / "atlas.html"
        proc = subprocess.run([sys.executable, str(RENDERER), str(FIXTURE_ATLAS), "--out",
                               str(out), *extra], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return out.read_text(encoding="utf-8")

    def study_panel(self, page):
        start = page.index('<aside id="study"')
        return page[start:page.index("</aside>", start)]

    def test_study_is_computed_per_family(self):
        module = load(RENDERER, "render_atlas")
        study = module.study(json.loads(FIXTURE_ATLAS.read_text(encoding="utf-8")))
        names = [f["family"] for f in study["families"]]
        self.assertEqual(names, ["Biomarcadores de voz", "Detección multimodal de depresión"])
        multimodal = study["families"][1]
        self.assertEqual([s["id"] for s in multimodal["systems"]], ["paper-1", "paper-3"])
        self.assertIn({"label": "Falta de hardware en clínicas rurales", "system": "paper-3"},
                      multimodal["problems"])
        self.assertIn({"label": "Agregación por ensamble de instancias", "system": "paper-1"},
                      multimodal["novelties"])
        self.assertIn({"label": "F1 de 0,88 en DAIC-WOZ", "system": "paper-1"},
                      multimodal["results"])
        self.assertEqual(study["relations"]["extends"], 1)
        self.assertEqual(study["relations"]["shares-family-with"], 1)
        self.assertEqual(study["relations"]["contradicts"], 0)
        origins = {e["origin"] for e in study["evidence"]}
        self.assertEqual(origins, {"https://doi.org/10.1000/fixture.1",
                                   "https://doi.org/10.1000/fixture.2",
                                   "https://arxiv.org/abs/2501.00003"})

    def test_study_orders_paper_ids_naturally(self):
        module = load(RENDERER, "render_atlas")
        doc = atlas(systems=[system("paper-10", "F"), system("paper-2", "F")])
        study = module.study(doc)
        self.assertEqual([s["id"] for s in study["families"][0]["systems"]],
                         ["paper-2", "paper-10"])

    def test_page_carries_a_collapsible_study_panel(self):
        page = self.render()
        panel = self.study_panel(page)
        self.assertIn("Estudio de constelaciones", panel)
        self.assertIn("Familia: Detección multimodal de depresión", panel)
        self.assertIn("Edge inference for mental health screening on low-cost devices", panel)
        self.assertIn("Falta de hardware en clínicas rurales", panel)
        self.assertIn("Marcadores acústicos de trauma", panel)
        self.assertIn("AUC de 0,81 en cohorte externa", panel)
        self.assertIn("Relaciones por tipo", panel)
        self.assertIn("https://arxiv.org/abs/2501.00003", panel)
        self.assertIn("2026-10-20", panel)
        self.assertIn("#e65a5a", panel)  # problem slot color
        self.assertIn('id="studytoggle"', page)
        self.assertIn("aria-expanded", page)

    def test_study_panel_escapes_markup(self):
        doc = json.loads(FIXTURE_ATLAS.read_text(encoding="utf-8"))
        doc["systems"][0]["planets"][3]["label"] = "<b>bold</b>"
        source = self.tmp / "atlas.json"
        source.write_text(json.dumps(doc), encoding="utf-8")
        out = self.tmp / "x.html"
        subprocess.run([sys.executable, str(RENDERER), str(source), "--out", str(out)],
                       check=True, capture_output=True)
        panel = self.study_panel(out.read_text(encoding="utf-8"))
        self.assertNotIn("<b>bold</b>", panel)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", panel)

    def test_markdown_report_carries_the_same_study(self):
        report = self.tmp / "report.md"
        self.render("--report", str(report))
        text = report.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Estudio de constelaciones"))
        self.assertIn("### Familia: Biomarcadores de voz", text)
        self.assertIn("### Familia: Detección multimodal de depresión", text)
        self.assertLess(text.index("### Familia: Biomarcadores de voz"),
                        text.index("### Familia: Detección multimodal de depresión"))
        for heading in ("- Problemas:", "- Novedades:", "- Resultados:",
                        "## Relaciones por tipo", "## Evidencias"):
            self.assertIn(heading, text)
        self.assertIn("Falta de hardware en clínicas rurales (paper-3)", text)
        self.assertIn("- extends: 1", text)
        self.assertIn("https://doi.org/10.1000/fixture.2", text)
        self.assertNotIn(" — ", text)
        self.assertNotIn("--", text)


class BuildManuscriptGraphTests(Tmp):
    def make_run(self, with_atlas: bool) -> Path:
        run = self.tmp / "2026-10-demo"
        papers = run / "artefactos" / "scoping" / "papers"
        shutil.copytree(FIXTURE_PAPERS, papers)
        (run / "grafos").mkdir(parents=True)
        if with_atlas:
            shutil.copy(FIXTURE_ATLAS, run / "artefactos" / "scoping" / "atlas.json")
        return run

    def builder(self):
        return load(BUILDER, "build_manuscript_graph_under_test")

    def test_atlas_present_renders_the_constellation(self):
        run = self.make_run(with_atlas=True)
        result = self.builder().build_papers_graph(run)
        page = (run / "grafos" / "papers-graph.html").read_text(encoding="utf-8")
        self.assertIn(DATA_OPEN, page)
        self.assertIn("Estudio de constelaciones", page)
        report = (run / "grafos" / "papers-constellation-report.md").read_text(encoding="utf-8")
        self.assertIn("### Familia: Biomarcadores de voz", report)
        self.assertEqual(result.get("source"), "atlas")
        self.assertFalse((run / "grafos" / "papers-graph.json").exists())

    def test_atlas_absent_keeps_the_legacy_graph(self):
        run = self.make_run(with_atlas=False)
        self.builder().build_papers_graph(run)
        self.assertTrue((run / "grafos" / "papers-graph.json").is_file())
        self.assertFalse((run / "grafos" / "papers-constellation-report.md").exists())
        html_path = run / "grafos" / "papers-graph.html"
        if html_path.exists():
            self.assertNotIn(DATA_OPEN, html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
