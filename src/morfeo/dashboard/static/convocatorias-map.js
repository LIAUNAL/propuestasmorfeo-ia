// «Convocatorias» views: opportunity tree, affinity constellation, side by
// side, requirements matrix, timeline and the detail panel (bottom sheet under
// 1080 px). Port of the validated prototype (prototipos/convocatorias) driven
// by the real view payload `morfeo.convocatorias-vista/v1`: every score, tema,
// alert and date comes from scripts/convocatorias.py (match, componentes,
// temas_match, experiencia, historial, alertas, preparar_desde, titulo_corto,
// mapa, perfiles, alcance); this file only draws them. Older payloads without
// those keys still render (puntaje instead of match, «—» without requisitos).
//
// The page's inline script owns the data, the filters and the «Lista» view; it
// calls window.cvMap.render(viewEl, detailEl, items, ctx) for the other views.
// Loaded before that script: page helpers (startOpportunity, cvAmount) are
// looked up when used, never at load time.
//
// Hover and selection only toggle classes and redraw the link layers: the
// elements under the pointer are never replaced, so clicks and drags on the
// constellation stay reliable and any node can be clicked after another.
//
// Public surface: window.cvMap = { render, select, reset, closeSheet }.
(function () {
  'use strict';

  const DAY = 86400000;
  const ROLES = {
    lider: ['Puede liderar', 'ok'],
    socio: ['Solo como socio', 'warn'],
    coaplicante: ['Solo como coaplicante', 'warn'],
    anfitrion_exterior: ['Requiere anfitrión en el exterior', 'warn'],
    no_elegible: ['No elegible desde Colombia', 'bad'],
    desconocido: ['Rol por confirmar', 'dim'],
  };
  const AMBITOS = { colombia: 'Colombia', latam: 'América Latina', internacional: 'Internacional' };
  const IDIOMAS = { es: 'Español', en: 'Inglés', pt: 'Portugués', fr: 'Francés' };
  const APLICANTES = {
    investigador: 'Investigador', estudiante: 'Estudiante', grupo: 'Grupo de investigación',
    centro: 'Centro', universidad: 'Universidad', empresa: 'Empresa',
  };
  // Days of preparation per effort level (same table as the script's `need`).
  const ESFUERZO = { bajo: 15, medio: 45, alto: 90 };
  const REQ_COLS = [
    ['consorcio', 'Consorcio'], ['contrapartida', 'Contrapartida'], ['anfitrion', 'Anfitrión'], ['idioma', 'Idioma'],
    ['perfil', 'Perfil'], ['aval', 'Aval o categoría'], ['entidad', 'Tipo de entidad'], ['otro', 'Otro'],
  ];
  const REQ_MARK = { cumple: ['m-ok', '✓'], por_verificar: ['m-warn', '⚠'], no_cumple: ['m-no', '✕'] };
  const REQ_RANK = { cumple: 1, por_verificar: 2, no_cumple: 3 };
  const COMPONENTES = [
    ['tematica', 'Temática', 'Coincidencia de los temas de la convocatoria con el perfil (35 %)'],
    ['experiencia', 'Experiencia', 'Experiencia del banco LIA conectada y financiador previo (25 %)'],
    ['elegibilidad', 'Elegibilidad', 'Rol que puede tener un solicitante colombiano (25 %)'],
    ['tiempo', 'Tiempo', 'Días al cierre frente al esfuerzo estimado (15 %)'],
  ];
  const NO_EXPERIENCE = 'Ejecuta Buscar para el banco LIA para ver la experiencia del laboratorio';
  const EMPTY = '<div class="cvm-empty">Ninguna convocatoria cumple los filtros.</div>';

  const S = {
    sel: null, focus: null, expanded: new Set(), cv: null, cpos: null,
    last: null, X: null, wired: false, resizeTimer: null,
  };

  // ------------------------------------------------------------- helpers
  function esc(value) {
    const text = value == null ? '' : String(value);
    return text.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  const fold = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const list = v => (Array.isArray(v) ? v : []);
  const str = v => (typeof v === 'string' ? v : '');
  const cap = s => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
  function num(v) {
    if (typeof v === 'number') return Number.isFinite(v) ? v : null;
    if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) return Number(v);
    return null;
  }
  function media(query) {
    try { return !!(window.matchMedia && window.matchMedia(query).matches); } catch (_) { return false; }
  }
  const coarse = () => media('(pointer: coarse)');
  const isDay = d => typeof d === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(d);
  const toDate = d => (isDay(d) ? new Date(`${d}T00:00:00`) : null);
  function fmtDate(d) {
    const x = toDate(d);
    return x ? x.toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' }) : 'sin fecha';
  }
  function safeUrl(url) {
    const s = str(url).trim();
    return /^https?:\/\//i.test(s) ? s : '';
  }

  // Fallback short name for payloads without `titulo_corto` (the script derives
  // the same: cut at a word boundary, at most 28 characters with the «…»).
  function shortTitle(title) {
    const s = String(title || '').trim();
    if (s.length <= 28) return s;
    const cut = s.slice(0, 27);
    const at = cut.lastIndexOf(' ');
    return `${(at > 8 ? cut.slice(0, at) : cut).replace(/[\s·,;:–-]+$/, '')}…`;
  }

  // Two to four letters for an experiencia box: an acronym in the name when it
  // has one (EEG), else the initials of its longer words.
  function abbrev(name) {
    const words = String(name || '').split(/\s+/).filter(Boolean);
    const acro = words.find(w => /^[A-ZÁÉÍÓÚÑ0-9]{2,5}$/.test(w));
    if (acro) return acro.slice(0, 4);
    const long = words.filter(w => w.length > 3);
    const pick = (long.length ? long : words).slice(0, 2).map(w => w.charAt(0).toUpperCase()).join('');
    return pick || '·';
  }

  function norm(o) {
    const rol = ROLES[o.rol_colombia] ? o.rol_colombia : 'desconocido';
    const match = num(o.match) !== null ? num(o.match) : (num(o.puntaje) !== null ? num(o.puntaje) : 0);
    const temas = list(o.temas_match).filter(t => t && typeof t.tema === 'string' && t.tema.trim())
      .map(t => ({ tema: t.tema, key: fold(t.tema), peso: num(t.peso) !== null ? num(t.peso) : 0 }))
      .sort((a, b) => b.peso - a.peso);
    return {
      raw: o,
      id: String(o.id || ''),
      titulo: String(o.titulo || o.id || 'Convocatoria sin título'),
      corto: str(o.titulo_corto).trim() || shortTitle(o.titulo || o.id),
      match: Math.round(match),
      rol,
      dias: num(o.dias_restantes),
      vigente: o.vigente === true,
      estado: str(o.estado),
      temas,
      exp: list(o.experiencia).filter(x => typeof x === 'string'),
      historial: o.historial === true,
      comp: o.componentes && typeof o.componentes === 'object' ? o.componentes : null,
      alertas: list(o.alertas).filter(a => a && typeof a.texto === 'string'),
      esfuerzo: ESFUERZO[o.esfuerzo] ? o.esfuerzo : null,
      preparar: isDay(o.preparar_desde) ? o.preparar_desde : null,
      requisitos: Array.isArray(o.requisitos) ? o.requisitos.filter(r => r && typeof r === 'object') : null,
    };
  }

  function context(ctx, rawItems) {
    const v = ctx.vista && typeof ctx.vista === 'object' ? ctx.vista : {};
    const hoy = isDay(v.hoy) ? v.hoy : new Date().toISOString().slice(0, 10);
    const items = rawItems.map(norm);
    const mapa = v.mapa && typeof v.mapa === 'object' ? v.mapa : {};
    const total = list(v.oportunidades).length || items.length;
    let temas = list(mapa.temas).filter(t => t && typeof t.tema === 'string' && t.tema.trim())
      .map(t => ({ tema: t.tema, key: fold(t.tema), n: num(t.n) !== null ? num(t.n) : 0 }));
    if (!temas.length) {
      // Older payloads: the temas the calls themselves matched.
      const seen = new Map();
      items.forEach(c => c.temas.forEach(t => {
        if (!seen.has(t.key)) seen.set(t.key, { tema: t.tema, key: t.key, n: 0 });
        seen.get(t.key).n += 1;
      }));
      temas = [...seen.values()];
    }
    const exp = list(mapa.experiencia).filter(x => x && typeof x.id === 'string')
      .map(x => ({
        id: x.id, nombre: String(x.nombre || x.id), detalle: str(x.detalle), corto: abbrev(x.nombre || x.id),
        temas: list(x.temas).filter(t => typeof t === 'string').map(fold), n: num(x.n) !== null ? num(x.n) : 0,
      }));
    const perfil = v.perfil && typeof v.perfil === 'object' ? v.perfil : {};
    const alcance = ctx.alcance === 'banco' ? 'banco' : 'proyecto';
    const scopeLabel = alcance === 'banco' ? 'Banco LIA' : 'Proyecto en formulación';
    return {
      v, hoy, items, temas, exp, total, alcance, scopeLabel,
      titulo: str(perfil.titulo).trim() || scopeLabel,
      trunkDetail: perfil.existe === false ? 'Todavía no hay perfil de búsqueda para este alcance'
        : `Perfil de búsqueda: ${temas.length} ${temas.length === 1 ? 'tema' : 'temas'}${exp.length ? ` y ${exp.length} ${exp.length === 1 ? 'línea' : 'líneas'} de experiencia` : ''}`,
      agrupar: ['ambito', 'rol'].includes(ctx.agrupar) ? ctx.agrupar : 'tema',
      view: ctx.view,
    };
  }

  function urgency(c) {
    if (!c.vigente) return { color: 'var(--text-dim)', label: c.estado === 'pausada' ? 'Pausada' : 'Cerrada', tone: 'dim', u: 'dim' };
    if (c.dias === null) return { color: 'var(--cvm-info)', label: 'Sin fecha', tone: 'info', u: 'info' };
    const n = Math.round(c.dias);
    if (n <= 30) return { color: 'var(--bad)', label: n <= 0 ? 'Cierra hoy' : `Cierra en ${n} d`, tone: 'bad', u: 'bad' };
    if (n <= 90) return { color: 'var(--warn)', label: `Cierra en ${n} d`, tone: 'warn', u: 'warn' };
    return { color: 'var(--ok)', label: `Cierra en ${n} d`, tone: 'ok', u: 'ok' };
  }

  const isLate = (c, X) => c.vigente && !!c.preparar && c.preparar < X.hoy;

  function groupOf(c, X) {
    if (X.agrupar === 'ambito') return AMBITOS[c.raw.ambito] ? c.raw.ambito : 'otro';
    if (X.agrupar === 'rol') return c.rol;
    return c.temas.length ? c.temas[0].key : '';
  }
  function groupLabel(k, X) {
    if (X.agrupar === 'ambito') return AMBITOS[k] || 'Otro ámbito';
    if (X.agrupar === 'rol') return ROLES[k][0];
    if (!k) return 'Sin tema del perfil';
    const t = X.temas.find(x => x.key === k);
    return cap(t ? t.tema : k);
  }
  function groups(X) {
    const map = new Map();
    X.items.forEach(c => {
      const k = groupOf(c, X);
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(c);
    });
    return [...map.entries()].map(([k, items]) => ({
      k, label: groupLabel(k, X),
      list: items.slice().sort((a, b) => b.match - a.match),
      avg: Math.round(items.reduce((a, c) => a + c.match, 0) / items.length),
    })).sort((a, b) => b.avg - a.avg);
  }

  // Which elements light up for the hovered or selected thing.
  function lit(X) {
    const f = S.focus || (S.sel ? { kind: 'call', id: S.sel } : null);
    if (!f) return null;
    const out = { calls: new Set(), themes: new Set(), roots: new Set(), f };
    if (f.kind === 'call') {
      const c = X.items.find(x => x.id === f.id);
      if (!c) return null;
      out.calls.add(c.id);
      c.temas.forEach(t => out.themes.add(t.key));
      c.exp.forEach(id => out.roots.add(id));
    } else if (f.kind === 'theme') {
      out.themes.add(f.id);
      X.items.filter(c => c.temas.some(t => t.key === f.id)).forEach(c => out.calls.add(c.id));
      X.exp.filter(r => r.temas.includes(f.id)).forEach(r => out.roots.add(r.id));
    } else if (f.kind === 'root') {
      const root = X.exp.find(r => r.id === f.id);
      out.roots.add(f.id);
      if (root) root.temas.forEach(t => out.themes.add(t));
      X.items.filter(c => c.exp.includes(f.id)).forEach(c => out.calls.add(c.id));
    }
    return out;
  }

  // ------------------------------------------------------------- tree view
  function cardHtml(c) {
    const u = urgency(c);
    const role = ROLES[c.rol];
    const warn = c.alertas.filter(a => a.severidad !== 'info').length;
    return `<button type="button" class="cvm-card${S.sel === c.id ? ' is-sel' : ''}" data-call="${esc(c.id)}" style="--c:${u.color};--m:${clamp(c.match, 0, 100)}" aria-label="${esc(c.titulo)}, match ${c.match}">
        <span class="cvm-score"><span>${c.match}</span></span>
        <span class="cvm-card__t">${esc(c.titulo)}</span>
        <span class="cvm-card__meta">
          <span class="cvm-pill cvm-pill--${u.tone}">⏱ ${esc(u.label)}</span>
          <span class="cvm-pill cvm-pill--${role[1]}">${esc(role[0])}</span>
          ${warn ? `<span class="cvm-pill cvm-pill--warn" title="Alertas de requisitos">⚠ ${warn}</span>` : ''}
          ${c.raw.idioma ? `<span>${esc(String(c.raw.idioma).toUpperCase())}</span>` : ''}
        </span>
      </button>`;
  }

  function renderTree(el, X) {
    const gs = groups(X);
    const groupsHtml = gs.map(g => {
      const open = S.expanded.has(g.k);
      const shown = open ? g.list : g.list.slice(0, 4);
      const rest = g.list.length - shown.length;
      return `<section class="cvm-group" data-ids="${esc(g.list.map(c => c.id).join(' '))}">
          <div class="cvm-group__head"><span>${esc(g.label)}</span><small>${g.list.length} · match medio ${g.avg}</small></div>
          ${shown.map(cardHtml).join('')}
          ${rest > 0 ? `<button type="button" class="cvm-more" data-cvm-expand="${esc(g.k)}">+ ${rest} más</button>` : ''}
          ${open && g.list.length > 4 ? `<button type="button" class="cvm-more" data-cvm-expand="${esc(g.k)}">Mostrar menos</button>` : ''}
        </section>`;
    }).join('');
    const themeHtml = X.temas.map(t => {
      const w = Math.round(100 * t.n / Math.max(1, X.total));
      return `<button type="button" class="cvm-node cvm-node--theme" data-theme="${esc(t.key)}" title="${t.n} de ${X.total} convocatorias tocan este tema">
          ${esc(cap(t.tema))}<span class="cvm-bar"><span style="width:${w}%"></span></span></button>`;
    }).join('') || '<span class="cvm-hint">El perfil todavía no declara temas.</span>';
    const rootHtml = X.exp.map(r => `<button type="button" class="cvm-node cvm-node--root" data-root="${esc(r.id)}">
        <strong>${esc(r.nombre)}</strong>${r.detalle ? `<small>${esc(r.detalle)}</small>` : ''}<small>${r.n} ${r.n === 1 ? 'convocatoria' : 'convocatorias'}</small></button>`).join('')
      || `<span class="cvm-hint">${NO_EXPERIENCE}.</span>`;
    el.innerHTML = `<div class="cvm-tree">
        <svg class="cvm-links" aria-hidden="true"></svg>
        <div class="cvm-tier">Frutos · convocatorias ordenadas por match</div>
        ${gs.length ? `<div class="cvm-groups">${groupsHtml}</div>` : EMPTY}
        <div class="cvm-tree-link"></div>
        <div class="cvm-tier">Ramas · temas del perfil (barra = parte de las convocatorias)</div>
        <div class="cvm-row">${themeHtml}</div>
        <div class="cvm-tree-link"></div>
        <div class="cvm-tier">Tronco · ${esc(X.scopeLabel)}</div>
        <div class="cvm-row"><div class="cvm-node cvm-node--trunk"><strong>${esc(X.titulo)}</strong><small>${esc(X.trunkDetail)}</small></div></div>
        <div class="cvm-tree-link"></div>
        <div class="cvm-tier">Raíces · experiencia del banco LIA</div>
        <div class="cvm-row">${rootHtml}</div>
      </div>`;
  }

  function drawTreeLinks(view, X, hl) {
    view.querySelectorAll('.cvm-tree').forEach(box => {
      const svg = box.querySelector('svg.cvm-links');
      if (!svg) return;
      svg.innerHTML = '';
      if (!hl) return;
      const b = box.getBoundingClientRect();
      if (!b.width) return;
      const pt = (el, side) => {
        const q = el.getBoundingClientRect();
        return [q.left - b.left + q.width / 2, side === 'top' ? q.top - b.top : q.bottom - b.top];
      };
      let paths = '';
      const path = (a, z, cls) => {
        const my = (a[1] + z[1]) / 2;
        paths += `<path class="${cls}" d="M${a[0]},${a[1]} C${a[0]},${my} ${z[0]},${my} ${z[0]},${z[1]}"/>`;
      };
      const trunk = box.querySelector('.cvm-node--trunk');
      const themeEls = [...box.querySelectorAll('.cvm-node--theme')];
      const themeEl = k => themeEls.find(el => el.dataset.theme === k);
      box.querySelectorAll('.cvm-card[data-call]').forEach(card => {
        if (!hl.calls.has(card.dataset.call)) return;
        const c = X.items.find(x => x.id === card.dataset.call);
        if (c) c.temas.filter(t => hl.themes.has(t.key)).forEach(t => { const te = themeEl(t.key); if (te) path(pt(card, 'bottom'), pt(te, 'top'), 'lk'); });
      });
      hl.themes.forEach(k => { const te = themeEl(k); if (te && trunk) path(pt(te, 'bottom'), pt(trunk, 'top'), 'lk'); });
      box.querySelectorAll('.cvm-node--root').forEach(re => {
        if (hl.roots.has(re.dataset.root) && trunk) path(pt(trunk, 'bottom'), pt(re, 'top'), 'lk lk--root');
      });
      svg.innerHTML = paths;
    });
  }

  // ------------------------------------------------------- constellation view
  // Every node carries its short name. Names sit in two side columns with leader
  // lines, so they never overlap; the name, the node and a wider invisible ring
  // are all clickable. Dragging starts only after the pointer moves 4 px, so a
  // click is a click; a click on the background clears the selection.
  function baseViewBox(k) {
    // Wide enough for the two name columns (cx ± 400 plus the longest short name).
    const ext = Math.round((k - 1) * 170);
    return { x: -190 - ext, y: -40, w: 1380 + 2 * ext, h: 900 };
  }

  function shapeSvg(rol, nr) {
    if (rol === 'no_elegible') {
      const a = (nr * 0.75).toFixed(1);
      return `<g class="shape sh-x sh-sel"><line x1="-${a}" y1="-${a}" x2="${a}" y2="${a}"/><line x1="-${a}" y1="${a}" x2="${a}" y2="-${a}"/></g>`;
    }
    if (rol === 'lider') return `<circle class="shape sh-fill sh-sel" r="${nr.toFixed(1)}"/>`;
    if (rol === 'anfitrion_exterior') return `<circle class="shape sh-ring sh-sel" r="${(nr * 0.9).toFixed(1)}" stroke-dasharray="4 3"/>`;
    if (rol === 'desconocido') return `<circle class="shape sh-ring sh-thin sh-sel" r="${(nr * 0.9).toFixed(1)}" stroke-dasharray="1 3"/>`;
    return `<g class="shape"><circle class="sh-ring sh-sel" r="${nr.toFixed(1)}"/><path class="sh-half" d="M0,${(-nr).toFixed(1)} A${nr.toFixed(1)},${nr.toFixed(1)} 0 0 1 0,${nr.toFixed(1)} Z"/></g>`;
  }

  function renderConstellation(el, X) {
    el.innerHTML = `<div class="cvm-constwrap"><div class="cvm-zoombar" role="group" aria-label="Zoom">
        <button type="button" class="btn btn--xs" data-cvm-zoom="in" aria-label="Acercar">＋</button>
        <button type="button" class="btn btn--xs" data-cvm-zoom="out" aria-label="Alejar">－</button>
        <button type="button" class="btn btn--xs" data-cvm-zoom="reset" aria-label="Restablecer vista">⟲</button></div>
        <div class="cvm-constscroll"><svg class="cvm-const" role="img" aria-label="Constelación de afinidad: más cerca del centro, mejor match"></svg></div></div>
        ${legendHtml()}`;
    const svg = el.querySelector('svg.cvm-const');
    const width = Math.max(320, svg.getBoundingClientRect().width || el.clientWidth || 900);
    // Scale text and nodes so names stay near 10-11 px on screen at any width.
    const k = clamp(1250 / width, 1, 2.8);
    const fs = 12.5 * k;
    const nr = 9 * Math.min(k, 1.6);
    const lh = fs * 1.5;
    const vb = baseViewBox(k);
    if (!S.cv || S.cv.k !== k) S.cv = { ...vb, k };
    const cx = 500;
    const cy = 410;
    const items = X.items;
    const ms = items.map(c => c.match);
    const hi = ms.length ? Math.max(...ms) : 100;
    const lo = ms.length ? Math.min(...ms) : 0;
    const R = m => 120 + (hi - m) / Math.max(10, hi - lo) * 230;
    const gs = groups(X);
    const gap = 0.08;
    const full = Math.PI * 2 - gap * Math.max(gs.length, 1);
    const weight = gs.reduce((a, g) => a + Math.max(g.list.length, 1.5), 0) || 1;
    let a0 = -Math.PI / 2;
    const nodes = [];
    const sectors = [];
    gs.forEach(g => {
      const span = full * Math.max(g.list.length, 1.5) / weight;
      sectors.push({ g, a0, a1: a0 + span });
      g.list.forEach((c, i) => {
        const ang = a0 + span * (i + 0.5) / g.list.length;
        const rad = R(c.match) + (i % 3 === 1 ? 14 : i % 3 === 2 ? -10 : 0);
        nodes.push({ c, x: cx + rad * Math.cos(ang), y: cy + rad * Math.sin(ang) });
      });
      a0 += span + gap;
    });
    // The experiencia boxes ring the centre; the busiest first, at most 12.
    const roots = X.exp.slice().sort((a, b) => b.n - a.n).slice(0, 12);
    const rr = clamp(roots.length * 34 / (2 * Math.PI), 50, 92);
    const rootPos = roots.map((r, i) => {
      const ang = -Math.PI / 2 + i * 2 * Math.PI / Math.max(roots.length, 1);
      return { r, px: cx + rr * Math.cos(ang), py: cy + rr * Math.sin(ang) };
    });
    S.cpos = { cx, cy, nodes, rootPos, sectors };

    // Label columns: right half to the right column, left half to the left one,
    // ordered by the node's height and pushed apart to a minimum line gap.
    const colR = cx + 400;
    const colL = cx - 400;
    const top = vb.y + 20;
    const bottom = vb.y + vb.h - 20;
    const place = side => {
      side.sort((a, b) => a.n.y - b.n.y);
      side.forEach(l => { l.y = clamp(l.n.y, top, bottom); });
      for (let i = 1; i < side.length; i++) if (side[i].y < side[i - 1].y + lh) side[i].y = side[i - 1].y + lh;
      const over = side.length ? side[side.length - 1].y - bottom : 0;
      if (over > 0) side.forEach(l => { l.y -= over; });
      for (let i = side.length - 2; i >= 0; i--) if (side[i].y > side[i + 1].y - lh) side[i].y = side[i + 1].y - lh;
    };
    const right = nodes.filter(n => n.x >= cx).map(n => ({ n, right: true }));
    const left = nodes.filter(n => n.x < cx).map(n => ({ n, right: false }));
    place(right);
    place(left);
    const labelOf = new Map([...right, ...left].map(l => [l.n.c.id, l]));

    const step = hi - lo > 40 ? 20 : 10;
    const ringVals = [];
    for (let m = Math.floor(hi / step) * step; m > lo; m -= step) if (m < hi) ringVals.push(m);
    const rings = ringVals.map(m => `<circle class="ring" cx="${cx}" cy="${cy}" r="${R(m).toFixed(1)}"/><text class="ringlbl" x="${cx + 4}" y="${(cy - R(m) - 4).toFixed(1)}" font-size="${(10.5 * k).toFixed(1)}">match ${m}</text>`).join('');
    const sectorLines = sectors.length > 1 ? sectors.map(s => {
      const a = s.a0 - gap / 2;
      return `<line class="sector" x1="${(cx + 70 * Math.cos(a)).toFixed(1)}" y1="${(cy + 70 * Math.sin(a)).toFixed(1)}" x2="${(cx + 370 * Math.cos(a)).toFixed(1)}" y2="${(cy + 370 * Math.sin(a)).toFixed(1)}"/>`;
    }).join('') : '';
    const sectorLabels = sectors.map(s => {
      const am = (s.a0 + s.a1) / 2;
      return `<text class="seclbl" data-ids="${esc(s.g.list.map(c => c.id).join(' '))}" x="${(cx + 372 * Math.cos(am)).toFixed(1)}" y="${(cy + 372 * Math.sin(am)).toFixed(1)}" text-anchor="middle" dominant-baseline="middle" font-size="${(11.5 * k).toFixed(1)}">${esc(s.g.label)} · ${s.g.avg}</text>`;
    }).join('');
    const nodeSvg = nodes.map(n => {
      const u = urgency(n.c);
      const l = labelOf.get(n.c.id);
      const colX = (l.right ? colR : colL) - n.x;
      const ly = l.y - n.y;
      const dir = l.right ? 1 : -1;
      const leader = `<path class="leader" d="M${(dir * (nr + 2)).toFixed(1)},0 L${(colX - dir * 14).toFixed(1)},${ly.toFixed(1)} L${(colX - dir * 4).toFixed(1)},${ly.toFixed(1)}"/>`;
      const label = `<text class="lbl" x="${colX.toFixed(1)}" y="${(ly + fs * 0.35).toFixed(1)}" text-anchor="${l.right ? 'start' : 'end'}" font-size="${fs.toFixed(1)}">${esc(n.c.corto)} · ${n.c.match}</text>`;
      return `<g class="n u-${u.u}${S.sel === n.c.id ? ' is-sel' : ''}" data-call="${esc(n.c.id)}" transform="translate(${n.x.toFixed(1)},${n.y.toFixed(1)})" tabindex="0" role="button" aria-label="${esc(n.c.titulo)}, match ${n.c.match}">`
        + `${leader}<circle class="hit" r="${(nr + 8).toFixed(1)}"/>${shapeSvg(n.c.rol, nr)}${label}</g>`;
    }).join('');
    const rootSvg = rootPos.map(rp => `<g class="root" data-root="${esc(rp.r.id)}" transform="translate(${rp.px.toFixed(1)},${rp.py.toFixed(1)})"><rect x="-15" y="-11" width="30" height="22" rx="5"/><text text-anchor="middle" y="4">${esc(rp.r.corto)}</text><title>${esc(rp.r.nombre)}</title></g>`).join('');
    svg.setAttribute('viewBox', `${S.cv.x} ${S.cv.y} ${S.cv.w} ${S.cv.h}`);
    svg.innerHTML = `${rings}${sectorLines}${sectorLabels}<g class="cvm-edges"></g>
        <circle class="center" cx="${cx}" cy="${cy}" r="24"/>
        <text class="centerlbl" x="${cx}" y="${cy + 4}" text-anchor="middle">${X.alcance === 'banco' ? 'LIA' : 'PRY'}</text>
        ${rootSvg}${nodeSvg}`;
    wireSvg(svg);
  }

  function legendHtml() {
    return `<div class="cvm-legend">
        <span>Más cerca del centro = mejor match</span>
        <span><span class="cvm-dot" style="background:var(--bad)"></span>cierra en ≤30 d</span><span><span class="cvm-dot" style="background:var(--warn)"></span>31 a 90 d</span>
        <span><span class="cvm-dot" style="background:var(--ok)"></span>más de 90 d</span><span><span class="cvm-dot" style="background:var(--cvm-info)"></span>sin fecha</span>
        <span>● lidera · ◐ socio o coaplicante · ◌ anfitrión en el exterior · ✕ no elegible</span>
        <span>Cuadros violeta = experiencia del banco LIA</span>
        <span>${coarse() ? 'Toca un nodo o su nombre; usa ＋ y － para el zoom' : 'Clic en un nodo o su nombre · rueda o ＋/－: zoom · arrastrar el fondo: mover · clic en el fondo: limpiar'}</span>
      </div>`;
  }

  const setViewBox = svg => svg.setAttribute('viewBox', `${S.cv.x} ${S.cv.y} ${S.cv.w} ${S.cv.h}`);
  function zoomAt(svg, k, px, py) {
    S.cv.x = px - (px - S.cv.x) * k;
    S.cv.y = py - (py - S.cv.y) * k;
    S.cv.w *= k;
    S.cv.h *= k;
    setViewBox(svg);
  }

  function zoom(kind) {
    const svg = S.last && S.last.viewEl.querySelector('svg.cvm-const');
    if (!svg || !S.cv) return;
    if (kind === 'reset') { S.cv = null; rerender(); return; }
    zoomAt(svg, kind === 'in' ? 1 / 1.25 : 1.25, S.cv.x + S.cv.w / 2, S.cv.y + S.cv.h / 2);
  }

  function wireSvg(svg) {
    svg.addEventListener('wheel', e => {
      if (!S.cv || typeof svg.createSVGPoint !== 'function' || typeof svg.getScreenCTM !== 'function') return;
      const ctm = svg.getScreenCTM();
      if (!ctm) return;
      e.preventDefault();
      const p = svg.createSVGPoint();
      p.x = e.clientX;
      p.y = e.clientY;
      const q = p.matrixTransform(ctm.inverse());
      zoomAt(svg, e.deltaY > 0 ? 1.12 : 1 / 1.12, q.x, q.y);
    }, { passive: false });
    let drag = null;
    svg.addEventListener('pointerdown', e => {
      if (e.button !== 0 || (e.target.closest && e.target.closest('.n, .root'))) return;
      drag = { x: e.clientX, y: e.clientY, cx: S.cv ? S.cv.x : 0, cy: S.cv ? S.cv.y : 0, id: e.pointerId, moved: false };
    });
    svg.addEventListener('pointermove', e => {
      if (!drag || !S.cv || coarse()) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      if (!drag.moved) {
        if (Math.hypot(dx, dy) < 4) return;
        drag.moved = true;
        try { svg.setPointerCapture(drag.id); } catch (_) { /* pointer already gone */ }
        svg.classList.add('is-dragging');
      }
      const scale = S.cv.w / (svg.getBoundingClientRect().width || S.cv.w);
      S.cv.x = drag.cx - dx * scale;
      S.cv.y = drag.cy - dy * scale;
      setViewBox(svg);
    });
    svg.addEventListener('pointerup', () => {
      if (drag && !drag.moved && (S.sel || S.focus)) select(null);
      drag = null;
      svg.classList.remove('is-dragging');
    });
    svg.addEventListener('pointercancel', () => { drag = null; svg.classList.remove('is-dragging'); });
  }

  // ------------------------------------------------------ requirements matrix
  function renderMatrix(el, X) {
    if (!X.items.length) { el.innerHTML = EMPTY; return; }
    const mark = (c, tipo) => {
      const reqs = (c.requisitos || []).filter(r => r.tipo === tipo && REQ_MARK[r.estado]);
      if (!reqs.length) return `<td class="m-na" data-tipo="${tipo}" title="No se exige o no está registrado">—</td>`;
      const worst = reqs.reduce((a, r) => (REQ_RANK[r.estado] > REQ_RANK[a.estado] ? r : a));
      const [cls, sym] = REQ_MARK[worst.estado];
      return `<td class="${cls}" data-tipo="${tipo}" title="${esc(reqs.map(r => str(r.texto)).join(' · '))}">${sym}</td>`;
    };
    const none = X.items.every(c => c.requisitos === null);
    el.innerHTML = `<div class="cvm-tablewrap"><table class="cvm-matrix">
        <thead><tr><th class="l">Convocatoria</th><th>Match</th><th>Rol de Colombia</th><th>Cierre</th>${REQ_COLS.map(([, l]) => `<th>${l}</th>`).join('')}</tr></thead>
        <tbody>${X.items.map(c => {
          const u = urgency(c);
          return `<tr data-call="${esc(c.id)}" class="${S.sel === c.id ? 'is-sel' : ''}"><td class="l"><strong>${esc(c.titulo)}</strong><br><span class="cvm-dim">${esc(c.raw.financiador || '')}</span></td>
            <td><strong>${c.match}</strong></td><td><span class="cvm-pill cvm-pill--${ROLES[c.rol][1]}">${esc(ROLES[c.rol][0])}</span></td>
            <td><span class="cvm-pill cvm-pill--${u.tone}">${esc(u.label)}</span></td>${REQ_COLS.map(([tipo]) => mark(c, tipo)).join('')}</tr>`;
        }).join('')}</tbody></table></div>
        <div class="cvm-legend"><span class="m-ok">✓ cumple</span><span class="m-warn">⚠ por verificar</span><span class="m-no">✕ no cumple</span><span class="m-na">— no se exige o no está registrado</span><span>Pasa el cursor por una celda para ver el requisito.</span>${none ? '<span>Esta búsqueda no trae requisitos: ejecuta una búsqueda nueva para verlos.</span>' : ''}</div>`;
  }

  // ------------------------------------------------------------- timeline
  function renderTimeline(el, X) {
    if (!X.items.length) { el.innerHTML = EMPTY; return; }
    const rows = X.items.slice().sort((a, b) => (a.dias === null ? 9999 : a.dias) - (b.dias === null ? 9999 : b.dias));
    const hoy = toDate(X.hoy);
    const W = 1000;
    const L = 330;
    const top = 34;
    const rh = 30;
    const H = top + rows.length * rh + 16;
    const t0 = new Date(hoy.getTime() - 20 * DAY);
    const t1 = new Date(hoy.getTime() + 330 * DAY);
    const X0 = d => L + (W - L - 10) * (d - t0) / (t1 - t0);
    let months = '';
    for (let d = new Date(t0.getFullYear(), t0.getMonth() + 1, 1); d < t1; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) {
      const x = X0(d).toFixed(1);
      months += `<line class="grid" x1="${x}" y1="${top - 6}" x2="${x}" y2="${H - 8}"/><text x="${Number(x) + 3}" y="${top - 12}">${d.toLocaleDateString('es-CO', { month: 'short' })}${d.getMonth() === 0 ? ` ${d.getFullYear()}` : ''}</text>`;
    }
    const body = rows.map((c, i) => {
      const y = top + i * rh;
      const name = c.titulo.length > 46 ? `${c.titulo.slice(0, 45)}…` : c.titulo;
      const late = isLate(c, X);
      const end = toDate(c.raw.cierre);
      let bar;
      if (end && c.vigente) {
        const open = toDate(c.raw.apertura);
        const start = new Date(Math.max(t0, open || t0));
        const x0 = X0(start);
        const x1 = Math.max(X0(end), x0 + 4);
        const prep = toDate(c.preparar);
        const marker = prep ? (() => {
          const px = X0(new Date(Math.max(prep, t0))).toFixed(1);
          return `<line class="tl-prep${late ? ' is-late' : ''}" x1="${px}" y1="${y + 3}" x2="${px}" y2="${y + 25}"><title>${late ? 'Ya debió empezar la preparación' : 'Empezar a preparar a más tardar aquí'}</title></line>`;
        })() : '';
        bar = `<rect class="tl-bar" x="${x0.toFixed(1)}" y="${y + 7}" width="${(x1 - x0).toFixed(1)}" height="14" rx="4" opacity="${(0.25 + 0.75 * clamp(c.match, 0, 100) / 100).toFixed(2)}"/>
          ${marker}<text x="${(x1 + 6).toFixed(1)}" y="${y + 18}">${c.match}${late ? ' · tarde' : ''}</text>`;
      } else {
        bar = `<text class="tl-none" x="${(X0(hoy) + 8).toFixed(1)}" y="${y + 18}">${c.vigente ? 'Sin fecha de cierre publicada' : (c.estado === 'pausada' ? 'Pausada' : 'Cerrada')}</text>`;
      }
      return `<g class="tl-row${S.sel === c.id ? ' is-sel' : ''}" data-call="${esc(c.id)}" data-late="${late ? '1' : '0'}"><rect class="tl-bg" x="0" y="${y}" width="${W}" height="${rh}"/>
          <text class="tl-name" x="6" y="${y + 18}">${esc(name)}<title>${esc(c.titulo)}</title></text>${bar}</g>`;
    }).join('');
    const xh = X0(hoy).toFixed(1);
    el.innerHTML = `<div class="cvm-tlscroll"><svg class="cvm-timeline" viewBox="0 0 ${W} ${H}" role="img" aria-label="Línea de tiempo de cierres">
        <g class="axis">${months}</g>${body}
        <line class="today" x1="${xh}" y1="${top - 8}" x2="${xh}" y2="${H - 8}"/><text class="todaylbl" x="${Number(xh) + 4}" y="${H - 10}">hoy</text>
      </svg></div>
      <div class="cvm-legend"><span>Barra = ventana abierta, más intensa con mejor match</span><span>Línea punteada = empezar a preparar a más tardar (según el esfuerzo)</span><span class="m-no">roja = ya es tarde</span></div>`;
  }

  // ------------------------------------------------------------- detail
  function amount(monto) {
    if (typeof window.cvAmount === 'function') return window.cvAmount(monto);
    return typeof monto === 'string' && monto ? monto : 'Monto no indicado';
  }

  function renderDetail(X) {
    const el = S.last.detailEl;
    const c = X.items.find(x => x.id === S.sel);
    el.classList.toggle('is-sheet', !!c);
    document.body.classList.toggle('cvm-has-sheet', !!c);
    if (!c) {
      const best = X.items.filter(x => x.vigente && x.rol !== 'no_elegible').slice().sort((a, b) => b.match - a.match).slice(0, 3);
      el.innerHTML = `<h3 class="cvm-detail__title">Detalle</h3><p class="cvm-muted">Haz clic en una convocatoria para ver por qué encaja, sus requisitos y sus tiempos. Pasa el cursor por un tema o por una raíz del banco LIA para iluminar lo que conecta.</p>
          <h4>Mejores opciones ahora</h4>${best.map(cardHtml).join('') || '<p class="cvm-muted">Sin opciones con los filtros actuales.</p>'}`;
      return;
    }
    const o = c.raw;
    const u = urgency(c);
    const role = ROLES[c.rol];
    const icon = s => (s === 'error' ? '🔴' : s === 'warning' ? '⚠️' : 'ℹ️');
    const bars = c.comp ? `<div class="cvm-bars">${COMPONENTES.map(([key, label, hint]) => {
      const v = clamp(Math.round(num(c.comp[key]) || 0), 0, 100);
      return `<span title="${esc(hint)}">${label}</span><span class="cvm-b" data-componente="${key}" data-valor="${v}"><span style="width:${v}%"></span></span><strong>${v}</strong>`;
    }).join('')}</div>` : '<p class="cvm-muted">Esta búsqueda no trae el desglose del match: el número es la afinidad temática.</p>';
    const tiempos = (() => {
      const parts = [`Apertura: ${esc(fmtDate(o.apertura))} · Cierre: ${esc(fmtDate(o.cierre))}${o.cierre_tipo === 'estimado' ? ' (estimado)' : ''}`];
      if (c.esfuerzo) {
        let line = `Esfuerzo estimado: ${c.esfuerzo} (unos ${ESFUERZO[c.esfuerzo]} días)`;
        if (c.preparar && c.vigente) {
          line += isLate(c, X)
            ? ` · <strong class="cvm-late">ya es tarde: la preparación debió empezar el ${esc(fmtDate(c.preparar))}</strong>`
            : ` · empezar a más tardar el ${esc(fmtDate(c.preparar))}`;
        }
        parts.push(line);
      }
      return parts.join('<br>');
    })();
    const scopePill = `<span class="cvm-pill cvm-pill--accent">${X.alcance === 'banco' ? 'Banco LIA' : 'Proyecto'}</span>`;
    const whyTemas = c.temas.map(t => `<div>${scopePill}<span class="cvm-arrow">→</span>${esc(cap(t.tema))} <span class="cvm-dim">(coincidencia ${Math.round(100 * t.peso)} %)</span></div>`).join('');
    const whyExp = c.exp.map(id => X.exp.find(r => r.id === id) || { id, nombre: id, corto: abbrev(id) })
      .map(r => `<div><span class="cvm-pill cvm-pill--violet">${esc(r.corto)}</span> ${esc(r.nombre)}</div>`).join('');
    const whyHist = c.historial ? '<div><span class="cvm-pill cvm-pill--ok">financiador previo ✓</span> El financiador ya apoyó al laboratorio.</div>' : '';
    const why = whyTemas + whyExp + whyHist || '<div class="cvm-dim">Ningún tema ni experiencia del perfil conectados con esta convocatoria.</div>';
    const aplicantes = list(o.aplicantes).map(a => APLICANTES[a] || String(a)).join(', ');
    const evidencia = list(o.evidencia).filter(e => e && typeof e === 'object').map(e => {
      const url = safeUrl(e.url);
      const label = esc(e.texto || e.url || '');
      return `<li>${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label || esc(url)}</a>` : label}</li>`;
    }).join('');
    const url = safeUrl(o.url);
    el.innerHTML = `
        <button class="btn btn--xs cvm-sheet-close" type="button" data-cvm-clear aria-label="Cerrar detalle">✕ Cerrar</button>
        <h2>${esc(c.titulo)}</h2>
        <div class="cvm-muted">${esc(o.financiador || '')}${o.programa ? ` · ${esc(o.programa)}` : ''}</div>
        <div class="cvm-tags">
          <span class="cvm-pill">${esc(AMBITOS[o.ambito] || o.ambito || '—')}</span><span class="cvm-pill">${esc(IDIOMAS[o.idioma] || o.idioma || '—')}</span>
          <span class="cvm-pill cvm-pill--${role[1]}">${esc(role[0])}</span><span class="cvm-pill cvm-pill--${u.tone}">⏱ ${esc(u.label)}</span>
        </div>
        <div class="cvm-bigscore"><div class="cvm-ring" style="--m:${clamp(c.match, 0, 100)}"><span>${c.match}</span></div>
          <div><strong>Match</strong><div class="cvm-muted cvm-small">con el ${X.alcance === 'banco' ? 'banco LIA' : 'proyecto en formulación'}</div></div></div>
        ${bars}
        ${o.aviso ? `<div class="cvm-notice">${esc(o.aviso)}</div>` : ''}
        <h4>Alertas</h4>
        ${c.alertas.length ? `<ul class="cvm-alerts">${c.alertas.map(a => `<li data-severidad="${esc(a.severidad)}"><span>${icon(a.severidad)}</span><span>${esc(a.texto)}</span></li>`).join('')}</ul>` : '<p class="cvm-muted">Sin alertas.</p>'}
        <h4>Tiempos</h4>
        <div class="cvm-small">${tiempos}</div>
        <h4>Por qué encaja</h4>
        <div class="cvm-why">${why}</div>
        ${o.resumen ? `<h4>Resumen</h4><p class="cvm-small">${esc(o.resumen)}</p>` : ''}
        <div class="cvm-small cvm-muted">Monto: ${esc(amount(o.monto))}${aplicantes ? ` · Aplicantes: ${esc(aplicantes)}` : ''}</div>
        ${evidencia ? `<h4>Evidencia</h4><ul class="cvm-evidence">${evidencia}</ul>` : ''}
        <div class="cvm-actions">
          <button class="btn btn--sm btn--primary" type="button" data-iniciar="${esc(c.id)}" onclick="startOpportunity(this.getAttribute('data-iniciar'))">🚀 Iniciar propuesta con esta</button>
          ${url ? `<a class="btn btn--sm" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Abrir la convocatoria</a>` : ''}
          <button class="btn btn--sm" type="button" data-cvm-clear>Cerrar</button>
        </div>`;
  }

  // ------------------------------------------------------------- highlight
  function applyHighlight(X) {
    if (!S.last) return;
    const view = S.last.viewEl;
    const hl = lit(X);
    // Hover dims hard; a selection alone dims softly, so the rest still reads as clickable.
    view.style.setProperty('--cvm-dim', S.focus ? '0.18' : '0.42');
    const off = (set, id) => !!hl && !set.has(id);
    view.querySelectorAll('.cvm-card[data-call]').forEach(el => el.classList.toggle('is-dim', off(hl ? hl.calls : null, el.dataset.call)));
    view.querySelectorAll('.cvm-group[data-ids]').forEach(g => {
      g.classList.toggle('is-dim', !!hl && !g.dataset.ids.split(' ').some(i => hl.calls.has(i)));
    });
    view.querySelectorAll('.cvm-node--theme').forEach(el => {
      el.classList.toggle('is-dim', off(hl ? hl.themes : null, el.dataset.theme));
      el.classList.toggle('is-hl', !!hl && hl.themes.has(el.dataset.theme));
    });
    view.querySelectorAll('.cvm-node--root').forEach(el => {
      el.classList.toggle('is-dim', off(hl ? hl.roots : null, el.dataset.root));
      el.classList.toggle('is-hl', !!hl && hl.roots.has(el.dataset.root));
    });
    drawTreeLinks(view, X, hl);
    const svg = view.querySelector('svg.cvm-const');
    if (!svg || !S.cpos) return;
    svg.querySelectorAll('g.n').forEach(g => {
      g.classList.toggle('is-dim', off(hl ? hl.calls : null, g.dataset.call));
      g.classList.toggle('is-hl', !!hl && hl.calls.has(g.dataset.call));
    });
    svg.querySelectorAll('g.root').forEach(g => g.classList.toggle('is-dim', off(hl ? hl.roots : null, g.dataset.root)));
    svg.querySelectorAll('.seclbl').forEach(t => t.classList.toggle('is-dim', !!hl && !t.dataset.ids.split(' ').some(i => hl.calls.has(i))));
    let edges = '';
    if (hl) {
      const { cx, cy, nodes, rootPos, sectors } = S.cpos;
      nodes.filter(n => hl.calls.has(n.c.id)).forEach(n => {
        rootPos.filter(rp => n.c.exp.includes(rp.r.id) && hl.roots.has(rp.r.id)).forEach(rp => {
          const mx = (n.x + rp.px) / 2 + (cy - n.y) * 0.12;
          const my = (n.y + rp.py) / 2 + (n.x - cx) * 0.12;
          edges += `<path class="edge" d="M${n.x.toFixed(1)},${n.y.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${rp.px.toFixed(1)},${rp.py.toFixed(1)}"/>`;
        });
      });
      if (hl.f.kind === 'call' && X.agrupar === 'tema') {
        const n = nodes.find(m => m.c.id === hl.f.id);
        if (n) {
          sectors.filter(s => n.c.temas.some(t => t.key === s.g.k) && s.g.k !== groupOf(n.c, X)).forEach(s => {
            const am = (s.a0 + s.a1) / 2;
            edges += `<path class="edge edge--theme" d="M${n.x.toFixed(1)},${n.y.toFixed(1)} Q${cx},${cy} ${(cx + 372 * Math.cos(am)).toFixed(1)},${(cy + 372 * Math.sin(am)).toFixed(1)}"/>`;
          });
        }
      }
    }
    const layer = svg.querySelector('g.cvm-edges');
    if (layer) layer.innerHTML = edges;
  }

  function setFocus(f) {
    if (JSON.stringify(f) === JSON.stringify(S.focus)) return;
    S.focus = f;
    if (S.X) applyHighlight(S.X);
  }

  function tipEl() {
    let tip = document.getElementById('cvmTip');
    if (!tip) {
      tip = document.createElement('div');
      tip.id = 'cvmTip';
      tip.className = 'cvm-tip';
      tip.setAttribute('role', 'tooltip');
      document.body.appendChild(tip);
    }
    return tip;
  }
  function showTip(e, c) {
    const tip = tipEl();
    const u = urgency(c);
    tip.innerHTML = `<strong>${esc(c.titulo)}</strong>${esc(c.raw.financiador || '')}<br>Match ${c.match} · ${esc(u.label)} · ${esc(ROLES[c.rol][0])}${c.temas.length ? `<br><span class="cvm-muted">${c.temas.map(t => esc(cap(t.tema))).join(' · ')}</span>` : ''}`;
    tip.style.display = 'block';
    tip.style.left = `${Math.max(4, Math.min(e.clientX + 14, window.innerWidth - 300))}px`;
    tip.style.top = `${Math.max(4, Math.min(e.clientY + 14, window.innerHeight - 120))}px`;
  }
  function hideTip() {
    const tip = document.getElementById('cvmTip');
    if (tip) tip.style.display = 'none';
  }

  // ------------------------------------------------------------- wiring
  const paneActive = () => {
    const pane = document.getElementById('pane-convocatorias');
    return !pane || pane.classList.contains('active');
  };
  const inMap = el => !!(S.last && el && (S.last.viewEl.contains(el) || S.last.detailEl.contains(el)));

  function onClick(e) {
    const t = e.target;
    if (!t || !t.closest || !inMap(t)) return;
    const exp = t.closest('[data-cvm-expand]');
    if (exp) {
      const k = exp.getAttribute('data-cvm-expand');
      if (S.expanded.has(k)) S.expanded.delete(k); else S.expanded.add(k);
      rerender();
      return;
    }
    const z = t.closest('[data-cvm-zoom]');
    if (z) { zoom(z.getAttribute('data-cvm-zoom')); return; }
    if (t.closest('[data-cvm-clear]')) { select(null); return; }
    if (t.closest('[data-iniciar], a')) return;
    const call = t.closest('[data-call]');
    if (call) select(call.dataset.call === S.sel ? null : call.dataset.call);
  }

  function onOver(e) {
    if (!S.X || !S.last || !paneActive()) return;
    const t = e.target && e.target.closest && e.target.closest('[data-call], [data-theme], [data-root]');
    if (!t || !S.last.viewEl.contains(t)) { if (S.focus) setFocus(null); hideTip(); return; }
    if (t.dataset.call) {
      setFocus({ kind: 'call', id: t.dataset.call });
      if (t.tagName.toLowerCase() === 'g') {
        const c = S.X.items.find(x => x.id === t.dataset.call);
        if (c) showTip(e, c);
      }
    } else if (t.dataset.theme) setFocus({ kind: 'theme', id: t.dataset.theme });
    else if (t.dataset.root) setFocus({ kind: 'root', id: t.dataset.root });
  }

  function onMove(e) {
    if (!S.X || !S.last) return;
    const g = e.target && e.target.closest && e.target.closest('g[data-call]');
    if (g && S.last.viewEl.contains(g)) {
      const c = S.X.items.find(x => x.id === g.dataset.call);
      if (c) showTip(e, c);
    }
  }

  function onKey(e) {
    if (!S.last || !paneActive()) return;
    if (e.key === 'Escape' && (S.sel || S.focus)) { select(null); return; }
    if (e.key === 'Enter') {
      const a = document.activeElement;
      const g = a && a.closest && a.closest('g[data-call]');
      if (g && S.last.viewEl.contains(g)) select(g.dataset.call);
    }
  }

  function wire() {
    if (S.wired) return;
    S.wired = true;
    document.addEventListener('click', onClick);
    document.addEventListener('pointerover', onOver);
    document.addEventListener('pointermove', onMove);
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', () => {
      clearTimeout(S.resizeTimer);
      S.resizeTimer = setTimeout(() => {
        if (S.last && paneActive() && ['arbol', 'constelacion', 'lado'].includes(S.last.ctx.view)) rerender();
      }, 150);
    });
  }

  // ------------------------------------------------------------- public API
  function render(viewEl, detailEl, rawItems, ctx) {
    if (!viewEl || !detailEl) return;
    wire();
    S.last = { viewEl, detailEl, rawItems: Array.isArray(rawItems) ? rawItems : [], ctx: ctx || {} };
    const X = context(S.last.ctx, S.last.rawItems);
    S.X = X;
    if (S.sel && !X.items.some(c => c.id === S.sel)) S.sel = null;
    S.focus = null;
    S.cpos = null;
    hideTip();
    if (X.view === 'constelacion') renderConstellation(viewEl, X);
    else if (X.view === 'lado') {
      viewEl.innerHTML = `<div class="cvm-side"><div><div class="cvm-view-title">🌳 Árbol de oportunidades</div><div class="cvm-side__tree"></div></div>
          <div><div class="cvm-view-title">✦ Constelación de afinidad</div><div class="cvm-side__const"></div></div></div>`;
      renderTree(viewEl.querySelector('.cvm-side__tree'), X);
      renderConstellation(viewEl.querySelector('.cvm-side__const'), X);
    } else if (X.view === 'requisitos') renderMatrix(viewEl, X);
    else if (X.view === 'tiempo') renderTimeline(viewEl, X);
    else renderTree(viewEl, X);
    renderDetail(X);
    applyHighlight(X);
  }

  function rerender() {
    if (S.last) render(S.last.viewEl, S.last.detailEl, S.last.rawItems, S.last.ctx);
  }

  // Selecting toggles classes and repaints only the detail: the view's
  // elements (and the constellation's zoom and pan) stay as they are.
  function select(id) {
    S.sel = id || null;
    S.focus = null;
    hideTip();
    if (!S.last || !S.X) return;
    S.last.viewEl.querySelectorAll('[data-call]').forEach(el => el.classList.toggle('is-sel', el.dataset.call === S.sel));
    renderDetail(S.X);
    applyHighlight(S.X);
  }

  function reset() {
    S.sel = null;
    S.focus = null;
    S.expanded.clear();
    S.cv = null;
  }

  function closeSheet() {
    document.body.classList.remove('cvm-has-sheet');
    if (S.last) S.last.detailEl.classList.remove('is-sheet');
    hideTip();
  }

  window.cvMap = { render, select, reset, closeSheet };
})();
