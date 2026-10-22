# sgr-secciones-reglas

Objetivo: en un proyecto SGR, el panel Secciones y el flujo de redacción siguen las reglas explícitas de la guía SGR, empezando por el planteamiento del problema (§3). Rama `feat/sgr-secciones-reglas`; entrega: commits por tarea y merge directo a `main` cuando el usuario lo pida. Runner: `python3 -m unittest` y `node --test tests/js/*.test.mjs`.

## Specs

- **S1.** «para las secciones del proecto, del panel secciones y sus reglas, ajuste para que cuando sea proyecto de sgr, se siguan las reglas explicitas del sgr». Con `flujo: sgr`, el modal de estructura de cada sección del panel muestra, además de sus reglas base, el bloque `### SGR §N` de `guiaProyectosIA_Agente_Regalias.md` que le corresponde (los anexos A19 a A25 incluidos), leído de la guía del proyecto para que el panel y el dispatcher digan lo mismo. En el flujo base, el modal queda igual.
- **S2.** «revisa las reglas que definimos para el planteamiento del problema que incluyen problema central, contexto general de la problematica, etc, ajusta las reglas del planteamiento de problema para sgr». La guía SGR fija la estructura de §3 en el flujo SGR, la misma de `artefactos/mga_resumido.md`: Problema central (el tronco, literal), Descripción de la situación existente (antecedentes, zona, evolución, intervenciones previas; cierra con las tres causas directas), un párrafo por causa directa C1 a C3 (los subproblemas SP1 a SP3), Magnitud del problema con la tabla de indicadores y la línea base, y el cierre con la pregunta de investigación y el árbol de problemas. El panel muestra esa estructura para §3 cuando el proyecto es SGR.
- **S3.** «ajsuta dichas reglas en el flujo y en el panel». El dispatcher inyecta `### SGR §3` en el fragmento de guía de §3; el investigador escribe §3 con esa estructura; `scripts/check_run.py` advierte (`sgr-problema-estructura`) cuando el §3 de una corrida SGR no trae las subsecciones Problema central, Descripción de la situación existente y Magnitud del problema. Kit y puertos regenerados con `--check` en verde.
- **S4.** «y actualiza el proyecto regalias56UNAL en ese sentido». `morfeo upgrade` en `~/Documents/regalias-56UNAL` y reinicio del tablero. No se escribe nada dentro de `proposals/`.

## Tasks

| ID | Specs | Ruta | Estado | Evidencia |
|---|---|---|---|---|
| T1 | S2, S3 | inline | hecha | 06a08fd; RED 3F+2E → GREEN 8/8; suite 596 OK; kit y puertos `--check` en verde |
| T2 | S1, S2 | inline | hecha | RED JS 2F con el index anterior → GREEN 3/3; parser y endpoint 3/3; suite 599 OK, JS 136/136 |
| T3 | S4 | inline | pendiente | |

Ruta inline: una sola línea de trabajo entendida, sin unidades paralelas.

## Log

- **L1 (2026-10-22, usuario):** «para las secciones del proecto, del panel secciones y sus reglas, ajuste para que cuando sea proyecto de sgr, se siguan las reglas explicitas del sgr, por ejemplo, revisa las reglas que definimos para el planteamiento del problema que incluyen problema central, contexto general de la problematica, etc, ajusta las reglas del planteamiento de problema para sgr, ajsuta dichas reglas en el flujo y en el panel, y actualiza el proyecto regalias56UNAL en ese sentido»
- **L2 (mapa):** las reglas del modal salen de `SECTIONS_STRUCTURE_DATA` en `src/morfeo/dashboard/static/index.html`, iguales para todo proyecto; el flujo ya llega al frente en `/api/status` (`flujo`). La estructura Problema central / Situación existente / Magnitud vive solo en la restricción 15 del investigador (`mga_resumido.md`); el bloque `### SGR §3` de la guía no fija párrafos. El fragmento de la Fase 1 para §3 no nombra `### SGR §3`. Ningún check revisa la estructura de §3.
- **L3 (T1):** la guía SGR §3 abre con «Estructura de §3» (tres subsecciones con títulos textuales y el cierre con la pregunta y el árbol); el investigador la aplica al escribir §3 desde `mga_resumido.md`; el fragmento de la Fase 1 suma `### SGR §3`; `check_run.py` emite `sgr-problema-estructura` como advertencia, también con `--final`, para no bloquear una corrida en curso.
- **L4 (T2):** `/api/guide/sgr` sirve los bloques `### SGR §N` y `### SGR A<n>` de la guía del proyecto (con la copia del kit como respaldo), leídos por `core/sgr_rules.py`. Con `flujo: sgr`, el modal de §3 cambia a la estructura MGA y cada sección suma el bloque «Reglas explícitas de la guía SGR»; los anexos 19 a 25 abren con su bloque en lugar de caer en §3. El flujo base no pide la guía SGR.
- **L5 (revisión de commits ajenos):** antes de esta rama, el hook de RDD pidió revisar los tres commits de otra sesión en `main` (3c03270, 77b7fc7, 6647955); la revisión halló la figura del árbol de objetivos incluida dos veces en `plantilla/main.tex` y el rail de la presentación desplazado en uno, corregidos en d58d06e y aprobados.
