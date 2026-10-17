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
    # Escape each word
    escaped = [re.escape(w) for w in words]
    # Join with flexible whitespace pattern
    return r"\s+".join(escaped)


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
    """Anexa al archivo de pendientes las instrucciones que aún no estaban.

    Devuelve la ruta del archivo y cuántas entradas nuevas se escribieron. El
    archivo se anexa con `open(..., "a")` en lugar de reescribirse: una
    instrucción sin ejecutar no se puede recuperar de ningún otro sitio, y
    `write_text` trunca primero, de modo que un fallo a mitad de la escritura
    perdería todo lo anterior. Anexar no toca los bytes que ya están, así que
    tampoco un segundo escritor puede borrar lo que otro ya dejó.
    """
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
    
    Removes formulaic mechanical boilerplate while preserving 100% of facts,
    citations, numbers, percentages and technical register.
    """
    polished = text

    # Formulaic bureaucratic opening phrases to eliminate or streamline
    fillers = [
        (r"\bEs importante destacar que\s*", ""),
        (r"\bCabe resaltar que\s*", ""),
        (r"\bEs menester señalar que\s*", ""),
        (r"\bVale la pena mencionar que\s*", ""),
        (r"\bEs necesario subrayar que\s*", ""),
        (r"\bEn este sentido,\s*", ""),
        (r"\bPor su parte,\s*", ""),
        (r"\bDe manera similar,\s*", "Asimismo, "),
        (r"\bPor consiguiente,\s*", "Así, "),
        (r"\bEn virtud de lo anterior,\s*", "Por ello, "),
        (r"\bCon el propósito de\b", "Para"),
        (r"\bCon el fin de\b", "Para"),
        (r"\ba través de la utilización de\b", "mediante"),
        (r"\bcon el objeto de\b", "para"),
    ]

    for pat, rep in fillers:
        polished = re.sub(pat, rep, polished, flags=re.IGNORECASE)

    # Clean up any resulting double spaces or awkward punctuation
    polished = re.sub(r" {2,}", " ", polished)
    polished = re.sub(r"\s+([,\.;:])", r"\1", polished)

    # Capitalize sentence starts if a leading filler was stripped at beginning
    if text and text[0].isupper() and polished and polished[0].islower():
        polished = polished[0].upper() + polished[1:]

    return polished.strip()


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

        words = _normalize_words(target_text)
        if not words:
            # Sin texto ancla la anotación no puede nombrar a qué se refiere ni
            # hay pasaje que buscar. Antes se descartaba en silencio; ahora el
            # fallo queda a la vista del operador.
            failed_annotations.append({
                "id": ann_id,
                "type": ann_type,
                "text": target_text,
                "page": page_num,
                "reason": "Anotación sin texto ancla: no hay pasaje que localizar",
            })
            continue

        # Search for target text in all candidate files
        # Try progressively smaller subsets of words if exact match fails
        matched_file: Path | None = None
        match_span: tuple[int, int] | None = None

        search_lengths = [len(words)]
        if len(words) > 8:
            search_lengths.extend([len(words) - 1, 6])

        for w_len in search_lengths:
            cur_words = words[:w_len]
            regex_pat = _build_fuzzy_regex(cur_words)
            for tf in tex_files:
                content = file_contents[tf]
                m = re.search(regex_pat, content, re.IGNORECASE)
                if m:
                    matched_file = tf
                    match_span = m.span()
                    break
            if matched_file:
                break

        matched_original = (
            file_contents[matched_file][match_span[0]:match_span[1]]
            if matched_file and match_span
            else None
        )

        # Un comentario no reescribe prosa: no toca la fuente y viaja al agente
        # del pipeline como instrucción pendiente. Se registra aunque el ancla no
        # se localice, porque una instrucción sigue siendo válida sin ella; lo
        # que exigía ancla era la línea `%` que se insertaba antes.
        if ann_type in ("comment", "comentario"):
            registered_comments.append({
                "id": ann.get("id", str(idx + 1)),
                "file": str(matched_file.relative_to(run_dir)) if matched_file else None,
                "page": page_num,
                "target_text": matched_original if matched_original else target_text,
                "comment": comment_body,
                "located": bool(matched_file),
            })
            continue

        if not matched_file or not match_span:
            failed_annotations.append({
                "id": ann.get("id", str(idx + 1)),
                "type": ann_type,
                "text": target_text,
                "page": page_num,
                "reason": "Texto no localizado en las secciones LaTeX fuente",
            })
            continue

        content = file_contents[matched_file]
        start, end = match_span

        if ann_type in ("strikethrough", "tachar", "delete"):
            # Quitar únicamente el texto explícitamente tachado sin reescribir ni humanizar el resto
            prefix = content[:start]
            suffix = content[end:]
            # Limpiar solo el espacio doble en la juntura exacta del corte
            if prefix.endswith(" ") and suffix.startswith(" "):
                suffix = suffix[1:]
            new_content = prefix + suffix
            file_contents[matched_file] = new_content
            files_modified.add(matched_file)
            applied_strikethroughs.append({
                "id": ann.get("id", str(idx + 1)),
                "file": str(matched_file.relative_to(run_dir)),
                "page": page_num,
                "original_text": matched_original,
            })

        elif ann_type in ("humanize", "humanizar"):
            # Aplicar pulido con skill estilo-natural-es
            polished_text = _humanize_text_span(matched_original)
            new_content = content[:start] + polished_text + content[end:]
            file_contents[matched_file] = new_content
            files_modified.add(matched_file)
            applied_humanize.append({
                "id": ann.get("id", str(idx + 1)),
                "file": str(matched_file.relative_to(run_dir)),
                "page": page_num,
                "original_text": matched_original,
                "polished_text": polished_text,
            })

        elif ann_type in ("replace", "reemplazar"):
            # Reemplazo determinista: el texto literal que escribió el operador
            # sustituye el pasaje anclado. Ningún modelo interviene aquí.
            raw_replacement = ann.get("replacement")
            replacement = "" if raw_replacement is None else str(raw_replacement)
            delete_intent = bool(ann.get("delete_intent"))
            if replacement.strip() == "" and not delete_intent:
                failed_annotations.append({
                    "id": ann.get("id", str(idx + 1)),
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
            applied_replace.append({
                "id": ann.get("id", str(idx + 1)),
                "file": str(matched_file.relative_to(run_dir)),
                "page": page_num,
                "original_text": matched_original,
                "replacement": replacement,
                "deleted": replacement == "",
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
