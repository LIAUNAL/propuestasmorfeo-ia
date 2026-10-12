---
name: estilo-natural-es
description: Rewrite or polish Spanish proposal prose so it reads as natural, varied, human-authored academic writing instead of formulaic machine output. Use when drafting, editing, proofreading, or auditing the Spanish narrative of the proposal (sections 1-16 and the front-matter) and the goal is prose quality and natural cadence. It preserves facts, figures, citations and technical meaning; it never invents content and never degrades the formal academic register.
---

# Estilo natural en español para prosa de propuesta

## What this skill is (and is not)

This skill improves the *writing quality* of Spanish academic prose. It removes
the mechanical, uniform, template-like texture that makes a section read as
machine output, and replaces it with natural Spanish academic style.

It is deliberately **not** an "AI-detector evasion" tool. It is an editorial
quality pass. Concrete red lines:

- It never fabricates facts, numbers, results, citations, or quotes.
- It never introduces deliberate typos, punctuation errors, or inconsistencies:
  a funding proposal must be typographically clean.
- It never adds artificial vagueness ("más o menos", "algo así") to simulate
  human imperfection. Precision is a requirement of this genre.
- It never injects personal emotion, opinionated asides, or colloquial register
  ("mira", "la verdad es que", "no sé"). The register stays formal and academic.
- Only the *style* changes. The *content* is frozen: same claims, same data,
  same citations, same technical meaning.

Naturalness is a legitimate editorial goal: grant reviewers read dense proposals
under time pressure, and formulaic texture costs them attention. Simulating human
authorship to defeat an AI detector is a different and unacceptable goal.

> Adapted for this framework from the community skill `humanizar-texto-es`
> (`majiayu000/claude-skill-registry`), reduced to its proposal-safe techniques.
> The evasion framing and the techniques that degrade a formal document
> (deliberate typos, manufactured imprecision, emotional insertions, register
> mixing) were removed by design.

## When to use

- Any Spanish narrative prose of the proposal: sections 1-16 and the
  front-matter (Resumen, Resumen ejecutivo, Palabras clave).
- As the polish pass after `redactor` / `investigador` produce or edit a
  section, executed through `grant-flow-auditor`, before the `revisor` gate.
- When a section "reads like AI": uniform sentence length, formulaic openers,
  mechanical enumerations, flat vocabulary.

Do **not** apply it to:

- BibTeX entries, LaTeX tables, the budget table (§13), the Gantt chart (§14),
  or TikZ code.
- Enumerations the guide mandates (objetivos específicos, rubros, productos
  esperados). Those stay as structured lists.
- English text.

## Step 1 — Detect the mechanical texture first

Record what you find in the original, concretely:

- Mechanical enumerations: "En primer lugar... En segundo lugar... En tercer
  lugar...".
- Formulaic openers: "Es importante destacar que", "Cabe mencionar que",
  "Adicionalmente, se observa", "Es fundamental comprender que".
- Uniform sentence rhythm (every sentence 20-25 words).
- Flat, over-neutral vocabulary with no lexical variation.
- Parallel structures and bullet stacks where prose is expected.
- Empty intensifiers: "innovador", "de vanguardia", "revolucionario", "crucial".

## Step 2 — One holistic rewrite

Apply every technique in a single pass. Never do multiple partial passes.

| # | Technique | How to apply it |
|---|---|---|
| 1 | Syntactic reformulation | Vary clause structure: mix simple and compound sentences; move adjuncts to the front or the end. |
| 2 | Burstiness within academic bounds | Alternate short sentences (8-14 words) with long ones (25-35). Keep fragments out of formal sections. |
| 3 | Contained lexical surprise | Prefer the precise, specific, non-formulaic word over the generic one. Never a rare word for its own sake. |
| 4 | Spanish discourse markers (formal) | Vary connectives: *no obstante*, *en cambio*, *de hecho*, *ahora bien*, *así las cosas*, *en la práctica*, *en última instancia*, *por lo demás*. Never their colloquial equivalents. |
| 5 | 70/30 vocabulary rule | Keep terminology stable (70-80 %) so the argument stays coherent; vary the remaining adjectives and action verbs. |
| 6 | Register consistency | Stay formal and academic throughout. No colloquial drift, no jargon for show. |
| 7 | Explicit but sober stance | State positions and value judgments plainly ("este enfoque resulta insuficiente porque..."), without emotion or rhetorical inflation. |
| 8 | Concrete references | Replace generic claims with specific, verifiable statements backed by citations **already present** in the section. |
| 9 | De-mechanize enumerations | Turn "En primer lugar..." chains and parallel bullet stacks into integrated prose, except where the guide mandates a list. |
| 10 | Honest epistemic calibration | Hedge only where the evidence warrants it ("los resultados sugieren", "en este escenario"). Never manufacture vagueness. |
| 11 | Typographic polish | Consistent punctuation, quotation marks, dashes and spacing. **No deliberate errors.** |

## Step 3 — Hard invariants (do not violate)

- **Fidelity:** numbers, percentages, dates, proper nouns, citations, equations
  and results are byte-identical after the rewrite. If a sentence cannot keep a
  number intact, leave that sentence alone.
- **LaTeX safety:** preserve every command, environment, `\label`, `\ref`,
  `\cref`, `\citep{}` / `\citet{}` key, and `\input` as-is.
- **No new sources:** never add a citation that is not already in `refs.bib`
  and already used in the section. Never change a citation key.
- **Structure:** keep headings, section order, and the required lists.
- **Language:** the proposal text stays Spanish.

## Step 4 — Output contract inside this framework

Unlike a standalone text-humanizing tool, this skill does **not** create
`*_humanizado` / `*_analisis` files. Inside this framework:

- The target is one `.tex` file under `redaccion/sections/` (or the
  front-matter).
- The rewrite is applied **in place**, through `grant-flow-auditor`, which owns
  the edit. The skill supplies the method and the checklist.
- The report is returned **in the agent's response**, not as a new file.

Report format (in the response):

1. **Patrones mecánicos detectados** — the concrete items found.
2. **Cambios aplicados** — table: technique | original fragment | rewritten fragment.
3. **Verificación de invariantes** — one line per invariant, with the check performed.
4. **Puntuación de naturalidad y fidelidad (0-100)** — the five criteria below.
   State explicitly that this measures prose quality and fidelity, **not**
   detectability.

| Criterion | Points |
|---|---|
| Sentence-length variation (burstiness) | 25 |
| Spanish discourse-marker variety | 20 |
| Lexical variation (70/30 rule) | 20 |
| Absence of mechanical enumerations | 15 |
| Factual and LaTeX fidelity (no changed data) | 20 |

## Common mistakes

| Mistake | Correction |
|---|---|
| Introducing typos or punctuation inconsistencies | Clean typography; no deliberate errors. |
| Adding colloquial markers ("mira", "no sé") | Formal markers only. |
| Manufacturing hedges or vagueness | Hedge only when the evidence warrants it. |
| Changing a number, date or citation "so it reads better" | Never. Preserve it byte-for-byte. |
| Dissolving a list the guide requires | Only prose enumerations become prose. |
| Rewriting content or adding claims | Style only; meaning is frozen. |
| Producing new output files | Edit in place; report in the response. |
| Applying it to tables, TikZ or BibTeX | Out of scope; leave them untouched. |
