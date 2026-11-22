---
name: propuesta-juez-avance
description: Juez de avance de la propuesta activa. Puntúa de 0 a 100 la propuesta hasta una etapa (arbol, novedad o final, la propuesta completa) y devuelve el resumen de la idea, los puntos fuertes, los puntos débiles y las alertas; es asesor y no cambia el veredicto del revisor.
---

# /propuesta-juez-avance: juez de avance por etapa

Evalúa la propuesta activa **hasta una etapa** del tablero, como la leería un
par exigente antes de tener el documento completo, y deja la ronda en
`artefactos/juez/avance_<etapa>.json`. Funciona en los dos flujos (`base` y
`sgr`) y se puede correr cuantas veces haga falta: cada corrida es una ronda
nueva y las anteriores quedan en el historial. La etapa `final` lee la
propuesta completa y es el juez final del flujo base; en el flujo SGR el juez
final es `/propuesta-juez`, con la rúbrica de la convocatoria.

Entrada:

$ARGUMENTS

## 1. Resolver la corrida y la etapa

1. Leé `proposals/.current-run`. Si no existe o está vacío, decí que no hay
   corrida activa y sugerí `/propuesta-init <idea>`. Detenete.
2. `RUN_ROOT` es `proposals/<run-id>/`. Leé `<RUN_ROOT>/_run.md` para el
   título.
3. La etapa es la primera palabra de la entrada: `arbol`, `novedad` o
   `final`. Sin entrada, la etapa es `arbol` y lo decís. Cualquier otra palabra
   se informa («Etapa desconocida: usa arbol, novedad o final.») y te detenés
   sin despachar nada.
4. Con la etapa `arbol`, si no existe
   `<RUN_ROOT>/redaccion/specs/arbol_problemas.spec.json`, informá que el árbol
   de problemas todavía no existe y que el juez evaluará solo la idea y los
   insumos. Con la etapa `novedad`, si no existe
   `<RUN_ROOT>/artefactos/novedad/novedad.json`, informá que la novedad y las
   hipótesis todavía no se generaron y que el juez lo marcará como alerta. Con
   la etapa `final`, si `<RUN_ROOT>/redaccion/sections/` no tiene archivos
   `.tex`, informá que todavía no hay secciones redactadas y que el juez
   evaluará lo que exista. En ningún caso te detenés por eso.

## 2. Evaluar

Despachá con `Task` al agente `juez-avance`, con `RUN_ROOT` absoluto y la etapa
en el prompt. El agente lee los archivos de la etapa, escribe
`artefactos/juez/avance_<etapa>_borrador.json` y corre
`python3 scripts/juez_avance.py registrar <RUN_ROOT> --etapa <etapa>` hasta que
sale con 0. Si el agente devuelve errores del script después de sus
reintentos, mostralos tal cual y detenete.

## 3. Mostrar la ronda

Leé `artefactos/juez/avance_<etapa>.json` (no la respuesta del agente) y
mostrá:

- el puntaje sobre 100 y el veredicto, con la ronda y la fecha;
- el resumen de la idea;
- los puntos fuertes, cada uno con su evidencia;
- los puntos débiles, cada uno con su acción sugerida;
- las alertas agrupadas por nivel (`alta`, `media`, `baja`);
- con más de una ronda, el historial (`ronda`, `fecha`, `puntaje`) para ver si
  la propuesta mejora.

Cerrá con cómo iterar: el tablero (`morfeo ui`) muestra la misma ronda en el
pliegue «Juez de avance» del panel «Árbol de problemas y objetivos» (etapa
`arbol`) o del panel «Novedad e hipótesis» (etapa `novedad`), con el botón
«Evaluar hasta aquí» para una ronda nueva. La etapa `final` aparece en el
pliegue «Juez final» de «Previsualización PDF» cuando el flujo es `base`, con
el botón «Evaluar la propuesta». Las debilidades se corrigen en el panel de
árboles, en la previsualización PDF o con `/propuesta-continuar` y una
indicación.

## Qué nunca hace este comando

- No cambia el VEREDICTO PASS/FAIL del `revisor` ni aprueba compuertas.
- No modifica `next_step` ni el `## Control de ejecución` de
  `artefactos/estado_propuesta.md`.
- No edita árboles, secciones ni artefactos: solo el juez escribe su borrador y
  el script registra la ronda.
- No borra rondas anteriores: quedan en el `historial` del mismo archivo.
