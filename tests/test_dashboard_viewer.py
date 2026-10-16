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

    # --- Panel de anotaciones que consume lo que registra (S7) -------------
    def test_annotation_panel_consumes_replacements_and_shows_the_queue(self) -> None:
        # El reemplazo es determinista: el panel lo aplica sobre el ancla y
        # recompila, sin pasar por el agente. La cola del redactor, en cambio,
        # no cambia nada hasta que alguien la consuma, y eso debe verse.
        self.assertPresent('id="commentReplacementInput"')
        self.assertPresent('id="commentReplacementIsDelete"')
        self.assertPresent('id="pendingQueueBox"')
        self.assertPresent("function renderPendingInstructionsQueue(")
        self.assertPresent("type: 'replace'")

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
            self.html.count("if (generation !== pdfRenderGeneration) { releasePage(n, canvas); return; }"),
            0,
            "toda salida posterior a pintar comprueba generación e identidad",
        )
        self.assertEqual(
            self.html.count(
                "if (generation !== pdfRenderGeneration || identity !== pdfDocIdentity) "
                "{ releasePage(n, canvas); return; }"
            ),
            3,
            "las tres salidas posteriores a pintar liberan el canvas que pintaron",
        )
        # Cancelada o fallida sin registrarse: el finally también libera.
        self.assertPresent("if (!pdfRenderedPages.has(n)) releasePage(n);")

    def test_reload_releases_the_dom_before_dropping_the_tracking(self) -> None:
        # Vaciar los conjuntos sin vaciar el DOM dejaba los canvas viejos sin
        # dueño, y el desalojo ya no podía liberarlos.
        self.assertPresent("cancelAllPageRenders();")
        self.assertPresent("if (strip) strip.innerHTML = '';")
        self.assertPresent("pdfRenderGeneration += 1;")

    # --- Carreras del render continuo (bucle de corrección) -----------------
    # No hay entorno DOM en el repositorio: ni jsdom en `node_modules`, ni un
    # runner de JavaScript, ni un arnés de navegador, ni una extracción con
    # `node --check` en la suite existente. Lo que sigue fija el orden de las
    # sentencias del visor; es estructural, no de comportamiento, y su límite
    # está declarado a propósito.

    def functionSource(self, signature: str, following: str) -> str:
        """Cuerpo de una función del visor, entre su firma y la que le sigue."""
        start = self.html.index(signature)
        return self.html[start : self.html.index(following, start)]

    def test_force_reload_awaits_pending_renders_before_tearing_down(self) -> None:
        # La recarga invalidaba la generación, vaciaba la tira y limpiaba las
        # cachés sin esperar a las tareas en vuelo. Una tarea vieja se reanudaba
        # contra los nodos nuevos de la tira y, al resolver el canvas por número
        # de página, borraba el que acababa de pintar la tarea nueva; la página
        # quedaba en blanco.
        body = self.functionSource(
            "async function initPdfViewer(", "async function buildPagesStrip("
        )
        wait = body.index(
            "await settleWithinBound(Array.from(pdfPendingRenders.values()), PDF_RELOAD_SETTLE_MS)"
        )
        self.assertLess(body.index("pdfRenderGeneration += 1;"), wait)
        self.assertLess(body.index("pdfReloadInProgress = true;"), wait)
        self.assertLess(body.index("disconnectPageObserver();"), wait)
        self.assertLess(body.index("cancelAllPageRenders();"), wait)
        self.assertLess(
            wait,
            body.index("if (strip) strip.innerHTML = '';"),
            "la recarga espera los renders en vuelo antes de vaciar la tira",
        )
        self.assertLess(
            wait,
            body.index("pdfPageCache.clear();"),
            "la recarga espera los renders en vuelo antes de olvidar las cachés",
        )
        # La espera es acotada: una tarea atascada en una frontera que
        # `cancelPageRender` no alcanza no puede retener la recarga para siempre.
        self.assertPresent("const PDF_RELOAD_SETTLE_MS = 2500;")
        bound = self.functionSource("function settleWithinBound(", "async function initPdfViewer(")
        self.assertIn("setTimeout(finish, ms);", bound)
        self.assertIn("Promise.allSettled(promises).then(finish, finish);", bound)

    def test_reload_seals_the_render_entries_before_awaiting(self) -> None:
        # El sello se levanta de forma síncrona, antes del primer await, y deja
        # sordos al callback del observer y a los puntos de entrada del render: la
        # tira vieja sigue viva durante la espera, así que una intersección tardía
        # arrancaba una tarea contra el documento viejo que capturaba la generación
        # nueva. Se baja cuando la tira nueva quedó construida.
        self.assertPresent("let pdfReloadInProgress = false;")
        self.assertPresent("function disconnectPageObserver()")
        resets = self.html.count("pdfReloadInProgress = false;")
        self.assertEqual(resets, 2, "el indicador arranca y se baja en el finally")
        observer = self.functionSource(
            "function onPageIntersection(", "function renderPageInto("
        )
        self.assertIn(
            "if (pdfReloadInProgress) return;",
            observer,
            "el callback del observer se sorda durante la recarga",
        )
        render = self.functionSource("function renderPageInto(", "function renderVisiblePages(")
        self.assertIn(
            "if (pdfReloadInProgress) return Promise.resolve();",
            render,
            "renderPageInto se sorda durante la recarga",
        )
        build = self.functionSource("async function buildPagesStrip(", "function createPageSlot(")
        self.assertIn("disconnectPageObserver();", build)

    def test_a_stale_task_cannot_write_the_pdf_caches(self) -> None:
        # Las escrituras iban antes de la comprobación de generación, así que el
        # contenido del documento viejo envenenaba las cachés del nuevo. La
        # generación no basta: la identidad del documento distingue una tarea
        # que arrancó tras la recarga contra el documento viejo.
        self.assertIn("let pdfDocIdentity = 0;", self.html)
        self.assertIn("pdfDocIdentity += 1;", self.html)
        get_page = self.functionSource(
            "async function getPageObject(", "async function initPdfViewer("
        )
        self.assertIn("identity = pdfDocIdentity", get_page)
        self.assertIn(
            "if (generation === pdfRenderGeneration && identity === pdfDocIdentity) {",
            get_page,
        )
        render = self.functionSource("function renderPageInto(", "function renderVisiblePages(")
        block = render[
            render.index("let textContent = pdfTextContentCache.get(n);")
            : render.index("textLayerDiv.style.setProperty(")
        ]
        guard = (
            "if (generation !== pdfRenderGeneration || identity !== pdfDocIdentity) "
            "{ releasePage(n, canvas); return; }"
        )
        self.assertLess(
            block.index(guard),
            block.index("pdfTextContentCache.set(n, fetched);"),
            "el contenido de texto se guarda después de comprobar generación e identidad",
        )
        preload = self.functionSource("function preloadAdjacentPages(", "function zoomPdf(")
        self.assertIn("await getPageObject(p, generation, identity)", preload)
        self.assertIn("identity === pdfDocIdentity && !pdfTextContentCache.has(p)", preload)
        self.assertIn("pdfTextContentCache.set(p, text);", preload)

    def test_release_page_only_frees_the_canvas_its_task_painted(self) -> None:
        # `releasePage` resolvía el nodo por número de página, así que una tarea
        # vieja vaciaba el canvas de la nueva. Ahora solo puede liberar el nodo
        # que ella misma pintó.
        release = self.functionSource("function releasePage(", "function evictDistantPages(")
        self.assertIn("function releasePage(n, paintedCanvas) {", release)
        self.assertIn("if (paintedCanvas && paintedCanvas !== canvas) return;", release)
        render = self.functionSource("function renderPageInto(", "function renderVisiblePages(")
        guard = (
            "if (generation !== pdfRenderGeneration || identity !== pdfDocIdentity) "
            "{ releasePage(n, canvas); return; }"
        )
        self.assertEqual(
            render.count(guard),
            3,
            "las tres salidas posteriores a pintar liberan el canvas que pintaron",
        )
        # El registro queda atado al nodo que se pintó: una página "registrada"
        # sobre un canvas desprendido no cuenta como servida, así que la tira
        # nueva vuelve a pintarla en lugar de dejarla en blanco.
        self.assertPresent("const pdfRenderedCanvases = new Map();")
        self.assertPresent("if (isPagePainted(n)) return Promise.resolve();")
        self.assertIn("pdfRenderedCanvases.set(n, canvas);", render)
        registry = self.functionSource("function isPagePainted(", "function releasePage(")
        self.assertIn("if (painted !== getPageCanvas(n)) return false;", registry)

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

    def test_the_drawer_offers_the_next_command_to_copy(self) -> None:
        # Decisión del operador: avanzar desde el tablero se hace sugiriendo el
        # comando, no lanzando agentes desde el servidor.
        self.assertPresent("function copyNextCommand(")
        self.assertPresent('onclick="copyNextCommand(this)"')
        self.assertPresent("let NEXT_PENDING_UNIT = null;")
        self.assertPresent("NEXT_PENDING_UNIT = (PHASES_INFO.find(p => p.kind === 'step'")
        self.assertPresent("Copiar /propuesta-continuar")

    def test_the_unit_in_progress_is_marked_and_explained(self) -> None:
        # El latido `_en_curso.json` es lo único que permite mostrar qué agente se
        # está levantando mientras ocurre: el `NN-fase*.md` se escribe al terminar.
        self.assertPresent("let EN_CURSO = null;")
        self.assertPresent("EN_CURSO = data.en_curso || null;")
        self.assertPresent("En ejecución ahora")
        self.assertPresent("${enCurso ? 'EN CURSO' : (isLit ? 'PASS' : 'SIN LUZ')}")

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
