# Tarea: asignar unidad de pipeline a §1, §17 y §18

## Contexto

La corrida `2026-09-tept-depresion-ia-portable` cerró la compuerta G5 y, al
regenerar el grafo del vault, apareció un enlace hacia adelante nuevo:
`[[17_articulacion_comunidades]]`. Ese enlace destapó un hueco del framework, no
de la propuesta.

La guía ajustada al TDR exige **§17 Estrategia de articulación con comunidades y
actores territoriales** y **§18 Estrategia de acceso, mediación, divulgación y
apropiación social del conocimiento**. Son secciones nuevas frente a la guía
base, corresponden a los apartados o) y p) del TDR §8.3, tienen prioridad ALTA
y juntas sirven directamente a los criterios de 20 puntos de *Integración del
equipo de trabajo con comunidades* y 20 puntos de *Enfoque territorial*. Es
decir, **40 puntos del puntaje**.

Sin embargo, `.claude/commands/_propuesta-steps.md` recorre las unidades
`fase1a`…`fase7` sin mencionar §17 ni §18. Ninguna unidad las escribe. El mismo
archivo tampoco contempla el bloque obligatorio de identificación de §1, que el
ajuste del TDR define con cuatro puntos: título de 12 a 15 palabras compilado una
sola vez, línea temática *Salud pública en el marco de desastres naturales* con
justificación explícita —incluida la mención de salud mental—, lugar de ejecución
con justificación territorial, y director del proyecto.

## Decisiones del operador (2026-09-30)

1. **§17 y §18 reciben unidad y compuerta propias**, no se pliegan dentro de
   ninguna otra fase.
2. **§1 amplía el alcance de `fase6_5`**, la unidad del front-matter.

## Restricción que fija la ubicación

§18 debe anclar sus acciones a los **tres productos de tipo C** de §15, con
responsable y momento de entrega en §14. Como §14 y §15 se escriben en
`fase6_45`, la unidad nueva no puede ir antes de ahí. Y como el front-matter
sintetiza el documento completo, tampoco debe ir después. El único punto válido
es **entre `fase6_45` y `fase6_5`**.

## Cambios

### `fase6_46` — unidad nueva

- **Identificador:** `fase6_46` (sigue la convención decimal de `fase6_4`,
  `fase6_45`, `fase6_5`).
- **Alcance:** §17 articulación con comunidades y actores territoriales
  (`17_articulacion_comunidades.tex`) + §18 acceso, mediación, divulgación y
  apropiación social (`18_apropiacion_social.tex`), ambas del `redactor`, con sus
  espejos de vault, más `revisor`.
- **Compuerta:** `G comunidades`, con aprobación explícita del usuario.
- **Sucesora:** `fase6_5`.
- **Reencadenado:** `fase6_45` pasa de apuntar a `fase6_5` a apuntar a
  `fase6_46`.

### `fase6_5` — alcance ampliado

Además del front-matter (Resumen, Resumen ejecutivo, Palabras clave), escribe
**§1 Título e identificación del proyecto** con su bloque obligatorio de cuatro
puntos. La compuerta `G front` pasa a validar cuatro artefactos en lugar de tres.
El título se compila una sola vez, en `\title{}`, conforme a la regla de
unicidad.

## Archivos a tocar

| Archivo | Cambio |
|---|---|
| `.claude/commands/_propuesta-steps.md` | Fila de `fase6_46`; reencadenado de `fase6_45`; alcance de `fase6_5` |
| `.claude/commands/propuesta.md` | Bloque de la Fase 6.46; alcance de la Fase 6.5; nota de `70-fase6.md` |
| `.claude/agents/redactor.md` | Solo si su contrato exige declarar las secciones que redacta |

Los tres ports (`.opencode/`, `.pi/`, `.agent/`) se regeneran con
`gen-opencode.py`, `gen-pi.py` y `gen-antigravity.py`; no se editan a mano.

## Tareas

1. Escribir la fila de `fase6_46` en la tabla de unidades y reencadenar
   `fase6_45`.
2. Ampliar el alcance de `fase6_5` para que incluya §1.
3. Escribir el bloque de la Fase 6.46 en `propuesta.md` con su compuerta.
4. Actualizar el bloque de la Fase 6.5 en `propuesta.md`.
5. Regenerar los tres ports y pasarles `--check`.
6. Correr la suite de tests.
7. Commit en la rama de trabajo.

## Criterios de aceptación

- `_propuesta-steps.md` encadena `fase1a`…`fase7` sin huecos y sin unidades
  huérfanas; `fase6_45 → fase6_46 → fase6_5`.
- La tabla y el cuerpo de `propuesta.md` describen la misma secuencia.
- `gen-opencode.py --check`, `gen-pi.py --check` y `gen-antigravity.py --check`
  pasan limpios.
- La suite de tests sigue verde.
- `grep` no encuentra §17 ni §18 sin unidad asignada.

## Riesgo

Cambio de framework que afecta a todas las corridas, incluidas las que ya están
en curso con un `next_step` escrito en `artefactos/estado_propuesta.md`. La
corrida de salud mental está hoy en `fase5_5`, así que el cambio entra muy antes
de que le toque `fase6_46`. Ninguna corrida archivada se ve afectada.
