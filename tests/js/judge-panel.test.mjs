/**
 * «Juez final» (odd/tasks/juez-sgr.md, S7 y S8), hoy un desplegable de la
 * previsualización PDF (odd/tasks/tablero-juez-novedad.md, S8).
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/judge` y sus POST
 * se sustituyen por dobles deterministas. Se observa el panel y el prompt que
 * llega a la terminal del agente por el mismo camino que usan los árboles.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { createViewerHarness, flush, DASHBOARD_STATIC } from './harness.mjs';

const JUDGE_AVANCE = readFileSync(path.join(DASHBOARD_STATIC, 'judge-avance.js'), 'utf8');

const RUBRICA = {
  id: 'conv54',
  convocatoria: 'Convocatoria 54 SGR',
  umbral_total: 75,
  minimos: [{ criterio: '1', minimo: 24 }],
  criterios: [
    { id: '1', nombre: 'Calidad técnica', max: 40, subcriterios: [
      { id: '1.1', nombre: 'Coherencia del planteamiento', max: 20, modo: 'niveles' },
      { id: '1.2', nombre: 'Trayectoria del equipo', max: 20, modo: 'conteo' },
    ] },
    { id: '2', nombre: 'Impacto regional', max: 60, subcriterios: [
      { id: '2', nombre: 'Impacto regional', max: 60, modo: 'acumulable' },
    ] },
  ],
};

function evaluacion(overrides = {}) {
  return {
    schema: 'morfeo.evaluacion-sgr-consolidada/v1',
    ronda: 2,
    fecha: '2026-11-19',
    rubrica: 'conv54',
    criterios: [
      { id: '1.1', puntaje: 10, componentes: null, nivel_descriptor: 'Coherencia parcial',
        justificacion: 'La clave <script>alert(1)</script> no coincide.',
        evidencia: [{ ubicacion: '§10', cita: 'Actividad 1.1' }],
        para_subir: { puntaje_objetivo: 20, que_falta: 'Unificar la clave de actividad.' } },
      { id: '1.2', puntaje: 15, componentes: null, nivel_descriptor: '', justificacion: 'Conteo de proyectos.', evidencia: [], para_subir: null },
      { id: '2', puntaje: 45, componentes: { a: 45 }, nivel_descriptor: '', justificacion: 'Bien sustentado.', evidencia: [], para_subir: null },
    ],
    alertas: [{ id: 'A1', severidad: 'error', tipo: 'inconsistencia', mensaje: 'Totales de §29 y Anexo 3 distintos', ubicacion: '§29', criterios: ['2'] }],
    acciones: [
      { id: 'X2', criterios: ['2'], agente: 'presupuestador', secciones: ['§13'], instruccion: 'Cuadra los totales.', impacto_estimado: 2, prioridad: 2 },
      { id: 'X3', criterios: ['1.2'], agente: 'usuario', secciones: [], instruccion: 'Aporta las certificaciones.', impacto_estimado: 1, prioridad: 1 },
      { id: 'X1', criterios: ['1.1'], agente: 'redactor', secciones: ['§10'], instruccion: 'Usa la clave OE.Producto.Actividad.', impacto_estimado: 10, prioridad: 1 },
    ],
    concepto: 'No recomienda todavía.',
    recomienda: false,
    subtotales: { 1: 25, 2: 45 },
    total: 70,
    elegible: false,
    motivos_no_elegible: ['El total 70 es menor que 75.'],
    incompleto: false,
    verificaciones: [{ id: 'V1', severidad: 'advertencia', tipo: 'forma', mensaje: 'El título MGA cambia entre documentos', ubicacion: '§1', criterios: [] }],
    historial: [
      { ronda: 1, fecha: '2026-11-18', total: 62, elegible: false },
      { ronda: 2, fecha: '2026-11-19', total: 70, elegible: false },
    ],
    errores_validacion: [],
    ...overrides,
  };
}

function payload(overrides = {}) {
  return { ok: true, run: '2026-11-demo', flujo: 'sgr', disponible: true, evaluacion: evaluacion(), rubrica: RUBRICA, errores: [], ...overrides };
}

function json(body, status = 200) {
  return { ok: status < 400, status, json: async () => body, text: async () => JSON.stringify(body) };
}

async function harness(t, body, posts = []) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  viewer.window.fetch = async (url, init) => {
    const u = String(url);
    if (u.includes('/api/judge/send')) {
      const sent = JSON.parse(init.body);
      posts.push({ url: u, body: sent });
      return json({ ok: true, accion_id: sent.accion_id, prompt: `Aplica la acción ${sent.accion_id}` });
    }
    if (u.includes('/api/judge/run')) {
      posts.push({ url: u, body: JSON.parse(init.body || '{}') });
      return json({ ok: true, prompt: '/propuesta-juez' });
    }
    if (u.includes('/api/judge-avance')) return json({ ok: true, run: 'demo', etapa: 'final', disponible: false, evaluacion: null, archivo: 'artefactos/juez/avance_final.json', errores: [] });
    if (u.includes('/api/judge')) return json(body);
    return json({}, 503);
  };
  viewer.window.eval(JUDGE_AVANCE);
  viewer.window.eval(`window.__prompts = []; sendTerminalPrompt = (cmd) => { window.__prompts.push(cmd); return Promise.resolve(true); };`);
  await viewer.viewer('loadJudge');
  await flush();
  return viewer;
}

test('el «Juez final» vive sobre el visor de la previsualización PDF, no en una pestaña', async (t) => {
  const viewer = await harness(t, payload());
  const labels = Array.from(viewer.document.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
  assert.ok(!labels.includes('Juez final'));
  assert.equal(viewer.document.getElementById('pane-judge'), null);
  const fold = viewer.document.getElementById('previewJudgeFold');
  assert.ok(fold.closest('#pane-preview .pdf-main-column'));
  assert.ok(fold.contains(viewer.document.getElementById('judgeSummary')));
});

test('el encabezado muestra el total frente al umbral, la elegibilidad y el mínimo del criterio 1', async (t) => {
  const viewer = await harness(t, payload());
  const head = viewer.document.getElementById('judgeSummary');
  assert.match(head.textContent, /70\s*\/\s*100/);
  assert.match(head.textContent, /75/);
  assert.match(head.querySelector('.judge-elegible').textContent, /No elegible/);
  assert.match(head.textContent, /Convocatoria 54 SGR/);
  assert.match(head.textContent, /Ronda 2/);
  const minimo = head.querySelector('[data-minimo="1"]');
  assert.ok(minimo, 'estado del mínimo del criterio 1');
  assert.match(minimo.textContent, /25.*24/);
  assert.ok(minimo.classList.contains('is-ok'));
});

test('los criterios agrupan sus subcriterios con puntaje, nivel y lo que falta para subir', async (t) => {
  const viewer = await harness(t, payload());
  const doc = viewer.document;
  const groups = doc.querySelectorAll('#judgeCriteria .judge-criterion');
  assert.equal(groups.length, 2);
  assert.match(groups[0].textContent, /Calidad técnica/);
  assert.equal(groups[0].querySelectorAll('.judge-sub').length, 2);
  const sub = doc.querySelector('.judge-sub[data-sub="1.1"]');
  assert.match(sub.textContent, /10\s*\/\s*20/);
  assert.match(sub.textContent, /Coherencia parcial/);
  assert.match(sub.querySelector('.judge-sub__up').textContent, /Unificar la clave/);
  assert.match(sub.textContent, /§10/);
});

test('la justificación se escapa: el HTML del agente no se ejecuta ni se inserta', async (t) => {
  const viewer = await harness(t, payload());
  const sub = viewer.document.querySelector('.judge-sub[data-sub="1.1"]');
  assert.equal(sub.querySelector('script'), null);
  assert.match(sub.querySelector('.judge-sub__why').textContent, /<script>alert\(1\)<\/script>/);
});

test('las alertas del agente y las verificaciones del script se agrupan por severidad', async (t) => {
  const viewer = await harness(t, payload());
  const alerts = viewer.document.getElementById('judgeAlerts');
  const error = alerts.querySelector('[data-severidad="error"]');
  const warn = alerts.querySelector('[data-severidad="advertencia"]');
  assert.match(error.textContent, /Totales de §29/);
  assert.match(warn.textContent, /título MGA/);
});

test('las acciones van por prioridad y luego por impacto, y «Enviar al agente» manda su id', async (t) => {
  const posts = [];
  const viewer = await harness(t, payload(), posts);
  const ids = Array.from(viewer.document.querySelectorAll('#judgeActions [data-accion]')).map(el => el.dataset.accion);
  assert.deepEqual(ids, ['X1', 'X3', 'X2']);
  assert.match(viewer.document.querySelector('#judgeActions [data-accion="X1"]').textContent, /redactor/);

  viewer.document.querySelector('#judgeActions [data-accion="X1"] .judge-send').click();
  await flush();
  assert.equal(posts.length, 1);
  assert.match(posts[0].url, /\/api\/judge\/send$/);
  assert.deepEqual(posts[0].body, { accion_id: 'X1' });
  assert.deepEqual(Array.from(viewer.window.__prompts), ['Aplica la acción X1']);
});

test('«Volver a evaluar» envía /propuesta-juez a la terminal', async (t) => {
  const posts = [];
  const viewer = await harness(t, payload(), posts);
  viewer.document.getElementById('judgeRunBtn').click();
  await flush();
  assert.match(posts[0].url, /\/api\/judge\/run$/);
  assert.deepEqual(Array.from(viewer.window.__prompts), ['/propuesta-juez']);
});

test('el historial muestra cada ronda con su total', async (t) => {
  const viewer = await harness(t, payload());
  const rows = viewer.document.querySelectorAll('#judgeHistory tbody tr');
  assert.equal(rows.length, 2);
  assert.match(rows[0].textContent, /62/);
  assert.match(rows[1].textContent, /70/);
});

test('los errores de validación se muestran de forma destacada', async (t) => {
  const viewer = await harness(t, payload({ evaluacion: evaluacion({ errores_validacion: ['criterio 1.1: 13 no es un nivel permitido'] }) }));
  assert.match(viewer.document.getElementById('judgeValidation').textContent, /13 no es un nivel permitido/);
});

test('en SGR sin evaluación se explica cómo correr el juez', async (t) => {
  const posts = [];
  const viewer = await harness(t, payload({ disponible: false, evaluacion: null, rubrica: null }), posts);
  const pane = viewer.document.getElementById('judgeContent');
  assert.match(pane.textContent, /\/propuesta-juez/);
  viewer.document.getElementById('judgeRunBtn').click();
  await flush();
  assert.deepEqual(Array.from(viewer.window.__prompts), ['/propuesta-juez']);
});

test('en el flujo base el juez final es el juez de avance con la etapa `final`', async (t) => {
  const viewer = await harness(t, payload({ flujo: 'base', disponible: false, evaluacion: null, rubrica: null }));
  await flush();
  const root = viewer.document.getElementById('judgeFinalAvance');
  assert.equal(root.hidden, false);
  assert.equal(root.getAttribute('data-judge-avance-etapa'), 'final');
  assert.match(root.textContent, /propuesta completa/);
  assert.equal(viewer.document.getElementById('judgeSgr').hidden, true);
  assert.equal(viewer.document.getElementById('judgeSummary'), null);
});
