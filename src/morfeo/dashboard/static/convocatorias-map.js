// «Convocatorias» views: opportunity tree, affinity constellation, side by
// side, requirements matrix, timeline and the detail panel (bottom sheet under
// 1080 px). The constellation is the SOTA 3D viewer: an iframe of
// /api/convocatorias/atlas (scripts/render_atlas.py, profile "convocatorias",
// scene from scripts/convocatorias.py `constelacion`) with the panel's
// grouping and filters in its query; a click on any node opens its card inside
// the frame, and the frame's «Iniciar propuesta con esta» message is honored
// only from that frame, from this origin and for a call of the view. Port of the validated prototype (prototipos/convocatorias) driven
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
// Hover and selection only toggle classes and redraw the tree's link layer:
// the elements under the pointer are never replaced, and a repaint with the
// same query keeps the loaded constellation frame.
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
    sel: null, focus: null, expanded: new Set(),
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
  // The SOTA 3D viewer in a frame. Its query carries the scope, the grouping,
  // the calls the filters left (only when they left out some) and a signature
  // of the view, so a new search reloads it and a repaint does not.
  const SLUG = /^[a-z0-9-]+$/;
  function signature(value) {
    const text = JSON.stringify(value) || '';
    let h = 5381;
    for (let i = 0; i < text.length; i++) h = ((h * 33) ^ text.charCodeAt(i)) >>> 0;
    return h.toString(36);
  }
  function atlasUrl(X) {
    const q = new URLSearchParams({ alcance: X.alcance, agrupar: X.agrupar });
    if (X.items.length < X.total) q.set('ids', X.items.map(c => c.id).filter(id => SLUG.test(id)).join(','));
    q.set('v', signature(X.v));
    return `/api/convocatorias/atlas?${q.toString()}`;
  }

  function renderConstellation(el, X) {
    if (!X.items.length) { el.innerHTML = EMPTY; return; }
    const src = atlasUrl(X);
    const current = el.querySelector('iframe.cvm-atlas');
    if (current && current.getAttribute('src') === src) return;
    el.innerHTML = `<div class="cvm-constwrap"><iframe class="cvm-atlas" loading="lazy" title="Constelación de convocatorias" src="${esc(src)}"></iframe></div>`;
    const frame = el.querySelector('iframe.cvm-atlas');
    frame.addEventListener('load', () => { if (typeof window.syncOpportunitiesAtlasPause === 'function') window.syncOpportunitiesAtlasPause(); });
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
  }

  function setFocus(f) {
    if (JSON.stringify(f) === JSON.stringify(S.focus)) return;
    S.focus = f;
    if (S.X) applyHighlight(S.X);
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
    if (t.closest('[data-cvm-clear]')) { select(null); return; }
    if (t.closest('[data-iniciar], a')) return;
    const call = t.closest('[data-call]');
    if (call) select(call.dataset.call === S.sel ? null : call.dataset.call);
  }

  function onOver(e) {
    if (!S.X || !S.last || !paneActive()) return;
    const t = e.target && e.target.closest && e.target.closest('[data-call], [data-theme], [data-root]');
    if (!t || !S.last.viewEl.contains(t)) { if (S.focus) setFocus(null); return; }
    if (t.dataset.call) setFocus({ kind: 'call', id: t.dataset.call });
    else if (t.dataset.theme) setFocus({ kind: 'theme', id: t.dataset.theme });
    else if (t.dataset.root) setFocus({ kind: 'root', id: t.dataset.root });
  }

  function onKey(e) {
    if (!S.last || !paneActive()) return;
    if (e.key === 'Escape' && (S.sel || S.focus)) select(null);
  }

  // «Iniciar propuesta con esta» inside the constellation frame: the frame only
  // names a call; it counts when it comes from that frame, from this origin and
  // names a call of the view, and then runs the page's own start flow.
  function onMessage(e) {
    const data = e.data;
    if (!data || typeof data !== 'object' || data.type !== 'convocatoria-iniciar') return;
    if (e.origin !== window.location.origin || !S.last || !S.X) return;
    const frames = Array.from(S.last.viewEl.querySelectorAll('iframe.cvm-atlas'));
    if (!frames.some(f => f.contentWindow && f.contentWindow === e.source)) return;
    const id = typeof data.id === 'string' ? data.id : '';
    if (!id || !S.X.items.some(c => c.id === id)) return;
    if (typeof window.startOpportunity === 'function') window.startOpportunity(id);
  }

  function wire() {
    if (S.wired) return;
    S.wired = true;
    document.addEventListener('click', onClick);
    document.addEventListener('pointerover', onOver);
    document.addEventListener('keydown', onKey);
    window.addEventListener('message', onMessage);
    window.addEventListener('resize', () => {
      clearTimeout(S.resizeTimer);
      S.resizeTimer = setTimeout(() => {
        if (S.last && paneActive() && ['arbol', 'lado'].includes(S.last.ctx.view)) rerender();
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
    if (X.view === 'constelacion') {
      if (!viewEl.querySelector(':scope > .cvm-constwrap')) viewEl.innerHTML = '';
      renderConstellation(viewEl, X);
    } else if (X.view === 'lado') {
      // Keep the layout (and its loaded frame) when it is already there.
      if (!viewEl.querySelector(':scope > .cvm-side')) {
        viewEl.innerHTML = `<div class="cvm-side"><div><div class="cvm-view-title">🌳 Árbol de oportunidades</div><div class="cvm-side__tree"></div></div>
          <div><div class="cvm-view-title">✦ Constelación de afinidad</div><div class="cvm-side__const"></div></div></div>`;
      }
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
  // elements (and the constellation frame) stay as they are.
  function select(id) {
    S.sel = id || null;
    S.focus = null;
    if (!S.last || !S.X) return;
    S.last.viewEl.querySelectorAll('[data-call]').forEach(el => el.classList.toggle('is-sel', el.dataset.call === S.sel));
    renderDetail(S.X);
    applyHighlight(S.X);
  }

  function reset() {
    S.sel = null;
    S.focus = null;
    S.expanded.clear();
  }

  function closeSheet() {
    document.body.classList.remove('cvm-has-sheet');
    if (S.last) S.last.detailEl.classList.remove('is-sheet');
  }

  window.cvMap = { render, select, reset, closeSheet };
})();
