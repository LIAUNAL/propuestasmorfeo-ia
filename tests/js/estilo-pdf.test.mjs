/**
 * PDF preview of the «Estilo y redundancia» panel (odd/tasks/tablero-juez-novedad.md, S5).
 *
 * The real dashboard runs under jsdom with static/estilo-pdf.js loaded into the
 * same window. PDF.js and fetch are doubled: each fake page carries text items,
 * so locating a finding exercises the real needle search, scroll and highlight.
 * jsdom has no layout, so the fit-width scale falls back to 1 and scroll
 * positions are not observed; the page counter and the highlighted slot are.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { JSDOM } from 'jsdom';

import { createViewerHarness, flush, DASHBOARD_STATIC } from './harness.mjs';

const SCRIPT = readFileSync(path.join(DASHBOARD_STATIC, 'estilo-pdf.js'), 'utf8');

const PAGES = [
  ['Justificación y pertinencia', 'El documento abre con el contexto general del proyecto.'],
  ['La región cafetera reúne vein-', 'te municipios con datos dispersos.', 'La segunda oración existe porque el ejemplo', 'lo pide (Doe, 2024) y nada más.'],
  ['Metodología', 'El último párrafo cierra la idea con una oración breve.'],
];

function fakePdf(pages = PAGES) {
  const documents = [];
  const page = (n) => ({
    getViewport: ({ scale }) => ({ width: 600 * scale, height: 800 * scale, scale, transform: [scale, 0, 0, -scale, 0, 800 * scale] }),
    render: () => ({ promise: Promise.resolve(), cancel() {} }),
    getTextContent: async () => ({
      items: pages[n - 1].map((str, i) => ({ str, transform: [10, 0, 0, 10, 72, 700 - i * 14], width: str.length * 5, height: 10 })),
    }),
  });
  const lib = {
    GlobalWorkerOptions: {},
    getDocument(request) {
      const doc = { numPages: pages.length, destroyed: false, getPage: async (n) => page(n), destroy() { this.destroyed = true; } };
      documents.push({ url: request.url, doc });
      return { promise: Promise.resolve(doc) };
    },
  };
  return { lib, documents };
}

function json(body, status = 200) {
  return { ok: status < 400, status, json: async () => body, text: async () => JSON.stringify(body) };
}

async function dashboard(t, { pdf = { exists: true, version: 'v1' }, report = { disponible: false }, lib = fakePdf() } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const env = { pdf, report, requests: [], lib };
  viewer.window.fetch = async (url) => {
    const u = String(url);
    env.requests.push(u);
    if (u.startsWith('/api/pdf/version')) return env.pdf ? json({ ok: true, ...env.pdf }) : json({}, 404);
    if (u.startsWith('/api/estilo')) return json({ ok: true, ...env.report });
    return json({}, 503);
  };
  // The harness inlines only the scripts it knows; this one loads the same way
  // the page loads it, before anything asks for it.
  if (!viewer.window.EstiloPdf) viewer.window.eval(SCRIPT);
  viewer.window.pdfjsLib = lib ? lib.lib : undefined;
  env.viewer = viewer;
  env.estilo = viewer.window.EstiloPdf;
  env.$ = (id) => viewer.document.getElementById(id);
  return env;
}

async function openEstilo(env) {
  env.viewer.viewer('navigateTab', 'estilo');
  await flush(8);
  await env.estilo.sync();
  await flush(4);
}

// Values built inside the jsdom window carry its prototypes; compare them as data.
const plain = (value) => JSON.parse(JSON.stringify(value));

const SENTENCE = 'La segunda oración existe porque el ejemplo lo pide  y nada más.';

// --- Needles ------------------------------------------------------------------

function bare() {
  const dom = new JSDOM('<!doctype html><body></body>', { runScripts: 'dangerously' });
  dom.window.eval(SCRIPT);
  return dom.window.EstiloPdf;
}

test('normalization ignores accents, case, ligatures, hyphenation, whitespace and LaTeX', () => {
  const { normalize } = bare();
  assert.equal(normalize('Región  CAFETERA'), 'regioncafetera');
  assert.equal(normalize('e\u{FB01}ciencia'), 'eficiencia');
  assert.equal(normalize('e\u{FB03}ciente'), 'efficiente');
  assert.equal(normalize('vein-\nte munici\u{00AD}pios'), 'veintemunicipios');
  assert.equal(normalize('\\textbf{Región}~«cafetera»'), 'regioncafetera');
  assert.equal(normalize('7,4 %'), '74');
});

test('needles come from the sentence first, never cross a citation, then from the fragment', () => {
  const { needlesFor } = bare();
  // «y nada más.» follows the dropped citation and is too short to stand alone.
  assert.deepEqual(plain(needlesFor({ fragmento: 'porque', oracion_texto: SENTENCE })), ['La segunda oración existe porque el ejemplo']);
  assert.deepEqual(plain(needlesFor({ fragmento: 'x', oracion_texto: 'Según (cita), el monitoreo continuo de la cuenca del río Chinchiná reduce la incertidumbre.' })), [
    'el monitoreo continuo de la cuenca del',
    'cuenca del río Chinchiná reduce la incertidumbre.',
  ]);
  assert.deepEqual(plain(needlesFor({ fragmento: 'la comunidad universitaria del eje cafetero de Caldas y Risaralda' })), [
    'la comunidad universitaria del eje cafetero de',
    'del eje cafetero de Caldas y Risaralda',
  ]);
  assert.deepEqual(plain(needlesFor({ fragmento: 'porque' })), [], 'a lone short fragment is too weak to search');
});

test('each needle is tried across the whole document before the next one', async () => {
  const { search, indexPage } = bare();
  const pages = [['alpha beta gamma delta epsilon'], ['zeta eta theta iota kappa lambda']]
    .map((lines) => indexPage(lines.map((str) => ({ str }))));
  const hit = await search((n) => pages[n - 1], 2, ['zeta eta theta iota', 'alpha beta gamma delta']);
  assert.equal(hit.page, 2);
  const fallback = await search((n) => pages[n - 1], 2, ['nothing like this here', 'alpha beta gamma delta']);
  assert.equal(fallback.page, 1);
  assert.equal(fallback.needle, 'alpha beta gamma delta');
  assert.equal(await search((n) => pages[n - 1], 2, ['nothing like this here']), null);
});

// --- Viewer lifecycle ---------------------------------------------------------

test('the viewer stays idle until the estilo tab opens', async (t) => {
  const env = await dashboard(t);
  await flush(8);
  assert.equal(env.estilo.state().mode, 'idle');
  assert.equal(env.lib.documents.length, 0);
  assert.ok(!env.requests.some((u) => u.startsWith('/api/pdf/version') || u.startsWith('/api/pdf?')), env.requests.join(', '));

  await openEstilo(env);
  assert.equal(env.estilo.state().mode, 'pdfjs');
  assert.deepEqual(env.lib.documents.map((d) => d.url), ['/api/pdf?t=v1']);
  assert.equal(env.$('estiloPdfPages').querySelectorAll('.estilo-pdf-page').length, 3);
  assert.equal(env.$('estiloPdfPageInfo').textContent, 'Página 1 de 3');
  assert.ok(env.estilo.state().rendered.includes(1), 'the current page is painted');
  assert.ok(env.estilo.state().polling, 'the open tab polls /api/pdf/version');
});

test('a new main.pdf reloads the viewer and keeps the current page', async (t) => {
  const env = await dashboard(t);
  await openEstilo(env);
  await env.estilo.goToPage(3);
  assert.equal(env.$('estiloPdfPageInfo').textContent, 'Página 3 de 3');

  await env.viewer.advance(env.estilo.POLL_MS);
  await flush(8);
  assert.equal(env.lib.documents.length, 1, 'an unchanged version does not reload');

  env.pdf = { exists: true, version: 'v2' };
  await env.viewer.advance(env.estilo.POLL_MS);
  await flush(8);
  await env.estilo.sync();
  await flush(4);
  assert.deepEqual(env.lib.documents.map((d) => d.url), ['/api/pdf?t=v1', '/api/pdf?t=v2']);
  assert.ok(env.lib.documents[0].doc.destroyed, 'the old document is released');
  assert.equal(env.estilo.state().currentPage, 3);
  assert.equal(env.$('estiloPdfPageInfo').textContent, 'Página 3 de 3');
});

test('leaving the tab or hiding the browser tab pauses the polling', async (t) => {
  const env = await dashboard(t);
  await openEstilo(env);
  assert.equal(env.estilo.state().polling, true, 'the open tab polls');
  env.viewer.viewer('navigateTab', 'sections');
  await flush(4);
  assert.equal(env.estilo.state().polling, false);
  env.pdf = { exists: true, version: 'v2' };
  await env.viewer.advance(env.estilo.POLL_MS * 3);
  await flush(8);
  assert.equal(env.lib.documents.length, 1, 'no reload while the tab is closed');

  await openEstilo(env);
  assert.equal(env.lib.documents.length, 2, 'reopening catches up with main.pdf');
  Object.defineProperty(env.viewer.document, 'hidden', { configurable: true, get: () => true });
  env.viewer.document.dispatchEvent(new env.viewer.window.Event('visibilitychange'));
  assert.equal(env.estilo.state().polling, false);
});

test('without pdfjsLib the browser viewer shows the PDF in an iframe', async (t) => {
  const env = await dashboard(t, { lib: null });
  await openEstilo(env);
  assert.equal(env.estilo.state().mode, 'frame');
  const frame = env.$('estiloPdfFrame');
  assert.equal(frame.hidden, false);
  assert.equal(frame.getAttribute('src'), '/api/pdf?t=v1#page=1');
  const result = await env.estilo.locate({ fragmento: 'veinte municipios con datos dispersos' });
  assert.equal(result.found, false);
  assert.equal(env.$('estiloPdfStatus').textContent, env.estilo.MESSAGES.frameOnly);
});

test('without main.pdf the panel shows an empty state', async (t) => {
  const env = await dashboard(t, { pdf: { exists: false, version: null } });
  await openEstilo(env);
  assert.equal(env.estilo.state().mode, 'empty');
  assert.equal(env.$('estiloPdfEmpty').hidden, false);
  assert.equal(env.$('estiloPdfPages').hidden, true);
  assert.equal(env.$('estiloPdfStatus').textContent, env.estilo.MESSAGES.empty);
  assert.equal(env.lib.documents.length, 0);
  assert.equal((await env.estilo.locate({ fragmento: 'la región cafetera reúne veinte' })).reason, 'no-pdf');
});

// --- Locating findings ----------------------------------------------------------

test('a finding is found by its sentence, scrolled to and highlighted', async (t) => {
  const env = await dashboard(t);
  await openEstilo(env);
  const result = await env.estilo.locate({ fragmento: 'porque', oracion_texto: SENTENCE });
  assert.equal(result.found, true);
  assert.equal(result.page, 2);
  assert.equal(env.estilo.state().currentPage, 2);
  assert.equal(env.$('estiloPdfPageInfo').textContent, 'Página 2 de 3');
  assert.equal(env.$('estiloPdfStatus').textContent, 'Hallazgo ubicado en la página 2.');
  const marks = env.viewer.document.querySelectorAll('.estilo-pdf-page[data-page="2"] .estilo-pdf-hl');
  assert.equal(marks.length, 1, 'the fragment «porque» sits in one text item');
  await env.viewer.advance(5000);
  assert.equal(env.viewer.document.querySelectorAll('.estilo-pdf-hl').length, 0, 'the highlight fades');
});

test('a sentence hyphenated across lines is still found', async (t) => {
  const env = await dashboard(t);
  await openEstilo(env);
  const result = await env.estilo.locate({ fragmento: 'veinte municipios con datos', oracion_texto: 'La región cafetera reúne veinte municipios con datos dispersos.' });
  assert.equal(result.page, 2);
  assert.equal(env.viewer.document.querySelectorAll('.estilo-pdf-page[data-page="2"] .estilo-pdf-hl').length, 2);
});

test('when the opening words changed, the closing words still find the page', async (t) => {
  const env = await dashboard(t);
  await openEstilo(env);
  const result = await env.estilo.locate({ fragmento: 'breve', oracion_texto: 'Este párrafo, que antes decía otra cosa, cierra la idea con una oración breve.' });
  assert.equal(result.found, true);
  assert.equal(result.page, 3);
  assert.equal(result.needle, 'cierra la idea con una oración breve.');
  assert.equal(env.$('estiloPdfPageInfo').textContent, 'Página 3 de 3');
});

test('a finding that is not in the PDF says so', async (t) => {
  const env = await dashboard(t);
  await openEstilo(env);
  const result = await env.estilo.locate({ fragmento: 'una frase que el documento compilado nunca tuvo' });
  assert.deepEqual(plain(result), { found: false, reason: 'not-found' });
  assert.equal(env.$('estiloPdfStatus').textContent, 'No encontrado en el PDF: el texto pudo cambiar desde la última compilación.');
  assert.equal(env.estilo.state().currentPage, 1);
});

// --- Findings table ------------------------------------------------------------

const many = (n) => Array.from({ length: n }, (_, i) => ({
  seccion: '02_justificacion', oracion: i + 1, categoria: 'oracion_larga', fragmento: `Fragmento número ${i + 1} del documento`, orientacion: 'Divide la oración.',
}));

test('every finding is reachable and each row locates its own finding', async (t) => {
  const env = await dashboard(t, { report: { disponible: true, indice: 80, veredicto: 'fluida', aviso: '', secciones: [], hallazgos: many(15), exentos: [] } });
  await openEstilo(env);
  const rows = () => env.$('estiloHallazgos').querySelectorAll('tr');
  const more = env.$('btnEstiloVerTodos');
  assert.equal(rows().length, 12);
  assert.equal(more.hidden, false);
  assert.equal(more.textContent, 'Ver los 15 hallazgos');

  more.click();
  assert.equal(rows().length, 15);
  assert.equal(more.textContent, 'Ver solo los primeros 12');
  assert.equal(env.$('estiloHallazgos').querySelectorAll('[data-locate]').length, 15);

  const asked = [];
  env.estilo.locate = async (finding) => { asked.push(finding); return { found: false }; };
  rows()[13].querySelector('[data-locate]').click();
  await flush(2);
  assert.equal(asked.length, 1);
  assert.equal(asked[0].fragmento, 'Fragmento número 14 del documento');
  assert.ok(rows()[13].classList.contains('is-located'));
});

test('a short report shows every finding without the toggle, and no report keeps its message', async (t) => {
  const env = await dashboard(t, { report: { disponible: true, indice: 90, veredicto: 'fluida', aviso: '', secciones: [], hallazgos: many(3), exentos: [] } });
  await openEstilo(env);
  assert.equal(env.$('estiloHallazgos').querySelectorAll('tr').length, 3);
  assert.equal(env.$('btnEstiloVerTodos').hidden, true);

  env.viewer.viewer('renderStyleReport', { disponible: false });
  assert.equal(env.$('estiloResumen').textContent, 'Aún no hay reporte. Usa «Auditar el documento» para generarlo.');
  assert.equal(env.$('estiloHallazgos').querySelectorAll('tr').length, 0);
  assert.equal(env.$('btnEstiloVerTodos').hidden, true);
});
