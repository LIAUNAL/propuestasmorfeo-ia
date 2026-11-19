/**
 * Pestaña «Alianza y territorio» (odd/tasks/sgr-alianza-territorio.md, S1 y S6).
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/status`,
 * `/api/alliance` y los POST se sustituyen por dobles deterministas. En el
 * flujo base la pestaña no existe y la ruta directa avisa.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const ALIANZA = {
  schema: 'morfeo.alianza-sgr/v1', monto_sgr_solicitado: 3000000000, duracion_meses: 24,
  entidades: [
    { id: 'E1', nombre: 'Universidad <b>Nacional</b>', nit: '899999063', tipo: 'IES', proponente: true, departamento: 'Caldas',
      rol: 'Ejecutor', posicion: 'cooperante', responsabilidades: ['Dirigir'], actividades: ['1.1.1', '1.2.1'],
      aporte_especie: 200000000, aporte_efectivo: 0,
      grupos: [{ nombre: 'Grupo LIA', codigo_gruplac: 'COL0001', clasificacion: 'A1', lineas: ['IA'] }],
      trayectoria: [
        { nombre: 'Proyecto A', codigo: 'BPIN1', financiador: 'SGR', anio: 2022, sgr_o_elegible: true },
        { nombre: 'Proyecto B', codigo: null, financiador: 'Minciencias', anio: 2020, sgr_o_elegible: false },
      ] },
    { id: 'E2', nombre: 'Gobernación de Caldas', tipo: 'entidad_territorial', proponente: false, departamento: 'Caldas',
      rol: 'Aliado <script>x</script>', posicion: 'beneficiario', responsabilidades: [], actividades: [],
      aporte_especie: null, aporte_efectivo: 50000000, grupos: [], trayectoria: [] },
    { id: 'E3', nombre: 'Universidad de Caldas', tipo: 'IES', proponente: false, departamento: 'Caldas',
      rol: 'Coejecutor', posicion: 'cooperante', responsabilidades: [], actividades: [], aporte_especie: 0,
      aporte_efectivo: null, grupos: [], trayectoria: [] },
  ],
  gobernanza: { toma_decisiones: 'Comité técnico por consenso', instancias: ['Comité directivo'], propiedad_intelectual: 'Pactada por acuerdo', seguimiento: 'Informe trimestral' },
};

const TERRITORIO = {
  schema: 'morfeo.territorio-sgr/v1', region_sgr: 'Eje Cafetero',
  departamentos: [{ nombre: 'Caldas', municipios: ['Manizales', 'Chinchiná'] }, { nombre: 'Risaralda', municipios: [] }],
  demandas: [
    { codigo: 'D1', texto: 'Fortalecer la gestión <i>del agua</i>', departamento: 'Caldas', fuente: 'TdR §5', causas: ['C1', 'C2'],
      objetivos: ['OE1'], actividades: ['1.1.1'], productos: ['1.1'], articulacion: 'El proyecto mide la calidad del agua.' },
  ],
  configuracion_regional: [{ actor: 'Corpocaldas', departamento: 'Caldas', pertinencia: 'Autoridad ambiental regional' }],
};

const PUNTAJE = [
  { subcriterio: '2.2', nombre: 'Alcance regional', puntaje: 3, max: 6, incompleto: false, calculo: '2 departamento(s) de ejecución.' },
  { subcriterio: '3.2', nombre: 'Composición de la alianza', puntaje: 0, max: 5, incompleto: true, calculo: 'aliados es null.' },
];

function alliance(overrides = {}) {
  return {
    ok: true, run: '2026-11-demo', flujo: 'sgr', disponible: true, alianza: ALIANZA, territorio: TERRITORIO,
    puntaje: PUNTAJE, hash: 'h456', aprobado: false, revision: null, errores: [],
    hallazgos: [
      { severity: 'error', code: 'alianza-composicion', message: 'Falta un usuario adoptante', node: '' },
      { severity: 'warning', code: 'territorio-departamento-sin-entidad', message: 'Risaralda no tiene entidad territorial', node: 'Risaralda' },
    ],
    ...overrides,
  };
}

const BASE = { ok: true, run: 'r', flujo: 'base', disponible: false, alianza: null, territorio: null, puntaje: [], hallazgos: [], aprobado: false, hash: null, revision: null, errores: [] };

function status(flujo) {
  return {
    flujo, active_run: '2026-11-demo', all_runs: ['2026-11-demo'], totals: { total_words: 10 },
    sections: [], gates: [], telemetria: [], pipeline_units: [], artifacts: [],
  };
}

function json(body, code = 200) {
  return { ok: code < 400, status: code, json: async () => body, text: async () => JSON.stringify(body) };
}

async function harness(t, { flujo = 'sgr', body = alliance(), posts = [] } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    if (u.includes('/api/alliance/approve')) {
      posts.push({ url: u, body: JSON.parse(init.body) });
      return json({ ok: true, hash: 'h456', fecha: '2026-11-19T10:00:00' });
    }
    if (u.includes('/api/alliance/adjust')) {
      const sent = JSON.parse(init.body);
      posts.push({ url: u, body: sent });
      return json({ ok: true, prompt: `Ajusta la alianza: ${sent.nota}` });
    }
    if (u.includes('/api/alliance')) return json(flujo === 'sgr' ? body : BASE);
    if (u.includes('/api/value-chain')) return json({ ok: true, flujo, disponible: false, cadena: null, hallazgos: [], errores: [] });
    if (u.includes('/api/style-sgr')) return json({ ok: true, flujo, disponible: false, por_seccion: {}, errores: [] });
    if (u.includes('/api/status')) return json(status(flujo));
    return json({}, 503);
  };
  viewer.window.eval(`window.__prompts = []; sendTerminalPrompt = (cmd) => { window.__prompts.push(cmd); return Promise.resolve(true); };`);
  await viewer.viewer('loadStatusNow');
  await flush();
  return viewer;
}

async function loaded(t, opts) {
  const viewer = await harness(t, opts);
  await viewer.viewer('loadAlliance');
  await flush();
  return viewer;
}

function tabLabels(doc) {
  return Array.from(doc.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
}

test('SGR: la pestaña «Alianza y territorio» aparece justo después de «Cadena de valor»', async (t) => {
  const viewer = await harness(t);
  const labels = tabLabels(viewer.document);
  const i = labels.indexOf('Alianza y territorio');
  assert.ok(i > 0, 'la pestaña existe en SGR');
  assert.equal(labels[i - 1], 'Cadena de valor');
  assert.equal(labels[i + 1], 'Presupuesto y cronograma');
  viewer.viewer('navigateTab', 'alianza');
  await flush();
  const active = viewer.document.querySelector('.tab-nav__btn.active');
  assert.equal(active.textContent.trim(), 'Alianza y territorio');
  assert.ok(viewer.document.getElementById('pane-alianza').classList.contains('active'));
});

test('base: la pestaña no existe y la ruta directa muestra un aviso', async (t) => {
  const viewer = await harness(t, { flujo: 'base' });
  assert.ok(!tabLabels(viewer.document).includes('Alianza y territorio'));
  viewer.viewer('navigateTab', 'alianza');
  await viewer.viewer('loadAlliance');
  await flush();
  const content = viewer.document.getElementById('alContent');
  assert.match(content.textContent, /solo en el flujo SGR/);
  assert.equal(content.querySelector('.al-entity'), null);
});

test('la vista previa de la rúbrica muestra puntaje, máximo, cálculo e insignia de incompleto', async (t) => {
  const viewer = await loaded(t);
  const cards = viewer.document.querySelectorAll('#alScores .al-score');
  assert.equal(cards.length, 2);
  const regional = viewer.document.querySelector('.al-score[data-subcriterio="2.2"]');
  assert.match(regional.textContent, /Alcance regional/);
  assert.match(regional.textContent, /3\s*\/\s*6/);
  assert.match(regional.textContent, /2 departamento\(s\) de ejecución/);
  assert.equal(regional.querySelector('.al-incompleto'), null);
  const alianza = viewer.document.querySelector('.al-score[data-subcriterio="3.2"]');
  assert.match(alianza.textContent, /0\s*\/\s*5/);
  assert.match(alianza.querySelector('.al-incompleto').textContent, /incompleto/);
});

test('las entidades se agrupan por tipo con proponente, rol, aportes, actividades, grupos y trayectoria', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const ies = doc.querySelector('.al-group[data-tipo="IES"]');
  assert.equal(ies.querySelectorAll('.al-entity').length, 2);
  assert.ok(doc.querySelector('.al-group[data-tipo="entidad_territorial"] .al-entity[data-entidad="E2"]'));
  const e1 = doc.querySelector('.al-entity[data-entidad="E1"]');
  assert.ok(e1.querySelector('.al-proponente'), 'insignia de proponente');
  assert.equal(doc.querySelector('.al-entity[data-entidad="E3"] .al-proponente'), null);
  for (const text of ['Ejecutor', 'Cooperante', 'Caldas', '200.000.000', '1.1.1', '1.2.1', 'Grupo LIA', 'A1']) {
    assert.ok(e1.textContent.includes(text), `falta ${text} en E1`);
  }
  assert.match(e1.querySelector('.al-trayectoria').textContent, /2 proyectos/);
  assert.match(e1.querySelector('.al-trayectoria').textContent, /1 SGR o elegible/);
  assert.match(doc.querySelector('.al-entity[data-entidad="E2"]').textContent, /50\.000\.000/);
});

test('departamentos con municipios y matriz demanda → causas/OE → actividades → productos', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const depts = doc.getElementById('alDepartamentos').textContent;
  assert.match(depts, /Eje Cafetero/);
  assert.match(depts, /Manizales/);
  assert.match(depts, /Chinchiná/);
  assert.match(depts, /Risaralda/);
  const row = doc.querySelector('#alDemandas [data-demanda="D1"]');
  for (const text of ['D1', 'Fortalecer la gestión <i>del agua</i>', 'TdR §5', 'C1', 'C2', 'OE1', '1.1.1', '1.1', 'El proyecto mide la calidad del agua.']) {
    assert.ok(row.textContent.includes(text), `falta ${text} en la demanda`);
  }
  assert.match(doc.getElementById('alConfig').textContent, /Corpocaldas/);
  assert.match(doc.getElementById('alGobernanza').textContent, /Comité técnico por consenso/);
});

test('el texto del agente se escapa: no se inserta HTML', async (t) => {
  const viewer = await loaded(t);
  const content = viewer.document.getElementById('alContent');
  assert.equal(content.querySelector('script'), null);
  assert.equal(content.querySelector('b'), null);
  assert.equal(content.querySelector('i'), null);
  assert.match(viewer.document.querySelector('.al-entity[data-entidad="E2"]').textContent, /<script>x<\/script>/);
});

test('los hallazgos se agrupan por severidad y los errores bloquean la aprobación', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  assert.match(doc.querySelector('#alFindings [data-severidad="error"]').textContent, /usuario adoptante/);
  const warn = doc.querySelector('#alFindings [data-severidad="warning"]');
  assert.match(warn.textContent, /Risaralda no tiene entidad territorial/);
  assert.match(warn.textContent, /territorio-departamento-sin-entidad/);
  assert.ok(doc.getElementById('alApproveBtn').disabled);
});

test('«Aprobar» envía el hash que se está viendo', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { body: alliance({ hallazgos: [] }), posts });
  const btn = viewer.document.getElementById('alApproveBtn');
  assert.equal(btn.disabled, false);
  btn.click();
  await flush();
  assert.match(posts[0].url, /\/api\/alliance\/approve$/);
  assert.deepEqual(posts[0].body, { hash: 'h456' });
});

test('una aprobación vieja se marca desactualizada', async (t) => {
  const viewer = await loaded(t, { body: alliance({ hallazgos: [], revision: { aprobado: true, hash: 'viejo', fecha: '2026-11-18T10:00:00' } }) });
  assert.match(viewer.document.getElementById('alStatusBadge').textContent, /Desactualizada/);
});

test('«Enviar ajuste al agente» manda la nota y entrega el prompt a la terminal', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { posts });
  viewer.document.getElementById('alNoteInput').value = 'Agrega la Alcaldía de Manizales';
  viewer.document.getElementById('alSendBtn').click();
  await flush();
  assert.match(posts[0].url, /\/api\/alliance\/adjust$/);
  assert.deepEqual(posts[0].body, { nota: 'Agrega la Alcaldía de Manizales' });
  assert.deepEqual(Array.from(viewer.window.__prompts), ['Ajusta la alianza: Agrega la Alcaldía de Manizales']);
});

test('sin archivos se explica la unidad fase1b_sgr y el check', async (t) => {
  const viewer = await loaded(t, { body: alliance({ disponible: false, alianza: null, territorio: null, hash: null, hallazgos: [], puntaje: [] }) });
  const content = viewer.document.getElementById('alContent');
  assert.match(content.textContent, /fase1b_sgr/);
  assert.match(content.textContent, /alianza_territorio_sgr\.py check/);
});
