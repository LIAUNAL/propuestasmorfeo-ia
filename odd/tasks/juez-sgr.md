# Juez SGR: rúbrica mejorada y agente evaluador para propuestas de regalías

Objective: give Morfeo's SGR flow a judge that estimates the peer-review score with the official call rubric plus a guidance layer, raises inconsistency alerts and routes improvement actions to the other agents so the user can iterate.
Branch `feat/juez-sgr`, delivery `single-pr` (merged whole, like the previous features). Tests: `uv run python -m unittest discover tests -p "test_*.py"` and `npm test`.

## Specs

S1. Pedido textual (L1): «construye rubrica mejorada y agente revisor sgr que permita evaluar la calidad de la propuesta para cuando sea sgr y sea parte del juez final del docuemnto para dar un estimado de puntuacion y pueda iterar con los otros jueces y agentes de morfeo para mejorar la calidad de la propuesta o presentar alertas de inconsistencias o mejroar para que el usuario pueda iterar con morfeo». Fuentes (L1): «con base a lo que tienes e manuales dnp, informacion curso udea, proyectos referencia y esta rubrica».

S2. Rúbricas oficiales como datos, una por convocatoria, con el texto de los niveles **textual** del TdR:
- `scripts/rubricas_sgr/conv54.json`: TdR Conv 54, numeral 16, Tabla 10 (4 criterios, 15 subcriterios, total 100; elegible con ≥75 y ≥24 de los 40 del criterio 1; tope SGR $17.177.626.246).
- `scripts/rubricas_sgr/conv56.json`: formato M801PR02MO8 de la Conv 56 (7 criterios, total 100; elegible con ≥75; justificación 1000–4000 caracteres, criterio 7 150–300; concepto final ≥300 palabras con «Recomienda»; tope SGR $14.000 millones, TdR 11.5).
- Cada subcriterio declara su modo: `niveles` (puntajes cerrados), `acumulable` (componentes con tope) o `conteo` (se calcula con datos del proyecto).
- La rúbrica se elige por convocatoria: bandera explícita, luego la ya copiada en la corrida, luego detección en el TdR de `insumos/`. Si no se detecta, se pide elegir; nunca se adivina.

S3. Rúbrica mejorada (capa guía) `scripts/rubricas_sgr/_guia_comun.json`: por familia de criterio (coherencia, metodología/novedad, TRL, presupuesto, riesgos, demandas territoriales, alcance regional, transferencia, ASC, productos y divulgación, trayectoria, alianza, gobernanza, sostenibilidad, cofinanciación, enfoque diferencial, emergencia, oportunidad), las preguntas que hace un par exigente, las señales de alerta, la evidencia mínima y la fuente (Instructivo MGA 2023, Manual conceptual MGA, módulos del diplomado UdeA, Anexo 2 de las convocatorias, proyectos de referencia). La capa guía orienta; los puntos solo salen de los niveles oficiales.

S4. Agente `juez-sgr` (solo lectura sobre `redaccion/`): emite una evaluación por ronda con puntaje cerrado, justificación con evidencia ubicada, «qué falta para el siguiente nivel», alertas de inconsistencia y acciones de mejora dirigidas a un agente de Morfeo o al usuario. Estima como un par exigente: sin evidencia en el documento, no hay puntos.

S5. Script `scripts/juez_sgr.py` (stdlib, determinista): `preparar` (rúbrica + verificaciones), `calificar` (valida la ronda, calcula los subcriterios de conteo, cruza cifras, suma, decide elegibilidad y escribe el consolidado y el formulario), `estado` (resumen corto). `calificar` sale con código ≠ 0 si la ronda no cumple el esquema o los rangos.

S6. Parte del juez final: comando `/propuesta-juez` que se puede correr en cualquier momento (en flujo SGR despacha `juez-sgr`; en flujo base informa que el juez de investigación llega en una entrega posterior) y paso del juez SGR en la Fase 7 del flujo SGR. Es asesor: no cambia el PASS/FAIL del `revisor`, pero el `revisor` de la auditoría final recibe las alertas de error abiertas.

S7. Iteración: las acciones se envían desde el tablero al agente indicado (terminal del agente), y un botón vuelve a correr el juez. Cada ronda queda en el historial con su total para ver si la propuesta mejora.

S8. Tablero: pestaña «Juez final» con total vs umbral, mínimos por criterio, tarjetas por subcriterio, alertas por severidad, acciones con botón de envío e historial de rondas. En flujo base muestra el aviso de S6.

S9. Confidencialidad: el borrador de evaluación de par que motivó los patrones es confidencial. Al repositorio solo llegan la rúbrica oficial y patrones de error generalizados, sin título, código, proponente, cifras ni lugares de ningún proyecto evaluado.

## Schemas (shared contract for every unit)

Run files live under `<RUN>/artefactos/juez/`.

`rubrica.json` (copy of `scripts/rubricas_sgr/<id>.json`), schema `morfeo.rubrica-sgr/v1`:
```
{schema, id, convocatoria, fuente, deteccion:[regex...], total:100,
 elegibilidad:{umbral_total, minimos:[{criterio, minimo}]},
 justificacion:{min_chars, max_chars, excepciones:{"7":[150,300]}}, concepto:{min_palabras},
 tope_solicitud_sgr, desempate:[ids], tercer_evaluador:{diferencia, promedio_min},
 criterios:[{id, nombre, max, subcriterios:[{
   id, nombre, descripcion, max, modo:"niveles"|"acumulable"|"conteo",
   niveles:[{puntos, descriptor}],            # niveles: allowed values, verbatim
   componentes:[{id, nombre, max, descriptor}],  # acumulable: integer 0..max each, sum capped at max
   regla_conteo:{tipo, ...},                  # conteo: computed by calificar from datos_sgr.json
   notas:[verbatim], familia, evidencia:[section keys], agentes:[agent ids]}]}]}
```
A criterion without subcriteria (Conv 56 «4», «5», «6», «7») is modelled as one subcriterion with the same id.

`datos_sgr.json` (written by the agent, facts with source), schema `morfeo.datos-sgr/v1`:
```
{monto_sgr:{valor, fuente}, duracion_meses, departamentos_ejecucion:[{nombre, fuente}],
 proponente:{nombre, domicilio_en_region, tipo_diverso, fuente},
 aliados:[{nombre, tipo:"IES"|"SNCTI"|"entidad_territorial"|"usuario_adoptante"|"sector_productivo"|"internacional"|"otro",
           departamento, contrapartida_especie, contrapartida_efectivo, fuente}],
 trayectoria:{proyectos_adicionales, proyectos_sgr_o_elegibles, fuente},
 aliado_internacional_con_aporte, transferencia_valor,
 trl:{tipologia, entrada, salida, fuente},
 productos_adicionales:{total, top_o_a, fuente},
 totales_declarados:[{documento, concepto:"sgr"|"contrapartida"|"total", valor}]}
```
Unknown values are `null`; the agent never invents them.

`evaluacion_ronda_<N>.json` (written by the agent), schema `morfeo.evaluacion-sgr/v1`:
```
{ronda, fecha, rubrica,
 criterios:[{id, puntaje|null, componentes:{id:int}|null, nivel_descriptor, justificacion,
             evidencia:[{ubicacion, cita}], para_subir:{puntaje_objetivo, que_falta}|null}],
 alertas:[{id, severidad:"error"|"advertencia"|"info", tipo:"inconsistencia"|"faltante"|"riesgo_puntaje"|"forma",
           mensaje, ubicacion, criterios:[ids]}],
 acciones:[{id, criterios:[ids], agente, secciones:[...], instruccion, impacto_estimado, prioridad:1|2|3}],
 concepto, recomienda}
```
`agente` ∈ {redactor, investigador, presupuestador, disenador-tikz, bibliografo-propuesta, grant-flow-auditor, usuario}. `puntaje` is `null` for `conteo` subcriteria.

`evaluacion.json` (written by `calificar`), schema `morfeo.evaluacion-sgr-consolidada/v1`: the latest round with every `puntaje` resolved, plus
`{subtotales:{criterio:int}, total, elegible, motivos_no_elegible:[...], incompleto:bool, verificaciones:[alerts from the script],
  historial:[{ronda, fecha, total, elegible}], errores_validacion:[]}`.
`evaluacion.md`: the same as a readable form (table criterio | máx | puntaje, then justificaciones, alertas, acciones, concepto).

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S2, S3, S5, S9 | delegated (parallel writer, disjoint surface) | done, uncommitted | 22 tests RED→GREEN; counting rules checked against the TdR by the parent |
| T2 | S4, S6, S9 | delegated (parallel writer, disjoint surface) | done, uncommitted | registration test RED→GREEN; ports regenerated by parent |
| T3 | S7, S8 | delegated (parallel writer, disjoint surface) | done, uncommitted | 11 py + 11 js tests RED→GREEN |
| T4 | all | inline (parent): ports, manifest seam, full suite, docs check | done, uncommitted | build-kit in step; ports no drift; suite = base failures only; JS 150/150 |

Route evidence: T1–T3 are independent units with disjoint edit surfaces, each several files and well over 100 changed lines, launched together; the parent context is also near the long-session backstop. The parent owns git, the generated ports and `kit-manifest.json`.

## Log

L1 (2026-11-19, user, verbatim): «luego de explorar y actulaizar tu idea de mejoras de smith con los proyectos orientarc y rio cauca, revisa en mi drive la carpet aque tenemos de revision de proyectos convocaotria 54 de minciencias de regalias, explora la rubrica que nos dieron, y con base a lo que tienes e manuales dnp, informacion curso udea, proyectos referencia y esta rubrica, construye rubrica mejorada y agente revisor sgr que permita evaluar la calidad de la propuesta para cuando sea sgr y sea parte del juez final del docuemnto para dar un estimado de puntuacion y pueda iterar con los otros jueces y agentes de morfeo para mejorar la calidad de la propuesta o presentar alertas de inconsistencias o mejroar para que el usuario pueda iterar con morfeo»

L2 (2026-11-19, evidence): the Drive folder «revision regalias» holds a Conv 56 peer review (official M801PR02MO8 form in blank, an evaluation draft and its justifications), not Conv 54. The Conv 54 rubric comes from its TdR (numeral 16, Tabla 10), downloaded from the Río Cauca copy folder. Both rubrics are supported. The review route marks the evaluated project as confidential (S9).

L3 (2026-11-19, generalized peer-review patterns for the guidance layer, no project data): points are lost when (a) one rubro concentrates almost all of the SGR money without itemized costs or per-component quotes; (b) quotes come from an ally of the project or from a firm outside the field, or copy the proponent's own figures; (c) the SGR pays licences of software owned by the executor, who keeps the IP, so the territory ends up dependent instead of appropriating the technology; (d) an activity costs different amounts in Anexo 2 and Anexo 3, or the 1 % transfer plan has no budget line; (e) the methods measure a different hazard than the one the problem or emergency names; (f) an AI component lists no variables, training data, thresholds, metrics or validation protocol, or names a technique that does not do the job claimed; (g) impact indicators lack baseline and measurement method, and the population figure is not derived from the area of influence; (h) cited territorial demands are unrelated to the chosen line; (i) the schedule is quarterly without milestones per site, or schedules training before the equipment exists; (j) the TRL claim rests on a delivery certificate without performance records (alerts issued, hit and false-alarm rates, lead time, availability); (k) a territorial link rests on location only; (l) georeferenced coordinates are wrong or duplicated; (m) ASC products have no budget, verification means or delivery month; (n) the alliance leaves out the departmental level the solution depends on.

L4 (2026-11-19, reference-project patterns): ORIENTAR-C and Río Cauca use the Conv 54 Anexo 2 (31 chapters). Trees as five-row tables; one activity key OE.Producto.Actividad shared by methodology, value chain, budget, schedule and responsibility matrix; Anexo 3 RESUMEN with entity × especie/efectivo + SGR; §29 and Anexo 3 money totals must match; the MGA title must be identical everywhere. The submitted reference files fail several of these cross-checks, so the deterministic checks are worth it.

L5 (2026-11-19, verification): end-to-end smoke (preparar → round → calificar → `load_judge` → action prompt) works. `scripts/build-kit.py --check`: kit in step. `gen-*.py --check`: no drift. Full Python suite: 14 failures, the same 14 that fail on a HEAD export (LaTeX `fancyhdr.sty` missing, `pi --list-models`, PTY terminal interrupt). JS suite 150/150 with jsdom installed in scratch (the repo has no `node_modules`). Added `test_only_the_sgr_final_audit_lists_the_sgr_judge` (RED without the `pipeline_units` change, GREEN with it) and a module teardown so the judge tests stop leaving temp runs behind. The parent's work-unit commits were blocked by the auto-mode classifier; nothing is committed and the user decides. Native review waits for a commit candidate (the assessment on the uncommitted tree was `unassessable` because of untracked files). Risk: none by the Task Size list (the new agent, command, routes and model-map keys are additions; the SGR-only fase7 agent was requested and the base flow is pinned unchanged). Pending outside scope: `docs/marco-cli.md` still says «10 agentes» (stale before this feature).
