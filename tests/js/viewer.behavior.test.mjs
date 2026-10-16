/**
 * Comportamiento observable del visor PDF continuo del tablero.
 *
 * Cada prueba arranca el JavaScript real de
 * `src/morfeo/dashboard/static/index.html` bajo jsdom, con el navegador y
 * PDF.js doblados (`harness.mjs`) y nada del visor reimplementado. Lo que se
 * observa es el DOM que el visor escribe y su propio registro de páginas.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  DASHBOARD_INDEX,
  PAGE_WIDTH,
  createViewerHarness,
  extractInlineScript,
  flush,
} from './harness.mjs';

test('el arnés ejecuta el guion en línea real del tablero, no una copia', async (t) => {
  const html = await readFile(DASHBOARD_INDEX, 'utf8');
  const viewer = await createViewerHarness({ numPages: 3 });
  t.after(() => viewer.dispose());

  assert.equal(
    viewer.inlineScript,
    extractInlineScript(html),
    'el código ejecutado es el texto en línea del archivo, extraído en esta corrida',
  );
  assert.ok(viewer.inlineScript.length > 50_000, 'el visor real ocupa decenas de miles de caracteres');

  // Prueba directa de que no hay copia: el cuerpo de la función que se ejecuta
  // aparece literalmente en index.html.
  for (const name of ['initPdfViewer', 'renderPageInto', 'buildPagesStrip', 'releasePage']) {
    const source = viewer.window[name].toString();
    assert.ok(
      html.includes(source),
      `la función ${name} ejecutada no coincide con ninguna definición de index.html`,
    );
  }
});

test('el observer pinta y registra la página que entra en pantalla', async (t) => {
  const viewer = await createViewerHarness({ numPages: 4 });
  t.after(() => viewer.dispose());

  await viewer.viewer('initPdfViewer');
  await flush();

  assert.deepEqual(viewer.slots(), [1, 2, 3, 4], 'la carga inicial construye un slot por página');
  assert.deepEqual(viewer.state().rendered, [], 'ninguna página se pinta antes de ser visible');
  assert.deepEqual(
    viewer.documentRequests().map((request) => request.url),
    ['/api/pdf?t=doc'],
    'la carga inicial usa la URL sin cache-buster',
  );

  viewer.intersect(3);
  await flush(8);

  assert.equal(viewer.isPainted(3), true, 'la página visible queda con canvas y texto pintados');
  assert.equal(viewer.hasRendered(3), true, 'la página visible queda registrada');
  assert.deepEqual(viewer.state().textCache, [3], 'el contenido de texto entra a la caché');
  assert.equal(viewer.documentRequests().length, 1, 'pintar una página no recarga el documento');
  assert.ok(
    viewer.fetchCalls().some((call) => call.url === '/api/pdf/annotations'),
    'el visor consulta el historial de anotaciones con la misma carga del documento',
  );
});

test('una recarga sin renders en vuelo deja la tira nueva pintada y registrada', async (t) => {
  const viewer = await createViewerHarness({ numPages: 3 });
  t.after(() => viewer.dispose());

  await viewer.viewer('initPdfViewer');
  await flush();
  viewer.intersect(1);
  await flush(8);
  assert.equal(viewer.isPainted(1), true, 'precondición: la página 1 se pinta antes de recargar');

  // Nada en vuelo: la recarga espera el conjunto vacío de pendientes.
  await viewer.viewer('initPdfViewer', true);
  await flush();

  assert.equal(viewer.documentRequests().length, 2, 'la recarga pide el documento nuevo');
  assert.equal(
    viewer.documentRequests()[1].url.startsWith('/api/pdf?t='),
    true,
    'la recarga usa una URL con cache-buster',
  );
  assert.notEqual(viewer.documentRequests()[1].url, '/api/pdf?t=doc');
  assert.deepEqual(viewer.state().rendered, [], 'la recarga olvida el registro anterior');
  assert.equal(viewer.isPainted(1), false, 'la tira nueva arranca en blanco');

  viewer.intersect(1);
  await flush(8);

  assert.equal(
    viewer.isPainted(1),
    true,
    'la página visible de la tira nueva se pinta después de la recarga',
  );
  assert.equal(viewer.hasRendered(1), true, 'y queda registrada');
});

test('control: una recarga aparcada en un render no cancelable termina pintando', async (t) => {
  const viewer = await createViewerHarness({ numPages: 3 });
  t.after(() => viewer.dispose());

  await viewer.viewer('initPdfViewer');
  await flush();

  // Misma ventana que la prueba de la carrera: la página 2 espera en
  // `pdfDoc.getPage()`, así que la recarga no puede cerrarla.
  viewer.boundary.holdGetPage(2);
  viewer.intersect(2);
  await flush();
  const reload = viewer.viewer('initPdfViewer', true);
  await flush();
  assert.equal(viewer.documentRequests().length, 1, 'la recarga sigue aparcada');

  // Única diferencia con la carrera: el observer no arranca ningún render
  // mientras la recarga está aparcada.
  viewer.boundary.releaseGetPage(2);
  await reload;
  await flush();
  assert.equal(viewer.documentRequests().length, 2, 'la recarga pidió el documento nuevo');

  viewer.intersect(1);
  await flush(8);

  assert.equal(
    viewer.isPainted(1),
    true,
    'sin render intercalado, la página visible de la tira nueva se pinta',
  );
  assert.equal(viewer.hasRendered(1), true, 'y queda registrada');
});

test('el desalojo libera las páginas lejanas y acota el registro', async (t) => {
  const viewer = await createViewerHarness({ numPages: 9 });
  t.after(() => viewer.dispose());

  await viewer.viewer('initPdfViewer');
  await flush();

  for (const pageNumber of [1, 2, 3, 4, 5, 6, 7, 8]) {
    viewer.intersect(pageNumber);
    await flush(8);
  }

  const rendered = viewer.state().rendered.slice().sort((a, b) => a - b);
  assert.deepEqual(
    rendered,
    [1, 2, 3, 4, 5, 6],
    'solo quedan registradas las seis páginas más cercanas a la visible',
  );
  assert.equal(viewer.hasRendered(8), false, 'la página desalojada sale del registro');
  assert.equal(viewer.painted(8).canvasWidth, 0, 'el canvas de la página desalojada se libera');
  assert.ok(viewer.painted(8).hasLiveSlot, 'el slot desalojado conserva su lugar en la tira');
});

test('el zoom aplica la escala nueva en serie y repinta lo visible', async (t) => {
  const viewer = await createViewerHarness({ numPages: 4 });
  t.after(() => viewer.dispose());

  await viewer.viewer('initPdfViewer');
  await flush();
  viewer.intersect(1);
  await flush(8);
  assert.equal(viewer.isPainted(1), true, 'precondición: la página 1 se pinta a 1.25');
  const before = viewer.state();

  // `zoomPdf` solo fija la escala y agenda el debounce: con el reloj manual,
  // nada se aplica hasta que la prueba lo avanza.
  viewer.viewer('zoomPdf', 0.15);
  assert.equal(viewer.state().scale, 1.4, 'el zoom actualiza la escala de inmediato');
  assert.ok(viewer.pendingTimers() >= 1, 'el debounce de zoom queda agendado en el reloj manual');

  await viewer.advance(120);
  await flush(12);

  const after = viewer.state();
  assert.equal(after.scale, 1.4, 'la escala nueva queda vigente');
  assert.equal(
    after.generation,
    before.generation + 1,
    'aplicar la escala invalida la generación de render',
  );
  assert.equal(viewer.isPainted(1), true, 'la página visible se repinta a la escala nueva');
  assert.equal(
    viewer.painted(1).canvasWidth,
    Math.floor(PAGE_WIDTH * 1.4),
    'el canvas se redimensiona al viewport de la escala nueva',
  );
  assert.deepEqual(
    after.rendered.slice().sort((a, b) => a - b),
    [1, 2, 3, 4],
    'el zoom repinta todo lo visible y no deja canvas huérfanos',
  );
});

test('la recarga no queda retenida para siempre por una tarea que no se puede cancelar', async (t) => {
  const viewer = await createViewerHarness({ numPages: 3 });
  t.after(() => viewer.dispose());

  await viewer.viewer('initPdfViewer');
  await flush();

  // Misma frontera que la prueba de control: la página 2 espera en
  // `pdfDoc.getPage()`, que `cancelPageRender` no puede tocar, así que la recarga
  // queda aparcada sin poder cerrarla.
  viewer.boundary.holdGetPage(2);
  viewer.intersect(2);
  await flush();
  const reload = viewer.viewer('initPdfViewer', true);
  await flush();
  assert.equal(viewer.documentRequests().length, 1, 'la recarga sigue aparcada');

  // Se vence el tope sin liberar la tarea atascada: la recarga debe continuar.
  await viewer.advance(60_000);
  await reload;
  await flush();

  assert.equal(
    viewer.documentRequests().length,
    2,
    'vencido el tope, la recarga reconstruye aunque la tarea vieja siga atascada',
  );
  assert.ok(viewer.document.getElementById('pdfPageSlot-1'), 'la tira nueva existe');

  // Y la tira nueva sigue siendo utilizable: la página visible se pinta.
  viewer.intersect(1);
  await flush(8);
  assert.equal(viewer.isPainted(1), true, 'la tira nueva pinta la página visible');
});

test('el zoom durante la ventana sellada de la recarga no toca el estado', async (t) => {
  const viewer = await createViewerHarness({ numPages: 3 });
  t.after(() => viewer.dispose());

  await viewer.viewer('initPdfViewer');
  await flush();

  // Aparca la recarga en la frontera no cancelable `pdfDoc.getPage()`: el sello
  // queda levantado y la tira vieja sigue en pie, con la página 2 en vuelo.
  viewer.boundary.holdGetPage(2);
  viewer.intersect(2);
  await flush();
  const reload = viewer.viewer('initPdfViewer', true);
  await flush();
  assert.equal(viewer.documentRequests().length, 1, 'la recarga sigue aparcada');

  const before = viewer.state();
  const renderRecordsBefore = viewer.renderRecords().length;

  // El usuario hace zoom durante la recarga: la escala cambia de inmediato y el
  // debounce vence dentro de la ventana sellada.
  viewer.viewer('zoomPdf', 0.15);
  assert.equal(viewer.state().scale, 1.4, 'el zoom actualiza la escala de inmediato');
  await viewer.advance(120);
  await flush(12);

  const during = viewer.state();
  assert.equal(
    during.generation,
    before.generation,
    'el zoom sellado no invalida la generación de render',
  );
  assert.equal(
    during.pending.length,
    before.pending.length,
    'el zoom sellado no toca los renders en vuelo',
  );
  assert.equal(
    during.rendered.length,
    before.rendered.length,
    'el zoom sellado no toca lo registrado',
  );
  assert.equal(
    viewer.renderRecords().length,
    renderRecordsBefore,
    'el zoom sellado no arranca renders',
  );

  // La recarga termina: la tira nueva nace a la escala que el zoom fijó, así que
  // la aplicación sellada se descarta sin perder el zoom del usuario.
  viewer.boundary.releaseGetPage(2);
  await reload;
  await flush();

  viewer.intersect(1);
  await flush(8);

  assert.equal(viewer.isPainted(1), true, 'la tira nueva pinta la página visible');
  assert.equal(
    viewer.painted(1).canvasWidth,
    Math.floor(PAGE_WIDTH * 1.4),
    'la tira nueva se reconstruye a la escala del zoom hecho durante la recarga',
  );
});

test('un fallo durante el sello no deja el visor sellado para siempre', async (t) => {
  const viewer = await createViewerHarness({ numPages: 3 });
  t.after(() => viewer.dispose());

  await viewer.viewer('initPdfViewer');
  await flush();

  // El observer vivo falla al desconectarse: el error cae justo después de
  // levantar el sello y antes del `try` que hoy lo protege. Sin el `finally`, el
  // visor queda sordo para siempre.
  const observer = viewer.observers[viewer.observers.length - 1];
  observer.disconnect = () => {
    throw new Error('fallo al desconectar el observer');
  };

  await viewer.viewer('initPdfViewer', true).catch(() => {});
  await flush();

  assert.equal(
    viewer.window.eval('pdfReloadInProgress'),
    false,
    'el sello debe bajarse aunque la recarga falle',
  );

  // Y el visor vuelve a aceptar renders: la página visible se pinta.
  viewer.intersect(1);
  await flush(8);
  assert.equal(
    viewer.isPainted(1),
    true,
    'con el sello bajado, la tira sigue siendo utilizable',
  );
});
