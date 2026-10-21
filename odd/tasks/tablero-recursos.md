# Tablero Morfeo con menos memoria, GPU y CPU

Objetivo: reducir lo que consume el tablero `morfeo ui` (memoria, GPU, procesador) sin alterar demasiado la calidad de las visualizaciones.
Rama: `perf/tablero-recursos` · Entrega: merge local a `main` · Tests: `npm test`, `uv run python -m unittest discover tests -p "test_*.py"` · Medición: `scratchpad/measure.mjs` (Chrome headless por CDP: CPU-s de todos los procesos de Chrome en 10 s de reposo, RSS, animaciones, nodos).

## Specs

- **S1** «optimizar procesos, para consumir menos recursos de memoria, gpu, procesador». Medido en reposo, en la corrida `2026-09-tept-depresion-ia-portable` (con grafos y PDF) en :8095, baja el CPU de Chrome y su memoria frente a la línea base de L2.
- **S2** «sin alterar demasiado la calidad de las visualizaciones». Los grafos, el PDF, el flujo y las animaciones de estado se siguen viendo igual cuando están a la vista; lo que se apaga es lo que no se ve (pestañas ocultas, página en segundo plano) o se reemplaza por un efecto equivalente más barato.

## Tasks

| ID | Specs | Ruta | Estado | Evidencia |
|----|-------|------|--------|-----------|
| T1 | S1, S2 | inline | hecha | d44fda7; RED 4/4 → GREEN (tests/js/lazy.frames.test.mjs), tests/test_graph_html_idle.py |
| T2 | S1, S2 | inline | hecha | 80d97fc; tests/js/status.poll.test.mjs (CSS y pausa), captura sin cambio visible |
| T3 | S1 | inline | hecha | 80d97fc; RED 7/7 → GREEN, tests/js/status.poll.test.mjs |
| T4 | S1 | inline | hecha | 453e89f; JSON compacto RED → GREEN; recorte del búfer (sin cambio de comportamiento) |

- T1: memoria. Los iframes del grafo y del PDF nativo se cargan al abrir su pestaña, no al abrir la página. El bucle WebGL del grafo (`scripts/graph_html.py`) no dibuja con la página oculta ni con el lienzo en tamaño 0.
- T2: GPU. El brillo neón y el halo animan la opacidad de una capa con la sombra fija, no `box-shadow`. Las animaciones se pausan con la página oculta y respetan `prefers-reduced-motion`. Se agregan los keyframes que faltaban (`spin`).
- T3: CPU del cliente. Un solo sondeo de estado que se reprograma solo (2 s durante una ejecución, 5 s si no), sin pedidos solapados y en pausa con la página oculta. El seguidor se repinta solo si cambió. El sondeo no reajusta la terminal si la conexión está viva.
- T4: CPU del servidor. La caché de estado dura más que el intervalo de sondeo, el JSON va compacto, y el búfer de la sesión se recorta por bloques en lugar de a cada fragmento.

Ruta: inline (no se dispara el Writer trigger).

## Log

- L1 (2026-10-21): «revisa el funcionamiento del tablero ui morfeo, mira donde puedes optimizar procesos, para consumir menos recursos de memoria, gpu,procesador, sin alterar demasiado la calidad de las visualizaicones»
- L2: Línea base, en reposo durante 10 s, con Chrome headless 1440×900, en :8095 (`PropuestaUNALEmergencias`, corrida tept con grafos y PDF):
  - pestaña Fases: 3,88 s de CPU de Chrome, RSS de 2002 MB, 30 animaciones corriendo (14 `neon-pulse`, 14 `halo-pulse`, `pulse` y `fabPulse`);
  - pestaña Grafos: 1,99 s de CPU, RSS de 1917 MB.

  El mapa del explorador muestra lo siguiente:
  - los iframes del grafo (`index.html:2677`) y del PDF nativo (`:2756`) cargan al abrir la página;
  - `animate()` en `graph_html.py:1769` dibuja cada cuadro sin condición;
  - la caché de estado (`status.py:465`, 1,5 s) vence antes de cada sondeo;
  - dos temporizadores de estado se solapan (`index.html:8929`);
  - `renderPhaseRunTracker` y `ensureTerminalConnected` corren en cada sondeo;
  - las animaciones `execute-glow` y `spin` no tienen keyframes.
- L3: Hallazgos de paso:
  - `navigateTab` llegaba a correr dos veces al entrar en Grafos, y la segunda recargaba el grafo antes de que terminara (`?t=`). Ahora el `hashchange` no vuelve a navegar a la pestaña activa, y una carga pedida hace menos de 5 s no se reinicia.
  - La pestaña Flujo es la predeterminada y se carga al arrancar si es la visible.
- L4: La caché de estado no se alargó. Reconstruirlo cuesta 7,6 ms en la corrida grande (menos de 0,4 % de un núcleo con sondeo de 2 a 5 s), y alargarla retrasaría lo que muestra el tablero. Solo se compactó el JSON (41,7 KB → 29,2 KB).
- L5: Medición final, en reposo durante 10 s. Copias de PropuestaUNALEmergencias: antes, `main` 8994d71 en :8097; después, esta rama en :8096 con el bucle de grafo nuevo aplicado a sus HTML.
  - Fases: CPU de Chrome 3,08 → 1,36 s (−56 %), RSS 1984 → 1527 MB (−23 %), nodos 10 455 → 5858.
  - Grafos (grafo a la vista): CPU 2,88 → 2,11 s (−27 %), RSS 1922 → 1563 MB (−19 %).
  - Las capturas de la pestaña Fases antes y después son iguales a la vista.
  - Los grafos ya generados en las corridas conservan el bucle viejo hasta que se regeneren.
- L6: JS 124/124. Python: 376 tests, con 5 fallas que no vienen de este cambio. Las causa la entrada `banco-lia` que otro actor agregó a `.mcp.json` sin commitear, igual que en la feature anterior.
