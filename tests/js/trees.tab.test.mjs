/**
 * Pestaña «Árbol de problemas y objetivos».
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/trees` y sus POST
 * se sustituyen por dobles deterministas. Se observa el DOM del árbol, el panel
 * de revisión y el comando que llega a la terminal del agente.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

const PROBLEM_TREE = {
  caption: '',
  groups: [
    { id: 'SP1', title: 'SP1 · Uno', causes: [{ id: 'r1', text: 'Causa uno' }, { id: 'r2', text: 'Causa dos' }] },
    { id: 'SP2', title: 'SP2 · Dos', causes: [{ id: 'r3', text: 'Causa tres' }] },
  ],
  trunk: { label: 'PROBLEMA CENTRAL', text: 'Problema central' },
  branches: [{ id: 'b1', text: 'Efecto uno' }],
  crown: { label: 'SOLUCIÓN', text: 'Sistema' },
};

const OBJECTIVE_TREE = {
  groups: [
    { id: 'OE1', from: 'SP1', title: 'OE1', objective: 'Desarrollar uno', means: [{ id: 'm1', from: 'r1', text: null }, { id: 'm2', from: 'r2', text: 'Medio dos' }] },
    { id: 'OE2', from: 'SP2', title: 'OE2', objective: null, means: [{ id: 'm3', from: 'r3', text: null }] },
  ],
  trunk: { label: 'OBJETIVO GENERAL', text: null },
  branches: [{ id: 'f1', from: 'b1', text: null }],
  crown: { label: 'IMPACTO', text: 'Sistema' },
};

function review(status) {
  return { status, approved_at: null, iterations: [] };
}

function treesPayload({ problemStatus = 'pendiente', objectiveStatus = 'pendiente' } = {}) {
  return {
    ok: true,
    run: '2026-01-demo',
    stage: problemStatus === 'aprobado' ? 'objetivos' : 'problemas',
    problem: { available: true, source: 'redaccion/specs/arbol_problemas.spec.json', hint: null, tree: PROBLEM_TREE, hash: 'p1', review: review(problemStatus) },
    objectives: { available: true, derived: true, source: 'artefactos/arboles/arbol_objetivos.json', hint: 'Espejo propuesto', tree: OBJECTIVE_TREE, hash: 'o1', missing: ['objetivo general', 'medio m1'], review: review(objectiveStatus) },
  };
}

function json(payload, status = 200) {
  return { ok: status < 400, status, json: async () => payload, text: async () => JSON.stringify(payload) };
}

async function harness(t, payload, posts = []) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    if (u.includes('/api/trees/feedback')) {
      posts.push({ url: u, body: JSON.parse(init.body) });
      return json({ ok: true, request: 'artefactos/arboles/ajuste_problemas_01.md', prompt: 'Ajusta el árbol de problemas según X', iteration: 1 });
    }
    if (u.includes('/api/trees/approve')) {
      posts.push({ url: u, body: JSON.parse(init.body) });
      return json({ ok: false, error: 'Primero hay que aprobar el árbol de problemas' }, 409);
    }
    if (u.includes('/api/trees')) return json(payload);
    return json({}, 503);
  };
  viewer.window.eval(`window.__prompts = []; sendTerminalPrompt = (cmd) => window.__prompts.push(cmd);`);
  await viewer.viewer('loadTrees');
  await flush();
  return viewer;
}

test('la pestaña queda entre «Pipeline y Avance» y «Secciones»', async (t) => {
  const viewer = await harness(t, treesPayload());
  const labels = Array.from(viewer.document.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
  const i = labels.indexOf('Árbol de problemas y objetivos');
  assert.ok(i > 0, 'la pestaña existe');
  assert.equal(labels[i - 1], 'Pipeline y Avance');
  assert.equal(labels[i + 1], 'Secciones');
  assert.ok(viewer.document.getElementById('pane-trees'));
});

test('el árbol de problemas pinta copa, efectos, tronco y causas por subproblema', async (t) => {
  const viewer = await harness(t, treesPayload());
  const canvas = viewer.document.getElementById('treeCanvas');
  for (const id of ['crown', 'b1', 'trunk', 'SP1', 'r1', 'r2', 'SP2', 'r3']) {
    assert.ok(canvas.querySelector(`[data-node="${id}"]`), `nodo ${id}`);
  }
  assert.match(canvas.textContent, /Problema central/);
});

test('el árbol de objetivos marca como pendientes los textos que faltan', async (t) => {
  const viewer = await harness(t, treesPayload());
  viewer.viewer('setTreeView', 'objetivos');
  const canvas = viewer.document.getElementById('treeCanvas');
  const m1 = canvas.querySelector('[data-node="m1"]');
  assert.ok(m1.classList.contains('tree-node--pending'));
  assert.match(m1.textContent, /Causa uno/, 'un medio pendiente muestra la causa de la que sale');
  assert.ok(!canvas.querySelector('[data-node="m2"]').classList.contains('tree-node--pending'));
});

test('comentar un nodo y enviar el ajuste escribe la solicitud y la manda a la terminal', async (t) => {
  const posts = [];
  const viewer = await harness(t, treesPayload(), posts);
  viewer.document.querySelector('#treeCanvas [data-node="r1"]').click();
  viewer.document.getElementById('treeCommentInput').value = 'Más específica';
  viewer.viewer('addTreeComment');
  assert.match(viewer.document.getElementById('treeCommentList').textContent, /Más específica/);

  await viewer.viewer('submitTreeFeedback');
  await flush();
  assert.equal(posts.length, 1);
  assert.deepEqual(posts[0].body.comments, [{ node: 'r1', text: 'Más específica' }]);
  assert.equal(posts[0].body.tree, 'problemas');
  assert.deepEqual(Array.from(viewer.window.__prompts), ['Ajusta el árbol de problemas según X']);
  assert.equal(viewer.document.getElementById('treeCommentList').children.length, 0, 'los comentarios enviados se limpian');
});

test('sin comentarios ni indicación general no se envía nada', async (t) => {
  const posts = [];
  const viewer = await harness(t, treesPayload(), posts);
  await viewer.viewer('submitTreeFeedback');
  await flush();
  assert.equal(posts.length, 0);
  assert.match(viewer.document.getElementById('treeMessage').textContent, /comenta un nodo/i);
});

test('el árbol de objetivos no se itera con el agente antes de aprobar el de problemas', async (t) => {
  const viewer = await harness(t, treesPayload());
  viewer.viewer('setTreeView', 'objetivos');
  const send = viewer.document.getElementById('treeSendBtn');
  assert.equal(send.disabled, true);
  assert.match(viewer.document.getElementById('treeGateNote').textContent, /aprobar el árbol de problemas/i);
});

test('con el árbol de problemas aprobado el de objetivos se puede iterar', async (t) => {
  const viewer = await harness(t, treesPayload({ problemStatus: 'aprobado' }));
  assert.equal(viewer.window.eval('TREES_STATE.view'), 'objetivos', 'la vista sigue la etapa del flujo');
  assert.equal(viewer.document.getElementById('treeSendBtn').disabled, false);
});

test('un rechazo al aprobar se muestra al usuario', async (t) => {
  const posts = [];
  const viewer = await harness(t, treesPayload(), posts);
  await viewer.viewer('approveCurrentTree');
  await flush();
  assert.equal(posts[0].body.tree, 'problemas');
  assert.match(viewer.document.getElementById('treeMessage').textContent, /Primero hay que aprobar/);
});

test('sin spec el árbol de problemas explica cómo se construye', async (t) => {
  const payload = treesPayload();
  payload.problem = { available: false, hint: 'El árbol de problemas se construye en la Fase 1', tree: null, hash: null, review: review('pendiente') };
  payload.stage = 'sin_arbol';
  const viewer = await harness(t, payload);
  assert.match(viewer.document.getElementById('treeCanvas').textContent, /se construye en la Fase 1/);
});

test('aprobar el árbol de problemas pasa a objetivos sin perder la confirmación', async (t) => {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  let approved = false;
  viewer.window.fetch = async (url) => {
    const u = String(url);
    if (u.includes('/api/trees/approve')) { approved = true; return json({ ok: true }); }
    if (u.includes('/api/trees')) return json(treesPayload({ problemStatus: approved ? 'aprobado' : 'pendiente' }));
    return json({}, 503);
  };
  await viewer.viewer('loadTrees');
  await viewer.viewer('approveCurrentTree');
  await flush();
  assert.equal(viewer.window.eval('TREES_STATE.view'), 'objetivos');
  assert.match(viewer.document.getElementById('treeMessage').textContent, /Árbol de problemas aprobado/);
});
