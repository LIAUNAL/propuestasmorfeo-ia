/* Search progress bar of the «Convocatorias» tab (window.cvSearchProgress).
 *
 * The explorador-convocatorias agent stamps each of its five phases in
 * convocatorias/progreso.json; GET /api/convocatorias/progreso returns the
 * server's estimate (percent, remaining_seconds, phase_label, estado, stale).
 * This file only draws it: no estimate is computed here.
 *
 * - Idle (no search, an earlier finished one, or a stale one): the bar is hidden.
 * - Running: «Fase N/5 · <nombre> · ~X % · faltan ~M min», polled every 3 s.
 * - After «Buscar»: «Esperando que el agente empiece…» until the agent resets
 *   the file (a started_at other than the one seen before the click).
 * - Finished while watched: 100 %, the list reloads, then the bar hides.
 * - Stale: hidden, and the panel keeps the message it already shows.
 * Polling runs only while the tab is open (start/stop from index.html).
 */
(function () {
  'use strict';

  const FAST_MS = 3000;
  const IDLE_MS = 15000;
  const DONE_HIDE_MS = 10000;
  // Ten minutes of fast polls without a fresh progress file: give up waiting.
  const WAIT_LIMIT_POLLS = 200;

  const state = {
    active: false, timer: null, hideTimer: null, fetched: false, last: null,
    pending: false, baseline: null, waitPolls: 0, done: false,
  };

  function els() {
    return {
      box: document.getElementById('cvProgress'),
      fill: document.getElementById('cvProgressFill'),
      label: document.getElementById('cvProgressLabel'),
    };
  }

  function remainingText(seconds) {
    const s = Number(seconds) || 0;
    if (s < 60) return 'falta menos de 1 min';
    const minutes = Math.ceil(s / 60);
    return minutes === 1 ? 'falta ~1 min' : `faltan ~${minutes} min`;
  }

  function show(estado, percent, text) {
    const { box, fill, label } = els();
    if (!box) return;
    const pct = Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
    box.hidden = false;
    box.setAttribute('data-estado', estado);
    box.setAttribute('aria-valuenow', String(pct));
    box.setAttribute('aria-valuetext', text);
    if (fill) fill.style.width = `${pct}%`;
    if (label) label.textContent = text;
  }

  function hide() {
    const { box } = els();
    if (!box) return;
    box.hidden = true;
    box.removeAttribute('data-estado');
  }

  function isFresh(p) {
    return Boolean(p && p.started_at && p.started_at !== state.baseline);
  }

  function render() {
    const p = state.last;
    if (state.pending && !isFresh(p)) {
      state.waitPolls += 1;
      if (state.waitPolls > WAIT_LIMIT_POLLS) {
        state.pending = false;
        hide();
        return;
      }
      show('esperando', 0, 'Esperando que el agente empiece la búsqueda…');
      return;
    }
    if (p && p.estado === 'en_curso' && !p.stale) {
      state.done = false;
      show('en_curso', p.percent, `${p.phase_label} · ~${p.percent} % · ${remainingText(p.remaining_seconds)}`);
      return;
    }
    if (p && p.estado === 'terminada' && state.pending) {
      state.pending = false;
      state.done = true;
      show('terminada', 100, 'Búsqueda terminada · 100 %');
      if (typeof window.loadOpportunities === 'function') window.loadOpportunities();
      if (state.hideTimer) clearTimeout(state.hideTimer);
      state.hideTimer = setTimeout(() => {
        state.hideTimer = null;
        state.done = false;
        hide();
      }, DONE_HIDE_MS);
      return;
    }
    if (state.done) return; // the finished bar lingers until its timer hides it
    state.pending = false;
    hide();
  }

  async function fetchProgress() {
    try {
      const res = await fetch('/api/convocatorias/progreso', { cache: 'no-store' });
      const data = await res.json();
      state.last = res.ok && data && data.ok ? data.progreso || null : null;
    } catch (err) {
      state.last = null;
    }
    state.fetched = true;
  }

  function running() {
    return Boolean(state.last && state.last.estado === 'en_curso' && !state.last.stale);
  }

  function schedule() {
    if (state.timer) clearTimeout(state.timer);
    state.timer = null;
    if (!state.active) return;
    state.timer = setTimeout(tick, state.pending || running() ? FAST_MS : IDLE_MS);
  }

  async function tick() {
    state.timer = null;
    if (!state.active) return;
    if (!document.hidden) {
      await fetchProgress();
      if (!state.active) return;
      render();
    }
    schedule();
  }

  async function refresh() {
    await fetchProgress();
    render();
    schedule();
  }

  function start() {
    if (state.active) return;
    state.active = true;
    refresh();
  }

  function stop() {
    state.active = false;
    if (state.timer) clearTimeout(state.timer);
    state.timer = null;
  }

  // Called before the search prompt goes to the terminal: what the file holds
  // now belongs to an earlier search, so only a reset counts as this one.
  async function expectSearch() {
    if (!state.fetched) await fetchProgress();
    state.baseline = state.last ? state.last.started_at || null : null;
    state.pending = true;
    state.waitPolls = 0;
    state.done = false;
    if (state.hideTimer) clearTimeout(state.hideTimer);
    state.hideTimer = null;
    render();
    schedule();
  }

  function cancelSearch() {
    state.pending = false;
    render();
    schedule();
  }

  window.cvSearchProgress = { start, stop, refresh, expectSearch, cancelSearch };
}());
