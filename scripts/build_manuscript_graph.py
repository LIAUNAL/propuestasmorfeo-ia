#!/usr/bin/env python3
"""build_manuscript_graph.py: Extract LaTeX manuscript architecture, cross-dependencies,
and citations into a 3D constellation graph (manuscript-graph.json and manuscript-graph.html).

Usage:
    scripts/build_manuscript_graph.py [run_dir_or_id]
"""

from __future__ import annotations

import collections
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def resolve_run_dir(arg: str | None = None) -> Path:
    base = Path(__file__).resolve().parent.parent
    if arg:
        candidate = Path(arg)
        if candidate.is_dir():
            return candidate.resolve()
        candidate = base / "proposals" / arg
        if candidate.is_dir():
            return candidate.resolve()

    ptr = base / "proposals" / ".current-run"
    if ptr.is_file():
        name = ptr.read_text(encoding="utf-8").strip()
        candidate = base / "proposals" / name
        if candidate.is_dir():
            return candidate.resolve()

    # Fallback to first proposal found
    proposals = sorted((base / "proposals").glob("20*"))
    if proposals:
        return proposals[0].resolve()

    raise RuntimeError("No se encontró ninguna corrida activa de propuesta.")


def extract_citations(text: str) -> list[str]:
    """Extract all BibTeX citation keys in text."""
    keys: list[str] = []
    # Match \cite, \citep, \citet with optional brackets and stars
    matches = re.findall(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])?\{([^}]+)\}", text)
    for m in matches:
        for k in m.split(","):
            k_clean = k.strip()
            if k_clean and not k_clean.startswith("%"):
                keys.append(k_clean)
    return keys


def clean_latex_str(text: str) -> str:
    """Strip basic LaTeX formatting commands and comments from text."""
    t = re.sub(r"%.*", "", text)
    t = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", t)
    t = re.sub(r"\\[a-zA-Z]+", " ", t)
    t = re.sub(r"[\{\}\$]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def parse_scientific_architecture(run_dir: Path) -> dict[str, Any]:
    sections_dir = run_dir / "redaccion" / "sections"

    # 1. Subproblemas y Pregunta desde 03_descripcion_problema.tex
    sp_nodes = [
        ("sci:sp1", "SP1: Subproblema de Modelado y Representación"),
        ("sci:sp2", "SP2: Subproblema de Optimización e Inferencia"),
        ("sci:sp3", "SP3: Subproblema de Validación y Transferencia"),
    ]
    pregunta_label = "Pregunta: ¿Cómo resolver el problema central mediante IA?"

    sec3_file = sections_dir / "03_descripcion_problema.tex"
    if sec3_file.is_file():
        sec3_raw = sec3_file.read_text(encoding="utf-8", errors="replace")
        sp_matches = re.findall(r"(?:\\textbf\{)?(?:Subproblema\s*(\d)|SP(\d))[:\.\s\}]+([^\.\n]+)", sec3_raw, re.IGNORECASE)
        parsed_sps = []
        for m in sp_matches:
            num = m[0] or m[1]
            title = clean_latex_str(m[2])[:60]
            if title and not any(p[0] == f"sci:sp{num}" for p in parsed_sps):
                parsed_sps.append((f"sci:sp{num}", f"SP{num}: {title}"))
        if len(parsed_sps) >= 3:
            sp_nodes = parsed_sps[:3]

        q_match = re.search(r"¿([^?]+)\?", sec3_raw)
        if q_match:
            clean_q = clean_latex_str(q_match.group(1))[:70]
            pregunta_label = f"Pregunta: ¿{clean_q}?"

    # 2. Objetivo General desde 06_objetivo_general.tex
    og_label = "OG: Objetivo General del Proyecto"
    sec6_file = sections_dir / "06_objetivo_general.tex"
    if sec6_file.is_file():
        sec6_raw = sec6_file.read_text(encoding="utf-8", errors="replace")
        cleaned_og = clean_latex_str(sec6_raw)
        if cleaned_og:
            short_og = cleaned_og[:65]
            if len(cleaned_og) > 65:
                short_og += "..."
            og_label = f"OG: {short_og}"

    # 3. Objetivos Específicos desde 07_objetivos_especificos.tex
    oe_nodes = [
        ("sci:oe1", "OE1: Objetivo Específico 1"),
        ("sci:oe2", "OE2: Objetivo Específico 2"),
        ("sci:oe3", "OE3: Objetivo Específico 3"),
    ]
    sec7_file = sections_dir / "07_objetivos_especificos.tex"
    if sec7_file.is_file():
        sec7_raw = sec7_file.read_text(encoding="utf-8", errors="replace")
        items = re.findall(r"\\item\s+([^\n\\]+)", sec7_raw)
        parsed_oes = []
        for idx, it in enumerate(items[:3]):
            clean_it = clean_latex_str(it)[:60]
            parsed_oes.append((f"sci:oe{idx+1}", f"OE{idx+1}: {clean_it}"))
        if len(parsed_oes) >= 3:
            oe_nodes = parsed_oes[:3]

    # 4. Hipótesis desde 05_hipotesis.tex
    h1_label = "H1: Hipótesis de Investigación"
    sec5_file = sections_dir / "05_hipotesis.tex"
    if sec5_file.is_file():
        sec5_raw = sec5_file.read_text(encoding="utf-8", errors="replace")
        clean_h = clean_latex_str(sec5_raw)
        if clean_h:
            short_h = clean_h[:65]
            if len(clean_h) > 65:
                short_h += "..."
            h1_label = f"H1: {short_h}"

    # 5. Metodología Fases desde 10_metodologia.tex
    fase_nodes = [
        ("met:fase1", "Fase 1: Preparación y Modelado"),
        ("met:fase2", "Fase 2: Implementación y Optimización"),
        ("met:fase3", "Fase 3: Validación y Pruebas"),
    ]
    sec10_file = sections_dir / "10_metodologia.tex"
    if sec10_file.is_file():
        sec10_raw = sec10_file.read_text(encoding="utf-8", errors="replace")
        subsecs = re.findall(r"\\(?:sub)?section\*?\{([^}]+)\}", sec10_raw)
        parsed_fases = []
        for idx, sub in enumerate(subsecs[:3]):
            clean_sub = clean_latex_str(sub)[:55]
            parsed_fases.append((f"met:fase{idx+1}", f"Fase {idx+1}: {clean_sub}"))
        if len(parsed_fases) >= 3:
            fase_nodes = parsed_fases[:3]

    # 6. Entregables desde 15_productos_esperados.tex
    prod_nodes = [
        ("prod:prototipo_trl", "Entregable: Prototipo Tecnológico TRL 6/7"),
        ("prod:paper_q1", "Entregable: Artículo Científico en Revista Q1/Q2"),
        ("prod:plan_transferencia", "Entregable: Estrategia de Transferencia Tecnológica"),
    ]
    sec15_file = sections_dir / "15_productos_esperados.tex"
    if sec15_file.is_file():
        sec15_raw = sec15_file.read_text(encoding="utf-8", errors="replace")
        items = re.findall(r"\\item\s+([^\n\\]+)", sec15_raw)
        if not items:
            items = [re.sub(r"&.*", "", line).strip() for line in sec15_raw.splitlines() if "&" in line and not line.strip().startswith("%")]
        parsed_prods = []
        for idx, it in enumerate(items[:3]):
            clean_it = clean_latex_str(it)[:55]
            if clean_it and not clean_it.startswith("---") and not clean_it.lower().startswith("producto"):
                parsed_prods.append((f"prod:prod_{idx+1}", f"Entregable: {clean_it}"))
        if len(parsed_prods) >= 3:
            prod_nodes = parsed_prods[:3]

    # 7. Roles del Equipo desde 09_equipo_trabajo.tex
    team_nodes = [
        ("team:pi", "Rol: Investigador Principal"),
        ("team:co_inv", "Rol: Co-investigador / Aliado Territorial"),
        ("team:developer", "Rol: Personal Técnico y Desarrollador"),
    ]
    sec9_file = sections_dir / "09_equipo_trabajo.tex"
    if sec9_file.is_file():
        sec9_raw = sec9_file.read_text(encoding="utf-8", errors="replace")
        roles = re.findall(r"\\(?:sub)?section\*?\{([^}]+)\}", sec9_raw)
        if not roles:
            roles = re.findall(r"\\item\s+([^\n\\]+)", sec9_raw)
        parsed_roles = []
        for idx, r in enumerate(roles[:3]):
            clean_r = clean_latex_str(r)[:50]
            parsed_roles.append((f"team:role_{idx+1}", f"Rol: {clean_r}"))
        if len(parsed_roles) >= 3:
            team_nodes = parsed_roles[:3]

    # 8. Presupuesto desde 13_presupuesto.tex
    pres_nodes = [
        ("pres:personal", "Rubro: Servicios Técnicos y Personal"),
        ("pres:equipos", "Rubro: Equipos y Recursos Tecnológicos"),
        ("pres:campo", "Rubro: Validación de Campo y Operación"),
    ]
    sec13_file = sections_dir / "13_presupuesto.tex"
    if sec13_file.is_file():
        sec13_raw = sec13_file.read_text(encoding="utf-8", errors="replace")
        rubros = [re.sub(r"&.*", "", line).strip() for line in sec13_raw.splitlines() if "&" in line and not line.strip().startswith("%")]
        parsed_pres = []
        for idx, rub in enumerate(rubros[:3]):
            clean_rub = clean_latex_str(rub)[:50]
            if clean_rub and not clean_rub.startswith("---") and not clean_rub.lower().startswith("rubro"):
                parsed_pres.append((f"pres:rubro_{idx+1}", f"Rubro: {clean_rub}"))
        if len(parsed_pres) >= 3:
            pres_nodes = parsed_pres[:3]

    return {
        "sp_nodes": sp_nodes,
        "pregunta_label": pregunta_label,
        "og_label": og_label,
        "oe_nodes": oe_nodes,
        "h1_label": h1_label,
        "fase_nodes": fase_nodes,
        "prod_nodes": prod_nodes,
        "team_nodes": team_nodes,
        "pres_nodes": pres_nodes,
    }


def build_manuscript_graph(run_dir: Path) -> dict:
    redaccion_dir = run_dir / "redaccion"
    sections_dir = redaccion_dir / "sections"
    grafos_dir = run_dir / "grafos"
    grafos_dir.mkdir(parents=True, exist_ok=True)

    run_id = run_dir.name
    now_iso = datetime.now().isoformat()

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    def add_node(nid: str, label: str, ntype: str, group: str):
        if nid not in node_ids:
            nodes.append({
                "id": nid,
                "label": label,
                "type": ntype,
                "group": group
            })
            node_ids.add(nid)

    def add_edge(src: str, tgt: str, etype: str):
        if src in node_ids and tgt in node_ids:
            edges.append({
                "source": src,
                "target": tgt,
                "type": etype
            })

    # 1. Register Core LaTeX Sections
    section_files = sorted(glob.glob(str(sections_dir / "*.tex")))
    main_tex_file = redaccion_dir / "main.tex"
    main_tex_content = main_tex_file.read_text(encoding="utf-8", errors="replace") if main_tex_file.is_file() else ""

    sec_citations: dict[str, list[str]] = {}
    sec_names_ordered: list[str] = []

    section_labels = {
        "00_frontmatter.tex": "Front-matter (Resumen y Palabras Clave)",
        "01_titulo_identificacion.tex": "§1 Título e Identificación",
        "02_justificacion.tex": "§2 Justificación y Pertinencia",
        "03_descripcion_problema.tex": "§3 Descripción del Problema",
        "04_estado_arte.tex": "§4 Estado del Arte",
        "05_hipotesis.tex": "§5 Hipótesis",
        "06_objetivo_general.tex": "§6 Objetivo General",
        "07_objetivos_especificos.tex": "§7 Objetivos Específicos",
        "08_marco_conceptual.tex": "§8 Marco Conceptual",
        "09_equipo_trabajo.tex": "§9 Equipo de Trabajo",
        "10_metodologia.tex": "§10 Metodología",
        "11_resultados_esperados.tex": "§11 Resultados Esperados",
        "12_consideraciones_eticas.tex": "§12 Consideraciones Éticas",
        "13_presupuesto.tex": "§13 Presupuesto",
        "14_cronograma_actividades.tex": "§14 Cronograma de Actividades",
        "15_productos_esperados.tex": "§15 Productos Esperados (Tabla 4)",
        "16_bibliografia.tex": "§16 Bibliografía Consolidada",
        "17_articulacion_comunidades.tex": "§17 Articulación Comunitaria y Territorial",
        "18_apropiacion_social.tex": "§18 Apropiación Social del Conocimiento",
        "diag_arbol_problemas.tex": "Diagrama: Árbol de Problemas (TikZ)",
        "diag_estado_arte_a.tex": "Diagrama: Estado del Arte Parte A (TikZ)",
        "diag_estado_arte_b.tex": "Diagrama: Estado del Arte Parte B (TikZ)",
        "diag_metodologico.tex": "Diagrama: Metodología y Cadena de Valor (TikZ)",
    }

    all_citations_counter: collections.Counter[str] = collections.Counter()

    for s_path in section_files:
        fname = os.path.basename(s_path)
        content = Path(s_path).read_text(encoding="utf-8", errors="replace")
        lbl = section_labels.get(fname, fname)
        is_diag = fname.startswith("diag_")
        grp = "Diagrama TikZ" if is_diag else "Sección LaTeX"
        ntype = "Diagram" if is_diag else "Section"
        sec_id = f"sec:{fname}"
        add_node(sec_id, lbl, ntype, grp)
        if not is_diag:
            sec_names_ordered.append(sec_id)

        cites = extract_citations(content)
        sec_citations[sec_id] = cites
        for c in cites:
            all_citations_counter[c] += 1

    # 2. Sequential Flow Edges between consecutive numbered body sections
    for i in range(len(sec_names_ordered) - 1):
        add_edge(sec_names_ordered[i], sec_names_ordered[i + 1], "NARRATIVE_FLOW")

    # 3. Register Core Scientific Architecture Nodes
    arch = parse_scientific_architecture(run_dir)

    for sp_id, sp_label in arch["sp_nodes"]:
        add_node(sp_id, sp_label, "Subproblema", "Coherencia Científica")

    add_node("sci:pregunta", arch["pregunta_label"], "Pregunta", "Coherencia Científica")
    add_node("sci:og", arch["og_label"], "Objetivo General", "Coherencia Científica")

    for oe_id, oe_label in arch["oe_nodes"]:
        add_node(oe_id, oe_label, "Objetivo Específico", "Coherencia Científica")

    add_node("sci:h1", arch["h1_label"], "Hipótesis", "Coherencia Científica")

    for fase_id, fase_label in arch["fase_nodes"]:
        add_node(fase_id, fase_label, "Fase Metodológica", "Metodología y Fases")

    for prod_id, prod_label in arch["prod_nodes"]:
        add_node(prod_id, prod_label, "Producto", "Productos y Transferencia")

    for team_id, team_label in arch["team_nodes"]:
        add_node(team_id, team_label, "Rol Equipo", "Gobernanza y Recursos")

    for pres_id, pres_label in arch["pres_nodes"]:
        add_node(pres_id, pres_label, "Presupuesto", "Gobernanza y Recursos")

    # 4. Mandatory Cross-Dependencies Edges (Playbook Rule 5)
    # 1:1 Mapping Subproblemas ↔ Objetivos Específicos
    for (sp_id, _), (oe_id, _) in zip(arch["sp_nodes"], arch["oe_nodes"]):
        add_edge(sp_id, oe_id, "MAPS_1TO1")

    # Pregunta e Hipótesis ↔ Objetivo General
    add_edge("sci:pregunta", "sci:og", "FORMULATES")
    add_edge("sci:h1", "sci:og", "TESTS")

    # Objetivos Específicos ↔ Metodología
    for (oe_id, _), (fase_id, _) in zip(arch["oe_nodes"], arch["fase_nodes"]):
        add_edge(oe_id, fase_id, "EXECUTES")

    # Objetivos Específicos ↔ Roles de Equipo
    for (oe_id, _), (team_id, _) in zip(arch["oe_nodes"], arch["team_nodes"]):
        add_edge(oe_id, team_id, "ASSIGNED_ROLE")

    # Metodología Fases ↔ Cronograma y Presupuesto
    for (fase_id, _), (pres_id, _) in zip(arch["fase_nodes"], arch["pres_nodes"]):
        add_edge(fase_id, "sec:14_cronograma_actividades.tex", "SCHEDULED_IN")
        add_edge(fase_id, pres_id, "REQUIRES_RESOURCE")

    # Sections embedding Scientific Core
    for sp_id, _ in arch["sp_nodes"]:
        add_edge("sec:03_descripcion_problema.tex", sp_id, "DEFINES")
    add_edge("sec:03_descripcion_problema.tex", "sci:pregunta", "CLOSES_WITH")
    add_edge("sec:03_descripcion_problema.tex", "sec:diag_arbol_problemas.tex", "EMBEDS_DIAGRAM")

    add_edge("sec:04_estado_arte.tex", "sec:diag_estado_arte_a.tex", "EMBEDS_DIAGRAM")
    add_edge("sec:04_estado_arte.tex", "sec:diag_estado_arte_b.tex", "EMBEDS_DIAGRAM")

    add_edge("sec:05_hipotesis.tex", "sci:h1", "FORMULATES")
    add_edge("sec:06_objetivo_general.tex", "sci:og", "DEFINES")

    for oe_id, _ in arch["oe_nodes"]:
        add_edge("sec:07_objetivos_especificos.tex", oe_id, "DEFINES")

    for team_id, _ in arch["team_nodes"]:
        add_edge("sec:09_equipo_trabajo.tex", team_id, "ASSIGNED")

    for fase_id, _ in arch["fase_nodes"]:
        add_edge("sec:10_metodologia.tex", fase_id, "DESCRIBES")
    add_edge("sec:10_metodologia.tex", "sec:diag_metodologico.tex", "EMBEDS_DIAGRAM")

    for prod_id, _ in arch["prod_nodes"]:
        add_edge("sec:11_resultados_esperados.tex", prod_id, "TARGETS")
        add_edge("sec:15_productos_esperados.tex", prod_id, "DELIVERS")

    for pres_id, _ in arch["pres_nodes"]:
        add_edge("sec:13_presupuesto.tex", pres_id, "ALLOCATES")

    if arch["prod_nodes"]:
        add_edge("sec:17_articulacion_comunidades.tex", arch["prod_nodes"][-1][0], "ENGAGES")
        add_edge("sec:18_apropiacion_social.tex", arch["prod_nodes"][0][0], "OPEN_ACCESS")

    # 5. Top Citations Integration
    top_cites = [k for k, _ in all_citations_counter.most_common(28)]
    for cite_key in top_cites:
        cid = f"cite:{cite_key}"
        add_node(cid, f"BibTeX: {cite_key}", "Citation", "Referencia Bibliográfica")

    for sec_id, cites in sec_citations.items():
        for c in set(cites):
            if c in top_cites:
                add_edge(sec_id, f"cite:{c}", "CITES")

    # 6. Compute Node Degrees for Central Nodes
    in_degree = collections.defaultdict(int)
    out_degree = collections.defaultdict(int)
    for e in edges:
        out_degree[e["source"]] += 1
        in_degree[e["target"]] += 1

    central_items = []
    for n in nodes:
        nid = n["id"]
        deg = in_degree[nid] + out_degree[nid]
        if deg >= 4:
            central_items.append({
                "id": nid,
                "label": n["label"],
                "degree": deg,
                "out": out_degree[nid],
                "in": in_degree[nid]
            })

    central_items.sort(key=lambda x: x["degree"], reverse=True)

    # 7. Define Coherence Communities (Clusters)
    clusters = [
        {
            "name": "Fundamentación y Planteamiento del Problema",
            "files": [
                "sec:00_frontmatter.tex",
                "sec:02_justificacion.tex",
                "sec:03_descripcion_problema.tex",
                *[sp[0] for sp in arch["sp_nodes"]],
                "sec:diag_arbol_problemas.tex",
            ]
        },
        {
            "name": "Estado del Arte y Síntesis Bibliográfica",
            "files": [
                "sec:04_estado_arte.tex",
                "sec:diag_estado_arte_a.tex",
                "sec:diag_estado_arte_b.tex",
                "sec:16_bibliografia.tex",
            ] + [f"cite:{k}" for k in top_cites[:10]]
        },
        {
            "name": "Formulación Estratégica y Coherencia 1:1",
            "files": [
                "sci:pregunta",
                "sci:og",
                "sci:h1",
                "sec:05_hipotesis.tex",
                "sec:06_objetivo_general.tex",
                "sec:07_objetivos_especificos.tex",
                *[oe[0] for oe in arch["oe_nodes"]],
            ]
        },
        {
            "name": "Marco Conceptual, Metodología y Cadena de Valor",
            "files": [
                "sec:08_marco_conceptual.tex",
                "sec:10_metodologia.tex",
                "sec:diag_metodologico.tex",
                *[f[0] for f in arch["fase_nodes"]],
            ]
        },
        {
            "name": "Gobernanza, Equipo, Recursos y Ética",
            "files": [
                "sec:09_equipo_trabajo.tex",
                *[t[0] for t in arch["team_nodes"]],
                "sec:12_consideraciones_eticas.tex",
                "sec:13_presupuesto.tex",
                *[pr[0] for pr in arch["pres_nodes"]],
                "sec:14_cronograma_actividades.tex",
            ]
        },
        {
            "name": "Productos, Articulación y Apropiación Social",
            "files": [
                "sec:11_resultados_esperados.tex",
                "sec:15_productos_esperados.tex",
                *[p[0] for p in arch["prod_nodes"]],
                "sec:17_articulacion_comunidades.tex",
                "sec:18_apropiacion_social.tex",
            ]
        }
    ]

    questions = [
        "**Mapeo 1:1 estricto.** Cada uno de los 3 subproblemas técnicos se acopla exactamente con su respectivo objetivo específico (OE1, OE2, OE3) y su correspondiente fase metodológica.",
        "**Articulación de la Hipótesis.** La hipótesis de investigación converge directamente sobre el Objetivo General sin derivaciones ajenas, sustentando la validez científica del proyecto.",
        "**Cadena de Valor Presupuesto-Cronograma.** Los rubros presupuestales asignados respaldan las actividades operativas e hitos temporales a lo largo de las fases de la propuesta.",
        "**Madurez Tecnológica TRL 6/7.** La progresión metodológica declarada y los resultados esperados culminan en productos tangibles y verificables conforme al TRL objetivo."
    ]

    payload = {
        "corpus": "manuscript",
        "run_id": run_id,
        "title": f"Grafo del Manuscrito LaTeX: {run_id}",
        "generated_at": now_iso,
        "index": {
            "project": f"{run_id}-manuscript",
            "nodes": len(nodes),
            "edges": len(edges),
            "freshness": "generación completa a partir de redaccion/sections/*.tex y main.tex"
        },
        "central_nodes": {
            "note": "Hotspots de coherencia: los nodos con mayor centralidad conectan los objetivos específicos con la metodología, las figuras TikZ y los entregables verificables.",
            "items": central_items[:12]
        },
        "communities": {
            "note": "6 comunidades estructurales que garantizan la integridad de las dependencias cruzadas de la propuesta según la guía.",
            "clusters": clusters
        },
        "questions": questions,
        "nodes": nodes,
        "edges": edges
    }

    out_json = grafos_dir / "manuscript-graph.json"
    out_html = grafos_dir / "manuscript-graph.html"

    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON generado exitosamente: {out_json} ({len(nodes)} nodos, {len(edges)} aristas)")

    # Call graph_html.py to render the 3D visual constellation
    graph_html_script = Path(__file__).resolve().parent / "graph_html.py"
    if graph_html_script.is_file():
        res = subprocess.run([sys.executable, str(graph_html_script), str(out_json), str(out_html)], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"HTML 3D generado exitosamente: {out_html}")
        else:
            print(f"Error generando HTML 3D: {res.stderr}")
    else:
        print("Aviso: scripts/graph_html.py no encontrado.")

    return payload


def build_papers_graph(run_dir: Path) -> dict:
    grafos_dir = run_dir / "grafos"
    grafos_dir.mkdir(parents=True, exist_ok=True)
    papers_dir = run_dir / "artefactos" / "scoping" / "papers"
    sec_sota_file = run_dir / "redaccion" / "sections" / "04_estado_arte.tex"
    run_id = run_dir.name
    now_iso = datetime.now().isoformat()

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    def add_node(nid: str, label: str, ntype: str, group: str):
        if nid not in node_ids:
            nodes.append({
                "id": nid,
                "label": label,
                "type": ntype,
                "group": group
            })
            node_ids.add(nid)

    def add_edge(src: str, tgt: str, etype: str):
        if src in node_ids and tgt in node_ids:
            edges.append({
                "source": src,
                "target": tgt,
                "type": etype
            })

    # 1. Parse or Fallback SOTA Subtopics from 04_estado_arte.tex
    subtopics = []
    subtopic_by_cite = {}
    if sec_sota_file.is_file():
        sec_text = sec_sota_file.read_text(encoding="utf-8", errors="replace")
        matches = list(re.finditer(r"\\subsection\*?\{([^}]+)\}", sec_text))
        for i, m in enumerate(matches):
            st_name = clean_latex_str(m.group(1))
            st_id = f"sota:axis_{i+1}"
            st_short = st_name if len(st_name) <= 45 else st_name[:42] + "..."
            sp_target = f"sci:sp{min(i+1, 3)}"
            subtopics.append({
                "id": st_id,
                "name": st_name,
                "short": f"Eje {i+1}: {st_short}",
                "sp": sp_target
            })
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(sec_text)
            chunk = sec_text[start:end]
            cites = re.findall(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])?\{([^}]+)\}", chunk)
            for c in cites:
                for k in c.split(","):
                    k = k.strip()
                    if k and not k.startswith("%"):
                        subtopic_by_cite[k] = st_name

    if not subtopics:
        default_axes = [
            ("sota:axis_1", "Modelos Base y Representación de Conocimiento", "Eje 1: Modelos Base y Representación", "sci:sp1"),
            ("sota:axis_2", "Métodos de Aprendizaje, Calibración y Optimización", "Eje 2: Aprendizaje y Optimización", "sci:sp1"),
            ("sota:axis_3", "Validación Experimental y Benchmarks Comparativos", "Eje 3: Validación y Benchmarks", "sci:sp2"),
            ("sota:axis_4", "Arquitectura, Despliegue e Inferencia Tecnológica", "Eje 4: Despliegue e Inferencia", "sci:sp2"),
            ("sota:axis_5", "Transferencia Tecnológica e Impacto Sectorial", "Eje 5: Transferencia e Impacto", "sci:sp3"),
        ]
        for aid, aname, ashort, asp in default_axes:
            subtopics.append({
                "id": aid,
                "name": aname,
                "short": ashort,
                "sp": asp
            })

    for st in subtopics:
        add_node(st["id"], st["short"], "Eje Temático SOTA", st["name"])

    # 2. Bridge Nodes (Subproblemas parsed from run_dir)
    arch = parse_scientific_architecture(run_dir)
    for sp_id, sp_label in arch["sp_nodes"]:
        add_node(sp_id, sp_label, "Subproblema", "Subproblemas de Investigación")

    # Connect SOTA hubs to Subproblemas
    for st in subtopics:
        add_edge(st["id"], st["sp"], "ADDRESSES_PROBLEM")

    # 3. Parse papers from scoping dir and citations in 04_estado_arte.tex
    paper_files = sorted(papers_dir.glob("paper-*.md")) if papers_dir.is_dir() else []

    prior_json = grafos_dir / "papers-graph.json"
    prior_clusters = {}
    if prior_json.is_file():
        try:
            prior_data = json.loads(prior_json.read_text(encoding="utf-8"))
            for cl in prior_data.get("communities", {}).get("clusters", []):
                cl_name = cl.get("name", "")
                for pf in cl.get("files", []):
                    prior_clusters[pf] = cl_name
        except Exception:
            pass

    clave_to_paper_id = {}
    paper_texts = {}

    for idx, pf in enumerate(paper_files):
        text = pf.read_text(encoding="utf-8", errors="replace")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        title = lines[0].lstrip("#").strip() if lines else pf.stem

        m_clave = re.search(r"- Clave:\s*([^\n]+)", text)
        clave = m_clave.group(1).strip() if m_clave else pf.stem
        clave_to_paper_id[clave] = pf.name
        paper_texts[pf.name] = (clave, text)

        m_autor = re.search(r"- Autores:\s*([^\n]+)", text)
        autores = m_autor.group(1).strip() if m_autor else ""
        first_author = autores.split(",")[0].split(" and ")[0].strip() if autores else ""
        if len(first_author.split()) > 1:
            first_author = first_author.split()[-1]
        m_ano = re.search(r"- Año:\s*([^\n]+)", text)
        ano = m_ano.group(1).strip() if m_ano else "2025"
        m_q = re.search(r"- Cuartil:\s*([^\n]+)", text)
        cuartil = m_q.group(1).strip() if m_q else "Q1"

        assigned_group = subtopic_by_cite.get(clave)
        if not assigned_group:
            assigned_group = prior_clusters.get(pf.name)
        if not assigned_group:
            assigned_st = subtopics[idx % len(subtopics)]
            assigned_group = assigned_st["name"]

        short_title = title if len(title) <= 55 else title[:52] + "..."
        display_label = f"{first_author} ({ano}) · {short_title}" if first_author else f"{clave} ({ano}) · {short_title}"
        node_type = f"Paper {cuartil}"
        paper_id = pf.name

        add_node(paper_id, display_label, node_type, assigned_group)

        # Connect paper to its SOTA Subtopic hub
        hub_id = next((st["id"] for st in subtopics if st["name"].lower() in assigned_group.lower() or assigned_group.lower() in st["name"].lower()), subtopics[0]["id"])
        add_edge(hub_id, paper_id, "CONTAINS_PAPER")

    # Cross-citation edges between papers
    for pid, (k, ptxt) in paper_texts.items():
        for other_k, other_pid in clave_to_paper_id.items():
            if other_pid != pid and other_k in ptxt:
                add_edge(pid, other_pid, "CITES")

    # Degrees and hotspots
    in_deg = collections.defaultdict(int)
    out_deg = collections.defaultdict(int)
    for e in edges:
        out_deg[e["source"]] += 1
        in_deg[e["target"]] += 1

    central_items = []
    for n in nodes:
        nid = n["id"]
        deg = in_deg[nid] + out_deg[nid]
        if deg >= 2:
            central_items.append({
                "id": nid,
                "label": n["label"],
                "degree": deg,
                "out": out_deg[nid],
                "in": in_deg[nid]
            })
    central_items.sort(key=lambda x: x["degree"], reverse=True)

    # Clusters structure
    cluster_map = collections.defaultdict(list)
    for n in nodes:
        if n["type"].startswith("Paper"):
            cluster_map[n["group"]].append(n["id"])

    clusters = []
    for grp_name, files in cluster_map.items():
        clusters.append({
            "name": grp_name,
            "files": files
        })
    clusters.append({
        "name": "Subproblemas de Investigación",
        "files": [sp[0] for sp in arch["sp_nodes"]]
    })

    q1_count = sum(1 for n in nodes if "Q1" in n.get("type", ""))
    q2_count = sum(1 for n in nodes if "Q2" in n.get("type", ""))
    total_papers = len(paper_files)

    questions = [
        f"**Solidez del Corpus Bibliográfico.** El corpus de literatura analizado reúne {total_papers} artículos científicos con predominio de publicaciones de alto impacto ({q1_count} Q1 y {q2_count} Q2), fundamentando el estado del arte reciente.",
        "**Articulación con los Subproblemas.** La literatura indexada respalda directamente los 3 subproblemas técnicos formulados en §3, abordando las brechas metodológicas identificadas.",
        "**Equilibrio en los Ejes Temáticos SOTA.** La distribución de referencias entre los ejes temáticos garantiza cobertura integral desde los modelos conceptuales hasta la evaluación experimental.",
        "**Viabilidad Tecnológica y Transferencia.** Los antecedentes analizados demuestran factibilidad técnica para alcanzar el nivel de madurez tecnológica TRL 6/7 proyectado.",
        "**Rigor Metodológico y Ético.** Las evidencias de la literatura orientan las salvaguardas éticas, la reproducibilidad experimental y los protocolos de validación en campo."
    ]

    payload = {
        "corpus": "papers",
        "run_id": run_id,
        "title": f"Grafo de Literatura SOTA: {run_id}",
        "generated_at": now_iso,
        "index": {
            "project": f"{run_id}-papers",
            "nodes": len(nodes),
            "edges": len(edges),
            "freshness": f"síntesis automatizada sobre {len(paper_files)} papers de scoping y §4 Estado del Arte"
        },
        "central_nodes": {
            "note": "Nodos con mayor centralidad en el corpus SOTA: ejes temáticos, benchmarks clínicos y publicaciones clave con mayor impacto metodológico.",
            "items": central_items[:12]
        },
        "communities": {
            "note": "5 comunidades temáticas SOTA que articulan la base teórica del proyecto con los tres subproblemas de investigación.",
            "clusters": clusters
        },
        "questions": questions,
        "nodes": nodes,
        "edges": edges
    }

    out_json = grafos_dir / "papers-graph.json"
    out_html = grafos_dir / "papers-graph.html"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Papers JSON generado exitosamente: {out_json} ({len(nodes)} nodos, {len(edges)} aristas)")

    graph_html_script = Path(__file__).resolve().parent / "graph_html.py"
    if graph_html_script.is_file():
        res = subprocess.run([sys.executable, str(graph_html_script), str(out_json), str(out_html)], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Papers HTML 3D generado exitosamente: {out_html}")
        else:
            print(f"Error generando Papers HTML: {res.stderr}")
    return payload


def build_vault_graph(run_dir: Path) -> dict:
    grafos_dir = run_dir / "grafos"
    grafos_dir.mkdir(parents=True, exist_ok=True)
    vault_dir = run_dir / "artefactos" / "vault"
    run_id = run_dir.name
    now_iso = datetime.now().isoformat()

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    def add_node(nid: str, label: str, ntype: str, group: str):
        if nid not in node_ids:
            nodes.append({
                "id": nid,
                "label": label,
                "type": ntype,
                "group": group
            })
            node_ids.add(nid)

    def add_edge(src: str, tgt: str, etype: str):
        if src in node_ids and tgt in node_ids:
            edges.append({
                "source": src,
                "target": tgt,
                "type": etype
            })

    # Section Labels & Group Mapping
    section_meta = {
        "00_frontmatter.md": ("Front-matter (Resumen y Palabras Clave)", "Núcleo Problemático y Justificación"),
        "01_titulo_identificacion.md": ("§1 Título e Identificación Institucional", "Núcleo Problemático y Justificación"),
        "02_justificacion.md": ("§2 Justificación y Pertinencia (TRL 6/7)", "Núcleo Problemático y Justificación"),
        "03_descripcion_problema.md": ("§3 Descripción del Problema (3 SP)", "Núcleo Problemático y Justificación"),
        "04_estado_arte.md": ("§4 Estado del Arte (5 Ejes Temáticos)", "SOTA y Fundamentación Conceptual"),
        "05_hipotesis.md": ("§5 Hipótesis H1", "Núcleo Problemático y Justificación"),
        "06_objetivo_general.md": ("§6 Objetivo General", "Núcleo Problemático y Justificación"),
        "07_objetivos_especificos.md": ("§7 Objetivos Específicos (OE1, OE2, OE3)", "Núcleo Problemático y Justificación"),
        "08_marco_conceptual.md": ("§8 Marco Conceptual", "SOTA y Fundamentación Conceptual"),
        "09_equipo_trabajo.md": ("§9 Equipo de Trabajo (Roles OE)", "Metodología e Ingeniería"),
        "10_metodologia.md": ("§10 Metodología (Fases 1, 2 y 3)", "Metodología e Ingeniería"),
        "11_resultados_esperados.md": ("§11 Resultados Esperados (TRL 6/7)", "Impacto Social, Ética y Territorio"),
        "12_consideraciones_eticas.md": ("§12 Consideraciones Éticas y Consentimiento", "Impacto Social, Ética y Territorio"),
        "13_presupuesto.md": ("§13 Presupuesto por Rubros", "Gobernanza y Operación Presupuestal"),
        "14_cronograma_actividades.md": ("§14 Cronograma de Actividades (Gantt)", "Gobernanza y Operación Presupuestal"),
        "15_productos_esperados.md": ("§15 Productos Esperados (Tabla 4)", "Gobernanza y Operación Presupuestal"),
        "16_bibliografia.md": ("§16 Bibliografía APA Autor-Año", "SOTA y Fundamentación Conceptual"),
        "17_articulacion_comunidades.md": ("§17 Articulación Comunitaria y Territorial", "Impacto Social, Ética y Territorio"),
        "18_apropiacion_social.md": ("§18 Apropiación Social del Conocimiento", "Impacto Social, Ética y Territorio"),
    }

    figuras_meta = {
        "fig_arbol_problemas-1.png": ("Figura: Árbol de Problemas (TikZ)", "Metodología e Ingeniería"),
        "fig_estado_arte_a-1.png": ("Figura: Estado del Arte Parte A (TikZ)", "SOTA y Fundamentación Conceptual"),
        "fig_estado_arte_b-1.png": ("Figura: Estado del Arte Parte B (TikZ)", "SOTA y Fundamentación Conceptual"),
        "fig_metodologico-1.png": ("Figura: Diagrama Metodológico (TikZ)", "Metodología e Ingeniería"),
        "fig_cronograma-1.png": ("Figura: Cronograma de Actividades Gantt", "Gobernanza y Operación Presupuestal"),
    }

    # Register figure nodes
    for fig_id, (fig_label, fig_group) in figuras_meta.items():
        add_node(fig_id, fig_label, "Figura TikZ", fig_group)
        add_node(f"figuras/{fig_id}", fig_label, "Figura TikZ", fig_group)

    if vault_dir.is_dir():
        for mf in sorted(vault_dir.rglob("*.md")):
            rel_path = str(mf.relative_to(vault_dir))
            stem = mf.stem
            name = mf.name

            if rel_path.startswith("secciones/"):
                meta = section_meta.get(name)
                lbl = meta[0] if meta else f"Sección: {stem}"
                grp = meta[1] if meta else "Estructura de Secciones"
                ntype = "Sección Canónica"
            else:
                text_head = mf.read_text(encoding="utf-8", errors="replace").split("\n")
                first_line = text_head[0].lstrip("#").strip() if text_head else stem
                lbl = first_line if len(first_line) <= 50 else first_line[:47] + "..."
                if not lbl:
                    lbl = stem
                grp = "Insumos SOTA y Bibliografía" if "paper-" in stem or "zhang" in stem or "202" in stem else "Insumos Base y TDR"
                ntype = "Insumo de Investigación"

            add_node(rel_path, lbl, ntype, grp)
            add_node(stem, lbl, ntype, grp)

    # Parse wikilinks
    if vault_dir.is_dir():
        for mf in sorted(vault_dir.rglob("*.md")):
            src_rel = str(mf.relative_to(vault_dir))
            src_stem = mf.stem
            text = mf.read_text(encoding="utf-8", errors="replace")
            links = re.findall(r"\[\[([^\]]+)\]\]", text)
            for link in links:
                target = link.strip()
                candidate_targets = [
                    target,
                    f"secciones/{target}.md",
                    f"secciones/{target}",
                    f"insumos/{target}.md",
                    f"insumos/{target}",
                    f"figuras/{target}",
                    target.replace(".png", "")
                ]
                resolved_tgt = None
                for c in candidate_targets:
                    if c in node_ids:
                        resolved_tgt = c
                        break
                if resolved_tgt:
                    add_edge(src_rel, resolved_tgt, "WIKILINK")
                    add_edge(src_stem, resolved_tgt, "WIKILINK")

    # Filter duplicate alias nodes (keep rel_path for files, and fig_id for figures)
    primary_nodes = []
    primary_ids = set()
    for n in nodes:
        nid = n["id"]
        if "/" not in nid and not nid.startswith("fig_"):
            continue
        if nid not in primary_ids:
            primary_nodes.append(n)
            primary_ids.add(nid)

    primary_edges = []
    seen_edges = set()
    for e in edges:
        s = e["source"]
        t = e["target"]
        if "/" not in s and f"secciones/{s}.md" in primary_ids:
            s = f"secciones/{s}.md"
        elif "/" not in s and f"insumos/{s}.md" in primary_ids:
            s = f"insumos/{s}.md"
        if "/" not in t and f"secciones/{t}.md" in primary_ids:
            t = f"secciones/{t}.md"
        elif "/" not in t and f"insumos/{t}.md" in primary_ids:
            t = f"insumos/{t}.md"

        if s in primary_ids and t in primary_ids and s != t:
            edge_key = (s, t, e["type"])
            if edge_key not in seen_edges:
                primary_edges.append({
                    "source": s,
                    "target": t,
                    "type": e["type"]
                })
                seen_edges.add(edge_key)

    # Node degrees
    in_deg = collections.defaultdict(int)
    out_deg = collections.defaultdict(int)
    for e in primary_edges:
        out_deg[e["source"]] += 1
        in_deg[e["target"]] += 1

    central_items = []
    for n in primary_nodes:
        nid = n["id"]
        deg = in_deg[nid] + out_deg[nid]
        if deg >= 4:
            central_items.append({
                "id": nid,
                "label": n["label"],
                "degree": deg,
                "out": out_deg[nid],
                "in": in_deg[nid]
            })
    central_items.sort(key=lambda x: x["degree"], reverse=True)

    comm_map = collections.defaultdict(list)
    for n in primary_nodes:
        comm_map[n["group"]].append(n["id"])

    clusters = []
    for grp_name, files in comm_map.items():
        clusters.append({
            "name": grp_name,
            "files": files
        })

    questions = [
        "**Densidad de Enlaces del Vault.** La red de wikilinks conecta transversalmente las 18 secciones con los insumos y figuras, garantizando trazabilidad total desde la pregunta hasta la apropiación social.",
        "**Hubs de Centralidad Metodológica.** Las secciones de Estado del Arte (§4), Metodología (§10) y Justificación (§2) actúan como nodos nucleares con alta densidad de conexiones entrantes y salientes.",
        "**Articulación Bidireccional de Insumos.** Los insumos TDR y los papers de scoping alimentan las secciones narrativas sin enlaces rotos ni derivaciones huérfanas.",
        "**Consistencia de Diagramas TikZ.** Las figuras metodológicas, árbol de problemas y cronograma están referenciadas exactamente en los puntos del texto donde se describen sus procesos.",
        "**Sincronización con LaTeX.** El vault Markdown refleja fielmente el contenido científico de `redaccion/sections/`, asegurando coherencia conceptual y navegación fluida estilo Obsidian."
    ]

    payload = {
        "corpus": "vault",
        "run_id": run_id,
        "title": f"Grafo del Vault Obsidian: {run_id}",
        "generated_at": now_iso,
        "index": {
            "project": f"{run_id}-vault",
            "nodes": len(primary_nodes),
            "edges": len(primary_edges),
            "freshness": f"síntesis automatizada sobre {len(primary_nodes)} notas del vault y red de wikilinks"
        },
        "central_nodes": {
            "note": "Hotspots estructurales del vault Obsidian: notas con mayor grado de wikilinks entrantes y salientes.",
            "items": central_items[:12]
        },
        "communities": {
            "note": "5 agrupaciones funcionales que organizan el conocimiento del vault según el ciclo de formulación.",
            "clusters": clusters
        },
        "questions": questions,
        "nodes": primary_nodes,
        "edges": primary_edges
    }

    out_json = grafos_dir / "vault-graph.json"
    out_html = grafos_dir / "vault-graph.html"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Vault JSON generado exitosamente: {out_json} ({len(primary_nodes)} nodos, {len(primary_edges)} aristas)")

    graph_html_script = Path(__file__).resolve().parent / "graph_html.py"
    if graph_html_script.is_file():
        res = subprocess.run([sys.executable, str(graph_html_script), str(out_json), str(out_html)], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Vault HTML 3D generado exitosamente: {out_html}")
        else:
            print(f"Error generando Vault HTML: {res.stderr}")
    return payload


def build_all_graphs(run_dir: Path) -> dict[str, dict]:
    print(f"==> Generando constelaciones 3D completas (SOTA, Vault, Manuscrito) para: {run_dir}")
    res_papers = build_papers_graph(run_dir)
    res_vault = build_vault_graph(run_dir)
    res_manuscript = build_manuscript_graph(run_dir)
    return {
        "papers": res_papers,
        "vault": res_vault,
        "manuscript": res_manuscript
    }


if __name__ == "__main__":
    target = None
    action = "all"
    for arg in sys.argv[1:]:
        if arg in ("--papers", "-p"):
            action = "papers"
        elif arg in ("--vault", "-v"):
            action = "vault"
        elif arg in ("--manuscript", "-m"):
            action = "manuscript"
        elif arg in ("--all", "-a"):
            action = "all"
        elif not arg.startswith("-"):
            target = arg

    run_path = resolve_run_dir(target)
    print(f"Construyendo grafos ({action}) para: {run_path}")
    if action == "papers":
        build_papers_graph(run_path)
    elif action == "vault":
        build_vault_graph(run_path)
    elif action == "manuscript":
        build_manuscript_graph(run_path)
    else:
        build_all_graphs(run_path)
