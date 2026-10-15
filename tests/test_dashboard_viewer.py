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

    def test_in_flight_renders_are_cancelled_and_invalidated(self) -> None:
        # La verificación independiente falsó esta garantía: esperar los renders
        # en vuelo no bastaba, porque un scroll durante la espera arrancaba otro
        # render sobre el mismo canvas. Sostienen la garantía tres piezas: la
        # cancelación por página, el bloqueo mientras se aplica la escala y la
        # generación que descarta la tarea que aún no había pintado.
        self.assertPresent("const pdfRenderTasks = new Map();")
        self.assertPresent("function cancelPageRender(")
        self.assertPresent("function cancelAllPageRenders(")
        self.assertPresent("const renderTask = page.render(")
        self.assertPresent("pdfRenderTasks.set(n, renderTask);")
        self.assertPresent("let pdfScaleApplying = false;")
        self.assertPresent("if (pdfScaleApplying) return Promise.resolve();")
        self.assertPresent("let pdfRenderGeneration = 0;")
        self.assertPresent("if (generation !== pdfRenderGeneration) return;")
        # Una tarea vieja no puede borrar el registro de la nueva.
        self.assertPresent("if (pdfPendingRenders.get(n) === task) {")
        self.assertPresent("pdfPendingRenders.delete(n);")
        # Un canvas pintado y no registrado sería invisible para el desalojo:
        # toda salida posterior a pintar tiene que liberarlo, y solo el descarte
        # previo a pintar puede ser seco.
        self.assertEqual(
            self.html.count("if (generation !== pdfRenderGeneration) return;"),
            1,
            "solo el descarte previo a pintar puede ser seco",
        )
        self.assertEqual(
            self.html.count("if (generation !== pdfRenderGeneration) { releasePage(n); return; }"),
            3,
            "las tres salidas posteriores a pintar liberan el canvas",
        )
        # Cancelada o fallida sin registrarse: el finally también libera.
        self.assertPresent("if (!pdfRenderedPages.has(n)) releasePage(n);")

    def test_reload_releases_the_dom_before_dropping_the_tracking(self) -> None:
        # Vaciar los conjuntos sin vaciar el DOM dejaba los canvas viejos sin
        # dueño, y el desalojo ya no podía liberarlos.
        self.assertPresent("cancelAllPageRenders();")
        self.assertPresent("if (strip) strip.innerHTML = '';")
        self.assertPresent("pdfRenderGeneration += 1;")

    def test_scale_application_is_serialized(self) -> None:
        # Sin la cadena, dos cambios de zoom solapados dejan un mismo canvas con
        # dos render() en vuelo y PDF.js lanza "Cannot use the same canvas during
        # multiple render() operations".
        self.assertPresent("let scaleApplyChain = Promise.resolve();")
        self.assertPresent("await Promise.allSettled(Array.from(pdfPendingRenders.values()))")
        # Una sola fuente de verdad para --scale-factor: la propia capa de texto,
        # fijada con el viewport que se está pintando. En la tira no sirve, porque
        # zoomPdf cambia pdfScale antes de que su debounce aplique la escala.
        self.assertPresent("textLayerDiv.style.setProperty('--scale-factor', String(viewport.scale));")
        self.assertAbsent(
            "strip.style.setProperty('--scale-factor'",
            "la variable vive en la capa de texto, no en la tira",
        )

    def test_annotations_are_scoped_to_their_page(self) -> None:
        self.assertPresent("function renderAnnotationsForPage(")
        self.assertPresent("function findTextRectsInPage(")
        self.assertAbsent(
            "function renderPdfAnnotationsOverlay(",
            "el overlay de una sola página ya no existe",
        )

    def test_phase_list_comes_from_the_status_envelope(self) -> None:
        # Antes era una constante con trece entradas que inventaba compuerta para
        # `fase6` y `fase6_45` y omitía `fase1a` y `fase1b`.
        self.assertAbsent('{ id: "Fase 0"', "la lista de fases no puede estar aquí")
        self.assertPresent("let PHASES_INFO = [];")
        self.assertPresent("function buildPhasesInfo(")
        self.assertPresent("setPhasesInfo(data.pipeline_units);")

    def test_units_without_a_gate_are_not_shown_with_one(self) -> None:
        self.assertPresent("gateLabel: u.gate || 'sin compuerta'")
        self.assertPresent("${p.gateLabel}: ${gateStatus}")
        # El cajón nombra la compuerta solo cuando la unidad tiene una.
        self.assertPresent(
            "${p.gate ? `Gate ${p.gate}: ${gateStatus}` : 'Sin compuerta propia'}"
        )

    def test_drawer_shows_agents_skills_and_manuscript(self) -> None:
        self.assertPresent("Agentes que levanta")
        self.assertPresent("Skills que aplica")
        self.assertPresent("Manuscrito que produce")
        self.assertPresent("Siguiente unidad")
        self.assertPresent("function unitSections(")

    def test_drawer_shows_the_measured_cost_of_the_unit(self) -> None:
        # La telemetría ya trae una fila por unidad con tokens, tool-uses y
        # duración, y el cajón no la mostraba.
        self.assertPresent("Costo medido de la unidad")
        self.assertPresent("currentStatus?.telemetria || []")

    def test_missing_inventory_is_reported_not_faked(self) -> None:
        self.assertPresent("no publica el inventario de unidades")
        self.assertPresent("Sin inventario de unidades en el sobre de estado")

    def test_pdf_is_still_served_and_downloadable(self) -> None:
        self.assertPresent("/api/pdf")
        self.assertPresent('href="/api/pdf" download')

    def test_native_viewer_fallback_survives(self) -> None:
        self.assertPresent('id="pdfNativeIframe"')
        self.assertPresent('id="pdfLoadingSpinner"')


if __name__ == "__main__":
    unittest.main()
