/**
 * Comportamiento del panel de anotaciones del visor PDF.
 *
 * El panel recibe marcas del operador. Un comentario viaja como instrucción al
 * `redactor` y no reescribe prosa; un reemplazo, en cambio, se aplica de forma
 * determinista sobre el pasaje anclado. Estas pruebas arrancan el JavaScript
 * real de `index.html` bajo jsdom y observan la cola local del visor, la
 * tarjeta de cada marca y la caja que hace visible la cola de instrucciones
 * pendientes del redactor.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness } from './harness.mjs';

function queued(viewer) {
  return JSON.parse(viewer.window.eval('JSON.stringify(queuedAnnotations)'));
}

async function addViaModal(viewer, options) {
  const {
    text,
    page = 1,
    comment = '',
    replacement = '',
    deleteIntent = false,
  } = options;
  viewer.window.eval(
    `currentSelectedText = ${JSON.stringify(text)}; currentSelectedPage = ${page};`,
  );
  viewer.viewer('triggerAddComment');

  const commentInput = viewer.document.getElementById('commentModalInput');
  const replacementInput = viewer.document.getElementById('commentReplacementInput');
  const deleteBox = viewer.document.getElementById('commentReplacementIsDelete');
  assert.ok(commentInput, 'el modal conserva su campo de comentario');
  assert.ok(
    replacementInput,
    'el modal ofrece el campo estructurado «Reemplazar por»',
  );
  assert.ok(
    deleteBox,
    'el modal permite confirmar el borrado cuando el reemplazo va vacío',
  );

  commentInput.value = comment;
  replacementInput.value = replacement;
  deleteBox.checked = deleteIntent;
  viewer.viewer('saveCommentAnnotation');
}

test('un reemplazo literal viaja como marca determinista, sin modelo', async (t) => {
  const viewer = await createViewerHarness({ numPages: 2 });
  t.after(() => viewer.dispose());

  await addViaModal(viewer, {
    text: 'El modelo alcanza 89.4% de F1.',
    replacement: 'El modelo alcanza 91.2% de F1.',
  });

  const marks = queued(viewer);
  assert.equal(marks.length, 1, 'el reemplazo entra a la cola del visor');
  assert.equal(marks[0].type, 'replace', 'el tipo distingue el camino determinista');
  assert.equal(marks[0].replacement, 'El modelo alcanza 91.2% de F1.');
  assert.equal(marks[0].text, 'El modelo alcanza 89.4% de F1.');
});

test('un reemplazo vacío sin confirmación se queda como comentario', async (t) => {
  const viewer = await createViewerHarness({ numPages: 2 });
  t.after(() => viewer.dispose());

  await addViaModal(viewer, {
    text: 'Un pasaje con redacción mejorable.',
    comment: 'ajustar el tono de este pasaje',
  });

  const marks = queued(viewer);
  assert.equal(marks.length, 1);
  assert.equal(marks[0].type, 'comment', 'sin reemplazo ni borrado, la marca es un comentario');
  assert.equal(marks[0].comment, 'ajustar el tono de este pasaje');
  assert.equal(marks[0].replacement, undefined, 'el comentario no lleva reemplazo');
});

test('un borrado confirmado sí envía el reemplazo vacío', async (t) => {
  const viewer = await createViewerHarness({ numPages: 2 });
  t.after(() => viewer.dispose());

  await addViaModal(viewer, {
    text: 'Frase que el operador quiere borrar.',
    replacement: '',
    deleteIntent: true,
  });

  const marks = queued(viewer);
  assert.equal(marks.length, 1);
  assert.equal(marks[0].type, 'replace');
  assert.equal(marks[0].replacement, '');
  assert.equal(marks[0].delete_intent, true, 'el borrado viaja confirmado, no por descuido');
});

test('la tarjeta dice con claridad qué se reemplazará', async (t) => {
  const viewer = await createViewerHarness({ numPages: 2 });
  t.after(() => viewer.dispose());

  await addViaModal(viewer, {
    text: 'El modelo alcanza 89.4% de F1.',
    replacement: 'El modelo alcanza 91.2% de F1.',
  });

  const listText = viewer.document.getElementById('annotsList').textContent;
  assert.ok(
    listText.includes('Reemplazar por'),
    `la tarjeta debe enunciar el reemplazo: ${listText}`,
  );
  assert.ok(
    listText.includes('El modelo alcanza 91.2% de F1.'),
    'la tarjeta debe mostrar el texto literal que reemplazará al ancla',
  );
});

test('el panel hace visible la cola de instrucciones pendientes del redactor', async (t) => {
  const viewer = await createViewerHarness({ numPages: 2 });
  t.after(() => viewer.dispose());

  viewer.viewer('renderPendingInstructionsQueue', 3, 5);

  const box = viewer.document.getElementById('pendingQueueBox');
  assert.ok(box, 'existe la caja que muestra la cola del redactor');
  assert.ok(box.textContent.includes('3'), 'se muestra cuántas instrucciones están pendientes');
  assert.ok(
    box.textContent.toLowerCase().includes('no cambian el manuscrito'),
    `la caja debe decir que la cola no cambia nada todavía: ${box.textContent}`,
  );
  assert.ok(
    box.textContent.includes('redactor'),
    'y debe nombrar quién consume esas instrucciones',
  );

  await viewer.viewer('loadPendingInstructionsQueue');
  assert.ok(
    viewer
      .fetchCalls()
      .some(
        (call) =>
          call.url.includes('/api/artifact?file=') &&
          call.url.includes('instrucciones_revisor_pdf'),
      ),
    `el panel consulta el archivo real de instrucciones pendientes: ${JSON.stringify(
      viewer.fetchCalls(),
    )}`,
  );
});
