# Canonical pipeline step table (SSOT)

**Not a slash command.** Reference fragment for `/propuesta-continuar`,
`/propuesta`, and `/propuesta-analizar`. Full Task recipes, codebase-memory
rules, and gate prose live in `.claude/commands/propuesta.md` (body
ported from the historical monolith). This file defines **unit ids**,
**order**, and **what each unit covers** so stepped and auto modes cannot
diverge.

Also summarized in `.claude/agents/coordinador-propuesta.md`.

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

## Step sequence (post-intake)

| `next_step` | Unit | Gate | On PASS → next |
|-------------|------|------|----------------|
| `fase1a` | Early scoping (bibliógrafo MODE=scope, codebase-memory scoping, investigador early) | G1a | `fase1b` |
| `fase1b` | SOTA corpus expansion + WRITE-REFS + vault codebase-memory once | G1b | `fase1` |
| `fase1` | §3 problema + spec del árbol de problemas (`figura.py`) + revisor | G1 | `fase2` |
| `fase2` | §4 SOTA + §5 hipótesis + spec del mapa SOTA (`figura.py`) + revisor | G2 | `fase3` |
| `fase3` | §2 justificación + revisor | G3 | `fase4` |
| `fase4` | §6–§7 objetivos + revisor | G4 | `fase5` |
| `fase5` | §8 marco + §9 equipo + revisor | G5 | `fase5_5` |
| `fase5_5` | §10 metodología + spec del diagrama (`figura.py`) + revisor | G5.5 | `fase6` |
| `fase6` | §11 resultados + §12 ética (no own gate) | — | `fase6_4` |
| `fase6_4` | §13 presupuesto + revisor | G budget | `fase6_45` |
| `fase6_45` | §14 cronograma + §15 productos + §16 bib (no own gate) | — | `fase6_46` |
| `fase6_46` | §17 articulación con comunidades + §18 apropiación social + revisor | G comunidades | `fase6_5` |
| `fase6_5` | Front-matter (Resumen, Resumen ejecutivo, Palabras clave) + revisor | G front | `fase7` |
| `fase7` | Final audit + assemble `main.tex` | G final | `done` |
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
`.claude/commands/propuesta.md` (same content as the historical
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

