# constelacion-sota

Objetivo: el grafo de papers SOTA de Morfeo replica la constelación de papersmith-ai (un sistema por paper con planetas tipados, la misma visualización, interacción y paneles, y sus optimizaciones de recursos), con un estudio de constelaciones, en el flujo base y en el SGR. Rama `feat/constelacion-sota`; entrega: commits por tarea y merge directo a `main` cuando el usuario lo pida. Runner: `python3 -m unittest`.

## Specs

- **S1.** «ajusta la presentacino de los grafos de sota papers, del proyecto flujo morfeo, tanto para proyectos generales como para proyectos sgr, para qye incluyan la visualizacion y el estudio de constelaciones, con analisis de topic, problema, resultados, etc, segun se trabaja en https://github.com/LIAUNAL/papersmith-ai». Cada paper del corpus (Fase 1a y Fase 1c) se analiza desde su abstract como un sistema con los planetas de papersmith (sun, branch, topic_app, topic_ai, problem, application, novelty, contribution, family, result, conclusion), cada uno con cita textual y procedencia, en `artefactos/scoping/atlas.json`. Aplica igual en ambos flujos.
- **S2.** «asegurate de revisar tambien que se utilice la misma forma de visualiacion e interaccino con nodos y paneles del grafo sota de smith, para que se replique en morfeo». El grafo de papers se dibuja con el renderizador de papersmith (`render_atlas.py` y su visor 3D, con la vista 2D de respaldo): posiciones deterministas, órbitas por tipo de planeta, colores por tipo y por relación, atenuación al pasar el cursor, ventana con la evidencia al hacer clic, vuelo de cámara con doble clic, chips de familia, leyenda de relaciones y barra de herramientas. El tablero lo sigue mostrando en `grafos/papers-graph.html`.
- **S3.** «estudio de constelaciones, con analisis de topic, problema, resultados, etc». La página y un reporte Markdown citable en las compuertas (`grafos/papers-constellation-report.md`) traen, por familia, los sistemas, problemas, novedades y resultados, más el conteo de relaciones por tipo y la lista de evidencias.
- **S4.** «incluye su optimizacin de recursos y todo lo que se ajusto en ese sentido en Documents/papers_smith». Visor que dibuja solo cuando algo cambia, pausa con `visibilitychange` y con mensajes del tablero (pausa al ocultar la pestaña de grafos, reanuda al mostrarla), respaldo 2D sin WebGL, con WebGL por software, con poca memoria o pocos núcleos, o bajo 20 fps en los primeros 3 s, y relación de píxeles acotada entre 1 y 2. Las mismas pausas y el watchdog se agregan a `scripts/graph_html.py` (grafos de vault y de manuscrito).

## Tasks

| ID | Specs | Ruta | Estado | Evidencia |
|---|---|---|---|---|
| T1 | S1-S3 | delegada (escritor A, paralelo con T2) | pendiente | port de `check_atlas.py`, `render_atlas.py`, bundle, panel de estudio y reporte |
| T2 | S4 | delegada (escritor B, paralelo con T1) | hecha | RED 15F+6E → GREEN 21/21; suites de grafo y tablero 66 OK; falta probar en navegador real |
| T3 | S1 | inline | pendiente | skill `constelacion-sota`, bibliografo, dispatcher Fases 1a y 1c, docs, manifest, ports y kit |

Ruta: T1 y T2 son unidades independientes con superficies disjuntas, cada una más pesada que lanzar un subagente; van en paralelo en el mismo árbol (la rama la maneja el padre). T3 depende del contrato de T1 y la hace el padre.

## Contrato compartido

- Atlas: `artefactos/scoping/atlas.json`, esquema de papersmith sin cambios (`systems[].planets[]` con `id, slot, orbit, label, detail, provenance, evidence{origin, quote, retrieved}`, y `links[]` con `from_system, from, to_system, to, rel`). Id de sistema = `paper-N`; `evidence.origin` = DOI o URL del paper; `quote` = fragmento textual del abstract de `artefactos/scoping/papers/paper-N.md`.
- Scripts en la raíz del marco, como `check_run.py`: `scripts/check_atlas.py <atlas.json> --papers <dir>` y `scripts/render_atlas.py <atlas.json> --out <html> [--report <md>]`.
- Salidas: `grafos/papers-graph.html` (lo que ya sirve `/api/graph/papers`) y `grafos/papers-constellation-report.md`.
- Mensajes del tablero al iframe: `{"type": "atlas-control", "cmd": "pause" | "resume"}`; ambos visores los atienden.

## Log

- **L1 (2026-10-22, usuario):** «ajusta la presentacino de los grafos de sota papers, del proyecto flujo morfeo, tanto para proyectos generales como para proyectos sgr, para qye incluyan la visualizacion y el estudio de constelaciones, con analisis de topic, problema, resultados, etc, segun se trabaja en https://github.com/LIAUNAL/papersmith-ai, asegurate de revisar tambien que se utilice la misma forma de visualiacion e interaccino con nodos y paneles del grafo sota de smith, para que se replique en morfeo, incluye su optimizacin de recursos y todo lo que se ajusto en ese sentido en Documents/papers_smith»
- **L2 (mapa):** en Morfeo, `paper-N.md` solo trae metadatos y abstract; dos productores escriben `grafos/papers-graph.json` (el dispatcher vía codegraph, con cero aristas en la práctica, y `build_manuscript_graph.py:717`, con grupos por turnos); `graph_html.py` es el único renderizador y no tiene pausa por `visibilitychange` ni watchdog de fps. En papersmith, el agente `sota-grapher` escribe `atlas.json` desde los abstracts, `check_atlas.py` lo valida (incluida la fidelidad de las citas) y `render_atlas.py` lo dibuja con posiciones deterministas; licencia Apache 2.0, solo biblioteca estándar.
