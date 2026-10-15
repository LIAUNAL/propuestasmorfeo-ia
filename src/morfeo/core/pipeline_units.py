"""Inventario canónico de las unidades del pipeline y sus compuertas.

Fuente única de los ids de unidad, de la compuerta de cada una y de los alias con
los que los artefactos las nombran. La tabla de
`.claude/commands/_propuesta-steps.md` se declara SSOT y esta lista la transcribe;
`tests/test_pipeline_units.py` ata las dos, de modo que una divergencia falle ahí
y no en el tablero.

Antes de este módulo el mismo modelo estaba escrito tres veces y las tres se
contradecían: la lista canónica de `status.py` no tenía `G1a` ni `G1b`, que la
corrida de referencia sí pasó, y en su lugar llevaba `G6` y `G6.45`, que la tabla
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
        "name": "Corpus SOTA y Semilla Bibliográfica",
        "phase": "Fase 1b",
        "reviewer": "Revisor",
        "criteria": "Corpus Q1/Q2 expandido, WRITE-REFS y los índices del vault construidos una sola vez.",
    },
    "G1": {
        "name": "Árbol de Problemas y Pregunta",
        "phase": "Fase 1",
        "reviewer": "Revisor",
        "criteria": "Subproblemas mutuamente excluyentes y árbol TikZ verificado.",
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
# `skills`: skills del marco que la unidad levanta.

PIPELINE_UNITS: list[dict[str, Any]] = [
    {
        "id": "fase0",
        "kind": "pre",
        "name": "Intake y enrutamiento de insumos",
        "gate": "G0.5",
        "sections": [],
        "agents": ["insumos-observador"],
        "skills": [],
        "next": "fase1a",
    },
    {
        "id": "g0_5",
        "kind": "pre",
        "name": "Guía ajustada al TDR (opcional)",
        "gate": None,
        "sections": [],
        "agents": [],
        "skills": [],
        "next": "fase1a",
    },
    {
        "id": "fase1a",
        "kind": "step",
        "name": "Scoping temprano y subproblemas",
        "gate": "G1a",
        "sections": [],
        "agents": ["bibliografo-propuesta", "investigador"],
        "skills": [],
        "next": "fase1b",
    },
    {
        "id": "fase1b",
        "kind": "step",
        "name": "Corpus SOTA y semilla bibliográfica",
        "gate": "G1b",
        "sections": [],
        "agents": ["bibliografo-propuesta"],
        "skills": [],
        "next": "fase1",
    },
    {
        "id": "fase1",
        "kind": "step",
        "name": "Problema, pregunta y árbol de problemas",
        "gate": "G1",
        "sections": ["03"],
        "agents": ["investigador", "grant-flow-auditor", "disenador-tikz", "revisor-figuras", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase2",
    },
    {
        "id": "fase2",
        "kind": "step",
        "name": "Estado del arte e hipótesis",
        "gate": "G2",
        "sections": ["04", "05"],
        "agents": ["bibliografo-propuesta", "investigador", "grant-flow-auditor", "disenador-tikz", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase3",
    },
    {
        "id": "fase3",
        "kind": "step",
        "name": "Justificación y pertinencia",
        "gate": "G3",
        "sections": ["02"],
        "agents": ["redactor", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es", "depuracion-redundancias-es"],
        "next": "fase4",
    },
    {
        "id": "fase4",
        "kind": "step",
        "name": "Objetivo general y objetivos específicos",
        "gate": "G4",
        "sections": ["06", "07"],
        "agents": ["investigador", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase5",
    },
    {
        "id": "fase5",
        "kind": "step",
        "name": "Marco conceptual y equipo de trabajo",
        "gate": "G5",
        "sections": ["08", "09"],
        "agents": ["investigador", "redactor", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase5_5",
    },
    {
        "id": "fase5_5",
        "kind": "step",
        "name": "Metodología y diagrama metodológico",
        "gate": "G5.5",
        "sections": ["10"],
        "agents": ["redactor", "grant-flow-auditor", "disenador-tikz", "revisor-figuras", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase6",
    },
    {
        "id": "fase6",
        "kind": "step",
        "name": "Resultados esperados y consideraciones éticas",
        "gate": None,
        "sections": ["11", "12"],
        "agents": ["redactor", "grant-flow-auditor"],
        "skills": ["estilo-natural-es"],
        "next": "fase6_4",
    },
    {
        "id": "fase6_4",
        "kind": "step",
        "name": "Presupuesto",
        "gate": "G6.4",
        "sections": ["13"],
        "agents": ["presupuestador", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase6_45",
    },
    {
        "id": "fase6_45",
        "kind": "step",
        "name": "Cronograma, productos y bibliografía",
        "gate": None,
        "sections": ["14", "15", "16"],
        "agents": ["redactor", "bibliografo-propuesta", "grant-flow-auditor"],
        "skills": ["estilo-natural-es"],
        "next": "fase6_46",
    },
    {
        "id": "fase6_46",
        "kind": "step",
        "name": "Articulación comunitaria y apropiación social",
        "gate": "G6.46",
        "sections": ["17", "18"],
        "agents": ["redactor", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es", "depuracion-redundancias-es"],
        "next": "fase6_5",
    },
    {
        "id": "fase6_5",
        "kind": "step",
        "name": "Front-matter y síntesis",
        "gate": "G6.5",
        "sections": ["00"],
        "agents": ["redactor", "grant-flow-auditor", "revisor"],
        "skills": ["estilo-natural-es"],
        "next": "fase7",
    },
    {
        "id": "fase7",
        "kind": "step",
        "name": "Auditoría final y ensamble",
        "gate": "G7",
        "sections": [],
        "agents": ["revisor", "coordinador-propuesta"],
        "skills": ["estilo-natural-es", "depuracion-redundancias-es"],
        "next": "done",
    },
]


def canonical_gates() -> list[dict[str, Any]]:
    """Compuertas en orden de pipeline, una por unidad que declare una.

    El orden es el del pipeline y no el alfabético: la lista alimenta el
    flujograma del tablero y su numeración visible.
    """
    gates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unit in PIPELINE_UNITS:
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
