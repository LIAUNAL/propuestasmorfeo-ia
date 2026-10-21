#!/usr/bin/env python3
"""Deterministic PDF intake for insumos-observador (Phase 0).

Converts one PDF to Markdown with page markers, triaging every page first so
the agent knows which pages lack a text layer (scanned) or carry math, and
which ones it should open visually instead of trusting the extracted text.

Engines, best first (``--engine auto``), all free of revenue or field-of-use
limits (PyMuPDF is AGPL and Marker restricts commercial use, so neither is used):
  pdfium     pypdfium2 (BSD-3/Apache-2.0, Chrome's PDFium): fast text per page;
             pdfplumber (MIT), when installed, adds Markdown tables.
             Run with: uv run --no-project --with pdfplumber python scripts/pdf_to_md.py ...
  pdftotext  poppler CLI, stdlib-only path (``-layout`` keeps table columns).
OCR (``--ocr auto``) runs only on low-text pages, through the tesseract and
pdftoppm CLIs when both are installed; otherwise those pages are listed in
``needs_visual_pages`` for the agent to open with Read (pages=...) or pixelshot.

Results are cached in ``--cache-dir`` as ``<sha256>.md`` + ``<sha256>.json``;
an identical rerun (same file bytes, engine, settings) does no extraction.
Token counts are estimates (characters / 4), not tokenizer output.

PDF text is untrusted input: it is written to a file, never executed.

Exit codes: 0 converted (possibly with flagged pages), 2 bad input or
unreadable PDF or invalid option, 3 no engine available.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = "1"
CHARS_PER_TOKEN = 4
# Characters that rarely appear in prose but often in formulas: Latin-1 math
# signs, Greek, and the Unicode math operator / arrow / letterlike blocks.
MATH_RE = re.compile(r"[±×÷µ°¬Α-ω←-⇿∀-⋿⨀-⫿\U0001d400-\U0001d7ff]")


class InputError(Exception):
    pass


# ---------------------------------------------------------------- engines


def _pdfium():
    import pypdfium2  # ImportError means the engine is unavailable

    return pypdfium2


def _engine_available(name: str) -> bool:
    if name == "pdfium":
        try:
            _pdfium()
        except ImportError:
            return False
        return True
    return shutil.which("pdftotext") is not None and shutil.which("pdfinfo") is not None


def _resolve_engine(requested: str) -> str:
    candidates = ["pdfium", "pdftotext"] if requested == "auto" else [requested]
    for name in candidates:
        if _engine_available(name):
            return name
    raise LookupError(
        "no PDF engine available: install poppler (pdftotext) or run under "
        "`uv run --no-project --with pdfplumber python scripts/pdf_to_md.py ...`"
    )


def _engine_version(engine: str) -> str:
    if engine == "pdfium":
        version = f"pypdfium2 {_pdfium().version.PYPDFIUM_INFO}"
        if importlib.util.find_spec("pdfplumber"):
            import pdfplumber

            version += f" + pdfplumber {pdfplumber.__version__}"
        return version
    out = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True)
    lines = (out.stderr or out.stdout).strip().splitlines()
    return lines[0] if lines else "pdftotext"


def _plain_pages(pdf: Path, engine: str) -> list[str]:
    """Text of every page, used both for triage and as the page body."""
    if engine == "pdfium":
        pdfium = _pdfium()
        try:
            doc = pdfium.PdfDocument(str(pdf))
        except pdfium.PdfiumError as exc:
            raise InputError(f"unreadable PDF: {exc}") from exc
        try:
            return [doc[i].get_textpage().get_text_bounded() for i in range(len(doc))]
        finally:
            doc.close()
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
    match = re.search(r"^Pages:\s+(\d+)", info.stdout, re.M)
    if info.returncode != 0 or not match:
        raise InputError(f"unreadable PDF: {info.stderr.strip() or 'pdfinfo failed'}")
    count = int(match.group(1))
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True)
    pages = text.stdout.split("\f")
    return (pages + [""] * count)[:count]


def _table_markdown(rows: list[list]) -> str:
    def cell(value) -> str:
        return " ".join(str(value or "").split()).replace("|", "\\|")

    width = max(len(row) for row in rows)
    rows = [[cell(c) for c in row] + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return "\n".join(lines)


def _tables(pdf: Path, pages: list[int]) -> dict[int, list[str]]:
    """Markdown tables per page via pdfplumber (MIT), only when it is installed."""
    if not importlib.util.find_spec("pdfplumber"):
        return {}
    import pdfplumber

    found: dict[int, list[str]] = {}
    with pdfplumber.open(str(pdf)) as doc:
        for p in pages:
            tables = [t for t in doc.pages[p - 1].extract_tables() if t and any(any(c for c in r) for r in t)]
            if tables:
                found[p] = [_table_markdown(t) for t in tables]
    return found


def _ocr_languages() -> str:
    out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True)
    have = set(out.stdout.split())
    langs = [lang for lang in ("spa", "eng") if lang in have]
    return "+".join(langs) or "eng"


def _ocr_page(pdf: Path, page: int, langs: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        prefix = Path(tmp) / "p"
        subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", "200", "-png", str(pdf), str(prefix)],
                       capture_output=True, check=False, timeout=120)
        images = sorted(Path(tmp).glob("p*.png"))
        if not images:
            return ""
        out = subprocess.run(["tesseract", str(images[0]), "-", "-l", langs],
                             capture_output=True, text=True, timeout=300)
        return out.stdout.strip()


# ---------------------------------------------------------------- pipeline


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_range(spec: str | None, count: int) -> list[int]:
    if not spec:
        return list(range(1, count + 1))
    pages: list[int] = []
    for part in spec.split(","):
        start, _, end = part.strip().partition("-")
        try:
            lo, hi = int(start), int(end or start)
        except ValueError as exc:
            raise InputError(f"invalid --pages value: {spec!r}") from exc
        if lo < 1 or hi < lo or hi > count:
            raise InputError(f"invalid --pages value {spec!r}: the document has {count} pages")
        pages.extend(p for p in range(lo, hi + 1) if p not in pages)
    return pages


def _tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def _compact_ranges(pages: list[int]) -> str:
    spans: list[str] = []
    for p in pages:
        if spans and int(spans[-1].split("-")[-1]) == p - 1:
            spans[-1] = f"{spans[-1].split('-')[0]}-{p}"
        else:
            spans.append(str(p))
    return ",".join(spans)


def convert(args: argparse.Namespace) -> dict:
    pdf = Path(args.pdf)
    if not pdf.is_file():
        raise InputError(f"file not found: {pdf}")
    size_mb = pdf.stat().st_size / (1 << 20)
    if size_mb > args.max_mb:
        raise InputError(f"file is {size_mb:.1f} MB, above --max-mb {args.max_mb}")
    with pdf.open("rb") as fh:
        if b"%PDF-" not in fh.read(1024):
            raise InputError(f"not a PDF (no %PDF- header): {pdf}")

    if args.max_pages < 1 or args.max_tokens < 1:
        raise InputError("--max-pages and --max-tokens must be at least 1")
    engine = _resolve_engine(args.engine)
    sha = _sha256(pdf)
    settings = {
        "version": VERSION, "engine": engine, "engine_version": _engine_version(engine),
        "pages": args.pages, "max_pages": args.max_pages, "max_tokens": args.max_tokens,
        "min_chars": args.min_chars, "math_threshold": args.math_threshold, "ocr": args.ocr,
        "tables": args.tables,
    }
    cache = Path(args.cache_dir).resolve()
    if cache.exists() and not cache.is_dir():
        raise InputError(f"--cache-dir is not a directory: {cache}")
    md_path, meta_path = cache / f"{sha}.md", cache / f"{sha}.json"
    if not args.force and md_path.is_file() and meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, ValueError):
            meta = {}  # unreadable metadata counts as a miss and is rewritten
        if meta.get("settings") == settings and "result" in meta:
            return {**meta["result"], "source": str(pdf), "cached": True}

    plain = _plain_pages(pdf, engine)
    count = len(plain)
    chars = [len(re.sub(r"\s", "", text)) for text in plain]
    scanned = [p for p in range(1, count + 1) if chars[p - 1] < args.min_chars]
    math_pages = [p for p in range(1, count + 1) if len(MATH_RE.findall(plain[p - 1])) >= args.math_threshold]

    wanted = _parse_range(args.pages, count)
    selected, over_cap = wanted[: args.max_pages], wanted[args.max_pages:]
    markdown = {p: plain[p - 1].rstrip() for p in selected}
    tables = _tables(pdf, selected) if engine == "pdfium" and args.tables == "auto" else {}
    for p, found in tables.items():
        markdown[p] += "".join(f"\n\n**Table {n} (page {p})**\n\n{t}" for n, t in enumerate(found, 1))

    ocr_pages: list[int] = []
    if args.ocr == "auto" and shutil.which("tesseract") and shutil.which("pdftoppm"):
        langs = _ocr_languages()
        for p in (p for p in selected if p in scanned):
            text = _ocr_page(pdf, p, langs)
            if len(re.sub(r"\s", "", text)) >= args.min_chars:
                markdown[p] = text
                ocr_pages.append(p)

    body: list[str] = []
    used, extracted, truncated = 0, [], list(over_cap)
    for p in selected:
        block = f"<!-- page {p} -->\n\n{markdown[p]}\n"
        cost = _tokens(block)
        if extracted and used + cost > args.max_tokens:
            truncated.extend(q for q in selected if q >= p)
            break
        body.append(block)
        used += cost
        extracted.append(p)
    truncated = sorted(set(truncated))

    header = (f"<!-- pdf_to_md v{VERSION}: source={pdf.name} sha256={sha} engine={engine} "
              f"pages={count} extracted={_compact_ranges(extracted)} -->\n\n")
    footer = ""
    if truncated:
        footer = (f"\n<!-- truncated: pages {_compact_ranges(truncated)} not included "
                  f"(--max-pages {args.max_pages} / --max-tokens {args.max_tokens}); rerun with --pages -->\n")

    result = {
        "sha256": sha,
        "engine": engine,
        "engine_version": settings["engine_version"],
        "page_count": count,
        "pages_extracted": extracted,
        "scanned_pages": scanned,
        "ocr_pages": ocr_pages,
        "needs_visual_pages": [p for p in scanned if p in extracted and p not in ocr_pages],
        "math_pages": math_pages,
        "table_pages": sorted(tables),
        "truncated": bool(truncated),
        "truncated_pages": truncated,
        "estimated_tokens": used,
        "token_estimate": f"characters/{CHARS_PER_TOKEN}",
        "markdown": str(md_path),
    }
    cache.mkdir(parents=True, exist_ok=True)
    md_path.write_text(header + "\n".join(body) + footer, encoding="utf-8")
    meta_path.write_text(json.dumps({"settings": settings, "result": result}, indent=2), encoding="utf-8")
    return {**result, "source": str(pdf), "cached": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pdf", help="PDF file to convert")
    parser.add_argument("--cache-dir", required=True, help="directory for <sha256>.md and <sha256>.json")
    parser.add_argument("--engine", choices=["auto", "pdfium", "pdftotext"], default="auto")
    parser.add_argument("--tables", choices=["auto", "off"], default="auto",
                        help="Markdown tables via pdfplumber when installed (pdfium engine only)")
    parser.add_argument("--ocr", choices=["auto", "off"], default="auto",
                        help="OCR low-text pages with tesseract when installed (default auto)")
    parser.add_argument("--pages", help="1-based pages to extract, e.g. 1-5,9")
    parser.add_argument("--max-pages", type=int, default=80)
    parser.add_argument("--max-tokens", type=int, default=60000, help="estimated-token budget for the Markdown")
    parser.add_argument("--max-mb", type=float, default=100.0)
    parser.add_argument("--min-chars", type=int, default=50,
                        help="non-space characters below which a page counts as scanned")
    parser.add_argument("--math-threshold", type=int, default=4,
                        help="math symbols on a page that flag it as math")
    parser.add_argument("--force", action="store_true", help="ignore the cache and convert again")
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = parser.parse_args(argv)

    try:
        result = convert(args)
    except InputError as exc:
        error, code = str(exc), 2
    except LookupError as exc:
        error, code = str(exc), 3
    else:
        if args.json:
            print(json.dumps(result))
        else:
            for key in ("markdown", "engine", "page_count", "pages_extracted", "scanned_pages", "ocr_pages",
                        "needs_visual_pages", "math_pages", "table_pages", "truncated_pages", "estimated_tokens", "cached"):
                print(f"{key}: {result[key]}")
        return 0
    if args.json:
        print(json.dumps({"error": error}))
    else:
        print(f"error: {error}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
