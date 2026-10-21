"""2D/3D view choice and constellation look of the graph page.

Ported from the Banco LIA constellation: the page draws in 3D only when the
browser offers a WebGL context without a major performance caveat and the
machine reports enough memory and cores; otherwise it opens the 2D
constellation, which draws on a plain canvas and only when something changes.
The decision function is pure, so it runs under node; the rest pins structure,
since WebGL does not run headless here.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import graph_html  # noqa: E402

TEMPLATE = graph_html.TEMPLATE


def view_mode_source() -> str:
    match = re.search(r"// view-mode:begin\n(.*?)// view-mode:end", TEMPLATE, re.S)
    assert match, "chooseViewMode block not found"
    return match.group(1)


def choose(**env) -> dict:
    script = view_mode_source() + "\nprocess.stdout.write(JSON.stringify(chooseViewMode(" + json.dumps(env) + ")));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class ChooseViewModeTest(unittest.TestCase):
    def test_a_capable_machine_opens_in_3d(self) -> None:
        self.assertEqual(choose(search="", saved="", gl="ok", memory=8, cores=8), {"mode": "3d", "reason": "gpu"})

    def test_no_webgl_opens_in_2d_and_cannot_be_forced_to_3d(self) -> None:
        self.assertEqual(choose(search="", saved="", gl="none", memory=8, cores=8)["mode"], "2d")
        self.assertEqual(choose(search="?view=3d", saved="3d", gl="none", memory=8, cores=8), {"mode": "2d", "reason": "none"})

    def test_a_weak_gpu_or_few_resources_open_in_2d(self) -> None:
        self.assertEqual(choose(search="", saved="", gl="weak", memory=8, cores=8), {"mode": "2d", "reason": "weak"})
        self.assertEqual(choose(search="", saved="", gl="ok", memory=2, cores=8), {"mode": "2d", "reason": "resources"})
        self.assertEqual(choose(search="", saved="", gl="ok", memory=8, cores=2), {"mode": "2d", "reason": "resources"})

    def test_a_very_large_graph_opens_in_2d_unless_asked(self) -> None:
        self.assertEqual(choose(search="", saved="", gl="ok", memory=8, cores=8, nodes=2000), {"mode": "2d", "reason": "large"})
        self.assertEqual(choose(search="", saved="", gl="ok", memory=8, cores=8, nodes=1500)["mode"], "3d")
        self.assertEqual(choose(search="", saved="3d", gl="ok", memory=8, cores=8, nodes=2000)["mode"], "3d")

    def test_unknown_resources_do_not_force_2d(self) -> None:
        self.assertEqual(choose(search="", saved="", gl="ok", memory=None, cores=None)["mode"], "3d")

    def test_the_url_and_the_saved_choice_win_over_the_heuristics(self) -> None:
        self.assertEqual(choose(search="?view=2d", saved="", gl="ok", memory=8, cores=8), {"mode": "2d", "reason": "url"})
        self.assertEqual(choose(search="?x=1&view=3D", saved="", gl="weak", memory=2, cores=2), {"mode": "3d", "reason": "url"})
        self.assertEqual(choose(search="", saved="2d", gl="ok", memory=8, cores=8), {"mode": "2d", "reason": "user"})
        self.assertEqual(choose(search="", saved="3d", gl="weak", memory=2, cores=2), {"mode": "3d", "reason": "user"})


class GraphViewStructureTest(unittest.TestCase):
    def test_the_probe_asks_for_a_context_without_performance_caveat_and_releases_it(self) -> None:
        self.assertIn("failIfMajorPerformanceCaveat: true", TEMPLATE)
        self.assertIn("WEBGL_lose_context", TEMPLATE)
        self.assertIn("navigator.deviceMemory", TEMPLATE)
        self.assertIn("navigator.hardwareConcurrency", TEMPLATE)

    def test_the_header_offers_the_view_and_names_toggles(self) -> None:
        self.assertIn('id="btnViewMode"', TEMPLATE)
        self.assertIn('id="btnNames"', TEMPLATE)
        self.assertIn('id="viewNote"', TEMPLATE)

    def test_leaving_3d_frees_the_webgl_context(self) -> None:
        body = re.search(r"function setViewMode\(.*?\n  \}\n", TEMPLATE, re.S).group(0)
        self.assertIn(".dispose()", body)
        self.assertIn(".forceContextLoss()", body)

    def test_halos_share_one_texture(self) -> None:
        self.assertEqual(TEMPLATE.count("createGlowTexture("), 2)  # definition and one call
        self.assertIn("var glowTexture = createGlowTexture()", TEMPLATE)

    def test_pixel_ratio_never_drops_below_one(self) -> None:
        self.assertIn("Math.min(Math.max(window.devicePixelRatio || 1, 1), 2)", TEMPLATE)

    def test_an_idle_still_view_skips_the_frame(self) -> None:
        body = re.search(r"function animate\(\) \{.*?\n  \}\n", TEMPLATE, re.S).group(0)
        self.assertIn("!autoRotate && !frameDirty && !cameraMoving", body)

    def test_constellation_names_have_a_budget_and_reject_overlaps(self) -> None:
        body = re.search(r"function placeNames\(.*?\n  \}\n", TEMPLATE, re.S).group(0)
        self.assertIn("Math.floor(w * h / 12000)", body)
        self.assertIn("overlaps", body)

    def test_the_starfield_is_deterministic(self) -> None:
        stars = re.search(r"function addStarfield\(.*?\n  \}\n", TEMPLATE, re.S).group(0)
        self.assertNotIn("Math.random", stars)

    def test_the_kit_copy_matches(self) -> None:
        kit = REPO / "src" / "morfeo" / "_kit" / "scripts" / "graph_html.py"
        self.assertEqual(kit.read_text(encoding="utf-8"), (REPO / "scripts" / "graph_html.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
