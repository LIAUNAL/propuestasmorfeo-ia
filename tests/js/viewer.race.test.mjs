/**
 * Carreras del render continuo del visor, confirmadas por verificación
 * independiente y hoy selladas.
 *
 * El visor es una tira continua que reemplaza el documento en caliente. La
 * recarga (`initPdfViewer(true)`) levanta un sello ANTES del primer `await`:
 * incrementa la generación, desconecta el observer y deja sordos a los puntos
 * de entrada del render y al callback de intersección. Solo después espera, de
 * forma acotada, a que las tareas en vuelo terminen; recién entonces vacía la
 * tira y olvida las cachés. Las escrituras de caché quedan atadas a la
 * identidad del documento además de la generación, y la liberación de una
 * página solo toca el canvas que esa tarea pintó.
 *
 * Dos huecos quedan fijados aquí, los dos producen una página registrada pero
 * en blanco:
 *
 * A. Una tarea vieja que ya pintó su bitmap se detiene en la lectura del texto
 *    (`page.getTextContent()`, una frontera asíncrona real de PDF.js). Si la
 *    recarga reconstruye la tira y la tarea se reanuda después, una liberación
 *    resuelta por número de página vacía el canvas NUEVO y la página queda
 *    registrada y en blanco.
 *
 * B. Durante la espera de la recarga, la tira vieja y su observer siguen
 *    vivos. Una intersección tardía arrancaba una tarea contra el documento
 *    viejo que capturaba la generación NUEVA, pasaba todos los guardas de
 *    generación y escribía en el estado nuevo.
 *
 * Cada prueba arranca el JavaScript real de
 * `src/morfeo/dashboard/static/index.html` bajo el arnés de `harness.mjs`.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

function isPainted(paint) {
  return paint.canvasWidth > 0 && paint.canvasHeight > 0 && paint.textSpans > 0;
}

/**
 * Escenario A: la tarea vieja despierta después de que la tira nueva pintó su
 * página visible. Debe liberar solo su canvas viejo, nunca el vivo, y no debe
 * envenenar la caché de texto del documento nuevo.
 */
async function reproduceStaleRelease() {
  const viewer = await createViewerHarness({ numPages: 4 });
  try {
    // 1. Carga inicial: tira de 4 slots.
    await viewer.viewer('initPdfViewer');
    await flush();
    assert.deepEqual(viewer.slots(), [1, 2, 3, 4], 'la carga inicial debe construir la tira');

    // 2. La página 1 pinta su bitmap en `page.render()` y se detiene en la
    //    lectura del texto del documento viejo.
    viewer.boundary.holdTextContent(1);
    viewer.intersect(1);
    await flush(4);
    assert.equal(
      viewer.state().pending.includes(1),
      true,
      'precondición: la página 1 queda en vuelo en la lectura de texto',
    );

    // 3. Arranca la recarga. El sello se levanta de forma síncrona y el tope de
    //    la espera vence sin liberar la tarea atascada: la recarga reconstruye
    //    igual, porque la identidad del documento protege el estado nuevo.
    const reload = viewer.viewer('initPdfViewer', true);
    await flush(4);
    await viewer.advance(60_000);
    await reload;
    await flush(8);

    assert.equal(viewer.documentRequests().length, 2, 'la recarga debe pedir el documento nuevo');
    assert.ok(viewer.document.getElementById('pdfPageSlot-1'), 'la tira nueva existe');

    // 4. La tira nueva pinta su página visible con el documento nuevo.
    viewer.intersect(1);
    await flush(8);
    assert.ok(
      isPainted(viewer.painted(1)),
      'precondición: la tira nueva pinta la página 1 antes de despertar la tarea vieja',
    );

    // 5. Recién ahora despierta la tarea vieja.
    viewer.boundary.releaseTextContent(1);
    await flush(8);

    return {
      paint: viewer.painted(1),
      registered: viewer.hasRendered(1),
      text: viewer.textLayerText(1),
      state: viewer.state(),
    };
  } finally {
    viewer.dispose();
  }
}

/**
 * Escenario B: la ventana de la recarga que abre una tarea no cancelable
 * (`pdfDoc.getPage()`, que `cancelPageRender` no alcanza). El sello debe dejar
 * sorda la entrada durante esa espera.
 */
async function reproduceSealedWindow() {
  const viewer = await createViewerHarness({ numPages: 4 });
  try {
    await viewer.viewer('initPdfViewer');
    await flush();
    assert.deepEqual(viewer.slots(), [1, 2, 3, 4], 'la carga inicial debe construir la tira');

    // Dos renders en vuelo: página 1 dentro de `page.render()` (cancelable) y
    // página 2 aparcada en `pdfDoc.getPage()` (no cancelable).
    viewer.boundary.holdRender(1);
    viewer.boundary.holdGetPage(2);
    viewer.intersect(1);
    await flush();
    assert.deepEqual(
      viewer.state().renderTasks,
      [1],
      'precondición: la página 1 debe estar suspendida dentro de page.render()',
    );
    viewer.intersect(2);
    await flush();
    assert.deepEqual(
      viewer.state().pending.slice().sort(),
      [1, 2],
      'precondición: las dos páginas deben quedar en vuelo',
    );

    // Recarga: el sello se levanta antes del primer await. La espera queda
    // abierta porque la página 2 no se puede cancelar.
    const reload = viewer.viewer('initPdfViewer', true);
    await flush();

    let sealEvidence = null;
    const parkedOnBound = viewer.documentRequests().length === 1;
    if (parkedOnBound) {
      assert.equal(viewer.state().generation, 1, 'la recarga debe invalidar la generación');
      assert.ok(
        viewer.document.getElementById('pdfPageSlot-1'),
        'precondición: la tira vieja sigue en el DOM durante la espera',
      );

      // SELLO: el observer está desconectado, así que la intersección tardía no
      // arranca nada. Antes, esta misma llamada abría un render contra el
      // documento viejo que capturaba la generación nueva.
      const fired = viewer.tryIntersect(1);
      await flush();

      // SELLO: los puntos de entrada también devuelven sin arrancar nada. No se
      // espera el valor de retorno: con el sello ausente, `renderPageInto`
      // devuelve la tarea en vuelo de la página y esperarla colgaría la prueba
      // en vez de delatar el hueco.
      const recordsBefore = viewer.renderRecords().length;
      void viewer.viewer('renderPageInto', 1);
      await flush();

      sealEvidence = {
        intersectionFiredAnObserver: fired,
        lateRenderRecords: viewer.renderRecords().length - recordsBefore,
      };
    }

    // La tarea aparcada se libera y la recarga termina.
    viewer.boundary.releaseGetPage(2);
    await reload;
    await flush();
    viewer.boundary.releaseRender(1);
    await flush(4);

    assert.equal(viewer.documentRequests().length, 2, 'la recarga debe pedir el documento nuevo');
    assert.equal(viewer.state().pending.length, 0, 'la recarga olvidó los pendientes');
    assert.ok(viewer.document.getElementById('pdfPageSlot-1'), 'la tira nueva existe');

    // La tira nueva pinta la página visible.
    viewer.intersect(1);
    await flush(8);

    return {
      paint: viewer.painted(1),
      registered: viewer.hasRendered(1),
      sealEvidence,
      state: viewer.state(),
    };
  } finally {
    viewer.dispose();
  }
}

test('la recarga no deja una página registrada pero en blanco', async () => {
  const { paint, registered, text, state } = await reproduceStaleRelease();

  assert.ok(
    isPainted(paint),
    `la página 1 quedó registrada pero en blanco en la tira nueva: ${JSON.stringify({
      paint,
      registered,
      textoDeLaCapa: text,
      estadoDelVisor: state,
    })}`,
  );
  assert.equal(registered, true, 'la página 1 debe seguir registrada tras pintarse');
  assert.match(
    text,
    /Doc2/,
    `la capa de texto debe venir del documento nuevo, no del viejo: ${text}`,
  );
});

test('la recarga sella el observer y la entrada de render mientras espera', async () => {
  const { paint, registered, sealEvidence, state } = await reproduceSealedWindow();

  if (sealEvidence) {
    assert.equal(
      sealEvidence.intersectionFiredAnObserver,
      false,
      'el observer debe estar desconectado durante la espera de la recarga',
    );
    assert.equal(
      sealEvidence.lateRenderRecords,
      0,
      'los puntos de entrada sellados no deben arrancar una tarea nueva',
    );
    assert.equal(
      state.pending.includes(1),
      false,
      'el sello impide que la intersección tardía deje una tarea en vuelo',
    );
  }

  assert.ok(
    isPainted(paint),
    `la página 1 quedó registrada pero en blanco en la tira nueva: ${JSON.stringify({
      paint,
      registered,
      sealEvidence,
      estadoDelVisor: state,
    })}`,
  );
  assert.equal(registered, true, 'la página 1 debe seguir registrada tras pintarse');
});

test('testigo: la carrera está cerrada; la tira nueva repinta la página registrada', async () => {
  let result = null;
  let failure = null;
  try {
    result = await reproduceSealedWindow();
  } catch (error) {
    failure = error;
  }

  if (failure) {
    assert.fail(
      'la secuencia de la carrera dejó de reproducirse: falló una precondición ' +
        `(${failure.message}). Revisa las precondiciones de reproduceSealedWindow().`,
    );
  }

  assert.equal(
    isPainted(result.paint),
    true,
    `la carrera volvió a abrirse: la página 1 queda registrada pero en blanco ${JSON.stringify({
      paint: result.paint,
      registered: result.registered,
    })}`,
  );
});
