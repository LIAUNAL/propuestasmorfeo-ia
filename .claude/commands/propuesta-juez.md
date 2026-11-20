---
description: Juez final de la propuesta activa. En el flujo SGR estima el puntaje con la rúbrica de la convocatoria, lista alertas y acciones de mejora y permite aplicarlas; es asesor y no cambia el veredicto del revisor.
argument-hint: "[--rubrica <id>] | [AC1 AC2 ... para aplicar acciones de la última ronda]"
---

# /propuesta-juez: juez final de la propuesta

Estima el puntaje que la propuesta activa obtendría en la evaluación por pares
y devuelve alertas y acciones de mejora para iterar con los agentes de Morfeo.
Se puede correr en cualquier momento del pipeline, no solo en la Fase 7.

Entrada:

$ARGUMENTS

## 1. Resolver la corrida y el flujo

1. Leé `proposals/.current-run`. Si no existe o está vacío, decí que no hay
   corrida activa y sugerí `/propuesta-init <idea>`. Detenete.
2. `RUN_ROOT` es `proposals/<run-id>/`. Leé `<RUN_ROOT>/_run.md` para el
   título.
3. El flujo es el valor de `"flujo"` en `.morfeo/config.json` (o en
   `.marco/config.json`); sin clave es `base`.

## 2. Flujo `base`

Informá: «El juez final para propuestas de investigación (flujo base) llega en
una entrega posterior. Por ahora el juez existe para el flujo SGR.» Detenete
sin despachar nada.

## 3. Flujo `sgr`: evaluar

Si la entrada no trae identificadores de acción (`AC<n>`), despachá con `Task`
al agente `juez-sgr`, con `RUN_ROOT` absoluto en el prompt y, si la entrada
trae `--rubrica <id>`, esa bandera para `preparar`. El agente corre
`python3 scripts/juez_sgr.py preparar <RUN_ROOT>`, escribe
`artefactos/juez/datos_sgr.json` y `artefactos/juez/evaluacion_ronda_<N>.json`
y corre `python3 scripts/juez_sgr.py calificar <RUN_ROOT>` hasta que sale con
0. Si el agente devuelve que la convocatoria no se detectó, mostrale al
usuario la lista de rúbricas y pedile que elija; con la respuesta, volvé a
correr este comando con `--rubrica <id>`.

Con la ronda consolidada, leé `artefactos/juez/evaluacion.json` (no la
respuesta del agente) y mostrá:

- total frente al umbral y elegibilidad, con los motivos si no es elegible
  (incluido un mínimo por criterio que no se alcanza);
- la tabla `Criterio | Máx | Puntaje`, con los subtotales por criterio;
- las alertas de severidad `error` y el número de advertencias;
- las cinco acciones de mayor prioridad (`id`, agente, instrucción resumida,
  impacto estimado);
- con más de una ronda, el historial (`ronda`, `total`, `elegible`) para ver si
  la propuesta mejora;
- la ruta de `artefactos/juez/evaluacion.md`, el formulario legible completo.

Cerrá con cómo iterar:

- desde el tablero (`morfeo ui`), pestaña «Juez final»: cada acción tiene un
  botón que la envía al terminal de su agente, y otro botón vuelve a correr
  el juez;
- o respondiendo con los identificadores de las acciones que se quieren
  aplicar, por ejemplo `/propuesta-juez AC1 AC3`.

## 4. Flujo `sgr`: aplicar acciones

Si la entrada trae identificadores `AC<n>`, leé esas acciones en
`artefactos/juez/evaluacion.json`. Un identificador que no existe se informa y
se omite. Para cada acción, en orden de prioridad:

1. Si `agente` es `usuario`, no despachás nada: la listás al final como tarea
   del equipo (cartas, cotizaciones, aliados, cifras).
2. Si no, despachá con `Task` al agente indicado, con `RUN_ROOT` absoluto, las
   `secciones` de la acción y la `instruccion` literal bajo el encabezado
   `## ACCIÓN DEL JUEZ SGR (<id>)`, más el fragmento de guía de esas secciones
   como en el pipeline (Directrices Generales, Directrices Generales SGR y el
   bloque `### SGR §N` que corresponda).
3. Si el agente modificó prosa (`investigador`, `redactor`,
   `bibliografo-propuesta`), despachá después `grant-flow-auditor` sobre esas
   mismas secciones.

Al terminar, recordá al usuario que una sección modificada después de un PASS
del `revisor` invalida ese PASS en su compuerta, y sugerí volver a correr
`/propuesta-juez` para una ronda nueva con el documento corregido.

## Qué nunca hace este comando

- No cambia el VEREDICTO PASS/FAIL del `revisor` ni aprueba compuertas.
- No modifica `next_step` ni el `## Control de ejecución` de
  `artefactos/estado_propuesta.md`.
- No edita secciones por su cuenta: toda edición la hace el agente de cada
  acción.
- No borra rondas anteriores: el historial queda en `artefactos/juez/`.
