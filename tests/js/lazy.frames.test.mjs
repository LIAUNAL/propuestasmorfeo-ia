/**
 * Heavy iframes load when their tab is shown, not when the dashboard opens.
 *
 * The 3D graph (WebGL with three.js inline), the Archify flow and the native
 * PDF viewer used to load at page open even with their tabs hidden. The real
 * dashboard runs under jsdom and the tests read each iframe's `src` before and
 * after navigating.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness } from './harness.mjs';

async function harness(t) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  return viewer;
}

const src = (viewer, id) => viewer.document.getElementById(id).getAttribute('src');

test('the graph, flow and native PDF iframes start empty', async (t) => {
  const viewer = await harness(t);
  assert.equal(src(viewer, 'graphIframe'), 'about:blank');
  assert.equal(src(viewer, 'pdfNativeIframe'), 'about:blank');
  assert.equal(src(viewer, 'flowIframe'), 'about:blank');
});

test('opening the graph tab loads the selected graph', async (t) => {
  const viewer = await harness(t);
  viewer.viewer('navigateTab', 'atlas');
  await viewer.advance(100);
  assert.equal(src(viewer, 'graphIframe'), '/api/graph/papers');
});

test('the flow loads with the current theme when it is shown', async (t) => {
  const viewer = await harness(t);
  viewer.viewer('applyThemeChrome', 'light');
  assert.equal(src(viewer, 'flowIframe'), 'about:blank', 'a theme change alone does not load it');
  viewer.viewer('navigateTab', 'flow');
  assert.equal(src(viewer, 'flowIframe'), '/api/flow?theme=light');
  viewer.viewer('applyThemeChrome', 'dark');
  assert.equal(src(viewer, 'flowIframe'), '/api/flow?theme=dark', 'once loaded, a theme change reloads it');
});

test('the flow, the default tab, loads at startup when its pane is the visible one', async (t) => {
  const viewer = await harness(t);
  assert.ok(viewer.document.getElementById('pane-flow').classList.contains('active'));
  viewer.viewer('ensureFlowLoaded');
  assert.match(src(viewer, 'flowIframe'), /^\/api\/flow\?theme=/);
});
