---
name: estilo-natural-en
description: Polish English academic and scientific prose for research proposals written in English (runs with LANG=en). Fixes 36 mechanical patterns that slow a reviewer down (stock phrases, inflated significance, overused academic vocabulary such as delve or tapestry, trailing participle clauses, reflexive triads, negative parallelisms, hedging stacks, Spanish-shaped phrasing), varies sentence cadence, and keeps strict factual fidelity (figures, dates, BibTeX keys, LaTeX commands, paragraph structure, no em dashes or double hyphens). English counterpart of estilo-natural-es.
---

# Natural Academic English for Research Proposals

## 1. Nature and purpose

This skill raises the readability, argumentative flow and sentence cadence of the English prose of a research proposal. It is the English counterpart of `estilo-natural-es`, and it applies when the run's writing language is English (`LANG=en`, `python3 scripts/language.py run <RUN_ROOT>`). Its goal is to remove the mechanical, predictable and uniform texture that tires a reviewer and leave the sober, precise prose of a senior investigator. The measure is readability: a reviewer with little time understands the argument on the first reading.

The register is the one international funders and review panels expect (research councils, foundations, multilateral and bilateral calls, industry partners): formal, concrete and economical. The measurable part of the catalog lives in `scripts/estilo_en.py`, which applies it deterministically and writes the same report as `scripts/estilo_es.py`. Neither the skill nor the script estimates who wrote a text; they measure how it reads, and they never change an AI-use declaration the call or the institution requires.

### Red lines (what this skill never does)

1. **No encoding tricks:** no invisible characters, zero-width spaces, homoglyphs or Unicode manipulation. No deliberate typos, no fake imperfections.
2. **No register degradation:** naturalness is not informality. No slang, no contractions in the narrative (*it's*, *don't*), no first-person chattiness, no false-confidence openers (*honestly*, *let's be clear*). The register stays formal and rigorous.
3. **Factual fidelity is sacred:** the skill changes *style* and *sentence structure* only. Numbers, percentages, dates, budgets, cohorts (`EST-MZ-xxx`, `EST-PE-xxx`), TRL levels (6 or 7), equations, formulas and scientific claims stay byte-identical.
4. **LaTeX and citation safety:** every command, environment, label (`\label`, `\ref`, `\cref`), included file (`\input`) and natbib APA author-year key (`\citep{...}`, `\citet{...}`) stays intact. It never invents a citation or alters a key.
5. **No em dashes and no double hyphens:** the em dash (` — ` or `word—word`) and the double hyphen (`--`) are banned in narrative prose. Asides use commas, semicolons, colons or parentheses. This is the same rule as the Spanish document (AGENTS.md, document invariants) and `scripts/check_run.py` enforces it.
6. **Structure intact:** the number of paragraphs and the argumentative progression the guide requires stay (the six paragraphs of §2, the 1:1 mapping of three subproblems to three specific objectives). Required lists (objectives, budget items, products) are never dissolved into prose.

---

## 2. Scope

### Applies to
- All English narrative prose of the proposal: sections 2 to 12, 14, 15, 17, 18 and the front matter (Abstract, Executive summary, Keywords).
- The style audit `grant-flow-auditor` runs before each review gate (`revisor`) on an English run.
- English documentation, reports and notes the primary assistant writes for an English run.

### Does not apply to
- BibTeX entries (`refs.bib`), LaTeX tables, the budget table (§13), the Gantt code (§14) or TikZ code.
- Structured lists the guide requires as bullets or numbered items (specific objectives, budget items, products of Table 4).
- Spanish text: Spanish prose follows `estilo-natural-es`. The guide `guiaProyectosIA_Agente.md` is written in Spanish; read it for the instructions and write the section in English.

---

## 3. Catalog of 36 mechanical patterns

### A. Content and rhetoric
1. **Inflated significance:** *plays a pivotal/crucial/key role*, *stands as a testament to*, *marks a turning point*, *a paradigm shift*, *lays the groundwork*, *paves the way*, *at the heart of*, *at the forefront of*.
   *Fix:* a direct verb (*reduces*, *measures*, *enables*, *replaces*) or the copula (*is*, *are*).
2. **Vague attribution:** *experts agree*, *recent studies show*, *the literature suggests*, *it is widely accepted* with no citation in the sentence.
   *Fix:* cite the source (`\citep{...}`) or state the technical fact directly.
3. **Trailing participle clauses:** sentences that end in a decorative *-ing* clause (*, highlighting its relevance*, *, underscoring the commitment*, *, ensuring a lasting impact*, *, thereby fostering...*).
   *Fix:* a coordinate or subordinate clause with a finite verb, or end the sentence on the main claim.
4. **Promotional language:** *groundbreaking*, *revolutionary*, *cutting-edge*, *unprecedented*, *transformative*, *world-class*, *remarkable*, *profound impact*.
   *Fix:* state the technical scope with quantitative or methodological evidence.
5. **Generic optimistic endings:** *opening a promising horizon for the region*, *a step in the right direction*.
   *Fix:* end on the tangible deliverable, the verifiable milestone or the TRL reached.
6. **Formulaic transition paragraphs:** *despite these challenges, the opportunities remain promising*.
   *Fix:* name the operational risk or methodological limitation and how the project handles it.

### B. Vocabulary and grammar
7. **Overused academic vocabulary:** *delve*, *tapestry*, *testament*, *beacon*, *realm*, *interplay*, *multifaceted*, *meticulous*, *seamless*, *holistic*, *pivotal*, *paramount*, *nuanced*, *myriad*, *plethora*, *synergy*, *underscore*, *bolster*, *foster*, *harness*, *leverage*, *showcase*, *unlock the potential*, *a wide array of*, *ultimately*, *crucial*.
   *Fix:* the 70/30 rule (70% stable technical terms, 30% variation in precise verbs and descriptive adjectives). A word stays only when it says something measurable.
8. **Avoided copula:** *serves as*, *stands as*, *functions as*, *boasts* where *is* or *has* says the same.
   *Fix:* the copula or the plain verb of possession.
9. **Negative parallelisms and tail negations:** *not only X but also Y*, *it is not just a model, it is an architecture*, and clipped tails (*no guesswork*, *without friction*).
   *Fix:* state directly what the system does.
10. **Reflexive triads:** three adjectives, nouns or benefits in a row by reflex (*innovation, rigor, and relevance*; *captures, processes, and evaluates*).
    *Fix:* coordinate the two that matter, or rank the ideas in clauses.
11. **Elegant variation:** rotating synonyms for one technical concept inside a paragraph (*the model... the algorithm... the network... the predictive tool*).
    *Fix:* keep one term. Protected terms (problem and objective tree vocabulary, tree nodes, the title, TDR chapter titles, institutions) repeat as they are and do not count as redundancy.
12. **False ranges:** *ranging from signal capture to territorial inclusion*, where the two ends do not sit on one measurable scale.
    *Fix:* list the dimensions on separate planes.
13. **Agentless passives:** *processing is performed*, *data collection is carried out* when the reader needs to know which component or actor acts.
    *Fix:* name the agent (*the extraction module processes...*, *the field team collects...*). A passive that keeps the focus on the object stays.
14. **Spanish-shaped phrasing (false friends of Colombian authors):**
    - *investigation group / line of investigation* → *research group / research line*.
    - *formation of researchers*, *capacitation* → *training*.
    - *realize / make a study* → *conduct a study*.
    - *in base to* → *based on*.
    - *assist to a meeting* → *attend a meeting*.
    - *actual situation* (for *situación actual*) → *current situation*.
    - *the project contemplates / pretends to* → *the project includes / aims to*.
    - *apply to a call* → *apply for funding* or *submit to a call*.
15. **Ceremonial openers:** *In today's world*, *In the digital age*, *Nowadays*, *It is worth noting that*, *It is important to note that*, *It is clear that*.
    *Fix:* drop the preamble and open with the subject or the claim.
16. **Hedging stacks:** *could potentially*, *might possibly*, *it may perhaps be argued that*.
    *Fix:* one calibrated modal, the one the evidence supports.

### C. Style, punctuation and typography
17. **Em dashes and double hyphens:** banned in narrative prose (red line 5). Use commas, semicolons, colons or parentheses.
18. **Mechanical bold:** do not bold whole phrases or obvious terms inside running paragraphs.
19. **Inline-header lists instead of prose:** turn `- **Dimension:** explanation` schemes into cohesive paragraphs, except where the call or the guide requires a table or a list.
20. **Title case drift:** pick sentence case for section titles (`\section{Rationale and relevance}`) and keep it across the document.
21. **Emojis and decorations:** incompatible with a scientific document.
22. **Quotation marks and spelling:** one spelling variant per document (US or UK, as the call expects; US by default) and one quotation style.

### D. Communication, metadiscourse and structure
23. **Chatbot residue:** *Certainly!*, *Of course*, *I hope this section meets the requirements*, *Here is...*, *Let's dive in*. Remove all of it.
24. **Speculative filler:** paragraphs about missing information instead of the data at hand.
25. **Servile tone:** flattery of the call or the reviewer.
26. **Wordy periphrasis:** *in order to* → *to*; *due to the fact that* → *because*; *has the ability to* → *can*; *for the purpose of* → *to*; *a large number of* → *many* or the number.
27. **Buzzword compounds:** saturating with *real-time*, *data-driven*, *end-to-end*, *multidisciplinary*, *state-of-the-art* when they add nothing measurable.
28. **Borrowed authority:** *The real question is*, *What truly matters*, *At its core*.
29. **Signposting (throat-clearing):** *In this section we will describe...*, *This section presents...*. Start with the content.
30. **Fragmented headings:** a title followed by a one-line sentence that repeats it before the content starts.
31. **Changelog writing:** *this section was revised to...*. The proposal reads as a final document.
32. **Melodramatic staccato:** four or five clipped sentences in a row to fake drama.
33. **Pretentious aphorisms:** *Data is the new oil*, *Technology is the mirror of society*.
34. **False-confidence openers:** *To be honest*, *Truth be told*, *The truth is that*.
35. **Mixed varieties:** mixing US and UK spelling or idiom inside one document.
36. **Opening connector chains:** *Moreover... Furthermore... Additionally...* opening consecutive sentences. A connector comes after naming the logical relation (cause, contrast, consequence, precision, example); swapping one connector for another fixes nothing, and often the sentence's own subject can carry the link.

---

## 4. Register for English research proposals

1. **Institutional vocabulary:** *research and development (R&D) project*, *technology transfer*, *social appropriation of knowledge*, *research groups recognized by MinCiencias*, *in-kind and cash co-funding*, *training of researchers*, *territorial articulation*, *research seedbed (semillero)*, *young researchers*. Institution names stay in their official form (Universidad Nacional de Colombia, Sede Manizales; Universidad Tecnológica de Pereira); an English gloss may follow once in parentheses.
2. **Connectors:** prefer the relation to the formula. *However*, *therefore*, *in turn*, *by contrast*, *as a result*, *specifically*, *that is* are fine once; never three consecutive openers.
3. **Voice:** third person about the project (*the project develops*, *the team will validate*), with the first person plural only where the call asks for it. A passive is fine when the object matters more than the actor (*a sample of 120 students was selected*).

---

## 5. Cadence and sentence variety

Expert prose varies sentence length and structure. A text of medium sentences of 20 to 25 words, all built the same way, reads flat and tires the reviewer.

This is the framework's single length rule, the same as in `estilo-natural-es`, `depuracion-redundancias-en` and `grant-flow-auditor`:
1. **Alternate sentence length:** short, firm sentences (8 to 15 words) that fix claims, with compound sentences (25 to 40 words) that develop causal or technical reasoning. Split any sentence over 45 words, the signal `scripts/estilo_en.py` measures, and avoid strings of clipped fragments.
2. **Vary openings:** never three consecutive sentences with the bare [Subject + Verb] scheme. Open with a prepositional phrase (*On both campuses,...*), a condition or cause (*Because edge latency is a hard constraint,...*), a figure (*Forty-two percent of the students...*), or a contrast (*By contrast, convergence requires...*).
3. **Punctuation:** semicolons join closely related clauses; colons introduce a direct explanation or consequence; parentheses hold methodological details, acronyms and numeric ranges.

---

## 6. Audit and polish procedure

Before revising a section in `redaccion/sections/`, run `python3 scripts/estilo_en.py audit <RUN_ROOT> --section N` and copy the original file to a temporary folder:

```
Step 1: Map ──> Step 2: Prune ──> Step 3: Holistic rewrite (cadence) ──> Step 4: Check invariants
```

1. **Map:** start from the report's `hallazgos` (section, paragraph, sentence, category and guidance) and add the patterns a script cannot see. Entries under `exentos` stay untouched.
2. **Prune:** remove empty preambles, redundant connectors and inflated adjectives.
3. **Holistic rewrite in one pass:** reshape the prose with varied sentence length and precise verbs, without changing technical terms or meaning.
4. **Check invariants:**
   - [ ] Are every figure, date, percentage and budget exactly the same?
   - [ ] Are every BibTeX key (`\citep`, `\citet`) and LaTeX command intact?
   - [ ] Are there no double hyphens (`--`) or em dashes left in the prose?
   - [ ] Is the number of paragraphs the section requires unchanged?
   - [ ] Is the register formal and consistent in spelling?

   The first four questions are answered by `python3 scripts/estilo_en.py verify <before> <after>`, which exits with an error when a figure, a date, an amount in `\$`, a citation key, a `\label` or `\ref`, a cohort, a TRL level or the paragraph count changed. Without its output there is no check.

---

## 7. Output contract (audit report)

Edit the corresponding `.tex` file **in place**. The agent's answer reports:

1. **Patterns addressed:** the findings handled, with their category.
2. **Key transformations:**
   | Pattern | Original | Rewritten |
   | :--- | :--- | :--- |
   | *[e.g. trailing participle]* | *"...improving the network's performance."* | *"...which raises the model's hit rate."* |
3. **Invariants:** the output of `estilo_en.py verify` and the confirmation that no `--` or em dash remains in the prose.
4. **Deterministic report:** `indice`, `veredicto`, `puntaje_estilo` and `puntaje_flujo` before and after, copied from `artefactos/estilo/reporte.json`. No agent assigns itself a score: the report is the only measure, its thresholds are provisional, and a low score guides the revision without failing it.
