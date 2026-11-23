---
name: depuracion-redundancias-en
description: Audit and remove conceptual, lexical and structural redundancy inside one section of a research proposal written in English (runs with LANG=en), applying the estilo-natural-en skill to every passage it condenses. English counterpart of depuracion-redundancias-es.
---

# Redundancy Removal and Natural Style in English

## Purpose and scope

This skill gives a systematic method to audit, prune and condense the English prose of an academic proposal. It is the English counterpart of `depuracion-redundancias-es` and applies when the run's writing language is English (`LANG=en`). Its goal is to remove the needless repetition of concepts, justifications and turns of phrase inside one section, and to apply in the same pass the humanization and cadence method of `estilo-natural-en`.

A proposal full of redundancy tires the reviewer, scatters the central argument and reads as filler. Each paragraph and each sentence must do a distinct, progressive argumentative job, with maximum conceptual density and no loss of clarity or rigor.

## Red lines

1. **Strict content fidelity:** pruning removes repeated form, never facts, figures, budget amounts, deadlines, citation keys (`\citep`, `\citet`) or technical commitments.
2. **Formal register:** naturalness is not informality. The prose keeps the formal, rigorous tone of a high-level scientific proposal.
3. **Zero invention:** a condensed passage is never padded with new assumptions or data. What the inputs do not state is not invented.
4. **Always with `estilo-natural-en`:** every passage touched to remove redundancy goes through the cadence, sentence-length and connector criteria of that skill in the same pass.

---

## Types of redundancy to find and fix

### 1. Conceptual and premise redundancy
* **Defect:** the same justification, scope or premise repeated in several paragraphs of one section with slightly different wording (stating three times that the system does not diagnose, or that it was built with a given partner).
* **Fix:** state it once, fully, where it belongs methodologically or normatively; later mentions point back to it briefly, or disappear when they add no new evidence or decision.

### 2. Lexical redundancy and connector tics
* **Defect:** formulaic connectors (*moreover*, *furthermore*, *additionally*, *in this regard*, *it is worth noting that*) opening consecutive sentences or crowding one paragraph.
* **Fix:** drop the expendable connector and let the meaning carry the link through order or punctuation. When a transition is needed, rebuild it from the logical relation between the two sentences, never by swapping one connector for another.

### 3. Preamble and metadiscourse (throat-clearing)
* **Defect:** empty openers that announce instead of stating (*The following paragraphs describe in detail the aspects related to...*, *It is essential to point out that this activity requires...*).
* **Fix:** remove the preamble and open with the claim, the subject or the technical action.

### 4. Structural or mirror redundancy
* **Defect:** prose that repeats what an adjacent table or list already says, or a budget item justified at three levels of detail with no new operational context.
* **Fix:** the prose explains the articulation logic, the decision criterion and the systemic effect; the specific data stay in their table or list.

---

## Integrated workflow (audit and humanization)

```
Step 1: Density map ──> Step 2: Prune and merge ──> Step 3: Humanize (estilo-natural-en) ──> Step 4: Check
```

### Step 1: Map the density of ideas
1. Run `python3 scripts/estilo_en.py audit <RUN_ROOT> --section N`, read the whole section and name the purpose of each paragraph. The report's `frase_repetida` and `casi_duplicado` categories locate literal repetition; conceptual repetition is your judgement.
2. List the substantive claims.
3. Mark the sentences that repeat an idea already stated in an earlier paragraph of the same section.

### Step 2: Prune and merge
1. When two sentences in different paragraphs say substantially the same thing, keep the better wording in the main paragraph and remove the secondary copy.
2. When a paragraph has two or three sentences circling one concept, merge them into one precise sentence.
3. Remove metadiscourse and mechanical openers.

### Step 3: Apply `estilo-natural-en`
On the pruned text, apply the guidelines of `estilo-natural-en` at once:
1. **Alternate length:** short, direct sentences (8 to 15 words) with compound sentences (25 to 40 words), and split any sentence over 45 words. It is the rule of `estilo-natural-en` and breaks the monotony of uniform 20-word sentences.
2. **De-mechanize openings:** remove formulaic lists (*First... Second...*, *On the one hand... On the other hand...*).
3. **Active, natural syntax:** prefer direct action verbs over stacked nominalizations and agentless passives.
4. **Lexical variety:** technical and protected terms (problem and objective tree vocabulary, tree nodes, the title, TDR chapter titles, institutions) repeat as they are: a synonym would create ambiguity, as `estilo-natural-en` warns. Variation is for general words, above all those the report marks as `sobreuso`, with pronouns or ellipsis when the referent is unambiguous.

### Step 4: Check consistency and close
1. Confirm that no BibTeX key was removed (`\citep{...}`, `\citet{...}`).
2. Check that every amount, deadline, percentage and metric matches the original exactly.
3. Make sure the section keeps an adequate length and reads as agile and persuasive for the reviewer.
4. Run `python3 scripts/estilo_en.py verify <before> <after>`: it exits with an error when a figure, a date, an amount, a citation key, a label, a cohort, a TRL level or the paragraph count changed.

## Outside this skill

Redundancy across sections is measured with `python3 scripts/estilo_en.py audit <RUN_ROOT> --all`. The `revisor-redundancia` agent judges it and `grant-flow-auditor` does the editing. What the summary restates from the body appears under `exentos` and is not pruned.
