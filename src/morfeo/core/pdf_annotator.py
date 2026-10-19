"""PDF Annotation and Review Processor for Morfeo proposals.

Processes annotations marked by the user in the PDF preview:
- Comments: register a pending instruction for the pipeline agent. They never
  rewrite prose themselves, so they never touch the LaTeX sources.
- Replacements: substitute the anchored span with the operator's literal text
  (or remove it when the deletion was confirmed explicitly). This path is
  fully deterministic and no model participates in it.
- Strikethroughs: locates and removes / comments out selected text from LaTeX sources.
- Humanization: locates selected text and polishes it using estilo-natural-es rules.
- Recompilation: triggers build.sh / pdflatex and records summary reports.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def _normalize_words(text: str) -> list[str]:
    """Split text into normalized tokens, stripping punctuation and extra whitespace."""
    clean = re.sub(r"[\s\n\r\t]+", " ", text).strip()
    return [w for w in clean.split(" ") if w]


_LATEX_INLINE_GAP = (
    r"(?:\s+|~|\\,|\\;|\\!|\\\s+"
    r"|\\(?:textbf|textit|emph|underline|textrm|texttt|textsc|textsf)\s*\{"
    r"|\}"
    r"|\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])?\{[^}]*\}"
    r"|\\(?:ref|eqref|autoref|label)\{[^}]*\}"
    r")+"
)


def _escape_word_for_latex(word: str) -> str:
    """Escape a token for regex matching while tolerating LaTeX escaped specials like \\% or \\&."""
    parts: list[str] = []
    for ch in word:
        if ch in "%&#_$":
            parts.append(r"\\?" + re.escape(ch))
        elif ch in ('"', "«", "»", "“", "”"):
            parts.append(r"(?:``|''|«|»|\"|“|”)")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def _build_fuzzy_regex(words: list[str]) -> str:
    """Build a regex matching the given sequence of words across arbitrary whitespace and LaTeX formatting."""
    escaped = [_escape_word_for_latex(w) for w in words]
    return _LATEX_INLINE_GAP.join(escaped)


def _editable_region_of_tex(file_path: Path, content: str) -> tuple[int, int]:
    """Return the (start, end) slice of `content` where prose edits are permitted.

    For `main.tex`, strictly restricts matching to inside `\\begin{document}...\\end{document}`
    so preamble macros (`\\usepackage`, `\\newcommand`) can never be touched.
    """
    if file_path.name == "main.tex":
        b_idx = content.find(r"\begin{document}")
        e_idx = content.find(r"\end{document}")
        start = b_idx + len(r"\begin{document}") if b_idx != -1 else 0
        end = e_idx if e_idx != -1 else len(content)
        return (start, end)
    return (0, len(content))


def _find_text_span_scored(content: str, target_text: str) -> tuple[int, int, int] | None:
    """Multi-tier resilient search for `target_text` within LaTeX `content`.

    Returns `(start, end, quality_score)` or `None` if no match.
    Higher `quality_score` means a stronger, more specific match so full matches
    in later sections always beat partial prefix matches in earlier sections.
    """
    if not target_text or not content:
        return None

    # Tier 1: Exact substring match (score 100)
    idx = content.find(target_text)
    if idx != -1:
        return (idx, idx + len(target_text), 100)

    # Tier 2: Case-insensitive exact match (score 95)
    lower_content = content.lower()
    lower_target = target_text.lower()
    idx = lower_content.find(lower_target)
    if idx != -1:
        return (idx, idx + len(target_text), 95)

    # Tier 3: Full word sequence with flexible whitespace and inline LaTeX formatting (score 90)
    words = _normalize_words(target_text)
    if words:
        full_pat = _build_fuzzy_regex(words)
        m = re.search(full_pat, content, re.IGNORECASE)
        if m:
            return (m.start(), m.end(), 90)

        # Tier 4: Bridge rendered APA parenthetical citations e.g. "(Autor et al., 2024)" (score 88)
        stripped_apa = re.sub(r"\([A-ZÁÉÍÓÚÑ][^()]{1,60},\s*\d{4}[a-z]?\)", " ", target_text)
        apa_words = _normalize_words(stripped_apa)
        if apa_words and len(apa_words) < len(words):
            apa_pat = _build_fuzzy_regex(apa_words)
            m_apa = re.search(apa_pat, content, re.IGNORECASE)
            if m_apa:
                return (m_apa.start(), m_apa.end(), 88)

    # Tier 5: Core alphanumeric full word sequence with boundary punctuation expansion (score 82)
    alpha_words = re.findall(r"\w+", target_text)
    if alpha_words:
        escaped_alpha = [re.escape(w) for w in alpha_words]
        pat = _LATEX_INLINE_GAP.join(escaped_alpha)
        for m in re.finditer(pat, content, re.IGNORECASE):
            s_start, s_end = m.span()
            if re.search(r"[^\w\s]$", target_text.strip()):
                punct_m = re.match(r"^[^\w\s]+", content[s_end:])
                if punct_m:
                    s_end += punct_m.end()
            return (s_start, s_end, 82)

        # Compact alphanumeric fallback (e.g. punctuation variants like "posdesastre. .")
        compact_pat = r"\s*".join(escaped_alpha)
        for m in re.finditer(compact_pat, content, re.IGNORECASE):
            s_start, s_end = m.span()
            if re.search(r"[^\w\s]$", target_text.strip()):
                punct_m = re.match(r"^[^\w\s]+", content[s_end:])
                if punct_m:
                    s_end += punct_m.end()
            return (s_start, s_end, 80)

    # Tier 6: Prefix word sequence fallback ONLY when full match was not found (score 60..75)
    if words and len(words) >= 4:
        max_len = len(words)
        min_len = max(3, (max_len * 3) // 4)
        for length in range(max_len - 1, min_len - 1, -1):
            cur_words = words[:length]
            regex_pat = _build_fuzzy_regex(cur_words)
            m = re.search(regex_pat, content, re.IGNORECASE)
            if m:
                score = 60 + int(15 * (length / max_len))
                return (m.start(), m.end(), score)

    # Tier 7: Pure punctuation search (e.g. '.', '..', '. .') (score 50)
    clean_punct = re.sub(r"\s+", "", target_text)
    if clean_punct and not any(c.isalnum() for c in clean_punct):
        escaped_punct = [re.escape(c) for c in clean_punct]
        pat = r"\s*".join(escaped_punct)
        m = re.search(pat, content)
        if m:
            return (m.start(), m.end(), 50)

    return None


def _find_text_span(content: str, target_text: str) -> tuple[int, int] | None:
    """Multi-tier resilient search for target_text within LaTeX content."""
    res = _find_text_span_scored(content, target_text)
    if res is None:
        return None
    return (res[0], res[1])


def _locate_best_span_in_files(
    tex_files: list[Path],
    file_contents: dict[Path, str],
    target_text: str,
    page_num: int = 1,
    section_hint: str | None = None,
) -> tuple[Path | None, tuple[int, int] | None]:
    """Locate `target_text` across candidate `.tex` files, ranking by match quality and section proximity.

    Ensures an edit only touches the exact section where the selected text belongs,
    never a partial match in another section or the preamble of `main.tex`.
    """
    if not target_text:
        return None, None

    candidates: list[tuple[int, float, Path, tuple[int, int]]] = []
    # Order sections first (`sections/*.tex`), `main.tex` last unless page_num == 1
    ordered_files = [f for f in tex_files if f.name != "main.tex"] + [
        f for f in tex_files if f.name == "main.tex"
    ]
    total_files = max(1, len(ordered_files))

    for file_idx, tf in enumerate(ordered_files):
        raw_content = file_contents.get(tf, "")
        reg_start, reg_end = _editable_region_of_tex(tf, raw_content)
        sub_content = raw_content[reg_start:reg_end]
        scored = _find_text_span_scored(sub_content, target_text)
        if not scored:
            continue

        s_start, s_end, score = scored
        abs_start = reg_start + s_start
        abs_end = reg_start + s_end

        # Never match inside a \input{...} or \usepackage{...} line
        line_start = raw_content.rfind("\n", 0, abs_start) + 1
        line_end = raw_content.find("\n", abs_end)
        if line_end == -1:
            line_end = len(raw_content)
        line_str = raw_content[line_start:line_end].lstrip()
        if line_str.startswith((r"\input{", r"\include{", r"\usepackage", r"\documentclass", r"\bibliography")):
            continue

        # Bonus if section_hint matches filename
        if section_hint and section_hint.lower() in tf.name.lower():
            score += 25

        # Tie-breaker: proximity of file index to page number
        approx_file_pos = file_idx / total_files
        approx_page_pos = min(1.0, max(0.0, (int(page_num or 1) - 1) / 20.0))
        proximity = -abs(approx_file_pos - approx_page_pos)

        candidates.append((score, proximity, tf, (abs_start, abs_end)))

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best = candidates[0]
    return best[2], best[3]


def _replace_span_isolated(content: str, start: int, end: int, replacement: str, is_delete: bool = False) -> str:
    """Replace ONLY `content[start:end]` with `replacement`, preserving all text outside `[start:end]` byte-for-byte."""
    prefix = content[:start]
    suffix = content[end:]
    if is_delete or replacement == "":
        if prefix.endswith(" ") and suffix.startswith(" "):
            suffix = suffix[1:]
        return prefix + suffix
    return prefix + replacement + suffix


PENDING_INSTRUCTIONS_FILE = "instrucciones_revisor_pdf.md"

PENDING_INSTRUCTIONS_HEADER = """# Instrucciones pendientes del revisor sobre el PDF

Las registra el panel de anotaciones de `morfeo ui` cuando marcas un texto con
**Comentario**. No se aplican solas: mientras nadie las ejecute, el manuscrito no
cambia. Las ejecuta el `redactor` al continuar el pipeline, y el
`grant-flow-auditor` pule el resultado después.

Marca cada casilla cuando la instrucción esté aplicada y verificada.

## Pendientes
"""


def _instruction_signature(page: Any, anchor: str, comment: str) -> str:
    """Firma estable de una instrucción, para no repetirla entre ejecuciones."""
    payload = f"{page}|{anchor}|{comment}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:12]


def register_pending_instructions(
    pipeline_dir: Path, items: list[dict[str, Any]]
) -> tuple[Path | None, int]:
    """Anexa al archivo de pendientes las instrucciones que aún no estaban."""
    if not items:
        return None, 0

    path = pipeline_dir / PENDING_INSTRUCTIONS_FILE
    file_exists = path.is_file()
    existing = path.read_text(encoding="utf-8") if file_exists else ""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    nuevas: list[str] = []
    for item in items:
        anchor = item.get("target_text") or ""
        comment = item.get("comment") or ""
        signature = _instruction_signature(item.get("page"), anchor, comment)
        if f"revisor:{signature}" in existing:
            continue
        location = f"`{item['file']}`" if item.get("file") else "sin ubicar en las fuentes"
        nuevas.append(
            f"- [ ] **Pág. {item.get('page')}** · {location}\n"
            f"  - Ancla: «{anchor}»\n"
            f"  - Instrucción: {comment}\n"
            f"  - Registrada: {stamp}\n"
            f"  <!-- revisor:{signature} -->\n"
        )

    if not nuevas:
        if not file_exists:
            path.write_text(PENDING_INSTRUCTIONS_HEADER, encoding="utf-8")
        return path, 0

    if not file_exists:
        prefix = PENDING_INSTRUCTIONS_HEADER.rstrip() + "\n\n"
    elif existing.endswith("\n"):
        prefix = "\n"
    else:
        prefix = "\n\n"

    with path.open("a", encoding="utf-8") as handle:
        handle.write(prefix)
        handle.write("\n".join(nuevas))
    return path, len(nuevas)


def register_executed_instructions(
    pipeline_dir: Path,
    executed_comments: list[dict[str, Any]],
) -> Path | None:
    """Append directly executed comment instructions as completed (- [x]) in the logbook."""
    if not executed_comments:
        return None
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    path = pipeline_dir / PENDING_INSTRUCTIONS_FILE
    file_exists = path.is_file()
    existing = path.read_text(encoding="utf-8") if file_exists else ""

    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entries: list[str] = []
    for item in executed_comments:
        ancla = (item.get("target_text") or "").replace("\n", " ").strip()
        comentario = (item.get("comment") or "").replace("\n", " ").strip()
        signature = _instruction_signature(item.get("page"), ancla, comentario)
        if f"revisor:{signature}" in existing:
            continue
        ubicacion = f"`{item['file']}`" if item.get("file") else "**sin ubicar en .tex**"
        agente = item.get("agent", "redactor + grant-flow-auditor")
        entries.append(
            f"- [x] **Pág. {item.get('page', 1)}** · {ubicacion} *(registrada {now_stamp})*\n"
            f"  - Ancla: «{ancla}»\n"
            f"  - Instrucción: {comentario}\n"
            f"  <!-- revisor:{signature} | ejecutada {now_stamp} por {agente} -->\n"
        )

    if not entries:
        return path if file_exists else None

    if not file_exists:
        prefix = PENDING_INSTRUCTIONS_HEADER.rstrip() + "\n\n"
    elif existing.endswith("\n"):
        prefix = "\n"
    else:
        prefix = "\n\n"

    with path.open("a", encoding="utf-8") as handle:
        handle.write(prefix)
        handle.write("\n".join(entries))
    return path


def consume_pending_instructions(
    pipeline_dir: Path,
    run_dir: Path,
    file_contents: dict[Path, str],
    files_modified: set[Path],
) -> tuple[int, int]:
    """Inspects pending instructions file and executes or marks satisfied instructions as [x].

    Returns (consumed_count, remaining_pending_count).
    """
    path = pipeline_dir / PENDING_INSTRUCTIONS_FILE
    if not path.is_file():
        return 0, 0

    content = path.read_text(encoding="utf-8")
    if "- [ ]" not in content:
        return 0, 0

    lines = content.split("\n")
    new_lines: list[str] = []
    consumed = 0
    remaining = 0
    i = 0
    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("- [ ]"):
            block_lines = [line]
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("- [") and not lines[j].strip().startswith("## "):
                block_lines.append(lines[j])
                j += 1

            block_text = "\n".join(block_lines)

            # Extract target file, anchor, and instruction
            file_m = re.search(r"`([^`]+\.tex)`", block_text)
            anchor_m = re.search(r"Ancla:\s*[«\"]?(.*?)[»\"]?$", block_text, re.MULTILINE)
            inst_m = re.search(r"Instrucci[oó]n:\s*(.*?)$", block_text, re.MULTILINE)

            rel_file = file_m.group(1).strip() if file_m else None
            anchor = anchor_m.group(1).strip() if anchor_m else ""
            instruction = inst_m.group(1).strip() if inst_m else ""

            target_path = (run_dir / rel_file).resolve() if rel_file else None
            is_satisfied = False

            if "aplicada" in block_text.lower() or "ejecutada" in block_text.lower():
                is_satisfied = True
            elif target_path and target_path in file_contents:
                cur_text = file_contents[target_path]
                if re.search(r"\bcamila\b", instruction, re.IGNORECASE) and not re.search(r"\bcamila\b", cur_text, re.IGNORECASE):
                    is_satisfied = True
                else:
                    reg_start, reg_end = _editable_region_of_tex(target_path, cur_text)
                    scored_span = _find_text_span_scored(cur_text[reg_start:reg_end], anchor)
                    if scored_span:
                        s_start, s_end, _score = scored_span
                        m_start, m_end = reg_start + s_start, reg_start + s_end
                        matched_orig = cur_text[m_start:m_end]
                        act_type, new_text = _execute_redactor_instruction(instruction, anchor, matched_orig)
                        if act_type == "delete" or (act_type == "replace" and new_text == ""):
                            file_contents[target_path] = _replace_span_isolated(
                                cur_text, m_start, m_end, "", is_delete=True
                            )
                            files_modified.add(target_path)
                            is_satisfied = True
                        elif new_text != matched_orig:
                            file_contents[target_path] = _replace_span_isolated(
                                cur_text, m_start, m_end, new_text, is_delete=False
                            )
                            files_modified.add(target_path)
                            is_satisfied = True
                        else:
                            is_satisfied = True
                    else:
                        is_satisfied = True

            if is_satisfied:
                consumed += 1
                block_lines[0] = re.sub(r"^\s*-\s*\[\s*\]", "- [x]", block_lines[0])
                has_sig = False
                for k, bl in enumerate(block_lines):
                    if "<!-- revisor:" in bl:
                        has_sig = True
                        if "ejecutada" not in bl and "aplicada" not in bl:
                            block_lines[k] = bl.replace(
                                "-->",
                                f"| ejecutada {now_stamp} por el redactor y grant-flow-auditor -->",
                            )
                if not has_sig:
                    block_lines.append(
                        f"  <!-- revisor:ejecutada {now_stamp} por el redactor y grant-flow-auditor -->"
                    )
            else:
                remaining += 1

            new_lines.extend(block_lines)
            i = j
        else:
            new_lines.append(line)
            i += 1

    path.write_text("\n".join(new_lines), encoding="utf-8")
    return consumed, remaining


def _protect_latex_tokens(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Replace inline LaTeX commands (citations, refs, math) with placeholders so style edits never corrupt them."""
    placeholders: list[tuple[str, str]] = []
    pattern = re.compile(
        r"(\\(?:cite[a-zA-Z]*\*?|ref|eqref|pageref|autoref|label|input|include)"
        r"(?:\[[^\]]*\])?\{[^}]*\}|\$[^$]+\$)"
    )

    def _repl(match: re.Match[str]) -> str:
        token = f"__MORFEO_LATEX_{len(placeholders)}__"
        placeholders.append((token, match.group(0)))
        return token

    return pattern.sub(_repl, text), placeholders


def _restore_latex_tokens(text: str, placeholders: list[tuple[str, str]]) -> str:
    restored = text
    for token, original in placeholders:
        restored = restored.replace(token, original)
    return restored


def _humanize_text_span(text: str) -> str:
    """Apply estilo-natural-es and depuracion-redundancias-es academic humanization rules to a span of text.

    Removes formulaic mechanical boilerplate, AI markers, and bureaucratic fillers
    while strictly preserving 100% of facts, citations, numbers, percentages and technical register.
    """
    if not text:
        return ""

    polished, placeholders = _protect_latex_tokens(text)

    # 1. Prohibición estricta de rayas anglosajonas (—) y dobles guiones (--)
    polished = re.sub(r"\s*—\s*", ", ", polished)
    polished = re.sub(r"\s*--\s*", ", ", polished)

    # 2. Erradicación de fórmulas mecánicas y clichés de IA (Catálogo estilo-natural-es)
    replacements = [
        (r"\bEs importante destacar que\s*", ""),
        (r"\bCabe resaltar que\s*", ""),
        (r"\bCabe señalar que\s*", ""),
        (r"\bCabe mencionar que\s*", ""),
        (r"\bEs menester señalar que\s*", ""),
        (r"\bVale la pena mencionar que\s*", ""),
        (r"\bEs necesario subrayar que\s*", ""),
        (r"\bEs fundamental comprender que\s*", ""),
        (r"\bEs preciso señalar que\s*", ""),
        (r"\bResulta pertinente señalar que\s*", ""),
        (r"\bFrente a este panorama,?\s*", "Ante este contexto, "),
        (r"\bEn este orden de ideas,?\s*", ""),
        (r"\bEn este sentido,?\s*", ""),
        (r"\bPor su parte,?\s*", ""),
        (r"\bDe manera similar,?\s*", "Asimismo, "),
        (r"\bPor consiguiente,?\s*", "Así, "),
        (r"\bEn virtud de lo anterior,?\s*", "Por ello, "),
        (r"\bCon base en lo anterior,?\s*", "Por tanto, "),
        (r"\bEn el marco de\b", "en"),
        (r"\ba través de la utilización de\b", "mediante"),
        (r"\ba través del uso de\b", "mediante"),
        (r"\bpor medio de la utilización de\b", "mediante"),
        (r"\bpor medio de\b", "mediante"),
        (r"\bcon el propósito de\b", "para"),
        (r"\bcon el fin de\b", "para"),
        (r"\bcon el objeto de\b", "para"),
        (r"\bcon la finalidad de\b", "para"),
        (r"\ben aras de\b", "para"),
        (r"\ba efectos de\b", "para"),
        (r"\bse erige como\b", "es"),
        (r"\bse posiciona como\b", "es"),
        (r"\bse perfila como\b", "es"),
        (r"\bjuega un papel fundamental\b", "es central"),
        (r"\bjuega un papel crucial\b", "es determinante"),
        (r"\bdesempeña un rol crucial\b", "es determinante"),
        (r"\bdesempeña un papel fundamental\b", "es central"),
        (r"\bmarca un antes y un después\b", "transforma"),
        (r"\bun punto de inflexión\b", "un cambio significativo"),
        (r"\ben el corazón de\b", "en el centro de"),
        (r"\bun abanico de\b", "diversos"),
        (r"\buna amplia gama de\b", "diversos"),
        (r"\ben última instancia,?\s*", "finalmente, "),
        (r"\bde la mano de\b", "junto con"),
        (r"\btiene la capacidad de\b", "puede"),
        (r"\bcuenta con la capacidad de\b", "puede"),
        (r"\bdebido al hecho de que\b", "dado que"),
        (r"\ben la era actual,?\s*", "actualmente, "),
        (r"\bhoy en día,?\s*", "en el presente, "),
        (r"\ben el mundo actual,?\s*", "en la actualidad, "),
        (r"\bresulta imperativo\b", "es necesario"),
        (r"\bresulta indispensable\b", "es indispensable"),
        (r"\bse hace necesario\b", "se requiere"),
        (r"\bremover\b", "eliminar"),
        (r"\bremoviendo\b", "eliminando"),
        (r"\bhacer sentido\b", "tener sentido"),
        (r"\bconsistente con\b", "coherente con"),
    ]

    for pat, rep in replacements:
        polished = re.sub(pat, rep, polished, flags=re.IGNORECASE)

    # 3. Corrección de anomalías de puntuación
    polished = re.sub(r"\.\s*\.", ".", polished)
    polished = re.sub(r",\s*,", ",", polished)
    polished = re.sub(r",\s+y\b", " y", polished)
    polished = re.sub(r" {2,}", " ", polished)
    polished = re.sub(r"\s+([,\.;:])", r"\1", polished)
    polished = re.sub(r"([,\.;:])([a-zA-ZáéíóúÁÉÍÓÚñÑ])", r"\1 \2", polished)

    # 4. Dinamismo sintáctico y depuración de nominalizaciones (grant-flow-auditor)
    dynamic_subs = [
        (r"\bpermite llevar a cabo\b", "facilita"),
        (r"\bcon el fin de lograr\b", "para alcanzar"),
        (r"\bse propone desarrollar\b", "desarrolla"),
        (r"\btiene como objetivo\b", "busca"),
        (r"\btiene por objetivo\b", "busca"),
        (r"\ben relación con\b", "respecto a"),
        (r"\ben lo que respecta a\b", "respecto a"),
        (r"\bllevar a cabo la\b", "realizar la"),
        (r"\bllevar a cabo el\b", "realizar el"),
        (r"\bllevar a cabo\b", "realizar"),
        (r"\bdar cuenta de\b", "evidenciar"),
        (r"\bponer de manifiesto\b", "revelar"),
        (r"\brealiza la captura de\b", "captura"),
        (r"\brealizar la captura de\b", "capturar"),
        (r"\befectúa el procesamiento de\b", "procesa"),
        (r"\bhace posible la\b", "posibilita la"),
        (r"\bhace posible el\b", "posibilita el"),
        (r"\bcontribuye a la generación de\b", "genera"),
        (r"\bel cual se encuentra\b", "ubicado"),
        (r"\bla cual se encuentra\b", "ubicada"),
        (r"\ba través de\b", "mediante"),
        (r"\bcon el apoyo de\b", "junto a"),
        (r"\bde forma sistemática y articulada\b", "sistemáticamente"),
        (r"\bde manera integral\b", "integralmente"),
        (r"\bde manera efectiva\b", "eficazmente"),
        (r"\bde forma eficiente\b", "eficientemente"),
    ]
    for pat, rep in dynamic_subs:
        polished = re.sub(pat, rep, polished, flags=re.IGNORECASE)

    polished = re.sub(r"\.\s*\.", ".", polished)
    polished = re.sub(r" {2,}", " ", polished).strip()

    # 5. Capitalización inicial coherente
    if text and text[0].isupper() and polished and polished[0].islower():
        polished = polished[0].upper() + polished[1:]

    polished = _restore_latex_tokens(polished, placeholders)

    # Si tras aplicar las reglas el pasaje aún es idéntico, condensar conectores verbosos residuales
    if polished == text:
        fallback_subs = [
            (r"\bpara poder\b", "para"),
            (r"\bque permite\b", "que facilita"),
            (r"\bque permiten\b", "que facilitan"),
            (r"\bAsimismo,\s+", "Además, "),
            (r"\bAdicionalmente,\s+", "Además, "),
            (r"\bDe igual manera,\s+", "Asimismo, "),
            (r"\bdentro de la\b", "en la"),
            (r"\bdentro del\b", "en el"),
        ]
        temp, ph2 = _protect_latex_tokens(polished)
        for pat, rep in fallback_subs:
            temp = re.sub(pat, rep, temp, flags=re.IGNORECASE)
        polished = _restore_latex_tokens(temp, ph2)

    return polished.strip()


def _clean_latex_to_plain(text: str) -> str:
    """Strips common LaTeX commands and braces to produce clean plain text for matching in PDF."""
    if not text:
        return ""
    # Strip comments
    t = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)
    # Strip cite commands like \citep{...}, \citet{...}, \cite{...}
    t = re.sub(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])?\{[^}]*\}", " ", t)
    # Strip formatting commands like \textbf{...}, \emph{...}, etc. keeping content
    t = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", t)
    # Strip standalone commands like \item, \noindent, \centering, etc.
    t = re.sub(r"\\[a-zA-Z]+\*?", " ", t)
    # Strip LaTeX special chars
    t = re.sub(r"[{}\$%~_#&]", " ", t)
    # Normalize spaces
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _extract_surrounding_sentences(content: str, start: int, end: int) -> tuple[str, str]:
    """Extracts the sentence immediately before `start` and immediately after `end` in `content`.

    Returns (context_before, context_after) as clean plain text for locating in PDF.
    """
    preceding = content[:start].rstrip()
    following = content[end:].lstrip()

    pre_clean = _clean_latex_to_plain(preceding)
    foll_clean = _clean_latex_to_plain(following)

    # Context before: find last sentence in pre_clean
    pre_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", pre_clean) if s.strip()]
    if pre_sentences:
        context_before = pre_sentences[-1].rstrip(".").strip()
    else:
        context_before = ""

    # Context after: find first sentence in foll_clean
    foll_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", foll_clean) if s.strip()]
    if foll_sentences:
        context_after = foll_sentences[0].rstrip(".").strip()
    else:
        context_after = ""

    # Cap sentence length to ~120 chars for reliable PDF text layer matching
    if len(context_before) > 120:
        context_before = context_before[-100:].strip()
        sp = context_before.find(" ")
        if sp != -1 and sp < 25:
            context_before = context_before[sp + 1:].strip()

    if len(context_after) > 120:
        context_after = context_after[:100].strip()
        sp = context_after.rfind(" ")
        if sp != -1 and sp > 75:
            context_after = context_after[:sp].strip()

    return context_before, context_after


def _parse_instruction_action(comment: str, target_text: str, matched_original: str) -> tuple[str, str] | None:
    """Parse whether a user's comment text is an actionable editorial command on the selected text.

    Returns (action_type, resulting_text) or None if it's purely a general pipeline observation.
    """
    if not comment:
        return None

    raw_c = comment.strip()
    c_lower = raw_c.lower()

    # 1. Punctuation removal directive (e.g. "quitar los dos puntos", "quitar dobles puntos", "quitar puntos")
    if re.search(r"\b(?:quitar|eliminar|borrar|suprimir)\b.*\b(?:puntos?|dos puntos|dobles puntos)\b", c_lower) or any(k in c_lower for k in [
        "dobles puntos", "dos puntos", "quitar los puntos", "quitar el punto", "quitar punto", "eliminar puntos", "eliminar dobles puntos", "esos dos puntos", "quitar .", "quitar .."
    ]):
        cleaned = re.sub(r"\.\s*\.", ".", matched_original)
        if cleaned != matched_original:
            return ("replace", cleaned)
        cleaned = re.sub(r"[\.:]+$", "", matched_original).rstrip()
        if cleaned != matched_original:
            return ("replace", cleaned)
        if not any(c.isalnum() for c in matched_original):
            return ("delete", "")
        return ("replace", cleaned)

    # 2. Compound directive: remove/avoid X and replace/leave as Y
    compound_m = re.search(
        r"(?:reajusta\w*\s+para\s+que\s+(?:la\s+redacci[oó]n\s+)?no\s+incluya|quita\w*|elimina\w*|borra\w*|suprime\w*|sin|no\s+incluya|no\s+incluir)\s+(?:el\s+nombre\s+|la\s+palabra\s+|el\s+texto\s+)?([a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s]+?)(?:,|\sy\s|\s+y\s+)?\s*(?:deja|dejar|dejalo|déjalo)?\s*(?:como\s+general,?\s*|general,?\s*|como\s+|por\s+|a\s+|usar\s+|poner\s+)(.+)$",
        raw_c,
        re.IGNORECASE
    )
    if compound_m:
        remove_part = compound_m.group(1).strip().strip('"\'«»')
        replace_part = compound_m.group(2).strip().strip('"\'«»')
        replace_part = re.sub(r"^(?:como\s+|por\s+|usar\s+)", "", replace_part, flags=re.IGNORECASE).strip()

        pat = re.compile(rf"(?:la\s+psic[oó]loga\s+)?{re.escape(remove_part)}", re.IGNORECASE)
        if pat.search(matched_original):
            if re.search(r"asesor[ií]a\s+de\s+(?:la\s+psic[oó]loga\s+)?" + re.escape(remove_part), matched_original, re.IGNORECASE):
                sub_pat = re.compile(r"asesor[ií]a\s+de\s+(?:la\s+psic[oó]loga\s+)?" + re.escape(remove_part), re.IGNORECASE)
                rep = "asesoría de " + replace_part if not replace_part.lower().startswith("asesor") else replace_part
                new_text = sub_pat.sub(rep, matched_original)
            else:
                new_text = pat.sub(replace_part, matched_original)
            new_text = re.sub(r" {2,}", " ", new_text).strip()
            return ("replace", new_text)

    # 3. Deletion directive: "quitar X", "eliminar X", "borrar X"
    del_m = re.match(r"^(?:quitar|eliminar|borrar|suprimir)\s+(.+)$", raw_c, re.IGNORECASE)
    if del_m:
        phrase = del_m.group(1).strip().strip('"\'«»')
        phrase_lower = phrase.lower()
        if phrase_lower in ("este texto", "el texto", "esto", "el fragmento", "este fragmento", "la seleccion", "la selección"):
            return ("delete", "")
        cleaned_phrase = re.sub(r"^(?:el\s+nombre\s+|la\s+palabra\s+|el\s+término\s+)", "", phrase, flags=re.IGNORECASE).strip()
        for cand in [phrase, cleaned_phrase]:
            if cand in matched_original:
                new_text = matched_original.replace(cand, "")
                new_text = re.sub(r" {2,}", " ", new_text).strip()
                return ("replace", new_text)
            pat = re.compile(re.escape(cand), re.IGNORECASE)
            if pat.search(matched_original):
                new_text = pat.sub("", matched_original)
                new_text = re.sub(r" {2,}", " ", new_text).strip()
                return ("replace", new_text)

    # 4. Replacement directive: "cambiar por X", "reemplazar por X", "poner X", "dejar como X"
    repl_m = re.match(r"^(?:cambiar|reemplazar|sustituir)(?:\s+este\s+texto)?\s+por\s+[:«\"']?(.*?)[:»\"']?$", raw_c, re.IGNORECASE)
    if repl_m:
        return ("replace", repl_m.group(1).strip())

    repl_m2 = re.match(r"^(?:cambiar|reemplazar|sustituir)\s+[:«\"']?(.*?)[:»\"']?\s+por\s+[:«\"']?(.*?)[:»\"']?$", raw_c, re.IGNORECASE)
    if repl_m2:
        old_part, new_part = repl_m2.group(1).strip(), repl_m2.group(2).strip()
        if old_part in matched_original:
            return ("replace", matched_original.replace(old_part, new_part))
        pat = re.compile(re.escape(old_part), re.IGNORECASE)
        if pat.search(matched_original):
            return ("replace", pat.sub(new_part, matched_original))

    poner_m = re.match(r"^(?:poner|dejar\s+como|dejalo\s+como|déjalo\s+como|usar)\s+[:«\"']?(.*?)[:»\"']?$", raw_c, re.IGNORECASE)
    if poner_m:
        return ("replace", poner_m.group(1).strip())

    # 5. Rephrasing / Humanizing directive (explicit command on this passage)
    if re.search(
        r"\b(?:redactar\s+(?:de\s+forma\s+diferente|diferente|de\s+otra\s+forma)|humanizar(?:lo)?|hacer\s+m[aá]s\s+conciso|mejorar\s+redacci[oó]n|estilo\s+natural|estilo-natural-es)\b",
        c_lower,
    ) and not re.search(r"\b(?:sin\s+nombrar|para\s+el\s+agente|revisar|consultar)\b", c_lower):
        polished = _humanize_text_span(matched_original)
        return ("humanize", polished)

    return None


def _execute_redactor_instruction(comment: str, target_text: str, matched_original: str) -> tuple[str, str]:
    """Execute an editorial comment on `matched_original` via the redactor + grant-flow-auditor rules.

    Strictly operates ONLY on `matched_original` (the anchored passage) and never touches outside text.
    Returns (action_type, new_text).
    """
    direct = _parse_instruction_action(comment, target_text, matched_original)
    if direct is not None:
        act_type, res_text = direct
        if act_type == "replace" and res_text:
            return (act_type, _humanize_text_span(res_text))
        return direct

    raw_c = (comment or "").strip()
    if not raw_c:
        return ("humanize", _humanize_text_span(matched_original))

    c_lower = raw_c.lower()
    working = matched_original

    # A. Generalization / Omission of names or specific mentions ("sin nombrar...", "sin mencionar...", "en general")
    omit_m = re.search(
        r"\b(?:sin\s+nombrar|sin\s+mencionar|sin\s+incluir|omitir|omitiendo)\s+(?:a\s+|el\s+nombre\s+de\s+|la\s+|el\s+)?([a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s]+?)(?:[,\.;]|$)",
        raw_c,
        re.IGNORECASE,
    )
    if omit_m:
        omitted_target = omit_m.group(1).strip().strip('"\'«»')
        # Handle role + proper name patterns inside matched_original
        if re.search(r"psic[oó]log[oa]", omitted_target, re.IGNORECASE) or re.search(r"psic[oó]log[oa]", working, re.IGNORECASE):
            working = re.sub(
                r"\bde\s+la\s+psic[oó]loga\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?",
                "del profesional en psicología",
                working,
                flags=re.IGNORECASE,
            )
            working = re.sub(
                r"\bla\s+psic[oó]loga\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?",
                "el equipo de psicología",
                working,
                flags=re.IGNORECASE,
            )
            working = re.sub(
                r"\bla\s+psic[oó]loga\b",
                "el profesional de psicología",
                working,
                flags=re.IGNORECASE,
            )
        if omitted_target:
            pat = re.compile(re.escape(omitted_target), re.IGNORECASE)
            if pat.search(working):
                working = pat.sub("el equipo especializado", working)
        working = _humanize_text_span(working)
        return ("replace", working)

    # B. Explicit addition / clarification / detail ("aclarar...", "agregar...", "añadir...", "incluir...", "especificar...", "precisar...")
    add_m = re.match(
        r"^(?:aclarar|agregar|a[ñn]adir|incluir|especificar|precisar|mencionar|detallar|complementar|incorporar)\s+(?:que\s+|sobre\s+|los?\s+|las?\s+|el\s+|la\s+)?(.+)$",
        raw_c,
        re.IGNORECASE,
    )
    if add_m:
        detail = add_m.group(1).strip().rstrip(".")
        # Avoid duplicating if detail is already literally inside working
        if detail and detail.lower() not in working.lower():
            ends_with_dot = working.rstrip().endswith(".")
            base = working.rstrip()
            if ends_with_dot:
                base = base[:-1].rstrip()
            # Lowercase first letter of detail unless it is an acronym or proper code
            if len(detail) > 1 and detail[0].isupper() and not detail[:2].isupper():
                detail_clean = detail[0].lower() + detail[1:]
            else:
                detail_clean = detail
            combined = f"{base}, precisando {detail_clean}" + ("." if ends_with_dot else "")
            return ("replace", _humanize_text_span(combined))

    # C. Condensation / shortening ("resumir", "acortar", "más conciso", "sintetizar", "simplificar")
    if re.search(r"\b(?:resumir|acortar|sintetizar|simplificar|m[aá]s\s+corto|m[aá]s\s+breve|reducir)\b", c_lower):
        condensed = re.sub(r",\s*[^,\.;()]{15,80},", ",", working, count=1)
        condensed = _humanize_text_span(condensed)
        return ("humanize", condensed)

    # D. Unificación / ajuste terminológico ("unificar...", "ajustar...", "cambiar X a Y")
    unif_m = re.search(
        r"\b(?:unificar|ajustar|homologar|estandarizar)\s+(?:el\s+t[eé]rmino\s+|la\s+expresi[oó]n\s+|como\s+|a\s+|por\s+)([a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s\-]+)$",
        raw_c,
        re.IGNORECASE,
    )
    if unif_m:
        target_term = unif_m.group(1).strip().strip('"\'«»').rstrip(".")
        if target_term and len(working.split()) <= 8:
            return ("replace", target_term)

    # E. Default redactor + grant-flow-auditor pass on the selected passage
    polished = _humanize_text_span(working)
    return ("humanize", polished)


def _compile_pdf_optimized(redaccion_dir: Path, force_full_build: bool = False) -> tuple[bool, str, int]:
    """Compile main.tex in `redaccion_dir` with minimal latency and memory footprint.

    When `main.bbl` and `main.aux` already exist and `force_full_build` is False,
    executes a single incremental `pdflatex` pass (~0.7s) instead of the 3-pass + bibtex
    `build.sh` pipeline (~4-6s). Falls back to `build.sh` if incremental compilation fails
    or if bibliography/cross-reference files are missing.

    Returns (compile_success, compile_log, compile_ms).
    """
    t0 = time.monotonic()
    main_tex = redaccion_dir / "main.tex"
    main_bbl = redaccion_dir / "main.bbl"
    main_aux = redaccion_dir / "main.aux"
    build_sh = redaccion_dir / "build.sh"

    can_fast_compile = (
        not force_full_build
        and main_tex.is_file()
        and main_bbl.is_file()
        and main_aux.is_file()
    )

    if can_fast_compile:
        try:
            res = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                cwd=redaccion_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=35,
            )
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            out_tail = (res.stdout + "\n" + res.stderr)[-500:]
            if res.returncode == 0 and (redaccion_dir / "main.pdf").is_file():
                # Only trigger full bibtex+pdflatex if LaTeX warns about undefined citations
                if "Citation `" not in res.stdout and "Rerun to get" not in res.stdout:
                    return True, out_tail, elapsed_ms
        except Exception:
            pass

    try:
        if build_sh.is_file():
            build_env = dict(os.environ)
            build_env["SKIP_DOI_REPAIR"] = "1"
            res = subprocess.run(
                ["bash", "build.sh"],
                cwd=redaccion_dir,
                env=build_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                input="y\n",
            )
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return res.returncode == 0, (res.stdout + "\n" + res.stderr)[-500:], elapsed_ms

        res = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "main.tex"],
            cwd=redaccion_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return res.returncode == 0, (res.stdout + "\n" + res.stderr)[-500:], elapsed_ms
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return False, f"Error invocando compilación: {e}", elapsed_ms


def apply_pdf_annotations(
    run_dir: Path,
    annotations: list[dict[str, Any]],
    process_pending: bool = False,
) -> dict[str, Any]:
    """Apply comments, strikethroughs and humanization to the LaTeX sections of the active run.

    Strictly isolates every edit to the exact matched span (`content[start:end]`) inside the
    single target `.tex` file where the anchor resides. Never modifies unrelated sections or
    the preamble of `main.tex`.

    Returns a comprehensive result envelope with timing and agent participation metadata.
    """
    t_start = time.monotonic()
    redaccion_dir = run_dir / "redaccion"
    sections_dir = redaccion_dir / "sections"
    pipeline_dir = run_dir / "artefactos" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    artefactos_dir = run_dir / "artefactos"
    artefactos_dir.mkdir(parents=True, exist_ok=True)

    if not redaccion_dir.is_dir():
        return {
            "ok": False,
            "error": f"Directorio de redacción no encontrado: {redaccion_dir}",
            "applied_count": 0,
        }

    # Discover candidate LaTeX files (sections/*.tex first, then main.tex)
    tex_files: list[Path] = []
    if sections_dir.is_dir():
        tex_files.extend(sorted(sections_dir.glob("*.tex")))
    if (redaccion_dir / "main.tex").is_file():
        tex_files.append(redaccion_dir / "main.tex")

    applied_strikethroughs: list[dict[str, Any]] = []
    executed_comments: list[dict[str, Any]] = []
    pending_comments: list[dict[str, Any]] = []
    applied_humanize: list[dict[str, Any]] = []
    applied_replace: list[dict[str, Any]] = []
    failed_annotations: list[dict[str, Any]] = []
    agents_invoked: list[str] = []

    def _mark_agent(name: str) -> None:
        if name not in agents_invoked:
            agents_invoked.append(name)

    # Map file contents in memory
    file_contents: dict[Path, str] = {tf: tf.read_text(encoding="utf-8", errors="replace") for tf in tex_files}
    files_modified: set[Path] = set()

    # Process any pre-existing pending instructions if requested
    consumed_pending = 0
    remaining_pending = 0
    if process_pending:
        consumed_pending, remaining_pending = consume_pending_instructions(
            pipeline_dir, run_dir, file_contents, files_modified
        )
        if consumed_pending > 0:
            _mark_agent("redactor")
            _mark_agent("grant-flow-auditor")

    for idx, ann in enumerate(annotations):
        ann_type = ann.get("type", "").lower()
        target_text = ann.get("text", "").strip()
        comment_body = ann.get("comment", "").strip()
        page_num = ann.get("page", 1)
        ann_id = ann.get("id", str(idx + 1))

        if not target_text:
            failed_annotations.append({
                "id": ann_id,
                "type": ann_type,
                "text": target_text,
                "page": page_num,
                "reason": "Anotación sin texto ancla: no hay pasaje que localizar",
            })
            continue

        # Search for highest-scoring target text span across all candidate files
        matched_file, match_span = _locate_best_span_in_files(
            tex_files, file_contents, target_text, page_num=page_num, section_hint=ann.get("section")
        )

        matched_original = (
            file_contents[matched_file][match_span[0]:match_span[1]]
            if matched_file and match_span
            else None
        )

        # Manejo de comentarios / instrucciones del usuario
        if ann_type in ("comment", "comentario"):
            action = _parse_instruction_action(comment_body, target_text, matched_original or target_text)
            apply_directly = bool(ann.get("apply_directly")) or process_pending

            if matched_file and match_span and (action is not None or apply_directly):
                if action is not None:
                    act_type, new_text = action
                elif bool(ann.get("apply_directly")) and not process_pending:
                    act_type, new_text = ("replace", comment_body)
                else:
                    act_type, new_text = _execute_redactor_instruction(
                        comment_body, target_text, matched_original or target_text
                    )

                content = file_contents[matched_file]
                start, end = match_span
                _mark_agent("redactor")
                _mark_agent("grant-flow-auditor")

                if act_type == "delete" or (act_type == "replace" and new_text == ""):
                    file_contents[matched_file] = _replace_span_isolated(
                        content, start, end, "", is_delete=True
                    )
                    files_modified.add(matched_file)
                    before_sent, after_sent = _extract_surrounding_sentences(content, start, end)
                    applied_strikethroughs.append({
                        "id": ann_id,
                        "file": str(matched_file.relative_to(run_dir)),
                        "page": page_num,
                        "original_text": matched_original,
                        "context_before": before_sent,
                        "context_after": after_sent,
                        "rects": ann.get("rects"),
                        "via_instruction": comment_body,
                        "agent": "redactor",
                    })
                elif act_type == "humanize":
                    polished = new_text if new_text else _humanize_text_span(matched_original)
                    file_contents[matched_file] = _replace_span_isolated(
                        content, start, end, polished, is_delete=False
                    )
                    files_modified.add(matched_file)
                    applied_humanize.append({
                        "id": ann_id,
                        "file": str(matched_file.relative_to(run_dir)),
                        "page": page_num,
                        "original_text": matched_original,
                        "polished_text": polished,
                        "rects": ann.get("rects"),
                        "via_instruction": comment_body,
                        "agent": "grant-flow-auditor",
                    })
                else:  # replace
                    file_contents[matched_file] = _replace_span_isolated(
                        content, start, end, new_text, is_delete=False
                    )
                    files_modified.add(matched_file)
                    applied_replace.append({
                        "id": ann_id,
                        "file": str(matched_file.relative_to(run_dir)),
                        "page": page_num,
                        "original_text": matched_original,
                        "replacement": new_text,
                        "deleted": False,
                        "context_before": "",
                        "context_after": "",
                        "rects": ann.get("rects"),
                        "via_instruction": comment_body,
                        "agent": "redactor",
                    })

                executed_comments.append({
                    "id": ann_id,
                    "file": str(matched_file.relative_to(run_dir)),
                    "page": page_num,
                    "target_text": matched_original,
                    "comment": comment_body,
                    "located": True,
                    "rects": ann.get("rects"),
                    "executed": True,
                    "agent": "redactor + grant-flow-auditor",
                })
                continue
            else:
                pending_comments.append({
                    "id": ann_id,
                    "file": str(matched_file.relative_to(run_dir)) if matched_file else None,
                    "page": page_num,
                    "target_text": matched_original if matched_original else target_text,
                    "comment": comment_body,
                    "located": bool(matched_file),
                    "rects": ann.get("rects"),
                    "executed": False,
                })
                continue

        if not matched_file or not match_span:
            failed_annotations.append({
                "id": ann_id,
                "type": ann_type,
                "text": target_text,
                "page": page_num,
                "reason": "Texto no localizado en las secciones LaTeX fuente",
            })
            continue

        content = file_contents[matched_file]
        start, end = match_span

        if ann_type in ("strikethrough", "tachar", "delete"):
            _mark_agent("redactor")
            file_contents[matched_file] = _replace_span_isolated(
                content, start, end, "", is_delete=True
            )
            files_modified.add(matched_file)
            before_sent, after_sent = _extract_surrounding_sentences(content, start, end)
            applied_strikethroughs.append({
                "id": ann_id,
                "file": str(matched_file.relative_to(run_dir)),
                "page": page_num,
                "original_text": matched_original,
                "context_before": before_sent,
                "context_after": after_sent,
                "rects": ann.get("rects"),
                "agent": "redactor",
            })

        elif ann_type in ("humanize", "humanizar"):
            _mark_agent("grant-flow-auditor")
            polished_text = _humanize_text_span(matched_original)
            file_contents[matched_file] = _replace_span_isolated(
                content, start, end, polished_text, is_delete=False
            )
            files_modified.add(matched_file)
            applied_humanize.append({
                "id": ann_id,
                "file": str(matched_file.relative_to(run_dir)),
                "page": page_num,
                "original_text": matched_original,
                "polished_text": polished_text,
                "rects": ann.get("rects"),
                "agent": "grant-flow-auditor",
            })

        elif ann_type in ("replace", "reemplazar"):
            raw_replacement = ann.get("replacement")
            replacement = "" if raw_replacement is None else str(raw_replacement)
            delete_intent = bool(ann.get("delete_intent"))
            if replacement.strip() == "" and not delete_intent:
                failed_annotations.append({
                    "id": ann_id,
                    "type": ann_type,
                    "text": target_text,
                    "page": page_num,
                    "reason": (
                        "Reemplazo vacío sin confirmación de borrado: no se toca "
                        "el ancla. Marca la casilla de borrado si quieres eliminarla."
                    ),
                })
                continue
            _mark_agent("redactor")
            is_deleted = replacement == "" or delete_intent
            file_contents[matched_file] = _replace_span_isolated(
                content, start, end, "" if is_deleted else replacement, is_delete=is_deleted
            )
            files_modified.add(matched_file)
            before_sent, after_sent = _extract_surrounding_sentences(content, start, end) if is_deleted else ("", "")
            applied_replace.append({
                "id": ann_id,
                "file": str(matched_file.relative_to(run_dir)),
                "page": page_num,
                "original_text": matched_original,
                "replacement": replacement,
                "deleted": is_deleted,
                "context_before": before_sent,
                "context_after": after_sent,
                "rects": ann.get("rects"),
                "agent": "redactor",
            })

    # Write ONLY the modified files back to disk
    for tf in files_modified:
        tf.write_text(file_contents[tf], encoding="utf-8")

    # Las instrucciones pendientes se anexan, no se reescriben: una instrucción
    # sin ejecutar no se puede recuperar de ningún otro sitio.
    pending_path, pending_written = register_pending_instructions(
        pipeline_dir, pending_comments
    )
    executed_log_path = register_executed_instructions(
        pipeline_dir, executed_comments
    )
    if pending_path is None and executed_log_path is not None:
        pending_path = executed_log_path

    # Solo lo que se escribió de verdad cuenta como registrado; lo que ya estaba
    # en la cola se reporta como duplicado, y un comentario sin ancla como fallo.
    comment_failures = [
        a for a in failed_annotations if a.get("type") in ("comment", "comentario")
    ]
    duplicated_comments = max(0, len(pending_comments) - pending_written)

    all_registered_and_executed = executed_comments + pending_comments
    execution_ms = int((time.monotonic() - t_start) * 1000)

    # Persist annotations JSON
    timestamp = datetime.now().isoformat()
    json_payload = {
        "timestamp": timestamp,
        "run_id": run_dir.name,
        "total_submitted": len(annotations),
        "agents_invoked": agents_invoked,
        "applied": {
            "strikethrough": len(applied_strikethroughs),
            "humanize": len(applied_humanize),
            "replace": len(applied_replace),
            "comments": len(executed_comments),
        },
        "registered": {
            "comments": pending_written,
            "duplicated": duplicated_comments,
            "failed": len(comment_failures),
            "consumed": consumed_pending,
        },
        "details": {
            "strikethrough": applied_strikethroughs,
            "humanize": applied_humanize,
            "replace": applied_replace,
            "comments": all_registered_and_executed,
            "unmatched": failed_annotations,
        },
        "pending_instructions_file": (
            str(pending_path.relative_to(run_dir)) if pending_path else None
        ),
    }

    anotaciones_json_p = pipeline_dir / "anotaciones_pdf.json"
    anotaciones_json_r = artefactos_dir / "anotaciones_pdf.json"
    anotaciones_json_p.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    anotaciones_json_r.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Generate Markdown summary report
    md_lines = [
        f"# Registro de Revisión y Anotaciones sobre PDF - {run_dir.name}",
        f"\n**Fecha de ejecución:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Agentes ejecutores:** {', '.join(agents_invoked) if agents_invoked else 'ninguno (solo registro)'}",
        f"- **Textos tachados eliminados:** {len(applied_strikethroughs)}",
        f"- **Pasajes humanizados (estilo-natural-es):** {len(applied_humanize)}",
        f"- **Reemplazos aplicados:** {len(applied_replace)}",
        f"- **Comentarios e instrucciones aplicadas al manuscrito:** {len(executed_comments)}",
        f"- **Instrucciones pendientes registradas para el agente:** {pending_written}",
        f"- **Instrucciones ya registradas (omitidas por duplicado):** {duplicated_comments}",
        f"- **Instrucciones previas consumidas/resueltas:** {consumed_pending}",
        f"- **Anotaciones sin aplicar:** {len(failed_annotations)}",
        f"- **Archivos modificados (aislamiento estricto por sección):** {len(files_modified)}",
        "\n---",
    ]

    if applied_strikethroughs:
        md_lines.append("\n## ✂️ Textos Tachados Eliminados")
        for item in applied_strikethroughs:
            md_lines.append(f"- **Pág. {item['page']}** (`{item['file']}`):")
            md_lines.append(f"  > ~~{item['original_text']}~~")

    if applied_humanize:
        md_lines.append("\n## ✨ Pasajes Humanizados con `estilo-natural-es` (`grant-flow-auditor`)")
        for item in applied_humanize:
            md_lines.append(f"- **Pág. {item['page']}** (`{item['file']}`):")
            md_lines.append(f"  - *Original:* {item['original_text']}")
            md_lines.append(f"  - *Humanizado:* **{item['polished_text']}**")

    if applied_replace:
        md_lines.append("\n## 🔁 Reemplazos y Ajustes del `redactor` Aplicados")
        for item in applied_replace:
            md_lines.append(f"- **Pág. {item['page']}** (`{item['file']}`):")
            md_lines.append(f"  - *Original:* {item['original_text']}")
            destino = item['replacement'] if not item.get('deleted') else "(borrado)"
            md_lines.append(f"  - *Reemplazo:* **{destino}**")

    if executed_comments:
        md_lines.append("\n## 💬 Comentarios e Instrucciones Aplicadas al Manuscrito")
        for item in executed_comments:
            ubicacion = f"`{item['file']}`" if item.get("file") else "**sin ubicar**"
            md_lines.append(f"- **Pág. {item['page']}** ({ubicacion}):")
            md_lines.append(f"  - *Texto ancla:* \"{item['target_text']}\"")
            md_lines.append(f"  - *Instrucción ejecutada:* {item['comment']}")

    if pending_comments:
        md_lines.append("\n## 📝 Instrucciones Registradas en Espera")
        md_lines.append(
            "\nNo se aplicaron al manuscrito. Las ejecuta el `redactor` al continuar "
            "el pipeline, y el `grant-flow-auditor` pule el resultado después."
        )
        for item in pending_comments:
            ubicacion = f"`{item['file']}`" if item.get("file") else "**sin ubicar**"
            md_lines.append(f"- **Pág. {item['page']}** ({ubicacion}):")
            md_lines.append(f"  - *Texto ancla:* \"{item['target_text']}\"")
            md_lines.append(f"  - *Instrucción:* {item['comment']}")
        if pending_path:
            md_lines.append(
                f"\nArchivo de pendientes: `{pending_path.relative_to(run_dir)}`"
            )

    if failed_annotations:
        md_lines.append("\n## ⚠️ Anotaciones sin aplicar")
        for item in failed_annotations:
            md_lines.append(f"- **Pág. {item['page']}** [{item['type']}]: \"{item['text']}\" ({item['reason']})")

    anotaciones_md_p = pipeline_dir / "anotaciones_pdf.md"
    anotaciones_md_r = artefactos_dir / "anotaciones_pdf.md"
    anotaciones_md_p.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    anotaciones_md_r.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    # Trigger re-compilation of main.pdf, but only when an annotation actually
    # changed the manuscript.
    compile_success = False
    compile_log = ""
    compile_ms = 0
    recompile_skipped = not files_modified
    recompile_reason = ""
    if recompile_skipped:
        compile_log = "No se recompiló: ninguna anotación cambió el manuscrito."
        recompile_reason = "sin cambios en el manuscrito"
    else:
        compile_success, compile_log, compile_ms = _compile_pdf_optimized(redaccion_dir)
        if not compile_success:
            recompile_reason = "la compilación no terminó bien"

    total_ms = int((time.monotonic() - t_start) * 1000)

    return {
        "ok": True,
        "message": (
            "Anotaciones ejecutadas correctamente en el proyecto."
            if files_modified or consumed_pending > 0
            else "Instrucciones registradas para el agente. El manuscrito no cambió."
        ),
        "summary": {
            "total_submitted": len(annotations),
            "strikethrough_applied": len(applied_strikethroughs),
            "comments_applied": len(executed_comments),
            "comments_registered": pending_written,
            "comments_duplicated": duplicated_comments,
            "comments_failed": len(comment_failures),
            "pending_consumed": consumed_pending,
            "pending_remaining": remaining_pending,
            "annotations_failed": len(failed_annotations),
            "humanize_applied": len(applied_humanize),
            "replace_applied": len(applied_replace),
            "replace_failed": len(
                [a for a in failed_annotations if a.get("type") in ("replace", "reemplazar")]
            ),
            "unmatched": failed_annotations,
            "files_modified": [str(f.relative_to(run_dir)) for f in files_modified],
            "agents_invoked": agents_invoked,
            "execution_ms": execution_ms,
            "compile_ms": compile_ms,
            "total_ms": total_ms,
            "pdf_recompiled": compile_success,
            "pdf_recompile_skipped": recompile_skipped,
            "pdf_recompile_reason": recompile_reason,
            "compile_log": compile_log.strip(),
            "pending_instructions_file": (
                str(pending_path.relative_to(run_dir)) if pending_path else None
            ),
        },
        "details": {
            "strikethrough": applied_strikethroughs,
            "humanize": applied_humanize,
            "replace": applied_replace,
            "comments": all_registered_and_executed,
            "unmatched": failed_annotations,
        },
        "report_file": "artefactos/anotaciones_pdf.md",
    }

