/**
 * «Juez final» and «Estilo y redundancia» inside the PDF preview, papersmith
 * layout (odd/tasks/tablero-juez-novedad.md, S8).
 *
 * The real dashboard runs under jsdom (tests/js/harness.mjs) with the static
 * scripts the harness does not inline (section-folds.js, judge-avance.js and
 * pdf-locate.js) evaluated in the same window, as the browser loads them. The
 * PDF.js double gets per-page text items, so «Ubicar» exercises the real loose
 * search against the main preview viewer: its page indicator and the marks
 * painted over the page container are observed. jsdom has no layout, so the
 * 360 px behaviour is pinned by its CSS rule and checked in a real browser.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';

import { createViewerHarness, flush, DASHBOARD_INDEX, DASHBOARD_STATIC } from './harness.mjs';

const read = (name) => readFileSync(path.join(DASHBOARD_STATIC, name), 'utf8');
const FOLDS = read('section-folds.js');
const JUDGE_AVANCE = read('judge-avance.js');
const LOCATE = read('pdf-locate.js');

const PAGE_TEXT = {
  1: ['Justificación y pertinencia', 'El documento abre con el contexto general del proyecto.'],
  2: ['La región cafetera reúne vein-', 'te municipios con datos dispersos.', 'La segunda oración existe porque el ejemplo', 'lo pide (Doe, 2024) y nada más.'],
  3: ['Metodología', 'El último párrafo cierra la idea con una oración breve.'],
};

const SGR_JUDGE = {
  ok: true, run: '2026-11-demo', flujo: 'sgr', disponible: true, errores: [],
  rubrica: { id: 'conv54', convocatoria: 'Convocatoria 54 SGR', umbral_total: 75, minimos: [], criterios: [
    { id: '1', nombre: 'Calidad técnica', max: 100, subcriterios: [{ id: '1', nombre: 'Calidad técnica', max: 100, modo: 'niveles' }] },
  ] },
  evaluacion: {
    schema: 'morfeo.evaluacion-sgr-consolidada/v1', ronda: 1, fecha: '2026-11-22', rubrica: 'conv54',
    criterios: [{ id: '1', puntaje: 80, componentes: null, nivel_descriptor: '', justificacion: 'Bien.', evidencia: [], para_subir: null }],
    alertas: [], acciones: [], concepto: '', recomienda: true, subtotales: { 1: 80 }, total: 80, elegible: true,
    motivos_no_elegible: [], incompleto: false, verificaciones: [], historial: [{ ronda: 1, fecha: '2026-11-22', total: 80, elegible: true }],
    errores_validacion: [],
  },
};

const BASE_JUDGE = { ok: true, run: '2026-11-demo', flujo: 'base', disponible: false, evaluacion: null, rubrica: null, errores: [] };

const FINAL_ROUND = {
  schema: 'morfeo.juez-avance/v1', etapa: 'final', ronda: 1, fecha: '2026-11-22', puntaje: 78,
  veredicto: 'Propuesta completa y coherente.', resumen_idea: 'Monitoreo hídrico con IA para Caldas, con sensores comunitarios.',
  fortalezas: [{ texto: 'Mapeo 1:1 entre subproblemas y objetivos.', evidencia: '§3 y §7' }],
  debilidades: [{ texto: 'El cronograma no nombra la fase 3.', evidencia: '§14', accion: 'Agregar la fase 3 al Gantt.' }],
  alertas: [], historial: [],
};

const findings = (n) => Array.from({ length: n }, (_, i) => ({
  seccion: '02_justificacion', oracion: i + 1, categoria: 'oracion_larga', fragmento: `Fragmento número ${i + 1} del documento`, orientacion: 'Divide la oración.',
}));

const ESTILO = {
  ok: true, disponible: true, indice: 72, veredicto: 'irregular', aviso: 'Mide legibilidad, no autoría.',
  secciones: [{ seccion: '02_justificacion', indice: 72, palabras: 900 }, { seccion: '10_metodologia', indice: 55, palabras: 1400 }],
  hallazgos: [
    { seccion: '02_justificacion', oracion: 2, categoria: 'oracion_larga', fragmento: 'porque', oracion_texto: 'La segunda oración existe porque el ejemplo lo pide  y nada más.', orientacion: 'Divide la oración.' },
    { seccion: '10_metodologia', oracion: 9, categoria: 'cliche', fragmento: 'cierra la idea con una oración breve', orientacion: 'Usa un verbo directo.' },
    { seccion: '10_metodologia', oracion: 12, categoria: 'cliche', fragmento: 'una frase que el documento compilado nunca tuvo', orientacion: 'Revisa.' },
    ...findings(12),
  ],
  exentos: [],
};

function json(body, status = 200) {
  return { ok: status < 400, status, json: async () => body, text: async () => JSON.stringify(body) };
}

async function dashboard(t, { judge = SGR_JUDGE, estilo = ESTILO, avance = null, folds = null, hash = '' } = {}) {
  const viewer = await createViewerHarness({ numPages: 3 });
  t.after(() => viewer.dispose());
  const requests = [];
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    requests.push({ url: u, method: (init && init.method) || 'GET' });
    if (u.startsWith('/api/judge-avance/run')) return json({ ok: true, etapa: 'final', prompt: '/propuesta-juez-avance final' });
    if (u.startsWith('/api/judge-avance')) return json({ ok: true, run: 'demo', etapa: 'final', disponible: !!avance, evaluacion: avance, archivo: 'artefactos/juez/avance_final.json', errores: [] });
    if (u.startsWith('/api/judge')) return json(judge);
    if (u.startsWith('/api/estilo')) return json(estilo);
    if (u.startsWith('/api/pdf/version')) return json({ ok: true, exists: true, version: 'v1' });
    return json({}, 503);
  };
  // Each fake page answers with the text of PAGE_TEXT, laid out line by line.
  const lib = viewer.window.pdfjsLib;
  const getDocument = lib.getDocument.bind(lib);
  lib.getDocument = (request) => {
    const task = getDocument(request);
    task.promise = task.promise.then((doc) => {
      const stub = doc.pageStub.bind(doc);
      doc.pageStub = (n) => {
        const page = stub(n);
        page.getTextContent = async () => ({
          items: (PAGE_TEXT[n] || []).map((str, i) => ({ str, transform: [10, 0, 0, 10, 72, 700 - i * 14], width: str.length * 5, height: 10 })),
          styles: {},
        });
        return page;
      };
      return doc;
    });
    return task;
  };
  try {
    viewer.window.localStorage.clear();
    if (folds) viewer.window.localStorage.setItem('morfeo.folds', JSON.stringify(folds));
  } catch (_) { /* storage blocked */ }
  viewer.window.eval(FOLDS);
  viewer.window.eval(JUDGE_AVANCE);
  viewer.window.eval(LOCATE);
  viewer.window.eval(`window.__prompts = []; sendTerminalPrompt = async (cmd) => { window.__prompts.push(cmd); return true; };`);
  if (hash) {
    viewer.window.history.replaceState(null, '', `#${hash}`);
    viewer.window.dispatchEvent(new viewer.window.Event('load'));
  }
  await flush(8);
  const $ = (id) => viewer.document.getElementById(id);
  const fold = () => viewer.document.querySelector('details.exp-fold[data-fold-name="juez-final"]');
  const asked = (prefix) => requests.filter((r) => r.url.startsWith(prefix)).length;
  return { viewer, requests, $, fold, asked, document: viewer.document, window: viewer.window };
}

async function openPreview(env) {
  env.viewer.viewer('navigateTab', 'preview');
  await flush(12);
}

const activeTab = (env) => env.window.eval('activeTab');
// jsdom fires a details element's `toggle` on its own (real) timer, as browsers do.
const toggled = () => new Promise((resolve) => setTimeout(resolve, 20)).then(() => flush(4));
const plain = (value) => JSON.parse(JSON.stringify(value));

// --- Layout -------------------------------------------------------------------

test('the «Juez final» and «Estilo y redundancia» tabs are gone and the preview holds both', async (t) => {
  const env = await dashboard(t);
  const labels = Array.from(env.document.querySelectorAll('.tab-nav__btn')).map((b) => b.textContent.trim());
  assert.ok(!labels.includes('Juez final'), labels.join(', '));
  assert.ok(!labels.includes('Estilo y redundancia'), labels.join(', '));
  assert.equal(env.$('pane-judge'), null);
  assert.equal(env.$('pane-estilo'), null);
  const fold = env.fold();
  assert.ok(fold, 'the «Juez final» fold exists');
  assert.ok(fold.closest('#pane-preview .pdf-main-column'), 'it sits in the preview column');
  assert.equal(fold.querySelector('.exp-fold__title').textContent.trim(), 'Juez final');
  assert.equal(fold.open, true, 'open by default');
  const topbar = env.document.querySelector('#pane-preview .pdf-viewer-topbar');
  assert.ok(fold.compareDocumentPosition(topbar) & env.window.Node.DOCUMENT_POSITION_FOLLOWING, 'above the viewer');
  const button = env.$('btnStyleDrawer');
  assert.ok(button && topbar.contains(button), 'the toolbar carries the style button');
  assert.equal(button.textContent.trim(), 'Estilo y redundancia');
  assert.equal(env.$('styleDrawer').hidden, true);
});

test('the duplicate viewer is gone and the page loads pdf-locate.js', async (t) => {
  const env = await dashboard(t);
  const html = readFileSync(DASHBOARD_INDEX, 'utf8');
  assert.equal(existsSync(path.join(DASHBOARD_STATIC, 'estilo-pdf.js')), false);
  assert.doesNotMatch(html, /estilo-pdf/);
  assert.doesNotMatch(html, /EstiloPdf/);
  assert.match(html, /<script src="\/static\/pdf-locate\.js"><\/script>/);
  assert.equal(env.window.EstiloPdf, undefined);
  assert.equal(typeof env.window.PdfLocate.locate, 'function');
});

// --- Redirects ----------------------------------------------------------------

test('#judge and navigateTab(\'judge\') land on the preview with the fold open', async (t) => {
  for (const how of ['hash', 'call']) {
    const env = await dashboard(t, { folds: { 'juez-final': false }, hash: how === 'hash' ? 'judge' : '' });
    if (how === 'call') {
      assert.equal(env.fold().open, false, 'the remembered choice is honoured');
      env.viewer.viewer('navigateTab', 'judge');
      await flush(8);
    }
    assert.equal(activeTab(env), 'preview', how);
    assert.equal(env.window.location.hash, '#preview', how);
    assert.ok(env.$('pane-preview').classList.contains('active'), how);
    assert.equal(env.fold().open, true, how);
    assert.ok(env.asked('/api/judge') > 0, `${how}: the judge is read`);
  }
});

test('#estilo and navigateTab(\'estilo\') land on the preview with the style drawer open', async (t) => {
  for (const how of ['hash', 'call']) {
    const env = await dashboard(t, { hash: how === 'hash' ? 'estilo' : '' });
    if (how === 'call') {
      env.viewer.viewer('navigateTab', 'estilo');
      await flush(8);
    }
    assert.equal(activeTab(env), 'preview', how);
    assert.equal(env.$('styleDrawer').hidden, false, how);
    assert.equal(env.$('btnStyleDrawer').getAttribute('aria-expanded'), 'true', how);
    assert.ok(env.asked('/api/estilo') > 0, `${how}: the report is read`);
    assert.match(env.$('styleDrawer').textContent, /72/);
  }
});

// --- Juez final fold ------------------------------------------------------------

test('the fold reads the judge lazily and polls only on the preview with the fold open', async (t) => {
  const env = await dashboard(t, { folds: { 'juez-final': false } });
  await openPreview(env);
  assert.equal(env.asked('/api/judge'), 0, 'a closed fold reads nothing');
  await env.viewer.advance(5000);
  assert.equal(env.asked('/api/judge'), 0, 'nor polls');
  // jsdom, like the browser, fires `toggle` when the fold opens or closes.
  const fold = env.fold();
  fold.open = true;
  await toggled();
  await flush(6);
  assert.equal(env.asked('/api/judge'), 1, 'opening the fold refreshes it');
  await env.viewer.advance(5000);
  await flush(4);
  assert.equal(env.asked('/api/judge'), 2, 'then it polls every 5 s');
  fold.open = false;
  await toggled();
  await env.viewer.advance(5000);
  await flush(4);
  assert.equal(env.asked('/api/judge'), 2, 'a closed fold stops polling');
  fold.open = true;
  await toggled();
  await flush(6);
  env.viewer.viewer('navigateTab', 'sections');
  const before = env.asked('/api/judge');
  await env.viewer.advance(10000);
  await flush(4);
  assert.equal(env.asked('/api/judge'), before, 'another tab stops polling');
});

test('SGR flow: the fold shows the rubric judge of the convocatoria', async (t) => {
  const env = await dashboard(t, { judge: SGR_JUDGE });
  await openPreview(env);
  const fold = env.fold();
  const summary = env.$('judgeSummary');
  assert.ok(summary && fold.contains(summary), 'the rubric summary renders inside the fold');
  assert.match(summary.textContent, /80\s*\/\s*100/);
  assert.match(summary.textContent, /Convocatoria 54 SGR/);
  assert.equal(env.$('judgeSgr').hidden, false);
  assert.equal(env.$('judgeFinalAvance').hidden, true);
  assert.equal(env.asked('/api/judge-avance'), 0, 'the stage judge is not used in SGR');
  assert.equal(env.$('judgeRunMeta').textContent, 'Corrida 2026-11-demo');
});

test('base flow: the fold mounts the stage judge `final` over the whole proposal', async (t) => {
  const env = await dashboard(t, { judge: BASE_JUDGE, avance: FINAL_ROUND });
  await openPreview(env);
  const root = env.$('judgeFinalAvance');
  assert.equal(root.hidden, false);
  assert.equal(env.$('judgeSgr').hidden, true);
  assert.equal(root.getAttribute('data-judge-avance-etapa'), 'final');
  assert.ok(env.requests.some((r) => r.url === '/api/judge-avance?etapa=final'));
  assert.match(root.querySelector('.ja-score').textContent, /78/);
  assert.match(root.querySelector('.ja-verdict').textContent, /Propuesta completa y coherente/);
  root.querySelector('button.ja-run').click();
  await flush(6);
  assert.deepEqual(JSON.parse(env.window.eval('JSON.stringify(window.__prompts)')), ['/propuesta-juez-avance final']);
  const before = env.requests.filter((r) => r.url === '/api/judge-avance?etapa=final').length;
  await env.viewer.advance(5000);
  await flush(4);
  assert.ok(env.requests.filter((r) => r.url === '/api/judge-avance?etapa=final').length > before, 'it refreshes with the fold');
});

// --- Style drawer ----------------------------------------------------------------

test('the toolbar button opens the drawer with the index, the sections and every finding', async (t) => {
  const env = await dashboard(t);
  await openPreview(env);
  env.$('btnStyleDrawer').click();
  await flush(6);
  const drawer = env.$('styleDrawer');
  assert.equal(drawer.hidden, false);
  assert.match(env.$('estiloResumen').textContent, /Índice 72 de 100/);
  assert.equal(env.$('estiloSecciones').querySelectorAll('tr').length, 2);
  const items = () => env.$('estiloHallazgos').querySelectorAll('[data-finding]');
  const more = env.$('btnEstiloVerTodos');
  assert.equal(items().length, 12);
  assert.equal(more.hidden, false);
  assert.equal(more.textContent, 'Ver los 15 hallazgos');
  more.click();
  assert.equal(items().length, 15);
  assert.equal(env.$('estiloHallazgos').querySelectorAll('[data-locate]').length, 15);
  assert.equal(env.$('estiloHallazgos').querySelector('i'), null, 'values are escaped');
  env.document.dispatchEvent(new env.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert.equal(drawer.hidden, true, 'Escape closes it');
  env.$('btnStyleDrawer').click();
  await flush(4);
  drawer.querySelector('.style-drawer__close').click();
  assert.equal(drawer.hidden, true, '✕ closes it');
  assert.equal(env.$('btnStyleDrawer').getAttribute('aria-expanded'), 'false');
});

test('the drawer coexists with the annotation panel and is not a modal', async (t) => {
  const env = await dashboard(t);
  await openPreview(env);
  env.$('btnStyleDrawer').click();
  await flush(4);
  const drawer = env.$('styleDrawer');
  assert.equal(drawer.getAttribute('aria-modal'), 'false');
  assert.equal(drawer.closest('.drawer-overlay'), null);
  assert.equal(env.$('drawerOverlay').classList.contains('active'), false);
  const panel = env.$('pdfControlPanel');
  assert.ok(panel && !panel.hidden && panel.closest('#pane-preview'), 'the change-control panel stays');
  // Text selected inside the drawer is never taken as a PDF selection.
  const text = drawer.querySelector('#estiloResumen').firstChild;
  const selection = { rangeCount: 1, getRangeAt: () => ({ startContainer: text }) };
  assert.equal(env.viewer.viewer('isSelectionInsidePdf', selection), false);
  env.viewer.viewer('navigateTab', 'sections');
  assert.equal(drawer.hidden, true, 'leaving the preview closes the drawer');
});

test('«Ubicar» finds the sentence in the main viewer, jumps to its page and highlights it', async (t) => {
  const env = await dashboard(t);
  await openPreview(env);
  assert.ok(env.window.eval('pdfDoc !== null'), 'the preview loaded the PDF');
  env.$('btnStyleDrawer').click();
  await flush(6);
  env.$('estiloHallazgos').querySelector('[data-locate="0"]').click();
  await flush(12);
  assert.equal(env.$('estiloLocateStatus').textContent, 'Hallazgo ubicado en la página 2.');
  assert.equal(env.$('inputPdfPage').value, '2');
  assert.equal(env.window.eval('pdfCurrentPage'), 2);
  const marks = env.document.querySelectorAll('#pdfPageContainer-2 .pdf-locate-hl');
  assert.equal(marks.length, 1, 'the fragment «porque» is highlighted');
  assert.ok(env.$('estiloHallazgos').querySelector('[data-finding="0"]').classList.contains('is-located'));
  await env.viewer.advance(5000);
  assert.equal(env.document.querySelectorAll('.pdf-locate-hl').length, 0, 'the highlight fades');
});

test('«Ubicar» falls back to the fragment and says when the text is not in the PDF', async (t) => {
  const env = await dashboard(t);
  await openPreview(env);
  env.$('btnStyleDrawer').click();
  await flush(6);
  const result = await env.viewer.viewer('locateStyleFinding', 1);
  assert.equal(result.found, true);
  assert.equal(result.page, 3);
  assert.equal(env.$('inputPdfPage').value, '3');
  assert.ok(env.document.querySelectorAll('#pdfPageContainer-3 .pdf-locate-hl').length >= 1);
  const missing = await env.viewer.viewer('locateStyleFinding', 2);
  assert.deepEqual(plain(missing), { found: false, reason: 'not-found' });
  assert.equal(env.$('estiloLocateStatus').textContent, 'No encontrado en el PDF: el texto pudo cambiar desde la última compilación.');
  assert.equal(env.$('inputPdfPage').value, '3', 'the viewer stays where it was');
});

test('in the native viewer «Ubicar» explains that it cannot search there', async (t) => {
  const env = await dashboard(t);
  await openPreview(env);
  env.viewer.viewer('toggleNativeViewer');
  env.$('btnStyleDrawer').click();
  await flush(6);
  const result = await env.viewer.viewer('locateStyleFinding', 0);
  assert.deepEqual(plain(result), { found: false, reason: 'native' });
  assert.match(env.$('estiloLocateStatus').textContent, /visor nativo del navegador no permite buscar/);
  assert.equal(env.document.querySelectorAll('.pdf-locate-hl').length, 0);
});

test('without a report the drawer invites to audit, and «Auditar» refreshes it', async (t) => {
  const env = await dashboard(t, { estilo: { ok: true, disponible: false } });
  await openPreview(env);
  env.$('btnStyleDrawer').click();
  await flush(6);
  assert.equal(env.$('estiloResumen').textContent, 'Aún no hay reporte. Usa «Auditar el documento» para generarlo.');
  assert.equal(env.$('btnEstiloVerTodos').hidden, true);
  const audit = env.$('btnEstiloAuditar');
  assert.ok(env.$('styleDrawer').contains(audit));
  audit.click();
  await flush(6);
  assert.ok(env.requests.some((r) => r.url === '/api/estilo/auditar' && r.method === 'POST'));
});

test('on narrow screens the drawer becomes a full-width bottom sheet', () => {
  const html = readFileSync(DASHBOARD_INDEX, 'utf8');
  const rule = html.match(/@media \(max-width: 720px\) \{\s*\.style-drawer \{([^}]*)\}/);
  assert.ok(rule, 'a narrow-screen rule exists for the drawer');
  assert.match(rule[1], /left: 0/);
  assert.match(rule[1], /width: 100%/);
  assert.match(rule[1], /top: auto/);
});
