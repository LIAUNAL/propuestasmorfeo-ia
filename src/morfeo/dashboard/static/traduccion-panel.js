/**
 * traduccion-panel.js: the «Versión del documento» fold of the PDF preview
 * (papersmith translation-panel.js and its translationDetails fold).
 *
 * The run's manuscript stays canonical; scripts/traducir.py keeps a derived
 * translation into the other language under redaccion/traducciones/<lang>/.
 * The panel reads GET /api/traducciones (blocks and fragments by state
 * missing/current/stale, whether the version is built and compiled, the last
 * style audit) and offers three actions:
 *   «Traducir / actualizar»  types /propuesta-traducir <lang> into the agent's
 *                            terminal (sendTerminalPrompt) and keeps polling;
 *   «Compilar traducción»    POST /api/traduccion/compilar?traduccion=<lang>;
 *   «Ver traducción / Ver original»
 *                            switches the main viewer between main.pdf and
 *                            /api/pdf?traduccion=<lang> through onSource.
 * The target language travels as `traduccion=`, never `lang=` (the i18n
 * runtime adds ?lang=<interface language> to every /api/ request). Every
 * value is escaped before insertion and every string comes from the
 * `panel.traduccion.*` catalogue keys; the panel re-renders on languagechange.
 *
 * Public surface (window.TraduccionPanel):
 *   mount(root, { fetch, send, onSource, interval, isVisible, lang }) -> controller
 *     fetch      fetch implementation; default window.fetch at call time
 *     send       async (prompt) => boolean; default window.sendTerminalPrompt
 *     onSource   async (lang | null) => void; default window.setPdfSource
 *     interval   polling period in ms while started; default 5000
 *     isVisible  () => boolean, polling only while true; default: fold open
 *     lang       target language; default the other language of the run
 *   controller: refresh(), translate(), retry(), compile(), toggleSource(),
 *               start(), stop(), polling, data, showing
 *   render(data, { showing }) -> HTML of the body (pure)
 */
(function () {
  'use strict';

  const STYLE_ID = 'traduccion-panel-styles';
  const CSS = `
    .tp [hidden] { display: none !important; }
    .tp-intro { margin: 0 0 0.6rem; color: var(--text-muted); font-size: 0.85rem; }
    .tp-toolbar { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; margin-bottom: 0.6rem; }
    .tp-message { font-size: 0.8rem; color: var(--text-muted); }
    .tp-message.is-ok { color: var(--ok, #10b981); }
    .tp-message.is-error { color: var(--bad, #ef4444); white-space: pre-wrap; }
    .tp-rows { display: grid; gap: 0.35rem; margin: 0; padding: 0; list-style: none; font-size: 0.82rem; }
    .tp-row { display: flex; flex-wrap: wrap; gap: 0.35rem 0.75rem; align-items: baseline; }
    .tp-row strong { min-width: 12rem; }
    .tp-state--ok { color: var(--ok, #10b981); }
    .tp-state--warn { color: var(--warn, #f59e0b); }
    .tp-errors { color: var(--bad, #ef4444); font-size: 0.8rem; }
    .pdf-workspace-layout.is-translation .pdf-interaction-bar,
    .pdf-workspace-layout.is-translation .pdf-control-panel { display: none !important; }
  `;

  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);
  const tr = (key, vars) => (typeof window.t === 'function' ? window.t(key, vars) : key);
  const langName = (lang) => tr(lang === 'en' ? 'panel.traduccion.langEn' : 'panel.traduccion.langEs');
  const counts = (c) => {
    const n = (k) => (c && Number.isFinite(Number(c[k])) ? Number(c[k]) : 0);
    return { total: n('total'), current: n('current'), missing: n('missing'), stale: n('stale') };
  };

  function injectStyles(doc) {
    if (doc.getElementById(STYLE_ID)) return;
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = CSS;
    (doc.head || doc.documentElement).appendChild(style);
  }

  function countsRow(label, value) {
    const c = counts(value);
    const done = c.total > 0 && c.current === c.total;
    return `<li class="tp-row" data-row="${esc(label)}"><strong>${esc(tr(`panel.traduccion.${label}`))}</strong>`
      + `<span class="tp-state--${done ? 'ok' : 'warn'}">${esc(tr('panel.traduccion.counts', c))}</span></li>`;
  }

  function render(data, options) {
    const d = data && typeof data === 'object' ? data : {};
    const errors = [].concat(d.errores || [], d.error ? [d.error] : []);
    const parts = [];
    if (errors.length) {
      parts.push(`<div class="tp-errors">${errors.map((e) => `<p>${esc(e)}</p>`).join('')}</div>`);
    }
    const status = d.status && typeof d.status === 'object' ? d.status : null;
    if (!status) return parts.join('');
    if (!status.planned) {
      parts.push(`<p class="tp-empty">${esc(tr('panel.traduccion.notPlanned'))}</p>`);
    }
    const rows = [countsRow('blocks', status.counts), countsRow('fragments', status.fragment_counts)];
    rows.push(`<li class="tp-row" data-row="built"><span class="tp-state--${status.built ? 'ok' : 'warn'}">`
      + `${esc(tr(status.built ? 'panel.traduccion.built' : 'panel.traduccion.notBuilt'))}</span></li>`);
    const pdfKey = status.pdf ? (status.pdf_current ? 'pdfCurrent' : 'pdfOld') : 'noPdf';
    rows.push(`<li class="tp-row" data-row="pdf"><span class="tp-state--${pdfKey === 'pdfCurrent' ? 'ok' : 'warn'}">`
      + `${esc(tr(`panel.traduccion.${pdfKey}`))}</span></li>`);
    const audit = status.audit && typeof status.audit === 'object' ? status.audit : null;
    if (audit) {
      const doc = audit.document || {};
      const checker = String(audit.checker || '').split('/').pop();
      rows.push(`<li class="tp-row" data-row="audit"><span class="tp-state--${audit.fresh ? 'ok' : 'warn'}">`
        + `${esc(tr('panel.traduccion.audit', { checker, indice: doc.indice == null ? '?' : doc.indice,
          verdict: doc.veredicto || '?', failures: Number(audit.fidelity_failures) || 0 }))}</span>`
        + `${audit.fresh ? '' : ` <span class="tp-state--warn">${esc(tr('panel.traduccion.auditOld'))}</span>`}</li>`);
    } else {
      rows.push(`<li class="tp-row" data-row="audit">${esc(tr('panel.traduccion.noAudit'))}</li>`);
    }
    parts.push(`<ul class="tp-rows">${rows.join('')}</ul>`);
    if (options && options.showing) {
      parts.push(`<p class="tp-viewing">${esc(tr('panel.traduccion.viewing', { target: langName(d.lang) }))}</p>`);
    }
    return parts.join('');
  }

  function defaultVisible(root) {
    const fold = root.closest && root.closest('details.exp-fold');
    return !fold || fold.open;
  }

  function mount(root, options) {
    const opts = options || {};
    const doc = root.ownerDocument;
    const interval = Number(opts.interval) > 0 ? Number(opts.interval) : 5000;
    const doFetch = opts.fetch || ((...args) => window.fetch(...args));
    const send = opts.send || ((prompt) => window.sendTerminalPrompt(prompt));
    const onSource = opts.onSource || ((lang) => (window.setPdfSource ? window.setPdfSource(lang) : undefined));
    const isVisible = opts.isVisible || (() => defaultVisible(root));
    injectStyles(doc);

    root.classList.add('tp');
    root.innerHTML = `
      <p class="tp-intro"></p>
      <div class="tp-toolbar">
        <button class="btn btn--sm btn--primary tp-translate" type="button"></button>
        <button class="btn btn--sm tp-compile" type="button"></button>
        <button class="btn btn--sm tp-source" type="button"></button>
        <button class="btn btn--sm tp-retry" type="button" hidden></button>
        <span class="tp-message" role="status" aria-live="polite"></span>
      </div>
      <div class="tp-body"></div>`;
    const intro = root.querySelector('.tp-intro');
    const translateBtn = root.querySelector('.tp-translate');
    const compileBtn = root.querySelector('.tp-compile');
    const sourceBtn = root.querySelector('.tp-source');
    const retryBtn = root.querySelector('.tp-retry');
    const message = root.querySelector('.tp-message');
    const body = root.querySelector('.tp-body');
    const state = { data: null, showing: false, prompt: null, timer: null, busy: false, said: null };

    function target() {
      return (state.data && state.data.lang) || opts.lang || '';
    }

    function query() {
      const lang = opts.lang || (state.data && state.data.lang);
      return lang ? `?traduccion=${encodeURIComponent(lang)}` : '';
    }

    function say(key, vars, kind) {
      state.said = key ? { key, vars, kind } : null;
      message.textContent = key ? tr(key, vars) : '';
      message.className = `tp-message${kind ? ` is-${kind}` : ''}`;
    }

    function paint() {
      const d = state.data || {};
      const status = d.status || {};
      intro.textContent = d.source_language
        ? tr('panel.traduccion.intro', { source: langName(d.source_language), target: langName(d.lang) }) : '';
      translateBtn.textContent = tr('panel.traduccion.translate');
      compileBtn.textContent = tr('panel.traduccion.compile');
      retryBtn.textContent = tr('panel.traduccion.retry');
      sourceBtn.textContent = tr(state.showing ? 'panel.traduccion.showOriginal' : 'panel.traduccion.showTranslation');
      translateBtn.disabled = !d.command || state.busy;
      compileBtn.disabled = !status.built || state.busy;
      sourceBtn.disabled = !state.showing && !status.pdf;
      body.innerHTML = render(d, { showing: state.showing });
      const fold = root.closest && root.closest('details.exp-fold');
      const title = fold && fold.querySelector('.exp-fold__title');
      if (title) title.textContent = tr('panel.traduccion.title');
      const meta = doc.getElementById('translationMeta');
      if (meta && d.source_language) {
        meta.textContent = tr('panel.traduccion.meta', { source: langName(d.source_language), target: langName(d.lang) });
      }
      if (state.said) say(state.said.key, state.said.vars, state.said.kind);
    }

    async function refresh() {
      try {
        const res = await doFetch(`/api/traducciones${query()}`, { cache: 'no-store' });
        const data = await res.json();
        if (!data || (!res.ok && !data.status)) throw new Error((data && data.error) || `HTTP ${res.status}`);
        state.data = data;
      } catch (err) {
        state.data = { ...(state.data || {}), status: (state.data || {}).status || null, error: null,
          errores: [tr('panel.traduccion.loadFailed', { error: err && err.message ? err.message : err })] };
      }
      paint();
      return state.data;
    }

    async function deliver(prompt) {
      state.prompt = prompt;
      say('panel.traduccion.sending', { command: prompt });
      let delivered = false;
      try { delivered = await send(prompt); } catch (_) { delivered = false; }
      if (delivered === false) {
        retryBtn.hidden = false;
        say('panel.traduccion.notDelivered', null, 'error');
        return false;
      }
      retryBtn.hidden = true;
      say('panel.traduccion.sent', { command: prompt }, 'ok');
      return true;
    }

    async function translate() {
      if (!state.data) await refresh();
      const command = state.data && state.data.command;
      return command ? deliver(command) : false;
    }

    async function retry() {
      return state.prompt ? deliver(state.prompt) : false;
    }

    async function compile() {
      state.busy = true;
      say('panel.traduccion.compiling');
      paint();
      let result = {};
      try {
        const res = await doFetch(`/api/traduccion/compilar${query()}`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        });
        try { result = await res.json(); } catch (_) { result = {}; }
        if (!res.ok || !result.ok) throw new Error(result.error || `HTTP ${res.status}`);
        say('panel.traduccion.compiled', null, 'ok');
      } catch (err) {
        say('panel.traduccion.compileFailed', { error: err && err.message ? err.message : err }, 'error');
        result = { ok: false };
      } finally {
        state.busy = false;
      }
      await refresh();
      if (result.ok && state.showing) await onSource(target());
      return !!result.ok;
    }

    async function toggleSource() {
      state.showing = !state.showing;
      const layout = doc.querySelector('.pdf-workspace-layout');
      if (layout) layout.classList.toggle('is-translation', state.showing);
      paint();
      await onSource(state.showing ? target() : null);
      return state.showing;
    }

    function start() {
      if (isVisible()) refresh();
      if (state.timer) return;
      state.timer = setInterval(() => {
        if (!doc.hidden && isVisible()) refresh();
      }, interval);
    }

    function stop() {
      if (state.timer) clearInterval(state.timer);
      state.timer = null;
    }

    translateBtn.addEventListener('click', () => { translate(); });
    compileBtn.addEventListener('click', () => { compile(); });
    sourceBtn.addEventListener('click', () => { toggleSource(); });
    retryBtn.addEventListener('click', () => { retry(); });
    doc.addEventListener('languagechange', () => paint());
    doc.addEventListener('toggle', (event) => {
      const item = event.target;
      if (item && item.contains && item.contains(root) && item.open && state.timer) refresh();
    }, true);
    paint();

    return {
      refresh, translate, retry, compile, toggleSource, start, stop,
      get polling() { return !!state.timer; },
      get data() { return state.data; },
      get showing() { return state.showing; },
    };
  }

  window.TraduccionPanel = { mount, render };
})();
