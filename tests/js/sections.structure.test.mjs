/**
 * Pruebas unitarias para la columna Estructura, el botón Ver y el modal interactivo
 * de desglose canónico de secciones, mini-grafo de dependencias y reglas de redacción.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const REPO = fileURLToPath(new URL('../../', import.meta.url)).replace(/\/$/, '');

test('la tabla de secciones incluye la columna Estructura en el encabezado y el modal de estructura en el DOM', () => {
  const indexHtml = fs.readFileSync(path.resolve(REPO, 'src/morfeo/dashboard/static/index.html'), 'utf8');
  assert.ok(indexHtml.includes('<th>Estructura</th>'), 'La tabla de secciones debe incluir la columna Estructura');
  assert.ok(indexHtml.includes('id="sectionStructureModal"'), 'Debe existir el modal sectionStructureModal en index.html');
  assert.ok(indexHtml.includes('id="secModalTitle"'), 'Debe existir el elemento secModalTitle para el título de la sección');
  assert.ok(indexHtml.includes('id="secModalBody"'), 'Debe existir el elemento secModalBody para el contenido detallado');
});

test('openSectionStructure renderiza principio, mini-grafo de conexiones, párrafos y reglas', () => {
  const indexHtml = fs.readFileSync(path.resolve(REPO, 'src/morfeo/dashboard/static/index.html'), 'utf8');
  const dom = new JSDOM(indexHtml, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'http://localhost:8000/',
    beforeParse(window) {
      window.localStorage = {
        _data: {},
        getItem(k) { return this._data[k] || null; },
        setItem(k, v) { this._data[k] = String(v); }
      };
      window.fetch = () => Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ sections: [], gates: [], telemetria: [], pipeline_units: [] }),
        text: () => Promise.resolve(''),
      });
      window.matchMedia = () => ({ matches: false, addListener: () => {}, removeListener: () => {} });
      window.requestAnimationFrame = (cb) => setTimeout(cb, 0);
    }
  });

  const { window } = dom;
  const doc = window.document;

  assert.ok(typeof window.openSectionStructure === 'function', 'openSectionStructure debe ser una función global');
  assert.ok(typeof window.closeSectionStructureModal === 'function', 'closeSectionStructureModal debe ser una función');
  assert.ok(window.SECTIONS_STRUCTURE_DATA, 'SECTIONS_STRUCTURE_DATA debe estar definido');

  // Verificar que §3 tiene datos canónicos completos
  const sec3 = window.SECTIONS_STRUCTURE_DATA['03_descripcion_problema'];
  assert.ok(sec3, '§3 debe estar en SECTIONS_STRUCTURE_DATA');
  assert.equal(sec3.code, '§3');
  assert.ok(sec3.principle.length > 30, 'El principio de §3 debe estar detallado');
  assert.ok(sec3.connections.outputs.some(o => o.code === '§7'), '§3 debe tener salida hacia §7');
  assert.ok(sec3.paragraphs.length >= 6, '§3 debe tener al menos 6 párrafos descritos');
  assert.ok(sec3.rules.allowed.length >= 2, '§3 debe tener reglas permitidas');
  assert.ok(sec3.rules.forbidden.length >= 2, '§3 debe tener reglas prohibidas');

  // Abrir la estructura de §3
  window.openSectionStructure('03_descripcion_problema');

  const modal = doc.getElementById('sectionStructureModal');
  assert.ok(modal.classList.contains('active'), 'El modal debe tener la clase active al abrirse');
  assert.equal(modal.style.display, 'flex');

  const titleEl = doc.getElementById('secModalTitle');
  assert.ok(titleEl.textContent.includes('§3'), 'El título del modal debe contener §3');
  assert.ok(titleEl.textContent.includes('Descripción del problema'), 'El título debe indicar la sección');

  const bodyEl = doc.getElementById('secModalBody');
  const bodyText = bodyEl.textContent;

  // Verificar los 4 bloques exigidos por el usuario:
  // 1. Principio básico
  assert.ok(bodyText.includes('Principio Básico y Propósito Rector'), 'Debe incluir el bloque de principio básico');
  assert.ok(bodyText.includes(sec3.principle), 'Debe contener la descripción del principio de §3');

  // 2. Conexión como grafo pequeño
  assert.ok(bodyText.includes('Conexión en el Manuscrito (Grafo de Dependencias)'), 'Debe incluir el mini-grafo');
  assert.ok(bodyText.includes('Insumos Directos'), 'Debe mostrar la columna de insumos');
  assert.ok(bodyText.includes('Dependencias Cruzadas'), 'Debe mostrar la columna de dependencias');
  assert.ok(bodyText.includes('§7'), 'Debe mostrar el nodo conectado §7');

  // 3. Descripción párrafo por párrafo
  assert.ok(bodyText.includes('Descripción de la Redacción Párrafo por Párrafo'), 'Debe incluir la descripción párrafo a párrafo');
  assert.ok(bodyText.includes('Subproblema 1 (SP1)'), 'Debe listar el párrafo de SP1');
  assert.ok(bodyText.includes('Subproblema 2 (SP2)'), 'Debe listar el párrafo de SP2');
  assert.ok(bodyText.includes('Subproblema 3 (SP3)'), 'Debe listar el párrafo de SP3');

  // 4. Reglas permitidas y no permitidas
  assert.ok(bodyText.includes('Reglas Permitidas y No Permitidas'), 'Debe incluir el bloque de reglas');
  assert.ok(bodyText.includes('Permitido y Exigido (DOs)'), 'Debe incluir la sección de permitidos');
  assert.ok(bodyText.includes('No Permitido y Prohibido (DONTs)'), 'Debe incluir la sección de prohibidos');

  // Probar navegación interactiva a través del grafo (ej: clic hacia §7)
  window.openSectionStructure('07_objetivos_especificos');
  assert.ok(titleEl.textContent.includes('§7'), 'El modal debe navegar a §7 al invocarla');
  assert.ok(bodyEl.textContent.includes('Fundamentos y caracterización (OE1)'), 'Debe mostrar los párrafos de OE1');

  // Cerrar el modal
  window.closeSectionStructureModal();
  assert.equal(modal.classList.contains('active'), false, 'El modal no debe tener la clase active al cerrarse');
  assert.equal(modal.style.display, 'none');

  dom.window.close();
});
