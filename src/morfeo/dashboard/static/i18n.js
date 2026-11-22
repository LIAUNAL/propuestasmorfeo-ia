// Dashboard language runtime: Spanish by default, English on request.
//
// Ported from papersmith-ai (command_center/static/i18n.js). Morfeo's
// dashboard was written in Spanish, so Spanish is the default language and
// the fallback of every key.
//
// Catalogues
// ----------
// Strings live in ./i18n/<lang>/<namespace>.js, one file per namespace and
// language (core.js holds the markup and the inline script of index.html).
// Each file merges a flat { key: text } object into the shared table:
//
//   (window.MORFEO_I18N = window.MORFEO_I18N || {}).es =
//     Object.assign(window.MORFEO_I18N.es || {}, { "key": "texto" });
//
// A namespace needs the same file in every language with the same keys and
// the same {placeholders} (tests/test_dashboard_i18n.py holds them equal), and
// a key lives in exactly one namespace file. Load order does not matter: t()
// reads the table on every call, so a catalogue may load before or after this
// file, as long as it loads before DOMContentLoaded.
//
// Public surface
// --------------
//   t(key, vars)        the text of `key` in the active language; `{name}`
//                       placeholders are filled from `vars`. A key missing from
//                       the active catalogue falls back to Spanish, then to
//                       the key itself, never to an empty string.
//   tl(key, vars)       a marker for text written into data defined once at
//                       load time (a top-level table of labels); i18n.live(obj)
//                       turns every marker under obj into a getter that
//                       returns t(key, vars) in the language active when read.
//   setLanguage(lang)   'es' or 'en': persists the choice in localStorage
//                       (morfeo.lang), sets <html lang>, re-applies the static
//                       markup, syncs every [data-lang-select] and dispatches a
//                       'languagechange' CustomEvent on document (detail:
//                       { lang }) so each panel re-renders itself.
//   getLanguage()       the active language.
//   i18n.has(key)       whether the catalogues know `key`.
//   applyTranslations(root)
//                       re-applies the markup under `root` (default document).
//   i18n.withLanguage(url)
//                       `url` with ?lang=<lang> when it is a same-origin /api/
//                       URL and the language is not Spanish (for iframes and
//                       links, which do not go through fetch).
//
// Markup opts in with data-i18n="key" (text), data-i18n-html="key" (catalogue
// HTML; trusted, shipped with the dashboard) and
// data-i18n-attr="title:key;placeholder:key;aria-label:key". An element is
// rewritten only while it still shows a catalogue text for its key, so a value
// a script has written since (a run id, a count) is never overwritten.
//
// Server labels
// -------------
// Same-origin /api/ requests made through fetch() or loaded with iframe.src
// carry ?lang=<lang> when the language is not Spanish; the server then
// localizes its display labels (localize.py, never a machine value) and the
// pages it renders write their chrome in that language. Spanish requests are
// sent unchanged, byte for byte.
(function () {
  'use strict';

  const STORAGE_KEY = 'morfeo.lang';
  const SUPPORTED = ['es', 'en'];
  const DEFAULT_LANGUAGE = 'es';
  const catalogues = window.MORFEO_I18N || (window.MORFEO_I18N = {});

  function readSaved() {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      return SUPPORTED.includes(saved) ? saved : DEFAULT_LANGUAGE;
    } catch (_) {
      return DEFAULT_LANGUAGE;
    }
  }

  let current = readSaved();

  function has(table, key) {
    return !!table && Object.prototype.hasOwnProperty.call(table, key);
  }

  function format(text, vars) {
    if (!vars) return text;
    return text.replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (match, name) =>
      (has(vars, name) && vars[name] !== undefined && vars[name] !== null ? String(vars[name]) : match));
  }

  function t(key, vars) {
    const active = catalogues[current];
    const fallback = catalogues[DEFAULT_LANGUAGE];
    let text = has(active, key) ? active[key] : '';
    if (!text) text = has(fallback, key) && fallback[key] ? fallback[key] : String(key);
    return format(text, vars);
  }

  function getLanguage() {
    return current;
  }

  // Whether `key` has a text in Spanish (the catalogue every key is in).
  function hasKey(key) {
    return has(catalogues[DEFAULT_LANGUAGE], key);
  }

  // --- Text inside data defined at load time -------------------------------
  const MARK = typeof Symbol === 'function' ? Symbol('i18n.later') : '__i18nLater';

  function tl(key, vars) {
    const mark = { key, vars: vars || null };
    mark[MARK] = true;
    return mark;
  }

  const isMark = (value) => !!value && typeof value === 'object' && value[MARK] === true;

  // Replaces every tl() marker under `data` (objects and arrays, in place) by
  // a getter that translates on read. Returns `data`.
  function live(data, seen) {
    if (!data || typeof data !== 'object') return data;
    const visited = seen || new Set();
    if (visited.has(data)) return data;
    visited.add(data);
    Object.keys(data).forEach((prop) => {
      const value = data[prop];
      if (isMark(value)) {
        Object.defineProperty(data, prop, {
          get: () => t(value.key, value.vars),
          enumerable: true,
          configurable: true,
        });
      } else if (value && typeof value === 'object') {
        live(value, visited);
      }
    });
    return data;
  }

  // --- Markup ---------------------------------------------------------------
  const normalize = (text) => String(text == null ? '' : text).replace(/\s+/g, ' ').trim();

  // HTML values compare as the browser serializes them (<br/> becomes <br>,
  // entities are canonical), so a catalogue text still matches after parsing.
  let probe = null;
  function serialized(html) {
    if (typeof document === 'undefined' || typeof document.createElement !== 'function') return normalize(html);
    if (!probe) probe = document.createElement('div');
    probe.innerHTML = html;
    return normalize(probe.innerHTML);
  }

  // True while `shown` is the text of `key` in some catalogue: the element
  // still holds what this runtime (or the shipped markup) put there.
  function showsCatalogueText(key, shown, asHtml) {
    const value = asHtml ? serialized(shown) : normalize(shown);
    return SUPPORTED.some((lang) => has(catalogues[lang], key)
      && (asHtml ? serialized(catalogues[lang][key]) : normalize(catalogues[lang][key])) === value);
  }

  // Panel scripts also run under bare DOM stubs (the node render tests).
  const canQuery = (scope) => !!scope && typeof scope.querySelectorAll === 'function';

  function applyTranslations(root) {
    const scope = root || document;
    if (!canQuery(scope)) return;
    const pick = (selector) => {
      const found = Array.from(scope.querySelectorAll(selector));
      if (typeof scope.matches === 'function' && scope.matches(selector)) found.unshift(scope);
      return found;
    };
    pick('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (!key || !showsCatalogueText(key, el.textContent, false)) return;
      const next = t(key);
      if (el.textContent !== next) el.textContent = next;
    });
    pick('[data-i18n-html]').forEach((el) => {
      const key = el.getAttribute('data-i18n-html');
      if (!key || !showsCatalogueText(key, el.innerHTML, true)) return;
      const next = t(key);
      if (serialized(el.innerHTML) !== serialized(next)) el.innerHTML = next;
    });
    pick('[data-i18n-attr]').forEach((el) => {
      el.getAttribute('data-i18n-attr').split(';').forEach((pair) => {
        const at = pair.indexOf(':');
        if (at < 1) return;
        const attr = pair.slice(0, at).trim();
        const key = pair.slice(at + 1).trim();
        if (!el.hasAttribute(attr) || showsCatalogueText(key, el.getAttribute(attr), false)) {
          const next = t(key);
          if (el.getAttribute(attr) !== next) el.setAttribute(attr, next);
        }
      });
    });
  }

  function syncSelectors() {
    if (!canQuery(document)) return;
    document.querySelectorAll('[data-lang-select]').forEach((select) => {
      if (select.value !== current) select.value = current;
    });
  }

  function setLanguage(lang) {
    const next = SUPPORTED.includes(lang) ? lang : DEFAULT_LANGUAGE;
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch (_) { /* private mode: the choice lasts for this page only */ }
    const changed = next !== current;
    current = next;
    if (document.documentElement) document.documentElement.lang = next;
    applyTranslations(document);
    syncSelectors();
    if (changed && typeof document.dispatchEvent === 'function' && typeof CustomEvent === 'function') {
      document.dispatchEvent(new CustomEvent('languagechange', { detail: { lang: next } }));
    }
    return next;
  }

  // Same-origin /api/ URLs (and the /presentacion page) get ?lang=<lang>
  // unless they already name one.
  function withLanguage(url) {
    if (current === DEFAULT_LANGUAGE || typeof url !== 'string') return url;
    let parsed;
    try {
      parsed = new URL(url, window.location.href);
    } catch (_) {
      return url;
    }
    const served = parsed.pathname.startsWith('/api/') || parsed.pathname === '/presentacion';
    if (parsed.origin !== window.location.origin || !served) return url;
    if (parsed.searchParams.has('lang')) return url;
    parsed.searchParams.set('lang', current);
    return parsed.pathname + parsed.search + parsed.hash;
  }

  if (typeof window.fetch === 'function') {
    const nativeFetch = window.fetch.bind(window);
    window.fetch = (input, init) => nativeFetch(typeof input === 'string' ? withLanguage(input) : input, init);
  }

  // Iframes too: a page the dashboard embeds through iframe.src (the graphs,
  // the constellations) is asked for in the active language, as fetch is.
  const Frame = window.HTMLIFrameElement;
  const frameSrc = Frame && Object.getOwnPropertyDescriptor(Frame.prototype, 'src');
  if (frameSrc && frameSrc.set && frameSrc.configurable) {
    Object.defineProperty(Frame.prototype, 'src', {
      configurable: true,
      enumerable: frameSrc.enumerable,
      get: frameSrc.get,
      set(value) { frameSrc.set.call(this, typeof value === 'string' ? withLanguage(value) : value); },
    });
  }

  // A non-default language hides the page until the markup is translated, so
  // the Spanish shipped in index.html never flashes (index.html: the CSS rule
  // on html[data-i18n-pending]).
  if (document.documentElement) {
    document.documentElement.lang = current;
    if (current !== DEFAULT_LANGUAGE && document.documentElement.dataset) {
      document.documentElement.dataset.i18nPending = '';
    }
  }

  function bindSelectors() {
    if (!canQuery(document)) return;
    document.querySelectorAll('[data-lang-select]').forEach((select) => {
      if (select.dataset.langBound) return;
      select.dataset.langBound = '1';
      select.value = current;
      select.addEventListener('change', () => setLanguage(select.value));
    });
  }

  function start() {
    try {
      applyTranslations(document);
      bindSelectors();
    } finally {
      if (document.documentElement && document.documentElement.dataset) {
        delete document.documentElement.dataset.i18nPending;
      }
    }
  }

  if (document.readyState === 'loading' && typeof document.addEventListener === 'function') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }

  window.t = t;
  window.tl = tl;
  window.i18n = {
    t, tl, live, has: hasKey, setLanguage, getLanguage, applyTranslations, withLanguage,
    SUPPORTED: SUPPORTED.slice(), DEFAULT_LANGUAGE,
  };
})();
