# SGR: productos, talento humano e indicadores (plan P5)

Objective: give the SGR flow structured data, rendered sections, a pipeline unit and a dashboard tab for the expected products (DNP 3906 catalog and CTeI products above the call minimum), the public science dissemination strategy, the human talent to be linked (with the call minimums), and the management and product indicators. SGR-only; the base flow does not change.
Branch `feat/sgr-productos-indicadores` (stacked on `feat/sgr-trl-componentes`), delivery `single-pr`. Tests: `uv run python -m unittest discover tests -p "test_*.py"` and the JS suite (scratch jsdom). Receipt-driven review is off for this clone.

## Specs

S1. Pedido textual (L1): «dale», accepting the proposal (verbatim from the previous reply): «Siguen en la hoja de ruta «Productos e indicadores» (productos DNP 3906, indicadores de gestión y de producto, mínimos de talento humano), luego «Requisitos y anexos» y por último la vista del Anexo 2. ¿Continúo con «Productos e indicadores»?». Standing rule (verbatim): «asegurate de que este flujo sea especifico para cuando se activa modo sgr, para proyectos de investigacion generales seguimos con el flujo general». Base runs keep the same units, findings, sections (including the hand-written §15) and tabs (pinned by tests).

S2. Standing rule (verbatim): «asegurate de constuir patrones de redaccion en cada seccion que ajustes o agregues». Each new or changed SGR section gets its `### SGR` block with a «Redacción» part and lexicon entries (from `docs/sgr/patrones_redaccion_sgr.md` chapters 12.4, 20, 21, 24 and 25), third-person project voice.

S3. Data: `artefactos/sgr/productos.json` per Contracts; `scripts/productos_sgr.py` (`check`, `render`, `datos`) validates it against the value chain (products, DNP codes, indicators), the alliance (entities), the budget (talent items) and the call rubric (talent minimums, CTeI product minimum and the 2.5 scoring), and renders the sections deterministically.

S4. Sections (SGR stems, registered wherever SGR sections are listed): `36_talento_humano` (Anexo 2 caps. 12.4 and 20), `37_indicadores` (caps. 24 and 25), both rendered; in SGR runs `15_productos_esperados` (cap. 21, products by objective with DNP code plus the CTeI products and the dissemination strategy) is rendered instead of hand-written. Rubric evidence for products/dissemination (Conv 54 2.5) and for timeliness/talent where relevant points to them. The call minimums live in the rubric files (`minimos_talento`, `minimo_productos`), copied verbatim from the TdR.

S5. Pipeline: SGR-only unit `fase5_sgr` «Productos, talento e indicadores», gate `GProductos`, after `fase5` (§8–§9) and before `fase5_5`: investigador writes the CTeI products, the dissemination strategy and the management indicators; redactor writes the talent profiles; `check` until clean; `render`; revisor; approval in the dashboard tab. Fase 6.4 talent items in the budget match the talent block; Fase 6.45 (where §15 is written today) in SGR re-renders §15. The judge reads `productos_sgr.py datos`.

S6. Dashboard: SGR-only tab «Productos e indicadores» after «TRL y componentes»: talent table against the call minimums (badges), products by objective with DNP code, indicator, unit and goal (from the value chain), CTeI products with the additional-above-minimum count and TOP/A count and the 2.5 preview, the dissemination checklist (audiences, media, products, responsible, schedule, costed), management and product indicator tables, findings by severity, approval tied to the hash, «Enviar ajuste al agente».

## Contracts

`artefactos/sgr/productos.json`, schema `morfeo.productos-sgr/v1`:
```
{schema,
 talento:[{categoria:"joven_investigador"|"maestria"|"doctorado"|"posdoctorado"|"profesional"|"tecnico"|"otro",
           cantidad:int, entidad:"E1", perfil, formacion, actividades:["1.1.1"], duracion_meses:int|null,
           valor_mensual:number|null, producto_final}],
 productos_ctei:[{tipo:"nuevo_conocimiento"|"desarrollo_tecnologico"|"apropiacion_social"|"formacion",
                  subtipo, categoria:"TOP"|"A"|"B"|"otro"|null, cantidad:int, adicional:bool,
                  producto_cadena:"1.1"|null, descripcion}],
 divulgacion:{introduccion, publicos:[str], medios:[str], productos:[str], responsable:"E1"|null,
              cronograma:[{mes, accion}], costeada:bool}|null,
 indicadores_gestion:[{indicador, codigo|null, meta, unidad, formula, tipo_fuente, periodicidad}]}
```
Product indicators are read from `cadena_valor.json` (`codigo_dnp`, `indicador`, `unidad`, `meta`), never duplicated here. Rules (`check`, codes `productos-*`): entity ids exist; activity codes and `producto_cadena` exist in the value chain; every value-chain product has a DNP code `^39\d{5}$`, indicator, unit and goal (warning when missing); talent meets the call minimums from the rubric (`minimos_talento`; Conv 54 numeral 10: one doctor in a postdoctoral stay, two research master's students, six young researchers and innovators) — error when below; talent with value and duration matches the budget's `talento_humano` items for the same entity (warning on mismatch, when the budget exists); CTeI products: the call minimum is met (error), additional products are counted and the Conv 54 2.5 component A preview is computed (3 or more additional with 2 TOP/A → 3; 2 with 1 TOP/A → 2; 1 → 1); dissemination: complete and costed for 2 points, incomplete for 1 (preview), missing → warning; management indicators: at least the supervision and the technical-financial reporting indicators with periodicity (warning when missing). `datos RUN --json`: `{productos_adicionales:{total, top_o_a, fuente}, fuente}` for `datos_sgr`, plus `{talento:{categoria:cantidad}}`.

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S2, S3, S4 | delegated (parallel writer, disjoint surface) | done | 2753309 (52 tests RED→GREEN; check_run differential on the base run identical) |
| T2 | S1, S5 | delegated (parallel writer, disjoint surface) | done | 39255db (137 tests RED→GREEN) |
| T3 | S1, S6 | delegated (parallel writer, disjoint surface) | done | ccd430e (20 py + 18 js tests RED→GREEN) |
| T4 | all | inline (parent): ports, kit, seam, full suite, commits | done | seam in 39255db |

Route evidence: three independent units with disjoint edit surfaces, each several files and over 100 changed lines, launched together; the parent context is past the long-session backstop. The parent owns git, ports and the kit manifest.

## Log

L1 (2026-11-19, user, verbatim): «dale»

L2 (2026-11-19, evidence): Conv 54 TdR numeral 10 asks for talent in training and lists the minimums «Un (1) doctor para la realización de una estancia posdoctoral», «Dos (2) estudiantes de maestría en modalidad de investigación», «Seis (6) jóvenes investigadores e innovadores»; criterion 2.5 (5 points) scores CTeI products committed above the minimum of numeral 10 (A: 3 with 2 TOP/A → 3, 2 with 1 TOP/A → 2, 1 → 1) and a dissemination strategy «con públicos, medios, productos, responsable y cronograma definidos y costeados» (2) or incomplete (1); products of numeral 10 do not score. The finished reference project presents products as «Programa | Producto | Medido a través de | Indicador de producto | Unidad de medida | Descripción» with DNP 3906 codes, talent as «Categoría | Cantidad | Entidad que vincula | Duración | Valor mensual | Producto final» and profiles as «Perfil | Entidad que lo vincula | Formación y experiencia | Actividades y meses | Producto final», and management indicators as «Indicador | Medida/Meta | Código | Fórmula | Tipo de fuente | Fecha» with quarterly supervision and technical-financial reports.

L3 (2026-11-19, close): kit manifest gains `productos_sgr.py` (README asset count 102); kit rebuilt; ports regenerated with no drift. Full Python suite: 1182 tests, only the 14 base environment failures; JS 219/219 (scratch jsdom). All three writers observed RED before implementing. Interpretations to confirm with the user: a talent entry matches a budget `talento_humano` item of the same entity by value (±1 peso); the TdR rule that master's and postdoc products must be TOP/A is not enforced (the minimums shape cannot express it); the «Programa» column shows the four-digit program code from `codigo_dnp`; only new-knowledge and technological-development products count toward the CTeI minimum and the additional count (ASC products score in 2.4); Conv 56 numeral 9 sets the same talent minimums as Conv 54 numeral 10. Rendered sections could not be compiled here (`xltabular.sty` missing, as in the base LaTeX failures). SGR `--final` now also requires 36 and 37. Risk: item 3 (rubric keys read by the judge, SGR sections, recipe). Next roadmap step: Requisitos y anexos.
