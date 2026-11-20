# SGR: TRL y componentes transversales (plan P4)

Objective: give the SGR flow structured data, rendered sections, a pipeline unit and a dashboard tab for the TRL route and its verification and for the transversal components the TdR scores: transfer, social appropriation of knowledge (ASC), social and environmental sustainability, post-project use and operation, and differential measures. SGR-only; the base flow does not change.
Branch `feat/sgr-trl-componentes` (stacked on `feat/sgr-presupuesto-gantt`), delivery `single-pr`. Tests: `uv run python -m unittest discover tests -p "test_*.py"` and the JS suite (scratch jsdom). Receipt-driven review is off for this clone.

## Specs

S1. Pedido textual (L1): «si», accepting the proposal (verbatim from the previous reply): «El siguiente paso de la hoja de ruta es «TRL y componentes transversales»: ruta y verificación del TRL, sostenibilidad, uso posterior, transferencia, los 7 elementos de apropiación social y medidas diferenciales. ¿Sigo con eso?». Standing rule (verbatim): «asegurate de que este flujo sea especifico para cuando se activa modo sgr, para proyectos de investigacion generales seguimos con el flujo general». Base runs keep the same units, findings, sections (including the hand-written §18) and tabs (pinned by tests).

S2. Standing rule (verbatim): «asegurate de constuir patrones de redaccion en cada seccion que ajustes o agregues». Each new or changed SGR section gets its `### SGR` block with a «Redacción» part and lexicon entries (from `docs/sgr/patrones_redaccion_sgr.md` chapters 14, 16, 17, 18, 19 and 21), third-person project voice.

S3. Data: `artefactos/sgr/componentes.json` per Contracts; `scripts/componentes_sgr.py` (`check`, `render`, `datos`) validates it against the value chain, the alliance, the budget and the call rubric, and renders the sections deterministically. Each component carries an `introduccion` text (agent-written, third person) rendered before its tables.

S4. Sections (SGR stems, registered wherever SGR sections are listed): `31_trl` (Anexo 2 caps. 14.1–14.2), `32_sostenibilidad` (cap. 16), `33_uso_posterior` (cap. 17.1), `34_transferencia` (cap. 18), `35_medidas_diferenciales` (cap. 21.1), all rendered; in SGR runs `18_apropiacion_social` (cap. 19) is rendered from the ASC block instead of hand-written. Rubric evidence for TRL, transfer, ASC, sustainability/use and differential measures points to them.

S5. Pipeline: SGR-only unit `fase5_5_sgr` «TRL y componentes transversales», gate `GComponentes`, after `fase5_5` (methodology) and before `fase6`; investigador writes `trl`, `transferencia` and `uso_posterior`, redactor writes the `introduccion` texts and the `asc`, `sostenibilidad` and `diferencial` blocks, with `revisor-estilo-sgr` on the prose; `check` until clean; revisor; approval in the dashboard tab. Fase 6.4 tags budget items with `componente` consistently with the component activities; Fase 6.45 milestones include the TRL route milestones; Fase 6.46 in SGR writes only §17 and renders §18. The judge reads `componentes_sgr.py datos`.

S6. Dashboard: SGR-only tab «TRL y componentes» after «Presupuesto y cronograma»: the TRL ladder (entry → exit with the route milestones and the verification plan), transfer (results, users, route, barriers, activities, % against the 1 % line from the budget summary), the ASC route as a checklist of the seven elements with activities and products, sustainability (SDG cards, actors, environmental effects), post-project use (goods, operator, funding, adoption), differential measures, findings by severity, approval tied to the hash, «Enviar ajuste al agente».

## Contracts

`artefactos/sgr/componentes.json`, schema `morfeo.componentes-sgr/v1`:
```
{schema,
 trl:{introduccion, tipologia:"A"|"B"|null, entrada:int|null, salida:int|null, evidencia_entrada:[str],
      ruta:[{hito, mes, trl, actividades:["1.1.1"], evidencia}],
      verificacion:{escenario, responsables:["E1"], criterios_aceptacion:[str], evidencias:[str], actor_usuario:"E3"|null}},
 transferencia:{introduccion, resultados:[{resultado, usuarios:[str], proteccion_pi|null}],
      ruta:[{etapa, mecanismo, barreras, acciones}], actividades:["1.1.1"], continuidad},
 asc:{introduccion, actores:[{grupo, relacion_problematica, saberes, rol_momento, incidencia}],
      ruta:[{elemento:"identificacion_problema"|"vinculacion_actores"|"diseno"|"planeacion"|"ejecucion"|"seguimiento"|"resultados_sostenibilidad",
             meses, que_se_hace, actividades:["1.1.1"]}],
      productos:[{producto, descripcion, medio_verificacion, mes, actividad:"1.1.1"}]},
 sostenibilidad:{introduccion, ods:[{ods, contribucion, productos:[str]}], actores:[{actor, funciones, compromiso}],
      ambiental:[{actividad, medio, efecto, manejo}]},
 uso_posterior:{introduccion, bienes:[{bien, valor_sgr, operador:"E1", financiacion, mantenimiento}],
      adopcion:[{actor:"E3", resultado, condiciones}]},
 diferencial:{introduccion, barreras:[{barrera, poblacion, medida, actividades:["1.1.1"], indicador, meta, evidencia}],
      justificacion_sin_barreras|null}}
```
Rules (`check`, findings `{severity, code, message, node}`, codes `componentes-*`): activity codes exist in `cadena_valor.json`; entity ids exist in `alianza.json`; TRL: tipología, entry and exit present, exit > entry, months inside the duration, route milestones reach the exit level, verification plan complete, tipología B needs `actor_usuario`, and the call's TdR range when the rubric is known (Conv 54: A up to TRL 6 with entry backed by evidence, B entry ≥ 4 and exit 7–9; Conv 56: exit below 7 scores 0, warning); transfer: ≥1 result with users, ≥1 route stage with barriers and actions, ≥1 activity, and when `presupuesto.json` exists the transfer component reaches 1 % of total SGR (warning) and the component activities match the budget items tagged `transferencia` (warning); ASC: the seven elements present (error), each with ≥1 activity, ≥1 product with verification means and month (error, rubric pitfall), a warning when every ASC activity name reads as dissemination only; sustainability: ≥1 SDG with products and ≥1 actor with commitment; post-project use: every good with SGR value has operator and funding (error), ≥1 adoption by a `usuario_adoptante` entity (warning); differential: barriers or a justification (error). `datos RUN --json`: `{trl:{tipologia, entrada, salida, fuente}, transferencia_valor|null, fuente}` for `datos_sgr`.

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S2, S3, S4 | delegated (parallel writer, disjoint surface) | done | efbe586 (54 tests; script written before its tests, RED observed afterwards by removing it) |
| T2 | S1, S5 | delegated (parallel writer, disjoint surface) | done | a3a3324 (123 tests RED→GREEN) |
| T3 | S1, S6 | delegated (parallel writer, disjoint surface) | done | 043e641 (19 py + 15 js; RED for routes and JS, not for the loader) |
| T4 | all | inline (parent): ports, kit, seam, full suite, commits | done | seam in a3a3324 |

Route evidence: three independent units with disjoint edit surfaces, each several files and over 100 changed lines, launched together; the parent context is past the long-session backstop. The parent owns git, ports and the kit manifest.

## Log

L1 (2026-11-19, user, verbatim): «si»

L2 (2026-11-19, evidence): Conv 54 TdR §6.1 sets the three mandatory components (new knowledge; technological development, innovation and transfer with declared TRL in and out; ASC as a transversal line developed from formulation, with a route covering at least problem identification, actor engagement, design, planning, execution, follow-up, results and sustainability, «no se limite a actividades aisladas de divulgación»). §16 scores TRL viability 1.3 (10 points: entry evidence 3, maturation route 4, exit verification plan 3), transfer 2.3 (6), ASC 2.4 (6), sustainability and use 4.2 (5: operator, funding source, adopter commitment) and differential measures 4.4 (2: barriers, measures, activities, indicators, goals, evidence, or a justified absence). Conv 56 3.1 scores exit TRL 7/8/9 as 3/8/13 points. The finished reference project presents the TRL route with milestones and acceptance criteria, a decisions table, sustainability with «ODS | Contribución | Productos que la respaldan» and «Actores | Funciones | Compromiso», post-project use with «Bienes adquiridos con SGR | Valor SGR | Operación y mantenimiento posterior» and «Actor | Resultado que adoptará | Condiciones de adopción», transfer tables 18.2–18.4 from the template, and ASC with «Grupo y actores | Relación con la problemática | Saberes y capacidades | Rol y momento de participación | Incidencia», «Fase | Meses | Qué se hace con los actores | Momento del ciclo | Actividades» and «Producto | Descripción».

L3 (2026-11-19, close): seam: Fase 6.4 SGR re-renders the components after `sync-cadena` (sections 18 and 31–35 depend on the value chain); `componentes_sgr.py` in the kit manifest; README asset count 100 → 101; kit rebuilt; ports regenerated with no drift. Full Python suite: 1080 tests, only the 14 base environment failures; JS 201/201 (scratch jsdom). Choices to tell the user: in table 18.4 «Resultado» shows the activity's objective (the contract has no result-to-activity link) and «Presupuesto» the activity's budget share; Conv 54 TRL range violations are errors, Conv 56 exit below 7 a warning; SGR `--final` now also requires 31–35. Risk: item 3 (SGR sections, rubric evidence, recipe contracts); base output pinned by tests and the check_run differential. Next roadmap step: Productos e indicadores.
