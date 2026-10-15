"""Contrato estructural del visor PDF del Command Center.

El visor es JavaScript en línea dentro de un único HTML, así que ninguna prueba
unitaria puede fijar su comportamiento en tiempo de ejecución: eso se verifica
en un navegador. Estas aserciones fijan el contrato que la tira continua debe
cumplir y las piezas del visor anterior que no pueden desaparecer con la
reescritura. Una prueba que solo mira cadenas atrapa una regresión de estructura,
nunca una de comportamiento; su límite está declarado a propósito.
"""

from __future__ import annotations

import unittest
from pathlib import Path

INDEX = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "morfeo"
    / "dashboard"
    / "static"
    / "index.html"
)

LEGACY_SINGLETON_NODES = (
    'id="pdfPageContainer"',
    'id="pdfCanvas"',
    'id="pdfTextLayer"',
    'id="pdfAnnotationsLayer"',
)

PER_PAGE_HELPERS = (
    "function getPageSlot(",
    "function getPageEl(",
    "function getPageCanvas(",
    "function getPageTextLayer(",
    "function getPageAnnotLayer(",
)

EDITORIAL_TOOLS = (
    "function triggerAddComment(",
    "function triggerStrikethrough(",
    "function triggerHumanize(",
    "function renderAnnotationsTray(",
    "function clearAllAnnotations(",
    "function executeQueuedChanges(",
    "function removeAnnotation(",
)

VIEWER_CONTROLS = (
    "function zoomPdf(",
    "function resetZoomPdf(",
    "function toggleNativeViewer(",
    "function initPdfViewer(",
)

MARK_COUNTERS = (
    'id="marksCountStrike"',
    'id="marksCountComment"',
    'id="marksCountHumanize"',
    'id="marksCountAll"',
)


class TestDashboardViewerContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = INDEX.read_text(encoding="utf-8")

    # Aserciones compactas: un assertIn sobre el HTML completo escupe el archivo
    # entero en el mensaje de fallo y vuelve ilegible la salida de la suite.
    def assertPresent(self, needle: str) -> None:
        self.assertTrue(needle in self.html, f"falta {needle!r} en index.html")

    def assertAbsent(self, needle: str, why: str = "") -> None:
        self.assertTrue(needle not in self.html, f"sobra {needle!r}. {why}".strip())

    def test_index_ships_and_is_readable(self) -> None:
        self.assertTrue(INDEX.is_file(), f"falta el tablero: {INDEX}")
        self.assertGreater(len(self.html), 50_000)

    # --- Tira continua de páginas (S1, S2, S3) -----------------------------
    def test_continuous_strip_container_exists(self) -> None:
        self.assertPresent('id="pdfPagesStrip"')

    def test_single_page_viewer_markup_is_gone(self) -> None:
        for node in LEGACY_SINGLETON_NODES:
            self.assertAbsent(node, "sobrevive del visor de una sola página")

    def test_each_page_carries_its_number_and_renders_lazily(self) -> None:
        # `dataset.pageNumber` produce el atributo `data-page-number` en tiempo
        # de ejecución; buscarlo literal en el HTML nunca lo encontraría.
        self.assertPresent("dataset.pageNumber")
        self.assertPresent("new IntersectionObserver(")
        self.assertPresent("function renderPageInto(")

    def test_pages_are_addressed_by_number_not_by_singleton_id(self) -> None:
        for helper in PER_PAGE_HELPERS:
            self.assertPresent(helper)

    def test_navigation_scrolls_the_strip_instead_of_repainting_one_canvas(
        self,
    ) -> None:
        self.assertPresent("function scrollToPdfPage(")
        self.assertPresent("function changePdfPage(")
        self.assertPresent("function goToPdfPage(")

    def test_strip_scroll_updates_the_current_page(self) -> None:
        self.assertPresent("function onStripScroll(")
        self.assertPresent("function syncCurrentPageFromScroll(")
        self.assertPresent("strip.addEventListener('scroll'")

    # --- Barra interactiva nueva (S4, S6) ----------------------------------
    def test_interaction_bar_is_materialized_in_markup(self) -> None:
        self.assertPresent('id="pdfSelectionInfoText"')
        self.assertPresent('id="selectionActionsQuick"')
        self.assertPresent('id="pdfInteractionBar"')

    def test_deselect_control_exists(self) -> None:
        self.assertPresent('id="btnClearSelection"')
        self.assertPresent("function deselectPdfText(")

    def test_marks_can_be_removed_per_type(self) -> None:
        self.assertPresent("function removeAnnotationsByType(")
        for counter in MARK_COUNTERS:
            self.assertPresent(counter)

    def test_marks_menu_offers_each_type_and_all(self) -> None:
        for call in (
            "removeAnnotationsByType('strikethrough')",
            "removeAnnotationsByType('comment')",
            "removeAnnotationsByType('humanize')",
        ):
            self.assertPresent(call)
        self.assertPresent('id="marksMenuPanel"')
        self.assertPresent("function toggleMarksMenu(")
        self.assertPresent("function closeMarksMenu(")

    # --- Comportamiento anterior que debe sobrevivir (S5) -----------------
    def test_editorial_tools_and_side_panel_survive(self) -> None:
        for fn in EDITORIAL_TOOLS:
            self.assertPresent(fn)
        self.assertPresent('id="annotsList"')
        self.assertPresent('id="pdfControlPanel"')

    def test_viewer_controls_survive(self) -> None:
        for fn in VIEWER_CONTROLS:
            self.assertPresent(fn)

    def test_keyboard_navigation_survives(self) -> None:
        self.assertPresent("'ArrowRight'")
        self.assertPresent("'PageDown'")
        self.assertPresent("changePdfPage(e.shiftKey")

    def test_lazy_rendering_is_bounded_on_memory(self) -> None:
        # Un canvas por página son varios megabytes: sin desalojo, recorrer el
        # manuscrito entero acumularía una decena de ellos.
        self.assertPresent("function evictDistantPages(")
        self.assertPresent("function releasePage(")
        self.assertPresent("canvas.width = 0")
        self.assertPresent("const PDF_KEEP_RENDERED = 6;")

    def test_scale_application_is_serialized(self) -> None:
        # Sin la cadena, dos cambios de zoom solapados dejan un mismo canvas con
        # dos render() en vuelo y PDF.js lanza "Cannot use the same canvas during
        # multiple render() operations".
        self.assertPresent("let scaleApplyChain = Promise.resolve();")
        self.assertPresent("await Promise.allSettled(Array.from(pdfPendingRenders.values()))")
        self.assertPresent("--scale-factor")
        # Vaciar los conjuntos sin liberar los mapas de bits dejaba canvas
        # pintados fuera de todo seguimiento, y el desalojo ya no podía verlos.
        self.assertPresent("Array.from(pdfRenderedPages).forEach(releasePage);")

    def test_annotations_are_scoped_to_their_page(self) -> None:
        self.assertPresent("function renderAnnotationsForPage(")
        self.assertPresent("function findTextRectsInPage(")
        self.assertAbsent(
            "function renderPdfAnnotationsOverlay(",
            "el overlay de una sola página ya no existe",
        )

    def test_pdf_is_still_served_and_downloadable(self) -> None:
        self.assertPresent("/api/pdf")
        self.assertPresent('href="/api/pdf" download')

    def test_native_viewer_fallback_survives(self) -> None:
        self.assertPresent('id="pdfNativeIframe"')
        self.assertPresent('id="pdfLoadingSpinner"')


if __name__ == "__main__":
    unittest.main()
