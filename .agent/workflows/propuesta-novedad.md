# Workflow: propuesta-novedad

> Novedad e hipótesis de la propuesta activa. El investigador propone los pilares de novedad y las hipótesis, cada una con sus experimentos, acciones, implementaciones, intervenciones o transferencias, ligados a las causas y a los objetivos de los árboles; scripts/novedad.py los valida y los registra para el tablero. Es asesor y no reescribe secciones.


# /propuesta-novedad: pilares de novedad e hipótesis

Propone, para la corrida activa, los **pilares de novedad** y las
**hipótesis** del proyecto, cada hipótesis con los experimentos, acciones,
implementaciones, intervenciones o transferencias que producirían su evidencia,
y los liga a las causas directas del árbol de problemas y a los objetivos
específicos del árbol de objetivos. El resultado queda en
`artefactos/novedad/novedad.json` y lo muestra la pestaña «Novedad e
hipótesis» del tablero, con la matriz del proyecto. Funciona en los dos flujos
(`base` y `sgr`) y se puede correr cuantas veces haga falta: cada corrida
reemplaza el artefacto anterior.

Entrada (indicaciones opcionales del operador, por ejemplo «más énfasis en la
transferencia»):

$ARGUMENTS

## 1. Resolver la corrida

1. Leé `proposals/.current-run`. Si no existe o está vacío, decí que no hay
   corrida activa y sugerí `/propuesta-init <idea>`. Detenete.
2. `RUN_ROOT` es `proposals/<run-id>/`. Leé `<RUN_ROOT>/_run.md` para el
   título.
3. Si no existe `<RUN_ROOT>/redaccion/specs/arbol_problemas.spec.json`,
   informá que el árbol de problemas todavía no existe: el investigador
   propondrá las tres causas directas y los tres objetivos desde la idea y el
   script no podrá contrastarlos con los árboles. No te detenés por eso.

## 2. Proponer

Despachá con `Task` al agente `investigador` con `MODE=novedad`, `RUN_ROOT`
absoluto y las indicaciones de la entrada en el prompt (sección «Modo novedad»
del agente). El agente lee la idea, los insumos, la
guía ajustada al TDR, los dos árboles, los subproblemas y objetivos, el
Proyecto Resumido y el estado del arte; escribe
`artefactos/novedad/novedad_borrador.json` y corre
`python3 scripts/novedad.py registrar <RUN_ROOT>` hasta que sale con 0. Si el
agente devuelve errores del script después de sus reintentos, mostralos tal
cual y detenete.

## 3. Mostrar el resultado

Leé `artefactos/novedad/novedad.json` (no la respuesta del agente) y corré
`python3 scripts/novedad.py matriz <RUN_ROOT>`. Mostrá:

- cada pilar con su resumen y los objetivos que atiende;
- cada hipótesis con su enunciado, sus pilares y sus experimentos o acciones,
  con el tipo de cada uno;
- la matriz en una tabla corta: por objetivo específico, la causa directa, los
  pilares, las hipótesis, los experimentos o acciones y sus productos.

Cerrá con cómo iterar: el tablero (`morfeo ui`) muestra lo mismo en la pestaña
«Novedad e hipótesis», con el botón «Generar / actualizar» para otra ronda y el
pliegue «Juez de avance» para puntuar la propuesta hasta este punto
(`/propuesta-juez-avance novedad`).

## Qué nunca hace este comando

- No reescribe §5, §7 ni §10: el artefacto es asesor y alimenta al juez de
  avance y a la redacción posterior.
- No cambia el VEREDICTO del `revisor`, no aprueba compuertas y no modifica
  `next_step` ni el `## Control de ejecución` de
  `artefactos/estado_propuesta.md`.
- No edita los árboles: si una causa o un objetivo no cuadra, el investigador
  lo dice en su respuesta y el cambio se hace en el panel de árboles.
- El agente nunca escribe `novedad.json` a mano: solo el script lo registra.
