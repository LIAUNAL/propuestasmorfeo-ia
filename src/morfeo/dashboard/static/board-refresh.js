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
// Texts come from the catalogues static/i18n/<lang>/board-refresh.js; on a
// language switch the report on screen is drawn again in the new language.
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

  // The text of `key` in the dashboard's language (static/i18n.js).
  const tr = (key, vars) => (window.i18n ? window.i18n.t(key, vars) : key);
  // The button's label as the page markup writes it, so the runtime keeps translating it.
  const buttonLabel = () => `⟳ <span class="btn__label" data-i18n="page.refreshBoard">${esc(tr('page.refreshBoard'))}</span>`;

  // The page's escape helper when it is there; the same rules otherwise.
  function esc(value) {
    const text = value == null ? '' : String(value);
    if (typeof window.escapeHtml === 'function') return window.escapeHtml(text);
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  const STATE_KEYS = {
    verified: 'panel.boardRefresh.stateVerified', skipped: 'panel.boardRefresh.stateSkipped',
    running: 'panel.boardRefresh.stateRunning', partial: 'panel.boardRefresh.statePartial',
    pending: 'panel.boardRefresh.statePending', failed: 'panel.boardRefresh.stateFailed',
  };

  function gateNames(list) {
    return list.map((g) => (g.name ? `${g.id} · ${g.name}` : g.id)).join(', ');
  }

  let lastNextCommand = '';
  // What the panel shows, so a language switch can draw it again.
  let shown = null;

  function closeButton() {
    const label = esc(tr('panel.boardRefresh.close'));
    return `<button type="button" class="board-status__close" data-board-close aria-label="${label}" title="${label}">✕</button>`;
  }

  // The tone and HTML of a refresh result (or a bare { summary }). Pure apart
  // from remembering the next command, so it is testable without a server.
  // `time` is the clock reading of a manual refresh (now when absent).
  function message(result, origin, time) {
    const summary = (result && result.summary) || {};
    const artifacts = (result && result.artifacts) || [];
    const tone = summary.tone || 'info';
    const current = summary.current;
    let headline;
    if (!summary.active_run) headline = tr('panel.boardRefresh.noActiveRun');
    else if (tone === 'done') headline = tr('panel.boardRefresh.allUnitsPassed');
    else if (tone === 'alert') headline = tr('panel.boardRefresh.gateFailed');
    else if (current) headline = tr('panel.boardRefresh.currentStatusUnit', { id: current.id, name: current.name });
    else headline = tr('panel.boardRefresh.currentStatus');

    const lines = [];
    lines.push(tr('panel.boardRefresh.counts', {
      units: summary.units_completed || 0, unitsTotal: summary.units_total || 0,
      gates: summary.gates_passed || 0, gatesTotal: summary.gates_total || 0,
    }));
    if (current && STATE_KEYS[current.state]) {
      lines.push(tr('panel.boardRefresh.unitState', { id: current.id, state: tr(STATE_KEYS[current.state]) }));
    }
    if ((summary.failed_gates || []).length) lines.push(tr('panel.boardRefresh.failedGates', { gates: gateNames(summary.failed_gates) }));
    if ((summary.open_gates || []).length) lines.push(tr('panel.boardRefresh.openGates', { gates: gateNames(summary.open_gates) }));
    const failed = summary.failed_artifacts || artifacts.filter((a) => a.state === 'failed');
    if (failed.length) {
      lines.push(tr('panel.boardRefresh.notRegenerated', {
        items: failed.map((a) => `${a.label || a.id}: ${a.detail}`).join('; '),
      }));
    }
    const skipped = artifacts.filter((a) => a.state === 'skipped');
    if (skipped.length) {
      lines.push(tr('panel.boardRefresh.noInputYet', {
        items: skipped.map((a) => `${a.label || a.id} (${a.detail})`).join('; '),
      }));
    }

    const missing = summary.missing || [];
    const missingItems = missing.slice(0, MAX_MISSING).map((label) => `<li>${esc(label)}</li>`);
    if (missing.length > MAX_MISSING) {
      missingItems.push(`<li>${esc(tr('panel.boardRefresh.andMore', { n: missing.length - MAX_MISSING }))}</li>`);
    }

    lastNextCommand = summary.next_command || '';
    const when = origin === 'startup' ? tr('panel.boardRefresh.updatedAtStartup')
      : origin === 'summary' ? tr('panel.boardRefresh.whenSummary')
        : tr('panel.boardRefresh.updatedAt', { time: time || new Date().toLocaleTimeString() });
    const next = lastNextCommand
      ? `<button type="button" class="btn btn--primary board-status__next" data-board-next title="${esc(tr('panel.boardRefresh.sendToTerminal'))}">${tr('panel.boardRefresh.nextHtml', { command: esc(lastNextCommand) })}</button>`
      : '';
    const html = '<div class="board-status__head">'
      + `<strong class="board-status__title">${esc(headline)}</strong>`
      + `<span class="board-status__when">${esc(when)}</span>`
      + `${closeButton()}</div>`
      + `<ul class="board-status__lines">${lines.map((line) => `<li>${esc(line)}</li>`).join('')}</ul>`
      + (missingItems.length
        ? `<p class="board-status__sub">${esc(tr('panel.boardRefresh.missingSteps'))}</p><ul class="board-status__missing">${missingItems.join('')}</ul>`
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
    const time = origin === 'startup' || origin === 'summary' ? '' : new Date().toLocaleTimeString();
    shown = { result, origin, time };
    const { tone, html } = message(result, origin, time);
    box.dataset.tone = tone;
    box.innerHTML = html;
    box.hidden = false;
  }

  // `key` and `vars` name a catalogue text, kept so a language switch redraws it.
  function notice(key, vars, tone) {
    const box = panel();
    if (!box) return;
    shown = { key, vars, tone };
    box.dataset.tone = tone || 'info';
    box.innerHTML = `<div class="board-status__head"><strong class="board-status__title">${esc(tr(key, vars))}</strong>`
      + `${closeButton()}</div>`;
    box.hidden = false;
  }

  // A language switch: the panel's own texts change at once; the server's
  // labels in a report (unit and gate names, missing steps) are read again in
  // the new language from GET /api/board/summary, which holds the same report.
  async function redraw() {
    const box = panel();
    if (!box || box.hidden || !shown) return;
    if (shown.key) {
      notice(shown.key, shown.vars, shown.tone);
      return;
    }
    const draw = (result) => {
      const { tone, html } = message(result, shown.origin, shown.time);
      box.dataset.tone = tone;
      box.innerHTML = html;
    };
    draw(shown.result);
    try {
      const res = await fetch('/api/board/summary');
      if (!res.ok) return;
      const data = await res.json();
      const result = shown.origin === 'summary' ? { summary: data.summary } : data.last_refresh;
      if (result && result.summary && !box.hidden && shown && !shown.key) {
        shown.result = result;
        draw(result);
      }
    } catch (_) { /* the report keeps the labels it had */ }
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
    if (btn) { btn.disabled = true; btn.innerHTML = `⟳ <span class="btn__label">${esc(tr('panel.boardRefresh.refreshing'))}</span>`; }
    notice('panel.boardRefresh.regenerating', null, 'info');
    try {
      const res = await fetch('/api/board/refresh', { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (res.status === 409) {
        notice('panel.boardRefresh.busy', null, 'warn');
      } else if (!res.ok || !data.ok) {
        notice('panel.boardRefresh.failed', { reason: (data && data.error) || res.status }, 'alert');
      } else {
        render(data, 'manual');
        markSeen(data);
      }
    } catch (err) {
      notice('panel.boardRefresh.failed', { reason: err && err.message }, 'alert');
    } finally {
      if (btn) { btn.disabled = false; btn.innerHTML = buttonLabel(); }
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
      if (!polls) notice('panel.boardRefresh.startupRefreshing', null, 'info');
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
  document.addEventListener('languagechange', redraw);

  window.boardRefresh = { run, message, render, showStartup, sendNext };
  window.refreshBoard = run;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => showStartup(0));
  } else {
    showStartup(0);
  }
})();
