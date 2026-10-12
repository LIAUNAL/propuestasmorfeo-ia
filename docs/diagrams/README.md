# Diagrama de Arquitectura y Flujo de Morfeo IA

`morfeo-pipeline-flow.html` es el diagrama canónico e interactivo de arquitectura del ecosistema **Morfeo IA**: documenta los 11 subagentes especializados, las 13 fases metodológicas, las 8 compuertas de revisión (*gates* G0.5–G7), los comandos del CLI, el tablero de seguimiento (*Command Center UI*), el bucle determinista de TikZ y la capa de grafos de conocimiento.

| Archivo | Descripción |
|---|---|
| [`morfeo-pipeline-flow.html`](./morfeo-pipeline-flow.html) | Artefacto HTML autónomo (*standalone*), navegable, sin dependencias de red |
| [`morfeo-pipeline-flow.png`](./morfeo-pipeline-flow.png) | Render gráfico PNG a alta resolución para visualización directa |
| [`morfeo-flow.build.mjs`](./morfeo-flow.build.mjs) | Código fuente generador en Node.js |
| `candidate.json` | Especificación JSON intermedia validada contra el esquema de Archify |

## Regeneración

Requisitos: Node.js y la skill Archify (`~/.claude/skills/archify`).

```bash
# 1. Generar la especificación candidate.json
node docs/diagrams/morfeo-flow.build.mjs docs/diagrams/candidate.json

# 2. Renderizar el artefacto interactivo con Archify
node ~/.claude/skills/archify/bin/archify.mjs render architecture \
  docs/diagrams/candidate.json docs/diagrams/morfeo-pipeline-flow.html \
  --repo-root .

# 3. Auditar cumplimiento de estándares visuales y métricas
node ~/.claude/skills/archify/bin/archify.mjs check docs/diagrams/morfeo-pipeline-flow.html
```

La auditoría mecánica verifica legibilidad de texto a 1440px, ausencia de colisiones en flechas, ortogonalidad de rutas y distancias mínimas entre etiquetas y nodos.
