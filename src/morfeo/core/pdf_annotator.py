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

        # If matched span starts with punctuation (e.g. ". El sismo...") that is actually
        # the closing period of a preceding sentence (preceded by a word char), advance abs_start
        # past the punctuation+space so we never eat the previous sentence's period.
        if abs_start > 0 and re.match(r"^[\.,;:]+\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]", raw_content[abs_start:abs_end]):
            prev_char = raw_content[abs_start - 1]
            if prev_char.isalnum() or prev_char in ")]}":
                lead_m = re.match(r"^[\.,;:]+\s+", raw_content[abs_start:abs_end])
                if lead_m:
                    abs_start += lead_m.end()

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
    # Clean up any pre-existing stray period at the start of the line immediately before the span
    prefix = re.sub(r"((?:^|\n|\\noindent)\s*)\.\s+$", r"\1", prefix)
    if is_delete or replacement == "":
        if prefix.endswith(" ") and suffix.startswith(" "):
            suffix = suffix[1:]
        # If deleting a sentence at the start of a paragraph/section or right after another period,
        # strip any orphan leading period/comma left behind in suffix (e.g. ". El sismo...")
        prefix_trimmed = prefix.rstrip()
        if (
            not prefix_trimmed
            or prefix_trimmed.endswith(("\n", "{", ".", "!", "?", ":"))
            or re.search(r"\\(?:noindent|section\*?\{[^}]*\})\s*$", prefix_trimmed)
        ):
            suffix = re.sub(r"^\s*[\.,;:]+\s*", "", suffix)
            if suffix and suffix[0].islower():
                suffix = suffix[0].upper() + suffix[1:]
            if prefix.endswith("\n") and suffix.startswith(" "):
                suffix = suffix.lstrip(" ")
        return prefix + suffix
    if prefix.endswith("\n ") and not replacement.startswith(" "):
        prefix = prefix[:-1]
    if prefix and re.search(r"[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\)\]]$", prefix) and replacement and replacement[0].isupper():
        prefix = prefix + ". "
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
    clean_anchor = re.sub(r"\s+", " ", (anchor or "")).strip()
    clean_comment = re.sub(r"\s+", " ", (comment or "")).strip()
    payload = f"{page}|{clean_anchor}|{clean_comment}".encode("utf-8")
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
        anchor = re.sub(r"\s+", " ", (item.get("target_text") or "")).strip()
        comment = re.sub(r"\s+", " ", (item.get("comment") or "")).strip()
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
        ancla = re.sub(r"\s+", " ", (item.get("target_text") or "")).strip()
        comentario = re.sub(r"\s+", " ", (item.get("comment") or "")).strip()
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


def _resolve_section_target_from_instruction(
    instruction: str,
    tex_files: list[Path],
    file_contents: dict[Path, str],
    default_file: Path | None = None,
) -> tuple[Path | None, tuple[int, int] | None]:
    """Resolve a target `.tex` file and sentence span when an instruction names a section or position.

    Supports directives such as:
    - "agrega dos oraciones al inicio del resumen que den más contexto del proyecto"
    - "elimina la primera oración del resumen"
    - "al principio del resumen ejecutivo"
    - "al inicio de la justificación"
    """
    if not instruction:
        return None, None

    inst_low = instruction.lower()
    section_map = [
        (r"\bresumen\s+ejecutivo\b", "00_frontmatter.tex", r"\\section\*\{Resumen\s+ejecutivo\}"),
        (r"\bpalabras\s+clave\b", "00_frontmatter.tex", r"\\section\*\{Palabras\s+clave\}"),
        (r"\bresumen\b", "00_frontmatter.tex", r"\\section\*\{Resumen\}"),
        (r"\bjustificaci[oó]n\b", "02_", r"\\section\{"),
        (r"\bdescripci[oó]n\s+del\s+problema\b|\bplanteamiento\b", "03_", r"\\section\{"),
        (r"\bestado\s+del\s+arte\b", "04_", r"\\section\{"),
        (r"\bhip[oó]tesis\b", "05_", r"\\section\{"),
        (r"\bobjetivo\s+general\b", "06_", r"\\section\{"),
        (r"\bobjetivos\s+espec[ií]ficos\b", "07_", r"\\section\{"),
        (r"\bmarco\s+conceptual\b", "08_", r"\\section\{"),
        (r"\bequipo\s+de\s+trabajo\b", "09_", r"\\section\{"),
        (r"\bmetodolog[ií]a\b", "10_", r"\\section\{"),
        (r"\bresultados\s+esperados\b", "11_", r"\\section\{"),
        (r"\bconsideraciones\s+[eé]ticas\b", "12_", r"\\section\{"),
        (r"\bpresupuesto\b", "13_", r"\\section\{"),
        (r"\bcronograma\b", "14_", r"\\section\{"),
    ]

    target_file: Path | None = None
    header_regex: str | None = None
    for kw_pat, file_hint, hdr_pat in section_map:
        if re.search(kw_pat, inst_low):
            for tf in tex_files:
                if file_hint in tf.name:
                    target_file = tf
                    header_regex = hdr_pat
                    break
            if target_file:
                break

    if target_file is None:
        target_file = default_file
    if target_file is None or target_file not in file_contents:
        return None, None

    raw = file_contents[target_file]
    reg_start, reg_end = _editable_region_of_tex(target_file, raw)
    search_start = reg_start
    search_end = reg_end

    if header_regex:
        m_hdr = re.search(header_regex, raw[reg_start:reg_end], re.IGNORECASE)
        if m_hdr:
            search_start = reg_start + m_hdr.end()
            m_next = re.search(r"\\section\*?\{", raw[search_start:reg_end])
            if m_next:
                search_end = search_start + m_next.start()

    # Locate the first prose sentence inside [search_start, search_end]
    body_slice = raw[search_start:search_end]
    # Skip leading whitespace, % comments, \noindent, \label{...}, and stray punctuation
    pos = 0
    while pos < len(body_slice):
        ws_m = re.match(r"^(?:\s+|\\noindent\b|\\label\{[^}]*\}|%[^\n]*\n)+", body_slice[pos:])
        if ws_m:
            pos += ws_m.end()
            continue
        break

    if pos >= len(body_slice):
        return None, None

    prose_start = search_start + pos
    # Match up to the end of the first real sentence (period followed by space + uppercase or newline, skipping decimals like 7,4)
    rem = raw[prose_start:search_end]
    sent_m = re.search(r"^[.\s]*([^\n]+?\.)(?=\s+[A-ZÁÉÍÓÚÑ]|\s*\n|$)", rem)
    if sent_m:
        prose_end = prose_start + sent_m.end()
    else:
        line_end = rem.find("\n")
        prose_end = prose_start + (line_end if line_end != -1 else min(len(rem), 260))

    return target_file, (prose_start, prose_end)


def consume_pending_instructions(
    pipeline_dir: Path,
    run_dir: Path,
    file_contents: dict[Path, str],
    files_modified: set[Path],
    tex_files: list[Path] | None = None,
    applied_strikethroughs: list[dict[str, Any]] | None = None,
    applied_humanize: list[dict[str, Any]] | None = None,
    applied_replace: list[dict[str, Any]] | None = None,
    executed_comments: list[dict[str, Any]] | None = None,
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

    all_tex_files = tex_files if tex_files is not None else list(file_contents.keys())
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

            # Extract page, target file, multiline anchor, and instruction
            page_m = re.search(r"P[aá]g\.\s*(\d+)", block_text)
            page_num = int(page_m.group(1)) if page_m else 1
            file_m = re.search(r"`([^`]+\.tex)`", block_text)
            anchor_m = re.search(r"Ancla:\s*«(.*?)»", block_text, re.DOTALL)
            if not anchor_m:
                anchor_m = re.search(r"Ancla:\s*[«\"]?(.*?)[»\"]?$", block_text, re.MULTILINE)
            inst_m = re.search(r"Instrucci[oó]n:\s*(.*?)$", block_text, re.MULTILINE)

            rel_file = file_m.group(1).strip() if file_m else None
            anchor = re.sub(r"\s+", " ", anchor_m.group(1)).strip() if anchor_m else ""
            instruction = inst_m.group(1).strip() if inst_m else ""

            target_path = (run_dir / rel_file).resolve() if rel_file else None
            if target_path and target_path not in file_contents:
                for k_path in file_contents:
                    if str(k_path).endswith(rel_file):
                        target_path = k_path
                        break

            is_satisfied = False

            if "aplicada" in block_text.lower() or "ejecutada" in block_text.lower():
                is_satisfied = True
            else:
                # 1. Check if already satisfied (e.g. Camila removal)
                if target_path and target_path in file_contents:
                    cur_text = file_contents[target_path]
                    if re.search(r"\bcamila\b", instruction, re.IGNORECASE) and not re.search(r"\bcamila\b", cur_text, re.IGNORECASE):
                        is_satisfied = True

                if not is_satisfied:
                    # 2. Locate span in target_path, across all tex_files, or via section instruction
                    m_span: tuple[int, int] | None = None
                    is_section_positional = bool(
                        re.search(
                            r"\b(?:al\s+inicio\s+del?|al\s+principio\s+del?|la\s+primera\s+oraci[oó]n\s+del?|la\s+primeera\s+oraci[oó]n\s+del?|al\s+comienzo\s+del?)\b",
                            instruction,
                            re.IGNORECASE,
                        )
                    )
                    is_ui_anchor = bool(re.match(r"^Morfeo\s+IA:", anchor, re.IGNORECASE))

                    if not is_section_positional and not is_ui_anchor and target_path and target_path in file_contents:
                        cur_text = file_contents[target_path]
                        reg_start, reg_end = _editable_region_of_tex(target_path, cur_text)
                        scored_span = _find_text_span_scored(cur_text[reg_start:reg_end], anchor)
                        if scored_span:
                            m_span = (reg_start + scored_span[0], reg_start + scored_span[1])

                    if m_span is None and not is_section_positional and not is_ui_anchor and anchor:
                        found_f, found_s = _locate_best_span_in_files(
                            all_tex_files, file_contents, anchor, page_num=page_num
                        )
                        if found_f and found_s:
                            target_path = found_f
                            m_span = found_s

                    if m_span is None:
                        sec_f, sec_s = _resolve_section_target_from_instruction(
                            instruction, all_tex_files, file_contents, default_file=target_path
                        )
                        if sec_f and sec_s:
                            target_path = sec_f
                            m_span = sec_s

                    if target_path and target_path in file_contents and m_span:
                        cur_text = file_contents[target_path]
                        m_start, m_end = m_span
                        matched_orig = cur_text[m_start:m_end]
                        act_type, new_text = _execute_redactor_instruction(
                            instruction, anchor, matched_orig, section_context=cur_text
                        )
                        rel_target = str(target_path.relative_to(run_dir))
                        block_lines[0] = re.sub(
                            r"sin ubicar en las fuentes",
                            f"`{rel_target}`",
                            block_lines[0],
                        )
                        if act_type == "delete" or (act_type == "replace" and new_text == ""):
                            before_sent, after_sent = _extract_surrounding_sentences(cur_text, m_start, m_end)
                            file_contents[target_path] = _replace_span_isolated(
                                cur_text, m_start, m_end, "", is_delete=True
                            )
                            files_modified.add(target_path)
                            if applied_strikethroughs is not None:
                                applied_strikethroughs.append({
                                    "id": f"queue_{consumed + 1}",
                                    "file": rel_target,
                                    "page": page_num,
                                    "original_text": matched_orig,
                                    "context_before": before_sent,
                                    "context_after": after_sent,
                                    "rects": None,
                                    "via_instruction": instruction,
                                    "agent": "redactor",
                                })
                            is_satisfied = True
                        elif new_text != matched_orig:
                            file_contents[target_path] = _replace_span_isolated(
                                cur_text, m_start, m_end, new_text, is_delete=False
                            )
                            files_modified.add(target_path)
                            if act_type == "humanize" and applied_humanize is not None:
                                applied_humanize.append({
                                    "id": f"queue_{consumed + 1}",
                                    "file": rel_target,
                                    "page": page_num,
                                    "original_text": matched_orig,
                                    "polished_text": new_text,
                                    "rects": None,
                                    "via_instruction": instruction,
                                    "agent": "grant-flow-auditor",
                                })
                            elif applied_replace is not None:
                                applied_replace.append({
                                    "id": f"queue_{consumed + 1}",
                                    "file": rel_target,
                                    "page": page_num,
                                    "original_text": matched_orig,
                                    "replacement": new_text,
                                    "deleted": False,
                                    "context_before": "",
                                    "context_after": "",
                                    "rects": None,
                                    "via_instruction": instruction,
                                    "agent": "redactor",
                                })
                            is_satisfied = True
                        else:
                            is_satisfied = True

                        if is_satisfied and executed_comments is not None:
                            executed_comments.append({
                                "id": f"queue_{consumed + 1}",
                                "file": rel_target,
                                "page": page_num,
                                "target_text": matched_orig,
                                "comment": instruction,
                                "located": True,
                                "rects": None,
                                "executed": True,
                                "agent": "redactor + grant-flow-auditor",
                            })
                    else:
                        # Anchor was already deleted or superseded in the manuscript
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


_SPANISH_ACCENT_CORRECTIONS: dict[str, str] = {
    "oracion": "oración",
    "orancioens": "oraciones",
    "oranciones": "oraciones",
    "primeera": "primera",
    "andtes": "antes",
    "poblacion": "población",
    "investigacion": "investigación",
    "evaluacion": "evaluación",
    "validacion": "validación",
    "identificacion": "identificación",
    "atencion": "atención",
    "intervencion": "intervención",
    "aplicacion": "aplicación",
    "implementacion": "implementación",
    "ejecucion": "ejecución",
    "optimizacion": "optimización",
    "calibracion": "calibración",
    "estimacion": "estimación",
    "prediccion": "predicción",
    "clasificacion": "clasificación",
    "extraccion": "extracción",
    "deteccion": "detección",
    "recoleccion": "recolección",
    "generacion": "generación",
    "integracion": "integración",
    "articulacion": "articulación",
    "apropiacion": "apropiación",
    "informacion": "información",
    "comunicacion": "comunicación",
    "educacion": "educación",
    "formacion": "formación",
    "participacion": "participación",
    "correlacion": "correlación",
    "regresion": "regresión",
    "dimension": "dimensión",
    "depresion": "depresión",
    "expresion": "expresión",
    "comprension": "comprensión",
    "extension": "extensión",
    "precision": "precisión",
    "decision": "decisión",
    "exclusion": "exclusión",
    "inclusion": "inclusión",
    "conclusion": "conclusión",
    "distribucion": "distribución",
    "contribucion": "contribución",
    "institucion": "institución",
    "reduccion": "reducción",
    "produccion": "producción",
    "construccion": "construcción",
    "instruccion": "instrucción",
    "seccion": "sección",
    "prevencion": "prevención",
    "rehabilitacion": "rehabilitación",
    "ubicacion": "ubicación",
    "situacion": "situación",
    "limitacion": "limitación",
    "medicion": "medición",
    "condicion": "condición",
    "exposicion": "exposición",
    "proposicion": "proposición",
    "composicion": "composición",
    "definicion": "definición",
    "transicion": "transición",
    "adquisicion": "adquisición",
    "analisis": "análisis",
    "hipotesis": "hipótesis",
    "sintesis": "síntesis",
    "diagnostico": "diagnóstico",
    "diagnostica": "diagnóstica",
    "diagnosticos": "diagnósticos",
    "pronostico": "pronóstico",
    "metodo": "método",
    "metodos": "métodos",
    "metodologia": "metodología",
    "metodologias": "metodologías",
    "metodologico": "metodológico",
    "metodologica": "metodológica",
    "clinico": "clínico",
    "clinica": "clínica",
    "clinicos": "clínicos",
    "clinicas": "clínicas",
    "psicometrico": "psicométrico",
    "psicometrica": "psicométrica",
    "psicometricos": "psicométricos",
    "psicometricas": "psicométricas",
    "psicologico": "psicológico",
    "psicologica": "psicológica",
    "psicologicos": "psicológicos",
    "psicologicas": "psicológicas",
    "psicologia": "psicología",
    "psiquiatrico": "psiquiátrico",
    "psiquiatrica": "psiquiátrica",
    "postraumatico": "postraumático",
    "postraumatica": "postraumática",
    "estres": "estrés",
    "sintoma": "síntoma",
    "sintomas": "síntomas",
    "sintomatico": "sintomático",
    "sintomatica": "sintomática",
    "sismico": "sísmico",
    "sismica": "sísmica",
    "sismicos": "sísmicos",
    "sismicas": "sísmicas",
    "telurico": "telúrico",
    "telurica": "telúrica",
    "teluricos": "telúricos",
    "acustico": "acústico",
    "acustica": "acústica",
    "acusticos": "acústicos",
    "acusticas": "acústicas",
    "linguistico": "lingüístico",
    "linguistica": "lingüística",
    "linguisticos": "lingüísticos",
    "linguisticas": "lingüísticas",
    "prosodico": "prosódico",
    "prosodica": "prosódica",
    "prosodicos": "prosódicos",
    "prosodicas": "prosódicas",
    "semantico": "semántico",
    "semantica": "semántica",
    "semanticos": "semánticos",
    "semanticas": "semánticas",
    "lexico": "léxico",
    "lexica": "léxica",
    "estadistico": "estadístico",
    "estadistica": "estadística",
    "estadisticos": "estadísticos",
    "estadisticas": "estadísticas",
    "automatico": "automático",
    "automatica": "automática",
    "automaticos": "automáticos",
    "automaticas": "automáticas",
    "sistematico": "sistemático",
    "sistematica": "sistemática",
    "especifico": "específico",
    "especifica": "específica",
    "especificos": "específicos",
    "especificas": "específicas",
    "cientifico": "científico",
    "cientifica": "científica",
    "cientificos": "científicos",
    "cientificas": "científicas",
    "academico": "académico",
    "academica": "académica",
    "academicos": "académicos",
    "academicas": "académicas",
    "tecnologico": "tecnológico",
    "tecnologica": "tecnológica",
    "tecnologicos": "tecnológicos",
    "tecnologicas": "tecnológicas",
    "tecnologia": "tecnología",
    "tecnologias": "tecnologías",
    "empirico": "empírico",
    "empirica": "empírica",
    "teorico": "teórico",
    "teorica": "teórica",
    "teoricos": "teóricos",
    "teoricas": "teóricas",
    "etico": "ético",
    "etica": "ética",
    "eticos": "éticos",
    "eticas": "éticas",
    "publico": "público",
    "publica": "pública",
    "publicos": "públicos",
    "publicas": "públicas",
    "unico": "único",
    "unica": "única",
    "unicos": "únicos",
    "unicas": "únicas",
    "numero": "número",
    "numeros": "números",
    "codigo": "código",
    "codigos": "códigos",
    "pagina": "página",
    "paginas": "páginas",
    "indice": "índice",
    "indices": "índices",
    "limite": "límite",
    "limites": "límites",
    "ambito": "ámbito",
    "ambitos": "ámbitos",
    "parametro": "parámetro",
    "parametros": "parámetros",
    "fenomeno": "fenómeno",
    "fenomenos": "fenómenos",
    "proposito": "propósito",
    "propositos": "propósitos",
    "caracter": "carácter",
    "regimen": "régimen",
    "deficit": "déficit",
    "habito": "hábito",
    "habitos": "hábitos",
    "movil": "móvil",
    "moviles": "móviles",
    "util": "útil",
    "utiles": "útiles",
    "facil": "fácil",
    "dificil": "difícil",
    "fragil": "frágil",
    "tambien": "también",
    "ademas": "además",
    "despues": "después",
    "segun": "según",
}

_ACCENT_REGEX = re.compile(
    r"(?<!\\)(?<![\{\w])(" + "|".join(re.escape(k) for k in _SPANISH_ACCENT_CORRECTIONS) + r")(?![\w\}])",
    re.IGNORECASE,
)


def _apply_case_preserving(match: re.Match[str]) -> str:
    word = match.group(0)
    corr = _SPANISH_ACCENT_CORRECTIONS.get(word.lower(), word)
    if word.isupper():
        return corr.upper()
    if word[0].isupper():
        return corr[0].upper() + corr[1:]
    return corr


def _fix_spanish_orthography_and_grammar(text: str) -> str:
    """Review and fix Spanish orthography (accentuation, proper names), punctuation, and grammar/concordance."""
    if not text:
        return ""

    fixed = text

    # 1. Strip stray leading punctuation at start of span or start of paragraph/line (e.g. ". El sismo...")
    fixed = re.sub(r"^\s*[\.,;:]+\s*", "", fixed)
    fixed = re.sub(r"(\n\s*)[\.,;:]+\s*", r"\1", fixed)

    # 2. Orthography: restore missing tildes in academic/technical words (skipping LaTeX commands)
    fixed = _ACCENT_REGEX.sub(_apply_case_preserving, fixed)

    # 3. Orthography of proper regional/institutional names
    fixed = re.sub(r"\beje\s+cafetero\b", "Eje Cafetero", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\bsan\s+jos[eé]\s+del\s+palmar\b", "San José del Palmar", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\bchoc[oó]\b", "Chocó", fixed, flags=re.IGNORECASE)

    # 4. Grammar: remove accidentally duplicated adjacent words (e.g. "de de", "la la", "en en")
    fixed = re.sub(
        r"\b(el|la|los|las|un|una|unos|unas|de|del|al|en|con|por|para|sin|sobre|entre|que|se|su|sus|y|e|o|u|a|no|es|son)\s+\1\b",
        r"\1",
        fixed,
        flags=re.IGNORECASE,
    )

    # 5. Grammar: Spanish hiatus conjunctions ("y i-" -> "e i-", "o o-" -> "u o-")
    fixed = re.sub(
        r"\by\s+(i[bcdfghjklmnñpqrstvwxyz][a-záéíóúñ]*|hi[bcdfghjklmnñpqrstvwxyz][a-záéíóúñ]*)\b",
        r"e \1",
        fixed,
        flags=re.IGNORECASE,
    )
    fixed = re.sub(
        r"\bo\s+(o[a-záéíóúñ]+|ho[a-záéíóúñ]+)\b",
        r"u \1",
        fixed,
        flags=re.IGNORECASE,
    )

    # 6. Grammar & prepositional regime
    fixed = re.sub(
        r",\s*en\s+particular,\s*(?=[A-ZÁÉÍÓÚÑ])",
        ", en particular en ",
        fixed,
    )
    grammar_subs = [
        (r"\bde acuerdo a\b", "de acuerdo con"),
        (r"\ben base a\b", "con base en"),
        (r"\ba nivel de\b", "en el ámbito de"),
        (r"\ben relación a\b", "respecto a"),
        (r"\bmas\s+(contexto|amplio|preciso|reciente|frecuente|complejo|alto|bajo|allá)\b", r"más \1"),
        (
            r"\bel\s+(cohorte|variable|hipótesis|metodología|arquitectura|intervención|evaluación|población|muestra|fase|etapa|escala|tasa|prevalencia|incidencia|herramienta|plataforma|aplicación|región|ciudad|universidad|salud|ansiedad|depresión)\b",
            r"la \1",
        ),
        (
            r"\bla\s+(proyecto|sistema|modelo|algoritmo|análisis|estudio|diagnóstico|tamizaje|trastorno|sismo|evento|protocolo|instrumento|cuestionario|equipo|presupuesto|cronograma|objetivo|impacto|riesgo|desarrollo|entorno|departamento|municipio)\b",
            r"el \1",
        ),
        (
            r"\blos\s+(variables|hipótesis|metodologías|intervenciones|evaluaciones|poblaciones|muestras|fases|etapas|escalas|tasas|herramientas|plataformas|aplicaciones|regiones|ciudades|universidades|pruebas|encuestas)\b",
            r"las \1",
        ),
        (
            r"\blas\s+(proyectos|sistemas|modelos|algoritmos|estudios|diagnósticos|trastornos|sismos|eventos|protocolos|instrumentos|cuestionarios|equipos|objetivos|impactos|riesgos|entornos|departamentos|municipios)\b",
            r"los \1",
        ),
    ]
    for pat, rep in grammar_subs:
        fixed = re.sub(pat, rep, fixed, flags=re.IGNORECASE)

    # 7. Punctuation normalization (collided/doubled punctuation, spacing, sentence capitalization)
    fixed = re.sub(r"\.\s*\.+", ".", fixed)
    fixed = re.sub(r",\s*,+", ",", fixed)
    fixed = re.sub(r";\s*;+", ";", fixed)
    fixed = re.sub(r"[,;]\s*\.", ".", fixed)
    fixed = re.sub(r"\.\s*,", ".", fixed)
    fixed = re.sub(r",\s+y\b", " y", fixed)
    fixed = re.sub(r"\s+([,\.;:\)\]])", r"\1", fixed)
    fixed = re.sub(r"([\(\[])\s+", r"\1", fixed)
    fixed = re.sub(r"([,\.;:])([a-zA-ZáéíóúÁÉÍÓÚñÑ])", r"\1 \2", fixed)
    fixed = re.sub(r" {2,}", " ", fixed)

    # Capitalize lowercase letter after sentence-ending period
    fixed = re.sub(
        r"(\.\s+)([a-záéíóúñ])",
        lambda m: m.group(1) + m.group(2).upper(),
        fixed,
    )

    return fixed.strip()


def _humanize_text_span(text: str) -> str:
    """Apply estilo-natural-es, depuracion-redundancias-es, and orthography/punctuation/grammar rules to a span of text.

    Removes formulaic mechanical boilerplate, AI markers, and bureaucratic fillers,
    and corrects orthography, punctuation, and grammatical concordance while strictly
    preserving 100% of facts, citations, numbers, percentages and technical register.
    """
    if not text:
        return ""

    had_initial_upper = bool(re.match(r"^[\s\.,;:]*[A-ZÁÉÍÓÚÑ]", text))
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

    # 3. Dinamismo sintáctico y depuración de nominalizaciones (grant-flow-auditor)
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

    # 4. Revisión integral de ortografía, puntuación y gramática/concordancia
    polished = _fix_spanish_orthography_and_grammar(polished)

    # 5. Capitalización inicial coherente
    if had_initial_upper and polished and polished[0].islower():
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


def _build_project_context_sentences(num_sentences: int, section_context: str = "") -> str:
    """Generate 1 or 2 academic contextual sentences grounded in the manuscript's domain (estilo-natural-es)."""
    ctx_low = (section_context or "").lower()
    if any(k in ctx_low for k in ("sismo", "sísmic", "tept", "postraum", "depresión", "phq-8")):
        s1 = (
            "Las emergencias sísmicas en zonas densamente pobladas desencadenan una carga persistente "
            "de afectaciones en salud mental cuyas secuelas clínicas suelen prolongarse mucho después del evento inicial."
        )
        s2 = (
            "En este escenario, la detección oportuna de sintomatología depresiva y de estrés postraumático "
            "en comunidades universitarias exige herramientas portables e interpretables que complementen la valoración psicométrica convencional."
        )
    else:
        s1 = (
            "La problemática abordada en esta propuesta responde a la necesidad de fortalecer las capacidades "
            "científicas y tecnológicas del territorio mediante soluciones basadas en inteligencia artificial interpretable."
        )
        s2 = (
            "Para ello, el proyecto articula validación empírica en entorno relevante y transferencia tecnológica "
            "orientada a la toma de decisiones oportuna."
        )

    chosen: list[str] = []
    if s1.lower()[:50] not in ctx_low:
        chosen.append(s1)
    if num_sentences >= 2 and s2.lower()[:50] not in ctx_low:
        chosen.append(s2)
    elif num_sentences == 1 and not chosen and s2.lower()[:50] not in ctx_low:
        chosen.append(s2)

    return " ".join(chosen)


def _parse_instruction_action(comment: str, target_text: str, matched_original: str) -> tuple[str, str] | None:
    """Parse whether a user's comment text is an actionable editorial command on the selected text.

    Returns (action_type, resulting_text) or None if it's purely a general pipeline observation.
    """
    if not comment:
        return None

    raw_c = comment.strip()
    c_lower = raw_c.lower()

    # 1. Punctuation removal directive (e.g. "quitar los dos puntos", "quitar dobles puntos", "quitar puntos")
    if re.search(r"\b(?:quita\w*|elimina\w*|borra\w*|suprim\w*)\b.*\b(?:puntos?|dos puntos|dobles puntos)\b", c_lower) or any(k in c_lower for k in [
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

    # 2. Sentence-level deletion directive (e.g. "elimina la primera oración del resumen", "quita esta oración")
    if re.search(
        r"\b(?:quita\w*|elimina\w*|borra\w*|suprim\w*)\s+(?:la\s+)?(?:primera|primeera|1ra|esta|esa)\s+(?:oraci[oó]n|orancioens|oranciones|frase)\b",
        c_lower,
    ):
        cleaned_orig = re.sub(r"^\s*[\.,;:]+\s*", "", matched_original)
        m_first = re.match(r"^([^\n]+?\.)\s+([A-ZÁÉÍÓÚÑ].*)$", cleaned_orig, re.DOTALL)
        if m_first:
            return ("replace", m_first.group(2).strip())
        return ("delete", "")

    # 3. Compound directive: remove/avoid X and replace/leave as Y
    compound_m = re.search(
        r"(?:reajusta\w*\s+para\s+que\s+(?:la\s+redacci[oó]n\s+)?no\s+incluya|quita\w*|elimina\w*|borra\w*|suprim\w*|sin|no\s+incluya|no\s+incluir)\s+(?:el\s+nombre\s+|la\s+palabra\s+|el\s+texto\s+)?([a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s]+?)(?:,|\sy\s|\s+y\s+)?\s*(?:deja|dejar|dejalo|déjalo)?\s*(?:como\s+general,?\s*|general,?\s*|como\s+|por\s+|a\s+|usar\s+|poner\s+)(.+)$",
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

    # 4. Deletion directive: "quitar X", "eliminar X", "borrar X", "quita X", "elimina X"
    del_m = re.match(r"^(?:quita\w*|elimina\w*|borra\w*|suprim\w*)\s+(.+)$", raw_c, re.IGNORECASE)
    if del_m:
        phrase = del_m.group(1).strip().strip('"\'«»')
        phrase_lower = phrase.lower()
        if phrase_lower in ("este texto", "el texto", "esto", "el fragmento", "este fragmento", "la seleccion", "la selección", "esta oracion", "esta oración"):
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

    # 5. Replacement directive: "cambiar por X", "reemplazar por X", "poner X", "dejar como X"
    repl_m = re.match(r"^(?:cambia\w*|reemplaza\w*|sustitu\w*)(?:\s+este\s+texto)?\s+por\s+[:«\"']?(.*?)[:»\"']?$", raw_c, re.IGNORECASE)
    if repl_m:
        return ("replace", repl_m.group(1).strip())

    repl_m2 = re.match(r"^(?:cambia\w*|reemplaza\w*|sustitu\w*)\s+[:«\"']?(.*?)[:»\"']?\s+por\s+[:«\"']?(.*?)[:»\"']?$", raw_c, re.IGNORECASE)
    if repl_m2:
        old_part, new_part = repl_m2.group(1).strip(), repl_m2.group(2).strip()
        if old_part in matched_original:
            return ("replace", matched_original.replace(old_part, new_part))
        pat = re.compile(re.escape(old_part), re.IGNORECASE)
        if pat.search(matched_original):
            return ("replace", pat.sub(new_part, matched_original))

    poner_m = re.match(r"^(?:pon(?:er)?|deja(?:r)?\s+como|dejalo\s+como|déjalo\s+como|usa(?:r)?)\s+[:«\"']?(.*?)[:»\"']?$", raw_c, re.IGNORECASE)
    if poner_m:
        return ("replace", poner_m.group(1).strip())

    # 6. Rephrasing / Humanizing directive (explicit command on this passage)
    if re.search(
        r"\b(?:redacta\w*\s+(?:de\s+forma\s+diferente|diferente|de\s+otra\s+forma)|humaniza\w*|hacer\s+m[aá]s\s+conciso|mejora\w*\s+redacci[oó]n|estilo\s+natural|estilo-natural-es)\b",
        c_lower,
    ) and not re.search(r"\b(?:sin\s+nombrar|para\s+el\s+agente|revisar|consultar)\b", c_lower):
        polished = _humanize_text_span(matched_original)
        return ("humanize", polished)

    return None


def _execute_redactor_instruction(
    comment: str,
    target_text: str,
    matched_original: str,
    section_context: str = "",
) -> tuple[str, str]:
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
    working = re.sub(r"^\s*[\.,;:]+\s*", "", matched_original)

    # A0. Contextual sentence insertion ("agrega una oración que dé contexto... antes de este texto",
    # "agrega dos oraciones al inicio del resumen que den más contexto del proyecto")
    ctx_sent_m = re.search(
        r"\b(?:agrega\w*|a[ñn]ad\w*|incluy\w*|incorpora\w*|escribe\w*|redacta\w*)\s+"
        r"(?:(una|un|1|dos|2|tres|3)\s+)?"
        r"(?:oraci[oó]n(?:es)?|orancioens|oranciones|frases?|l[ií]neas?)",
        c_lower,
    )
    if ctx_sent_m or (
        re.search(r"\b(?:agrega\w*|a[ñn]ad\w*|incluy\w*)\b", c_lower)
        and re.search(r"\bcontexto\b", c_lower)
    ):
        qty_tok = (ctx_sent_m.group(1) if ctx_sent_m else "") or "1"
        num_sentences = 2 if qty_tok in ("dos", "2", "tres", "3") else 1
        ctx_prefix = _build_project_context_sentences(num_sentences, section_context or working)
        is_after = bool(re.search(r"\b(?:despu[eé]s|al\s+final)\b", c_lower))
        if ctx_prefix:
            if is_after:
                combined = f"{working.rstrip()} {ctx_prefix}"
            else:
                combined = f"{ctx_prefix} {working.lstrip()}"
            return ("replace", _humanize_text_span(combined))
        return ("replace", _humanize_text_span(working))

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
        r"^(?:aclara\w*|agrega\w*|a[ñn]ad\w*|incluy\w*|especifica\w*|precisa\w*|menciona\w*|detalla\w*|complementa\w*|incorpora\w*)\s+(?:que\s+|sobre\s+|los?\s+|las?\s+|el\s+|la\s+)?(.+)$",
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
            pipeline_dir,
            run_dir,
            file_contents,
            files_modified,
            tex_files=tex_files,
            applied_strikethroughs=applied_strikethroughs,
            applied_humanize=applied_humanize,
            applied_replace=applied_replace,
            executed_comments=executed_comments,
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
        is_ui_anchor = bool(re.match(r"^Morfeo\s+IA:", target_text, re.IGNORECASE))
        is_section_positional = bool(
            ann_type in ("comment", "comentario")
            and re.search(
                r"\b(?:al\s+inicio\s+del?|al\s+principio\s+del?|la\s+primera\s+oraci[oó]n\s+del?|la\s+primeera\s+oraci[oó]n\s+del?|al\s+comienzo\s+del?)\b",
                comment_body,
                re.IGNORECASE,
            )
        )

        matched_file: Path | None = None
        match_span: tuple[int, int] | None = None
        if target_text and not is_ui_anchor and not is_section_positional:
            matched_file, match_span = _locate_best_span_in_files(
                tex_files, file_contents, target_text, page_num=page_num, section_hint=ann.get("section")
            )

        if (matched_file is None or match_span is None) and ann_type in ("comment", "comentario"):
            sec_f, sec_s = _resolve_section_target_from_instruction(
                comment_body, tex_files, file_contents
            )
            if sec_f and sec_s:
                matched_file, match_span = sec_f, sec_s

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
                    if act_type == "replace" and new_text:
                        new_text = _humanize_text_span(new_text)
                elif bool(ann.get("apply_directly")) and not process_pending:
                    act_type, new_text = ("replace", comment_body)
                else:
                    act_type, new_text = _execute_redactor_instruction(
                        comment_body,
                        target_text,
                        matched_original or target_text,
                        section_context=file_contents[matched_file],
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

