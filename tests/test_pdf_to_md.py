"""scripts/pdf_to_md.py: deterministic PDF intake for insumos-observador (Phase 0).

The agent used to run `python -c "import pymupdf4llm; ..."`, which fails twice:
the library is not installed by default, pymupdf4llm 2.0 is an empty shim
whose code moved into pymupdf 2.x, and PyMuPDF is AGPL. The script uses
permissive engines only (pypdfium2, pdfplumber, poppler CLI). The script triages every page, extracts
with the best engine available, flags scanned and math pages, caps tokens,
and caches by SHA-256 so the same PDF is never converted twice.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "pdf_to_md.py"

HAS_PDFTOTEXT = shutil.which("pdftotext") is not None and shutil.which("pdfinfo") is not None
HAS_PDFIUM = importlib.util.find_spec("pypdfium2") is not None
HAS_PDFPLUMBER = importlib.util.find_spec("pdfplumber") is not None


def _write_pdf(path: Path, pages: list[str]) -> None:
    """Minimal valid PDF, one Helvetica text line per page; '' gives a blank (scan-like) page."""
    objects: list[bytes] = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font_id = 3 + 2 * len(pages)
    for i, text in enumerate(pages):
        content_id = 4 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
        lines = [t for t in text.split("\n") if t]
        ops = "".join(f"BT /F1 11 Tf 72 {720 - 16 * n} Td ({line}) Tj ET\n" for n, line in enumerate(lines))
        stream = ops.encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def _write_table_pdf(path: Path) -> None:
    """One page with a ruled 2x3 grid (Criterion/Weight, Impact/40, Novelty/60)."""
    cells = [("Criterion", "Weight"), ("Impact", "40"), ("Novelty", "60")]
    ops = ["0.5 w"]
    for r in range(4):
        ops.append(f"72 {700 - 20 * r} m 372 {700 - 20 * r} l S")
    for x in (72, 222, 372):
        ops.append(f"{x} 700 m {x} 640 l S")
    for r, (a, b) in enumerate(cells):
        y = 686 - 20 * r
        ops.append(f"BT /F1 10 Tf 78 {y} Td ({a}) Tj ET BT /F1 10 Tf 228 {y} Td ({b}) Tj ET")
    stream = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


LONG = "\n".join(f"Line {n} of the terms of reference describes eligibility rules." for n in range(20))


def _run(*args: str) -> tuple[int, dict]:
    result = subprocess.run([sys.executable, str(SCRIPT), *args, "--json"], capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)


class _Base(unittest.TestCase):
    engine = "auto"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.cache = self.tmp / "cache"

    def convert(self, pdf: Path, *extra: str) -> tuple[int, dict]:
        return _run(str(pdf), "--cache-dir", str(self.cache), "--engine", self.engine, "--ocr", "off", *extra)


class InputErrors(_Base):
    def test_missing_file_exits_2_with_error(self) -> None:
        code, data = self.convert(self.tmp / "nope.pdf")
        self.assertEqual(code, 2)
        self.assertIn("not found", data["error"])

    def test_corrupt_pdf_exits_2_without_traceback(self) -> None:
        bad = self.tmp / "bad.pdf"
        bad.write_bytes(b"this is not a pdf")
        code, data = self.convert(bad)
        self.assertEqual(code, 2)
        self.assertIn("not a PDF", data["error"])
        self.assertFalse(self.cache.exists() and any(self.cache.iterdir()))


@unittest.skipUnless(HAS_PDFTOTEXT, "pdftotext/pdfinfo not installed")
class PdftotextEngine(_Base):
    engine = "pdftotext"

    def test_extracts_every_page_with_page_markers(self) -> None:
        pdf = self.tmp / "tdr.pdf"
        _write_pdf(pdf, ["Terms of reference", "Budget ceiling 500 million"])
        code, data = self.convert(pdf)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["engine"], "pdftotext")
        self.assertEqual(data["page_count"], 2)
        self.assertEqual(data["pages_extracted"], [1, 2])
        md = Path(data["markdown"]).read_text()
        self.assertIn("<!-- page 1 -->", md)
        self.assertIn("<!-- page 2 -->", md)
        self.assertIn("Budget ceiling 500 million", md)
        self.assertEqual(Path(data["markdown"]).name, f"{data['sha256']}.md")

    def test_blank_page_is_flagged_scanned_and_needs_visual(self) -> None:
        pdf = self.tmp / "scan.pdf"
        _write_pdf(pdf, [LONG, ""])
        code, data = self.convert(pdf)
        self.assertEqual(code, 0)
        self.assertEqual(data["scanned_pages"], [2])
        self.assertEqual(data["needs_visual_pages"], [2])
        self.assertEqual(data["ocr_pages"], [])

    def test_math_symbols_flag_math_page(self) -> None:
        pdf = self.tmp / "math.pdf"
        # Helvetica in latin-1 has no math glyphs; use the ones it has (plus/minus, micro, multiply, degree).
        _write_pdf(pdf, ["Plain prose only.", "x \xb1 y \xd7 z = \xb5 \xb1 2\xb0 \xb1 \xd7"])
        code, data = self.convert(pdf)
        self.assertEqual(code, 0)
        self.assertEqual(data["math_pages"], [2])

    def test_token_budget_truncates_and_lists_pages(self) -> None:
        pdf = self.tmp / "long.pdf"
        _write_pdf(pdf, [LONG, LONG, LONG])
        code, data = self.convert(pdf, "--max-tokens", "400")
        self.assertEqual(code, 0)
        self.assertTrue(data["truncated"])
        self.assertEqual(data["pages_extracted"], [1])
        self.assertEqual(data["truncated_pages"], [2, 3])
        self.assertLessEqual(data["estimated_tokens"], 400)
        md = Path(data["markdown"]).read_text()
        self.assertIn("truncated", md)
        self.assertNotIn("<!-- page 2 -->", md)

    def test_page_range_and_max_pages(self) -> None:
        pdf = self.tmp / "five.pdf"
        _write_pdf(pdf, [f"Page {n} text" for n in range(1, 6)])
        code, data = self.convert(pdf, "--pages", "2-4", "--max-pages", "2")
        self.assertEqual(code, 0)
        self.assertEqual(data["pages_extracted"], [2, 3])
        self.assertEqual(data["truncated_pages"], [4])

    def test_second_run_is_served_from_cache(self) -> None:
        pdf = self.tmp / "tdr.pdf"
        _write_pdf(pdf, ["Terms of reference"])
        _, first = self.convert(pdf)
        self.assertFalse(first["cached"])
        _, second = self.convert(pdf)
        self.assertTrue(second["cached"])
        self.assertEqual(second["sha256"], first["sha256"])

    def test_changed_settings_or_force_rebuild_cache(self) -> None:
        pdf = self.tmp / "tdr.pdf"
        _write_pdf(pdf, [LONG, LONG])
        self.convert(pdf)
        _, other = self.convert(pdf, "--max-tokens", "400")
        self.assertFalse(other["cached"])
        _, forced = self.convert(pdf, "--max-tokens", "400", "--force")
        self.assertFalse(forced["cached"])

    def test_cache_hit_returns_absolute_markdown_path(self) -> None:
        pdf = self.tmp / "tdr.pdf"
        _write_pdf(pdf, ["Terms of reference"])
        sub = self.tmp / "sub"
        sub.mkdir()
        cmd = [sys.executable, str(SCRIPT), "../tdr.pdf", "--cache-dir", "cache", "--engine", self.engine,
               "--ocr", "off", "--json"]
        subprocess.run(cmd, cwd=self.tmp / "sub", capture_output=True, text=True)
        second = json.loads(subprocess.run(cmd, cwd=sub, capture_output=True, text=True).stdout)
        self.assertTrue(second["cached"])
        self.assertTrue(Path(second["markdown"]).is_absolute())
        self.assertTrue(Path(second["markdown"]).is_file())

    def test_corrupt_cache_metadata_is_a_cache_miss(self) -> None:
        pdf = self.tmp / "tdr.pdf"
        _write_pdf(pdf, ["Terms of reference"])
        _, first = self.convert(pdf)
        Path(first["markdown"]).with_suffix(".json").write_text("{bad")
        code, again = self.convert(pdf)
        self.assertEqual(code, 0)
        self.assertFalse(again["cached"])

    def test_invalid_page_options_exit_2(self) -> None:
        pdf = self.tmp / "five.pdf"
        _write_pdf(pdf, [f"Page {n} text" for n in range(1, 6)])
        for extra in (["--pages", "5-3"], ["--pages", "100-200"], ["--max-pages", "0"], ["--max-tokens", "-1"]):
            code, data = self.convert(pdf, *extra)
            self.assertEqual(code, 2, extra)
            self.assertIn("error", data)

    def test_needs_visual_pages_stay_inside_requested_range(self) -> None:
        pdf = self.tmp / "scan.pdf"
        _write_pdf(pdf, [LONG, "", LONG])
        code, data = self.convert(pdf, "--pages", "3")
        self.assertEqual(code, 0)
        self.assertEqual(data["scanned_pages"], [2])
        self.assertEqual(data["needs_visual_pages"], [])

    def test_human_output_without_json(self) -> None:
        pdf = self.tmp / "tdr.pdf"
        _write_pdf(pdf, ["Terms of reference"])
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(pdf), "--cache-dir", str(self.cache), "--engine", "pdftotext"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("markdown:", result.stdout)


@unittest.skipUnless(HAS_PDFIUM, "pypdfium2 not importable (run under: uv run --with pdfplumber)")
class PdfiumEngine(PdftotextEngine):
    engine = "pdfium"

    def test_extracts_every_page_with_page_markers(self) -> None:
        pdf = self.tmp / "tdr.pdf"
        _write_pdf(pdf, ["Terms of reference", "Budget ceiling 500 million"])
        code, data = self.convert(pdf)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["engine"], "pdfium")
        self.assertEqual(data["pages_extracted"], [1, 2])
        self.assertIn("Budget ceiling 500 million", Path(data["markdown"]).read_text())

    @unittest.skipUnless(HAS_PDFPLUMBER, "pdfplumber not importable")
    def test_ruled_table_becomes_markdown_table(self) -> None:
        pdf = self.tmp / "table.pdf"
        _write_table_pdf(pdf)
        code, data = self.convert(pdf)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["table_pages"], [1])
        md = Path(data["markdown"]).read_text()
        self.assertIn("| Criterion | Weight |", md)
        self.assertIn("| Impact | 40 |", md)

    def test_tables_off_skips_detection(self) -> None:
        pdf = self.tmp / "table.pdf"
        _write_table_pdf(pdf)
        code, data = self.convert(pdf, "--tables", "off")
        self.assertEqual(code, 0)
        self.assertEqual(data["table_pages"], [])


class EngineSelection(_Base):
    def test_unknown_engine_is_rejected_by_argparse(self) -> None:
        pdf = self.tmp / "x.pdf"
        _write_pdf(pdf, ["x"])
        result = subprocess.run([sys.executable, str(SCRIPT), str(pdf), "--engine", "marker"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
