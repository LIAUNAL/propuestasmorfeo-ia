/**
 * Search progress bar of the «Convocatorias» tab (odd/tasks/tablero-juez-novedad.md, T1: S1).
 *
 * The real dashboard runs under jsdom. The harness inlines only the local
 * scripts its LOCAL_SCRIPT_TAG names, so this file evaluates the real
 * static/convocatorias-progress.js in the page's window after it loads, with
 * fetch doubled; GET /api/convocatorias/progreso returns the estimate the
 * server computes (morfeo.core.opportunities.estimate_progress).
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { createViewerHarness, DASHBOARD_STATIC, flush } from './harness.mjs';

const PROGRESS_SCRIPT = readFileSync(path.join(DASHBOARD_STATIC, 'convocatorias-progress.js'), 'utf8');

function json(body, code = 200) {
  return { ok: code < 400, status: code, json: async () => body, text: async () => JSON.stringify(body) };
}

function status() {
  return { flujo: 'base', active_run: null, all_runs: [], totals: { total_words: 0 }, sections: [], gates: [],
    telemetria: [], pipeline_units: [], artifacts: [] };
}

const VIEW = {
  ok: true, disponible: true, error: null,
  vista: { schema: 'morfeo.convocatorias-vista/v1', hoy: '2026-11-22', workspace: '/tmp/ws', alcance: 'proyecto',
    perfiles: { proyecto: true, banco: false },
    perfil: { existe: true, aplicantes: [], idiomas: [], ambitos: [], n_palabras_clave: 0 },
    resumen: { total: 0, vigentes: 0, por_ambito: {}, por_rol: {}, por_idioma: {} },
    fuentes_consultadas: [], oportunidades: [], hallazgos: [] },
};

function estimate(overrides = {}) {
  return {
    estado: 'en_curso', alcance: 'proyecto', started_at: '2026-11-22T10:00:00+00:00', updated_at: '2026-11-22T10:07:30+00:00',
    finished_at: null, fase: 3, fases_total: 5, fase_nombre: 'Búsqueda abierta', phase_label: 'Fase 3/5 · Búsqueda abierta',
    percent: 60, remaining_seconds: 300, stale: false, priors: {}, ...overrides,
  };
}

async function harness(t, initial = null) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const server = { progreso: initial, calls: [] };
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    server.calls.push({ url: u, method: (init && init.method) || 'GET' });
    if (u.includes('/api/convocatorias/progreso')) return json({ ok: true, progreso: server.progreso, error: null });
    if (u.includes('/api/convocatorias/buscar')) return json({ ok: true, prompt: '/propuesta-convocatorias buscar --alcance proyecto' });
    if (u.includes('/api/convocatorias')) return json(VIEW);
    if (u.includes('/api/status')) return json(status());
    return json({}, 503);
  };
  viewer.window.eval('window.__prompts = []; sendTerminalPrompt = (cmd) => { window.__prompts.push(cmd); return Promise.resolve(true); };');
  viewer.window.eval(PROGRESS_SCRIPT);
  await viewer.viewer('loadStatusNow');
  viewer.viewer('navigateTab', 'convocatorias');
  await flush();
  return { viewer, server };
}

const bar = (viewer) => viewer.document.getElementById('cvProgress');
const label = (viewer) => viewer.document.getElementById('cvProgressLabel').textContent.trim();
const fill = (viewer) => viewer.document.getElementById('cvProgressFill').style.width;
const viewLoads = (server) => server.calls.filter(c => /\/api\/convocatorias(\?|$)/.test(c.url)).length;

test('sin búsqueda en curso la barra queda oculta', async (t) => {
  const { viewer, server } = await harness(t, null);
  assert.ok(server.calls.some(c => c.url.includes('/api/convocatorias/progreso')), 'el panel consulta el avance');
  assert.equal(bar(viewer).hidden, true);
});

test('una búsqueda en curso muestra fase, porcentaje y tiempo restante', async (t) => {
  const { viewer } = await harness(t, estimate());
  const el = bar(viewer);
  assert.equal(el.hidden, false);
  assert.equal(el.getAttribute('data-estado'), 'en_curso');
  assert.equal(el.getAttribute('aria-valuenow'), '60');
  assert.equal(fill(viewer), '60%');
  assert.equal(label(viewer), 'Fase 3/5 · Búsqueda abierta · ~60 % · faltan ~5 min');
});

test('el tiempo restante se redondea hacia arriba y dice cuándo falta menos de un minuto', async (t) => {
  const { viewer, server } = await harness(t, estimate({ remaining_seconds: 61 }));
  assert.match(label(viewer), /faltan ~2 min$/);
  server.progreso = estimate({ remaining_seconds: 45, percent: 97 });
  await viewer.boundary.clock.advance(15000);
  await flush();
  assert.match(label(viewer), /~97 % · falta menos de 1 min$/);
});

test('al pulsar Buscar la barra espera al agente y se sondea cada 3 s', async (t) => {
  const old = estimate({ estado: 'terminada', percent: 100, remaining_seconds: 0, started_at: '2026-11-20T09:00:00+00:00' });
  const { viewer, server } = await harness(t, old);
  assert.equal(bar(viewer).hidden, true, 'una búsqueda anterior terminada no se muestra');
  await viewer.viewer('searchOpportunities', 'proyecto');
  await flush();
  assert.deepEqual([...viewer.window.__prompts], ['/propuesta-convocatorias buscar --alcance proyecto']);
  assert.equal(bar(viewer).hidden, false);
  assert.equal(fill(viewer), '0%');
  assert.equal(label(viewer), 'Esperando que el agente empiece la búsqueda…');
  // The agent resets the file and starts phase 1: the next fast poll shows it.
  server.progreso = estimate({ fase: 1, phase_label: 'Fase 1/5 · Perfil', percent: 2, remaining_seconds: 740,
    started_at: '2026-11-22T10:00:00+00:00' });
  await viewer.boundary.clock.advance(3000);
  await flush();
  assert.equal(label(viewer), 'Fase 1/5 · Perfil · ~2 % · faltan ~13 min');
});

test('al terminar la barra llega al 100 %, recarga la lista y luego se oculta', async (t) => {
  const { viewer, server } = await harness(t, null);
  await viewer.viewer('searchOpportunities', 'proyecto');
  await flush();
  server.progreso = estimate();
  await viewer.boundary.clock.advance(3000);
  await flush();
  const before = viewLoads(server);
  server.progreso = estimate({ estado: 'terminada', percent: 100, remaining_seconds: 0, finished_at: '2026-11-22T10:12:00+00:00' });
  await viewer.boundary.clock.advance(3000);
  await flush();
  assert.equal(bar(viewer).hidden, false);
  assert.equal(bar(viewer).getAttribute('data-estado'), 'terminada');
  assert.equal(fill(viewer), '100%');
  assert.equal(label(viewer), 'Búsqueda terminada · 100 %');
  assert.ok(viewLoads(server) > before, 'la lista de convocatorias se recarga');
  await viewer.boundary.clock.advance(10000);
  await flush();
  assert.equal(bar(viewer).hidden, true);
});

test('un avance sin anotaciones recientes oculta la barra y deja el mensaje de siempre', async (t) => {
  const { viewer, server } = await harness(t, null);
  await viewer.viewer('searchOpportunities', 'proyecto');
  await flush();
  const message = viewer.document.getElementById('cvMessage').textContent;
  assert.match(message, /Los resultados aparecen aquí cuando termine/);
  server.progreso = estimate({ estado: 'detenida', stale: true });
  await viewer.boundary.clock.advance(3000);
  await flush();
  assert.equal(bar(viewer).hidden, true);
  assert.equal(viewer.document.getElementById('cvMessage').textContent, message);
});

test('si el envío a la terminal falla, la barra no queda esperando', async (t) => {
  const { viewer } = await harness(t, null);
  viewer.window.eval('sendTerminalPrompt = () => Promise.resolve(false);');
  await viewer.viewer('searchOpportunities', 'proyecto');
  await flush();
  assert.equal(bar(viewer).hidden, true);
});

test('salir de la pestaña detiene el sondeo del avance', async (t) => {
  const { viewer, server } = await harness(t, estimate());
  viewer.viewer('navigateTab', 'flow');
  await flush();
  const count = server.calls.filter(c => c.url.includes('/progreso')).length;
  await viewer.boundary.clock.advance(60000);
  await flush();
  assert.equal(server.calls.filter(c => c.url.includes('/progreso')).length, count);
});

test('a language switch redraws the bar and asks the server for the phase label again', async (t) => {
  const { viewer, server } = await harness(t, estimate());
  const before = server.calls.filter(c => c.url.includes('/progreso')).length;
  server.progreso = estimate({ phase_label: 'Phase 3/5 · Open search' });
  viewer.window.i18n.setLanguage('en');
  assert.equal(label(viewer), 'Fase 3/5 · Búsqueda abierta · ~60 % · ~5 min left', 'the panel text changes at once');
  await flush();
  assert.ok(server.calls.filter(c => c.url.includes('/progreso')).length > before);
  assert.equal(label(viewer), 'Phase 3/5 · Open search · ~60 % · ~5 min left');
  server.progreso = estimate();
  viewer.window.i18n.setLanguage('es');
  await flush();
  assert.equal(label(viewer), 'Fase 3/5 · Búsqueda abierta · ~60 % · faltan ~5 min');
});
