/**
 * section-folds.js: folding bars of the dashboard panels (odd/tasks/tablero-juez-novedad.md, S3).
 *
 * The real static/section-folds.js runs in a small jsdom page: a block marked
 * `data-fold` becomes a <details class="exp-fold"> whose open state is
 * remembered in localStorage under `morfeo.folds`. A last test checks that the
 * dashboard loads the script and styles the folds.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { JSDOM } from 'jsdom';

import { DASHBOARD_INDEX, DASHBOARD_STATIC } from './harness.mjs';

const SCRIPT = readFileSync(path.join(DASHBOARD_STATIC, 'section-folds.js'), 'utf8');

const BODY = `
  <div id="host">
    <section id="alpha" data-fold="alpha" data-fold-title="Proyecto Resumido"><p id="alphaText">Contenido</p></section>
    <section id="beta" data-fold="beta" data-fold-title="Juez de avance" data-fold-open><p>Juez</p></section>
  </div>`;

async function page({ stored = null, blockStorage = false } = {}) {
  const dom = new JSDOM(`<!doctype html><html><body>${BODY}</body></html>`, {
    runScripts: 'outside-only',
    url: 'http://localhost:8000/',
  });
  const { window } = dom;
  if (stored !== null) window.localStorage.setItem('morfeo.folds', stored);
  if (blockStorage) {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() { throw new window.DOMException('blocked', 'SecurityError'); },
    });
  }
  // The script runs while the page parses, as a <script> at the end of the
  // body does, and wraps on DOMContentLoaded.
  const ready = window.document.readyState === 'loading'
    ? new Promise((resolve) => window.document.addEventListener('DOMContentLoaded', resolve))
    : Promise.resolve();
  window.eval(SCRIPT);
  await ready;
  return { window, document: window.document };
}

function toggle(window, details, open) {
  details.open = open;
  details.dispatchEvent(new window.Event('toggle'));
}

test('a data-fold block is wrapped in a details bar titled from data-fold-title', async () => {
  const { document } = await page();
  const fold = document.querySelector('details.exp-fold[data-fold-name="alpha"]');
  assert.ok(fold, 'the fold exists');
  const summary = fold.querySelector(':scope > summary.exp-fold__summary');
  assert.equal(summary.querySelector('.exp-fold__title').textContent, 'Proyecto Resumido');
  const body = fold.querySelector(':scope > .exp-fold__body');
  assert.equal(body.firstElementChild, document.getElementById('alpha'), 'the block moves inside the body');
  assert.ok(document.getElementById('alphaText'), 'ids inside the block survive');
  assert.equal(fold.parentElement.id, 'host', 'the fold takes the block place');
});

test('data-fold-open starts open; without it the fold starts closed', async () => {
  const { document } = await page();
  assert.equal(document.querySelector('[data-fold-name="alpha"]').open, false);
  assert.equal(document.querySelector('[data-fold-name="beta"]').open, true);
});

test('the stored choice wins over the default', async () => {
  const { document } = await page({ stored: JSON.stringify({ alpha: true, beta: false }) });
  assert.equal(document.querySelector('[data-fold-name="alpha"]').open, true);
  assert.equal(document.querySelector('[data-fold-name="beta"]').open, false);
});

test('opening or closing a fold is remembered under morfeo.folds', async () => {
  const { window, document } = await page();
  toggle(window, document.querySelector('[data-fold-name="alpha"]'), true);
  toggle(window, document.querySelector('[data-fold-name="beta"]'), false);
  assert.deepEqual(JSON.parse(window.localStorage.getItem('morfeo.folds')), { alpha: true, beta: false });
});

test('wrapping twice does not nest folds', async () => {
  const { window, document } = await page();
  window.SectionFolds.wrap(document);
  assert.equal(document.querySelectorAll('details.exp-fold').length, 2);
  assert.equal(document.querySelectorAll('details.exp-fold details.exp-fold').length, 0);
});

test('open(name) opens the fold, remembers it and reports it; unknown names return false', async () => {
  const { window, document } = await page();
  assert.equal(window.SectionFolds.isOpen('alpha'), false);
  assert.equal(window.SectionFolds.open('alpha'), true);
  assert.equal(document.querySelector('[data-fold-name="alpha"]').open, true);
  assert.equal(window.SectionFolds.isOpen('alpha'), true);
  assert.equal(JSON.parse(window.localStorage.getItem('morfeo.folds')).alpha, true);
  assert.equal(window.SectionFolds.open('nope'), false);
});

test('onToggle(name, fn) reports the open state of that fold only', async () => {
  const { window, document } = await page();
  const seen = [];
  window.SectionFolds.onToggle('alpha', (open) => seen.push(open));
  toggle(window, document.querySelector('[data-fold-name="beta"]'), false);
  toggle(window, document.querySelector('[data-fold-name="alpha"]'), true);
  window.SectionFolds.open('alpha');
  assert.deepEqual(seen, [true]);
});

test('blocked storage leaves the folds working with their defaults', async () => {
  const { window, document } = await page({ blockStorage: true });
  const alpha = document.querySelector('[data-fold-name="alpha"]');
  assert.ok(alpha, 'the fold exists without storage');
  assert.equal(alpha.open, false);
  assert.equal(document.querySelector('[data-fold-name="beta"]').open, true);
  assert.doesNotThrow(() => toggle(window, alpha, true));
  assert.equal(window.SectionFolds.open('alpha'), true);
});

test('corrupt stored state is ignored', async () => {
  const { document } = await page({ stored: '{roto' });
  assert.equal(document.querySelector('[data-fold-name="beta"]').open, true);
});

test('the dashboard loads section-folds.js after board-refresh.js and styles the folds', async () => {
  const html = readFileSync(DASHBOARD_INDEX, 'utf8');
  const board = html.indexOf('<script src="/static/board-refresh.js"></script>');
  const folds = html.indexOf('<script src="/static/section-folds.js"></script>');
  assert.ok(board > 0 && folds > board, 'the script tag follows board-refresh.js');
  for (const rule of ['.exp-fold__summary', '.exp-fold[open] > .exp-fold__summary', '.exp-fold__body']) {
    assert.ok(html.includes(rule), `CSS rule ${rule}`);
  }
});
