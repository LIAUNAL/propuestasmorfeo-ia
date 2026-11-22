# Morfeo: text size, English/Spanish dashboard and writing language, manuscript translation

Objective: port papersmith-ai's text-size selector and EN/ES dashboard switch, let a project write its artifacts, phases and manuscript in English or Spanish, and translate the manuscript ES→EN and EN→ES keeping humanization, anti-redundancy and anti-"claudism" rules.
Branch `feat/idioma-tablero-traduccion` from `main` ea5c928. Delivery `ask-on-risk` (forecast well above 400 lines; work-unit commits, PR at the end). Tests: `uv run python -m unittest discover tests -p "test_*.py"` and `node --test tests/js/*.test.mjs`.

## Specs

S1. Text size (L1, verbatim): «cambio de tamaño de textos como en proyecto smith con selector arriba a la derecha en el ui.» Acceptance: a selector in the top-right actions of the dashboard with ×1, ×1.25, ×1.5 and ×2 scales the root font size (papersmith `text-size.js`: `--text-scale`, `data-text-scale`), persists per viewer in localStorage, applies before first paint, and no tab overflows horizontally at ×2 or at 360 px.

S2. Dashboard language (L1, verbatim): «cambio de idioma en el tablero como en smith». Acceptance: an EN/ES selector next to the text size switches every user-visible dashboard string (markup, inline script, `static/*.js` panels, server-built labels such as gate and phase names) through catalogues with key parity tests (papersmith `i18n.js`, `data-i18n*`, `t()`, `languagechange`, `/api` localization), persists per viewer, defaults to Spanish, and never changes machine values or workspace files.

S3. Writing language (L1, verbatim): «y la posibildiad de escribir y ejecutar enningles o en español los artefactos fases y manuscrito». Acceptance: a project-level writing language (`lang` in `.morfeo/config.json`, `es` default, set at `morfeo init --lang` and changeable afterwards) that the dispatcher and every agent receive, so artifacts, phases and the manuscript are written in that language; English prose gets its own humanization and anti-redundancy rules (an English counterpart of `estilo-natural-es` and of the deterministic style check), the LaTeX template, DOCX build and `check_run.py` rules follow the language, and Spanish projects behave exactly as today. The dashboard language (S2) and the writing language are independent settings (assumption L2).

S4. Manuscript translation (L1, verbatim): «habilitar la posibilidad de traduccion ingles español y español ingles el manuscrito, preservando estrategias de himanizacion, evitar redundancia, claudismo etc, segun reglas de redaccion y agentes para ello en smith y morfeo». Acceptance: both directions (ES→EN and EN→ES); the manuscript in the writing language stays canonical and the translation is a derived artifact per block with staleness by digest (papersmith `paper_translate.py`: plan/store/build/audit/status, fidelity gate on citations, labels, math, numbers and paragraph count, refusal codes); a translator agent and a target-language style reviewer apply the target language's humanization, anti-redundancy and anti-claudism rules; the PDF preview offers the translated version in a fold like papersmith's «Manuscript version».

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S1, S2 (runtime, top bar, markup and inline script of index.html) | delegated writer, isolated worktree, parallel with T2 | pending | |
| T2 | S3 | delegated writer, isolated worktree, parallel with T1 | pending | |
| T3 | S2 (static/*.js panels, server-built labels, pages rendered by the server) | delegated writer after T1 merges | pending | |
| T4 | S4 | delegated writer after T2 merges (needs the English style rules) | pending | |
| T5 | all | inline (parent): merges, kit and ports, docs, suites, browser seam check, PR | pending | |

Route evidence: T1 and T2 are independent behaviors with disjoint surfaces (dashboard vs agents, skills, scripts, template), each well over 100 lines; T3 needs T1's runtime; T4 needs T2's English style rules and touches the PDF preview after T1. Writers also justified by the parent context backstop.

## Log

L1 (2026-11-22, user, verbatim): «luego explora planea y implementa: 1 cambio de tamaño de textos como en proyecto smith con selector arriba a la derecha en el ui. 2 cambio de idioma en el tablero como en smith y la posibildiad de escribir y ejecutar enningles o en español los artefactos fases y manuscrito. 3 habilitar la posibilidad de traduccion ingles español y español ingles el manuscrito, preservando estrategias de himanizacion, evitar redundancia, claudismo etc, segun reglas de redaccion y agentes para ello en smith y morfeo»

L2 (2026-11-22, exploration and decisions): papersmith: `CC/static/text-size.js` (`papersmith.textScale`, scales 1/1.25/1.5/2, `html{font-size:calc(100% * var(--text-scale,1))}`); `CC/static/i18n.js` + `i18n/en.js`/`es.js` (1848 keys each), `LocalizeMiddleware` (`CC/localize.py`, `server-es.json`), parity tests `tests/test_dashboard_i18n.py`; dashboard language never changes artifacts there (artifacts always English). Translation is EN→ES only: `skills/paper-writing/scripts/paper_translate.py` (677 lines), `paper_style_es.py` (adapted from Morfeo `estilo_es.py`), agents `translator.md`, `translation-style-reviewer.md`, UI `translation-panel.js`, fold `translationDetails`. Morfeo: no i18n layer (`<html lang="es">`, several thousand Spanish strings; 331 of 334 font sizes in rem; xterm fixed 13 px); `lang` written by `morfeo init --lang` (`core/init.py:96`) and never read; Spanish hard-coded in 15 of 17 agents, AGENTS.md rule 1, skills `estilo-natural-es`/`depuracion-redundancias-es`/`estilo-sgr`, `estilo_es.py`, `check_run.py` regexes, `plantilla/main.tex` babel spanish, `prep_docx.py` nouns, `core/pipeline_units.py` GATE_INFO; AGENTS.md is 23965/24000 characters (`tests/test_token_budget.py`). Decisions (assumptions): dashboard language (per viewer, default es) and project writing language (per project, default es) are independent; the SGR flow stays Spanish-only (DNP/MGA, Colombian royalties); translation keeps the writing-language manuscript canonical.
