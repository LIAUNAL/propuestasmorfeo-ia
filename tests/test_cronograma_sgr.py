"""scripts/cronograma_sgr.py: the SGR schedule from the value chain (odd/tasks/sgr-presupuesto-gantt.md, S4).

§14 is never hand-written in the SGR flow: it is rendered from
`artefactos/sgr/cadena_valor.json` and the optional `artefactos/sgr/hitos.json`,
in the `ganttchart` convention of the base §14, and the annual financial
projection spreads each activity's cost across its months.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))

from test_cadena_valor_sgr import TREE, _valid_chain  # noqa: E402

SCRIPT = REPO / "scripts" / "cronograma_sgr.py"
CHECK_RUN = REPO / "scripts" / "check_run.py"
PREP_DOCX = REPO / "plantilla" / "scripts" / "prep_docx.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def _milestones(months=(3, 6, 9, 12, 15, 18, 21, 24)) -> dict:
    return {"schema": "morfeo.hitos-sgr/v1", "hitos": [
        {"codigo": f"H{n}", "nombre": f"Entrega del avance {n}", "mes": month, "actividades": ["1.1.1"],
         "verificacion": "Informe técnico aprobado por la supervisión"}
        for n, month in enumerate(months, start=1)]}


def _codes(found: list[dict], severity: str | None = None) -> list[str]:
    return [f["code"] for f in found if severity is None or f["severity"] == severity]


class _Run(unittest.TestCase):
    sgr = True

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        if self.sgr:
            (self.tmp / ".morfeo").mkdir()
            (self.tmp / ".morfeo" / "config.json").write_text(json.dumps({"flujo": "sgr"}), encoding="utf-8")
        self.run_root = self.tmp / "run"
        (self.run_root / "redaccion" / "sections").mkdir(parents=True)
        (self.run_root / "artefactos" / "arboles").mkdir(parents=True)
        (self.run_root / "artefactos" / "arboles" / "arbol_objetivos.json").write_text(
            json.dumps(TREE, ensure_ascii=False), encoding="utf-8")
        self.mod = _load(SCRIPT, "cronograma_sgr_under_test")
        self.chain = _valid_chain()
        self.tex = self.run_root / "redaccion" / "sections" / "14_cronograma_actividades.tex"

    def write(self, chain: dict | None = None, milestones: dict | None = None) -> None:
        sgr = self.run_root / "artefactos" / "sgr"
        sgr.mkdir(parents=True, exist_ok=True)
        (sgr / "cadena_valor.json").write_text(json.dumps(chain or self.chain, ensure_ascii=False), encoding="utf-8")
        if milestones is not None:
            (sgr / "hitos.json").write_text(json.dumps(milestones, ensure_ascii=False), encoding="utf-8")

    def act(self, code: str) -> dict:
        for objective in self.chain["objetivos"]:
            for prod in objective["productos"]:
                for act in prod["actividades"]:
                    if act["codigo"] == code:
                        return act
        raise KeyError(code)

    def findings(self, milestones: dict | None = None) -> list[dict]:
        self.write(milestones=milestones if milestones is not None else _milestones())
        return self.mod.findings(self.run_root)


class Check(_Run):
    def test_a_complete_schedule_is_clean(self) -> None:
        self.assertEqual(self.findings(), [])

    def test_findings_follow_the_check_run_shape(self) -> None:
        self.act("1.1.1")["mes_inicio"] = None
        finding = self.findings()[0]
        self.assertEqual(set(finding), {"severity", "code", "message", "node"})
        self.assertEqual(finding["node"], "1.1.1")
        self.assertTrue(finding["code"].startswith("cronograma-"))

    def test_an_activity_without_months_is_an_error(self) -> None:
        self.act("2.1.1")["mes_fin"] = None
        self.assertEqual(_codes(self.findings(), "error"), ["cronograma-meses-faltantes"])

    def test_months_inside_the_duration_and_in_order(self) -> None:
        self.act("1.1.1")["mes_fin"] = 25
        self.assertEqual(_codes(self.findings(), "error"), ["cronograma-mes-fuera-de-rango"])
        self.act("1.1.1")["mes_fin"], self.act("1.1.1")["mes_inicio"] = 3, 5
        self.assertEqual(_codes(self.findings(), "error"), ["cronograma-meses-invertidos"])
        self.act("1.1.1")["mes_inicio"] = 0
        self.assertEqual(_codes(self.findings(), "error"), ["cronograma-mes-fuera-de-rango"])

    def test_an_unknown_stage_is_an_error_and_the_three_stages_are_valid(self) -> None:
        for code, etapa in (("1.1.1", "preinversion"), ("1.1.2", "inversion"), ("2.2.2", "operacion")):
            self.act(code)["etapa"] = etapa
        self.assertEqual(self.findings(), [])
        self.act("2.2.2")["etapa"] = "cierre"
        self.assertEqual(_codes(self.findings(), "error"), ["cronograma-etapa-invalida"])

    def test_a_product_without_a_critical_activity_warns(self) -> None:
        for code in ("2.1.1", "2.1.2"):
            self.act(code)["ruta_critica"] = False
        found = self.findings()
        self.assertEqual(_codes(found), ["cronograma-sin-ruta-critica"])
        self.assertEqual((found[0]["severity"], found[0]["node"]), ("warning", "2.1"))

    def test_without_milestones_file_a_single_warning(self) -> None:
        self.write()
        found = self.mod.findings(self.run_root)
        self.assertEqual(_codes(found), ["cronograma-hitos-faltantes"])
        self.assertEqual(found[0]["severity"], "warning")

    def test_milestones_file_with_the_wrong_schema_is_an_error(self) -> None:
        self.assertEqual(_codes(self.findings({"schema": "otro", "hitos": []}), "error"), ["cronograma-hitos-invalido"])

    def test_milestone_rules(self) -> None:
        milestones = _milestones()
        milestones["hitos"][0]["mes"] = 30
        self.assertEqual(_codes(self.findings(milestones)), ["cronograma-hito-mes-fuera-de-rango"])
        milestones = _milestones()
        milestones["hitos"][1]["actividades"] = ["1.1.1", "9.9.9"]
        self.assertEqual(_codes(self.findings(milestones)), ["cronograma-hito-actividad-desconocida"])
        milestones = _milestones()
        milestones["hitos"][2]["verificacion"] = ""
        found = self.findings(milestones)
        self.assertEqual(_codes(found), ["cronograma-hito-sin-verificacion"])
        self.assertEqual(found[0]["severity"], "warning")
        milestones = _milestones()
        milestones["hitos"][3]["codigo"] = "H1"
        self.assertEqual(_codes(self.findings(milestones)), ["cronograma-hito-codigo-duplicado"])
        milestones = _milestones()
        milestones["hitos"][4]["nombre"] = " "
        self.assertEqual(_codes(self.findings(milestones)), ["cronograma-hito-sin-nombre"])

    def test_more_than_three_months_without_a_milestone_after_month_three_warns(self) -> None:
        found = self.findings(_milestones((3, 8, 11, 14, 17, 20, 23)))
        self.assertEqual(_codes(found), ["cronograma-hitos-espaciados"])
        self.assertEqual(found[0]["severity"], "warning")
        self.assertIn("4 y 7", found[0]["message"])

    def test_three_months_without_a_milestone_is_fine_and_the_first_quarter_is_exempt(self) -> None:
        self.assertEqual(self.findings(_milestones((4, 8, 12, 16, 20, 24))), [])
        self.assertEqual(self.findings(_milestones((3, 7, 11, 15, 19, 23))), [])

    def test_a_gap_at_the_end_of_the_project_warns(self) -> None:
        self.assertEqual(_codes(self.findings(_milestones((3, 6, 9, 12, 15, 18)))), ["cronograma-hitos-espaciados"])

    def test_duration_falls_back_to_the_budget_then_to_the_last_month(self) -> None:
        self.chain["duracion_meses"] = None
        self.act("1.1.1")["mes_fin"] = 26
        (self.run_root / "artefactos" / "sgr").mkdir(parents=True)
        budget = self.run_root / "artefactos" / "sgr" / "presupuesto.json"
        budget.write_text(json.dumps({"schema": "morfeo.presupuesto-sgr/v1", "duracion_meses": 24}), encoding="utf-8")
        self.assertEqual(_codes(self.findings(), "error"), ["cronograma-mes-fuera-de-rango"])
        budget.unlink()
        self.write(milestones=_milestones())
        self.assertEqual(self.mod.duration(self.run_root, self.chain), 26)
        self.assertEqual(_codes(self.mod.findings(self.run_root), "error"), [])

    def test_no_value_chain_means_no_findings(self) -> None:
        self.assertEqual(self.mod.findings(self.run_root), [])


class CheckCli(_Run):
    def test_exit_codes_and_json(self) -> None:
        self.assertEqual(_cli("check", str(self.run_root)).returncode, 2)
        self.write(milestones=_milestones())
        result = _cli("check", str(self.run_root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"findings": []})
        self.act("1.1.1")["mes_fin"] = 40
        self.write(milestones=_milestones())
        result = _cli("check", str(self.run_root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("cronograma-mes-fuera-de-rango", result.stdout)


class Projection(_Run):
    def test_costs_are_spread_evenly_with_exact_totals_per_year(self) -> None:
        self.write(milestones=_milestones())
        data = self.mod.proyeccion(self.run_root)
        # 2.1.1: 1000 over months 7..18 = 83 a month, the remainder (87) on month 18.
        self.assertEqual(data["por_actividad"]["2.1.1"], [498, 502])
        self.assertEqual(data["por_actividad"]["1.1.1"], [1000, 0])
        self.assertEqual(data["por_actividad"]["2.1.2"], [0, 0])
        for code, row in data["por_actividad"].items():
            self.assertEqual(sum(row), self.act(code)["costo"], code)
        self.assertEqual([y["anio"] for y in data["anios"]], [1, 2])
        self.assertEqual(sum(y["valor"] for y in data["anios"]), 9000)
        self.assertAlmostEqual(sum(y["pct"] for y in data["anios"]), 100, places=1)

    def test_years_are_twelve_month_blocks(self) -> None:
        self.chain["duracion_meses"] = 36
        self.act("1.1.3")["mes_fin"] = 36
        self.act("1.1.3")["costo"] = 3600
        self.write(milestones=_milestones())
        data = self.mod.proyeccion(self.run_root)
        self.assertEqual(data["por_actividad"]["1.1.3"], [1200, 1200, 1200])
        self.assertEqual(len(data["anios"]), 3)

    def test_decimal_costs_keep_their_cents(self) -> None:
        self.act("1.1.1").update({"mes_inicio": 1, "mes_fin": 3, "costo": 100.01})
        self.write(milestones=_milestones())
        data = self.mod.proyeccion(self.run_root)
        self.assertEqual(data["por_actividad"]["1.1.1"], [100.01, 0])
        self.assertEqual(self.mod._spread(100.01, 3), [33.33, 33.33, 33.35])

    def test_activity_without_cost_counts_zero(self) -> None:
        self.act("1.1.1")["costo"] = None
        self.write(milestones=_milestones())
        data = self.mod.proyeccion(self.run_root)
        self.assertEqual(data["por_actividad"]["1.1.1"], [0, 0])
        self.assertEqual(sum(y["valor"] for y in data["anios"]), 8000)

    def test_cli_json(self) -> None:
        self.write(milestones=_milestones())
        result = _cli("proyeccion", str(self.run_root), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(json.loads(result.stdout)), {"anios", "por_actividad"})


class Render(_Run):
    def render(self) -> subprocess.CompletedProcess:
        return _cli("render", str(self.run_root))

    def test_render_writes_the_gantt_grouped_by_objective_and_product(self) -> None:
        self.act("2.2.2")["etapa"] = "operacion"
        self.act("1.1.1")["etapa"] = "preinversion"
        self.write(milestones=_milestones())
        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.tex.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("% GENERADO por scripts/cronograma_sgr.py"))
        self.assertEqual(text.count(r"\begin{ganttchart}"), 1)
        self.assertIn("]{1}{24}", text)
        self.assertIn(r"\gantttitle{Año 1}{12} \gantttitle{Año 2}{12}", text)
        self.assertIn(r"\gantttitlelist{1,...,24}{1}", text)
        order = [r"\ganttgroup{OE1}{1}{24}", r"{1.1 $\cdot$ Documentos de investigación}{1}{24}",
                 r"{1.1.1 $\cdot$ Levantar los datos clínicos de la cohorte $\star$}{1}{6}",
                 r"\ganttgroup{OE2}{1}{24}", r"{2.1 $\cdot$ Servicio de información implementado}{7}{20}",
                 r"{2.2.4 $\cdot$ Realizar la supervisión técnica del componente}{1}{6}",
                 r"\ganttmilestone{\textbf{H1} $\cdot$ Entrega del avance 1}{3}"]
        positions = [text.index(fragment) for fragment in order]
        self.assertEqual(positions, sorted(positions))
        bar_111 = next(line for line in text.splitlines() if "{1.1.1 $\\cdot$" in line)
        self.assertIn("fill=grisLabIA", bar_111)
        self.assertIn("draw=rojoLimitante", bar_111)
        bar_222 = next(line for line in text.splitlines() if "{2.2.2 $\\cdot$" in line)
        self.assertIn("fill=verdeGCPDS", bar_222)
        bar_223 = next(line for line in text.splitlines() if "{2.2.3 $\\cdot$" in line)
        self.assertIn("fill=azulUNAL", bar_223)
        self.assertNotIn(r"$\star$}", bar_223)
        self.assertIn(r"2.2.2 & Socializar la guía con las instituciones & Operación & 20 a 24 & Sí \\", text)
        self.assertIn(r"H1 & Entrega del avance 1 & 3 & 1.1.1 & Informe técnico aprobado por la supervisión \\", text)

    def test_render_is_deterministic(self) -> None:
        self.write(milestones=_milestones())
        self.assertEqual(self.render().returncode, 0)
        first = self.tex.read_bytes()
        self.assertEqual(self.render().returncode, 0)
        self.assertEqual(self.tex.read_bytes(), first)

    def test_render_without_milestones_has_no_milestone_rows(self) -> None:
        self.write()
        self.assertEqual(self.render().returncode, 0)
        text = self.tex.read_text(encoding="utf-8")
        self.assertNotIn(r"\ganttmilestone", text)
        self.assertNotIn("tab:cronograma_hitos", text)
        self.assertIn("]{1}{24}", text)

    def test_render_escapes_latex_specials(self) -> None:
        self.act("1.1.2")["nombre"] = "Integrar datos & fuentes al 100 %"
        self.write(milestones=_milestones())
        self.assertEqual(self.render().returncode, 0)
        self.assertIn(r"Integrar datos \& fuentes al 100 \%", self.tex.read_text(encoding="utf-8"))

    def test_render_refuses_with_error_findings(self) -> None:
        self.act("1.1.1")["mes_fin"] = 40
        self.write(milestones=_milestones())
        result = self.render()
        self.assertEqual(result.returncode, 1)
        self.assertIn("cronograma-mes-fuera-de-rango", result.stderr)
        self.assertFalse(self.tex.exists())

    def test_render_without_value_chain_is_bad_input(self) -> None:
        self.assertEqual(self.render().returncode, 2)
        self.assertFalse(self.tex.exists())

    def test_rendered_file_satisfies_the_sgr_schedule_rules_of_check_run(self) -> None:
        self.write(milestones=_milestones())
        self.assertEqual(self.render().returncode, 0)
        out = subprocess.run([sys.executable, str(CHECK_RUN), str(self.run_root), "--json", "--flujo", "sgr"],
                             capture_output=True, text=True)
        codes = {f["code"] for f in json.loads(out.stdout)["findings"]}
        self.assertNotIn("sgr-cronograma-sin-etapas", codes)
        self.assertNotIn("sgr-cronograma-sin-ruta-critica", codes)

    def test_rendered_file_keeps_the_docx_gantt_convention(self) -> None:
        self.write(milestones=_milestones())
        self.assertEqual(self.render().returncode, 0)
        text = self.tex.read_text(encoding="utf-8")
        first = text.index(r"\begin{ganttchart}")
        line = text[text.rfind("\n", 0, first) + 1:first]
        self.assertNotIn("%", line, "compile_tikz extracts the first \\begin{ganttchart}, which must be real code")
        swapped = _load(PREP_DOCX, "prep_docx_under_test").swap_figure_graphics(text, "fig_gantt.png")
        self.assertNotIn("ganttchart", swapped)
        self.assertIn(r"\includegraphics[width=\linewidth]{fig_gantt.png}", swapped)
        self.assertIn(r"\label{tab:cronograma}", swapped)


class BaseRun(_Run):
    sgr = False

    def test_render_refuses_in_a_base_run_and_keeps_the_hand_written_section(self) -> None:
        self.write(milestones=_milestones())
        self.tex.write_text("\\section{Cronograma de actividades}\nEscrito por el redactor.\n", encoding="utf-8")
        before = self.tex.read_bytes()
        result = _cli("render", str(self.run_root))
        self.assertEqual(result.returncode, 2)
        self.assertIn("flujo sgr", result.stderr)
        self.assertEqual(self.tex.read_bytes(), before)

    def test_a_base_run_without_sgr_data_has_no_schedule_findings(self) -> None:
        self.assertEqual(self.mod.findings(self.run_root), [])


class KitCopy(unittest.TestCase):
    def test_kit_copy_is_byte_identical(self) -> None:
        kit = REPO / "src" / "morfeo" / "_kit" / "scripts" / "cronograma_sgr.py"
        self.assertEqual(kit.read_bytes(), SCRIPT.read_bytes())


if __name__ == "__main__":
    unittest.main()
