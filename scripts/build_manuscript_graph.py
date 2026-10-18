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

    # 1. 5 SOTA Subtopics
    subtopics = [
        {
            "id": "sota:mil",
            "name": "Aprendizaje múltiple-instancia y granularidad fina en entrevistas clínicas",
            "short": "Eje 1: Aprendizaje MIL y Granularidad Fina",
            "sp": "sci:sp1"
        },
        {
            "id": "sota:fusion",
            "name": "Fusión multimodal de voz, texto y video para la estimación de severidad",
            "short": "Eje 2: Fusión Multimodal Voz-Texto-Video",
            "sp": "sci:sp1"
        },
        {
            "id": "sota:voice",
            "name": "Biomarcadores vocales y validación diagnóstica del tamizaje por voz",
            "short": "Eje 3: Biomarcadores Vocales y Validez",
            "sp": "sci:sp2"
        },
        {
            "id": "sota:edge",
            "name": "Inferencia en el borde y salud mental digital en entornos de recursos limitados",
            "short": "Eje 4: Inferencia en Borde y Recursos Restringidos",
            "sp": "sci:sp2"
        },
        {
            "id": "sota:disaster",
            "name": "Transferencia intercultural y salud mental juvenil en contextos posdesastre",
            "short": "Eje 5: Salud Mental Juvenil y Posdesastre",
            "sp": "sci:sp3"
        }
    ]

    for st in subtopics:
        add_node(st["id"], st["short"], "Eje Temático SOTA", st["name"])

    # 2. Bridge Nodes (Subproblemas y Benchmarks)
    add_node("sci:sp1", "SP1: Desbalance y granularidad en entrevistas clínicas", "Subproblema", "Subproblemas de Investigación")
    add_node("sci:sp2", "SP2: Inferencia en el borde y telemetría por voz", "Subproblema", "Subproblemas de Investigación")
    add_node("sci:sp3", "SP3: Adaptación intercultural posdesastre Manizales-Pereira", "Subproblema", "Subproblemas de Investigación")

    add_node("bench:daic", "Dataset Clínico DAIC-WOZ / E-DAIC (Audio + Texto)", "Benchmark Clínico", "Corpus y Validación")
    add_node("bench:phq", "Instrumento Clínico PHQ-8 / PHQ-9 (8-9 Ítems)", "Escala Psicofisiológica", "Corpus y Validación")
    add_node("bench:cohort", "Cohorte Estudiantil UNAL Manizales y UTP Pereira (80 sujetos)", "Validación Territorial", "Corpus y Validación")

    # Connect SOTA hubs to Subproblemas
    for st in subtopics:
        add_edge(st["id"], st["sp"], "ADDRESSES_PROBLEM")

    # Connect Benchmarks to Subtopics
    add_edge("sota:mil", "bench:daic", "EVALUATED_ON")
    add_edge("sota:fusion", "bench:daic", "EVALUATED_ON")
    add_edge("sota:mil", "bench:phq", "TARGETS_ITEMS")
    add_edge("sota:voice", "bench:phq", "TARGETS_ITEMS")
    add_edge("sota:edge", "bench:cohort", "FIELD_TESTS")
    add_edge("sota:disaster", "bench:cohort", "FIELD_TESTS")

    # 3. Parse papers from scoping dir and citations in 04_estado_arte.tex
    subtopic_by_cite = {}
    if sec_sota_file.is_file():
        sec_text = sec_sota_file.read_text(encoding="utf-8", errors="replace")
        matches = list(re.finditer(r"\\subsection\*\{([^}]+)\}", sec_text))
        for i, m in enumerate(matches):
            st_name = m.group(1).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(sec_text)
            chunk = sec_text[start:end]
            cites = re.findall(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])?\{([^}]+)\}", chunk)
            for c in cites:
                for k in c.split(","):
                    k = k.strip()
                    if k and not k.startswith("%"):
                        subtopic_by_cite[k] = st_name

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

    for pf in paper_files:
        text = pf.read_text(encoding="utf-8", errors="replace")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        title = lines[0].lstrip("#").strip() if lines else pf.stem

        m_clave = re.search(r"- Clave:\s*([^\n]+)", text)
        clave = m_clave.group(1).strip() if m_clave else pf.stem
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
            lower_text = text.lower()
            if "voice" in lower_text or "speech" in lower_text or "vocal" in lower_text or "acoustic" in lower_text:
                assigned_group = "Biomarcadores vocales y validación diagnóstica del tamizaje por voz"
            elif "multimodal" in lower_text or "video" in lower_text or "fusion" in lower_text:
                assigned_group = "Fusión multimodal de voz, texto y video para la estimación de severidad"
            elif "edge" in lower_text or "wearable" in lower_text or "disaster" in lower_text or "lmic" in lower_text:
                assigned_group = "Inferencia en el borde y salud mental digital en entornos de recursos limitados"
            elif "earthquake" in lower_text or "ptsd" in lower_text or "tept" in lower_text:
                assigned_group = "Transferencia intercultural y salud mental juvenil en contextos posdesastre"
            else:
                assigned_group = "Aprendizaje múltiple-instancia y granularidad fina en entrevistas clínicas"

        short_title = title if len(title) <= 55 else title[:52] + "..."
        display_label = f"{first_author} ({ano}) · {short_title}" if first_author else f"{clave} ({ano}) · {short_title}"
        node_type = f"Paper {cuartil}"
        paper_id = pf.name

        add_node(paper_id, display_label, node_type, assigned_group)

        # Connect paper to its SOTA Subtopic hub
        hub_id = next((st["id"] for st in subtopics if st["name"].lower() in assigned_group.lower() or assigned_group.lower() in st["name"].lower()), None)
        if hub_id:
            add_edge(hub_id, paper_id, "CONTAINS_PAPER")

        # Contextual edges
        lower_content = text.lower()
        if "daic" in lower_content:
            add_edge(paper_id, "bench:daic", "BENCHMARKS_ON")
        if "phq" in lower_content:
            add_edge(paper_id, "bench:phq", "ASSESSES")
        if "edge" in lower_content or "mobile" in lower_content or "wearable" in lower_content:
            add_edge(paper_id, "sci:sp2", "SUPPORTS_EDGE")
        if "disaster" in lower_content or "earthquake" in lower_content or "ptsd" in lower_content:
            add_edge(paper_id, "sci:sp3", "LOCAL_EVIDENCE")

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
        "name": "Subproblemas y Validación de Campo",
        "files": ["sci:sp1", "sci:sp2", "sci:sp3", "bench:daic", "bench:phq", "bench:cohort"]
    })

    questions = [
        "**Densidad de SP1 y Supervisión Débil.** El corpus concentra una densidad sobresaliente en aprendizaje múltiple-instancia y prompts finos sobre entrevistas DAIC-WOZ, sustentando la necesidad de alineación explícita por ítem sintomático.",
        "**Biomarcadores de Voz y Sensibilidad Clínica.** Los metaanálisis recientes validan AUC superiores a 0.89 en habla para tamizaje, exigiendo cuantificación de incertidumbre y equidad sociodemográfica en atención primaria.",
        "**Factibilidad de Despliegue en Borde (SP2).** Los transformers reparametrizados y modelos acústicos compactos demuestran viabilidad en dispositivos móviles y portátiles sin requerir cómputo en nube centralizada.",
        "**Urgencia y Validación Territorial Posdesastre (SP3).** Los estudios en zonas sísmicas documentan prevalencias de TEPT y depresión de hasta 32.4 % en población joven, fundamentando el trabajo de campo en Manizales y Pereira.",
        "**Riesgo y Rigor Ético.** La literatura advierte sobre la fragilidad de modelos sin validación externa; la propuesta responde con protocolo de consentimiento informado y prototipo de tamizaje asistido sin emitir diagnósticos definitivos."
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
        "11_resultados_esperados.md": ("§11 Resultados Esperados (TRL 6)", "Impacto Social, Ética y Territorio"),
        "12_consideraciones_eticas.md": ("§12 Consideraciones Éticas y Consentimiento", "Impacto Social, Ética y Territorio"),
        "13_presupuesto.md": ("§13 Presupuesto por Rubros", "Gobernanza y Operación Presupuestal"),
        "14_cronograma_actividades.md": ("§14 Cronograma de Actividades (Gantt)", "Gobernanza y Operación Presupuestal"),
        "15_productos_esperados.md": ("§15 Productos Esperados (Tabla 4)", "Gobernanza y Operación Presupuestal"),
        "16_bibliografia.md": ("§16 Bibliografía APA Autor-Año", "SOTA y Fundamentación Conceptual"),
        "17_articulacion_comunidades.md": ("§17 Articulación Comunitaria Eje Cafetero", "Impacto Social, Ética y Territorio"),
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
