---
description: Fase 0 de intake (clasificación, checklist, TDR/draft, G0.5 opcional). Escribe estado y se detiene antes del scoping; imprime el siguiente comando.
argument-hint: "[idea de investigación] [run-id=... opcional]"
---

# /propuesta-analizar — Intake only (preflight)

Ejecutá **solo** la preparación de corrida: run-id, guardia de colisión,
`insumos-observador`, INTAKE CHECKLIST, ramas TDR/draft, y **G0.5** si hay
TDR. **NO** inicies Fase 1a (scoping / literatura).

Fuente de detalle de cada sub-paso: los bloques **Fase 0** y **Fase 0.5** de
`.claude/commands/propuesta.md` (misma lógica que el pipeline completo).
Tabla de unidades y control de ejecución:
`.claude/commands/_propuesta-steps.md`.

Entrada:

$ARGUMENTS

## Qué hacés vos (asistente primario)

### 1. Run-id y guardia de colisión (fase-aware e idempotente)

Seguí **exactamente** "RESOLUCIÓN DE RUN-ID", "GUARDIA DE COLISIÓN" y
"ARCHIVADO-Y-REINICIO" de `propuesta.md` Fase 0:

- **Post-intake, pre-redacción (`last_completed` es `fase0`, `g0.5` o `g0.5-omitida`)**:
  Si `artefactos/estado_propuesta.md` ya existe con `intake_complete: true` y aún
  no se han redactado secciones (`fase1a` no iniciada), **no** muestres advertencia
  de colisión ni pidas archivar. Ejecutá un **refresco idempotente** de intake
  (re-evaluá `insumos/`, actualizá `insumos.md` y `estado_propuesta.md`) y
  continuá normalmente indicando que el intake está al día.
- **Redacción activa (`last_completed` es `fase1a` o posterior)**:
  **Nunca** ofrezcas ejecutar `fase1a` ni reanudar redacción desde dentro de
  `/propuesta-analizar` (este comando tiene estrictamente prohibido redactar
  secciones). Informá que la redacción está en curso y dirigí al usuario a
  `/propuesta-continuar` (para continuar) o `/propuesta-limpiar` (para archivar
  y reiniciar).
- Escribí la identidad de corrida en `artefactos/estado_propuesta.md` y la fila
  en `proposals/registry.md`.

### 2. Fingerprint de guía + insumos-observador

Calculá `guide_fingerprint` como en `propuesta.md`. Despachá `Task` →
`insumos-observador` sobre `insumos/` (**recursivo**, drop zones
`tdr|draft|background|doc-secciones|ideas` — ver agente). Inyectá
`guide_fingerprint` en el prompt.

### 3. Resolución de idea de investigación (antes / junto al checklist)

Orden **fijo** (también en INTAKE de `propuesta.md`):

1. **`$ARGUMENTS`** con idea usable (tras quitar `run-id=` / `--run-id`) →
   gana. `idea_source: arguments`. Los archivos `ideas/` siguen como
   contexto idea-seed suplementario en el digest.
2. Si no hay idea en args → leé `artefactos/insumos.md` sección **Idea del
   operador** / archivos `idea-seed`. Preferí `ideas/idea.md` si
   **Usable as run idea: sí**. Si solo hay template vacío o placeholders →
   tratá como ausente.
3. Si sigue sin idea usable → **preguntá** al usuario.
4. Persistí en `artefactos/estado_propuesta.md` (bloque identidad o control):
   - `idea: <texto resuelto>`
   - `idea_source: arguments | ideas/idea.md | ideas/* | user`

**Adaptar al grant:** si hay TDR confirmado, la idea es semilla
científica/de producto a **alinear** con secciones, criterios, topes y
duración del TDR — no licencia para ignorar la convocatoria. `draft/` sigue
siendo propuesta previa completa; `ideas/` no la reemplaza.

### 4. INTAKE CHECKLIST + ambigüedad + ramas TDR/draft

Aplicá la **INTAKE CHECKLIST (Fase 0)** de `propuesta.md`: solo ítems no
resueltos (la idea ya puede estar satisfecha por args o `ideas/`). Confirmá
AMBIGUA con el usuario. Completá RAMA TDR, RAMA DRAFT, corroboración de
secciones, y escribí "Clasificación y ruta (Fase 0)" en
`estado_propuesta.md`.

### 5. Fase 0.5 (G0.5) si hay TDR

Si hay TDR confirmado, ejecutá el bloque Fase 0.5 de `propuesta.md`
(bloqueo por secciones, opt-in, generación de `guia_ajustada_TDR.md`, gate de
aprobación de la tabla). Si no hay TDR, omití G0.5.

### 6. Control de ejecución (obligatorio al terminar intake)

Escribí o actualizá en `artefactos/estado_propuesta.md`:

```markdown
## Control de ejecución
- mode: stepped
- next_step: fase1a
- next_command: /propuesta-continuar
- last_completed: g0.5   # o fase0 si G0.5 omitida
- intake_complete: true
- idea: <texto resuelto>
- idea_source: arguments | ideas/idea.md | ideas/* | user
```

Si G0.5 quedó `OMITIDA-POR-USUARIO` o no aplica TDR, `last_completed: fase0`
(o `g0.5-omitida`). Si G0.5 = APROBADA, `last_completed: g0.5`.

### 7. DETENTE — no Fase 1a

**No** despaches bibliógrafo MODE=scope ni codebase-memory de scoping. **No**
redactes secciones.

### 8. Tarjeta de operador (imprimir siempre)

```text
## Intake listo
- run-id: <run_id>
- idea_source: <arguments|ideas/idea.md|ideas/*|user>
- modo dual: scratch | improve-from-draft | both
- TDR: <archivo o (ninguno)>
- draft-base: <archivo o (ninguno)>
- G0.5: APROBADA | OMITIDA-POR-USUARIO | N/A
- next_step: fase1a

### Siguiente (stepped — un paso por comando)
/propuesta-continuar

### Alternativa (pipeline completo en esta sesión)
Solo si aún no avanzaste unidades post-intake:
/propuesta
(o /propuesta)

### Compilar al final (cuando next_step sea done)
cd proposal && ./build.sh

## 🎯 NEXT STEPS
- **Fase Completada**: /propuesta-analizar (Fase 0 Intake & Clasificación)
- **Archivos Actualizados**: `artefactos/insumos.md`, `artefactos/estado_propuesta.md`
- **Acción requerida**: Revisar clasificación e insumos
- **Próximo comando**: `/propuesta-continuar`
```

## Qué nunca hace este comando

- No ofrece ni ejecuta unidades `fase1a`…`fase7` (tampoco como opción de fallback o reanudación en guardias de colisión).
- No auto-resuelve AMBIGUA.
- No inventa identidades de equipo (§9).
- No es un CLI headless ni un run sin gates posteriores (los gates viven en
  `/propuesta-continuar` o `/propuesta`).
