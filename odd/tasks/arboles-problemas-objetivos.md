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
| T1 | S2, S4 | inline | pendiente | |
| T2 | S1, S3, S4 | inline | pendiente | |

T1: `core/trees.py` + API (`GET /api/trees`, `POST /api/trees/feedback`, `POST /api/trees/approve`) + pruebas Python.
T2: pestaña, render visual, comentarios, envío al agente, aprobación + pruebas JS.

## Log

- **L1** (2026-10-19) «agrega una pestaña entre pipeline y avance y secciones, que se llame Arbol de problemas y objetivos. explora e implementa una alternativa eficiente y visual, que inicialmente proponga el arbor de problemas y luego el de objetivos segun la evolucion de las fases y el flujo del proyecto, debe ser visual y claro, y permitir iterar y ajustar con el agente de forma interactiva, para ir puliendo hasta aprobar dichos arboles»
- **L2** Exploración: la spec del árbol de problemas (`kind: arbol`) trae `groups[].causes`, `trunk`, `branches`, `crown`. No existe árbol de objetivos en el marco; §6/§7 traen el objetivo general y OE1–OE3 en `enumerate`.
