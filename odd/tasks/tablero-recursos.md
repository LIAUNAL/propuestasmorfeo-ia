# Tablero Morfeo con menos memoria, GPU y CPU

Objetivo: reducir lo que consume el tablero `morfeo ui` (memoria, GPU, procesador) sin alterar demasiado la calidad de las visualizaciones.
Rama: `perf/tablero-recursos` · Entrega: merge local a `main` · Tests: `npm test`, `uv run python -m unittest discover tests -p "test_*.py"` · Medición: `scratchpad/measure.mjs` (Chrome headless por CDP: CPU-s de todos los procesos de Chrome en 10 s de reposo, RSS, animaciones, nodos).

## Specs

- **S1** «optimizar procesos, para consumir menos recursos de memoria, gpu, procesador». Medido en reposo, en la corrida `2026-09-tept-depresion-ia-portable` (con grafos y PDF) en :8095, baja el CPU de Chrome y su memoria frente a la línea base de L2.
- **S2** «sin alterar demasiado la calidad de las visualizaciones». Los grafos, el PDF, el flujo y las animaciones de estado se siguen viendo igual cuando están a la vista; lo que se apaga es lo que no se ve (pestañas ocultas, página en segundo plano) o se reemplaza por un efecto equivalente más barato.

## Tasks

| ID | Specs | Ruta | Estado | Evidencia |
|----|-------|------|--------|-----------|
| T1 | S1, S2 | inline | pendiente | |
| T2 | S1, S2 | inline | pendiente | |
| T3 | S1 | inline | pendiente | |
| T4 | S1 | inline | pendiente | |

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
