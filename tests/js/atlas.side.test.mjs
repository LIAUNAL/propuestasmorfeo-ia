/**
 * The paper summary side panel of the SOTA constellation page
 * (`scripts/render_atlas.py` -> `grafos/papers-graph.html`).
 *
 * The page is rendered from the test fixture by the real renderer and run
 * as is under jsdom. jsdom has no WebGL, so the page opens its 2D
 * constellation; a click there goes through the same `onSelect` hook the 3D
 * viewer calls. Doubled here: only the browser (2D canvas context,
 * ResizeObserver, pointer capture) and the framing dashboard (a second jsdom
 * window standing in as `window.parent`, recording what the page posts).
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, copyFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { JSDOM } from 'jsdom';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..');
const RENDERER = path.join(REPO, 'scripts', 'render_atlas.py');
const FIXTURES = path.join(REPO, 'tests', 'fixtures', 'constelacion');
const PYTHON = process.env.PYTHON || 'python3';

function renderPage(atlasPath) {
  const dir = mkdtempSync(path.join(tmpdir(), 'atlas-side-js-'));
  try {
    const out = path.join(dir, 'atlas.html');
    execFileSync(PYTHON, [RENDERER, atlasPath, '--out', out], { stdio: 'pipe' });
    return readFileSync(out, 'utf-8');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function fakeContext(counter) {
  const target = { measureText: (s) => ({ width: 6 * String(s).length }) };
  return new Proxy(target, {
    get(obj, prop) {
      if (prop in obj) return obj[prop];
      return () => { counter.calls += 1; };
    },
  });
}

// Mount the page framed by a recording parent; return handles the tests use.
function mount(t, html) {
  const parentDom = new JSDOM('<!doctype html><title>tablero</title>', { url: 'http://localhost:8080/' });
  const posted = [];
  // postMessage hands over a structured clone, never the page's own object.
  parentDom.window.postMessage = (message) => posted.push(structuredClone(message));
  const counter = { calls: 0 };
  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'http://localhost:8080/api/graph/papers',
    beforeParse(window) {
      Object.defineProperty(window, 'parent', { configurable: true, get: () => parentDom.window });
      window.HTMLCanvasElement.prototype.getContext = function (type) {
        return type === '2d' ? fakeContext(counter) : null;
      };
      window.ResizeObserver = class { observe() {} disconnect() {} };
      window.Element.prototype.setPointerCapture = () => {};
    },
  });
  t.after(() => { dom.window.close(); parentDom.window.close(); });
  const { window } = dom;
  const send = (data) => window.dispatchEvent(new window.MessageEvent('message', { data, source: parentDom.window }));
  return { window, doc: window.document, posted, counter, send };
}

const frame = (window) => new Promise((resolve) => window.requestAnimationFrame(() => resolve()));

// A real click on the 2D canvas, at the planet's projected position.
async function clickPlanet(window, key) {
  await frame(window);
  const [point] = window.eval(`viewer.project([${JSON.stringify(key)}])`);
  assert.ok(point, `planet ${key} must be drawn`);
  const canvas = window.document.querySelector('#sky canvas');
  const at = { clientX: point.x, clientY: point.y, button: 0, bubbles: true };
  canvas.dispatchEvent(new window.MouseEvent('pointerdown', at));
  canvas.dispatchEvent(new window.MouseEvent('pointerup', at));
}

const keepOf = (window) => window.eval('namesKeep ? [...namesKeep].sort() : null');

test('a click on any planet opens the paper summary with its sections and the selected planet', async (t) => {
  const { window, doc, posted } = mount(t, renderPage(path.join(FIXTURES, 'atlas.json')));
  const side = doc.getElementById('side');
  assert.equal(side.hidden, true, 'the panel starts closed');
  assert.equal(doc.getElementById('overlay'), null, 'the old modal is gone');

  await clickPlanet(window, 'paper-1.p1-problem');

  assert.equal(side.hidden, false);
  const body = doc.getElementById('sidebody');
  const atlas = JSON.parse(readFileSync(path.join(FIXTURES, 'atlas.json'), 'utf-8'));
  const sys1 = atlas.systems.find((s) => s.id === 'paper-1');
  const sun = sys1.planets.find((p) => p.slot === 'sun');
  const problem = sys1.planets.find((p) => p.slot === 'problem');
  assert.equal(body.querySelector('h2').textContent, sun.label);

  const node = body.querySelector('.side-node');
  assert.match(node.textContent, /Seleccionado · problema/);
  assert.ok(node.textContent.includes(problem.label));
  assert.equal(node.querySelector('.quote').textContent, problem.evidence.quote);

  const titles = [...body.querySelectorAll('dl.side-sections dt')].map((dt) => dt.textContent);
  assert.deepEqual(titles, ['Tema de aplicación', 'Tema de IA', 'Problema', 'Aplicación',
    'Novedad principal', 'Resultados', 'Conclusiones', 'Familia']);
  const lit = body.querySelectorAll('dl.side-sections .sel');
  assert.equal(lit.length, 1, 'exactly the selected planet is highlighted');
  assert.ok(lit[0].textContent.startsWith(problem.label));

  const meta = Object.fromEntries([...body.querySelectorAll('dl.side-paper dt')]
    .map((dt) => [dt.textContent, dt.nextElementSibling.textContent]));
  assert.deepEqual(meta, {
    'Autores': 'Ana Pérez, Luis Gómez', 'Año': '2025', 'Publicación': 'Scientific Reports',
    'Cuartil': 'Q1', 'DOI/URL': 'https://doi.org/10.1000/fixture.1', 'Clave BibTeX': 'perez2025_mil',
  });
  const link = body.querySelector('dl.side-paper a');
  assert.equal(link.href, 'https://doi.org/10.1000/fixture.1');
  assert.equal(link.target, '_blank');
  assert.equal(link.rel, 'noopener');

  // The dashboard contract is unchanged.
  assert.deepEqual(posted.filter((m) => m.type === 'atlas-planet-selected'), [{
    type: 'atlas-planet-selected', key: 'paper-1.p1-problem', label: problem.label,
    slot: 'problem', system: { id: 'paper-1', title: sys1.title },
  }]);
});

test('the selection dims every paper but the selected one and those it links to', async (t) => {
  const { window, doc } = mount(t, renderPage(path.join(FIXTURES, 'atlas.json')));
  await clickPlanet(window, 'paper-2.p2-result');
  const keep = keepOf(window);
  assert.ok(keep.some((k) => k.startsWith('paper-2.')));
  assert.ok(keep.some((k) => k.startsWith('paper-1.')), 'paper-2 supports paper-1');
  assert.ok(!keep.some((k) => k.startsWith('paper-3.')), 'paper-3 is not linked to paper-2');
  const buttons = [...doc.querySelectorAll('#sidebody .side-links button')].map((b) => b.textContent);
  assert.equal(buttons.length, 1);
});

test('a linked paper button selects that paper; Esc and the close button clear the selection', async (t) => {
  const { window, doc, posted } = mount(t, renderPage(path.join(FIXTURES, 'atlas.json')));
  const side = doc.getElementById('side');
  await clickPlanet(window, 'paper-2.p2-result');
  doc.querySelector('#sidebody .side-links button').click();
  const atlas = JSON.parse(readFileSync(path.join(FIXTURES, 'atlas.json'), 'utf-8'));
  const sun1 = atlas.systems.find((s) => s.id === 'paper-1').planets.find((p) => p.slot === 'sun');
  assert.equal(doc.querySelector('#sidebody h2').textContent, sun1.label);
  assert.equal(doc.querySelector('#sidebody .side-node'), null, 'a sun selection shows no planet block');
  assert.equal(posted.filter((m) => m.type === 'atlas-planet-selected').at(-1).key, 'paper-1.' + sun1.id);
  assert.ok(keepOf(window).some((k) => k.startsWith('paper-3.')), 'paper-1 links to paper-3');

  doc.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert.equal(side.hidden, true);
  assert.equal(keepOf(window), null, 'nothing stays dimmed');

  await clickPlanet(window, 'paper-3.p3-novelty');
  assert.equal(side.hidden, false);
  doc.getElementById('sideclose').click();
  assert.equal(side.hidden, true);
  assert.equal(keepOf(window), null);
});

test('pause, resume and view messages still work and keep the selection', async (t) => {
  const { window, doc, counter, send } = mount(t, renderPage(path.join(FIXTURES, 'atlas.json')));
  await clickPlanet(window, 'paper-2.p2-result');
  const selected = keepOf(window);

  send({ type: 'atlas-control', cmd: 'pause' });
  await frame(window);
  const before = counter.calls;
  doc.getElementById('zoomin').click();
  await frame(window);
  await frame(window);
  assert.equal(counter.calls, before, 'a paused sky draws nothing');
  send({ type: 'atlas-control', cmd: 'resume' });
  await frame(window);
  await frame(window);
  assert.ok(counter.calls > before, 'resuming draws again');

  const canvas = doc.querySelector('#sky canvas');
  send({ type: 'atlas-control', cmd: 'view-2d' });
  assert.notEqual(doc.querySelector('#sky canvas'), canvas, 'the view was mounted again');
  assert.deepEqual(keepOf(window), selected, 'the selection survives a view switch');
  assert.equal(doc.getElementById('side').hidden, false);
});

test('hostile titles, quotes and metadata are shown as text, never as markup', async (t) => {
  const dir = mkdtempSync(path.join(tmpdir(), 'atlas-side-hostile-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  mkdirSync(path.join(dir, 'papers'));
  const atlas = JSON.parse(readFileSync(path.join(FIXTURES, 'atlas.json'), 'utf-8'));
  const sys1 = atlas.systems.find((s) => s.id === 'paper-1');
  const evil = '<img src=x onerror="window.__pwned=1">';
  sys1.title = evil;
  sys1.planets.find((p) => p.slot === 'sun').label = evil;
  const problem = sys1.planets.find((p) => p.slot === 'problem');
  problem.label = '<b>bold</b>';
  problem.evidence.quote = '</script><script>window.__pwned=1</script>';
  problem.evidence.origin = 'javascript:window.__pwned=1';
  writeFileSync(path.join(dir, 'atlas.json'), JSON.stringify(atlas));
  copyFileSync(path.join(FIXTURES, 'papers', 'paper-2.md'), path.join(dir, 'papers', 'paper-2.md'));
  writeFileSync(path.join(dir, 'papers', 'paper-1.md'),
    '# x\n\n- Autores: <i>Mallory</i>\n- DOI/URL: javascript:window.__pwned=1\n- Clave: evil\n');

  const { window, doc } = mount(t, renderPage(path.join(dir, 'atlas.json')));
  await clickPlanet(window, 'paper-1.p1-problem');
  const body = doc.getElementById('sidebody');
  assert.equal(body.querySelector('h2').textContent, evil);
  assert.equal(body.querySelectorAll('img, b, i, script').length, 0);
  assert.equal(body.querySelector('a[href^="javascript"]'), null);
  assert.ok(body.textContent.includes('<i>Mallory</i>'));
  assert.ok(body.textContent.includes('javascript:window.__pwned=1'));
  assert.equal(window.__pwned, undefined);
});
