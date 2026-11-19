# SGR: presupuesto como datos y cronograma (Gantt) desde la cadena de valor (plan P3)

Objective: in the SGR flow, the budget becomes structured data with the Minciencias rubros and the MGA insumos as two views of the same items, per entity and source (SGR, especie, efectivo), tied to activity codes; the schedule (§14 Gantt) and the annual financial projection are generated from the value chain; the Anexo 2 chapter 29 (resumen de fuentes de financiación) is rendered; and a dashboard tab shows it all with live checks and a counterpart-hours calculator. SGR-only; the base flow does not change.
Branch `feat/sgr-presupuesto-gantt` (stacked on `feat/sgr-alianza-territorio`), delivery `single-pr`. Tests: `uv run python -m unittest discover tests -p "test_*.py"` and the JS suite (scratch jsdom). Receipt-driven review is off for this clone.

## Specs

S1. Pedido textual (L1): «si, sigue con presupuesto sgr y gantt», continuing roadmap L4 of `odd/tasks/sgr-cadena-estilo.md`: «Presupuesto SGR (Minciencias rubros × entity especie/efectivo/SGR, MGA view, live checks: transfer ≥1 %, mobility ≤2 %, cofinancing, Seguimiento, quotes; counterpart-hours calculator) with a Gantt by activity code». Standing rule (verbatim): «asegurate de que este flujo sea especifico para cuando se activa modo sgr, para proyectos de investigacion generales seguimos con el flujo general». Base runs keep the same units, findings, sections, §13/§14 behaviour and tabs (pinned by tests).

S2. Standing rule (verbatim): «asegurate de constuir patrones de redaccion en cada seccion que ajustes o agregues». The `### SGR §13`, `### SGR §14` blocks are updated and a new `### SGR A30` block is added, each with its «Redacción» part and lexicon entries (from `docs/sgr/patrones_redaccion_sgr.md` chapters 22 and 29 and the Anexo 3 practice), third-person project voice.

S3. Presupuesto: `artefactos/sgr/presupuesto.json` per Contracts; `scripts/presupuesto_sgr.py` (`check`, `render`, `sync-cadena`, `resumen`, `datos`) validates it, splits each item's value evenly across its activities (the reference workbook's rule) and writes the resulting `costo` into `artefactos/sgr/cadena_valor.json`, renders `13_presupuesto.tex` (SGR form: rubro × source per entity, MGA insumos view, annual projection) and the new `30_fuentes_financiacion.tex` (cap. 29, the three literal lines in letters and numbers), and gives the judge the money facts.

S4. Cronograma: `scripts/cronograma_sgr.py` (`check`, `render`, `proyeccion`) builds `14_cronograma_actividades.tex` from the value chain (OE → producto → actividad with code, months, stage, critical path) and the optional `artefactos/sgr/hitos.json`; checks months, stages, critical path and milestone spacing; computes the share of each activity's cost per year for the financial projection. The value chain activities gain an optional `etapa` («preinversion» | «inversion» | «operacion», default «inversion»).

S5. Pipeline (no new units): in SGR, Fase 6.4 has the presupuestador write `presupuesto.json` instead of hand-writing §13, then `check`, `sync-cadena`, `render`, and the user approves the budget in the dashboard tab (gate G6.4); Fase 6.45 renders §14 with `cronograma_sgr.py` after the investigador writes `hitos.json`; the annex phase renders `30_fuentes_financiacion`. The judge reads `presupuesto_sgr.py datos`.

S6. Dashboard: SGR-only tab «Presupuesto y cronograma» after «Alianza y territorio»: summary cards (total SGR vs cap, counterpart especie/efectivo, cofinancing %, transfer %, mobility %, Seguimiento present, quotes missing), rubro × source table with per-entity breakdown and an MGA-insumos toggle, items list with activities and quotes, annual projection, a Gantt grid from the value chain (critical path highlighted, milestones), the counterpart-hours calculator (hours/week × hourly rate × months × weeks per month × factor, all editable, client-side), findings by severity, approval tied to the hash of both files, «Enviar ajuste al agente».

## Contracts

Minciencias rubros (TdR Conv 54 §13.2): `talento_humano`, `equipos_software`, `capacitacion_eventos`, `servicios_tecnologicos_pruebas`, `materiales_insumos_documentacion`, `proteccion_conocimiento_divulgacion`, `gastos_viaje`, `infraestructura`, `administrativos`, `seguimiento`, `otros`. MGA insumos (Instructivo MGA 2023, p. 68): `mano_obra_calificada`, `mano_obra_no_calificada`, `materiales`, `servicios_domiciliarios`, `terrenos`, `edificios`, `maquinaria_equipo`, `transporte`, `alojamiento_comidas`, `servicios_empresas`, `servicios_comunitarios`.

`artefactos/sgr/presupuesto.json`, schema `morfeo.presupuesto-sgr/v1`:
```
{schema, duracion_meses|null, tope_sgr|null, semanas_por_mes:4, factor_prestacional|null,
 items:[{id:"P1", rubro, insumo_mga, descripcion, justificacion, entidad:"E1", fuente:"sgr"|"especie"|"efectivo",
         componente:"transferencia"|"asc"|"seguimiento"|null,
         cantidad, valor_unitario,                       # valor = cantidad × valor_unitario
         talento:{perfil, horas_semana, valor_hora, meses}|null,   # when present, valor = horas_semana × valor_hora × meses × semanas_por_mes × (factor_prestacional or 1)
         actividades:["1.1.1"], cotizaciones:int, soporte|null}]}
```
Rules (`check`, findings `{severity, code, message, node}` with codes `presupuesto-*`): valid enums; entity exists in `alianza.json`; every item has ≥1 activity and every code exists in the value chain; total SGR ≤ `tope_sgr` (or the rubric's cap from `artefactos/juez/rubrica.json`) is an error; a `seguimiento` rubro with SGR money is required (error); `equipos_software` and `servicios_tecnologicos_pruebas` items with fewer than 2 quotes (warning); SGR `gastos_viaje` > 2 % of total SGR (warning); `componente: transferencia` total < 1 % of total SGR (warning); per entity, especie/efectivo totals equal the entity's `aporte_especie`/`aporte_efectivo` in `alianza.json` when declared (error on mismatch); after `sync-cadena`, each value-chain activity's `costo` equals the sum of its shares (error on drift); non-negative numbers. `resumen RUN [--json]`: `{total_sgr, total_especie, total_efectivo, total, por_rubro:{rubro:{sgr,especie,efectivo}}, por_insumo:{…}, por_entidad:{id:{sgr,especie,efectivo}}, cofinanciacion_pct, transferencia_pct, movilidad_pct, seguimiento, cotizaciones_faltantes, por_actividad:{codigo:valor}}`. `datos RUN --json`: the money part of `morfeo.datos-sgr/v1` (monto_sgr, entity contributions, transferencia_valor, totales_declarados for «presupuesto»).

`artefactos/sgr/hitos.json`, schema `morfeo.hitos-sgr/v1`: `{schema, hitos:[{codigo:"H1", nombre, mes, actividades:["1.1.1"], verificacion}]}`.
`cronograma_sgr.py`: `findings(run_root)` with codes `cronograma-*` (activity without months, months outside 1..duracion, inicio > fin, a product with no critical activity (warning), more than 3 consecutive months without a milestone after month 3 (warning, rubric pitfall), training activities that start before the equipment/platform activities they depend on cannot be inferred and are left to the judge); `proyeccion(run_root)` → `{anios:[{anio, valor, pct}], por_actividad:{codigo:[valor por año]}}` spreading each activity's `costo` evenly across its months; `render` writes `14_cronograma_actividades.tex` with a «% GENERADO por scripts/cronograma_sgr.py» header, grouped OE → producto, stage and critical-path marks, milestones, in the Gantt convention the base §14 already uses (keep `check_run`'s `sgr-cronograma-*` rules satisfied).

New SGR stem: `30_fuentes_financiacion` (Anexo 2 cap. 29), rendered; registered wherever SGR sections are listed (check_run, status, template, ensamblar_main chapter placement, rubric evidence for cofinancing and budget coherence).

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S2, S3 | delegated (parallel writer, disjoint surface) | done | 33c5552 (47 tests; RED for check_run and placement, not for presupuesto_sgr's own rules, written before its tests) |
| T2 | S1, S4, S5 | delegated (parallel writer, disjoint surface) | done | bc9e2b2 (147 tests RED→GREEN; Gantt checked structurally, pgfgantt not installed here) |
| T3 | S1, S6 | delegated (parallel writer, disjoint surface) | done | 68a11df (20 py + 14 js tests RED→GREEN; smoke against the real scripts) |
| T4 | all | inline (parent): ports, kit, seam, full suite, commits | done | seam in 33c5552 and bc9e2b2 |

Route evidence: three independent units with disjoint edit surfaces, each several files and over 100 changed lines, launched together; the parent context is past the long-session backstop. The parent owns git, ports and the kit manifest.

## Log

L1 (2026-11-19, user, verbatim): «si, sigue con presupuesto sgr y gantt»

L2 (2026-11-19, evidence): Conv 54 TdR §13.2 lists the eleven rubros and requires every rubro to be justified against the objectives and to agree with SIGP, Anexo 1, Anexo 2 and Anexo 3; criterion 1.4 (6 points) scores budget ↔ activities/products/responsibles/territories/schedule, cost reasonableness with quotes, and figure coherence across SIGP and Anexos 1–3. The reference workbook (Anexo 3) has sheets RESUMEN (entity × especie/efectivo + SGR + TOTAL), one sheet per rubro with activity-code flag columns (an item's value is split evenly across the flagged activities), «Cadena de valor» (rubro × activity), «cronograma» (activity, start, end, months, annual %) and «Proyección Financiera». Conv 56 TdR caps mobility at 2 % of the SGR request; the transfer component needs at least 1 %; Seguimiento is a mandatory rubro. The Conv 56 evaluation pattern penalises a quarterly schedule without verifiable milestones. The UNAL counterpart-time sheet computes hours/week × hourly rate × months × 4 × a factor.

L3 (2026-11-19, close): seam: the recipe re-renders A23 after `sync-cadena` (which leaves the annex stale); the `estilo-sgr` skill table maps chapter 29 to `30_fuentes_financiacion`; `estilo_sgr.py` docstring updated; both new scripts in the kit manifest; README asset count corrected (73 → 100, stale since earlier features). Full Python suite: 979 tests, only the 14 base environment failures; JS 186/186 (scratch jsdom). Notes for the user: the Gantt could not be compiled here (pgfgantt is not installed), so it was checked structurally and through the DOCX swap; the transfer percentage is the transfer component across all sources divided by total SGR (literal spec; the TdR could be read as SGR money only); `unit_progress` now expects `hitos.json` for Fase 6.45 in SGR, so in-flight SGR runs past that phase show it as partial; SGR `--final` now also requires section 30. Risk: item 3 (shared SGR sections, rubric evidence order, the pipeline inventory gains `artifacts_flujo`); base output pinned by tests and the check_run differential. Next roadmap step: TRL y componentes transversales.
