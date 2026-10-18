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
  body {
    margin: 0;
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
    flex: 1;
    position: relative;
    overflow: hidden;
    width: 100%;
    height: 100%;
  }
  #stage3d {
    flex: 1 1 0%;
    min-width: 0;
    position: relative;
    cursor: grab;
    overflow: hidden;
  }
  #stage3d.dragging { cursor: grabbing; }
  #stage3d canvas { display: block; }

  /* 3D HUD overlay */
  .hud-overlay {
    position: absolute;
    top: 14px;
    left: 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    pointer-events: none;
    z-index: 5;
  }
  .hud-pill {
    pointer-events: auto;
    background: var(--panel-bg);
    backdrop-filter: blur(8px);
    border: 1px solid var(--panel-border);
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 11px;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
  }
  .hud-cluster-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    max-width: 480px;
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
    width: 380px;
    max-height: 480px;
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
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
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
    background: rgba(11, 15, 28, 0.95);
    border: 1px solid var(--cyan);
    color: #fff;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 11px;
    opacity: 0;
    transition: opacity 0.1s;
    z-index: 20;
    max-width: 320px;
    box-shadow: 0 0 15px rgba(0, 240, 255, 0.3);
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
    </div>
  </div>

  <div class="header-actions">
    <div class="search-box">
      <input type="text" id="searchInput" placeholder="Buscar paper, archivo, nodo..." oninput="handleSearch(this.value)">
    </div>
    <button class="btn-hud" id="btnAutoRotate" onclick="toggleAutoRotate()">⟳ Auto-Giro</button>
    <button class="btn-hud" onclick="resetCamera()">🎯 Centrar</button>
    <button class="btn-hud active" id="btnToggleSide" onclick="toggleSidebar()" title="Mostrar/ocultar panel de métricas">▤ Panel Datos</button>
  </div>
</header>

<div class="viewport-wrap">
  <div id="stage3d">
    <div class="hud-overlay">
      <div class="hud-pill">
        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--cyan); box-shadow:0 0 6px var(--cyan);"></span>
        <span>Haz clic en un nodo para <strong>resaltar sus conexiones</strong>. Arrastra para orbitar en 3D.</span>
      </div>
      <div class="hud-cluster-tags" id="clusterFilterTags">
        <!-- Rendered by JS -->
      </div>
    </div>

    <!-- Inspector HUD Card -->
    <div class="inspector-card" id="inspectorCard">
      <div class="inspector-header">
        <div class="inspector-title" id="inspTitle">—</div>
        <button class="inspector-close" onclick="clearSelection()">&times;</button>
      </div>
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
    var nodeObj = {
      id: n.id,
      label: n.label || n.id,
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

    // 3D Relaxation Simulation to settle nodes into celestial balance
    for (var it = 0; it < 160; it++) {
      var cool = 1 - it / 160;
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

  // Procedural Glowing Texture Generator for Luminous Orbs
  function createGlowTexture(colorHex) {
    var canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    var ctx = canvas.getContext("2d");
    var grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, "#ffffff");
    grad.addColorStop(0.2, colorHex);
    grad.addColorStop(0.55, colorHex);
    grad.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(32, 32, 32, 0, Math.PI * 2);
    ctx.fill();
    return new THREE.CanvasTexture(canvas);
  }

  // State Management
  var selectedNode = null;
  var hoveredNode = null;
  var autoRotate = true;
  var activeClusterFilter = null;

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
      tag.onclick = function() {
        if (activeClusterFilter === g) {
          activeClusterFilter = null;
          tag.classList.remove("active");
        } else {
          document.querySelectorAll(".cluster-tag").forEach(function(t) { t.classList.remove("active"); });
          activeClusterFilter = g;
          tag.classList.add("active");
        }
        updateVisualStates();
      };
      clusterTagsEl.appendChild(tag);
    });
  }

  // --- THREE.JS 3D SCENE SETUP (SOTA ATLAS CELESTIAL SKY) ---
  var scene, camera, renderer;
  var nodeMeshes = [];
  var nodeGlowSprites = [];
  var lineSegments;
  var linePositions, lineColors;
  var edgeSegmentMeta = [];

  function initThree() {
    var width = stageEl.clientWidth || window.innerWidth - 360;
    var height = stageEl.clientHeight || window.innerHeight - 60;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x070a13);
    scene.fog = new THREE.FogExp2(0x070a13, 0.00045);

    camera = new THREE.PerspectiveCamera(52, width / height, 1, 4500);
    camera.position.set(0, 120, 750);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    stageEl.appendChild(renderer.domElement);

    // Subtle 3D Starfield particles (celestial dust)
    var starGeo = new THREE.BufferGeometry();
    var starCount = 450;
    var starPos = new Float32Array(starCount * 3);
    for (var s = 0; s < starCount * 3; s += 3) {
      starPos[s] = (Math.random() - 0.5) * 2400;
      starPos[s+1] = (Math.random() - 0.5) * 2400;
      starPos[s+2] = (Math.random() - 0.5) * 2400;
    }
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    var starMat = new THREE.PointsMaterial({ color: 0x93c5fd, size: 2.2, transparent: true, opacity: 0.5 });
    var stars = new THREE.Points(starGeo, starMat);
    scene.add(stars);

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
    var sphereGeo = new THREE.SphereGeometry(1, 24, 24);

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
      var glowTex = createGlowTexture(n.color);
      var glowMat = new THREE.SpriteMaterial({
        map: glowTex,
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
      blending: THREE.AdditiveBlending
    });
    lineSegments = new THREE.LineSegments(lineGeo, lineMat);
    scene.add(lineSegments);
  }

  // Connected Nodes Highlighting Logic
  function updateVisualStates() {
    nodes.forEach(function(n) {
      var isConnected = false;
      var isTarget = (selectedNode === n);

      if (selectedNode) {
        isConnected = isTarget || selectedNode.neighbors.has(n.id);
      } else if (activeClusterFilter) {
        isConnected = (n.group === activeClusterFilter);
      } else {
        isConnected = true;
      }

      if (selectedNode) {
        if (isTarget) {
          n.mesh.material.opacity = 1.0;
          n.mesh.scale.setScalar(n.size * 1.5);
          n.sprite.material.opacity = 0.95;
          n.sprite.scale.setScalar(n.size * 8.5);
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
      } else if (activeClusterFilter) {
        if (isConnected) {
          n.mesh.material.opacity = 1.0;
          n.mesh.scale.setScalar(n.size * 1.25);
          n.sprite.material.opacity = 0.85;
          n.sprite.scale.setScalar(n.size * 6.5);
        } else {
          n.mesh.material.opacity = 0.14;
          n.mesh.scale.setScalar(n.size * 0.75);
          n.sprite.material.opacity = 0.06;
          n.sprite.scale.setScalar(n.size * 2.0);
        }
      } else {
        // Default Luminous State
        n.mesh.material.opacity = 0.95;
        n.mesh.scale.setScalar(n.size);
        n.sprite.material.opacity = 0.72;
        n.sprite.scale.setScalar(n.size * 5.4);
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
        } else if (activeClusterFilter) {
          activeEdge = (e.source.group === activeClusterFilter && e.target.group === activeClusterFilter);
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
        } else if (activeClusterFilter) {
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
    document.getElementById("inspType").textContent = n.type;
    document.getElementById("inspGroup").innerHTML = '<span style="width:8px; height:8px; border-radius:50%; background:' + n.color + '; box-shadow:0 0 6px ' + n.color + '"></span> ' + (n.group || "General");

    var neighList = Array.from(n.neighbors).map(function(nid) { return byId[nid]; }).filter(Boolean);
    document.getElementById("inspNeighborsCount").textContent = "Conexiones Directas (" + neighList.length + ")";

    var container = document.getElementById("inspNeighborsList");
    container.innerHTML = "";
    neighList.forEach(function(neighbor) {
      var chip = document.createElement("div");
      chip.className = "neighbor-chip";
      chip.innerHTML = '<span>' + neighbor.label.slice(0, 36) + (neighbor.label.length > 36 ? "…" : "") + '</span><span style="font-size:10px; color:var(--cyan);">' + neighbor.type + '</span>';
      chip.onclick = function() {
        focusNodeById(neighbor.id);
      };
      container.appendChild(chip);
    });

    updateVisualStates();
  }

  window.clearSelection = function() {
    selectedNode = null;
    inspectorCard.style.display = "none";
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
    targetCamPos = {
      x: selectedNode.x * 1.2,
      y: selectedNode.y * 1.2 + 30,
      z: selectedNode.z + 280
    };
    targetOrbitCenter = {
      x: selectedNode.x,
      y: selectedNode.y,
      z: selectedNode.z
    };
  };

  // 3D Camera Controls (Orbit & Pan)
  var isDragging = false;
  var isRightDrag = false;
  var previousMousePos = { x: 0, y: 0 };
  var spherical = { radius: 680, theta: 0, phi: Math.PI / 2 };
  var orbitCenter = { x: 0, y: 0, z: 0 };
  var targetCamPos = null;
  var targetOrbitCenter = null;

  stageEl.addEventListener("mousedown", function(e) {
    if (e.target.closest("#inspectorCard") || e.target.closest(".hud-overlay")) return;
    isDragging = true;
    isRightDrag = (e.button === 2 || e.shiftKey);
    previousMousePos = { x: e.clientX, y: e.clientY };
    stageEl.classList.add("dragging");
  });

  window.addEventListener("mousemove", function(e) {
    var rect = stageEl.getBoundingClientRect();
    var mouseX = e.clientX - rect.left;
    var mouseY = e.clientY - rect.top;

    if (isDragging) {
      var deltaX = e.clientX - previousMousePos.x;
      var deltaY = e.clientY - previousMousePos.y;

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
      targetCamPos = null;
      return;
    }

    // Raycast on hover
    if (camera && renderer) {
      var mouse = new THREE.Vector2(
        (mouseX / stageEl.clientWidth) * 2 - 1,
        -(mouseY / stageEl.clientHeight) * 2 + 1
      );
      var raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(mouse, camera);
      var intersects = raycaster.intersectObjects(nodeMeshes);

      if (intersects.length > 0) {
        var hitNode = intersects[0].object.userData.node;
        if (hitNode !== hoveredNode) {
          hoveredNode = hitNode;
          tooltipEl.innerHTML = '<strong>' + hitNode.label + '</strong><br><span style="color:var(--cyan);">' + hitNode.type + '</span> · ' + hitNode.group + ' (' + hitNode.neighbors.size + ' conex)';
          tooltipEl.style.left = Math.min(mouseX + 15, stageEl.clientWidth - 260) + "px";
          tooltipEl.style.top = (mouseY + 15) + "px";
          tooltipEl.style.opacity = 1;
        }
      } else {
        hoveredNode = null;
        tooltipEl.style.opacity = 0;
      }
    }
  });

  window.addEventListener("mouseup", function() {
    isDragging = false;
    stageEl.classList.remove("dragging");
  });

  stageEl.addEventListener("contextmenu", function(e) { e.preventDefault(); });

  stageEl.addEventListener("wheel", function(e) {
    e.preventDefault();
    spherical.radius = Math.max(100, Math.min(1800, spherical.radius + e.deltaY * 0.7));
    targetCamPos = null;
  }, { passive: false });

  stageEl.addEventListener("click", function(e) {
    if (e.target.closest("#inspectorCard") || e.target.closest(".hud-overlay") || e.target.closest("header")) return;
    var rect = stageEl.getBoundingClientRect();
    var mouseX = e.clientX - rect.left;
    var mouseY = e.clientY - rect.top;

    var mouse = new THREE.Vector2(
      (mouseX / stageEl.clientWidth) * 2 - 1,
      -(mouseY / stageEl.clientHeight) * 2 + 1
    );
    var raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(mouse, camera);
    var intersects = raycaster.intersectObjects(nodeMeshes);

    if (intersects.length > 0) {
      var hitNode = intersects[0].object.userData.node;
      showInspector(hitNode);
    } else {
      clearSelection();
    }
  });

  window.toggleAutoRotate = function() {
    autoRotate = !autoRotate;
    document.getElementById("btnAutoRotate").classList.toggle("active", autoRotate);
  };

  window.resetCamera = function() {
    targetCamPos = { x: 0, y: 80, z: 680 };
    targetOrbitCenter = { x: 0, y: 0, z: 0 };
    spherical = { radius: 680, theta: 0, phi: Math.PI / 2 };
    clearSelection();
  };

  window.handleSearch = function(query) {
    var q = query.trim().toLowerCase();
    if (!q) {
      clearSelection();
      return;
    }
    var found = nodes.find(function(n) {
      return n.label.toLowerCase().indexOf(q) >= 0 || n.id.toLowerCase().indexOf(q) >= 0;
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

  function onWindowResize() {
    if (!camera || !renderer || !stageEl) return;
    var width = stageEl.clientWidth;
    var height = stageEl.clientHeight;
    if (width <= 0 || height <= 0) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }

  window.addEventListener("resize", onWindowResize);

  // Animation Loop with Smooth Damping and Pulse
  var clock = new THREE.Clock();

  function animate() {
    requestAnimationFrame(animate);

    var delta = clock.getDelta();
    var time = clock.getElapsedTime();

    if (autoRotate && !isDragging && !selectedNode) {
      spherical.theta += 0.0035;
    }

    // Camera smoothing
    if (targetCamPos && targetOrbitCenter) {
      camera.position.x += (targetCamPos.x - camera.position.x) * 0.08;
      camera.position.y += (targetCamPos.y - camera.position.y) * 0.08;
      camera.position.z += (targetCamPos.z - camera.position.z) * 0.08;
      orbitCenter.x += (targetOrbitCenter.x - orbitCenter.x) * 0.08;
      orbitCenter.y += (targetOrbitCenter.y - orbitCenter.y) * 0.08;
      orbitCenter.z += (targetOrbitCenter.z - orbitCenter.z) * 0.08;
      camera.lookAt(orbitCenter.x, orbitCenter.y, orbitCenter.z);
    } else {
      var cx = orbitCenter.x + spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
      var cy = orbitCenter.y + spherical.radius * Math.cos(spherical.phi);
      var cz = orbitCenter.z + spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);

      camera.position.x += (cx - camera.position.x) * 0.12;
      camera.position.y += (cy - camera.position.y) * 0.12;
      camera.position.z += (cz - camera.position.z) * 0.12;
      camera.lookAt(orbitCenter.x, orbitCenter.y, orbitCenter.z);
    }

    // Luminous Breathing Effect for Nodes
    nodes.forEach(function(n) {
      if (n.sprite) {
        var baseScale = n.size * 5.2;
        var pulse = Math.sin(time * 2.5 + n.x * 0.05) * 0.4;
        if (selectedNode === n) {
          n.sprite.scale.setScalar(n.size * 8.5 + pulse * 1.5);
        }
      }
    });

    renderer.render(scene, camera);
  }

  // Initialize
  if (typeof THREE !== "undefined") {
    initThree();
    animate();
    document.getElementById("btnAutoRotate").classList.add("active");
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
