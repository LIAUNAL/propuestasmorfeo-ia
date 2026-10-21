/**
 * A running phase is followed from any tab, and the run can be stopped.
 *
 * The real dashboard JavaScript runs under jsdom, with `/api/status` replaced by
 * a double that each test changes and a fake terminal (open socket, a visible
 * screen, the last output time). The tests watch the run dock on the page body,
 * its floating panel, «Detener proceso», the idle warning and the agent picker
 * of the execute modal.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const UNITS = [
  { id: 'fase0', kind: 'pre', name: 'Intake', gate: 'G0.5', sections: [], agents: ['insumos-observador'], next: 'fase1' },
  { id: 'fase1', kind: 'step', name: 'Problema', gate: 'G1', sections: ['03'], agents: ['investigador'], next: 'fase2' },
  { id: 'fase2', kind: 'step', name: 'Estado del arte', gate: 'G2', sections: ['04'], agents: ['bibliografo-propuesta'], next: 'fase3' },
  { id: 'fase3', kind: 'step', name: 'Justificación', gate: 'G3', sections: ['02'], agents: ['redactor'], next: 'done' },
];

const progress = (state, extra = {}) => ({ state, verdict: null, event: null, checks: [], missing: [], artifacts: [], ...extra });

function envelope(overrides = {}) {
  return {
    active_run: '2026-01-demo',
    run_details: { id: '2026-01-demo', insumos_count: 2 },
    pipeline_units: UNITS,
    gates: [{ id: 'G1', phase: 'fase1', status: 'PASS' }],
    telemetria: [], sections: [], artifacts: [],
    en_curso: null,
    control: { mode: 'stepped', next_step: 'fase2', last_completed: 'fase1', intake_complete: true },
    unit_progress: {
      fase0: progress('verified'),
      fase1: progress('verified'),
      fase2: progress('pending', { checks: [{ id: 'gate', label: 'Compuerta G2 en PASS', ok: false }], missing: ['Compuerta G2 en PASS'] }),
      fase3: progress('pending'),
    },
    ...overrides,
  };
}

const running = (extra = {}) => envelope({
  en_curso: { fase: 'fase2', agentes: ['bibliografo-propuesta'], nota: 'Task → bibliografo', inicio: new Date(Date.now() - 5000).toISOString(), stale: false },
  unit_progress: { ...envelope().unit_progress, fase2: progress('running') },
  ...extra,
});

async function harness(t, initial = envelope()) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const state = { data: initial };
  viewer.window.__calls = [];
  viewer.window.fetch = async (url, opts = {}) => {
    viewer.window.__calls.push(`${(opts && opts.method) || 'GET'} ${url}`);
    if (String(url).includes('/api/status')) return { ok: true, status: 200, json: async () => state.data };
    if (/\/interrupt$/.test(String(url))) return { ok: true, status: 200, json: async () => ({ ok: true, key: 'esc' }) };
    return { ok: true, status: 200, json: async () => ({}), text: async () => '' };
  };
  viewer.window.eval(`
    window.__sent = [];
    window.__confirm = true;
    window.confirm = () => window.__confirm;
    window.__screen = [];
    TERMINAL_READY_TIMEOUT_MS = 60;
    TERMINAL_SETTLE_MAX_MS = 20;
    selectedAgent = 'claude';
    terminalSocket = { readyState: 1, send: () => {} };
    terminalSessionId = 'sess-1';
    terminalSessionAgent = 'claude';
    terminalInstance = { rows: 3, reset() {}, write() {}, focus() {}, buffer: { active: { viewportY: 0, getLine: (y) => ({ translateToString: () => window.__screen[y] || '' }) } } };
    openMorfeoTerminal = () => { isTerminalOpen = true; window.__opened = true; };
    ensureTerminalConnected = () => {};
    sendTerminalQuickCommand = (cmd) => window.__sent.push(cmd);
  `);
  const load = async (data) => {
    if (data) state.data = data;
    await viewer.viewer('loadStatus');
    await flush();
  };
  await load();
  return { viewer, load };
}

async function execute(viewer, unitId = 'fase2') {
  await viewer.viewer('runPhaseExecution', unitId);
  viewer.document.getElementById('phaseExecConfirmBtn').click();
  await viewer.advance(200);
  await flush();
}

test('a launched phase shows a progress dock on every tab and its panel shows the checkpoints', async (t) => {
  const { viewer, load } = await harness(t);
  await execute(viewer);
  assert.deepEqual(Array.from(viewer.window.__sent), ['/propuesta-continuar']);
  const dock = viewer.document.getElementById('phaseRunDock');
  assert.ok(dock && !dock.hidden, 'the dock is shown');
  assert.equal(dock.parentElement, viewer.document.body, 'the dock lives on the page body, outside any tab');
  assert.match(dock.textContent, /Estado del arte/);
  assert.equal(dock.querySelectorAll('.phase-dock__seg').length, 5);
  assert.equal(dock.querySelectorAll('.phase-dock__seg.is-on').length, 1, 'only «enviada» so far');

  viewer.viewer('navigateTab', 'artifacts');
  await load(running());
  assert.ok(!viewer.document.getElementById('phaseRunDock').hidden, 'still visible on another tab');
  assert.ok(viewer.document.querySelectorAll('#phaseRunDock .phase-dock__seg.is-on').length >= 3);

  viewer.document.querySelector('#phaseRunDock [data-run-dock]').click();
  await flush();
  const panel = viewer.document.getElementById('phaseRunPanel');
  assert.ok(panel && !panel.hidden, 'the floating panel opens on the current tab');
  assert.equal(viewer.window.eval('activeTab'), 'artifacts', 'the user does not leave the tab');
  assert.match(panel.textContent, /En curso/);
  assert.match(panel.textContent, /Verificación de la etapa/);
  assert.match(panel.textContent, /Detener proceso/);
  assert.match(panel.textContent, /Ver terminal/);

  panel.querySelector('[data-run-terminal]').click();
  assert.equal(viewer.window.__opened, true, '«Ver terminal» opens the session the phase was sent to');
  panel.querySelector('[data-panel-close]').click();
  assert.ok(viewer.document.getElementById('phaseRunPanel').hidden);
});

test('«Detener proceso» interrupts the session, keeps it and unblocks the phase', async (t) => {
  const { viewer, load } = await harness(t);
  await execute(viewer);
  await load(running());
  assert.equal(viewer.viewer('evaluatePhaseExecution', 'fase2', running()).allowed, false, 'blocked while it runs');

  viewer.document.querySelector('#phaseRunTracker [data-run-stop]').click();
  await flush();
  assert.ok(viewer.window.__calls.includes('POST /api/terminal/sessions/sess-1/interrupt'));
  assert.equal(viewer.window.eval('terminalSessionId'), 'sess-1', 'the session stays open');
  await load(running());
  const tracker = viewer.document.getElementById('phaseRunTracker');
  assert.match(tracker.textContent, /Detenida por el operador/);
  assert.doesNotMatch(tracker.textContent, /Detener proceso/);
  assert.equal(viewer.viewer('evaluatePhaseExecution', 'fase2', running()).allowed, true, 'the stopped heartbeat no longer blocks');
  assert.equal(viewer.viewer('phaseRunActive'), false);

  const later = running({ en_curso: { fase: 'fase2', agentes: [], inicio: new Date(Date.now() + 60000).toISOString(), stale: false } });
  assert.equal(viewer.viewer('evaluatePhaseExecution', 'fase2', later).allowed, false, 'a new run of the phase counts again');
});

test('declining the stop confirmation sends nothing', async (t) => {
  const { viewer, load } = await harness(t);
  await execute(viewer);
  await load(running());
  viewer.window.__confirm = false;
  viewer.document.querySelector('#phaseRunTracker [data-run-stop]').click();
  await flush();
  assert.ok(!viewer.window.__calls.some(c => c.includes('/interrupt')));
});

test('an agent that stops writing is reported as waiting in the terminal, once per pause', async (t) => {
  const { viewer, load } = await harness(t);
  await execute(viewer);
  // The pause counts from the latest of the send and the last output.
  viewer.window.eval('PHASE_RUN.sentAt = Date.now() - 30000; terminalLastOutputAt = Date.now() - 25000;');
  await load(running());
  const tracker = viewer.document.getElementById('phaseRunTracker');
  assert.match(tracker.textContent, /esperando en la terminal/i);
  const notice = viewer.document.getElementById('phaseRunNotice');
  assert.ok(notice && !notice.hidden, 'a notice is shown');
  assert.match(notice.textContent, /Estado del arte/);
  notice.hidden = true;
  await load(running({ control: { ...envelope().control, mode: 'stepped' } }));
  assert.ok(notice.hidden, 'not repeated during the same pause');

  viewer.window.eval('terminalLastOutputAt = Date.now();');
  await viewer.advance(1100);
  assert.doesNotMatch(tracker.textContent, /esperando en la terminal/i, 'output resumed');
  viewer.window.eval('terminalLastOutputAt = Date.now() - 25000;');
  await viewer.advance(1100);
  assert.ok(!notice.hidden, 'the next pause notifies again');
});

test('a run whose session is gone says so', async (t) => {
  const { viewer, load } = await harness(t);
  await execute(viewer);
  viewer.window.eval(`terminalSessionId = 'other';`);
  await load(running());
  assert.match(viewer.document.getElementById('phaseRunTracker').textContent, /sin sesión/i);
});

test('the execute modal offers the agent and says whether it continues the open session', async (t) => {
  const { viewer } = await harness(t);
  viewer.window.eval(`cachedTerminalAgents = [{ id: 'claude', installed: true }, { id: 'opencode', installed: true }, { id: 'pi', installed: false }, { id: 'shell', installed: true }];`);
  await viewer.viewer('runPhaseExecution', 'fase2');
  const select = viewer.document.getElementById('phaseExecAgent');
  assert.ok(select, 'there is an agent picker');
  assert.deepEqual(Array.from(select.options).map(o => o.value), ['claude', 'opencode'], 'only installed agents that run the framework commands');
  assert.equal(select.value, 'claude', 'defaults to the open session');
  const note = viewer.document.getElementById('phaseExecAgentNote');
  assert.match(note.textContent, /Sigue en la sesión abierta de Claude Code/);

  select.value = 'opencode';
  select.dispatchEvent(new viewer.window.Event('change'));
  assert.match(note.textContent, /Cierra la sesión abierta de Claude Code/);
  select.value = 'claude';
  const fresh = viewer.document.getElementById('phaseExecFresh');
  fresh.checked = true;
  fresh.dispatchEvent(new viewer.window.Event('change'));
  assert.match(note.textContent, /abre una nueva/);
});

test('choosing another agent asks before closing the session; declining keeps the modal open', async (t) => {
  const { viewer } = await harness(t);
  viewer.window.eval(`cachedTerminalAgents = [{ id: 'claude', installed: true }, { id: 'opencode', installed: true }];`);
  await viewer.viewer('runPhaseExecution', 'fase2');
  viewer.document.getElementById('phaseExecAgent').value = 'opencode';
  viewer.window.__confirm = false;
  viewer.document.getElementById('phaseExecConfirmBtn').click();
  await viewer.advance(200);
  await flush();
  assert.deepEqual(Array.from(viewer.window.__sent), []);
  assert.ok(viewer.document.getElementById('phaseExecModal').classList.contains('is-open'));
  const error = viewer.document.getElementById('phaseExecError');
  assert.ok(!error.hidden);
  assert.match(error.textContent, /Se mantuvo la sesión de Claude Code/);
});

test('an agent startup question blocks the send and is explained in a red box', async (t) => {
  const { viewer } = await harness(t);
  viewer.window.eval(`window.__screen = ['Do you trust the files in this folder?', '❯ 1. Yes, I trust this folder', '  2. No, exit'];`);
  await viewer.viewer('runPhaseExecution', 'fase2');
  viewer.document.getElementById('phaseExecConfirmBtn').click();
  await viewer.advance(200);
  await flush();
  assert.deepEqual(Array.from(viewer.window.__sent), [], 'the Enter of the command would answer the question');
  const error = viewer.document.getElementById('phaseExecError');
  assert.ok(error && !error.hidden);
  assert.match(error.textContent, /Yes, I trust this folder/);
  assert.ok(viewer.document.getElementById('phaseExecModal').classList.contains('is-open'));
  assert.equal(viewer.document.getElementById('phaseRunDock')?.hidden ?? true, true, 'no run is followed');
});
