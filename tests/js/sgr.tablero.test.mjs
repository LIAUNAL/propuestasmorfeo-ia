/**
 * Tablero por flujo (odd/tasks/sgr-flujo-convocatorias.md, S9).
 * En SGR se ocultan Flujo general, Telemetría y los grafos de vault y
 * manuscrito; Pipeline abre por defecto; un id tdr* no cae en las reglas de §3;
 * Secciones lista los capítulos del TDR y Estilo lee /api/estilo.
 */

import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { readDashboardHtml } from './harness.mjs';

// index.html with its local /static scripts inlined, as the browser runs it.
const INDEX = readDashboardHtml();

const CAPITULOS = {
  ok: true,
  fuente: 'Anexo 2',
  capitulos: [
    { numero: 1, titulo: 'IDENTIFICACIÓN DEL PROYECTO', estado: 'escrito', archivos: [{ nombre: 'tdr01_identificacion', existe: true, palabras: 120 }] },
    { numero: 2, titulo: 'RESUMEN <b>EJECUTIVO</b>', estado: 'vacio', archivos: [{ nombre: '00_frontmatter', existe: false, palabras: 0 }] },
  ],
};

const ESTILO = {
  ok: true,
  disponible: true,
  indice: 72,
  veredicto: 'irregular',
  aviso: 'Mide legibilidad, no autoría.',
  secciones: [{ seccion: '02_justificacion', indice: 72, palabras: 900 }],
  hallazgos: [{ seccion: '02_justificacion', parrafo: 2, categoria: 'cliche', fragmento: 'juega un <i>papel</i>', orientacion: 'Usar un verbo directo.' }],
  exentos: [{ termino: 'objetivo general' }],
};

const windows = [];
after(() => windows.forEach(w => w.close()));
const tick = () => new Promise(resolve => setTimeout(resolve, 0));

async function boot(flujo, { hash = '', capitulos = CAPITULOS, estilo = ESTILO } = {}) {
  const calls = [];
  const dom = new JSDOM(INDEX, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: `http://localhost:8000/${hash}`,
    beforeParse(window) {
      window.localStorage = { _d: {}, getItem(k) { return this._d[k] || null; }, setItem(k, v) { this._d[k] = String(v); } };
      window.fetch = (url) => {
        const u = String(url);
        calls.push(u);
        let body = { flujo, sections: [], gates: [], telemetria: [], pipeline_units: [] };
        if (u.startsWith('/api/guide/sgr')) body = { ok: true, flujo, blocks: {} };
        if (u.startsWith('/api/tdr/capitulos')) body = capitulos;
        if (u.startsWith('/api/estilo')) body = estilo;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body), text: () => Promise.resolve('') });
      };
      window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      window.requestAnimationFrame = (cb) => setTimeout(cb, 0);
    },
  });
  const { window } = dom;
  windows.push(window);
  for (let i = 0; i < 25; i++) await tick();
  return { window, doc: window.document, calls };
}

const btn = (doc, tab) => Array.from(doc.querySelectorAll('.tab-nav__btn'))
  .find(b => (b.getAttribute('onclick') || '').includes(`'${tab}'`));

test('SGR: Pipeline abre por defecto y se ocultan Flujo general y Telemetría', async () => {
  const { doc } = await boot('sgr');
  assert.ok(btn(doc, 'flow').hidden);
  assert.ok(btn(doc, 'telemetria').hidden);
  assert.ok(doc.getElementById('pane-pipeline').classList.contains('active'));
  assert.ok(!doc.getElementById('pane-flow').classList.contains('active'));
});

test('SGR: Telemetría sigue disponible por su enlace del pie', async () => {
  const { doc } = await boot('sgr');
  const link = doc.getElementById('footerTelemetria');
  assert.ok(link && !link.hidden);
});

test('SGR: el enlace directo a #flow termina en Pipeline', async () => {
  const { doc } = await boot('sgr', { hash: '#flow' });
  assert.ok(doc.getElementById('pane-pipeline').classList.contains('active'));
});

test('SGR: solo queda el grafo de literatura', async () => {
  const { doc } = await boot('sgr');
  assert.ok(doc.getElementById('btnGraphVault').hidden);
  assert.ok(doc.getElementById('btnGraphManuscript').hidden);
  assert.ok(!doc.getElementById('btnGraphPapers').hidden);
});

test('Base: pestañas y grafos quedan como estaban', async () => {
  const { doc, calls } = await boot('base');
  assert.ok(!btn(doc, 'flow').hidden);
  assert.ok(!btn(doc, 'telemetria').hidden);
  assert.ok(!doc.getElementById('btnGraphVault').hidden);
  assert.ok(doc.getElementById('pane-flow').classList.contains('active'));
  assert.ok(doc.getElementById('footerTelemetria').hidden);
  assert.ok(!calls.some(u => u.startsWith('/api/tdr/capitulos')));
});

test('SGR: un id tdr* no muestra las reglas de §3', async () => {
  const { window, doc } = await boot('sgr');
  window.openSectionStructure('tdr01_identificacion');
  for (let i = 0; i < 10; i++) await tick();
  assert.doesNotMatch(doc.getElementById('secModalTitle').textContent, /problema/i);
  assert.match(doc.getElementById('secModalTitle').textContent, /IDENTIFICACIÓN DEL PROYECTO/);
});

test('SGR: Secciones lista los capítulos del TDR con su estado, sin inyectar HTML', async () => {
  const { window, doc } = await boot('sgr');
  window.navigateTab('sections');
  for (let i = 0; i < 10; i++) await tick();
  const panel = doc.getElementById('tdrChaptersPanel');
  assert.ok(!panel.hidden);
  assert.match(panel.textContent, /IDENTIFICACIÓN DEL PROYECTO/);
  assert.match(panel.textContent, /1 de 2/);
  assert.equal(panel.querySelector('b'), null);
});

test('SGR sin estructura del TDR: el panel de capítulos no aparece', async () => {
  const { window, doc } = await boot('sgr', { capitulos: { ok: true, capitulos: [] } });
  window.navigateTab('sections');
  for (let i = 0; i < 10; i++) await tick();
  assert.ok(doc.getElementById('tdrChaptersPanel').hidden);
});

test('Estilo: muestra índice, aviso y hallazgos en ambos flujos, sin inyectar HTML', async () => {
  for (const flujo of ['base', 'sgr']) {
    const { window, doc } = await boot(flujo);
    assert.ok(!btn(doc, 'estilo').hidden);
    window.navigateTab('estilo');
    for (let i = 0; i < 10; i++) await tick();
    const pane = doc.getElementById('pane-estilo');
    assert.match(pane.textContent, /72/);
    assert.match(pane.textContent, /Mide legibilidad/);
    assert.match(pane.textContent, /Usar un verbo directo/);
    assert.match(pane.textContent, /juega un/);
    assert.equal(pane.querySelector('#estiloHallazgos i'), null);
  }
});

test('Estilo: sin reporte invita a generarlo', async () => {
  const { window, doc } = await boot('sgr', { estilo: { ok: true, disponible: false } });
  window.navigateTab('estilo');
  for (let i = 0; i < 10; i++) await tick();
  assert.match(doc.getElementById('pane-estilo').textContent, /Aún no hay reporte/);
});

// odd/tasks/tablero-juez-novedad.md, T5 (S4): «Novedad e hipótesis» follows the
// trees tab and the SGR tabs, inserted by the flow, come after it.
const tabLabels = doc => Array.from(doc.querySelectorAll('.tab-nav__btn')).filter(b => !b.hidden).map(b => b.textContent.trim());

test('SGR: el orden es árbol, novedad y luego las pestañas SGR', async () => {
  const { doc } = await boot('sgr');
  const labels = tabLabels(doc);
  const i = labels.indexOf('Árbol de problemas y objetivos');
  assert.deepEqual(labels.slice(i, i + 9), [
    'Árbol de problemas y objetivos', 'Novedad e hipótesis', 'Cadena de valor', 'Alianza y territorio',
    'Presupuesto y cronograma', 'TRL y componentes', 'Productos e indicadores', 'Requisitos y anexos', 'Anexo 2',
  ]);
  assert.equal(labels[i + 9], 'Secciones');
});

test('Base: novedad sigue al árbol y no aparecen pestañas SGR', async () => {
  const { doc } = await boot('base');
  const labels = tabLabels(doc);
  const i = labels.indexOf('Árbol de problemas y objetivos');
  assert.deepEqual(labels.slice(i, i + 3), ['Árbol de problemas y objetivos', 'Novedad e hipótesis', 'Secciones']);
  assert.ok(!labels.includes('Cadena de valor'));
});
