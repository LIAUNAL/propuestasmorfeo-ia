"""Graph builder resolution for the Command Center.

A portable project keeps its own copy of ``scripts/`` from the kit version it
was created with. The dashboard must render graphs with the builder bundled in
the installed package, so an upgrade reaches the Grafos tab without re-syncing
every project; the workspace copy is only a fallback.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from morfeo.dashboard.server import MorfeoDashboardHandler

KIT_SCRIPTS = (
    Path(__file__).resolve().parent.parent / "src" / "morfeo" / "_kit" / "scripts"
)


def _handler(workspace: Path) -> MorfeoDashboardHandler:
    handler = MorfeoDashboardHandler.__new__(MorfeoDashboardHandler)
    handler.workspace_dir = workspace
    return handler


class GraphScriptsResolutionTest(unittest.TestCase):
    def test_prefers_packaged_kit_over_stale_workspace_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "scripts").mkdir()
            (workspace / "scripts" / "build_manuscript_graph.py").write_text("# stale v0.5.0\n")

            resolved = _handler(workspace)._resolve_scripts_dir()

            self.assertEqual(resolved.resolve(), KIT_SCRIPTS.resolve())

    def test_workspace_without_scripts_uses_packaged_kit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resolved = _handler(Path(tmp))._resolve_scripts_dir()

            self.assertTrue((resolved / "build_manuscript_graph.py").is_file())
            self.assertTrue((resolved / "graph_html.py").is_file())


if __name__ == "__main__":
    unittest.main()
