"""The dashboard always shows the Morfeo logo and tab icon.

Other local tools (PaperSmith, for one) also run on 127.0.0.1 and serve their
own /favicon.ico and /favicon.png. A browser that cached one of those for a
port shows the wrong icon on a Morfeo dashboard later opened on that port, so
Morfeo's icon URLs carry their own cache key and are revalidated on each load.
"""

from __future__ import annotations

import re
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from morfeo.dashboard.server import MorfeoDashboardHandler

STATIC = Path(__file__).resolve().parent.parent / "src" / "morfeo" / "dashboard" / "static"
INDEX = STATIC / "index.html"


class BrandingTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": Path(tmp.name)})
        handler.log_message = lambda *a, **k: None
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def _refs(self) -> list[str]:
        html = INDEX.read_text(encoding="utf-8")
        icons = re.findall(r'<link rel="(?:shortcut )?icon"[^>]*href="([^"]+)"', html)
        logos = re.findall(r'<img src="([^"]*morfeo-logo[^"]*)"', html)
        self.assertTrue(icons and logos)
        return icons + logos

    def test_icon_and_logo_urls_carry_a_morfeo_cache_key(self) -> None:
        for ref in self._refs():
            self.assertIn("?app=morfeo", ref, ref)

    def test_each_reference_serves_the_morfeo_bytes_and_revalidates(self) -> None:
        expected = {
            "favicon.ico": (STATIC / "favicon.ico").read_bytes(),
            "favicon.png": (STATIC / "favicon.png").read_bytes(),
            "morfeo-logo.png": (STATIC / "morfeo-logo.png").read_bytes(),
        }
        for ref in self._refs():
            with urllib.request.urlopen(self.base + ref) as res:
                name = ref.split("?")[0].rsplit("/", 1)[-1]
                self.assertEqual(res.read(), expected[name], ref)
                self.assertIn("no-cache", res.headers["Cache-Control"], ref)

    def test_the_bare_favicon_paths_still_answer(self) -> None:
        for path in ("/favicon.ico", "/favicon.png"):
            with urllib.request.urlopen(self.base + path) as res:
                self.assertEqual(res.status, 200)


if __name__ == "__main__":
    unittest.main()
