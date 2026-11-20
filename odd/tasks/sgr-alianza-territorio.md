# SGR: alianza y territorio (plan P2)

Objective: give the SGR flow structured data, sections, a pipeline unit and a dashboard tab for the alliance and the territory: Anexo 2 chapters 1 (identificación), 8 and 8.1 (demandas territoriales, configuración regional), 10.1 (matriz de responsabilidades), 27 (idoneidad y trayectoria) and the Anexo 1 governance model, with a live preview of the counted rubric criteria. SGR-only; the base flow does not change.
Branch `feat/sgr-alianza-territorio` (stacked on `feat/sgr-cadena-estilo`), delivery `single-pr`. Tests: `uv run python -m unittest discover tests -p "test_*.py"` and the JS suite (scratch jsdom). Receipt-driven review is off for this clone.

## Specs

S1. Pedido textual (L1): «si, sigue con alianza y territorio», continuing the roadmap L4 of `odd/tasks/sgr-cadena-estilo.md`: «Alianza y territorio (entities, type, role, department, contributions; demand → cause/OE → activity → product matrix; live 2.2/3.2 score)». Standing rule from the previous request (verbatim): «asegurate de que este flujo sea especifico para cuando se activa modo sgr, para proyectos de investigacion generales seguimos con el flujo general». Base runs keep the same units, findings, sections and tabs (pinned by tests).

S2. Standing rule (verbatim): «asegurate de constuir patrones de redaccion en cada seccion que ajustes o agregues». Each new section gets its `### SGR` block with a «Redacción» part and lexicon entries, from `docs/sgr/patrones_redaccion_sgr.md` (chapters 1, 8, 10, 27), third-person project voice.

S3. Data: `artefactos/sgr/alianza.json` and `artefactos/sgr/territorio.json` per Contracts; `scripts/alianza_territorio_sgr.py` (`check`, `render`, `puntaje`, `datos`) validates them, renders the table sections deterministically, previews the counted rubric criteria with `juez_sgr.compute_conteo`, and builds the partial `datos_sgr` the judge starts from.

S4. Sections (new SGR stems, registered wherever SGR sections are listed): `26_identificacion` (Anexo 2 cap. 1, rendered), `27_demandas_territoriales` (caps. 8 and 8.1, rendered table + agent-written `articulacion` text inside the data), `28_matriz_responsabilidades` (cap. 10.1 + governance model, rendered), `29_idoneidad_trayectoria` (cap. 27, written by the redactor from the data). The rubric evidence keys of conv54/conv56 point to them.

S5. Pipeline: SGR-only unit `fase1b_sgr` «Alianza y territorio», gate `GTerritorio`, after the trees (`fase1b`) and before the SOTA corpus (`fase1c`): insumos-observador extracts the demand texts verbatim from the TdR and the alliance facts from the inputs; investigador links each demand to causes/OE (activities and products are linked once the value chain exists, `fase4_sgr`); `check` until clean; revisor; the user approves in the dashboard tab. `29_idoneidad_trayectoria` is written in the SGR annex phase. The juez-sgr agent reads both files (and `datos`) before extracting facts.

S6. Dashboard: SGR-only tab «Alianza y territorio» after «Cadena de valor»: entity cards grouped by type (role, position, department, contributions especie/efectivo, activities, research groups, trajectory count), the demand matrix demanda → causas/OE → actividades → productos, the live rubric preview (alcance regional, composición de la alianza, arraigo, aliado internacional, cofinanciación) with its explanation, findings by severity, approval tied to both files' hash, «Enviar ajuste al agente».

## Contracts

`artefactos/sgr/alianza.json`, schema `morfeo.alianza-sgr/v1`:
```
{schema, monto_sgr_solicitado|null, duracion_meses|null,
 entidades:[{id:"E1", nombre, nit|null,
   tipo:"IES"|"SNCTI"|"entidad_territorial"|"usuario_adoptante"|"sector_productivo"|"internacional"|"otro",
   proponente:bool, departamento|null, rol, posicion:"cooperante"|"beneficiario"|"oponente"|"perjudicado"|null,
   interes|null, responsabilidades:[str], actividades:["1.1.1"], aporte_especie|null, aporte_efectivo|null,
   domicilio_en_region|null, tipo_diverso|null,
   grupos:[{nombre, codigo_gruplac|null, clasificacion|null, lineas:[str]}],
   trayectoria:[{nombre, codigo|null, financiador|null, anio|null, sgr_o_elegible:bool}]}],
 gobernanza:{toma_decisiones, instancias, propiedad_intelectual, seguimiento}|null}
```
`artefactos/sgr/territorio.json`, schema `morfeo.territorio-sgr/v1`:
```
{schema, region_sgr|null, departamentos:[{nombre, municipios:[str]}],
 demandas:[{codigo, texto, departamento, fuente, causas:[tree node ids], objetivos:["OE1"],
            actividades:["1.1.1"], productos:["1.1"], articulacion}],
 configuracion_regional:[{actor, departamento, pertinencia}]}
```
`texto` is the demand copied verbatim from the TdR (whitelisted for verbatim repetition by estilo_sgr). Rules (`check`, findings `{severity, code, message, node}` with codes `alianza-*` / `territorio-*`): exactly one proponent; valid enums; minimum composition (≥1 IES, ≥1 other SNCTI entity, ≥1 entidad_territorial, ≥1 usuario_adoptante) is an error; each execution department has ≥1 entidad_territorial (warning); entity departments are execution departments (warning); every demand has texto, fuente and ≥1 objective (error) and, once `artefactos/sgr/cadena_valor.json` exists, ≥1 activity and ≥1 product whose codes exist there (error for unknown codes, warning for none); objective ids exist in the objective tree; contributions non-negative; activity codes of entities exist in the chain; governance missing is a warning; the same trajectory project listed by two entities counts once.
`puntaje RUN [--json]`: `[{subcriterio, nombre, puntaje, max, incompleto, calculo}]` for the rubric's `conteo` subcriteria, using `artefactos/juez/rubrica.json` when present, else the rubric detected by `juez_sgr` from the TdR, else none (empty list with a note). `datos RUN [--json]`: a partial `morfeo.datos-sgr/v1` object (monto, departamentos, proponente, aliados, trayectoria counts, aliado internacional) with `fuente` pointing to these files.

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S2, S3, S4 | delegated (parallel writer, disjoint surface) | done | ee31b84 (55 tests RED→GREEN; check_run differential on the base run identical) |
| T2 | S1, S5 | delegated (parallel writer, disjoint surface) | done | a4146a6 (102 tests RED→GREEN) |
| T3 | S1, S6 | delegated (parallel writer, disjoint surface) | done | 1c5d434 (18 py + 11 js tests RED→GREEN) |
| T4 | all | inline (parent): ports, kit, seam, full suite, commits | done | ports/kit in a4146a6 and ee31b84 |

Route evidence: three independent units with disjoint edit surfaces, each several files and over 100 changed lines, launched together; the parent context is past the long-session backstop. The parent owns git, ports and the kit manifest.

## Log

L1 (2026-11-19, user, verbatim): «si, sigue con alianza y territorio»

L2 (2026-11-19, evidence): Conv 54 TdR §13.1 fixes chapters 1, 8, 10 (with 10.1) and 27; §16 scores 2.1 demands (7), 2.2 regional scope (6), 3.1 trajectory (6), 3.2 alliance (5), 3.3 roots (3), 3.4 international ally (1), 4.1 governance (5) and 4.3 cofinancing (3). The finished reference project presents chapter 8 as «Demanda Territorial | Descripción | Articulación y contribución del proyecto», 8.1 as actors per department with their pertinence, 10 with «Posición | Interés | Poder/influencia», 10.1 as «Entidad | Tipo de aliado | Posición | Rol | Responsabilidades/Obligaciones | Aportes», responsibilities tied to activity codes, and chapter 27 per entity. The VRI requires an alliance of at least four entities in two or more departments of one SGR region.

L3 (2026-11-19, decision by T1, accepted): the guide blocks are `### SGR A26`…`A29`, because the dashboard's `sgrBlockKey` maps every section numbered 19 or more to `A<n>` and the recipe already uses the A19–A25 convention.

L4 (2026-11-19, close): seam: the `estilo-sgr` skill table now maps chapters 1, 8/8.1, 10.1 and 27 to their files; the value-chain tab-order JS test expects «Alianza y territorio» after «Cadena de valor» in SGR; kit rebuilt; ports regenerated with no drift. Full Python suite: 858 tests, only the 14 base environment failures. JS 172/172 (scratch jsdom). Note: SGR `--final` now requires sections 26–29, so in-flight SGR runs see four more required files at Fase 7. Risk: item 3, as T1 noted (`SGR_SECTIONS`, rubric evidence keys and the lexicon contract changed); base output is pinned by tests and the check_run differential. Next roadmap step: Presupuesto SGR with its Gantt.
