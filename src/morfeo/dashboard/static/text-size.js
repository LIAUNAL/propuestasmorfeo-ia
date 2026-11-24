/**
 * text-size.js: the dashboard's text-size control (×1, ×1.25, ×1.5, ×2).
 *
 * Ported from papersmith-ai (command_center/static/text-size.js). The page
 * sizes its text and spacing in rem, so scaling the root font size scales the
 * whole dashboard the way a reader expects from "bigger text", without touching
 * each rule. The choice is remembered per browser under `morfeo.textScale`.
 * This file runs in <head>, before the body is drawn, so a reload never flashes
 * the default size first.
 *
 * The few sizes the page keeps in px (the xterm terminal, SVG timeline labels)
 * read the active scale from `data-text-scale` on <html> and listen for the
 * `textscalechange` event (detail: { scale }) dispatched on document.
 */
(function () {
  'use strict';

  const KEY = 'morfeo.textScale';
  const SCALES = ['1', '1.25', '1.5', '2'];

  function stored() {
    try {
      const value = window.localStorage.getItem(KEY);
      return SCALES.includes(value) ? value : '1';
    } catch (_) {
      return '1';
    }
  }

  function apply(scale) {
    const value = SCALES.includes(String(scale)) ? String(scale) : '1';
    document.documentElement.style.setProperty('--text-scale', value);
    document.documentElement.dataset.textScale = value;
    return value;
  }

  function choose(scale) {
    const value = apply(scale);
    try { window.localStorage.setItem(KEY, value); } catch (_) { /* private mode: this page only */ }
    const select = document.getElementById('textSizeSelect');
    if (select) select.value = value;
    if (typeof document.dispatchEvent === 'function' && typeof CustomEvent === 'function') {
      document.dispatchEvent(new CustomEvent('textscalechange', { detail: { scale: value } }));
    }
    return value;
  }

  apply(stored());

  document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('textSizeSelect');
    if (!select) return;
    select.value = stored();
    select.addEventListener('change', () => { select.value = choose(select.value); });
  });

  window.setTextScale = choose;
})();
