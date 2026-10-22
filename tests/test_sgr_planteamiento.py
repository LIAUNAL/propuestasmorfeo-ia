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
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))

from test_trees import make_run  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
