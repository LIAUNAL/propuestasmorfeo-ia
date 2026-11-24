/**
 * Text-size control of the dashboard (S1 of odd/tasks/idioma-tablero-traduccion.md).
 *
 * `static/text-size.js` scales the root font size (×1, ×1.25, ×1.5, ×2), so
 * every rem of the page grows with it. It runs in <head>, before the body is
 * drawn, remembers the choice per browser and announces it with a
 * `textscalechange` event (the terminal refits its font on it).
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { JSDOM } from 'jsdom';

import { DASHBOARD_INDEX, DASHBOARD_STATIC, readDashboardHtml } from './harness.mjs';

const SCRIPT = readFileSync(path.join(DASHBOARD_STATIC, 'text-size.js'), 'utf8');
const RAW = readFileSync(DASHBOARD_INDEX, 'utf8');

function run(t, { saved, body = '' } = {}) {
  const dom = new JSDOM(`<!DOCTYPE html><html><head></head><body>${body}</body></html>`, {
    runScripts: 'dangerously',
    url: 'http://localhost:8000/',
  });
  t.after(() => dom.window.close());
  if (saved !== undefined) dom.window.localStorage.setItem('morfeo.textScale', saved);
  dom.window.eval(SCRIPT);
  return dom.window;
}

const SELECT = `<select id="textSizeSelect">
  <option value="1">A ×1</option><option value="1.25">A ×1.25</option>
  <option value="1.5">A ×1.5</option><option value="2">A ×2</option></select>`;

test('without a saved choice the page is drawn at ×1', (t) => {
  const window = run(t);
  const root = window.document.documentElement;
  assert.equal(root.style.getPropertyValue('--text-scale'), '1');
  assert.equal(root.dataset.textScale, '1');
});

test('a saved scale is applied before the body exists', (t) => {
  for (const scale of ['1', '1.25', '1.5', '2']) {
    const window = run(t, { saved: scale });
    assert.equal(window.document.documentElement.style.getPropertyValue('--text-scale'), scale);
    assert.equal(window.document.documentElement.dataset.textScale, scale);
  }
});

test('an unknown saved value falls back to ×1', (t) => {
  for (const bad of ['3', 'abc', '', '0.5']) {
    const window = run(t, { saved: bad });
    assert.equal(window.document.documentElement.dataset.textScale, '1', bad);
  }
});

test('setTextScale persists the scale, syncs the selector and announces it', (t) => {
  const window = run(t, { body: SELECT });
  window.document.dispatchEvent(new window.Event('DOMContentLoaded'));
  const events = [];
  window.document.addEventListener('textscalechange', (e) => events.push(e.detail.scale));
  assert.equal(window.setTextScale('1.5'), '1.5');
  assert.equal(window.localStorage.getItem('morfeo.textScale'), '1.5');
  assert.equal(window.document.getElementById('textSizeSelect').value, '1.5');
  assert.equal(window.document.documentElement.style.getPropertyValue('--text-scale'), '1.5');
  assert.equal(window.setTextScale('7'), '1', 'an invalid scale resets to ×1');
  assert.equal(window.localStorage.getItem('morfeo.textScale'), '1');
  assert.deepEqual(events, ['1.5', '1']);
});

test('choosing an option in the selector applies and remembers it', (t) => {
  const window = run(t, { saved: '1.25', body: SELECT });
  window.document.dispatchEvent(new window.Event('DOMContentLoaded'));
  const select = window.document.getElementById('textSizeSelect');
  assert.equal(select.value, '1.25', 'the selector shows the saved choice');
  select.value = '2';
  select.dispatchEvent(new window.Event('change'));
  assert.equal(window.document.documentElement.dataset.textScale, '2');
  assert.equal(window.localStorage.getItem('morfeo.textScale'), '2');
});

test('the page loads text-size.js in <head> and scales the root font size', () => {
  const head = RAW.slice(0, RAW.indexOf('</head>'));
  assert.match(head, /<script src="\/static\/text-size\.js"><\/script>/);
  assert.match(RAW, /html \{ font-size: calc\(100% \* var\(--text-scale, 1\)\); \}/);
});

test('the top bar offers the four scales between the theme and the refresh buttons', () => {
  const dom = new JSDOM(readDashboardHtml());
  const actions = dom.window.document.querySelector('.topbar__actions');
  const select = actions.querySelector('#textSizeSelect');
  assert.ok(select, 'the selector lives in the top-bar actions');
  assert.deepEqual(JSON.parse(JSON.stringify([...select.options].map((o) => o.value))), ['1', '1.25', '1.5', '2']);
  assert.ok(select.getAttribute('aria-label'), 'the selector has an accessible name');
  const ids = [...actions.children].map((el) => el.id).filter(Boolean);
  const order = ['runSelector', 'themeBtn', 'textSizeSelect', 'boardRefreshBtn'].map((id) => ids.indexOf(id));
  assert.ok(order.every((i) => i >= 0), JSON.stringify(ids));
  assert.deepEqual(order, [...order].sort((a, b) => a - b), JSON.stringify(ids));
});

test('the terminal font follows the text size and refits on a change', async (t) => {
  const { createViewerHarness } = await import('./harness.mjs');
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.eval(`
    window.__fits = 0;
    window.Terminal = class {
      constructor(opts) { this.options = { ...opts }; this.cols = 80; this.rows = 24; }
      loadAddon() {} open() {} focus() {} onData() {} onBinary() {} write() {} reset() {} clear() {}
    };
    window.FitAddon = { FitAddon: class { fit() { window.__fits += 1; } } };
    window.WebSocket = class { constructor() { this.readyState = 0; } send() {} close() {} };
    WebSocket.OPEN = 1;
    window.setTextScale('1.5');
  `);
  viewer.viewer('setupTerminal');
  assert.equal(viewer.window.eval('terminalInstance.options.fontSize'), 20, '13 px × 1.5, rounded');
  const before = viewer.window.__fits;
  viewer.window.setTextScale('2');
  assert.equal(viewer.window.eval('terminalInstance.options.fontSize'), 26);
  assert.ok(viewer.window.__fits > before, 'the terminal refits to its new cell size');
});
