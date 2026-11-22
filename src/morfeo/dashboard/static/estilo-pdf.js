/**
 * PDF preview of the «Estilo y redundancia» panel (odd/tasks/tablero-juez-novedad.md, S5).
 *
 * A small pdf.js viewer that lives next to the style findings, separate from the
 * `preview` tab viewer: a continuous stack of pages rendered lazily at fit-width,
 * a page counter, and `locate(finding)`, which searches the finding's sentence in
 * the PDF text with loose needles (papersmith-ai `findTextInPdf`) and scrolls to
 * the page with the matched text highlighted.
 *
 * It reuses `/api/pdf` and `/api/pdf/version` and the `pdfjsLib` the page already
 * loads. Nothing runs until the estilo tab opens (`open()`); `hide()` and a hidden
 * browser tab pause the version polling. Without pdfjsLib the panel falls back to
 * the browser's own PDF viewer in an iframe; without main.pdf it shows an empty
 * state.
 */
(function () {
  'use strict';

  const POLL_MS = 5000;
  const HIGHLIGHT_MS = 4000;
  const MIN_NEEDLE = 12;
  const NEEDLE_WORDS = 7;
  const RENDER_MARGIN = '600px 0px';
  const CITE = /\(cita\)/gi;
  const CITE_GAP = /\(cita\)|\s{2,}/i;

  const MESSAGES = {
    empty: 'Todavía no hay un PDF compilado. Compílalo con /compilar-pdf o desde la pestaña «Vista previa» para verlo junto a los hallazgos.',
    loading: 'Cargando el PDF…',
    loadFailed: 'El visor integrado no pudo abrir el PDF; se muestra con el visor del navegador.',
    frameOnly: 'El visor del navegador no permite buscar el hallazgo; recorre el PDF a mano.',
    searching: 'Buscando el hallazgo en el PDF…',
    found: (page) => `Hallazgo ubicado en la página ${page}.`,
    notFound: 'No encontrado en el PDF: el texto pudo cambiar desde la última compilación.',
    noText: 'El hallazgo no trae texto suficiente para buscarlo en el PDF.',
    noPdf: 'No hay PDF en el cual buscar.',
  };

  // --- Loose text normalization ---------------------------------------------
  // Accents, case, ligatures (NFKD), punctuation, whitespace and hyphens all
  // vanish, so a word hyphenated at a line end, «comillas», a non-breaking
  // space or a LaTeX command left in the source still match the PDF text.
  function normalize(value) {
    return String(value || '')
      .replace(/\\[a-zA-Z@]+\*?/g, ' ')
      .normalize('NFKD')
      .replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, '');
  }

  function words(text) {
    return String(text || '').split(/\s+/).filter(Boolean);
  }

  // The audit drops `\citep{…}` (leaving two spaces) and writes `\citet{…}` as
  // «(cita)»; the PDF prints «(Autor, 2024)» there. Needles never cross one.
  function segments(text) {
    return String(text || '').split(CITE_GAP).map((part) => part.replace(/^[\s,;:.]+|[\s,;:]+$/g, '')).filter(Boolean);
  }

  /**
   * Needles for a finding, strongest first: the opening and closing words of
   * its sentence (`oracion_texto`, attached by `/api/estilo`), then the opening
   * and closing words of the fragment itself. Short or duplicate needles drop.
   */
  function needlesFor(finding) {
    const out = [];
    const sentence = segments(finding && finding.oracion_texto).filter((part) => words(part).length >= 3);
    if (sentence.length) {
      out.push(words(sentence[0]).slice(0, NEEDLE_WORDS).join(' '));
      out.push(words(sentence[sentence.length - 1]).slice(-NEEDLE_WORDS).join(' '));
    }
    const fragment = segments(finding && finding.fragmento).sort((a, b) => b.length - a.length)[0] || '';
    const fragmentWords = words(fragment);
    if (fragmentWords.length >= 3) {
      out.push(fragmentWords.slice(0, NEEDLE_WORDS).join(' '));
      out.push(fragmentWords.slice(-NEEDLE_WORDS).join(' '));
    }
    const seen = new Set();
    return out.filter((needle) => {
      const key = normalize(needle);
      if (key.length < MIN_NEEDLE || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  /** Normalized text of one page plus, per character, the text item it came from. */
  function indexPage(items) {
    let text = '';
    const owners = [];
    (items || []).forEach((item, index) => {
      const piece = normalize(item && item.str);
      text += piece;
      for (let i = 0; i < piece.length; i += 1) owners.push(index);
    });
    return { text, owners, items: items || [] };
  }

  /**
   * First page holding a needle. Each needle is tried across the whole document
   * before the next one, so a weak needle never wins on an earlier page.
   * `pageAt(n)` returns (or resolves to) `indexPage` output for page n.
   */
  async function search(pageAt, numPages, needles) {
    for (const needle of needles) {
      const key = normalize(needle);
      if (key.length < MIN_NEEDLE) continue;
      for (let page = 1; page <= numPages; page += 1) {
        const indexed = await pageAt(page);
        const start = indexed.text.indexOf(key);
        if (start >= 0) return { page, needle, start, end: start + key.length };
      }
    }
    return null;
  }

  /** The fragment's own span near the hit, when the hit came from its sentence. */
  function refineRange(indexed, hit, finding) {
    const fragment = normalize(finding && finding.fragmento);
    const sentence = normalize(String((finding && finding.oracion_texto) || '').replace(CITE, ' '));
    if (fragment.length < 3 || !sentence) return hit;
    const windowEnd = Math.min(indexed.text.length, hit.start + sentence.length + 200);
    const windowStart = Math.max(0, hit.end - sentence.length - 200);
    const at = indexed.text.slice(windowStart, windowEnd).indexOf(fragment);
    if (at < 0) return hit;
    return { ...hit, start: windowStart + at, end: windowStart + at + fragment.length };
  }

  // pdf.js `Util.transform`, kept local so the highlight needs nothing else.
  function multiply(m1, m2) {
    return [
      m1[0] * m2[0] + m1[2] * m2[1],
      m1[1] * m2[0] + m1[3] * m2[1],
      m1[0] * m2[2] + m1[2] * m2[3],
      m1[1] * m2[2] + m1[3] * m2[3],
      m1[0] * m2[4] + m1[2] * m2[5] + m1[4],
      m1[1] * m2[4] + m1[3] * m2[5] + m1[5],
    ];
  }

  /** Item boxes covering [start, end), as fractions of the page viewport. */
  function highlightBoxes(indexed, start, end, viewport) {
    const picked = [];
    for (let i = start; i < end; i += 1) {
      const owner = indexed.owners[i];
      if (owner !== undefined && picked[picked.length - 1] !== owner) picked.push(owner);
    }
    const width = viewport && viewport.width ? viewport.width : 1;
    const height = viewport && viewport.height ? viewport.height : 1;
    const transform = (viewport && viewport.transform) || [1, 0, 0, 1, 0, 0];
    const scale = (viewport && viewport.scale) || 1;
    return [...new Set(picked)].map((owner) => {
      const item = indexed.items[owner] || {};
      const m = multiply(transform, item.transform || [1, 0, 0, 1, 0, 0]);
      const fontHeight = Math.hypot(m[2], m[3]) || (Number(item.height) || 10) * scale;
      const boxWidth = Math.max((Number(item.width) || 0) * scale, fontHeight);
      return {
        left: m[4] / width,
        top: (m[5] - fontHeight) / height,
        width: boxWidth / width,
        height: (fontHeight * 1.2) / height,
      };
    });
  }

  // --- Viewer -----------------------------------------------------------------
  const state = {
    active: false,
    mode: 'idle', // idle | loading | pdfjs | frame | empty
    version: null,
    doc: null,
    numPages: 0,
    base: null, // page 1 size at scale 1
    scale: 1,
    currentPage: 1,
    generation: 0,
    observer: null,
    pollTimer: null,
    syncing: null,
    rendered: new Map(), // page -> scale painted
    pending: new Map(), // page -> promise
    renderTasks: new Map(), // page -> pdf.js render task
    texts: new Map(), // page -> indexPage output
    highlightTimer: null,
    listening: false,
  };

  const $ = (id) => document.getElementById(id);

  function setStatus(message, tone) {
    const el = $('estiloPdfStatus');
    if (!el) return;
    el.textContent = message || '';
    el.dataset.tone = tone || '';
  }

  function updateCounter() {
    const el = $('estiloPdfPageInfo');
    if (!el) return;
    el.textContent = state.mode === 'pdfjs' && state.numPages
      ? `Página ${state.currentPage} de ${state.numPages}`
      : '—';
  }

  function showMode(mode) {
    state.mode = mode;
    const empty = $('estiloPdfEmpty');
    const pages = $('estiloPdfPages');
    const frame = $('estiloPdfFrame');
    if (empty) empty.hidden = mode !== 'empty';
    if (pages) pages.hidden = mode !== 'pdfjs';
    if (frame) {
      frame.hidden = mode !== 'frame';
      if (mode !== 'frame' && frame.getAttribute('src') !== 'about:blank') frame.setAttribute('src', 'about:blank');
    }
    if (mode === 'empty') setStatus(MESSAGES.empty);
    updateCounter();
  }

  async function fetchVersion() {
    try {
      const res = await fetch('/api/pdf/version', { cache: 'no-store' });
      if (res.status === 404) return null;
      if (!res.ok) return undefined;
      const data = await res.json();
      return data && data.exists && data.version ? String(data.version) : null;
    } catch (_) {
      return undefined; // transient: keep whatever is on screen
    }
  }

  function pdfUrl(version) {
    return `/api/pdf?t=${encodeURIComponent(version)}`;
  }

  function cancelRenders() {
    state.renderTasks.forEach((task) => {
      try { task.cancel(); } catch (_) {}
    });
    state.renderTasks.clear();
    state.pending.clear();
  }

  function teardown() {
    state.generation += 1;
    if (state.observer) state.observer.disconnect();
    state.observer = null;
    cancelRenders();
    state.rendered.clear();
    state.texts.clear();
    const old = state.doc;
    state.doc = null;
    state.numPages = 0;
    if (old && typeof old.destroy === 'function') {
      try { old.destroy(); } catch (_) {}
    }
    const pages = $('estiloPdfPages');
    if (pages) pages.innerHTML = '';
  }

  function showFrame(version) {
    teardown();
    const frame = $('estiloPdfFrame');
    if (frame) frame.setAttribute('src', `${pdfUrl(version)}#page=${state.currentPage || 1}`);
    state.version = version;
    showMode('frame');
  }

  function computeScale() {
    const viewport = $('estiloPdfViewport');
    const available = viewport ? viewport.clientWidth - 16 : 0;
    if (!state.base || !(available > 0)) return 1;
    return Math.min(3, Math.max(0.4, available / state.base.width));
  }

  function slot(page) {
    return document.querySelector(`#estiloPdfPages .estilo-pdf-page[data-page="${page}"]`);
  }

  function releasePage(page) {
    const el = slot(page);
    const canvas = el && el.querySelector('canvas');
    if (canvas) {
      canvas.width = 0;
      canvas.height = 0;
      canvas.remove();
    }
    const task = state.renderTasks.get(page);
    if (task) {
      try { task.cancel(); } catch (_) {}
      state.renderTasks.delete(page);
    }
    state.pending.delete(page);
    state.rendered.delete(page);
  }

  function observe() {
    if (state.observer) state.observer.disconnect();
    state.observer = null;
    const Observer = window.IntersectionObserver;
    const pages = document.querySelectorAll('#estiloPdfPages .estilo-pdf-page');
    if (typeof Observer !== 'function') {
      // No observer: paint the first pages; `goToPage` paints the rest on demand.
      renderPage(1);
      if (state.numPages > 1) renderPage(2);
      return;
    }
    state.observer = new Observer((entries) => {
      entries.forEach((entry) => {
        const page = Number(entry.target.dataset.page);
        if (entry.isIntersecting) renderPage(page);
        else releasePage(page);
      });
    }, { root: $('estiloPdfViewport'), rootMargin: RENDER_MARGIN });
    pages.forEach((el) => state.observer.observe(el));
  }

  function buildSlots() {
    const pages = $('estiloPdfPages');
    if (!pages || !state.base) return;
    if (state.observer) state.observer.disconnect();
    cancelRenders();
    state.rendered.clear();
    pages.innerHTML = '';
    const width = Math.floor(state.base.width * state.scale);
    const height = Math.floor(state.base.height * state.scale);
    for (let page = 1; page <= state.numPages; page += 1) {
      const el = document.createElement('div');
      el.className = 'estilo-pdf-page';
      el.dataset.page = String(page);
      el.style.width = `${width}px`;
      el.style.height = `${height}px`;
      el.setAttribute('aria-label', `Página ${page}`);
      const layer = document.createElement('div');
      layer.className = 'estilo-pdf-hl-layer';
      el.appendChild(layer);
      pages.appendChild(el);
    }
    observe();
  }

  function renderPage(page) {
    if (!state.doc || page < 1 || page > state.numPages) return Promise.resolve();
    if (state.rendered.get(page) === state.scale) return Promise.resolve();
    if (state.pending.has(page)) return state.pending.get(page);
    const generation = state.generation;
    const scale = state.scale;
    const doc = state.doc;
    const task = (async () => {
      try {
        const pdfPage = await doc.getPage(page);
        if (generation !== state.generation || scale !== state.scale) return;
        const viewport = pdfPage.getViewport({ scale });
        const el = slot(page);
        if (!el) return;
        const ratio = Math.min(2, window.devicePixelRatio || 1);
        const canvas = document.createElement('canvas');
        canvas.width = Math.floor(viewport.width * ratio);
        canvas.height = Math.floor(viewport.height * ratio);
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;
        const renderTask = pdfPage.render({
          canvasContext: canvas.getContext('2d'),
          viewport,
          transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined,
        });
        state.renderTasks.set(page, renderTask);
        await renderTask.promise;
        if (generation !== state.generation || scale !== state.scale || !el.isConnected) return;
        const previous = el.querySelector('canvas');
        if (previous) previous.remove();
        el.insertBefore(canvas, el.firstChild);
        state.rendered.set(page, scale);
      } catch (err) {
        if (!err || err.name !== 'RenderingCancelledException') console.error(`Estilo: no se pudo pintar la página ${page}`, err);
      } finally {
        if (state.pending.get(page) === task) state.pending.delete(page);
        state.renderTasks.delete(page);
      }
    })();
    state.pending.set(page, task);
    return task;
  }

  async function pageText(page) {
    if (state.texts.has(page)) return state.texts.get(page);
    const generation = state.generation;
    const pdfPage = await state.doc.getPage(page);
    const content = await pdfPage.getTextContent();
    const indexed = indexPage(content && content.items);
    if (generation === state.generation) state.texts.set(page, indexed);
    return indexed;
  }

  function scrollToPage(page, fraction) {
    const viewport = $('estiloPdfViewport');
    const el = slot(page);
    if (!viewport || !el) return;
    const top = el.offsetTop + (fraction || 0) * el.offsetHeight - 48;
    if (typeof viewport.scrollTo === 'function') viewport.scrollTo({ top: Math.max(0, top), behavior: 'auto' });
    else viewport.scrollTop = Math.max(0, top);
  }

  function goToPage(page, fraction) {
    const target = Math.min(Math.max(1, Number(page) || 1), state.numPages || 1);
    state.currentPage = target;
    updateCounter();
    scrollToPage(target, fraction);
    return renderPage(target);
  }

  async function load(version) {
    const keep = state.currentPage || 1;
    teardown();
    const generation = state.generation;
    const lib = window.pdfjsLib;
    if (!lib || typeof lib.getDocument !== 'function') {
      showFrame(version);
      return;
    }
    showMode('loading');
    setStatus(MESSAGES.loading);
    let doc;
    try {
      doc = await lib.getDocument({
        url: pdfUrl(version),
        cMapUrl: '/static/vendor/cmaps/',
        cMapPacked: true,
        enableXfa: false,
      }).promise;
      if (generation !== state.generation) {
        if (doc && typeof doc.destroy === 'function') doc.destroy();
        return;
      }
      const first = await doc.getPage(1);
      const base = first.getViewport({ scale: 1 });
      if (generation !== state.generation) return;
      state.doc = doc;
      state.numPages = doc.numPages;
      state.base = { width: base.width, height: base.height };
      state.version = version;
    } catch (err) {
      if (generation !== state.generation) return;
      console.error('Estilo: PDF.js no pudo abrir main.pdf', err);
      showFrame(version);
      setStatus(MESSAGES.loadFailed, 'warn');
      return;
    }
    state.scale = computeScale();
    showMode('pdfjs');
    setStatus('');
    buildSlots();
    await goToPage(Math.min(keep, state.numPages));
  }

  /** Brings the panel in line with main.pdf on disk. */
  function sync() {
    if (state.syncing) return state.syncing;
    state.syncing = (async () => {
      const version = await fetchVersion();
      if (version === undefined) return;
      if (version === null) {
        teardown();
        state.version = null;
        showMode('empty');
        return;
      }
      if (version === state.version && (state.mode === 'pdfjs' || state.mode === 'frame')) return;
      await load(version);
    })().finally(() => { state.syncing = null; });
    return state.syncing;
  }

  function stopPolling() {
    if (state.pollTimer !== null) clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  function startPolling() {
    stopPolling();
    if (!state.active || document.hidden) return;
    state.pollTimer = setInterval(() => {
      if (state.active && !document.hidden) sync();
    }, POLL_MS);
  }

  function onScroll() {
    const viewport = $('estiloPdfViewport');
    if (!viewport || state.mode !== 'pdfjs') return;
    const mark = viewport.scrollTop + viewport.clientHeight * 0.3;
    let page = 1;
    document.querySelectorAll('#estiloPdfPages .estilo-pdf-page').forEach((el) => {
      if (el.offsetTop <= mark) page = Number(el.dataset.page);
    });
    if (page !== state.currentPage) {
      state.currentPage = page;
      updateCounter();
    }
  }

  let resizeTimer = null;
  function onResize() {
    if (resizeTimer !== null) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      resizeTimer = null;
      if (!state.active || state.mode !== 'pdfjs') return;
      const next = computeScale();
      if (Math.abs(next - state.scale) < 0.01) return;
      const page = state.currentPage;
      state.scale = next;
      buildSlots();
      goToPage(page);
    }, 150);
  }

  function listenOnce() {
    if (state.listening) return;
    state.listening = true;
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stopPolling();
      else if (state.active) {
        startPolling();
        sync();
      }
    });
    window.addEventListener('resize', onResize);
    const viewport = $('estiloPdfViewport');
    if (viewport) viewport.addEventListener('scroll', () => {
      if (typeof requestAnimationFrame === 'function') requestAnimationFrame(onScroll);
      else onScroll();
    }, { passive: true });
  }

  /** The estilo tab opened: mount on first use, then keep main.pdf current. */
  function open() {
    state.active = true;
    listenOnce();
    if (state.mode === 'pdfjs' && state.observer === null && typeof window.IntersectionObserver === 'function') observe();
    startPolling();
    return sync();
  }

  /** The estilo tab closed: stop polling and painting; the document stays loaded. */
  function hide() {
    state.active = false;
    stopPolling();
    if (state.observer) state.observer.disconnect();
    state.observer = null;
  }

  function highlight(page, boxes) {
    document.querySelectorAll('#estiloPdfPages .estilo-pdf-hl').forEach((el) => el.remove());
    if (state.highlightTimer !== null) clearTimeout(state.highlightTimer);
    const layer = slot(page) && slot(page).querySelector('.estilo-pdf-hl-layer');
    if (!layer) return;
    boxes.forEach((box) => {
      const mark = document.createElement('div');
      mark.className = 'estilo-pdf-hl';
      mark.style.left = `${(box.left * 100).toFixed(3)}%`;
      mark.style.top = `${(box.top * 100).toFixed(3)}%`;
      mark.style.width = `${(box.width * 100).toFixed(3)}%`;
      mark.style.height = `${(box.height * 100).toFixed(3)}%`;
      layer.appendChild(mark);
    });
    state.highlightTimer = setTimeout(() => {
      state.highlightTimer = null;
      layer.querySelectorAll('.estilo-pdf-hl').forEach((el) => el.remove());
    }, HIGHLIGHT_MS);
  }

  /**
   * Finds the finding in the PDF, scrolls there and highlights it.
   * Resolves to `{ found, page?, needle?, reason? }`.
   */
  async function locate(finding) {
    if (state.syncing) await state.syncing;
    if (state.mode === 'frame') {
      setStatus(MESSAGES.frameOnly, 'warn');
      return { found: false, reason: 'frame' };
    }
    if (state.mode !== 'pdfjs' || !state.doc) {
      setStatus(MESSAGES.noPdf, 'warn');
      return { found: false, reason: 'no-pdf' };
    }
    const needles = needlesFor(finding);
    if (!needles.length) {
      setStatus(MESSAGES.noText, 'warn');
      return { found: false, reason: 'no-text' };
    }
    setStatus(MESSAGES.searching);
    const generation = state.generation;
    let hit;
    try {
      hit = await search(pageText, state.numPages, needles);
    } catch (err) {
      console.error('Estilo: falló la búsqueda en el PDF', err);
      hit = null;
    }
    if (generation !== state.generation) return { found: false, reason: 'reloaded' };
    if (!hit) {
      setStatus(MESSAGES.notFound, 'bad');
      return { found: false, reason: 'not-found' };
    }
    const indexed = state.texts.get(hit.page) || await pageText(hit.page);
    const range = refineRange(indexed, hit, finding);
    const pdfPage = await state.doc.getPage(hit.page);
    const boxes = highlightBoxes(indexed, range.start, range.end, pdfPage.getViewport({ scale: 1 }));
    await goToPage(hit.page, boxes.length ? boxes[0].top : 0);
    highlight(hit.page, boxes);
    setStatus(MESSAGES.found(hit.page), 'ok');
    return { found: true, page: hit.page, needle: hit.needle };
  }

  function snapshot() {
    return {
      active: state.active,
      mode: state.mode,
      version: state.version,
      numPages: state.numPages,
      currentPage: state.currentPage,
      scale: state.scale,
      polling: state.pollTimer !== null,
      rendered: [...state.rendered.keys()].sort((a, b) => a - b),
    };
  }

  window.EstiloPdf = {
    open,
    hide,
    sync,
    locate,
    goToPage,
    state: snapshot,
    // Pure helpers, exposed for tests.
    normalize,
    needlesFor,
    indexPage,
    search,
    highlightBoxes,
    POLL_MS,
    MESSAGES,
  };
}());
