/**
 * novedad-panel.js: the «Novedad e hipótesis» tab, the novelty pillars and the
 * hypotheses of the proposal with their experiments, actions, implementations,
 * interventions or transfers (papersmith model-panel noveltyTree pattern), and
 * the project matrix that follows the value chain.
 *
 * The panel reads GET /api/novedad (artefactos/novedad/novedad.json recorded by
 * scripts/novedad.py, the matrix that script derives and its validation). It
 * fills four slots of its root, each marked data-nov-slot:
 *   meta    run and date of the artifact
 *   head    intro, «Generar / actualizar», the pending banner and the errors
 *   tree    a strip with the central problem, each direct cause and its
 *           specific objective; the pillars above and the hypotheses below,
 *           each hypothesis with its experiments or actions as chips badged by
 *           type; SVG arrows objective → pillar and pillar → hypothesis drawn
 *           from the boxes' real edges, hover focus, and text lines that carry
 *           the links when the grid falls to one column
 *   matrix  header, stat cards, search, type filter and one row per specific
 *           objective (cause → objective → pillars → hypotheses → experiments
 *           or actions → products → expected result and indicator → effects),
 *           each row with expandable details
 *   judge   the stage judge (judge-avance.js) with etapa 'novedad'
 * «Generar / actualizar» asks POST /api/novedad/run for the slash command and
 * types it into the embedded terminal; the panel then stays pending until a
 * newer artifact arrives through polling. Every value is escaped.
 *
 * Public surface (window.NovedadPanel):
 *   mount(root, { interval, fetch, send }) -> controller
 *     interval  polling period in ms while started; default 5000
 *     fetch     fetch implementation; default window.fetch at call time
 *     send      async (prompt) => boolean; default window.sendTerminalPrompt
 *   controller: refresh(), run(), retry(), start(), stop(), polling, data, judge
 *   renderTree(novedad), renderMatrix(matriz, state) -> HTML (pure)
 *   filterRows(matriz, { query, tipo }) -> rows (pure)
 *   drawArrows(tree)  lays out the arrows of one [data-novelty-tree]
 *   TIPOS             [[id, label], ...] experiment and action types
 */
(function () {
  'use strict';

  const TIPOS = [
    ['experimento', 'Experimento'],
    ['intervencion', 'Intervención'],
    ['transferencia', 'Transferencia'],
    ['implementacion', 'Implementación'],
    ['accion', 'Acción'],
  ];
  const TIPO_LABEL = Object.fromEntries(TIPOS);
  const TIPO_PLURAL = {
    experimento: ['experimento', 'experimentos'],
    intervencion: ['intervención', 'intervenciones'],
    transferencia: ['transferencia', 'transferencias'],
    implementacion: ['implementación', 'implementaciones'],
    accion: ['acción', 'acciones'],
  };
  const TONES = ['#38bdf8', '#a78bfa', '#34d399', '#f59e0b', '#f472b6', '#fb7185'];
  const FOLD_TREE = 'novedad-pilares';
  const STYLE_ID = 'novedad-panel-styles';

  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);
  const list = (v) => (Array.isArray(v) ? v : []);
  const dicts = (v) => list(v).filter((x) => x && typeof x === 'object' && !Array.isArray(x));
  const plain = (v) => String(v == null ? '' : v).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const ids = (v) => list(v).filter((x) => typeof x === 'string');

  // --- Novelty tree -----------------------------------------------------------

  function graph(nov) {
    const pillars = dicts(nov.pilares);
    const hyps = dicts(nov.hipotesis);
    const objectives = dicts(nov.objetivos);
    const pids = pillars.map((p) => p.id);
    const oeIds = objectives.map((o) => o.id);
    const tone = (pid) => TONES[Math.max(0, pids.indexOf(pid)) % TONES.length];
    const links = [];
    pillars.forEach((p) => ids(p.objetivos).filter((oe) => oeIds.includes(oe))
      .forEach((oe) => links.push({ from: oe, to: p.id, kind: 'objetivo' })));
    hyps.forEach((h) => ids(h.pilares).filter((pid) => pids.includes(pid))
      .forEach((pid) => links.push({ from: pid, to: h.id, kind: 'pilar', tone: tone(pid) })));
    // Focus also follows the links that carry no arrow: cause ↔ objective and
    // hypothesis ↔ objective.
    const near = new Map();
    const add = (a, b) => {
      if (!near.has(a)) near.set(a, new Set());
      if (!near.has(b)) near.set(b, new Set());
      near.get(a).add(b);
      near.get(b).add(a);
    };
    links.forEach((l) => add(l.from, l.to));
    objectives.forEach((o) => { if (o.causa) add(o.causa, o.id); });
    hyps.forEach((h) => ids(h.objetivos).forEach((oe) => add(oe, h.id)));
    return { pillars, hyps, objectives, pids, links, near, tone };
  }

  function kind(label, id, extra) {
    return `<div class="nov-kind"><span>${esc(label)} · ${esc(id)}</span>${extra || ''}</div>`;
  }

  function line(label, values) {
    return values.length ? `<small class="nov-line">${esc(label)}: ${esc(values.join(', '))}</small>` : '';
  }

  function chip(e) {
    const tipo = TIPO_LABEL[e.tipo] ? e.tipo : 'accion';
    return `<span class="nov-chip nov-chip--${tipo}" title="${esc(e.descripcion || '')}"><b>${esc(TIPO_LABEL[tipo])}</b> ${esc(e.id)} · ${esc(e.titulo)}</span>`;
  }

  function renderTree(nov) {
    const data = nov && typeof nov === 'object' ? nov : {};
    const g = graph(data);
    const causes = new Map(dicts(data.causas).map((c) => [c.id, c]));
    const chains = g.objectives.map((o) => {
      const c = causes.get(o.causa) || {};
      return `<div class="nov-chain">
          <div class="nov-node nov-node--cause" data-tree-node="${esc(o.causa || '')}">${kind('Causa directa', o.causa || '?')}<p>${esc(c.texto)}</p></div>
          <span class="nov-chain__arrow" aria-hidden="true">↓</span>
          <div class="nov-node nov-node--objective" data-tree-node="${esc(o.id)}">${kind('Objetivo específico', o.id)}<p>${esc(o.texto)}</p></div>
        </div>`;
    }).join('');
    const pillarNodes = g.pillars.map((p) => {
      const supports = g.links.filter((l) => l.kind === 'pilar' && l.from === p.id).map((l) => l.to);
      return `<div class="nov-node nov-node--pillar" data-tree-node="${esc(p.id)}" style="--tone: ${g.tone(p.id)};">
          ${kind('Pilar', p.id)}
          <p class="nov-name">${esc(p.nombre)}</p>
          <p class="nov-text">${esc(p.resumen)}</p>
          ${line('Objetivos', ids(p.objetivos))}
          ${line('Sostiene', supports)}
        </div>`;
    }).join('');
    const hypNodes = g.hyps.map((h) => {
      const from = ids(h.pilares).filter((pid) => g.pids.includes(pid));
      const exps = dicts(h.experimentos);
      return `<div class="nov-node nov-node--hypothesis" data-tree-node="${esc(h.id)}">
          ${kind('Hipótesis', h.id)}
          <p class="nov-name">${esc(h.titulo)}</p>
          <p class="nov-text">${esc(h.enunciado)}</p>
          ${line('Objetivos', ids(h.objetivos))}
          ${line('Apoyado por', from)}
          ${exps.length ? `<div class="nov-chips">${exps.map(chip).join('')}</div>` : ''}
        </div>`;
    }).join('');
    const markerTones = [...new Set(g.links.map((l) => l.tone || 'var(--text-dim)'))];
    const markerId = (tone) => `novArrow${markerTones.indexOf(tone)}`;
    const markers = markerTones.map((tone) => `<marker id="${markerId(tone)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" style="fill: ${tone};"></path></marker>`).join('');
    const arrows = g.links.map((l) => {
      const tone = l.tone || 'var(--text-dim)';
      return `<path class="nov-arrow nov-arrow--${l.kind}" data-from="${esc(l.from)}" data-to="${esc(l.to)}" style="stroke: ${tone};" marker-end="url(#${markerId(tone)})"></path>`;
    }).join('');
    return `<div class="nov-tree" data-novelty-tree>
        <p class="nov-legend">Cada causa directa del árbol de problemas da un objetivo específico; los pilares de novedad atienden esos objetivos y sostienen las hipótesis, y cada hipótesis se pone a prueba con experimentos, acciones, implementaciones, intervenciones o transferencias. Señala una caja para resaltar sus relaciones.</p>
        <div class="nov-level nov-level--chain">
          <h5>Problema y objetivos</h5>
          <div class="nov-node nov-node--central" data-tree-node="problema">${kind('Problema central', 'tronco')}<p>${esc(data.problema_central)}</p></div>
          <div class="nov-grid nov-grid--chains">${chains}</div>
        </div>
        <div class="nov-level"><h5>Pilares de novedad</h5><div class="nov-grid">${pillarNodes}</div></div>
        <div class="nov-level"><h5>Hipótesis con sus experimentos y acciones</h5><div class="nov-grid">${hypNodes}</div></div>
        <svg class="nov-arrows" aria-hidden="true"><defs>${markers}</defs>${arrows}</svg>
      </div>`;
  }

  // Each arrow leaves the bottom edge of its source and lands on the top edge
  // of its target; arrows sharing an edge spread apart so none hides another.
  function drawArrows(tree) {
    if (!tree || !tree.querySelector) return;
    const svg = tree.querySelector('.nov-arrows');
    const box = tree.getBoundingClientRect();
    if (!svg || !box.width) return;
    const rects = (sel) => Array.from(tree.querySelectorAll(sel), (n) => n.getBoundingClientRect());
    let column = rects('.nov-node--pillar');
    if (column.length < 2) column = rects('.nov-node--hypothesis');
    const stacked = column.length > 1 && column.every((r) => Math.abs(r.left - column[0].left) < 1);
    tree.classList.toggle('is-stacked', stacked);
    if (stacked) return;
    svg.setAttribute('viewBox', `0 0 ${box.width} ${box.height}`);
    const nodes = new Map(Array.from(tree.querySelectorAll('[data-tree-node]'),
      (n) => [n.getAttribute('data-tree-node'), n.getBoundingClientRect()]));
    const paths = Array.from(svg.querySelectorAll('.nov-arrow'));
    const spread = (key) => {
      const group = {};
      paths.forEach((p) => { (group[p.getAttribute(key)] = group[p.getAttribute(key)] || []).push(p); });
      return (p) => {
        const peers = group[p.getAttribute(key)];
        return (peers.indexOf(p) - (peers.length - 1) / 2) * 12;
      };
    };
    const out = spread('data-from');
    const into = spread('data-to');
    paths.forEach((p) => {
      const a = nodes.get(p.getAttribute('data-from'));
      const b = nodes.get(p.getAttribute('data-to'));
      if (!a || !b) return;
      const x1 = a.left + a.width / 2 - box.left + out(p);
      const y1 = a.top + a.height - box.top;
      const x2 = b.left + b.width / 2 - box.left + into(p);
      const y2 = b.top - box.top - 2;
      const bend = Math.max(18, (y2 - y1) / 2);
      p.setAttribute('d', `M${x1},${y1} C${x1},${y1 + bend} ${x2},${y2 - bend} ${x2},${y2}`);
    });
  }

  function wireFocus(tree, near) {
    const clear = () => {
      tree.classList.remove('has-focus');
      tree.querySelectorAll('.is-focus').forEach((n) => n.classList.remove('is-focus'));
    };
    tree.addEventListener('mouseover', (event) => {
      const node = event.target && event.target.closest && event.target.closest('[data-tree-node]');
      const id = node ? node.getAttribute('data-tree-node') : '';
      if (!id || !near.has(id)) { clear(); return; }
      const focus = new Set([id, ...near.get(id)]);
      tree.classList.add('has-focus');
      tree.querySelectorAll('[data-tree-node]').forEach((n) => n.classList.toggle('is-focus', focus.has(n.getAttribute('data-tree-node'))));
      tree.querySelectorAll('.nov-arrow').forEach((p) => p.classList.toggle('is-focus',
        focus.has(p.getAttribute('data-from')) && focus.has(p.getAttribute('data-to'))
        && (p.getAttribute('data-from') === id || p.getAttribute('data-to') === id)));
    });
    tree.addEventListener('mouseleave', clear);
  }

  // --- Matrix -----------------------------------------------------------------

  function haystack(row) {
    const parts = [row.objetivo && row.objetivo.id, row.objetivo && row.objetivo.texto, row.causa && row.causa.id,
      row.causa && row.causa.texto];
    dicts(row.pilares).forEach((p) => parts.push(p.id, p.nombre, p.resumen));
    dicts(row.hipotesis).forEach((h) => parts.push(h.id, h.titulo, h.enunciado));
    dicts(row.experimentos).forEach((e) => parts.push(e.id, TIPO_LABEL[e.tipo], e.titulo, e.descripcion, e.metrica,
      e.producto, e.resultado_esperado));
    parts.push(...list(row.productos), ...list(row.indicadores), ...list(row.resultados));
    return plain(parts.filter(Boolean).join(' '));
  }

  function filterRows(matriz, state) {
    const query = plain((state && state.query) || '').trim();
    const tipo = (state && state.tipo) || '';
    return dicts(matriz && matriz.filas).map((row) => {
      if (!tipo) return row;
      const experimentos = dicts(row.experimentos).filter((e) => e.tipo === tipo);
      return experimentos.length ? { ...row, experimentos } : null;
    }).filter((row) => row && (!query || query.split(/\s+/).every((word) => haystack(row).includes(word))));
  }

  const idChips = (items, label) => items.map((x) => `<span class="nov-id" title="${esc(label(x))}">${esc(x.id)}</span> ${esc(label(x))}`).join('<br>');

  function rowHtml(row, effects, expanded) {
    const oe = (row.objetivo && row.objetivo.id) || '';
    const exps = dicts(row.experimentos);
    const effectIds = ids(row.efectos);
    const cells = `
        <td data-col="causa" data-label="Causa directa"><span class="nov-id">${esc(row.causa && row.causa.id)}</span> ${esc(row.causa && row.causa.texto)}</td>
        <td data-col="objetivo" data-label="Objetivo específico"><span class="nov-id">${esc(oe)}</span> ${esc(row.objetivo && row.objetivo.texto)}</td>
        <td data-col="pilares" data-label="Pilares">${idChips(dicts(row.pilares), (p) => p.nombre || '')}</td>
        <td data-col="hipotesis" data-label="Hipótesis">${idChips(dicts(row.hipotesis), (h) => h.titulo || '')}</td>
        <td data-col="experimentos" data-label="Experimentos y acciones"><div class="nov-chips">${exps.map(chip).join('')}</div></td>
        <td data-col="productos" data-label="Productos">${list(row.productos).map(esc).join('<br>')}</td>
        <td data-col="resultado" data-label="Resultado esperado e indicador">${exps.map((e) => `<span class="nov-id">${esc(e.id)}</span> ${esc(e.resultado_esperado)} <small class="nov-indicator">Indicador: ${esc(e.metrica)}</small>`).join('<br>')}</td>
        <td data-col="efecto" data-label="Efecto o impacto">${effectIds.map((id) => `<span class="nov-id" title="${esc((effects.get(id) || {}).texto || '')}">${esc(id)}</span>`).join(' ')}</td>
        <td data-col="detalle" data-label=""><button class="btn btn--sm nov-expand" type="button" aria-expanded="${expanded ? 'true' : 'false'}">${expanded ? 'Ocultar ▴' : 'Detalle ▾'}</button></td>`;
    const detail = `
        <div class="nov-detail">
          <p><strong>Causa directa ${esc(row.causa && row.causa.id)}:</strong> ${esc(row.causa && row.causa.texto)}</p>
          ${dicts(row.pilares).map((p) => `<p><strong>Pilar ${esc(p.id)}, ${esc(p.nombre)}:</strong> ${esc(p.resumen)}</p>`).join('')}
          ${dicts(row.hipotesis).map((h) => `<p><strong>Hipótesis ${esc(h.id)}, ${esc(h.titulo)}:</strong> ${esc(h.enunciado)}</p>`).join('')}
          ${exps.length ? `<ul class="nov-detail__exps">${exps.map((e) => `<li>${chip(e)} <span class="nov-muted">(${esc(e.hipotesis)})</span><br>${esc(e.descripcion)}<br><small>Indicador: ${esc(e.metrica)} · Producto: ${esc(e.producto)} · Resultado esperado: ${esc(e.resultado_esperado)}</small></li>`).join('')}</ul>` : ''}
          ${effectIds.length ? `<p><strong>Efectos:</strong></p><ul>${effectIds.map((id) => `<li><span class="nov-id">${esc(id)}</span> ${esc((effects.get(id) || {}).texto || '')}</li>`).join('')}</ul>` : ''}
        </div>`;
    return `<tr class="nov-row" data-oe="${esc(oe)}">${cells}</tr>
      <tr class="nov-row-detail" data-oe="${esc(oe)}"${expanded ? '' : ' hidden'}><td colspan="9">${detail}</td></tr>`;
  }

  function tbodyHtml(matriz, state) {
    const effects = new Map(dicts(matriz && matriz.efectos).map((e) => [e.id, e]));
    const rows = filterRows(matriz, state);
    if (!rows.length) return '<tr><td colspan="9" class="nov-muted">Ningún objetivo específico coincide con la búsqueda o el filtro.</td></tr>';
    return rows.map((row) => rowHtml(row, effects, state.expanded.has(row.objetivo && row.objetivo.id))).join('');
  }

  function countText(matriz, state) {
    const total = dicts(matriz && matriz.filas).length;
    return `${filterRows(matriz, state).length} de ${total} objetivos específicos`;
  }

  function stat(key, value, label, extra) {
    return `<div class="matrix-stat-card nov-stat" data-stat="${key}"><span class="matrix-stat-val nov-stat__val">${esc(value)}</span><span class="matrix-stat-lbl">${esc(label)}</span>${extra || ''}</div>`;
  }

  function renderMatrix(matriz, state) {
    const st = state || { query: '', tipo: '', expanded: new Set() };
    if (!st.expanded) st.expanded = new Set();
    const m = matriz && typeof matriz === 'object' ? matriz : {};
    const t = m.totales || {};
    const porTipo = t.por_tipo || {};
    const breakdown = TIPOS.filter(([id]) => Number(porTipo[id]) > 0)
      .map(([id]) => `${porTipo[id]} ${TIPO_PLURAL[id][Number(porTipo[id]) === 1 ? 0 : 1]}`).join(' · ');
    const head = [['Problema central', m.problema_central], ['Objetivo general', m.objetivo_general],
      ['Efecto final', m.efecto_final]].filter(([, v]) => v)
      .map(([k, v]) => `<div><span class="nov-k">${esc(k)}</span><p>${esc(v)}</p></div>`).join('');
    const options = TIPOS.map(([id, label]) => `<option value="${id}"${st.tipo === id ? ' selected' : ''}>${esc(label)}</option>`).join('');
    const fuente = m.fuente_efectos === 'arbol' ? 'Los efectos vienen del árbol de problemas.'
      : m.fuente_efectos === 'novedad' ? 'Los efectos vienen del artefacto de novedad: el árbol de problemas aún no los tiene.'
        : 'Todavía no hay efectos: aparecen cuando el árbol de problemas los tenga.';
    return `<div class="nov-matrix">
        <p class="nov-legend">La matriz resume el proyecto hasta este punto con la lógica de la cadena de valor: cada causa directa da un objetivo específico, que se desagrega en pilares de novedad, hipótesis y experimentos o acciones con su producto, su resultado esperado y su indicador, y apunta a los efectos del árbol de problemas.</p>
        <div class="nov-matrix__head">${head}</div>
        <div class="matrix-stats-grid nov-stats">
          ${stat('objetivos', t.objetivos || 0, 'Objetivos específicos')}
          ${stat('pilares', t.pilares || 0, 'Pilares de novedad')}
          ${stat('hipotesis', t.hipotesis || 0, 'Hipótesis')}
          ${stat('experimentos', t.experimentos || 0, 'Experimentos y acciones', breakdown ? `<small class="nov-muted">${esc(breakdown)}</small>` : '')}
        </div>
        <div class="matrix-toolbar nov-toolbar">
          <label class="matrix-search-box nov-search"><span class="matrix-search-icon" aria-hidden="true">🔍</span>
            <input type="search" class="matrix-search-input nov-search__input" value="${esc(st.query)}" placeholder="Buscar en causas, objetivos, pilares, hipótesis o productos" aria-label="Buscar en la matriz"></label>
          <div class="matrix-filters">
            <select class="matrix-select nov-type" aria-label="Filtrar por tipo"><option value="">Todos los tipos</option>${options}</select>
            <button class="btn btn--sm nov-clear" type="button">↺ Limpiar</button>
          </div>
        </div>
        <p class="nov-count nov-muted">${esc(countText(m, st))}</p>
        <div class="nov-table-wrap">
          <table class="table nov-table">
            <thead><tr><th>Causa directa</th><th>Objetivo específico</th><th>Pilares</th><th>Hipótesis</th><th>Experimentos y acciones</th><th>Productos</th><th>Resultado esperado e indicador</th><th>Efecto o impacto</th><th><span class="sr-only">Detalle</span></th></tr></thead>
            <tbody>${tbodyHtml(m, st)}</tbody>
          </table>
        </div>
        <p class="nov-source nov-muted">${esc(fuente)}</p>
      </div>`;
  }

  // --- Styles -----------------------------------------------------------------

  const CSS = `
    .nov-intro, .nov-legend { font-size: 0.82rem; color: var(--text-muted); line-height: 1.5; }
    .nov-toolbar-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin-top: 0.6rem; }
    .nov-message { font-size: 0.8rem; color: var(--text-muted); overflow-wrap: anywhere; }
    .nov-message.is-error { color: var(--bad); }
    .nov-message.is-ok { color: var(--ok); }
    .nov-pending { margin-top: 0.6rem; padding: 0.5rem 0.7rem; border-radius: var(--radius); border: 1px dashed var(--accent); background: var(--accent-dim); color: var(--text); font-size: 0.82rem; }
    .nov-errors { margin-top: 0.6rem; padding: 0.5rem 0.7rem; border-radius: var(--radius); border: 1px solid var(--bad); background: var(--bad-dim); font-size: 0.8rem; overflow-wrap: anywhere; }
    .nov-errors ul { padding-left: 1.1rem; margin: 0.3rem 0 0; }
    .nov-empty { color: var(--text-muted); font-size: 0.85rem; padding: 0.6rem 0; }
    .nov-muted { color: var(--text-dim); }
    .nov-tree { position: relative; display: flex; flex-direction: column; gap: 0.6rem; }
    .nov-level { position: relative; z-index: 1; }
    .nov-level h5 { font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 0.4rem; display: inline-block; background: var(--surface); padding-right: 0.5rem; }
    .nov-level + .nov-level { margin-top: 2.6rem; }
    .nov-level + .nov-level h5 { margin-bottom: 1.6rem; }
    .nov-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(15rem, 100%), 1fr)); gap: 0.75rem 1rem; }
    .nov-grid--chains { margin-top: 0.6rem; }
    .nov-chain { display: flex; flex-direction: column; align-items: stretch; gap: 0.2rem; min-width: 0; }
    .nov-chain__arrow { text-align: center; color: var(--text-dim); line-height: 1; }
    .nov-node { background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius); padding: 0.6rem 0.7rem; font-size: 0.82rem; line-height: 1.45; min-width: 0; overflow-wrap: anywhere; transition: opacity 0.15s ease; }
    .nov-node p { margin: 0; }
    .nov-node--central { border-left: 4px solid var(--bad); }
    .nov-node--cause { border-bottom: 3px solid var(--accent); }
    .nov-node--objective { border-left: 4px solid var(--ok); }
    .nov-node--pillar { border-top: 4px solid var(--tone, var(--accent)); }
    .nov-node--hypothesis { border-left: 4px solid #a78bfa; }
    .nov-kind { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0.3rem; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; color: var(--text-dim); margin-bottom: 0.3rem; }
    .nov-node--pillar .nov-kind > span:first-child { color: var(--tone, var(--accent)); }
    .nov-node--hypothesis .nov-kind > span:first-child { color: #a78bfa; }
    .nov-name { font-weight: 700; color: var(--text); }
    .nov-text { font-size: 0.78rem; color: var(--text-muted); margin-top: 0.3rem !important; }
    .nov-line { display: block; margin-top: 0.35rem; color: var(--text-dim); }
    .nov-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.45rem; }
    .nov-chip { display: inline-block; max-width: 100%; font-size: 0.72rem; line-height: 1.35; padding: 0.15rem 0.5rem; border-radius: 999px; border: 1px solid var(--chip, var(--border)); background: color-mix(in srgb, var(--chip, var(--accent)) 14%, transparent); color: var(--text); overflow-wrap: anywhere; }
    .nov-chip b { color: var(--chip, var(--accent)); font-weight: 700; white-space: nowrap; margin-right: 0.3rem; }
    .nov-chip--experimento { --chip: #38bdf8; }
    .nov-chip--intervencion { --chip: #f59e0b; }
    .nov-chip--transferencia { --chip: #34d399; }
    .nov-chip--implementacion { --chip: #a78bfa; }
    .nov-chip--accion { --chip: #f472b6; }
    [data-theme="light"] .nov-chip--experimento { --chip: #0369a1; }
    [data-theme="light"] .nov-chip--intervencion { --chip: #b45309; }
    [data-theme="light"] .nov-chip--transferencia { --chip: #047857; }
    [data-theme="light"] .nov-chip--implementacion { --chip: #6d28d9; }
    [data-theme="light"] .nov-chip--accion { --chip: #be185d; }
    .nov-arrows { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; z-index: 0; }
    .nov-arrow { fill: none; stroke-width: 1.6; opacity: 0.75; transition: opacity 0.15s ease; }
    .nov-arrow--objetivo { stroke-dasharray: 4 3; opacity: 0.55; }
    .nov-tree.has-focus .nov-arrow { opacity: 0.12; }
    .nov-tree.has-focus .nov-arrow.is-focus { opacity: 1; stroke-width: 2.4; }
    .nov-tree.has-focus [data-tree-node]:not(.is-focus) { opacity: 0.45; }
    .nov-tree.is-stacked .nov-arrows { display: none; }
    .nov-tree.is-stacked .nov-level + .nov-level { margin-top: 1rem; }
    .nov-tree.is-stacked .nov-level + .nov-level h5 { margin-bottom: 0.4rem; }
    .nov-matrix { display: flex; flex-direction: column; gap: 0.7rem; min-width: 0; }
    .nov-matrix__head { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr)); gap: 0.6rem; }
    .nov-matrix__head > div { background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius); padding: 0.55rem 0.7rem; font-size: 0.82rem; overflow-wrap: anywhere; }
    .nov-matrix__head p { margin: 0.2rem 0 0; }
    .nov-k { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-dim); }
    .nov-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(10rem, 100%), 1fr)); gap: 0.6rem; }
    .nov-stat { background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius); padding: 0.6rem 0.8rem; display: flex; flex-direction: column; gap: 0.15rem; }
    .nov-stat__val { font-size: 1.3rem; font-weight: 700; color: var(--accent); font-family: var(--font-mono); line-height: 1.1; }
    .nov-stat .matrix-stat-lbl { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; color: var(--text-dim); }
    .nov-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius); padding: 0.55rem 0.7rem; }
    .nov-search { display: flex; align-items: center; gap: 0.4rem; flex: 1 1 14rem; min-width: 0; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 0.3rem 0.55rem; }
    .nov-search__input { background: none; border: none; color: var(--text); font-size: 0.82rem; width: 100%; min-width: 0; outline: none; }
    .nov-toolbar .matrix-filters { display: flex; flex-wrap: wrap; gap: 0.4rem; }
    .nov-type { background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: var(--radius); padding: 0.35rem 0.6rem; font-size: 0.78rem; max-width: 100%; }
    .nov-count, .nov-source { font-size: 0.78rem; margin: 0; }
    .nov-table-wrap { border: 1px solid var(--border); border-radius: var(--radius); overflow-x: auto; max-width: 100%; }
    .nov-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
    .nov-table th { position: sticky; top: 0; background: var(--surface); text-align: left; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.03em; color: var(--text-dim); padding: 0.45rem 0.5rem; box-shadow: 0 1px 0 var(--border); }
    .nov-table td { vertical-align: top; padding: 0.5rem; border-top: 1px solid var(--border-subtle); overflow-wrap: anywhere; min-width: 7rem; }
    .nov-table tr.nov-row:hover td { background: var(--surface-hover); }
    .nov-table td[data-col="detalle"] { min-width: 0; white-space: nowrap; }
    .nov-table td[data-col="experimentos"] { min-width: 11rem; }
    .nov-id { font-family: var(--font-mono); font-size: 0.72rem; font-weight: 700; color: var(--accent); }
    .nov-indicator { display: block; color: var(--text-dim); }
    .nov-detail { font-size: 0.8rem; display: flex; flex-direction: column; gap: 0.35rem; background: var(--surface-2); border-radius: var(--radius); padding: 0.6rem 0.75rem; }
    .nov-detail p, .nov-detail ul { margin: 0; }
    .nov-detail ul { padding-left: 1.1rem; }
    .nov-detail__exps li { margin-bottom: 0.35rem; }
    .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
    @media (max-width: 760px) {
      .nov-table-wrap { overflow-x: visible; border: none; }
      .nov-table thead { display: none; }
      .nov-table, .nov-table tbody, .nov-table tr, .nov-table td { display: block; width: 100%; }
      .nov-table tr.nov-row { border: 1px solid var(--border); border-radius: var(--radius); margin-top: 0.6rem; }
      .nov-table tr.nov-row-detail[hidden] { display: none; }
      .nov-table td { min-width: 0; border-top: none; padding: 0.35rem 0.6rem; }
      .nov-table td::before { content: attr(data-label); display: block; font-size: 0.66rem; font-weight: 700; text-transform: uppercase; color: var(--text-dim); }
      .nov-table td[data-col="detalle"]::before { content: none; }
    }
  `;

  function injectStyles(doc) {
    if (doc.getElementById(STYLE_ID)) return;
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = CSS;
    (doc.head || doc.documentElement).appendChild(style);
  }

  // --- Controller -------------------------------------------------------------

  function mount(root, options) {
    const opts = options || {};
    const interval = Number(opts.interval) > 0 ? Number(opts.interval) : 5000;
    const doFetch = opts.fetch || ((...args) => window.fetch(...args));
    const send = opts.send || ((prompt) => window.sendTerminalPrompt(prompt));
    const doc = root.ownerDocument;
    const win = doc.defaultView || window;
    injectStyles(doc);
    const slot = (name) => root.querySelector(`[data-nov-slot="${name}"]`);
    const slots = { meta: slot('meta'), head: slot('head'), tree: slot('tree'), matrix: slot('matrix'), judge: slot('judge') };

    if (slots.head) {
      slots.head.innerHTML = `
        <p class="nov-intro">El investigador propone los pilares de novedad y las hipótesis a partir de la idea, los insumos, la guía ajustada al TDR, los dos árboles, el Proyecto Resumido y el estado del arte. Cada hipótesis trae los experimentos, acciones, implementaciones, intervenciones o transferencias que producirían su evidencia, y no siempre pasan por la IA. Es una vista asesora: no reescribe secciones ni aprueba compuertas.</p>
        <div class="nov-toolbar-row">
          <button class="btn btn--sm btn--primary nov-run" type="button">Generar / actualizar</button>
          <button class="btn btn--sm nov-retry" type="button" hidden>Reintentar envío</button>
          <span class="nov-message" role="status" aria-live="polite"></span>
        </div>
        <div class="nov-status"></div>`;
    }
    const runBtn = root.querySelector('.nov-run');
    const retryBtn = root.querySelector('.nov-retry');
    const message = root.querySelector('.nov-message');
    const status = root.querySelector('.nov-status');

    const state = { data: null, sig: null, pending: null, prompt: null, timer: null, observer: null,
      matrix: { query: '', tipo: '', expanded: new Set() } };

    let judge = null;
    if (slots.judge && win.JudgeAvance) {
      judge = win.JudgeAvance.mount(slots.judge, { etapa: 'novedad', interval, fetch: doFetch, send });
    }

    function say(text, kind) {
      if (!message) return;
      message.textContent = text || '';
      message.className = `nov-message${kind ? ` is-${kind}` : ''}`;
    }

    function draw() {
      const tree = slots.tree && slots.tree.querySelector('[data-novelty-tree]');
      if (tree) drawArrows(tree);
    }

    function paintMatrixBody() {
      const m = state.data && state.data.matriz;
      const box = slots.matrix && slots.matrix.querySelector('.nov-matrix');
      if (!m || !box) return;
      box.querySelector('tbody').innerHTML = tbodyHtml(m, state.matrix);
      box.querySelector('.nov-count').textContent = countText(m, state.matrix);
    }

    function wireMatrix() {
      const box = slots.matrix && slots.matrix.querySelector('.nov-matrix');
      if (!box) return;
      const input = box.querySelector('.nov-search__input');
      const select = box.querySelector('.nov-type');
      input.addEventListener('input', () => { state.matrix.query = input.value; paintMatrixBody(); });
      select.addEventListener('change', () => { state.matrix.tipo = select.value; paintMatrixBody(); });
      box.querySelector('.nov-clear').addEventListener('click', () => {
        state.matrix.query = '';
        state.matrix.tipo = '';
        input.value = '';
        select.value = '';
        paintMatrixBody();
      });
      box.querySelector('tbody').addEventListener('click', (event) => {
        const btn = event.target && event.target.closest && event.target.closest('.nov-expand');
        if (!btn) return;
        const oe = btn.closest('tr').getAttribute('data-oe');
        if (state.matrix.expanded.has(oe)) state.matrix.expanded.delete(oe);
        else state.matrix.expanded.add(oe);
        paintMatrixBody();
      });
    }

    function paint() {
      const data = state.data || {};
      const sig = JSON.stringify([data, !!state.pending]);
      if (sig === state.sig) return;
      state.sig = sig;
      const nov = data.disponible ? data.novedad : null;
      if (slots.meta) slots.meta.textContent = [data.run, nov && nov.fecha].filter(Boolean).join(' · ') || '—';
      if (runBtn) runBtn.disabled = !!state.pending;
      if (status) {
        const errors = [...list(data.errores), ...list(data.validacion && data.validacion.errores)];
        status.innerHTML = `${state.pending ? '<div class="nov-pending">El investigador está proponiendo los pilares y las hipótesis. Esta vista se actualiza sola cuando el script registre el artefacto.</div>' : ''}
          ${errors.length ? `<div class="nov-errors"><strong>El artefacto tiene ${errors.length} ${errors.length === 1 ? 'observación' : 'observaciones'} de validación:</strong><ul>${errors.map((e) => `<li>${esc(e)}</li>`).join('')}</ul></div>` : ''}`;
      }
      const loading = state.data === null;
      if (slots.tree) {
        slots.tree.innerHTML = nov
          ? renderTree(nov)
          : loading ? '<p class="nov-empty">Cargando…</p>' : '<p class="nov-empty">Todavía no hay pilares ni hipótesis. Pulsa «Generar / actualizar» para que el investigador los proponga desde los árboles, el Proyecto Resumido y el estado del arte.</p>';
        const tree = slots.tree.querySelector('[data-novelty-tree]');
        if (tree) {
          wireFocus(tree, graph(nov).near);
          if (state.observer) state.observer.disconnect();
          if (typeof win.ResizeObserver === 'function') {
            state.observer = new win.ResizeObserver(() => drawArrows(tree));
            state.observer.observe(tree);
          }
          draw();
        }
      }
      if (slots.matrix) {
        slots.matrix.innerHTML = nov && data.matriz
          ? renderMatrix(data.matriz, state.matrix)
          : loading ? '<p class="nov-empty">Cargando…</p>' : '<p class="nov-empty">La matriz aparece cuando exista el artefacto de novedad.</p>';
        wireMatrix();
      }
    }

    async function refresh() {
      let data;
      try {
        const res = await doFetch('/api/novedad', { cache: 'no-store' });
        data = await res.json();
        if (!res.ok || !data || data.ok === false) throw new Error((data && data.error) || `HTTP ${res.status}`);
      } catch (err) {
        state.data = { errores: [`No se pudo consultar la novedad: ${err && err.message ? err.message : err}`] };
        paint();
        return state.data;
      }
      state.data = data;
      if (state.pending && data.disponible && data.actualizado && data.actualizado !== state.pending.from) {
        state.pending = null;
        say('Llegaron los pilares y las hipótesis del investigador.', 'ok');
      }
      paint();
      return data;
    }

    async function deliver(prompt) {
      state.prompt = prompt;
      say('Enviando el pedido al agente…');
      let delivered = false;
      try { delivered = await send(prompt); } catch (_) { delivered = false; }
      if (delivered === false) {
        if (retryBtn) retryBtn.hidden = false;
        say('El pedido no llegó al agente: la terminal no conectó. Abre el asistente y pulsa «Reintentar envío».', 'error');
        return false;
      }
      if (retryBtn) retryBtn.hidden = true;
      state.pending = { from: (state.data && state.data.actualizado) || null };
      say(`Se envió ${prompt} al agente.`, 'ok');
      paint();
      return true;
    }

    async function run() {
      let result;
      try {
        const res = await doFetch('/api/novedad/run', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        });
        result = await res.json();
      } catch (err) {
        say(`No se pudo pedir la generación: ${err && err.message ? err.message : err}`, 'error');
        return false;
      }
      if (!result || !result.ok || !result.prompt) {
        say((result && result.error) || 'No se pudo pedir la generación.', 'error');
        return false;
      }
      return deliver(result.prompt);
    }

    async function retry() {
      return state.prompt ? deliver(state.prompt) : false;
    }

    function start() {
      refresh();
      if (judge) judge.start();
      if (state.timer) return;
      state.timer = setInterval(() => {
        if (!doc.hidden) refresh();
      }, interval);
      if (win.requestAnimationFrame) win.requestAnimationFrame(draw);
    }

    function stop() {
      if (state.timer) clearInterval(state.timer);
      state.timer = null;
      if (judge) judge.stop();
    }

    if (runBtn) runBtn.addEventListener('click', () => { run(); });
    if (retryBtn) retryBtn.addEventListener('click', () => { retry(); });
    if (win.SectionFolds) win.SectionFolds.onToggle(FOLD_TREE, (open) => { if (open) draw(); });
    if (win.addEventListener) win.addEventListener('resize', draw);
    paint();

    return {
      refresh,
      run,
      retry,
      start,
      stop,
      judge,
      get polling() { return !!state.timer; },
      get data() { return state.data; },
    };
  }

  window.NovedadPanel = { mount, renderTree, renderMatrix, filterRows, drawArrows, TIPOS };
})();
