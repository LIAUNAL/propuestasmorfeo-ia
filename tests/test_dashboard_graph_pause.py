"""The dashboard pauses the graph iframe while its tab is not shown.

Ported from papersmith-ai's command center (commit fc19c4b1): the graph iframe
starts at about:blank and loads the first time the graph tab opens; from then on
the dashboard posts ``{"type": "atlas-control", "cmd": "pause"}`` to it when the
tab is hidden (another tab, or the dashboard page itself hidden) and ``resume``
when it is shown again. ``syncGraphPause`` runs under node with stubbed globals;
its wiring into navigation, page visibility and iframe load is pinned
structurally.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HTML = (REPO / "src" / "morfeo" / "dashboard" / "static" / "index.html").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _slice(start: str, end: str) -> str:
    i = HTML.index(start)
    return HTML[i : HTML.index(end, i)]


HARNESS = """
const input = JSON.parse(process.argv[1]);
const posted = [];
let activeTab = input.tab;
const iframe = {
  getAttribute: (k) => (k === 'src' ? input.src : null),
  contentWindow: { postMessage: (data, origin) => posted.push(data) },
};
const document = { hidden: input.hidden, getElementById: (id) => (id === 'graphIframe' ? iframe : null) };
%s
syncGraphPause();
console.log(JSON.stringify(posted));
"""


def posted(tab: str, src: str = "/api/graph/papers", hidden: bool = False) -> list:
    script = HARNESS % (_slice("function syncGraphPause(", "\n    }\n") + "\n    }\n")
    payload = json.dumps({"tab": tab, "src": src, "hidden": hidden})
    out = subprocess.run([NODE, "-e", script, payload], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(NODE, "node not installed")
class SyncGraphPauseTest(unittest.TestCase):
    def test_showing_the_graph_tab_resumes(self) -> None:
        self.assertEqual(posted("atlas"), [{"type": "atlas-control", "cmd": "resume"}])

    def test_another_tab_pauses(self) -> None:
        self.assertEqual(posted("flow"), [{"type": "atlas-control", "cmd": "pause"}])

    def test_a_hidden_dashboard_pauses_even_on_the_graph_tab(self) -> None:
        self.assertEqual(posted("atlas", hidden=True), [{"type": "atlas-control", "cmd": "pause"}])

    def test_an_unloaded_iframe_gets_nothing(self) -> None:
        self.assertEqual(posted("flow", src="about:blank"), [])
        self.assertEqual(posted("atlas", src=""), [])


class GraphPauseWiringTest(unittest.TestCase):
    def test_the_iframe_still_loads_lazily(self) -> None:
        tag = re.search(r'<iframe id="graphIframe"[^>]*>', HTML).group(0)
        self.assertIn('src="about:blank"', tag)
        # A page loaded while its tab is hidden is told to pause right away.
        self.assertIn('onload="syncGraphPause()"', tag)
        nav = _slice("function navigateTab(", "let currentGraphKind")
        atlas = nav[nav.index("tabId === 'atlas'"):]
        self.assertIn("iframe.src = `/api/graph/${currentGraphKind}`;", atlas)

    def test_navigation_syncs_the_pause_after_switching(self) -> None:
        nav = _slice("function navigateTab(", "let currentGraphKind")
        self.assertLess(nav.index("activeTab = tabId;"), nav.index("syncGraphPause();"))

    def test_page_visibility_syncs_the_pause(self) -> None:
        listener = _slice("document.addEventListener('visibilitychange', () => {", "window.addEventListener('focus'")
        self.assertIn("syncGraphPause();", listener)


if __name__ == "__main__":
    unittest.main()
