/**
 * novedad-panel.js: the «Novedad e hipótesis» tab (odd/tasks/tablero-juez-novedad.md, T5: S4).
 *
 * The real static/novedad-panel.js runs in a small jsdom page with fetch, the
 * terminal delivery and the stage judge doubled; the last tests run it inside
 * the real dashboard (the harness does not inline it, so it is evaluated in the
 * page's window, as judge-avance.test.mjs does).
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { JSDOM } from 'jsdom';

import { createViewerHarness, DASHBOARD_INDEX, DASHBOARD_STATIC, flush } from './harness.mjs';

const SCRIPT = readFileSync(path.join(DASHBOARD_STATIC, 'novedad-panel.js'), 'utf8');
const FOLDS = readFileSync(path.join(DASHBOARD_STATIC, 'section-folds.js'), 'utf8');
const JUDGE = readFileSync(path.join(DASHBOARD_STATIC, 'judge-avance.js'), 'utf8');

const exp = (id, tipo, titulo, producto) => ({
  id, tipo, titulo, descripcion: `Descripción de ${titulo}.`, metrica: `Indicador de ${titulo}`,
  producto, resultado_esperado: `Resultado de ${titulo}.`,
});

const NOVEDAD = {
  schema: 'morfeo.novedad/v1',
  fecha: '2026-11-22',
  problema_central: 'Identificación tardía de patrones de depresión en estudiantes <b>afectados</b>.',
  objetivo_general: 'Desarrollar un sistema portable que identifique patrones de depresión.',
  causas: [
    { id: 'CD1', texto: 'Procesado multimodal de biomarcadores' },
    { id: 'CD2', texto: 'Despliegue portable en terreno' },
    { id: 'CD3', texto: 'Transferencia y evidencia local' },
  ],
  objetivos: [
    { id: 'OE1', causa: 'CD1', texto: 'Desarrollar una estrategia de procesado multimodal.' },
    { id: 'OE2', causa: 'CD2', texto: 'Diseñar un esquema de despliegue portable.' },
    { id: 'OE3', causa: 'CD3', texto: 'Implementar la transferencia del sistema.' },
  ],
  pilares: [
    { id: 'P1', nombre: 'Alineación instancia y síntoma', resumen: 'Cada instancia se asocia a un ítem.', detalle: 'Detalle 1.', objetivos: ['OE1'], causas: ['CD1'] },
    { id: 'P2', nombre: 'Inferencia local', resumen: 'El modelo corre en el dispositivo.', detalle: 'Detalle 2.', objetivos: ['OE2'], causas: ['CD2'] },
    { id: 'P3', nombre: 'Apropiación universitaria', resumen: 'Bienestar adopta el tamizaje.', detalle: 'Detalle 3.', objetivos: ['OE3', 'OE2'], causas: ['CD3'] },
  ],
  hipotesis: [
    { id: 'H1', titulo: 'La alineación mejora la detección', enunciado: 'Enunciado H1 <script>x</script>.', pilares: ['P1'], objetivos: ['OE1'],
      experimentos: [exp('E1', 'experimento', 'Comparación de agregaciones', 'Artículo de comparación')] },
    { id: 'H2', titulo: 'El despliegue local conserva el desempeño', enunciado: 'Enunciado H2.', pilares: ['P2'], objetivos: ['OE2'],
      experimentos: [exp('E2', 'implementacion', 'Aplicación móvil de tamizaje', 'Aplicación móvil')] },
    { id: 'H3', titulo: 'La transferencia sostiene el uso', enunciado: 'Enunciado H3.', pilares: ['P3', 'P2'], objetivos: ['OE3'],
      experimentos: [exp('E3', 'transferencia', 'Protocolo con bienestar', 'Protocolo'), exp('E4', 'intervencion', 'Jornadas de tamizaje', 'Informe de jornadas')] },
  ],
};

function row(oe, causa, pilares, hipotesis, experimentos) {
  return {
    objetivo: { id: oe.id, texto: oe.texto },
    causa,
    pilares: pilares.map(p => ({ id: p.id, nombre: p.nombre, resumen: p.resumen })),
    hipotesis: hipotesis.map(h => ({ id: h.id, titulo: h.titulo, enunciado: h.enunciado, pilares: h.pilares })),
    experimentos: experimentos.map(([h, e]) => ({ ...e, hipotesis: h })),
    productos: experimentos.map(([, e]) => e.producto),
    indicadores: experimentos.map(([, e]) => e.metrica),
    resultados: experimentos.map(([, e]) => e.resultado_esperado),
    efectos: ['b1'],
  };
}

const [H1, H2, H3] = NOVEDAD.hipotesis;
const [P1, P2, P3] = NOVEDAD.pilares;
const MATRIZ = {
  problema_central: NOVEDAD.problema_central,
  objetivo_general: NOVEDAD.objetivo_general,
  efecto_final: 'Deterioro del bienestar universitario.',
  efectos: [{ id: 'b1', texto: 'Subdiagnóstico y detección tardía.' }],
  fuente_efectos: 'arbol',
  tipos: [],
  filas: [
    row(NOVEDAD.objetivos[0], NOVEDAD.causas[0], [P1], [H1], [['H1', H1.experimentos[0]]]),
    row(NOVEDAD.objetivos[1], NOVEDAD.causas[1], [P2, P3], [H2], [['H2', H2.experimentos[0]]]),
    row(NOVEDAD.objetivos[2], NOVEDAD.causas[2], [P3], [H3], [['H3', H3.experimentos[0]], ['H3', H3.experimentos[1]]]),
  ],
  totales: { objetivos: 3, pilares: 3, hipotesis: 3, experimentos: 4,
    por_tipo: { experimento: 1, intervencion: 1, transferencia: 1, implementacion: 1, accion: 0 } },
};

function json(payload, status = 200) {
  return { ok: status < 400, status, json: async () => payload, text: async () => JSON.stringify(payload) };
}

function payload({ novedad = NOVEDAD, matriz = MATRIZ, validacion = { ok: true, errores: [] }, actualizado = '2026-11-22T10:00:00' } = {}) {
  if (!novedad) {
    return { ok: true, run: 'demo', disponible: false, archivo: 'artefactos/novedad/novedad.json', novedad: null, matriz: null, validacion: null, actualizado: null, errores: [] };
  }
  return { ok: true, run: 'demo', disponible: true, archivo: 'artefactos/novedad/novedad.json', novedad, matriz, validacion, actualizado, errores: [] };
}

const PAGE = `<!doctype html><html><body><div id="root">
  <span data-nov-slot="meta"></span><div data-nov-slot="head"></div>
  <div data-nov-slot="tree"></div><div data-nov-slot="matrix"></div><div data-nov-slot="judge"></div>
</div></body></html>`;

async function mountPage({ answer = () => json(payload()), send = async () => true, judge = false } = {}) {
  const dom = new JSDOM(PAGE, { runScripts: 'outside-only', url: 'http://localhost:8000/' });
  const { window } = dom;
  if (judge) window.eval(JUDGE);
  window.eval(SCRIPT);
  const calls = [];
  const prompts = [];
  const fetch = async (url, init) => {
    calls.push({ url: String(url), method: (init && init.method) || 'GET', body: init && init.body });
    if (String(url).startsWith('/api/judge-avance')) return json({ ok: true, etapa: 'novedad', disponible: false, evaluacion: null, errores: [] });
    return answer(String(url), init);
  };
  const root = window.document.getElementById('root');
  const controller = window.NovedadPanel.mount(root, {
    interval: 1000, fetch, send: async (prompt) => { prompts.push(prompt); return send(prompt); },
  });
  return { window, document: window.document, controller, calls, prompts, root };
}

const texts = (nodes) => Array.from(nodes, n => n.textContent.replace(/\s+/g, ' ').trim());

test('the tree shows the cause and objective strip, pillars above and hypotheses below with type-badged chips', async () => {
  const { controller, root, calls } = await mountPage();
  await controller.refresh();
  assert.ok(calls.some(c => c.url === '/api/novedad' && c.method === 'GET'));
  const tree = root.querySelector('[data-nov-slot="tree"] [data-novelty-tree]');
  assert.ok(tree, 'the novelty tree renders');
  assert.match(tree.querySelector('.nov-node--central').textContent, /Identificación tardía/);
  assert.equal(tree.querySelector('.nov-node--central b'), null, 'text is escaped');
  const chains = tree.querySelectorAll('.nov-chain');
  assert.equal(chains.length, 3);
  assert.deepEqual(JSON.parse(JSON.stringify(Array.from(chains, c => Array.from(c.querySelectorAll('[data-tree-node]'), n => n.dataset.treeNode)))),
    [['CD1', 'OE1'], ['CD2', 'OE2'], ['CD3', 'OE3']]);
  const pillars = tree.querySelectorAll('.nov-node--pillar');
  const hyps = tree.querySelectorAll('.nov-node--hypothesis');
  assert.equal(pillars.length, 3);
  assert.equal(hyps.length, 3);
  assert.ok(pillars[0].compareDocumentPosition(hyps[0]) & 4, 'pillars come before hypotheses');
  assert.match(pillars[2].textContent, /Objetivos: OE3, OE2/);
  assert.match(pillars[1].textContent, /Sostiene: H2, H3/);
  assert.match(hyps[2].textContent, /Apoyado por: P3, P2/);
  assert.equal(hyps[0].querySelector('script'), null);
  const chips = hyps[2].querySelectorAll('.nov-chip');
  assert.deepEqual(texts(chips), ['Transferencia E3 · Protocolo con bienestar', 'Intervención E4 · Jornadas de tamizaje']);
  assert.ok(chips[0].classList.contains('nov-chip--transferencia'));
  assert.ok(chips[1].classList.contains('nov-chip--intervencion'));
  const arrows = Array.from(tree.querySelectorAll('.nov-arrow'), a => `${a.dataset.from}>${a.dataset.to}`);
  assert.deepEqual(JSON.parse(JSON.stringify(arrows)).sort(),
    ['OE1>P1', 'OE2>P2', 'OE2>P3', 'OE3>P3', 'P1>H1', 'P2>H2', 'P2>H3', 'P3>H3'].sort());
});

test('without an artifact the panel invites to generate it', async () => {
  const { controller, root } = await mountPage({ answer: () => json(payload({ novedad: null })) });
  await controller.refresh();
  assert.match(root.querySelector('[data-nov-slot="tree"]').textContent, /Todavía no hay pilares ni hipótesis/);
  assert.match(root.querySelector('[data-nov-slot="matrix"]').textContent, /matriz aparece/);
  assert.equal(root.querySelector('.nov-run').disabled, false);
});

test('validation errors of the artifact are listed above the tree', async () => {
  const { controller, root } = await mountPage({ answer: () => json(payload({ validacion: { ok: false, errores: ['objetivos[OE2]: ninguna hipótesis <i>lo</i> atiende.'] } })) });
  await controller.refresh();
  const errors = root.querySelector('.nov-errors');
  assert.ok(errors);
  assert.match(errors.textContent, /OE2/);
  assert.equal(errors.querySelector('i'), null);
});

test('the matrix shows the header, stat cards and one row per objective with expandable details', async () => {
  const { controller, root } = await mountPage();
  await controller.refresh();
  const matrix = root.querySelector('[data-nov-slot="matrix"]');
  assert.match(matrix.querySelector('.nov-matrix__head').textContent, /Identificación tardía/);
  assert.match(matrix.querySelector('.nov-matrix__head').textContent, /Desarrollar un sistema portable/);
  const stats = Object.fromEntries(Array.from(matrix.querySelectorAll('.nov-stat'), s => [s.dataset.stat, s.querySelector('.nov-stat__val').textContent.trim()]));
  assert.deepEqual(JSON.parse(JSON.stringify(stats)), { objetivos: '3', pilares: '3', hipotesis: '3', experimentos: '4' });
  assert.match(matrix.querySelector('[data-stat="experimentos"]').textContent, /1 transferencia/);
  const rows = matrix.querySelectorAll('tbody tr.nov-row');
  assert.deepEqual(JSON.parse(JSON.stringify(Array.from(rows, r => r.dataset.oe))), ['OE1', 'OE2', 'OE3']);
  const oe2 = rows[1];
  assert.match(oe2.querySelector('[data-col="causa"]').textContent, /CD2/);
  assert.match(oe2.querySelector('[data-col="pilares"]').textContent, /P2.*P3/s);
  assert.match(oe2.querySelector('[data-col="experimentos"]').textContent, /Implementación/);
  assert.match(oe2.querySelector('[data-col="productos"]').textContent, /Aplicación móvil/);
  assert.match(oe2.querySelector('[data-col="resultado"]').textContent, /Indicador de Aplicación móvil de tamizaje/);
  assert.match(oe2.querySelector('[data-col="efecto"]').textContent, /b1/);
  const detail = matrix.querySelector('tr.nov-row-detail[data-oe="OE2"]');
  assert.equal(detail.hidden, true);
  oe2.querySelector('.nov-expand').click();
  assert.equal(matrix.querySelector('tr.nov-row-detail[data-oe="OE2"]').hidden, false);
  assert.match(matrix.querySelector('tr.nov-row-detail[data-oe="OE2"]').textContent, /Subdiagnóstico y detección tardía/);
});

test('the matrix search and type filter narrow the rows', async () => {
  const { controller, root, window } = await mountPage();
  await controller.refresh();
  const matrix = root.querySelector('[data-nov-slot="matrix"]');
  const visible = () => JSON.parse(JSON.stringify(Array.from(matrix.querySelectorAll('tbody tr.nov-row'), r => r.dataset.oe)));
  const input = matrix.querySelector('.nov-search__input');
  input.value = 'movil';
  input.dispatchEvent(new window.Event('input'));
  assert.deepEqual(visible(), ['OE2'], 'search ignores accents and case');
  assert.match(matrix.querySelector('.nov-count').textContent, /1 de 3/);
  input.value = '';
  input.dispatchEvent(new window.Event('input'));
  const select = matrix.querySelector('.nov-type');
  select.value = 'transferencia';
  select.dispatchEvent(new window.Event('change'));
  assert.deepEqual(visible(), ['OE3']);
  assert.doesNotMatch(matrix.querySelector('tr.nov-row[data-oe="OE3"] [data-col="experimentos"]').textContent, /Intervención/);
  matrix.querySelector('.nov-clear').click();
  assert.deepEqual(visible(), ['OE1', 'OE2', 'OE3']);
  const filtered = window.NovedadPanel.filterRows(MATRIZ, { query: '', tipo: 'accion' });
  assert.equal(filtered.length, 0);
});

test('«Generar / actualizar» sends the command and stays pending until a newer artifact arrives', async () => {
  let actualizado = '2026-11-22T10:00:00';
  const answer = (url) => (url === '/api/novedad/run'
    ? json({ ok: true, prompt: '/propuesta-novedad' })
    : json(payload({ actualizado })));
  const { controller, root, prompts, calls } = await mountPage({ answer });
  await controller.refresh();
  root.querySelector('.nov-run').click();
  await flush();
  assert.ok(calls.some(c => c.url === '/api/novedad/run' && c.method === 'POST'));
  assert.deepEqual(prompts, ['/propuesta-novedad']);
  assert.ok(root.querySelector('.nov-pending'), 'pending banner');
  assert.equal(root.querySelector('.nov-run').disabled, true);
  await controller.refresh();
  assert.ok(root.querySelector('.nov-pending'), 'same artifact keeps it pending');
  actualizado = '2026-11-22T11:00:00';
  await controller.refresh();
  assert.equal(root.querySelector('.nov-pending'), null);
  assert.equal(root.querySelector('.nov-run').disabled, false);
});

test('a failed delivery offers a retry and sends nothing pending', async () => {
  const answer = (url) => (url === '/api/novedad/run' ? json({ ok: true, prompt: '/propuesta-novedad' }) : json(payload()));
  let ok = false;
  const { controller, root, prompts } = await mountPage({ answer, send: async () => ok });
  await controller.refresh();
  await controller.run();
  assert.equal(root.querySelector('.nov-retry').hidden, false);
  assert.equal(root.querySelector('.nov-pending'), null);
  ok = true;
  root.querySelector('.nov-retry').click();
  await flush();
  assert.deepEqual(prompts, ['/propuesta-novedad', '/propuesta-novedad']);
  assert.ok(root.querySelector('.nov-pending'));
});

function stubBoxes(window, tree, layout) {
  tree.getBoundingClientRect = () => ({ left: 0, top: 0, width: 900, height: 700, right: 900, bottom: 700 });
  tree.querySelectorAll('[data-tree-node]').forEach((node) => {
    const box = layout(node);
    node.getBoundingClientRect = () => ({ ...box, right: box.left + box.width, bottom: box.top + box.height });
  });
}

test('arrows are drawn from the real boxes; one column drops them for the text lines', async () => {
  const { controller, root, window } = await mountPage();
  await controller.refresh();
  const tree = root.querySelector('[data-novelty-tree]');
  const columns = { 1: 0, 2: 300, 3: 600 };
  stubBoxes(window, tree, (node) => {
    const id = node.dataset.treeNode;
    const n = Number(id.replace(/\D/g, ''));
    const top = id.startsWith('H') ? 500 : id.startsWith('P') ? 300 : id.startsWith('OE') ? 150 : 50;
    return { left: columns[n], top, width: 250, height: 80 };
  });
  window.NovedadPanel.drawArrows(tree);
  assert.equal(tree.classList.contains('is-stacked'), false);
  const arrow = tree.querySelector('.nov-arrow[data-from="P1"][data-to="H1"]');
  assert.match(arrow.getAttribute('d'), /^M125,380 C/);
  stubBoxes(window, tree, (node) => ({ left: 0, top: 100 * Number(node.dataset.treeNode.replace(/\D/g, '')), width: 300, height: 80 }));
  window.NovedadPanel.drawArrows(tree);
  assert.equal(tree.classList.contains('is-stacked'), true);
});

test('pointing at a pillar focuses its arrows, objectives and hypotheses', async () => {
  const { controller, root, window } = await mountPage();
  await controller.refresh();
  const tree = root.querySelector('[data-novelty-tree]');
  const pillar = tree.querySelector('[data-tree-node="P2"]');
  pillar.dispatchEvent(new window.MouseEvent('mouseover', { bubbles: true }));
  assert.ok(tree.classList.contains('has-focus'));
  const focused = Array.from(tree.querySelectorAll('.nov-arrow.is-focus'), a => `${a.dataset.from}>${a.dataset.to}`).sort();
  assert.deepEqual(JSON.parse(JSON.stringify(focused)), ['OE2>P2', 'P2>H2', 'P2>H3']);
  const nodes = Array.from(tree.querySelectorAll('[data-tree-node].is-focus'), n => n.dataset.treeNode).sort();
  assert.deepEqual(JSON.parse(JSON.stringify(nodes)), ['H2', 'H3', 'OE2', 'P2']);
  tree.dispatchEvent(new window.MouseEvent('mouseleave'));
  assert.equal(tree.classList.contains('has-focus'), false);
});

test('the stage judge is mounted with etapa novedad and polls with the panel', async () => {
  const { controller, root, calls } = await mountPage({ judge: true });
  const slot = root.querySelector('[data-nov-slot="judge"]');
  assert.equal(slot.getAttribute('data-judge-avance-etapa'), 'novedad');
  controller.start();
  await flush();
  assert.ok(calls.some(c => c.url === '/api/judge-avance?etapa=novedad'));
  assert.ok(calls.some(c => c.url === '/api/novedad'));
  assert.equal(controller.polling, true);
  controller.stop();
  assert.equal(controller.polling, false);
});

async function dashboard(t) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const calls = [];
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    calls.push({ url: u, method: (init && init.method) || 'GET' });
    if (u.startsWith('/api/novedad/run')) return json({ ok: true, prompt: '/propuesta-novedad' });
    if (u.startsWith('/api/novedad')) return json(payload());
    if (u.startsWith('/api/judge-avance')) return json({ ok: true, etapa: 'novedad', disponible: false, evaluacion: null, errores: [] });
    return json({}, 503);
  };
  try { viewer.window.localStorage.clear(); } catch (_) { /* storage blocked */ }
  viewer.window.eval(FOLDS);
  viewer.window.eval(JUDGE);
  viewer.window.eval(SCRIPT);
  viewer.window.eval(`window.__prompts = []; sendTerminalPrompt = async (cmd) => { window.__prompts.push(cmd); return true; };`);
  return { viewer, calls };
}

test('in the dashboard the «Novedad e hipótesis» tab sits right after the trees tab', async (t) => {
  const { viewer } = await dashboard(t);
  const labels = Array.from(viewer.document.querySelectorAll('.tab-nav__btn'), b => b.textContent.trim());
  const i = labels.indexOf('Árbol de problemas y objetivos');
  assert.ok(i >= 0);
  assert.equal(labels[i + 1], 'Novedad e hipótesis');
  assert.equal(labels[i + 2], 'Secciones', 'base flow: no SGR tab in between');
});

test('in the dashboard the tab opens the pane with its folds, the judge and the command', async (t) => {
  const { viewer, calls } = await dashboard(t);
  await viewer.viewer('navigateTab', 'novedad');
  await flush();
  const doc = viewer.document;
  const pane = doc.getElementById('pane-novedad');
  assert.ok(pane.classList.contains('active'));
  const fold = (name) => pane.querySelector(`details.exp-fold[data-fold-name="${name}"]`);
  assert.equal(fold('novedad-pilares').open, true);
  assert.equal(fold('novedad-pilares').querySelector('.exp-fold__title').textContent.trim(), 'Pilares e hipótesis');
  assert.equal(fold('novedad-matriz').open, false);
  assert.equal(fold('novedad-matriz').querySelector('.exp-fold__title').textContent.trim(), 'Matriz del proyecto');
  assert.equal(fold('juez-avance-novedad').querySelector('.exp-fold__title').textContent.trim(), 'Juez de avance');
  assert.ok(fold('novedad-pilares').compareDocumentPosition(fold('novedad-matriz')) & 4);
  assert.ok(fold('novedad-matriz').compareDocumentPosition(fold('juez-avance-novedad')) & 4);
  assert.ok(calls.some(c => c.url === '/api/novedad'));
  assert.ok(calls.some(c => c.url === '/api/judge-avance?etapa=novedad'));
  assert.equal(fold('juez-avance-novedad').querySelector('[data-judge-avance-etapa]').getAttribute('data-judge-avance-etapa'), 'novedad');
  assert.equal(pane.querySelectorAll('.nov-node--pillar').length, 3);
  pane.querySelector('.nov-run').click();
  await flush();
  assert.deepEqual(JSON.parse(viewer.window.eval('JSON.stringify(window.__prompts)')), ['/propuesta-novedad']);
  await viewer.viewer('navigateTab', 'trees');
  assert.equal(viewer.window.eval('NOVEDAD_PANEL && NOVEDAD_PANEL.polling'), false, 'leaving the tab stops the polling');
});

test('the dashboard loads novedad-panel.js right after judge-avance.js', () => {
  const html = readFileSync(DASHBOARD_INDEX, 'utf8');
  const judge = html.indexOf('<script src="/static/judge-avance.js"></script>');
  const panel = html.indexOf('<script src="/static/novedad-panel.js"></script>');
  assert.ok(judge > 0 && panel > judge);
  assert.equal(html.slice(judge, panel).split('<script').length, 2, 'nothing loads in between');
});
