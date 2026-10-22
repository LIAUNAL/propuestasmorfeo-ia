/**
 * Panel Secciones en el flujo SGR (odd/tasks/sgr-secciones-reglas.md, S1-S2).
 * Con flujo "sgr", el modal de §3 muestra la estructura MGA y el bloque
 * «### SGR §N» de la guía del proyecto; en el flujo base queda igual.
 */

import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const REPO = fileURLToPath(new URL('../../', import.meta.url)).replace(/\/$/, '');
const INDEX = fs.readFileSync(path.resolve(REPO, 'src/morfeo/dashboard/static/index.html'), 'utf8');

const BLOCKS = {
  '§3': 'Además de las reglas de la guía base:\n\n* **Estructura de §3.** Tres subsecciones:\n  1. `\\subsection{Problema central}`: el tronco.\n  2. Situación existente.\n\n  La sección cierra con la pregunta.\n* **Localización.** El problema central nombra el territorio.',
  'A19': '* **Alineación.** Tabla de planes <script>x</script>.',
};

const windows = [];
after(() => windows.forEach(w => w.close()));

const tick = () => new Promise(resolve => setTimeout(resolve, 0));

async function openModal(flujo, secId) {
  const calls = [];
  const dom = new JSDOM(INDEX, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'http://localhost:8000/',
    beforeParse(window) {
      window.localStorage = { _d: {}, getItem(k) { return this._d[k] || null; }, setItem(k, v) { this._d[k] = String(v); } };
      window.fetch = (url) => {
        calls.push(String(url));
        const body = String(url).startsWith('/api/guide/sgr')
          ? { ok: true, flujo, blocks: BLOCKS }
          : { flujo, sections: [], gates: [], telemetria: [], pipeline_units: [] };
        return Promise.resolve({ ok: true, json: () => Promise.resolve(body), text: () => Promise.resolve('') });
      };
      window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      window.requestAnimationFrame = (cb) => setTimeout(cb, 0);
    },
  });
  const { window } = dom;
  windows.push(window);
  for (let i = 0; i < 20; i++) await tick();
  window.openSectionStructure(secId);
  for (let i = 0; i < 10; i++) await tick();
  return { body: window.document.getElementById('secModalBody'), title: window.document.getElementById('secModalTitle'), calls };
}

test('SGR: §3 muestra la estructura MGA y las reglas explícitas de la guía SGR', async () => {
  const { body, title, calls } = await openModal('sgr', '03_descripcion_problema');
  assert.match(title.textContent, /Planteamiento del problema \(MGA\)/);
  const html = body.innerHTML;
  for (const label of ['Problema central', 'Situación existente', 'Causa directa C1', 'Causa directa C3', 'Magnitud del problema', 'Cierre']) {
    assert.ok(html.includes(label), `falta el párrafo ${label}`);
  }
  assert.ok(!html.includes('Desafíos técnicos de IA y lista de subproblemas'), 'no debe mostrar el párrafo 2 base');
  const block = body.querySelector('.sgr-rules-block');
  assert.ok(block, 'falta el bloque de reglas SGR');
  assert.equal(block.dataset.sgrKey, '§3');
  assert.match(block.textContent, /Reglas explícitas de la guía SGR \(§3\)/);
  assert.equal(block.querySelector('strong').textContent, 'Estructura de §3.');
  assert.equal(block.querySelectorAll('ol li').length, 2);
  assert.match(block.querySelector('code').textContent, /\\subsection\{Problema central\}/);
  assert.match(block.textContent, /La sección cierra con la pregunta/);
  assert.ok(calls.includes('/api/guide/sgr'));
});

test('SGR: un anexo MGA muestra solo su bloque de la guía, con el HTML escapado', async () => {
  const { body, title } = await openModal('sgr', '19_alineacion_planes');
  assert.match(title.textContent, /A19/);
  const block = body.querySelector('.sgr-rules-block');
  assert.equal(block.dataset.sgrKey, 'A19');
  assert.equal(body.querySelector('script'), null);
  assert.match(block.textContent, /<script>x<\/script>/);
});

test('base: §3 conserva sus párrafos y no pide la guía SGR', async () => {
  const { body, title, calls } = await openModal('base', '03_descripcion_problema');
  assert.match(title.textContent, /Descripción del problema y pregunta de investigación/);
  assert.ok(body.innerHTML.includes('Contexto general de la problemática'));
  assert.ok(body.innerHTML.includes('Desafíos técnicos de IA y lista de subproblemas'));
  assert.equal(body.querySelector('.sgr-rules-block'), null);
  assert.ok(!calls.includes('/api/guide/sgr'));
});
