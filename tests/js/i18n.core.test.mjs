/**
 * Language switch of the dashboard (S2 of odd/tasks/idioma-tablero-traduccion.md).
 *
 * The real page runs under jsdom with static/i18n.js and the core catalogues
 * loaded in <head>, as in the browser. Spanish is the default and must look
 * exactly as before; English is chosen with the top-bar selector, persists,
 * applies before the page shows and re-renders what the script drew.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { JSDOM } from 'jsdom';

import { createViewerHarness, flush, readDashboardHtml } from './harness.mjs';

const STATUS = {
  active_run: 'run-1',
  all_runs: ['run-1'],
  flujo: 'base',
  run_details: { title: 'Proyecto de prueba' },
  totals: { sections_count: 3, total_words: 1200, gates_passed: 1, gates_total: 13 },
  sections: [],
  gates: [],
  telemetria: [],
  artifacts: [],
  pipeline_units: [
    { id: 'fase0', name: 'Intake', kind: 'pre', gate: null, next: 'fase1a', agents: [], skills: [], sections: [] },
    { id: 'fase1a', name: 'Scoping', kind: 'step', gate: 'G1a', next: 'done', agents: ['investigador'], skills: [], sections: [] },
  ],
};

async function dashboard(t) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url) => (String(url).startsWith('/api/status')
    ? { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(STATUS)), text: async () => '' }
    : { ok: false, status: 503, json: async () => ({}), text: async () => '' });
  await viewer.window.loadStatus({ fresh: true });
  await flush(6);
  return viewer;
}

const $ = (viewer, id) => viewer.document.getElementById(id);
const tabLabel = (viewer, tab) => Array.from(viewer.document.querySelectorAll('.tab-nav__btn'))
  .find((b) => (b.getAttribute('onclick') || '').includes(`'${tab}'`)).textContent.trim();
const visibleText = (viewer) => viewer.document.body.textContent.replace(/\s+/g, ' ').trim();

test('the dashboard opens in Spanish with the selector on ES', async (t) => {
  const viewer = await dashboard(t);
  assert.equal(viewer.document.documentElement.lang, 'es');
  assert.equal($(viewer, 'langSelect').value, 'es');
  assert.equal(tabLabel(viewer, 'flow'), 'Flujo general');
  assert.equal($(viewer, 'flujoBadge').textContent, 'Flujo base');
  assert.match($(viewer, 'totalsContainer').textContent, /3 secciones/);
  assert.equal($(viewer, 'themeBtn').getAttribute('title'), 'Cambiar tema');
});

test('choosing EN in the selector translates the markup and persists', async (t) => {
  const viewer = await dashboard(t);
  const select = $(viewer, 'langSelect');
  select.value = 'en';
  select.dispatchEvent(new viewer.window.Event('change'));
  await flush(6);
  assert.equal(viewer.window.localStorage.getItem('morfeo.lang'), 'en');
  assert.equal(viewer.document.documentElement.lang, 'en');
  assert.equal(select.value, 'en');
  assert.equal(tabLabel(viewer, 'flow'), 'Overview');
  assert.equal(tabLabel(viewer, 'preview'), 'PDF preview');
  assert.equal($(viewer, 'textSizeSelect').getAttribute('aria-label'), 'Text size');
  assert.equal($(viewer, 'themeBtn').getAttribute('title'), 'Switch theme');
  assert.equal($(viewer, 'runSelector').value, 'run-1', 'machine values stay as they are');
});

test('a language change re-renders what the inline script drew', async (t) => {
  const viewer = await dashboard(t);
  viewer.window.i18n.setLanguage('en');
  await flush(6);
  assert.equal($(viewer, 'themeBtn').textContent.trim(), '☀️ Light');
  assert.equal($(viewer, 'flujoBadge').textContent, 'Base flow');
  assert.match($(viewer, 'totalsContainer').textContent, /3 sections/);
  assert.match($(viewer, 'totalsContainer').textContent, /1,200 words/);
  assert.equal($(viewer, 'runSelector').value, 'run-1');
});

test('switching back to ES restores the exact Spanish text', async (t) => {
  const viewer = await dashboard(t);
  const before = visibleText(viewer);
  viewer.window.i18n.setLanguage('en');
  await flush(6);
  assert.notEqual(visibleText(viewer), before);
  viewer.window.i18n.setLanguage('es');
  await flush(6);
  assert.equal(visibleText(viewer), before);
});

test('a value the script wrote is never overwritten by the catalogue', async (t) => {
  const viewer = await dashboard(t);
  assert.equal($(viewer, 'metaProposalTitle').textContent, 'Proyecto de prueba');
  viewer.window.i18n.setLanguage('en');
  await flush(6);
  assert.equal($(viewer, 'metaProposalTitle').textContent, 'Proyecto de prueba');
});

test('tables defined at load time follow the language', async (t) => {
  const viewer = await dashboard(t);
  assert.equal(viewer.window.eval('PHASE_GUIDES.fase5_sgr.panel.label'), 'Ver productos e indicadores');
  assert.equal(viewer.window.eval('PHASE_GUIDES.fase5_sgr.panel.tab'), 'productos');
  viewer.window.i18n.setLanguage('en');
  assert.equal(viewer.window.eval('PHASE_GUIDES.fase5_sgr.panel.label'), 'See products and indicators');
  assert.equal(viewer.window.eval('PHASE_GUIDES.fase5_sgr.panel.tab'), 'productos');
  assert.equal(viewer.window.eval('TREE_STATUS.aprobado[0]'), 'Approved');
});

test('a saved English choice applies before the page shows, with no Spanish flash', async () => {
  let pendingAtParse = null;
  const dom = new JSDOM(readDashboardHtml(), {
    runScripts: 'dangerously',
    url: 'http://localhost:8000/',
    beforeParse(window) {
      window.localStorage.setItem('morfeo.lang', 'en');
      window.fetch = async () => ({ ok: false, status: 503, json: async () => ({}), text: async () => '' });
      // Capture on window runs before the runtime's own DOMContentLoaded listener.
      window.addEventListener('DOMContentLoaded', () => {
        pendingAtParse = 'i18nPending' in window.document.documentElement.dataset;
      }, true);
    },
  });
  await new Promise((resolve) => dom.window.addEventListener('load', resolve));
  try {
    const doc = dom.window.document;
    assert.equal(pendingAtParse, true, 'the page is hidden while the markup is still Spanish');
    assert.equal('i18nPending' in doc.documentElement.dataset, false, 'and shown once translated');
    assert.equal(doc.documentElement.lang, 'en');
    assert.equal(doc.getElementById('langSelect').value, 'en');
    const overview = Array.from(doc.querySelectorAll('.tab-nav__btn')).find((b) => (b.getAttribute('onclick') || '').includes("'flow'"));
    assert.equal(overview.textContent.trim(), 'Overview');
    assert.equal(doc.getElementById('themeBtn').getAttribute('title'), 'Switch theme');
  } finally {
    dom.window.close();
  }
});

test('an unknown saved language falls back to Spanish', () => {
  const dom = new JSDOM(readDashboardHtml(), {
    runScripts: 'dangerously',
    url: 'http://localhost:8000/',
    beforeParse(window) {
      window.localStorage.setItem('morfeo.lang', 'fr');
      window.fetch = async () => ({ ok: false, status: 503, json: async () => ({}), text: async () => '' });
    },
  });
  try {
    assert.equal(dom.window.document.documentElement.lang, 'es');
    assert.equal(dom.window.document.getElementById('langSelect').value, 'es');
    assert.equal('i18nPending' in dom.window.document.documentElement.dataset, false);
  } finally {
    dom.window.close();
  }
});
