"""scripts/cadena_valor_sgr.py: the SGR value chain as data (odd/tasks/sgr-cadena-estilo.md, S6).

`artefactos/sgr/cadena_valor.json` is seeded from the approved objective tree,
validated by `check` and rendered by `render` into
`redaccion/sections/23_cadena_valor.tex`, so annex A23 is never hand-written.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "cadena_valor_sgr.py"

TREE = {
    "groups": [
        {"id": "OE1", "from": "SP1", "title": "OE1", "objective": "Aumentar la información oportuna sobre la salud mental",
         "means": [{"id": "m1", "from": "r1", "text": "Fortalecer el levantamiento de datos clínicos"},
                   {"id": "m2", "from": "r2", "text": "Integrar las fuentes de información existentes"}]},
        {"id": "OE2", "from": "SP2", "title": "OE2", "objective": "Ampliar la capacidad tecnológica del territorio",
         "means": [{"id": "m3", "from": "r3", "text": "Construir modelos de tamizaje con IA"}]},
    ],
    "trunk": {"label": "OBJETIVO GENERAL", "text": "Mejorar la detección temprana de la depresión en estudiantes"},
    "branches": [{"id": "f1", "from": "b1", "text": "Reducir la deserción estudiantil"}],
    "crown": {"label": "FIN ÚLTIMO", "text": "Mejorar el bienestar de la población estudiantil"},
}


def _load():
    spec = importlib.util.spec_from_file_location("cadena_valor_sgr_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_run(tmp: Path, tree: dict | None = TREE) -> Path:
    run = tmp / "run"
    (run / "redaccion" / "sections").mkdir(parents=True)
    (run / "artefactos" / "arboles").mkdir(parents=True)
    if tree is not None:
        (run / "artefactos" / "arboles" / "arbol_objetivos.json").write_text(
            json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    return run


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def _valid_chain() -> dict:
    """A chain that passes every rule: 2 OEs, ≥2 technical activities per product,
    administration and supervision under each OE's last product."""
    def activity(code: str, name: str, tipo: str = "tecnica", medio: str | None = None,
                 start: int = 1, end: int = 6, cost: int = 1000) -> dict:
        return {"codigo": code, "nombre": name, "tipo": tipo, "ruta_critica": tipo == "tecnica",
                "mes_inicio": start, "mes_fin": end, "costo": cost, "medio": medio}

    def product(code: str, name: str, activities: list[dict]) -> dict:
        return {"codigo": code, "codigo_dnp": "3906001", "nombre": name,
                "medido_a_traves_de": "Número de documentos", "indicador": "Documentos elaborados",
                "unidad": "Número", "meta": 2, "actividades": activities}

    return {
        "schema": "morfeo.cadena-valor-sgr/v1",
        "duracion_meses": 24,
        "arbol_hash": None,
        "objetivos": [
            {"id": "OE1", "texto": TREE["groups"][0]["objective"], "productos": [
                product("1.1", "Documentos de investigación", [
                    activity("1.1.1", "Levantar los datos clínicos de la cohorte", medio="m1"),
                    activity("1.1.2", "Integrar las fuentes de información", medio="m2"),
                    activity("1.1.3", "Realizar la gestión administrativa del proyecto", "administracion", start=1, end=24),
                    activity("1.1.4", "Realizar la supervisión técnica del proyecto", "supervision", start=1, end=24),
                ]),
            ]},
            {"id": "OE2", "texto": TREE["groups"][1]["objective"], "productos": [
                product("2.1", "Servicio de información implementado", [
                    activity("2.1.1", "Construir los modelos de tamizaje", medio="m3", start=7, end=18),
                    activity("2.1.2", "Validar los modelos con la cohorte", start=12, end=20, cost=0),
                ]),
                product("2.2", "Documentos de lineamientos técnicos", [
                    activity("2.2.1", "Redactar la guía de uso", start=18, end=22),
                    activity("2.2.2", "Socializar la guía con las instituciones", start=20, end=24),
                    activity("2.2.3", "Realizar la gestión administrativa del componente", "administracion"),
                    activity("2.2.4", "Realizar la supervisión técnica del componente", "supervision"),
                ]),
            ]},
        ],
    }


def _codes(findings: list[dict], severity: str | None = None) -> list[str]:
    return [f["code"] for f in findings if severity is None or f["severity"] == severity]


class Init(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_root = _make_run(Path(tmp.name))
        self.chain_path = self.run_root / "artefactos" / "sgr" / "cadena_valor.json"

    def test_init_seeds_one_objective_per_group_with_its_verbatim_text(self) -> None:
        result = _cli("init", str(self.run_root))
        self.assertEqual(result.returncode, 0, result.stderr)
        chain = json.loads(self.chain_path.read_text(encoding="utf-8"))
        self.assertEqual(chain["schema"], "morfeo.cadena-valor-sgr/v1")
        self.assertEqual([o["id"] for o in chain["objetivos"]], ["OE1", "OE2"])
        self.assertEqual([o["texto"] for o in chain["objetivos"]], [g["objective"] for g in TREE["groups"]])
        tree_bytes = (self.run_root / "artefactos" / "arboles" / "arbol_objetivos.json").read_bytes()
        self.assertEqual(chain["arbol_hash"], hashlib.sha256(tree_bytes).hexdigest())
        self.assertIsNone(chain["duracion_meses"])

    def test_init_seeds_one_product_per_objective_and_one_activity_per_means(self) -> None:
        _cli("init", str(self.run_root))
        chain = json.loads(self.chain_path.read_text(encoding="utf-8"))
        oe1, oe2 = chain["objetivos"]
        self.assertEqual([p["codigo"] for p in oe1["productos"]], ["1.1"])
        self.assertEqual([p["codigo"] for p in oe2["productos"]], ["2.1"])
        acts = oe1["productos"][0]["actividades"]
        self.assertEqual([a["codigo"] for a in acts], ["1.1.1", "1.1.2", "1.1.3", "1.1.4"])
        self.assertEqual([a["tipo"] for a in acts], ["tecnica", "tecnica", "administracion", "supervision"])
        self.assertEqual([a["medio"] for a in acts], ["m1", "m2", None, None])
        self.assertEqual(acts[0]["nombre"], "Fortalecer el levantamiento de datos clínicos")
        self.assertEqual([a["tipo"] for a in oe2["productos"][0]["actividades"]],
                         ["tecnica", "administracion", "supervision"])
        product = oe1["productos"][0]
        self.assertIsNone(product["codigo_dnp"])
        self.assertIsNone(product["meta"])
        for key in ("nombre", "medido_a_traves_de", "indicador", "unidad"):
            self.assertIn(key, product)
        for key in ("ruta_critica", "mes_inicio", "mes_fin", "costo"):
            self.assertIn(key, acts[0])

    def test_init_takes_the_duration_when_given(self) -> None:
        _cli("init", str(self.run_root), "--duracion-meses", "24")
        self.assertEqual(json.loads(self.chain_path.read_text(encoding="utf-8"))["duracion_meses"], 24)

    def test_init_refuses_to_overwrite_without_force(self) -> None:
        _cli("init", str(self.run_root))
        self.chain_path.write_text('{"edited": true}', encoding="utf-8")
        result = _cli("init", str(self.run_root))
        self.assertEqual(result.returncode, 2)
        self.assertIn("--force", result.stderr)
        self.assertEqual(self.chain_path.read_text(encoding="utf-8"), '{"edited": true}')
        self.assertEqual(_cli("init", str(self.run_root), "--force").returncode, 0)
        self.assertIn("objetivos", json.loads(self.chain_path.read_text(encoding="utf-8")))

    def test_init_without_the_objective_tree_is_bad_input(self) -> None:
        (self.run_root / "artefactos" / "arboles" / "arbol_objetivos.json").unlink()
        result = _cli("init", str(self.run_root))
        self.assertEqual(result.returncode, 2)
        self.assertIn("arbol_objetivos.json", result.stderr)
        self.assertFalse(self.chain_path.exists())


class Check(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _load()
        self.chain = _valid_chain()

    def findings(self, chain: dict | None = None, budget_phase: bool = False) -> list[dict]:
        return self.mod.chain_findings(chain or self.chain, TREE, budget_phase=budget_phase)

    def test_a_complete_chain_is_clean(self) -> None:
        self.assertEqual(self.findings(), [])
        self.assertEqual(self.findings(budget_phase=True), [])

    def test_a_non_text_mga_evaluation_is_an_error(self) -> None:
        self.chain["evaluacion_mga"] = ["no", "texto"]
        codes = [f["code"] for f in self.findings()]
        self.assertIn("cadena-evaluacion-mga", codes)

    def test_findings_follow_the_check_run_shape(self) -> None:
        self.chain["objetivos"][0]["texto"] = "Otro objetivo"
        finding = self.findings()[0]
        self.assertEqual(set(finding), {"severity", "code", "message", "node"})
        self.assertEqual(finding["node"], "OE1")
        self.assertTrue(finding["code"].startswith("cadena-"))

    def test_objective_text_must_equal_the_tree(self) -> None:
        self.chain["objetivos"][1]["texto"] = "Ampliar otra cosa"
        self.assertEqual(_codes(self.findings(), "error"), ["cadena-objetivo-distinto"])
        self.chain["objetivos"][1]["texto"] = TREE["groups"][1]["objective"] + "."
        self.assertEqual(self.findings(), [], "trailing punctuation is not a different text")

    def test_objective_count_must_match_the_tree(self) -> None:
        del self.chain["objetivos"][1]
        self.assertIn("cadena-objetivos-numero", _codes(self.findings(), "error"))

    def test_every_product_has_two_technical_activities(self) -> None:
        acts = self.chain["objetivos"][1]["productos"][0]["actividades"]
        del acts[1]
        self.assertEqual(_codes(self.findings(), "error"), ["cadena-producto-pocas-actividades"])

    def test_administration_and_supervision_under_the_last_product(self) -> None:
        last = self.chain["objetivos"][1]["productos"][1]["actividades"]
        moved = last.pop(2)
        last[-1]["codigo"] = "2.2.3"
        self.assertIn("cadena-gestion-faltante", _codes(self.findings(), "error"))
        first = self.chain["objetivos"][1]["productos"][0]["actividades"]
        moved["codigo"] = "2.1.3"
        first.append(moved)
        self.assertIn("cadena-gestion-fuera-de-lugar", _codes(self.findings(), "error"))

    def test_a_repeated_administration_activity_is_an_error(self) -> None:
        acts = self.chain["objetivos"][0]["productos"][0]["actividades"]
        acts.append(dict(acts[2], codigo="1.1.5"))
        self.assertEqual(_codes(self.findings(), "error"), ["cadena-gestion-repetida"])

    def test_codes_are_consistent_with_their_parents(self) -> None:
        self.chain["objetivos"][1]["productos"][0]["codigo"] = "1.1"
        self.assertIn("cadena-codigo-inconsistente", _codes(self.findings(), "error"))
        chain = _valid_chain()
        chain["objetivos"][0]["productos"][0]["actividades"][1]["codigo"] = "1.2.2"
        self.assertEqual(_codes(self.findings(chain), "error"), ["cadena-codigo-inconsistente"])

    def test_codes_are_unique(self) -> None:
        self.chain["objetivos"][0]["productos"][0]["actividades"][1]["codigo"] = "1.1.1"
        self.assertIn("cadena-codigo-duplicado", _codes(self.findings(), "error"))

    def test_banned_mga_verb_in_an_activity_name(self) -> None:
        self.chain["objetivos"][0]["productos"][0]["actividades"][0]["nombre"] = "Fortalecer el levantamiento de datos"
        found = self.findings()
        self.assertEqual(_codes(found, "error"), ["cadena-verbo-prohibido"])
        self.assertEqual(found[0]["node"], "1.1.1")

    def test_banned_verb_ignores_case_and_accents_but_only_the_first_word(self) -> None:
        acts = self.chain["objetivos"][0]["productos"][0]["actividades"]
        acts[0]["nombre"] = "IMPLEMENTAR la plataforma"
        self.assertEqual(_codes(self.findings(), "error"), ["cadena-verbo-prohibido"])
        acts[0]["nombre"] = "Levantar datos para fortalecer el sistema"
        self.assertEqual(self.findings(), [])

    def test_banned_verb_does_not_apply_to_product_names(self) -> None:
        self.chain["objetivos"][0]["productos"][0]["nombre"] = "Desarrollar documentos de investigación"
        self.assertEqual(self.findings(), [])

    def test_banned_verb_list_is_the_mga_list(self) -> None:
        self.assertEqual(self.mod.MGA_BANNED_ACTIVITY_VERBS, frozenset({
            "apropiar", "asegurar", "colaborar", "consolidar", "desarrollar", "fomentar", "fortalecer",
            "garantizar", "implementar", "impulsar", "mejorar", "movilizar", "proponer", "promover"}))

    def test_dnp_code_format(self) -> None:
        product = self.chain["objetivos"][0]["productos"][0]
        product["codigo_dnp"] = "4001001"
        self.assertEqual(_codes(self.findings(), "error"), ["cadena-codigo-dnp-invalido"])
        product["codigo_dnp"] = None
        found = self.findings()
        self.assertEqual(_codes(found), ["cadena-codigo-dnp-faltante"])
        self.assertEqual(found[0]["severity"], "warning")

    def test_months_inside_the_duration_and_in_order(self) -> None:
        act = self.chain["objetivos"][0]["productos"][0]["actividades"][0]
        act["mes_fin"] = 25
        self.assertEqual(_codes(self.findings(), "error"), ["cadena-mes-fuera-de-rango"])
        act["mes_fin"], act["mes_inicio"] = 3, 5
        self.assertEqual(_codes(self.findings(), "error"), ["cadena-meses-invertidos"])
        act["mes_inicio"] = 0
        self.assertEqual(_codes(self.findings(), "error"), ["cadena-mes-fuera-de-rango"])

    def test_without_duration_only_the_lower_bound_applies(self) -> None:
        self.chain["duracion_meses"] = None
        self.chain["objetivos"][0]["productos"][0]["actividades"][0]["mes_fin"] = 40
        self.assertEqual(self.findings(), [])

    def test_costs_are_not_negative(self) -> None:
        self.chain["objetivos"][0]["productos"][0]["actividades"][0]["costo"] = -5
        self.assertEqual(_codes(self.findings(), "error"), ["cadena-costo-negativo"])

    def test_missing_cost_warns_only_from_the_budget_phase_on(self) -> None:
        self.chain["objetivos"][0]["productos"][0]["actividades"][0]["costo"] = None
        self.assertEqual(self.findings(), [])
        found = self.findings(budget_phase=True)
        self.assertEqual(_codes(found), ["cadena-costo-faltante"])
        self.assertEqual(found[0]["severity"], "warning")

    def test_cost_sum(self) -> None:
        self.assertEqual(self.mod.total_cost(self.chain), 9000)
        self.chain["objetivos"][0]["productos"][0]["actividades"][0]["costo"] = None
        self.assertEqual(self.mod.total_cost(self.chain), 8000)

    def test_activity_type_is_known(self) -> None:
        self.chain["objetivos"][0]["productos"][0]["actividades"][0]["tipo"] = "otra"
        self.assertIn("cadena-tipo-invalido", _codes(self.findings(), "error"))

    def test_wrong_schema_is_an_error(self) -> None:
        self.chain["schema"] = "otro"
        self.assertEqual(_codes(self.findings(), "error"), ["cadena-esquema"])

    def test_stage_is_optional_and_takes_the_three_mga_stages(self) -> None:
        acts = self.chain["objetivos"][0]["productos"][0]["actividades"]
        for act, etapa in zip(acts, ("preinversion", "inversion", "operacion")):
            act["etapa"] = etapa
        self.assertEqual(self.findings(), [])
        acts[3]["etapa"] = None
        self.assertEqual(self.findings(), [])

    def test_an_unknown_stage_is_an_error(self) -> None:
        self.chain["objetivos"][1]["productos"][0]["actividades"][0]["etapa"] = "ejecucion"
        found = self.findings()
        self.assertEqual(_codes(found, "error"), ["cadena-etapa-invalida"])
        self.assertEqual(found[0]["node"], "2.1.1")


class CheckCli(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_root = _make_run(Path(tmp.name))
        self.chain_path = self.run_root / "artefactos" / "sgr" / "cadena_valor.json"

    def write(self, chain: dict) -> None:
        self.chain_path.parent.mkdir(parents=True, exist_ok=True)
        self.chain_path.write_text(json.dumps(chain, ensure_ascii=False), encoding="utf-8")

    def test_check_exits_1_on_errors_and_reports_json(self) -> None:
        _cli("init", str(self.run_root))
        result = _cli("check", str(self.run_root), "--json")
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertIn("cadena-nombre-vacio", _codes(data["findings"], "error"))
        self.assertIn("cadena-verbo-prohibido", _codes(data["findings"], "error"))
        self.assertIn("costo_total", data)

    def test_check_exits_0_on_a_clean_chain_with_the_cost_total(self) -> None:
        self.write(_valid_chain())
        result = _cli("check", str(self.run_root), "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data["costo_total"], 9000)
        self.assertEqual(_codes(data["findings"], "error"), [])
        text = _cli("check", str(self.run_root))
        self.assertIn("9.000", text.stdout)

    def test_check_warns_when_the_tree_changed_after_seeding(self) -> None:
        chain = _valid_chain()
        chain["arbol_hash"] = "0" * 64
        self.write(chain)
        data = json.loads(_cli("check", str(self.run_root), "--json").stdout)
        self.assertIn("cadena-arbol-modificado", _codes(data["findings"], "warning"))

    def test_check_reads_the_budget_phase_from_the_budget_section(self) -> None:
        chain = _valid_chain()
        chain["objetivos"][0]["productos"][0]["actividades"][0]["costo"] = None
        self.write(chain)
        self.assertNotIn("cadena-costo-faltante",
                         _codes(json.loads(_cli("check", str(self.run_root), "--json").stdout)["findings"]))
        (self.run_root / "redaccion" / "sections" / "13_presupuesto.tex").write_text("\\section{Presupuesto}\n")
        self.assertIn("cadena-costo-faltante",
                      _codes(json.loads(_cli("check", str(self.run_root), "--json").stdout)["findings"]))

    def test_invalid_json_is_an_error_finding(self) -> None:
        self.chain_path.parent.mkdir(parents=True)
        self.chain_path.write_text("{no", encoding="utf-8")
        result = _cli("check", str(self.run_root), "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(_codes(json.loads(result.stdout)["findings"]), ["cadena-json-invalido"])

    def test_check_without_the_file_is_bad_input(self) -> None:
        self.assertEqual(_cli("check", str(self.run_root)).returncode, 2)


class Render(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_root = _make_run(Path(tmp.name))
        self.chain_path = self.run_root / "artefactos" / "sgr" / "cadena_valor.json"
        self.tex = self.run_root / "redaccion" / "sections" / "23_cadena_valor.tex"

    def write(self, chain: dict) -> None:
        self.chain_path.parent.mkdir(parents=True, exist_ok=True)
        self.chain_path.write_text(json.dumps(chain, ensure_ascii=False), encoding="utf-8")

    def test_render_writes_the_annex_table(self) -> None:
        chain = _valid_chain()
        chain["objetivos"][0]["productos"][0]["nombre"] = "Documentos 100% de investigación & datos_abiertos"
        self.write(chain)
        result = _cli("render", str(self.run_root))
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.tex.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("% GENERADO por scripts/cadena_valor_sgr.py"))
        self.assertIn("\\section{Cadena de valor}", text)
        self.assertIn("\\begin{xltabular}", text)
        for header in ("Objetivo específico", "Producto", "Actividades", "Costo"):
            self.assertIn(f"\\textbf{{{header}}}", text)
        self.assertIn("Documentos 100\\% de investigación \\& datos\\_abiertos", text)
        self.assertIn("3906001", text)
        self.assertIn("Medido a través de: Número de documentos", text)
        self.assertIn("Meta: 2", text)
        self.assertIn("1.1.1 Levantar los datos clínicos de la cohorte", text)
        self.assertIn("Ruta crítica: sí", text)
        self.assertIn("Ruta crítica: no", text)
        self.assertIn("Meses: 7 a 18", text)
        self.assertIn("\\$\\,9.000", text)
        self.assertIn(TREE["groups"][1]["objective"], text)
        self.assertNotIn("--", text.replace("% ", ""))

    def test_render_appends_the_mga_evaluation_after_the_table(self) -> None:
        chain = _valid_chain()
        chain["evaluacion_mga"] = "La alternativa se evalúa por costo eficiencia.\n\nLa TSD es del 9 % & se aplica al flujo."
        self.write(chain)
        result = _cli("render", str(self.run_root))
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.tex.read_text(encoding="utf-8")
        self.assertIn("\\subsection*{Evaluación MGA}", text)
        self.assertLess(text.index("\\end{xltabular}"), text.index("Evaluación MGA"))
        self.assertIn("La alternativa se evalúa por costo eficiencia.\n\nLa TSD es del 9 \\% \\& se aplica al flujo.", text)

    def test_render_without_mga_evaluation_has_no_subsection(self) -> None:
        self.write(_valid_chain())
        _cli("render", str(self.run_root))
        self.assertNotIn("Evaluación MGA", self.tex.read_text(encoding="utf-8"))

    def test_render_is_deterministic(self) -> None:
        self.write(_valid_chain())
        _cli("render", str(self.run_root))
        first = self.tex.read_bytes()
        _cli("render", str(self.run_root))
        self.assertEqual(self.tex.read_bytes(), first)
        mod = _load()
        self.assertEqual(mod.render_tex(_valid_chain()), mod.render_tex(copy.deepcopy(_valid_chain())))

    def test_render_refuses_on_error_findings(self) -> None:
        chain = _valid_chain()
        chain["objetivos"][0]["productos"][0]["actividades"][0]["nombre"] = "Implementar la plataforma"
        self.write(chain)
        result = _cli("render", str(self.run_root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("cadena-verbo-prohibido", result.stderr)
        self.assertFalse(self.tex.exists())

    def test_render_accepts_warnings_and_marks_pending_values(self) -> None:
        chain = _valid_chain()
        chain["objetivos"][0]["productos"][0]["codigo_dnp"] = None
        chain["objetivos"][0]["productos"][0]["actividades"][0]["costo"] = None
        self.write(chain)
        self.assertEqual(_cli("render", str(self.run_root)).returncode, 0)
        text = self.tex.read_text(encoding="utf-8")
        self.assertIn("Por asignar", text)
        self.assertIn("Código DNP: por definir", text)


class KitCopy(unittest.TestCase):
    def test_kit_copy_is_byte_identical(self) -> None:
        kit = REPO / "src" / "morfeo" / "_kit" / "scripts" / "cadena_valor_sgr.py"
        self.assertEqual(kit.read_bytes(), SCRIPT.read_bytes())


if __name__ == "__main__":
    unittest.main()
