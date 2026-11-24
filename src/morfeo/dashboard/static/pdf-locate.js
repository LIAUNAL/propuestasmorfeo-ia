/**
 * pdf-locate.js: finds a style finding in the PDF preview and highlights it
 * (odd/tasks/tablero-juez-novedad.md, S8; papersmith-ai `findTextInPdf` with
 * `{ loose: true }` and `locateStyleFinding`).
 *
 * The «Estilo y redundancia» drawer of the PDF preview calls `locate(finding,
 * adapter)` for «Ubicar». The search is loose: accents, case, ligatures (NFKD),
 * punctuation, whitespace, hyphens at line ends and LaTeX commands left in the
 * source all vanish, so the audited sentence still matches the compiled text.
 * Needles, strongest first: the first and the last seven words of the finding's
 * sentence (`oracion_texto`, attached by `/api/estilo`), then those of the
 * fragment itself. Each needle is tried across the whole document before the
 * next one, so a weak needle never wins on an earlier page.
 *
 * The module owns no viewer. The adapter is the main preview viewer:
 *   mode        'pdfjs' (searchable), 'native' (browser viewer) or 'none'
 *   numPages    pages of the loaded document
 *   pageItems   async (n) => pdf.js text items of page n
 *   viewport    async (n) => page n viewport at scale 1
 *   reveal      async (page, boxes) => scrolls there and highlights the boxes
 *   isCurrent   () => false once the document was replaced during the search
 *
 * Public surface (window.PdfLocate):
 *   locate(finding, adapter) -> { found, page, needle, boxes } | { found: false, reason }
 *   message(result)          -> status line for that result, in the active language
 *   highlight(container, boxes, { ms }) paints fading marks over a page
 *   normalize, needlesFor, indexPage, search, refineRange, highlightBoxes (pure)
 *   MESSAGES, HIGHLIGHT_MS, NEEDLE_WORDS
 */
(function () {
  'use strict';

  const HIGHLIGHT_MS = 4000;
  const MIN_NEEDLE = 12;
  const NEEDLE_WORDS = 7;
  const CITE = /\(cita\)/gi;
  const CITE_GAP = /\(cita\)|\s{2,}/i;

  // Status lines in the dashboard's language (static/i18n/<lang>/pdf-locate.js):
  // each one is read in the language active when it is shown.
  const tr = (key, vars) => (window.i18n ? window.i18n.t(key, vars) : key);
  const later = (key) => (window.i18n ? window.i18n.tl(key) : key);
  const MESSAGES = {
    searching: later('panel.pdfLocate.searching'),
    found: (page) => tr('panel.pdfLocate.found', { page }),
    notFound: later('panel.pdfLocate.notFound'),
    noText: later('panel.pdfLocate.noText'),
    noPdf: later('panel.pdfLocate.noPdf'),
    native: later('panel.pdfLocate.native'),
    reloaded: later('panel.pdfLocate.reloaded'),
  };
  if (window.i18n) window.i18n.live(MESSAGES);

  // --- Loose text normalization ---------------------------------------------
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

  /** Needles for a finding, strongest first; short or duplicate needles drop. */
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

  /** First page holding a needle; `pageAt(n)` returns (or resolves to) `indexPage` output. */
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
        left: Math.max(0, m[4] / width),
        top: Math.max(0, (m[5] - fontHeight) / height),
        width: boxWidth / width,
        height: (fontHeight * 1.2) / height,
      };
    });
  }

  // --- Locate -----------------------------------------------------------------
  async function locate(finding, adapter) {
    const a = adapter || {};
    if (a.mode === 'native') return { found: false, reason: 'native' };
    if (a.mode !== 'pdfjs' || !(Number(a.numPages) > 0)) return { found: false, reason: 'no-pdf' };
    const needles = needlesFor(finding);
    if (!needles.length) return { found: false, reason: 'no-text' };
    const current = typeof a.isCurrent === 'function' ? a.isCurrent : () => true;
    const indexed = new Map();
    const pageAt = async (n) => {
      if (!indexed.has(n)) indexed.set(n, indexPage(await a.pageItems(n)));
      return indexed.get(n);
    };
    let hit = null;
    try {
      hit = await search(pageAt, Number(a.numPages), needles);
    } catch (err) {
      if (typeof console !== 'undefined') console.error('Ubicar: falló la búsqueda en el PDF', err);
      hit = null;
    }
    if (!current()) return { found: false, reason: 'reloaded' };
    if (!hit) return { found: false, reason: 'not-found' };
    const page = await pageAt(hit.page);
    const range = refineRange(page, hit, finding);
    const boxes = highlightBoxes(page, range.start, range.end, await a.viewport(hit.page));
    if (!current()) return { found: false, reason: 'reloaded' };
    if (typeof a.reveal === 'function') await a.reveal(hit.page, boxes);
    return { found: true, page: hit.page, needle: hit.needle, boxes };
  }

  function message(result) {
    const r = result || {};
    if (r.found) return MESSAGES.found(r.page);
    return {
      native: MESSAGES.native,
      'no-pdf': MESSAGES.noPdf,
      'no-text': MESSAGES.noText,
      reloaded: MESSAGES.reloaded,
    }[r.reason] || MESSAGES.notFound;
  }

  // --- Highlight ----------------------------------------------------------------
  let fadeTimer = null;

  /** Fading marks over one page container; only one located finding at a time. */
  function highlight(container, boxes, options) {
    const ms = options && Number(options.ms) > 0 ? Number(options.ms) : HIGHLIGHT_MS;
    const doc = container ? container.ownerDocument : (typeof document !== 'undefined' ? document : null);
    if (doc) doc.querySelectorAll('.pdf-locate-hl').forEach((el) => el.remove());
    if (fadeTimer !== null) clearTimeout(fadeTimer);
    fadeTimer = null;
    if (!container) return [];
    let layer = Array.from(container.children).find((el) => el.classList.contains('pdf-locate-layer'));
    if (!layer) {
      layer = doc.createElement('div');
      layer.className = 'pdf-locate-layer';
      container.appendChild(layer);
    }
    const marks = (boxes || []).map((box) => {
      const mark = doc.createElement('div');
      mark.className = 'pdf-locate-hl';
      mark.style.left = `${(box.left * 100).toFixed(3)}%`;
      mark.style.top = `${(box.top * 100).toFixed(3)}%`;
      mark.style.width = `${(box.width * 100).toFixed(3)}%`;
      mark.style.height = `${(box.height * 100).toFixed(3)}%`;
      layer.appendChild(mark);
      return mark;
    });
    fadeTimer = setTimeout(() => {
      fadeTimer = null;
      marks.forEach((mark) => mark.remove());
    }, ms);
    return marks;
  }

  window.PdfLocate = {
    locate,
    message,
    highlight,
    normalize,
    needlesFor,
    indexPage,
    search,
    refineRange,
    highlightBoxes,
    MESSAGES,
    HIGHLIGHT_MS,
    NEEDLE_WORDS,
  };
}());
