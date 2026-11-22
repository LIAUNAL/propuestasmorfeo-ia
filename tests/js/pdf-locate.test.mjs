/**
 * static/pdf-locate.js: the loose search that «Ubicar» runs against the PDF
 * preview viewer (odd/tasks/tablero-juez-novedad.md, S8).
 *
 * The module is evaluated in a bare jsdom window. The adapter stands in for the
 * main preview viewer: each fake page carries pdf.js text items, so `locate`
 * exercises the real needles, search, refined range and highlight boxes. The
 * wiring into the dashboard viewer is covered by preview-judge-style.test.mjs.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { JSDOM } from 'jsdom';

import { DASHBOARD_STATIC } from './harness.mjs';

const SCRIPT = readFileSync(path.join(DASHBOARD_STATIC, 'pdf-locate.js'), 'utf8');

const PAGES = [
  ['Justificación y pertinencia', 'El documento abre con el contexto general del proyecto.'],
  ['La región cafetera reúne vein-', 'te municipios con datos dispersos.', 'La segunda oración existe porque el ejemplo', 'lo pide (Doe, 2024) y nada más.'],
  ['Metodología', 'El último párrafo cierra la idea con una oración breve.'],
];

const SENTENCE = 'La segunda oración existe porque el ejemplo lo pide  y nada más.';

// Values built inside the jsdom window carry its prototypes; compare them as data.
const plain = (value) => JSON.parse(JSON.stringify(value));

function bare() {
  const dom = new JSDOM('<!doctype html><body><div id="page"></div></body>', { runScripts: 'outside-only' });
  dom.window.eval(SCRIPT);
  return { api: dom.window.PdfLocate, window: dom.window };
}

function adapter(overrides = {}) {
  const revealed = [];
  const asked = [];
  const items = (n) => PAGES[n - 1].map((str, i) => ({ str, transform: [10, 0, 0, 10, 72, 700 - i * 14], width: str.length * 5, height: 10 }));
  return {
    revealed,
    asked,
    mode: 'pdfjs',
    numPages: PAGES.length,
    pageItems: async (n) => { asked.push(n); return items(n); },
    viewport: async () => ({ width: 600, height: 800, scale: 1, transform: [1, 0, 0, -1, 0, 800] }),
    reveal: async (page, boxes) => { revealed.push({ page, boxes: plain(boxes) }); },
    ...overrides,
  };
}

test('normalization ignores accents, case, ligatures, hyphenation, whitespace and LaTeX', () => {
  const { normalize } = bare().api;
  assert.equal(normalize('Región  CAFETERA'), 'regioncafetera');
  assert.equal(normalize('e\u{FB01}ciencia'), 'eficiencia');
  assert.equal(normalize('e\u{FB03}ciente'), 'efficiente');
  assert.equal(normalize('vein-\nte munici\u{00AD}pios'), 'veintemunicipios');
  assert.equal(normalize('\\textbf{Región}~«cafetera»'), 'regioncafetera');
  assert.equal(normalize('7,4 %'), '74');
});

test('needles come from the sentence first, never cross a citation, then from the fragment', () => {
  const { needlesFor } = bare().api;
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
  const { search, indexPage } = bare().api;
  const pages = [['alpha beta gamma delta epsilon'], ['zeta eta theta iota kappa lambda']]
    .map((lines) => indexPage(lines.map((str) => ({ str }))));
  const hit = await search((n) => pages[n - 1], 2, ['zeta eta theta iota', 'alpha beta gamma delta']);
  assert.equal(hit.page, 2);
  const fallback = await search((n) => pages[n - 1], 2, ['nothing like this here', 'alpha beta gamma delta']);
  assert.equal(fallback.page, 1);
  assert.equal(fallback.needle, 'alpha beta gamma delta');
  assert.equal(await search((n) => pages[n - 1], 2, ['nothing like this here']), null);
});

test('locate finds the sentence, reveals its page with the fragment boxes and reports it', async () => {
  const { api } = bare();
  const a = adapter();
  const result = await api.locate({ fragmento: 'porque', oracion_texto: SENTENCE }, a);
  assert.equal(result.found, true);
  assert.equal(result.page, 2);
  assert.equal(result.needle, 'La segunda oración existe porque el ejemplo');
  assert.equal(a.revealed.length, 1);
  assert.equal(a.revealed[0].page, 2);
  assert.equal(a.revealed[0].boxes.length, 1, 'the fragment «porque» sits in one text item');
  assert.equal(api.message(result), 'Hallazgo ubicado en la página 2.');
  assert.deepEqual(a.asked.filter((n, i, all) => all.indexOf(n) === i), a.asked, 'each page is read once per search');
});

test('a sentence hyphenated across lines is still found and both lines are boxed', async () => {
  const { api } = bare();
  const a = adapter();
  const result = await api.locate({ fragmento: 'veinte municipios con datos', oracion_texto: 'La región cafetera reúne veinte municipios con datos dispersos.' }, a);
  assert.equal(result.page, 2);
  assert.equal(a.revealed[0].boxes.length, 2);
});

test('when the opening words changed, the closing words find the page; then the fragment', async () => {
  const { api } = bare();
  let result = await api.locate({ fragmento: 'breve', oracion_texto: 'Este párrafo, que antes decía otra cosa, cierra la idea con una oración breve.' }, adapter());
  assert.equal(result.found, true);
  assert.equal(result.page, 3);
  assert.equal(result.needle, 'cierra la idea con una oración breve.');
  result = await api.locate({ fragmento: 'abre con el contexto general del proyecto', oracion_texto: 'Una oración que ya no existe en ninguna versión compilada.' }, adapter());
  assert.equal(result.page, 1);
  assert.equal(result.needle, 'abre con el contexto general del proyecto');
});

test('a finding that is not in the PDF says so and reveals nothing', async () => {
  const { api } = bare();
  const a = adapter();
  const result = await api.locate({ fragmento: 'una frase que el documento compilado nunca tuvo' }, a);
  assert.deepEqual(plain(result), { found: false, reason: 'not-found' });
  assert.equal(a.revealed.length, 0);
  assert.equal(api.message(result), 'No encontrado en el PDF: el texto pudo cambiar desde la última compilación.');
});

test('the native viewer, a missing PDF, a finding without text and a reload each have their own answer', async () => {
  const { api } = bare();
  const finding = { fragmento: 'abre con el contexto general del proyecto' };
  const native = await api.locate(finding, adapter({ mode: 'native' }));
  assert.deepEqual(plain(native), { found: false, reason: 'native' });
  assert.match(api.message(native), /visor nativo del navegador no permite buscar/);
  assert.deepEqual(plain(await api.locate(finding, adapter({ mode: 'none' }))), { found: false, reason: 'no-pdf' });
  assert.deepEqual(plain(await api.locate(finding, adapter({ numPages: 0 }))), { found: false, reason: 'no-pdf' });
  assert.deepEqual(plain(await api.locate({ fragmento: 'porque' }, adapter())), { found: false, reason: 'no-text' });
  const reloaded = await api.locate(finding, adapter({ isCurrent: () => false }));
  assert.deepEqual(plain(reloaded), { found: false, reason: 'reloaded' });
  for (const reason of ['native', 'no-pdf', 'no-text', 'reloaded', 'not-found']) {
    const text = api.message({ found: false, reason });
    assert.doesNotMatch(text, /—|--/, reason);
  }
});

test('highlight paints fading marks over one page and clears the previous ones', async () => {
  const { api, window } = bare();
  const page = window.document.getElementById('page');
  const marks = api.highlight(page, [{ left: 0.1, top: 0.2, width: 0.3, height: 0.05 }], { ms: 20 });
  assert.equal(marks.length, 1);
  assert.equal(page.querySelectorAll('.pdf-locate-layer .pdf-locate-hl').length, 1);
  assert.equal(parseFloat(marks[0].style.left), 10);
  assert.equal(parseFloat(marks[0].style.top), 20);
  api.highlight(page, [{ left: 0, top: 0, width: 0.1, height: 0.1 }, { left: 0, top: 0.5, width: 0.1, height: 0.1 }], { ms: 20 });
  assert.equal(page.querySelectorAll('.pdf-locate-hl').length, 2, 'the previous finding is cleared');
  assert.equal(page.querySelectorAll('.pdf-locate-layer').length, 1);
  await new Promise((resolve) => setTimeout(resolve, 40));
  assert.equal(page.querySelectorAll('.pdf-locate-hl').length, 0, 'the highlight fades');
});
