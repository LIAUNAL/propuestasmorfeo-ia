/**
 * Botón «Ejecutar» de las cajas de «Fases del Pipeline Metodológico de Redacción».
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom. La regla de habilitación
 * se observa a través de `evaluatePhaseExecution` y del modal que abre
 * `runPhaseExecution`: una unidad solo se ejecuta si es la que el flujo
 * (`next_step` del control de ejecución) va a correr; en cualquier otro caso el
 * modal explica qué etapas, artefactos o procesos faltan.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const UNITS = [
  { id: 'fase0', kind: 'pre', name: 'Intake', gate: 'G0.5', sections: [], agents: ['insumos-observador'], next: 'fase1a' },
  { id: 'g0_5', kind: 'pre', name: 'Guía TDR', gate: null, sections: [], agents: [], next: 'fase1a' },
  { id: 'fase1a', kind: 'step', name: 'Scoping', gate: 'G1a', sections: [], agents: [], next: 'fase1b' },
  { id: 'fase1b', kind: 'step', name: 'Árboles', gate: 'G1b', sections: [], agents: [], next: 'fase1c' },
  { id: 'fase1c', kind: 'step', name: 'Corpus', gate: 'G1c', sections: [], agents: [], next: 'fase1' },
  { id: 'fase1', kind: 'step', name: 'Problema', gate: 'G1', sections: ['03'], agents: [], next: 'fase2' },
  { id: 'fase2', kind: 'step', name: 'Estado del arte', gate: 'G2', sections: ['04', '05'], agents: [], next: 'fase3' },
  { id: 'fase3', kind: 'step', name: 'Justificación', gate: 'G3', sections: ['02'], agents: [], next: 'fase4' },
  { id: 'fase4', kind: 'step', name: 'Objetivos', gate: 'G4', sections: ['06', '07'], agents: [], next: 'done' },
];

function envelope(overrides = {}) {
  return {
    active_run: '2026-01-demo',
    run_details: { id: '2026-01-demo', insumos_count: 2 },
    pipeline_units: UNITS,
    gates: [],
    telemetria: [],
    sections: [],
    en_curso: null,
    control: { mode: 'stepped', next_step: 'fase2', last_completed: 'fase1', intake_complete: true },
    ...overrides,
  };
}

async function harness(t) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  await flush();
  return viewer;
}

test('solo la unidad de next_step queda habilitada y apunta a /propuesta-continuar', async (t) => {
  const viewer = await harness(t);
  const verdict = viewer.viewer('evaluatePhaseExecution', 'fase2', envelope());
  assert.equal(verdict.allowed, true);
  assert.equal(verdict.command, '/propuesta-continuar');
});

test('una unidad posterior explica las etapas y artefactos que faltan', async (t) => {
  const viewer = await harness(t);
  const verdict = viewer.viewer('evaluatePhaseExecution', 'fase4', envelope());
  assert.equal(verdict.allowed, false);
  const missing = verdict.missing.join('\n');
  assert.match(missing, /Estado del arte/);
  assert.match(missing, /Justificación/);
  assert.match(missing, /G2/);
  assert.match(missing, /§04/);
  assert.match(missing, /§02/);
  assert.doesNotMatch(missing, /Problema/, 'una unidad ya superada no es un faltante');
});

test('una unidad ya superada no se vuelve a lanzar desde el botón', async (t) => {
  const viewer = await harness(t);
  const verdict = viewer.viewer('evaluatePhaseExecution', 'fase1', envelope());
  assert.equal(verdict.allowed, false);
  assert.match(verdict.reason, /ya se complet/i);
});

test('sin intake completo solo se habilita el intake con /propuesta-analizar', async (t) => {
  const viewer = await harness(t);
  const data = envelope({ control: null });
  const intake = viewer.viewer('evaluatePhaseExecution', 'fase0', data);
  assert.equal(intake.allowed, true);
  assert.equal(intake.command, '/propuesta-analizar');

  const step = viewer.viewer('evaluatePhaseExecution', 'fase1a', data);
  assert.equal(step.allowed, false);
  assert.match(step.missing.join('\n'), /Intake/);
});

test('sin corrida activa el intake se lanza con la idea inicial y el resto pide /propuesta-init', async (t) => {
  const viewer = await harness(t);
  const data = envelope({ active_run: null, control: null });
  const intake = viewer.viewer('evaluatePhaseExecution', 'fase0', data);
  assert.equal(intake.allowed, true);
  assert.equal(intake.command, '/propuesta-analizar');
  assert.equal(intake.idea, true);
  assert.match(intake.reason, /crea la corrida/);

  const step = viewer.viewer('evaluatePhaseExecution', 'fase1a', data);
  assert.equal(step.allowed, false);
  assert.match(step.missing.join('\n'), /\/propuesta-init|Intake/);
});

test('el intake ofrece la idea inicial de idea.md y la envía con /propuesta-analizar', async (t) => {
  const viewer = await harness(t);
  viewer.window.fetch = async (url) => {
    if (String(url).includes('/api/idea')) {
      return { ok: true, status: 200, json: async () => ({ ok: true, text: 'Problema: baja cobertura del monitoreo hídrico en Caldas.', source: 'idea.md' }) };
    }
    return { ok: false, status: 503, json: async () => ({}) };
  };
  viewer.window.eval(`currentStatus = ${JSON.stringify(envelope({ active_run: null, control: null }))}; setPhasesInfo(currentStatus.pipeline_units);
    window.__sent = [];
    sendTerminalQuickCommand = (cmd) => window.__sent.push(cmd);
    terminalSocket = { readyState: 1, send: () => {} }; openMorfeoTerminal = () => {}; ensureTerminalConnected = () => {}; TERMINAL_SETTLE_MAX_MS = 1;`);
  await viewer.viewer('runPhaseExecution', 'fase0');
  await flush();
  const idea = viewer.document.getElementById('phaseExecInput');
  assert.ok(idea, 'el modal trae el campo de idea inicial');
  assert.equal(idea.value, 'Problema: baja cobertura del monitoreo hídrico en Caldas.');
  idea.value = 'Problema: baja cobertura\ndel monitoreo hídrico.';
  viewer.document.getElementById('phaseExecConfirmBtn').click();
  await flush();
  await viewer.advance(50);
  await flush();
  assert.deepEqual(Array.from(viewer.window.__sent), ['/propuesta-analizar Problema: baja cobertura del monitoreo hídrico.']);
});

test('con una unidad en curso ninguna otra se puede lanzar', async (t) => {
  const viewer = await harness(t);
  const data = envelope({ en_curso: { fase: 'fase2', agentes: ['redactor'] } });
  const same = viewer.viewer('evaluatePhaseExecution', 'fase2', data);
  assert.equal(same.allowed, false);
  assert.match(same.reason, /en ejecución/i);
});

test('con el pipeline terminado el botón remite a la compilación', async (t) => {
  const viewer = await harness(t);
  const data = envelope({ control: { next_step: 'done', intake_complete: true } });
  const verdict = viewer.viewer('evaluatePhaseExecution', 'fase4', data);
  assert.equal(verdict.allowed, false);
  assert.match(verdict.missing.join('\n'), /\/compilar-pdf/);
});

test('el modal de una unidad bloqueada lista lo que falta y no ofrece ejecutar', async (t) => {
  const viewer = await harness(t);
  viewer.window.eval(`currentStatus = ${JSON.stringify(envelope())}; setPhasesInfo(currentStatus.pipeline_units);`);
  viewer.viewer('runPhaseExecution', 'fase4');
  const modal = viewer.document.getElementById('phaseExecModal');
  assert.ok(modal.classList.contains('is-open'));
  const body = viewer.document.getElementById('phaseExecModalBody').textContent;
  assert.match(body, /Estado del arte/);
  const confirm = viewer.document.getElementById('phaseExecConfirmBtn');
  assert.equal(confirm.style.display, 'none');
});

test('el modal de la unidad habilitada ofrece el comando y lo envía a la terminal', async (t) => {
  const viewer = await harness(t);
  viewer.window.eval(`currentStatus = ${JSON.stringify(envelope())}; setPhasesInfo(currentStatus.pipeline_units);
    window.__sent = [];
    sendTerminalQuickCommand = (cmd) => window.__sent.push(cmd);
    terminalSocket = { readyState: 1, send: () => {} }; openMorfeoTerminal = () => {}; ensureTerminalConnected = () => {}; TERMINAL_SETTLE_MAX_MS = 1;`);
  await viewer.viewer('runPhaseExecution', 'fase2');
  const confirm = viewer.document.getElementById('phaseExecConfirmBtn');
  assert.notEqual(confirm.style.display, 'none');
  confirm.click();
  await flush();
  await viewer.advance(50);
  await flush();
  assert.deepEqual(Array.from(viewer.window.__sent), ['/propuesta-continuar']);
  assert.ok(!viewer.document.getElementById('phaseExecModal').classList.contains('is-open'));
});

test('la unidad habilitada abre un recuadro con la guía de la fase y envía las indicaciones', async (t) => {
  const viewer = await harness(t);
  viewer.window.eval(`currentStatus = ${JSON.stringify(envelope())}; setPhasesInfo(currentStatus.pipeline_units);
    window.__sent = [];
    sendTerminalQuickCommand = (cmd) => window.__sent.push(cmd);
    terminalSocket = { readyState: 1, send: () => {} }; openMorfeoTerminal = () => {}; ensureTerminalConnected = () => {}; TERMINAL_SETTLE_MAX_MS = 1;`);
  await viewer.viewer('runPhaseExecution', 'fase2');
  const box = viewer.document.getElementById('phaseExecInput');
  assert.ok(box, 'el recuadro de indicaciones existe');
  assert.match(box.getAttribute('placeholder'), /estado del arte/i);
  box.value = 'Priorizar  modelos\nfundacionales.';
  viewer.document.getElementById('phaseExecConfirmBtn').click();
  await flush();
  await viewer.advance(50);
  await flush();
  assert.deepEqual(Array.from(viewer.window.__sent), ['/propuesta-continuar Priorizar modelos fundacionales.']);
});

test('una fase con panel propio ofrece ir a ese panel', async (t) => {
  const viewer = await harness(t);
  const data = envelope({ control: { mode: 'stepped', next_step: 'fase1b', last_completed: 'fase1a', intake_complete: true } });
  viewer.window.eval(`currentStatus = ${JSON.stringify(data)}; setPhasesInfo(currentStatus.pipeline_units);
    startTreesPolling = () => {};`);
  await viewer.viewer('runPhaseExecution', 'fase1b');
  const link = viewer.document.querySelector('#phaseExecModalBody [data-panel]');
  assert.ok(link, 'hay un acceso al panel de la fase');
  assert.equal(link.getAttribute('data-panel'), 'trees');
  link.click();
  assert.equal(viewer.window.eval('activeTab'), 'trees');
  assert.ok(!viewer.document.getElementById('phaseExecModal').classList.contains('is-open'));
});

test('una fase bloqueada también remite a su panel, sin recuadro de indicaciones', async (t) => {
  const viewer = await harness(t);
  viewer.window.eval(`currentStatus = ${JSON.stringify(envelope())}; setPhasesInfo(currentStatus.pipeline_units);`);
  await viewer.viewer('runPhaseExecution', 'fase1');
  assert.equal(viewer.document.getElementById('phaseExecInput'), null);
  const link = viewer.document.querySelector('#phaseExecModalBody [data-panel]');
  assert.equal(link && link.getAttribute('data-panel'), 'mga');
});

test('clic en la caja del pipeline abre el recuadro de ejecución de esa fase', async (t) => {
  const viewer = await harness(t);
  const data = envelope();
  viewer.window.fetch = async (url) => String(url).includes('/api/status')
    ? { ok: true, status: 200, json: async () => data, text: async () => JSON.stringify(data) }
    : { ok: false, status: 503, json: async () => ({}), text: async () => '' };
  await viewer.viewer('loadStatus');
  await flush();
  const card = Array.from(viewer.document.querySelectorAll('#pipelineGrid .phase-card')).find(c => /Estado del arte/.test(c.textContent));
  assert.ok(card);
  card.click();
  await flush();
  assert.ok(viewer.document.getElementById('phaseExecModal').classList.contains('is-open'));
  assert.ok(viewer.document.getElementById('phaseExecInput'));
});

test('la caja del intake se ve activa cuando es la fase inicial ejecutable', async (t) => {
  const viewer = await harness(t);
  const data = envelope({ active_run: null, control: null });
  viewer.window.fetch = async (url) => String(url).includes('/api/status')
    ? { ok: true, status: 200, json: async () => data, text: async () => JSON.stringify(data) }
    : { ok: false, status: 503, json: async () => ({}), text: async () => '' };
  await viewer.viewer('loadStatus');
  await flush();
  const cards = Array.from(viewer.document.querySelectorAll('#pipelineGrid .phase-card'));
  const intake = cards.find(c => /Intake/.test(c.textContent));
  assert.ok(intake.classList.contains('phase-card--ready'), intake.className);
  assert.ok(!intake.classList.contains('phase-card--unlit'), 'no se pinta apagada');
  assert.match(intake.textContent, /LISTA PARA EJECUTAR/);
  const scoping = cards.find(c => /Scoping/.test(c.textContent));
  assert.ok(scoping.classList.contains('phase-card--unlit'), 'las bloqueadas siguen apagadas');
  assert.ok(!scoping.classList.contains('phase-card--ready'));
});
