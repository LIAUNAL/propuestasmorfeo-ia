/**
 * Pestaña «Cadena de valor» y columna «Estilo SGR» de Secciones
 * (odd/tasks/sgr-cadena-estilo.md, S1 y S7).
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/status`,
 * `/api/value-chain`, `/api/style-sgr` y los POST se sustituyen por dobles
 * deterministas. En el flujo base la pestaña y la columna no existen.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const CADENA = {
  schema: 'morfeo.cadena-valor-sgr/v1',
  duracion_meses: 24,
  objetivos: [
    { id: 'OE1', texto: 'Caracterizar la calidad del agua <b>cruda</b>', productos: [
      { codigo: '1.1', codigo_dnp: '3906001', nombre: 'Documentos de investigación', medido_a_traves_de: 'Número de documentos',
        indicador: 'Documentos elaborados', unidad: 'Número', meta: 2, actividades: [
          { codigo: '1.1.1', nombre: 'Muestreo de campo <script>x</script>', tipo: 'tecnica', ruta_critica: true, mes_inicio: 1, mes_fin: 6, costo: 1000 },
          { codigo: '1.1.2', nombre: 'Análisis de laboratorio', tipo: 'tecnica', ruta_critica: false, mes_inicio: 0, mes_fin: 8, costo: 0 },
          { codigo: '1.1.3', nombre: 'Administración del objetivo', tipo: 'administracion', ruta_critica: false, mes_inicio: null, mes_fin: null, costo: null },
        ] },
    ] },
    { id: 'OE2', texto: 'Desarrollar la plataforma', productos: [
      { codigo: '2.1', codigo_dnp: null, nombre: 'Servicio de información', medido_a_traves_de: 'Sistemas', indicador: 'Sistemas implementados',
        unidad: 'Número', meta: null, actividades: [
          { codigo: '2.1.1', nombre: 'Supervisión del objetivo', tipo: 'supervision', ruta_critica: false, mes_inicio: 3, mes_fin: 24, costo: 250 },
        ] },
    ] },
  ],
};

function chain(overrides = {}) {
  return {
    ok: true, run: '2026-11-demo', flujo: 'sgr', disponible: true, fuente: 'artefactos/sgr/cadena_valor.json',
    cadena: CADENA, hash: 'h123', aprobado: false, revision: null, total_costos: 1250, errores: [],
    hallazgos: [
      { severity: 'error', code: 'cadena-actividades-tecnicas', message: 'El producto 2.1 tiene menos de dos actividades técnicas', node: '2.1' },
      { severity: 'warning', code: 'cadena-codigo-dnp-nulo', message: 'Producto sin código DNP', node: '2.1' },
    ],
    ...overrides,
  };
}

const STYLE = {
  ok: true, flujo: 'sgr', disponible: true, errores: [],
  por_seccion: {
    '02_justificacion': { total: 2, advertencias: 1, info: 1, hallazgos: [
      { severity: 'advertencia', code: 'sgr-estilo-primera-persona', regla: 'primera-persona', linea: 12, extracto: 'proponemos <i>x</i>', message: 'Primera persona' },
      { severity: 'info', code: 'sgr-estilo-falta-de', regla: 'falta-de', linea: 30, extracto: 'falta de', message: 'Evita «falta de»' },
    ] },
  },
};

function status(flujo) {
  return {
    flujo, active_run: '2026-11-demo', all_runs: ['2026-11-demo'], totals: { total_words: 10 },
    sections: [
      { id: '02_justificacion', title: 'Justificación', filename: '02_justificacion.tex', words: 5, citations: 1, has_figures: false, status: 'DRAFT' },
      { id: '10_metodologia', title: 'Metodología', filename: '10_metodologia.tex', words: 5, citations: 0, has_figures: false, status: 'DRAFT' },
    ],
    gates: [], telemetria: [], pipeline_units: [], artifacts: [],
  };
}

function json(body, code = 200) {
  return { ok: code < 400, status: code, json: async () => body, text: async () => JSON.stringify(body) };
}

async function harness(t, { flujo = 'sgr', body = chain(), posts = [], approve = null } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    if (u.includes('/api/value-chain/approve')) {
      posts.push({ url: u, body: JSON.parse(init.body) });
      return approve || json({ ok: true, hash: 'h123', fecha: '2026-11-19T10:00:00' });
    }
    if (u.includes('/api/value-chain/adjust')) {
      const sent = JSON.parse(init.body);
      posts.push({ url: u, body: sent });
      return json({ ok: true, prompt: `Ajusta la cadena: ${sent.nota}` });
    }
    if (u.includes('/api/value-chain')) return json(flujo === 'sgr' ? body : { ok: true, run: 'r', flujo: 'base', disponible: false, cadena: null, hallazgos: [], aprobado: false, hash: null, total_costos: null, errores: [] });
    if (u.includes('/api/style-sgr')) return json(flujo === 'sgr' ? STYLE : { ok: true, flujo: 'base', disponible: false, por_seccion: {}, errores: [] });
    if (u.includes('/api/status')) return json(status(flujo));
    return json({}, 503);
  };
  viewer.window.eval(`window.__prompts = []; sendTerminalPrompt = (cmd) => { window.__prompts.push(cmd); return Promise.resolve(true); };`);
  await viewer.viewer('loadStatusNow');
  await flush();
  return viewer;
}

function tabLabels(doc) {
  return Array.from(doc.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
}

test('SGR: la pestaña «Cadena de valor» aparece justo después de la novedad, que sigue al árbol', async (t) => {
  const viewer = await harness(t);
  const labels = tabLabels(viewer.document);
  const i = labels.indexOf('Cadena de valor');
  assert.ok(i > 0, 'la pestaña existe en SGR');
  assert.equal(labels[i - 1], 'Novedad e hipótesis');
  assert.equal(labels[i - 2], 'Árbol de problemas y objetivos');
  assert.equal(labels[i + 1], 'Alianza y territorio');
});

test('base: la pestaña no existe y la ruta directa muestra un aviso', async (t) => {
  const viewer = await harness(t, { flujo: 'base' });
  assert.ok(!tabLabels(viewer.document).includes('Cadena de valor'));
  viewer.viewer('navigateTab', 'cadena');
  await viewer.viewer('loadValueChain');
  await flush();
  const content = viewer.document.getElementById('vcContent');
  assert.match(content.textContent, /solo en el flujo SGR/);
  assert.equal(content.querySelector('.vc-oe'), null);
});

test('una columna por objetivo con su texto literal, productos, actividades y totales', async (t) => {
  const viewer = await harness(t);
  await viewer.viewer('loadValueChain');
  await flush();
  const doc = viewer.document;
  const cols = doc.querySelectorAll('#vcContent .vc-oe');
  assert.equal(cols.length, 2);
  assert.equal(cols[0].querySelector('.vc-oe__text').textContent, 'Caracterizar la calidad del agua <b>cruda</b>');
  assert.match(cols[0].querySelector('.vc-oe__total').textContent, /1\.000/);
  assert.match(cols[1].querySelector('.vc-oe__total').textContent, /250/);

  const prod = doc.querySelector('.vc-product[data-producto="1.1"]');
  for (const text of ['1.1', '3906001', 'Documentos de investigación', 'Número de documentos', 'Documentos elaborados', 'Número', '2']) {
    assert.ok(prod.textContent.includes(text), `falta ${text} en el producto`);
  }
  assert.match(doc.querySelector('.vc-product[data-producto="2.1"]').textContent, /Sin código DNP/);

  const row = doc.querySelector('[data-actividad="1.1.1"]');
  assert.match(row.textContent, /Muestreo de campo/);
  assert.match(row.querySelector('.vc-tipo').textContent, /Técnica/);
  assert.ok(row.querySelector('.vc-critica'), 'insignia de ruta crítica');
  assert.match(row.textContent, /1–6/);
  const zero = doc.querySelector('[data-actividad="1.1.2"]');
  assert.match(zero.textContent, /0–8/);
  assert.match(zero.querySelector('.vc-costo').textContent, /\$\s*0/);
  assert.equal(doc.querySelector('[data-actividad="1.1.2"] .vc-critica'), null);
  assert.match(doc.querySelector('[data-actividad="1.1.3"] .vc-tipo').textContent, /Administración/);
  assert.match(doc.querySelector('[data-actividad="2.1.1"] .vc-tipo').textContent, /Supervisión/);

  assert.match(doc.getElementById('vcTotal').textContent, /1\.250/);
});

test('el texto del agente se escapa: no se inserta HTML', async (t) => {
  const viewer = await harness(t);
  await viewer.viewer('loadValueChain');
  await flush();
  const content = viewer.document.getElementById('vcContent');
  assert.equal(content.querySelector('script'), null);
  assert.equal(content.querySelector('b'), null);
  assert.match(viewer.document.querySelector('[data-actividad="1.1.1"]').textContent, /<script>x<\/script>/);
});

test('los hallazgos se agrupan por severidad con el código del nodo, y bloquean la aprobación', async (t) => {
  const viewer = await harness(t);
  await viewer.viewer('loadValueChain');
  await flush();
  const doc = viewer.document;
  const error = doc.querySelector('#vcFindings [data-severidad="error"]');
  const warn = doc.querySelector('#vcFindings [data-severidad="warning"]');
  assert.match(error.textContent, /menos de dos actividades técnicas/);
  assert.match(error.textContent, /2\.1/);
  assert.match(warn.textContent, /sin código DNP/);
  assert.ok(doc.getElementById('vcApproveBtn').disabled, 'con errores no se aprueba');
});

test('«Aprobar cadena» envía el hash que se está viendo', async (t) => {
  const posts = [];
  const viewer = await harness(t, { body: chain({ hallazgos: [] }), posts });
  await viewer.viewer('loadValueChain');
  await flush();
  const btn = viewer.document.getElementById('vcApproveBtn');
  assert.equal(btn.disabled, false);
  btn.click();
  await flush();
  assert.match(posts[0].url, /\/api\/value-chain\/approve$/);
  assert.deepEqual(posts[0].body, { hash: 'h123' });
});

test('una cadena aprobada lo dice y una aprobación vieja se marca desactualizada', async (t) => {
  const viewer = await harness(t, { body: chain({ hallazgos: [], aprobado: true, revision: { aprobado: true, hash: 'h123', fecha: '2026-11-19T10:00:00' } }) });
  await viewer.viewer('loadValueChain');
  await flush();
  assert.match(viewer.document.getElementById('vcStatusBadge').textContent, /Aprobada/);

  const stale = await harness(t, { body: chain({ hallazgos: [], aprobado: false, revision: { aprobado: true, hash: 'viejo', fecha: '2026-11-18T10:00:00' } }) });
  await stale.viewer('loadValueChain');
  await flush();
  assert.match(stale.document.getElementById('vcStatusBadge').textContent, /Desactualizada/);
});

test('«Enviar ajuste al agente» manda la nota y entrega el prompt a la terminal', async (t) => {
  const posts = [];
  const viewer = await harness(t, { posts });
  await viewer.viewer('loadValueChain');
  await flush();
  viewer.document.getElementById('vcNoteInput').value = 'Divide el producto 1.1';
  viewer.document.getElementById('vcSendBtn').click();
  await flush();
  assert.match(posts[0].url, /\/api\/value-chain\/adjust$/);
  assert.deepEqual(posts[0].body, { nota: 'Divide el producto 1.1' });
  assert.deepEqual(Array.from(viewer.window.__prompts), ['Ajusta la cadena: Divide el producto 1.1']);
});

test('sin cadena se explica que se siembra después de la compuerta de objetivos', async (t) => {
  const viewer = await harness(t, { body: chain({ disponible: false, cadena: null, hash: null, hallazgos: [], total_costos: null }) });
  await viewer.viewer('loadValueChain');
  await flush();
  const content = viewer.document.getElementById('vcContent');
  assert.match(content.textContent, /cadena_valor_sgr\.py init/);
  assert.match(content.textContent, /objetivos/);
});

test('SGR: Secciones muestra la columna «Estilo SGR» y abre la lista de hallazgos', async (t) => {
  const viewer = await harness(t);
  await viewer.viewer('loadStyleSgr');
  await flush();
  const doc = viewer.document;
  const heads = Array.from(doc.querySelectorAll('#pane-sections thead th')).map(th => th.textContent.trim());
  assert.ok(heads.includes('Estilo SGR'));
  const cell = doc.querySelector('[data-style-section="02_justificacion"]');
  assert.match(cell.textContent, /2/);
  assert.match(doc.querySelector('[data-style-section="10_metodologia"]').textContent, /0/);
  cell.querySelector('button').click();
  await flush();
  const body = doc.getElementById('secModalBody');
  assert.match(body.textContent, /primera-persona/);
  assert.match(body.textContent, /12/);
  assert.match(body.textContent, /proponemos <i>x<\/i>/);
  assert.match(body.textContent, /Primera persona/);
  assert.equal(body.querySelector('i'), null);
});

test('base: Secciones conserva su tabla sin la columna de estilo', async (t) => {
  const viewer = await harness(t, { flujo: 'base' });
  const doc = viewer.document;
  // The canonical sections table; the TDR chapters panel above it stays hidden in base.
  const table = doc.getElementById('sectionsTableBody').closest('table');
  const heads = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent.trim());
  assert.deepEqual(heads, ['Código', 'Sección y Título Oficial', 'Estructura', 'Archivo LaTeX', 'Palabras', 'Citas APA', 'Figuras', 'Estado']);
  assert.equal(doc.querySelector('[data-style-section]'), null);
  assert.equal(doc.querySelectorAll('#sectionsTableBody tr')[0].children.length, 8);
});
