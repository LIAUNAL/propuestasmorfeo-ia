/**
 * «Activar CLI» and the non-blocking CLI alerts of the dashboard.
 *
 * The real dashboard JavaScript (index.html + static/cli-console.js) runs
 * under jsdom with a fake xterm, a fake WebSocket and a fake server behind
 * `fetch`. The tests check what the page asks the server for: activation only
 * on a click, the polling until the browser is authorized, the external-launch
 * button and notice when tools are missing, disabled agents that are not
 * installed and the quick commands the server lists.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const FAKES = `
  window.__sockets = [];
  window.Terminal = class {
    constructor() { this.cols = 100; this.rows = 30; this.written = []; this.buffer = { active: { viewportY: 0, getLine: () => null } }; }
    loadAddon() {} open() {} focus() {} onData() {} onBinary() {}
    write(d) { this.written.push(typeof d === 'string' ? d : new TextDecoder().decode(d)); }
    reset() { this.written = []; } clear() {}
  };
  window.WebSocket = class {
    constructor(url) { this.url = url; this.readyState = 0; this.sent = []; window.__sockets.push(this); }
    send(d) { this.sent.push(d); } close() { this.readyState = 3; }
  };
  WebSocket.CONNECTING = 0; WebSocket.OPEN = 1; WebSocket.CLOSING = 2; WebSocket.CLOSED = 3;
`;

const AGENTS = [
  { id: 'herdr', name: 'Herdr (Workspace Manager)', installed: true, available: true },
  { id: 'claude', name: 'Claude Code', installed: false, available: false },
  { id: 'shell', name: 'Shell Zsh / Bash', installed: true, available: true },
];
const QUICK = [
  { name: '/compilar-pdf', description: 'Compila la propuesta a PDF.' },
  { name: '/propuesta-continuar', description: 'Avanza una unidad.' },
];
const READY_TOOLS = { ready: true, preferred_terminal: 'ghostty', missing: [], herdr: { installed: true }, monitored_path: '/ws' };

async function harness(t, server = {}) {
  const state = {
    authorized: false,
    authorizeAfterPolls: Infinity,
    activateOrigin: null,
    tools: READY_TOOLS,
    calls: [],
    polls: 0,
    ...server,
  };
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.TextEncoder = TextEncoder;
  viewer.window.TextDecoder = TextDecoder;
  viewer.window.eval(FAKES);
  const reply = (status, body) => ({ ok: status < 400, status, json: async () => body, text: async () => JSON.stringify(body) });
  viewer.window.fetch = async (url, opts = {}) => {
    const method = (opts && opts.method) || 'GET';
    const path = String(url);
    state.calls.push(`${method} ${path}`);
    if (path === '/api/terminal/agents') {
      if (state.activated) {
        state.polls += 1;
        if (state.polls >= state.authorizeAfterPolls) state.authorized = true;
      }
      return reply(200, {
        ok: true, enabled: true, authorized: state.authorized,
        agents: state.authorized ? AGENTS : [], default: 'herdr', quick: QUICK,
      });
    }
    if (path === '/api/terminal/activate' && method === 'POST') {
      state.activated = true;
      return reply(200, { ok: true, opened: true, origin: state.activateOrigin || viewer.window.location.origin });
    }
    if (path === '/api/terminal/tools') {
      if (!state.authorized) return reply(401, { ok: false, error: 'no activado' });
      return reply(200, { ok: true, tools: state.tools });
    }
    if (path.startsWith('/api/terminal/sessions/')) {
      return state.authorized ? reply(404, { ok: false }) : reply(401, { ok: false });
    }
    return reply(200, {});
  };
  if (viewer.document.readyState !== 'complete') {
    await new Promise((resolve) => viewer.window.addEventListener('load', resolve, { once: true }));
  }
  await flush(10);
  return { viewer, state };
}

const posts = (state, path) => state.calls.filter((c) => c === `POST ${path}`).length;

test('loading the page never POSTs activate and shows the red banner', async (t) => {
  const { viewer, state } = await harness(t);
  await viewer.advance(5000);
  await flush(10);
  assert.equal(posts(state, '/api/terminal/activate'), 0, 'activation only happens on a click');
  const banner = viewer.document.getElementById('cliActivationBanner');
  assert.ok(banner, 'the banner is shown when the server says not authorized');
  assert.match(banner.textContent, /El CLI del tablero no está activado/);
  const button = viewer.document.getElementById('cliActivateBtn');
  assert.equal(button.textContent, 'Activar CLI');
  assert.equal(viewer.window.__sockets.length, 0, 'no WebSocket is opened without authorization');
});

test('opening the CLI unauthorized opens no WebSocket and keeps the banner', async (t) => {
  const { viewer, state } = await harness(t);
  viewer.document.getElementById('cliActivationBanner').remove();
  viewer.viewer('toggleMorfeoTerminal');
  await viewer.advance(2000);
  await flush(10);
  assert.ok(viewer.document.getElementById('morfeoTerminalWindow').classList.contains('is-open'));
  assert.equal(viewer.window.__sockets.length, 0, 'no WebSocket, so no reconnect loop');
  assert.ok(viewer.document.getElementById('cliActivationBanner'), 'the banner comes back');
  assert.equal(posts(state, '/api/terminal/activate'), 0);
});

test('clicking «Activar CLI» POSTs once and polls every 0.7 s until authorized', async (t) => {
  const { viewer, state } = await harness(t, { authorizeAfterPolls: 3 });
  const button = viewer.document.getElementById('cliActivateBtn');
  button.click();
  button.click();
  await flush(10);
  assert.equal(posts(state, '/api/terminal/activate'), 1, 'a second click while activating does not POST again');
  const pollsBefore = state.polls;
  await viewer.advance(699);
  await flush(10);
  assert.equal(state.polls, pollsBefore, 'nothing before 0.7 s');
  for (let i = 0; i < 3; i += 1) {
    await viewer.advance(700);
    await flush(10);
  }
  assert.equal(state.polls, 3);
  assert.equal(viewer.document.getElementById('cliActivationBanner'), null, 'the banner goes away');
  await viewer.advance(2000);
  await flush(10);
  assert.equal(state.polls, 3, 'polling stops once authorized');
  assert.ok(viewer.document.getElementById('morfeoTerminalWindow').classList.contains('is-open'), 'the session opens');
  assert.ok(viewer.window.__sockets.length >= 1, 'the WebSocket connects after activation');
  assert.equal(posts(state, '/api/terminal/activate'), 1);
});

test('activation gives up after 45 s of polling', async (t) => {
  const { viewer, state } = await harness(t);
  viewer.document.getElementById('cliActivateBtn').click();
  await flush(10);
  for (let i = 0; i < 70; i += 1) {
    await viewer.advance(700);
    await flush(4);
  }
  assert.equal(state.polls, Math.ceil(45000 / 700));
  await viewer.advance(5000);
  await flush(10);
  assert.equal(state.polls, Math.ceil(45000 / 700), 'no polling after the deadline');
  assert.match(viewer.document.getElementById('cliActivationBanner').textContent, /morfeo ui/);
});

test('a tab under another name is told where the cookie lives and does not poll', async (t) => {
  const { viewer, state } = await harness(t, { activateOrigin: 'http://127.0.0.1:8000' });
  viewer.document.getElementById('cliActivateBtn').click();
  await flush(10);
  await viewer.advance(3000);
  await flush(10);
  assert.equal(state.polls, 0);
  const link = viewer.document.querySelector('#cliActivationBanner a');
  assert.ok(link, 'a link to the activated origin');
  assert.equal(link.getAttribute('href'), 'http://127.0.0.1:8000/');
});

test('missing tools keep the embedded terminal open and only disable the external button', async (t) => {
  const { viewer } = await harness(t, {
    authorized: true,
    tools: { ready: false, preferred_terminal: null, missing: ['herdr', 'terminal'], herdr: { installed: false }, ghostty: { installed: false }, wezterm: { installed: false } },
  });
  viewer.viewer('toggleMorfeoTerminal');
  await viewer.advance(500);
  await flush(10);
  const win = viewer.document.getElementById('morfeoTerminalWindow');
  assert.ok(win.classList.contains('is-open'), 'the embedded terminal stays open');
  assert.ok(!viewer.document.getElementById('morfeoToolsRequiredModal').classList.contains('is-open'), 'no blocking modal');
  const btn = viewer.document.getElementById('btnLaunchExternalTerm');
  assert.equal(btn.disabled, true);
  assert.match(btn.title, /Herdr/);
  assert.match(btn.title, /Ghostty o WezTerm/);
  const notice = viewer.document.getElementById('cliToolsNotice');
  assert.ok(notice, 'a dismissible notice');
  assert.match(notice.textContent, /brew install --cask ghostty/);
  notice.querySelector('button').click();
  assert.equal(viewer.document.getElementById('cliToolsNotice'), null, 'the notice can be dismissed');
  assert.ok(viewer.window.__sockets.length >= 1, 'the embedded session still connects');
});

test('on Linux the notice gives a generic emulator hint', async (t) => {
  const { viewer } = await harness(t, {
    authorized: true,
    tools: { ready: false, preferred_terminal: null, missing: ['terminal emulator'], herdr: { installed: true } },
  });
  viewer.viewer('toggleMorfeoTerminal');
  await viewer.advance(500);
  await flush(10);
  const notice = viewer.document.getElementById('cliToolsNotice');
  assert.match(notice.textContent, /instala un emulador de terminal \(GNOME Terminal, Konsole, Ghostty o WezTerm\)/);
  assert.doesNotMatch(notice.textContent, /brew install --cask ghostty/);
  viewer.window.showToolsRequiredModal({ ready: false, missing: ['terminal emulator'], herdr: { installed: true } });
  const body = viewer.document.getElementById('morfeoToolsModalBody').textContent;
  assert.match(body, /instala un emulador de terminal \(GNOME Terminal, Konsole, Ghostty o WezTerm\)/);
  assert.doesNotMatch(body, /brew install --cask ghostty/);
});

for (const [pref, label] of [['gnome-terminal', 'GNOME Terminal'], ['konsole', 'Konsole'], ['x-terminal-emulator', 'Terminal'], ['wezterm', 'WezTerm'], ['ghostty', 'Ghostty']]) {
  test(`the external button names ${label}`, async (t) => {
    const { viewer } = await harness(t, {
      authorized: true,
      tools: { ready: true, preferred_terminal: pref, missing: [], herdr: { installed: true } },
    });
    const btn = viewer.document.getElementById('btnLaunchExternalTerm');
    assert.equal(btn.textContent, `🖥️ ${label}`);
    assert.equal(btn.disabled, false);
    assert.match(btn.title, new RegExp(label));
  });
}

test('agents whose CLI is not installed are disabled', async (t) => {
  const { viewer } = await harness(t, { authorized: true });
  const select = viewer.document.getElementById('terminalAgentSelect');
  const claude = [...select.options].find((o) => o.value === 'claude');
  assert.equal(claude.disabled, true);
  assert.match(claude.textContent, /\(no instalado\)/);
  const herdr = [...select.options].find((o) => o.value === 'herdr');
  assert.equal(herdr.disabled, false);
});

test('quick commands come from the server list', async (t) => {
  const { viewer } = await harness(t, { authorized: true });
  const select = viewer.document.getElementById('terminalQuickSelect');
  assert.ok(select, 'a quick-command picker');
  const values = [...select.options].map((o) => o.value).filter(Boolean);
  assert.deepEqual(values, ['/compilar-pdf', '/propuesta-continuar']);
  assert.equal([...select.options].find((o) => o.value === '/compilar-pdf').title, 'Compila la propuesta a PDF.');
  const hardCoded = [...viewer.document.querySelectorAll('.terminal-footer-actions button')]
    .filter((b) => /sendTerminalQuickCommand/.test(b.getAttribute('onclick') || ''));
  assert.equal(hardCoded.length, 0, 'the hard-coded shortcuts are replaced');

  viewer.window.eval(`window.__sent = []; sendTerminalQuickCommand = (cmd) => window.__sent.push(cmd);`);
  select.value = '/propuesta-continuar';
  select.dispatchEvent(new viewer.window.Event('change'));
  assert.deepEqual(Array.from(viewer.window.__sent), ['/propuesta-continuar']);
  assert.equal(select.value, '', 'the picker resets');
});

test('a language switch labels the banner and its note again', async (t) => {
  const { viewer } = await harness(t, { activateOrigin: 'http://127.0.0.1:8000' });
  viewer.document.getElementById('cliActivateBtn').click();
  await flush(10);
  const banner = viewer.document.getElementById('cliActivationBanner');
  const spanish = banner.innerHTML;
  viewer.window.i18n.setLanguage('en');
  assert.match(banner.textContent, /The board's CLI is not activated/);
  assert.equal(viewer.document.getElementById('cliActivateBtn').textContent, 'Activate CLI');
  assert.match(banner.querySelector('#cliActivationNote').textContent, /^The CLI activates at another address; open the board at/);
  assert.equal(banner.querySelector('#cliActivationNote a').getAttribute('href'), 'http://127.0.0.1:8000/');
  assert.equal(viewer.document.getElementById('cliActivationClose').title, 'Hide notice');
  viewer.window.i18n.setLanguage('es');
  await flush(10);
  assert.equal(banner.innerHTML, spanish);
});

test('a language switch labels the tools notice, the selectors and the external button again', async (t) => {
  const { viewer } = await harness(t, {
    authorized: true,
    tools: { ready: false, preferred_terminal: null, missing: ['herdr', 'terminal'], herdr: { installed: false } },
  });
  viewer.viewer('toggleMorfeoTerminal');
  await viewer.advance(500);
  await flush(10);
  viewer.window.i18n.setLanguage('en');
  const notice = viewer.document.getElementById('cliToolsNotice');
  assert.match(notice.textContent, /The embedded CLI works; the external terminal is unavailable because Herdr and Ghostty or WezTerm is missing/);
  assert.equal(viewer.document.getElementById('btnLaunchExternalTerm').title, 'Unavailable: Herdr and Ghostty or WezTerm is missing');
  const claude = [...viewer.document.getElementById('terminalAgentSelect').options].find((o) => o.value === 'claude');
  assert.match(claude.textContent, /\(not installed\)$/);
  const quick = viewer.document.getElementById('terminalQuickSelect');
  assert.equal(quick.options[0].textContent, 'Commands…');
  assert.equal(quick.getAttribute('aria-label'), 'Quick commands');
  assert.match(viewer.document.getElementById('terminalStatusDot').title, /^(Connected to|Connecting to|Disconnected)/);
  viewer.window.i18n.setLanguage('es');
  await flush(10);
  assert.match(viewer.document.getElementById('cliToolsNotice').textContent, /El CLI embebido funciona/);
  assert.equal(quick.options[0].textContent, 'Comandos…');
});
