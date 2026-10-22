# sgr-figuras-estructura

Objetivo: en el flujo SGR, las figuras (árboles, metodología, cronograma) siguen la guía SGR y salen del panel de árboles, y `main.tex` sigue la estructura que exige el TDR. Rama `feat/sgr-figuras-estructura`; entrega: commits por tarea y merge directo a `main` cuando el usuario lo pida. Runner: `python3 -m unittest`.

## Specs

- **S1.** «arbol de problemas del docuento debe salir del panel arborl de problemas y objetivos». La figura `diag_arbol_problemas.tex` tiene que corresponder a la spec vigente que muestra el panel. `check_run.py` reporta error si la figura se compiló desde una spec distinta de la actual. En SGR reporta advertencia si el árbol no está aprobado en el panel o si la aprobación quedó desactualizada.
- **S2.** «igual que el arbol de objetivos». En SGR, el árbol de objetivos del documento se dibuja desde `artefactos/arboles/arbol_objetivos.json`, el archivo que muestra el panel, sin que un agente redacte otra spec. Se produce `diag_arbol_objetivos.tex` y aplica la misma regla de sincronía de S1.
- **S3.** «asegurate que las secciones del docuemnto latex main.tex, para sgr si sigan las reglas sgr para caundo el proyecto asi lo pide». Cuando el TDR fija capítulos (por ejemplo, los 30 del Anexo 2), `main.tex` se arma en el orden del TDR, sin `\setcounter{section}{1}`, desde un archivo estructurado `artefactos/estructura_tdr.json`. Si el archivo trae títulos, `check_run.py` verifica que cada capítulo abra con su título textual. Sin TDR con capítulos, `main.tex` queda como hoy.
- **S4.** «las figuras de diagrama de problemas, metodolgoia y calendario y demas deben guiarse segun la guia sgr». En SGR, la figura metodológica es una cadena de valor organizada por etapa (preinversión, inversión, operación) y ligada a los objetivos específicos (guía SGR §10). El cronograma agrupa actividades por etapa y marca la ruta crítica (guía SGR §14). `check_run.py` lo advierte cuando falta.
- **S6.** «ajsuta tambien, para que los subproblemas par acuando es regalias, estan alineadas con las reglas del arbol de problemas y las cuasas, explorar como ajustar y resume como podria ser la guia para definir mejor problema, subproblema (causas en lenguaje sgr), segun las reglas planteadas para arbol de problemas». Primero se explora y se presenta un resumen de la guía propuesta; la guía se edita después de que el usuario lo apruebe.
- **S7.** «despues de identificar los 3 subproblemas, debes poner una gate, donde se le sugiere acomodar los 3 subproblemas a las 3 causas plantilla para proyectos sgr en ia aplicada, con levantamiento datos, plataforma y modelos y apropiacion, o en modo exploratorio, en donde el agente debe proponer 3 causas raices segun la idea del rpoyecto y los 3 subproblemas identificados en etado del arte». Unidad solo SGR `fase1a_sgr` con compuerta `GCausas` entre G1a y la Fase 1b; sus causas directas aprobadas alimentan el árbol de problemas.
- **S5.** «no dañes el flujo actual que esta corriendo en regalias_56UNAL». No se escribe nada dentro de `proposals/` de ese proyecto. El flujo base no cambia de salida. Las reglas nuevas que podrían bloquear una compuerta en curso entran como advertencia, salvo la desincronía figura/spec de S1 y S2, que se arregla volviendo a compilar.

## Tasks

| ID | Specs | Ruta | Estado | Evidencia |
|---|---|---|---|---|
| T1 | S1, S2 | inline | hecha | dfc9c68; RED 5F+3E → GREEN 12/12; suites relacionadas 136 OK |
| T2 | S3 | inline | hecha | d8eb8e7; RED 10E → GREEN 11/11; bootstrap sobre copia de la guía viva: 30 capítulos |
| T3 | S4 | inline | hecha | cd1efe9; RED 7F → GREEN 15/15; «dos o más actividades por producto» queda sin verificación mecánica (Gantt de forma libre) |
| T4 | S1-S5 | inline | hecha | 718d144; revisión RDD aprobada; dispatcher, agentes, docs, ports y kit; suite completa 465 OK |
| T5 | S6 | inline | hecha | guía SGR §3, investigador, `sgr-causa-sin-magnitud`/`sgr-efecto-sin-magnitud` (RED → GREEN) |
| T6 | S7 | inline | hecha | unidad `fase1a_sgr` y compuerta `GCausas` (RED 1F+3E → GREEN); continuar, tabla de pasos, tablero |
| T7 | S1-S4 | inline | hecha | 3 defectos de la revisión (RED 2F → GREEN) y test tautológico reemplazado |

Ruta inline en las cuatro: no hay unidades paralelas que justifiquen un escritor delegado. Estimación cercana a 900 líneas; estrategia `exception-ok`, porque el usuario integra con commit, merge y push directo a `main`.

## Log

- **L1 (2026-10-21, usuario):** «ahora, rvisa el flujo para cuando es regalias, las figuras de diagrama de problemas, metodolgoia y calendario y demas deben guiarse segun la guia sgr, para cuando el proyecto es sgr, por ej, arbol de problemas del docuento debe salir del panel arborl de problemas y objetivos, igual que el arbol de objetivos, asegurate que las secciones del docuemnto latex main.tex, para sgr si sigan las reglas sgr para caundo el proyecto asi lo pide. no dañes el flujo actual que esta corriendo en regalias_56UNAL»
- **L2 (mapa):** el panel lee el árbol de problemas desde `redaccion/specs/arbol_problemas.spec.json`, la misma spec que compila `figura.py`, pero nada verifica que la figura corresponda a la spec vigente ni a la aprobada. No existe figura del árbol de objetivos. `render_tikz.py` no distingue flujos. `plantilla/main.tex` fija el orden base, y la guía ajustada de la corrida viva (`guia_ajustada_TDR.md:87`) deja pendiente el reordenamiento del Anexo 2.
- **L3 (decisión):** los scripts nuevos viven en `scripts/` de la raíz y reciben `<RUN_ROOT>`, como `check_run.py`. Así una corrida existente los usa después de `morfeo upgrade` sin recopiar `redaccion/scripts/`. El árbol de objetivos se convierte a una spec `kind: arbol` y se compila con el renderizador existente, que una corrida vieja ya tiene.
- **L4 (2026-10-21, usuario):** «ajsuta tambien, para que los subproblemas par acuando es regalias, estan alineadas con las reglas del arbol de problemas y las cuasas, explorar como ajustar y resume como podria ser la guia para definir mejor problema, subproblema (causas en lenguaje sgr), segun las reglas planteadas para arbol de problemas»
- **L5 (T2):** sobre una copia de `guia_ajustada_TDR.md` de la corrida viva, `--from-guide` leyó los 30 capítulos. Los capítulos 2 y 3 comparten `00_frontmatter` y el 19 menciona `17_articulacion_comunidades` (no se produce). El dispatcher debe dar a cada capítulo numerado su propio archivo; `tdr-capitulo-secciones` lo advierte.
- **L6 (T4):** suite completa 465 tests en verde (14 omitidos por dependencias opcionales). Ports y kit pasan `--check`. Nada se escribió en `proposals/` de regalias-56UNAL; esa corrida recibe estos cambios con `morfeo upgrade`, que no toca `proposals/`.
- **L7 (2026-10-21, usuario):** «despues de identificar los 3 subproblemas, debes poner una gate, donde se le sugiere acomodar los 3 subproblemas a las 3 causas plantilla para proyectos sgr en ia aplicada, con levantamiento datos, plataforma y modelos y apropiacion, o en modo exploratorio, en donde el agente debe proponer 3 causas raices segun la idea del rpoyecto y los 3 subproblemas identificados en etado del arte». Se toma como aprobación de la propuesta de T5. La revisión RDD de T1-T4 quedó aprobada con 9 observaciones no bloqueantes; T7 atiende las 3 que son defectos.
- **L8 (decisión):** `status.py` compara compuertas por subcadena, así que un id como `G1a.5` se marcaría aprobado al aprobar G1a. Se usa `GCausas`, que no contiene ni está contenido en otro id.
- **L9 (T5-T7):** suite completa 476 tests en verde (14 omitidos). La verificación «jerga técnica en causas directas» se descartó: el modo plantilla incluye a propósito la causa C2 «plataforma y modelos».
