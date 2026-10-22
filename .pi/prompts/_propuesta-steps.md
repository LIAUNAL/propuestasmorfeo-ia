# Canonical pipeline step table (SSOT)

**Not a slash command.** Reference fragment for `/propuesta-continuar`,
`/propuesta`, and `/propuesta-analizar`. Full Task recipes, codebase-memory
rules, and gate prose live in `.pi/prompts/propuesta.md` (body
ported from the historical monolith). This file defines **unit ids**,
**order**, and **what each unit covers** so stepped and auto modes cannot
diverge.

Also summarized in the pipeline body of `.pi/prompts/propuesta.md`; the canonical coordinador-propuesta reference document is not part of this port.

## Control de ejecución (`artefactos/estado_propuesta.md`)

Every run that uses analizar / continuar / auto MUST maintain:

```markdown
## Control de ejecución
- mode: stepped | auto
- next_step: <id> | done
- next_command: /propuesta-continuar | (none)
- last_completed: <id or gate id or empty>
- intake_complete: true | false
```

| Field | Meaning |
|-------|---------|
| `mode` | `stepped` after `/propuesta-analizar` or when using continuar; `auto` for `/propuesta` (single-session full pipeline) |
| `next_step` | Unit id to run next (see table below) |
| `next_command` | Usually `/propuesta-continuar` in stepped mode; `(none)` when `done` or in pure auto mid-session |
| `last_completed` | Last finished unit or gate |
| `intake_complete` | `true` after Fase 0 (+ G0.5 if applicable) finished |
| `idea` / `idea_source` | Resolved research idea and source (`arguments` \| `ideas/idea.md` \| `ideas/*` \| `user`) |

**Clearing state:** `/propuesta-limpiar` and ARCHIVADO-Y-REINICIO rewrite
`artefactos/estado_propuesta.md` to empty (0 bytes) — no stale `next_step`.

## Latido de la unidad en curso (`artefactos/pipeline/_en_curso.json`)

`artefactos/pipeline/NN-fase*.md` se escribe **al terminar** cada unidad, así que
por sí solo no puede decir qué está pasando ahora. Para eso el dispatcher
mantiene un latido: al abrir una unidad escribe

```json
{
  "fase": "<id de la unidad>",
  "agentes": ["<subagente>", "..."],
  "skill": "<skill o null>",
  "artefacto_esperado": "<ruta que va a escribir>",
  "inicio": "<ISO-8601>",
  "nota": "<paso en curso, opcional>"
}
```

en `artefactos/pipeline/_en_curso.json`. Antes de cada `subagent_run` de la unidad lo
reescribe con `agentes` y `skill` del despacho que arranca y una `nota` corta
del paso (por ejemplo `"nota": "Task → revisor (G1b)"`), para que el tablero
muestre el avance dentro de la unidad. Lo **borra** al cerrar la unidad, antes
de escribir su `NN-fase*.md`. El tablero lo lee y marca «EN CURSO» sobre esa
unidad, con sus agentes y su skill en el cajón. Un latido que no se borra miente:
si una unidad queda interrumpida, el latido se queda y el operador ve que ahí se
cortó, que es justo lo que hay que ver.

El tablero da una unidad por cumplida solo con tres pruebas: su compuerta en
PASS (o, sin compuerta, su `NN-<id>.md`), `next_step` ya más allá de ella, y sus
artefactos y secciones en disco (`artifacts` y `sections` de cada unidad en
`src/morfeo/core/pipeline_units.py`). Un latido de una unidad ya cumplida, o con
más de 6 h, se muestra como obsoleto y no bloquea el botón «Ejecutar».

## Step sequence (post-intake)

| `next_step` | Unit | Gate | On PASS → next |
|-------------|------|------|----------------|
| `fase1a` | Early scoping (bibliógrafo MODE=scope, codebase-memory scoping, investigador early) | G1a | `fase1a_sgr` (flujo SGR) o `fase1b` (flujo base) |
| `fase1a_sgr` | Solo flujo SGR: causas directas en lenguaje MGA (`artefactos/arboles/causas_directas.md`), modo plantilla de IA aplicada (levantamiento de datos, plataforma y modelos, apropiación) o exploratorio; el flujo base la salta | G causas | `fase1b` |
| `fase1b` | Árbol de problemas (spec + `figura.py`) y árbol de objetivos (`arbol_objetivos.json`) con las reglas MGA, en ambos flujos + revisor | G1b | `fase1c` |
| `fase1c` | SOTA corpus expansion + WRITE-REFS + vault codebase-memory once | G1c | `fase1` |
| `fase1` | MGA resumido (`artefactos/mga_resumido.md`) + §3 problema derivada de él + grant-flow-auditor + revisor | G1 | `fase2` |
| `fase2` | §4 SOTA + §5 hipótesis + grant-flow-auditor + spec del mapa SOTA (`figura.py`) + revisor | G2 | `fase3` |
| `fase3` | §2 justificación + grant-flow-auditor + revisor | G3 | `fase4` |
| `fase4` | §6–§7 objetivos + grant-flow-auditor + revisor | G4 | `fase5` |
| `fase5` | §8 marco + §9 equipo + grant-flow-auditor + revisor | G5 | `fase5_5` |
| `fase5_5` | §10 metodología + grant-flow-auditor + spec del diagrama (`figura.py`) + revisor | G5.5 | `fase6` |
| `fase6` | §11 resultados + §12 ética + grant-flow-auditor (no own gate) | — | `fase6_4` |
| `fase6_4` | §13 presupuesto + revisor | G budget | `fase6_45` |
| `fase6_45` | §14 cronograma + §15 productos (xltabular) + §16 bib + grant-flow-auditor (no own gate) | — | `fase6_46` |
| `fase6_46` | §17 articulación con comunidades + §18 apropiación social + grant-flow-auditor + revisor | G comunidades | `fase6_47` (flujo SGR) o `fase6_5` (flujo base) |
| `fase6_47` | Solo flujo SGR: anexos MGA 19 a 25 (`guiaProyectosIA_Agente_Regalias.md`) + revisor; el flujo base la salta | G anexos | `fase6_5` |
| `fase6_5` | Front-matter (Resumen, Resumen ejecutivo, Palabras clave; sin sección cuerpo de título) + grant-flow-auditor + revisor | G front | `fase7` |
| `fase7` | Final audit + assemble `main.tex` (\setcounter{section}{1}, xltabular, bibliografía limpia) | G final | `done` |
| `done` | Pipeline complete | — | print `cd proposal && ./build.sh` |

**Pre-intake units** (only in analizar / start of auto, not as `next_step` after
intake):

| Logical unit | Command | Sets after success |
|--------------|---------|-------------------|
| `fase0` | run-id, collision, insumos-observador, INTAKE, TDR/draft routing | (internal) |
| `g0_5` | Optional guide adjusted to TDR | `next_step: fase1a`, `intake_complete: true` |

## Stepped vs auto

| Mode | Behavior |
|------|----------|
| **stepped** | `/propuesta-continuar` runs **exactly one** row from the table, then stops and prints the next command |
| **auto** | Loop all rows in one session; stop only at gates that already require user approval |

Units without a formal gate (`fase6`, `fase6_45`) still **stop once** in
stepped mode after the unit finishes, so the operator always re-invokes
`/propuesta-continuar` deliberately.

## Recipe authority

For each unit id, execute the matching **Fase …** block in
`.pi/prompts/propuesta.md` (same content as the historical
`propuesta.md` pipeline). Do not invent alternate Task graphs.

**Diagram building is deterministic.** The three figure loops (Fases 1, 2 and
5.5) are defined once in the **"Bucle de figuras (canónico)"** section of
`propuesta.md` and referenced from each phase; never re-implement them per
phase. Their geometry comes from `scripts/render_tikz.py` (spec JSON → `.tex`),
not from a model drawing LaTeX, and the whole render + compile + autofix +
audit sequence is one command:

```bash
python3 scripts/figura.py <name> --spec specs/<name>.spec.json
```

`<name>` is `arbol_problemas`, `estado_arte` or `metodologico`. The command
exits non-zero if the sequence exceeds its 180 s budget, so a figure can never
silently exceed the 3-minute ceiling.

## Standardized Next Steps Output Banner (`## 🎯 NEXT STEPS`)

Every proposal command and agent execution phase MUST append a standardized `## 🎯 NEXT STEPS` block at the end of its response report.

Format:
```markdown
## 🎯 NEXT STEPS
- **Phase Completed**: [Phase / Step Name]
- **Files Modified**: `redaccion/...`, `artefactos/...`, `grafos/...`
- **Action Required**: Review changes or provide gate approval
- **Next Command**: `/propuesta-continuar` (or compilation instructions if done)
```

