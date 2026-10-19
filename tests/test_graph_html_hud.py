"""HUD and camera contract of the 3D graph page.

The legend used to float open over the top-left corner of the canvas and cover
nodes; the camera started at a fixed distance whatever the graph size; and a
drag released outside the dashboard iframe never ended. The page is inline
JavaScript, so these assertions pin structure only: runtime behavior is
verified in a browser.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import graph_html  # noqa: E402

MINIMAL_DATA = {
    "corpus": "demo",
    "title": "Demo",
    "index": {"freshness": "", "project": "demo", "nodes": 1, "edges": 0},
}


def _page() -> str:
    empty = lambda *a, **k: ""  # noqa: E731
    with mock.patch.multiple(
        graph_html,
        render_central=empty,
        render_communities=empty,
        render_questions=empty,
        render_payload=empty,
    ):
        return graph_html.build_html(MINIMAL_DATA)


class TestGraphHud(unittest.TestCase):
    def setUp(self) -> None:
        self.page = _page()

    def test_legend_is_a_collapsible_panel_closed_by_default(self) -> None:
        match = re.search(r"<details[^>]*id=\"hudLegend\"[^>]*>", self.page)
        self.assertIsNotNone(match, "the legend must be a <details id=\"hudLegend\">")
        self.assertNotIn(" open", match.group(0), "the legend must start collapsed")
        legend = self.page[match.start():self.page.index("</details>", match.start())]
        self.assertIn('id="clusterFilterTags"', legend, "cluster filters belong inside the legend")
        self.assertIn("Pasa el cursor", legend, "the usage hint belongs inside the legend")

    def test_camera_fits_the_graph_on_load_and_on_reset(self) -> None:
        self.assertTrue("function fitCameraToGraph(" in self.page, "fitCameraToGraph is missing")
        reset = self.page[self.page.index("window.resetCamera"):]
        reset = reset[: reset.index("};")]
        self.assertIn("fitCameraToGraph(", reset, "Centrar must refit to the graph bounds")

    def test_drag_uses_pointer_capture(self) -> None:
        self.assertTrue('addEventListener("pointerdown"' in self.page, "no pointerdown handler")
        self.assertTrue("setPointerCapture(" in self.page, "drag does not capture the pointer")
        self.assertFalse('window.addEventListener("mouseup"' in self.page, "drag still ends on window mouseup")

    def test_community_filters_toggle_independently(self) -> None:
        self.assertTrue("activeClusters = new Set()" in self.page, "filters must hold a set of communities")
        self.assertFalse("activeClusterFilter" in self.page, "a single-community filter remains")
        self.assertTrue("window.clearClusterFilters = function" in self.page, "no way to clear every filter")

    def test_previous_controls_still_exist(self) -> None:
        for control in ("toggleAutoRotate", "resetCamera", "toggleSidebar", "handleSearch", "focusCameraOnSelected"):
            self.assertTrue(f"window.{control} = function" in self.page, f"{control} is missing")


if __name__ == "__main__":
    unittest.main()
