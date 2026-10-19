# Revisión integral de Morfeo: kit, especificación, tokens y tablero

Rama `feat/revision-integral`. Entrega por unidades de trabajo (un commit por
tarea), estrategia `ask-on-risk`. Pruebas: `uv run python -m unittest discover
tests -p "test_*.py"` y `npm test`; el tablero se verifica además con el arnés
Playwright de T6.

## Specs

S1. Pedido del operador, textual (L1): «realiza una revision completa del
proyecto general de redaccion de propuestas morfeo. desde 0, revsia y optimiza
uso de recursos, consumo de tokens, revisiones de calidad y cumplimiento de
especificaciones en la creacion de proyecots, revisa la funcionalidad del
tablero, usa playwrigth o harneses para revisar calidad de la visualicaion, que
no tenga traslapes de textos, buena distribuciones de los elementos,
funcionamiento de botones, cumplimiento de requisitos y todo lo que consideres.»

S2. Un proyecto portable recién creado con `morfeo init` puede crear una corrida
y compilar sin tocar permisos: los scripts del kit conservan el bit de
ejecución, y existe una forma de comprobar que `src/morfeo/_kit/` está al día
sin reescribirlo.

S3. La plantilla trae un `main.tex` canónico que ya cumple las reglas 4, 5, 6 y
8 (sin §1 en el cuerpo, `\setcounter{section}{1}`, `xltabular`, natbib autor-año
con `\bibsection` vacío, 11pt a4, `sectsty`, logos), y compila con secciones de
relleno.

S4. Logos (L2): «el logo utp va solo en ciertas propuestas, no siempre». UNAL
arriba a la derecha, GCPDS abajo a la izquierda y LabIA abajo a la derecha,
según la guía; UTP solo cuando la propuesta lo trae. La alianza UNAL y UTP de la
regla 5 deja de ser obligatoria para toda propuesta.

S5. Una sola especificación canónica: 18 secciones numeradas (§17 articulación
comunitaria y §18 apropiación social como secciones propias); mínimos de
referencias §2 ≥13, §4 ≥39 y total ≥65, declarados en un solo lugar y con tope
de búsqueda al alcanzarlos. Se corrigen las contradicciones C1 a C7 de la
auditoría.

S6. Un verificador determinista de corridas (`scripts/check_run.py`) revisa lo
que hoy depende solo del `revisor`: rayas y dobles guiones en prosa, `\cite{}`
genérico, tope de 3 claves por cita, mínimos de referencias, TRL fuera de §6 y
§7, ausencia de §1 en el cuerpo, presencia de `\setcounter`, `\bibsection` y de
las 18 secciones, y logos referenciados que existan.

S7. Consumo de tokens: tope de llamadas de búsqueda del bibliógrafo, `AGENTS.md`
reducido a lo que necesitan los agentes, un solo bloque de fase por unidad en
`/propuesta-continuar`, orden auditor y revisor que no invalide un PASS sin
necesidad, y modelo más liviano para los agentes de figuras.

S8. Portabilidad (L2): «asegurate tambien que los cambios y revisiones sean
portables con pi, opencode, y antigravity». Todo cambio en `.claude/` se
regenera con `gen-opencode.py`, `gen-pi.py` y `gen-antigravity.py` y pasa su
`--check`; los scripts nuevos no dependen de un runtime.

S9. Tablero: sin desbordes ni traslapes en móvil (390 px), botón flotante que no
tape contenido, contraste suficiente en modo claro, columna «Figuras» real, zoom
coherente, versión y corrida mostradas completas, y el arnés Playwright queda en
el repositorio para volver a correrlo.

## Tasks

| ID | Specs | Ruta | Estado | Commit |
|----|-------|------|--------|--------|
| T1 | S2 | inline | hecha: RED 5/5 (exit 126 reproducido), GREEN 5/5 | 0b5437e |
| T2 | S3, S4 | inline | hecha: RED 5/6, GREEN 6/6 con compilación real con y sin logo UTP | 4398a86 |
| T3 | S6, S8 | inline | hecha: RED 4/5, GREEN 6/6; en la corrida de referencia reporta las 4 rayas de §10 y el 01_titulo | a949ae6 |
| T4 | S4, S5, S8 | inline | hecha: prueba de consistencia RED sobre la spec vieja, GREEN; puertos regenerados | eb46e04 |
| T5 | S7, S8 | inline | hecha: 5 pruebas de presupuesto, RED 5/5 sin los cambios, GREEN; puertos regenerados | b79969d |
| T6 | S9 | delegada (escritor paralelo, superficie disjunta: tablero) | hecha: RED en Python y JS, GREEN; arnés PASS en 64 combinaciones | 0eaaaac |

Ruta: T6 se delega porque corre en paralelo con T1 a T5 sobre archivos
disjuntos (`src/morfeo/dashboard/`, `src/morfeo/core/status.py`, pruebas del
tablero) y es más pesada que lanzar un subagente.

## Log

L1 (2026-10-19). Pedido original, textual en S1.

L2 (2026-10-19). Respuesta del operador a la propuesta de valores canónicos:
«el logo utp va solo en ciertas propuestas, no siempre. asegurate tambien que
los cambios y revisiones sean portables con pi, opencode, y antigravity». Se
toman como aceptados los demás valores propuestos (18 secciones, mínimos
13/39/65, logos según la guía).

L3 (2026-10-19). Auditoría de partida, con tres revisiones paralelas de solo
lectura:
- Tokens: 55,07 M en la corrida de referencia (runtime Pi). El bibliógrafo se
  lleva el 31,8 %, sin tope de búsquedas.
- Preámbulo fijo por subagente: unos 30 k tokens (`AGENTS.md` más el
  `CLAUDE.md` global del usuario).
- `/propuesta-continuar` relee los 26 k tokens de `propuesta.md` en cada unidad.
- Kit: pierde el bit de ejecución (`shutil.copyfile`), así que `build.sh` e
  `init-run.sh` salen con 126 en un proyecto portable.
- Plantilla: no existe `plantilla/main.tex`, y el logo UTP falta en el kit.
- Especificación: contradicciones de 16 contra 18 secciones, mínimos 10/30/50
  contra 13/39/65, y ubicación de logos.
- No hay verificador determinista: dos rayas en §10 pasaron las compuertas.
- Tablero: en móvil el visor PDF queda en ancho cero y todas las pestañas
  desbordan en horizontal. Además, el botón CLI tapa contenido, el modo claro
  tiene poco contraste, la columna Figuras está siempre vacía y el zoom dice
  120 % con escala 1,25.

L4 (2026-10-19). T1 y T2 cerradas. Los scripts del kit recuperan el bit de
ejecución, y `morfeo upgrade` lo repara en proyectos existentes porque usa la
misma copia. `build-kit.py --check` reemplaza la reconstrucción que hacía la
prueba de publicación.

La plantilla compila desde la primera compuerta. El orden impreso conserva el
de la corrida de referencia: articulación (archivo 17_) y apropiación (18_)
quedan numeradas como §16 y §17, y la bibliografía (16_) cierra el documento
como §18. Los identificadores de la guía (§16 bibliografía, §17, §18) nombran
archivos y responsabilidades, no la numeración impresa. Esto se documenta en
T4.

L5 (2026-10-19). T3, T4 y T5 cerradas.
- `check_run.py` entra antes de cada `revisor` en los tres puertos.
- La especificación queda con un solo valor por regla, y una prueba la ata a
  las constantes del verificador.
- `AGENTS.md` baja de 33,8 k a 21,2 k caracteres: el material del despachador
  pasa a `docs/operacion-pipeline.md`.
- El bibliógrafo tiene un tope de 25 búsquedas por despacho.
- `/propuesta-continuar` lee solo su bloque de fase.
- El auditor corre una vez por unidad.
- `tikz-optimizer` y `revisor-figuras` pasan a haiku; `disenador-tikz` sigue
  en sonnet porque diseña el contenido de la spec.

Quedan fuera de este corte, como seguimiento:
- Acotar las dependencias que lee el `revisor` en cada compuerta (ahorro
  estimado de 30 a 50 % de su costo; riesgo de perder cruces).
- Una lista de verificación compacta para el auditor en vez de leer las dos
  skills completas.
- El `CLAUDE.md` global del usuario, que agrega unos 21 k tokens a cada
  subagente y está fuera del repositorio.

L6 (2026-10-19). T6 cerrada.
- Verificación del padre: diff dentro de la superficie autorizada; suite
  completa con 264 pruebas Python OK y 62 JS OK.
- Dashboards reiniciados; `/api/status` ya trae `package_version` 0.5.5 y
  figuras en §3, §4 (2) y §10.
- Arnés `tests/ui/dashboard_audit.py`: PASS en 4 tamaños, 2 temas y 8
  pestañas.
- Evaluación RDD de la rama: riesgo alto (`high_risk`). Se lanza un
  verificador independiente antes de la revisión.
