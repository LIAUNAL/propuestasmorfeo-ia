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
  { id: 'fase1b', kind: 'step', name: 'Corpus', gate: 'G1b', sections: [], agents: [], next: 'fase1' },
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

test('sin corrida activa nada se ejecuta y se indica /propuesta-init', async (t) => {
  const viewer = await harness(t);
  const verdict = viewer.viewer('evaluatePhaseExecution', 'fase0', envelope({ active_run: null }));
  assert.equal(verdict.allowed, false);
  assert.match(verdict.missing.join('\n'), /\/propuesta-init/);
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
    sendTerminalQuickCommand = (cmd) => window.__sent.push(cmd);`);
  viewer.viewer('runPhaseExecution', 'fase2');
  const confirm = viewer.document.getElementById('phaseExecConfirmBtn');
  assert.notEqual(confirm.style.display, 'none');
  confirm.click();
  assert.deepEqual(Array.from(viewer.window.__sent), ['/propuesta-continuar']);
  assert.ok(!viewer.document.getElementById('phaseExecModal').classList.contains('is-open'));
});
