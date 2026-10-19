# Pestaña «Árbol de problemas y objetivos» del tablero

Rama `feat/arboles-problemas-objetivos`. Entrega: `single-pr`. Pruebas: `python3 -m unittest discover -s tests` y `npm test`.

## Specs

- **S1** Pestaña nueva entre «Pipeline y Avance» y «Secciones»: «agrega una pestaña entre pipeline y avance y secciones, que se llame Arbol de problemas y objetivos».
- **S2** «que inicialmente proponga el arbol de problemas y luego el de objetivos segun la evolucion de las fases y el flujo del proyecto». El árbol de problemas sale de `redaccion/specs/arbol_problemas.spec.json`; el de objetivos se deriva en espejo (causa → medio, subproblema → objetivo específico, problema central → objetivo general, efecto → fin) y toma §6/§7 cuando existen. Supuesto: el de objetivos solo se aprueba con el de problemas ya aprobado.
- **S3** «debe ser visual y claro».
- **S4** «permitir iterar y ajustar con el agente de forma interactiva, para ir puliendo hasta aprobar dichos arboles». Comentarios por nodo → solicitud de ajuste escrita en `artefactos/arboles/` y enviada a la terminal del agente; aprobación atada al hash del contenido (si el árbol cambia, la aprobación caduca).

## Tasks

| ID | Specs | Ruta | Estado | Commit |
|----|-------|------|--------|--------|
| T0 | (previo) botón Ejecutar | inline | hecho | bf13626 |
| T1 | S2, S4 | inline | hecho | b5cde53 |
| T2 | S1, S3, S4 | inline | hecho | 15a462a |

T1: `core/trees.py` + API (`GET /api/trees`, `POST /api/trees/feedback`, `POST /api/trees/approve`) + pruebas Python.
T2: pestaña, render visual, comentarios, envío al agente, aprobación + pruebas JS.

## Log

- **L1** (2026-10-19) «agrega una pestaña entre pipeline y avance y secciones, que se llame Arbol de problemas y objetivos. explora e implementa una alternativa eficiente y visual, que inicialmente proponga el arbor de problemas y luego el de objetivos segun la evolucion de las fases y el flujo del proyecto, debe ser visual y claro, y permitir iterar y ajustar con el agente de forma interactiva, para ir puliendo hasta aprobar dichos arboles»
- **L2** Exploración: la spec del árbol de problemas (`kind: arbol`) trae `groups[].causes`, `trunk`, `branches`, `crown`. No existe árbol de objetivos en el marco; §6/§7 traen el objetivo general y OE1–OE3 en `enumerate`.
- **L3** T1: RED 14/14 → GREEN (`tests/test_trees.py`), contra la corrida real §6/§7 se extraen bien (3 OE, 13 textos pendientes). Commit b5cde53.
- **L4** T2: RED 9/9 → GREEN (`tests/js/trees.tab.test.mjs`); suites completas 221 Python y 48 JS en verde; generadores `--check` sin deriva. Verificado en navegador contra la corrida real (solo lectura). Commit 15a462a.
- **L5** Siguiente paso: probar el ciclo completo con Claude Code en una corrida real (enviar un ajuste, que el agente reescriba la spec, aprobar).
- **L6** (2026-10-19) «dale ciclo completo, luegpo revisa que todo funcione en esa pestaña, comit, mergea, y borra ramas»
- **L7** Ciclo completo en la corrida real, por el camino del tablero (navegador → terminal → Claude Code). Problemas: ajuste de forma de los títulos SP; `disenador-tikz` editó solo saltos de línea de SP2/SP3, `figura.py` pasó la auditoría, §3 intacta; el tablero detectó la versión nueva y se aprobó. Objetivos: `investigador` escribió `arbol_objetivos.json` con 9 medios y 4 fines en espejo, §6/§7 intactas; se aprobó y la etapa quedó en «aprobados». Respaldo previo del árbol en el scratchpad de la sesión.
- **L8** Defectos del ciclo, corregidos con RED/GREEN: la cita de un nodo con saltos de línea rompía la lista de la solicitud; el mensaje de aprobación se borraba al pasar a la vista de objetivos. Suites: 222 Python y 49 JS en verde.
- **L9** (2026-10-19) «arregla 1 y 2, y luego 3 y 4»: hallazgos no bloqueantes de la revisión RDD. (1) entrega a la terminal con resultado y botón de reintento; (2) `revision.json` con candado, escritura atómica y archivo dañado nunca sobrescrito; (3) validación de comentarios con error 400; (4) `/api/trees` lee el puntero de la corrida sin reconstruir el estado. Suites: 226 Python y 52 JS en verde.
