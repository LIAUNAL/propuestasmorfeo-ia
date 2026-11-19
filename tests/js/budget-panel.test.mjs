/**
 * Pestaña «Presupuesto y cronograma» (odd/tasks/sgr-presupuesto-gantt.md, S1 y S6).
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/status`,
 * `/api/budget` y los POST se sustituyen por dobles deterministas. En el flujo
 * base la pestaña no existe y la ruta directa avisa.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const PRESUPUESTO = {
  schema: 'morfeo.presupuesto-sgr/v1', duracion_meses: 12, tope_sgr: 1000000000, semanas_por_mes: 4, factor_prestacional: 1.5,
  items: [
    { id: 'P1', rubro: 'talento_humano', insumo_mga: 'mano_obra_calificada', descripcion: 'Investigador <b>principal</b>',
      justificacion: 'Dirige', entidad: 'E1', fuente: 'sgr', componente: null, cantidad: 1, valor_unitario: 0,
      talento: { perfil: 'PhD', horas_semana: 20, valor_hora: 100000, meses: 12 }, actividades: ['1.1.1'], cotizaciones: 0, soporte: null },
    { id: 'P2', rubro: 'equipos_software', insumo_mga: 'maquinaria_equipo', descripcion: 'Servidor GPU', justificacion: 'Entrena',
      entidad: 'E2', fuente: 'efectivo', componente: null, cantidad: 2, valor_unitario: 50000000, talento: null,
      actividades: ['1.1.1', '1.1.2'], cotizaciones: 1, soporte: null },
  ],
};

const RESUMEN = {
  total_sgr: 1200000000, total_especie: 200000000, total_efectivo: 100000000, total: 1500000000,
  por_rubro: {
    talento_humano: { sgr: 1200000000, especie: 200000000, efectivo: 0 },
    equipos_software: { sgr: 0, especie: 0, efectivo: 100000000 },
  },
  por_insumo: {
    mano_obra_calificada: { sgr: 1200000000, especie: 200000000, efectivo: 0 },
    maquinaria_equipo: { sgr: 0, especie: 0, efectivo: 100000000 },
  },
  por_entidad: { E1: { sgr: 1200000000, especie: 200000000, efectivo: 0 }, E2: { sgr: 0, especie: 0, efectivo: 100000000 } },
  cofinanciacion_pct: 20, transferencia_pct: 0.5, movilidad_pct: 1.5, seguimiento: false, cotizaciones_faltantes: 1, por_actividad: {},
};

const PROYECCION = { anios: [{ anio: 1, valor: 1125000000, pct: 75 }, { anio: 2, valor: 375000000, pct: 25 }], por_actividad: {} };

const CADENA_MESES = [
  { codigo: '1.1.1', nombre: 'Levantar datos', oe: 'OE1', oe_texto: 'Medir el agua', producto: '1.1', producto_nombre: 'Servicio de información',
    mes_inicio: 1, mes_fin: 3, ruta_critica: true, etapa: 'preinversion' },
  { codigo: '1.1.2', nombre: 'Entrenar <i>modelos</i>', oe: 'OE1', oe_texto: 'Medir el agua', producto: '1.1', producto_nombre: 'Servicio de información',
    mes_inicio: 4, mes_fin: 8, ruta_critica: false, etapa: 'inversion' },
  { codigo: '2.1.1', nombre: 'Transferir', oe: 'OE2', oe_texto: 'Apropiar', producto: '2.1', producto_nombre: 'Documentos',
    mes_inicio: 9, mes_fin: 12, ruta_critica: true, etapa: 'operacion' },
];

const HITOS = [{ codigo: 'H1', nombre: 'Línea base', mes: 3, actividades: ['1.1.1'], verificacion: 'Informe de línea base' }];

function budget(overrides = {}) {
  return {
    ok: true, run: '2026-11-demo', flujo: 'sgr', disponible: true, presupuesto: PRESUPUESTO, resumen: RESUMEN,
    proyeccion: PROYECCION, cadena_meses: CADENA_MESES, hitos: HITOS, duracion_meses: 12, hash: 'b789',
    aprobado: false, revision: null, errores: [],
    hallazgos: [
      { severity: 'error', code: 'presupuesto-tope', message: 'El total SGR supera el tope', node: '' },
      { severity: 'warning', code: 'cronograma-sin-hito', message: 'Cuatro meses sin hito', node: '8' },
    ],
    ...overrides,
  };
}

const BASE = { ok: true, run: 'r', flujo: 'base', disponible: false, presupuesto: null, resumen: null, proyeccion: null, cadena_meses: [], hitos: [], hallazgos: [], aprobado: false, hash: null, revision: null, errores: [] };

function status(flujo) {
  return {
    flujo, active_run: '2026-11-demo', all_runs: ['2026-11-demo'], totals: { total_words: 10 },
    sections: [], gates: [], telemetria: [], pipeline_units: [], artifacts: [],
  };
}

function json(body, code = 200) {
  return { ok: code < 400, status: code, json: async () => body, text: async () => JSON.stringify(body) };
}

async function harness(t, { flujo = 'sgr', body = budget(), posts = [] } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    if (u.includes('/api/budget/approve')) {
      posts.push({ url: u, body: JSON.parse(init.body) });
      return json({ ok: true, hash: 'b789', fecha: '2026-11-19T10:00:00' });
    }
    if (u.includes('/api/budget/adjust')) {
      const sent = JSON.parse(init.body);
      posts.push({ url: u, body: sent });
      return json({ ok: true, prompt: `Ajusta el presupuesto: ${sent.nota}` });
    }
    if (u.includes('/api/budget')) return json(flujo === 'sgr' ? body : BASE);
    if (u.includes('/api/alliance')) return json({ ok: true, flujo, disponible: false, alianza: null, territorio: null, hallazgos: [], puntaje: [], errores: [] });
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
  await viewer.viewer('loadBudget');
  await flush();
  return viewer;
}

function tabLabels(doc) {
  return Array.from(doc.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
}

function card(doc, name) {
  return doc.querySelector(`#pgCards .pg-card[data-card="${name}"]`);
}

function setInput(viewer, id, value) {
  const el = viewer.document.getElementById(id);
  el.value = String(value);
  el.dispatchEvent(new viewer.window.Event('input', { bubbles: true }));
}

test('SGR: la pestaña «Presupuesto y cronograma» aparece justo después de «Alianza y territorio»', async (t) => {
  const viewer = await harness(t);
  const labels = tabLabels(viewer.document);
  const i = labels.indexOf('Presupuesto y cronograma');
  assert.ok(i > 0, 'la pestaña existe en SGR');
  assert.equal(labels[i - 1], 'Alianza y territorio');
  assert.equal(labels[i + 1], 'MGA resumido');
  viewer.viewer('navigateTab', 'presupuesto');
  await flush();
  const active = viewer.document.querySelector('.tab-nav__btn.active');
  assert.equal(active.textContent.trim(), 'Presupuesto y cronograma');
  assert.ok(viewer.document.getElementById('pane-presupuesto').classList.contains('active'));
});

test('base: la pestaña no existe y la ruta directa muestra un aviso', async (t) => {
  const viewer = await harness(t, { flujo: 'base' });
  assert.ok(!tabLabels(viewer.document).includes('Presupuesto y cronograma'));
  viewer.viewer('navigateTab', 'presupuesto');
  await viewer.viewer('loadBudget');
  await flush();
  const content = viewer.document.getElementById('pgContent');
  assert.match(content.textContent, /solo en el flujo SGR/);
  assert.equal(content.querySelector('.pg-card'), null);
  assert.ok(viewer.document.getElementById('pgCalcPanel').hidden);
  assert.ok(viewer.document.getElementById('pgReviewPanel').hidden);
});

test('las tarjetas resumen muestran cifras y se colorean por estado', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const total = card(doc, 'total-sgr');
  assert.ok(total.classList.contains('is-bad'), 'el total supera el tope');
  assert.match(total.textContent, /1\.200\.000\.000/);
  assert.match(total.textContent, /1\.000\.000\.000/);
  assert.match(card(doc, 'especie').textContent, /200\.000\.000/);
  assert.match(card(doc, 'efectivo').textContent, /100\.000\.000/);
  assert.match(card(doc, 'cofinanciacion').textContent, /20 %/);
  const transfer = card(doc, 'transferencia');
  assert.ok(transfer.classList.contains('is-warn'));
  assert.match(transfer.textContent, /0,5 %/);
  assert.match(transfer.textContent, /1 %/);
  const movilidad = card(doc, 'movilidad');
  assert.ok(movilidad.classList.contains('is-ok'));
  assert.match(movilidad.textContent, /1,5 %/);
  assert.match(movilidad.textContent, /2 %/);
  assert.ok(card(doc, 'seguimiento').classList.contains('is-bad'));
  const quotes = card(doc, 'cotizaciones');
  assert.ok(quotes.classList.contains('is-warn'));
  assert.match(quotes.textContent, /1/);
});

test('el tope efectivo del resumen (el de la rúbrica) manda sobre el declarado', async (t) => {
  const viewer = await loaded(t, { body: budget({ resumen: { ...RESUMEN, tope_sgr: 2000000000 } }) });
  const total = card(viewer.document, 'total-sgr');
  assert.ok(total.classList.contains('is-ok'));
  assert.match(total.textContent, /2\.000\.000\.000/);
});

test('la tabla rubro × fuente suma totales y alterna a la vista de insumos MGA', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const wrap = doc.getElementById('pgRubros');
  assert.equal(wrap.dataset.vista, 'rubros');
  assert.match(wrap.textContent, /Talento humano/);
  assert.match(wrap.textContent, /Equipos y software/);
  assert.match(wrap.querySelector('tfoot').textContent, /1\.500\.000\.000/);
  assert.match(wrap.querySelector('tr[data-clave="talento_humano"]').textContent, /1\.400\.000\.000/);
  doc.getElementById('pgVistaBtn').click();
  await flush();
  assert.equal(doc.getElementById('pgRubros').dataset.vista, 'mga');
  assert.match(doc.getElementById('pgRubros').textContent, /Mano de obra calificada/);
  assert.match(doc.getElementById('pgRubros').textContent, /Maquinaria y equipo/);
  assert.doesNotMatch(doc.getElementById('pgRubros').textContent, /Talento humano/);
  doc.getElementById('pgVistaBtn').click();
  await flush();
  assert.equal(doc.getElementById('pgRubros').dataset.vista, 'rubros');
});

test('el desglose por entidad, los ítems y la proyección anual se muestran', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const e2 = doc.querySelector('#pgEntidades tr[data-entidad="E2"]');
  assert.match(e2.textContent, /100\.000\.000/);
  const p1 = doc.querySelector('#pgItems tr[data-item="P1"]');
  for (const text of ['Talento humano', 'Mano de obra calificada', 'E1', 'SGR', '1.1.1', '144.000.000']) {
    assert.ok(p1.textContent.includes(text), `falta ${text} en P1`);
  }
  const p2 = doc.querySelector('#pgItems tr[data-item="P2"]');
  for (const text of ['Servidor GPU', 'Efectivo', '1.1.2', '100.000.000']) {
    assert.ok(p2.textContent.includes(text), `falta ${text} en P2`);
  }
  assert.equal(p2.querySelector('[data-cotizaciones]').textContent.trim(), '1');
  const proy = doc.getElementById('pgProyeccion').textContent;
  assert.match(proy, /Año 1/);
  assert.match(proy, /1\.125\.000\.000/);
  assert.match(proy, /75 %/);
});

test('el Gantt agrupa OE → producto → actividad con barras por etapa, ruta crítica e hitos', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const gantt = doc.querySelector('#pgGantt table');
  assert.equal(gantt.querySelectorAll('thead th.pg-month').length, 12);
  assert.ok(gantt.querySelector('tr.pg-gantt__oe[data-oe="OE1"]'));
  assert.ok(gantt.querySelector('tr.pg-gantt__oe[data-oe="OE2"]'));
  assert.ok(gantt.querySelector('tr.pg-gantt__producto[data-producto="1.1"]'));
  const a1 = gantt.querySelector('tr[data-actividad="1.1.1"]');
  assert.ok(a1.classList.contains('is-critical'));
  assert.equal(a1.querySelectorAll('td.pg-bar').length, 3);
  assert.equal(a1.querySelectorAll('td.pg-bar--preinversion').length, 3);
  const a2 = gantt.querySelector('tr[data-actividad="1.1.2"]');
  assert.ok(!a2.classList.contains('is-critical'));
  assert.equal(a2.querySelectorAll('td.pg-bar--inversion').length, 5);
  assert.equal(gantt.querySelector('tr[data-actividad="2.1.1"]').querySelectorAll('td.pg-bar--operacion').length, 4);
  const marker = gantt.querySelector('.pg-hito[data-hito="H1"]');
  assert.equal(marker.closest('td').dataset.mes, '3');
  assert.match(marker.getAttribute('title'), /Línea base/);
  assert.match(marker.getAttribute('title'), /Informe de línea base/);
  assert.match(doc.getElementById('pgGantt').textContent, /Informe de línea base/);
});

test('la calculadora de horas de contrapartida multiplica en vivo, con el factor', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  assert.equal(doc.getElementById('pgCalcPanel').hidden, false);
  assert.equal(doc.getElementById('pgCalcSemanas').value, '4');
  assert.equal(doc.getElementById('pgCalcFactor').value, '1');
  setInput(viewer, 'pgCalcHoras', 10);
  setInput(viewer, 'pgCalcValorHora', 50000);
  setInput(viewer, 'pgCalcMeses', 6);
  assert.match(doc.getElementById('pgCalcResult').textContent, /12\.000\.000/);
  setInput(viewer, 'pgCalcFactor', 1.5);
  assert.match(doc.getElementById('pgCalcResult').textContent, /18\.000\.000/);
  setInput(viewer, 'pgCalcSemanas', 4.3);
  assert.match(doc.getElementById('pgCalcResult').textContent, /19\.350\.000/);
  assert.equal(viewer.viewer('budgetCalc', 20, 100000, 12, 4, 1.5), 144000000);
  assert.equal(viewer.viewer('budgetCalc', '', 100000, 12, 4, 1), null);
  setInput(viewer, 'pgCalcHoras', '');
  assert.match(doc.getElementById('pgCalcResult').textContent, /—/);
});

test('el texto del agente se escapa: no se inserta HTML', async (t) => {
  const viewer = await loaded(t);
  const content = viewer.document.getElementById('pgContent');
  assert.equal(content.querySelector('b'), null);
  assert.equal(content.querySelector('i'), null);
  assert.match(content.textContent, /Investigador <b>principal<\/b>/);
  assert.match(content.textContent, /Entrenar <i>modelos<\/i>/);
});

test('los hallazgos se agrupan por severidad y los errores bloquean la aprobación', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  assert.match(doc.querySelector('#pgFindings [data-severidad="error"]').textContent, /supera el tope/);
  const warn = doc.querySelector('#pgFindings [data-severidad="warning"]');
  assert.match(warn.textContent, /Cuatro meses sin hito/);
  assert.match(warn.textContent, /cronograma-sin-hito/);
  assert.ok(doc.getElementById('pgApproveBtn').disabled);
});

test('«Aprobar» envía el hash que se está viendo', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { body: budget({ hallazgos: [] }), posts });
  const btn = viewer.document.getElementById('pgApproveBtn');
  assert.equal(btn.disabled, false);
  btn.click();
  await flush();
  assert.match(posts[0].url, /\/api\/budget\/approve$/);
  assert.deepEqual(posts[0].body, { hash: 'b789' });
});

test('una aprobación vieja se marca desactualizada', async (t) => {
  const viewer = await loaded(t, { body: budget({ hallazgos: [], revision: { aprobado: true, hash: 'viejo', fecha: '2026-11-18T10:00:00' } }) });
  assert.match(viewer.document.getElementById('pgStatusBadge').textContent, /Desactualizad/);
});

test('«Enviar ajuste al agente» manda la nota y entrega el prompt a la terminal', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { posts });
  viewer.document.getElementById('pgNoteInput').value = 'Agrega una segunda cotización';
  viewer.document.getElementById('pgSendBtn').click();
  await flush();
  assert.match(posts[0].url, /\/api\/budget\/adjust$/);
  assert.deepEqual(posts[0].body, { nota: 'Agrega una segunda cotización' });
  assert.deepEqual(Array.from(viewer.window.__prompts), ['Ajusta el presupuesto: Agrega una segunda cotización']);
});

test('sin presupuesto se explica la Fase 6.4 y el check, y el Gantt de la cadena sigue visible', async (t) => {
  const viewer = await loaded(t, { body: budget({ disponible: false, presupuesto: null, resumen: null, hitos: [], hash: null, hallazgos: [] }) });
  const content = viewer.document.getElementById('pgContent');
  assert.match(content.textContent, /Fase 6\.4/);
  assert.match(content.textContent, /presupuesto_sgr\.py check/);
  assert.equal(content.querySelector('.pg-card'), null);
  assert.ok(content.querySelector('#pgGantt tr[data-actividad="1.1.1"]'));
  assert.ok(viewer.document.getElementById('pgApproveBtn').disabled);
});
