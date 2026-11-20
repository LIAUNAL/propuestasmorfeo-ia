/**
 * Pestaña «Requisitos y anexos» (odd/tasks/sgr-requisitos-anexos.md, S1 y S7).
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/status`,
 * `/api/requirements` y los POST se sustituyen por dobles deterministas. En el
 * flujo base la pestaña no existe, la lista de pestañas no cambia y la ruta
 * directa avisa.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const BASE_TABS = ['Flujo general', 'Convocatorias', 'Pipeline y Avance', 'Árbol de problemas y objetivos', 'MGA resumido', 'Secciones',
  'Juez final', 'Grafos Proyecto', 'Estilo y redundancia', 'Previsualización PDF', 'Artefactos',
  'Telemetría y Costos'];

function isoInDays(days) {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() + days);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const REQUISITOS = [
  { id: '11.4', nombre: 'Anexo 1', texto: 'Adjuntar el Anexo 1 firmado', condicion: null, documento: 'Anexo 1', numeral_fuente: '11.4',
    estado: 'listo', responsable: 'E1', archivo: 'insumos/requisitos/anexo1.pdf', fecha: '2026-11-05', nota: null, justificacion: null, aplica_derivada: null },
  { id: '11.10', nombre: 'Aval de <b>ética</b>', texto: 'Aval del comité de ética cuando aplique', condicion: 'etica', documento: 'Aval de ética', numeral_fuente: '11.10',
    estado: 'no_aplica', responsable: null, archivo: null, fecha: null, nota: null, justificacion: 'Sin participantes humanos', aplica_derivada: null },
  { id: '11.11', nombre: 'Entidades internacionales', texto: 'Carta de la entidad internacional', condicion: 'internacional', documento: 'Carta de intención', numeral_fuente: '11.11',
    estado: 'pendiente', responsable: 'E2', archivo: null, fecha: null, nota: 'Pedir a la embajada', justificacion: null, aplica_derivada: true },
];

const CIFRAS = [
  { documento: 'sigp', campo: 'total_sgr', declarado: 100, esperado: 100, coincide: true },
  { documento: 'sigp', campo: 'total', declarado: 125, esperado: 120, coincide: false },
  { documento: 'anexo1', campo: 'E1.especie', declarado: null, esperado: 20, coincide: null },
];

const LICENCIAS = {
  introduccion: 'El proyecto no requiere <i>licencia</i> ambiental.',
  items: [
    { licencia: 'Licencia ambiental', norma: 'Decreto 1076 de 2015', aplica: false, justificacion: 'No hay intervención física', responsable: null, momento: null },
    { licencia: 'Permiso de investigación científica', norma: 'Decreto 3016 de 2013', aplica: true, justificacion: '', responsable: 'E1', momento: 'previo' },
  ],
};

const AVAL = {
  institucion: { id: 'unal', nombre: 'Universidad Nacional de Colombia' },
  documentos: [
    { indice: 1, texto: 'Cartas de certificación de la contrapartida en especie', estado: 'listo', archivo: 'insumos/requisitos/cartas.pdf' },
    { indice: 2, texto: 'MGA WEB preliminar Tipología D', estado: 'pendiente', archivo: null },
  ],
  hitos: [
    { actividad: 'Radicación en Hermes', responsable: 'Grupo de investigación', fecha: '2000-01-01', fecha_texto: '1 de enero de 2000' },
    { actividad: 'Validación de la facultad', responsable: 'Facultad', fecha: isoInDays(10), fecha_texto: 'en diez días' },
  ],
};

const HALLAZGOS = [
  { severity: 'error', code: 'requisitos-cifras', message: 'El total del SIGP no coincide con el presupuesto', node: 'cifras.sigp' },
  { severity: 'warning', code: 'requisitos-sin-archivo', message: 'El 11.11 no tiene archivo', node: '11.11' },
];

function vista(overrides = {}) {
  return { convocatoria: 'conv54', requisitos: REQUISITOS, progreso: { listos: 1, aplicables: 2 }, cifras: CIFRAS,
    licencias: LICENCIAS, aval: AVAL, findings: HALLAZGOS, ...overrides };
}

function requirements(overrides = {}) {
  return {
    ok: true, run: '2026-11-demo', flujo: 'sgr', disponible: true, requisitos: { schema: 'morfeo.requisitos-sgr/v1' },
    vista: vista(), hallazgos: HALLAZGOS, entidades: { E1: 'Universidad Nacional', E2: 'Acueducto Municipal' },
    hash: 'r123', aprobado: false, revision: null, errores: [], ...overrides,
  };
}

const BASE = { ok: true, run: 'r', flujo: 'base', disponible: false, requisitos: null, vista: null, hallazgos: [], entidades: {}, aprobado: false, hash: null, revision: null, errores: [] };

function status(flujo) {
  return {
    flujo, active_run: '2026-11-demo', all_runs: ['2026-11-demo'], totals: { total_words: 10 },
    sections: [], gates: [], telemetria: [], pipeline_units: [], artifacts: [],
  };
}

function json(body, code = 200) {
  return { ok: code < 400, status: code, json: async () => body, text: async () => JSON.stringify(body) };
}

function savedItem(id, cambios) {
  const row = REQUISITOS.find(r => r.id === id) || {};
  const item = { ...row, ...cambios };
  return { ...requirements({ hash: 'r456' }), vista: vista({ requisitos: REQUISITOS.map(r => (r.id === id ? item : r)) }), item };
}

async function harness(t, { flujo = 'sgr', body = requirements(), posts = [], itemReply = null } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    if (u.includes('/api/requirements/item')) {
      const sent = JSON.parse(init.body);
      posts.push({ url: u, body: sent });
      if (itemReply) return itemReply(sent);
      return json(sent.id.startsWith('cifras.') ? { ...requirements(), item: sent.cambios } : savedItem(sent.id, sent.cambios));
    }
    if (u.includes('/api/requirements/approve')) {
      posts.push({ url: u, body: JSON.parse(init.body) });
      return json({ ok: true, hash: 'r123', fecha: '2026-11-20T10:00:00' });
    }
    if (u.includes('/api/requirements/adjust')) {
      const sent = JSON.parse(init.body);
      posts.push({ url: u, body: sent });
      return json({ ok: true, prompt: `Ajusta los requisitos: ${sent.nota}` });
    }
    if (u.includes('/api/requirements')) return json(flujo === 'sgr' ? body : BASE);
    if (u.includes('/api/products')) return json({ ok: true, flujo, disponible: false, productos: null, cadena_productos: [], minimos_talento: [], entidades: {}, hallazgos: [], errores: [] });
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
  await viewer.viewer('loadRequirements');
  await flush();
  return viewer;
}

function tabLabels(doc) {
  return Array.from(doc.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
}

function row(doc, id) {
  return doc.querySelector(`#rqRequisitos tr[data-id="${id}"]`);
}

function edit(viewer, el, value) {
  el.value = value;
  el.dispatchEvent(new viewer.window.Event('change', { bubbles: true }));
}

test('SGR: la pestaña «Requisitos y anexos» aparece justo después de «Productos e indicadores»', async (t) => {
  const viewer = await harness(t);
  const labels = tabLabels(viewer.document);
  const i = labels.indexOf('Requisitos y anexos');
  assert.ok(i > 0, 'la pestaña existe en SGR');
  assert.equal(labels[i - 1], 'Productos e indicadores');
  assert.equal(labels[i + 1], 'Anexo 2');
  viewer.viewer('navigateTab', 'requisitos');
  await flush();
  const active = viewer.document.querySelectorAll('.tab-nav__btn.active');
  assert.equal(active.length, 1);
  assert.equal(active[0].textContent.trim(), 'Requisitos y anexos');
  assert.ok(viewer.document.getElementById('pane-requisitos').classList.contains('active'));
});

test('base: la lista de pestañas sigue igual y la ruta directa muestra un aviso', async (t) => {
  const viewer = await harness(t, { flujo: 'base' });
  assert.deepEqual(tabLabels(viewer.document), BASE_TABS);
  viewer.viewer('navigateTab', 'requisitos');
  await viewer.viewer('loadRequirements');
  await flush();
  const content = viewer.document.getElementById('rqContent');
  assert.match(content.textContent, /solo en el flujo SGR/);
  assert.equal(content.querySelector('#rqRequisitos'), null);
  assert.ok(viewer.document.getElementById('rqReviewPanel').hidden);
});

test('el progreso muestra listos sobre aplicables', async (t) => {
  const viewer = await loaded(t);
  const box = viewer.document.getElementById('rqProgreso');
  assert.equal(box.getAttribute('data-listos'), '1');
  assert.equal(box.getAttribute('data-aplicables'), '2');
  assert.match(box.textContent, /1 de 2/);
});

test('la tabla de requisitos muestra condición, aplicabilidad, documento, estado y responsable', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  assert.equal(doc.querySelectorAll('#rqRequisitos tbody tr').length, 3);
  const r4 = row(doc, '11.4');
  for (const text of ['11.4', 'Anexo 1', 'Siempre', 'Listo']) assert.ok(r4.textContent.includes(text), `falta ${text} en 11.4`);
  assert.equal(r4.querySelector('[data-field="estado"]').value, 'listo');
  assert.equal(r4.querySelector('[data-field="responsable"]').value, 'E1');
  assert.equal(r4.querySelector('[data-field="archivo"]').value, 'insumos/requisitos/anexo1.pdf');
  assert.equal(r4.querySelector('[data-field="fecha"]').value, '2026-11-05');
  assert.ok(r4.querySelector('[data-field="estado"] option[value="no_aplica"]').disabled, 'sin condición no se puede marcar «No aplica»');
  const r11 = row(doc, '11.11');
  assert.match(r11.textContent, /Entidad internacional/);
  assert.match(r11.textContent, /Aplica/);
  assert.match(r11.textContent, /Carta de intención/);
  assert.equal(r11.querySelector('[data-field="nota"]').value, 'Pedir a la embajada');
  assert.ok(Array.from(r11.querySelectorAll('[data-field="responsable"] option')).some(o => o.textContent.includes('Acueducto Municipal')));
  assert.equal(row(doc, '11.10').querySelector('[data-field="justificacion"]').value, 'Sin participantes humanos');
});

test('editar el estado de un requisito envía solo ese campo y pinta la respuesta', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { posts });
  edit(viewer, row(viewer.document, '11.11').querySelector('[data-field="estado"]'), 'en_tramite');
  await flush();
  assert.match(posts[0].url, /\/api\/requirements\/item$/);
  assert.deepEqual(posts[0].body, { id: '11.11', cambios: { estado: 'en_tramite' } });
  assert.equal(row(viewer.document, '11.11').querySelector('[data-field="estado"]').value, 'en_tramite');
  assert.match(viewer.document.getElementById('rqHashNote').textContent, /r456/);
  assert.match(viewer.document.getElementById('rqMessage').textContent, /11\.11/);
});

test('vaciar un campo de texto lo envía como null', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { posts });
  edit(viewer, row(viewer.document, '11.11').querySelector('[data-field="nota"]'), '  ');
  await flush();
  assert.deepEqual(posts[0].body, { id: '11.11', cambios: { nota: null } });
});

test('un rechazo del servidor se muestra y la fila vuelve al valor guardado', async (t) => {
  const posts = [];
  const itemReply = () => json({ ok: false, error: 'Estado inválido: listo sin archivo' }, 400);
  const viewer = await loaded(t, { posts, itemReply });
  edit(viewer, row(viewer.document, '11.11').querySelector('[data-field="archivo"]'), 'insumos/requisitos/carta.pdf');
  await flush();
  assert.match(viewer.document.getElementById('rqMessage').textContent, /Estado inválido: listo sin archivo/);
  assert.ok(viewer.document.getElementById('rqMessage').classList.contains('is-error'));
  assert.equal(row(viewer.document, '11.11').querySelector('[data-field="archivo"]').value, '');
});

test('la coherencia de cifras compara declarado y esperado y edita el bloque del documento', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { posts });
  const doc = viewer.document;
  const total = doc.querySelector('#rqCifras tr[data-documento="sigp"][data-campo="total"]');
  assert.match(total.textContent, /SIGP/);
  assert.match(total.textContent, /No coincide/);
  assert.match(doc.querySelector('#rqCifras tr[data-documento="sigp"][data-campo="total_sgr"]').textContent, /Coincide/);
  assert.match(doc.querySelector('#rqCifras tr[data-documento="anexo1"]').textContent, /Sin declarar/);
  edit(viewer, total.querySelector('input[data-cifra]'), '120');
  await flush();
  assert.deepEqual(posts[0].body, { id: 'cifras.sigp', cambios: { total_sgr: 100, total: 120 } });
  edit(viewer, doc.querySelector('#rqCifras tr[data-documento="anexo1"] input[data-cifra]'), '20');
  await flush();
  assert.deepEqual(posts[1].body, { id: 'cifras.anexo1', cambios: { por_entidad: { E1: { especie: 20 } } } });
});

test('la tabla de licencias muestra norma, si aplica, justificación, responsable y momento', async (t) => {
  const viewer = await loaded(t);
  const box = viewer.document.getElementById('rqLicencias');
  const rows = box.querySelectorAll('tbody tr');
  assert.equal(rows.length, 2);
  assert.match(rows[0].textContent, /Licencia ambiental/);
  assert.match(rows[0].textContent, /Decreto 1076 de 2015/);
  assert.match(rows[0].textContent, /No/);
  assert.match(rows[0].textContent, /No hay intervención física/);
  assert.match(rows[1].textContent, /Universidad Nacional/);
  assert.match(rows[1].textContent, /Previo/);
  for (const h of ['Licencia o permiso', 'Norma', '¿Aplica?', 'Justificación', 'Responsable', 'Momento del trámite']) {
    assert.ok(box.querySelector('thead').textContent.includes(h), `falta el encabezado ${h}`);
  }
});

test('el aval institucional lista los documentos y los días que faltan a cada hito', async (t) => {
  const viewer = await loaded(t);
  const box = viewer.document.getElementById('rqAval');
  assert.match(box.textContent, /Universidad Nacional de Colombia/);
  const docs = box.querySelectorAll('.pr-check');
  assert.equal(docs.length, 2);
  assert.ok(docs[0].classList.contains('is-ok'));
  assert.ok(docs[1].classList.contains('is-missing'));
  const hitos = box.querySelectorAll('tr[data-dias]');
  assert.equal(hitos.length, 2);
  assert.ok(Number(hitos[0].getAttribute('data-dias')) < 0);
  assert.match(hitos[0].textContent, /Vencido/);
  assert.equal(hitos[1].getAttribute('data-dias'), '10');
  assert.match(hitos[1].textContent, /Faltan 10 días/);
});

test('los días que faltan se cuentan por fecha calendario', async (t) => {
  const viewer = await harness(t);
  const days = (fecha, y, m, d) => viewer.window.eval(`rqDaysLeft(${JSON.stringify(fecha)}, new Date(${y}, ${m}, ${d}, 23, 30))`);
  assert.equal(days('2026-11-13', 2026, 10, 9), 4);
  assert.equal(days('2026-11-09', 2026, 10, 9), 0);
  assert.equal(days('2026-11-08', 2026, 10, 9), -1);
  assert.equal(days('sin fecha', 2026, 10, 9), null);
});

test('el texto del agente se escapa: no se inserta HTML', async (t) => {
  const viewer = await loaded(t);
  const content = viewer.document.getElementById('rqContent');
  assert.equal(content.querySelector('b'), null);
  assert.equal(content.querySelector('i'), null);
  assert.match(content.textContent, /Aval de <b>ética<\/b>/);
});

test('los hallazgos se agrupan por severidad y los errores bloquean la aprobación', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  assert.match(doc.querySelector('#rqFindings [data-severidad="error"]').textContent, /SIGP no coincide/);
  assert.match(doc.querySelector('#rqFindings [data-severidad="warning"]').textContent, /requisitos-sin-archivo/);
  assert.ok(doc.getElementById('rqApproveBtn').disabled);
});

test('«Aprobar» envía el hash que se está viendo', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { body: requirements({ hallazgos: [] }), posts });
  const btn = viewer.document.getElementById('rqApproveBtn');
  assert.equal(btn.disabled, false);
  btn.click();
  await flush();
  assert.match(posts[0].url, /\/api\/requirements\/approve$/);
  assert.deepEqual(posts[0].body, { hash: 'r123' });
});

test('una aprobación vieja se marca desactualizada y sin archivo no se puede aprobar', async (t) => {
  let viewer = await loaded(t, { body: requirements({ hallazgos: [], revision: { aprobado: true, hash: 'viejo', fecha: '2026-11-18T10:00:00' } }) });
  assert.match(viewer.document.getElementById('rqStatusBadge').textContent, /Desactualizad/);
  viewer = await loaded(t, { body: requirements({ hallazgos: [], requisitos: null, hash: null }) });
  assert.ok(viewer.document.getElementById('rqApproveBtn').disabled);
  assert.match(viewer.document.getElementById('rqContent').textContent, /requisitos_sgr\.py init/);
});

test('«Enviar ajuste al agente» manda la nota y entrega el prompt a la terminal', async (t) => {
  const posts = [];
  const viewer = await loaded(t, { posts });
  viewer.document.getElementById('rqNoteInput').value = 'Agrega el permiso de colecta';
  viewer.document.getElementById('rqSendBtn').click();
  await flush();
  assert.match(posts[0].url, /\/api\/requirements\/adjust$/);
  assert.deepEqual(posts[0].body, { nota: 'Agrega el permiso de colecta' });
  assert.deepEqual(Array.from(viewer.window.__prompts), ['Ajusta los requisitos: Agrega el permiso de colecta']);
});

test('si la terminal no conecta, el ajuste queda pendiente con «Reintentar envío»', async (t) => {
  const viewer = await loaded(t);
  viewer.window.eval(`window.__tries = 0; sendTerminalPrompt = (cmd) => { window.__tries += 1; window.__prompts.push(cmd); return Promise.resolve(window.__tries > 1); };`);
  viewer.document.getElementById('rqNoteInput').value = 'Revisa las cifras';
  viewer.document.getElementById('rqSendBtn').click();
  await flush();
  const retry = viewer.document.getElementById('rqRetryBtn');
  assert.notEqual(retry.style.display, 'none');
  retry.click();
  await flush();
  assert.equal(retry.style.display, 'none');
  assert.equal(viewer.window.__prompts.length, 2);
});

test('sin el script del kit se explica la unidad fase6_9_sgr', async (t) => {
  const viewer = await loaded(t, { body: requirements({ disponible: false, vista: null, hallazgos: [] }) });
  const content = viewer.document.getElementById('rqContent');
  assert.match(content.textContent, /fase6_9_sgr/);
  assert.match(content.textContent, /requisitos_sgr\.py/);
  assert.equal(content.querySelector('#rqRequisitos'), null);
});

test('la guía de fase6_9_sgr enlaza la pestaña de requisitos', async (t) => {
  const viewer = await harness(t);
  const guide = viewer.window.eval('PHASE_GUIDES.fase6_9_sgr');
  assert.equal(guide.panel.tab, 'requisitos');
  assert.equal(guide.panel.label, 'Ver requisitos y anexos');
});
