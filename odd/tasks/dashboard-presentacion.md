# Presentación desde el visor PDF y plantilla con árbol de objetivos y referencias provisionales

Objetivo: que el PDF de cualquier corrida muestre el árbol de objetivos y resuelva sus citas antes de la Fase 6, y que el visor PDF del tablero genere una presentación con el estilo de LIAUNAL/AgentPt.
Rama: `feat/dashboard-presentacion`. Entrega: un commit por tarea. Pruebas: `PYTHONPATH=src python3 -m unittest`, `npm test` (jsdom).

## Specs

- **S1.** Palabras del usuario: «ajust para que el pdf tenga las escudos mas grandes en la primera pagina, revisa las citas del pdf que no se ven, y incluye el arbol de objetivos».
  - En `plantilla/main.tex`, la figura `diag_arbol_objetivos` se inserta después de §7.
  - Mientras no exista `sections/16_bibliografia.tex`, las citas se resuelven contra `refs.bib` con una lista provisional de «Referencias».
  - Una corrida sin citas sigue compilando.
  - El tamaño de los escudos es un ajuste de la corrida, no de la plantilla.
- **S2.** Palabras del usuario: «agrega un boton en el tablero del previsualizador pdf, que se llame presntacion, y usando el estilo de presentacion https://github.com/LIAUNAL/AgentPt, con la siguiente estructura Slide1: nombre convocatoria, nombre propuesta, linea tematica, slide 2: entidad ejecutura y aliados con escudos, slide 3: arbol de problemas, slide 4: arbol de objetivos, slide 5: metodologia ?».
  - Hay un botón «Presentación» en la barra del visor PDF que abre la presentación.
  - La presentación tiene esas cinco diapositivas y toma sus datos de la corrida activa.
  - Mientras `10_metodologia.tex` no exista, la diapositiva 5 se marca como preliminar y se deriva del árbol de objetivos.
  - La interfaz usa el estilo de AgentPt: tipografías, paleta, riel de módulos, pie con logos y navegación por teclado.

## Tasks

| ID | Specs | Ruta | Estado | Commit |
|---|---|---|---|---|
| T1 | S1 | inline | hecho (RED con la plantilla vieja; GREEN; pdflatex sin citas y con citas: exit 0, 0 citas sin resolver) | ver git log |
| T2 | S2 | inline | hecho (RED: import y botón ausentes; GREEN: 11 Python + 1 JS; suite 587 OK, JS 133/133; revisión visual de las 5 diapositivas con la corrida real) | ver git log |

## Log

- **L1** (2026-10-22): pedido original del usuario, citado en S1 y S2.
- **L2:** en la corrida `2026-10-salud-mental-permanencia` los escudos ya se agrandaron (dos filas de tres, 2,1 cm). Esa corrida también tiene ya la figura de objetivos y la lista provisional, y compila con 0 citas sin resolver.
- **L3:** AgentPt (LIAUNAL) no tiene archivo de licencia. Es un repositorio del laboratorio del usuario, que pidió usar su estilo, así que se reutilizan su CSS y su JS y se cita la fuente en el encabezado de los archivos.
