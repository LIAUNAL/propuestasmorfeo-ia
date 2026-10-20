"""`/api/idea` hands the dashboard the project's initial idea for the intake.

The Intake card launches `/propuesta-analizar <idea>`; the idea comes from the
project's `idea.md` (or the active run's `insumos/ideas/idea.md`). The template
`morfeo init` writes has only headings and HTML comments, which is no idea.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from morfeo.dashboard.server import MorfeoDashboardHandler

TEMPLATE = """# Idea de propuesta

## Problema
<!-- Describe el problema u oportunidad que aborda la propuesta -->

## Enfoque
<!-- Describe el enfoque de solución propuesto -->
"""


class IdeaEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": self.root})
        handler.log_message = lambda *a, **k: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.url = f"http://127.0.0.1:{server.server_address[1]}/api/idea"

    def _get(self) -> dict:
        with urllib.request.urlopen(self.url) as res:
            return json.loads(res.read())

    def test_template_only_is_no_idea(self) -> None:
        (self.root / "idea.md").write_text(TEMPLATE, encoding="utf-8")
        self.assertEqual(self._get(), {"ok": True, "text": "", "source": None})

    def test_filled_sections_flatten_into_one_line(self) -> None:
        (self.root / "idea.md").write_text(
            TEMPLATE.replace("<!-- Describe el problema u oportunidad que aborda la propuesta -->",
                             "Baja cobertura del monitoreo\nhídrico en Caldas.")
            .replace("<!-- Describe el enfoque de solución propuesto -->", "Sensores e IA."),
            encoding="utf-8")
        self.assertEqual(self._get(), {
            "ok": True,
            "text": "Problema: Baja cobertura del monitoreo hídrico en Caldas. Enfoque: Sensores e IA.",
            "source": "idea.md",
        })

    def test_missing_file_is_no_idea(self) -> None:
        self.assertEqual(self._get(), {"ok": True, "text": "", "source": None})


if __name__ == "__main__":
    unittest.main()
