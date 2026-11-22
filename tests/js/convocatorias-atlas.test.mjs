/**
 * The «Convocatorias» constellation drawn with the SOTA 3D viewer
 * (odd/tasks/tablero-juez-novedad.md, T7, S7).
 *
 * Two halves. The page: scripts/convocatorias.py builds the scene from a view
 * double and scripts/render_atlas.py renders it with the "convocatorias"
 * profile; the page runs as is under jsdom (no WebGL, so its 2D constellation
 * opens and a click goes through the same `onSelect` hook as the 3D viewer),
 * framed by a recording parent window. The dashboard: the real index.html with
 * convocatorias-map.js inlined, where the «Constelación de afinidad» view is an
 * iframe of /api/convocatorias/atlas that pauses with its tab and whose
 * «Iniciar propuesta con esta» message is honored only from that iframe and
 * only for a known call.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { JSDOM } from 'jsdom';

import { createViewerHarness, flush } from './harness.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..');
const PYTHON = process.env.PYTHON || 'python3';

function call(overrides = {}) {
  return {
    id: 'sgr-salud', titulo: 'Convocatoria SGR CTeI · Salud y bienestar regional', titulo_corto: 'SGR Salud regional',
    financiador: 'Minciencias', programa: 'Asignación CTeI', url: 'https://minciencias.gov.co/sgr',
    ambito: 'colombia', idioma: 'es', aplicantes: ['universidad'], rol_colombia: 'lider', aviso: null,
    estado: 'abierta', apertura: '2026-10-23', cierre: '2026-12-11', cierre_tipo: 'fijo', dias_restantes: 21,
    vigente: true, monto: { min: null, max: 4500000000, moneda: 'COP' },
    elegibilidad: 'Universidades colombianas con grupo reconocido.', puntaje: 70, match: 78,
    evidencia: [{ texto: 'Términos de referencia', url: 'https://minciencias.gov.co/tdr.pdf' }],
    temas_match: [{ tema: 'salud mental', peso: 1 }, { tema: 'eeg', peso: 0.5 }],
    experiencia: ['lia-eeg'], esfuerzo: 'alto', preparar_desde: '2026-09-12', alertas: [], requisitos: [],
    ...overrides,
  };
}

const CALLS = [
  call(),
  call({
    id: 'horizon-cl1', titulo: 'Horizon Europe Cluster 1 · Mental health', titulo_corto: 'Horizon CL1',
    financiador: 'Comisión Europea', ambito: 'internacional', idioma: 'en', rol_colombia: 'socio', match: 64,
    temas_match: [{ tema: 'salud mental', peso: 1 }], experiencia: ['lia-dl'], monto: {}, evidencia: [],
  }),
  call({
    id: 'cyted-redes', titulo: 'CYTED Redes temáticas 2027', titulo_corto: 'CYTED Redes', financiador: 'CYTED',
    ambito: 'latam', rol_colombia: 'coaplicante', match: 60, temas_match: [{ tema: 'aprendizaje automatico', peso: 1 }],
    experiencia: [], evidencia: [],
  }),
  call({
    id: 'msca-global', titulo: 'MSCA Global Postdoctoral Fellowships', titulo_corto: 'MSCA Global PF',
    financiador: 'Comisión Europea', ambito: 'internacional', rol_colombia: 'no_elegible', match: 18,
    temas_match: [], experiencia: [], evidencia: [],
  }),
];

const MAPA = {
  temas: [{ tema: 'salud mental', n: 2 }, { tema: 'eeg', n: 1 }, { tema: 'aprendizaje automatico', n: 1 }],
  experiencia: [
    { id: 'lia-eeg', nombre: 'Análisis de EEG y neuroimagen', detalle: 'Proyectos con Minciencias', temas: ['eeg'], financiadores: ['Minciencias'], n: 1 },
    { id: 'lia-dl', nombre: 'Aprendizaje profundo', detalle: null, temas: ['aprendizaje automatico'], financiadores: [], n: 1 },
  ],
};

function vista(overrides = {}) {
  return {
    schema: 'morfeo.convocatorias-vista/v1', hoy: '2026-11-20', workspace: '/tmp/ws', alcance: 'proyecto',
    perfil: {
      existe: true, alcance: 'proyecto', titulo: 'IA para la detección temprana de depresión con EEG',
      aplicantes: ['investigador'], idiomas: ['es', 'en'], ambitos: ['colombia'], n_palabras_clave: 6,
    },
    perfiles: { proyecto: true, banco: false },
    resumen: { total: CALLS.length, vigentes: CALLS.length, por_ambito: {}, por_rol: {}, por_idioma: {} },
    fuentes_consultadas: [], oportunidades: CALLS, mapa: MAPA, hallazgos: [], ...overrides,
  };
}

// --- The page --------------------------------------------------------------

const BUILD = `
import json, sys
from pathlib import Path
repo = Path(sys.argv[1])
sys.path.insert(0, str(repo / "src"))
from morfeo.core import value_chain
value_chain._script_candidates = lambda name: [repo / "scripts" / name]
from morfeo.core import opportunities
conv = value_chain.load_kit_script("convocatorias.py", ("atlas_de_vista",))
view = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
built = conv.atlas_de_vista(view, agrupar=sys.argv[3], idea=sys.argv[4] or None)
sys.stdout.write(json.dumps({"html": opportunities.atlas_page(built), "built": built}))
`;

function build(view, { agrupar = 'tema', idea = '' } = {}) {
  const dir = mkdtempSync(path.join(tmpdir(), 'cv-atlas-js-'));
  try {
    const file = path.join(dir, 'vista.json');
    writeFileSync(file, JSON.stringify(view));
    const out = execFileSync(PYTHON, ['-c', BUILD, REPO, file, agrupar, idea], { stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 64 * 1024 * 1024 });
    return JSON.parse(out.toString('utf-8'));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function fakeContext() {
  const target = { measureText: (s) => ({ width: 6 * String(s).length }) };
  return new Proxy(target, { get: (obj, prop) => (prop in obj ? obj[prop] : () => {}) });
}

function mount(t, html, { framed = true } = {}) {
  const parentDom = new JSDOM('<!doctype html><title>tablero</title>', { url: 'http://localhost:8080/' });
  const posted = [];
  parentDom.window.postMessage = (message) => posted.push(structuredClone(message));
  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'http://localhost:8080/api/convocatorias/atlas',
    beforeParse(window) {
      if (framed) Object.defineProperty(window, 'parent', { configurable: true, get: () => parentDom.window });
      window.HTMLCanvasElement.prototype.getContext = function (type) { return type === '2d' ? fakeContext() : null; };
      window.ResizeObserver = class { observe() {} disconnect() {} };
      window.Element.prototype.setPointerCapture = () => {};
    },
  });
  t.after(() => { dom.window.close(); parentDom.window.close(); });
  return { window: dom.window, doc: dom.window.document, posted };
}

const frame = (window) => new Promise((resolve) => window.requestAnimationFrame(() => resolve()));

async function clickPlanet(window, key) {
  await frame(window);
  const [point] = window.eval(`viewer.project([${JSON.stringify(key)}])`);
  assert.ok(point, `planet ${key} must be drawn`);
  const canvas = window.document.querySelector('#sky canvas');
  const at = { clientX: point.x, clientY: point.y, button: 0, bubbles: true };
  canvas.dispatchEvent(new window.MouseEvent('pointerdown', at));
  canvas.dispatchEvent(new window.MouseEvent('pointerup', at));
}

const facts = (body) => Object.fromEntries([...body.querySelectorAll('dl.side-paper dt')]
  .map((dt) => [dt.textContent, dt.nextElementSibling.textContent]));
const sections = (body) => [...body.querySelectorAll('dl.side-sections dt')].map((dt) => dt.textContent);

test('a call planet opens its card: base data, sections, cited evidence and «Iniciar propuesta con esta»', async (t) => {
  const { html } = build(vista());
  const { window, doc, posted } = mount(t, html);
  assert.equal(doc.title, 'Constelación de convocatorias');
  assert.ok(doc.getElementById('toolbar').textContent.includes('Vista 2D') || doc.getElementById('viewmode'));
  await clickPlanet(window, 'cv-sgr-salud.deadline');
  const side = doc.getElementById('side');
  assert.equal(side.hidden, false);
  const body = doc.getElementById('sidebody');
  assert.equal(body.querySelector('h2').textContent, 'SGR Salud regional');
  assert.match(body.querySelector('.side-meta').textContent, /Convocatoria SGR CTeI · Salud y bienestar regional/);
  assert.match(body.querySelector('.side-node').textContent, /Seleccionado · cierre: Cierra en 21 d/);
  assert.deepEqual(facts(body), {
    'Programa': 'Asignación CTeI', 'Idioma': 'Español', 'Aplicantes': 'Universidad', 'Apertura': '2026-10-23',
    'Match': '78/100', 'Esfuerzo estimado': 'alto (unos 90 días)', 'Enlace': 'https://minciencias.gov.co/sgr',
  });
  assert.deepEqual(sections(body), ['Financiador', 'Ámbito', 'Monto', 'Cierre', 'Rol de Colombia', 'Elegibilidad', 'Temas', 'Grupo']);
  assert.equal(body.querySelector('dl.side-sections .sel').textContent.startsWith('Cierra en 21 d'), true);
  const cited = [...body.querySelectorAll('dl.side-cited')].map((dl) => [dl.querySelector('dt').textContent,
    [...dl.querySelectorAll('a')].map((a) => [a.textContent, a.getAttribute('href'), a.target, a.rel])]);
  assert.deepEqual(cited, [
    ['Evidencia citada', [['Términos de referencia', 'https://minciencias.gov.co/tdr.pdf', '_blank', 'noopener']]],
    ['Enlace', [['minciencias.gov.co', 'https://minciencias.gov.co/sgr', '_blank', 'noopener']]],
  ]);
  const linked = [...body.querySelectorAll('.side-links button')].map((b) => b.textContent).sort();
  assert.deepEqual(linked, ['Análisis de EEG y neuroimagen', 'IA para la detección temprana de depresión con EEG']);
  const start = body.querySelector('button.side-start');
  assert.equal(start.textContent, '🚀 Iniciar propuesta con esta');
  start.click();
  assert.deepEqual(posted.filter((m) => m.type === 'convocatoria-iniciar'), [{ type: 'convocatoria-iniciar', id: 'sgr-salud' }]);
});

test('the profile and a banco LIA line open their own cards, without the start button', async (t) => {
  const { html } = build(vista(), { idea: 'Detectar depresión con EEG portátil en atención primaria.' });
  const { window, doc } = mount(t, html);
  await clickPlanet(window, 'perfil.sun');
  const body = doc.getElementById('sidebody');
  assert.equal(body.querySelector('h2').textContent, 'IA para la detección temprana de depresión con EEG');
  assert.deepEqual(sections(body), ['Idea', 'Temas', 'Grupo']);
  assert.match(body.textContent, /Detectar depresión con EEG portátil/);
  assert.deepEqual(facts(body), {
    'Alcance': 'Proyecto en formulación', 'Idiomas': 'Español, Inglés', 'Ámbitos': 'Colombia',
    'Aplicantes': 'Investigador', 'Palabras clave': '6',
  });
  assert.equal(body.querySelector('button.side-start'), null);
  assert.equal(body.querySelectorAll('.side-links button').length, 3, 'the three calls sharing a profile tema');

  await clickPlanet(window, 'exp-lia-eeg.sun');
  assert.equal(body.querySelector('h2').textContent, 'Análisis de EEG y neuroimagen');
  assert.deepEqual(sections(body), ['Financiador', 'Detalle', 'Temas', 'Grupo']);
  assert.deepEqual(facts(body), { 'Convocatorias conectadas': '1' });
  assert.equal(body.querySelector('button.side-start'), null);
});

test('opened alone, a call card has no start button', async (t) => {
  const { html } = build(vista());
  const { window, doc } = mount(t, html, { framed: false });
  await clickPlanet(window, 'cv-sgr-salud.sun');
  assert.equal(doc.querySelector('#sidebody h2').textContent, 'SGR Salud regional');
  assert.equal(doc.querySelector('#sidebody button.side-start'), null);
});

test('hostile titles and urls are text: no markup, no javascript: or data: links', async (t) => {
  const evilText = '<img src=x onerror="window.__pwned=1"></script><script>window.__pwned=1</script>';
  const evil = call({
    id: 'evil', titulo: evilText, titulo_corto: '<b>corto</b>', financiador: '<i>F</i>', programa: evilText,
    url: 'javascript:window.__pwned=1', elegibilidad: '<u>x</u>',
    evidencia: [{ texto: '<s>cita</s>', url: 'javascript:window.__pwned=1' }, { texto: 'otra', url: 'data:text/html,x' }],
    temas_match: [{ tema: '<em>tema</em>', peso: 1 }],
  });
  const { html } = build(vista({ oportunidades: [evil], mapa: { temas: [{ tema: '<em>tema</em>', n: 1 }], experiencia: [] } }));
  const { window, doc } = mount(t, html);
  assert.equal(window.__pwned, undefined);
  await clickPlanet(window, 'cv-evil.eligibility');
  const body = doc.getElementById('sidebody');
  assert.equal(body.querySelector('h2').textContent, '<b>corto</b>');
  assert.equal(body.querySelectorAll('img, b, i, u, s, em, script').length, 0);
  assert.equal(body.querySelectorAll('a').length, 0, 'no web address, no link');
  assert.ok(body.textContent.includes('<s>cita</s>'));
  assert.equal(doc.querySelectorAll('#study img, #study script').length, 0);
  assert.equal(window.__pwned, undefined);
});

// --- The dashboard -----------------------------------------------------------

function payload(view = vista()) {
  return { ok: true, disponible: true, vista: view, error: null };
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
    if (u.includes('/api/convocatorias/iniciar')) return json({ ok: true, prompt: `/propuesta-convocatorias iniciar ${JSON.parse(init.body).id}` });
    if (u.includes('/api/convocatorias')) return json(body);
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

const atlasFrame = (viewer) => $(viewer, '#cvView iframe.cvm-atlas');
function query(frameEl) {
  const src = frameEl.getAttribute('src');
  assert.ok(src.startsWith('/api/convocatorias/atlas?'), src);
  return new URLSearchParams(src.split('?')[1]);
}

test('the constellation view is a lazy iframe of /api/convocatorias/atlas that follows grouping and filters', async (t) => {
  const viewer = await loaded(t);
  assert.equal(atlasFrame(viewer), null, 'nothing loads before the view is opened');
  await showView(viewer, 'constelacion');
  const frameEl = atlasFrame(viewer);
  assert.ok(frameEl, 'the constellation is the 3D page');
  assert.equal($(viewer, '#cvView svg.cvm-const'), null, 'the old SVG constellation is gone');
  assert.equal(frameEl.getAttribute('loading'), 'lazy');
  assert.equal(frameEl.getAttribute('title'), 'Constelación de convocatorias');
  let q = query(frameEl);
  assert.equal(q.get('alcance'), 'proyecto');
  assert.equal(q.get('agrupar'), 'tema');
  assert.equal(q.get('ids'), null, 'no filter, no ids');
  assert.ok(q.get('v'), 'a view signature reloads the frame after a new search');
  viewer.viewer('cvRenderBody');
  await flush();
  assert.equal(atlasFrame(viewer), frameEl, 'a repaint with the same data keeps the loaded frame');

  $(viewer, '#cvAgrupar [data-agrupar="ambito"]').click();
  await flush();
  assert.equal(query(atlasFrame(viewer)).get('agrupar'), 'ambito');
  const box = $(viewer, '#cvSoloElegibles');
  box.checked = true;
  box.dispatchEvent(new viewer.window.Event('change', { bubbles: true }));
  await flush();
  q = query(atlasFrame(viewer));
  assert.deepEqual(q.get('ids').split(','), ['sgr-salud', 'horizon-cl1', 'cyted-redes']);
  const search = $(viewer, '#cvBuscar');
  search.value = 'nada coincide';
  search.dispatchEvent(new viewer.window.Event('input', { bubbles: true }));
  await flush();
  assert.equal(atlasFrame(viewer), null);
  assert.match($(viewer, '#cvView').textContent, /Ninguna convocatoria cumple los filtros/);
});

test('side by side shows the tree next to the 3D constellation', async (t) => {
  const viewer = await loaded(t);
  await showView(viewer, 'lado');
  assert.ok($(viewer, '#cvView .cvm-tree'));
  assert.ok($(viewer, '#cvView .cvm-side__const iframe.cvm-atlas'));
  const frameEl = atlasFrame(viewer);
  $(viewer, '#cvView .cvm-card[data-call="horizon-cl1"]').click();
  await flush();
  assert.equal(atlasFrame(viewer), frameEl, 'selecting a fruit keeps the frame');
});

test('the frame pauses when its tab hides and resumes when it shows', async (t) => {
  const viewer = await loaded(t);
  await showView(viewer, 'constelacion');
  const sent = [];
  atlasFrame(viewer).contentWindow.postMessage = (message) => sent.push(JSON.parse(JSON.stringify(message)));
  viewer.viewer('navigateTab', 'atlas');
  await flush();
  assert.deepEqual(sent.at(-1), { type: 'atlas-control', cmd: 'pause' });
  viewer.viewer('navigateTab', 'convocatorias');
  await flush();
  assert.deepEqual(sent.at(-1), { type: 'atlas-control', cmd: 'resume' });
});

test('«Iniciar propuesta con esta» from the frame starts only a known call sent by that frame', async (t) => {
  const calls = [];
  const viewer = await loaded(t, { calls });
  await showView(viewer, 'constelacion');
  const { window } = viewer;
  const send = (data, { source = atlasFrame(viewer).contentWindow, origin = window.location.origin } = {}) =>
    window.dispatchEvent(new window.MessageEvent('message', { data, source, origin }));
  const starts = () => calls.filter((c) => c.url.includes('/api/convocatorias/iniciar')).map((c) => JSON.parse(c.body).id);

  send({ type: 'convocatoria-iniciar', id: 'sgr-salud' }, { source: window });
  send({ type: 'convocatoria-iniciar', id: 'sgr-salud' }, { origin: 'http://evil.test' });
  send({ type: 'convocatoria-iniciar', id: 'no-existe' });
  send({ type: 'convocatoria-iniciar', id: ['sgr-salud'] });
  send('convocatoria-iniciar');
  await flush();
  assert.deepEqual(starts(), [], 'foreign sources, origins, unknown or malformed ids are ignored');

  send({ type: 'convocatoria-iniciar', id: 'horizon-cl1' });
  await flush();
  assert.deepEqual(starts(), ['horizon-cl1']);
  assert.deepEqual(Array.from(window.__prompts), ['/propuesta-convocatorias iniciar horizon-cl1']);
});

test('the constellation groups are the tree groups for each grouping (Python and JS agree)', async (t) => {
  const viewer = await loaded(t);
  for (const agrupar of ['tema', 'ambito', 'rol']) {
    $(viewer, `#cvAgrupar [data-agrupar="${agrupar}"]`).click();
    await flush();
    const tree = {};
    $$(viewer, '#cvView .cvm-group').forEach((g) => {
      const label = g.querySelector('.cvm-group__head span').textContent;
      g.getAttribute('data-ids').split(' ').forEach((id) => { tree[id] = label; });
    });
    const { built } = build(vista(), { agrupar });
    const sky = {};
    built.atlas.systems.filter((s) => s.kind === 'convocatoria').forEach((s) => {
      sky[s.call_id] = s.planets.find((p) => p.slot === 'family').label;
    });
    assert.deepEqual(sky, tree, agrupar);
  }
});
