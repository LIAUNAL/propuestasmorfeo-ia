/**
 * Pestaña «Convocatorias» (odd/tasks/convocatorias-explorador.md, S6).
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/status` y
 * `/api/convocatorias` se sustituyen por dobles con la forma del contrato
 * `morfeo.convocatorias-vista/v1`. La pestaña existe en ambos flujos, justo
 * después de «Flujo general», es de solo lectura y sus botones solo piden el
 * prompt al servidor y lo entregan a la terminal. Las tarjetas viven en la
 * vista «Lista» del selector de vistas (odd/tasks/convocatorias-mapa.md, S4).
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

function call(overrides = {}) {
  return {
    id: 'minciencias-ia-2026', titulo: 'Convocatoria de IA para regiones', financiador: 'Minciencias', programa: 'Ciencia para la vida',
    url: 'https://minciencias.gov.co/convocatorias/ia-2026', fuente: 'minciencias', ambito: 'colombia', idioma: 'es',
    aplicantes: ['investigador', 'grupo'], rol_colombia: 'lider', rol_agente: 'lider', regla: null, aviso: null,
    estado: 'abierta', apertura: '2026-10-01', cierre: '2026-12-05', cierre_tipo: 'fijo', dias_restantes: 15, vigente: true,
    monto: { min: null, max: 500000000, moneda: 'COP' }, temas: ['IA'], resumen: 'Financia proyectos de IA aplicada en regiones.',
    elegibilidad: null, puntaje_agente: 80, lexico: 60, puntaje: 70,
    evidencia: [{ texto: 'Dirigida a grupos reconocidos', url: 'https://minciencias.gov.co/tdr.pdf' }], encontrada: '2026-11-20',
    ...overrides,
  };
}

const CALLS = [
  call(),
  call({
    id: 'horizon-cl4-2026', titulo: 'Horizon Europe Cluster 4', financiador: 'Comisión Europea', programa: 'Horizon Europe',
    url: 'https://ec.europa.eu/info/funding-tenders/cl4', ambito: 'internacional', idioma: 'en', aplicantes: ['universidad', 'empresa'],
    rol_colombia: 'socio', regla: { id: 'horizon-europe', aviso: 'Participa como socio financiado; no cuenta para el mínimo de tres países.' },
    aviso: 'Participa como socio financiado; no cuenta para el mínimo de tres países.', dias_restantes: 0, monto: { min: 1000000, max: 3000000, moneda: 'EUR' },
    puntaje: 55, evidencia: [],
  }),
  call({
    id: 'wellcome-discovery', titulo: 'Wellcome Discovery Award', financiador: 'Wellcome', programa: null, url: 'https://wellcome.org/discovery',
    ambito: 'internacional', idioma: 'en', aplicantes: ['investigador'], rol_colombia: 'coaplicante', aviso: null,
    estado: 'abierta', cierre: null, cierre_tipo: 'continuo', dias_restantes: null, monto: null, puntaje: 50,
  }),
  call({
    id: 'cyted-redes-2025', titulo: 'CYTED Redes temáticas', financiador: 'CYTED', programa: 'Redes', url: 'https://cyted.org/redes',
    ambito: 'latam', idioma: 'es', aplicantes: ['grupo', 'centro'], rol_colombia: 'socio', estado: 'cerrada', cierre: '2026-03-01',
    dias_restantes: -264, vigente: false, puntaje: 40,
  }),
  call({
    id: 'msca-global', titulo: 'MSCA Global Postdoctoral', financiador: 'Comisión Europea', programa: 'MSCA', url: 'https://marie-sklodowska-curie-actions.ec.europa.eu/',
    ambito: 'internacional', idioma: 'en', aplicantes: ['investigador'], rol_colombia: 'no_elegible', aviso: null, dias_restantes: 1, puntaje: 30,
  }),
  call({
    id: 'erc-starting', titulo: 'ERC Starting Grant', financiador: 'ERC', programa: null, url: 'https://erc.europa.eu/starting',
    ambito: 'internacional', idioma: 'en', aplicantes: ['investigador'], rol_colombia: 'anfitrion_exterior', aviso: null, dias_restantes: 40, puntaje: 25,
  }),
  call({
    id: 'fondo-x', titulo: 'Fondo X', financiador: 'Fundación X', programa: null, url: 'https://example.org/x', ambito: 'latam', idioma: 'pt',
    aplicantes: ['estudiante'], rol_colombia: 'desconocido', aviso: null, dias_restantes: 20, puntaje: 20,
  }),
];

const FUENTES = [
  { fuente: 'Minciencias', url: 'https://minciencias.gov.co/convocatorias', fecha: '2026-11-20', resultado: 'ok', n: 1 },
  { fuente: 'IDB Lab', url: 'https://bidlab.org', fecha: '2026-11-20', resultado: 'bloqueado', n: 0 },
];

function vista(overrides = {}) {
  return {
    schema: 'morfeo.convocatorias-vista/v1', hoy: '2026-11-20', workspace: '/tmp/ws',
    perfil: { existe: true, aplicantes: ['investigador'], idiomas: ['es', 'en'], ambitos: ['colombia', 'latam', 'internacional'], n_palabras_clave: 6 },
    resumen: {
      total: 7, vigentes: 6, por_ambito: { colombia: 1, latam: 2, internacional: 4 },
      por_rol: { lider: 1, socio: 2, coaplicante: 1, anfitrion_exterior: 1, no_elegible: 1, desconocido: 1 },
      por_idioma: { es: 2, en: 4, pt: 1 },
    },
    fuentes_consultadas: FUENTES, oportunidades: CALLS, hallazgos: [], ...overrides,
  };
}

function payload(overrides = {}) {
  return { ok: true, disponible: true, vista: vista(), error: null, ...overrides };
}

function status(flujo) {
  return {
    flujo, active_run: null, all_runs: [], totals: { total_words: 0 },
    sections: [], gates: [], telemetria: [], pipeline_units: [], artifacts: [],
  };
}

function json(body, code = 200) {
  return { ok: code < 400, status: code, json: async () => body, text: async () => JSON.stringify(body) };
}

async function harness(t, { flujo = 'base', body = payload(), calls = [] } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    calls.push({ url: u, method: (init && init.method) || 'GET', body: init && init.body });
    if (u.includes('/api/convocatorias/buscar')) return json({ ok: true, prompt: '/propuesta-convocatorias' });
    if (u.includes('/api/convocatorias/iniciar')) {
      const { id } = JSON.parse(init.body);
      return json({ ok: true, prompt: `/propuesta-convocatorias iniciar ${id}` });
    }
    if (u.includes('/api/convocatorias')) return json(body);
    if (u.includes('/api/status')) return json(status(flujo));
    return json({}, 503);
  };
  viewer.window.eval('window.__prompts = []; sendTerminalPrompt = (cmd) => { window.__prompts.push(cmd); return Promise.resolve(true); };');
  await viewer.viewer('loadStatusNow');
  await flush();
  return viewer;
}

async function loaded(t, opts) {
  const viewer = await harness(t, opts);
  viewer.viewer('setOpportunityView', 'lista');
  await viewer.viewer('loadOpportunities');
  await flush();
  return viewer;
}

const tabLabels = doc => Array.from(doc.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
const card = (doc, id) => doc.querySelector(`#cvLista [data-id="${id}"]`);
const cardIds = doc => Array.from(doc.querySelectorAll('#cvLista [data-id]')).map(c => c.getAttribute('data-id'));

function change(viewer, id, value) {
  const el = viewer.document.getElementById(id);
  if (el.type === 'checkbox') el.checked = value;
  else el.value = value;
  el.dispatchEvent(new viewer.window.Event('change', { bubbles: true }));
}

for (const flujo of ['base', 'sgr']) {
  test(`${flujo}: la pestaña «Convocatorias» aparece justo después de «Flujo general»`, async (t) => {
    const viewer = await harness(t, { flujo });
    const labels = tabLabels(viewer.document);
    const i = labels.indexOf('Convocatorias');
    assert.equal(labels[i - 1], 'Flujo general');
    assert.equal(labels[i + 1], 'Pipeline y Avance');
    const btn = Array.from(viewer.document.querySelectorAll('.tab-nav__btn')).find(b => b.textContent.trim() === 'Convocatorias');
    assert.equal(btn.hidden, false, 'visible en ambos flujos');
    viewer.viewer('navigateTab', 'convocatorias');
    await flush();
    const active = viewer.document.querySelectorAll('.tab-nav__btn.active');
    assert.equal(active.length, 1);
    assert.equal(active[0].textContent.trim(), 'Convocatorias');
    assert.ok(viewer.document.getElementById('pane-convocatorias').classList.contains('active'));
  });
}

test('abrir la pestaña lee la vista con GET y nunca escribe', async (t) => {
  const calls = [];
  const viewer = await harness(t, { calls });
  viewer.viewer('setOpportunityView', 'lista');
  viewer.viewer('navigateTab', 'convocatorias');
  await flush();
  const own = calls.filter(c => c.url.includes('/api/convocatorias'));
  assert.ok(own.length >= 1);
  assert.ok(own.every(c => c.method === 'GET'));
  assert.ok(card(viewer.document, 'minciencias-ia-2026'));
});

test('el resumen cuenta vigentes, convocatorias por ámbito y por rol', async (t) => {
  const viewer = await loaded(t);
  const box = viewer.document.getElementById('cvResumen');
  assert.match(box.textContent, /7 convocatorias/);
  assert.match(box.textContent, /6 vigentes/);
  assert.equal(box.querySelector('[data-ambito="colombia"]').getAttribute('data-n'), '1');
  assert.equal(box.querySelector('[data-ambito="latam"]').getAttribute('data-n'), '2');
  assert.equal(box.querySelector('[data-ambito="internacional"]').getAttribute('data-n'), '4');
  assert.equal(box.querySelector('[data-rol="socio"]').getAttribute('data-n'), '2');
  assert.equal(box.querySelector('[data-rol="no_elegible"]').getAttribute('data-n'), '1');
});

test('cada tarjeta muestra título enlazado, financiador, ámbito, idioma, monto, puntaje, resumen y evidencia', async (t) => {
  const viewer = await loaded(t);
  const c = card(viewer.document, 'minciencias-ia-2026');
  const link = c.querySelector('a.cv-card__title');
  assert.equal(link.getAttribute('href'), 'https://minciencias.gov.co/convocatorias/ia-2026');
  assert.equal(link.getAttribute('target'), '_blank');
  assert.match(link.getAttribute('rel'), /noopener/);
  assert.equal(link.textContent.trim(), 'Convocatoria de IA para regiones');
  for (const text of ['Minciencias', 'Ciencia para la vida', 'Colombia', 'Español', '500.000.000 COP', '70', 'Financia proyectos de IA aplicada en regiones.']) {
    assert.ok(c.textContent.includes(text), `falta ${text}`);
  }
  const ev = c.querySelector('.cv-evidencia a');
  assert.equal(ev.getAttribute('href'), 'https://minciencias.gov.co/tdr.pdf');
  assert.match(ev.textContent, /Dirigida a grupos reconocidos/);
  assert.match(card(viewer.document, 'horizon-cl4-2026').textContent, /1\.000\.000 – 3\.000\.000 EUR/);
  assert.match(card(viewer.document, 'wellcome-discovery').textContent, /Monto no indicado/);
});

test('la cuenta regresiva distingue días, hoy, uno, cerrada y sin fecha', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const countdown = id => card(doc, id).querySelector('.cv-cuenta').textContent.trim();
  assert.equal(countdown('minciencias-ia-2026'), 'Cierra en 15 días');
  assert.equal(countdown('horizon-cl4-2026'), 'Cierra hoy');
  assert.equal(countdown('msca-global'), 'Cierra en 1 día');
  assert.equal(countdown('cyted-redes-2025'), 'Cerrada');
  assert.equal(countdown('wellcome-discovery'), 'Sin fecha');
});

test('los avisos de rol usan el aviso de la regla o una etiqueta por rol', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  const rol = id => card(doc, id).querySelector('.cv-rol');
  assert.equal(rol('horizon-cl4-2026').getAttribute('data-rol'), 'socio');
  assert.match(card(doc, 'horizon-cl4-2026').textContent, /no cuenta para el mínimo de tres países/);
  assert.match(rol('horizon-cl4-2026').textContent, /Solo como socio/);
  assert.match(rol('wellcome-discovery').textContent, /Solo como coaplicante/);
  assert.match(rol('erc-starting').textContent, /Requiere anfitrión en el exterior/);
  assert.match(rol('msca-global').textContent, /No elegible desde Colombia/);
  assert.match(rol('fondo-x').textContent, /Rol por confirmar/);
  assert.match(rol('minciencias-ia-2026').textContent, /Puede liderar/);
});

test('los filtros por ámbito, idioma, tipo de aplicante y «Solo vigentes» acotan las tarjetas', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  assert.equal(cardIds(doc).length, 7);
  change(viewer, 'cvAmbito', 'latam');
  await flush();
  assert.deepEqual(cardIds(doc).sort(), ['cyted-redes-2025', 'fondo-x']);
  assert.equal(doc.getElementById('cvAmbito').value, 'latam', 'el filtro sobrevive al repintado');
  change(viewer, 'cvSoloVigentes', true);
  await flush();
  assert.deepEqual(cardIds(doc), ['fondo-x']);
  change(viewer, 'cvAmbito', '');
  change(viewer, 'cvSoloVigentes', false);
  change(viewer, 'cvIdioma', 'en');
  await flush();
  assert.deepEqual(cardIds(doc).sort(), ['erc-starting', 'horizon-cl4-2026', 'msca-global', 'wellcome-discovery']);
  change(viewer, 'cvIdioma', '');
  change(viewer, 'cvAplicante', 'empresa');
  await flush();
  assert.deepEqual(cardIds(doc), ['horizon-cl4-2026']);
  change(viewer, 'cvAplicante', 'centro');
  change(viewer, 'cvIdioma', 'en');
  await flush();
  assert.deepEqual(cardIds(doc), []);
  assert.match(doc.getElementById('cvLista').textContent, /Ninguna convocatoria cumple los filtros/);
});

test('las fuentes consultadas se listan con su resultado', async (t) => {
  const viewer = await loaded(t);
  const items = viewer.document.querySelectorAll('#cvFuentes li');
  assert.equal(items.length, 2);
  assert.equal(items[0].getAttribute('data-resultado'), 'ok');
  assert.match(items[0].textContent, /Minciencias/);
  assert.equal(items[1].getAttribute('data-resultado'), 'bloqueado');
  assert.match(items[1].textContent, /Bloqueada/);
});

test('sin convocatorias se explica cómo correr la búsqueda', async (t) => {
  const empty = vista({
    oportunidades: [], fuentes_consultadas: [],
    resumen: { total: 0, vigentes: 0, por_ambito: { colombia: 0, latam: 0, internacional: 0 }, por_rol: {}, por_idioma: {} },
    hallazgos: [{ severidad: 'info', codigo: 'sin-oportunidades', mensaje: 'No hay oportunidades.json', id: null }],
  });
  const viewer = await loaded(t, { body: payload({ vista: empty }) });
  const content = viewer.document.getElementById('cvContent');
  assert.match(content.textContent, /Todavía no hay convocatorias/);
  assert.match(content.textContent, /Buscar para el proyecto/);
  assert.equal(content.querySelector('#cvLista [data-id]'), null);
});

test('un script ausente o roto se muestra como error sin insertar HTML', async (t) => {
  const viewer = await loaded(t, { body: payload({ disponible: false, vista: null, error: 'convocatorias.py no pudo calcular la vista: <b>roto</b>' }) });
  const content = viewer.document.getElementById('cvContent');
  assert.match(content.textContent, /convocatorias\.py no pudo calcular la vista: <b>roto<\/b>/);
  assert.equal(content.querySelector('b'), null);
  assert.match(content.textContent, /Buscar para el proyecto/);
});

test('«Buscar para el proyecto» pide el prompt al servidor y lo entrega a la terminal', async (t) => {
  const calls = [];
  const viewer = await loaded(t, { calls });
  viewer.document.getElementById('cvSearchBtn').click();
  await flush();
  const post = calls.find(c => c.url.includes('/api/convocatorias/buscar'));
  assert.equal(post.method, 'POST');
  assert.deepEqual(Array.from(viewer.window.__prompts), ['/propuesta-convocatorias']);
});

test('«Iniciar propuesta con esta» envía el id de la tarjeta y entrega el prompt devuelto', async (t) => {
  const calls = [];
  const viewer = await loaded(t, { calls });
  card(viewer.document, 'horizon-cl4-2026').querySelector('[data-iniciar]').click();
  await flush();
  const post = calls.find(c => c.url.includes('/api/convocatorias/iniciar'));
  assert.equal(post.method, 'POST');
  assert.deepEqual(JSON.parse(post.body), { id: 'horizon-cl4-2026' });
  assert.deepEqual(Array.from(viewer.window.__prompts), ['/propuesta-convocatorias iniciar horizon-cl4-2026']);
});

test('el texto de la vista se escapa y los enlaces que no son http(s) no se pintan', async (t) => {
  const evil = call({
    id: 'evil', titulo: '<img src=x onerror="window.__pwned=1"><b>Malicioso</b>', financiador: '<i>F</i>',
    url: 'javascript:alert(1)', resumen: '<script>window.__pwned=1</script>',
    evidencia: [{ texto: '<b>cita</b>', url: 'javascript:alert(2)' }],
  });
  const viewer = await loaded(t, { body: payload({ vista: vista({ oportunidades: [evil] }) }) });
  const c = card(viewer.document, 'evil');
  assert.equal(c.querySelector('img'), null);
  assert.equal(c.querySelector('b'), null);
  assert.equal(c.querySelector('i'), null);
  assert.equal(c.querySelector('script'), null);
  assert.match(c.textContent, /<b>Malicioso<\/b>/);
  assert.equal(c.querySelector('a[href^="javascript"]'), null);
  assert.equal(viewer.window.__pwned, undefined);
});

// National coverage (odd/tasks/convocatorias-nacional.md, S1): the level of a
// Colombian call is a chip on its card and a filter of the panel; the summary
// names the mandatory sources the search did not consult.
const LEVEL_CALLS = [
  call({ nivel: 'nacional' }),
  call({ id: 'ruta-n-reto', titulo: 'Reto de innovación abierta', financiador: 'Ruta N', url: 'https://rutanmedellin.org/ofertas/reto', nivel: 'local' }),
  CALLS[1],
];
const COVERAGE = {
  requerida: true, completa: false, desconocidas: [],
  obligatorias: [],
  faltantes: [{ id: 'atenea', nombre: 'Agencia Atenea (Bogotá): convocatorias', url: 'https://agenciaatenea.gov.co/convocatorias', nivel: 'regional' }],
  descuadres: [{ fuente: 'innpulsa', n: 4, registradas: 0 }],
};
const levelView = (overrides = {}) => vista({ oportunidades: LEVEL_CALLS, cobertura: COVERAGE, ...overrides });

test('el nivel de una convocatoria de Colombia es una etiqueta de su tarjeta y un filtro', async (t) => {
  const viewer = await loaded(t, { body: payload({ vista: levelView() }) });
  const doc = viewer.document;
  const chip = card(doc, 'minciencias-ia-2026').querySelector('.cv-nivel');
  assert.equal(chip.textContent.trim(), 'Nacional');
  assert.equal(chip.getAttribute('data-nivel'), 'nacional');
  assert.equal(card(doc, 'ruta-n-reto').querySelector('.cv-nivel').textContent.trim(), 'Local');
  assert.equal(card(doc, 'horizon-cl4-2026').querySelector('.cv-nivel'), null, 'sin nivel no hay etiqueta');
  assert.match(doc.getElementById('cvFiltros').textContent, /Nivel/);
  change(viewer, 'cvNivel', 'local');
  await flush();
  assert.deepEqual(cardIds(doc), ['ruta-n-reto']);
  assert.equal(doc.getElementById('cvNivel').value, 'local', 'el filtro sobrevive al repintado');
  change(viewer, 'cvNivel', '');
  await flush();
  assert.equal(cardIds(doc).length, 3);
});

test('sin niveles ni cobertura en la vista no aparecen etiqueta, filtro ni aviso nuevos', async (t) => {
  const viewer = await loaded(t);
  const doc = viewer.document;
  assert.equal(doc.querySelector('.cv-nivel'), null);
  assert.equal(doc.getElementById('cvNivel'), null);
  assert.equal(doc.getElementById('cvCobertura'), null);
});

test('el resumen avisa las fuentes obligatorias sin consultar y los conteos que no cuadran', async (t) => {
  const viewer = await loaded(t, { body: payload({ vista: levelView() }) });
  const box = viewer.document.getElementById('cvCobertura');
  assert.ok(box, 'aviso de cobertura');
  assert.equal(box.getAttribute('data-faltantes'), '1');
  assert.equal(box.getAttribute('data-descuadres'), '1');
  assert.match(box.textContent, /Cobertura nacional incompleta/);
  assert.match(box.textContent, /Fuentes obligatorias sin consultar \(1\)/);
  assert.equal(box.querySelector('a').getAttribute('href'), 'https://agenciaatenea.gov.co/convocatorias');
  assert.match(box.textContent, /Agencia Atenea/);
  assert.match(box.textContent, /innpulsa/);
  const done = { ...COVERAGE, faltantes: [], descuadres: [], completa: true };
  const complete = await loaded(t, { body: payload({ vista: levelView({ cobertura: done }) }) });
  assert.equal(complete.document.getElementById('cvCobertura'), null);
});

test('sin convocatorias el aviso de cobertura sigue visible', async (t) => {
  const empty = levelView({ oportunidades: [], resumen: { total: 0, vigentes: 0, por_ambito: {}, por_rol: {}, por_idioma: {} } });
  const viewer = await loaded(t, { body: payload({ vista: empty }) });
  assert.match(viewer.document.getElementById('cvCobertura').textContent, /Agencia Atenea/);
});

test('las fuentes que piden sesión se listan como tales', async (t) => {
  const fuentes = [...FUENTES, { fuente: 'hermes', url: 'http://www.hermes.unal.edu.co/', fecha: '2026-11-20', resultado: 'requiere_sesion', n: 0 }];
  const viewer = await loaded(t, { body: payload({ vista: vista({ fuentes_consultadas: fuentes }) }) });
  const item = viewer.document.querySelector('#cvFuentes li[data-resultado="requiere_sesion"]');
  assert.match(item.textContent, /Requiere sesión/);
});

test('en inglés el nivel, su filtro y el aviso de cobertura cambian de idioma', async (t) => {
  const viewer = await loaded(t, { body: payload({ vista: levelView() }) });
  viewer.window.i18n.setLanguage('en');
  await flush();
  const doc = viewer.document;
  assert.equal(card(doc, 'minciencias-ia-2026').querySelector('.cv-nivel').textContent.trim(), 'National');
  assert.match(doc.getElementById('cvFiltros').textContent, /Level/);
  assert.match(doc.getElementById('cvNivel').textContent, /All levels/);
  const box = doc.getElementById('cvCobertura');
  assert.match(box.textContent, /National coverage incomplete/);
  assert.match(box.textContent, /Mandatory sources not checked \(1\)/);
  viewer.window.i18n.setLanguage('es');
  await flush();
  assert.equal(card(doc, 'minciencias-ia-2026').querySelector('.cv-nivel').textContent.trim(), 'Nacional');
});
