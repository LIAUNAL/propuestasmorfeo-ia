#!/usr/bin/env python3
"""Deterministic renderer: a Morfeo SOTA atlas to one self-contained HTML file.

Ported from papersmith-ai (skills/plausibility/scripts/render_atlas.py,
https://github.com/LIAUNAL/papersmith-ai), Apache License 2.0. Changes for
Morfeo: Spanish UI; the dashboard's ``{"type": "atlas-control", "cmd": ...}``
message is answered beside papersmith's ``atlas-command``; a collapsible
"Estudio de constelaciones" side panel and an optional Markdown report of the
same study (``--report``), both computed here with no model in the loop. See
scripts/assets/THIRD_PARTY_NOTICES.md.

Reads ``artefactos/scoping/atlas.json`` and writes a single HTML page: every
system placed in ONE shared 3D sky (family neighborhoods on a golden spiral,
each lifted to its own height; systems sorted by id, each on its own tilted
orbital plane, so the same atlas always draws the same sky), intra-system links
as straight segments, inter-system links as arcs running planet to planet
across systems, and dashed ties between planets sharing a family name.

The scene is computed here and written as a JSON data island; the vendored
three.js viewer (``scripts/assets/atlas3d.bundle.js``) is inlined verbatim and
only draws it: no CDN, no network at view time. Hovering a planet dims what is
not linked to it; clicking opens its evidence; double-clicking flies to it;
family chips filter; a toolbar zooms, turns, tilts, pauses the rotation,
toggles names, regroups systems by family and switches to the 2D view.

Resource use (as in papersmith): the 3D viewer draws only when something
changed, caps the pixel ratio between 1 and 2, pauses while the page is hidden
(``visibilitychange``) or while the dashboard says so, and disposes its GPU
resources on a view switch. A canvas 2D constellation opens instead when WebGL
is missing or software-only, the machine reports under 4 GB or under 4 cores,
or the 3D sky draws under 20 fps during its first 3 seconds.

Usage: render_atlas.py <atlas.json> --out <html> [--report <md>] [--title <text>]

Exit 0 on written files, 1 when the atlas fails this module's own shape read
(run check_atlas.py first: it names violations, this one only refuses to draw),
2 on usage, unreadable input, or a missing/unsafe viewer bundle.

Stdlib only.
"""

from __future__ import annotations

import html
import json
import math
import sys
from pathlib import Path

SLOT_COLORS = {
    "sun": "#e8b339",
    "branch": "#7fb069",
    "topic_app": "#5aa9e6",
    "topic_ai": "#7f6ae6",
    "problem": "#e65a5a",
    "application": "#5ad1e6",
    "family": "#9b7ede",
    "novelty": "#e67e22",
    "contribution": "#e879f9",
    "result": "#2ecc71",
    "conclusion": "#95a5a6",
}

REL_COLORS = {
    "about": "#4a5a80",
    "addresses": "#8a93ad",
    "extends": "#2ecc71",
    "contradicts": "#e65a5a",
    "supports": "#5aa9e6",
    "yields": "#e8b339",
    "shares-family-with": "#9b7ede",
}

ORBIT_RADII = {0: 0, 1: 90, 2: 170, 3: 250}
CLUSTER_STEP = 3400
MEMBER_STEP = 660
GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))
PHI = (math.sqrt(5) - 1) / 2
FAMILY_LIFT = 900
MEMBER_LIFT = 260
TILT_MAX = 0.9
VIEWER = Path(__file__).resolve().parent / "assets" / "atlas3d.bundle.js"


def _spread(index: int) -> float:
    """A deterministic value in [-1, 1): the golden-ratio sequence, so
    consecutive indices land far apart without any randomness."""
    return 2 * ((index * PHI) % 1.0) - 1


def _family_of(system: dict) -> str:
    """The group this system belongs to: its one family planet's label.
    Systems with none gather under the empty name — the checker refuses
    them, but the renderer still draws something rather than crashing."""
    for planet in system.get("planets") or []:
        if isinstance(planet, dict) and planet.get("slot") == "family":
            label = planet.get("label")
            if isinstance(label, str) and label.strip():
                return label.strip()
    return ""


def _system_centers(systems: list[dict]) -> dict[str, tuple[float, float, float]]:
    """One shared sky, grouped by family: each family owns a cluster center
    on an outer golden spiral lifted to its own height, and its member
    systems spiral locally around it. A family reads as a neighborhood.
    Pure function of sorted ids and labels — deterministic by construction."""
    by_family: dict[str, list[str]] = {}
    for system in sorted(systems, key=lambda s: s["id"]):
        by_family.setdefault(_family_of(system), []).append(system["id"])
    centers: dict[str, tuple[float, float, float]] = {}
    for findex, fam in enumerate(sorted(by_family)):
        radius = CLUSTER_STEP * math.sqrt(findex)
        angle = findex * GOLDEN_ANGLE
        ccx, ccy = radius * math.cos(angle), radius * math.sin(angle)
        ccz = FAMILY_LIFT * _spread(findex)
        for mindex, sid in enumerate(by_family[fam]):
            mradius = MEMBER_STEP * math.sqrt(mindex)
            mangle = mindex * GOLDEN_ANGLE
            centers[sid] = (
                round(ccx + mradius * math.cos(mangle), 1),
                round(ccy + mradius * math.sin(mangle), 1),
                round(ccz + MEMBER_LIFT * _spread(mindex + 1), 1),
            )
    return centers


def _orbital_frame(index: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """The orthonormal basis (u, v) of one system's orbital plane: spun about
    the vertical by the golden angle, then tilted out of the horizontal, so
    neighboring systems never share a plane. Deterministic by index."""
    spin = index * GOLDEN_ANGLE
    tilt = TILT_MAX * _spread(index + 1)
    u = (math.cos(spin), math.sin(spin), 0.0)
    v = (-math.sin(spin) * math.cos(tilt), math.cos(spin) * math.cos(tilt), math.sin(tilt))
    return tuple(round(c, 4) for c in u), tuple(round(c, 4) for c in v)


def _local_positions(planets: list[dict]) -> dict[str, tuple[float, float]]:
    """System-local layout: orbit radius by slot, evenly spaced angles in id
    order — the same planets always draw the same system."""
    by_orbit: dict[int, list[dict]] = {}
    for planet in planets:
        by_orbit.setdefault(planet["orbit"], []).append(planet)
    positions: dict[str, tuple[float, float]] = {}
    for orbit in sorted(by_orbit):
        members = sorted(by_orbit[orbit], key=lambda p: p["id"])
        radius = ORBIT_RADII.get(orbit, 250)
        if radius == 0:
            positions[members[0]["id"]] = (0.0, 0.0)
            continue
        for index, planet in enumerate(members):
            angle = 2 * math.pi * index / len(members) - math.pi / 2
            positions[planet["id"]] = (
                round(radius * math.cos(angle), 1),
                round(radius * math.sin(angle), 1),
            )
    return positions


def _family_ties(atlas: dict, positions: dict[str, list[float]]) -> list[dict]:
    """One tie per consecutive pair of planets sharing a family name,
    chaining them across systems in system-id order. This draws identity,
    not findings: families are the only planets two systems may share by
    name, so equal labels ARE the same family and the tie only makes that
    visible. Deterministic — same atlas, same ties."""
    by_label: dict[str, list[tuple[str, str]]] = {}
    for system in atlas["systems"]:
        for planet in system["planets"]:
            if planet.get("slot") == "family":
                by_label.setdefault(str(planet.get("label")), []).append(
                    (system["id"], planet["id"]))
    ties = []
    for label in sorted(by_label):
        members = [f"{sid}.{pid}" for sid, pid in sorted(by_label[label])]
        for first, second in zip(members, members[1:]):
            if first in positions and second in positions:
                ties.append({"family": label, "from": first, "to": second})
    return ties


def _scene(atlas: dict) -> dict:
    """Everything the viewer draws, precomputed: the viewer lays out nothing,
    so the same atlas always yields the same scene."""
    centers = _system_centers(atlas["systems"])
    positions: dict[str, list[float]] = {}
    frames: dict[str, dict] = {}
    for index, system in enumerate(sorted(atlas["systems"], key=lambda s: s["id"])):
        center = centers[system["id"]]
        u, v = _orbital_frame(index)
        frames[system["id"]] = {"center": list(center), "u": list(u), "v": list(v)}
        for pid, (lx, ly) in _local_positions(system["planets"]).items():
            positions[f"{system['id']}.{pid}"] = [
                round(center[axis] + lx * u[axis] + ly * v[axis], 1) for axis in range(3)]
    edges = []
    for link in sorted(atlas["links"],
                       key=lambda l: (str(l.get("from_system")), str(l.get("from")),
                                      str(l.get("to_system")), str(l.get("to")))):
        source = f"{link.get('from_system')}.{link.get('from')}"
        target = f"{link.get('to_system')}.{link.get('to')}"
        if source not in positions or target not in positions:
            continue
        edges.append({"from": source, "to": target, "rel": link.get("rel"),
                      "color": REL_COLORS.get(link.get("rel"), "#4a5a80"),
                      "inter": link.get("from_system") != link.get("to_system")})
    return {
        "version": 1,
        "atlas": atlas,
        "positions": dict(sorted(positions.items())),
        "frames": dict(sorted(frames.items())),
        "edges": edges,
        "ties": _family_ties(atlas, positions),
        "slot_colors": SLOT_COLORS,
        "orbit_radii": {str(orbit): radius for orbit, radius in ORBIT_RADII.items() if radius},
    }


def _readable_shape(atlas: object) -> str | None:
    if not isinstance(atlas, dict):
        return "ATLAS_NOT_AN_OBJECT"
    if not isinstance(atlas.get("systems"), list) or not atlas["systems"]:
        return "SYSTEMS_NOT_A_NONEMPTY_LIST"
    if not isinstance(atlas.get("links"), list):
        return "LINKS_NOT_A_LIST"
    for system in atlas["systems"]:
        if not isinstance(system, dict) or not isinstance(system.get("planets"), list):
            return "SYSTEM_MALFORMED"
    return None


PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@</title>
<style>
html,body{height:100%}
body{font-family:system-ui,sans-serif;background:#0a0a10;color:#e4e4ed;margin:0;padding:12px 16px;box-sizing:border-box;display:flex;flex-direction:column}
h1{font-size:18px;font-weight:600;margin:0 0 8px;letter-spacing:.02em}
#stage{flex:1 1 auto;display:flex;gap:10px;min-height:420px}
.sky{position:relative;flex:1 1 auto;min-height:420px;min-width:0;background:#0a0a10;border:1px solid #1e2236;border-radius:10px;overflow:hidden;cursor:grab}
.sky canvas{display:block;width:100%;height:100%}
.sky:active{cursor:grabbing}
#panel{color:#9aa3bd;font-size:13px;margin:0 0 8px}
#overlay{position:fixed;inset:0;background:rgba(5,5,10,.65);display:none;align-items:center;justify-content:center;z-index:10}
#overlay.open{display:flex}
#modal{background:#11131f;border:1px solid #9b7ede;border-radius:10px;padding:16px 20px;max-width:580px;max-height:82vh;overflow:auto;box-shadow:0 0 40px rgba(155,126,222,.25)}
#modal h3{margin:0 0 6px}
#modal .quote{font-style:italic;color:#b9c4de;border-left:3px solid #9b7ede;margin:10px 0;padding-left:10px}
#modalclose{float:right;cursor:pointer;font-size:14px;padding:2px 10px;background:#1a1d2e;color:#e4e4ed;border:1px solid #2a3350;border-radius:6px}
#famlegend,#rellegend,#toolbar{margin:0 0 6px;font-size:13px;color:#9aa3bd}
.famchip{margin:2px;padding:3px 12px;cursor:pointer;border-radius:12px;border:1px solid #9b7ede;background:#14172a;color:#e4e4ed;font-size:12px}
.famchip.on{background:#9b7ede;color:#0a0a10}
.dot{display:inline-block;width:16px;height:0;border-top:2px solid;margin:0 4px 3px 10px;vertical-align:middle}
#toolbar{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
#toolbar button{font-size:13px;padding:3px 12px;cursor:pointer;background:#14172a;color:#e4e4ed;border:1px solid #2a3350;border-radius:6px}
#toolbar button.on{background:#9b7ede;color:#0a0a10;border-color:#9b7ede}
#toolbar .sep{width:1px;height:20px;background:#2a3350;margin:0 4px}
#gpunote{margin:0 0 6px;font-size:12px;color:#e8b339}
#gpunote[hidden]{display:none}
.atlas-tip{max-width:340px;white-space:normal!important;text-align:center;line-height:1.3;z-index:5}
.atlas-names{position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:4}
.atlas-names div{position:absolute;left:0;top:0;font:11px system-ui,sans-serif;white-space:nowrap;color:#f3d98b;text-shadow:0 0 3px #0a0a10,0 0 3px #0a0a10,0 0 6px #0a0a10}
.atlas-names .lit{font-weight:600;color:#fff}
#study{flex:0 0 340px;max-width:40%;overflow:auto;background:#0e1020;border:1px solid #1e2236;border-radius:10px;padding:10px 12px;font-size:12.5px;color:#c9d0e4;box-sizing:border-box}
#study[hidden]{display:none}
#study h2{font-size:15px;margin:0 0 6px;color:#e4e4ed}
#study h3{font-size:13px;margin:12px 0 4px;color:#9b7ede}
#study h4{font-size:12px;margin:8px 0 2px;font-weight:600}
#study ul{margin:2px 0 6px;padding-left:18px}
#study li{margin:1px 0}
#study .sys{cursor:pointer;text-decoration:underline dotted}
#study .pid{color:#7d86a3;font-size:11px}
#study .counts{color:#9aa3bd;margin:0 0 6px}
@media (max-width:820px){#toolbar .sep{display:none}#stage{flex-direction:column}#study{flex:0 0 auto;max-width:none;max-height:45vh}}
</style>
</head>
<body>
<h1>@@HEADING@@</h1>
<div id="panel">Arrastra para orbitar, arrastra con el botón derecho para desplazar y usa la rueda para acercar. Pasa el cursor sobre un planeta para ver sus enlaces entre sistemas; haz clic para leer su evidencia y doble clic para volar hasta él.</div>
<div id="gpunote" role="status" hidden></div>
<div id="overlay"><div id="modal"><button id="modalclose">cerrar</button><div id="modalbody"></div></div></div>
<div id="famlegend"><em>Familias:</em> <span id="famchips"></span></div>
<div id="rellegend"><em>Relaciones:</em> <span class="dot" style="border-color:#2ecc71"></span>extiende <span class="dot" style="border-color:#5aa9e6"></span>respalda <span class="dot" style="border-color:#e65a5a"></span>contradice <span class="dot" style="border-color:#8a93ad"></span>aborda <span class="dot" style="border-color:#9b7ede;border-top-style:dashed"></span>familia compartida <span class="dot" style="border-color:#e8b339"></span>produce <span class="dot" style="border-color:#4a5a80"></span>trata de</div>
<div id="toolbar"><button id="zoomin">acercar +</button><button id="zoomout">alejar −</button><span class="sep"></span><button id="spinleft" title="Girar a la izquierda">⟲ girar</button><button id="spinright" title="Girar a la derecha">girar ⟳</button><button id="tiltup" title="Inclinar hacia arriba">▲ inclinar</button><button id="tiltdown" title="Inclinar hacia abajo">▼ inclinar</button><button id="autorotate" class="on" title="Rotación automática">⏸ rotación</button><button id="names" class="on" title="Muestra u oculta los nombres de los sistemas; solo se dibujan los que no se solapan y al acercar aparecen más">nombres</button><span class="sep"></span><button id="zoomreset">restablecer vista</button><button id="grouplayout">Disposición de grupos</button><span class="sep"></span><button id="viewmode" title="Alterna entre el cielo 3D y la constelación 2D, más liviana">Vista 2D</button><span class="sep"></span><button id="studytoggle" class="on" aria-expanded="true" aria-controls="study" title="Muestra u oculta el estudio de constelaciones">Estudio de constelaciones</button></div>
<div id="stage"><div id="sky" class="sky"></div>
@@STUDY@@</div>
<script type="application/json" id="atlas-data">@@DATA@@</script>
<script>
@@VIEWER@@
</script>
<script>
const SCENE = JSON.parse(document.getElementById('atlas-data').textContent);
const ATLAS = SCENE.atlas;
const SLOT_NAMES = {sun: 'sol', branch: 'rama', topic_app: 'tema de aplicación', topic_ai: 'tema de IA',
  problem: 'problema', application: 'aplicación', family: 'familia', novelty: 'novedad',
  contribution: 'contribución', result: 'resultado', conclusion: 'conclusión'};
const PROVENANCE_NAMES = {stated: 'declarado', grouped: 'agrupado'};
const PLANETS = new Map();
const SYSTEMS = new Map();
ATLAS.systems.forEach(s => {
  SYSTEMS.set(s.id, s);
  s.planets.forEach(p => PLANETS.set(s.id + '.' + p.id, {system: s, planet: p}));
});
// The group a system belongs to: its first non-blank family label (the viewer's rule).
function familyLabel(s) {
  const fam = s ? s.planets.find(p => p.slot === 'family' && typeof p.label === 'string' && p.label.trim()) : null;
  return fam ? fam.label.trim() : '';
}
const panel = document.getElementById('modalbody');
const overlay = document.getElementById('overlay');
function closeModal() { overlay.classList.remove('open'); }
document.getElementById('modalclose').addEventListener('click', closeModal);
overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
function line(tag, text, cls) {
  const el = document.createElement(tag);
  el.textContent = text;
  if (cls) el.className = cls;
  return el;
}
function openModal(nodes) {
  panel.replaceChildren(...nodes);
  overlay.classList.add('open');
}
function showPlanet(key) {
  const entry = PLANETS.get(key);
  if (!entry) return;
  const p = entry.planet;
  const ev = p.evidence || {};
  openModal([
    line('h3', p.label),
    line('p', (SLOT_NAMES[p.slot] || p.slot) + ' · órbita ' + p.orbit + ' · ' + (PROVENANCE_NAMES[p.provenance] || p.provenance || '') + ' · ' + (entry.system.title || entry.system.id) + ' (' + entry.system.id + ')'),
    line('p', p.detail || ''),
    line('p', ev.quote || '', 'quote'),
    line('small', (ev.origin || '') + ' · consultado ' + (ev.retrieved || '')),
  ]);
}
let activeFam = null;
function familyKeep() {
  if (activeFam === null) return null;
  const keep = new Set();
  ATLAS.systems.forEach(s => {
    if (s.planets.some(p => p.slot === 'family' && p.label === activeFam))
      s.planets.forEach(p => keep.add(s.id + '.' + p.id));
  });
  return keep;
}
function hoverKeep(key) {
  const keep = new Set([key]);
  SCENE.edges.forEach(e => {
    if (e.inter && (e.from === key || e.to === key)) { keep.add(e.from); keep.add(e.to); }
  });
  const entry = PLANETS.get(key);
  if (entry && entry.planet.slot === 'family') {
    PLANETS.forEach((other, otherKey) => {
      if (other.planet.slot === 'family' && other.planet.label === entry.planet.label) keep.add(otherKey);
    });
  }
  return keep;
}
// Framed by the dashboard, the page reports to its parent; opened alone, it
// posts nothing. Only plain strings cross the frame.
function tellParent(message) {
  if (window.parent !== window) window.parent.postMessage(message, '*');
}
function reportPlanet(key) {
  const entry = PLANETS.get(key);
  if (!entry) return;
  tellParent({
    type: 'atlas-planet-selected',
    key: String(key),
    label: String(entry.planet.label || ''),
    slot: String(entry.planet.slot || ''),
    system: {id: String(entry.system.id), title: String(entry.system.title || '')},
  });
}
// 'ok' when WebGL runs on a real GPU; 'weak' when only a software renderer is
// available (failIfMajorPerformanceCaveat, or a renderer named like one);
// 'none' when WebGL cannot start at all.
function webglSupport() {
  try {
    const strict = {failIfMajorPerformanceCaveat: true};
    const c = document.createElement('canvas');
    const g = c.getContext('webgl2', strict) || c.getContext('webgl', strict);
    if (g) {
      const debug = g.getExtension('WEBGL_debug_renderer_info');
      const name = debug ? String(g.getParameter(debug.UNMASKED_RENDERER_WEBGL)) : '';
      const lose = g.getExtension('WEBGL_lose_context');
      if (lose) lose.loseContext();
      return /swiftshader|llvmpipe|softpipe|software|basic render/i.test(name) ? 'weak' : 'ok';
    }
    const any = document.createElement('canvas');
    return any.getContext('webgl2') || any.getContext('webgl') ? 'weak' : 'none';
  } catch (e) {
    return 'none';
  }
}
// Which view to open: ?view=2d or ?view=3d wins, then the viewer's last choice,
// then the machine: no or software WebGL, under 4 GB of memory or under 4
// cores opens the 2D constellation, which costs a fraction of the 3D sky.
const VIEW_KEY = 'morfeo-atlas-view';
function storedView() {
  try { return localStorage.getItem(VIEW_KEY); } catch (e) { return null; }
}
function storeView(mode) {
  try { localStorage.setItem(VIEW_KEY, mode); } catch (e) { /* sandboxed frame: no storage */ }
}
function chooseView() {
  const asked = new URLSearchParams(location.search).get('view') || storedView();
  const gl = webglSupport();
  if (asked === '2d') return {mode: '2d', reason: 'chosen'};
  if (asked === '3d' && gl !== 'none') return {mode: '3d', reason: 'chosen'};
  if (gl !== 'ok') return {mode: '2d', reason: gl};
  const memory = navigator.deviceMemory, cores = navigator.hardwareConcurrency;
  if ((memory && memory < 4) || (cores && cores < 4)) return {mode: '2d', reason: 'low'};
  return {mode: '3d', reason: 'auto'};
}
// Canvas 2D constellation with the same handle as AtlasViewer: an orthographic
// projection of the precomputed sky that can still spin and tilt, drawn only
// when something changes (one requestAnimationFrame per change, none at rest).
const FlatViewer = {mount(host, scene, opts) {
  const keys = Object.keys(scene.positions).sort();
  const index = new Map(keys.map((k, i) => [k, i]));
  const color = keys.map(k => {
    const e = PLANETS.get(k);
    return (e && scene.slot_colors[e.planet.slot]) || '#9aa3bd';
  });
  const isSun = keys.map(k => { const e = PLANETS.get(k); return !!e && e.planet.slot === 'sun'; });
  const skyPos = keys.map(k => scene.positions[k]);
  const centroid = [0, 1, 2].map(d => skyPos.reduce((a, p) => a + p[d], 0) / Math.max(1, skyPos.length));
  // Group layout: the 3D viewer's rule (sorted family labels, then system ids,
  // a golden spiral per family on a flat grid), each system keeping its shape.
  const families = new Map();
  ATLAS.systems.map(s => s.id).filter(id => scene.frames[id]).sort().forEach(id => {
    const fam = familyLabel(SYSTEMS.get(id));
    if (!families.has(fam)) families.set(fam, []);
    families.get(fam).push(id);
  });
  const famNames = [...families.keys()].sort();
  const most = Math.max(1, ...famNames.map(f => families.get(f).length));
  const cell = 2 * (720 * Math.sqrt(most - 1) + 300) + 1600;
  const cols = Math.ceil(Math.sqrt(famNames.length)), rows = Math.ceil(famNames.length / cols);
  const anchor = new Map();
  famNames.forEach((f, n) => {
    const cx = (n % cols - (cols - 1) / 2) * cell, cy = ((rows - 1) / 2 - Math.floor(n / cols)) * cell;
    families.get(f).forEach((id, j) => {
      const r = 720 * Math.sqrt(j), a = j * Math.PI * (3 - Math.sqrt(5));
      anchor.set(id, [cx + r * Math.cos(a), cy + r * Math.sin(a), 0]);
    });
  });
  const groupPos = keys.map((k, i) => {
    const id = PLANETS.get(k) ? PLANETS.get(k).system.id : k.split('.')[0];
    const f = scene.frames[id], a = anchor.get(id);
    if (!f || !a) return skyPos[i];
    return [0, 1, 2].map(d => a[d] + skyPos[i][d] - f.center[d]);
  });
  const lines = scene.edges.map(e => ({a: index.get(e.from), b: index.get(e.to), color: e.color, inter: e.inter}))
    .concat((scene.ties || []).map(t => ({a: index.get(t.from), b: index.get(t.to), color: '#9b7ede', tie: true})))
    .filter(l => l.a !== undefined && l.b !== undefined);

  const canvas = document.createElement('canvas');
  host.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  const tip = document.createElement('div');
  tip.className = 'atlas-tip';
  tip.style.cssText = 'position:absolute;pointer-events:none;display:none;padding:3px 8px;border-radius:6px;background:rgba(10,10,16,.88);border:1px solid #2a3350;color:#e4e4ed;font:12px system-ui,sans-serif;white-space:nowrap;transform:translate(-50%,-130%)';
  host.appendChild(tip);

  let layout = 'sky', yaw = 0, pitch = 0, scale = 1, fit = 1, panX = 0, panY = 0;
  let dim = null, hover = null, spinning = false, queued = false, last = 0, hidden = false, gone = false;
  let W = 0, H = 0;
  const sx = new Float32Array(keys.length), sy = new Float32Array(keys.length);
  function points() { return layout === 'groups' ? groupPos : skyPos; }
  function project() {
    const pts = points(), cy = Math.cos(yaw), sn = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const c = layout === 'groups' ? [0, 0, 0] : centroid;
    pts.forEach((p, i) => {
      const dx = p[0] - c[0], dy = p[1] - c[1], dz = p[2] - c[2];
      const x = dx * cy - dy * sn, y = dx * sn + dy * cy;
      sx[i] = W / 2 + (x - panX) * scale;
      sy[i] = H / 2 - (y * cp - dz * sp - panY) * scale;
    });
  }
  function fitView() {
    const pts = points(), c = layout === 'groups' ? [0, 0, 0] : centroid;
    let ext = 1;
    pts.forEach(p => { ext = Math.max(ext, Math.abs(p[0] - c[0]), Math.abs(p[1] - c[1])); });
    fit = scale = Math.min(W, H) / (2 * ext) * 0.92;
    panX = panY = 0;
  }
  function draw() {
    queued = false;
    if (gone) return;
    project();
    const dpr = Math.min(Math.max(window.devicePixelRatio || 1, 1), 2);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = '#0a0a10';
    ctx.fillRect(0, 0, W, H);
    const lit = i => !dim || dim.has(keys[i]);
    ctx.lineWidth = 1;
    lines.forEach(l => {
      const on = lit(l.a) && lit(l.b);
      ctx.globalAlpha = on ? (l.inter ? 0.9 : l.tie ? 0.45 : 0.35) : 0.05;
      ctx.strokeStyle = l.color;
      ctx.setLineDash(l.tie ? [4, 4] : []);
      ctx.beginPath();
      ctx.moveTo(sx[l.a], sy[l.a]);
      ctx.lineTo(sx[l.b], sy[l.b]);
      ctx.stroke();
    });
    ctx.setLineDash([]);
    const grow = Math.min(3, Math.max(1, Math.sqrt(scale / fit)));
    keys.forEach((k, i) => {
      if (sx[i] < -10 || sy[i] < -10 || sx[i] > W + 10 || sy[i] > H + 10) return;
      ctx.globalAlpha = lit(i) ? 1 : 0.12;
      ctx.fillStyle = color[i];
      ctx.beginPath();
      ctx.arc(sx[i], sy[i], (isSun[i] ? 4.5 : 2) * grow + (k === hover ? 2 : 0), 0, 2 * Math.PI);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
    if (opts.afterDraw) opts.afterDraw(ctx, W, H);
  }
  function redraw() {
    if (!queued && !hidden && !gone) { queued = true; requestAnimationFrame(draw); }
  }
  function resize() {
    const dpr = Math.min(Math.max(window.devicePixelRatio || 1, 1), 2);
    const first = !W;
    W = host.clientWidth || 800;
    H = host.clientHeight || 600;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    if (first) fitView();
    redraw();
  }
  function tick(t) {
    if (!spinning || hidden || gone) return;
    if (last) yaw += (t - last) * 0.00008;
    last = t;
    draw();
    requestAnimationFrame(tick);
  }
  function pick(ev) {
    const r = canvas.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
    let best = -1, bestD = 64;
    for (let i = 0; i < keys.length; i++) {
      const d = (sx[i] - x) ** 2 + (sy[i] - y) ** 2;
      if (d < bestD) { bestD = d; best = i; }
    }
    return best < 0 ? null : {key: keys[best], x: sx[best], y: sy[best]};
  }
  let drag = null;
  canvas.addEventListener('contextmenu', ev => ev.preventDefault());
  canvas.addEventListener('pointerdown', ev => {
    drag = {x: ev.clientX, y: ev.clientY, panX, panY, moved: false};
    canvas.setPointerCapture(ev.pointerId);
    spinning = false;
  });
  canvas.addEventListener('pointermove', ev => {
    if (drag) {
      const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      panX = drag.panX - dx / scale;
      panY = drag.panY + dy / scale;
      redraw();
      return;
    }
    const hit = pick(ev);
    const key = hit ? hit.key : null;
    if (hit) {
      const e = PLANETS.get(hit.key);
      tip.textContent = e ? (e.planet.tip || e.planet.label + ' [' + (SLOT_NAMES[e.planet.slot] || e.planet.slot) + ']') : hit.key;
      tip.style.left = hit.x + 'px';
      tip.style.top = hit.y + 'px';
      tip.style.display = 'block';
    } else {
      tip.style.display = 'none';
    }
    canvas.style.cursor = key ? 'pointer' : 'grab';
    if (key !== hover) {
      hover = key;
      if (opts.onHover) opts.onHover(key);
      redraw();
    }
  });
  canvas.addEventListener('pointerleave', () => {
    tip.style.display = 'none';
    if (hover) { hover = null; if (opts.onHover) opts.onHover(null); redraw(); }
  });
  canvas.addEventListener('pointerup', ev => {
    const d = drag;
    drag = null;
    if (!d || d.moved || ev.button !== 0) return;
    const hit = pick(ev);
    if (hit && opts.onSelect) opts.onSelect(hit.key);
  });
  canvas.addEventListener('dblclick', ev => { const hit = pick(ev); if (hit) api.focus(hit.key); });
  canvas.addEventListener('wheel', ev => {
    ev.preventDefault();
    const r = canvas.getBoundingClientRect();
    const mx = ev.clientX - r.left - W / 2, my = ev.clientY - r.top - H / 2;
    const f = Math.exp(-ev.deltaY * 0.0015);
    panX += mx / scale - mx / (scale * f);
    panY -= my / scale - my / (scale * f);
    scale *= f;
    spinning = false;
    redraw();
  }, {passive: false});
  const resizer = new ResizeObserver(resize);
  resizer.observe(host);
  resize();

  const api = {
    setDim(keep) { dim = keep && keep.size ? keep : null; redraw(); },
    focus(key) {
      const i = index.get(key);
      if (i === undefined) return;
      spinning = false;
      scale = Math.max(scale, fit * 4);
      project();
      panX += (sx[i] - W / 2) / scale;
      panY -= (sy[i] - H / 2) / scale;
      redraw();
    },
    zoom(f) { scale *= f; redraw(); },
    spin(a) { spinning = false; yaw += a; redraw(); },
    tilt(a) { spinning = false; pitch = Math.min(Math.PI / 2, Math.max(-Math.PI / 2, pitch + a)); redraw(); },
    reset() { spinning = false; yaw = pitch = 0; dim = null; fitView(); redraw(); },
    rotating() { return spinning; },
    rotate(on) {
      spinning = on === undefined ? !spinning : !!on;
      last = 0;
      if (spinning && !hidden) requestAnimationFrame(tick);
      return spinning;
    },
    setLayout(name) { layout = name === 'groups' ? 'groups' : 'sky'; fitView(); redraw(); return layout; },
    layout() { return layout; },
    project(ks) {
      return ks.map(k => {
        const i = index.get(k);
        return i === undefined ? null
          : {x: sx[i], y: sy[i], z: 0, on: sx[i] >= 0 && sy[i] >= 0 && sx[i] <= W && sy[i] <= H};
      });
    },
    refresh() { redraw(); },
    pause() { hidden = true; },
    resume() {
      if (!hidden) return;
      hidden = false;
      last = 0;
      if (spinning) requestAnimationFrame(tick);
      redraw();
    },
    dispose() {
      gone = true;
      resizer.disconnect();
      canvas.width = canvas.height = 0;
      canvas.remove();
      tip.remove();
    },
  };
  return api;
}};
// System names next to their suns, placed greedily by priority (hovered, lit,
// then nearer and better connected); a name that would overlap one already
// placed is skipped, so zooming in reveals more of them.
const SUNS = [];
ATLAS.systems.forEach(s => {
  const sun = s.planets.find(p => p.slot === 'sun');
  if (sun) SUNS.push({key: s.id + '.' + sun.id, id: s.id, name: String(s.title || s.id).slice(0, 48)});
});
const DEGREE = new Map(SUNS.map(s => [s.id, 0]));
SCENE.edges.forEach(e => {
  if (!e.inter) return;
  [e.from, e.to].forEach(k => { const p = PLANETS.get(k); if (p && DEGREE.has(p.system.id)) DEGREE.set(p.system.id, DEGREE.get(p.system.id) + 1); });
});
const NAME_FONT = '11px system-ui, sans-serif';
const measureCtx = document.createElement('canvas').getContext('2d');
measureCtx.font = NAME_FONT;
const NAME_WIDTH = new Map(SUNS.map(s => [s.key, Math.ceil(measureCtx.measureText(s.name).width)]));
let showNames = true;
let hovered = null;
let namesKeep = null;
let namesDirty = true;
function placeNames(W, H, pos) {
  if (!showNames || !viewer) return [];
  pos = pos || viewer.project(SUNS.map(s => s.key));
  const keep = namesKeep;
  const hoverId = hovered && PLANETS.get(hovered) ? PLANETS.get(hovered).system.id : null;
  const cands = [];
  SUNS.forEach((s, i) => {
    const p = pos[i];
    if (!p || !p.on) return;
    const lit = !keep || keep.has(s.key);
    const boost = s.id === hoverId ? 3 : 0;
    if (!lit && !boost) return;
    cands.push({s, p, prio: boost + (keep && lit ? 2 : 0) + (1 - p.z) + DEGREE.get(s.id) * 0.01});
  });
  cands.sort((a, b) => b.prio - a.prio);
  const placed = [], budget = Math.max(12, Math.floor(W * H / 12000));
  for (const c of cands) {
    if (placed.length >= budget) break;
    const w = NAME_WIDTH.get(c.s.key), h = 14;
    const box = {x: c.p.x - w / 2, y: c.p.y - h - 7, w, h};
    if (box.x < 2 || box.y < 2 || box.x + w > W - 2 || box.y + h > H - 2) continue;
    if (placed.some(o => box.x < o.x + o.w + 6 && o.x < box.x + w + 6 && box.y < o.y + o.h + 2 && o.y < box.y + h + 2)) continue;
    placed.push(Object.assign(box, {s: c.s, lit: c.prio >= 2}));
  }
  return placed;
}
// 2D: names are drawn on the canvas whenever it redraws.
function drawNames(ctx, W, H) {
  ctx.font = NAME_FONT;
  ctx.textBaseline = 'top';
  ctx.lineJoin = 'round';
  placeNames(W, H).forEach(b => {
    ctx.lineWidth = 3;
    ctx.strokeStyle = '#0a0a10';
    ctx.strokeText(b.s.name, b.x, b.y + 1);
    ctx.fillStyle = b.lit ? '#ffffff' : '#f3d98b';
    ctx.fillText(b.s.name, b.x, b.y + 1);
  });
}
// 3D: an HTML layer over the WebGL canvas. Each frame only projects the suns;
// placement and DOM writes happen when the view moved by half a pixel or the
// dimming changed, and the loop stops whenever the viewer is paused.
const nameLayer = {running: false, stop: true, el: null};
function startNameLayer(host) {
  if (!nameLayer.el) {
    nameLayer.el = document.createElement('div');
    nameLayer.el.className = 'atlas-names';
    nameLayer.pool = new Map();
  }
  if (nameLayer.el.parentNode !== host) host.appendChild(nameLayer.el);
  const keys = SUNS.map(s => s.key);
  let last = null, lastW = 0, lastH = 0;
  function moved(pos, W, H) {
    if (!last || W !== lastW || H !== lastH) return true;
    for (let i = 0; i < pos.length; i++) {
      const a = pos[i], b = last[i];
      if (!a !== !b || (a && (Math.abs(a.x - b.x) > 0.5 || Math.abs(a.y - b.y) > 0.5 || a.on !== b.on))) return true;
    }
    return false;
  }
  function frame() {
    if (nameLayer.stop || !viewer || view !== '3d') { nameLayer.running = false; return; }
    const W = host.clientWidth, H = host.clientHeight;
    const pos = showNames ? viewer.project(keys) : null;
    if (namesDirty || (pos && moved(pos, W, H))) {
      namesDirty = false;
      last = pos; lastW = W; lastH = H;
      const shown = new Set();
      placeNames(W, H, pos).forEach(b => {
        let el = nameLayer.pool.get(b.s.key);
        if (!el) {
          el = document.createElement('div');
          el.textContent = b.s.name;
          nameLayer.pool.set(b.s.key, el);
          nameLayer.el.appendChild(el);
        }
        el.className = b.lit ? 'lit' : '';
        el.style.transform = 'translate(' + Math.round(b.x) + 'px,' + Math.round(b.y) + 'px)';
        el.style.display = '';
        shown.add(b.s.key);
      });
      nameLayer.pool.forEach((el, key) => { if (!shown.has(key)) el.style.display = 'none'; });
    }
    requestAnimationFrame(frame);
  }
  nameLayer.stop = false;
  namesDirty = true;
  if (!nameLayer.running) { nameLayer.running = true; requestAnimationFrame(frame); }
}
function stopNameLayer(remove) {
  nameLayer.stop = true;
  if (remove && nameLayer.el) { nameLayer.el.remove(); nameLayer.el = null; }
}
// Every dimming change goes through here, so the names know what is lit.
function dimTo(keep) {
  namesKeep = keep;
  namesDirty = true;
  if (viewer) viewer.setDim(keep);
}
const skyHost = document.getElementById('sky');
const gpuNote = document.getElementById('gpunote');
const viewButton = document.getElementById('viewmode');
const helpPanel = document.getElementById('panel');
const HELP_3D = helpPanel.textContent;
const HELP_2D = 'Vista 2D: arrastra para desplazar y usa la rueda para acercar; girar e inclinar cambian el ángulo. Pasa el cursor sobre un planeta para ver sus enlaces entre sistemas; haz clic para leer su evidencia y doble clic para centrarlo.';
const NOTES = {
  weak: '⚠ Este equipo no tiene una GPU adecuada para el cielo 3D (render por software): se muestra la constelación 2D.',
  none: '⚠ WebGL no está disponible aquí: se muestra la constelación 2D.',
  low: '⚠ Este equipo informa poca memoria o pocos núcleos: se muestra la constelación 2D, más liviana.',
  slow: '⚠ El cielo 3D se dibujaba demasiado lento aquí: se cambió a la constelación 2D, más liviana.',
};
const viewerHooks = {
  onSelect: key => { showPlanet(key); reportPlanet(key); },
  onHover: key => { hovered = key; dimTo(key ? hoverKeep(key) : familyKeep()); },
  afterDraw: drawNames,
};
let viewer = null;
let view = null;
let pageHidden = document.hidden;
let dashboardPaused = false;
function mountView(mode, reason) {
  const layout = viewer ? viewer.layout() : 'sky';
  if (viewer && viewer.dispose) viewer.dispose();
  stopNameLayer(true);
  viewer = null;
  skyHost.textContent = '';
  if (mode === '3d') viewer = AtlasViewer.mount(skyHost, SCENE, viewerHooks);
  if (!viewer) {
    if (mode === '3d') reason = 'none';
    mode = '2d';
    skyHost.textContent = '';
    viewer = FlatViewer.mount(skyHost, SCENE, viewerHooks);
  }
  view = mode;
  if (layout !== 'sky') viewer.setLayout(layout);
  dimTo(familyKeep());
  gpuNote.textContent = NOTES[reason] || '';
  gpuNote.hidden = !NOTES[reason];
  helpPanel.textContent = mode === '2d' ? HELP_2D : HELP_3D;
  viewButton.textContent = mode === '2d' ? 'Vista 3D' : 'Vista 2D';
  viewButton.disabled = mode === '2d' && webglSupport() === 'none';
  if (mode === '3d') startNameLayer(skyHost);
  applyVisibility();
  syncRotate();
  if (mode === '3d' && reason === 'auto') watchFrameRate();
}
// Draw nothing while nobody can see the sky: the page is hidden (another
// browser tab, a minimized window) or the dashboard paused it.
function applyVisibility() {
  if (!viewer) return;
  if (pageHidden || dashboardPaused) {
    viewer.pause();
    stopNameLayer(false);
  } else {
    viewer.resume();
    if (view === '3d') startNameLayer(skyHost);
  }
}
document.addEventListener('visibilitychange', () => { pageHidden = document.hidden; applyVisibility(); });
// A machine that passed the GPU check can still be too slow for the 3D sky:
// count frames for a few seconds after opening and fall back to 2D under 20 fps.
function watchFrameRate() {
  let frames = 0, start = 0;
  const mounted = viewer;
  function count(t) {
    if (viewer !== mounted || pageHidden || dashboardPaused) return;
    if (!start) start = t;
    frames++;
    if (t - start < 3000) { requestAnimationFrame(count); return; }
    if (frames * 1000 / (t - start) < 20) mountView('2d', 'slow');
  }
  setTimeout(() => requestAnimationFrame(count), 1000);
}
viewButton.addEventListener('click', () => {
  const next = view === '2d' ? '3d' : '2d';
  storeView(next);
  mountView(next, 'chosen');
});
const rotateButton = document.getElementById('autorotate');
function syncRotate() {
  if (!viewer) return;
  const on = viewer.rotating();
  rotateButton.classList.toggle('on', on);
  rotateButton.textContent = on ? '⏸ rotación' : '▶ rotación';
}
rotateButton.addEventListener('click', () => { if (viewer) { viewer.rotate(); syncRotate(); } });
skyHost.addEventListener('pointerdown', () => setTimeout(syncRotate, 0));
skyHost.addEventListener('wheel', () => setTimeout(syncRotate, 0), {passive: true});
const STEP = Math.PI / 12;
function act(id, fn) {
  document.getElementById(id).addEventListener('click', () => { if (viewer) { fn(); syncRotate(); } });
}
act('spinleft', () => viewer.spin(STEP));
act('spinright', () => viewer.spin(-STEP));
act('tiltup', () => viewer.tilt(STEP / 2));
act('tiltdown', () => viewer.tilt(-STEP / 2));
const namesButton = document.getElementById('names');
namesButton.addEventListener('click', () => {
  showNames = !showNames;
  namesDirty = true;
  namesButton.classList.toggle('on', showNames);
  if (viewer) viewer.refresh();
});
// Keep the hover label inside the sky: the viewer centers it over the planet.
skyHost.addEventListener('pointermove', () => {
  const tip = skyHost.querySelector('.atlas-tip');
  if (!tip || tip.style.display === 'none') return;
  const w = tip.offsetWidth, h = tip.offsetHeight, W = skyHost.clientWidth;
  tip.style.left = Math.min(Math.max(parseFloat(tip.style.left), w / 2 + 4), W - w / 2 - 4) + 'px';
  tip.style.transform = parseFloat(tip.style.top) < h * 1.3 + 4 ? 'translate(-50%, 30%)' : 'translate(-50%,-130%)';
});
const initial = chooseView();
mountView(initial.mode, initial.reason);
function resetView() {
  if (!viewer) return;
  activeFam = null;
  document.querySelectorAll('.famchip').forEach(c => c.classList.remove('on'));
  viewer.reset();
  dimTo(null);
  syncRotate();
}
const layoutButton = document.getElementById('grouplayout');
function applyLayout(mode) {
  if (!viewer) return;
  const now = viewer.setLayout(mode);
  layoutButton.classList.toggle('on', now === 'groups');
  tellParent({type: 'atlas-layout', mode: String(now)});
}
function toggleLayout() {
  if (viewer) applyLayout(viewer.layout() === 'groups' ? 'sky' : 'groups');
}
document.getElementById('zoomin').addEventListener('click', () => viewer && viewer.zoom(1.5));
document.getElementById('zoomout').addEventListener('click', () => viewer && viewer.zoom(1 / 1.5));
document.getElementById('zoomreset').addEventListener('click', resetView);
layoutButton.addEventListener('click', toggleLayout);
// Dashboard commands: only from the framing parent, only the named few.
const COMMANDS = {
  'group-layout': () => applyLayout('groups'),
  'sky-layout': () => applyLayout('sky'),
  'toggle-layout': toggleLayout,
  'reset': resetView,
  'pause': () => { dashboardPaused = true; applyVisibility(); },
  'resume': () => { dashboardPaused = false; applyVisibility(); },
  'view-2d': () => { storeView('2d'); mountView('2d', 'chosen'); },
  'view-3d': () => { storeView('3d'); mountView('3d', 'chosen'); },
};
// Two channels, one table: Morfeo's dashboard sends {type: 'atlas-control',
// cmd: 'pause' | 'resume'} when the graphs tab hides or shows; papersmith's
// {type: 'atlas-command', command} keeps working.
window.addEventListener('message', event => {
  if (!(event.source === window.parent) || window.parent === window) return;
  const data = event.data;
  if (!data || typeof data !== 'object') return;
  let command = null;
  if (data.type === 'atlas-control') command = data.cmd;
  else if (data.type === 'atlas-command') command = data.command;
  else return;
  if (typeof command !== 'string' || !Object.prototype.hasOwnProperty.call(COMMANDS, command)) return;
  COMMANDS[command]();
});
if (viewer) tellParent({type: 'atlas-layout', mode: String(viewer.layout())});
const chips = document.getElementById('famchips');
const fams = {};
ATLAS.systems.forEach(s => s.planets.forEach(p => {
  if (p.slot === 'family') fams[p.label] = (fams[p.label] || 0) + 1;
}));
Object.keys(fams).sort().forEach(label => {
  const b = document.createElement('button');
  b.textContent = label + ' (' + fams[label] + ')';
  b.className = 'famchip';
  b.addEventListener('click', () => {
    activeFam = (activeFam === label) ? null : label;
    document.querySelectorAll('.famchip').forEach(c => c.classList.toggle('on', c === b && activeFam === label));
    dimTo(familyKeep());
  });
  chips.appendChild(b);
});
// "Estudio de constelaciones": the panel is static HTML computed by the
// renderer; here it only collapses (narrow frames start collapsed) and a
// paper title flies to its sun.
const studyPanel = document.getElementById('study');
const studyButton = document.getElementById('studytoggle');
function setStudy(open) {
  studyPanel.hidden = !open;
  studyButton.classList.toggle('on', open);
  studyButton.setAttribute('aria-expanded', open ? 'true' : 'false');
  if (viewer) viewer.refresh();
}
setStudy(window.innerWidth >= 900);
studyButton.addEventListener('click', () => setStudy(studyPanel.hidden));
studyPanel.addEventListener('click', ev => {
  const target = ev.target.closest('[data-sun]');
  if (target && viewer) viewer.focus(target.getAttribute('data-sun'));
});
</script>
</body>
</html>
"""


def _viewer_bundle() -> str:
    return VIEWER.read_text(encoding="utf-8")


# --- Estudio de constelaciones ---------------------------------------------
# Computed from the atlas alone, no model in the loop: per family, its systems
# and their topic, problem, novelty and result planets; links counted by rel;
# every evidence origin with its retrieval dates.

#: Slots the study lists per family, in reading order, with their Spanish name.
STUDY_SLOTS = (
    ("topics", ("topic_app", "topic_ai"), "Temas"),
    ("problems", ("problem",), "Problemas"),
    ("novelties", ("novelty",), "Novedades"),
    ("results", ("result",), "Resultados"),
)

#: Relation order for the counts: the checker's closed set.
REL_ORDER = ("about", "addresses", "extends", "contradicts", "supports", "yields",
             "shares-family-with")

DEFAULT_TITLE = "Constelación SOTA"
DEFAULT_HEADING = "Constelación SOTA: un solo cielo"


def _natural(sid: str) -> tuple:
    """paper-2 before paper-10: digit runs compare as numbers."""
    import re
    return tuple(int(part) if part.isdigit() else part
                 for part in re.split(r"(\d+)", str(sid)))


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def study(atlas: dict) -> dict:
    """The constellation study as plain data (the HTML panel and the Markdown
    report both render this). Families sort by label, systems by paper number."""
    by_family: dict[str, list[dict]] = {}
    for system in atlas["systems"]:
        by_family.setdefault(_family_of(system), []).append(system)
    families = []
    for fam in sorted(by_family):
        members = sorted(by_family[fam], key=lambda s: _natural(s.get("id")))
        entry = {"family": fam or "(sin familia)", "systems": []}
        for key, _, _ in STUDY_SLOTS:
            entry[key] = []
        for system in members:
            planets = [p for p in system.get("planets") or [] if isinstance(p, dict)]
            sun = next((p for p in planets if p.get("slot") == "sun"), None)
            entry["systems"].append({
                "id": str(system.get("id")),
                "title": _text(system.get("title")) or str(system.get("id")),
                "sun": f"{system.get('id')}.{sun['id']}" if sun else None,
            })
            for key, slots, _ in STUDY_SLOTS:
                for planet in sorted((p for p in planets if p.get("slot") in slots),
                                     key=lambda p: (slots.index(p.get("slot")), str(p.get("id")))):
                    entry[key].append({"label": _text(planet.get("label")),
                                       "system": str(system.get("id"))})
        families.append(entry)
    relations = {rel: 0 for rel in REL_ORDER}
    for link in atlas.get("links") or []:
        if isinstance(link, dict):
            rel = str(link.get("rel"))
            relations[rel] = relations.get(rel, 0) + 1
    evidence: dict[str, dict] = {}
    for system in atlas["systems"]:
        for planet in system.get("planets") or []:
            ev = planet.get("evidence") if isinstance(planet, dict) else None
            if not isinstance(ev, dict) or not _text(ev.get("origin")):
                continue
            item = evidence.setdefault(_text(ev.get("origin")),
                                       {"origin": _text(ev.get("origin")), "systems": set(),
                                        "retrieved": set(), "quotes": 0})
            item["systems"].add(str(system.get("id")))
            if _text(ev.get("retrieved")):
                item["retrieved"].add(_text(ev.get("retrieved")))
            item["quotes"] += 1
    evidence_list = [{"origin": item["origin"],
                      "systems": sorted(item["systems"], key=_natural),
                      "retrieved": sorted(item["retrieved"]),
                      "quotes": item["quotes"]}
                     for item in evidence.values()]
    evidence_list.sort(key=lambda e: (_natural(e["systems"][0]) if e["systems"] else (), e["origin"]))
    planets = sum(len(s.get("planets") or []) for s in atlas["systems"])
    return {"families": families, "relations": relations, "evidence": evidence_list,
            "totals": {"systems": len(atlas["systems"]), "planets": planets,
                       "links": len(atlas.get("links") or []), "families": len(families)}}


def _slot_color(key: str) -> str:
    slots = next(slots for name, slots, _ in STUDY_SLOTS if name == key)
    return SLOT_COLORS[slots[0]]


def study_html(data: dict) -> str:
    """The side panel, escaped static HTML."""
    esc = html.escape
    totals = data["totals"]
    out = ['<aside id="study" aria-label="Estudio de constelaciones">',
           "<h2>Estudio de constelaciones</h2>",
           f'<p class="counts">{totals["systems"]} sistemas · {totals["planets"]} planetas · '
           f'{totals["links"]} relaciones · {totals["families"]} familias</p>']
    for fam in data["families"]:
        out.append(f"<h3>Familia: {esc(fam['family'])}</h3>")
        out.append("<h4>Sistemas</h4><ul>")
        for system in fam["systems"]:
            sun = f' data-sun="{esc(system["sun"])}"' if system["sun"] else ""
            out.append(f'<li><span class="sys"{sun}>{esc(system["title"])}</span> '
                       f'<span class="pid">{esc(system["id"])}</span></li>')
        out.append("</ul>")
        for key, _, name in STUDY_SLOTS:
            color = _slot_color(key)
            out.append(f'<h4><span class="dot" style="border-color:{color};margin-left:0">'
                       f"</span>{name}</h4><ul>")
            for item in fam[key]:
                out.append(f'<li>{esc(item["label"])} <span class="pid">{esc(item["system"])}</span></li>')
            out.append("</ul>")
    out.append("<h3>Relaciones por tipo</h3><ul>")
    for rel, count in data["relations"].items():
        color = REL_COLORS.get(rel, "#4a5a80")
        out.append(f'<li><span class="dot" style="border-color:{color};margin-left:0"></span>'
                   f"{esc(rel)}: {count}</li>")
    out.append("</ul><h3>Evidencias</h3><ul>")
    for item in data["evidence"]:
        out.append(f'<li><span class="pid">{esc(", ".join(item["systems"]))}</span> '
                   f'{esc(item["origin"])} · consultado {esc(", ".join(item["retrieved"]))} · '
                   f'{item["quotes"]} citas</li>')
    out.append("</ul></aside>")
    return "\n".join(out)


def study_markdown(data: dict) -> str:
    """The same study as Markdown, citable in the gates."""
    totals = data["totals"]
    lines = ["# Estudio de constelaciones", "",
             f"Corpus: {totals['systems']} sistemas, {totals['planets']} planetas, "
             f"{totals['links']} relaciones y {totals['families']} familias. "
             "Generado por scripts/render_atlas.py a partir de artefactos/scoping/atlas.json.",
             "", "## Familias", ""]
    for fam in data["families"]:
        lines.append(f"### Familia: {fam['family']}")
        lines.append("")
        lines.append("- Sistemas:")
        for system in fam["systems"]:
            lines.append(f"  - {system['id']}: {system['title']}")
        for key, _, name in STUDY_SLOTS:
            lines.append(f"- {name}:")
            for item in fam[key]:
                lines.append(f"  - {item['label']} ({item['system']})")
        lines.append("")
    lines += ["## Relaciones por tipo", ""]
    lines += [f"- {rel}: {count}" for rel, count in data["relations"].items()]
    lines += ["", "## Evidencias", ""]
    for item in data["evidence"]:
        lines.append(f"- {', '.join(item['systems'])}: {item['origin']} "
                     f"(consultado {', '.join(item['retrieved'])}; {item['quotes']} citas)")
    return "\n".join(lines) + "\n"


def render(atlas: dict, viewer: str | None = None, *,
           title: str | None = None, heading: str | None = None) -> str:
    """The whole page. ``title`` names the tab and, unless ``heading`` says
    otherwise, the heading too, so the page cannot contradict its own tab."""
    bundle = _viewer_bundle() if viewer is None else viewer
    if "</script" in bundle.lower():
        raise ValueError("the viewer bundle contains </script and cannot be inlined")
    if title is None:
        title, heading = DEFAULT_TITLE, heading or DEFAULT_HEADING
    elif heading is None:
        heading = title
    named = PAGE.replace("@@TITLE@@", html.escape(title))
    named = named.replace("@@HEADING@@", html.escape(heading))
    named = named.replace("@@STUDY@@", study_html(study(atlas)))
    data = json.dumps(_scene(atlas)).replace("<", "\\u003c")
    head, rest = named.split("@@DATA@@")
    middle, tail = rest.split("@@VIEWER@@")
    return head + data + middle + bundle + tail


USAGE = "usage: render_atlas.py <atlas.json> --out <html> [--report <md>] [--title <text>]"


def main(argv: list[str]) -> int:
    inputs: list[str] = []
    out_path: Path | None = None
    report_path: Path | None = None
    title: str | None = None
    tokens = argv[1:]
    index = 0
    while index < len(tokens):
        flag = tokens[index]
        if flag in ("--out", "--report", "--title") and index + 1 < len(tokens):
            value = tokens[index + 1]
            if flag == "--out":
                out_path = Path(value)
            elif flag == "--report":
                report_path = Path(value)
            else:
                title = value
            index += 2
        else:
            inputs.append(flag)
            index += 1
    if len(inputs) != 1 or inputs[0].startswith("--") or out_path is None:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        raw = Path(inputs[0]).read_text(encoding="utf-8")
    except OSError as error:
        print(f"ATLAS_UNREADABLE: {error}", file=sys.stderr)
        return 2
    try:
        atlas = json.loads(raw)
    except json.JSONDecodeError as error:
        print(f"ATLAS_NOT_JSON: {error}", file=sys.stderr)
        return 2
    shape_error = _readable_shape(atlas)
    if shape_error is not None:
        print(f"{shape_error}: run scripts/check_atlas.py first", file=sys.stderr)
        return 1
    try:
        page = render(atlas, title=title)
    except OSError as error:
        print(f"ATLAS_VIEWER_MISSING: {error} (expected {VIEWER})", file=sys.stderr)
        return 2
    except ValueError as error:
        print(f"ATLAS_VIEWER_UNSAFE: {error}", file=sys.stderr)
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    systems = len(atlas["systems"])
    print(f"ATLAS_RENDERED: {systems} systems in one sky -> {out_path}")
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(study_markdown(study(atlas)), encoding="utf-8")
        print(f"ATLAS_STUDY_WRITTEN: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
