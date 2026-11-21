// «⟳ Actualizar tablero»: the topbar button regenerates what the board derives
// (POST /api/board/refresh: the run's graphs and the project status), re-reads
// the status and reports where the project stands in #boardStatus: the current
// unit, the checks it still lacks, the open or failed gates, the generators
// that failed and a «Siguiente» button that sends the next command to the
// embedded terminal. Port of papersmith-ai's board-refresh.js.
//
// `morfeo ui` runs the same refresh once when the server starts; on load this
// script reads GET /api/board/summary and reports that start-up refresh once
// per server run, polling every 3 s while it is still running.
//
// Loaded before the page's inline script: page helpers (escapeHtml, loadStatus,
// sendTerminalQuickCommand) are looked up when used, never at load time.
//
// Public surface: window.boardRefresh = { run, message, render, showStartup,
// sendNext } and the global refreshBoard() the button calls.
(function () {
  'use strict';

  const PANEL_ID = 'boardStatus';
  const BUTTON_ID = 'boardRefreshBtn';
  const SEEN_KEY = 'morfeo-board-refresh-seen';
  const MAX_MISSING = 6;
  const POLL_MS = 3000;
  const MAX_POLLS = 100;
  const BUTTON_LABEL = '⟳ <span class="btn__label">Actualizar tablero</span>';

  // The page's escape helper when it is there; the same rules otherwise.
  function esc(value) {
    const text = value == null ? '' : String(value);
    if (typeof window.escapeHtml === 'function') return window.escapeHtml(text);
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  const STATE_LABELS = {
    verified: 'aprobada', skipped: 'omitida', running: 'en curso',
    partial: 'incompleta', pending: 'pendiente', failed: 'fallida',
  };

  function gateNames(list) {
    return list.map((g) => (g.name ? `${g.id} · ${g.name}` : g.id)).join(', ');
  }

  let lastNextCommand = '';

  // The tone and HTML of a refresh result (or a bare { summary }). Pure apart
  // from remembering the next command, so it is testable without a server.
  function message(result, origin) {
    const summary = (result && result.summary) || {};
    const artifacts = (result && result.artifacts) || [];
    const tone = summary.tone || 'info';
    const current = summary.current;
    let headline;
    if (!summary.active_run) headline = 'No hay una corrida activa';
    else if (tone === 'done') headline = 'Todas las unidades están aprobadas';
    else if (tone === 'alert') headline = 'Atención: una compuerta falló';
    else if (current) headline = `Estado actual: ${current.id} · ${current.name}`;
    else headline = 'Estado actual del proyecto';

    const lines = [];
    lines.push(`${summary.units_completed || 0} de ${summary.units_total || 0} unidades aprobadas`
      + ` · ${summary.gates_passed || 0} de ${summary.gates_total || 0} compuertas aprobadas`);
    if (current && STATE_LABELS[current.state]) {
      lines.push(`La unidad ${current.id} está ${STATE_LABELS[current.state]}`);
    }
    if ((summary.failed_gates || []).length) lines.push(`Compuertas fallidas: ${gateNames(summary.failed_gates)}`);
    if ((summary.open_gates || []).length) lines.push(`Compuertas pendientes: ${gateNames(summary.open_gates)}`);
    const failed = summary.failed_artifacts || artifacts.filter((a) => a.state === 'failed');
    if (failed.length) {
      lines.push('No se pudieron regenerar: '
        + failed.map((a) => `${a.label || a.id}: ${a.detail}`).join('; '));
    }
    const skipped = artifacts.filter((a) => a.state === 'skipped');
    if (skipped.length) {
      lines.push('Sin entrada todavía: ' + skipped.map((a) => `${a.label || a.id} (${a.detail})`).join('; '));
    }

    const missing = summary.missing || [];
    const missingItems = missing.slice(0, MAX_MISSING).map((label) => `<li>${esc(label)}</li>`);
    if (missing.length > MAX_MISSING) {
      missingItems.push(`<li>…y ${esc(missing.length - MAX_MISSING)} más</li>`);
    }

    lastNextCommand = summary.next_command || '';
    const when = origin === 'startup' ? 'actualizado al iniciar morfeo ui'
      : origin === 'summary' ? 'estado actual'
        : `actualizado a las ${new Date().toLocaleTimeString()}`;
    const next = lastNextCommand
      ? `<button type="button" class="btn btn--primary board-status__next" data-board-next title="Enviar a la terminal integrada">Siguiente: <code>${esc(lastNextCommand)}</code></button>`
      : '';
    const html = '<div class="board-status__head">'
      + `<strong class="board-status__title">${esc(headline)}</strong>`
      + `<span class="board-status__when">${esc(when)}</span>`
      + '<button type="button" class="board-status__close" data-board-close aria-label="Cerrar" title="Cerrar">✕</button></div>'
      + `<ul class="board-status__lines">${lines.map((line) => `<li>${esc(line)}</li>`).join('')}</ul>`
      + (missingItems.length
        ? `<p class="board-status__sub">Pasos que aún faltan:</p><ul class="board-status__missing">${missingItems.join('')}</ul>`
        : '')
      + next;
    return { tone, html };
  }

  function panel() {
    return document.getElementById(PANEL_ID);
  }

  function render(result, origin) {
    const box = panel();
    if (!box) return;
    const { tone, html } = message(result, origin);
    box.dataset.tone = tone;
    box.innerHTML = html;
    box.hidden = false;
  }

  function notice(text, tone) {
    const box = panel();
    if (!box) return;
    box.dataset.tone = tone || 'info';
    box.innerHTML = `<div class="board-status__head"><strong class="board-status__title">${esc(text)}</strong>`
      + '<button type="button" class="board-status__close" data-board-close aria-label="Cerrar" title="Cerrar">✕</button></div>';
    box.hidden = false;
  }

  function reloadViews() {
    if (typeof window.loadStatus === 'function') window.loadStatus({ fresh: true });
  }

  function sendNext() {
    if (!lastNextCommand) return false;
    if (typeof window.sendTerminalQuickCommand !== 'function') return false;
    window.sendTerminalQuickCommand(lastNextCommand);
    return true;
  }

  async function run() {
    const btn = document.getElementById(BUTTON_ID);
    if (btn) { btn.disabled = true; btn.innerHTML = '⟳ <span class="btn__label">Actualizando…</span>'; }
    notice('Regenerando los grafos y revisando unidades y compuertas…', 'info');
    try {
      const res = await fetch('/api/board/refresh', { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (res.status === 409) {
        notice('Ya hay una actualización del tablero en curso; intenta de nuevo en un momento', 'warn');
      } else if (!res.ok || !data.ok) {
        notice(`La actualización del tablero falló: ${(data && data.error) || res.status}`, 'alert');
      } else {
        render(data, 'manual');
        markSeen(data);
      }
    } catch (err) {
      notice(`La actualización del tablero falló: ${err && err.message}`, 'alert');
    } finally {
      if (btn) { btn.disabled = false; btn.innerHTML = BUTTON_LABEL; }
      reloadViews();
    }
  }

  function seen(result) {
    try {
      return Boolean(result && result.finished_at)
        && window.sessionStorage.getItem(SEEN_KEY) === result.finished_at;
    } catch (_) {
      return false;
    }
  }

  function markSeen(result) {
    try {
      if (result && result.finished_at) window.sessionStorage.setItem(SEEN_KEY, result.finished_at);
    } catch (_) { /* storage blocked: the report may show again */ }
  }

  // On load: report the start-up refresh once per server run; while it is
  // still running, say so and ask again every POLL_MS.
  async function showStartup(polls) {
    polls = polls || 0;
    let data;
    try {
      const res = await fetch('/api/board/summary');
      if (!res.ok) return;
      data = await res.json();
    } catch (_) {
      return;
    }
    if (data.last_refresh) {
      if (!seen(data.last_refresh)) {
        render(data.last_refresh, 'startup');
        markSeen(data.last_refresh);
        reloadViews();
      }
      return;
    }
    if (data.refreshing && polls < MAX_POLLS) {
      if (!polls) notice('morfeo ui está actualizando el tablero…', 'info');
      setTimeout(() => showStartup(polls + 1), POLL_MS);
      return;
    }
    if (polls) render({ summary: data.summary }, 'summary');
  }

  document.addEventListener('click', (event) => {
    const target = event.target && event.target.closest ? event.target : null;
    if (!target) return;
    if (target.closest('[data-board-close]')) {
      const box = panel();
      if (box) box.hidden = true;
    } else if (target.closest('[data-board-next]')) {
      sendNext();
    }
  });

  window.boardRefresh = { run, message, render, showStartup, sendNext };
  window.refreshBoard = run;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => showStartup(0));
  } else {
    showStartup(0);
  }
})();
