"""Inventario canónico de las unidades del pipeline y sus compuertas.

Fuente única de los ids de unidad, de la compuerta de cada una y de los alias con
los que los artefactos las nombran. La tabla de
`.claude/commands/_propuesta-steps.md` se declara SSOT y esta lista la transcribe;
`tests/test_pipeline_units.py` ata las dos, de modo que una divergencia falle ahí
y no en el tablero.

Antes de este módulo el mismo modelo estaba escrito tres veces y las tres se
contradecían: la lista canónica de `status.py` no tenía `G1a` ni `G1b`, que la
corrida de referencia sí pasó (hoy `G1b` es la compuerta de los árboles y
`G1c` la del corpus SOTA), y en su lugar llevaba `G6` y `G6.45`, que la tabla
declara sin compuerta. El `13/13` que reportaba la corrida era la coincidencia de
dos treces distintos.
"""

from __future__ import annotations

from typing import Any

# --- Compuertas canónicas -------------------------------------------------
# El id numérico es el que usan los artefactos de una corrida. Los nombres en
# prosa de la tabla de pasos y las variantes que aparecen en los artefactos son
# alias que resuelven a él.

GATE_INFO: dict[str, dict[str, str]] = {
    "G0.5": {
        "name": "Ajuste de Guía al TDR",
        "phase": "Fase 0",
        "reviewer": "Usuario",
        "criteria": "Tabla de secciones del TDR aprobada y ajustada.",
    },
    "G1a": {
        "name": "Scoping Temprano y Subproblemas",
        "phase": "Fase 1a",
        "reviewer": "Revisor",
        "criteria": "Bibliografía de encuadre, scoping en codebase-memory y subproblemas tempranos mutuamente excluyentes.",
    },
    "G1b": {
        "name": "Árbol de Problemas y Árbol de Objetivos",
        "phase": "Fase 1b",
        "reviewer": "Revisor",
        "criteria": "Árbol de problemas y árbol de objetivos con las reglas MGA, sin hallazgos de error en check_run.",
    },
    "G1c": {
        "name": "Corpus SOTA y Semilla Bibliográfica",
        "phase": "Fase 1c",
        "reviewer": "Revisor",
        "criteria": "Corpus Q1/Q2 expandido, WRITE-REFS y los índices del vault construidos una sola vez.",
    },
    "G1": {
        "name": "MGA Resumido y Descripción del Problema",
        "phase": "Fase 1",
        "reviewer": "Revisor",
        "criteria": "MGA resumido con problema central, contexto, causas, magnitud y tabla de indicadores; §3 derivada de él.",
    },
    "G2": {
        "name": "Estado del Arte e Hipótesis",
        "phase": "Fase 2",
        "reviewer": "Revisor",
        "criteria": "≥30 referencias Q1/Q2 recientes e hipótesis falsable.",
    },
    "G3": {
        "name": "Justificación y Pertinencia",
        "phase": "Fase 3",
        "reviewer": "Revisor",
        "criteria": "Alineación ODS, PND y pertinencia tecnológica con TRL 6 o 7.",
    },
    "G4": {
        "name": "Objetivos General y Específicos",
        "phase": "Fase 4",
        "reviewer": "Revisor",
        "criteria": "Correspondencia biyectiva 1:1 entre subproblemas y objetivos.",
    },
    "G5": {
        "name": "Marco Conceptual y Equipo",
        "phase": "Fase 5",
        "reviewer": "Revisor",
        "criteria": "Teoría fundamental y roles de equipo derivados de objetivos.",
    },
    "G5.5": {
        "name": "Metodología y Diagrama TikZ",
        "phase": "Fase 5.5",
        "reviewer": "Revisor",
        "criteria": "Cadena de valor por fase, causalidad y esquema metodológico.",
    },
    "G6.4": {
        "name": "Presupuesto Financiero",
        "phase": "Fase 6.4",
        "reviewer": "Revisor",
        "criteria": "Aritmética exacta de rubros, topes y cofinanciación institucional.",
    },
    "G6.46": {
        "name": "Articulación Territorial y Comunitaria",
        "phase": "Fase 6.46",
        "reviewer": "Revisor",
        "criteria": "Estrategia de anclaje territorial y apropiación social del conocimiento.",
    },
    "GCausas": {
        "name": "Causas directas (flujo SGR)",
        "phase": "Fase 1a SGR",
        "reviewer": "Usuario",
        "criteria": "Los 3 subproblemas se acomodan a las 3 causas plantilla de IA aplicada (levantamiento de datos, plataforma y modelos, apropiación) o se reemplazan por 3 causas raíz propuestas en modo exploratorio, en lenguaje MGA.",
    },
    "G6.47": {
        "name": "Anexos MGA (flujo SGR)",
        "phase": "Fase 6.47",
        "reviewer": "Revisor",
        "criteria": "Alineación con planes, participantes, población, alternativas, cadena de valor, riesgos y marco lógico según la MGA.",
    },
    "G6.5": {
        "name": "Front-Matter y Síntesis",
        "phase": "Fase 6.5",
        "reviewer": "Revisor",
        "criteria": "Resumen ejecutivo, palabras clave y unicidad del título.",
    },
    "G7": {
        "name": "Auditoría Final y Ensamble",
        "phase": "Fase 7",
        "reviewer": "Revisor & Coordinador",
        "criteria": "Auditoría cruzada integral, 0 errores en LaTeX y compilación PDF.",
    },
}

# Nombres en prosa que usa la tabla de pasos. La prueba de deriva exige que
# sigan apareciendo en ella.
GATE_ALIASES: dict[str, str] = {
    "G budget": "G6.4",
    "G comunidades": "G6.46",
    "G anexos": "G6.47",
    "G causas": "GCausas",
    "G front": "G6.5",
    "G final": "G7",
}

# Variantes que aparecen en artefactos de corridas, no en la tabla.
ARTIFACT_ALIASES: dict[str, str] = {
    "G-Presupuesto": "G6.4",
}

# Etiquetas que nombran a una unidad **sin** compuerta. `G6` y `G6.45` las usó la
# corrida de referencia porque la lista canónica vieja las inventaba para `fase6`
# y `fase6_45`. Resuelven a None: no son compuertas.
LEGACY_GATELESS_LABELS = frozenset({"G6", "G6.45", "none", "n/a", "—", "-", ""})


def normalise_gate(raw: Any) -> str | None:
    """Resuelve el nombre de una compuerta a su id canónico, o a None si es una
    etiqueta sin compuerta. Un valor desconocido también cae a None: inventar una
    compuerta es justo el defecto que este módulo existe para evitar."""
    if raw is None:
        return None
    value = str(raw).strip()
    if value in LEGACY_GATELESS_LABELS:
        return None
    if value in GATE_ALIASES:
        return GATE_ALIASES[value]
    if value in ARTIFACT_ALIASES:
        return ARTIFACT_ALIASES[value]
    return value if value in GATE_INFO else None


# --- Unidades -------------------------------------------------------------
# `kind`: "pre" para el intake (no aparece como `next_step` después del intake),
# "step" para las unidades que la tabla de pasos encadena.
# `sections`: secciones del manuscrito que produce, por número, tal como aparecen
# en `redaccion/sections/NN_*.tex`.
# `artifacts`: otros archivos que la unidad deja dentro de la corrida, relativos a
# RUN_ROOT; un `*` final acepta cualquier archivo de esa carpeta. Con las
# secciones, son lo que el tablero comprueba para dar la unidad por cumplida.
# `skills`: skills del marco que la unidad levanta.
# `flujo`: solo en las unidades exclusivas de un flujo (hoy, los anexos MGA del
# flujo SGR). Las demás corren en todos los flujos; ver `units_for_flujo`.

PIPELINE_UNITS: list[dict[str, Any]] = [
    {
        "id": "fase0",
        "kind": "pre",
        "name": "Intake y enrutamiento de insumos",
        "desc": "Ingesta, clasificación y extracción de los insumos del usuario (documentos base, TDR, papers y enlaces) para estructurar el contexto compartido de la propuesta.",
        "gate": "G0.5",
        "sections": [],
        "artifacts": ["artefactos/insumos.md"],
        "agents": ["insumos-observador"],
        "skills": [],
        "next": "fase1a",
    },
    {
        "id": "g0_5",
        "kind": "pre",
        "name": "Guía ajustada al TDR (opcional)",
        "desc": "Cotejo preliminar de las secciones de la guía frente a los términos de referencia de la convocatoria, fijando requisitos específicos y restricciones formales.",
        "gate": None,
        "sections": [],
        "artifacts": ["artefactos/guia_ajustada_TDR.md"],
        "agents": [],
        "skills": [],
        "next": "fase1a",
    },
    {
        "id": "fase1a",
        "kind": "step",
        "name": "Scoping temprano y subproblemas",
        "desc": "Búsqueda bibliográfica de encuadre en el grafo de conocimiento para delimitar el alcance temático y postular los tres subproblemas preliminares mutuamente excluyentes.",
        "gate": "G1a",
        "sections": [],
        "artifacts": ["artefactos/scoping/papers/*"],
        "agents": ["bibliografo-propuesta", "investigador"],
        "skills": [],
        "next": "fase1a_sgr",
    },
    {
        "id": "fase1a_sgr",
        "kind": "step",
        "flujo": "sgr",
        "name": "Causas directas SGR",
        "desc": "Solo flujo SGR: compuerta que acomoda los tres subproblemas a las tres causas plantilla de un proyecto de IA aplicada (levantamiento de datos, plataforma y modelos, apropiación) o, en modo exploratorio, propone tres causas raíz desde la idea y el estado del arte.",
        "gate": "GCausas",
        "sections": [],
        "artifacts": ["artefactos/arboles/causas_directas.md"],
        "agents": ["investigador"],
        "skills": [],
        "next": "fase1b",
    },
    {
        "id": "fase1b",
        "kind": "step",
        "name": "Árbol de problemas y árbol de objetivos",
        "desc": "Construcción del árbol de problemas a partir de los subproblemas y de su espejo positivo, el árbol de objetivos, con las reglas de la MGA en ambos flujos; la figura TikZ del árbol se valida en el bucle de figuras.",
        "gate": "G1b",
        "sections": [],
        "artifacts": ["artefactos/arboles/arbol_problemas.md", "artefactos/arboles/arbol_objetivos.json"],
        "agents": ["investigador", "disenador-tikz", "revisor-figuras", "revisor"],
        "skills": [],
        "next": "fase1c",
    },
    {
        "id": "fase1c",
        "kind": "step",
        "name": "Corpus SOTA y semilla bibliográfica",
        "desc": "Consolidación del corpus de literatura Q1/Q2 reciente, extrayendo las referencias semilla e indexando el grafo de papers y el vault de conocimiento.",
        "gate": "G1c",
        "sections": [],
        "artifacts": ["redaccion/refs.bib"],
        "agents": ["bibliografo-propuesta"],
        "skills": [],
        "next": "fase1",
    },
    {
        "id": "fase1",
        "kind": "step",
        "name": "MGA resumido y descripción del problema",
        "desc": "Redacción del MGA resumido (problema central del árbol, contexto, expansión de las tres causas directas y magnitud con tabla de indicadores de línea base) y, a partir de él, de la descripción del problema (§3) con la pregunta central.",
        "gate": "G1",
        "sections": ["03"],
        "artifacts": ["artefactos/mga_resumido.md"],
        "agents": ["investigador", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase2",
    },
    {
        "id": "fase2",
        "kind": "step",
        "name": "Estado del arte e hipótesis",
        "desc": "Construcción del estado del arte con referencias Q1/Q2 (§4), formulación de la hipótesis falsable (§5) y elaboración del mapa visual del estado del arte.",
        "gate": "G2",
        "sections": ["04", "05"],
        "artifacts": [],
        "agents": ["bibliografo-propuesta", "investigador", "grant-flow-auditor", "disenador-tikz", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase3",
    },
    {
        "id": "fase3",
        "kind": "step",
        "name": "Justificación y pertinencia",
        "desc": "Elaboración de la justificación y pertinencia (§2), articulando la solución con los ODS, el PND y el nivel de madurez tecnológica TRL 6 o 7.",
        "gate": "G3",
        "sections": ["02"],
        "artifacts": [],
        "agents": ["redactor", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es", "depuracion-redundancias-es"],
        "next": "fase4",
    },
    {
        "id": "fase4",
        "kind": "step",
        "name": "Objetivo general y objetivos específicos",
        "desc": "Formulación del objetivo general (§6) y los tres objetivos específicos (§7), garantizando una correspondencia biyectiva estricta con los subproblemas.",
        "gate": "G4",
        "sections": ["06", "07"],
        "artifacts": [],
        "agents": ["investigador", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase5",
    },
    {
        "id": "fase5",
        "kind": "step",
        "name": "Marco conceptual y equipo de trabajo",
        "desc": "Desarrollo de los fundamentos teóricos (§8) y conformación del equipo de trabajo (§9), derivando roles operativos directamente de los objetivos específicos.",
        "gate": "G5",
        "sections": ["08", "09"],
        "artifacts": [],
        "agents": ["investigador", "redactor", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase5_5",
    },
    {
        "id": "fase5_5",
        "kind": "step",
        "name": "Metodología y diagrama metodológico",
        "desc": "Estructuración de la metodología (§10) por fases y cadena de valor, junto con la especificación y verificación determinista del diagrama en TikZ.",
        "gate": "G5.5",
        "sections": ["10"],
        "artifacts": [],
        "agents": ["redactor", "grant-flow-auditor", "disenador-tikz", "revisor-figuras", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase6",
    },
    {
        "id": "fase6",
        "kind": "step",
        "name": "Resultados esperados y consideraciones éticas",
        "desc": "Definición de los resultados e impactos esperados (§11) y fundamentación de las consideraciones éticas y de gestión de datos (§12).",
        "gate": None,
        "sections": ["11", "12"],
        "artifacts": [],
        "agents": ["redactor", "grant-flow-auditor"],
        "skills": ["estilo-natural-es"],
        "next": "fase6_4",
    },
    {
        "id": "fase6_4",
        "kind": "step",
        "name": "Presupuesto",
        "desc": "Construcción del presupuesto (§13) detallando rubros, contrapartidas y cofinanciación con balance aritmético verificable conforme al TDR.",
        "gate": "G6.4",
        "sections": ["13"],
        "artifacts": [],
        "agents": ["presupuestador", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase6_45",
    },
    {
        "id": "fase6_45",
        "kind": "step",
        "name": "Cronograma, productos y bibliografía",
        "desc": "Planificación del cronograma de actividades (§14, Gantt), consolidación de la tabla de productos entregables (§15) y bibliografía en BibTeX APA (§16).",
        "gate": None,
        "sections": ["14", "15", "16"],
        "artifacts": [],
        "agents": ["redactor", "bibliografo-propuesta", "grant-flow-auditor"],
        "skills": ["estilo-natural-es"],
        "next": "fase6_46",
    },
    {
        "id": "fase6_46",
        "kind": "step",
        "name": "Articulación comunitaria y apropiación social",
        "desc": "Diseño de la articulación comunitaria territorial (§17) y el plan de apropiación social del conocimiento (§18) con las comunidades de interés.",
        "gate": "G6.46",
        "sections": ["17", "18"],
        "artifacts": [],
        "agents": ["redactor", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es", "depuracion-redundancias-es"],
        "next": "fase6_47",
    },
    {
        "id": "fase6_47",
        "kind": "step",
        "flujo": "sgr",
        "name": "Anexos MGA",
        "desc": "Solo flujo SGR: alineación con los planes de desarrollo, participantes, población, alternativas, cadena de valor, riesgos y matriz de marco lógico.",
        "gate": "G6.47",
        "sections": ["19", "20", "21", "22", "23", "24", "25"],
        "artifacts": [],
        "agents": ["redactor", "presupuestador", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase6_5",
    },
    {
        "id": "fase6_5",
        "kind": "step",
        "name": "Front-matter y síntesis",
        "desc": "Redacción del resumen técnico, resumen ejecutivo institucional, palabras clave y verificación final del título definitivo en el encabezado.",
        "gate": "G6.5",
        "sections": ["00"],
        "artifacts": [],
        "agents": ["redactor", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase7",
    },
    {
        "id": "fase7",
        "kind": "step",
        "name": "Auditoría final y ensamble",
        "desc": "Auditoría cruzada integral de dependencias, verificación de consistencia entre secciones, ensamble del documento y compilación del PDF final.",
        "gate": "G7",
        "sections": [],
        "artifacts": ["redaccion/main.tex"],
        "agents": ["revisor", "coordinador-propuesta"],
        "skills": ["estilo-natural-es", "depuracion-redundancias-es"],
        "next": "done",
    },
]


def units_for_flujo(flujo: str | None) -> list[dict[str, Any]]:
    """Inventario de unidades de un flujo (`base` o `sgr`), en orden de pipeline.

    Un flujo desconocido es el base. Las unidades exclusivas de otro flujo se
    omiten y el `next` de la unidad previa salta sobre ellas, de modo que el
    flujo base nunca espera una compuerta que no le corresponde. Devuelve copias:
    el inventario canónico no se toca.
    """
    flujo = flujo if flujo in ("base", "sgr") else "base"
    kept = [dict(u) for u in PIPELINE_UNITS if u.get("flujo", flujo) == flujo]
    ids = {u["id"] for u in kept}
    by_id = {u["id"]: u for u in PIPELINE_UNITS}
    for unit in kept:
        nxt = unit.get("next")
        while nxt and nxt not in ids and nxt in by_id:
            nxt = by_id[nxt].get("next")
        if "next" in unit:
            unit["next"] = nxt
    return kept


def canonical_gates(flujo: str | None = None) -> list[dict[str, Any]]:
    """Compuertas en orden de pipeline, una por unidad que declare una.

    El orden es el del pipeline y no el alfabético: la lista alimenta el
    flujograma del tablero y su numeración visible. Con `flujo`, solo las
    compuertas de ese flujo; sin él, todas.
    """
    gates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unit in (PIPELINE_UNITS if flujo is None else units_for_flujo(flujo)):
        gate = unit.get("gate")
        if not gate or gate in seen:
            continue
        seen.add(gate)
        info = GATE_INFO.get(gate)
        if info is None:
            raise KeyError(
                f"la unidad {unit['id']} declara la compuerta {gate}, que no está en GATE_INFO"
            )
        gates.append({"id": gate, **info})
    return gates


def unit_by_id(unit_id: str) -> dict[str, Any] | None:
    for unit in PIPELINE_UNITS:
        if unit["id"] == unit_id:
            return unit
    return None


def unit_for_gate(gate_id: str) -> dict[str, Any] | None:
    canonical = normalise_gate(gate_id)
    if canonical is None:
        return None
    for unit in PIPELINE_UNITS:
        if unit.get("gate") == canonical:
            return unit
    return None
