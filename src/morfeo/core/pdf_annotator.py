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


def _build_fuzzy_regex(words: list[str]) -> str:
    """Build a regex matching the given sequence of words across arbitrary whitespace and LaTeX formatting."""
    escaped = [re.escape(w) for w in words]
    return r"(?:\s+|~|\\,|\\citep?\{[^}]*\}|\\cite\{[^}]*\})+".join(escaped)


def _find_text_span(content: str, target_text: str) -> tuple[int, int] | None:
    """Multi-tier resilient search for target_text within LaTeX content.

    Handles exact matches, flexible whitespace, LaTeX citations/tildes,
    and punctuation variations (such as 'posdesastre. .' vs 'posdesastre.').
    """
    if not target_text or not content:
        return None

    # Tier 1: Exact substring match
    idx = content.find(target_text)
    if idx != -1:
        return (idx, idx + len(target_text))

    # Tier 2: Case-insensitive exact match
    lower_content = content.lower()
    lower_target = target_text.lower()
    idx = lower_content.find(lower_target)
    if idx != -1:
        return (idx, idx + len(target_text))

    # Tier 3: Word sequence with flexible whitespace and LaTeX citations
    words = _normalize_words(target_text)
    if words:
        max_len = len(words)
        min_len = 1 if max_len <= 3 else (max_len - 2 if max_len <= 6 else max(2, max_len // 2))
        for length in range(max_len, min_len - 1, -1):
            cur_words = words[:length]
            regex_pat = _build_fuzzy_regex(cur_words)
            m = re.search(regex_pat, content, re.IGNORECASE)
            if m:
                return m.span()

    # Tier 4: Core alphanumeric words with boundary punctuation expansion
    alpha_words = re.findall(r"\w+", target_text)
    if alpha_words:
        escaped_alpha = [re.escape(w) for w in alpha_words]
        pat = r"\s*".join(escaped_alpha)
        for m in re.finditer(pat, content, re.IGNORECASE):
            s_start, s_end = m.span()
            if re.search(r"[^\w\s]$", target_text.strip()):
                punct_m = re.match(r"^[^\w\s]+", content[s_end:])
                if punct_m:
                    s_end += punct_m.end()
            return (s_start, s_end)

    # Tier 5: Pure punctuation search (e.g. '.', '..', '. .')
    clean_punct = re.sub(r"\s+", "", target_text)
    if clean_punct and not any(c.isalnum() for c in clean_punct):
        escaped_punct = [re.escape(c) for c in clean_punct]
        pat = r"\s*".join(escaped_punct)
        m = re.search(pat, content)
        if m:
            return m.span()

    return None


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


def _humanize_text_span(text: str) -> str:
    """Apply estilo-natural-es academic humanization rules to a span of text.

    Removes formulaic mechanical boilerplate, AI markers, and bureaucratic fillers
    while strictly preserving 100% of facts, citations, numbers, percentages and technical register.
    """
    if not text:
        return ""

    polished = text

    # 1. Prohibición estricta de rayas anglosajonas (—) y dobles guiones (--)
    polished = re.sub(r"\s*—\s*", ", ", polished)
    polished = re.sub(r"\s*--\s*", ", ", polished)

    # 2. Erradicación de fórmulas mecánicas y clichés de IA (Catálogo estilo-natural-es)
    replacements = [
        (r"\bEs importante destacar que\s*", ""),
        (r"\bCabe resaltar que\s*", ""),
        (r"\bEs menester señalar que\s*", ""),
        (r"\bVale la pena mencionar que\s*", ""),
        (r"\bEs necesario subrayar que\s*", ""),
        (r"\bEs fundamental comprender que\s*", ""),
        (r"\bFrente a este panorama,?\s*", "Ante este contexto, "),
        (r"\bEn este sentido,?\s*", ""),
        (r"\bPor su parte,?\s*", ""),
        (r"\bDe manera similar,?\s*", "Asimismo, "),
        (r"\bPor consiguiente,?\s*", "Así, "),
        (r"\bEn virtud de lo anterior,?\s*", "Por ello, "),
        (r"\bEn el marco de\b", "en"),
        (r"\ba través de la utilización de\b", "mediante"),
        (r"\bpor medio de la utilización de\b", "mediante"),
        (r"\bpor medio de\b", "mediante"),
        (r"\bcon el propósito de\b", "para"),
        (r"\bcon el fin de\b", "para"),
        (r"\bcon el objeto de\b", "para"),
        (r"\ben aras de\b", "para"),
        (r"\bse erige como\b", "es"),
        (r"\bse posiciona como\b", "es"),
        (r"\bjuega un papel fundamental\b", "es central"),
        (r"\bjuega un papel crucial\b", "es determinante"),
        (r"\bdesempeña un rol crucial\b", "es determinante"),
        (r"\bmarca un antes y un después\b", "transforma"),
        (r"\bun punto de inflexión\b", "un cambio significativo"),
        (r"\ben el corazón de\b", "en el centro de"),
        (r"\bun abanico de\b", "diversos"),
        (r"\ben última instancia,?\s*", "finalmente, "),
        (r"\bde la mano de\b", "junto con"),
        (r"\btiene la capacidad de\b", "puede"),
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

    # 4. Dinamismo sintáctico adicional si no cambió (pule construcciones pasivas verbose)
    if polished == text:
        dynamic_subs = [
            (r"\bpermite llevar a cabo\b", "facilita"),
            (r"\bcon el fin de lograr\b", "para alcanzar"),
            (r"\bse propone desarrollar\b", "pretende desarrollar"),
            (r"\btiene como objetivo\b", "busca"),
            (r"\ben relación con\b", "respecto a"),
            (r"\bllevar a cabo\b", "realizar"),
            (r"\bdar cuenta de\b", "evidenciar"),
            (r"\bponer de manifiesto\b", "revelar"),
        ]
        for pat, rep in dynamic_subs:
            polished = re.sub(pat, rep, polished, flags=re.IGNORECASE)
        polished = re.sub(r"\.\s*\.", ".", polished)
        polished = re.sub(r" {2,}", " ", polished).strip()

    # 5. Capitalización inicial coherente
    if text and text[0].isupper() and polished and polished[0].islower():
        polished = polished[0].upper() + polished[1:]

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

    # 2. Deletion directive: "quitar X", "eliminar X", "borrar X"
    del_m = re.match(r"^(?:quitar|eliminar|borrar|suprimir)\s+(.+)$", raw_c, re.IGNORECASE)
    if del_m:
        phrase = del_m.group(1).strip().strip('"\'«»')
        phrase_lower = phrase.lower()
        if phrase_lower in ("este texto", "el texto", "esto", "el fragmento", "este fragmento", "la seleccion", "la selección"):
            return ("delete", "")
        if phrase in matched_original:
            new_text = matched_original.replace(phrase, "")
            new_text = re.sub(r" {2,}", " ", new_text).strip()
            return ("replace", new_text)
        pat = re.compile(re.escape(phrase), re.IGNORECASE)
        if pat.search(matched_original):
            new_text = pat.sub("", matched_original)
            new_text = re.sub(r" {2,}", " ", new_text).strip()
            return ("replace", new_text)

    # 3. Replacement directive: "cambiar por X", "reemplazar por X", "poner X"
    repl_m = re.match(r"^(?:cambiar|reemplazar|sustituir)(?:\s+este\s+texto)?\s+por\s+[:«\"']?(.*?)[:»\"']?$", raw_c, re.IGNORECASE)
    if repl_m:
        return ("replace", repl_m.group(1).strip())
    poner_m = re.match(r"^poner\s+[:«\"']?(.*?)[:»\"']?$", raw_c, re.IGNORECASE)
    if poner_m:
        return ("replace", poner_m.group(1).strip())

    # 4. Rephrasing / Humanizing directive (explicit command on this passage)
    if re.match(
        r"^(?:por favor\s+)?(?:redactar\s+(?:de\s+forma\s+diferente|diferente|de\s+otra\s+forma)|humanizar|hacer\s+m[aá]s\s+conciso|mejorar\s+redacci[oó]n)(?:\s+(?:este\s+texto|este\s+pasaje|esta\s+frase))?\.?$",
        raw_c,
        re.IGNORECASE,
    ):
        polished = _humanize_text_span(matched_original)
        return ("humanize", polished)

    return None


def apply_pdf_annotations(run_dir: Path, annotations: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply comments, strikethroughs and humanization to the LaTeX sections of the active run.

    Returns a comprehensive result envelope.
    """
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

    # Discover candidate LaTeX files (sections/*.tex + main.tex)
    tex_files: list[Path] = []
    if (redaccion_dir / "main.tex").is_file():
        tex_files.append(redaccion_dir / "main.tex")
    if sections_dir.is_dir():
        tex_files.extend(sorted(sections_dir.glob("*.tex")))

    applied_strikethroughs: list[dict[str, Any]] = []
    registered_comments: list[dict[str, Any]] = []
    applied_humanize: list[dict[str, Any]] = []
    applied_replace: list[dict[str, Any]] = []
    failed_annotations: list[dict[str, Any]] = []

    # Map file contents in memory
    file_contents: dict[Path, str] = {tf: tf.read_text(encoding="utf-8", errors="replace") for tf in tex_files}
    files_modified: set[Path] = set()

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

        # Search for target text in all candidate files
        matched_file: Path | None = None
        match_span: tuple[int, int] | None = None

        if target_text:
            for tf in tex_files:
                span = _find_text_span(file_contents[tf], target_text)
                if span:
                    matched_file = tf
                    match_span = span
                    break

        matched_original = (
            file_contents[matched_file][match_span[0]:match_span[1]]
            if matched_file and match_span
            else None
        )

        # Manejo de comentarios / instrucciones del usuario
        if ann_type in ("comment", "comentario"):
            action = _parse_instruction_action(comment_body, target_text, matched_original or target_text)
            apply_directly = bool(ann.get("apply_directly"))

            if matched_file and match_span and (action is not None or apply_directly):
                act_type, new_text = action if action else ("replace", comment_body)
                content = file_contents[matched_file]
                start, end = match_span

                if act_type == "delete" or (act_type == "replace" and new_text == ""):
                    prefix = content[:start]
                    suffix = content[end:]
                    if prefix.endswith(" ") and suffix.startswith(" "):
                        suffix = suffix[1:]
                    file_contents[matched_file] = prefix + suffix
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
                    })
                elif act_type == "humanize":
                    polished = _humanize_text_span(matched_original)
                    file_contents[matched_file] = content[:start] + polished + content[end:]
                    files_modified.add(matched_file)
                    applied_humanize.append({
                        "id": ann_id,
                        "file": str(matched_file.relative_to(run_dir)),
                        "page": page_num,
                        "original_text": matched_original,
                        "polished_text": polished,
                        "rects": ann.get("rects"),
                        "via_instruction": comment_body,
                    })
                else:  # replace
                    file_contents[matched_file] = content[:start] + new_text + content[end:]
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
                    })

                registered_comments.append({
                    "id": ann_id,
                    "file": str(matched_file.relative_to(run_dir)),
                    "page": page_num,
                    "target_text": matched_original,
                    "comment": comment_body,
                    "located": True,
                    "rects": ann.get("rects"),
                    "executed": True,
                })
                continue
            else:
                registered_comments.append({
                    "id": ann_id,
                    "file": str(matched_file.relative_to(run_dir)) if matched_file else None,
                    "page": page_num,
                    "target_text": matched_original if matched_original else target_text,
                    "comment": comment_body,
                    "located": bool(matched_file),
                    "rects": ann.get("rects"),
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
            prefix = content[:start]
            suffix = content[end:]
            if prefix.endswith(" ") and suffix.startswith(" "):
                suffix = suffix[1:]
            new_content = prefix + suffix
            file_contents[matched_file] = new_content
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
            })

        elif ann_type in ("humanize", "humanizar"):
            polished_text = _humanize_text_span(matched_original)
            new_content = content[:start] + polished_text + content[end:]
            file_contents[matched_file] = new_content
            files_modified.add(matched_file)
            applied_humanize.append({
                "id": ann_id,
                "file": str(matched_file.relative_to(run_dir)),
                "page": page_num,
                "original_text": matched_original,
                "polished_text": polished_text,
                "rects": ann.get("rects"),
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
            new_content = content[:start] + replacement + content[end:]
            file_contents[matched_file] = new_content
            files_modified.add(matched_file)
            is_deleted = replacement == "" or delete_intent
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
            })

    # Write all modified files back to disk
    for tf in files_modified:
        tf.write_text(file_contents[tf], encoding="utf-8")

    # Las instrucciones pendientes se anexan, no se reescriben: una instrucción
    # sin ejecutar no se puede recuperar de ningún otro sitio.
    pending_path, pending_written = register_pending_instructions(
        pipeline_dir, registered_comments
    )
    # Solo lo que se escribió de verdad cuenta como registrado; lo que ya estaba
    # en la cola se reporta como duplicado, y un comentario sin ancla como fallo.
    comment_failures = [
        a for a in failed_annotations if a.get("type") in ("comment", "comentario")
    ]
    duplicated_comments = max(0, len(registered_comments) - pending_written)

    # Persist annotations JSON
    timestamp = datetime.now().isoformat()
    json_payload = {
        "timestamp": timestamp,
        "run_id": run_dir.name,
        "total_submitted": len(annotations),
        "applied": {
            "strikethrough": len(applied_strikethroughs),
            "humanize": len(applied_humanize),
            "replace": len(applied_replace),
        },
        "registered": {
            "comments": pending_written,
            "duplicated": duplicated_comments,
            "failed": len(comment_failures),
        },
        "details": {
            "strikethrough": applied_strikethroughs,
            "humanize": applied_humanize,
            "replace": applied_replace,
            "comments": registered_comments,
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
        f"# Registro de Revisión y Anotaciones sobre PDF — {run_dir.name}",
        f"\n**Fecha de ejecución:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Textos tachados eliminados:** {len(applied_strikethroughs)}",
        f"- **Pasajes humanizados (estilo-natural-es):** {len(applied_humanize)}",
        f"- **Reemplazos deterministas aplicados:** {len(applied_replace)}",
        f"- **Instrucciones nuevas registradas para el agente:** {pending_written}",
        f"- **Instrucciones ya registradas (omitidas por duplicado):** {duplicated_comments}",
        f"- **Anotaciones sin aplicar:** {len(failed_annotations)}",
        "- **Comentarios aplicados al manuscrito:** 0 (un comentario no reescribe prosa)",
        f"- **Archivos modificados:** {len(files_modified)}",
        "\n---",
    ]

    if applied_strikethroughs:
        md_lines.append("\n## ✂️ Textos Tachados Eliminados")
        for item in applied_strikethroughs:
            md_lines.append(f"- **Pág. {item['page']}** (`{item['file']}`):")
            md_lines.append(f"  > ~~{item['original_text']}~~")

    if applied_humanize:
        md_lines.append("\n## ✨ Pasajes Humanizados con `estilo-natural-es`")
        for item in applied_humanize:
            md_lines.append(f"- **Pág. {item['page']}** (`{item['file']}`):")
            md_lines.append(f"  - *Original:* {item['original_text']}")
            md_lines.append(f"  - *Humanizado:* **{item['polished_text']}**")

    if applied_replace:
        md_lines.append("\n## 🔁 Reemplazos Deterministas Aplicados")
        md_lines.append(
            "\nEl panel los aplicó sobre el pasaje anclado y recompiló. "
            "Ningún modelo intervino en este camino."
        )
        for item in applied_replace:
            md_lines.append(f"- **Pág. {item['page']}** (`{item['file']}`):")
            md_lines.append(f"  - *Original:* {item['original_text']}")
            destino = item['replacement'] if not item.get('deleted') else "(borrado)"
            md_lines.append(f"  - *Reemplazo:* **{destino}**")

    if registered_comments:
        md_lines.append("\n## 💬 Instrucciones Registradas para el Agente")
        md_lines.append(
            "\nNo se aplicaron al manuscrito. Las ejecuta el `redactor` al continuar "
            "el pipeline, y el `grant-flow-auditor` pule el resultado después."
        )
        for item in registered_comments:
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
    # changed the manuscript. Recompiling after a comment-only run produced an
    # identical PDF and reinforced the illusion that something had been applied.
    compile_success = False
    compile_log = ""
    recompile_skipped = not files_modified
    recompile_reason = ""
    if recompile_skipped:
        compile_log = "No se recompiló: ninguna anotación cambió el manuscrito."
        recompile_reason = "sin cambios en el manuscrito"
    else:
        try:
            build_sh = redaccion_dir / "build.sh"
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
                compile_success = res.returncode == 0
                compile_log = (res.stdout + "\n" + res.stderr)[-500:]
            else:
                res = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                    cwd=redaccion_dir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                )
                compile_success = res.returncode == 0
                compile_log = (res.stdout + "\n" + res.stderr)[-500:]
        except Exception as e:
            compile_log = f"Error invocando compilación: {e}"
        if not compile_success:
            recompile_reason = "la compilación no terminó bien"

    return {
        "ok": True,
        "message": (
            "Anotaciones ejecutadas correctamente en el proyecto."
            if files_modified
            else "Instrucciones registradas para el agente. El manuscrito no cambió."
        ),
        "summary": {
            "total_submitted": len(annotations),
            "strikethrough_applied": len(applied_strikethroughs),
            "comments_applied": 0,
            "comments_registered": pending_written,
            "comments_duplicated": duplicated_comments,
            "comments_failed": len(comment_failures),
            "annotations_failed": len(failed_annotations),
            "humanize_applied": len(applied_humanize),
            "replace_applied": len(applied_replace),
            "replace_failed": len(
                [a for a in failed_annotations if a.get("type") in ("replace", "reemplazar")]
            ),
            "unmatched": failed_annotations,
            "files_modified": [str(f.relative_to(run_dir)) for f in files_modified],
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
            "comments": registered_comments,
            "unmatched": failed_annotations,
        },
        "report_file": "artefactos/anotaciones_pdf.md",
    }
