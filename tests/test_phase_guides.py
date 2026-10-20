"""Every pipeline unit has a guide in the dashboard's execution modal.

The «Ejecutar» modal shows, per unit, the guidance for what the operator can
write for the command and, when the unit has its own panel, a link to it. A
unit added to the inventory without a guide would open an empty box.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from morfeo.core.pipeline_units import PIPELINE_UNITS

INDEX = Path(__file__).resolve().parent.parent / "src" / "morfeo" / "dashboard" / "static" / "index.html"
PANELS = {"pipeline", "trees", "mga", "sections", "atlas", "preview", "artifacts", "telemetria", "flow"}


class PhaseGuidesTest(unittest.TestCase):
    def setUp(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        start = html.index("const PHASE_GUIDES = {")
        self.block = html[start:html.index("\n    };", start)]

    def test_every_unit_has_a_guide_with_a_placeholder(self) -> None:
        for unit in PIPELINE_UNITS:
            entry = re.search(rf"^\s+{unit['id']}: \{{(.*?)\}},?$", self.block, re.M | re.S)
            self.assertIsNotNone(entry, f"{unit['id']} has no guide")
            self.assertIn("placeholder:", entry.group(1), unit["id"])

    def test_panels_point_to_existing_tabs(self) -> None:
        for panel in re.findall(r"tab: '([a-z]+)'", self.block):
            self.assertIn(panel, PANELS)


if __name__ == "__main__":
    unittest.main()
