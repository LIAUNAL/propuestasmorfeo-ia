/**
 * section-folds.js: folding bars for dashboard panels, ported from
 * papersmith-ai (skills/_core/command_center/static/section-folds.js).
 *
 * A block marked `data-fold="<name>"` with `data-fold-title="<title>"` (and
 * `data-fold-open` when it should start open) is wrapped in a
 * <details class="exp-fold" data-fold-name="<name>"> whose summary carries that
 * title. The operator's open or closed choice is remembered per browser under
 * localStorage['morfeo.folds'], so a reload or a panel that redraws keeps it.
 * Blocked or corrupt storage falls back to the defaults.
 *
 * Public surface (window.SectionFolds):
 *   wrap(root)          wraps every unwrapped [data-fold] block under root
 *   open(name)          opens that fold and remembers it; false if absent
 *   isOpen(name)        current open state of that fold (false if absent)
 *   onToggle(name, fn)  calls fn(open) whenever that fold opens or closes
 *   KEY                 the storage key
 */
(function () {
  'use strict';

  const KEY = 'morfeo.folds';
  const listeners = [];

  function storage() {
    try { return window.localStorage; } catch (_) { return null; }
  }

  function stored() {
    try {
      const store = storage();
      const value = JSON.parse((store && store.getItem(KEY)) || '{}');
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch (_) {
      return {};
    }
  }

  function remember(name, open) {
    const folds = stored();
    folds[name] = open;
    try {
      const store = storage();
      if (store) store.setItem(KEY, JSON.stringify(folds));
    } catch (_) { /* this page only */ }
  }

  function find(name) {
    return Array.from(document.querySelectorAll('details.exp-fold[data-fold-name]'))
      .find((d) => d.getAttribute('data-fold-name') === name) || null;
  }

  function wrap(root) {
    const scope = root || document;
    if (!scope.querySelectorAll) return;
    const saved = stored();
    scope.querySelectorAll('[data-fold]:not(details)').forEach((block) => {
      if (block.parentElement && block.parentElement.classList.contains('exp-fold__body')) return;
      const name = block.getAttribute('data-fold');
      const details = document.createElement('details');
      details.className = 'exp-fold';
      details.setAttribute('data-fold-name', name);
      details.open = typeof saved[name] === 'boolean' ? saved[name] : block.hasAttribute('data-fold-open');
      reported[name] = details.open;
      const summary = document.createElement('summary');
      summary.className = 'exp-fold__summary';
      const title = document.createElement('span');
      title.className = 'exp-fold__title';
      title.textContent = block.getAttribute('data-fold-title') || name;
      summary.appendChild(title);
      const body = document.createElement('div');
      body.className = 'exp-fold__body';
      block.replaceWith(details);
      details.append(summary, body);
      body.appendChild(block);
    });
  }

  // Last state the listeners were told about: open() notifies at once, and the
  // browser's own toggle event for that same change is then ignored.
  const reported = {};

  function notify(name, open) {
    if (reported[name] === open) return;
    reported[name] = open;
    listeners.forEach((l) => {
      if (l.name !== name) return;
      try { l.fn(open); } catch (_) { /* one listener never breaks the others */ }
    });
  }

  function open(name) {
    const details = find(name);
    if (!details) return false;
    if (!details.open) details.open = true;
    remember(name, true);
    notify(name, true);
    return true;
  }

  function isOpen(name) {
    const details = find(name);
    return !!(details && details.open);
  }

  function onToggle(name, fn) {
    if (typeof fn === 'function') listeners.push({ name, fn });
  }

  document.addEventListener('toggle', (event) => {
    const item = event.target;
    const name = item && item.getAttribute && item.getAttribute('data-fold-name');
    if (!name) return;
    remember(name, item.open);
    notify(name, item.open);
  }, true);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => wrap(document));
  else wrap(document);

  window.SectionFolds = { wrap, open,isOpen, onToggle, KEY };
})();
