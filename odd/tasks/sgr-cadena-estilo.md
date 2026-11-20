# SGR: cadena de valor como datos, patrones de redacción y revisor de estilo DNP

Objective: first increment of the SGR plan (P1) plus the SGR writing layer: a structured value chain with one activity code, SGR writing patterns and lexicon per section, an SGR style/humanization/redundancy reviewer, and the dashboard panels that show them. Everything is gated on `flujo == "sgr"`; the base research flow does not change.
Branch `feat/sgr-cadena-estilo` (stacked on `feat/juez-sgr`), delivery `single-pr`. Tests: `uv run python -m unittest discover tests -p "test_*.py"` and the JS suite. Receipt-driven review is off for this clone (user, 2026-11-19).

## Specs

S1. Pedido textual (L1): «asegurate de que este flujo sea especifico para cuando se activa modo sgr, para proyectos de investigacion generales seguimos con el flujo general». Every new unit, rule, agent dispatch and panel applies only when the run flow is `sgr`; a base run produces the same pipeline units, check_run findings, dispatches and dashboard tabs as before (pinned by tests).

S2. Patrones de redacción por sección (L1): «asegurate de constuir patrones de redaccion en cada seccion que ajustes o agregues». Each `### SGR` block of `guiaProyectosIA_Agente_Regalias.md` gains a «Redacción» part: opening pattern, favored expressions, expressions to avoid with reason, tense, measured length, and table headers where the chapter is a table. Source: `docs/sgr/patrones_redaccion_sgr.md` (the evidence base, committed with the feature, no project-identifying data).

S3. Voz (L1): «trtar de hablar en tercera persona relacionado con la proppuesta, ej, este proyecto busca, la presente propuesta se enmarca». SGR prose speaks of the project in third person («El proyecto…», «Este proyecto busca…», «La presente propuesta se enmarca…», impersonal «se»); no first person (nosotros, nuestro, hemos, proponemos); present for diagnosis, past for antecedentes, future for activities and results.

S4. Léxico por sección (L1): «explora que palabras no se deberian usar en cada seccion, que expresiones se favorecen». `scripts/sgr/lexico_sgr.json` holds global and per-section forbidden/discouraged and favored expressions with reason, source and (when checkable) a regex; `scripts/estilo_sgr.py` reports hits per section file, honouring the exemptions (quoted plan names, catalog product names, the official «Jóvenes Investigadores e Innovadores») and the whitelist of texts that must repeat verbatim (title, central problem/general objective, specific objectives, product and activity names, demand texts). The MGA activity-verb ban (Manual MGA 2015, p. 81) applies to activity names only.

S5. Revisor de estilo SGR (L1): «incluir agente de revisoin de estilo y humanizacion y redundancia, segun los patrones y reglas que tenemos, pero que se ajusten a las directrices de dnp, y a los ejemplo s de proyectos y rubricas». Agent `revisor-estilo-sgr` + skill `estilo-sgr`: applies `estilo-natural-es` and `depuracion-redundancias-es` with the SGR adjustments (the conflicts C1–C18 of the evidence base: keep impersonal/passive «se» and labelled template fields, allow required verbatim repetition, no «6 párrafos de §2», no «we will» voice), plus the SGR lexicon and the redundancy patterns R1–R14. In the SGR flow it runs wherever `grant-flow-auditor` runs today (before each `revisor`); in the base flow `grant-flow-auditor` stays.

S6. Cadena de valor como datos (plan P1): `artefactos/sgr/cadena_valor.json` seeded from the approved objective tree; `scripts/cadena_valor_sgr.py` (`init`, `check`, `render`) validates it and writes `redaccion/sections/23_cadena_valor.tex` deterministically. A new SGR-only unit after the objectives gate (G4) builds products and activities; the SGR budget assigns costs by activity code; A23 is rendered, never hand-written.

S7. Paneles (L1): «explora que paneles debemos agregar al morfeo ui». This increment adds the SGR-only tab «Cadena de valor» (OE → producto → indicador/meta → actividades with code, ruta crítica, months, cost; findings; approve with hash; send adjustment to the agent) and an «Estilo SGR» column in Secciones for SGR runs. The roadmap for the remaining SGR panels is recorded in the Log (L4).

## Contracts

`artefactos/sgr/cadena_valor.json`, schema `morfeo.cadena-valor-sgr/v1`:
```
{schema, duracion_meses|null, arbol_hash,
 objetivos:[{id:"OE1", texto,                       # verbatim specific objective of the tree
   productos:[{codigo:"1.1", codigo_dnp|null, nombre, medido_a_traves_de, indicador, unidad, meta|null,
     actividades:[{codigo:"1.1.1", nombre, tipo:"tecnica"|"administracion"|"supervision",
                   ruta_critica:bool, mes_inicio|null, mes_fin|null, costo|null, medio|null}]}]}]}
```
Codes: product `<oe>.<p>`, activity `<oe>.<p>.<a>`, 1-based, consistent with their parents and unique. `medio` is the id of the tree means it comes from. Rules (`check`): objective texts equal the tree; every product has ≥2 technical activities; each OE has one `administracion` and one `supervision` activity under its last product; activity names do not open with an MGA-banned verb; `codigo_dnp` matches `^39\d{5}$` (warning when null); months inside 1..duracion and inicio ≤ fin; costs non-negative, warning when null from the budget phase on; sum of costs reported. Findings use check_run's shape `{severity, code, message, node}` with codes prefixed `cadena-`.

`artefactos/sgr/revision.json`: `{cadena_valor:{aprobado:bool, hash, fecha}}`, same approval semantics as `artefactos/arboles/revision.json` (approval tied to the file hash; a file with error findings cannot be approved).

`scripts/estilo_sgr.py`: `findings(run_root: Path, section: str | None = None) -> list[dict]` with `{severity:"advertencia"|"info", code:"sgr-estilo-<regla>", message, archivo, linea, extracto, regla}`; CLI `estilo_sgr.py RUN_ROOT [--section KEY] [--json]`, exit 0 always for findings (exit 2 only for bad input). Section keys are Morfeo section stems (`02_justificacion`, …, `25_marco_logico`).

check_run (SGR only): includes `cadena-*` findings and `sgr-estilo-*` findings (as warnings), by importing the two scripts from its own folder when they exist.

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S2, S3, S4, S5 | delegated (parallel writer, disjoint surface) | done | a5c2199 (31 tests RED→GREEN) |
| T2 | S1, S6 | delegated (parallel writer, disjoint surface) | done | 082acf2 (113 tests RED→GREEN; check_run differential: base identical) |
| T3 | S1, S7 | delegated (parallel writer, disjoint surface) | done | ee60397 (RED for routes and 10/11 JS; not for the two core loaders, written before their tests) |
| T4 | all | inline (parent): ports, kit manifest, seam check, full suite | done | a7dcee7 gate fix; ports/kit in 082acf2 |

Route evidence: three independent units with disjoint edit surfaces, each several files and over 100 changed lines, launched together; the parent context is past the long-session backstop. The parent owns git, generated ports and `kit-manifest.json`.

## Log

L1 (2026-11-19, user, verbatim): «si, haz comit y sigue con el plan, pero, asegurate de que este flujo sea especifico para cuando se activa modo sgr, para proyectos de investigacion generales seguimos con el flujo general. ademas, asegurate de constuir patrones de redaccion en cada seccion que ajustes o agregues, explora que paneles debemos agregar al morfeo ui, y incluir agente de revisoin de estilo y humanizacion y redundancia, segun los patrones y reglas que tenemos, pero que se ajusten a las directrices de dnp, y a los ejemplo s de proyectos y rubricas. explora que palabras no se deberian usar en cada seccion, que expresiones se favorecen, trtar de hablar en tercera persona relacionado con la proppuesta, ej, este proyecto busca, la presente propuesta se enmarca, etc»

L2 (2026-11-19, evidence): the writing-pattern evidence base (voice frequencies, chapters 1–31, lexicon L1–L30, redundancy R1–R14, conflicts C1–C18) was produced from the finished reference Anexo 2, the official Anexo 2 templates of Conv 55 and 56, the Conv 54 TdR, the MGA manuals, the UdeA diploma and the rubrics. Key facts: «el proyecto» is the default subject (1.95 per 1,000 words); first person only appears in pasted institutional text; the MGA verb ban covers activity names only; grant-flow-auditor Pass 1/3 and estilo-natural-es patterns 8, 11, 18 contradict SGR voice and required repetition; the SGR guide still closes §3 with a research question that neither the template nor the reference uses (drop it in SGR); the reference itself breaks MGA rules in places («Cero (0) prototipos» as baseline, «falta de» in the causal narrative), so the rules follow the MGA, not the example, where they disagree.

L3 (2026-11-19, decision): the SGR style reviewer is a separate agent that replaces grant-flow-auditor only in the SGR flow, so the base skills and auditor stay untouched.

L4 (2026-11-19, panel roadmap for the SGR flow, from the Anexo 2 coverage analysis): Cadena de valor (this increment); Alianza y territorio (entities, type, role, department, contributions; demand → cause/OE → activity → product matrix; live 2.2/3.2 score); Presupuesto SGR (Minciencias rubros × entity especie/efectivo/SGR, MGA view, live checks: transfer ≥1 %, mobility ≤2 %, cofinancing, Seguimiento, quotes; counterpart-hours calculator) with a Gantt by activity code; TRL y componentes transversales (TRL in/out, evidence, verification plan, ASC 7 elements, transfer %, differential measures, post-project operation); Productos e indicadores (DNP 3906 products, gestión/producto indicators, talent minimums); Requisitos y anexos (TdR and VRI checklist); Anexo 2 view (31 chapters with status and rule); Juez final (done).

L5 (2026-11-19, parent seam, partial): `status.parse_gates_info` matched gate ids by substring, so G4 approved G4.cv (and G6/G6.4, G1/G1a/G1c leaked into each other). Fixed with whole-token matching (`_gate_token_in`) and four tests (RED observed). Differential on the real base run `2026-09-tept-depresion-ia-portable`: G1c now reads PENDING instead of PASS; that run never recorded G1c (it predates Fase 1c), so the old PASS was the bug. Added `fase4_sgr` to `propuesta-continuar.md` (+kit), its phase guide in the dashboard (`tab: 'cadena'`), an in-flight skip in `unit_progress` for SGR runs that passed G4 before the unit existed (tests RED→GREEN), and `scripts/cadena_valor_sgr.py` to the kit manifest.

L6 (2026-11-19, close): T1 merged; SGR §3 research-question references aligned in `propuesta.md` and `investigador.md`; kit rebuilt (`build-kit.py`, in step); ports regenerated (no drift) and `.pi/README.md` counts updated (12 agents, 4 skills). AGENTS.md trims checked: the citation rule still lives in rule 6 and the typography in the style invariants. Full Python suite: 762 tests, only the 14 base environment failures (LaTeX, pi models, PTY). JS 161/161 (scratch jsdom). Commits: a5c2199 style, 082acf2 value chain + ports/kit, a7dcee7 gate fix, ee60397 dashboard. Risk: item 3, as noted by T1 and T2 (AGENTS.md trimmed; shared pipeline inventory, check_run and gate parsing changed). Base behaviour is pinned by tests and by the check_run and gate differentials. The one visible base change is G1c pending on a closed run that never recorded it. RDD is off for this clone. Next increments: L4 roadmap (Alianza y territorio, Presupuesto SGR with Gantt, TRL y componentes, Productos e indicadores, Requisitos, Anexo 2 view).
