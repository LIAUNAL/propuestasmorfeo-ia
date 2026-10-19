/**
 * Structural checks for the dashboard UI fixes of T6 (S9): zoom label, footer
 * version, mobile breakpoints, full run id, FAB gutter, Markdown artifacts and
 * light-theme contrast tokens.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const __dirname = dirname(fileURLToPath(import.meta.url));
const HTML_PATH = resolve(__dirname, '../../src/morfeo/dashboard/static/index.html');
const htmlSource = readFileSync(HTML_PATH, 'utf-8');
const css = (htmlSource.match(/<style>([\s\S]*?)<\/style>/) || [, ''])[1];

function load(t) {
  const dom = new JSDOM(htmlSource, { runScripts: 'dangerously', url: 'http://localhost:8080/' });
  t.after(() => dom.window.close());
  return dom.window;
}

// Rules declared inside every `@media (max-width: Npx)` block with N <= max.
function mobileCss(max) {
  const out = [];
  const re = /@media\s*\(max-width:\s*(\d+)px\)\s*\{/g;
  let m;
  while ((m = re.exec(css))) {
    if (Number(m[1]) > max) continue;
    let depth = 1, i = re.lastIndex;
    while (depth && i < css.length) { if (css[i] === '{') depth++; else if (css[i] === '}') depth--; i++; }
    out.push(css.slice(re.lastIndex, i - 1));
  }
  return out.join('\n');
}

test('el zoom del visor PDF sale de una sola constante (125 %)', (t) => {
  assert.match(htmlSource, /const PDF_DEFAULT_SCALE = 1\.25;/);
  assert.doesNotMatch(htmlSource, /120%/, 'no debe quedar ninguna etiqueta 120%');
  const doc = load(t).document;
  assert.equal(doc.getElementById('pdfZoomLabel').textContent.trim(), '125%');
  const reset = doc.getElementById('btnPdfZoomReset');
  assert.ok(reset, 'Debe existir #btnPdfZoomReset');
  assert.equal(reset.textContent.trim(), '125%');
  assert.match(reset.title, /125%/);
});

test('el pie muestra la versión del paquete desde los datos', (t) => {
  assert.doesNotMatch(htmlSource, /v0\.5\.0/);
  const window = load(t);
  const el = window.document.getElementById('footerVersion');
  assert.ok(el, 'Debe existir #footerVersion');
  window.renderFooterVersion({ version: '0.5.0', package_version: '0.5.5' });
  assert.match(el.textContent, /Morfeo IA v0\.5\.5/);
  assert.match(el.textContent, /kit del proyecto: 0\.5\.0/);
  window.renderFooterVersion({ version: '0.5.5', package_version: '0.5.5' });
  assert.equal(el.textContent.trim(), 'Morfeo IA v0.5.5');
});

test('la corrida activa se muestra completa, con elipsis y tooltip', () => {
  assert.doesNotMatch(htmlSource, /active_run\.split\('-'\)\.slice\(0, 3\)/);
  assert.match(htmlSource, /statRunId'\)\.title\s*=/);
  assert.match(css, /#statRunId\s*\{[^}]*text-overflow:\s*ellipsis/);
});

test('en móvil el visor PDF, la cabecera y el árbol no desbordan la página', () => {
  const mobile = mobileCss(900);
  assert.match(mobile, /\.pdf-workspace-layout\s*\{[^}]*flex-direction:\s*column/);
  assert.match(mobile, /\.pdf-control-panel\s*\{[^}]*width:\s*100%/);
  assert.match(mobile, /\.topbar__actions\s*\{[^}]*flex-wrap:\s*wrap/);
  assert.match(mobileCss(600), /\.tree-groups\s*\{[^}]*flex-direction:\s*column/);
  assert.match(css, /\.pdf-control-panel\s*\{[^}]*max-height:\s*calc\(100vh/);
});

test('el botón flotante tiene un margen reservado debajo del contenido', () => {
  assert.match(css, /--fab-size:/);
  assert.match(css, /main\s*\{[^}]*padding-bottom:\s*calc\([^)]*var\(--fab-size\)/);
});

test('los artefactos Markdown se renderizan escapando el HTML', (t) => {
  const window = load(t);
  const html = window.renderMarkdown('# Título\n\n<script>alert(1)</script> **negrita** y `code`\n\n- a\n- b\n\n| x | y |\n|---|---|\n| 1 | 2 |\n\n> cita\n\n[enlace](https://example.org)');
  assert.match(html, /<h1>Título<\/h1>/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /<strong>negrita<\/strong>/);
  assert.match(html, /<code>code<\/code>/);
  assert.match(html, /<ul><li>a<\/li><li>b<\/li><\/ul>/);
  assert.match(html, /<table>/);
  assert.match(html, /<blockquote>/);
  assert.match(html, /<a href="https:\/\/example\.org" target="_blank" rel="noopener">enlace<\/a>/);
  assert.doesNotMatch(window.renderMarkdown('[x](javascript:alert(1))'), /href="javascript/);
});

test('la tabla de secciones no anuncia un número fijo y desfasado', () => {
  assert.doesNotMatch(htmlSource, /16 Secciones/);
});

test('el árbol oculta los identificadores internos de los nodos', () => {
  assert.match(css, /\.tree-node__id\s*\{[^}]*display:\s*none/);
});

test('el tema claro usa tonos que alcanzan contraste AA', () => {
  const light = (css.match(/\[data-theme="light"\]\s*\{([^}]*)\}/) || [, ''])[1];
  const hex = (name) => (light.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`)) || [])[1];
  const lum = (h) => {
    const c = [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16) / 255)
      .map(v => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  for (const name of ['text-muted', 'text-dim', 'ok', 'accent']) {
    const fg = hex(name);
    assert.ok(fg, `--${name} definido en tema claro`);
    assert.ok(ratio(fg, hex('surface-2')) >= 4.5, `--${name} ${fg} debe alcanzar 4.5:1 sobre --surface-2`);
  }
});

test('las etiquetas del árbol ignoran los saltos manuales pensados para TikZ', () => {
  assert.match(htmlSource, /escapeHtml\(text\)\.replace\(\/\\s\*\\n\\s\*\/g, ' '\)/);
  assert.match(mobileCss(600), /\.tree-row > \.tree-node\s*\{[^}]*flex:\s*1 1 140px/);
});
