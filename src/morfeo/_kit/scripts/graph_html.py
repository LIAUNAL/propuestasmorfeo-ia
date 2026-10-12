#!/usr/bin/env python3
"""graph_html.py — render a self-contained interactive HTML view of a
codebase-memory graph report.

The framework's graph reports are Markdown (`grafos/<name>-graph-report.md`):
good for grepping and for quoting at a gate, poor for *seeing* a graph. This
script adds an HTML twin so the operator can actually look at the structure.

Contract
--------
The DISPATCHER (the only component with MCP access) writes the graph data next
to the Markdown report as `grafos/<name>-graph.json`, then runs this script:

    scripts/graph_html.py <input.json> [<output.html>]

The script is stdlib-only and deterministic: the same JSON in produces
byte-identical HTML out (no randomness, no timestamps taken from the clock —
the date comes from the JSON payload). No network access, no CDN: the output
opens and works offline from a plain double click.

Input JSON shape
----------------
{
  "corpus":       "papers",                     # optional label
  "run_id":       "2026-09-...",                # optional
  "title":        "Reporte de grafo — ...",     # optional
  "generated_at": "2026-09-29",                 # optional
  "index":  {"project": "...", "nodes": 0, "edges": 0, "freshness": "..."},
  "central_nodes": {"note": "...", "items": [{"id": "...", "label": "...", "degree": 4}]},
  "communities":   {"note": "...", "clusters": [{"name": "...", "files": ["..."]}]},
  "questions":     ["...", "..."],
  "nodes": [{"id": "...", "label": "...", "type": "File", "group": "..."}],
  "edges": [{"source": "...", "target": "...", "type": "DEFINES"}]
}

`group` is optional and drives node colour — use it for thematic groupings that
do NOT come from the graph itself (e.g. SOTA subsections). `note` fields are
rendered verbatim, so the dispatcher can state honestly when a section is
degenerate instead of leaving it silently empty.
"""

from __future__ import annotations

import html
import json
import pathlib
import sys

# Deterministic palette, cycled by group. Institutional colours first.
PALETTE = [
    "#0066B3",  # azulUNAL
    "#2E8B57",  # verdeGCPDS
    "#C0392B",  # rojoLimitante
    "#8E44AD",
    "#D68910",
    "#148F77",
    "#5D6D7E",
    "#B03A2E",
    "#1F618D",
    "#7D6608",
]


def default_output_path(src: pathlib.Path) -> pathlib.Path:
    """`...-graph.json` -> `...-graph.html`; otherwise swap the suffix."""
    name = src.name
    if name.endswith("-graph.json"):
        return src.with_name(name[: -len("-graph.json")] + "-graph.html")
    return src.with_suffix(".html")


def normalise(data: dict) -> dict:
    """Fill defaults so the renderer never has to guard for missing keys."""
    data = dict(data or {})
    data.setdefault("corpus", "graph")
    data.setdefault("run_id", "")
    data.setdefault("title", f"Reporte de grafo — {data['corpus']}")
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
    """JSON embedded in a <script type="application/json"> block."""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # `</` inside a script block would close it early.
    return raw.replace("</", "<\\/")


def render_central(data: dict) -> str:
    cn = data["central_nodes"]
    out = ["<h2>Nodos centrales</h2>"]
    if cn["note"]:
        out.append(f'<p class="note">{esc(cn["note"])}</p>')
    if not cn["items"]:
        out.append('<p class="empty">Sin nodos centrales que reportar.</p>')
        return "\n".join(out)
    out.append("<table><thead><tr><th>Nodo</th><th>Grado</th></tr></thead><tbody>")
    for item in cn["items"]:
        label = item.get("label") or item.get("id") or ""
        out.append(
            f"<tr><td>{esc(label)}</td><td class=\"num\">{esc(item.get('degree', ''))}</td></tr>"
        )
    out.append("</tbody></table>")
    return "\n".join(out)


def render_communities(data: dict) -> str:
    cm = data["communities"]
    out = ["<h2>Comunidades temáticas</h2>"]
    if cm["note"]:
        out.append(f'<p class="note">{esc(cm["note"])}</p>')
    if not cm["clusters"]:
        out.append('<p class="empty">Sin comunidades detectadas por el grafo.</p>')
        return "\n".join(out)
    for i, cluster in enumerate(cm["clusters"]):
        colour = PALETTE[i % len(PALETTE)]
        files = cluster.get("files") or []
        out.append(
            '<details open><summary>'
            f'<span class="swatch" style="background:{colour}"></span>'
            f'{esc(cluster.get("name", "cluster"))}'
            f'<span class="count">{len(files)}</span></summary><ul>'
        )
        out.extend(f"<li>{esc(f)}</li>" for f in files)
        out.append("</ul></details>")
    return "\n".join(out)


def render_questions(data: dict) -> str:
    out = ["<h2>Preguntas sugeridas</h2>"]
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
<title>{title}</title>
<style>
  :root {{
    --azul: #0066B3; --gris: #666666; --verde: #2E8B57; --rojo: #C0392B;
    --bg: #fbfbfd; --panel: #ffffff; --line: #e3e6ec; --ink: #1c1f26; --muted: #667085;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         color: var(--ink); background: var(--bg); }}
  header {{ background: var(--panel); border-bottom: 1px solid var(--line); padding: 18px 24px; }}
  h1 {{ margin: 0 0 6px; font-size: 19px; }}
  .meta {{ color: var(--muted); font-size: 13px; }}
  .meta code {{ background: #f1f3f7; padding: 1px 5px; border-radius: 4px; }}
  .wrap {{ display: grid; grid-template-columns: minmax(0, 1fr) 400px; gap: 0; align-items: start; }}
  @media (max-width: 1100px) {{ .wrap {{ grid-template-columns: 1fr; }} }}
  .stage {{ position: relative; background: var(--panel); border-right: 1px solid var(--line); }}
  #cv {{ display: block; width: 100%; height: 660px; cursor: grab; }}
  #cv.drag {{ cursor: grabbing; }}
  .toolbar {{ position: absolute; top: 12px; left: 12px; display: flex; flex-wrap: wrap; gap: 6px; max-width: calc(100% - 24px); }}
  .toolbar button {{ font: inherit; font-size: 12px; padding: 4px 9px; border: 1px solid var(--line);
                     background: #fff; border-radius: 999px; cursor: pointer; color: var(--ink); }}
  .toolbar button[aria-pressed="false"] {{ opacity: .42; text-decoration: line-through; }}
  .hint {{ position: absolute; bottom: 10px; left: 12px; font-size: 12px; color: var(--muted); }}
  #tip {{ position: absolute; pointer-events: none; background: #1c1f26; color: #fff; font-size: 12px;
          padding: 6px 9px; border-radius: 6px; max-width: 340px; opacity: 0; transition: opacity .1s; z-index: 5; }}
  .side {{ padding: 18px 22px 40px; }}
  .side h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted);
              margin: 22px 0 8px; border-bottom: 1px solid var(--line); padding-bottom: 6px; }}
  .side h2:first-child {{ margin-top: 0; }}
  .note {{ font-size: 13px; color: var(--muted); background: #f6f7fa; border-left: 3px solid var(--azul);
           padding: 8px 10px; margin: 0 0 10px; }}
  .empty {{ font-size: 13px; color: var(--muted); font-style: italic; margin: 0 0 10px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 5px 6px; border-bottom: 1px solid var(--line); }}
  th {{ color: var(--muted); font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  details {{ font-size: 13px; margin-bottom: 6px; }}
  summary {{ cursor: pointer; display: flex; align-items: center; gap: 7px; padding: 4px 0; }}
  .swatch {{ width: 11px; height: 11px; border-radius: 3px; display: inline-block; flex: none; }}
  .count {{ color: var(--muted); margin-left: auto; font-variant-numeric: tabular-nums; }}
  details ul {{ margin: 4px 0 8px 18px; padding: 0; color: var(--muted); }}
  ol {{ padding-left: 20px; font-size: 13px; }}
  ol li {{ margin-bottom: 9px; }}
  footer {{ padding: 12px 24px 24px; color: var(--muted); font-size: 12px; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="meta">
    <code>{project}</code> · {nodes} nodos / {edges} aristas{fresh}
  </div>
</header>

<div class="wrap">
  <div class="stage">
    <canvas id="cv"></canvas>
    <div class="toolbar" id="toolbar"></div>
    <div class="hint">arrastrá un nodo para reubicarlo · rueda para acercar · arrastrá el fondo para desplazar</div>
    <div id="tip"></div>
  </div>
  <div class="side">
    {central}
    {communities}
    {questions}
  </div>
</div>

<footer>
  Generado por <code>scripts/graph_html.py</code>{when}. La disposición de los nodos es
  determinista (misma entrada, mismo HTML): sirve para leer estructura, no para inferir
  agrupaciones que el grafo no contiene.
</footer>

<script type="application/json" id="graph-data">{payload}</script>
<script>
(function () {{
  "use strict";
  var DATA = JSON.parse(document.getElementById("graph-data").textContent);
  var nodes = DATA.nodes.map(function (n) {{
    return {{ id: n.id, label: n.label || n.id, type: n.type || "", group: n.group || null }};
  }});
  var byId = {{}};
  nodes.forEach(function (n) {{ byId[n.id] = n; }});
  var edges = (DATA.edges || []).filter(function (e) {{
    return byId[e.source] && byId[e.target];
  }}).map(function (e) {{
    return {{ source: e.source, target: e.target, type: e.type || "edge" }};
  }});

  var groups = [];
  var PAL = {palette};
  nodes.forEach(function (n) {{
    if (n.group && groups.indexOf(n.group) < 0) groups.push(n.group);
    n.colour = n.group ? PAL[groups.indexOf(n.group) % PAL.length] : "#98a2b3";
  }});
  var types = [];
  edges.forEach(function (e) {{ if (types.indexOf(e.type) < 0) types.push(e.type); }});
  types.sort();

  // ---- deterministic layout ------------------------------------------------
  var W = 1, H = 1;
  function seed() {{
    var n = nodes.length || 1, R = 300;
    nodes.forEach(function (node, i) {{
      var a = (2 * Math.PI * i) / n;
      node.x = Math.cos(a) * R;
      node.y = Math.sin(a) * R;
      node.vx = 0; node.vy = 0;
    }});
  }}
  function simulate(iterations) {{
    // Coulomb repulsion + springs on edges + weak centring. No randomness, so
    // the same input always yields the same picture.
    for (var it = 0; it < iterations; it++) {{
      var cool = 1 - it / iterations;
      for (var i = 0; i < nodes.length; i++) {{
        var a = nodes[i];
        for (var j = i + 1; j < nodes.length; j++) {{
          var b = nodes[j];
          var dx = b.x - a.x, dy = b.y - a.y;
          var d2 = dx * dx + dy * dy;
          if (d2 < 1e-6) {{ d2 = 1e-6; dx = 0.5; dy = 0.5; }}
          var d = Math.sqrt(d2);
          var f = 2600 / d2;
          var ux = (dx / d) * f, uy = (dy / d) * f;
          a.vx -= ux; a.vy -= uy; b.vx += ux; b.vy += uy;
        }}
      }}
      edges.forEach(function (e) {{
        var a = byId[e.source], b = byId[e.target];
        var dx = b.x - a.x, dy = b.y - a.y;
        var d = Math.sqrt(dx * dx + dy * dy) || 1e-6;
        var f = (d - 130) * 0.012;
        var ux = (dx / d) * f, uy = (dy / d) * f;
        a.vx += ux; a.vy += uy; b.vx -= ux; b.vy -= uy;
      }});
      nodes.forEach(function (n) {{
        n.vx -= n.x * 0.0016; n.vy -= n.y * 0.0016;
        n.vx *= 0.82; n.vy *= 0.82;
        n.x += n.vx * cool * 1.6; n.y += n.vy * cool * 1.6;
      }});
    }}
  }}

  // ---- view transform ------------------------------------------------------
  var view = {{ x: 0, y: 0, k: 1 }};
  var hiddenTypes = {{}};
  var cv = document.getElementById("cv");
  var ctx = cv.getContext("2d");
  var tip = document.getElementById("tip");
  var dpr = window.devicePixelRatio || 1;

  function resize() {{
    var r = cv.getBoundingClientRect();
    W = r.width; H = r.height;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }}
  function toScreen(n) {{
    return {{ x: W / 2 + view.x + n.x * view.k, y: H / 2 + view.y + n.y * view.k }};
  }}
  function toWorld(px, py) {{
    return {{ x: (px - W / 2 - view.x) / view.k, y: (py - H / 2 - view.y) / view.k }};
  }}

  function visibleEdges() {{
    return edges.filter(function (e) {{ return !hiddenTypes[e.type]; }});
  }}

  function draw() {{
    ctx.clearRect(0, 0, W, H);
    var vis = visibleEdges();
    vis.forEach(function (e) {{
      var a = toScreen(byId[e.source]), b = toScreen(byId[e.target]);
      ctx.strokeStyle = e.type === "THEME" ? "rgba(0,102,179,.30)" : "rgba(120,130,150,.22)";
      ctx.lineWidth = e.type === "THEME" ? 1.7 : 1;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }});
    nodes.forEach(function (n) {{
      var p = toScreen(n);
      var r = (n.type === "File" ? 5.5 : 4) * Math.min(1.6, Math.max(.7, view.k));
      if (p.x < -40 || p.y < -40 || p.x > W + 40 || p.y > H + 40) return;
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, 6.2832);
      ctx.fillStyle = n.colour; ctx.fill();
      if (n === hovered) {{ ctx.strokeStyle = "#1c1f26"; ctx.lineWidth = 2; ctx.stroke(); }}
      if (view.k > 1.5 && nodes.length <= 80) {{
        ctx.fillStyle = "#475467"; ctx.font = "11px -apple-system, sans-serif";
        ctx.fillText(n.label.slice(0, 26), p.x + r + 3, p.y + 3);
      }}
    }});
  }}

  // ---- interaction ---------------------------------------------------------
  var hovered = null, dragNode = null, panning = null;
  cv.addEventListener("mousemove", function (ev) {{
    var r = cv.getBoundingClientRect();
    var px = ev.clientX - r.left, py = ev.clientY - r.top;
    if (dragNode) {{
      var w = toWorld(px, py);
      dragNode.x = w.x; dragNode.y = w.y; dragNode.vx = dragNode.vy = 0;
      draw(); return;
    }}
    if (panning) {{
      view.x += px - panning.x; view.y += py - panning.y;
      panning = {{ x: px, y: py }}; draw(); return;
    }}
    var found = null, best = 14 * 14;
    nodes.forEach(function (n) {{
      var p = toScreen(n);
      var d = (p.x - px) * (p.x - px) + (p.y - py) * (p.y - py);
      if (d < best) {{ best = d; found = n; }}
    }});
    if (found !== hovered) {{ hovered = found; draw(); }}
    if (found) {{
      tip.textContent = found.label + (found.group ? "  ·  " + found.group : "");
      tip.style.left = Math.min(px + 14, W - 320) + "px";
      tip.style.top = (py + 14) + "px";
      tip.style.opacity = 1;
    }} else {{ tip.style.opacity = 0; }}
  }});
  cv.addEventListener("mousedown", function (ev) {{
    var r = cv.getBoundingClientRect();
    var px = ev.clientX - r.left, py = ev.clientY - r.top;
    if (hovered) {{ dragNode = hovered; }} else {{ panning = {{ x: px, y: py }}; }}
    cv.classList.add("drag");
  }});
  window.addEventListener("mouseup", function () {{
    dragNode = null; panning = null; cv.classList.remove("drag");
  }});
  cv.addEventListener("wheel", function (ev) {{
    ev.preventDefault();
    var r = cv.getBoundingClientRect();
    var px = ev.clientX - r.left, py = ev.clientY - r.top;
    var before = toWorld(px, py);
    view.k = Math.min(8, Math.max(0.15, view.k * (ev.deltaY < 0 ? 1.12 : 1 / 1.12)));
    var after = toWorld(px, py);
    view.x += (after.x - before.x) * view.k;
    view.y += (after.y - before.y) * view.k;
    draw();
  }}, {{ passive: false }});

  // ---- edge-type toggles ---------------------------------------------------
  var tb = document.getElementById("toolbar");
  types.forEach(function (t) {{
    var b = document.createElement("button");
    b.textContent = t; b.setAttribute("aria-pressed", "true");
    b.addEventListener("click", function () {{
      hiddenTypes[t] = !hiddenTypes[t];
      b.setAttribute("aria-pressed", hiddenTypes[t] ? "false" : "true");
      draw();
    }});
    tb.appendChild(b);
  }});
  if (groups.length) {{
    var legend = document.createElement("span");
    legend.style.cssText = "font-size:12px;color:#667085;display:inline-flex;gap:8px;align-items:center;margin-left:6px";
    legend.innerHTML = groups.map(function (g, i) {{
      return '<span style="display:inline-flex;align-items:center;gap:4px"><span class="swatch" style="background:'
        + PAL[i % PAL.length] + '"></span>' + g + "</span>";
    }}).join("");
    tb.appendChild(legend);
  }}

  seed(); simulate(320);
  window.addEventListener("resize", resize);
  resize();
}})();
</script>
</body>
</html>
"""


def build_html(data: dict) -> str:
    idx = data["index"]
    fresh = f" · frescura: {esc(idx['freshness'])}" if idx.get("freshness") else ""
    when = f" el {esc(data['generated_at'])}" if data.get("generated_at") else ""
    return TEMPLATE.format(
        title=esc(data["title"]),
        project=esc(idx.get("project") or data["corpus"]),
        nodes=esc(idx["nodes"]),
        edges=esc(idx["edges"]),
        fresh=fresh,
        central=render_central(data),
        communities=render_communities(data),
        questions=render_questions(data),
        payload=render_payload(data),
        palette=json.dumps(PALETTE),
        when=when,
    )


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
