/**
 * Pestaña «Anexo 2» (odd/tasks/sgr-anexo2.md, S1 y S4).
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/status` y
 * `/api/anexo2` se sustituyen por dobles deterministas con la forma del
 * contrato `morfeo.anexo2-sgr/v1`. En el flujo base la pestaña no existe, la
 * lista de pestañas no cambia y la ruta directa avisa. Es de solo lectura.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const BASE_TABS = ['Flujo general', 'Convocatorias', 'Pipeline y Avance', 'Árbol de problemas y objetivos', 'Novedad e hipótesis', 'Secciones',
  'Juez final', 'Grafos Proyecto', 'Estilo y redundancia', 'Previsualización PDF', 'Artefactos',
  'Telemetría y Costos'];

const REGLA = {
  proposito: 'Mostrar el <b>problema</b> central con cifras del territorio.',
  estructura: 'Antecedentes, magnitud y causas.',
  extension: 'Entre 600 y 900 palabras.',
  aperturas: ['El municipio registra', 'Según el DANE'],
  evitar: ['Aperturas cósmicas'],
  fuente: 'Guía MGA, capítulo 3',
};

const CAPITULOS = [
  {
    numero: 3, titulo: 'Planteamiento del problema', estado: 'incompleto', palabras: 640,
    secciones: [
      { stem: '03_descripcion_problema', existe: true, palabras: 640, origen: 'manual', script: null, estado: 'redactado',
        hallazgos: { error: 1, warning: 2, info: 0 }, guia: '§3' },
      { stem: '03b_arbol_problemas', existe: false, palabras: 0, origen: null, script: null, estado: 'falta',
        hallazgos: { error: 0, warning: 0, info: 0 }, guia: '§3' },
    ],
    regla: REGLA,
    lexico: { favorecida: 4, desaconsejada: 2, prohibida: 1 },
    criterios: [{ id: '2.1', nombre: 'Pertinencia', max: 10 }, { id: '2.3', nombre: 'Coherencia <i>técnica</i>', max: 5 }],
    hallazgos: [
      { severidad: 'error', codigo: 'sgr-cifra-sin-fuente', mensaje: 'Cifra sin fuente en el segundo párrafo', seccion: '03_descripcion_problema' },
      { severidad: 'warning', codigo: 'estilo-apertura', mensaje: 'Apertura desaconsejada', seccion: '03_descripcion_problema' },
    ],
  },
  {
    numero: 21, titulo: 'Anexo de cronograma', estado: 'listo', palabras: 80,
    secciones: [
      { stem: '21_cronograma', existe: true, palabras: 80, origen: 'generado', script: 'scripts/cronograma.py', estado: 'generado',
        hallazgos: { error: 0, warning: 0, info: 1 }, guia: 'A21' },
    ],
    regla: null,
    lexico: { favorecida: 0, desaconsejada: 0, prohibida: 0 },
    criterios: [],
    hallazgos: [],
  },
];

function vista(overrides = {}) {
  return {
    schema: 'morfeo.anexo2-sgr/v1', flujo: 'sgr', fuente_capitulos: 'artefactos/estructura_tdr.json',
    fuente_reglas: 'docs/sgr/patrones_redaccion_sgr.md', rubrica: 'conv54',
    resumen: { capitulos: 2, por_estado: { falta: 0, incompleto: 1, desactualizado: 0, listo: 1 }, palabras: 720 },
    capitulos: CAPITULOS, ...overrides,
  };
}

function annex2(overrides = {}) {
  return { ok: true, run: '2026-11-demo', flujo: 'sgr', disponible: true, vista: vista(), error: null, ...overrides };
}

const BASE = { ok: false, run: 'r', flujo: 'base', disponible: false, vista: null, error: 'La vista del Anexo 2 solo existe en el flujo SGR.' };

function status(flujo) {
  return {
    flujo, active_run: '2026-11-demo', all_runs: ['2026-11-demo'], totals: { total_words: 10 },
    sections: [], gates: [], telemetria: [], pipeline_units: [], artifacts: [],
  };
}

function json(body, code = 200) {
  return { ok: code < 400, status: code, json: async () => body, text: async () => JSON.stringify(body) };
}

async function harness(t, { flujo = 'sgr', body = annex2(), calls = [] } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    calls.push({ url: u, method: (init && init.method) || 'GET' });
    if (u.includes('/api/anexo2')) return flujo === 'sgr' ? json(body) : json(BASE, 409);
    if (u.includes('/api/requirements')) return json({ ok: true, flujo, disponible: false, requisitos: null, vista: null, hallazgos: [], entidades: {}, aprobado: false, hash: null, revision: null, errores: [] });
    if (u.includes('/api/products')) return json({ ok: true, flujo, disponible: false, productos: null, cadena_productos: [], minimos_talento: [], entidades: {}, hallazgos: [], errores: [] });
    if (u.includes('/api/components')) return json({ ok: true, flujo, disponible: false, componentes: null, cadena: {}, entidades: {}, hallazgos: [], errores: [] });
    if (u.includes('/api/budget')) return json({ ok: true, flujo, disponible: false, presupuesto: null, resumen: null, proyeccion: null, cadena_meses: [], hitos: [], hallazgos: [], errores: [] });
    if (u.includes('/api/alliance')) return json({ ok: true, flujo, disponible: false, alianza: null, territorio: null, hallazgos: [], puntaje: [], errores: [] });
    if (u.includes('/api/value-chain')) return json({ ok: true, flujo, disponible: false, cadena: null, hallazgos: [], errores: [] });
    if (u.includes('/api/style-sgr')) return json({ ok: true, flujo, disponible: false, por_seccion: {}, errores: [] });
    if (u.includes('/api/status')) return json(status(flujo));
    return json({}, 503);
  };
  await viewer.viewer('loadStatusNow');
  await flush();
  return viewer;
}

async function loaded(t, opts) {
  const viewer = await harness(t, opts);
  await viewer.viewer('loadAnnex2');
  await flush();
  return viewer;
}

function tabLabels(doc) {
  return Array.from(doc.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
}

function chapter(doc, numero) {
  return doc.querySelector(`#a2Capitulos [data-numero="${numero}"]`);
}

function section(doc, stem) {
  return doc.querySelector(`#a2Capitulos tr[data-stem="${stem}"]`);
}

test('SGR: la pestaña «Anexo 2» aparece justo después de «Requisitos y anexos»', async (t) => {
  const viewer = await harness(t);
  const labels = tabLabels(viewer.document);
  const i = labels.indexOf('Anexo 2');
  assert.ok(i > 0, 'la pestaña existe en SGR');
  assert.equal(labels[i - 1], 'Requisitos y anexos');
  assert.equal(labels[i + 1], 'Secciones');
  viewer.viewer('navigateTab', 'anexo2');
  await flush();
  const active = viewer.document.querySelectorAll('.tab-nav__btn.active');
  assert.equal(active.length, 1);
  assert.equal(active[0].textContent.trim(), 'Anexo 2');
  assert.ok(viewer.document.getElementById('pane-anexo2').classList.contains('active'));
});

test('base: la lista de pestañas sigue igual y la ruta directa avisa que es solo SGR', async (t) => {
  const calls = [];
  const viewer = await harness(t, { flujo: 'base', calls });
  assert.deepEqual(tabLabels(viewer.document), BASE_TABS);
  assert.equal(calls.filter(c => c.url.includes('/api/anexo2')).length, 0, 'sin la pestaña no se pide la vista');
  viewer.viewer('navigateTab', 'anexo2');
  await viewer.viewer('loadAnnex2');
  await flush();
  const content = viewer.document.getElementById('a2Content');
  assert.match(content.textContent, /solo en el flujo SGR/);
  assert.equal(content.querySelector('#a2Capitulos'), null);
});

test('la vista solo lee: abrir la pestaña nunca envía un POST', async (t) => {
  const calls = [];
  const viewer = await harness(t, { calls });
  viewer.viewer('navigateTab', 'anexo2');
  await flush();
  const own = calls.filter(c => c.url.includes('/api/anexo2'));
  assert.ok(own.length >= 1);
  assert.ok(own.every(c => c.method === 'GET'));
  assert.ok(chapter(viewer.document, 3));
});

test('el resumen cuenta los capítulos por estado', async (t) => {
  const viewer = await loaded(t);
  const box = viewer.document.getElementById('a2Resumen');
  const count = estado => box.querySelector(`[data-estado="${estado}"]`).getAttribute('data-n');
  assert.equal(count('falta'), '0');
  assert.equal(count('incompleto'), '1');
  assert.equal(count('desactualizado'), '0');
  assert.equal(count('listo'), '1');
  assert.match(box.textContent, /2 capítulos/);
  assert.match(box.textContent, /720 palabras/);
  for (const label of ['Falta', 'Incompleto', 'Desactualizado', 'Listo']) assert.ok(box.textContent.includes(label), `falta ${label}`);
});

test('cada capítulo muestra número, título, estado y palabras', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  assert.equal(doc.querySelectorAll('#a2Capitulos [data-numero]').length, 2);
  const c3 = chapter(doc, 3);
  assert.equal(c3.getAttribute('data-estado'), 'incompleto');
  for (const text of ['3.', 'Planteamiento del problema', 'Incompleto', '640 palabras']) assert.ok(c3.textContent.includes(text), `falta ${text}`);
  assert.ok(c3.querySelector('.a2-chapter__head .badge--warn'));
  const c21 = chapter(doc, 21);
  assert.match(c21.querySelector('.a2-chapter__head').textContent, /Listo/);
  assert.ok(c21.querySelector('.a2-chapter__head .badge--ok'));
});

test('las secciones muestran estado, palabras, hallazgos por severidad y la clave de la guía', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const s = section(doc, '03_descripcion_problema');
  assert.match(s.textContent, /Redactado/);
  assert.match(s.textContent, /640/);
  assert.match(s.textContent, /§3/);
  assert.equal(s.querySelector('[data-severidad="error"]').textContent.trim(), '1');
  assert.equal(s.querySelector('[data-severidad="warning"]').textContent.trim(), '2');
  assert.equal(s.querySelector('[data-severidad="info"]'), null, 'una severidad en cero no se pinta');
  assert.match(section(doc, '03b_arbol_problemas').textContent, /Falta/);
  const gen = section(doc, '21_cronograma');
  assert.match(gen.textContent, /Generado/);
  assert.match(gen.textContent, /A21/);
  assert.match(gen.textContent, /scripts\/cronograma\.py/);
});

test('la regla se despliega con propósito, estructura, extensión, aperturas, evitar y fuente; sin regla se dice', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const c3 = chapter(doc, 3);
  assert.equal(c3.querySelector('.a2-rule'), null, 'la regla empieza plegada');
  c3.querySelector('[data-regla-btn]').click();
  await flush();
  const rule = chapter(doc, 3).querySelector('.a2-rule');
  assert.ok(rule, 'la regla se despliega');
  for (const text of ['Propósito', 'Estructura', 'Extensión', 'Aperturas favorecidas', 'Evitar', 'Fuente',
    'Antecedentes, magnitud y causas.', 'Entre 600 y 900 palabras.', 'Según el DANE', 'Aperturas cósmicas', 'Guía MGA, capítulo 3']) {
    assert.ok(rule.textContent.includes(text), `falta ${text}`);
  }
  chapter(doc, 3).querySelector('[data-regla-btn]').click();
  await flush();
  assert.equal(chapter(doc, 3).querySelector('.a2-rule'), null, 'la regla se vuelve a plegar');
  const c21 = chapter(doc, 21);
  assert.match(c21.textContent, /Sin regla/);
  assert.equal(c21.querySelector('[data-regla-btn]'), null);
});

test('el léxico y los criterios de la rúbrica se muestran por capítulo', async (t) => {
  const viewer = await loaded(t);
  const c3 = chapter(viewer.document, 3);
  const lex = c3.querySelector('.a2-lexicon');
  assert.match(lex.textContent, /4 favorecidas/);
  assert.match(lex.textContent, /2 desaconsejadas/);
  assert.match(lex.textContent, /1 prohibida/);
  const chips = Array.from(c3.querySelectorAll('.a2-chip')).map(c => c.textContent.trim());
  assert.deepEqual(chips, ['2.1 Pertinencia (10)', '2.3 Coherencia <i>técnica</i> (5)']);
  assert.match(chapter(viewer.document, 21).textContent, /Ningún criterio de la rúbrica/);
});

test('sin rúbrica detectada se dice en vez de listar criterios', async (t) => {
  const viewer = await loaded(t, { body: annex2({ vista: vista({ rubrica: null }) }) });
  assert.match(chapter(viewer.document, 21).textContent, /Sin rúbrica detectada/);
});

test('los hallazgos del capítulo se listan con severidad, código y sección', async (t) => {
  const viewer = await loaded(t);
  const box = chapter(viewer.document, 3).querySelector('.a2-findings');
  const items = box.querySelectorAll('li');
  assert.equal(items.length, 2);
  assert.equal(items[0].getAttribute('data-severidad'), 'error');
  assert.match(items[0].textContent, /Cifra sin fuente/);
  assert.match(items[0].textContent, /sgr-cifra-sin-fuente/);
  assert.match(items[0].textContent, /03_descripcion_problema/);
  assert.equal(chapter(viewer.document, 21).querySelector('.a2-findings li'), null);
});

test('«Solo pendientes» oculta los capítulos listos', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const filter = doc.getElementById('a2SoloPendientes');
  assert.equal(filter.checked, false);
  filter.checked = true;
  filter.dispatchEvent(new viewer.window.Event('change', { bubbles: true }));
  await flush();
  assert.ok(chapter(doc, 3));
  assert.equal(chapter(doc, 21), null);
  assert.equal(doc.getElementById('a2SoloPendientes').checked, true);
  const again = doc.getElementById('a2SoloPendientes');
  again.checked = false;
  again.dispatchEvent(new viewer.window.Event('change', { bubbles: true }));
  await flush();
  assert.ok(chapter(doc, 21));
});

test('abrir una sección usa el panel de secciones existente', async (t) => {
  const viewer = await loaded(t);
  viewer.window.eval('window.__opened = []; openSectionStructure = (id) => { window.__opened.push(id); };');
  section(viewer.document, '03_descripcion_problema').querySelector('[data-open-stem]').click();
  await flush();
  assert.deepEqual(Array.from(viewer.window.__opened), ['03_descripcion_problema']);
  assert.ok(viewer.document.getElementById('pane-sections').classList.contains('active'));
});

test('un error del script se muestra en la pestaña', async (t) => {
  const viewer = await loaded(t, { body: annex2({ disponible: false, vista: null, error: 'anexo2_sgr.py no pudo calcular la vista: <b>roto</b>' }) });
  const content = viewer.document.getElementById('a2Content');
  assert.match(content.textContent, /anexo2_sgr\.py no pudo calcular la vista: <b>roto<\/b>/);
  assert.equal(content.querySelector('b'), null);
  assert.equal(content.querySelector('#a2Capitulos'), null);
});

test('el texto de la vista se escapa: no se inserta HTML', async (t) => {
  const viewer = await loaded(t);
  const c3 = chapter(viewer.document, 3);
  c3.querySelector('[data-regla-btn]').click();
  await flush();
  const content = viewer.document.getElementById('a2Content');
  assert.equal(content.querySelector('b'), null);
  assert.equal(content.querySelector('i'), null);
  assert.match(content.textContent, /Mostrar el <b>problema<\/b>/);
});
