"""«Estilo y redundancia» panel: the report endpoint and its PDF preview.

`GET /api/estilo` serves `artefactos/estilo/reporte.json` as before and attaches
to each finding the text of its sentence (`oracion_texto`), so the panel can
look the finding up in the compiled PDF (odd/tasks/tablero-juez-novedad.md, S5).
The sentence is attached only while the fragment still sits in it.
"""

from __future__ import annotations

import json
import re
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from morfeo.dashboard.server import MorfeoDashboardHandler

RUN = "2026-01-demo"
STATIC = Path(__file__).resolve().parents[1] / "src" / "morfeo" / "dashboard" / "static"

SECTION = "\n".join([
    r"\section{Justificación}",
    r"La región cafetera reúne veinte municipios con datos dispersos.",
    r"La segunda oración existe porque el ejemplo lo pide \citep{doe2024} y nada más.",
    "",
    r"El último párrafo cierra la idea con una oración breve.",
    "",
])


def finding(oracion: int, fragmento: str, **extra) -> dict:
    return {"seccion": "02_justificacion", "parrafo": 1, "oracion": oracion, "categoria": "causal_densidad",
            "fragmento": fragmento, "orientacion": "Revisa la causal.", **extra}


REPORT = {
    "version": 1,
    "fuente": RUN,
    "indice": 81,
    "veredicto": "fluida",
    "aviso": "Mide legibilidad, no autoría.",
    "secciones": [{"seccion": "02_justificacion", "palabras": 30, "indice": 81}],
    "hallazgos": [
        finding(2, "porque"),
        finding(1, "veinte municipios con datos"),
        finding(3, "un texto que no está en la oración"),
        finding(9, "oración inexistente"),
    ],
    "exentos": [],
}


class StyleEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        proposals = self.root / "proposals"
        self.run_dir = proposals / RUN
        (self.run_dir / "redaccion" / "sections").mkdir(parents=True)
        (proposals / ".current-run").write_text(RUN, encoding="utf-8")
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": self.root})
        handler.log_message = lambda *a, **k: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.base = f"http://127.0.0.1:{server.server_address[1]}"

    def _write_section(self, text: str = SECTION) -> None:
        (self.run_dir / "redaccion" / "sections" / "02_justificacion.tex").write_text(text, encoding="utf-8")

    def _write_report(self, report: dict = REPORT) -> None:
        folder = self.run_dir / "artefactos" / "estilo"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "reporte.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

    def _get(self, path: str) -> tuple[int, dict, bytes]:
        with urllib.request.urlopen(self.base + path) as res:
            return res.status, dict(res.headers), res.read()

    def _estilo(self) -> dict:
        status, _, body = self._get("/api/estilo")
        self.assertEqual(status, 200)
        return json.loads(body)

    def test_without_a_report_the_payload_is_unchanged(self) -> None:
        self._write_section()
        self.assertEqual(self._estilo(), {"ok": True, "disponible": False})

    def test_report_fields_are_served_as_written(self) -> None:
        self._write_section()
        self._write_report()
        data = self._estilo()
        self.assertTrue(data["ok"])
        self.assertTrue(data["disponible"])
        for key in ("version", "fuente", "indice", "veredicto", "aviso", "secciones", "exentos"):
            self.assertEqual(data[key], REPORT[key], key)
        self.assertEqual(len(data["hallazgos"]), len(REPORT["hallazgos"]))
        for served, written in zip(data["hallazgos"], REPORT["hallazgos"]):
            self.assertEqual({k: v for k, v in served.items() if k != "oracion_texto"}, written)

    def test_each_finding_carries_the_text_of_its_sentence(self) -> None:
        self._write_section()
        self._write_report()
        found = self._estilo()["hallazgos"]
        self.assertRegex(found[0]["oracion_texto"], r"^La segunda oración existe porque el ejemplo lo pide\s+y nada más\.$")
        self.assertEqual(found[1]["oracion_texto"], "La región cafetera reúne veinte municipios con datos dispersos.")

    def test_a_fragment_outside_its_sentence_gets_no_sentence(self) -> None:
        self._write_section()
        self._write_report()
        found = self._estilo()["hallazgos"]
        self.assertNotIn("oracion_texto", found[2])
        self.assertNotIn("oracion_texto", found[3])

    def test_a_section_edited_after_the_audit_drops_the_stale_sentence(self) -> None:
        self._write_section()
        self._write_report()
        self.assertIn("oracion_texto", self._estilo()["hallazgos"][1])
        self._write_section(SECTION.replace("veinte municipios con datos dispersos", "una red de estaciones"))
        self.assertNotIn("oracion_texto", self._estilo()["hallazgos"][1])

    def test_without_sections_the_report_is_served_without_sentences(self) -> None:
        self._write_report()
        data = self._estilo()
        self.assertTrue(data["disponible"])
        self.assertTrue(all("oracion_texto" not in item for item in data["hallazgos"]))

    def test_the_viewer_script_is_served_without_cache(self) -> None:
        status, headers, body = self._get("/static/estilo-pdf.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-cache")
        self.assertIn("javascript", headers["Content-Type"])
        self.assertIn(b"window.EstiloPdf", body)


class StylePaneMarkupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (STATIC / "index.html").read_text(encoding="utf-8")

    def test_the_viewer_script_loads_right_after_the_cli_console(self) -> None:
        self.assertRegex(self.html, r'<script src="/static/cli-console.js"></script>\s*<script src="/static/estilo-pdf.js"></script>')

    def test_the_pane_holds_findings_and_the_pdf_preview(self) -> None:
        pane = re.search(r'<div id="pane-estilo" class="tab-pane">(.*?)<div id="pane-atlas"', self.html, re.S).group(1)
        for element in ("estiloHallazgos", "btnEstiloVerTodos", "estiloPdfViewport", "estiloPdfPages",
                        "estiloPdfPageInfo", "estiloPdfStatus", "estiloPdfEmpty", "estiloPdfFrame"):
            self.assertIn(f'id="{element}"', pane, element)
        self.assertIn('class="estilo-layout"', pane)

    def test_the_layout_stacks_on_narrow_screens(self) -> None:
        self.assertIn(".estilo-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);", self.html)
        self.assertIn("@media (max-width: 1100px) { .estilo-layout { grid-template-columns: minmax(0, 1fr); } }", self.html)

    def test_ui_copy_has_no_em_dash_or_double_hyphen(self) -> None:
        script = (STATIC / "estilo-pdf.js").read_text(encoding="utf-8")
        messages = re.search(r"const MESSAGES = \{(.*?)\n  \};", script, re.S).group(1)
        self.assertNotIn("—", messages)
        self.assertNotIn("--", messages)


if __name__ == "__main__":
    unittest.main()
