/**
 * Responsive and small functional fixes of the dashboard (audit L3 of
 * odd/tasks/ui-smith-responsive.md).
 *
 * The real dashboard JavaScript runs under jsdom (tests/js/harness.mjs). jsdom
 * has no layout engine, so CSS breakpoints are verified in a real browser; here
 * only the behaviour jsdom can observe is pinned: the active tab is scrolled
 * into view, Escape closes the dialogs, the graph iframe can fire its load
 * event before the main script runs, the MGA tab does not request a file the
 * status says is absent, and the modal buttons have CSS rules.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { JSDOM, VirtualConsole } from 'jsdom';

import { createViewerHarness, flush, readDashboardHtml } from './harness.mjs';

async function harness(t) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const requests = [];
  viewer.window.fetch = async (url) => {
    requests.push(String(url));
    return { ok: false, status: 503, json: async () => ({}), text: async () => '' };
  };
  return { viewer, requests };
}

function spyScrollIntoView(viewer) {
  const calls = [];
  viewer.window.Element.prototype.scrollIntoView = function scrollIntoView(options) {
    calls.push({ el: this, options });
  };
  return calls;
}

function tabButton(viewer, tabId) {
  return Array.from(viewer.document.querySelectorAll('.tab-nav__btn'))
    .find(b => (b.getAttribute('onclick') || '').includes(`navigateTab('${tabId}')`));
}

test('navigateTab scrolls the active tab button into view without moving the page more than needed', async (t) => {
  const { viewer } = await harness(t);
  const calls = spyScrollIntoView(viewer);
  viewer.viewer('navigateTab', 'artifacts');
  const btn = tabButton(viewer, 'artifacts');
  assert.ok(btn.classList.contains('active'));
  const call = calls.find(c => c.el === btn);
  assert.ok(call, 'the active tab button is scrolled into view');
  // The options object comes from the jsdom realm: compare its fields.
  assert.deepEqual({ ...call.options }, { inline: 'nearest', block: 'nearest' });
});

test('the «gates» alias also reveals the Pipeline tab', async (t) => {
  const { viewer } = await harness(t);
  const calls = spyScrollIntoView(viewer);
  viewer.viewer('navigateTab', 'gates');
  const btn = tabButton(viewer, 'pipeline');
  assert.ok(calls.some(c => c.el === btn && c.options && c.options.inline === 'nearest'));
});

test('a deep link to the MGA or trees tab opens and reveals it on load', async (t) => {
  for (const tabId of ['mga', 'trees']) {
    const { viewer } = await harness(t);
    const calls = spyScrollIntoView(viewer);
    viewer.window.history.replaceState(null, '', `#${tabId}`);
    viewer.window.dispatchEvent(new viewer.window.Event('load'));
    await flush();
    assert.ok(viewer.document.getElementById(`pane-${tabId}`).classList.contains('active'), `#${tabId} opens its pane`);
    assert.ok(calls.some(c => c.el === tabButton(viewer, tabId)), `#${tabId} reveals its tab`);
  }
});

test('Escape closes the phase execution modal', async (t) => {
  const { viewer } = await harness(t);
  const modal = viewer.document.getElementById('phaseExecModal');
  modal.classList.add('is-open');
  viewer.document.dispatchEvent(new viewer.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert.equal(modal.classList.contains('is-open'), false);
});

test('Escape closes the CLI tools modal', async (t) => {
  const { viewer } = await harness(t);
  viewer.viewer('showToolsRequiredModal', { ready: false, missing: ['herdr'], herdr: { installed: false } });
  const modal = viewer.document.getElementById('morfeoToolsRequiredModal');
  assert.ok(modal.classList.contains('is-open'));
  viewer.document.dispatchEvent(new viewer.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert.equal(modal.classList.contains('is-open'), false);
});

test('other keys leave the modals open', async (t) => {
  const { viewer } = await harness(t);
  const modal = viewer.document.getElementById('phaseExecModal');
  modal.classList.add('is-open');
  viewer.document.dispatchEvent(new viewer.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  assert.ok(modal.classList.contains('is-open'));
});

test('the graph iframe can fire load before the main script defines syncGraphPause', async () => {
  // The about:blank iframe sits above the scripts and loads while the page is
  // still being parsed: its handler must not throw a ReferenceError then.
  const html = readDashboardHtml().replace(/<script\b(?![^>]*\bsrc=)[^>]*>[\s\S]*?<\/script>/gi, '');
  const errors = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (err) => errors.push(String(err && (err.detail || err.message || err))));
  const dom = new JSDOM(html, { runScripts: 'dangerously', virtualConsole, url: 'http://localhost:8000/' });
  try {
    const iframe = dom.window.document.getElementById('graphIframe');
    assert.ok(iframe, 'the graph iframe exists');
    assert.equal(typeof dom.window.syncGraphPause, 'undefined', 'the main script did not run');
    iframe.dispatchEvent(new dom.window.Event('load'));
    await flush();
    assert.deepEqual(errors.filter(e => /syncGraphPause/.test(e)), []);
  } finally {
    dom.window.close();
  }
});

test('the MGA tab does not request the file when the status says it is absent', async (t) => {
  const { viewer, requests } = await harness(t);
  viewer.window.eval(`currentStatus = { artifacts: [{ rel_path: 'artefactos/insumos.md' }] };`);
  await viewer.viewer('loadMgaResumido');
  await flush();
  assert.equal(requests.filter(u => u.includes('mga_resumido.md')).length, 0, requests.join(', '));
  assert.match(viewer.document.getElementById('mgaContent').textContent, /Aún no hay MGA resumido.*Fase 1/s);
});

test('the MGA tab requests the file when the status lists it', async (t) => {
  const { viewer, requests } = await harness(t);
  viewer.window.eval(`currentStatus = { artifacts: [{ rel_path: 'artefactos/mga_resumido.md' }] };`);
  await viewer.viewer('loadMgaResumido');
  await flush();
  assert.ok(requests.some(u => u.includes('mga_resumido.md')), requests.join(', '));
});

test('the modal footer buttons (.btn-secondary, .btn-primary) have CSS rules', async (t) => {
  const { viewer } = await harness(t);
  const selectors = [];
  for (const sheet of Array.from(viewer.document.styleSheets)) {
    for (const rule of Array.from(sheet.cssRules || [])) {
      if (rule.selectorText) selectors.push(rule.selectorText);
    }
  }
  for (const cls of ['.btn-secondary', '.btn-primary']) {
    assert.ok(selectors.some(s => s.split(',').some(part => part.trim() === cls)), `${cls} has a rule`);
  }
  assert.ok(viewer.document.querySelector('#phaseExecModal .btn-secondary'), 'the phase modal uses .btn-secondary');
});
