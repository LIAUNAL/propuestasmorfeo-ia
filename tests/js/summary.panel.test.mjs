/**
 * El resumen que el panel muestra tras ejecutar las marcas.
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom y se observa el DOM del
 * modal de resumen, no una copia. La respuesta HTTP de `/api/pdf/execute` se
 * sustituye por un doble determinista: el resto del visor es el archivo real.
 *
 * Cubre dos defectos de honestidad del resumen: un lote deduplicado no puede
 * contarse como trabajo aplicado, y un tachado no localizado en un lote mixto
 * debe aparecer en el panel y no solo en el detalle persistido.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

function executeResponse(payload) {
  return {
    ok: true,
    status: 200,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  };
}

async function runExecute(viewer, payload) {
  await viewer.viewer('initPdfViewer');
  await flush();

  viewer.window.fetch = async (url) => {
    if (String(url).includes('/api/pdf/execute')) {
      return executeResponse(payload);
    }
    return {
      ok: false,
      status: 503,
      json: async () => ({}),
      text: async () => '',
    };
  };

  await viewer.viewer('executeQueuedChanges');
  await flush();
  return viewer.document.getElementById('summaryModalBody').innerHTML;
}

test('el resumen del panel muestra el tachado que no se pudo aplicar', async (t) => {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());

  const body = await runExecute(viewer, {
    ok: true,
    summary: {
      strikethrough_applied: 1,
      humanize_applied: 0,
      comments_registered: 0,
      comments_duplicated: 0,
      comments_failed: 0,
      annotations_failed: 1,
      files_modified: [],
      pending_instructions_file: null,
      pdf_recompiled: false,
      pdf_recompile_skipped: true,
      pdf_recompile_reason: 'sin cambios en el manuscrito',
    },
    details: {
      strikethrough: [],
      humanize: [],
      comments: [],
      unmatched: [
        {
          id: 'a2',
          type: 'strikethrough',
          text: 'Un texto ausente de las fuentes',
          page: 7,
          reason: 'Texto no localizado en las secciones LaTeX fuente',
        },
      ],
    },
  });

  assert.match(
    body,
    /Un texto ausente de las fuentes/,
    'el panel debe nombrar la anotación que no se aplicó',
  );
  assert.match(
    body,
    /Texto no localizado/,
    'el panel debe explicar por qué no se aplicó',
  );
});

test('el resumen del panel distingue lo duplicado de lo escrito', async (t) => {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());

  const body = await runExecute(viewer, {
    ok: true,
    summary: {
      strikethrough_applied: 0,
      humanize_applied: 0,
      comments_registered: 0,
      comments_duplicated: 2,
      comments_failed: 0,
      annotations_failed: 0,
      files_modified: [],
      pending_instructions_file: 'artefactos/pipeline/instrucciones_revisor_pdf.md',
      pdf_recompiled: false,
      pdf_recompile_skipped: true,
      pdf_recompile_reason: 'sin cambios en el manuscrito',
    },
    details: { strikethrough: [], humanize: [], comments: [], unmatched: [] },
  });

  assert.match(
    body,
    /<strong>2<\/strong>[\s\S]{0,80}duplicad/i,
    'un lote deduplicado debe verse como tal, no como 2 registradas',
  );
  assert.match(
    body,
    /<strong>0<\/strong>[^<]*(instrucciones|registradas)/i,
    'el número de registradas de verdad debe ser 0',
  );
});
