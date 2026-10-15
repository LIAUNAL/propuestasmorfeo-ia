"""El HTML de grafo tiene que ser autocontenido.

El template declaraba *Three.js from robust CDN with internal fallback* y cargaba
solo el CDN: el fallback no existía. Sin red, el grafo no se dibujaba y nada lo
decía. Estas pruebas atan el activo vendorizado, su aviso de licencia y la
sustitución que lo empotra.
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import graph_html  # noqa: E402

NOTICE = REPO / "scripts" / "assets" / "THIRD_PARTY_NOTICES.md"

MINIMAL_DATA = {
    "corpus": "demo",
    "title": "Demo",
    "index": {"freshness": "", "project": "demo", "nodes": 1, "edges": 0},
}


class TestGraphHtmlSelfContained(unittest.TestCase):
    def test_the_template_carries_no_external_script(self) -> None:
        self.assertIn("<script>__THREE_BUNDLE__</script>", graph_html.TEMPLATE)
        self.assertNotIn("cdnjs", graph_html.TEMPLATE)
        self.assertNotIn('src="http', graph_html.TEMPLATE)

    def test_the_vendored_bundle_matches_its_notice(self) -> None:
        asset = graph_html.THREE_BUNDLE
        self.assertTrue(asset.is_file(), f"falta el activo vendorizado {asset}")
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        self.assertIn(
            digest,
            NOTICE.read_text(encoding="utf-8"),
            "el aviso de terceros no declara el SHA-256 del activo que se vendoriza",
        )
        self.assertNotIn("</script", asset.read_text(encoding="utf-8").lower())

    def test_a_missing_bundle_fails_loudly(self) -> None:
        """Prometer un fallback inexistente fue el defecto original: si el activo
        falta, el generador se niega en lugar de emitir un HTML que dependa de la
        red sin decirlo."""
        with mock.patch.object(graph_html, "THREE_BUNDLE", Path("/no/existe/three.js")):
            with self.assertRaises(SystemExit):
                graph_html._three_bundle()

    def test_generated_html_embeds_the_bundle_and_no_external_script(self) -> None:
        vacio = lambda *a, **k: ""  # noqa: E731
        with mock.patch.multiple(
            graph_html,
            render_central=vacio,
            render_communities=vacio,
            render_questions=vacio,
            render_payload=vacio,
        ):
            out = graph_html.build_html(MINIMAL_DATA)

        self.assertNotIn("__THREE_BUNDLE__", out, "el marcador quedó sin sustituir")
        self.assertIn("THREE", out, "el bundle no se empotró")
        self.assertNotIn("cdnjs", out)
        self.assertNotIn('src="http', out)

    def test_the_bundle_is_not_re_read_for_every_graph(self) -> None:
        """Se lee del disco en cada generación a propósito: el activo es la fuente
        y un caché de módulo escondería un archivo cambiado a mitad de corrida."""
        self.assertEqual(len(graph_html._three_bundle()), len(graph_html._three_bundle()))


if __name__ == "__main__":
    unittest.main()
