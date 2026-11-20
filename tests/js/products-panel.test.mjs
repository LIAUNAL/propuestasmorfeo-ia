/**
 * Pestaña «Productos e indicadores» (odd/tasks/sgr-productos-indicadores.md, S1 y S6).
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/status`,
 * `/api/products` y los POST se sustituyen por dobles deterministas. En el
 * flujo base la pestaña no existe y la ruta directa avisa.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const PRODUCTOS = {
  schema: 'morfeo.productos-sgr/v1',
  talento: [
    { categoria: 'joven_investigador', cantidad: 4, entidad: 'E1', perfil: 'Joven <b>investigador</b>', formacion: 'Pregrado en ingeniería',
      actividades: ['1.1.1'], duracion_meses: 12, valor_mensual: 3000000, producto_final: 'Informe técnico' },
    { categoria: 'maestria', cantidad: 2, entidad: 'E2', perfil: 'Estudiante de maestría', formacion: 'Ingeniería ambiental',
      actividades: ['1.1.2'], duracion_meses: 24, valor_mensual: 4000000, producto_final: 'Tesis de maestría' },
  ],
  productos_ctei: [
    { tipo: 'nuevo_conocimiento', subtipo: 'Artículo de investigación', categoria: 'A', cantidad: 2, adicional: true, producto_cadena: '1.1', descripcion: 'Artículos Q1' },
    { tipo: 'desarrollo_tecnologico', subtipo: 'Software', categoria: 'B', cantidad: 1, adicional: true, producto_cadena: null, descripcion: 'Registro de software' },
    { tipo: 'formacion', subtipo: 'Tesis', categoria: null, cantidad: 2, adicional: false, producto_cadena: null, descripcion: 'Tesis del mínimo' },
  ],
  divulgacion: {
    introduccion: 'La estrategia llega a la comunidad.', publicos: ['Juntas de acción comunal'], medios: ['Radio comunitaria'],
    productos: ['Podcast'], responsable: 'E1', cronograma: [{ mes: 6, accion: 'Emisión del podcast' }], costeada: true,
  },
  indicadores_gestion: [
    { indicador: 'Informes de supervisión', codigo: '0300G100', meta: 8, unidad: 'Número', formula: 'Informes entregados', tipo_fuente: 'Documento', periodicidad: 'Trimestral' },
  ],
};

const CADENA_PRODUCTOS = [
  { oe: 'OE1', oe_texto: 'Medir la calidad del agua', codigo: '1.1', codigo_dnp: '3906001', nombre: 'Servicio de monitoreo',
    medido_a_traves_de: 'Número de sistemas', indicador: 'Sistemas implementados', unidad: 'Número', meta: 2 },
  { oe: 'OE2', oe_texto: 'Transferir el modelo', codigo: '2.1', codigo_dnp: null, nombre: 'Documentos <i>técnicos</i>',
    medido_a_traves_de: '', indicador: '', unidad: '', meta: null },
];

const MINIMOS = [
  { categoria: 'posdoctorado', requerido: 1, comprometido: 0, cumple: false, texto: 'Un (1) doctor para la realización de una estancia posdoctoral' },
  { categoria: 'maestria', requerido: 2, comprometido: 2, cumple: true, texto: 'Dos (2) estudiantes de maestría en modalidad de investigación' },
  { categoria: 'joven_investigador', requerido: 6, comprometido: 4, cumple: false, texto: 'Seis (6) jóvenes investigadores e innovadores' },
];

function products(overrides = {}) {
  return {
    ok: true, run: '2026-11-demo', flujo: 'sgr', disponible: true, productos: PRODUCTOS, cadena_productos: CADENA_PRODUCTOS,
    minimos_talento: MINIMOS, minimo_productos: null, datos: null,
    entidades: { E1: 'Universidad Nacional', E2: 'Acueducto Municipal' },
    hash: 'p123', aprobado: false, revision: null, errores: [],
    hallazgos: [
      { severity: 'error', code: 'productos-talento-minimo', message: 'Faltan seis jóvenes investigadores', node: 'talento' },
      { severity: 'warning', code: 'productos-cadena-dnp', message: 'El producto 2.1 no tiene código DNP', node: '2.1' },
    ],
    ...overrides,
  };
}

const BASE = { ok: true, run: 'r', flujo: 'base', disponible: false, productos: null, cadena_productos: [], minimos_talento: [], minimo_productos: null, datos: null, entidades: {}, hallazgos: [], aprobado: false, hash: null, revision: null, errores: [] };

function status(flujo) {
  return {
    flujo, active_run: '2026-11-demo', all_runs: ['2026-11-demo'], totals: { total_words: 10 },
    sections: [], gates: [], telemetria: [], pipeline_units: [], artifacts: [],
  };
}

function json(body, code = 200) {
  return { ok: code < 400, status: code, json: async () => body, text: async () => JSON.stringify(body) };
}

async function harness(t, { flujo = 'sgr', body = products(), posts = [] } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    if (u.includes('/api/products/approve')) {
      posts.push({ url: u, body: JSON.parse(init.body) });
      return json({ ok: true, hash: 'p123', fecha: '2026-11-19T10:00:00' });
    }
    if (u.includes('/api/products/adjust')) {
      const sent = JSON.parse(init.body);
      posts.push({ url: u, body: sent });
      return json({ ok: true, prompt: `Ajusta los productos: ${sent.nota}` });
    }
    if (u.includes('/api/products')) return json(flujo === 'sgr' ? body : BASE);
    if (u.includes('/api/components')) return json({ ok: true, flujo, disponible: false, componentes: null, cadena: {}, entidades: {}, hallazgos: [], errores: [] });
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
  await viewer.viewer('loadProducts');
  await flush();
  return viewer;
}

function tabLabels(doc) {
  return Array.from(doc.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
}

function withCtei(list) {
  return products({ productos: { ...PRODUCTOS, productos_ctei: list } });
}

test('SGR: la pestaña «Productos e indicadores» aparece justo después de «TRL y componentes»', async (t) => {
  const viewer = await harness(t);
  const labels = tabLabels(viewer.document);
  const i = labels.indexOf('Productos e indicadores');
  assert.ok(i > 0, 'la pestaña existe en SGR');
  assert.equal(labels[i - 1], 'TRL y componentes');
  assert.equal(labels[i + 1], 'Requisitos y anexos');
  viewer.viewer('navigateTab', 'productos');
  await flush();
  const active = viewer.document.querySelectorAll('.tab-nav__btn.active');
  assert.equal(active.length, 1);
  assert.equal(active[0].textContent.trim(), 'Productos e indicadores');
  assert.ok(viewer.document.getElementById('pane-productos').classList.contains('active'));
});

test('base: la pestaña no existe y la ruta directa muestra un aviso', async (t) => {
  const viewer = await harness(t, { flujo: 'base' });
  assert.ok(!tabLabels(viewer.document).includes('Productos e indicadores'));
  viewer.viewer('navigateTab', 'productos');
  await viewer.viewer('loadProducts');
  await flush();
  const content = viewer.document.getElementById('prContent');
  assert.match(content.textContent, /solo en el flujo SGR/);
  assert.equal(content.querySelector('#prTalento'), null);
  assert.ok(viewer.document.getElementById('prReviewPanel').hidden);
});

test('el talento se muestra con la franja de mínimos y marca la categoría que falta', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const strip = doc.querySelectorAll('#prTalento .pr-min');
  assert.equal(strip.length, 3);
  const min = cat => doc.querySelector(`#prTalento .pr-min[data-categoria="${cat}"]`);
  assert.ok(min('maestria').classList.contains('is-ok'));
  assert.match(min('maestria').textContent, /Cumple/);
  assert.ok(min('posdoctorado').classList.contains('is-missing'));
  assert.match(min('posdoctorado').textContent, /Falta/);
  assert.match(min('posdoctorado').textContent, /Estancia posdoctoral/);
  const jovenes = min('joven_investigador').textContent;
  assert.match(jovenes, /4/);
  assert.match(jovenes, /6/);
  assert.match(jovenes, /Falta/);
  const table = doc.querySelector('#prTalento table').textContent;
  for (const text of ['Jóvenes investigadores e innovadores', 'Universidad Nacional', 'Acueducto Municipal', 'Pregrado en ingeniería',
    '1.1.1', '12', '3.000.000', 'Informe técnico', 'Tesis de maestría']) {
    assert.ok(table.includes(text), `falta ${text} en el talento`);
  }
});

test('sin mínimos en la rúbrica la franja lo explica', async (t) => {
  const viewer = await loaded(t, { body: products({ minimos_talento: [] }) });
  const box = viewer.document.getElementById('prTalento');
  assert.equal(box.querySelector('.pr-min'), null);
  assert.match(box.textContent, /rubrica\.json/);
});

test('los productos por objetivo muestran código DNP, indicador, unidad y meta de la cadena de valor', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const groups = doc.querySelectorAll('#prCadena [data-oe]');
  assert.equal(groups.length, 2);
  const oe1 = doc.querySelector('#prCadena [data-oe="OE1"]').textContent;
  for (const text of ['OE1', 'Medir la calidad del agua', '3906001', 'Servicio de monitoreo', 'Número de sistemas', 'Sistemas implementados', 'Número', '2']) {
    assert.ok(oe1.includes(text), `falta ${text} en OE1`);
  }
  assert.match(doc.querySelector('#prCadena [data-oe="OE2"]').textContent, /Sin código DNP/);
});

test('los productos de CTeI marcan los adicionales y su categoría', async (t) => {
  const viewer = await loaded(t);
  const box = viewer.document.getElementById('prCtei');
  const rows = box.querySelectorAll('tbody tr');
  assert.equal(rows.length, 3);
  assert.match(rows[0].textContent, /Adicional/);
  assert.match(rows[0].textContent, /Nuevo conocimiento/);
  assert.match(rows[0].textContent, /Artículo de investigación/);
  assert.match(rows[0].textContent, /A/);
  assert.match(rows[0].textContent, /Servicio de monitoreo/);
  assert.doesNotMatch(rows[2].textContent, /Adicional/);
  assert.match(rows[2].textContent, /Mínimo/);
  assert.match(box.textContent, /3 adicionales al mínimo/);
  assert.match(box.textContent, /2 TOP o A/);
});

test('la vista previa del 2.5 sigue los tramos del componente A y suma la divulgación', async (t) => {
  const cases = [
    [[{ tipo: 'nuevo_conocimiento', categoria: 'TOP', cantidad: 2, adicional: true }, { tipo: 'formacion', categoria: 'B', cantidad: 1, adicional: true }], '3'],
    [[{ tipo: 'nuevo_conocimiento', categoria: 'A', cantidad: 1, adicional: true }, { tipo: 'formacion', categoria: 'B', cantidad: 1, adicional: true }], '2'],
    [[{ tipo: 'nuevo_conocimiento', categoria: 'B', cantidad: 3, adicional: true }], '1'],
    [[{ tipo: 'nuevo_conocimiento', categoria: 'TOP', cantidad: 5, adicional: false }], '0'],
  ];
  for (const [list, expected] of cases) {
    const viewer = await loaded(t, { body: withCtei(list) });
    const preview = viewer.document.getElementById('prPreview');
    assert.equal(preview.getAttribute('data-puntaje-a'), expected, JSON.stringify(list));
    assert.equal(preview.getAttribute('data-puntaje-div'), '2');
    assert.equal(preview.getAttribute('data-total'), String(Number(expected) + 2));
  }
});

test('la divulgación incompleta o sin costear vale 1 punto y sin estrategia vale 0', async (t) => {
  const incompleta = products({ productos: { ...PRODUCTOS, divulgacion: { ...PRODUCTOS.divulgacion, costeada: false } } });
  let viewer = await loaded(t, { body: incompleta });
  assert.equal(viewer.document.getElementById('prPreview').getAttribute('data-puntaje-div'), '1');
  const sinMedios = products({ productos: { ...PRODUCTOS, divulgacion: { ...PRODUCTOS.divulgacion, medios: [] } } });
  viewer = await loaded(t, { body: sinMedios });
  assert.equal(viewer.document.getElementById('prPreview').getAttribute('data-puntaje-div'), '1');
  viewer = await loaded(t, { body: products({ productos: { ...PRODUCTOS, divulgacion: null } }) });
  assert.equal(viewer.document.getElementById('prPreview').getAttribute('data-puntaje-div'), '0');
  assert.match(viewer.document.getElementById('prDivulgacion').textContent, /Sin estrategia de divulgación/);
});

test('la lista de la divulgación marca públicos, medios, productos, responsable, cronograma y costeo', async (t) => {
  const div = { ...PRODUCTOS.divulgacion, cronograma: [], costeada: false };
  const viewer = await loaded(t, { body: products({ productos: { ...PRODUCTOS, divulgacion: div } }) });
  const doc = viewer.document;
  const item = key => doc.querySelector(`#prDivulgacion .pr-check[data-item="${key}"]`);
  for (const key of ['publicos', 'medios', 'productos', 'responsable']) {
    assert.ok(item(key).classList.contains('is-ok'), key);
  }
  for (const key of ['cronograma', 'costeada']) {
    assert.ok(item(key).classList.contains('is-missing'), key);
  }
  const box = doc.getElementById('prDivulgacion').textContent;
  for (const text of ['Juntas de acción comunal', 'Radio comunitaria', 'Podcast', 'Universidad Nacional']) {
    assert.ok(box.includes(text), `falta ${text} en la divulgación`);
  }
});

test('los indicadores de gestión y de producto se muestran en tablas', async (t) => {
  const viewer = await loaded(t);
  const box = viewer.document.getElementById('prIndicadores');
  const gestion = box.querySelector('#prGestion').textContent;
  for (const text of ['Informes de supervisión', '0300G100', '8', 'Número', 'Informes entregados', 'Documento', 'Trimestral']) {
    assert.ok(gestion.includes(text), `falta ${text} en indicadores de gestión`);
  }
  const producto = box.querySelector('#prIndicadoresProducto').textContent;
  for (const text of ['3906001', 'Sistemas implementados', 'Número', '2']) {
    assert.ok(producto.includes(text), `falta ${text} en indicadores de producto`);
  }
});

test('el texto del agente se escapa: no se inserta HTML', async (t) => {
  const viewer = await loaded(t);
  const content = viewer.document.getElementById('prContent');
  assert.equal(content.querySelector('b'), null);
  assert.equal(content.querySelector('i'), null);
  assert.match(content.textContent, /Joven <b>investigador<\/b>/);
  assert.match(content.textContent, /Documentos <i>técnicos<\/i>/);
});

test('los hallazgos se agrupan por severidad y los errores bloquean la aprobación', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  assert.match(doc.querySelector('#prFindings [data-severidad="error"]').textContent, /jóvenes investigadores/);
  assert.match(doc.querySelector('#prFindings [data-severidad="warning"]').textContent, /productos-cadena-dnp/);
  assert.ok(doc.getElementById('prApproveBtn').disabled);
});

test('«Aprobar» envía el hash que se está viendo', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { body: products({ hallazgos: [] }), posts });
  const btn = viewer.document.getElementById('prApproveBtn');
  assert.equal(btn.disabled, false);
  btn.click();
  await flush();
  assert.match(posts[0].url, /\/api\/products\/approve$/);
  assert.deepEqual(posts[0].body, { hash: 'p123' });
});

test('una aprobación vieja se marca desactualizada', async (t) => {
  const viewer = await loaded(t, { body: products({ hallazgos: [], revision: { aprobado: true, hash: 'viejo', fecha: '2026-11-18T10:00:00' } }) });
  assert.match(viewer.document.getElementById('prStatusBadge').textContent, /Desactualizad/);
});

test('«Enviar ajuste al agente» manda la nota y entrega el prompt a la terminal', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { posts });
  viewer.document.getElementById('prNoteInput').value = 'Agrega un artículo TOP';
  viewer.document.getElementById('prSendBtn').click();
  await flush();
  assert.match(posts[0].url, /\/api\/products\/adjust$/);
  assert.deepEqual(posts[0].body, { nota: 'Agrega un artículo TOP' });
  assert.deepEqual(Array.from(viewer.window.__prompts), ['Ajusta los productos: Agrega un artículo TOP']);
});

test('si la terminal no conecta, el ajuste queda pendiente con «Reintentar envío»', async (t) => {
  const viewer = await loaded(t);
  viewer.window.eval(`window.__tries = 0; sendTerminalPrompt = (cmd) => { window.__tries += 1; window.__prompts.push(cmd); return Promise.resolve(window.__tries > 1); };`);
  viewer.document.getElementById('prNoteInput').value = 'Costea la divulgación';
  viewer.document.getElementById('prSendBtn').click();
  await flush();
  const retry = viewer.document.getElementById('prRetryBtn');
  assert.notEqual(retry.style.display, 'none');
  assert.match(viewer.document.getElementById('prMessage').textContent, /Reintentar/);
  retry.click();
  await flush();
  assert.equal(retry.style.display, 'none');
  assert.equal(viewer.window.__prompts.length, 2);
});

test('sin productos se explica la unidad fase5_sgr y el check', async (t) => {
  const viewer = await loaded(t, { body: products({ disponible: false, productos: null, hash: null, hallazgos: [] }) });
  const content = viewer.document.getElementById('prContent');
  assert.match(content.textContent, /fase5_sgr/);
  assert.match(content.textContent, /productos_sgr\.py check/);
  assert.equal(content.querySelector('#prTalento'), null);
  assert.ok(viewer.document.getElementById('prApproveBtn').disabled);
});

test('la guía de fase5_sgr enlaza la pestaña de productos', async (t) => {
  const viewer = await harness(t);
  const guide = viewer.window.eval('PHASE_GUIDES.fase5_sgr');
  assert.equal(guide.panel.tab, 'productos');
  assert.equal(guide.panel.label, 'Ver productos e indicadores');
});
