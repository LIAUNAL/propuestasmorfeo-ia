/**
 * Botón «Presentación» del visor PDF: abre /presentacion en una pestaña nueva.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness } from './harness.mjs';

test('el visor tiene un botón Presentación que abre /presentacion', async (t) => {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const opened = [];
  viewer.window.open = (url, target) => { opened.push({ url: String(url), target }); return null; };

  const btn = viewer.document.getElementById('btnPresentacion');
  assert.ok(btn, 'existe el botón');
  assert.match(btn.textContent, /Presentación/);

  btn.click();
  assert.equal(opened.length, 1);
  assert.equal(opened[0].url, '/presentacion');
  assert.equal(opened[0].target, '_blank');
});
