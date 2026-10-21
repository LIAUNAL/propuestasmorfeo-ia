# Sesión del CLI persistente y seguimiento de fases desde cualquier pestaña

Objetivo: llevar a Morfeo la interacción con las fases que se hizo en papersmith: barra de avance, manejo del CLI, indicación del proceso por fases, botones de ejecución y apertura o reutilización de sesiones del CLI.
Rama: `feat/sesion-cli-seguimiento` · Entrega: merge local a `main` · Tests: `npm test`, `uv run python -m unittest discover tests -p "test_*.py"`.

## Specs

- **S1** «incluir barra de avance». Una barra de avance flotante, abajo a la izquierda, se ve en todas las pestañas mientras una fase corre o acaba de terminar. Tiene segmentos: enviada, el agente escribe, en curso, verificación y cumplida. Al pulsarla se abre un panel flotante de seguimiento en la misma pestaña, con los mismos puntos de control e información que el seguidor de la pestaña Fases.
- **S2** «manejo de cli … apertura o no de sesiones de cli». La sesión del agente vive en el servidor con un identificador y conserva su salida reciente.
  - Cambiar de pestaña, cerrar la ventana del CLI o perder la conexión no la terminan.
  - Al recargar, el tablero vuelve a conectarse a la misma sesión y redibuja su salida una sola vez.
  - Cambiar de agente o reiniciar con una sesión viva pide confirmación.
  - Si la sesión de una fase ya no existe, el seguimiento lo dice.
- **S3** «botones de ejecución». El modal de ejecución deja elegir el agente (por defecto, el de la sesión abierta o el último elegido) y dice si la fase sigue en la sesión abierta o abre una nueva; con «Nueva sesión» se pide confirmación antes de cerrar la viva.
  - Antes de escribir el comando, el tablero espera a que la salida se asiente. Si la pantalla muestra una pregunta de arranque del agente (confianza en la carpeta, «Enter to confirm»), no envía nada y lo explica en un recuadro rojo.
  - El seguimiento tiene «Detener proceso»: Esc para claude, opencode y pi; Ctrl-C para shell y herdr. Conserva la sesión y marca la ejecución como detenida. Tiene también «Ver terminal».
- **S4** «indicacion de proceso por fases». El seguimiento usa también la actividad de la terminal.
  - Si el agente deja de escribir durante 20 s mientras la fase no ha cerrado, muestra «esperando en la terminal» y avisa una vez por pausa; el aviso vuelve a salir tras la siguiente pausa.

## Tasks

| ID | Specs | Ruta | Estado | Evidencia |
|----|-------|------|--------|-----------|
| T1 | S2 | inline | pendiente | |
| T2 | S2, S3 | inline | pendiente | |
| T3 | S1, S3, S4 | inline | pendiente | |

- T1: servidor. Registro de sesiones PTY con identificador y búfer. El WebSocket se desacopla al cerrar y se reconecta con `?session=<id>`. Se agregan `GET` y `DELETE /api/terminal/sessions/<id>` y el tope de sesiones.
- T2: CLI del tablero. Recordar la sesión, reconectarse, redibujar una vez, confirmar el cambio de agente, registrar la actividad de salida, detectar preguntas de arranque y enviar la interrupción.
- T3: fases. La barra de avance y el panel flotante, «Detener proceso» y «Ver terminal», el selector de agente con «Nueva sesión» en el modal, el recuadro rojo y el estado de espera.

Ruta: inline. Las tres unidades comparten el contrato de sesión, así que no se dispara el Writer trigger. Riesgo: ítem 4 (procesos y concurrencia de sesiones), que lleva verificación independiente al final.

## Log

- L1 (2026-10-21): «revisa la interaccion con las fases que hcimos esta mañana en Documents/papers_smith, relacionado con incluir barra de avance, manejo de cli, indicacion de proceso por fases, etc, e implementalo de forma similar aca en morfeo. revisa muy bien interaccion con cli, botones de ejecucion, apertura o no de sesiones de cli, etc»
- L2: Mapa. papersmith (`skills/_core/command_center`) guarda las sesiones PTY en un `TerminalManager` con id y búfer. El cliente guarda `{id, agent}` y se reconecta con `GET /api/terminal/sessions/{id}`. Hace `term.reset()` antes de redibujar. El dock está en `phase-run.js`, con interrupción y aviso de inactividad, y el guardia de preguntas de arranque en `cli-console.js:466-531`. En Morfeo, `run_pty_session` (`terminal.py:613-894`) crea un proceso por WebSocket y lo mata al desconectarse: una recarga pierde el agente. El seguidor solo existe en `#pane-pipeline`. En Morfeo no se porta el prefijo `!` de papersmith: todos los comandos de fase son slash commands.
