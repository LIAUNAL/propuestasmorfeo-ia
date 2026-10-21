"""The 3D graph draws nothing while it is not visible.

The dashboard keeps the graph iframe in a hidden tab, and the loop used to draw
every frame anyway: WebGL work for a page nobody sees. The render loop now
returns before drawing when the page is hidden or its stage has no size, and
the idle auto-rotation draws at 30 fps. WebGL does not run under jsdom, so this
pins the guards in the generated loop structurally; the CPU effect is measured
in odd/tasks/tablero-recursos.md.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import graph_html  # noqa: E402


def animate_body() -> str:
    source = (REPO / "scripts" / "graph_html.py").read_text(encoding="utf-8")
    match = re.search(r"function animate\(\) \{(.*?)\n  \}\n", source, re.S)
    assert match, "animate() not found"
    return match.group(1)


class GraphRenderLoopIdleTest(unittest.TestCase):
    def test_a_hidden_page_or_an_empty_stage_returns_before_drawing(self) -> None:
        body = animate_body()
        guard = body.index("document.hidden")
        self.assertIn("stageEl.clientWidth === 0", body[guard:guard + 200])
        self.assertLess(guard, body.index("renderer.render"), "the guard must come before the draw")
        self.assertLess(body.index("requestAnimationFrame(animate)"), guard, "the loop keeps scheduling itself")

    def test_idle_rotation_is_capped_and_keeps_its_speed(self) -> None:
        body = animate_body()
        self.assertIn("IDLE_FRAME_SEC", body)
        self.assertRegex(body, r"busy = isDragging \|\| hoveredNode \|\| selectedNode")
        self.assertIn("spherical.theta += 0.0035 * spin", body)

    def test_the_kit_copy_matches(self) -> None:
        kit = REPO / "src" / "morfeo" / "_kit" / "scripts" / "graph_html.py"
        self.assertEqual(kit.read_text(encoding="utf-8"), (REPO / "scripts" / "graph_html.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
