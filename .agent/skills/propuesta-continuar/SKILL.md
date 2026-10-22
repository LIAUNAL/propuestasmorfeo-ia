---
name: propuesta-continuar
description: Avanza exactamente una unidad del pipeline según next_step en estado_propuesta.md; actualiza control e imprime el siguiente comando.
---

# /propuesta-continuar — Una unidad del pipeline

Ejecutá **exactamente una** fila de la tabla de unidades en
`.agent/workflows/_propuesta-steps.md`, según `next_step` en
`artefactos/estado_propuesta.md`. Tras el gate (o fin de unidad sin gate),
actualizá el control de ejecución e imprimí la tarjeta del siguiente comando.

Recetas completas de cada fase: bloques **Fase …** en
`.agent/workflows/propuesta.md` (misma autoridad que el modo auto).

**Leé solo lo que la unidad usa, no el archivo entero** (son unos 26 k
tokens y cada unidad necesita una fracción). Ubicá los límites corriendo
`grep -n '^Fase \|^## '` sobre `.agent/workflows/propuesta.md` y leé por
rangos de líneas:
- el bloque de la unidad, desde la línea que empieza con `Fase <n>` hasta la
  siguiente que empieza con `Fase ` (o con `## `);
- siempre, las secciones `## Raíz de corrida`, `## Reglas de gate` y
  `## Telemetría de uso por fase`;
- `## Bucle de figuras (canónico)` solo si la unidad dibuja un diagrama
  (Fases 1b, 2 y 5.5), y `## Cómo usar codebase-memory` solo si la unidad
  indexa o consulta un grafo.
Si el bloque remite a otra sección por su nombre, leé esa sección y nada más.

Entrada:

$ARGUMENTS

Si la entrada trae texto, son **indicaciones del operador** para esta unidad
(el tablero las envía desde el recuadro «Ejecutar» de la fase). Inyectalas
inline, bajo el encabezado `## INDICACIONES DEL OPERADOR`, en el prompt de cada
Task de la unidad que redacta o diseña contenido, después del fragmento de
guía. Son preferencias de contenido: no cambian `next_step`, no saltan
compuertas ni anulan las reglas de la guía ni las de los árboles MGA; si
alguna choca con una regla, la regla gana y lo decís en el reporte de la
unidad. Registralas en el evento `artefactos/pipeline/NN-<unidad>.md`.

## 1. Precondiciones (si fallan, DETENTE)

Leé `artefactos/estado_propuesta.md`.

| Condición | Acción |
|-----------|--------|
| No existe estado, o no hay `## Control de ejecución` | Decí: corré `/propuesta-analizar` o `/propuesta` primero. No inventes `next_step`. |
| `intake_complete` no es `true` | Igual: completar intake con `/propuesta-analizar`. |
| `next_step` es `done` | Informá que el pipeline ya terminó; sugerí `cd proposal && ./build.sh` y opcional `/propuesta-limpiar`. |
| `next_step` vacío o id desconocido | Error claro; listá ids válidos de `_propuesta-steps.md`. |

## 2. Ejecutar solo la unidad `next_step`

Mapeo id → bloque en `propuesta.md`:

| `next_step` | Ejecutar en `propuesta.md` |
|-------------|-------------------------------|
| `fase1a` | Fase 1a [G1a] |
| `fase1a_sgr` | Fase 1a SGR [GCausas] (solo flujo SGR) |
| `fase1b` | Fase 1b [G1b] |
| `fase1c` | Fase 1c [G1c] |
| `fase1` | Fase 1 |
| `fase2` | Fase 2 |
| `fase3` | Fase 3 |
| `fase4` | Fase 4 |
| `fase5` | Fase 5 |
| `fase5_5` | Fase 5.5 |
| `fase6` | Fase 6 |
| `fase6_4` | Fase 6.4 |
| `fase6_45` | Fase 6.45 |
| `fase6_46` | Fase 6.46 |
| `fase6_47` | Fase 6.47 (solo flujo SGR) |
| `fase6_5` | Fase 6.5 |
| `fase7` | Fase 7 |

**Latido (obligatorio).** Al abrir la unidad escribí
`artefactos/pipeline/_en_curso.json` (`fase`, `agentes`, `skill`,
`artefacto_esperado`, `inicio` en ISO-8601), reescribilo antes de cada `Task`
con el despacho que arranca y su `nota`, y borralo al cerrar la unidad, haya
PASS o FAIL, antes de escribir `artefactos/pipeline/NN-<unidad>.md`. Formato en
`_propuesta-steps.md`, «Latido de la unidad en curso». El tablero lo usa para
mostrar la ejecución en vivo.

Usá `Task` a los mismos subagentes, mismas reglas de codebase-memory/Skill, mismos
gates de aprobación de usuario. **No** encadenes la siguiente unidad en esta
invocación (aunque no haya gate formal: en stepped, `fase6` y `fase6_45`
también paran al terminar).

## 3. Tras la unidad

### Gate FAIL o usuario pide cambios sin aprobar

- Dejá `next_step` **igual**.
- `next_command: /propuesta-continuar`
- Imprimí: reintentar `/propuesta-continuar` tras las correcciones.

### Gate PASS o unidad sin gate completada

Actualizá control según la tabla de `_propuesta-steps.md` (columna "On PASS →
next"). Tras `fase1a` y tras `fase6_46`, el siguiente depende del flujo del
proyecto (`"flujo"` en `.morfeo/config.json`, o `.marco/config.json`; sin clave
es `base`): tras `fase1a`, `fase1a_sgr` con `sgr` y `fase1b` con `base`; tras
`fase6_46`, `fase6_47` con `sgr` y `fase6_5` con `base`.

```markdown
## Control de ejecución
- mode: stepped
- next_step: <siguiente id o done>
- next_command: /propuesta-continuar   # o (none) si done
- last_completed: <id de la unidad que acabás de cerrar>
- intake_complete: true
```

### Si `next_step` pasa a `done`

```text
## Pipeline completo
- run-id: <run_id>
- Compilar: cd proposal && ./build.sh
- DOCX opcional: ./build.sh --docx
- Nueva corrida: /propuesta-limpiar  (luego init/analizar o auto)
```

## 4. Tarjeta de operador (siempre al final de una unidad exitosa con más pasos)

```text
## Unidad completada: <id>
- last_completed: <id>
- next_step: <siguiente>

### Siguiente comando
/propuesta-continuar

## 🎯 NEXT STEPS
- **Fase Completada**: <id>
- **Archivos Actualizados**: `redaccion/sections/...`, `artefactos/vault/secciones/...`
- **Acción requerida**: Revisar contenido generado o gate de aprobación
- **Próximo comando**: `/propuesta-continuar` (o `cd proposal && ./build.sh` si next_step es done)
```

## Qué nunca hace este comando

- No salta unidades ni reordena el grafo de dependencias.
- No re-ejecuta intake (Fase 0) salvo que el usuario invoque analizar de nuevo.
- No aprueba gates por el usuario.
- No es lo mismo que `/opsx-continue` (OpenSpec en otro repo/workflow).
