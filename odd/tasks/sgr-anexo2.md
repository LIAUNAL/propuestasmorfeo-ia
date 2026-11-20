# SGR: vista del Anexo 2 (31 capítulos con estado y regla)

Objective: give the SGR flow a read-only view of the Anexo 2 chapters: for each chapter, the Morfeo sections that fill it with their state (missing, draft, written, generated, stale) and findings, the writing rule of the chapter (from `docs/sgr/patrones_redaccion_sgr.md`), its lexicon entries and the rubric criteria that read it; as a script (`scripts/anexo2_sgr.py datos`) and a dashboard tab. SGR-only; the base flow does not change.
Branch `feat/sgr-anexo2` (stacked on `feat/sgr-requisitos-anexos`), delivery `single-pr`, then merge to `main`, push and release (L1). Tests: `uv run python -m unittest discover tests -p "test_*.py"` and the JS suite (scratch jsdom). Receipt-driven review is off for this clone.

## Specs

S1. Pedido textual (L1): «si, luego mergea push y release», accepting the proposal (verbatim from the previous reply): «Queda el último paso de la hoja de ruta: la vista del Anexo 2, con los 31 capítulos, su estado y su regla. ¿Sigo con eso?». Roadmap line (sgr-cadena-estilo L4, verbatim): «Anexo 2 view (31 chapters with status and rule)». Standing rule (verbatim): «asegurate de que este flujo sea especifico para cuando se activa modo sgr, para proyectos de investigacion generales seguimos con el flujo general». Base runs keep the same units, findings, sections and tabs (pinned by tests).

S2. Script `scripts/anexo2_sgr.py datos RUN [--json]` computes the view per Contracts. Chapters come from the run's `artefactos/estructura_tdr.json` placed with `ensamblar_main.placed_chapters(data, "sgr")` when it exists, else from `mapa_capitulos` of `scripts/sgr/lexico_sgr.json` (Conv 54, 31 chapters). The text output lists one line per chapter (number, state, title, sections with their state). A base run exits 2 with a message that the view only exists in the SGR flow. It writes nothing.

S3. Rule per chapter: parsed from section «## 2.» of `docs/sgr/patrones_redaccion_sgr.md` (headings `### N. TITLE`; bullets «Propósito», «Estructura», «Extensión», «Aperturas favorecidas», «Evitar», «Fuente»), matched to the chapter by normalized title (accents, case and punctuation ignored; equal or one a prefix of the other), else by number when the chapters come from the lexicon. Lexicon counts per chapter from `secciones[stem]` of the lexicon. Rubric criteria: subcriteria of the run's rubric (`juez_sgr.detect_rubric`) whose `evidencia` lists any of the chapter's stems; no rubric → empty list and `rubrica: null`.

S4. Dashboard: SGR-only read-only tab «Anexo 2» after «Requisitos y anexos»: summary by state, the chapter list with state badge, sections (state, words, finding counts, guide block key), an expandable rule (purpose, structure, extension, favoured openings, avoid, source), lexicon counts and rubric criteria chips, a filter «Solo pendientes», and a way to open a section in the sections panel. `GET /api/anexo2` returns the script view; base runs get 409. No approval, no writes.

## Contracts

`anexo2_sgr.py datos RUN --json`, schema `morfeo.anexo2-sgr/v1`:
```
{schema, flujo:"sgr", fuente_capitulos:"artefactos/estructura_tdr.json"|"scripts/sgr/lexico_sgr.json",
 fuente_reglas:"docs/sgr/patrones_redaccion_sgr.md"|null, rubrica:"conv54"|null,
 resumen:{capitulos:int, por_estado:{falta, incompleto, desactualizado, listo}, palabras:int},
 capitulos:[{numero:int, titulo:str, estado:"falta"|"incompleto"|"desactualizado"|"listo", palabras:int,
   secciones:[{stem, existe:bool, palabras:int, origen:"generado"|"manual"|null, script:"scripts/x.py"|null,
               estado:"falta"|"borrador"|"redactado"|"generado"|"desactualizado",
               hallazgos:{error:int, warning:int, info:int}, guia:"§N"|"A<N>"}],
   regla:{proposito, estructura, extension, aperturas:[str], evitar:[str], fuente}|null,
   lexico:{favorecida:int, desaconsejada:int, prohibida:int},
   criterios:[{id, nombre, max}],
   hallazgos:[{severidad, codigo, mensaje, seccion}]}]}
```
Section state: `falta` (no file); `generado` (first lines carry `% GENERADO por scripts/<x>.py`, `script` set) or `desactualizado` (generated and check_run reports a `*-anexo-desactualizado` finding on that file); otherwise `borrador` (≤50 words after stripping LaTeX comments, the dashboard heuristic) or `redactado`. Chapter state: `falta` when no section exists; `desactualizado` when any section is stale; `incompleto` when any section is missing or a draft; else `listo`. `diag_*` files are not sections. Findings come from one `check_run` pass (non-final, flow sgr) and one `estilo_sgr` pass, mapped to sections by file stem; chapter `hallazgos` lists at most 20, errors first. Guide key: stem number ≥ 19 → `A<N>`, else `§N` (same rule as `sgrBlockKey` in index.html).

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S2, S3 | delegated (parallel writer, disjoint surface) | done | f139b3e (28 tests RED→GREEN) |
| T2 | S1, S4 | delegated (parallel writer, disjoint surface) | done | 5a31b83 (12 py + 14 js tests RED→GREEN) |
| T3 | all | inline (parent): kit, README, seam, full suite, commits, merge, push, release | done | seam in f139b3e; merge ef54868; release v0.8.0 |

Route evidence: two independent units with disjoint edit surfaces (script vs dashboard), each several files and over 100 changed lines, launched together; the contract above is the seam. The parent owns git, the kit manifest, ports and the release.

## Log

L1 (2026-11-20, user, verbatim): «si, luego mergea push y release»

L2 (2026-11-20, evidence): `origin/main` holds 11 commits the stack never saw: v0.7.0 with `feat/sgr-flujo-convocatorias` (per-call rules in `artefactos/convocatoria.json`, SGR `--final` from `estructura_tdr.json` chapters, unit `fase6_3`, `estilo_es.py` score and `revisor-redundancia`, trimmed SGR navigation and a TDR chapters panel). A trial merge leaves 32 conflicted files, 12 of them sources.

L3 (2026-11-20, user, verbatim answer to «¿Cómo hago el merge?»): «Unir ambas (Recomendado)» — keep both lines; where they collide the v0.7.0 rule wins (`--final` requires the `estructura_tdr.json` chapters, with the new SGR sections placed through `placed_chapters`); both style and rubric systems stay; full suite; release v0.8.0.

L4 (2026-11-20, close of T1–T2): kit manifest gains `scripts/anexo2_sgr.py` (README 105 assets); kit in step; three port checks clean. Seam against a copy of the tept run set to sgr: 31 chapters from the lexicon (10 listo, 7 incompleto, 14 falta), rule matched, base run rejected. Full Python suite 1329, only the 14 environment failures; JS 252/252. Choices: rubric through `juez_sgr.resolve_rubric`; check_run `sgr-estilo*` findings dropped in favour of the direct estilo_sgr pass; chapters 3, 24, 25, 29, 30 and 31 keep guidance under labels outside the six parsed bullets, so their rule shows little.

L5 (2026-11-20, merge): branch `merge/sgr-v0.8` from `origin/main`; 32 conflicts resolved by a delegated writer (context backstop) under the L3 policy; kit and ports regenerated; README 108 assets; AGENTS.md trimmed to the 24,000-char budget. SGR chain: fase1a → fase1a_sgr → fase1b → fase1b_sgr → fase1c → fase1 → fase2 → fase3 → fase4 → fase4_sgr → fase5 → fase5_sgr → fase5_5 → fase5_5_sgr → fase6 → fase6_3 → fase6_4 → fase6_45 → fase6_46 → fase6_47 → fase6_5 → fase6_9_sgr → fase7; base chain identical to v0.7.0. The union left A23 «Evaluación MGA» without a writer (v0.7.0 prose vs the stack's rendered A23); fixed inline: optional `evaluacion_mga` text in `cadena_valor.json`, rendered after the table (3 tests RED→GREEN). Full suite 1508, 13 environment failures; JS 262/262; base check_run differential against v0.7.0 identical. To confirm with the user: SGR `fase6_3` dispatches `revisor-estilo-sgr` instead of `grant-flow-auditor` (stack rule; a v0.7.0 test was adapted); the new «Redacción» part of guide §12 was written by the merge writer.
