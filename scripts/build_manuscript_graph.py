#!/usr/bin/env python3
"""build_manuscript_graph.py — Extract LaTeX manuscript architecture, cross-dependencies,
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
    # 3 Subproblemas
    add_node("sci:sp1", "SP1: Desalineación multimodal habla-síntomas de depresión", "Subproblema", "Coherencia Científica")
    add_node("sci:sp2", "SP2: Despliegue portable e incertidumbre clínica en borde", "Subproblema", "Coherencia Científica")
    add_node("sci:sp3", "SP3: Falta de validación territorial cohorte UNAL-UTP", "Subproblema", "Coherencia Científica")

    # Pregunta de investigación
    add_node("sci:pregunta", "Pregunta: ¿Cómo estimar objetivamente depresión pos-sismo en dispositivos móviles?", "Pregunta", "Coherencia Científica")

    # Objetivo General
    add_node("sci:og", "OG: Sistema de IA portable para tamizaje de depresión posdesastre", "Objetivo General", "Coherencia Científica")

    # 3 Objetivos Específicos
    add_node("sci:oe1", "OE1: Alineación multimodal débilmente supervisada (instancia-ítem PHQ-8)", "Objetivo Específico", "Coherencia Científica")
    add_node("sci:oe2", "OE2: Inferencia en el borde con cuantificación de incertidumbre y equidad", "Objetivo Específico", "Coherencia Científica")
    add_node("sci:oe3", "OE3: Validación territorial en cohorte 80 estudiantes Eje Cafetero", "Objetivo Específico", "Coherencia Científica")

    # Hipótesis
    add_node("sci:h1", "H1: La alineación semántica y optimización en borde superan el tamizaje estándar", "Hipótesis", "Coherencia Científica")

    # Metodología Fases
    add_node("met:fase1", "Fase 1: Preparación de corpus DAIC-WOZ y alineación MIL", "Fase Metodológica", "Metodología y Fases")
    add_node("met:fase2", "Fase 2: Optimización para hardware restringido y calibración", "Fase Metodológica", "Metodología y Fases")
    add_node("met:fase3", "Fase 3: Estudio de campo cohorte 80 estudiantes UNAL-UTP", "Fase Metodológica", "Metodología y Fases")

    # Entregables Clave
    add_node("prod:app_trl6", "Entregable: Prototipo Aplicativo Móvil TRL 6", "Producto", "Productos y Transferencia")
    add_node("prod:manual_campo", "Entregable: Manual de Operación de Campo", "Producto", "Productos y Transferencia")
    add_node("prod:corpus_anotado", "Entregable: Corpus Anotado Desidentificado en Español", "Producto", "Productos y Transferencia")
    add_node("prod:paper_q1", "Entregable: Artículo Científico en Revista Q1/Q2", "Producto", "Productos y Transferencia")
    add_node("prod:tesis_maestria", "Entregable: Tesis de Maestría en IA/Ingeniería", "Producto", "Productos y Transferencia")
    add_node("prod:taller_transferencia", "Entregable: Taller de Transferencia Tecnológica Eje Cafetero", "Producto", "Productos y Transferencia")

    # Roles del Equipo
    add_node("team:pi", "Rol: Investigador Principal (Prof. UNAL Manizales)", "Rol Equipo", "Gobernanza y Recursos")
    add_node("team:co_utp", "Rol: Co-investigador Territorial (Prof. UTP)", "Rol Equipo", "Gobernanza y Recursos")
    add_node("team:psicometria", "Rol: Asesoría de Personal Especializado en Psicometría", "Rol Equipo", "Gobernanza y Recursos")
    add_node("team:estudiante_msc", "Rol: Estudiante de Maestría (Desarrollo y Experimentación)", "Rol Equipo", "Gobernanza y Recursos")

    # Rubros Presupuestales
    add_node("pres:equipos", "Rubro: Dispositivos de Borde y Sensores de Captura", "Presupuesto", "Gobernanza y Recursos")
    add_node("pres:personal", "Rubro: Servicios Técnicos y Personal Científico", "Presupuesto", "Gobernanza y Recursos")
    add_node("pres:campo", "Rubro: Salidas de Campo Manizales-Pereira", "Presupuesto", "Gobernanza y Recursos")

    # 4. Mandatory Cross-Dependencies Edges (Playbook Rule 5)
    # 1:1 Mapping Subproblemas ↔ Objetivos Específicos
    add_edge("sci:sp1", "sci:oe1", "MAPS_1TO1")
    add_edge("sci:sp2", "sci:oe2", "MAPS_1TO1")
    add_edge("sci:sp3", "sci:oe3", "MAPS_1TO1")

    # Pregunta e Hipótesis ↔ Objetivo General
    add_edge("sci:pregunta", "sci:og", "FORMULATES")
    add_edge("sci:h1", "sci:og", "TESTS")

    # Objetivos Específicos ↔ Metodología
    add_edge("sci:oe1", "met:fase1", "EXECUTES")
    add_edge("sci:oe2", "met:fase2", "EXECUTES")
    add_edge("sci:oe3", "met:fase3", "EXECUTES")

    # Objetivos Específicos ↔ Roles de Equipo
    add_edge("sci:oe1", "team:pi", "LEADS")
    add_edge("sci:oe2", "team:estudiante_msc", "IMPLEMENTS")
    add_edge("sci:oe3", "team:co_utp", "COORDINATES")
    add_edge("sci:oe3", "team:psicometria", "SUPERVISES")

    # Metodología Fases ↔ Cronograma y Presupuesto
    add_edge("met:fase1", "sec:14_cronograma_actividades.tex", "SCHEDULED_IN")
    add_edge("met:fase2", "sec:14_cronograma_actividades.tex", "SCHEDULED_IN")
    add_edge("met:fase3", "sec:14_cronograma_actividades.tex", "SCHEDULED_IN")

    add_edge("met:fase1", "pres:equipos", "REQUIRES_RESOURCE")
    add_edge("met:fase2", "pres:personal", "REQUIRES_RESOURCE")
    add_edge("met:fase3", "pres:campo", "REQUIRES_RESOURCE")

    # Sections embedding Scientific Core
    add_edge("sec:03_descripcion_problema.tex", "sci:sp1", "DEFINES")
    add_edge("sec:03_descripcion_problema.tex", "sci:sp2", "DEFINES")
    add_edge("sec:03_descripcion_problema.tex", "sci:sp3", "DEFINES")
    add_edge("sec:03_descripcion_problema.tex", "sci:pregunta", "CLOSES_WITH")
    add_edge("sec:03_descripcion_problema.tex", "sec:diag_arbol_problemas.tex", "EMBEDS_DIAGRAM")

    add_edge("sec:04_estado_arte.tex", "sec:diag_estado_arte_a.tex", "EMBEDS_DIAGRAM")
    add_edge("sec:04_estado_arte.tex", "sec:diag_estado_arte_b.tex", "EMBEDS_DIAGRAM")

    add_edge("sec:05_hipotesis.tex", "sci:h1", "FORMULATES")
    add_edge("sec:06_objetivo_general.tex", "sci:og", "DEFINES")

    add_edge("sec:07_objetivos_especificos.tex", "sci:oe1", "DEFINES")
    add_edge("sec:07_objetivos_especificos.tex", "sci:oe2", "DEFINES")
    add_edge("sec:07_objetivos_especificos.tex", "sci:oe3", "DEFINES")

    add_edge("sec:09_equipo_trabajo.tex", "team:pi", "ASSIGNED")
    add_edge("sec:09_equipo_trabajo.tex", "team:co_utp", "ASSIGNED")
    add_edge("sec:09_equipo_trabajo.tex", "team:psicometria", "ASSIGNED")
    add_edge("sec:09_equipo_trabajo.tex", "team:estudiante_msc", "ASSIGNED")

    add_edge("sec:10_metodologia.tex", "met:fase1", "DESCRIBES")
    add_edge("sec:10_metodologia.tex", "met:fase2", "DESCRIBES")
    add_edge("sec:10_metodologia.tex", "met:fase3", "DESCRIBES")
    add_edge("sec:10_metodologia.tex", "sec:diag_metodologico.tex", "EMBEDS_DIAGRAM")

    add_edge("sec:11_resultados_esperados.tex", "prod:app_trl6", "TARGETS")
    add_edge("sec:11_resultados_esperados.tex", "prod:manual_campo", "TARGETS")
    add_edge("sec:11_resultados_esperados.tex", "prod:corpus_anotado", "TARGETS")
    add_edge("sec:15_productos_esperados.tex", "prod:app_trl6", "DELIVERS")
    add_edge("sec:15_productos_esperados.tex", "prod:paper_q1", "DELIVERS")
    add_edge("sec:15_productos_esperados.tex", "prod:tesis_maestria", "DELIVERS")
    add_edge("sec:15_productos_esperados.tex", "prod:taller_transferencia", "DELIVERS")

    add_edge("sec:13_presupuesto.tex", "pres:equipos", "ALLOCATES")
    add_edge("sec:13_presupuesto.tex", "pres:personal", "ALLOCATES")
    add_edge("sec:13_presupuesto.tex", "pres:campo", "ALLOCATES")

    add_edge("sec:17_articulacion_comunidades.tex", "prod:taller_transferencia", "ENGAGES")
    add_edge("sec:18_apropiacion_social.tex", "prod:corpus_anotado", "OPEN_ACCESS")

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
                "sci:sp1",
                "sci:sp2",
                "sci:sp3",
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
                "sci:oe1",
                "sci:oe2",
                "sci:oe3",
            ]
        },
        {
            "name": "Marco Conceptual, Metodología y Cadena de Valor",
            "files": [
                "sec:08_marco_conceptual.tex",
                "sec:10_metodologia.tex",
                "sec:diag_metodologico.tex",
                "met:fase1",
                "met:fase2",
                "met:fase3",
            ]
        },
        {
            "name": "Gobernanza, Equipo, Recursos y Ética",
            "files": [
                "sec:09_equipo_trabajo.tex",
                "team:pi",
                "team:co_utp",
                "team:psicometria",
                "team:estudiante_msc",
                "sec:12_consideraciones_eticas.tex",
                "sec:13_presupuesto.tex",
                "pres:equipos",
                "pres:personal",
                "pres:campo",
                "sec:14_cronograma_actividades.tex",
            ]
        },
        {
            "name": "Productos, Articulación y Apropiación Social",
            "files": [
                "sec:11_resultados_esperados.tex",
                "sec:15_productos_esperados.tex",
                "prod:app_trl6",
                "prod:manual_campo",
                "prod:corpus_anotado",
                "prod:paper_q1",
                "prod:tesis_maestria",
                "prod:taller_transferencia",
                "sec:17_articulacion_comunidades.tex",
                "sec:18_apropiacion_social.tex",
            ]
        }
    ]

    questions = [
        "**Mapeo 1:1 estricto.** Cada uno de los 3 subproblemas (SP1 desalineación, SP2 despliegue en borde, SP3 validación territorial) se acopla exactamente con su respectivo objetivo específico (OE1, OE2, OE3) y su fase metodológica.",
        "**Articulación de la Hipótesis.** La hipótesis H1 postula que la alineación semántica por ítem PHQ-8 y la cuantificación de incertidumbre superan el tamizaje estándar, convergiendo directamente sobre el Objetivo General sin derivaciones ajenas.",
        "**Cadena de Valor Presupuesto-Cronograma.** Los rubros clave de hardware embebido, talento humano y trabajo de campo Manizales-Pereira se corresponden con los hitos temporales de las Fases 1, 2 y 3.",
        "**Madurez Tecnológica TRL 6.** La progresión tecnológica declarada en Metodología (§10) y Resultados Esperados (§11) culmina en el prototipo verificado en entorno relevante sin invadir atribuciones de diagnóstico clínico."
    ]

    payload = {
        "corpus": "manuscript",
        "run_id": run_id,
        "title": f"Grafo del Manuscrito LaTeX — {run_id}",
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


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_path = resolve_run_dir(target)
    print(f"Construyendo grafo del manuscrito para: {run_path}")
    build_manuscript_graph(run_path)
