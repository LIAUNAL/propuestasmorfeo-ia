/**
 * Botón «Recompilar» del visor PDF y recarga cuando main.pdf cambió en disco.
 *
 * Corre el JavaScript real de `index.html` bajo jsdom (`harness.mjs`). La
 * frontera HTTP es un `fetch` doblado por URL: `/api/pdf/compile` responde la
 * compilación y `/api/pdf/version` la versión actual del PDF.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

function json(payload, status = 200) {
  return { ok: status < 400, status, json: async () => payload, text: async () => JSON.stringify(payload) };
}

async function harness(t, { version = 'v1', compile = { ok: true, version: 'v2', pages: 10 } } = {}) {
  const viewer = await createViewerHarness({ numPages: 2 });
  t.after(() => viewer.dispose());
  const calls = [];
  const state = { version };
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    calls.push({ url: u, method: (init && init.method) || 'GET' });
    if (u.startsWith('/api/pdf/version')) return json({ ok: true, exists: true, version: state.version });
    if (u.startsWith('/api/pdf/compile')) {
      state.version = compile.version || state.version;
      return json(compile, compile.ok ? 200 : 500);
    }
    return json({}, 503);
  };
  return { viewer, calls, state };
}

test('el visor tiene un botón Recompilar junto a Descargar', async (t) => {
  const { viewer } = await harness(t);
  const btn = viewer.document.getElementById('btnRecompilePdf');
  assert.ok(btn, 'existe el botón');
  assert.match(btn.textContent, /Recompilar/);
});

test('Recompilar hace POST a /api/pdf/compile y recarga el PDF con cache-buster', async (t) => {
  const { viewer, calls } = await harness(t);
  await viewer.viewer('initPdfViewer');
  await flush();

  await viewer.viewer('recompilePdf');
  await flush();

  const post = calls.find(c => c.url.startsWith('/api/pdf/compile'));
  assert.ok(post, 'se pidió la compilación');
  assert.equal(post.method, 'POST');
  const urls = viewer.documentRequests().map(r => r.url);
  assert.equal(urls.length, 2, 'el PDF se volvió a cargar después de compilar');
  assert.notEqual(urls[1], '/api/pdf?t=doc', 'la recarga no reutiliza la URL en caché');
  const btn = viewer.document.getElementById('btnRecompilePdf');
  assert.equal(btn.disabled, false, 'el botón vuelve a quedar activo');
});

test('si la compilación falla, el PDF no se recarga y se informa el error', async (t) => {
  const { viewer } = await harness(t, { compile: { ok: false, error: 'LaTeX falló', log_tail: '! Undefined control sequence.' } });
  const alerts = [];
  viewer.window.alert = (msg) => alerts.push(String(msg));
  await viewer.viewer('initPdfViewer');
  await flush();

  await viewer.viewer('recompilePdf');
  await flush();

  assert.equal(viewer.documentRequests().length, 1, 'no hubo recarga');
  assert.equal(alerts.length, 1);
  assert.match(alerts[0], /Undefined control sequence/);
  assert.equal(viewer.document.getElementById('btnRecompilePdf').disabled, false);
});

test('al volver a la pestaña, el visor recarga solo si main.pdf cambió en disco', async (t) => {
  const { viewer, state } = await harness(t);
  await viewer.viewer('navigateTab', 'preview');
  await flush();
  await flush();
  assert.equal(viewer.documentRequests().length, 1, 'carga inicial');

  await viewer.viewer('navigateTab', 'preview');
  await flush();
  await flush();
  assert.equal(viewer.documentRequests().length, 1, 'sin cambio en disco no recarga');

  state.version = 'v9';
  await viewer.viewer('navigateTab', 'preview');
  await flush();
  await flush();
  assert.equal(viewer.documentRequests().length, 2, 'con una versión nueva recarga');
});
