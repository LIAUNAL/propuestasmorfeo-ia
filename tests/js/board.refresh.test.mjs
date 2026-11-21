/**
 * «⟳ Actualizar tablero» and the #boardStatus report (odd/tasks/ui-smith-responsive.md, S3, T3).
 *
 * The real dashboard runs under jsdom. The harness inlines only the local
 * scripts its LOCAL_SCRIPT_TAG names, so this file evaluates the real
 * static/board-refresh.js in the page's window after it loads, with fetch
 * doubled; nothing of the script is re-implemented here.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { createViewerHarness, DASHBOARD_STATIC, flush } from './harness.mjs';

const BOARD_SCRIPT = readFileSync(path.join(DASHBOARD_STATIC, 'board-refresh.js'), 'utf8');

function json(status, payload) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload, text: async () => JSON.stringify(payload) };
}

function summary(overrides = {}) {
  return {
    active_run: '2026-01-demo',
    current: { id: 'fase1a', name: 'Scoping temprano', state: 'partial', verdict: 'PENDING', gate: 'G1a' },
    missing: ['Compuerta G1a en PASS'],
    open_gates: [{ id: 'G1a', name: 'Scoping', status: 'PENDING', phase: 'Fase 1a' }],
    failed_gates: [],
    failed_artifacts: [],
    units_completed: 1,
    units_total: 3,
    gates_passed: 1,
    gates_total: 2,
    next_step: 'fase1a',
    next_command: '/propuesta-continuar',
    tone: 'info',
    last_refresh: null,
    ...overrides,
  };
}

/** A page with board-refresh.js loaded and `routes(url, init)` answering fetch. */
async function boardPage(t, routes) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const calls = [];
  viewer.window.fetch = async (url, init) => {
    calls.push({ url: String(url), method: (init && init.method) || 'GET' });
    const answer = routes(String(url), init);
    return answer || json(503, {});
  };
  try { viewer.window.sessionStorage.clear(); } catch (_) { /* storage blocked */ }
  viewer.window.eval(BOARD_SCRIPT);
  await flush();
  return { viewer, calls, document: viewer.document, window: viewer.window };
}

test('the topbar carries «⟳ Actualizar tablero» and the status panel', async (t) => {
  const { document } = await boardPage(t, () => null);
  const button = document.getElementById('boardRefreshBtn');
  assert.ok(button, 'the refresh button exists');
  assert.match(button.textContent, /Actualizar tablero/);
  assert.equal(button.getAttribute('onclick'), 'refreshBoard()');
  const panel = document.getElementById('boardStatus');
  assert.ok(panel, 'the #boardStatus panel exists');
  assert.equal(panel.closest('main') !== null, true, 'the panel sits in the main area');
  assert.ok(document.querySelector('script[src="/static/board-refresh.js"]'), 'the page loads board-refresh.js');
});

test('the button posts the refresh and the panel reports the current unit and the next command', async (t) => {
  const result = { ok: true, finished_at: '2026-11-20T10:00:01Z', artifacts: [], summary: summary() };
  const { window, document, calls } = await boardPage(t, (url, init) =>
    (url === '/api/board/refresh' && init && init.method === 'POST' ? json(200, result) : null));
  await window.refreshBoard();
  await flush();
  assert.ok(calls.some((c) => c.url === '/api/board/refresh' && c.method === 'POST'));
  const panel = document.getElementById('boardStatus');
  assert.equal(panel.hidden, false);
  assert.equal(panel.dataset.tone, 'info');
  assert.match(panel.textContent, /Estado actual: fase1a · Scoping temprano/);
  assert.match(panel.textContent, /Pasos que aún faltan/);
  assert.match(panel.textContent, /Compuerta G1a en PASS/);
  assert.match(panel.textContent, /Siguiente: \/propuesta-continuar/);
  assert.ok(calls.some((c) => c.url.startsWith('/api/status')), 'the panels reload with loadStatus');
});

test('the message escapes what the run wrote', async (t) => {
  const { window } = await boardPage(t, () => null);
  const { html } = window.boardRefresh.message({
    summary: summary({
      current: { id: 'fase1a', name: '<img src=x onerror=alert(1)>', state: 'partial' },
      missing: ['<script>alert(2)</script>'],
      next_command: '/x "<b>"',
    }),
  }, 'manual');
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /<script>alert/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /&lt;script&gt;alert\(2\)&lt;\/script&gt;/);
  assert.match(html, /&quot;&lt;b&gt;&quot;/);
});

test('the pending list shows at most six steps', async (t) => {
  const { window, document } = await boardPage(t, () => null);
  const missing = Array.from({ length: 9 }, (_v, i) => `paso ${i + 1}`);
  window.boardRefresh.render({ summary: summary({ missing }) }, 'manual');
  const items = [...document.querySelectorAll('#boardStatus .board-status__missing li')].map((li) => li.textContent);
  assert.equal(items.length, 7, 'six steps plus the «…y N más» line');
  assert.deepEqual(items.slice(0, 6), missing.slice(0, 6));
  assert.match(items[6], /…y 3 más/);
});

test('«Siguiente» sends next_command to the embedded terminal', async (t) => {
  const { window, document } = await boardPage(t, () => null);
  const sent = [];
  window.sendTerminalQuickCommand = (cmd) => sent.push(cmd);
  window.boardRefresh.render({ summary: summary({ next_command: '/propuesta-continuar' }) }, 'manual');
  const next = document.querySelector('#boardStatus [data-board-next]');
  assert.ok(next, 'the «Siguiente» button is there');
  next.click();
  assert.deepEqual(sent, ['/propuesta-continuar']);
});

test('without a next command there is no «Siguiente» button', async (t) => {
  const { window, document } = await boardPage(t, () => null);
  window.boardRefresh.render({ summary: summary({ next_command: null, tone: 'done', current: null, missing: [] }) }, 'manual');
  assert.equal(document.querySelector('#boardStatus [data-board-next]'), null);
  assert.equal(document.getElementById('boardStatus').dataset.tone, 'done');
});

test('a refresh already running is reported as busy', async (t) => {
  const { window, document } = await boardPage(t, (url) =>
    (url === '/api/board/refresh' ? json(409, { ok: false, busy: true }) : null));
  await window.refreshBoard();
  await flush();
  const panel = document.getElementById('boardStatus');
  assert.equal(panel.dataset.tone, 'warn');
  assert.match(panel.textContent, /en curso/);
  assert.equal(document.getElementById('boardRefreshBtn').disabled, false);
});

test('the start-up refresh is polled every 3 s while it runs and polling stops when done', async (t) => {
  let summaryCalls = 0;
  const finished = { ok: true, finished_at: '2026-11-20T10:00:05Z', artifacts: [], summary: summary() };
  const { viewer, document } = await boardPage(t, (url) => {
    if (url !== '/api/board/summary') return null;
    summaryCalls += 1;
    return summaryCalls < 3
      ? json(200, { summary: summary(), last_refresh: null, refreshing: true })
      : json(200, { summary: summary(), last_refresh: finished, refreshing: false });
  });
  assert.equal(summaryCalls, 1);
  assert.match(document.getElementById('boardStatus').textContent, /actualizando el tablero/);
  await viewer.advance(3000);
  await flush();
  assert.equal(summaryCalls, 2);
  await viewer.advance(3000);
  await flush();
  assert.equal(summaryCalls, 3);
  assert.match(document.getElementById('boardStatus').textContent, /actualizado al iniciar morfeo ui/);
  await viewer.advance(9000);
  await flush();
  assert.equal(summaryCalls, 3, 'no more polling once the refresh finished');
});

test('the start-up refresh is shown once per server run', async (t) => {
  const finished = { ok: true, finished_at: '2026-11-20T10:00:05Z', artifacts: [], summary: summary() };
  const { window, document } = await boardPage(t, (url) =>
    (url === '/api/board/summary' ? json(200, { summary: summary(), last_refresh: finished, refreshing: false }) : null));
  const panel = document.getElementById('boardStatus');
  assert.equal(panel.hidden, false);
  panel.hidden = true;
  await window.boardRefresh.showStartup(0);
  await flush();
  assert.equal(panel.hidden, true, 'the same start-up refresh is not reported again');
});

test('the footer warns when the server is older than the installed package', async (t) => {
  const { window, document } = await boardPage(t, () => null);
  const stale = document.getElementById('footerStaleServer');
  assert.ok(stale);
  window.renderFooterVersion({ package_version: '0.8.0', version: '0.8.0', stale_server: true,
    server_version: '0.8.0', installed_version: '0.9.0' });
  assert.equal(stale.hidden, false);
  assert.match(stale.textContent, /El servidor corre una versión anterior/);
  assert.equal(stale.textContent, 'El servidor corre una versión anterior: reinicia `morfeo ui`');
  assert.match(stale.title, /0\.8\.0.*0\.9\.0/);
  window.renderFooterVersion({ package_version: '0.8.0', version: '0.8.0', stale_server: false });
  assert.equal(stale.hidden, true);
});
