/**
 * Seguimiento y verificación de la ejecución de una fase del pipeline.
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom con `/api/status`
 * sustituido por un doble que cada prueba va cambiando. Se observa la caja de la
 * fase (iluminada solo si `unit_progress` la da por cumplida), el seguidor
 * `#phaseRunTracker` que aparece al pulsar «Ejecutar» y la lista de
 * comprobaciones del modal.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const UNITS = [
  { id: 'fase0', kind: 'pre', name: 'Intake', gate: 'G0.5', sections: [], agents: ['insumos-observador'], next: 'fase1a' },
  { id: 'fase1', kind: 'step', name: 'Problema', gate: 'G1', sections: ['03'], agents: ['investigador'], next: 'fase2' },
  { id: 'fase2', kind: 'step', name: 'Estado del arte', gate: 'G2', sections: ['04'], agents: ['bibliografo-propuesta'], next: 'fase3' },
  { id: 'fase3', kind: 'step', name: 'Justificación', gate: 'G3', sections: ['02'], agents: ['redactor'], next: 'done' },
];

const ok = (label) => ({ id: 'x', label, ok: true });
const ko = (label) => ({ id: 'x', label, ok: false });

function progress(state, extra = {}) {
  return { state, verdict: null, event: null, checks: [], missing: [], artifacts: [], ...extra };
}

function envelope(overrides = {}) {
  return {
    active_run: '2026-01-demo',
    run_details: { id: '2026-01-demo', insumos_count: 2 },
    pipeline_units: UNITS,
    gates: [{ id: 'G1', phase: 'fase1', status: 'PASS' }],
    telemetria: [],
    sections: [],
    artifacts: [],
    en_curso: null,
    control: { mode: 'stepped', next_step: 'fase2', last_completed: 'fase1', intake_complete: true },
    unit_progress: {
      fase0: progress('verified'),
      fase1: progress('verified', { checks: [ok('Compuerta G1 en PASS')] }),
      fase2: progress('pending', { checks: [ko('Compuerta G2 en PASS')], missing: ['Compuerta G2 en PASS'] }),
      fase3: progress('pending'),
    },
    ...overrides,
  };
}

async function harness(t, initial) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const state = { data: initial };
  viewer.window.fetch = async (url) => String(url).includes('/api/status')
    ? { ok: true, status: 200, json: async () => state.data, text: async () => JSON.stringify(state.data) }
    : { ok: true, status: 200, json: async () => ({}), text: async () => 'contenido' };
  viewer.window.eval(`window.__sent = []; sendTerminalQuickCommand = (cmd) => window.__sent.push(cmd);`);
  const load = async (data) => {
    if (data) state.data = data;
    await viewer.viewer('loadStatus');
    await flush();
  };
  await load();
  return { viewer, load };
}

const card = (viewer, re) => Array.from(viewer.document.querySelectorAll('#pipelineGrid .phase-card')).find(c => re.test(c.textContent));

test('la caja se ilumina solo si la verificación da la unidad por cumplida', async (t) => {
  const data = envelope({
    gates: [{ id: 'G1', phase: 'fase1', status: 'PASS' }, { id: 'G2', phase: 'fase2', status: 'PASS' }],
    control: { mode: 'stepped', next_step: 'fase3', last_completed: 'fase2', intake_complete: true },
    unit_progress: { ...envelope().unit_progress, fase2: progress('partial', { missing: ['redaccion/sections/04_*.tex existe'] }) },
  });
  const { viewer } = await harness(t, data);
  assert.ok(card(viewer, /Problema/).classList.contains('phase-card--lit'));
  const sota = card(viewer, /Estado del arte/);
  assert.ok(!sota.classList.contains('phase-card--lit'), 'PASS sin archivos no se ilumina');
  assert.ok(sota.classList.contains('phase-card--partial'), sota.className);
  assert.match(sota.textContent, /INCOMPLETA/);
});

test('sin unit_progress (servidor anterior) la caja se ilumina con el PASS', async (t) => {
  const data = envelope();
  delete data.unit_progress;
  const { viewer } = await harness(t, data);
  assert.ok(card(viewer, /Problema/).classList.contains('phase-card--lit'));
});

test('un latido obsoleto no bloquea la unidad que sigue', async (t) => {
  const { viewer } = await harness(t, envelope());
  const data = envelope({ en_curso: { fase: 'fase1', agentes: [], stale: true } });
  const verdict = viewer.viewer('evaluatePhaseExecution', 'fase2', data);
  assert.equal(verdict.allowed, true);
  assert.match(verdict.note || '', /obsoleto/);
});

test('al ejecutar aparece el seguidor y sigue la unidad hasta verificarla', async (t) => {
  const { viewer, load } = await harness(t, envelope());
  await viewer.viewer('runPhaseExecution', 'fase2');
  viewer.document.getElementById('phaseExecConfirmBtn').click();
  assert.deepEqual(Array.from(viewer.window.__sent), ['/propuesta-continuar']);

  const tracker = viewer.document.getElementById('phaseRunTracker');
  assert.ok(tracker && !tracker.hidden, 'el seguidor se muestra');
  assert.match(tracker.textContent, /Estado del arte/);
  assert.match(tracker.textContent, /\/propuesta-continuar/);
  assert.match(tracker.textContent, /Esperando/);

  await load(envelope({
    en_curso: { fase: 'fase2', agentes: ['bibliografo-propuesta'], skill: null, nota: 'Task → revisor (G2)', inicio: new Date().toISOString(), stale: false },
    unit_progress: { ...envelope().unit_progress, fase2: progress('running') },
  }));
  assert.match(tracker.textContent, /En curso/);
  assert.match(tracker.textContent, /bibliografo-propuesta/);
  assert.match(tracker.textContent, /Task → revisor \(G2\)/);
  assert.match(card(viewer, /Estado del arte/).textContent, /EN CURSO/, 'un cambio de en_curso repinta la caja');

  const later = Date.now() / 1000 + 60;
  await load(envelope({
    gates: [{ id: 'G1', phase: 'fase1', status: 'PASS' }, { id: 'G2', phase: 'fase2', status: 'PASS' }],
    control: { mode: 'stepped', next_step: 'fase3', last_completed: 'fase2', intake_complete: true },
    unit_progress: {
      ...envelope().unit_progress,
      fase2: progress('verified', {
        checks: [ok('Compuerta G2 en PASS'), ok('Control de ejecución: next_step ya avanzó más allá de la unidad'), ok('redaccion/sections/04_estado_arte.tex existe')],
        artifacts: [{ path: 'redaccion/sections/04_estado_arte.tex', exists: true, mtime: later }],
      }),
    },
  }));
  assert.match(tracker.textContent, /Etapa cumplida/);
  assert.match(tracker.textContent, /Compuerta G2 en PASS/);
  assert.match(tracker.textContent, /04_estado_arte\.tex/);
  assert.match(tracker.textContent, /actualizado/);
  assert.match(tracker.textContent, /Justificación/, 'nombra la etapa que queda habilitada');
  assert.ok(card(viewer, /Estado del arte/).classList.contains('phase-card--lit'));
  assert.ok(card(viewer, /Justificación/).classList.contains('phase-card--ready'));

  tracker.querySelector('[data-run-next]').click();
  await flush();
  assert.ok(viewer.document.getElementById('phaseExecModal').classList.contains('is-open'));
  assert.match(viewer.document.getElementById('phaseExecModalTitle').textContent, /Justificación/);
});

test('una compuerta en FAIL se informa en el seguidor', async (t) => {
  const { viewer, load } = await harness(t, envelope());
  await viewer.viewer('runPhaseExecution', 'fase2');
  viewer.document.getElementById('phaseExecConfirmBtn').click();
  await load(envelope({ unit_progress: { ...envelope().unit_progress, fase2: progress('failed', { missing: ['Compuerta G2 en PASS'] }) } }));
  assert.match(viewer.document.getElementById('phaseRunTracker').textContent, /FAIL/);
});

test('el modal lista la verificación de la etapa', async (t) => {
  const { viewer } = await harness(t, envelope());
  await viewer.viewer('runPhaseExecution', 'fase1');
  const body = viewer.document.getElementById('phaseExecModalBody');
  assert.match(body.textContent, /Verificación de la etapa/);
  assert.match(body.textContent, /Compuerta G1 en PASS/);
});

test('un cambio de los artefactos repinta la lista de artefactos', async (t) => {
  const { viewer, load } = await harness(t, envelope({ artifacts: [{ name: 'insumos.md', rel_path: 'artefactos/insumos.md', size: 10, mtime: 1 }] }));
  assert.equal(viewer.document.querySelectorAll('#artifactsList .sidebar-item').length, 1);
  await load(envelope({ artifacts: [
    { name: 'insumos.md', rel_path: 'artefactos/insumos.md', size: 10, mtime: 1 },
    { name: 'mga_resumido.md', rel_path: 'artefactos/mga_resumido.md', size: 20, mtime: 2 },
  ] }));
  assert.equal(viewer.document.querySelectorAll('#artifactsList .sidebar-item').length, 2);
});

test('una ejecución que cierra incompleta deja de sondear rápido', async (t) => {
  const { viewer, load } = await harness(t, envelope());
  await viewer.viewer('runPhaseExecution', 'fase2');
  viewer.document.getElementById('phaseExecConfirmBtn').click();
  await load(envelope({
    en_curso: { fase: 'fase2', agentes: ['bibliografo-propuesta'], inicio: new Date().toISOString(), stale: false },
    unit_progress: { ...envelope().unit_progress, fase2: progress('running') },
  }));
  assert.equal(viewer.viewer('phaseRunActive'), true);
  await load(envelope({ unit_progress: { ...envelope().unit_progress, fase2: progress('partial', { missing: ['redaccion/sections/04_*.tex existe'] }) } }));
  assert.match(viewer.document.getElementById('phaseRunTracker').textContent, /sin todas las pruebas/);
  assert.equal(viewer.viewer('phaseRunActive'), false);
});

test('sin latido tras 10 minutos el seguidor avisa y deja de sondear rápido', async (t) => {
  const { viewer, load } = await harness(t, envelope());
  await viewer.viewer('runPhaseExecution', 'fase2');
  viewer.document.getElementById('phaseExecConfirmBtn').click();
  assert.equal(viewer.viewer('phaseRunActive'), true, 'recién enviado sondea rápido');
  viewer.window.eval('PHASE_RUN.sentAt = Date.now() - 11 * 60 * 1000;');
  await load();
  const tracker = viewer.document.getElementById('phaseRunTracker');
  assert.match(tracker.textContent, /Sin señal/);
  assert.match(tracker.textContent, /terminal/);
  assert.equal(viewer.viewer('phaseRunActive'), false);

  await load(envelope({
    en_curso: { fase: 'fase2', agentes: ['bibliografo-propuesta'], inicio: new Date().toISOString(), stale: false },
    unit_progress: { ...envelope().unit_progress, fase2: progress('running') },
  }));
  assert.match(tracker.textContent, /En curso/, 'si el latido llega tarde, el seguidor lo retoma');
});
