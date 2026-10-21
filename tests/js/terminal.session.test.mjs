/**
 * The dashboard CLI keeps one agent session on the server.
 *
 * The real dashboard JavaScript runs under jsdom with a fake xterm and a fake
 * WebSocket. Each test checks what the page asks the server for (the
 * `?session=` of the WebSocket URL, DELETE and GET calls) and what it does with
 * the server's `session` and `detached` announcements.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const FAKES = `
  window.__sockets = [];
  window.__calls = [];
  window.__confirm = true;
  window.confirm = () => window.__confirm;
  window.Terminal = class {
    constructor() { this.cols = 100; this.rows = 30; this.written = []; this.resets = 0; this.buffer = { active: { viewportY: 0, getLine: (y) => ({ translateToString: () => (window.__screen || [])[y] || '' }) } }; }
    loadAddon() {} open() {} focus() {} onData(fn) { this.__onData = fn; } onBinary() {}
    write(d) { this.written.push(typeof d === 'string' ? d : new TextDecoder().decode(d)); }
    reset() { this.resets += 1; this.written = []; } clear() {}
  };
  window.WebSocket = class {
    constructor(url) { this.url = url; this.readyState = 0; this.sent = []; window.__sockets.push(this); }
    send(d) { this.sent.push(d); } close() { this.readyState = 3; }
  };
  WebSocket.CONNECTING = 0; WebSocket.OPEN = 1; WebSocket.CLOSING = 2; WebSocket.CLOSED = 3;
  window.__open = (sock) => { sock.readyState = 1; sock.onopen && sock.onopen(); };
  window.__hello = (sock, id, agent, reattached) => sock.onmessage({ data: JSON.stringify({ type: 'session', id, agent, reattached }) });
  window.__out = (sock, text) => sock.onmessage({ data: new TextEncoder().encode(text).buffer });
`;

async function harness(t, { sessions = {} } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.TextEncoder = TextEncoder;
  viewer.window.TextDecoder = TextDecoder;
  viewer.window.eval(FAKES);
  viewer.window.fetch = async (url, opts = {}) => {
    const method = (opts && opts.method) || 'GET';
    viewer.window.__calls.push(`${method} ${url}`);
    const m = String(url).match(/\/api\/terminal\/sessions\/([^/]+)(\/interrupt)?$/);
    if (m) {
      const info = sessions[decodeURIComponent(m[1])];
      if (!info) return { ok: false, status: 404, json: async () => ({ ok: false }) };
      if (m[2]) return { ok: true, status: 200, json: async () => ({ ok: true, key: 'esc' }) };
      return { ok: true, status: 200, json: async () => ({ ok: true, alive: true, attached: false, ...info }) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };
  return viewer;
}

const last = (viewer) => viewer.window.__sockets.at(-1);

async function openCli(viewer) {
  viewer.viewer('openMorfeoTerminal');
  await viewer.advance(150);
  const sock = last(viewer);
  viewer.window.__open(sock);
  return sock;
}

test('the announced session is remembered and a reconnect asks for it', async (t) => {
  const viewer = await harness(t);
  viewer.window.eval(`selectedAgent = 'claude';`);
  const sock = await openCli(viewer);
  assert.doesNotMatch(sock.url, /session=/, 'the first connection opens a new session');
  viewer.window.__hello(sock, 'abc123', 'claude', false);
  assert.deepEqual(JSON.parse(viewer.window.localStorage.getItem(`morfeo.terminalSession@${viewer.window.location.host}`)), { id: 'abc123', agent: 'claude' });

  sock.readyState = 3;
  sock.onclose();
  await viewer.advance(700);
  assert.match(last(viewer).url, /session=abc123/, 'a dropped connection reattaches to the same session');
});

test('the replay after a reattach is drawn once and is not counted as activity', async (t) => {
  const viewer = await harness(t);
  viewer.window.eval(`selectedAgent = 'claude';`);
  const sock = await openCli(viewer);
  viewer.window.__out(sock, 'old screen');
  const term = viewer.window.eval('terminalInstance');
  const before = viewer.viewer('terminalActivity').lastOutputAt;
  viewer.window.__hello(sock, 'abc123', 'claude', true);
  assert.ok(term.resets >= 1, 'the screen is cleared before the replay');
  viewer.window.__out(sock, 'replayed output');
  assert.deepEqual(Array.from(term.written), ['replayed output']);
  assert.equal(viewer.viewer('terminalActivity').lastOutputAt, before, 'the replay burst is quiet');
});

test('changing agent with a live session asks first; declining keeps the session', async (t) => {
  const viewer = await harness(t);
  viewer.window.eval(`selectedAgent = 'claude';`);
  const sock = await openCli(viewer);
  viewer.window.__hello(sock, 'abc123', 'claude', false);
  const select = viewer.document.getElementById('terminalAgentSelect');
  select.innerHTML = '<option value="claude">Claude</option><option value="shell">Shell</option>';

  viewer.window.__confirm = false;
  select.value = 'shell';
  viewer.viewer('onTerminalAgentChange');
  assert.equal(select.value, 'claude', 'the picker goes back to the open agent');
  assert.equal(viewer.window.eval('terminalSessionId'), 'abc123');
  assert.ok(!viewer.window.__calls.some(c => c.startsWith('DELETE')));

  viewer.window.__confirm = true;
  select.value = 'shell';
  viewer.viewer('onTerminalAgentChange');
  assert.ok(viewer.window.__calls.includes('DELETE /api/terminal/sessions/abc123'), 'the old session is closed');
  assert.match(last(viewer).url, /agent=shell/);
  assert.doesNotMatch(last(viewer).url, /session=/);
});

test('a reload or a closed tab never ends the session: another tab may be using it', async (t) => {
  const viewer = await harness(t);
  viewer.window.eval(`selectedAgent = 'claude';`);
  const sock = await openCli(viewer);
  viewer.window.__hello(sock, 'abc123', 'claude', false);
  viewer.window.eval(`PHASE_RUN = null;`);
  viewer.window.dispatchEvent(new viewer.window.Event('beforeunload'));
  assert.ok(!viewer.window.__calls.some(c => c.startsWith('DELETE')));
  assert.ok(viewer.window.localStorage.getItem(`morfeo.terminalSession@${viewer.window.location.host}`));
});

test('a session the server ended is forgotten and not reconnected', async (t) => {
  const viewer = await harness(t);
  viewer.window.eval(`selectedAgent = 'claude';`);
  const sock = await openCli(viewer);
  viewer.window.__hello(sock, 'abc123', 'claude', false);
  sock.onmessage({ data: '{"type":"ended"}' });
  const count = viewer.window.__sockets.length;
  sock.readyState = 3;
  sock.onclose();
  await viewer.advance(2000);
  assert.equal(viewer.window.__sockets.length, count, 'no silent new agent');
  assert.equal(viewer.window.eval('terminalSessionId'), null);
  assert.equal(viewer.window.localStorage.getItem(`morfeo.terminalSession@${viewer.window.location.host}`), null);
});

test('after a reload the page reattaches in the background to a live session', async (t) => {
  const viewer = await harness(t, { sessions: { abc123: { id: 'abc123', agent: 'opencode' } } });
  viewer.window.localStorage.setItem(`morfeo.terminalSession@${viewer.window.location.host}`, JSON.stringify({ id: 'abc123', agent: 'opencode' }));
  assert.equal(await viewer.viewer('resumeTerminalSession'), true);
  await viewer.advance(150);
  assert.match(last(viewer).url, /agent=opencode&.*session=abc123/);
  assert.equal(viewer.window.eval('isTerminalOpen'), false, 'the CLI window stays closed');
});

test('a remembered session the server no longer has is forgotten', async (t) => {
  const viewer = await harness(t);
  const key = `morfeo.terminalSession@${viewer.window.location.host}`;
  viewer.window.localStorage.setItem(key, JSON.stringify({ id: 'gone', agent: 'claude' }));
  assert.equal(await viewer.viewer('resumeTerminalSession'), false);
  assert.equal(viewer.window.localStorage.getItem(key), null);
});

test('a tab whose session was taken by another one does not take it back on its own', async (t) => {
  const viewer = await harness(t);
  viewer.window.eval(`selectedAgent = 'claude';`);
  const sock = await openCli(viewer);
  viewer.window.__hello(sock, 'abc123', 'claude', false);
  sock.onmessage({ data: '{"type":"detached","reason":"taken"}' });
  const count = viewer.window.__sockets.length;
  sock.readyState = 3;
  sock.onclose();
  await viewer.advance(2000);
  assert.equal(viewer.window.__sockets.length, count, 'no reconnect loop between tabs');
  assert.match(viewer.window.eval('terminalInstance').written.join(''), /otra pestaña/);
});

test('interrupting posts to the session and keeps it', async (t) => {
  const viewer = await harness(t, { sessions: { abc123: { id: 'abc123', agent: 'claude' } } });
  viewer.window.eval(`terminalSessionId = 'abc123';`);
  const res = await viewer.viewer('interruptTerminalSession');
  assert.deepEqual(JSON.parse(JSON.stringify(res)), { ok: true, key: 'esc' });
  assert.ok(viewer.window.__calls.includes('POST /api/terminal/sessions/abc123/interrupt'));
  assert.equal(viewer.window.eval('terminalSessionId'), 'abc123');
});
