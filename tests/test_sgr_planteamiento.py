"""SGR problem statement (odd/tasks/sgr-secciones-reglas.md, S2-S3).

In the SGR flow §3 follows the structure of artefactos/mga_resumido.md: Problema
central, Descripción de la situación existente (closing with the three direct
causes), one paragraph per direct cause, Magnitud del problema with the
indicator table, and the closing question with the problem tree. The SGR guide
fixes it in its `### SGR §3` block, the dispatcher injects that block for §3,
and check_run warns when an SGR §3 misses one of the three subsections.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))

from test_trees import make_run  # noqa: E402

from morfeo.core.sgr_rules import parse_sgr_blocks  # noqa: E402
from morfeo.dashboard.server import MorfeoDashboardHandler  # noqa: E402

CHECK = REPO / "scripts" / "check_run.py"
SUBSECTIONS = ("Problema central", "Descripción de la situación existente", "Magnitud del problema")

SEC3_OK = r"""\section{Planteamiento del problema}
\subsection{Problema central}
Alta prevalencia de depresión en estudiantes universitarios de Caldas.
\subsection{Descripción de la situación existente}
Antecedentes y zona de estudio.
\subsection{Magnitud del problema}
Cifras y tabla de indicadores.
"""


def sgr_block(text: str, key: str) -> str:
    start = text.index(f"### SGR {key}\n")
    end = text.find("\n### ", start + 1)
    return text[start:end if end >= 0 else len(text)]


class GuideAndFlow(unittest.TestCase):
    def test_sgr_guide_fixes_the_problem_statement_structure(self) -> None:
        block = sgr_block((REPO / "guiaProyectosIA_Agente_Regalias.md").read_text(encoding="utf-8"), "§3")
        self.assertIn("**Estructura de §3.**", block)
        for title in SUBSECTIONS:
            self.assertIn(title, block)
        self.assertIn("pregunta de investigación", block)
        self.assertIn("mga_resumido.md", block)

    def test_dispatcher_injects_the_sgr_block_for_section_3(self) -> None:
        text = (REPO / ".claude" / "commands" / "propuesta.md").read_text(encoding="utf-8")
        start = text.index("Task → investigador → §3 descripción del problema")
        self.assertIn("### SGR §3", text[start:start + 900])

    def test_investigator_writes_section_3_with_the_sgr_structure(self) -> None:
        text = (REPO / ".claude" / "agents" / "investigador.md").read_text(encoding="utf-8")
        start = text.index("Then write §3 from this document")
        self.assertIn("### SGR §3", text[start:start + 700])


class StructureCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.run_dir = make_run(self.tmp)
        self.sec3 = self.run_dir / "redaccion" / "sections" / "03_descripcion_problema.tex"

    def findings(self, flujo: str = "sgr", *extra: str) -> dict[str, dict]:
        out = subprocess.run([sys.executable, str(CHECK), str(self.run_dir), "--json", "--flujo", flujo, *extra],
                             capture_output=True, text=True)
        return {f["code"]: f for f in json.loads(out.stdout)["findings"]}

    def test_missing_subsections_are_named_in_a_warning(self) -> None:
        self.sec3.write_text(SEC3_OK.replace("\\subsection{Magnitud del problema}\n", ""), encoding="utf-8")
        found = self.findings()["sgr-problema-estructura"]
        self.assertEqual(found["severity"], "warning")
        self.assertIn("Magnitud del problema", found["message"])
        self.assertNotIn("Problema central,", found["message"])

    def test_warning_stays_a_warning_with_final(self) -> None:
        self.sec3.write_text("\\section{Planteamiento del problema}\nTexto.\n", encoding="utf-8")
        self.assertEqual(self.findings("sgr", "--final")["sgr-problema-estructura"]["severity"], "warning")

    def test_three_subsections_pass_even_unnumbered(self) -> None:
        self.sec3.write_text(SEC3_OK.replace("\\subsection{", "\\subsection*{"), encoding="utf-8")
        self.assertNotIn("sgr-problema-estructura", self.findings())

    def test_base_flow_keeps_its_own_structure(self) -> None:
        self.sec3.write_text("\\section{Descripción del problema}\nTexto.\n", encoding="utf-8")
        self.assertNotIn("sgr-problema-estructura", self.findings("base"))

    def test_no_section_3_means_no_finding(self) -> None:
        self.sec3.unlink(missing_ok=True)
        self.assertNotIn("sgr-problema-estructura", self.findings())


class PanelGuide(unittest.TestCase):
    """S1: the sections panel reads the same `### SGR §N` blocks the dispatcher injects."""

    def test_parser_maps_sections_and_annexes_and_stops_at_the_next_heading(self) -> None:
        blocks = parse_sgr_blocks("# Guía\n\n### SGR §3\n\n* uno\n\n### SGR §10\ndos\n\n"
                                  "## Anexos MGA\n\nintro\n\n### SGR A19\ntres\n")
        self.assertEqual(blocks, {"§3": "* uno", "§10": "dos", "A19": "tres"})

    def test_real_guide_has_the_section_3_structure_and_the_annexes(self) -> None:
        blocks = parse_sgr_blocks((REPO / "guiaProyectosIA_Agente_Regalias.md").read_text(encoding="utf-8"))
        self.assertIn("**Estructura de §3.**", blocks["§3"])
        self.assertNotIn("### SGR §6", blocks["§3"])
        self.assertIn("A25", blocks)

    def test_endpoint_serves_the_project_guide(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / ".morfeo").mkdir()
        (root / ".morfeo" / "config.json").write_text(json.dumps({"flujo": "sgr"}), encoding="utf-8")
        (root / "guiaProyectosIA_Agente_Regalias.md").write_text("### SGR §3\nregla del proyecto\n", encoding="utf-8")
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": root})
        handler.log_message = lambda *a, **k: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_address[1]}/api/guide/sgr") as res:
            data = json.loads(res.read().decode("utf-8"))
        self.assertEqual(data["flujo"], "sgr")
        self.assertEqual(data["source"], "guiaProyectosIA_Agente_Regalias.md")
        self.assertEqual(data["blocks"], {"§3": "regla del proyecto"})


if __name__ == "__main__":
    unittest.main()
