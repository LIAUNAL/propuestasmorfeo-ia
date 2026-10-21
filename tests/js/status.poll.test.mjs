/**
 * The dashboard polls and repaints only as much as it needs.
 *
 * The real dashboard runs under jsdom with a manual clock and a counted
 * `/api/status`. The tests check four things:
 * - one request at a time;
 * - one self-rescheduling poll that stops while the page is hidden;
 * - a phase tracker that is not rebuilt when nothing changed;
 * - a live terminal that is not refitted on every poll.
 * They also pin the cheaper animations in the stylesheet.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

function envelope(overrides = {}) {
  return {
    active_run: '2026-01-demo', run_details: { id: '2026-01-demo', insumos_count: 1 },
    pipeline_units: [{ id: 'fase2', kind: 'step', name: 'Estado del arte', gate: 'G2', sections: ['04'], agents: [], next: 'done' }],
    gates: [], telemetria: [], sections: [], artifacts: [], en_curso: null,
    control: { mode: 'stepped', next_step: 'fase2', intake_complete: true },
    unit_progress: { fase2: { state: 'pending', checks: [], missing: [], artifacts: [] } },
    ...overrides,
  };
}

async function harness(t) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const state = { calls: 0, data: envelope(), release: null };
  viewer.window.fetch = async (url) => {
    if (String(url).includes('/api/status')) {
      state.calls += 1;
      if (state.hold) await new Promise((r) => { state.release = r; });
      return { ok: true, status: 200, json: async () => state.data };
    }
    return { ok: true, status: 200, json: async () => ({}), text: async () => '' };
  };
  // jsdom may fire the page load (one status request and the first schedule)
  // after the harness returns: let it happen before counting.
  await viewer.advance(0);
  await flush();
  state.calls = 0;
  return { viewer, state };
}

test('a poll while another request is in flight reuses it', async (t) => {
  const { viewer, state } = await harness(t);
  state.hold = true;
  const a = viewer.viewer('loadStatus');
  const b = viewer.viewer('loadStatus');
  await flush();
  assert.equal(state.calls, 1, 'one request on the wire');
  state.hold = false;
  state.release();
  await Promise.all([a, b]);
});

test('the poll reschedules itself every 5 s and stops while the page is hidden', async (t) => {
  const { viewer, state } = await harness(t);
  viewer.viewer('scheduleStatusPoll');
  await viewer.advance(4900);
  assert.equal(state.calls, 0);
  await viewer.advance(200);
  await flush();
  assert.equal(state.calls, 1);
  await viewer.advance(5000);
  await flush();
  assert.equal(state.calls, 2, 'rescheduled after the request');

  Object.defineProperty(viewer.document, 'hidden', { configurable: true, get: () => true });
  await viewer.advance(20000);
  await flush();
  assert.equal(state.calls, 2, 'nothing while hidden');
});

test('a running phase polls every 2 s', async (t) => {
  const { viewer, state } = await harness(t);
  viewer.window.eval(`PHASE_RUN = { unit: 'fase2', command: '/propuesta-continuar', sentAt: Date.now(), initialState: 'pending', finished: false };`);
  viewer.viewer('scheduleStatusPoll');
  await viewer.advance(2100);
  await flush();
  assert.equal(state.calls, 1);
});

test('an unchanged poll does not rebuild the phase tracker', async (t) => {
  const { viewer } = await harness(t);
  viewer.window.eval(`PHASE_RUN = { unit: 'fase2', command: '/propuesta-continuar', sentAt: Date.now(), initialState: 'pending', finished: false };`);
  await viewer.viewer('loadStatus');
  const first = viewer.document.querySelector('#phaseRunTracker .phase-run__head');
  assert.ok(first);
  await viewer.viewer('loadStatus');
  assert.equal(viewer.document.querySelector('#phaseRunTracker .phase-run__head'), first, 'same node: not rebuilt');
});

test('a poll does not refit a connected terminal', async (t) => {
  const { viewer } = await harness(t);
  viewer.window.eval(`window.__ensure = 0; isTerminalOpen = true; terminalSocket = { readyState: 1, send() {} }; ensureTerminalConnected = () => { window.__ensure += 1; };`);
  await viewer.viewer('loadStatus');
  assert.equal(viewer.window.__ensure, 0);
  viewer.window.eval(`terminalSocket = { readyState: 3, send() {} };`);
  await viewer.viewer('loadStatus');
  assert.equal(viewer.window.__ensure, 1, 'a dropped terminal is reconnected');
});

test('the neon pulse animates opacity, not box-shadow, and the spinner has its keyframes', async (t) => {
  const { viewer } = await harness(t);
  const css = Array.from(viewer.document.querySelectorAll('style')).map((s) => s.textContent).join('\n');
  const neon = css.match(/@keyframes neon-pulse\s*\{([\s\S]*?)\}\s*\}/);
  assert.ok(neon, 'neon-pulse keyframes exist');
  assert.match(neon[1], /opacity/);
  assert.doesNotMatch(neon[1], /box-shadow/);
  assert.match(css, /@keyframes spin\s*\{/);
  assert.doesNotMatch(css, /execute-glow/, 'no animation without keyframes');
});

test('a hidden page pauses the looping animations', async (t) => {
  const { viewer } = await harness(t);
  Object.defineProperty(viewer.document, 'hidden', { configurable: true, get: () => true });
  viewer.document.dispatchEvent(new viewer.window.Event('visibilitychange'));
  assert.ok(viewer.document.documentElement.classList.contains('is-page-hidden'));
  Object.defineProperty(viewer.document, 'hidden', { configurable: true, get: () => false });
  viewer.document.dispatchEvent(new viewer.window.Event('visibilitychange'));
  assert.ok(!viewer.document.documentElement.classList.contains('is-page-hidden'));
});

test('a fresh reload after a change waits for the in-flight request and asks again', async (t) => {
  const { viewer, state } = await harness(t);
  state.hold = true;
  state.data = envelope({ active_run: 'old' });
  const polling = viewer.viewer('loadStatus');
  await flush();
  const after = viewer.viewer('loadStatus', { fresh: true });
  state.data = envelope({ active_run: 'new' });
  state.hold = false;
  state.release();
  await polling;
  await after;
  assert.equal(state.calls, 2, 'a second request after the stale one');
  assert.equal(viewer.window.eval('currentStatus.active_run'), 'new');
});

test('a hung status request is aborted and polling goes on', async (t) => {
  const { viewer, state } = await harness(t);
  viewer.window.fetch = (url, opts = {}) => {
    if (!String(url).includes('/api/status')) return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    state.calls += 1;
    if (state.calls === 1) {
      return new Promise((_, reject) => opts.signal.addEventListener('abort', () => reject(new Error('aborted'))));
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => state.data });
  };
  const hung = viewer.viewer('loadStatus');
  await viewer.advance(15100);
  await hung;
  await viewer.viewer('loadStatus');
  assert.equal(state.calls, 2, 'the next poll makes a new request');
});

test('re-sending the same phase restarts the tracker clock', async (t) => {
  const { viewer } = await harness(t);
  const first = viewer.window.eval('Date.now() - 5000');
  viewer.window.eval(`PHASE_RUN = { unit: 'fase2', command: '/propuesta-continuar', sentAt: ${first}, initialState: 'pending', finished: false };`);
  await viewer.viewer('loadStatus');
  const second = first + 4000;
  viewer.window.eval(`PHASE_RUN.sentAt = ${second};`);
  viewer.viewer('renderPhaseRunTracker', viewer.window.eval('currentStatus'));
  assert.ok(viewer.document.querySelector(`#phaseRunTracker [data-elapsed-from="${second}"]`), 'the tracker shows the new send');
});
