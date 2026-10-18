/**
 * Pruebas estructurales y funcionales del Asistente Flotante y Terminal Web PTY.
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

test('el botón flotante (FAB) y la ventana del terminal existen en el DOM', () => {
  const dom = new JSDOM(htmlSource);
  const doc = dom.window.document;

  const fab = doc.getElementById('morfeoAssistantFab');
  assert.ok(fab, 'Debe existir el botón flotante #morfeoAssistantFab');
  assert.ok(fab.classList.contains('morfeo-fab'), 'El FAB debe tener la clase morfeo-fab');

  const win = doc.getElementById('morfeoTerminalWindow');
  assert.ok(win, 'Debe existir la ventana flotante #morfeoTerminalWindow');
  assert.ok(win.classList.contains('morfeo-terminal-window'), 'La ventana debe tener clase morfeo-terminal-window');

  const select = doc.getElementById('terminalAgentSelect');
  assert.ok(select, 'Debe existir el selector de agentes #terminalAgentSelect');
  const values = Array.from(select.options).map(o => o.value);
  assert.ok(values.includes('herdr'), 'Debe incluir la opción de Herdr (Espejo en Vivo)');
  assert.ok(values.includes('claude'), 'Debe incluir la opción de Claude Code');
  assert.ok(values.includes('opencode'), 'Debe incluir la opción de OpenCode');
  assert.ok(values.includes('pi'), 'Debe incluir la opción de Pi');
  assert.ok(values.includes('agy'), 'Debe incluir la opción de Antigravity (AGY)');
  assert.ok(values.includes('shell'), 'Debe incluir la opción de Shell interactivo');

  const btnExternal = doc.getElementById('btnLaunchExternalTerm');
  assert.ok(btnExternal, 'Debe existir el botón #btnLaunchExternalTerm para abrir terminal nativo');

  const toolsModal = doc.getElementById('morfeoToolsRequiredModal');
  assert.ok(toolsModal, 'Debe existir el modal #morfeoToolsRequiredModal');

  const container = doc.getElementById('xtermContainer');
  assert.ok(container, 'Debe existir el contenedor #xtermContainer');

  const dot = doc.getElementById('terminalStatusDot');
  assert.ok(dot, 'Debe existir el indicador de estado #terminalStatusDot');

  dom.window.close();
});

test('showToolsRequiredModal y closeToolsRequiredModal gestionan el aviso de dependencias', () => {
  const dom = new JSDOM(htmlSource, {
    runScripts: 'dangerously',
    url: 'http://localhost:8080/'
  });

  const { window } = dom;
  const doc = window.document;

  const modal = doc.getElementById('morfeoToolsRequiredModal');
  assert.ok(!modal.classList.contains('is-open'), 'El modal arranca cerrado');

  // Muestra el modal con herramientas faltantes
  window.showToolsRequiredModal({
    ready: false,
    missing: ['herdr', 'terminal'],
    herdr: { installed: false },
    ghostty: { installed: false },
    wezterm: { installed: false }
  });

  assert.ok(modal.classList.contains('is-open'), 'showToolsRequiredModal debe abrir el modal');
  const bodyText = doc.getElementById('morfeoToolsModalBody').textContent;
  assert.ok(bodyText.includes('Herdr'), 'Debe advertir sobre la falta de Herdr');
  assert.ok(bodyText.includes('Ghostty'), 'Debe advertir sobre la falta de Ghostty o WezTerm');

  // Cierra el modal
  window.closeToolsRequiredModal();
  assert.ok(!modal.classList.contains('is-open'), 'closeToolsRequiredModal debe cerrar el modal');

  dom.window.close();
});

test('toggleMorfeoTerminal y toggleMaximizeTerminal alternan los estados en el DOM', () => {
  const dom = new JSDOM(htmlSource, {
    runScripts: 'dangerously',
    url: 'http://localhost:8080/'
  });

  const { window } = dom;
  const doc = window.document;

  // Mock localStorage and fetch
  if (!window.localStorage) {
    window.localStorage = {
      getItem: () => null,
      setItem: () => {}
    };
  }

  const win = doc.getElementById('morfeoTerminalWindow');
  const fab = doc.getElementById('morfeoAssistantFab');

  assert.ok(!win.classList.contains('is-open'), 'La ventana arranca cerrada');

  // Abre el terminal
  window.toggleMorfeoTerminal();
  assert.ok(win.classList.contains('is-open'), 'toggleMorfeoTerminal debe añadir is-open');
  assert.ok(fab.classList.contains('is-active'), 'El FAB debe activarse');

  // Maximizar
  window.toggleMaximizeTerminal();
  assert.ok(win.classList.contains('is-maximized'), 'toggleMaximizeTerminal debe añadir is-maximized');

  // Restaurar tamaño
  window.toggleMaximizeTerminal();
  assert.ok(!win.classList.contains('is-maximized'), 'toggleMaximizeTerminal debe quitar is-maximized');

  // Cierra el terminal
  window.closeMorfeoTerminal();
  assert.ok(!win.classList.contains('is-open'), 'closeMorfeoTerminal debe remover is-open');
  assert.ok(!fab.classList.contains('is-active'), 'El FAB debe desactivarse');

  dom.window.close();
});
