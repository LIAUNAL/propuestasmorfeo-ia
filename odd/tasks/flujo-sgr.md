# Flujo SGR en `morfeo init` y árboles según la sgrguia

Rama `feat/flujo-sgr`. Entrega `single-pr`: la rama se mergea entera, como en las
features anteriores. Pruebas: `uv run python -m unittest discover tests -p "test_*.py"`
y `npm test`.

## Specs

S1. Pedido textual (L1): «al dar init, si se pone la bandera sgr, el flujo para
ese proyecto se actualiza segun tu exploracion». «no queremos reemplazar el que
ya esta, ese sigue». Sin la bandera, el flujo base no cambia, salvo lo que fija S2.

S2. Árboles en ambos flujos (L1): «revisa con cuidado las sugerencias para
escribir el arbol de problemas y arbol de objetivos, segun la guia sgrguia, ese
panel si debe ajustarse de base para ambos tipos de flujos, arbol de problemas y
arbol de objetivos deben ajustarse segun la guia sgrguia». Fuente (L2): «usa las
reglas de la sgrguia», no las notas del borrador `guiaProyectosIA_Agente_Regalias.md`.
- Árbol de problemas: el problema central es un estado negativo existente
  (calificativo + variable + población o lugar), nunca «la ausencia de su
  solución» (Instructivo MGA 2023, p. 122). Causas directas = subproblemas;
  causas indirectas debajo de cada una; efectos directos e indirectos cuelgan del
  problema central. La copa es el efecto indirecto, no la solución. Se registra la
  magnitud del problema (indicador, valor, fuente) como línea base.
- Árbol de objetivos, espejo positivo: el problema central da el objetivo general
  (infinitivo + objeto + elementos descriptivos, sin el medio, los fines ni las
  metas); cada causa directa da un objetivo específico; cada causa indirecta, un
  medio (el qué, no el cómo); cada efecto, un fin. La variable se conserva.
- El panel del tablero muestra estos niveles, la magnitud y los hallazgos, y no
  aprueba un árbol con hallazgos de error.

S3. Alcance en el flujo base (L3, decisión «Solo árboles»): §6 y §7 conservan sus
verbos de IA; solo se les exige la misma variable del árbol de objetivos. En el
flujo SGR, §6 y §7 son literalmente los textos del árbol de objetivos.

S4. Bandera: `morfeo init --sgr` guarda `"flujo": "sgr"` en `.morfeo/config.json`
y `.marco/config.json`; sin bandera guarda `"flujo": "base"`. `morfeo upgrade` lo
conserva. La corrida y el tablero muestran el flujo.

S5. Contenido SGR (exploración aceptada): guía complementaria SGR sobre la base,
inyectada por el dispatcher cuando el flujo es `sgr`; anexos MGA 19 a 25
(alineación con planes, participantes, población, alternativas, cadena de valor,
riesgos, marco lógico); §11 con indicador de resultado; §13 con los 11 insumos MGA
y solo gastos de inversión; §14 por etapa. Una unidad nueva del pipeline produce
los anexos y en el flujo base se salta.

S6. Portabilidad (decisión vigente de la feature anterior): los cambios llegan a
OpenCode, Pi y Antigravity por sus generadores, con `--check` limpio, y al kit
empaquetado.

## Tasks

| ID | Specs | Ruta | Estado | Commit |
|---|---|---|---|---|
| T1 | S2, S3 | delegada (paralela, superficie disjunta) | hecha: RED 50 Python + 6 JS, GREEN 69 + 69 | 20b2394 |
| T2 | S4 | delegada (paralela, superficie disjunta) | hecha: RED 11 pruebas, GREEN `test_flujo_sgr_init` + `test_morfeo_cli` | c22cdb0 |
| T3 | S2, S3, S5 | inline: guías, agentes, comandos, plantilla, unidad del pipeline | hecha: RED/GREEN `test_pipeline_units` (units_for_flujo), `test_plantilla_main` (anexos), `test_figure_pipeline` (leyenda MGA) | 0b06ace |
| T4 | S6 | inline: ports, kit, docs, suite completa | hecha: `gen-*.py --check` y `build-kit.py --check` limpios; 330 Python OK, 69 JS OK | 0628696 |
| T5 | S1-S6 | verificador independiente al final | hecha: S1-S6 PASS; un bloqueo corregido | ver L6 |

## Log

L1 (2026-10-20). «realiza una exploracion para incluir un flujo ajustado al dar
init a un proyecto con morfeo. en especial, segn las directrices del sistema
general de regalias, segun lo condensado en el proyecto Documents/sgrguia explora
las reglas o flujos que deberiamos ajustar el flujo principal morfeo. no queremos
reemplazar el que ya esta, ese sigue, solo que al dar init, si se pone la bandera
sgr, el flujo para ese proyecto se actualiza segun tu exploracion, revisa con
cuidado las sugerencias para escribir el arbol de problemas y arbol de objetivos,
segun la guia sgrguia, ese panel si debe ajustarse de base para ambos tipos de
flujos, arbol de problemas y arbol de objetivos deben ajustarse segun la guia
sgrguia»

L2 (2026-10-20). «usa las reglas de la sgrguia»

L3 (2026-10-20). Ante la pregunta de hasta dónde aplicar las reglas en el flujo
base, el operador eligió «Solo árboles (Recomendado)».

L4. Exploración. La sgrguia condensa la metodología MGA/SGR del DNP y no cubre los
TDR de Minciencias (TRL, ética, productos CTeI): esos siguen saliendo del TDR de
cada corrida. Hoy la guía base (§3) recomienda «Falta de…» para los subproblemas y
la copa del árbol es la solución, ambas cosas contrarias a la MGA; el árbol de
objetivos solo existe en el tablero (`src/morfeo/core/trees.py`). Ruta: T1 y T2 se
delegan en paralelo porque tienen superficies disjuntas y cada una pesa más que
lanzar un subagente; T3 queda inline. El borrador `guiaProyectosIA_Agente_Regalias.md`
se reemplaza por la guía complementaria SGR (sus notas quedan en el historial de git).

L5. T3 y T2 cerradas. La leyenda de la figura del árbol decía «SOLUCIÓN (COPA)» y
ahora nombra los niveles MGA («EFECTO FINAL», «EFECTOS DIRECTOS»). El flujo base
no ve la unidad `fase6_47` ni la compuerta G6.47: `units_for_flujo` las omite y
el `next` de `fase6_46` salta a `fase6_5`. La evaluación RDD queda para cuando T1
esté confirmada (había archivos sin rastrear de T1 en curso).

L6. Verificación independiente: S1 a S6 PASS. Un bloqueo: la línea de resumen de
`check_run` ganó el sufijo «(flujo …)» sin que nadie lo pidiera; se quitó (el
flujo sigue en `--json`, el tablero y `_run.md`) y una prueba fija la forma
anterior. Se aceptó el cambio de forma de `--json` (lista → `{flujo, findings}`),
sin consumidores en el repo. Avisos atendidos: «Irregular», «Malestar» y otros
adjetivos en -ar ya no se leen como infinitivos. Avisos abiertos, no bloqueantes:
el flujo SGR pide magnitud también en causas y efectos directos, pero el checker
solo la avisa en el tronco; si `.morfeo/config.json` no trae una clave válida,
`init-run.sh` cae a `.marco/config.json` y `detect_flujo` no (init nunca los deja
distintos). Las citas de p. 23 y p. 122 del Instructivo son pasajes distintos y
ambas son correctas según la exploración.

L7. RDD. La rama completa excedió el presupuesto de contexto del revisor; el
operador eligió «Tramos de código». T2 (c22cdb0) y T1 (20b2394) se revisaron por
separado con las lentes risk y reliability: ambos aprobados y reconocidos
(review-331365fc4472038c y review-f7e8ea0f85878f47, autoridad quemada). La guía y
los prompts (0b06ace) y el kit/ports generados quedaron fuera de la revisión y
cubiertos por el verificador. Hallazgos informativos, trabajo aparte:
- T1: el bloqueo de aprobación falla abierto si no carga `check_run.py`
  (`trees.py:67-112`); una spec mal formada puede tumbar el checker
  (`check_run.py:392-401`); `magnitude.valor` no se exige; falsos positivos
  residuales del infinitivo; cambio de forma de `--json` (aceptado).
- T2: un flujo base oculta una compuerta G6.47 ya registrada (`status.py:279`);
  `init-run.sh` imprime una línea más (`flujo: …`); `--sgr` del CLI heredado
  sin prueba; `status.py` ahora depende de `pipeline_units`.
