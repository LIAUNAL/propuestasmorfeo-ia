/**
 * Pestaña «TRL y componentes» (odd/tasks/sgr-trl-componentes.md, S1 y S6).
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/status`,
 * `/api/components` y los POST se sustituyen por dobles deterministas. En el
 * flujo base la pestaña no existe y la ruta directa avisa.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const COMPONENTES = {
  schema: 'morfeo.componentes-sgr/v1',
  trl: {
    introduccion: 'El proyecto madura el <b>modelo</b> desde el laboratorio.', tipologia: 'B', entrada: 4, salida: 7,
    evidencia_entrada: ['Prototipo validado en laboratorio'],
    ruta: [
      { hito: 'Prototipo en entorno relevante', mes: 10, trl: 5, actividades: ['1.1.1'], evidencia: 'Informe de pruebas' },
      { hito: 'Demostración en planta', mes: 20, trl: 7, actividades: ['1.1.2'], evidencia: 'Acta de validación' },
    ],
    verificacion: { escenario: 'Planta piloto del acueducto', responsables: ['E1'], criterios_aceptacion: ['Error menor al 5 %'],
      evidencias: ['Acta firmada'], actor_usuario: 'E2' },
  },
  transferencia: {
    introduccion: 'La transferencia llega al acueducto.',
    resultados: [{ resultado: 'Modelo predictivo', usuarios: ['Acueducto', 'Gobernación'], proteccion_pi: 'Registro de software' }],
    ruta: [{ etapa: 'Piloto', mecanismo: 'Licencia', barreras: 'Costos de operación', acciones: 'Capacitar operarios' }],
    actividades: ['1.1.2'], continuidad: 'Convenio de operación',
  },
  asc: {
    introduccion: 'La apropiación acompaña todo el ciclo.',
    actores: [{ grupo: 'Juntas de acción comunal', relacion_problematica: 'Usan el agua', saberes: 'Territorio', rol_momento: 'Diseño', incidencia: 'Alta' }],
    ruta: [
      { elemento: 'identificacion_problema', meses: '1-2', que_se_hace: 'Talleres de diagnóstico', actividades: ['1.1.1'] },
      { elemento: 'vinculacion_actores', meses: '2-3', que_se_hace: 'Mesas', actividades: ['1.1.1'] },
      { elemento: 'diseno', meses: '3-4', que_se_hace: 'Codiseño', actividades: ['1.1.2'] },
      { elemento: 'planeacion', meses: '4', que_se_hace: 'Plan', actividades: ['1.1.2'] },
      { elemento: 'ejecucion', meses: '5-18', que_se_hace: 'Pilotos', actividades: ['1.1.2'] },
      { elemento: 'seguimiento', meses: '6-20', que_se_hace: 'Comités', actividades: [] },
    ],
    productos: [{ producto: 'Cartilla', descripcion: 'Guía comunitaria', medio_verificacion: 'Cartilla publicada', mes: 18, actividad: '1.1.2' }],
  },
  sostenibilidad: {
    introduccion: '',
    ods: [{ ods: 'ODS 6', contribucion: 'Agua limpia', productos: ['Modelo predictivo'] }],
    actores: [{ actor: 'Acueducto', funciones: 'Operar', compromiso: 'Carta de intención' }],
    ambiental: [{ actividad: '1.1.1', medio: 'Agua', efecto: 'Muestreo', manejo: 'Protocolo' }],
  },
  uso_posterior: {
    introduccion: '',
    bienes: [{ bien: 'Servidor GPU', valor_sgr: 80000000, operador: 'E1', financiacion: 'Recursos propios', mantenimiento: 'Anual' }],
    adopcion: [{ actor: 'E2', resultado: 'Modelo predictivo', condiciones: 'Capacitación' }],
  },
  diferencial: {
    introduccion: '',
    barreras: [{ barrera: 'Conectividad', poblacion: 'Rural', medida: 'Material impreso', actividades: ['1.1.1'], indicador: 'Talleres', meta: 4, evidencia: 'Listas' }],
    justificacion_sin_barreras: null,
  },
};

function components(overrides = {}) {
  return {
    ok: true, run: '2026-11-demo', flujo: 'sgr', disponible: true, componentes: COMPONENTES, transferencia_pct: 0.6,
    cadena: { '1.1.1': 'Levantar <i>datos</i>', '1.1.2': 'Transferir el modelo' },
    entidades: { E1: 'Universidad Nacional', E2: 'Acueducto Municipal' },
    hash: 'c123', aprobado: false, revision: null, errores: [],
    hallazgos: [
      { severity: 'error', code: 'componentes-asc-elemento', message: 'Falta el elemento resultados y sostenibilidad', node: 'asc' },
      { severity: 'warning', code: 'componentes-transferencia-pct', message: 'La transferencia no llega al 1 %', node: 'transferencia' },
    ],
    ...overrides,
  };
}

const BASE = { ok: true, run: 'r', flujo: 'base', disponible: false, componentes: null, transferencia_pct: null, cadena: {}, entidades: {}, hallazgos: [], aprobado: false, hash: null, revision: null, errores: [] };

function status(flujo) {
  return {
    flujo, active_run: '2026-11-demo', all_runs: ['2026-11-demo'], totals: { total_words: 10 },
    sections: [], gates: [], telemetria: [], pipeline_units: [], artifacts: [],
  };
}

function json(body, code = 200) {
  return { ok: code < 400, status: code, json: async () => body, text: async () => JSON.stringify(body) };
}

async function harness(t, { flujo = 'sgr', body = components(), posts = [] } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    if (u.includes('/api/components/approve')) {
      posts.push({ url: u, body: JSON.parse(init.body) });
      return json({ ok: true, hash: 'c123', fecha: '2026-11-19T10:00:00' });
    }
    if (u.includes('/api/components/adjust')) {
      const sent = JSON.parse(init.body);
      posts.push({ url: u, body: sent });
      return json({ ok: true, prompt: `Ajusta los componentes: ${sent.nota}` });
    }
    if (u.includes('/api/components')) return json(flujo === 'sgr' ? body : BASE);
    if (u.includes('/api/budget')) return json({ ok: true, flujo, disponible: false, presupuesto: null, resumen: null, proyeccion: null, cadena_meses: [], hitos: [], hallazgos: [], errores: [] });
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
  await viewer.viewer('loadComponents');
  await flush();
  return viewer;
}

function tabLabels(doc) {
  return Array.from(doc.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
}

test('SGR: la pestaña «TRL y componentes» aparece justo después de «Presupuesto y cronograma»', async (t) => {
  const viewer = await harness(t);
  const labels = tabLabels(viewer.document);
  const i = labels.indexOf('TRL y componentes');
  assert.ok(i > 0, 'la pestaña existe en SGR');
  assert.equal(labels[i - 1], 'Presupuesto y cronograma');
  assert.equal(labels[i + 1], 'Productos e indicadores');
  viewer.viewer('navigateTab', 'componentes');
  await flush();
  const active = viewer.document.querySelectorAll('.tab-nav__btn.active');
  assert.equal(active.length, 1);
  assert.equal(active[0].textContent.trim(), 'TRL y componentes');
  assert.ok(viewer.document.getElementById('pane-componentes').classList.contains('active'));
});

test('base: la pestaña no existe y la ruta directa muestra un aviso', async (t) => {
  const viewer = await harness(t, { flujo: 'base' });
  assert.ok(!tabLabels(viewer.document).includes('TRL y componentes'));
  viewer.viewer('navigateTab', 'componentes');
  await viewer.viewer('loadComponents');
  await flush();
  const content = viewer.document.getElementById('cpContent');
  assert.match(content.textContent, /solo en el flujo SGR/);
  assert.equal(content.querySelector('.cp-trl'), null);
  assert.ok(viewer.document.getElementById('cpReviewPanel').hidden);
});

test('la escalera TRL marca entrada y salida y ubica los hitos por nivel con mes y evidencia', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const levels = doc.querySelectorAll('#cpTrl .cp-trl__level');
  assert.equal(levels.length, 9);
  const level = n => doc.querySelector(`#cpTrl .cp-trl__level[data-nivel="${n}"]`);
  assert.ok(level(4).classList.contains('is-entrada'));
  assert.ok(level(7).classList.contains('is-salida'));
  assert.ok(level(5).classList.contains('is-ruta'));
  assert.ok(!level(2).classList.contains('is-ruta'));
  assert.ok(!level(9).classList.contains('is-ruta'));
  const h5 = level(5).querySelector('.cp-trl__hito');
  assert.match(h5.textContent, /Prototipo en entorno relevante/);
  assert.match(h5.textContent, /mes 10/);
  assert.match(h5.textContent, /Informe de pruebas/);
  assert.match(level(7).textContent, /Demostración en planta/);
  assert.match(doc.querySelector('#cpTrl [data-tipologia]').textContent, /B/);
  const plan = doc.getElementById('cpVerificacion').textContent;
  for (const text of ['Planta piloto del acueducto', 'Universidad Nacional', 'Error menor al 5 %', 'Acta firmada', 'Acueducto Municipal']) {
    assert.ok(plan.includes(text), `falta ${text} en el plan de verificación`);
  }
  assert.match(doc.getElementById('cpTrl').textContent, /Prototipo validado en laboratorio/);
});

test('la transferencia muestra resultados, ruta, actividades con nombre y el medidor contra la línea del 1 %', async (t) => {
  const viewer = await loaded(t);
  const box = viewer.document.getElementById('cpTransferencia');
  for (const text of ['Modelo predictivo', 'Acueducto, Gobernación', 'Registro de software', 'Piloto', 'Licencia',
    'Costos de operación', 'Capacitar operarios', '1.1.2', 'Transferir el modelo', 'Convenio de operación', '0,6 %']) {
    assert.ok(box.textContent.includes(text), `falta ${text} en transferencia`);
  }
  const meter = box.querySelector('[data-pct] .pg-meter');
  assert.ok(meter, 'hay medidor del porcentaje');
  assert.match(meter.querySelector('.pg-meter__line').getAttribute('title'), /1 %/);
  assert.ok(box.querySelector('[data-pct]').classList.contains('is-warn'));
});

test('sin resumen del presupuesto el porcentaje de transferencia se explica', async (t) => {
  const viewer = await loaded(t, { body: components({ transferencia_pct: null }) });
  const box = viewer.document.getElementById('cpTransferencia');
  assert.equal(box.querySelector('.pg-meter'), null);
  assert.match(box.textContent, /presupuesto/);
});

test('la ruta ASC es una lista de los siete elementos y marca el que falta', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const items = doc.querySelectorAll('#cpAsc .cp-asc__step');
  assert.equal(items.length, 7);
  const missing = doc.querySelector('#cpAsc .cp-asc__step[data-elemento="resultados_sostenibilidad"]');
  assert.ok(missing.classList.contains('is-missing'));
  assert.match(missing.textContent, /Falta/);
  const first = doc.querySelector('#cpAsc .cp-asc__step[data-elemento="identificacion_problema"]');
  assert.ok(first.classList.contains('is-done'));
  assert.match(first.textContent, /Talleres de diagnóstico/);
  assert.match(first.textContent, /1-2/);
  assert.match(first.textContent, /1\.1\.1/);
  const seguimiento = doc.querySelector('#cpAsc .cp-asc__step[data-elemento="seguimiento"]');
  assert.ok(seguimiento.classList.contains('is-warn'), 'un elemento sin actividades se advierte');
  const asc = doc.getElementById('cpAsc').textContent;
  for (const text of ['Juntas de acción comunal', 'Cartilla', 'Cartilla publicada', '18']) {
    assert.ok(asc.includes(text), `falta ${text} en ASC`);
  }
});

test('sostenibilidad, uso posterior y medidas diferenciales se muestran con los nombres de las entidades', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const sost = doc.getElementById('cpSostenibilidad');
  assert.ok(sost.querySelector('.cp-ods'));
  for (const text of ['ODS 6', 'Agua limpia', 'Modelo predictivo', 'Carta de intención', 'Protocolo']) {
    assert.ok(sost.textContent.includes(text), `falta ${text} en sostenibilidad`);
  }
  const uso = doc.getElementById('cpUso').textContent;
  for (const text of ['Servidor GPU', '80.000.000', 'Universidad Nacional', 'Recursos propios', 'Acueducto Municipal', 'Capacitación']) {
    assert.ok(uso.includes(text), `falta ${text} en uso posterior`);
  }
  const dif = doc.getElementById('cpDiferencial').textContent;
  for (const text of ['Conectividad', 'Rural', 'Material impreso', 'Talleres', '4', 'Listas']) {
    assert.ok(dif.includes(text), `falta ${text} en medidas diferenciales`);
  }
});

test('sin barreras se muestra la justificación', async (t) => {
  const comp = { ...COMPONENTES, diferencial: { introduccion: '', barreras: [], justificacion_sin_barreras: 'La población no enfrenta barreras' } };
  const viewer = await loaded(t, { body: components({ componentes: comp }) });
  assert.match(viewer.document.getElementById('cpDiferencial').textContent, /La población no enfrenta barreras/);
});

test('las introducciones se muestran plegables', async (t) => {
  const viewer = await loaded(t);
  const intro = viewer.document.querySelector('#cpTrl details.cp-intro');
  assert.ok(intro);
  assert.match(intro.textContent, /madura el <b>modelo<\/b>/);
});

test('el texto del agente se escapa: no se inserta HTML', async (t) => {
  const viewer = await loaded(t);
  const content = viewer.document.getElementById('cpContent');
  assert.equal(content.querySelector('b'), null);
  assert.equal(content.querySelector('i'), null);
  assert.match(content.textContent, /Levantar <i>datos<\/i>/);
});

test('los hallazgos se agrupan por severidad y los errores bloquean la aprobación', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  assert.match(doc.querySelector('#cpFindings [data-severidad="error"]').textContent, /resultados y sostenibilidad/);
  assert.match(doc.querySelector('#cpFindings [data-severidad="warning"]').textContent, /componentes-transferencia-pct/);
  assert.ok(doc.getElementById('cpApproveBtn').disabled);
});

test('«Aprobar» envía el hash que se está viendo', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { body: components({ hallazgos: [] }), posts });
  const btn = viewer.document.getElementById('cpApproveBtn');
  assert.equal(btn.disabled, false);
  btn.click();
  await flush();
  assert.match(posts[0].url, /\/api\/components\/approve$/);
  assert.deepEqual(posts[0].body, { hash: 'c123' });
});

test('una aprobación vieja se marca desactualizada', async (t) => {
  const viewer = await loaded(t, { body: components({ hallazgos: [], revision: { aprobado: true, hash: 'viejo', fecha: '2026-11-18T10:00:00' } }) });
  assert.match(viewer.document.getElementById('cpStatusBadge').textContent, /Desactualizad/);
});

test('«Enviar ajuste al agente» manda la nota y entrega el prompt a la terminal', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { posts });
  viewer.document.getElementById('cpNoteInput').value = 'Agrega un ODS';
  viewer.document.getElementById('cpSendBtn').click();
  await flush();
  assert.match(posts[0].url, /\/api\/components\/adjust$/);
  assert.deepEqual(posts[0].body, { nota: 'Agrega un ODS' });
  assert.deepEqual(Array.from(viewer.window.__prompts), ['Ajusta los componentes: Agrega un ODS']);
});

test('sin componentes se explica la unidad fase5_5_sgr y el check', async (t) => {
  const viewer = await loaded(t, { body: components({ disponible: false, componentes: null, hash: null, hallazgos: [] }) });
  const content = viewer.document.getElementById('cpContent');
  assert.match(content.textContent, /fase5_5_sgr/);
  assert.match(content.textContent, /componentes_sgr\.py check/);
  assert.equal(content.querySelector('.cp-trl'), null);
  assert.ok(viewer.document.getElementById('cpApproveBtn').disabled);
});
