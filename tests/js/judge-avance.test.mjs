/**
 * judge-avance.js: the stage judge block («Juez de avance»), mounted in the
 * trees pane with etapa 'arbol' (odd/tasks/tablero-juez-novedad.md, S2).
 *
 * The real static/judge-avance.js runs in a small jsdom page with fetch and the
 * terminal delivery doubled; the last tests run it inside the real dashboard
 * (the harness does not inline it, so it is evaluated in the page's window,
 * as board.refresh.test.mjs does).
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { JSDOM } from 'jsdom';

import { createViewerHarness, DASHBOARD_INDEX, DASHBOARD_STATIC, flush } from './harness.mjs';

const SCRIPT = readFileSync(path.join(DASHBOARD_STATIC, 'judge-avance.js'), 'utf8');
const FOLDS = readFileSync(path.join(DASHBOARD_STATIC, 'section-folds.js'), 'utf8');

const ROUND = {
  schema: 'morfeo.juez-avance/v1',
  etapa: 'arbol',
  ronda: 2,
  fecha: '2026-11-22',
  puntaje: 74,
  veredicto: 'Árbol coherente; falta la fuente de la magnitud.',
  resumen_idea: 'Monitoreo hídrico con IA para Caldas, con sensores comunitarios.',
  fortalezas: [{ texto: 'Problema central medible.', evidencia: 'tronco del árbol' }],
  debilidades: [{ texto: 'Magnitud sin fuente.', evidencia: 'mga_resumido.md', accion: 'Citar el IDEAM con año.' }],
  alertas: [
    { nivel: 'baja', texto: 'Copa redactada como solución.', donde: 'copa' },
    { nivel: 'alta', texto: 'SP2 repite SP1 <b>.', donde: 'árbol, SP2' },
  ],
  historial: [{
    ronda: 1, fecha: '2026-11-21', puntaje: 41, veredicto: 'Versión inicial.',
    resumen_idea: 'Monitoreo hídrico para Caldas.',
    fortalezas: [{ texto: 'Idea pertinente.', evidencia: 'insumos.md' }],
    debilidades: [{ texto: 'Sin magnitud.', evidencia: 'árbol', accion: 'Agregar la magnitud.' }],
    alertas: [],
  }],
};

function json(payload, status = 200) {
  return { ok: status < 400, status, json: async () => payload, text: async () => JSON.stringify(payload) };
}

function judgePayload(evaluacion = ROUND, errores = []) {
  return { ok: true, run: 'demo', etapa: 'arbol', disponible: !!evaluacion, evaluacion, archivo: 'artefactos/juez/avance_arbol.json', errores };
}

async function mountPage({ answer = () => json(judgePayload()), send = async () => true, etapa = 'arbol' } = {}) {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    runScripts: 'outside-only', url: 'http://localhost:8000/',
  });
  const { window } = dom;
  window.eval(SCRIPT);
  const calls = [];
  const prompts = [];
  const controller = window.JudgeAvance.mount(window.document.getElementById('root'), {
    etapa,
    interval: 1000,
    fetch: async (url, init) => {
      calls.push({ url: String(url), method: (init && init.method) || 'GET', body: init && init.body });
      return answer(String(url), init);
    },
    send: async (prompt) => { prompts.push(prompt); return send(prompt); },
  });
  return { window, document: window.document, controller, calls, prompts, root: window.document.getElementById('root') };
}

test('it renders the score badge, verdict, idea summary, strengths, weaknesses with action and alerts by level', async () => {
  const { controller, root, calls } = await mountPage();
  await controller.refresh();
  assert.ok(calls.some(c => c.url === '/api/judge-avance?etapa=arbol' && c.method === 'GET'));
  const badge = root.querySelector('.ja-score');
  assert.match(badge.textContent, /74\s*\/\s*100/);
  assert.ok(badge.classList.contains('ja-tone--warn'), badge.className);
  assert.match(root.querySelector('.ja-verdict').textContent, /Árbol coherente/);
  assert.match(root.querySelector('.ja-idea').textContent, /Monitoreo hídrico con IA para Caldas/);
  const strengths = root.querySelectorAll('.ja-current .ja-strengths li');
  assert.equal(strengths.length, 1);
  assert.match(strengths[0].textContent, /Problema central medible/);
  assert.match(strengths[0].textContent, /tronco del árbol/);
  const weakness = root.querySelector('.ja-current .ja-weaknesses li');
  assert.match(weakness.textContent, /Magnitud sin fuente/);
  assert.match(weakness.querySelector('.ja-action').textContent, /Citar el IDEAM con año/);
  const levels = Array.from(root.querySelectorAll('.ja-current .ja-alert')).map(a => a.dataset.nivel);
  assert.deepEqual(levels, ['alta', 'baja'], 'alerts are ordered by level');
  assert.ok(root.querySelector('.ja-current .ja-alert[data-nivel="alta"] .ja-level--alta'));
  assert.match(root.textContent, /Ronda 2/);
  assert.match(root.textContent, /2026-11-22/);
});

test('every value is escaped', async () => {
  const { controller, root } = await mountPage();
  await controller.refresh();
  assert.equal(root.querySelector('.ja-current b'), null);
  assert.match(root.querySelector('.ja-current .ja-alert[data-nivel="alta"]').textContent, /<b>/);
});

test('earlier rounds stay collapsed under the current one', async () => {
  const { controller, root } = await mountPage();
  await controller.refresh();
  const rounds = root.querySelectorAll('details.ja-round');
  assert.equal(rounds.length, 1);
  assert.equal(rounds[0].open, false);
  assert.match(rounds[0].querySelector('summary').textContent, /Ronda 1.*41\s*\/\s*100/s);
  assert.match(rounds[0].textContent, /Agregar la magnitud/);
  assert.ok(rounds[0].querySelector('.ja-score.ja-tone--bad'));
});

test('stage final judges the whole proposal: its own query, copy, button and command', async () => {
  const finalRound = { ...ROUND, etapa: 'final', veredicto: 'Propuesta completa coherente.' };
  const answer = (url) => (url === '/api/judge-avance/run'
    ? json({ ok: true, etapa: 'final', prompt: '/propuesta-juez-avance final' })
    : json({ ...judgePayload(null), etapa: 'final', archivo: 'artefactos/juez/avance_final.json' }));
  const { controller, root, calls, prompts } = await mountPage({ etapa: 'final', answer });
  assert.equal(controller.etapa, 'final');
  assert.equal(root.getAttribute('data-judge-avance-etapa'), 'final');
  assert.match(root.querySelector('.ja-intro').textContent, /propuesta completa/);
  assert.doesNotMatch(root.querySelector('.ja-intro').textContent, /hasta/);
  assert.equal(root.querySelector('.ja-run').textContent.trim(), 'Evaluar la propuesta');
  await controller.refresh();
  assert.ok(calls.some(c => c.url === '/api/judge-avance?etapa=final'));
  assert.match(root.textContent, /Aún no hay evaluación de la propuesta completa/);
  assert.match(root.textContent, /«Evaluar la propuesta»/);
  await controller.run();
  assert.deepEqual(prompts, ['/propuesta-juez-avance final']);
  assert.deepEqual(JSON.parse(calls.find(c => c.method === 'POST').body), { etapa: 'final' });
  assert.match(root.querySelector('.ja-pending').textContent, /juez final/);
  const ui = await mountPage({ etapa: 'final', answer: () => json({ ...judgePayload(finalRound), etapa: 'final' }) });
  await ui.controller.refresh();
  assert.match(ui.root.querySelector('.ja-verdict').textContent, /Propuesta completa coherente/);
});

test('stages arbol and novedad keep their copy', async () => {
  for (const [etapa, phrase] of [['arbol', 'el árbol de problemas y objetivos'], ['novedad', 'la novedad y las hipótesis']]) {
    const { root, controller } = await mountPage({ etapa, answer: () => json(judgePayload(null)) });
    assert.equal(root.querySelector('.ja-intro').textContent,
      `El juez de avance puntúa la propuesta hasta ${phrase} (0 a 100) y resume la idea, sus puntos fuertes, sus puntos débiles y las alertas. Es asesor: no cambia el veredicto del revisor ni aprueba compuertas.`);
    assert.equal(root.querySelector('.ja-run').textContent.trim(), 'Evaluar hasta aquí');
    await controller.refresh();
    assert.match(root.textContent, /Aún no hay evaluación de esta etapa\. Pulsa «Evaluar hasta aquí» para que el juez de avance lea la propuesta hasta este punto\./);
  }
});

test('the badge tone follows the thresholds', async () => {
  const { window } = await mountPage();
  const tone = window.JudgeAvance.tone;
  assert.deepEqual([tone(100), tone(75), tone(74), tone(50), tone(49), tone(0)], ['ok', 'ok', 'warn', 'warn', 'bad', 'bad']);
});

test('without a recorded round it explains how to start, and shows the read errors', async () => {
  let payload = judgePayload(null);
  const { controller, root } = await mountPage({ answer: () => json(payload) });
  await controller.refresh();
  assert.match(root.textContent, /Aún no hay evaluación/);
  assert.match(root.textContent, /Evaluar hasta aquí/);
  assert.equal(root.querySelector('.ja-score'), null);
  payload = judgePayload(null, ['artefactos/juez/avance_arbol.json no es un JSON válido']);
  await controller.refresh();
  assert.match(root.querySelector('.ja-errors').textContent, /no es un JSON válido/);
});

test('«Evaluar hasta aquí» asks the server for the command, types it in the terminal and waits for the new round', async () => {
  let payload = judgePayload();
  const answer = (url) => (url === '/api/judge-avance/run'
    ? json({ ok: true, etapa: 'arbol', prompt: '/propuesta-juez-avance arbol' })
    : json(payload));
  const { controller, root, calls, prompts } = await mountPage({ answer: (u) => answer(u) });
  await controller.refresh();
  const button = root.querySelector('button.ja-run');
  assert.equal(button.textContent.trim(), 'Evaluar hasta aquí');
  button.click();
  await flush();
  const post = calls.find(c => c.url === '/api/judge-avance/run');
  assert.equal(post.method, 'POST');
  assert.deepEqual(JSON.parse(post.body), { etapa: 'arbol' });
  assert.deepEqual(prompts, ['/propuesta-juez-avance arbol']);
  assert.ok(root.querySelector('.ja-pending'), 'pending state while the file does not change');
  assert.equal(button.disabled, true);
  await controller.refresh();
  assert.ok(root.querySelector('.ja-pending'), 'the same round keeps it pending');
  payload = judgePayload({ ...ROUND, ronda: 3, puntaje: 82, historial: [] });
  await controller.refresh();
  assert.equal(root.querySelector('.ja-pending'), null);
  assert.equal(button.disabled, false);
  assert.match(root.querySelector('.ja-score').textContent, /82/);
  assert.ok(root.querySelector('.ja-score').classList.contains('ja-tone--ok'));
  assert.match(root.querySelector('.ja-message').textContent, /ronda 3/);
});

test('if the terminal does not connect, it says so and offers to retry the same command', async () => {
  let delivered = false;
  const answer = (url) => (url === '/api/judge-avance/run'
    ? json({ ok: true, etapa: 'arbol', prompt: '/propuesta-juez-avance arbol' })
    : json(judgePayload(null)));
  const { controller, root, prompts } = await mountPage({ answer, send: async () => delivered });
  await controller.run();
  assert.match(root.querySelector('.ja-message').textContent, /no llegó/);
  assert.equal(root.querySelector('.ja-pending'), null);
  const retry = root.querySelector('button.ja-retry');
  assert.equal(retry.hidden, false);
  delivered = true;
  retry.click();
  await flush();
  assert.deepEqual(prompts, ['/propuesta-juez-avance arbol', '/propuesta-juez-avance arbol']);
  assert.equal(retry.hidden, true);
  assert.ok(root.querySelector('.ja-pending'));
});

test('a server refusal is shown and nothing is sent', async () => {
  const answer = (url) => (url === '/api/judge-avance/run' ? json({ ok: false, error: 'No hay una corrida activa' }, 404) : json(judgePayload(null)));
  const { controller, root, prompts } = await mountPage({ answer });
  await controller.run();
  assert.deepEqual(prompts, []);
  assert.match(root.querySelector('.ja-message').textContent, /No hay una corrida activa/);
});

test('start() polls while the page is visible and stop() ends it; the stage goes in the query', async () => {
  const { controller, calls } = await mountPage({ etapa: 'novedad', answer: () => json({ ...judgePayload(null), etapa: 'novedad' }) });
  controller.start();
  await flush();
  assert.ok(calls.some(c => c.url === '/api/judge-avance?etapa=novedad'));
  assert.equal(controller.polling, true);
  controller.stop();
  assert.equal(controller.polling, false);
});

test('in the dashboard the trees pane carries the «Juez de avance» fold, open by default, after the Proyecto Resumido', async (t) => {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const calls = [];
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    calls.push({ url: u, method: (init && init.method) || 'GET' });
    if (u.startsWith('/api/judge-avance/run')) return json({ ok: true, etapa: 'arbol', prompt: '/propuesta-juez-avance arbol' });
    if (u.startsWith('/api/judge-avance')) return json(judgePayload());
    return json({}, 503);
  };
  try { viewer.window.localStorage.clear(); } catch (_) { /* storage blocked */ }
  viewer.window.eval(FOLDS);
  viewer.window.eval(SCRIPT);
  viewer.window.eval(`window.__prompts = []; sendTerminalPrompt = async (cmd) => { window.__prompts.push(cmd); return true; };`);
  await viewer.viewer('navigateTab', 'trees');
  await flush();
  const doc = viewer.document;
  const fold = doc.querySelector('#pane-trees details.exp-fold[data-fold-name="juez-avance-arbol"]');
  assert.ok(fold, 'the fold exists');
  assert.equal(fold.querySelector('.exp-fold__title').textContent.trim(), 'Juez de avance');
  assert.equal(fold.open, true);
  const resumen = doc.querySelector('#pane-trees details.exp-fold[data-fold-name="proyecto-resumido"]');
  assert.ok(resumen.compareDocumentPosition(fold) & viewer.window.Node.DOCUMENT_POSITION_FOLLOWING);
  assert.ok(calls.some(c => c.url === '/api/judge-avance?etapa=arbol'));
  assert.match(fold.querySelector('.ja-score').textContent, /74/);
  fold.querySelector('button.ja-run').click();
  await flush();
  assert.deepEqual(JSON.parse(viewer.window.eval('JSON.stringify(window.__prompts)')), ['/propuesta-juez-avance arbol']);
  await viewer.viewer('navigateTab', 'sections');
  assert.equal(viewer.window.eval('TREE_JUDGE && TREE_JUDGE.polling'), false, 'leaving the tab stops the polling');
});

test('the dashboard loads judge-avance.js right after section-folds.js', () => {
  const html = readFileSync(DASHBOARD_INDEX, 'utf8');
  const folds = html.indexOf('<script src="/static/section-folds.js"></script>');
  const judge = html.indexOf('<script src="/static/judge-avance.js"></script>');
  assert.ok(folds > 0 && judge > folds);
});
