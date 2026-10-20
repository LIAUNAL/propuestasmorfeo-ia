"""scripts/check_run.py: deterministic checks a gate runs before the revisor.

Every AGENTS.md rule used to depend on the Read/Grep-only revisor agent, and two
em dashes in §10 of the reference run passed every gate. The checker reports
each mechanical violation with file and line, and exits non-zero on errors.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECK = REPO / "scripts" / "check_run.py"
GUIDE = REPO / "guiaProyectosIA_Agente.md"


def _run_json(run_root: Path, *args: str) -> tuple[int, dict]:
    """The --json output is an object: the detected flow plus the findings."""
    result = subprocess.run([sys.executable, str(CHECK), str(run_root), "--json", *args],
                            capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout or '{"findings": []}')


def _run(run_root: Path, *args: str) -> tuple[int, list[dict]]:
    code, data = _run_json(run_root, *args)
    return code, data["findings"]


def _codes(findings: list[dict], severity: str | None = None) -> set[str]:
    return {f["code"] for f in findings if severity is None or f["severity"] == severity}


def _keys(prefix: str, n: int) -> list[str]:
    return [f"{prefix}{i}" for i in range(n)]


def _cites(keys: list[str]) -> str:
    """One \\citep per key, so no key is reused and no call exceeds 3 keys."""
    return " ".join(f"Dato \\citep{{{k}}}." for k in keys)


def _clean_run(root: Path) -> Path:
    red = root / "redaccion"
    (red / "sections").mkdir(parents=True)
    (red / "logos").mkdir()
    for logo in ("logo_unal.png", "logogcpds.png", "logo_labIA.png"):
        (red / "logos" / logo).write_bytes(b"png")
    (red / "main.tex").write_text(
        "\\fancyhead[R]{\\includegraphics{logos/logo_unal.png}}\n"
        "\\IfFileExists{logos/logo_utp.png}{\\fancyhead[L]{\\includegraphics{logos/logo_utp.png}}}{}\n"
        "\\begin{document}\n\\setcounter{section}{1}\n\\end{document}\n")
    (red / "datos_proyecto.tex").write_text("\\newcommand{\\TituloProyecto}{Sistema de prueba}\n")
    s = red / "sections"
    (s / "02_justificacion.tex").write_text(
        "\\section{Justificación}\nAlcanza TRL 6 en campo. " + _cites(_keys("j", 13)) + "\n")
    (s / "04_estado_arte.tex").write_text("\\section{Estado}\n" + _cites(_keys("e", 39)) + "\n")
    (s / "06_objetivo_general.tex").write_text("\\section{Objetivo general}\nDesarrollar un sistema.\n")
    (s / "07_objetivos_especificos.tex").write_text(
        "\\section{Objetivos}\n\\begin{enumerate}\n\\item Uno.\n\\item Dos.\n\\item Tres.\n\\end{enumerate}\n")
    (s / "11_resultados_esperados.tex").write_text(
        "\\section{Resultados}\nPrototipo en TRL 7. " + _cites(_keys("r", 13)) + "\n")
    (s / "16_bibliografia.tex").write_text(
        "\\clearpage\n\\section{Bibliografía}\n\\renewcommand{\\bibsection}{}\n\\bibliography{refs}\n")
    (s / "13_presupuesto.tex").write_text(
        "\\section{Presupuesto}\n\\begin{tabular}{ll}\nRubro -- A & 10 \\\\\n\\end{tabular}\n")
    return root


class CheckRunTest(unittest.TestCase):
    def test_a_clean_run_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, findings = _run(_clean_run(Path(tmp)))
            self.assertEqual(_codes(findings, "error"), set(), findings)
            self.assertEqual(code, 0)

    def test_each_mechanical_violation_is_reported_with_its_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _clean_run(Path(tmp))
            s = root / "redaccion" / "sections"
            (s / "05_hipotesis.tex").write_text(
                "\\section{Hipótesis}\n"
                "La propuesta —según el plan— avanza. Un rango 2020--2024.\n"
                "Ver \\cite{j0}. Cuatro \\citep{j1,j2,j3,\n j4}.\n"
                "% comentario con — raya que no cuenta\n")
            (s / "07_objetivos_especificos.tex").write_text(
                "\\section{Objetivos}\nAlcanzar TRL 6.\n\\begin{enumerate}\n\\item Uno.\n\\item Dos.\n\\end{enumerate}\n")
            (s / "01_titulo_identificacion.tex").write_text("\\section{Título}\n")
            (s / "11_resultados_esperados.tex").write_text("\\section{Resultados}\nSin nivel.\n")
            (s / "03_descripcion_problema.tex").write_text(
                "\\section{Problema}\n" + " ".join(f"\\citep{{e0}}" for _ in range(2)) + "\n")
            (root / "redaccion" / "main.tex").write_text("\\includegraphics{logos/logo_falta.png}\n")

            code, findings = _run(root)

            errors = _codes(findings, "error")
            for expected in ("raya-en-prosa", "doble-guion-en-prosa", "cite-generico", "cita-mas-de-3-claves",
                             "trl-en-objetivos", "trl-ausente", "seccion-1-en-cuerpo", "objetivos-no-son-3",
                             "clave-repetida-en-seccion", "logo-inexistente", "setcounter-ausente"):
                self.assertIn(expected, errors, findings)
            self.assertEqual(code, 1)
            dash = next(f for f in findings if f["code"] == "raya-en-prosa")
            self.assertTrue(dash["file"].endswith("05_hipotesis.tex"))
            self.assertEqual(dash["line"], 2)
            self.assertFalse(any(f.get("line") == 5 and f["file"].endswith("05_hipotesis.tex") for f in findings),
                             "a LaTeX comment was treated as prose")

    def test_tables_are_not_prose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, findings = _run(_clean_run(Path(tmp)))
            self.assertFalse([f for f in findings if f["file"].endswith("13_presupuesto.tex")], findings)

    def test_total_floor_applies_only_at_the_final_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _clean_run(Path(tmp))
            (root / "redaccion" / "sections" / "11_resultados_esperados.tex").write_text(
                "\\section{Resultados}\nPrototipo en TRL 7. " + _cites(_keys("r", 12)) + "\n")
            _, partial = _run(root)
            self.assertNotIn("piso-referencias", _codes(partial, "error"), "64 refs mid-run is not an error yet")
            _, final = _run(root, "--final")
            self.assertIn("piso-referencias", _codes(final, "error"))

    def test_reference_floors_come_from_the_guide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _clean_run(Path(tmp))
            (root / "redaccion" / "sections" / "04_estado_arte.tex").write_text(
                "\\section{Estado}\n" + _cites(_keys("e", 38)) + "\n")
            _, findings = _run(root)
            self.assertIn("piso-referencias", _codes(findings, "error"))

        guide = GUIDE.read_text(encoding="utf-8")
        self.assertIn("al menos 13 referencias", guide)
        self.assertIn("al menos 39 referencias", guide)

    def test_final_mode_requires_every_section_and_filled_cover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _clean_run(Path(tmp))
            (root / "redaccion" / "datos_proyecto.tex").write_text(
                "\\newcommand{\\TituloProyecto}{[Por definir: título del proyecto]}\n")
            _, partial = _run(root)
            self.assertNotIn("seccion-faltante", _codes(partial, "error"))
            self.assertNotIn("portada-sin-completar", _codes(partial, "error"))

            code, final = _run(root, "--final")
            self.assertIn("seccion-faltante", _codes(final, "error"))
            self.assertIn("portada-sin-completar", _codes(final, "error"))
            self.assertEqual(code, 1)


SGR_PROBLEM = {
    "kind": "arbol",
    "caption": "Árbol de problemas.",
    "groups": [
        {"id": "SP1", "title": "SP1 · Baja separación de los residuos en la fuente",
         "causes": [{"id": "r1", "text": "Escaso conocimiento de los hogares sobre la separación"}]},
    ],
    "trunk": {"label": "PROBLEMA CENTRAL",
              "text": "Bajo aprovechamiento de los residuos sólidos domiciliarios de la zona urbana de X",
              "magnitude": {"indicador": "Porcentaje de residuos aprovechados", "valor": "8 %", "fuente": "SUI 2024"}},
    "branches": [{"id": "b1", "text": "Mayor volumen de residuos dispuestos en el relleno"}],
    "crown": {"label": "EFECTO FINAL", "text": "Deterioro ambiental de la zona urbana"},
}

SGR_OBJECTIVES = {
    "groups": [
        {"id": "OE1", "from": "SP1", "title": "OE1", "objective": "Aumentar la separación de los residuos en la fuente",
         "means": [{"id": "m1", "from": "r1", "text": "Fortalecer el conocimiento de los hogares sobre la separación"}]},
    ],
    "trunk": {"label": "OBJETIVO GENERAL",
              "text": "Aumentar el aprovechamiento de los residuos sólidos domiciliarios de la zona urbana del Municipio X"},
    "branches": [{"id": "f1", "from": "b1", "text": "Reducir el volumen de residuos dispuestos en el relleno"}],
    "crown": {"label": "FIN ÚLTIMO", "text": "Mejorar la calidad ambiental de la zona urbana"},
}


def _with_trees(root: Path, problem: dict = SGR_PROBLEM, objectives: dict | None = SGR_OBJECTIVES) -> Path:
    (root / "redaccion" / "specs").mkdir(parents=True, exist_ok=True)
    (root / "redaccion" / "specs" / "arbol_problemas.spec.json").write_text(json.dumps(problem), encoding="utf-8")
    if objectives is not None:
        (root / "artefactos" / "arboles").mkdir(parents=True, exist_ok=True)
        (root / "artefactos" / "arboles" / "arbol_objetivos.json").write_text(json.dumps(objectives), encoding="utf-8")
    return root


def _write_objective_sections(root: Path, general: str, specifics: list[str]) -> None:
    s = root / "redaccion" / "sections"
    (s / "06_objetivo_general.tex").write_text(f"\\section{{Objetivo general}}\n\\label{{sec:og}}\n{general}\n")
    items = "\n".join(f"\\item {t}" for t in specifics)
    (s / "07_objetivos_especificos.tex").write_text(
        f"\\section{{Objetivos}}\n\\begin{{enumerate}}\n{items}\n\\end{{enumerate}}\n")


class FlujoTest(unittest.TestCase):
    """S2-S3: tree rules in both flows; §6/§7 literal and MGA annexes only in the SGR flow."""

    def test_the_json_output_reports_the_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _clean_run(Path(tmp))
            _, data = _run_json(root)
            self.assertEqual(data["flujo"], "base")
            _, data = _run_json(root, "--flujo", "sgr")
            self.assertEqual(data["flujo"], "sgr")

    def test_the_flow_is_detected_from_the_workspace_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".morfeo").mkdir()
            (workspace / ".morfeo" / "config.json").write_text('{"flujo": "sgr"}')
            run = _clean_run(workspace / "proposals" / "r1")
            _, data = _run_json(run)
            self.assertEqual(data["flujo"], "sgr")

    def test_the_text_output_names_the_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _clean_run(Path(tmp))
            result = subprocess.run([sys.executable, str(CHECK), str(root), "--flujo", "sgr"],
                                    capture_output=True, text=True)
            self.assertIn("flujo sgr", result.stdout)

    def test_sgr_final_requires_the_mga_annexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _clean_run(Path(tmp))
            _, findings = _run(root, "--flujo", "sgr", "--final")
            missing = [f for f in findings if f["code"] == "sgr-anexo-faltante"]
            self.assertEqual(len(missing), len(check_module().SGR_SECTIONS))
            self.assertTrue(all(f["severity"] == "error" for f in missing))
            self.assertIn("25_marco_logico", " ".join(f["message"] for f in missing))
            _, partial = _run(root, "--flujo", "sgr")
            self.assertNotIn("sgr-anexo-faltante", _codes(partial))

    def test_the_base_flow_never_requires_the_mga_annexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, findings = _run(_clean_run(Path(tmp)), "--final")
            self.assertNotIn("sgr-anexo-faltante", _codes(findings))

    def test_sgr_objectives_must_be_the_tree_texts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _with_trees(_clean_run(Path(tmp)))
            _write_objective_sections(root, "Desarrollar un sistema de IA para el reciclaje.", ["Uno.", "Dos.", "Tres."])
            _, findings = _run(root, "--flujo", "sgr")
            errors = _codes(findings, "error")
            self.assertIn("sgr-objetivo-general-distinto", errors)
            self.assertIn("sgr-objetivos-especificos-distintos", errors)

            _write_objective_sections(root, SGR_OBJECTIVES["trunk"]["text"] + ".",
                                      [g["objective"] for g in SGR_OBJECTIVES["groups"]])
            _, findings = _run(root, "--flujo", "sgr")
            self.assertNotIn("sgr-objetivo-general-distinto", _codes(findings))
            self.assertNotIn("sgr-objetivos-especificos-distintos", _codes(findings))

    def test_base_objective_must_keep_the_tree_variable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _with_trees(_clean_run(Path(tmp)))
            _write_objective_sections(root, "Desarrollar un modelo de lenguaje para tutorías.", ["Uno.", "Dos.", "Tres."])
            _, findings = _run(root)
            self.assertIn("objetivo-general-sin-variable-del-arbol", _codes(findings, "warning"))
            self.assertNotIn("sgr-objetivo-general-distinto", _codes(findings))

            _write_objective_sections(
                root, "Desarrollar un sistema de IA que aumente el aprovechamiento de los residuos sólidos "
                      "domiciliarios de la zona urbana del Municipio X.", ["Uno.", "Dos.", "Tres."])
            _, findings = _run(root)
            self.assertNotIn("objetivo-general-sin-variable-del-arbol", _codes(findings))

    def test_tree_findings_surface_through_the_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = json.loads(json.dumps(SGR_PROBLEM))
            bad["trunk"]["text"] = "Falta de un sistema de reciclaje en la zona urbana"
            root = _with_trees(_clean_run(Path(tmp)), problem=bad)
            code, findings = _run(root)
            tree = next(f for f in findings if f["code"] == "arbol-ausencia-de-solucion")
            self.assertEqual(tree["severity"], "error")
            self.assertEqual(tree["file"], "redaccion/specs/arbol_problemas.spec.json")
            self.assertEqual(tree["node"], "trunk")
            self.assertEqual(code, 1)
            bad_obj = json.loads(json.dumps(SGR_OBJECTIVES))
            bad_obj["trunk"]["text"] += " mediante un sistema de IA"
            _with_trees(root, problem=SGR_PROBLEM, objectives=bad_obj)
            _, findings = _run(root)
            obj = next(f for f in findings if f["code"] == "objetivo-general-con-medio")
            self.assertEqual(obj["file"], "artefactos/arboles/arbol_objetivos.json")

    def test_a_run_without_tree_files_reports_what_it_reported_before(self) -> None:
        """Regression guard: the new checks add nothing to a run without trees, in either mode."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _clean_run(Path(tmp))
            for args in ((), ("--final",)):
                _, findings = _run(root, *args)
                new_codes = {c for c in _codes(findings) if c.startswith(("arbol-", "objetivo-general-", "sgr-"))}
                self.assertEqual(new_codes, set(), findings)
                self.assertTrue(all("node" not in f for f in findings), findings)
            _, findings = _run(root, "--final")
            self.assertEqual(sorted(_codes(findings)), ["seccion-faltante"], findings)


def check_module():
    sys.path.insert(0, str(REPO / "scripts"))
    import check_run
    return check_run


class TemplateRunTest(unittest.TestCase):
    """A run created from the real plantilla/ must pass the checker as created."""

    def test_a_fresh_template_run_has_no_errors(self) -> None:
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("plantilla", "scripts"):
                shutil.copytree(REPO / rel, root / rel, ignore=shutil.ignore_patterns("__pycache__"))
            subprocess.run(["bash", "scripts/init-run.sh", "fresh", "idea"], cwd=root, check=True,
                           capture_output=True)
            code, findings = _run(root / "proposals" / "fresh")
            self.assertEqual(_codes(findings, "error"), set(), findings)
            self.assertEqual(code, 0)


class CoverCheckTest(unittest.TestCase):
    def test_a_filled_template_cover_passes_even_with_its_explanatory_comment(self) -> None:
        # The seeded datos_proyecto.tex explains "[Por definir: ...]" in a comment;
        # only the \newcommand values decide whether the cover is complete.
        with tempfile.TemporaryDirectory() as tmp:
            root = _clean_run(Path(tmp))
            template = (REPO / "plantilla" / "datos_proyecto.tex").read_text(encoding="utf-8")
            filled = template.replace("[Por definir: título del proyecto]", "Sistema de prueba") \
                .replace("[Por definir: investigador principal]", "Ana Demo") \
                .replace("[Por definir: grupo, laboratorio, facultad y sede]", "Grupo de prueba")
            self.assertIn("[Por definir", filled, "the template comment is part of what this test covers")
            (root / "redaccion" / "datos_proyecto.tex").write_text(filled, encoding="utf-8")
            _, findings = _run(root, "--final")
            self.assertNotIn("portada-sin-completar", _codes(findings), findings)


class SpecAgreesWithCheckerTest(unittest.TestCase):
    """The floors and the section count are stated once per file and must agree."""

    def test_floors_and_section_count_agree_across_the_spec(self) -> None:
        sys.path.insert(0, str(REPO / "scripts"))
        import check_run

        texts = {rel: (REPO / rel).read_text(encoding="utf-8") for rel in (
            "AGENTS.md", "guiaProyectosIA_Agente.md", ".claude/agents/revisor.md",
            ".claude/agents/redactor.md", ".claude/agents/bibliografo-propuesta.md", "README.md")}
        for rel in ("AGENTS.md", ".claude/agents/revisor.md"):
            for floor in (check_run.FLOOR_JUSTIFICACION, check_run.FLOOR_ESTADO_ARTE, check_run.FLOOR_TOTAL):
                self.assertIn(f"≥{floor}", texts[rel], f"{rel} does not state the ≥{floor} floor")
        for rel, text in texts.items():
            for stale in ("≥10 refs", "≥30 refs", "≥50 refs", "≥50 total", "16 secciones de la"):
                self.assertNotIn(stale, text, f"{rel} still says {stale!r}")
        self.assertEqual(len(check_run.CANONICAL_SECTIONS), 18)
        self.assertIn("18 secciones canónicas", texts["AGENTS.md"])


if __name__ == "__main__":
    unittest.main()
