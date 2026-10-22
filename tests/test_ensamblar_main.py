"""main.tex follows the TDR chapters when the call fixes them (odd/tasks/sgr-figuras-estructura.md, S3).

`scripts/ensamblar_main.py` rewrites the body of `redaccion/main.tex` from
`artefactos/estructura_tdr.json` (or bootstraps that file from the table in
`guia_ajustada_TDR.md`), keeping the template preamble and cover and dropping
`\\setcounter{section}{1}` so LaTeX prints the TDR chapter numbers.
`scripts/check_run.py` flags a stale main.tex and chapter titles that are not
the TDR's verbatim.
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
ENSAMBLAR = REPO / "scripts" / "ensamblar_main.py"
CHECK = REPO / "scripts" / "check_run.py"

ESTRUCTURA = {
    "fuente": "Anexo 2 (Documento técnico)",
    "capitulos": [
        {"numero": 1, "titulo": "Identificación del proyecto", "archivos": ["tdr01_identificacion"]},
        {"numero": 2, "titulo": "Planteamiento del problema", "archivos": ["03_descripcion_problema", "diag_arbol_problemas"]},
        {"numero": 3, "titulo": "Objetivos", "archivos": ["06_objetivo_general", "07_objetivos_especificos", "diag_arbol_objetivos"]},
        {"numero": 4, "titulo": "Bibliografía", "archivos": ["16_bibliografia"]},
    ],
}

GUIDE = """# Guía ajustada

| Cap. Anexo 2 | Sección(es) de la guía base | Archivo(s) en `redaccion/sections/` |
|---|---|---|
| 1 | §1 Título (adaptado) | `tdr01_identificacion.tex` [nuevo] |
| 2 | Resumen ejecutivo | `00_frontmatter.tex` (solo el capítulo 2) |
| 3 | Palabras clave | `00_frontmatter.tex` (solo el capítulo 3) |
| 5 | §3, SGR §3 y `artefactos/mga_resumido.md` | `03_descripcion_problema.tex` + `diag_arbol_problemas.tex` |
| 6 | §4 | `04_estado_arte.tex` + `diag_estado_arte.tex` |
| 6 (sub-bloque) | §5 | `05_hipotesis.tex` (con `\\subsection*`, no `\\section`) |
| 12 | §6, §7 | `06_objetivo_general.tex` + `07_objetivos_especificos.tex` + `diag_arbol_objetivos.tex` [nuevo] |
"""


class _Run(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.run_dir = self.tmp / "run"
        (self.run_dir / "redaccion" / "sections").mkdir(parents=True)
        (self.run_dir / "artefactos").mkdir()
        shutil.copy(REPO / "plantilla" / "main.tex", self.run_dir / "redaccion" / "main.tex")
        self.main = self.run_dir / "redaccion" / "main.tex"

    def write_structure(self, data: dict = ESTRUCTURA) -> None:
        (self.run_dir / "artefactos" / "estructura_tdr.json").write_text(json.dumps(data, ensure_ascii=False))

    def ensamblar(self, *extra: str) -> tuple[int, dict]:
        out = subprocess.run([sys.executable, str(ENSAMBLAR), str(self.run_dir), "--json", *extra],
                             capture_output=True, text=True)
        return out.returncode, json.loads(out.stdout)

    def findings(self, *extra: str) -> dict[str, list[dict]]:
        out = subprocess.run([sys.executable, str(CHECK), str(self.run_dir), "--json", "--flujo", "sgr", *extra],
                             capture_output=True, text=True)
        found: dict[str, list[dict]] = {}
        for f in json.loads(out.stdout)["findings"]:
            found.setdefault(f["code"], []).append(f)
        return found


class Assembly(_Run):
    def test_body_follows_the_tdr_order_without_setcounter(self) -> None:
        self.write_structure()
        code, data = self.ensamblar()
        self.assertEqual(code, 0, data)
        tex = self.main.read_text()
        body = tex[tex.index(r"\thispagestyle{fancy}"):]
        self.assertNotIn(r"\setcounter{section}{1}", body)
        order = [body.index(token) for token in (
            r"\SeccionSiExiste{tdr01_identificacion}",
            r"\SeccionSiExiste{03_descripcion_problema}",
            r"\DiagramaSiExiste{diag_arbol_problemas}",
            r"\SeccionSiExiste{06_objetivo_general}",
            r"\DiagramaSiExiste{diag_arbol_objetivos}",
            r"\SeccionSiExiste{16_bibliografia}",
        )]
        self.assertEqual(order, sorted(order))
        self.assertIn("% Cap. 3: Objetivos", body)
        self.assertTrue(tex.rstrip().endswith(r"\end{document}"))
        # Preamble and cover come from the template untouched.
        self.assertIn(r"\newcommand{\DiagramaSiExiste}", tex)
        self.assertIn(r"\TituloProyecto", tex)
        self.assertNotIn(r"\SeccionSiExiste{02_justificacion}", body)
        self.assertEqual(data["capitulos"], 4)

    def test_rerun_is_idempotent_and_keeps_a_previous_copy(self) -> None:
        self.write_structure()
        original = self.main.read_text()
        self.ensamblar()
        first = self.main.read_text()
        self.ensamblar()
        self.assertEqual(self.main.read_text(), first)
        self.assertEqual((self.run_dir / "redaccion" / "main.tex.prev").read_text(), original)

    def test_bootstrap_from_the_adjusted_guide_table(self) -> None:
        (self.run_dir / "artefactos" / "guia_ajustada_TDR.md").write_text(GUIDE)
        code, data = self.ensamblar("--from-guide")
        self.assertEqual(code, 0, data)
        estructura = json.loads((self.run_dir / "artefactos" / "estructura_tdr.json").read_text())
        caps = {c["numero"]: c for c in estructura["capitulos"]}
        self.assertEqual(sorted(caps), [1, 2, 3, 5, 6, 12])
        self.assertEqual(caps[6]["archivos"], ["04_estado_arte", "diag_estado_arte", "05_hipotesis"])
        self.assertEqual(caps[12]["archivos"], ["06_objetivo_general", "07_objetivos_especificos", "diag_arbol_objetivos"])
        self.assertIsNone(caps[1]["titulo"])
        body = self.main.read_text()
        self.assertEqual(body.count(r"\SeccionSiExiste{00_frontmatter}"), 1)

    def test_without_structure_or_guide_exits_2_and_keeps_main(self) -> None:
        original = self.main.read_text()
        code, data = self.ensamblar()
        self.assertEqual(code, 2)
        self.assertIn("estructura_tdr.json", data["error"])
        self.assertEqual(self.main.read_text(), original)

    def test_unsafe_file_name_is_rejected(self) -> None:
        bad = json.loads(json.dumps(ESTRUCTURA))
        bad["capitulos"][0]["archivos"] = ["../../etc/passwd"]
        self.write_structure(bad)
        code, data = self.ensamblar()
        self.assertEqual(code, 2)
        self.assertIn("../../etc/passwd", data["error"])


class Checks(_Run):
    def test_template_main_with_a_structure_is_stale(self) -> None:
        self.write_structure()
        self.assertEqual(self.findings()["tdr-main-desactualizado"][0]["severity"], "error")

    def test_assembled_main_is_current(self) -> None:
        self.write_structure()
        self.ensamblar()
        self.assertNotIn("tdr-main-desactualizado", self.findings())

    def test_structure_change_makes_main_stale_again(self) -> None:
        self.write_structure()
        self.ensamblar()
        changed = json.loads(json.dumps(ESTRUCTURA))
        changed["capitulos"][1]["titulo"] = "Problema"
        self.write_structure(changed)
        self.assertIn("tdr-main-desactualizado", self.findings())

    def test_chapter_title_must_be_verbatim(self) -> None:
        self.write_structure()
        self.ensamblar()
        sections = self.run_dir / "redaccion" / "sections"
        (sections / "tdr01_identificacion.tex").write_text("\\section{Identificación del proyecto}\nTexto.\n")
        (sections / "03_descripcion_problema.tex").write_text("\\section{Descripción del problema}\nTexto.\n")
        found = self.findings()
        titles = found.get("tdr-titulo-capitulo", [])
        self.assertEqual(len(titles), 1)
        self.assertIn("Planteamiento del problema", titles[0]["message"])
        self.assertEqual(titles[0]["severity"], "warning")
        self.assertEqual(self.findings("--final")["tdr-titulo-capitulo"][0]["severity"], "error")

    def test_a_chapter_with_two_numbered_sections_is_flagged(self) -> None:
        self.write_structure()
        self.ensamblar()
        sections = self.run_dir / "redaccion" / "sections"
        (sections / "06_objetivo_general.tex").write_text("\\section{Objetivos}\nUno.\n")
        (sections / "07_objetivos_especificos.tex").write_text("\\section{Objetivos específicos}\nDos.\n")
        self.assertIn("tdr-capitulo-secciones", self.findings())

    def test_no_structure_means_no_tdr_findings(self) -> None:
        found = self.findings()
        self.assertFalse([code for code in found if code.startswith("tdr-")])


if __name__ == "__main__":
    unittest.main()
