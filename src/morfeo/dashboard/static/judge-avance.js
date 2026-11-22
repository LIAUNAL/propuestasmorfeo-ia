/**
 * judge-avance.js: the «Juez de avance» block, the stage judge that scores the
 * proposal up to a panel (papersmith paper-review-panel pattern).
 *
 * The block reads GET /api/judge-avance?etapa=<etapa> (the round recorded by
 * scripts/juez_avance.py in artefactos/juez/avance_<etapa>.json) and shows the
 * score badge coloured by threshold, the verdict, the idea summary, strengths,
 * weaknesses with their suggested action, alerts by level and the earlier
 * rounds collapsed. «Evaluar hasta aquí» asks POST /api/judge-avance/run for
 * the slash command and types it into the embedded terminal; the block then
 * stays pending until a newer round arrives through polling. Advisory: it
 * never approves a gate. Every value is escaped before insertion.
 *
 * Public surface (window.JudgeAvance):
 *   mount(root, { etapa, interval, fetch, send }) -> controller
 *     etapa     'arbol' (trees pane), 'novedad' (novelty pane) or 'final' (the
 *               «Juez final» fold of the PDF preview, base flow); default 'arbol'
 *     interval  polling period in ms while started; default 5000
 *     fetch     fetch implementation; default window.fetch at call time
 *     send      async (prompt) => boolean; default window.sendTerminalPrompt
 *   controller: refresh(), run(), retry(), start(), stop(), polling, data
 *   render(data, { pending, etapa }) -> HTML of the body (pure)
 *   tone(score) -> 'ok' | 'warn' | 'bad'
 *   THRESHOLDS  { ok: 75, warn: 50 }
 *
 * Texts come from static/i18n/<lang>/judge-avance.js; a language switch draws
 * every mounted block again and reads the round once more (the server's
 * messages follow the language too). The judge's own round is shown as written.
 */
(function () {
  'use strict';

  // The text of `key` in the dashboard's language (static/i18n.js).
  const tr = (key, vars) => (window.i18n ? window.i18n.t(key, vars) : key);

  const THRESHOLDS = { ok: 75, warn: 50 };
  const LEVELS = [['alta', 'panel.judgeAvance.levelHigh'], ['media', 'panel.judgeAvance.levelMedium'],
    ['baja', 'panel.judgeAvance.levelLow']];
  const STAGES = {
    arbol: 'panel.judgeAvance.stageArbol',
    novedad: 'panel.judgeAvance.stageNovedad',
    final: 'panel.judgeAvance.stageFinal',
  };

  // UI copy per stage. `arbol` and `novedad` judge the proposal up to a panel;
  // `final` judges the whole proposal and is the final judge of the base flow.
  function copy(etapa) {
    if (etapa === 'final') {
      return {
        name: tr('panel.judgeAvance.finalName'),
        intro: tr('panel.judgeAvance.finalIntro'),
        run: tr('panel.judgeAvance.finalRun'),
        empty: tr('panel.judgeAvance.finalEmpty'),
        pending: tr('panel.judgeAvance.finalPending'),
      };
    }
    return {
      name: tr('panel.judgeAvance.name'),
      intro: tr('panel.judgeAvance.intro', { stage: tr(STAGES[etapa] || STAGES.arbol) }),
      run: tr('panel.judgeAvance.run'),
      empty: tr('panel.judgeAvance.empty'),
      pending: tr('panel.judgeAvance.pending'),
    };
  }

  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);
  const list = (v) => (Array.isArray(v) ? v : []);
  const obj = (v) => (v && typeof v === 'object' && !Array.isArray(v) ? v : {});

  function score(value) {
    const n = Number(value);
    return Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : null;
  }

  function tone(value) {
    const n = score(value);
    if (n === null) return 'bad';
    if (n >= THRESHOLDS.ok) return 'ok';
    if (n >= THRESHOLDS.warn) return 'warn';
    return 'bad';
  }

  function badge(round) {
    const n = score(round.puntaje);
    return `<span class="ja-score ja-tone--${tone(n)}"><strong>${n === null ? '?' : n}</strong><small>/100</small></span>`;
  }

  function bar(round) {
    const n = score(round.puntaje) || 0;
    return `<div class="ja-bar" role="img" aria-label="${esc(tr('panel.judgeAvance.scoreAria', { n }))}">
        <span class="ja-bar__fill ja-tone--${tone(n)}" style="width: ${n}%"></span>
        <span class="ja-bar__mark" style="left: ${THRESHOLDS.ok}%" title="${esc(tr('panel.judgeAvance.threshold', { n: THRESHOLDS.ok }))}"></span>
      </div>`;
  }

  const evidence = (text) => `<small class="ja-evidence">${esc(tr('panel.judgeAvance.evidence', { text }))}</small>`;

  function strengths(items) {
    if (!items.length) return '';
    return `<h5 class="ja-h">${esc(tr('panel.judgeAvance.strengths'))}</h5><ul class="ja-list ja-strengths">${items.map((f) => `
        <li><span>${esc(f.texto)}</span>${f.evidencia ? evidence(f.evidencia) : ''}</li>`).join('')}</ul>`;
  }

  function weaknesses(items) {
    if (!items.length) return '';
    return `<h5 class="ja-h">${esc(tr('panel.judgeAvance.weaknesses'))}</h5><ul class="ja-list ja-weaknesses">${items.map((d) => `
        <li><span>${esc(d.texto)}</span>${d.evidencia ? evidence(d.evidencia) : ''}
          ${d.accion ? `<p class="ja-action"><strong>${esc(tr('panel.judgeAvance.suggestedAction'))}</strong> ${esc(d.accion)}</p>` : ''}</li>`).join('')}</ul>`;
  }

  function alerts(items) {
    const ordered = LEVELS.flatMap(([level]) => items.filter((a) => obj(a).nivel === level));
    const body = ordered.length
      ? `<ul class="ja-list ja-alerts">${ordered.map((a) => {
        const level = LEVELS.find(([l]) => l === a.nivel);
        const label = level ? tr(level[1]) : a.nivel;
        return `<li class="ja-alert" data-nivel="${esc(a.nivel)}"><span class="ja-level ja-level--${esc(a.nivel)}">${esc(label)}</span>
            <span class="ja-alert__text">${esc(a.texto)}${a.donde ? ` <small class="ja-evidence">(${esc(a.donde)})</small>` : ''}</span></li>`;
      }).join('')}</ul>`
      : `<p class="ja-muted">${esc(tr('panel.judgeAvance.noAlerts'))}</p>`;
    return `<h5 class="ja-h">${esc(tr('panel.judgeAvance.alerts'))}</h5>${body}`;
  }

  function detail(round) {
    return `${round.resumen_idea ? `<h5 class="ja-h">${esc(tr('panel.judgeAvance.ideaSummary'))}</h5><p class="ja-idea">${esc(round.resumen_idea)}</p>` : ''}
      <div class="ja-columns">
        <div>${strengths(list(round.fortalezas))}</div>
        <div>${weaknesses(list(round.debilidades))}</div>
      </div>
      ${alerts(list(round.alertas))}`;
  }

  function head(round) {
    return `<div class="ja-head">${badge(round)}
        <div class="ja-head__text">
          <span class="ja-meta">${esc(tr('panel.judgeAvance.round', { n: round.ronda }))}${round.fecha ? ` · ${esc(round.fecha)}` : ''}</span>
          <p class="ja-verdict">${esc(round.veredicto)}</p>
        </div>
      </div>`;
  }

  function render(data, options) {
    const d = obj(data);
    const pending = !!(options && options.pending);
    const text = copy(options && options.etapa);
    const errors = list(d.errores);
    const parts = [];
    if (pending) {
      parts.push(`<p class="ja-pending" role="status">${esc(text.pending)}</p>`);
    }
    if (errors.length) {
      parts.push(`<div class="ja-errors"><strong>${esc(tr('panel.judgeAvance.readError'))}</strong><ul>${errors.map((e) => `<li>${esc(e)}</li>`).join('')}</ul></div>`);
    }
    const current = d.evaluacion && typeof d.evaluacion === 'object' ? d.evaluacion : null;
    if (!current) {
      if (!errors.length && !pending) {
        parts.push(`<p class="ja-empty">${esc(text.empty)}</p>`);
      }
      return parts.join('');
    }
    parts.push(`<div class="ja-current">${head(current)}${bar(current)}${detail(current)}</div>`);
    const older = list(current.historial).filter((r) => r && typeof r === 'object')
      .slice().sort((a, b) => Number(b.ronda) - Number(a.ronda));
    if (older.length) {
      parts.push(`<h5 class="ja-h">${esc(tr('panel.judgeAvance.olderRounds'))}</h5>${older.map((r) => `
        <details class="ja-round"><summary>${esc(tr('panel.judgeAvance.round', { n: r.ronda }))} ·${esc(r.fecha || '')} · ${score(r.puntaje) === null ? '?' : score(r.puntaje)}/100 · ${esc(r.veredicto || '')}</summary>
          <div class="ja-round__body">${head(r)}${detail(r)}</div></details>`).join('')}`);
    }
    return parts.join('');
  }

  const STYLE_ID = 'judgeAvanceStyles';
  const CSS = `
    .ja { display: flex; flex-direction: column; gap: 0.75rem; min-width: 0; font-size: 0.85rem; }
    .ja-intro { color: var(--text-muted); line-height: 1.5; }
    .ja-toolbar { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
    .ja-message { flex: 1 1 220px; min-width: 0; color: var(--text-muted); overflow-wrap: anywhere; }
    .ja-message.is-ok { color: var(--ok); }
    .ja-message.is-error { color: var(--bad); }
    .ja-body { display: flex; flex-direction: column; gap: 0.6rem; min-width: 0; overflow-wrap: anywhere; }
    .ja-head { display: flex; gap: 0.9rem; align-items: center; flex-wrap: wrap; }
    .ja-head__text { flex: 1 1 200px; min-width: 0; }
    .ja-score { display: inline-flex; align-items: baseline; gap: 0.15rem; padding: 0.35rem 0.7rem; border-radius: var(--radius); border: 2px solid var(--accent); background: var(--accent-dim); color: var(--text); white-space: nowrap; }
    .ja-score strong { font-size: 1.6rem; line-height: 1; }
    .ja-score small { color: var(--text-muted); }
    .ja-score.ja-tone--ok { border-color: var(--ok); background: var(--ok-dim); }
    .ja-score.ja-tone--warn { border-color: var(--warn); background: var(--warn-dim); }
    .ja-score.ja-tone--bad { border-color: var(--bad); background: var(--bad-dim); }
    .ja-meta { font-size: 0.75rem; color: var(--text-muted); }
    .ja-verdict { margin-top: 0.2rem; font-weight: 600; color: var(--text); }
    .ja-bar { position: relative; height: 8px; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border-subtle); }
    .ja-bar__fill { display: block; height: 100%; border-radius: 999px; background: var(--accent); }
    .ja-bar__fill.ja-tone--ok { background: var(--ok); }
    .ja-bar__fill.ja-tone--warn { background: var(--warn); }
    .ja-bar__fill.ja-tone--bad { background: var(--bad); }
    .ja-bar__mark { position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--text); }
    .ja-h { margin: 0.4rem 0 0.25rem; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-dim); }
    .ja-idea { line-height: 1.5; color: var(--text); }
    .ja-columns { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); gap: 0.75rem; }
    .ja-list { list-style: none; display: flex; flex-direction: column; gap: 0.35rem; }
    .ja-list li { padding: 0.45rem 0.6rem; border-radius: var(--radius); border: 1px solid var(--border-subtle); background: var(--surface-2); line-height: 1.45; display: flex; flex-direction: column; gap: 0.2rem; min-width: 0; }
    .ja-strengths li { border-left: 3px solid var(--ok); }
    .ja-weaknesses li { border-left: 3px solid var(--warn); }
    .ja-evidence { color: var(--text-muted); }
    .ja-action { margin-top: 0.15rem; color: var(--text); }
    .ja-alert { flex-direction: row !important; align-items: flex-start; gap: 0.5rem !important; }
    .ja-alert__text { min-width: 0; }
    .ja-level { flex: none; font-size: 0.7rem; font-weight: 700; padding: 0.1rem 0.45rem; border-radius: 999px; border: 1px solid; }
    .ja-level--alta { color: var(--bad); border-color: var(--bad); background: var(--bad-dim); }
    .ja-level--media { color: var(--warn); border-color: var(--warn); background: var(--warn-dim); }
    .ja-level--baja { color: var(--accent); border-color: var(--accent); background: var(--accent-dim); }
    .ja-muted, .ja-empty { color: var(--text-muted); }
    .ja-pending { padding: 0.5rem 0.7rem; border-radius: var(--radius); border: 1px dashed var(--accent); background: var(--accent-dim); color: var(--text); }
    .ja-errors { padding: 0.5rem 0.7rem; border-radius: var(--radius); border: 1px solid var(--bad); background: var(--bad-dim); }
    .ja-errors ul { padding-left: 1.1rem; }
    .ja-round { border: 1px solid var(--border-subtle); border-radius: var(--radius); padding: 0.4rem 0.6rem; }
    .ja-round > summary { cursor: pointer; color: var(--text-muted); overflow-wrap: anywhere; }
    .ja-round__body { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 0.5rem; }
  `;

  function injectStyles(doc) {
    if (doc.getElementById(STYLE_ID)) return;
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = CSS;
    (doc.head || doc.documentElement).appendChild(style);
  }

  function mount(root, options) {
    const opts = options || {};
    const etapa = STAGES[opts.etapa] ? opts.etapa : 'arbol';
    const interval = Number(opts.interval) > 0 ? Number(opts.interval) : 5000;
    const doFetch = opts.fetch || ((...args) => window.fetch(...args));
    const send = opts.send || ((prompt) => window.sendTerminalPrompt(prompt));
    const doc = root.ownerDocument;
    const text = () => copy(etapa);
    injectStyles(doc);

    root.classList.add('ja');
    root.setAttribute('data-judge-avance-etapa', etapa);
    root.innerHTML = `
      <p class="ja-intro">${esc(text().intro)}</p>
      <div class="ja-toolbar">
        <button class="btn btn--sm btn--primary ja-run" type="button">${esc(text().run)}</button>
        <button class="btn btn--sm ja-retry" type="button" hidden>${esc(tr('panel.judgeAvance.retrySend'))}</button>
        <span class="ja-message" role="status" aria-live="polite"></span>
      </div>
      <div class="ja-body"></div>`;
    const intro = root.querySelector('.ja-intro');
    const runBtn = root.querySelector('.ja-run');
    const retryBtn = root.querySelector('.ja-retry');
    const message = root.querySelector('.ja-message');
    const body = root.querySelector('.ja-body');

    const state = { data: null, sig: null, pending: null, prompt: null, timer: null, said: null };

    // `key` and `vars` name the message, kept so a language switch can say it again.
    function say(key, vars, kind) {
      state.said = key ? { key, vars, kind } : null;
      message.textContent = key ? tr(key, vars) : '';
      message.className = `ja-message${kind ? ` is-${kind}` : ''}`;
    }

    function currentRound() {
      const e = state.data && state.data.evaluacion;
      return e && Number.isFinite(Number(e.ronda)) ? Number(e.ronda) : 0;
    }

    function paint() {
      const sig = JSON.stringify([state.data, !!state.pending]);
      if (sig === state.sig) return;
      state.sig = sig;
      body.innerHTML = render(state.data, { pending: !!state.pending, etapa });
      runBtn.disabled = !!state.pending;
    }

    async function refresh() {
      let data;
      try {
        const res = await doFetch(`/api/judge-avance?etapa=${encodeURIComponent(etapa)}`, { cache: 'no-store' });
        data = await res.json();
        if (!res.ok || !data || data.ok === false) throw new Error((data && data.error) || `HTTP ${res.status}`);
      } catch (err) {
        state.data = { errores: [tr('panel.judgeAvance.queryFailed', {
          name: text().name, reason: err && err.message ? err.message : err,
        })] };
        paint();
        return state.data;
      }
      state.data = data;
      if (state.pending && currentRound() > state.pending.from) {
        state.pending = null;
        say('panel.judgeAvance.arrived', { n: currentRound(), name: text().name }, 'ok');
      }
      paint();
      return data;
    }

    async function deliver(prompt) {
      state.prompt = prompt;
      say('panel.judgeAvance.sending');
      let delivered = false;
      try { delivered = await send(prompt); } catch (_) { delivered = false; }
      if (delivered === false) {
        retryBtn.hidden = false;
        say('panel.judgeAvance.notDelivered', null, 'error');
        return false;
      }
      retryBtn.hidden = true;
      state.pending = { from: currentRound() };
      say('panel.judgeAvance.sent', { prompt }, 'ok');
      paint();
      return true;
    }

    async function run() {
      let result;
      try {
        const res = await doFetch('/api/judge-avance/run', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ etapa }),
        });
        result = await res.json();
      } catch (err) {
        say('panel.judgeAvance.requestFailedReason', { reason: err && err.message ? err.message : err }, 'error');
        return false;
      }
      if (!result || !result.ok || !result.prompt) {
        // The server's own message (localize.py translates it), shown as it comes.
        if (result && result.error) say('panel.judgeAvance.serverMessage', { message: result.error }, 'error');
        else say('panel.judgeAvance.requestFailed', null, 'error');
        return false;
      }
      return deliver(result.prompt);
    }

    async function retry() {
      return state.prompt ? deliver(state.prompt) : false;
    }

    function start() {
      refresh();
      if (state.timer) return;
      state.timer = setInterval(() => {
        if (!doc.hidden) refresh();
      }, interval);
    }

    function stop() {
      if (state.timer) clearInterval(state.timer);
      state.timer = null;
    }

    // A language switch: the block's own texts at once, then the round again
    // (the server translates its messages too). A block removed from the page stops listening.
    function relabel() {
      if (!root.isConnected) {
        doc.removeEventListener('languagechange', relabel);
        return;
      }
      intro.textContent = text().intro;
      runBtn.textContent = text().run;
      retryBtn.textContent = tr('panel.judgeAvance.retrySend');
      if (state.said) say(state.said.key, state.said.vars, state.said.kind);
      state.sig = null;
      paint();
      if (state.data) refresh();
    }
    doc.addEventListener('languagechange', relabel);

    runBtn.addEventListener('click', () => { run(); });
    retryBtn.addEventListener('click', () => { retry(); });
    paint();

    return {
      etapa,
      refresh,
      run,
      retry,
      start,
      stop,
      get polling() { return !!state.timer; },
      get data() { return state.data; },
    };
  }

  window.JudgeAvance = { mount, render, tone, THRESHOLDS };
})();
