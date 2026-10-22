"""Recompilar el PDF desde el tablero y saber cuándo main.pdf cambió.

`POST /api/pdf/compile` corre `build.sh` de la corrida activa y devuelve el
resultado; `GET /api/pdf/version` da una versión que cambia cada vez que se
reescribe `main.pdf`. `GET /api/pdf` sigue sirviendo el archivo, ahora con
`Cache-Control: no-cache` y un ETag que distingue reescrituras en el mismo
segundo.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from morfeo.dashboard.server import MorfeoDashboardHandler

RUN = "2026-01-demo"

OK_BUILD = """#!/usr/bin/env bash
printf '%%PDF-1.4 compiled %s\\n' "$$" > main.pdf
echo "[ OK ] Compilación exitosa: main.pdf (7 páginas, 3.0M)"
"""

FAIL_BUILD = """#!/usr/bin/env bash
echo "! Undefined control sequence."
echo "[FAIL] LaTeX reportó 1 error(es) real(es)"
exit 1
"""


class PdfCompileEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        proposals = self.root / "proposals"
        self.redaccion = proposals / RUN / "redaccion"
        self.redaccion.mkdir(parents=True)
        (proposals / ".current-run").write_text(RUN, encoding="utf-8")
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": self.root})
        handler.log_message = lambda *a, **k: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.base = f"http://127.0.0.1:{server.server_address[1]}"

    def _build(self, script: str) -> None:
        path = self.redaccion / "build.sh"
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def _request(self, path: str, method: str = "GET") -> tuple[int, dict, dict]:
        req = urllib.request.Request(self.base + path, method=method, data=b"{}" if method == "POST" else None)
        try:
            with urllib.request.urlopen(req) as res:
                body = res.read()
                return res.status, dict(res.headers), (json.loads(body) if "json" in res.headers.get("Content-Type", "") else {})
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), json.loads(err.read() or b"{}")

    def test_compile_runs_build_and_reports_pages_and_new_version(self) -> None:
        self._build(OK_BUILD)
        _, _, before = self._request("/api/pdf/version")
        self.assertFalse(before["exists"])

        status, _, result = self._request("/api/pdf/compile", "POST")

        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])
        self.assertEqual(result["pages"], 7)
        self.assertTrue((self.redaccion / "main.pdf").is_file())
        _, _, after = self._request("/api/pdf/version")
        self.assertTrue(after["exists"])
        self.assertEqual(result["version"], after["version"])

    def test_failed_build_returns_500_with_log_tail(self) -> None:
        self._build(FAIL_BUILD)
        status, _, result = self._request("/api/pdf/compile", "POST")
        self.assertEqual(status, 500)
        self.assertFalse(result["ok"])
        self.assertEqual(result["returncode"], 1)
        self.assertIn("Undefined control sequence", result["log_tail"])

    def test_compile_without_build_script_is_404(self) -> None:
        status, _, result = self._request("/api/pdf/compile", "POST")
        self.assertEqual(status, 404)
        self.assertFalse(result["ok"])

    def test_compile_without_active_run_is_404(self) -> None:
        (self.root / "proposals" / ".current-run").unlink()
        status, _, result = self._request("/api/pdf/compile", "POST")
        self.assertEqual(status, 404)
        self.assertFalse(result["ok"])

    def test_version_changes_when_pdf_is_rewritten_in_the_same_second(self) -> None:
        pdf = self.redaccion / "main.pdf"
        pdf.write_bytes(b"%PDF-1.4 a")
        os.utime(pdf, ns=(1_700_000_000_100_000_000, 1_700_000_000_100_000_000))
        _, _, first = self._request("/api/pdf/version")
        pdf.write_bytes(b"%PDF-1.4 b")
        os.utime(pdf, ns=(1_700_000_000_900_000_000, 1_700_000_000_900_000_000))
        _, _, second = self._request("/api/pdf/version")
        self.assertNotEqual(first["version"], second["version"])

    def test_pdf_is_served_with_no_cache_and_a_version_etag(self) -> None:
        pdf = self.redaccion / "main.pdf"
        pdf.write_bytes(b"%PDF-1.4 x")
        req = urllib.request.Request(self.base + "/api/pdf")
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)
            self.assertEqual(res.read(), b"%PDF-1.4 x")
            self.assertEqual(res.headers.get("Cache-Control"), "no-cache")
            etag = res.headers.get("ETag")
        _, _, version = self._request("/api/pdf/version")
        self.assertEqual(etag, f'"{version["version"]}"')

    def test_matching_etag_still_answers_304_and_ranges_still_work(self) -> None:
        pdf = self.redaccion / "main.pdf"
        pdf.write_bytes(b"%PDF-1.4 abcdef")
        with urllib.request.urlopen(self.base + "/api/pdf") as res:
            etag = res.headers.get("ETag")
        req = urllib.request.Request(self.base + "/api/pdf", headers={"If-None-Match": etag})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 304)
        req = urllib.request.Request(self.base + "/api/pdf", headers={"Range": "bytes=0-3"})
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 206)
            self.assertEqual(res.read(), b"%PDF")


if __name__ == "__main__":
    unittest.main()
