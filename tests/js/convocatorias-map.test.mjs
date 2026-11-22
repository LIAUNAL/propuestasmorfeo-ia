/**
 * «Convocatorias» views: opportunity tree, affinity constellation, side by
 * side, requirements matrix, timeline and the detail panel
 * (odd/tasks/convocatorias-mapa.md, S1 and S4). The constellation became the
 * SOTA 3D viewer in a frame (odd/tasks/tablero-juez-novedad.md, S7): here it is
 * only checked to open; its page and its frame are pinned in
 * convocatorias-atlas.test.mjs.
 *
 * The real dashboard runs under jsdom with static/convocatorias-map.js inlined
 * by the harness; `/api/status` and `/api/convocatorias` are doubles shaped
 * like `morfeo.convocatorias-vista/v1` with the S3 keys (match, componentes,
 * temas_match, experiencia, historial, alertas, preparar_desde, titulo_corto,
 * mapa, perfiles, alcance). jsdom has no layout, so geometry is not asserted:
 * the tests pin what each view draws, the interactions and the escaping.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

function call(overrides = {}) {
  return {
    id: 'sgr-salud', titulo: 'Convocatoria SGR CTeI · Salud y bienestar regional', titulo_corto: 'SGR Salud regional',
    financiador: 'Minciencias', programa: 'Asignación CTeI', url: 'https://minciencias.gov.co/sgr', fuente: 'minciencias',
    ambito: 'colombia', idioma: 'es', aplicantes: ['universidad', 'grupo'], rol_colombia: 'lider', regla: null, aviso: null,
    estado: 'abierta', apertura: '2026-10-23', cierre: '2026-12-11', cierre_tipo: 'fijo', dias_restantes: 21, vigente: true,
    monto: { min: null, max: 4500000000, moneda: 'COP' }, temas: ['salud'], resumen: 'Financia proyectos de CTeI en salud.',
    puntaje: 70, evidencia: [{ texto: 'Términos de referencia', url: 'https://minciencias.gov.co/tdr.pdf' }],
    match: 78, componentes: { tematica: 80, experiencia: 85, elegibilidad: 100, tiempo: 31 },
    temas_match: [{ tema: 'salud mental', peso: 1 }, { tema: 'eeg', peso: 0.5 }],
    experiencia: ['lia-eeg', 'lia-salud'], historial: true, esfuerzo: 'alto', preparar_desde: '2026-09-12',
    alertas: [
      { severidad: 'error', texto: 'Cierra en 21 días y el esfuerzo estimado es alto (unos 90 días)' },
      { severidad: 'warning', texto: 'Contrapartida mínima del 20 %' },
    ],
    requisitos: [
      { tipo: 'contrapartida', estado: 'por_verificar', texto: 'Contrapartida mínima del 20 %' },
      { tipo: 'idioma', estado: 'cumple', texto: 'Propuesta en español' },
    ],
    ...overrides,
  };
}

const CALLS = [
  call(),
  call({
    id: 'horizon-cl1', titulo: 'Horizon Europe Cluster 1 · Mental health', titulo_corto: 'Horizon CL1 Salud mental',
    financiador: 'Comisión Europea', programa: 'Horizon Europe', ambito: 'internacional', idioma: 'en', rol_colombia: 'socio',
    aviso: 'Participa como socio financiado; no cuenta para el mínimo de tres países.', dias_restantes: 146, cierre: '2027-04-15',
    match: 64, componentes: { tematica: 70, experiencia: 30, elegibilidad: 70, tiempo: 100 },
    temas_match: [{ tema: 'salud mental', peso: 1 }], experiencia: ['lia-dl'], historial: false, preparar_desde: '2027-01-15',
    alertas: [{ severidad: 'warning', texto: 'Mínimo 3 entidades de 3 países' }],
    requisitos: [{ tipo: 'consorcio', estado: 'por_verificar', texto: 'Mínimo 3 entidades de 3 países' }],
  }),
  call({
    id: 'cyted-redes', titulo: 'CYTED Redes temáticas 2027', titulo_corto: 'CYTED Redes', financiador: 'CYTED', ambito: 'latam',
    rol_colombia: 'lider', dias_restantes: 176, cierre: '2027-05-15', match: 60, esfuerzo: 'bajo', preparar_desde: '2027-04-30',
    temas_match: [{ tema: 'salud mental', peso: 0.5 }], experiencia: [], historial: false, alertas: [],
    requisitos: [{ tipo: 'otro', estado: 'cumple', texto: 'Grupos de seis países' }],
  }),
  call({
    id: 'wellcome-discovery', titulo: 'Wellcome Discovery Awards', titulo_corto: 'Wellcome Discovery', financiador: 'Wellcome',
    ambito: 'internacional', idioma: 'en', rol_colombia: 'coaplicante', dias_restantes: 61, cierre: '2027-01-20', match: 55,
    temas_match: [{ tema: 'salud mental', peso: 1 }], experiencia: [], historial: false, alertas: [], requisitos: [],
    preparar_desde: '2026-12-06',
  }),
  call({
    id: 'fulbright-scholar', titulo: 'Fulbright Visiting Scholar 2027', titulo_corto: 'Fulbright Scholar', financiador: 'Fulbright',
    rol_colombia: 'anfitrion_exterior', dias_restantes: 74, cierre: '2027-02-02', match: 52,
    temas_match: [{ tema: 'salud mental', peso: 0.5 }], experiencia: [], historial: false, alertas: [], requisitos: [],
    preparar_desde: '2026-12-19',
  }),
  call({
    id: 'google-phd', titulo: 'Google PhD Fellowship · América Latina', titulo_corto: 'Google PhD LatAm', financiador: 'Google',
    ambito: 'internacional', idioma: 'en', aplicantes: ['estudiante'], rol_colombia: 'lider', dias_restantes: 146,
    cierre: '2027-04-15', match: 58, esfuerzo: 'bajo', preparar_desde: '2027-03-31',
    temas_match: [{ tema: 'aprendizaje automatico', peso: 1 }], experiencia: ['lia-dl'], historial: false, alertas: [], requisitos: [],
  }),
  call({
    id: 'msca-global', titulo: 'MSCA Global Postdoctoral Fellowships', titulo_corto: 'MSCA Global PF', financiador: 'Comisión Europea',
    ambito: 'internacional', idioma: 'en', rol_colombia: 'no_elegible', dias_restantes: 293, cierre: '2027-09-09', match: 18,
    temas_match: [], experiencia: [], historial: false, preparar_desde: '2027-06-11',
    alertas: [{ severidad: 'error', texto: 'Nacionalidad o residencia larga en la UE' }],
    requisitos: [{ tipo: 'perfil', estado: 'no_cumple', texto: 'Nacionalidad o residencia larga en la UE' }],
  }),
];

const MAPA = {
  temas: [{ tema: 'salud mental', n: 5 }, { tema: 'eeg', n: 1 }, { tema: 'aprendizaje automatico', n: 1 }, { tema: 'educacion', n: 0 }],
  experiencia: [
    { id: 'lia-eeg', nombre: 'Análisis de EEG y neuroimagen', detalle: 'Proyectos con Minciencias', temas: ['eeg', 'salud mental'], financiadores: ['Minciencias'], n: 1 },
    { id: 'lia-salud', nombre: 'Salud digital regional', detalle: null, temas: ['salud mental'], financiadores: ['SGR'], n: 1 },
    { id: 'lia-dl', nombre: 'Aprendizaje profundo e interpretabilidad', detalle: 'Artículos y tesis', temas: ['aprendizaje automatico'], financiadores: [], n: 2 },
  ],
};

function vista(overrides = {}) {
  return {
    schema: 'morfeo.convocatorias-vista/v1', hoy: '2026-11-20', workspace: '/tmp/ws', alcance: 'proyecto',
    perfil: {
      existe: true, alcance: 'proyecto', titulo: 'IA para la detección temprana de depresión con EEG',
      aplicantes: ['investigador'], idiomas: ['es', 'en'], ambitos: ['colombia', 'latam', 'internacional'], n_palabras_clave: 6,
    },
    perfiles: { proyecto: true, banco: false },
    resumen: { total: CALLS.length, vigentes: CALLS.length, por_ambito: {}, por_rol: {}, por_idioma: {} },
    fuentes_consultadas: [], oportunidades: CALLS, mapa: MAPA, hallazgos: [], ...overrides,
  };
}

function payload(overrides = {}) {
  return { ok: true, disponible: true, vista: vista(), error: null, ...overrides };
}

function status() {
  return { flujo: 'base', active_run: null, all_runs: [], totals: { total_words: 0 }, sections: [], gates: [], telemetria: [], pipeline_units: [], artifacts: [] };
}

function json(body, code = 200) {
  return { ok: code < 400, status: code, json: async () => body, text: async () => JSON.stringify(body) };
}

async function loaded(t, { body = payload(), calls = [] } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    calls.push({ url: u, method: (init && init.method) || 'GET', body: init && init.body });
    if (u.includes('/api/convocatorias/buscar')) {
      const { alcance } = JSON.parse(init.body);
      return json({ ok: true, prompt: alcance ? `/propuesta-convocatorias buscar --alcance ${alcance}` : '/propuesta-convocatorias' });
    }
    if (u.includes('/api/convocatorias/iniciar')) return json({ ok: true, prompt: `/propuesta-convocatorias iniciar ${JSON.parse(init.body).id}` });
    if (u.includes('/api/convocatorias')) return json(typeof body === 'function' ? body(u) : body);
    if (u.includes('/api/status')) return json(status());
    return json({}, 503);
  };
  viewer.window.eval('window.__prompts = []; sendTerminalPrompt = (cmd) => { window.__prompts.push(cmd); return Promise.resolve(true); };');
  await viewer.viewer('loadStatusNow');
  await flush();
  viewer.viewer('navigateTab', 'convocatorias');
  await flush();
  return viewer;
}

const $ = (viewer, sel) => viewer.document.querySelector(sel);
const $$ = (viewer, sel) => Array.from(viewer.document.querySelectorAll(sel));

async function showView(viewer, key) {
  $(viewer, `#cvVistas [data-vista="${key}"]`).click();
  await flush();
}

function fire(viewer, el, type) {
  const Ctor = type.startsWith('pointer') && viewer.window.PointerEvent ? viewer.window.PointerEvent : viewer.window.MouseEvent;
  el.dispatchEvent(new Ctor(type, { bubbles: true, cancelable: true, button: 0 }));
}

test('the view switcher opens on the tree and renders each view', async (t) => {
  const viewer = await loaded(t);
  const tabs = $$(viewer, '#cvVistas [data-vista]').map(b => [b.getAttribute('data-vista'), b.textContent.trim()]);
  assert.deepEqual(tabs.map(([k]) => k), ['arbol', 'constelacion', 'lado', 'requisitos', 'tiempo', 'lista']);
  assert.match(tabs[0][1], /Árbol de oportunidades/);
  assert.match(tabs[1][1], /Constelación de afinidad/);
  assert.match(tabs[5][1], /Lista/);
  assert.ok($(viewer, '#cvView .cvm-tree'), 'the tree is the default view');
  assert.ok($(viewer, '#cvVistas [data-vista="arbol"]').classList.contains('is-on'));
  const marks = {
    arbol: ['.cvm-tree'], constelacion: ['iframe.cvm-atlas'], lado: ['.cvm-tree', 'iframe.cvm-atlas'],
    requisitos: ['table.cvm-matrix'], tiempo: ['svg.cvm-timeline'], lista: ['#cvLista'],
  };
  for (const [key, sels] of Object.entries(marks)) {
    await showView(viewer, key);
    for (const sel of sels) assert.ok($(viewer, `#cvView ${sel}`), `${key} draws ${sel}`);
    assert.ok($(viewer, `#cvVistas [data-vista="${key}"]`).classList.contains('is-on'));
    assert.equal($$(viewer, '#cvVistas .is-on').length, 1);
    assert.equal($(viewer, '#cvDetail').hidden, key === 'lista', `${key}: detail panel visibility`);
  }
  assert.equal($$(viewer, '#cvLista [data-id]').length, CALLS.length, 'the list keeps every card');
});

test('hover lights the connected temas and experiencia in the tree without replacing the cards', async (t) => {
  const viewer = await loaded(t);
  await showView(viewer, 'lado');
  const cards = $$(viewer, '#cvView .cvm-card[data-call]');
  const card = id => $(viewer, `#cvView .cvm-card[data-call="${id}"]`);
  fire(viewer, card('sgr-salud'), 'pointerover');
  assert.ok(!card('sgr-salud').classList.contains('is-dim'));
  assert.ok(card('google-phd').classList.contains('is-dim'));
  const theme = tema => $$(viewer, '#cvView .cvm-node--theme').find(el => el.getAttribute('data-theme') === tema);
  assert.ok(theme('salud mental').classList.contains('is-hl'));
  assert.ok(theme('eeg').classList.contains('is-hl'));
  assert.ok(theme('aprendizaje automatico').classList.contains('is-dim'));
  const root = id => $(viewer, `#cvView .cvm-node--root[data-root="${id}"]`);
  assert.ok(root('lia-eeg').classList.contains('is-hl'));
  assert.ok(root('lia-dl').classList.contains('is-dim'));
  // Hovering a root lights its calls.
  fire(viewer, root('lia-dl'), 'pointerover');
  assert.ok(!card('google-phd').classList.contains('is-dim'));
  assert.ok(!card('horizon-cl1').classList.contains('is-dim'));
  assert.ok(card('sgr-salud').classList.contains('is-dim'));
  assert.ok(cards.every((el, i) => el === $$(viewer, '#cvView .cvm-card[data-call]')[i]), 'same card elements');
});

test('the tree groups the fruits by tema, ámbito or rol with «+ N más»', async (t) => {
  const viewer = await loaded(t);
  const heads = () => $$(viewer, '#cvView .cvm-group__head span:first-child').map(s => s.textContent);
  assert.deepEqual(heads().slice(0, 1), ['Salud mental']);
  const salud = $(viewer, '#cvView .cvm-group');
  assert.equal(salud.querySelectorAll('.cvm-card').length, 4);
  const more = salud.querySelector('[data-cvm-expand]');
  assert.equal(more.textContent.trim(), '+ 1 más');
  more.click();
  await flush();
  assert.equal($(viewer, '#cvView .cvm-group').querySelectorAll('.cvm-card').length, 5);
  const scores = Array.from($(viewer, '#cvView .cvm-group').querySelectorAll('.cvm-score')).map(s => Number(s.textContent));
  assert.deepEqual(scores, [...scores].sort((a, b) => b - a), 'fruits sorted by match');
  assert.ok(heads().includes('Sin tema del perfil'));
  // Branches: the profile temas with their share; trunk: the scope; roots: experiencia.
  assert.deepEqual($$(viewer, '#cvView .cvm-node--theme').map(el => el.getAttribute('data-theme')),
    ['salud mental', 'eeg', 'aprendizaje automatico', 'educacion']);
  assert.match($(viewer, '#cvView .cvm-node--trunk').textContent, /IA para la detección temprana de depresión con EEG/);
  assert.match($(viewer, '#cvView .cvm-tree').textContent, /Proyecto en formulación/);
  assert.deepEqual($$(viewer, '#cvView .cvm-node--root strong').map(b => b.textContent),
    ['Análisis de EEG y neuroimagen', 'Salud digital regional', 'Aprendizaje profundo e interpretabilidad']);
  $(viewer, '#cvAgrupar [data-agrupar="ambito"]').click();
  await flush();
  assert.deepEqual(heads().sort(), ['América Latina', 'Colombia', 'Internacional']);
  $(viewer, '#cvAgrupar [data-agrupar="rol"]').click();
  await flush();
  assert.deepEqual(heads().sort(), ['No elegible desde Colombia', 'Puede liderar', 'Requiere anfitrión en el exterior',
    'Solo como coaplicante', 'Solo como socio'].sort());
});

test('the requirements matrix marks each requisito estado', async (t) => {
  const viewer = await loaded(t);
  await showView(viewer, 'requisitos');
  const cols = $$(viewer, '#cvView table.cvm-matrix thead th').map(th => th.textContent);
  for (const label of ['Consorcio', 'Contrapartida', 'Anfitrión', 'Idioma', 'Perfil', 'Aval o categoría', 'Tipo de entidad', 'Otro']) {
    assert.ok(cols.includes(label), label);
  }
  const cell = (id, tipo) => $(viewer, `#cvView tr[data-call="${id}"] td[data-tipo="${tipo}"]`);
  assert.equal(cell('sgr-salud', 'contrapartida').textContent, '⚠');
  assert.equal(cell('sgr-salud', 'contrapartida').getAttribute('title'), 'Contrapartida mínima del 20 %');
  assert.equal(cell('sgr-salud', 'idioma').textContent, '✓');
  assert.equal(cell('sgr-salud', 'consorcio').textContent, '—');
  assert.equal(cell('msca-global', 'perfil').textContent, '✕');
  assert.equal(cell('cyted-redes', 'otro').textContent, '✓');
  $(viewer, '#cvView tr[data-call="msca-global"] td').click();
  await flush();
  assert.equal($(viewer, '#cvDetail h2').textContent, 'MSCA Global Postdoctoral Fellowships');
});

test('the timeline marks a preparation that is already late', async (t) => {
  const viewer = await loaded(t);
  await showView(viewer, 'tiempo');
  const row = id => $(viewer, `#cvView svg.cvm-timeline g.tl-row[data-call="${id}"]`);
  assert.equal(row('sgr-salud').getAttribute('data-late'), '1');
  assert.ok(row('sgr-salud').querySelector('.tl-prep.is-late'));
  assert.match(row('sgr-salud').textContent, /tarde/);
  assert.equal(row('horizon-cl1').getAttribute('data-late'), '0');
  assert.ok(row('horizon-cl1').querySelector('.tl-prep:not(.is-late)'));
  assert.equal($$(viewer, '#cvView svg.cvm-timeline g.tl-row').length, CALLS.length);
});

test('the detail shows the match, the four componentes, alertas, tiempos and «Por qué encaja»', async (t) => {
  const calls = [];
  const viewer = await loaded(t, { calls });
  $(viewer, '#cvView .cvm-card[data-call="sgr-salud"]').click();
  await flush();
  const detail = $(viewer, '#cvDetail');
  assert.equal(detail.querySelector('h2').textContent, 'Convocatoria SGR CTeI · Salud y bienestar regional');
  assert.match(detail.textContent, /Minciencias · Asignación CTeI/);
  assert.equal(detail.querySelector('.cvm-bigscore').textContent.match(/\d+/)[0], '78');
  const comps = Array.from(detail.querySelectorAll('[data-componente]')).map(el => [el.getAttribute('data-componente'), el.getAttribute('data-valor')]);
  assert.deepEqual(comps, [['tematica', '80'], ['experiencia', '85'], ['elegibilidad', '100'], ['tiempo', '31']]);
  const alerts = Array.from(detail.querySelectorAll('.cvm-alerts li')).map(li => li.getAttribute('data-severidad'));
  assert.deepEqual(alerts, ['error', 'warning']);
  assert.match(detail.textContent, /Contrapartida mínima del 20 %/);
  assert.match(detail.textContent, /ya es tarde/);
  assert.match(detail.textContent, /esfuerzo estimado: alto \(unos 90 días\)/i);
  const why = detail.querySelector('.cvm-why').textContent;
  assert.match(why, /Salud mental/);
  assert.match(why, /Análisis de EEG y neuroimagen/);
  assert.match(why, /financiador previo ✓/);
  assert.match(detail.textContent, /Por qué encaja/);
  assert.match(detail.textContent, /4\.500\.000\.000 COP/);
  assert.ok(detail.querySelector('a[href="https://minciencias.gov.co/tdr.pdf"]'));
  assert.ok(detail.classList.contains('is-sheet'), 'a selection opens the bottom sheet on phones');
  detail.querySelector('[data-iniciar]').click();
  await flush();
  assert.deepEqual(JSON.parse(calls.find(c => c.url.includes('/iniciar')).body), { id: 'sgr-salud' });
  assert.deepEqual(Array.from(viewer.window.__prompts), ['/propuesta-convocatorias iniciar sgr-salud']);
  detail.querySelector('.cvm-sheet-close').click();
  await flush();
  assert.ok(!detail.classList.contains('is-sheet'));
  assert.equal($$(viewer, '#cvView .cvm-card.is-sel').length, 0);
  // Without componentes the detail falls back to the affinity score.
  $(viewer, '#cvView .cvm-card[data-call="horizon-cl1"]').click();
  await flush();
  assert.match(detail.querySelector('.cvm-notice').textContent, /no cuenta para el mínimo de tres países/);
  assert.match(detail.textContent, /empezar a más tardar/);
});

test('the scope toggle disables a missing profile and reloads with ?alcance=', async (t) => {
  const viewer = await loaded(t);
  const banco = $(viewer, '#cvAlcance [data-alcance="banco"]');
  const proyecto = $(viewer, '#cvAlcance [data-alcance="proyecto"]');
  assert.equal(banco.disabled, true);
  assert.match(banco.getAttribute('title'), /Buscar para el banco LIA/);
  assert.equal(proyecto.disabled, false);
  assert.ok(proyecto.classList.contains('is-on'));

  const calls = [];
  const both = payload({ vista: vista({ perfiles: { proyecto: true, banco: true } }) });
  const banked = payload({ vista: vista({ alcance: 'banco', perfiles: { proyecto: true, banco: true }, perfil: { existe: true, alcance: 'banco', titulo: 'Laboratorio de IA' } }) });
  const viewer2 = await loaded(t, { calls, body: u => (u.includes('alcance=banco') ? banked : both) });
  const banco2 = $(viewer2, '#cvAlcance [data-alcance="banco"]');
  assert.equal(banco2.disabled, false);
  banco2.click();
  await flush();
  assert.ok(calls.some(c => c.url.endsWith('/api/convocatorias?alcance=banco') && c.method === 'GET'));
  assert.ok($(viewer2, '#cvAlcance [data-alcance="banco"]').classList.contains('is-on'));
  assert.match($(viewer2, '#cvView .cvm-tree').textContent, /Banco LIA/);
});

test('both search buttons POST their alcance and hand the returned prompt to the terminal', async (t) => {
  const calls = [];
  const viewer = await loaded(t, { calls });
  assert.match($(viewer, '#cvSearchBtn').textContent, /Buscar para el proyecto/);
  assert.match($(viewer, '#cvSearchBancoBtn').textContent, /Buscar para el banco LIA/);
  $(viewer, '#cvSearchBtn').click();
  await flush();
  $(viewer, '#cvSearchBancoBtn').click();
  await flush();
  const posts = calls.filter(c => c.url.includes('/api/convocatorias/buscar'));
  assert.deepEqual(posts.map(p => [p.method, JSON.parse(p.body)]), [['POST', { alcance: 'proyecto' }], ['POST', { alcance: 'banco' }]]);
  assert.deepEqual(Array.from(viewer.window.__prompts), [
    '/propuesta-convocatorias buscar --alcance proyecto', '/propuesta-convocatorias buscar --alcance banco',
  ]);
});

test('after «Buscar para el banco LIA» the panel follows the banco scope once its profile appears', async (t) => {
  const calls = [];
  let ready = false;
  const before = payload();
  const both = payload({ vista: vista({ perfiles: { proyecto: true, banco: true } }) });
  const banked = payload({ vista: vista({ alcance: 'banco', perfiles: { proyecto: true, banco: true }, perfil: { existe: true, alcance: 'banco', titulo: 'Laboratorio de IA' } }) });
  const viewer = await loaded(t, { calls, body: u => (!ready ? before : u.includes('alcance=banco') ? banked : both) });
  $(viewer, '#cvSearchBancoBtn').click();
  await flush();
  assert.ok($(viewer, '#cvAlcance [data-alcance="proyecto"]').classList.contains('is-on'), 'no banco profile yet');
  ready = true;  // the agent wrote perfil_banco.json; the next poll sees it
  await viewer.viewer('loadOpportunities');
  await flush();
  assert.ok(calls.some(c => c.url.endsWith('/api/convocatorias?alcance=banco')), 'switched to the searched scope');
  assert.ok($(viewer, '#cvAlcance [data-alcance="banco"]').classList.contains('is-on'));
});

test('summary stats, «Solo elegibles» and the search box follow the filters', async (t) => {
  const viewer = await loaded(t);
  const stat = key => $(viewer, `#cvStats [data-stat="${key}"] b`).textContent;
  assert.equal(stat('total'), '7');
  assert.equal(stat('vigentes'), '7');
  assert.equal(stat('urgentes'), '1');
  assert.equal(stat('lider'), '3');
  assert.equal(stat('alertas'), '4');
  const box = $(viewer, '#cvSoloElegibles');
  box.checked = true;
  box.dispatchEvent(new viewer.window.Event('change', { bubbles: true }));
  await flush();
  assert.equal(stat('total'), '6');
  assert.equal($(viewer, '#cvView .cvm-card[data-call="msca-global"]'), null);
  const search = $(viewer, '#cvBuscar');
  search.value = 'wellcome';
  search.dispatchEvent(new viewer.window.Event('input', { bubbles: true }));
  await flush();
  assert.equal(stat('total'), '1');
  assert.equal($(viewer, '#cvBuscar'), search, 'typing never rebuilds the search box');
  assert.deepEqual($$(viewer, '#cvView .cvm-card').map(c => c.getAttribute('data-call')), ['wellcome-discovery']);
  search.value = 'SGR salud';
  search.dispatchEvent(new viewer.window.Event('input', { bubbles: true }));
  await flush();
  assert.equal(stat('total'), '1', 'the search also reads titulo_corto');
});

test('titles and short names are escaped in every view and in the detail', async (t) => {
  const evil = call({
    id: 'evil', titulo: '<img src=x onerror="window.__pwned=1"><b>Malicioso</b>', titulo_corto: '<i>corto</i>',
    financiador: '<u>F</u>', temas_match: [{ tema: '<em>tema</em>', peso: 1 }],
    alertas: [{ severidad: 'warning', texto: '<s>alerta</s>' }],
    requisitos: [{ tipo: 'idioma', estado: 'cumple', texto: '"><b>x</b>' }],
  });
  const body = payload({ vista: vista({ oportunidades: [evil], mapa: { temas: [{ tema: '<em>tema</em>', n: 1 }], experiencia: [] } }) });
  const viewer = await loaded(t, { body });
  for (const key of ['arbol', 'constelacion', 'requisitos', 'tiempo']) {
    await showView(viewer, key);
    const view = $(viewer, '#cvView');
    for (const tag of ['img', 'b', 'i', 'u', 'em', 's']) assert.equal(view.querySelector(tag), null, `${key}: <${tag}>`);
  }
  await showView(viewer, 'arbol');
  $(viewer, '#cvView .cvm-card[data-call="evil"]').click();
  await flush();
  const detail = $(viewer, '#cvDetail');
  for (const tag of ['img', 'b', 'i', 'u', 'em', 's']) assert.equal(detail.querySelector(tag), null, `detail: <${tag}>`);
  assert.match(detail.querySelector('h2').textContent, /<b>Malicioso<\/b>/);
  assert.equal(viewer.window.__pwned, undefined);
});

test('an older payload without the new fields still renders every view', async (t) => {
  const old = CALLS.slice(0, 3).map(c => {
    const o = { ...c };
    for (const k of ['match', 'componentes', 'temas_match', 'experiencia', 'historial', 'alertas', 'esfuerzo', 'preparar_desde', 'titulo_corto', 'requisitos']) delete o[k];
    return o;
  });
  const v = vista({ oportunidades: old });
  for (const k of ['mapa', 'perfiles', 'alcance']) delete v[k];
  delete v.perfil.alcance;
  delete v.perfil.titulo;
  const viewer = await loaded(t, { body: payload({ vista: v }) });
  const scores = $$(viewer, '#cvView .cvm-card .cvm-score').map(s => s.textContent);
  assert.deepEqual(scores, ['70', '70', '70'], 'no match: the puntaje is used');
  assert.match($(viewer, '#cvView .cvm-tree').textContent, /Ejecuta Buscar para el banco LIA para ver la experiencia del laboratorio/);
  assert.equal($(viewer, '#cvAlcance [data-alcance="banco"]').disabled, true);
  await showView(viewer, 'constelacion');
  assert.ok($(viewer, '#cvView iframe.cvm-atlas'), 'the constellation still opens');
  await showView(viewer, 'requisitos');
  const marks = $$(viewer, '#cvView tbody td[data-tipo]').map(td => td.textContent);
  assert.ok(marks.length > 0 && marks.every(m => m === '—'));
  await showView(viewer, 'tiempo');
  assert.equal($$(viewer, '#cvView svg.cvm-timeline g.tl-row').length, 3);
  await showView(viewer, 'arbol');
  $(viewer, '#cvView .cvm-card[data-call="sgr-salud"]').click();
  await flush();
  assert.equal($(viewer, '#cvDetail h2').textContent, 'Convocatoria SGR CTeI · Salud y bienestar regional');
  assert.equal($$(viewer, '#cvDetail [data-componente]').length, 0);
  assert.match($(viewer, '#cvDetail').textContent, /Sin alertas/);
});
