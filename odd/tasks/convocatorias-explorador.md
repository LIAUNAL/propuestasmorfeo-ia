# Convocatorias: agent and panel that find funding calls matching the idea and banco-lia

Objective: an agent (`explorador-convocatorias`, command `/propuesta-convocatorias`) that searches calls in Colombia, Latin America and internationally, in Spanish and English, for researchers, students, companies, centres, universities and groups; a stdlib script that validates, applies Colombian eligibility rules and ranks them; and a read-only dashboard tab «Convocatorias» for both flows. Plan A of the 2026-11-20 research.
Branch `feat/convocatorias` (stacked on `docs/sgr-guia-etica`), delivery `single-pr`, no push unless asked. Tests: `uv run python -m unittest discover tests -p "test_*.py"` and the JS suite (`node --test tests/js/*.test.mjs`). Receipt-driven review is off for this clone.

## Specs

S1. Pedido textual (L1): «haz commit de la guía §12 y luego plan A». Plan A, as proposed verbatim in the previous reply:
«1. **Perfil de búsqueda:** `idea.md` más banco-lia, con quién aplica (investigador, estudiante, empresa, centro o universidad), los temas, los financiadores previos y los idiomas (español e inglés).
2. **Agente `explorador-convocatorias`:** Usa la combinación de herramientas anterior, más una API de búsqueda (Exa o Tavily) para lo que no está en las fuentes fijas. Fuentes fijas: Minciencias, SEDIA, Grants.gov, los RSS de los agregadores, UKRI y Humboldt. Escribe `oportunidades.json` con rol, cierre, monto, idioma, ámbito, puntaje y evidencia citada.
3. **Script de reglas sin red:** filtra con las reglas de elegibilidad para Colombia (las de la sección anterior) y ordena combinando coincidencia por palabras y puntaje del agente.
4. **Panel «Convocatorias»** para ambos flujos: Tarjetas con cuenta regresiva y filtros por ámbito, idioma y tipo de aplicante. Avisos de rol, por ejemplo «solo como socio». Botón «Iniciar propuesta con esta».»
Origin request (L2): «explora que mcp cli web search podemos usar para constuir un agente y un panel en el morfeo ui que explore opciones de convocaroriqs afines a la idea del proyecto que se crea con moefeo init y opciones para lo que se trabaja en bancolia mcp, buscando match y oportunidades a nivel regional clombia, latinoamerica e internacional de convocatorias para investigadores, esrufiantes, grupos de investigacion, centros, universidades, empresas, etc.» and (L3) «explora tambien opciones para aplicar en ingles, dewde que sea compatible para investigadores, estufisntes, empresas, centros, universidades colombianas. para web scrappong mira si claude ya tiene herramientas similares, mas chrome dev tools».

S2. Script `scripts/convocatorias.py` (stdlib only, no network), CLI:
- `perfil DIR` creates `convocatorias/perfil.json` in the workspace when missing (title from `.morfeo/config.json`, idea text from `idea.md` or the active run's `insumos/ideas/idea.md`); never overwrites; prints the path.
- `check DIR` validates `perfil.json` and `oportunidades.json` per Contracts; exit 1 on any error, 0 otherwise; text lists findings `severidad código mensaje`.
- `datos DIR [--json] [--hoy YYYY-MM-DD]` prints the ranked view per Contracts; text output one line per call (puntaje, estado, días, rol, título).
- `fuentes [--json]` prints the fixed source catalogue `scripts/convocatorias/fuentes.json`.
`DIR` is the workspace root or any folder inside it (a run dir); the script walks up to the folder holding `.morfeo/config.json` (else `.marco/config.json`). Works in base and sgr flows alike. Writes only in `perfil`.

S3. Eligibility rules for Colombian applicants in `scripts/convocatorias/reglas_co.json`, applied by `datos`: each rule matches calls by funder/programme regex (accent- and case-insensitive over `financiador` + `programa` + `titulo`) and sets or confirms `rol_colombia` with a Spanish `aviso` shown to the user. Rules seeded from the research (L4): Horizon Europe → funded partner, does not count toward the 3-country minimum; MSCA Global Postdoctoral → no elegible; MSCA Postdoctoral/ERC → anfitrión en la UE o país asociado; MSCA Staff Exchanges/Doctoral Networks → socio; Erasmus+ CBHE → socio, multi-country only (Región 10); Erasmus+ KA171 → socio (EU university applies); Wellcome Discovery → coaplicante; TWAS/OWSD lagging-countries schemes → no elegible; IDRC AI4D → socio (LatAm not a lead region); NSF → socio sin financiación; UKRI ISPF / Royal Society International Exchanges → socio (UK lead); Newton International / British Academy International Fellowships → líder with UK sponsor; Humboldt Georg Forster → pausada; NIH → foreign subawards stopped, direct foreign award allowed. A rule never overrides an agent value of `no_elegible` with a more permissive role; when rule and agent disagree the view keeps the rule role and records both.

S4. Ranking: lexical score 0–100 from accent-insensitive token overlap between the call text (`titulo`, `temas`, `resumen`, `elegibilidad`) and the profile keywords (`temas`, `palabras_clave.es`, `palabras_clave.en`), with Spanish and English stopwords dropped; combined `puntaje = round(0.5 * puntaje_agente + 0.5 * lexico)` (lexical only when the agent score is missing). Order: vigentes (estado `abierta`/`proxima`, not past `cierre`) before the rest; within each, `rol_colombia` ≠ `no_elegible` first, then `puntaje` desc, then nearest `cierre`. `dias_restantes` = cierre − hoy (null without cierre). A call whose `cierre` is before `hoy` is shown as `cerrada` whatever the agent wrote.

S5. Agent `explorador-convocatorias` + command `/propuesta-convocatorias [buscar|iniciar <id>]`: builds the profile (`perfil`, then fills `temas`, keywords in es and en, applicant types and `financiadores_previos` from `idea.md` and the banco-lia MCP: `search_bank`, `lab_capabilities`, `related_items`); searches the fixed sources and the web (Claude Code `WebSearch`/`WebFetch`; an optional search MCP such as Exa or Tavily and Playwright MCP when configured); writes `oportunidades.json`; runs `check` and fixes errors. Politeness: one request at a time per host, ≥10 s between requests to minciencias.gov.co (robots Crawl-delay 10), a host ledger in `convocatorias/registro_fuentes.json`; bot-protected sites (HTTP 403) are recorded as `bloqueado`, never bypassed. Copyright: store metadata, link and own-words summaries only; quotes in `evidencia` ≤200 characters; never copy TdR PDFs into the workspace except on `iniciar`, which downloads the selected call's TdR into the active run's `insumos/tdr/` (or tells the user to run `/propuesta-init` first). Summaries in Spanish, third person, no promotional language.

S6. Dashboard: tab «Convocatorias» right after «Flujo general», in both flows, read-only: summary counts (vigentes, por ámbito, por rol), cards with title, funder, ámbito, idioma, role notice (e.g. «solo como socio»), countdown (días restantes / «cerrada» / «sin fecha»), amount, puntaje, own-words summary, evidence links; filters por ámbito, idioma and tipo de aplicante, plus «Solo vigentes»; the list of sources consulted with their result; buttons «Buscar convocatorias» (sends `/propuesta-convocatorias` to the terminal) and, per card, «Iniciar propuesta con esta» (sends `/propuesta-convocatorias iniciar <id>`). `GET /api/convocatorias` works without an active run (workspace level). No writes from the dashboard.

## Contracts

Workspace files (created by the agent; the script writes only `perfil.json` on `perfil`):

`convocatorias/perfil.json`, schema `morfeo.perfil-convocatorias/v1`:
```
{schema, actualizado:"YYYY-MM-DD"|null, titulo:str|null, idea:str|null,
 aplicantes:[ "investigador"|"estudiante"|"empresa"|"centro"|"universidad"|"grupo" ],
 temas:[str], palabras_clave:{es:[str], en:[str]}, financiadores_previos:[str],
 idiomas:[ "es"|"en"|"pt"|"fr" ], ambitos:[ "colombia"|"latam"|"internacional" ],
 institucion:{nombre:str|null, pais:"CO", tipo:str|null}}
```
Skeleton from `perfil`: all lists empty except `idiomas:["es","en"]`, `ambitos:["colombia","latam","internacional"]`; `titulo`/`idea` filled when found.

`convocatorias/oportunidades.json`, schema `morfeo.oportunidades/v1`:
```
{schema, actualizado:"YYYY-MM-DD",
 fuentes_consultadas:[{fuente:str, url:str, fecha:"YYYY-MM-DD", resultado:"ok"|"sin_resultados"|"bloqueado"|"error", n:int}],
 oportunidades:[{id:str (unique, slug), titulo, financiador, programa:str|null, url,
   fuente:str, ambito:"colombia"|"latam"|"internacional", idioma:"es"|"en"|"pt"|"fr",
   aplicantes:[same enum as perfil], rol_colombia:"lider"|"socio"|"coaplicante"|"anfitrion_exterior"|"no_elegible"|"desconocido",
   estado:"abierta"|"proxima"|"cerrada"|"pausada", apertura:"YYYY-MM-DD"|null, cierre:"YYYY-MM-DD"|null,
   cierre_tipo:"fijo"|"estimado"|"continuo"|"desconocido", monto:{min:number|null, max:number|null, moneda:str}|null,
   temas:[str], resumen:str (≤600 chars), elegibilidad:str|null (≤600 chars),
   puntaje_agente:int 0..100|null, evidencia:[{texto:str ≤200 chars, url:str}], encontrada:"YYYY-MM-DD"}]}
```
Errors: missing or wrong schema, invalid enum, bad date, duplicate id, missing `titulo`/`financiador`/`url`/`ambito`, `resumen` or `elegibilidad` over 600, `evidencia.texto` over 200, `puntaje_agente` out of range, `cierre` before `apertura`. Warnings: no `evidencia`, `rol_colombia` `desconocido`, `cierre` null with estado `abierta`.

`datos --json`, schema `morfeo.convocatorias-vista/v1`:
```
{schema, hoy, workspace, perfil:{existe:bool, aplicantes, idiomas, ambitos, n_palabras_clave:int},
 resumen:{total, vigentes, por_ambito:{colombia,latam,internacional}, por_rol:{lider,socio,coaplicante,anfitrion_exterior,no_elegible,desconocido}, por_idioma:{...}},
 fuentes_consultadas:[as in file],
 oportunidades:[{...call fields..., estado (recomputed), dias_restantes:int|null, vigente:bool,
   rol_colombia (final), rol_agente, regla:{id, aviso}|null, aviso:str|null,
   lexico:int, puntaje:int}],
 hallazgos:[{severidad, codigo, mensaje, id}]}
```
Without `oportunidades.json`: exit 0 with `oportunidades: []`, `resumen` zeros and a `hallazgos` info `sin-oportunidades`.

`scripts/convocatorias/reglas_co.json`, schema `morfeo.reglas-elegibilidad-co/v1`: `{schema, fuente, revisado:"YYYY-MM-DD", reglas:[{id, patron (regex), rol:"lider"|"socio"|"coaplicante"|"anfitrion_exterior"|"no_elegible"|null, estado:"pausada"|null, aviso:str, fuente_url}]}`; first matching rule wins; `rol: null` keeps the agent role and only adds the notice (and the state), used for NIH and Georg Forster, whose role depends on the call.

`scripts/convocatorias/fuentes.json`, schema `morfeo.fuentes-convocatorias/v1`: `{schema, revisado, fuentes:[{id, nombre, url, ambito, idioma, metodo:"api"|"rss"|"html"|"pdf"|"navegador"|"busqueda", aplicantes:[...], notas}]}` seeded with: Minciencias (html, crawl-delay 10, terms forbid reproduction), Plan bienal SGR (pdf), iNNpulsa RSS, Fulbright Colombia RSS, EU Funding & Tenders SEDIA API, Grants.gov search2 API, UKRI RSS, Humboldt (html), fundsforNGOs / Opportunity Desk / Scholars4Dev / ProFellow RSS, EURAXESS (html), CYTED (navegador), IDB Lab (navegador, 403 to fetchers), IDRC (html), Google Research programmes (html).

HTTP: `GET /api/convocatorias` → `{ok:true, disponible:bool, vista|null, error|null}` (never 404 for a missing run). `POST /api/convocatorias/buscar` → `{ok, prompt:"/propuesta-convocatorias"}`. `POST /api/convocatorias/iniciar {id}` → `{ok, prompt:"/propuesta-convocatorias iniciar <id>"}`; 400 when `id` is empty or not a slug `[a-z0-9-]+`.

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S2, S3, S4 | delegated (parallel writer, disjoint surface: script, data, tests) | done | 52d9cca (34 tests RED→GREEN; +1 parent fix for role-less rules) |
| T2 | S6 | delegated (parallel writer, disjoint surface: dashboard core, server, index.html, tests) | done | d76b9f6 (16 py + 14 js tests RED→GREEN) |
| T3 | S1, S5 | inline (parent): agent, command, agent-models, gen rules, ports, kit manifest, README/docs, seam, full suite, commits | done | f42c726 |

Route evidence: T1 and T2 are independent units with disjoint edit surfaces, each several files and over 100 changed lines, launched together; the Contracts above are the seam. The parent owns git, the kit manifest, ports and docs. Forecast ~1,600 authored lines; delivery `single-pr` as in the previous SGR features (no push without request).

## Log

L1 (2026-11-20, user, verbatim): «haz commit de la guía §12 y luego plan A»

L2 (2026-11-20, user, verbatim): «luego explora que mcp cli web search podemos usar para constuir un agente y un panel en el morfeo ui que explore opciones de convocaroriqs afines a la idea del proyecto que se crea con moefeo init y opciones para lo que se trabaja en bancolia mcp, buscando match y oportunidades a nivel regional clombia, latinoamerica e internacional de convocatorias para investigadores, esrufiantes, grupos de investigacion, centros, universidades, empresas, etc. busca opciones sinialres en repos github, papers, software y miraposibles planes para implementar»

L3 (2026-11-20, user, verbatim): «explora tambien opciones para aplicar en ingles, dewde que sea compatible para investigadores, estufisntes, empresas, centros, universidades colombianas. para web scrappong mira si claude ya tiene herramientas similares, mas chrome dev tools»

L4 (2026-11-20, evidence, research pass): no open-source or commercial recommender covers Colombia/LatAm; Minciencias has no API and robots Crawl-delay 10, terms (/node/722) forbid reproduction; EU SEDIA search API keyless; Grants.gov search2 keyless; aggregators expose RSS + WordPress REST; Horizon Europe list V4.2 makes Colombia a funded third country not counting toward minimums; MSCA Global PF excludes Colombians; Wellcome Discovery co-applicant only; TWAS/OWSD list excludes Colombia; IDRC AI4D lead regions exclude LatAm; Georg Forster paused; NIH stopped foreign subawards (NOT-OD-25-104). Scraping stack: WebFetch (static/PDF, no JS, lossy), Playwright MCP headless isolated (JS), attended Claude in Chrome for bot-protected sites; Puppeteer and Browserbase MCP archived. Morfeo constraints: zero Python deps, no outbound HTTP in Python, dashboard hands prompts to the embedded terminal, banco-lia unused so far, init stores only title/flujo/lang.

L5 (2026-11-20, decisions by the parent, assumptions): workspace-level folder `convocatorias/` (discovery precedes runs; upgrade copies only kit paths, so it is safe); no new `.mcp.json` server by default (Claude Code's built-in WebSearch/WebFetch need no key; Exa/Tavily and Playwright stay optional and documented), so the user's Exa/Tavily question does not block; adding the tab to the base flow changes the pinned BASE_TABS lists on purpose (the user asked for both flows). §12 committed as 575fbf5 on `docs/sgr-guia-etica`.

L6 (2026-11-20, close): T1 and T2 by parallel writers within their surfaces; T3 inline. Parent fix after T1: NIH and Georg Forster rules forced `lider`, wrong for NIH calls that exclude foreign entities; rules now accept `rol: null` (keep the agent role, add the notice), test RED→GREEN. AGENTS.md trimmed back to 24,000 chars; README 113 assets and 15 subagents; Pi README 14 agents and 12 prompts. Seam on a scratch workspace: `perfil` → `check` 0 → `datos` shows a Horizon Europe call corrected from `lider` to `socio` with its notice, and `load_opportunities` serves the same view. Full Python suite 1560, only the 13 environment failures (test_figure_pipeline 11, test_plantilla_main 2); JS 276/276; kit and three ports in step. `check-agent-models.py` fails only on the local Pi profile (same environment failure as test_the_real_repository_reconciles). Open: RSS feed paths and the SGR plan URL in fuentes.json point to site pages, to be confirmed by the agent's first run; the agent has not yet been run against the live web.
