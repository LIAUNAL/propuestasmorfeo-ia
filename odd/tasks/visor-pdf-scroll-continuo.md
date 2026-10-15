# Visor PDF de tira continua con controles de selección y marcas

Corrida `2026-09-tept-depresion-ia-portable`. El tablero del Command Center
previsualiza `main.pdf` con un lienzo de una sola página: la rueda del ratón no
hace nada y hay que navegar con los botones o el teclado. El encargo pide que el
scroll recorra las páginas del manuscrito compilado y que la zona interactiva del
visor gane controles para deseleccionar texto y para quitar marcas.

## Specs

S1. Pedido del operador, textual:

> ajusta el flujo del proyecto y las funcionalidades para la previsualizacion
> del pdf, para que el scroll permita avanzar en las paginas del pdf

S2. Aclaración del operador sobre «el flujo del proyecto», textual:

> me refiere a la zona del tablero de la previsualizacion del pdf, para que el
> pdf del manuscrito que se compila pueda avanzar y retroceder entre paginas
> usando el scroll del mouse

Queda fuera de alcance el diagrama Archify y el flujograma de 13 fases.

S3. Decisión del operador sobre el modo de paginación, textual: **«Tira continua
de páginas»**. Todas las páginas apiladas en un contenedor con scroll real, con
render virtualizado por intersección y con la capa de anotaciones recalculada
por página.

S4. Pedido adicional del operador, textual:

> y agrega un boton en la parte interactiva del previsualizador, para poder
> deseleccionar texto, y para quitar tachados, comentarios o zonas de
> humanizacion

S5. Lo que no puede romperse al reescribir el visor: la selección de texto y las
tres marcas editoriales (comentario, tachar y humanizar); el panel lateral de
control de cambios con sus tarjetas, «Vaciar marcas» y «Ejecutar»; los atajos de
teclado; el zoom; el alternado con el visor nativo; y la descarga de `main.pdf`.

S6. La zona interactiva del visor hoy no existe: `pdfSelectionInfoText` y
`selectionActionsQuick` se referencian desde el JavaScript pero no están en el
marcado, así que el aviso de selección y los accesos rápidos nunca se ven. La
barra nueva los materializa.

## Tareas

- [x] T1 Tira continua de páginas con render por intersección (S1, S2, S3)
- [x] T2 Página actual, navegación y zoom sobre la tira (S1, S2, S5)
- [x] T3 Barra interactiva: deseleccionar y quitar marcas por tipo (S4, S6)
- [x] T4 Prueba estructural del contrato del visor (S1 a S6)
- [x] T5 Verificación funcional en navegador sobre la corrida real (S1 a S6)
- [ ] T6 Commit de la unidad de trabajo (S1 a S6)

## Log

L1 (2026-10-15, pedido original): ajusta el flujo del proyecto y las
funcionalidades para la previsualizacion del pdf, para que el scroll permita
avanzar en las paginas del pdf.

L2 (2026-10-15, pedido adicional): y agrega un boton en la parte interactiva del
previsualizador, para poder deseleccionar texto, y para quitar tachados,
comentarios o zonas de humanizacion.

L3 (2026-10-15, decisiones): ante la pregunta de alcance, el operador precisó que
«el flujo del proyecto» es la zona de previsualización del PDF, no los artefactos
de flujo, y eligió la tira continua sobre el avance de una página por gesto.

L4 (2026-10-15, prueba en rojo): se escribió primero
`tests/test_dashboard_viewer.py`, que fija el contrato del visor y las piezas del
visor anterior que no pueden desaparecer. Contra el visor de una sola página dio
8 fallos de 14. Después de la reescritura cerró en 19 pruebas verdes, dentro de
una suite de 138.

L5 (2026-10-15, verificación funcional en navegador): sobre la corrida real, con
Chrome DevTools, la tira construye 59 marcadores y 59 slots; el scroll recorre el
documento de forma monotónica (1 → 8 → 16 → 23 → 30 → 38 → 45 → 53 → 59) y vuelve
al inicio; el render es perezoso (5 páginas pintadas a la vez de 59) y el desalojo
deja la memoria en 6 páginas y 72 MB con `devicePixelRatio` 2. Sin errores de
consola. La barra interactiva responde: seleccionar texto habilita las acciones
rápidas, «Tachar» crea la marca, el contador por tipo sube, «Quitar tachados» la
borra y «Deseleccionar» limpia la selección y la tarjeta lateral.

L6 (2026-10-15, defectos que la verificación destapó y se corrigieron):
1. Faltaba la variable `--scale-factor`, que PDF.js exige igual a `viewport.scale`
   en el contenedor de la capa de texto. Sin ella el texto seleccionable se
desalinea del lienzo al hacer zoom, y con él las coordenadas de las marcas.
2. Dos cambios de zoom solapados dejaban un mismo canvas con dos `render()` en
   vuelo, y PDF.js lo rechaza. La aplicación de escala ahora se serializa y
espera lo que esté en vuelo antes de liberar.
3. Vaciar los conjuntos de seguimiento sin liberar los mapas de bits dejaba
   canvas pintados fuera de todo desalojo, así que la memoria crecía con cada
página visitada. Ahora se liberan uno por uno antes de olvidar el estado.

L7 (2026-10-15, la verificación independiente falsó la garantía C5): el
verificador recorrió el commit y devolvió FAIL con tres contraejemplos. El
primero es alcanzable con uso normal y tiene razón: esperar los render en vuelo
no bastaba, porque un scroll durante la espera arrancaba un render nuevo sobre
el mismo canvas que la aplicación de escala estaba a punto de liberar. El
segundo y el tercero viven en el camino de recargue tras «Ejecutar». Se
introdujeron tres piezas: cancelación del render por página, bloqueo de renders
mientras se aplica la escala y una generación que descarta la tarea que aún no
había pintado.

L8 (2026-10-15, un cuarto defecto, este del propio arreglo): el descarte por
generación se colocó también después de pintar, y una tarea que ya había
redimensionado el canvas se retiraba sin registrarse: quedaba pintado y fuera de
todo desalojo. Lo delataron las medidas, no el razonamiento: 12 canvas pintados
contra 6 rastreados, y las páginas 1 y 2 ancladas al ancho de la escala vieja
mientras el resto ya estaba en la nueva. Ahora toda salida posterior a pintar
libera el canvas, y el `finally` libera también lo cancelado o fallido. Con eso
el descarte seco queda solo antes de pintar.

L9 (2026-10-15, causa de los avisos de `--scale-factor`): quedaba una segunda
fuente de verdad. La variable se fijaba en la tira, pero `zoomPdf` cambia
`pdfScale` de inmediato y su debounce aplica la escala 120 ms después; en esa
ventana, una tarea construía su viewport con la escala nueva mientras la tira
todavía declaraba la vieja, y PDF.js avisaba por la diferencia. Ahora la
variable se fija en la propia capa de texto, con el viewport exacto que se está
pintando.

L10 (2026-10-15, verificación del arreglo, en navegador): ocho ciclos de rueda y
zoom solapados más la travesía completa del manuscrito. **Cero errores de
consola, cero colisiones de canvas, 6 canvas pintados y 6 rastreados, un único
ancho de bitmap, cero tareas en vuelo.** La suite queda en 140 pruebas verdes y
`node --check` acepta el bloque de script en línea.
