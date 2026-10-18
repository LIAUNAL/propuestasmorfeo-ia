/**
 * Pruebas estructurales del panel Grafos Proyecto y alternancia al Grafo del Manuscrito.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const HTML_PATH = resolve(__dirname, '../../src/morfeo/dashboard/static/index.html');
const htmlSource = readFileSync(HTML_PATH, 'utf-8');

test('el panel de Grafos Proyecto incluye los 3 botones de grafos y el botón de manuscrito funciona', () => {
  const dom = new JSDOM(htmlSource, {
    runScripts: 'dangerously',
    url: 'http://localhost:8080/'
  });

  const { window } = dom;
  const doc = window.document;

  const pane = doc.getElementById('pane-atlas');
  assert.ok(pane, 'Debe existir el panel #pane-atlas');

  const btnPapers = doc.getElementById('btnGraphPapers');
  const btnVault = doc.getElementById('btnGraphVault');
  const btnManuscript = doc.getElementById('btnGraphManuscript');
  const btnBuild = doc.getElementById('btnBuildGraph');
  const iframe = doc.getElementById('graphIframe');
  const linkOpen = doc.getElementById('linkOpenGraph');

  assert.ok(btnPapers, 'Debe existir #btnGraphPapers');
  assert.ok(btnVault, 'Debe existir #btnGraphVault');
  assert.ok(btnManuscript, 'Debe existir #btnGraphManuscript');
  assert.ok(btnBuild, 'Debe existir #btnBuildGraph');
  assert.ok(iframe, 'Debe existir #graphIframe');

  // Verifica que archifyGatesPanel fue eliminado de pane-flow
  const archifyGatesPanel = doc.getElementById('archifyGatesPanel');
  assert.equal(archifyGatesPanel, null, 'El panel archifyGatesPanel debe haber sido eliminado');

  // Alterna a manuscrito
  window.switchGraph('manuscript');

  assert.ok(btnManuscript.classList.contains('btn--primary'), 'El botón de manuscrito debe estar activo');
  assert.ok(!btnPapers.classList.contains('btn--primary'), 'El botón de papers debe quedar inactivo');
  assert.ok(!btnVault.classList.contains('btn--primary'), 'El botón de vault debe quedar inactivo');
  assert.equal(iframe.src, 'http://localhost:8080/api/graph/manuscript');
  assert.equal(linkOpen.href, 'http://localhost:8080/api/graph/manuscript');

  dom.window.close();
});
