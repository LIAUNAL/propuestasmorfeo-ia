"""«Versión del documento»: the translation routes of the dashboard (S4 of
odd/tasks/idioma-tablero-traduccion.md).

GET /api/traducciones returns the status of the run's translation into the
other language (scripts/traducir.py status), POST /api/traduccion/compilar
compiles the built translation, and GET /api/pdf?traduccion=<lang> serves its
PDF (404 while it does not exist). The target travels as `traduccion=`: the
i18n runtime adds `lang=<interface language>` to every /api/ request, and that
never selects a manuscript. Without `traduccion`, /api/pdf serves main.pdf as
before.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from morfeo.core import translation  # noqa: E402
from morfeo.dashboard.server import MorfeoDashboardHandler  # noqa: E402

_spec = importlib.util.spec_from_file_location("traducir_fixture", REPO / "tests" / "test_traducir.py")
fixture = importlib.util.module_from_spec(_spec)
sys.modules["traducir_fixture"] = fixture
_spec.loader.exec_module(fixture)

PDF = b"%PDF-1.4\n" + b"x" * 2048 + b"\n%%EOF\n"


class Routes(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = Path(tmp.name) / "proyecto"
        self.run = fixture.make_run(self.workspace, "es")
        (self.workspace / "proposals" / ".current-run").write_text("demo", encoding="utf-8")
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": self.workspace})
        handler.log_message = lambda *a, **k: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.base = f"http://127.0.0.1:{server.server_address[1]}"

    def get(self, path: str, headers: dict | None = None) -> tuple[int, bytes, dict]:
        req = urllib.request.Request(self.base + path, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, res.read(), dict(res.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read(), dict(err.headers)

    def get_json(self, path: str) -> tuple[int, dict]:
        code, body, _ = self.get(path)
        return code, json.loads(body)

    def post_json(self, path: str) -> tuple[int, dict]:
        req = urllib.request.Request(self.base + path, data=b"{}", headers={"Content-Type": "application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_the_status_targets_the_other_language_whatever_the_interface_language(self) -> None:
        for path in ("/api/traducciones", "/api/traducciones?lang=en", "/api/traducciones?lang=es&traduccion=en"):
            with self.subTest(path=path):
                code, data = self.get_json(path)
                self.assertEqual(code, 200)
                self.assertEqual((data["source_language"], data["lang"], data["command"]),
                                 ("es", "en", "/propuesta-traducir en"))
                self.assertFalse(data["status"]["planned"])
                self.assertEqual(data["status"]["counts"]["missing"], 3)
                self.assertFalse(data["available"])

    def test_the_status_follows_the_stored_blocks(self) -> None:
        tr = translation.engine(REPO / "scripts")
        tr.plan(self.run, "en")
        draft = self.run.parent.parent / "b1.tex"
        draft.write_text(fixture.ENGLISH["02_justificacion-b01"], encoding="utf-8")
        tr.store(self.run, "en", "02_justificacion-b01", draft)
        code, data = self.get_json("/api/traducciones?traduccion=en")
        self.assertEqual(code, 200)
        self.assertEqual(data["status"]["counts"], {"total": 3, "current": 1, "missing": 2, "stale": 0})
        self.assertTrue(data["status"]["planned"])

    def test_the_same_or_an_unknown_language_is_refused(self) -> None:
        code, data = self.get_json("/api/traducciones?traduccion=es")
        self.assertEqual((code, data["ok"], data["code"]), (400, False, "TRANSLATION_SAME_LANGUAGE"))
        code, data = self.get_json("/api/traducciones?traduccion=fr")
        self.assertEqual((code, data["ok"]), (400, False))
        code, _, _ = self.get("/api/pdf?traduccion=fr")
        self.assertEqual(code, 400)

    def test_without_an_active_run_the_routes_answer_404(self) -> None:
        (self.workspace / "proposals" / ".current-run").unlink()
        self.assertEqual(self.get_json("/api/traducciones")[0], 404)
        self.assertEqual(self.post_json("/api/traduccion/compilar")[0], 404)

    def test_the_translated_pdf_is_served_only_when_it_exists(self) -> None:
        code, _, _ = self.get("/api/pdf?traduccion=en")
        self.assertEqual(code, 404)
        code, data = self.get_json("/api/pdf/version?traduccion=en")
        self.assertEqual((code, data["exists"]), (200, False))
        target = self.run / "redaccion" / "traducciones" / "en" / "main.pdf"
        target.parent.mkdir(parents=True)
        target.write_bytes(PDF)
        code, body, headers = self.get("/api/pdf?traduccion=en&lang=es&t=1")
        self.assertEqual((code, body, headers["Content-Type"]), (200, PDF, "application/pdf"))
        self.assertEqual(headers["ETag"], f'"{target.stat().st_mtime_ns}-{target.stat().st_size}"')
        code, body, headers = self.get("/api/pdf?traduccion=en", {"Range": "bytes=0-8"})
        self.assertEqual((code, body, headers["Content-Range"]), (206, PDF[:9], f"bytes 0-8/{len(PDF)}"))
        code, data = self.get_json("/api/pdf/version?traduccion=en")
        self.assertEqual((data["exists"], data["version"]), (True, f"{target.stat().st_mtime_ns}-{len(PDF)}"))

    def test_the_original_pdf_is_served_as_before(self) -> None:
        code, _, _ = self.get("/api/pdf")
        self.assertEqual(code, 404)
        original = self.run / "redaccion" / "main.pdf"
        original.write_bytes(PDF[::-1])
        translated = self.run / "redaccion" / "traducciones" / "en" / "main.pdf"
        translated.parent.mkdir(parents=True)
        translated.write_bytes(PDF)
        for path in ("/api/pdf", "/api/pdf?t=doc", "/api/pdf?lang=en"):
            with self.subTest(path=path):
                code, body, headers = self.get(path)
                self.assertEqual((code, body), (200, PDF[::-1]))
                self.assertEqual({k: headers[k] for k in ("Content-Type", "Accept-Ranges", "Cache-Control", "ETag")},
                                 {"Content-Type": "application/pdf", "Accept-Ranges": "bytes",
                                  "Cache-Control": "no-cache",
                                  "ETag": f'"{original.stat().st_mtime_ns}-{original.stat().st_size}"'})
        etag = headers["ETag"]
        code, _, _ = self.get("/api/pdf", {"If-None-Match": etag})
        self.assertEqual(code, 304)
        code, data = self.get_json("/api/pdf/version")
        self.assertEqual(data["version"], f"{original.stat().st_mtime_ns}-{original.stat().st_size}")

    def test_compiling_an_unbuilt_translation_is_refused_with_409(self) -> None:
        code, data = self.post_json("/api/traduccion/compilar?traduccion=en")
        self.assertEqual((code, data["ok"], data["code"]), (409, False, "TRANSLATION_NOT_BUILT"))

    def test_a_successful_compile_returns_the_new_version(self) -> None:
        result = {"ok": True, "lang": "en", "pdf": "redaccion/traducciones/en/main.pdf", "version": "1-2",
                  "log_tail": ""}
        with mock.patch.object(translation, "compile_translation", return_value=result) as compiled:
            code, data = self.post_json("/api/traduccion/compilar?traduccion=en&lang=es")
        self.assertEqual((code, data), (200, result))
        self.assertEqual(compiled.call_args.args[2], "en")


class CoreTests(unittest.TestCase):
    def test_the_command_names_the_target(self) -> None:
        self.assertEqual(translation.build_run_command("es"), "/propuesta-traducir es")
        with self.assertRaises(ValueError):
            translation.build_run_command("fr")

    def test_an_unknown_language_has_no_pdf(self) -> None:
        self.assertIsNone(translation.translated_pdf(Path("/x"), "fr"))
        self.assertEqual(translation.translated_pdf(Path("/x"), "en"),
                         Path("/x/redaccion/traducciones/en/main.pdf"))


if __name__ == "__main__":
    unittest.main()
