/**
 * Pruebas para la eliminación del panel redundante de fases y
 * la visualización del propósito de 2 líneas al dar clic en cajas del flujo Archify.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const REPO = fileURLToPath(new URL('../../', import.meta.url)).replace(/\/$/, '');

test('el panel redundante de fases del flujo ha sido eliminado del tablero', () => {
  const indexHtml = fs.readFileSync(path.resolve(REPO, 'src/morfeo/dashboard/static/index.html'), 'utf8');
  assert.equal(indexHtml.includes('id="archifyPhasesGrid"'), false, 'archifyPhasesGrid no debe existir en index.html');
  assert.equal(indexHtml.includes('Fases del Pipeline Metodológico de Redacción (Flujo general)'), false, 'El título del panel redundante no debe existir');
  assert.equal(indexHtml.includes('id="archifyStagePurposePanel"'), true, 'archifyStagePurposePanel debe existir en index.html');
});

test('las cajas del diagrama Archify tienen descripciones de propósito de 2 líneas y responden al clic', async () => {
  const flowHtml = fs.readFileSync(path.resolve(REPO, 'docs/diagrams/morfeo-pipeline-flow.html'), 'utf8');
  const dom = new JSDOM(flowHtml, {
    runScripts: 'dangerously',
    beforeParse(window) {
      window.matchMedia = () => ({ matches: false, addListener: () => {}, removeListener: () => {} });
      window.requestAnimationFrame = (cb) => setTimeout(cb, 0);
    }
  });
  const doc = dom.window.document;

  const sampleNodes = ['cliInit', 'cmdAnalizar', 'invProb', 'gate1', 'bibSota', 'redJust', 'presup', 'coordEns'];
  for (const id of sampleNodes) {
    const node = doc.querySelector(`g[data-node-id="${id}"]`);
    assert.ok(node, `El nodo ${id} debe existir en el diagrama`);
    const titleEl = node.querySelector('title');
    assert.ok(titleEl && titleEl.textContent.includes('Propósito:'), `El nodo ${id} debe incluir Propósito en su title`);

    // Simular clic
    node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 35));

    const box = doc.getElementById('focus-purpose-box');
    assert.ok(box, `El elemento focus-purpose-box debe crearse al hacer clic en ${id}`);
    const l1 = box.querySelector('.semantic-passport-purpose-line1');
    const l2 = box.querySelector('.semantic-passport-purpose-line2');
    assert.ok(l1 && l1.textContent.trim().length > 10, `Línea 1 del propósito de ${id} debe existir`);
    assert.ok(l2 && l2.textContent.trim().length > 10, `Línea 2 del propósito de ${id} debe existir`);
  }
});
