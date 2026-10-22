#!/usr/bin/env python3
"""graph_html.py — render an interactive 3D codebase-style HTML view of a
codebase-memory graph report with luminosity, particle depth, and connected node highlighting.

Usage:
    scripts/graph_html.py <input.json> [<output.html>]
"""

from __future__ import annotations

import html
import json
import pathlib
import sys

# SOTA Atlas celestial constellation palette (from Papersmith AI)
PALETTE = [
    "#5aa9e6",  # Celestial Cyan (topic_app)
    "#9b7ede",  # Stellar Violet (family)
    "#e8b339",  # Sun Gold (sun)
    "#2ecc71",  # Emerald Plasma (result)
    "#7f6ae6",  # Deep Nebula (topic_ai)
    "#e67e22",  # Stellar Amber (novelty)
    "#e65a5a",  # Radiant Ruby (problem)
    "#7fb069",  # Sage Branch (branch)
    "#e879f9",  # Cosmic Orchid (contribution)
    "#5ad1e6",  # Bright Pulsar (application)
    "#95a5a6",  # Starlight Silver (conclusion)
]


def default_output_path(src: pathlib.Path) -> pathlib.Path:
    name = src.name
    if name.endswith("-graph.json"):
        return src.with_name(name[: -len("-graph.json")] + "-graph.html")
    return src.with_suffix(".html")


def normalise(data: dict) -> dict:
    data = dict(data or {})
    data.setdefault("corpus", "graph")
    data.setdefault("run_id", "")
    data.setdefault("title", f"Atlas 3D — {data['corpus']}")
    data.setdefault("generated_at", "")
    idx = dict(data.get("index") or {})
    idx.setdefault("project", "")
    idx.setdefault("nodes", len(data.get("nodes") or []))
    idx.setdefault("edges", len(data.get("edges") or []))
    idx.setdefault("freshness", "")
    data["index"] = idx
    cn = dict(data.get("central_nodes") or {})
    cn.setdefault("note", "")
    cn.setdefault("items", [])
    data["central_nodes"] = cn
    cm = dict(data.get("communities") or {})
    cm.setdefault("note", "")
    cm.setdefault("clusters", [])
    data["communities"] = cm
    data.setdefault("questions", [])
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    return data


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def render_payload(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</", "<\\/")


def render_central(data: dict) -> str:
    cn = data["central_nodes"]
    out = ["<h3>Nodos Centrales</h3>"]
    if cn.get("note"):
        out.append(f'<p class="note">{esc(cn["note"])}</p>')
    if not cn.get("items"):
        out.append('<p class="empty">Sin hotspots topológicos detectados.</p>')
        return "\n".join(out)
    out.append("<table><thead><tr><th>Nodo</th><th>Grado</th></tr></thead><tbody>")
    for item in cn["items"]:
        label = item.get("label") or item.get("id") or ""
        out.append(
            f'<tr><td><a href="javascript:void(0)" onclick="focusNodeById(\'{esc(item.get("id"))}\')">{esc(label)}</a></td>'
            f'<td class="num">{esc(item.get("degree", ""))}</td></tr>'
        )
    out.append("</tbody></table>")
    return "\n".join(out)


def render_communities(data: dict) -> str:
    cm = data["communities"]
    out = ["<h3>Comunidades Temáticas</h3>"]
    if cm.get("note"):
        out.append(f'<p class="note">{esc(cm["note"])}</p>')
    if not cm.get("clusters"):
        out.append('<p class="empty">Sin comunidades detectadas.</p>')
        return "\n".join(out)
    for i, cluster in enumerate(cm["clusters"]):
        colour = PALETTE[i % len(PALETTE)]
        files = cluster.get("files") or []
        out.append(
            '<details open><summary>'
            f'<span class="swatch" style="background:{colour}; box-shadow: 0 0 8px {colour};"></span>'
            f'<strong>{esc(cluster.get("name", "cluster"))}</strong>'
            f'<span class="count">{len(files)}</span></summary><ul>'
        )
        for f in files:
            out.append(f'<li><a href="javascript:void(0)" onclick="focusNodeById(\'{esc(f)}\')">{esc(f)}</a></li>')
        out.append("</ul></details>")
    return "\n".join(out)


def render_questions(data: dict) -> str:
    out = ["<h3>Preguntas Sugeridas</h3>"]
    if not data["questions"]:
        out.append('<p class="empty">Sin preguntas sugeridas.</p>')
        return "\n".join(out)
    out.append("<ol>")
    out.extend(f"<li>{esc(q)}</li>" for q in data["questions"])
    out.append("</ol>")
    return "\n".join(out)


TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<!-- three.js r128, empotrado: el archivo es autocontenido y no necesita red -->
<script>__THREE_BUNDLE__</script>
<style>
  :root {
    --bg: #060814;
    --panel-bg: rgba(13, 17, 32, 0.85);
    --panel-border: rgba(0, 240, 255, 0.2);
    --cyan: #00f0ff;
    --emerald: #10b981;
    --purple: #a855f7;
    --amber: #f59e0b;
    --rose: #f43f5e;
    --ink: #f1f5f9;
    --muted: #94a3b8;
    --line: rgba(255, 255, 255, 0.1);
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
  }
  body {
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "JetBrains Mono", monospace, sans-serif;
    color: var(--ink);
    background: var(--bg);
    overflow: hidden;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    background: var(--panel-bg);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--panel-border);
    padding: 10px 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    z-index: 10;
  }
  .title-group h1 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .badge-3d {
    background: rgba(0, 240, 255, 0.15);
    color: var(--cyan);
    border: 1px solid var(--cyan);
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 1px 6px;
    border-radius: 4px;
    box-shadow: 0 0 10px rgba(0, 240, 255, 0.3);
  }
  .meta {
    color: var(--muted);
    font-size: 12px;
    margin-top: 2px;
  }
  .meta code {
    background: rgba(255, 255, 255, 0.08);
    color: var(--cyan);
    padding: 1px 5px;
    border-radius: 4px;
  }
  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .search-box {
    position: relative;
  }
  .search-box input {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid var(--line);
    color: #fff;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    width: 220px;
    outline: none;
    transition: all 0.2s;
  }
  .search-box input:focus {
    border-color: var(--cyan);
    box-shadow: 0 0 10px rgba(0, 240, 255, 0.25);
    width: 260px;
  }
  .btn-hud {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid var(--line);
    color: var(--ink);
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    transition: all 0.2s;
  }
  .btn-hud:hover {
    background: rgba(0, 240, 255, 0.12);
    border-color: var(--cyan);
    color: var(--cyan);
  }
  .btn-hud.active {
    background: rgba(0, 240, 255, 0.2);
    border-color: var(--cyan);
    color: var(--cyan);
    box-shadow: 0 0 8px rgba(0, 240, 255, 0.4);
  }

  /* Main viewport layout */
  .viewport-wrap {
    display: flex;
    flex: 1 1 0%;
    min-height: 0;
    position: relative;
    overflow: hidden;
    width: 100%;
    height: calc(100vh - 58px);
  }
  #stage3d {
    flex: 1 1 0%;
    min-width: 0;
    width: 100%;
    height: 100%;
    min-height: 420px;
    position: relative;
    cursor: grab;
    overflow: hidden;
    touch-action: none;
  }
  #stage3d.dragging { cursor: grabbing; }
  #stage3d canvas { display: block; width: 100%; height: 100%; }

  /* Constellation names: one pooled HTML layer over the canvas */
  .graph-names { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
  .graph-names.off { display: none; }
  .graph-name {
    position: absolute;
    left: 0; top: 0;
    font-size: 11px;
    line-height: 1;
    white-space: nowrap;
    color: #c7cde0;
    text-shadow: 0 0 3px #0a0a10, 0 0 6px #0a0a10;
  }
  .graph-name.grp { color: #f3d98b; font-size: 12px; font-weight: 600; letter-spacing: 0.02em; }
  .graph-name.lit { color: #ffffff; }
  .view-note { color: #f3d98b; }

  /* 3D HUD overlay */
  .hud-overlay {
    position: absolute;
    top: 12px;
    left: 12px;
    max-width: min(440px, calc(100% - 24px));
    max-height: calc(100% - 24px);
    display: flex;
    flex-direction: column;
    pointer-events: none;
    z-index: 16;
  }
  /* Collapsed by default so the legend never covers nodes until asked for */
  .hud-legend {
    pointer-events: auto;
    background: var(--panel-bg);
    backdrop-filter: blur(8px);
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
    display: flex;
    flex-direction: column;
    min-height: 0;
    max-height: 100%;
  }
  .hud-legend > summary.hud-legend__toggle {
    list-style: none;
    font-size: 11px;
    font-weight: 600;
    color: var(--ink);
    padding: 6px 10px;
    gap: 7px;
    user-select: none;
    white-space: nowrap;
  }
  .hud-legend > summary.hud-legend__toggle::-webkit-details-marker { display: none; }
  .hud-legend__toggle::after {
    content: "▸";
    color: var(--muted);
    margin-left: 2px;
    transition: transform 0.15s;
  }
  .hud-legend[open] .hud-legend__toggle::after { transform: rotate(90deg); }
  .hud-legend__filter {
    color: var(--cyan);
    font-weight: 500;
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .hud-legend__body {
    border-top: 1px solid var(--line);
    padding: 8px 10px 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;
    min-height: 0;
  }
  .hud-legend__hint, .hud-legend__controls {
    font-size: 11px;
    color: var(--muted);
    line-height: 1.45;
  }
  .hud-legend__controls kbd {
    font-family: inherit;
    font-size: 10px;
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: 0 4px;
  }
  .hud-cluster-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    pointer-events: auto;
  }
  .cluster-tag {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--line);
    cursor: pointer;
    color: var(--muted);
    transition: all 0.15s;
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .hud-cluster-tags.filtering .cluster-tag:not(.active) { opacity: 0.45; }
  .cluster-tag:hover, .cluster-tag.active {
    color: #fff;
    border-color: var(--cyan);
    box-shadow: 0 0 8px rgba(0, 240, 255, 0.3);
  }

  /* Selection Inspector Card */
  .inspector-card {
    position: absolute;
    bottom: 20px;
    left: 20px;
    width: min(380px, calc(100% - 40px));
    max-height: min(480px, calc(100% - 76px));
    overflow-y: auto;
    background: rgba(11, 15, 28, 0.92);
    backdrop-filter: blur(16px);
    border: 1px solid var(--cyan);
    border-radius: 10px;
    padding: 16px;
    box-shadow: 0 0 25px rgba(0, 240, 255, 0.25), 0 10px 30px rgba(0, 0, 0, 0.6);
    z-index: 15;
    display: none;
    flex-direction: column;
    animation: fadeIn 0.2s ease-out;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .inspector-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 1px solid var(--line);
    padding-bottom: 8px;
    margin-bottom: 10px;
  }
  .inspector-title {
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    word-break: break-word;
    line-height: 1.4;
  }
  .inspector-close {
    background: none;
    border: none;
    color: var(--muted);
    font-size: 18px;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }
  .inspector-close:hover { color: #fff; }
  .inspector-type {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 8px;
    background: rgba(0, 240, 255, 0.15);
    color: var(--cyan);
    border: 1px solid var(--cyan);
  }
  .inspector-group {
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .inspector-summary {
    font-size: 11.5px;
    color: #e2e8f0;
    background: rgba(0, 240, 255, 0.07);
    border-left: 2px solid var(--cyan);
    padding: 5px 8px;
    border-radius: 0 4px 4px 0;
    margin-bottom: 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
    line-height: 1.35;
  }
  .inspector-neighbors-title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    margin: 8px 0 6px;
  }
  .inspector-neighbors {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-y: auto;
    max-height: 220px;
    padding-right: 4px;
  }
  .neighbor-chip {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--line);
    padding: 5px 8px;
    border-radius: 4px;
    font-size: 11px;
    color: var(--ink);
    cursor: pointer;
    text-align: left;
    transition: all 0.15s;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .neighbor-chip:hover {
    background: rgba(0, 240, 255, 0.15);
    border-color: var(--cyan);
    color: var(--cyan);
  }
  .inspector-actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid var(--line);
  }

  /* Right Drawer / Sidebar */
  .sidebar-drawer {
    width: 360px;
    min-width: 360px;
    max-width: 360px;
    flex: 0 0 360px;
    background: var(--panel-bg);
    backdrop-filter: blur(12px);
    border-left: 1px solid var(--panel-border);
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    z-index: 10;
    transition: margin-right 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
  }
  .sidebar-drawer.collapsed {
    margin-right: -360px;
    opacity: 0;
    pointer-events: none;
  }
  .sidebar-drawer h3 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--cyan);
    margin: 0 0 8px;
    border-bottom: 1px solid var(--line);
    padding-bottom: 4px;
  }
  .note {
    font-size: 11px;
    color: var(--muted);
    background: rgba(0, 240, 255, 0.05);
    border-left: 3px solid var(--cyan);
    padding: 6px 8px;
    margin: 0 0 8px;
    border-radius: 0 4px 4px 0;
  }
  .empty { font-size: 12px; color: var(--muted); font-style: italic; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--line); }
  th { color: var(--muted); font-size: 11px; }
  td.num { text-align: right; }
  details { font-size: 12px; margin-bottom: 6px; }
  summary { cursor: pointer; display: flex; align-items: center; gap: 6px; padding: 4px 0; }
  .swatch { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex: none; }
  .count { color: var(--muted); margin-left: auto; }
  details ul { margin: 4px 0 6px 16px; padding: 0; color: var(--muted); font-size: 11px; }
  ol { padding-left: 18px; font-size: 12px; margin: 0; }
  ol li { margin-bottom: 8px; color: var(--muted); }
  ol li strong, ol li b { color: var(--ink); }
  a { color: var(--cyan); text-decoration: none; }
  a:hover { text-decoration: underline; }

  /* Tooltip HUD */
  #tooltipHud {
    position: absolute;
    pointer-events: none;
    background: rgba(11, 15, 28, 0.96);
    backdrop-filter: blur(12px);
    border: 1px solid var(--cyan);
    color: #fff;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 11.5px;
    opacity: 0;
    transition: opacity 0.12s ease;
    z-index: 25;
    width: max-content;
    max-width: min(440px, calc(100vw - 48px));
    box-shadow: 0 0 18px rgba(0, 240, 255, 0.28), 0 8px 20px rgba(0, 0, 0, 0.65);
  }
  #tooltipHud .tooltip-label {
    font-size: 12.5px;
    font-weight: 700;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 416px;
    margin-bottom: 3px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  #tooltipHud .tooltip-summary {
    font-size: 11px;
    color: #cbd5e1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 416px;
    line-height: 1.35;
    margin-bottom: 4px;
  }
  #tooltipHud .tooltip-meta {
    font-size: 10px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 416px;
  }
</style>
</head>
<body>

<header>
  <div class="title-group">
    <h1>
      __TITLE__
      <span class="badge-3d">3D Codebase Galaxy</span>
    </h1>
    <div class="meta">
      <code>__PROJECT__</code> · __NODES__ nodos / __EDGES__ aristas__FRESH__
      <span class="view-note" id="viewNote"></span>
    </div>
  </div>

  <div class="header-actions">
    <div class="search-box">
      <input type="text" id="searchInput" placeholder="Buscar paper, archivo, nodo..." oninput="handleSearch(this.value)">
    </div>
    <button class="btn-hud" id="btnAutoRotate" onclick="toggleAutoRotate()">⟳ Auto-Giro</button>
    <button class="btn-hud" onclick="resetCamera()">🎯 Centrar</button>
    <button class="btn-hud active" id="btnNames" onclick="toggleNames()" title="Mostrar u ocultar los nombres de la constelación">Aa Nombres</button>
    <button class="btn-hud" id="btnViewMode" onclick="toggleViewMode()" title="Cambiar entre la constelación 3D (GPU) y la 2D (liviana)">◐ Vista 2D</button>
    <button class="btn-hud active" id="btnToggleSide" onclick="toggleSidebar()" title="Mostrar/ocultar panel de métricas">▤ Panel Datos</button>
  </div>
</header>

<div class="viewport-wrap">
  <div id="stage3d">
    <div class="hud-overlay">
      <details class="hud-legend" id="hudLegend">
        <summary class="hud-legend__toggle" title="Mostrar u ocultar la leyenda y los controles">
          <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--cyan); box-shadow:0 0 6px var(--cyan);"></span>
          <span>Leyenda y controles</span>
          <span class="hud-legend__filter" id="hudLegendFilter"></span>
        </summary>
        <div class="hud-legend__body">
          <div class="hud-legend__hint">Pasa el cursor o haz clic en un nodo para ver su <strong>etiqueta principal y resumen</strong>. Haz clic en las comunidades para encenderlas o apagarlas; puedes combinar varias.</div>
          <div class="hud-legend__controls"><kbd>Arrastrar</kbd> orbitar · <kbd>Clic derecho</kbd> o <kbd>Shift</kbd>+arrastrar desplazar · <kbd>Rueda</kbd> o pellizco zoom · <kbd>Doble clic</kbd> enfocar nodo</div>
          <div class="hud-cluster-tags" id="clusterFilterTags">
            <!-- Rendered by JS -->
          </div>
          <button type="button" class="btn-hud" id="btnClearClusters" onclick="clearClusterFilters()" style="display:none; align-self:flex-start;">Mostrar todas las comunidades</button>
        </div>
      </details>
    </div>

    <!-- Inspector HUD Card -->
    <div class="inspector-card" id="inspectorCard">
      <div class="inspector-header">
        <div class="inspector-title" id="inspTitle">—</div>
        <button class="inspector-close" onclick="clearSelection()">&times;</button>
      </div>
      <div class="inspector-summary" id="inspSummary" title="">—</div>
      <div>
        <span class="inspector-type" id="inspType">File</span>
        <div class="inspector-group" id="inspGroup">Cluster</div>
      </div>
      <div class="inspector-neighbors-title" id="inspNeighborsCount">Conexiones Directas (0)</div>
      <div class="inspector-neighbors" id="inspNeighborsList">
        <!-- Neighbor chips -->
      </div>
      <div class="inspector-actions">
        <button class="btn-hud" onclick="focusCameraOnSelected()" style="flex:1;">🎯 Enfocar Nodo</button>
        <button class="btn-hud" onclick="clearSelection()">Limpiar</button>
      </div>
    </div>

    <div id="tooltipHud"></div>
  </div>

  <div class="sidebar-drawer" id="sideDrawer">
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--line); padding-bottom:8px;">
      <span style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:var(--cyan);">Panel de Datos y Métricas</span>
      <button class="inspector-close" onclick="toggleSidebar()" title="Ocultar panel" style="cursor:pointer; font-size:18px; color:var(--muted); line-height:1;">&times;</button>
    </div>
    __CENTRAL__
    __COMMUNITIES__
    __QUESTIONS__
  </div>
</div>

<script type="application/json" id="graph-data">__PAYLOAD__</script>

<script>
(function() {
  "use strict";

  var DATA = JSON.parse(document.getElementById("graph-data").textContent);
  var PAL = __PALETTE__;
  var BACKGROUND = "#0a0a10";

  // 3D needs a WebGL context without a major performance caveat (a software
  // rasterizer counts as one) and a machine that reports enough memory and
  // cores, for a graph of reasonable size; anything less opens the 2D
  // constellation. ?view=2d|3d and the
  // header button override the heuristics, but never a missing WebGL.
  // view-mode:begin
  function chooseViewMode(env) {
    var m = /[?&]view=(2d|3d)(?:&|#|$)/i.exec(env.search || "");
    if (env.gl === "none") return { mode: "2d", reason: "none" };
    if (m) return { mode: m[1].toLowerCase(), reason: "url" };
    if (env.saved === "2d" || env.saved === "3d") return { mode: env.saved, reason: "user" };
    if (env.gl !== "ok") return { mode: "2d", reason: "weak" };
    if ((env.memory && env.memory < 4) || (env.cores && env.cores <= 2)) return { mode: "2d", reason: "resources" };
    // Each node is one mesh and one halo: past this size the draw calls alone
    // keep a CPU core busy while the 3D view spins.
    if (env.nodes > 1500) return { mode: "2d", reason: "large" };
    return { mode: "3d", reason: "gpu" };
  }
  // view-mode:end

  function webglSupport() {
    try {
      var probe = document.createElement("canvas");
      var strict = { failIfMajorPerformanceCaveat: true };
      var g = probe.getContext("webgl2", strict) || probe.getContext("webgl", strict);
      if (g) {
        var lose = g.getExtension("WEBGL_lose_context");
        if (lose) lose.loseContext();
        return "ok";
      }
      var any = document.createElement("canvas");
      var weak = any.getContext("webgl2") || any.getContext("webgl");
      if (weak) {
        var loseWeak = weak.getExtension("WEBGL_lose_context");
        if (loseWeak) loseWeak.loseContext();
        return "weak";
      }
    } catch (_) {}
    return "none";
  }

  var VIEW_PREF_KEY = "morfeo.graphView";
  var NAMES_PREF_KEY = "morfeo.graphNames";
  function readPref(key) {
    try { return window.localStorage.getItem(key) || ""; } catch (_) { return ""; }
  }
  function writePref(key, value) {
    try { window.localStorage.setItem(key, value); } catch (_) {}
  }

  var glSupport = webglSupport();
  var rawNodeCount = (DATA.nodes || []).length;
  var viewChoice = chooseViewMode({
    search: window.location.search,
    saved: readPref(VIEW_PREF_KEY),
    gl: glSupport,
    memory: navigator.deviceMemory,
    cores: navigator.hardwareConcurrency,
    nodes: rawNodeCount
  });

  // Nodes & Edges Setup
  var rawNodes = DATA.nodes || [];
  var rawEdges = DATA.edges || [];

  var byId = {};
  var groups = [];

  rawNodes.forEach(function(n) {
    if (n.group && groups.indexOf(n.group) < 0) groups.push(n.group);
  });

  var nodes = rawNodes.map(function(n, idx) {
    var groupIndex = n.group ? groups.indexOf(n.group) : -1;
    var color = groupIndex >= 0 ? PAL[groupIndex % PAL.length] : "#00f0ff";
    var size = (n.type === "Subseccion" || n.type === "Branch") ? 7.5 : 4.5;
    var labelStr = String(n.label || n.id || "");
    var summaryStr = String(n.summary || n.group || labelStr).replace(/\\s+/g, " ").trim();
    var nodeObj = {
      id: n.id,
      label: labelStr,
      summary: summaryStr,
      type: n.type || "File",
      group: n.group || "General",
      color: color,
      size: size,
      x: 0, y: 0, z: 0,
      vx: 0, vy: 0, vz: 0,
      neighbors: new Set(),
      edges: []
    };
    byId[n.id] = nodeObj;
    return nodeObj;
  });

  var edges = [];
  rawEdges.forEach(function(e) {
    var sourceNode = byId[e.source];
    var targetNode = byId[e.target];
    if (sourceNode && targetNode) {
      sourceNode.neighbors.add(targetNode.id);
      targetNode.neighbors.add(sourceNode.id);
      var edgeObj = {
        source: sourceNode,
        target: targetNode,
        type: e.type || "CONNECTS"
      };
      edges.push(edgeObj);
      sourceNode.edges.push(edgeObj);
      targetNode.edges.push(edgeObj);
    }
  });

  // 3D Celestial Force Layout with Golden Spiral Neighborhoods (Papersmith SOTA Atlas)
  function init3DPositions() {
    var GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
    var PHI = (Math.sqrt(5) - 1) / 2;
    var CLUSTER_STEP = 320;
    var FAMILY_LIFT = 380;
    var MEMBER_STEP = 90;
    var TILT_MAX = 0.85;

    // Group nodes by community/cluster
    var byGroup = {};
    groups.forEach(function(g) { byGroup[g] = []; });
    nodes.forEach(function(n) {
      var g = n.group || "General";
      if (!byGroup[g]) byGroup[g] = [];
      byGroup[g].push(n);
    });

    // Compute cluster centers on an outer golden spiral with family lift
    var clusterCenters = {};
    groups.forEach(function(g, findex) {
      var radius = CLUSTER_STEP * Math.sqrt(findex);
      var angle = findex * GOLDEN_ANGLE;
      var ccx = radius * Math.cos(angle);
      var ccy = radius * Math.sin(angle);
      var ccz = FAMILY_LIFT * (2 * ((findex * PHI) % 1.0) - 1);
      clusterCenters[g] = { x: ccx, y: ccy, z: ccz };

      // Tilted orbital frame (u, v) for this cluster
      var spin = findex * GOLDEN_ANGLE;
      var tilt = TILT_MAX * (2 * (((findex + 1) * PHI) % 1.0) - 1);
      var u = { x: Math.cos(spin), y: Math.sin(spin), z: 0.0 };
      var v = {
        x: -Math.sin(spin) * Math.cos(tilt),
        y: Math.cos(spin) * Math.cos(tilt),
        z: Math.sin(tilt)
      };

      // Place cluster members along their orbital plane
      byGroup[g].forEach(function(n, mindex) {
        var mradius = MEMBER_STEP * Math.sqrt(mindex);
        var mangle = mindex * GOLDEN_ANGLE;
        var lx = mradius * Math.cos(mangle);
        var ly = mradius * Math.sin(mangle);
        n.x = ccx + lx * u.x + ly * v.x;
        n.y = ccy + lx * u.y + ly * v.y;
        n.z = ccz + lx * u.z + ly * v.z;
        n.vx = 0; n.vy = 0; n.vz = 0;
      });
    });

    // 3D Relaxation Simulation to settle nodes into celestial balance. The
    // repulsion pass is quadratic, so large graphs get fewer passes: the golden
    // spiral already places them, and the page must not freeze on load.
    var relaxIters = Math.max(40, Math.min(160, Math.round(160 * 600 / Math.max(nodes.length, 1))));
    for (var it = 0; it < relaxIters; it++) {
      var cool = 1 - it / relaxIters;
      // Repulsion between all nodes
      for (var i = 0; i < nodes.length; i++) {
        var a = nodes[i];
        for (var j = i + 1; j < nodes.length; j++) {
          var b = nodes[j];
          var dx = b.x - a.x;
          var dy = b.y - a.y;
          var dz = b.z - a.z;
          var d2 = dx*dx + dy*dy + dz*dz || 1.0;
          if (d2 < 65000) {
            var d = Math.sqrt(d2);
            var f = (3200 / d2) * cool;
            var fx = (dx / d) * f;
            var fy = (dy / d) * f;
            var fz = (dz / d) * f;
            a.vx -= fx; a.vy -= fy; a.vz -= fz;
            b.vx += fx; b.vy += fy; b.vz += fz;
          }
        }
      }
      // Edge spring attraction
      edges.forEach(function(e) {
        var a = e.source, b = e.target;
        var dx = b.x - a.x;
        var dy = b.y - a.y;
        var dz = b.z - a.z;
        var d = Math.sqrt(dx*dx + dy*dy + dz*dz) || 1.0;
        var targetDist = (a.group === b.group) ? 80 : 240;
        var f = (d - targetDist) * 0.025 * cool;
        var fx = (dx / d) * f;
        var fy = (dy / d) * f;
        var fz = (dz / d) * f;
        a.vx += fx; a.vy += fy; a.vz += fz;
        b.vx -= fx; b.vy -= fy; b.vz -= fz;
      });
      // Soft tether to cluster center
      nodes.forEach(function(n) {
        var c = clusterCenters[n.group] || { x: 0, y: 0, z: 0 };
        n.vx += (c.x - n.x) * 0.015 * cool;
        n.vy += (c.y - n.y) * 0.015 * cool;
        n.vz += (c.z - n.z) * 0.015 * cool;
        n.vx *= 0.82; n.vy *= 0.82; n.vz *= 0.82;
        n.x += n.vx; n.y += n.vy; n.z += n.vz;
      });
    }
  }

  init3DPositions();

  // One white radial halo shared by every node; each sprite material tints it
  // with the node color, instead of one canvas and one GPU texture per node.
  // color is a #rrggbb string; the 2D view caches one canvas per color.
  function glowCanvas(color, px) {
    var canvas = document.createElement("canvas");
    canvas.width = px;
    canvas.height = px;
    var ctx = canvas.getContext("2d");
    var r = px / 2;
    var grad = ctx.createRadialGradient(r, r, 0, r, r, r);
    grad.addColorStop(0, color + "ff");
    grad.addColorStop(0.2, color + "8c");
    grad.addColorStop(0.5, color + "1f");
    grad.addColorStop(1, color + "00");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, px, px);
    return canvas;
  }

  function createGlowTexture() {
    return new THREE.CanvasTexture(glowCanvas("#ffffff", 128));
  }

  // State Management
  var selectedNode = null;
  var hoveredNode = null;
  var autoRotate = true;
  // Communities lit by the legend filters; empty means no filter (all lit)
  var activeClusters = new Set();
  function clusterFilterOn() { return activeClusters.size > 0; }
  function clusterLit(g) { return activeClusters.has(g); }

  // DOM Elements
  var stageEl = document.getElementById("stage3d");
  var tooltipEl = document.getElementById("tooltipHud");
  var inspectorCard = document.getElementById("inspectorCard");
  var clusterTagsEl = document.getElementById("clusterFilterTags");

  // Render Cluster Filters
  if (groups.length) {
    groups.forEach(function(g, idx) {
      var col = PAL[idx % PAL.length];
      var tag = document.createElement("div");
      tag.className = "cluster-tag";
      tag.innerHTML = '<span style="width:7px; height:7px; border-radius:50%; background:' + col + '; box-shadow:0 0 6px ' + col + '"></span>' + g;
      tag.dataset.group = g;
      tag.title = "Clic para encender o apagar esta comunidad";
      // Each click toggles only this community, so any combination can be lit
      tag.onclick = function() {
        if (activeClusters.has(g)) activeClusters.delete(g);
        else activeClusters.add(g);
        tag.classList.toggle("active", activeClusters.has(g));
        refreshClusterFilterUi();
        updateVisualStates();
      };
      clusterTagsEl.appendChild(tag);
    });
  }

  function refreshClusterFilterUi() {
    // A collapsed legend still has to say a filter is dimming nodes
    var label = document.getElementById("hudLegendFilter");
    if (label) {
      if (activeClusters.size === 1) label.textContent = "· " + Array.from(activeClusters)[0];
      else if (activeClusters.size > 1) label.textContent = "· " + activeClusters.size + " comunidades";
      else label.textContent = "";
    }
    if (clusterTagsEl) clusterTagsEl.classList.toggle("filtering", clusterFilterOn());
    var clearBtn = document.getElementById("btnClearClusters");
    if (clearBtn) clearBtn.style.display = clusterFilterOn() ? "" : "none";
  }

  window.clearClusterFilters = function() {
    activeClusters.clear();
    document.querySelectorAll(".cluster-tag").forEach(function(t) { t.classList.remove("active"); });
    refreshClusterFilterUi();
    updateVisualStates();
  };

  // --- THREE.JS 3D SCENE SETUP (SOTA ATLAS CELESTIAL SKY) ---
  var scene, camera, renderer;
  var nodeMeshes = [];
  var nodeGlowSprites = [];
  var lineSegments;
  var linePositions, lineColors;
  var edgeSegmentMeta = [];

  function getStageSize() {
    var w = stageEl ? stageEl.clientWidth : 0;
    var h = stageEl ? stageEl.clientHeight : 0;
    if (w <= 0) {
      var drawer = document.getElementById("sideDrawer");
      var dw = (drawer && !drawer.classList.contains("collapsed")) ? 360 : 0;
      w = Math.max((window.innerWidth || 1280) - dw, 640);
    }
    if (h <= 0) {
      h = Math.max((window.innerHeight || 720) - 58, 480);
    }
    return { width: w, height: h };
  }

  function createCanvas3DRenderer(initW, initH) {
    var cvs = document.createElement("canvas");
    var ctx = cvs.getContext("2d");
    var dpr = Math.min(Math.max(window.devicePixelRatio || 1, 1), 2);
    // Halo images drawn once per color, so a frame is drawImage calls
    // instead of one radial gradient per node.
    var glowByColor = {};
    function glowFor(color) {
      if (!glowByColor[color]) glowByColor[color] = glowCanvas(color, 64);
      return glowByColor[color];
    }
    var cw = initW, ch = initH;
    var projVec = new THREE.Vector3();

    function setSize(w, h) {
      cw = Math.max(w, 1);
      ch = Math.max(h, 1);
      cvs.width = Math.round(cw * dpr);
      cvs.height = Math.round(ch * dpr);
      cvs.style.width = cw + "px";
      cvs.style.height = ch + "px";
    }
    setSize(initW, initH);

    function projectPoint(x, y, z, cam) {
      projVec.set(x, y, z);
      projVec.project(cam);
      if (projVec.z < -1 || projVec.z > 1) return null;
      return {
        sx: (projVec.x * 0.5 + 0.5) * cw,
        sy: (-projVec.y * 0.5 + 0.5) * ch,
        depth: projVec.z
      };
    }

    return {
      domElement: cvs,
      isCanvas2D: true,
      setPixelRatio: function(p) { dpr = Math.min(Math.max(p || 1, 1), 2); setSize(cw, ch); },
      dispose: function() { glowByColor = {}; },
      setSize: setSize,
      render: function(scn, cam) {
        if (!ctx) return;
        cam.updateMatrixWorld();
        ctx.save();
        ctx.scale(dpr, dpr);
        ctx.fillStyle = BACKGROUND;
        ctx.fillRect(0, 0, cw, ch);

        // Project nodes
        var projectedNodes = [];
        var projById = {};
        nodes.forEach(function(n) {
          var p = projectPoint(n.x, n.y, n.z, cam);
          if (p) {
            var item = { node: n, sx: p.sx, sy: p.sy, depth: p.depth };
            projectedNodes.push(item);
            projById[n.id] = item;
          }
        });

        // Draw edges
        ctx.lineWidth = selectedNode ? 1.5 : 1.0;
        edges.forEach(function(e) {
          var pa = projById[e.source.id];
          var pb = projById[e.target.id];
          if (!pa || !pb) return;
          var activeEdge = true;
          if (selectedNode) {
            activeEdge = (e.source === selectedNode || e.target === selectedNode);
          } else if (clusterFilterOn()) {
            activeEdge = (clusterLit(e.source.group) && clusterLit(e.target.group));
          }
          ctx.globalAlpha = selectedNode ? (activeEdge ? 0.85 : 0.08) : (activeEdge ? 0.35 : 0.08);
          ctx.strokeStyle = (selectedNode && activeEdge) ? "#38bdf8" : e.source.color;
          ctx.beginPath();
          ctx.moveTo(pa.sx, pa.sy);
          if (e.isInter) {
            var mx = (pa.sx + pb.sx) * 0.5;
            var my = (pa.sy + pb.sy) * 0.5 - 24;
            ctx.quadraticCurveTo(mx, my, pb.sx, pb.sy);
          } else {
            ctx.lineTo(pb.sx, pb.sy);
          }
          ctx.stroke();
        });

        // Sort back-to-front
        projectedNodes.sort(function(a, b) { return b.depth - a.depth; });

        projectedNodes.forEach(function(item) {
          var n = item.node;
          var isTarget = (selectedNode === n);
          var isHovered = (hoveredNode === n);
          var isConn = !selectedNode
            ? (!clusterFilterOn() || clusterLit(n.group))
            : (isTarget || selectedNode.neighbors.has(n.id));
          var alpha = (isTarget || isHovered) ? 1.0 : (isConn ? 0.92 : 0.14);
          var r = Math.max(2.5, n.size * (isTarget ? 1.6 : (isHovered ? 1.3 : (isConn ? 0.8 : 0.55))));

          if (item.sx < -r * 4 || item.sy < -r * 4 || item.sx > cw + r * 4 || item.sy > ch + r * 4) return;
          ctx.globalAlpha = alpha * 0.6;
          ctx.drawImage(glowFor(n.color), item.sx - r * 3.2, item.sy - r * 3.2, r * 6.4, r * 6.4);

          ctx.globalAlpha = alpha;
          ctx.fillStyle = (isTarget || isHovered) ? "#ffffff" : n.color;
          ctx.beginPath();
          ctx.arc(item.sx, item.sy, r, 0, Math.PI * 2);
          ctx.fill();
        });

        ctx.restore();
      }
    };
  }

  // Radius of the node cloud around its centroid: fog, far plane and the
  // star shell scale with it, so small and large graphs read the same.
  function sceneRadius() {
    var cx = 0, cy = 0, cz = 0, r = 0;
    nodes.forEach(function(n) { cx += n.x; cy += n.y; cz += n.z; });
    var k = Math.max(nodes.length, 1);
    cx /= k; cy /= k; cz /= k;
    nodes.forEach(function(n) {
      var dx = n.x - cx, dy = n.y - cy, dz = n.z - cz;
      r = Math.max(r, Math.sqrt(dx * dx + dy * dy + dz * dz));
    });
    return Math.max(r, 400);
  }

  // Deterministic star shell (an LCG, never Math.random): the same graph
  // always shows the same sky, and the stars keep a fixed screen size.
  function addStarfield(radius) {
    var seed = 1234567;
    function rand() {
      seed = (seed * 1664525 + 1013904223) % 4294967296;
      return seed / 4294967296;
    }
    var count = 1600;
    var pos = new Float32Array(count * 3);
    for (var i = 0; i < count; i++) {
      var u = rand() * 2 - 1;
      var th = rand() * Math.PI * 2;
      var dist = radius * (3 + rand() * 3);
      var sq = Math.sqrt(1 - u * u);
      pos[i * 3] = dist * sq * Math.cos(th);
      pos[i * 3 + 1] = dist * sq * Math.sin(th);
      pos[i * 3 + 2] = dist * u;
    }
    var geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    var mat = new THREE.PointsMaterial({
      color: 0x6b7090, size: 1.6, sizeAttenuation: false,
      transparent: true, opacity: 0.7, depthWrite: false
    });
    scene.add(new THREE.Points(geo, mat));
  }

  function initThree() {
    var sz = getStageSize();
    var width = sz.width;
    var height = sz.height;
    var radius = sceneRadius();

    scene = new THREE.Scene();
    scene.background = new THREE.Color(BACKGROUND);
    scene.fog = new THREE.FogExp2(BACKGROUND, 0.35 / radius);

    camera = new THREE.PerspectiveCamera(52, width / height, 1, Math.max(4500, radius * 14));
    camera.position.set(0, 120, 750);

    addStarfield(radius);

    // Warm & Cool Celestial Point Lights + Ambient + Directional Rim
    var ambient = new THREE.AmbientLight(0xdde8ff, 0.65);
    scene.add(ambient);

    var light1 = new THREE.PointLight(0x5aa9e6, 1.4, 4500);
    light1.position.set(800, 1000, 800);
    scene.add(light1);

    var light2 = new THREE.PointLight(0x9b7ede, 1.2, 4500);
    light2.position.set(-800, -700, 600);
    scene.add(light2);

    var light3 = new THREE.PointLight(0xe8b339, 0.85, 3500);
    light3.position.set(0, 500, -900);
    scene.add(light3);

    var rimLight = new THREE.DirectionalLight(0xffffff, 0.35);
    rimLight.position.set(0, 1200, 400);
    scene.add(rimLight);

    // Nodes Construction (Celestial bodies with specular reflection and emissive glow)
    var sphereGeo = new THREE.SphereGeometry(1, 20, 14);
    var glowTexture = createGlowTexture();

    nodes.forEach(function(n) {
      var colorObj = new THREE.Color(n.color);

      // Core Phong Sphere
      var mat = new THREE.MeshPhongMaterial({
        color: colorObj,
        emissive: colorObj.clone().multiplyScalar(0.22),
        shininess: 35,
        transparent: true,
        opacity: 0.95
      });
      var mesh = new THREE.Mesh(sphereGeo, mat);
      mesh.scale.setScalar(n.size);
      mesh.position.set(n.x, n.y, n.z);
      mesh.userData = { node: n };
      scene.add(mesh);
      nodeMeshes.push(mesh);
      n.mesh = mesh;

      // Luminous Glow Sprite (Additive Blending)
      var glowMat = new THREE.SpriteMaterial({
        map: glowTexture,
        depthWrite: false,
        color: colorObj,
        transparent: true,
        opacity: 0.72,
        blending: THREE.AdditiveBlending
      });
      var sprite = new THREE.Sprite(glowMat);
      sprite.scale.setScalar(n.size * 5.4);
      sprite.position.copy(mesh.position);
      scene.add(sprite);
      nodeGlowSprites.push(sprite);
      n.sprite = sprite;
    });

    // Edges Construction: Straight lines for intra-cluster, 3D curved parabolic arcs for cross-cluster
    var ARC_SEGMENTS = 12;
    var totalSegments = 0;
    edges.forEach(function(e) {
      e.isInter = (e.source.group !== e.target.group);
      totalSegments += e.isInter ? ARC_SEGMENTS : 1;
    });

    linePositions = new Float32Array(totalSegments * 2 * 3);
    lineColors = new Float32Array(totalSegments * 2 * 3);
    edgeSegmentMeta = [];

    var vertIdx = 0;
    edges.forEach(function(e) {
      var segStart = vertIdx;
      var cSrc = new THREE.Color(e.source.color);
      var cTgt = new THREE.Color(e.target.color);

      if (e.isInter) {
        // 3D Parabolic Curved Arc between clusters
        var v0 = new THREE.Vector3(e.source.x, e.source.y, e.source.z);
        var v2 = new THREE.Vector3(e.target.x, e.target.y, e.target.z);
        var mid = new THREE.Vector3().addVectors(v0, v2).multiplyScalar(0.5);
        var dist = v0.distanceTo(v2);

        // Control point lifted in normal direction away from the origin
        var liftDir = mid.clone().normalize();
        if (liftDir.lengthSq() < 0.01) liftDir.set(0, 1, 0);
        var arcLift = Math.min(dist * 0.45, 180);
        var v1 = mid.clone().add(liftDir.multiplyScalar(arcLift));

        var curve = new THREE.QuadraticBezierCurve3(v0, v1, v2);
        var pts = curve.getPoints(ARC_SEGMENTS);

        for (var s = 0; s < ARC_SEGMENTS; s++) {
          var pA = pts[s];
          var pB = pts[s + 1];
          var tA = s / ARC_SEGMENTS;
          var tB = (s + 1) / ARC_SEGMENTS;
          var colA = cSrc.clone().lerp(cTgt, tA);
          var colB = cSrc.clone().lerp(cTgt, tB);

          linePositions[vertIdx] = pA.x; linePositions[vertIdx+1] = pA.y; linePositions[vertIdx+2] = pA.z;
          lineColors[vertIdx] = colA.r; lineColors[vertIdx+1] = colA.g; lineColors[vertIdx+2] = colA.b;
          vertIdx += 3;

          linePositions[vertIdx] = pB.x; linePositions[vertIdx+1] = pB.y; linePositions[vertIdx+2] = pB.z;
          lineColors[vertIdx] = colB.r; lineColors[vertIdx+1] = colB.g; lineColors[vertIdx+2] = colB.b;
          vertIdx += 3;
        }
        edgeSegmentMeta.push({ edge: e, segStart: segStart, vertCount: ARC_SEGMENTS * 6, isInter: true });
      } else {
        // Straight line intra-cluster
        linePositions[vertIdx] = e.source.x; linePositions[vertIdx+1] = e.source.y; linePositions[vertIdx+2] = e.source.z;
        lineColors[vertIdx] = cSrc.r; lineColors[vertIdx+1] = cSrc.g; lineColors[vertIdx+2] = cSrc.b;
        vertIdx += 3;

        linePositions[vertIdx] = e.target.x; linePositions[vertIdx+1] = e.target.y; linePositions[vertIdx+2] = e.target.z;
        lineColors[vertIdx] = cTgt.r; lineColors[vertIdx+1] = cTgt.g; lineColors[vertIdx+2] = cTgt.b;
        vertIdx += 3;
        edgeSegmentMeta.push({ edge: e, segStart: segStart, vertCount: 6, isInter: false });
      }
    });

    var lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.BufferAttribute(linePositions, 3));
    lineGeo.setAttribute("color", new THREE.BufferAttribute(lineColors, 3));

    var lineMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.35,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
    lineSegments = new THREE.LineSegments(lineGeo, lineMat);
    scene.add(lineSegments);
  }

  // --- VIEW MODE: 3D on WebGL, or the 2D constellation on a plain canvas ---
  var viewMode = null;
  // A frame is drawn only when something changed, the camera still glides,
  // or the idle spin is on; every input and state change raises this flag.
  var frameDirty = true;
  var cameraMoving = false;
  function requestFrame() { frameDirty = true; }

  var VIEW_NOTES = {
    none: "Vista 2D: este equipo no ofrece WebGL",
    weak: "Vista 2D: la GPU de este equipo no es apropiada para 3D",
    resources: "Vista 2D: memoria o procesador limitados para 3D",
    large: "Vista 2D: grafo grande, la vista 3D cargaría el procesador",
    slow: "Vista 2D: la vista 3D dibujaba a menos de 20 fps en este equipo"
  };

  // Ported from papersmith-ai's atlas viewer. The loop stops scheduling frames
  // entirely while nobody can see the graph: the page is hidden (another
  // browser tab, a minimized window) or the dashboard paused its graph tab
  // with {type: "atlas-control", cmd: "pause"|"resume"}.
  // loop-control:begin
  var pageHidden = !!document.hidden;
  var dashboardPaused = false;
  var paused = pageHidden;
  var looping = false;

  // Called first by every animate() pass: false lets the loop lapse.
  function loopContinues() {
    if (paused) { looping = false; return false; }
    looping = true;
    return true;
  }

  function applyVisibility() {
    paused = pageHidden || dashboardPaused;
    if (paused) return;
    requestFrame();
    if (looping) return;
    looping = true;  // claimed now, so a second resume cannot start a second loop
    requestAnimationFrame(animate);
  }

  function onVisibilityChange() {
    pageHidden = !!document.hidden;
    applyVisibility();
  }

  function onControlMessage(event) {
    if (window.parent === window || event.source !== window.parent) return;
    var data = event.data;
    if (!data || typeof data !== "object" || data.type !== "atlas-control") return;
    if (data.cmd === "pause") dashboardPaused = true;
    else if (data.cmd === "resume") dashboardPaused = false;
    else return;
    applyVisibility();
  }

  // A machine that passed the GPU check can still be too slow for 3D: count
  // frames for 3 s, a second after opening, and fall back to 2D under 20 fps.
  // Only a 3D view the heuristics chose is watched; ?view=3d or a saved choice
  // stays as asked.
  function watchFrameRate() {
    if (viewMode !== "3d" || viewChoice.reason !== "gpu") return false;
    var frames = 0, start = 0;
    var mounted = renderer;
    function count(t) {
      if (renderer !== mounted || viewMode !== "3d" || paused) return;
      if (!start) start = t;
      frames++;
      if (t - start < 3000) { requestAnimationFrame(count); return; }
      if (frames * 1000 / (t - start) < 20) {
        viewChoice = { mode: "2d", reason: "slow" };
        // The 2D view starts still: its spin redraws the whole canvas on the CPU.
        if (autoRotate) toggleAutoRotate();
        setViewMode("2d");
      }
    }
    setTimeout(function() { requestAnimationFrame(count); }, 1000);
    return true;
  }
  // loop-control:end

  function createRenderer(mode, w, h) {
    if (mode === "3d") {
      try {
        var gl = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
        // Never below 1: zoomed-out browsers on large displays report a
        // fractional ratio that shrinks points and lines to a quarter.
        gl.setPixelRatio(Math.min(Math.max(window.devicePixelRatio || 1, 1), 2));
        gl.setSize(w, h);
        return gl;
      } catch (_) {}
    }
    return createCanvas3DRenderer(w, h);
  }

  function setViewMode(mode) {
    var sz = getStageSize();
    if (renderer) {
      if (renderer.domElement && renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
      // Leaving 3D hands the GPU memory and the WebGL context back now,
      // instead of whenever the garbage collector gets to them.
      renderer.dispose();
      if (renderer.forceContextLoss) renderer.forceContextLoss();
    }
    renderer = createRenderer(mode, sz.width, sz.height);
    viewMode = renderer.isCanvas2D ? "2d" : "3d";
    stageEl.insertBefore(renderer.domElement, stageEl.firstChild);
    if (namesEl) stageEl.insertBefore(namesEl, renderer.domElement.nextSibling);
    lastRenderWidth = 0;
    lastRenderHeight = 0;
    onWindowResize();
    updateViewUi();
    requestFrame();
  }

  function updateViewUi() {
    var btn = document.getElementById("btnViewMode");
    if (btn) {
      btn.textContent = viewMode === "3d" ? "◐ Vista 2D" : "◑ Vista 3D";
      btn.disabled = glSupport === "none";
      btn.title = glSupport === "none"
        ? "Este equipo no ofrece WebGL: solo hay vista 2D"
        : (viewMode === "3d" ? "Pasar a la constelación 2D, más liviana" : "Pasar a la constelación 3D (usa la GPU)");
    }
    var note = document.getElementById("viewNote");
    if (note) {
      var text = viewMode === "2d" ? VIEW_NOTES[viewChoice.reason] : "";
      note.textContent = text ? " · " + text : "";
    }
  }

  window.toggleViewMode = function() {
    if (glSupport === "none") return;
    var next = viewMode === "3d" ? "2d" : "3d";
    writePref(VIEW_PREF_KEY, next);
    viewChoice = { mode: next, reason: "user" };
    // The 2D view starts still: its spin redraws the whole canvas on the CPU.
    if (next === "2d" && autoRotate) toggleAutoRotate();
    setViewMode(next);
  };

  // --- CONSTELLATION NAMES: pooled HTML labels over the canvas ---
  var namesOn = readPref(NAMES_PREF_KEY) !== "off";
  var namesEl = null;
  var namePool = [];
  var nameCandidates = [];
  var nameVec = null;

  function buildNameCandidates() {
    var measure = document.createElement("canvas").getContext("2d");
    function width(text, font) {
      if (!measure) return text.length * 7;
      measure.font = font;
      return measure.measureText(text).width;
    }
    var sums = {};
    nodes.forEach(function(n) {
      var s = sums[n.group] || (sums[n.group] = { x: 0, y: 0, z: 0, k: 0 });
      s.x += n.x; s.y += n.y; s.z += n.z; s.k += 1;
    });
    // Community names first, then the most connected nodes
    groups.forEach(function(g) {
      var s = sums[g];
      if (!s) return;
      nameCandidates.push({
        x: s.x / s.k, y: s.y / s.k, z: s.z / s.k, group: g, node: null, text: g, cls: "grp",
        base: 3, degree: s.k, w: width(g, "600 12px sans-serif"), h: 12
      });
    });
    nodes.slice().sort(function(a, b) { return b.neighbors.size - a.neighbors.size; })
      .slice(0, 150)
      .forEach(function(n) {
        var text = n.label.length > 28 ? n.label.slice(0, 27) + "…" : n.label;
        nameCandidates.push({
          x: n.x, y: n.y, z: n.z, group: n.group, node: n, text: text, cls: "",
          base: 0, degree: n.neighbors.size, w: width(text, "11px sans-serif"), h: 11
        });
      });
  }

  function initNames() {
    namesEl = document.createElement("div");
    namesEl.className = "graph-names";
    namesEl.setAttribute("aria-hidden", "true");
    nameVec = new THREE.Vector3();
    buildNameCandidates();
    var btn = document.getElementById("btnNames");
    if (btn) btn.classList.toggle("active", namesOn);
  }

  // Greedy placement by priority (selected, hovered, lit, nearer, more
  // connected) within a budget that grows with the stage area; a name that
  // would leave the stage or touch a placed one is skipped, so zooming in
  // reveals more names.
  function placeNames() {
    if (!namesEl || !camera) return;
    namesEl.classList.toggle("off", !namesOn);
    if (!namesOn) return;
    var w = stageEl.clientWidth;
    var h = stageEl.clientHeight;
    var budget = Math.max(12, Math.floor(w * h / 12000));
    var filtering = Boolean(selectedNode) || clusterFilterOn();
    var items = [];
    nameCandidates.forEach(function(c) {
      var lit;
      if (c.node) {
        lit = selectedNode
          ? (c.node === selectedNode || selectedNode.neighbors.has(c.node.id))
          : (!clusterFilterOn() || clusterLit(c.group));
      } else {
        lit = !selectedNode && (!clusterFilterOn() || clusterLit(c.group));
      }
      if (filtering && !lit) return;
      nameVec.set(c.x, c.y, c.z).project(camera);
      if (nameVec.z < -1 || nameVec.z > 1) return;
      var sx = (nameVec.x * 0.5 + 0.5) * w;
      var sy = (-nameVec.y * 0.5 + 0.5) * h;
      var boost = c.node && c.node === selectedNode ? 4 : (c.node && c.node === hoveredNode ? 3 : 0);
      items.push({ c: c, sx: sx, sy: sy, lit: boost > 0, score: c.base + boost + (lit ? 2 : 0) + (1 - nameVec.z) + c.degree * 0.01 });
    });
    items.sort(function(a, b) { return b.score - a.score; });
    var placed = [];
    for (var i = 0; i < items.length && placed.length < budget; i++) {
      var it = items[i];
      var x = it.sx - it.c.w / 2;
      var y = it.c.node ? it.sy + 9 : it.sy - it.c.h / 2;
      if (x < 2 || y < 2 || x + it.c.w > w - 2 || y + it.c.h > h - 2) continue;
      var box = { x: x, y: y, w: it.c.w, h: it.c.h, it: it };
      var overlaps = placed.some(function(o) {
        return x < o.x + o.w + 6 && o.x < x + box.w + 6 && y < o.y + o.h + 2 && o.y < y + box.h + 2;
      });
      if (!overlaps) placed.push(box);
    }
    placed.forEach(function(box, k) {
      var el = namePool[k];
      if (!el) {
        el = document.createElement("span");
        namesEl.appendChild(el);
        namePool.push(el);
      }
      if (el.textContent !== box.it.c.text) el.textContent = box.it.c.text;
      var cls = "graph-name" + (box.it.c.cls ? " " + box.it.c.cls : "") + (box.it.lit ? " lit" : "");
      if (el.className !== cls) el.className = cls;
      el.style.transform = "translate(" + Math.round(box.x) + "px," + Math.round(box.y) + "px)";
      el.style.display = "";
    });
    for (var k = placed.length; k < namePool.length; k++) namePool[k].style.display = "none";
  }

  window.toggleNames = function() {
    namesOn = !namesOn;
    writePref(NAMES_PREF_KEY, namesOn ? "on" : "off");
    var btn = document.getElementById("btnNames");
    if (btn) btn.classList.toggle("active", namesOn);
    placeNames();
  };

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function projectNodeToScreen(n) {
    if (!camera || !stageEl) return null;
    var w = stageEl.clientWidth || 800;
    var h = stageEl.clientHeight || 600;
    camera.updateMatrixWorld();
    var v = new THREE.Vector3(n.x, n.y, n.z);
    v.project(camera);
    if (v.z < -1 || v.z > 1) return null;
    return {
      sx: (v.x * 0.5 + 0.5) * w,
      sy: (-v.y * 0.5 + 0.5) * h,
      depth: v.z
    };
  }

  function pickNodeAt(mouseX, mouseY) {
    if (!camera || !stageEl) return null;
    var w = stageEl.clientWidth || 800;
    var h = stageEl.clientHeight || 600;
    if (w <= 0 || h <= 0) return null;

    // 1. Direct Three.js raycast against node meshes
    var mouse = new THREE.Vector2(
      (mouseX / w) * 2 - 1,
      -(mouseY / h) * 2 + 1
    );
    var raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(mouse, camera);
    var intersects = viewMode === "3d" ? raycaster.intersectObjects(nodeMeshes) : [];
    if (intersects.length > 0 && intersects[0].object && intersects[0].object.userData) {
      return intersects[0].object.userData.node;
    }

    // 2. Screen-space proximity hit test (covers luminous glow orb & Canvas 2D mode)
    var bestNode = null;
    var bestScore = Infinity;
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      var p = projectNodeToScreen(n);
      if (!p) continue;
      var hitRadius = Math.max(16, n.size * 2.9);
      var dx = p.sx - mouseX;
      var dy = p.sy - mouseY;
      var dist = Math.sqrt(dx * dx + dy * dy);
      if (dist <= hitRadius) {
        var score = dist + p.depth * 1.5;
        if (score < bestScore) {
          bestScore = score;
          bestNode = n;
        }
      }
    }
    return bestNode;
  }

  function renderTooltipForNode(n, sx, sy, isPinned) {
    if (!n || !tooltipEl || !stageEl) return;
    var summaryLine = (n.summary && n.summary !== n.label)
      ? n.summary
      : (n.type + " · " + (n.group || "General"));
    var pinBadge = isPinned
      ? '<span style="font-size:9px; padding:1px 5px; border-radius:4px; background:rgba(0,240,255,0.18); color:var(--cyan); border:1px solid rgba(0,240,255,0.45);">Fijado</span>'
      : '';
    tooltipEl.innerHTML =
      '<div class="tooltip-label">' +
        '<span style="width:8px; height:8px; border-radius:50%; flex:none; background:' + n.color + '; box-shadow:0 0 6px ' + n.color + ';"></span>' +
        '<span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">' + escapeHtml(n.label) + '</span>' +
        pinBadge +
      '</div>' +
      '<div class="tooltip-summary">' + escapeHtml(summaryLine) + '</div>' +
      '<div class="tooltip-meta"><span style="color:var(--cyan);">' + escapeHtml(n.type) + '</span> · ' + escapeHtml(n.group || "General") + ' · ' + n.neighbors.size + ' conex</div>';

    var stageW = stageEl.clientWidth || 800;
    var stageH = stageEl.clientHeight || 600;
    var tipW = Math.min(430, Math.max(240, tooltipEl.offsetWidth || 320));
    var tipH = tooltipEl.offsetHeight || 68;
    var left = Math.max(12, Math.min(sx + 16, stageW - tipW - 14));
    var top = Math.max(12, Math.min(sy + 14, stageH - tipH - 14));
    tooltipEl.style.left = left + "px";
    tooltipEl.style.top = top + "px";
    tooltipEl.style.opacity = 1;
  }

  // Connected Nodes Highlighting Logic
  function updateVisualStates() {
    requestFrame();
    nodes.forEach(function(n) {
      var isConnected = false;
      var isTarget = (selectedNode === n);
      var isHovered = (hoveredNode === n);

      if (selectedNode) {
        isConnected = isTarget || selectedNode.neighbors.has(n.id);
      } else if (clusterFilterOn()) {
        isConnected = clusterLit(n.group);
      } else {
        isConnected = true;
      }

      if (selectedNode) {
        if (isTarget) {
          n.mesh.material.opacity = 1.0;
          n.mesh.scale.setScalar(n.size * 1.5);
          n.sprite.material.opacity = 0.95;
          n.sprite.scale.setScalar(n.size * 8.5);
        } else if (isHovered) {
          n.mesh.material.opacity = 1.0;
          n.mesh.scale.setScalar(n.size * 1.35);
          n.sprite.material.opacity = 0.9;
          n.sprite.scale.setScalar(n.size * 7.2);
        } else if (isConnected) {
          n.mesh.material.opacity = 0.95;
          n.mesh.scale.setScalar(n.size * 1.2);
          n.sprite.material.opacity = 0.8;
          n.sprite.scale.setScalar(n.size * 6.0);
        } else {
          n.mesh.material.opacity = 0.12;
          n.mesh.scale.setScalar(n.size * 0.7);
          n.sprite.material.opacity = 0.05;
          n.sprite.scale.setScalar(n.size * 2.0);
        }
      } else if (clusterFilterOn()) {
        if (isConnected || isHovered) {
          n.mesh.material.opacity = 1.0;
          n.mesh.scale.setScalar(n.size * (isHovered ? 1.4 : 1.25));
          n.sprite.material.opacity = 0.88;
          n.sprite.scale.setScalar(n.size * (isHovered ? 7.4 : 6.5));
        } else {
          n.mesh.material.opacity = 0.14;
          n.mesh.scale.setScalar(n.size * 0.75);
          n.sprite.material.opacity = 0.06;
          n.sprite.scale.setScalar(n.size * 2.0);
        }
      } else {
        // Default Luminous State
        n.mesh.material.opacity = isHovered ? 1.0 : 0.95;
        n.mesh.scale.setScalar(n.size * (isHovered ? 1.35 : 1.0));
        n.sprite.material.opacity = isHovered ? 0.92 : 0.72;
        n.sprite.scale.setScalar(n.size * (isHovered ? 7.2 : 5.4));
      }
    });

    // Update Edges Opacity and Luminosity
    if (lineSegments && edgeSegmentMeta) {
      var colorsAttr = lineSegments.geometry.attributes.color;
      var cArr = colorsAttr.array;

      edgeSegmentMeta.forEach(function(meta) {
        var e = meta.edge;
        var activeEdge = false;

        if (selectedNode) {
          activeEdge = (e.source === selectedNode || e.target === selectedNode);
        } else if (clusterFilterOn()) {
          activeEdge = (clusterLit(e.source.group) && clusterLit(e.target.group));
        } else {
          activeEdge = true;
        }

        var colSrc = new THREE.Color(e.source.color);
        var colTgt = new THREE.Color(e.target.color);

        if (selectedNode) {
          if (activeEdge) {
            colSrc = new THREE.Color(0x38bdf8); // Glowing celestial beam
            colTgt = new THREE.Color(0x818cf8);
          } else {
            colSrc = new THREE.Color(0x0a0f1d); // Dimmed into space
            colTgt = new THREE.Color(0x0a0f1d);
          }
        } else if (clusterFilterOn()) {
          if (!activeEdge) {
            colSrc = new THREE.Color(0x0a0f1d);
            colTgt = new THREE.Color(0x0a0f1d);
          }
        }

        for (var vi = 0; vi < meta.vertCount; vi += 6) {
          var vBase = meta.segStart + vi;
          var tA = vi / meta.vertCount;
          var tB = (vi + 3) / meta.vertCount;
          var cA = colSrc.clone().lerp(colTgt, tA);
          var cB = colSrc.clone().lerp(colTgt, tB);

          cArr[vBase] = cA.r; cArr[vBase+1] = cA.g; cArr[vBase+2] = cA.b;
          cArr[vBase+3] = cB.r; cArr[vBase+4] = cB.g; cArr[vBase+5] = cB.b;
        }
      });
      colorsAttr.needsUpdate = true;
      lineSegments.material.opacity = selectedNode ? 0.95 : 0.35;
    }
  }

  // Inspector Card UI Rendering
  function showInspector(n) {
    selectedNode = n;
    inspectorCard.style.display = "flex";
    document.getElementById("inspTitle").textContent = n.label;
    var summaryEl = document.getElementById("inspSummary");
    if (summaryEl) {
      var summaryLine = (n.summary && n.summary !== n.label)
        ? n.summary
        : (n.type + " · " + (n.group || "General"));
      summaryEl.textContent = summaryLine;
      summaryEl.title = summaryLine;
    }
    document.getElementById("inspType").textContent = n.type;
    document.getElementById("inspGroup").innerHTML = '<span style="width:8px; height:8px; border-radius:50%; background:' + n.color + '; box-shadow:0 0 6px ' + n.color + '"></span> ' + (n.group || "General");

    var neighList = Array.from(n.neighbors).map(function(nid) { return byId[nid]; }).filter(Boolean);
    document.getElementById("inspNeighborsCount").textContent = "Conexiones Directas (" + neighList.length + ")";

    var container = document.getElementById("inspNeighborsList");
    container.innerHTML = "";
    neighList.forEach(function(neighbor) {
      var chip = document.createElement("div");
      chip.className = "neighbor-chip";
      chip.title = neighbor.label + (neighbor.summary ? " — " + neighbor.summary : "");
      chip.innerHTML = '<span>' + escapeHtml(neighbor.label.slice(0, 36) + (neighbor.label.length > 36 ? "…" : "")) + '</span><span style="font-size:10px; color:var(--cyan);">' + escapeHtml(neighbor.type) + '</span>';
      chip.onclick = function() {
        focusNodeById(neighbor.id);
      };
      container.appendChild(chip);
    });

    var p = projectNodeToScreen(n);
    if (p) {
      renderTooltipForNode(n, p.sx, p.sy, true);
    }

    updateVisualStates();
  }

  window.clearSelection = function() {
    selectedNode = null;
    inspectorCard.style.display = "none";
    if (!hoveredNode && tooltipEl) {
      tooltipEl.style.opacity = 0;
    }
    updateVisualStates();
  };

  window.focusNodeById = function(nodeId) {
    var target = byId[nodeId];
    if (target) {
      showInspector(target);
      focusCameraOnSelected();
    }
  };

  window.focusCameraOnSelected = function() {
    if (!selectedNode || !camera) return;
    cameraTouched = true;
    targetOrbitCenter = { x: selectedNode.x, y: selectedNode.y, z: selectedNode.z };
    targetRadius = Math.max(fitRadius * 0.3, 140);
  };

  // 3D Camera Controls (Orbit & Pan). The camera always sits on a sphere
  // around orbitCenter; focus, reset and fit animate radius and center only,
  // so orbit, zoom and auto-rotate keep working after any of them.
  var isDragging = false;
  var isRightDrag = false;
  var dragDistancePx = 0;
  var previousMousePos = { x: 0, y: 0 };
  var spherical = { radius: 680, theta: 0, phi: Math.PI / 2 - 0.15 };
  var orbitCenter = { x: 0, y: 0, z: 0 };
  var targetOrbitCenter = null;
  var targetRadius = null;
  var fitRadius = 680;
  var cameraTouched = false;

  function isOverHud(target) {
    return Boolean(target && target.closest && (target.closest("#inspectorCard") || target.closest(".hud-overlay")));
  }

  // Frame the graph, whatever its size or the iframe shape: the smallest
  // orbit distance at which nodes project inside the view, checked at eight
  // orbit angles so auto-rotate does not carry them out. It frames the 95th
  // percentile, so a couple of isolated notes cannot shrink the whole graph.
  function fitCameraToGraph() {
    if (!camera || !nodes.length) return;
    var cx = 0, cy = 0, cz = 0;
    nodes.forEach(function(n) { cx += n.x; cy += n.y; cz += n.z; });
    cx /= nodes.length; cy /= nodes.length; cz /= nodes.length;
    var tanV = Math.tan(camera.fov * Math.PI / 360);
    var tanH = tanV * camera.aspect;
    var phi = spherical.phi;
    var need = nodes.map(function() { return 60; });
    for (var k = 0; k < 8; k++) {
      var th = spherical.theta + k * Math.PI / 4;
      // Unit vector from the orbit center to the camera, and the screen axes
      var d = { x: Math.sin(phi) * Math.sin(th), y: Math.cos(phi), z: Math.sin(phi) * Math.cos(th) };
      var right = { x: Math.cos(th), y: 0, z: -Math.sin(th) };
      var up = {
        x: d.y * right.z - d.z * right.y,
        y: d.z * right.x - d.x * right.z,
        z: d.x * right.y - d.y * right.x
      };
      nodes.forEach(function(n, i) {
        var px = n.x - cx, py = n.y - cy, pz = n.z - cz;
        var pad = (n.size || 4) * 2;
        var toward = px * d.x + py * d.y + pz * d.z;
        var sx = Math.abs(px * right.x + py * right.y + pz * right.z) + pad;
        var sy = Math.abs(px * up.x + py * up.y + pz * up.z) + pad;
        need[i] = Math.max(need[i], toward + sx / tanH, toward + sy / tanV);
      });
    }
    need.sort(function(a, b) { return a - b; });
    var dist = need[Math.min(need.length - 1, Math.floor(need.length * 0.95))] * 1.08;
    fitRadius = dist;
    camera.far = Math.max(4500, dist * 4);
    camera.updateProjectionMatrix();
    if (scene && scene.fog) scene.fog.density = 0.35 / dist;
    targetOrbitCenter = { x: cx, y: cy, z: cz };
    targetRadius = dist;
  }

  function clampRadius(r) {
    return Math.max(fitRadius * 0.08, Math.min(fitRadius * 3, r));
  }

  function endDrag(e) {
    if (!isDragging) return;
    isDragging = false;
    stageEl.classList.remove("dragging");
    if (e && e.pointerId !== undefined && stageEl.hasPointerCapture && stageEl.hasPointerCapture(e.pointerId)) {
      try { stageEl.releasePointerCapture(e.pointerId); } catch (_) {}
    }
  }

  function hideHover() {
    if (!hoveredNode) return;
    hoveredNode = null;
    if (selectedNode) {
      var sp = projectNodeToScreen(selectedNode);
      if (sp) renderTooltipForNode(selectedNode, sp.sx, sp.sy, true);
    } else if (tooltipEl) {
      tooltipEl.style.opacity = 0;
    }
    updateVisualStates();
  }

  stageEl.addEventListener("pointerdown", function(e) {
    if (isOverHud(e.target)) return;
    if (e.pointerType === "mouse" && e.button !== 0 && e.button !== 2) return;
    isDragging = true;
    dragDistancePx = 0;
    isRightDrag = (e.button === 2 || e.shiftKey);
    previousMousePos = { x: e.clientX, y: e.clientY };
    stageEl.classList.add("dragging");
    // Capture keeps the drag alive, and lets it end, when the pointer is
    // released outside the stage or outside the dashboard iframe.
    try { stageEl.setPointerCapture(e.pointerId); } catch (_) {}
  });

  stageEl.addEventListener("pointerup", endDrag);
  stageEl.addEventListener("pointercancel", endDrag);
  stageEl.addEventListener("lostpointercapture", endDrag);
  stageEl.addEventListener("pointerleave", function() {
    if (!isDragging) hideHover();
  });

  stageEl.addEventListener("pointermove", function(e) {
    var rect = stageEl.getBoundingClientRect();
    var mouseX = e.clientX - rect.left;
    var mouseY = e.clientY - rect.top;

    if (isDragging) {
      var deltaX = e.clientX - previousMousePos.x;
      var deltaY = e.clientY - previousMousePos.y;
      dragDistancePx += Math.abs(deltaX) + Math.abs(deltaY);

      if (isRightDrag) {
        // Pan
        var panSpeed = spherical.radius * 0.0012;
        orbitCenter.x -= deltaX * panSpeed;
        orbitCenter.y += deltaY * panSpeed;
      } else {
        // Orbit
        spherical.theta -= deltaX * 0.006;
        spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi + deltaY * 0.006));
      }
      previousMousePos = { x: e.clientX, y: e.clientY };
      if (dragDistancePx > 2) {
        cameraTouched = true;
        targetOrbitCenter = null;
        targetRadius = null;
      }
      return;
    }

    // Nodes behind the legend or the inspector are not hoverable through them
    if (isOverHud(e.target)) {
      hideHover();
      stageEl.style.cursor = "";
      return;
    }

    // Hover node detection (3D raycast + 2D screen-space orb hit test)
    if (camera && renderer) {
      var hitNode = pickNodeAt(mouseX, mouseY);
      if (hitNode) {
        var changed = (hitNode !== hoveredNode);
        hoveredNode = hitNode;
        stageEl.style.cursor = "pointer";
        renderTooltipForNode(hitNode, mouseX, mouseY, selectedNode === hitNode);
        if (changed) updateVisualStates();
      } else {
        var hadHover = Boolean(hoveredNode);
        hoveredNode = null;
        stageEl.style.cursor = isDragging ? "grabbing" : "grab";
        if (selectedNode) {
          var sp = projectNodeToScreen(selectedNode);
          if (sp) renderTooltipForNode(selectedNode, sp.sx, sp.sy, true);
        } else {
          tooltipEl.style.opacity = 0;
        }
        if (hadHover) updateVisualStates();
      }
    }
  });

  stageEl.addEventListener("contextmenu", function(e) { e.preventDefault(); });

  stageEl.addEventListener("wheel", function(e) {
    if (isOverHud(e.target)) return;
    e.preventDefault();
    cameraTouched = true;
    // Exponential steps feel the same at any distance; trackpad pinch
    // arrives as ctrl+wheel with small deltas, so it gets a larger gain.
    var gain = e.ctrlKey ? 0.01 : 0.0015;
    var base = targetRadius !== null ? targetRadius : spherical.radius;
    targetRadius = clampRadius(base * Math.exp(e.deltaY * gain));
  }, { passive: false });

  stageEl.addEventListener("dblclick", function(e) {
    if (isOverHud(e.target)) return;
    var rect = stageEl.getBoundingClientRect();
    var hitNode = pickNodeAt(e.clientX - rect.left, e.clientY - rect.top);
    if (hitNode) {
      showInspector(hitNode);
      focusCameraOnSelected();
    }
  });

  stageEl.addEventListener("click", function(e) {
    if (e.target.closest("#inspectorCard") || e.target.closest(".hud-overlay") || e.target.closest("header")) return;
    if (dragDistancePx > 6) return;
    var rect = stageEl.getBoundingClientRect();
    var mouseX = e.clientX - rect.left;
    var mouseY = e.clientY - rect.top;

    var hitNode = pickNodeAt(mouseX, mouseY);
    if (hitNode) {
      showInspector(hitNode);
      renderTooltipForNode(hitNode, mouseX, mouseY, true);
    } else {
      clearSelection();
    }
  });

  window.toggleAutoRotate = function() {
    autoRotate = !autoRotate;
    document.getElementById("btnAutoRotate").classList.toggle("active", autoRotate);
  };

  window.resetCamera = function() {
    cameraTouched = false;
    spherical.phi = Math.PI / 2 - 0.15;
    clearSelection();
    fitCameraToGraph();
  };

  window.handleSearch = function(query) {
    var q = query.trim().toLowerCase();
    if (!q) {
      clearSelection();
      return;
    }
    var found = nodes.find(function(n) {
      return n.label.toLowerCase().indexOf(q) >= 0 ||
             n.id.toLowerCase().indexOf(q) >= 0 ||
             (n.summary && n.summary.toLowerCase().indexOf(q) >= 0);
    });
    if (found) {
      showInspector(found);
    }
  };

  window.toggleSidebar = function() {
    var drawer = document.getElementById("sideDrawer");
    var btn = document.getElementById("btnToggleSide");
    var isCollapsed = drawer.classList.toggle("collapsed");
    if (btn) btn.classList.toggle("active", !isCollapsed);
    setTimeout(onWindowResize, 60);
    setTimeout(onWindowResize, 160);
    setTimeout(onWindowResize, 300);
  };

  var lastRenderWidth = 0;
  var lastRenderHeight = 0;

  function onWindowResize() {
    if (!camera || !renderer || !stageEl) return;
    var width = stageEl.clientWidth;
    var height = stageEl.clientHeight;
    if (width <= 0 || height <= 0) return;
    if (width === lastRenderWidth && height === lastRenderHeight) return;
    lastRenderWidth = width;
    lastRenderHeight = height;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
    requestFrame();
    // The dashboard iframe changes shape with the tab and the side panel;
    // keep the whole graph framed until the user takes the camera.
    if (!cameraTouched) fitCameraToGraph();
  }

  window.addEventListener("resize", onWindowResize);
  if (typeof ResizeObserver !== "undefined" && stageEl) {
    try {
      var stageObserver = new ResizeObserver(function() {
        onWindowResize();
      });
      stageObserver.observe(stageEl);
    } catch (_) {}
  }

  // Animation Loop with Smooth Damping and Pulse
  var clock = new THREE.Clock();

  // Last frame drawn, in seconds of the clock; idle auto-rotation draws at 30 fps.
  var lastFrameAt = -1;
  var IDLE_FRAME_SEC = 1 / 30;

  function animate() {
    if (!loopContinues()) return;
    requestAnimationFrame(animate);

    // Nothing to draw while the page, or the dashboard tab holding the graph, is hidden.
    if (document.hidden || !stageEl || stageEl.clientWidth === 0 || stageEl.clientHeight === 0) {
      return;
    }
    if (stageEl.clientWidth !== lastRenderWidth || stageEl.clientHeight !== lastRenderHeight) {
      onWindowResize();
    }

    var time = clock.getElapsedTime();
    // Interaction and camera moves keep the full frame rate; the slow idle spin
    // looks the same at 30 fps and costs half the GPU work.
    var busy = isDragging || hoveredNode || selectedNode || targetOrbitCenter || targetRadius !== null;
    // A still view draws nothing: no spin, no glide, no drag and no change.
    // The selected node only breathes in 3D, where the GPU does the work.
    var gliding = isDragging || targetOrbitCenter || targetRadius !== null || (selectedNode && viewMode === "3d");
    if (!autoRotate && !frameDirty && !cameraMoving && !gliding) {
      return;
    }
    if (!busy && lastFrameAt >= 0 && time - lastFrameAt < IDLE_FRAME_SEC) {
      return;
    }
    var spin = lastFrameAt >= 0 ? Math.min(time - lastFrameAt, 0.1) * 60 : 1;
    lastFrameAt = time;

    // Pause the spin while a node is hovered so it stays under the cursor
    if (autoRotate && !isDragging && !selectedNode && !hoveredNode) {
      spherical.theta += 0.0035 * spin;  // same angular speed at any frame rate
    }

    // Camera smoothing toward focus / fit targets
    if (targetOrbitCenter) {
      orbitCenter.x += (targetOrbitCenter.x - orbitCenter.x) * 0.1;
      orbitCenter.y += (targetOrbitCenter.y - orbitCenter.y) * 0.1;
      orbitCenter.z += (targetOrbitCenter.z - orbitCenter.z) * 0.1;
      if (Math.abs(targetOrbitCenter.x - orbitCenter.x) + Math.abs(targetOrbitCenter.y - orbitCenter.y) + Math.abs(targetOrbitCenter.z - orbitCenter.z) < 0.5) {
        targetOrbitCenter = null;
      }
    }
    if (targetRadius !== null) {
      spherical.radius += (targetRadius - spherical.radius) * 0.12;
      if (Math.abs(targetRadius - spherical.radius) < 0.5) {
        spherical.radius = targetRadius;
        targetRadius = null;
      }
    }

    var cx = orbitCenter.x + spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
    var cy = orbitCenter.y + spherical.radius * Math.cos(spherical.phi);
    var cz = orbitCenter.z + spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);

    camera.position.x += (cx - camera.position.x) * 0.2;
    camera.position.y += (cy - camera.position.y) * 0.2;
    camera.position.z += (cz - camera.position.z) * 0.2;
    cameraMoving = Math.abs(cx - camera.position.x) + Math.abs(cy - camera.position.y) + Math.abs(cz - camera.position.z) > 0.05;
    camera.lookAt(orbitCenter.x, orbitCenter.y, orbitCenter.z);

    // Luminous Breathing Effect for Nodes
    nodes.forEach(function(n) {
      if (n.sprite) {
        var pulse = Math.sin(time * 2.5 + n.x * 0.05) * 0.4;
        if (selectedNode === n) {
          n.sprite.scale.setScalar(n.size * 8.5 + pulse * 1.5);
        }
      }
    });

    if (selectedNode && !hoveredNode) {
      var sp = projectNodeToScreen(selectedNode);
      if (sp) {
        renderTooltipForNode(selectedNode, sp.sx, sp.sy, true);
      }
    }

    renderer.render(scene, camera);
    frameDirty = false;
    placeNames();
  }

  // Initialize
  if (typeof THREE !== "undefined") {
    initThree();
    initNames();
    if (viewChoice.mode === "2d") autoRotate = false;
    setViewMode(viewChoice.mode);
    // Any pointer, wheel or key input may move the camera or the hover state
    ["pointerdown", "pointermove", "pointerup", "wheel", "click", "dblclick"].forEach(function(type) {
      stageEl.addEventListener(type, requestFrame, { passive: true, capture: true });
    });
    window.addEventListener("keydown", requestFrame);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("message", onControlMessage);
    fitCameraToGraph();
    // Start framed instead of flying in from a fixed distance
    if (targetOrbitCenter) { orbitCenter = targetOrbitCenter; targetOrbitCenter = null; }
    if (targetRadius !== null) { spherical.radius = targetRadius; targetRadius = null; }
    animate();
    watchFrameRate();
    document.getElementById("btnAutoRotate").classList.toggle("active", autoRotate);
  } else {
    stageEl.innerHTML = '<div style="color:var(--cyan); padding:40px; text-align:center;">Cargando motor 3D...</div>';
  }

})();
</script>
</body>
</html>
"""


# three.js r128 vendorizado. Antes el template lo cargaba desde un CDN y prometía
# un «fallback interno» que nunca existió: sin red, el grafo no se dibujaba.
THREE_BUNDLE = pathlib.Path(__file__).resolve().parent / "assets" / "three-r128.min.js"


def _three_bundle() -> str:
    """Devuelve el bundle listo para empotrar.

    Falla con un mensaje claro si el activo no está, en lugar de generar un HTML
    que dependa de la red sin decirlo.
    """
    if not THREE_BUNDLE.is_file():
        raise SystemExit(
            f"Falta el activo vendorizado {THREE_BUNDLE}. Sin él el grafo se\n"
            "generaría dependiendo de la red. Restáuralo antes de continuar."
        )
    text = THREE_BUNDLE.read_text(encoding="utf-8")
    if "</script" in text.lower():
        raise SystemExit(
            "El bundle contiene '</script' y no puede empotrarse sin romper el HTML."
        )
    return text


def build_html(data: dict) -> str:
    idx = data["index"]
    fresh = f" · frescura: {esc(idx['freshness'])}" if idx.get("freshness") else ""
    out = TEMPLATE
    out = out.replace("__TITLE__", esc(data["title"]))
    out = out.replace("__PROJECT__", esc(idx.get("project") or data["corpus"]))
    out = out.replace("__NODES__", str(idx["nodes"]))
    out = out.replace("__EDGES__", str(idx["edges"]))
    out = out.replace("__FRESH__", fresh)
    out = out.replace("__CENTRAL__", render_central(data))
    out = out.replace("__COMMUNITIES__", render_communities(data))
    out = out.replace("__QUESTIONS__", render_questions(data))
    out = out.replace("__PAYLOAD__", render_payload(data))
    out = out.replace("__PALETTE__", json.dumps(PALETTE))
    out = out.replace("__THREE_BUNDLE__", _three_bundle())
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        sys.stderr.write(__doc__)
        return 2 if len(argv) < 2 else 0

    src = pathlib.Path(argv[1])
    if not src.is_file():
        sys.stderr.write(f"error: no such input file: {src}\n")
        return 1
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"error: invalid JSON in {src}: {exc}\n")
        return 1

    dst = pathlib.Path(argv[2]) if len(argv) > 2 else default_output_path(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(build_html(normalise(data)), encoding="utf-8")
    print(f"wrote: {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
