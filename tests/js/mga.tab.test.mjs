/**
 * Pestaña «MGA resumido».
 *
 * Se ejecuta el JavaScript real del tablero bajo jsdom; `/api/artifact` se
 * sustituye por un doble determinista. Se observa el orden de las pestañas, el
 * archivo que se pide y el Markdown renderizado (títulos, tabla y la línea base
 * resaltada).
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { createViewerHarness, flush } from './harness.mjs';

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

async function harness(t, respond) {
  const viewer = await createViewerHarness({ numPages: 1 });
  t.after(() => viewer.dispose());
  const requests = [];
  viewer.window.fetch = async (url) => {
    const u = String(url);
    requests.push(u);
    if (u.includes('/api/artifact')) return respond(u);
    return text('', 503);
  };
  return { viewer, requests };
}

test('la pestaña queda entre «Árbol de problemas y objetivos» y «Secciones»', async (t) => {
  const { viewer } = await harness(t, () => text(MGA));
  const labels = Array.from(viewer.document.querySelectorAll('.tab-nav__btn')).map(b => b.textContent.trim());
  const i = labels.indexOf('MGA resumido');
  assert.ok(i > 0, 'la pestaña existe');
  assert.equal(labels[i - 1], 'Árbol de problemas y objetivos');
  assert.equal(labels[i + 1], 'Secciones');
  assert.ok(viewer.document.getElementById('pane-mga'));
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

test('sin el archivo, explica que lo escribe la Fase 1', async (t) => {
  const { viewer } = await harness(t, () => text('File not found', 404));
  await viewer.viewer('loadMgaResumido');
  await flush();
  const box = viewer.document.getElementById('mgaContent');
  assert.match(box.textContent, /Fase 1/);
  assert.equal(box.querySelector('table'), null);
});

test('navegar a la pestaña dispara la carga', async (t) => {
  const { viewer, requests } = await harness(t, () => text(MGA));
  await viewer.viewer('navigateTab', 'mga');
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

test('la pestaña muestra las reglas de trabajo del MGA resumido', async (t) => {
  const { viewer } = await harness(t, () => text(MGA));
  const rules = viewer.document.querySelector('#pane-mga details.tree-rules#mgaRules');
  assert.ok(rules, 'el desplegable de reglas existe');
  assert.equal(rules.querySelector('summary').textContent.trim(), 'Reglas para construir el MGA resumido');
  const txt = rules.textContent;
  for (const rule of [/copiado textual/, /Descripción de la situación existente:/, /desde los antecedentes y el sector de aplicación/, /departamentos o regiones/, /Causa directa 1/, /plataforma interoperable/, /apropiación social/, /línea base/, /tabla/, /\[cifra por confirmar\]/]) {
    assert.match(txt, rule);
  }
  assert.doesNotMatch(txt, /Contexto general/);
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
