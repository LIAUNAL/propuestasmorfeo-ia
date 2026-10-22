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

async function harness(t, payload, posts = [], { stubPrompt = true } = {}) {
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
  if (stubPrompt) viewer.window.eval(`window.__prompts = []; sendTerminalPrompt = (cmd) => window.__prompts.push(cmd);`);
  await viewer.viewer('loadTrees');
  await flush();
  return viewer;
}

test('la pestaña queda entre «Pipeline y Avance» y «MGA resumido»', async (t) => {
  const viewer = await harness(t, treesPayload());
  const labels = Array.from(viewer.document.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
  const i = labels.indexOf('Árbol de problemas y objetivos');
  assert.ok(i > 0, 'la pestaña existe');
  assert.equal(labels[i - 1], 'Pipeline y Avance');
  assert.equal(labels[i + 1], 'MGA resumido');
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

test('cada objetivo específico se muestra limpio, sin el texto de la causa como preámbulo', async (t) => {
  const payload = treesPayload();
  payload.objectives.tree = structuredClone(OBJECTIVE_TREE);
  payload.objectives.tree.groups[0].title = 'Insuficiente información sobre la causa uno';
  const viewer = await harness(t, payload);
  viewer.viewer('setTreeView', 'objetivos');
  const head = viewer.document.querySelector('#treeCanvas [data-node="OE1"]');
  assert.equal(head.querySelector('.tree-node__text').textContent.trim(), 'Desarrollar uno');
  assert.equal(head.querySelector('.tree-node__id').textContent.trim(), 'OE1', 'el rótulo queda como insignia');
  assert.doesNotMatch(head.textContent, /Insuficiente información/);
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

// El tablero corre con el reloj manual del arnés: se avanza hasta que la
// promesa de la acción se resuelva.
async function settle(viewer, promise) {
  let done = false;
  promise.then(() => { done = true; }, () => { done = true; });
  for (let i = 0; i < 50 && !done; i += 1) {
    await flush();
    await viewer.advance(100);
  }
  await promise;
  await flush();
}

// Terminal doble: nunca conecta hasta que la prueba la abre, y registra lo enviado.
function fakeTerminal(viewer) {
  viewer.window.eval(`
    window.__sent = [];
    TERMINAL_READY_TIMEOUT_MS = 60;
    TERMINAL_BOOT_DELAY_MS = 0;
    selectedAgent = 'claude';
    terminalSocket = null;
    openMorfeoTerminal = () => {};
    ensureTerminalConnected = () => {};
    onTerminalAgentChange = () => {};
    window.__openTerminal = () => { terminalSocket = { readyState: 1, send: (d) => window.__sent.push(d) }; };
  `);
}

test('si la terminal no conecta, el tablero no dice que el agente recibió el ajuste y permite reintentar', async (t) => {
  const viewer = await harness(t, treesPayload(), [], { stubPrompt: false });
  fakeTerminal(viewer);
  viewer.document.getElementById('treeGeneralInput').value = 'Ajustar';
  await settle(viewer, viewer.viewer('submitTreeFeedback'));

  const msg = viewer.document.getElementById('treeMessage');
  assert.ok(msg.classList.contains('is-error'));
  assert.match(msg.textContent, /el agente no la recibió/);
  assert.doesNotMatch(msg.textContent, /enviada al agente/);
  const retry = viewer.document.getElementById('treeRetryBtn');
  assert.notEqual(retry.style.display, 'none');

  viewer.window.eval('window.__openTerminal()');
  await settle(viewer, viewer.viewer('retryTreePrompt'));
  assert.deepEqual(Array.from(viewer.window.__sent), ['Ajusta el árbol de problemas según X', '\r']);
  assert.match(msg.textContent, /enviada al agente/);
  assert.equal(retry.style.display, 'none');
});

test('con la terminal conectada el ajuste se envía y se confirma', async (t) => {
  const viewer = await harness(t, treesPayload(), [], { stubPrompt: false });
  fakeTerminal(viewer);
  viewer.window.eval('window.__openTerminal()');
  viewer.document.getElementById('treeGeneralInput').value = 'Ajustar';
  await settle(viewer, viewer.viewer('submitTreeFeedback'));
  assert.deepEqual(Array.from(viewer.window.__sent), ['Ajusta el árbol de problemas según X', '\r']);
  assert.match(viewer.document.getElementById('treeMessage').textContent, /enviada al agente/);
});

test('un revision.json dañado se muestra en la pestaña', async (t) => {
  const payload = treesPayload();
  payload.review_error = 'artefactos/arboles/revision.json está dañado y no se puede leer';
  const viewer = await harness(t, payload);
  assert.match(viewer.document.getElementById('treeBanner').textContent, /revision\.json está dañado/);
});

// --- Reglas de la guía SGR (S2) ---------------------------------------------

function tierTexts(viewer) {
  return Array.from(viewer.document.querySelectorAll('#treeCanvas .tree-tier, #treeCanvas .tree-subtier')).map(el => el.textContent.trim());
}

test('el árbol de problemas nombra sus niveles según la MGA', async (t) => {
  const viewer = await harness(t, treesPayload());
  const tiers = tierTexts(viewer);
  for (const label of ['Efecto final', 'Efectos directos', 'Problema central', 'Causas directas', 'Causas indirectas']) {
    assert.ok(tiers.includes(label), `nivel ${label} en ${JSON.stringify(tiers)}`);
  }
  assert.ok(!tiers.some(x => /Soluci/.test(x)), 'la copa ya no es la solución');
});

test('el árbol de objetivos nombra sus niveles como espejo positivo', async (t) => {
  const viewer = await harness(t, treesPayload());
  viewer.viewer('setTreeView', 'objetivos');
  const tiers = tierTexts(viewer);
  for (const label of ['Fin último', 'Fines', 'Objetivo general', 'Objetivos específicos', 'Medios']) {
    assert.ok(tiers.includes(label), `nivel ${label} en ${JSON.stringify(tiers)}`);
  }
});

test('la magnitud del problema central se muestra, y su ausencia se advierte', async (t) => {
  const payload = treesPayload();
  payload.problem.tree = { ...PROBLEM_TREE, trunk: { ...PROBLEM_TREE.trunk, magnitude: { indicador: 'Tasa de deserción', valor: '12 %', fuente: 'SIMAT 2024' } } };
  const viewer = await harness(t, payload);
  const mag = viewer.document.querySelector('#treeCanvas .tree-magnitude');
  assert.ok(mag, 'bloque de magnitud');
  assert.match(mag.textContent, /Tasa de deserción/);
  assert.match(mag.textContent, /12 %/);
  assert.match(mag.textContent, /SIMAT 2024/);

  const bare = await harness(t, treesPayload());
  assert.match(bare.document.querySelector('#treeCanvas .tree-magnitude').textContent,
    /Sin magnitud: agrega indicador, valor y fuente \(línea base\)/);
});

test('los hallazgos se listan, marcan su nodo y bloquean la aprobación si hay errores', async (t) => {
  const payload = treesPayload();
  payload.problem.findings = [
    { severity: 'error', code: 'arbol-ausencia-de-solucion', node: 'trunk', message: 'Un problema no es la ausencia de su solución' },
    { severity: 'warning', code: 'arbol-causa-directa-sin-indirectas', node: 'SP2', message: 'Causa directa sin causas indirectas' },
  ];
  const viewer = await harness(t, payload);
  const list = viewer.document.getElementById('treeFindings');
  assert.match(list.textContent, /Un problema no es la ausencia de su solución/);
  assert.match(list.textContent, /trunk/);
  assert.match(list.textContent, /Causa directa sin causas indirectas/);
  const canvas = viewer.document.getElementById('treeCanvas');
  assert.ok(canvas.querySelector('[data-node="trunk"]').classList.contains('tree-node--finding-error'));
  assert.ok(canvas.querySelector('[data-node="SP2"]').classList.contains('tree-node--finding-warning'));
  assert.ok(!canvas.querySelector('[data-node="r1"]').className.includes('finding'));
  const approve = viewer.document.getElementById('treeApproveBtn');
  assert.equal(approve.disabled, true);
  assert.match(approve.title, /hallazgos/i);
});

test('solo con avisos el árbol se puede aprobar', async (t) => {
  const payload = treesPayload();
  payload.problem.findings = [{ severity: 'warning', code: 'arbol-sin-magnitud', node: 'trunk', message: 'Sin magnitud' }];
  const viewer = await harness(t, payload);
  assert.equal(viewer.document.getElementById('treeApproveBtn').disabled, false);
});

test('la pestaña trae las reglas de la guía SGR, cerradas por defecto', async (t) => {
  const viewer = await harness(t, treesPayload());
  const box = viewer.document.getElementById('treeRules');
  assert.ok(box, 'caja de reglas');
  assert.equal(box.tagName, 'DETAILS');
  assert.equal(box.open, false);
  assert.match(box.querySelector('summary').textContent, /Reglas de la guía SGR/);
  assert.match(box.textContent, /Instructivo MGA 2023/);
  assert.match(box.textContent, /Manual conceptual MGA 2015/);
  assert.doesNotMatch(box.textContent, / — |--/);
});

test('las reglas del problema central traen el ejemplo, el criterio y las preguntas orientadoras', async (t) => {
  const viewer = await harness(t, treesPayload());
  const txt = viewer.document.getElementById('treeRules').textContent;
  assert.match(txt, /Limitados ambientes de aprendizaje innovadores/);
  assert.match(txt, /diversas alternativas de solución/);
  assert.match(txt, /necesidades de la población/);
  assert.match(txt, /efecto visible principal, no una causa raíz ni una consecuencia lejana/);
  for (const q of ['¿Qué está pasando?', '¿Por qué es un problema?', '¿Es el punto de partida lógico para buscar soluciones?',
    '¿Afecta a una población significativa?', '¿Es una prioridad para la política pública o el plan de desarrollo?',
    '¿Es abordable con los recursos y capacidades disponibles?']) {
    assert.ok(txt.includes(q), q);
  }
});

test('las reglas explican causas y efectos del problema con sus ejemplos', async (t) => {
  const viewer = await harness(t, treesPayload());
  const box = viewer.document.getElementById('treeRules');
  const heads = Array.from(box.querySelectorAll('h4')).map(h => h.textContent.trim());
  assert.ok(heads.includes('Causas del problema'), heads.join(' | '));
  assert.ok(heads.includes('Efectos del problema'), heads.join(' | '));
  const txt = box.textContent;
  for (const s of ['¿Qué está causando el problema?', 'factores que tienen una relación inmediata con el problema central',
    'Insuficientes docentes capacitados', 'raíces más profundas o estructurales', 'Escasa inversión en formación docente',
    '¿Qué pasa como consecuencia de este problema?', 'consecuencia inmediata del problema', 'se derivan de los efectos directos']) {
    assert.ok(txt.includes(s), s);
  }
  assert.doesNotMatch(txt, /Ejemplo: falta de/i);
});

test('los dos árboles son los títulos principales de las reglas, distintos de sus subtítulos', async (t) => {
  const viewer = await harness(t, treesPayload());
  const box = viewer.document.getElementById('treeRules');
  const trees = Array.from(box.querySelectorAll('h3.tree-rules__tree')).map(h => h.textContent.trim());
  assert.equal(trees.length, 2);
  assert.match(trees[0], /Árbol de problemas$/);
  assert.match(trees[1], /Árbol de objetivos$/);
  assert.ok(!Array.from(box.querySelectorAll('h4')).some(h => /^Árbol de/.test(h.textContent.trim())), 'los árboles ya no son h4');
});

test('el árbol de objetivos trae el método SMART y dónde va lo medible', async (t) => {
  const viewer = await harness(t, treesPayload());
  const txt = viewer.document.getElementById('treeRules').textContent;
  assert.ok(txt.includes('Los objetivos deben seguir el método SMART (Specific, Measurable, Achievable, Relevant and Time-bound). Es decir, deben ser claros y definidos, debe ser posible cuantificar el progreso o resultado, deben ser realistas y posibles de lograr, deben ser importantes y alineados con otras metas y deben tener un plazo definido para su cumplimiento.'));
  assert.ok(txt.includes('Lo medible y el plazo se expresan en los indicadores y en el cronograma, no dentro del enunciado del objetivo (sin porcentajes, metas ni fechas).'));
});

test('la cabecera muestra el flujo del proyecto', async (t) => {
  const viewer = await harness(t, treesPayload());
  const badge = viewer.document.getElementById('flujoBadge');
  assert.ok(badge, 'insignia de flujo');
  viewer.viewer('renderFlujoBadge', { flujo: 'sgr' });
  assert.equal(badge.textContent.trim(), 'Flujo SGR');
  viewer.viewer('renderFlujoBadge', {});
  assert.equal(badge.textContent.trim(), 'Flujo base');
  viewer.viewer('renderFlujoBadge', { flujo: 'base' });
  assert.equal(badge.textContent.trim(), 'Flujo base');
});

test('la pestaña «Relaciones entre las causas y objetivos» sigue a «Árbol de objetivos»', async (t) => {
  const viewer = await harness(t, treesPayload());
  const labels = Array.from(viewer.document.querySelectorAll('.tree-switch button')).map(b => b.textContent.trim());
  const i = labels.findIndex(l => l.includes('Árbol de objetivos'));
  assert.ok(labels[i + 1].includes('Relaciones entre las causas y objetivos'));
});

test('la tabla de relaciones liga cada causa directa e indirecta con su objetivo específico', async (t) => {
  const viewer = await harness(t, treesPayload());
  viewer.viewer('setTreeView', 'relaciones');
  const table = viewer.document.querySelector('#treeCanvas table.tree-relations');
  assert.ok(table, 'la tabla existe');
  const heads = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent.trim());
  assert.deepEqual(heads, ['Causa relacionada', 'Objetivos específicos']);
  const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr => Array.from(tr.cells).map(c => c.textContent.replace(/\s+/g, ' ').trim()));
  assert.deepEqual(rows, [
    ['Causa directa 1 SP1 · Uno', 'Desarrollar uno'],
    ['Causa indirecta 1.1 Causa uno', 'Pendiente'],
    ['Causa indirecta 1.2 Causa dos', 'Medio dos'],
    ['Causa directa 2 SP2 · Dos', 'Pendiente'],
    ['Causa indirecta 2.1 Causa tres', 'Pendiente'],
  ]);
  assert.ok(viewer.document.getElementById('treeViewRelaciones').classList.contains('btn--primary'));
  assert.ok(viewer.document.getElementById('treeReviewPanel').hidden, 'la tabla no se comenta: se oculta la revisión');
});

test('volver al árbol de objetivos restaura el lienzo y el panel de revisión', async (t) => {
  const viewer = await harness(t, treesPayload());
  viewer.viewer('setTreeView', 'relaciones');
  viewer.viewer('setTreeView', 'objetivos');
  assert.ok(viewer.document.querySelector('#treeCanvas [data-node="OE1"]'));
  assert.ok(!viewer.document.getElementById('treeReviewPanel').hidden);
});
