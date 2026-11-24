/**
 * traduccion-panel.js: the «Versión del documento» fold of the PDF preview
 * (odd/tasks/idioma-tablero-traduccion.md, S4).
 *
 * The real static/traduccion-panel.js runs in a small jsdom page with the i18n
 * runtime and its catalogues, fetch, the terminal delivery and the viewer
 * source switch doubled; the last tests run it inside the real dashboard, where
 * «Ver traducción» must switch the viewer to /api/pdf?traduccion=<lang>.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { JSDOM } from 'jsdom';

import { createViewerHarness, DASHBOARD_INDEX, DASHBOARD_STATIC, flush } from './harness.mjs';

const SCRIPT = readFileSync(path.join(DASHBOARD_STATIC, 'traduccion-panel.js'), 'utf8');
const FOLDS = readFileSync(path.join(DASHBOARD_STATIC, 'section-folds.js'), 'utf8');
const RUNTIME = readFileSync(path.join(DASHBOARD_STATIC, 'i18n.js'), 'utf8');
const CATALOGUES = ['es', 'en'].map((lang) => readFileSync(path.join(DASHBOARD_STATIC, 'i18n', lang, 'traduccion.js'), 'utf8'));

function json(payload, status = 200) {
  return { ok: status < 400, status, json: async () => payload, text: async () => JSON.stringify(payload) };
}

function statusPayload(overrides = {}) {
  return {
    ok: true, run: 'demo', source_language: 'es', lang: 'en', command: '/propuesta-traducir en',
    available: true, errores: [],
    status: {
      planned: true, built: true, pdf: 'redaccion/traducciones/en/main.pdf', pdf_current: true,
      counts: { total: 12, current: 9, missing: 2, stale: 1 },
      fragment_counts: { total: 4, current: 4, missing: 0, stale: 0 },
      audit: { generated_at: '2026-11-22T10:00:00+00:00', checker: 'scripts/estilo_en.py', fresh: true,
        fidelity_failures: 0, findings: 3, document: { indice: 81, veredicto: 'clara <b>' } },
      ...overrides,
    },
  };
}

async function mountPage({ answer = () => json(statusPayload()), send = async () => true } = {}) {
  const dom = new JSDOM('<!doctype html><html><body><div class="pdf-workspace-layout"><div id="root"></div></div></body></html>', {
    runScripts: 'outside-only', url: 'http://localhost:8000/',
  });
  const { window } = dom;
  CATALOGUES.forEach((code) => window.eval(code));
  window.eval(RUNTIME);
  window.eval(SCRIPT);
  const calls = [];
  const prompts = [];
  const sources = [];
  const controller = window.TraduccionPanel.mount(window.document.getElementById('root'), {
    interval: 1000,
    fetch: async (url, init) => {
      calls.push({ url: String(url), method: (init && init.method) || 'GET' });
      return answer(String(url), init);
    },
    send: async (prompt) => { prompts.push(prompt); return send(prompt); },
    onSource: async (lang) => { sources.push(lang); },
  });
  return { window, document: window.document, controller, calls, prompts, sources, root: window.document.getElementById('root') };
}

test('it shows block and fragment states, the build, the PDF and the style audit', async () => {
  const { controller, root, calls } = await mountPage();
  await controller.refresh();
  assert.equal(calls[0].url, '/api/traducciones', 'the first read lets the server pick the other language');
  assert.match(root.querySelector('.tp-intro').textContent, /español.*inglés/s);
  assert.match(root.querySelector('[data-row="blocks"]').textContent, /9 de 12 al día · 2 pendientes · 1 desactualizados/);
  assert.ok(root.querySelector('[data-row="blocks"] .tp-state--warn'));
  assert.ok(root.querySelector('[data-row="fragments"] .tp-state--ok'));
  assert.match(root.querySelector('[data-row="built"]').textContent, /construida/);
  assert.match(root.querySelector('[data-row="pdf"]').textContent, /compilado y al día/);
  assert.match(root.querySelector('[data-row="audit"]').textContent, /estilo_en\.py.*81 de 100.*0 fallas/s);
  assert.equal(root.querySelector('[data-row="audit"] b'), null, 'values are escaped');
  await controller.refresh();
  assert.equal(calls[1].url, '/api/traducciones?traduccion=en', 'later reads name the target as traduccion=, never lang=');
});

test('«Traducir / actualizar» types /propuesta-traducir <lang> and offers a retry when the terminal is down', async () => {
  let up = false;
  const { controller, root, prompts } = await mountPage({ send: async () => up });
  await controller.refresh();
  root.querySelector('.tp-translate').click();
  await flush();
  assert.deepEqual(prompts, ['/propuesta-traducir en']);
  const retry = root.querySelector('.tp-retry');
  assert.equal(retry.hidden, false);
  assert.match(root.querySelector('.tp-message').textContent, /no llegó al agente/);
  up = true;
  retry.click();
  await flush();
  assert.deepEqual(prompts, ['/propuesta-traducir en', '/propuesta-traducir en']);
  assert.equal(retry.hidden, true);
  assert.match(root.querySelector('.tp-message').textContent, /Se envió \/propuesta-traducir en/);
});

test('«Compilar traducción» posts the target and reports a failure', async () => {
  let fail = false;
  const answer = (url) => {
    if (url.startsWith('/api/traduccion/compilar')) {
      return fail ? json({ ok: false, code: 'TRANSLATION_COMPILE_FAILED', error: 'LaTeX reported 1 error(s)' }, 500)
        : json({ ok: true, version: 'v2' });
    }
    return json(statusPayload());
  };
  const { controller, root, calls } = await mountPage({ answer });
  await controller.refresh();
  root.querySelector('.tp-compile').click();
  await flush(8);
  const post = calls.find((c) => c.url.startsWith('/api/traduccion/compilar'));
  assert.deepEqual(post, { url: '/api/traduccion/compilar?traduccion=en', method: 'POST' });
  assert.match(root.querySelector('.tp-message').textContent, /Traducción compilada/);
  fail = true;
  assert.equal(await controller.compile(), false);
  assert.match(root.querySelector('.tp-message').textContent, /No se pudo compilar la traducción: LaTeX reported 1 error/);
});

test('compile is disabled until the version is built, and the source switch until a PDF exists', async () => {
  const answer = () => json(statusPayload({ built: false, pdf: null, pdf_current: false, planned: false, audit: null }));
  const { controller, root } = await mountPage({ answer });
  await controller.refresh();
  assert.equal(root.querySelector('.tp-compile').disabled, true);
  assert.equal(root.querySelector('.tp-source').disabled, true);
  assert.match(root.textContent, /Todavía no hay traducción/);
  assert.match(root.textContent, /Sin auditoría de estilo todavía/);
});

test('«Ver traducción» switches the viewer source and hides the annotation tools; «Ver original» restores it', async () => {
  const { controller, root, sources, document } = await mountPage();
  await controller.refresh();
  const button = root.querySelector('.tp-source');
  assert.equal(button.textContent, 'Ver traducción');
  button.click();
  await flush();
  assert.deepEqual(sources, ['en']);
  assert.equal(controller.showing, true);
  assert.equal(button.textContent, 'Ver original');
  assert.ok(document.querySelector('.pdf-workspace-layout').classList.contains('is-translation'));
  assert.match(root.querySelector('.tp-viewing').textContent, /traducción al inglés/);
  button.click();
  await flush();
  assert.deepEqual(sources, ['en', null]);
  assert.equal(document.querySelector('.pdf-workspace-layout').classList.contains('is-translation'), false);
});

test('switching the dashboard to English re-renders every string from the catalogue', async () => {
  const { controller, root, window } = await mountPage();
  await controller.refresh();
  window.i18n.setLanguage('en');
  assert.equal(root.querySelector('.tp-translate').textContent, 'Translate / update');
  assert.equal(root.querySelector('.tp-compile').textContent, 'Compile translation');
  assert.match(root.querySelector('[data-row="blocks"]').textContent, /9 of 12 current · 2 missing · 1 stale/);
  assert.match(root.querySelector('.tp-intro').textContent, /Spanish.*English/s);
});

test('polling runs only while started and visible', async () => {
  const { controller } = await mountPage();
  controller.start();
  assert.equal(controller.polling, true);
  controller.stop();
  assert.equal(controller.polling, false);
});

test('in the dashboard the «Versión del documento» fold sits below «Juez final» and switches the viewer', async (t) => {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const calls = [];
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    calls.push({ url: u, method: (init && init.method) || 'GET' });
    if (u.startsWith('/api/traducciones')) return json(statusPayload());
    if (u.startsWith('/api/pdf/version')) return json({ ok: true, exists: true, version: u.includes('traduccion') ? 't1' : 'v1' });
    return json({}, 503);
  };
  try { viewer.window.localStorage.clear(); } catch (_) { /* storage blocked */ }
  viewer.window.eval(FOLDS);
  viewer.window.eval(SCRIPT);
  await viewer.viewer('navigateTab', 'preview');
  await flush(8);
  const doc = viewer.document;
  const fold = doc.querySelector('#pane-preview details.exp-fold[data-fold-name="version-documento"]');
  assert.ok(fold, 'the fold exists');
  assert.equal(fold.querySelector('.exp-fold__title').textContent.trim(), 'Versión del documento');
  const judge = doc.querySelector('#pane-preview details.exp-fold[data-fold-name="juez-final"]');
  assert.ok(judge.compareDocumentPosition(fold) & viewer.window.Node.DOCUMENT_POSITION_FOLLOWING);
  fold.open = true;
  await viewer.window.eval('TRANSLATION_PANEL').refresh();
  assert.ok(calls.some((c) => c.url.startsWith('/api/traducciones')));
  fold.querySelector('button.tp-source').click();
  await flush(8);
  const urls = viewer.documentRequests().map((r) => r.url);
  assert.match(urls[urls.length - 1], /^\/api\/pdf\?traduccion=en&t=\d+$/);
  assert.match(doc.querySelector('.pdf-doc-title').textContent, /traducción \(en\)/);
  assert.equal(doc.querySelector('a.btn[download]').getAttribute('href'), '/api/pdf?traduccion=en');
  fold.querySelector('button.tp-source').click();
  await flush(8);
  const back = viewer.documentRequests().map((r) => r.url);
  assert.match(back[back.length - 1], /^\/api\/pdf\?t=\d+$/);
  assert.equal(doc.querySelector('a.btn[download]').getAttribute('href'), '/api/pdf');
  await viewer.viewer('navigateTab', 'sections');
  assert.equal(viewer.window.eval('TRANSLATION_PANEL.polling'), false, 'leaving the preview stops the polling');
});

test('the dashboard loads traduccion-panel.js after the other panels and its catalogues in the head', () => {
  const html = readFileSync(DASHBOARD_INDEX, 'utf8');
  const head = html.slice(0, html.indexOf('</head>'));
  assert.ok(head.includes('<script src="/static/i18n/es/traduccion.js"></script>'));
  assert.ok(head.includes('<script src="/static/i18n/en/traduccion.js"></script>'));
  const novedad = html.indexOf('<script src="/static/novedad-panel.js"></script>');
  assert.ok(html.indexOf('<script src="/static/traduccion-panel.js"></script>') > novedad);
});
