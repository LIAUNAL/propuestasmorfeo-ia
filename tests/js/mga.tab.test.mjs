/**
 * «Proyecto Resumido», the fold of the trees panel that replaced the «MGA
 * resumido» tab (odd/tasks/tablero-juez-novedad.md, S3).
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/artifact` se
 * sustituye por un doble determinista. The harness does not inline
 * static/section-folds.js, so these tests evaluate the real file in the page's
 * window after it loads, as board.refresh.test.mjs does with its script. Se
 * observa la navegación, el pliegue, el archivo que se pide y el Markdown
 * renderizado (títulos, tabla y la línea base resaltada).
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { createViewerHarness, DASHBOARD_STATIC, flush } from './harness.mjs';

const FOLDS_SCRIPT = readFileSync(path.join(DASHBOARD_STATIC, 'section-folds.js'), 'utf8');

const MGA = `# Planteamiento del problema

## Problema central
Baja cobertura del monitoreo hídrico en Caldas.

## Descripción de la situación existente
Contexto del sector.

## Magnitud del problema
Cifras con fuente.

| Indicador | Causa | Valor | Fuente | Año |
|---|---|---|---|---|
| **Estaciones con datos continuos (línea base del proyecto)** | 1 | 12 % | IDEAM | 2025 |
`;

function text(body, status = 200) {
  return { ok: status < 400, status, json: async () => ({}), text: async () => body };
}

async function harness(t, respond, { folds = true } = {}) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const requests = [];
  viewer.window.fetch = async (url) => {
    const u = String(url);
    requests.push(u);
    if (u.includes('/api/artifact')) return respond(u);
    return text('', 503);
  };
  try { viewer.window.localStorage.clear(); } catch (_) { /* storage blocked */ }
  if (folds) viewer.window.eval(FOLDS_SCRIPT);
  return { viewer, requests };
}

const fold = (document) => document.querySelector('#pane-trees details.exp-fold[data-fold-name="proyecto-resumido"]');

test('the «MGA resumido» tab is gone from the navigation and its pane is removed', async (t) => {
  const { viewer } = await harness(t, () => text(MGA));
  const labels = Array.from(viewer.document.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
  assert.ok(!labels.includes('MGA resumido'), labels.join(' | '));
  assert.ok(!labels.includes('Proyecto Resumido'), 'Proyecto Resumido is a fold, not a tab');
  const mgaButtons = Array.from(viewer.document.querySelectorAll('.tab-nav__btn'))
    .filter(b => (b.getAttribute('onclick') || '').includes("'mga'"));
  assert.equal(mgaButtons.length, 0);
  assert.equal(viewer.document.getElementById('pane-mga'), null);
});

test('the trees panel holds a «Proyecto Resumido» fold below the tree stage, closed by default', async (t) => {
  const { viewer } = await harness(t, () => text(MGA));
  const doc = viewer.document;
  const details = fold(doc);
  assert.ok(details, 'the fold exists');
  assert.equal(details.querySelector('.exp-fold__title').textContent.trim(), 'Proyecto Resumido');
  assert.equal(details.open, false);
  assert.ok(details.querySelector('#mgaContent'), 'the content box lives in the fold');
  assert.ok(details.querySelector('#mgaRules'), 'the rules live in the fold');
  const layout = doc.querySelector('#pane-trees .tree-layout');
  assert.ok(layout.compareDocumentPosition(details) & viewer.window.Node.DOCUMENT_POSITION_FOLLOWING, 'the fold follows the tree stage');
  assert.doesNotMatch(doc.getElementById('pane-trees').textContent, /MGA resumido/);
});

test('carga artefactos/mga_resumido.md y lo pinta como Markdown', async (t) => {
  const { viewer, requests } = await harness(t, () => text(MGA));
  await viewer.viewer('loadMgaResumido');
  await flush();
  assert.ok(requests.some(u => u.includes('/api/artifact?file=artefactos%2Fmga_resumido.md')), requests.join(', '));
  const box = viewer.document.getElementById('mgaContent');
  assert.ok(box.classList.contains('is-markdown'));
  const headings = Array.from(box.querySelectorAll('h1, h2')).map(h => h.textContent.trim());
  assert.deepEqual(headings, ['Planteamiento del problema', 'Problema central', 'Descripción de la situación existente', 'Magnitud del problema']);
  assert.ok(box.querySelector('table'), 'la tabla de indicadores se pinta');
  assert.match(box.querySelector('table strong').textContent, /línea base del proyecto/);
});

test('sin el archivo, explica que lo escribe la Fase 1 y nombra el Proyecto Resumido', async (t) => {
  const { viewer } = await harness(t, () => text('File not found', 404));
  await viewer.viewer('loadMgaResumido');
  await flush();
  const box = viewer.document.getElementById('mgaContent');
  assert.match(box.textContent, /Fase 1/);
  assert.match(box.textContent, /Proyecto Resumido/);
  assert.doesNotMatch(box.textContent, /MGA resumido/);
  assert.equal(box.querySelector('table'), null);
});

test('navigateTab("mga") lands on the trees panel with the fold open and loads the content', async (t) => {
  const { viewer, requests } = await harness(t, () => text(MGA));
  await viewer.viewer('navigateTab', 'mga');
  await flush();
  const doc = viewer.document;
  assert.equal(viewer.window.eval('activeTab'), 'trees');
  assert.ok(doc.getElementById('pane-trees').classList.contains('active'));
  assert.equal(viewer.window.location.hash, '#trees');
  const active = doc.querySelector('.tab-nav__btn.active');
  assert.equal(active.textContent.trim(), 'Árbol de problemas y objetivos');
  assert.equal(fold(doc).open, true);
  assert.ok(requests.some(u => u.includes('mga_resumido.md')));
});

test('opening the trees tab with the fold closed does not read the file; opening the fold does', async (t) => {
  const { viewer, requests } = await harness(t, () => text(MGA));
  await viewer.viewer('navigateTab', 'trees');
  await flush();
  assert.ok(!requests.some(u => u.includes('mga_resumido.md')), requests.join(', '));
  const details = fold(viewer.document);
  details.open = true;
  details.dispatchEvent(new viewer.window.Event('toggle'));
  await flush();
  assert.ok(requests.some(u => u.includes('mga_resumido.md')));
  assert.match(viewer.document.getElementById('mgaContent').textContent, /Problema central/);
});

test('with the fold remembered open, opening the trees tab loads the content', async (t) => {
  const { viewer, requests } = await harness(t, () => text(MGA), { folds: false });
  viewer.window.localStorage.setItem('morfeo.folds', JSON.stringify({ 'proyecto-resumido': true }));
  viewer.window.eval(FOLDS_SCRIPT);
  await viewer.viewer('navigateTab', 'trees');
  await flush();
  assert.ok(requests.some(u => u.includes('mga_resumido.md')));
});

test('un error que no es 404 se informa como error, no como archivo ausente', async (t) => {
  const { viewer } = await harness(t, () => text('boom', 500));
  await viewer.viewer('loadMgaResumido');
  await flush();
  const box = viewer.document.getElementById('mgaContent');
  assert.match(box.textContent, /HTTP 500/);
  assert.doesNotMatch(box.textContent, /Aún no hay/);
});

test('el pliegue muestra las reglas de trabajo del Proyecto Resumido', async (t) => {
  const { viewer } = await harness(t, () => text(MGA));
  const rules = viewer.document.querySelector('#pane-trees details.tree-rules#mgaRules');
  assert.ok(rules, 'el desplegable de reglas existe');
  assert.equal(rules.querySelector('summary').textContent.trim(), 'Reglas para construir el Proyecto Resumido');
  const txt = rules.textContent;
  for (const rule of [/copiado textual/, /Descripción de la situación existente:/, /desde los antecedentes y el sector de aplicación/, /departamentos o regiones/, /Causa directa 1/, /plataforma interoperable/, /apropiación social/, /línea base/, /tabla/, /\[cifra por confirmar\]/]) {
    assert.match(txt, rule);
  }
  assert.doesNotMatch(txt, /Contexto general/);
  assert.doesNotMatch(txt, /MGA resumido/);
});

test('la regla de la situación existente trae su ejemplo', async (t) => {
  const { viewer } = await harness(t, () => text(MGA));
  const ex = viewer.document.querySelector('#mgaRules .mga-rules__example');
  assert.ok(ex, 'el ejemplo existe');
  assert.match(ex.textContent, /^\s*Ejemplo/);
  assert.match(ex.textContent, /En los 12 municipios no certificados del departamento de Risaralda/);
  assert.match(ex.textContent, /afecta los resultados académicos y la motivación de los estudiantes en estas áreas\./);
});

test('la magnitud del problema trae su ejemplo', async (t) => {
  const { viewer } = await harness(t, () => text(MGA));
  const examples = Array.from(viewer.document.querySelectorAll('#mgaRules .mga-rules__example'));
  assert.equal(examples.length, 2);
  const ex = examples[1];
  assert.match(ex.textContent, /^\s*Ejemplo/);
  assert.match(ex.textContent, /En Risaralda, según el Sistema de Información Nacional de Educación Básica y Media - SINEB \(2022\)/);
  assert.match(ex.textContent, /76\.545 estudiantes de la básica primaria y media técnica, 4\.235 docentes y 1\.103 sedes del departamento\./);
  const magnitudeHead = Array.from(viewer.document.querySelectorAll('#mgaRules h4')).find(h => h.textContent.trim() === 'Magnitud del problema');
  assert.ok(magnitudeHead.compareDocumentPosition(ex) & viewer.window.Node.DOCUMENT_POSITION_FOLLOWING, 'el ejemplo va en la magnitud');
});
