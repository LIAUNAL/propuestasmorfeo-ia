"""scripts/productos_sgr.py: products, human talent and indicators as data (odd/tasks/sgr-productos-indicadores.md,
S2 to S4).

`artefactos/sgr/productos.json` is validated by `check` against the value
chain, the alliance, the budget and the call's rubric (talent minimums, CTeI
product minimum and the Conv 54 2.5 preview), rendered by `render` into
sections 36 and 37 and the SGR §15, and summarised for the judge by `datos`.
A base run's §15 is never touched (S1).
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
SCRIPT = REPO / "scripts" / "productos_sgr.py"
RUBRICS = REPO / "scripts" / "rubricas_sgr"
HEADER = "% GENERADO por scripts/productos_sgr.py"
STEMS = ("36_talento_humano", "37_indicadores")
RENDERED = STEMS + ("15_productos_esperados",)
sys.path.insert(0, str(REPO / "tests"))

from test_alianza_territorio_sgr import _alliance  # noqa: E402
from test_cadena_valor_sgr import TREE, _valid_chain  # noqa: E402
from test_presupuesto_sgr import _budget, _item  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _productos() -> dict:
    """Products that pass every rule against _valid_chain(), _alliance(), _budget_with_talent() and the
    Conv 54 and Conv 56 rubrics."""
    return {
        "schema": "morfeo.productos-sgr/v1",
        "talento": [
            {"categoria": "joven_investigador", "cantidad": 6, "entidad": "E1",
             "perfil": "Joven investigador en analítica de datos clínicos",
             "formacion": "Estudiante de pregrado en ingeniería con el 70 % de los créditos",
             "actividades": ["1.1.1", "1.1.2"], "duracion_meses": 12, "valor_mensual": 2_000_000,
             "producto_final": "Artículo en revista Publindex y un producto de divulgación"},
            {"categoria": "maestria", "cantidad": 2, "entidad": "E1",
             "perfil": "Estudiante de maestría en modelos de tamizaje",
             "formacion": "Admitido a una maestría en modalidad de investigación",
             "actividades": ["2.1.1"], "duracion_meses": 24, "valor_mensual": 3_000_000,
             "producto_final": "Artículo tipo A y un producto de divulgación"},
            {"categoria": "posdoctorado", "cantidad": 1, "entidad": "E1",
             "perfil": "Doctor en estancia posdoctoral en aprendizaje automático",
             "formacion": "Doctorado en ingeniería con publicaciones en salud digital",
             "actividades": ["2.1.1", "2.1.2"], "duracion_meses": 24, "valor_mensual": 7_000_000,
             "producto_final": "Dos artículos tipo TOP o A e informe técnico final"},
            {"categoria": "profesional", "cantidad": 1, "entidad": "E2", "perfil": "Profesional de apoyo clínico",
             "formacion": "Psicólogo con experiencia en tamizaje", "actividades": ["2.1.2"],
             "duracion_meses": None, "valor_mensual": None, "producto_final": "Protocolo de validación"},
        ],
        "productos_ctei": [
            {"tipo": "nuevo_conocimiento", "subtipo": "Artículo de investigación en revista Publindex",
             "categoria": "B", "cantidad": 6, "adicional": False, "producto_cadena": "1.1",
             "descripcion": "Artículos de los jóvenes investigadores"},
            {"tipo": "nuevo_conocimiento", "subtipo": "Artículo de investigación tipo A", "categoria": "A",
             "cantidad": 4, "adicional": False, "producto_cadena": "1.1",
             "descripcion": "Artículos de la maestría y del posdoctorado"},
            {"tipo": "nuevo_conocimiento", "subtipo": "Artículo de investigación tipo TOP", "categoria": "TOP",
             "cantidad": 2, "adicional": True, "producto_cadena": "2.1",
             "descripcion": "Artículos sobre la validación del modelo"},
            {"tipo": "desarrollo_tecnologico", "subtipo": "Software registrado", "categoria": "otro",
             "cantidad": 1, "adicional": True, "producto_cadena": "2.1",
             "descripcion": "Registro del software de tamizaje"},
        ],
        "divulgacion": {
            "introduccion": "La estrategia de divulgación pública de la ciencia acercará los resultados a los "
                            "estudiantes y al personal de salud.",
            "publicos": ["Estudiantes universitarios", "Personal de salud"],
            "medios": ["Podcast institucional", "Redes sociales de la universidad"],
            "productos": ["Serie de cápsulas de video", "Cartilla divulgativa"],
            "responsable": "E1",
            "cronograma": [{"mes": 6, "accion": "Lanzamiento de la serie"},
                           {"mes": 18, "accion": "Publicación de la cartilla"}],
            "costeada": True,
        },
        "indicadores_gestion": [
            {"indicador": "Informes de supervisión del proyecto", "codigo": None, "meta": 8, "unidad": "Número",
             "formula": "Informes entregados / informes programados", "tipo_fuente": "Informe de supervisión",
             "periodicidad": "Trimestral"},
            {"indicador": "Informes técnicos y financieros presentados", "codigo": "0900G127", "meta": 8,
             "unidad": "Número", "formula": "Suma de informes presentados", "tipo_fuente": "Informe",
             "periodicidad": "Trimestral"},
        ],
    }


def _budget_with_talent() -> dict:
    """_budget() plus one talento_humano item per paid talent entry of _productos()."""
    budget = _budget()
    budget["items"] += [
        _item("P9", "talento_humano", "mano_obra_calificada", "E1", "sgr", 24_000_000, ["1.1.1"], cantidad=6),
        _item("P10", "talento_humano", "mano_obra_calificada", "E1", "sgr", 72_000_000, ["2.1.1"], cantidad=2),
        _item("P11", "talento_humano", "mano_obra_calificada", "E1", "sgr", 168_000_000, ["2.1.1"]),
    ]
    return budget


def _write(run: Path, name: str, data) -> Path:
    path = run / "artefactos" / "sgr" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _make_run(tmp: Path, productos: dict | None = None, flujo: str | None = "sgr", budget=False,
              chain: bool = True, alliance: bool = True) -> Path:
    if flujo:
        (tmp / ".morfeo").mkdir(exist_ok=True)
        (tmp / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = tmp / "run"
    (run / "redaccion" / "sections").mkdir(parents=True, exist_ok=True)
    (run / "artefactos" / "arboles").mkdir(parents=True, exist_ok=True)
    (run / "artefactos" / "arboles" / "arbol_objetivos.json").write_text(json.dumps(TREE, ensure_ascii=False),
                                                                          encoding="utf-8")
    if chain:
        _write(run, "cadena_valor.json", _valid_chain())
    if alliance:
        _write(run, "alianza.json", _alliance())
    if budget:
        _write(run, "presupuesto.json", budget if isinstance(budget, dict) else _budget_with_talent())
    _write(run, "productos.json", productos if productos is not None else _productos())
    return run


def _rubric(run: Path, rid: str) -> None:
    folder = run / "artefactos" / "juez"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RUBRICS / f"{rid}.json", folder / "rubrica.json")


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def _codes(findings: list[dict], severity: str | None = None) -> list[str]:
    return [f["code"] for f in findings if severity is None or f["severity"] == severity]


def _talent(data: dict, categoria: str) -> dict:
    return next(t for t in data["talento"] if t["categoria"] == categoria)


class _Case(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.mod = _load("productos_sgr_under_test", SCRIPT)

    def run_with(self, productos: dict | None = None, rubric: str | None = None, **kwargs) -> Path:
        run = _make_run(Path(tempfile.mkdtemp(dir=self.tmp)), productos, **kwargs)
        if rubric:
            _rubric(run, rubric)
        return run

    def found(self, change=None, rubric: str | None = None, **kwargs) -> list[dict]:
        data = _productos()
        if change is not None:
            change(data)
        return self.mod.findings(self.run_with(data, rubric, **kwargs))


class Check(_Case):
    def test_valid_products_have_no_findings(self) -> None:
        self.assertEqual(self.found(), [])
        self.assertEqual(self.found(budget=True), [])
        self.assertEqual(self.found(rubric="conv54", budget=True), [])
        self.assertEqual(self.found(rubric="conv56"), [])

    def test_missing_file_is_silent_for_check_run_and_an_error_for_the_cli(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "productos.json").unlink()
        self.assertEqual(self.mod.findings(run), [])
        self.assertEqual(_codes(self.mod.check_findings(run)), ["productos-archivo-faltante"])
        self.assertEqual(_cli("check", str(run)).returncode, 2)

    def test_schema_and_invalid_json(self) -> None:
        self.assertEqual(_codes(self.found(lambda d: d.update(schema="otro"))), ["productos-esquema"])
        run = self.run_with()
        _write(run, "productos.json", "{no es json")
        self.assertEqual(_codes(self.mod.findings(run)), ["productos-json-invalido"])

    def test_without_chain_or_alliance_the_cross_checks_warn(self) -> None:
        found = self.found(chain=False, alliance=False)
        self.assertEqual(sorted(_codes(found, "warning")), ["productos-alianza-faltante", "productos-cadena-faltante"])
        self.assertEqual(_codes(found, "error"), [])

    def test_entity_ids_exist_in_the_alliance(self) -> None:
        def change(d):
            d["talento"][1]["entidad"] = "E99"
            d["divulgacion"]["responsable"] = "E77"
        hit = [f for f in self.found(change) if f["code"] == "productos-entidad-desconocida"]
        self.assertEqual([(f["severity"], f["node"]) for f in hit], [("error", "talento[2]"), ("error", "divulgacion")])
        self.assertIn("E99", hit[0]["message"])

    def test_activity_codes_and_chain_products_exist(self) -> None:
        def change(d):
            d["talento"][0]["actividades"] = ["1.1.1", "9.9.9"]
            d["productos_ctei"][2]["producto_cadena"] = "7.7"
        found = self.found(change)
        activity = [f for f in found if f["code"] == "productos-actividad-desconocida"]
        self.assertEqual([(f["severity"], f["node"]) for f in activity], [("error", "talento[1]")])
        self.assertIn("9.9.9", activity[0]["message"])
        product = [f for f in found if f["code"] == "productos-producto-desconocido"]
        self.assertEqual([(f["severity"], f["node"]) for f in product], [("error", "productos_ctei[3]")])

    def test_every_chain_product_has_dnp_code_indicator_unit_and_goal(self) -> None:
        run = self.run_with()
        chain = _valid_chain()
        chain["objetivos"][0]["productos"][0]["codigo_dnp"] = "1234567"
        chain["objetivos"][1]["productos"][1]["indicador"] = ""
        chain["objetivos"][1]["productos"][1]["meta"] = None
        _write(run, "cadena_valor.json", chain)
        hit = [f for f in self.mod.findings(run) if f["code"] == "productos-cadena-incompleta"]
        self.assertEqual([(f["severity"], f["node"]) for f in hit], [("warning", "1.1"), ("warning", "2.2")])
        self.assertIn("código DNP", hit[0]["message"])
        self.assertIn("indicador", hit[1]["message"])
        self.assertIn("meta", hit[1]["message"])

    def test_categories_types_and_quantities_are_validated(self) -> None:
        def change(d):
            d["talento"][3]["categoria"] = "investigador"
            d["productos_ctei"][3]["tipo"] = "patente"
            d["productos_ctei"][3]["categoria"] = "Q1"
            d["talento"][0]["cantidad"] = 0
        found = self.found(change)
        self.assertEqual([f["node"] for f in found if f["code"] == "productos-talento-categoria"], ["talento[4]"])
        self.assertEqual([f["node"] for f in found if f["code"] == "productos-ctei-tipo"],
                         ["productos_ctei[4]", "productos_ctei[4]"])
        self.assertIn("talento[1]", [f["node"] for f in found if f["code"] == "productos-valor-invalido"])
        self.assertTrue(all(f["severity"] == "error" for f in found
                            if f["code"] in ("productos-talento-categoria", "productos-ctei-tipo",
                                             "productos-valor-invalido")))

    def test_dissemination_months_stay_inside_the_duration(self) -> None:
        hit = [f for f in self.found(lambda d: d["divulgacion"]["cronograma"].append({"mes": 30, "accion": "X"}))
               if f["code"] == "productos-mes-fuera"]
        self.assertEqual([(f["severity"], f["node"]) for f in hit], [("error", "divulgacion.cronograma[3]")])

    def test_check_cli_exit_codes_and_json(self) -> None:
        run = self.run_with()
        result = _cli("check", str(run), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["vista_2_5"]["total"], 5)
        data = _productos()
        data["talento"][0]["entidad"] = "E99"
        bad = self.run_with(data)
        result = _cli("check", str(bad))
        self.assertEqual(result.returncode, 1)
        self.assertIn("productos-entidad-desconocida", result.stdout)
        self.assertEqual(_cli("check", str(self.tmp / "no-existe")).returncode, 2)


class TalentMinimums(_Case):
    def test_conv54_minimums_are_errors_when_below(self) -> None:
        def change(d):
            _talent(d, "joven_investigador")["cantidad"] = 5
            d["talento"] = [t for t in d["talento"] if t["categoria"] != "posdoctorado"]
        hit = [f for f in self.found(change, rubric="conv54") if f["code"] == "productos-talento-minimo"]
        self.assertEqual(len(hit), 2)
        self.assertTrue(all(f["severity"] == "error" for f in hit))
        messages = " ".join(f["message"] for f in hit)
        self.assertIn("Seis (6) jóvenes investigadores e innovadores", messages)
        self.assertIn("Un (1) doctor para la realización de una estancia posdoctoral.", messages)

    def test_conv56_sets_the_same_minimums(self) -> None:
        hit = self.found(lambda d: _talent(d, "maestria").update(cantidad=1), rubric="conv56")
        self.assertEqual([f["node"] for f in hit if f["code"] == "productos-talento-minimo"], ["talento"])
        self.assertIn("Dos (2) estudiantes de maestría en modalidad de investigación.",
                      next(f["message"] for f in hit if f["code"] == "productos-talento-minimo"))

    def test_without_a_rubric_there_is_no_minimum_check(self) -> None:
        found = self.found(lambda d: d.update(talento=[]))
        self.assertFalse([c for c in _codes(found) if c in ("productos-talento-minimo", "productos-minimo-ctei")])

    def test_talent_with_value_and_duration_matches_the_budget(self) -> None:
        hit = [f for f in self.found(lambda d: _talent(d, "joven_investigador").update(valor_mensual=2_500_000),
                                     budget=True)
               if f["code"] == "productos-talento-presupuesto"]
        self.assertEqual([(f["severity"], f["node"]) for f in hit], [("warning", "talento[1]")])
        self.assertIn("180.000.000", hit[0]["message"])

    def test_the_budget_match_is_per_entity(self) -> None:
        hit = self.found(lambda d: _talent(d, "maestria").update(entidad="E2"), budget=True)
        self.assertEqual([f["node"] for f in hit if f["code"] == "productos-talento-presupuesto"], ["talento[2]"])

    def test_without_the_budget_there_is_no_budget_check(self) -> None:
        found = self.found(lambda d: _talent(d, "joven_investigador").update(valor_mensual=2_500_000))
        self.assertNotIn("productos-talento-presupuesto", _codes(found))


class CteiProducts(_Case):
    def test_conv54_minimum_follows_the_talent_products(self) -> None:
        # 6 young researchers x 1 + 2 master's students x 1 + 1 postdoc x 2 = 10 products of numeral 10.
        hit = [f for f in self.found(lambda d: d["productos_ctei"][0].update(cantidad=5), rubric="conv54")
               if f["code"] == "productos-minimo-ctei"]
        self.assertEqual([(f["severity"], f["node"]) for f in hit], [("error", "productos_ctei")])
        self.assertIn("9", hit[0]["message"])
        self.assertIn("10", hit[0]["message"])

    def test_conv56_postdoc_delivers_one_product(self) -> None:
        # 6 + 2 + 1 = 9 in Conv 56.
        found = self.found(lambda d: d["productos_ctei"][0].update(cantidad=5), rubric="conv56")
        self.assertNotIn("productos-minimo-ctei", _codes(found))
        found = self.found(lambda d: d["productos_ctei"][0].update(cantidad=4), rubric="conv56")
        self.assertIn("productos-minimo-ctei", _codes(found, "error"))

    def test_the_minimum_grows_with_the_linked_talent(self) -> None:
        found = self.found(lambda d: _talent(d, "joven_investigador").update(cantidad=7), rubric="conv54")
        self.assertIn("productos-minimo-ctei", _codes(found))

    def test_additional_products_do_not_fill_the_minimum(self) -> None:
        found = self.found(lambda d: d["productos_ctei"][0].update(adicional=True), rubric="conv54")
        self.assertIn("productos-minimo-ctei", _codes(found))


class Preview25(_Case):
    def preview(self, ctei: list[dict], divulgacion="keep") -> dict:
        data = _productos()
        data["productos_ctei"] = data["productos_ctei"][:2] + ctei
        if divulgacion != "keep":
            data["divulgacion"] = divulgacion
        return self.mod.vista_2_5(self.run_with(data))

    @staticmethod
    def extra(categoria: str, cantidad: int = 1, tipo: str = "nuevo_conocimiento") -> dict:
        return {"tipo": tipo, "subtipo": "Artículo", "categoria": categoria, "cantidad": cantidad,
                "adicional": True, "producto_cadena": None, "descripcion": "Adicional"}

    def test_component_a_tiers(self) -> None:
        cases = [
            ([self.extra("TOP", 2), self.extra("B")], 3),
            ([self.extra("A"), self.extra("B", 2)], 2),
            ([self.extra("A"), self.extra("B")], 2),
            ([self.extra("B", 2)], 1),
            ([self.extra("otro")], 1),
            ([], 0),
        ]
        for ctei, points in cases:
            with self.subTest(ctei=[(c["categoria"], c["cantidad"]) for c in ctei]):
                self.assertEqual(self.preview(ctei)["A"], points)

    def test_social_appropriation_and_training_products_do_not_count(self) -> None:
        preview = self.preview([self.extra("A", 3, "apropiacion_social"), self.extra("A", 1, "formacion")])
        self.assertEqual(preview["A"], 0)

    def test_component_b_tiers(self) -> None:
        incomplete = dict(_productos()["divulgacion"], responsable=None)
        not_costed = dict(_productos()["divulgacion"], costeada=False)
        self.assertEqual(self.preview([])["B"], 2)
        self.assertEqual(self.preview([], incomplete)["B"], 1)
        self.assertEqual(self.preview([], not_costed)["B"], 1)
        self.assertEqual(self.preview([], None)["B"], 0)

    def test_total_adds_both_components(self) -> None:
        preview = self.preview([self.extra("TOP", 2), self.extra("B")])
        self.assertEqual((preview["A"], preview["B"], preview["total"]), (3, 2, 5))


class Dissemination(_Case):
    def test_missing_strategy_is_a_warning(self) -> None:
        hit = [f for f in self.found(lambda d: d.update(divulgacion=None)) if f["code"].startswith("productos-divul")]
        self.assertEqual([(f["severity"], f["code"]) for f in hit], [("warning", "productos-divulgacion-faltante")])

    def test_incomplete_or_uncosted_strategy_is_a_warning(self) -> None:
        def change(d):
            d["divulgacion"]["publicos"] = []
            d["divulgacion"]["costeada"] = False
        hit = [f for f in self.found(change) if f["code"] == "productos-divulgacion-incompleta"]
        self.assertEqual([f["severity"] for f in hit], ["warning"])
        self.assertIn("públicos", hit[0]["message"])
        self.assertIn("costeada", hit[0]["message"])


class ManagementIndicators(_Case):
    def test_supervision_and_technical_financial_reports_are_required(self) -> None:
        hit = [f for f in self.found(lambda d: d.update(indicadores_gestion=d["indicadores_gestion"][1:]))
               if f["code"] == "productos-indicadores-gestion"]
        self.assertEqual([f["severity"] for f in hit], ["warning"])
        self.assertIn("supervisión", hit[0]["message"])

    def test_each_one_needs_its_periodicity(self) -> None:
        hit = [f for f in self.found(lambda d: d["indicadores_gestion"][1].update(periodicidad=""))
               if f["code"] == "productos-indicadores-gestion"]
        self.assertEqual(len(hit), 1)
        self.assertIn("técnicos y financieros", hit[0]["message"])

    def test_no_management_indicators_names_both(self) -> None:
        hit = [f for f in self.found(lambda d: d.update(indicadores_gestion=[]))
               if f["code"] == "productos-indicadores-gestion"]
        self.assertIn("supervisión", hit[0]["message"])
        self.assertIn("técnicos y financieros", hit[0]["message"])


class Datos(_Case):
    def test_additional_products_and_talent(self) -> None:
        facts = self.mod.datos(self.run_with())
        self.assertEqual(facts["productos_adicionales"],
                         {"total": 3, "top_o_a": 2, "fuente": "artefactos/sgr/productos.json (productos_ctei)"})
        self.assertEqual(facts["talento"], {"joven_investigador": 6, "maestria": 2, "posdoctorado": 1,
                                            "profesional": 1})
        self.assertEqual(facts["fuente"], ["artefactos/sgr/productos.json"])

    def test_missing_file_gives_null_facts(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "productos.json").unlink()
        self.assertEqual(self.mod.datos(run), {"productos_adicionales": None, "talento": None, "fuente": []})

    def test_datos_cli_prints_json(self) -> None:
        result = _cli("datos", str(self.run_with()), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["productos_adicionales"]["total"], 3)


class Render(_Case):
    def sections(self, run: Path) -> dict[str, str]:
        return {stem: (run / "redaccion" / "sections" / f"{stem}.tex").read_text(encoding="utf-8")
                for stem in RENDERED}

    def test_render_writes_the_three_sections_with_the_header(self) -> None:
        run = self.run_with()
        result = _cli("render", str(run))
        self.assertEqual(result.returncode, 0, result.stderr)
        for stem, text in self.sections(run).items():
            with self.subTest(stem=stem):
                self.assertTrue(text.startswith(HEADER + "\n"))
                self.assertIn(f"{stem}.tex", result.stdout)

    def test_products_section_groups_the_chain_products_by_objective(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        text = self.sections(run)["15_productos_esperados"]
        self.assertIn(r"\textbf{Programa} & \textbf{Producto} & \textbf{Medido a través de} & "
                      r"\textbf{Indicador de producto} & \textbf{Unidad de medida} & \textbf{Descripción}", text)
        self.assertLess(text.index("OE1"), text.index("3906001 Documentos de investigación"))
        self.assertLess(text.index("3906001 Documentos de investigación"), text.index("OE2"))
        self.assertIn("3906 & 3906001 Servicio de información implementado", text)
        self.assertIn("Registro del software de tamizaje", text)
        self.assertIn("Artículo de investigación tipo TOP", text)
        self.assertIn("Adicional", text)
        self.assertIn("Mínimo de la convocatoria", text)
        self.assertIn("productos adicionales al mínimo de la convocatoria: 3, de ellos 2 de tipo TOP o A", text)

    def test_products_section_has_the_dissemination_strategy(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        text = self.sections(run)["15_productos_esperados"]
        self.assertIn(r"\subsection{Estrategia de divulgación pública de la ciencia}", text)
        self.assertIn("La estrategia de divulgación pública de la ciencia acercará", text)
        for cell in ("Personal de salud", "Podcast institucional", "Cartilla divulgativa",
                     "Universidad Nacional de Colombia", "Lanzamiento de la serie"):
            self.assertIn(cell, text)
        self.assertIn(r"\textbf{Mes} & \textbf{Acción}", text)

    def test_talent_section_has_the_table_the_minimums_and_the_profiles(self) -> None:
        run = self.run_with(rubric="conv54")
        self.mod.render_sections(run)
        text = self.sections(run)["36_talento_humano"]
        self.assertIn(r"\textbf{Categoría} & \textbf{Cantidad} & \textbf{Entidad que vincula} & \textbf{Duración} & "
                      r"\textbf{Valor mensual} & \textbf{Producto final}", text)
        self.assertIn(r"Jóvenes Investigadores e Innovadores & 6 & Universidad Nacional de Colombia & 12 meses & "
                      r"\$\,2.000.000", text)
        self.assertIn("Mínimos de la convocatoria", text)
        self.assertIn("6 de 6", text)
        self.assertIn(r"\subsection{Descripción de perfiles, actividades y plan de trabajo del talento humano a "
                      r"vincular}", text)
        self.assertIn(r"\textbf{Perfil} & \textbf{Entidad que lo vincula} & \textbf{Formación y experiencia} & "
                      r"\textbf{Actividades y meses} & \textbf{Producto final}", text)
        self.assertIn("1.1.1 Levantar los datos clínicos de la cohorte (meses 1 a 6)", text)
        self.assertIn("Por definir", text)

    def test_talent_section_without_a_rubric_has_no_minimums_line(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        self.assertNotIn("Mínimos de la convocatoria", self.sections(run)["36_talento_humano"])

    def test_indicators_section_has_management_and_product_indicators(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        text = self.sections(run)["37_indicadores"]
        self.assertIn(r"\textbf{Indicador} & \textbf{Medida/Meta} & \textbf{Código} & \textbf{Fórmula} & "
                      r"\textbf{Tipo de fuente} & \textbf{Periodicidad}", text)
        self.assertIn("Informes de supervisión del proyecto & Número / 8 & No aplica", text)
        self.assertIn("0900G127", text)
        self.assertIn("Documentos elaborados", text)
        self.assertIn("3906001", text)
        self.assertLess(text.index("Informes de supervisión"), text.index("Documentos elaborados"))

    def test_render_is_deterministic(self) -> None:
        run = self.run_with(rubric="conv54")
        self.mod.render_sections(run)
        first = self.sections(run)
        self.mod.render_sections(run)
        self.assertEqual(self.sections(run), first)

    def test_latex_specials_are_escaped(self) -> None:
        data = _productos()
        data["talento"][0]["perfil"] = "Perfil 100% & #1 con_guion"
        run = self.run_with(data)
        self.mod.render_sections(run)
        self.assertIn(r"Perfil 100\% \& \#1 con\_guion", self.sections(run)["36_talento_humano"])

    def test_render_refuses_on_error_findings(self) -> None:
        data = _productos()
        data["talento"][0]["entidad"] = "E99"
        run = self.run_with(data)
        result = _cli("render", str(run))
        self.assertEqual(result.returncode, 1)
        self.assertIn("productos-entidad-desconocida", result.stderr)
        for stem in RENDERED:
            self.assertFalse((run / "redaccion" / "sections" / f"{stem}.tex").exists(), stem)

    def test_base_run_section_15_is_never_rendered(self) -> None:
        run = self.run_with(flujo="base")
        tex = run / "redaccion" / "sections" / "15_productos_esperados.tex"
        tex.write_text("\\section{Productos esperados}\nA mano.\n", encoding="utf-8")
        result = _cli("render", str(run))
        self.assertEqual(result.returncode, 2)
        self.assertIn("flujo SGR", result.stderr)
        self.assertEqual(tex.read_text(encoding="utf-8"), "\\section{Productos esperados}\nA mano.\n")
        for stem in STEMS:
            self.assertFalse((run / "redaccion" / "sections" / f"{stem}.tex").exists(), stem)

    def test_missing_file_is_bad_input(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "productos.json").unlink()
        self.assertEqual(_cli("render", str(run)).returncode, 2)

    def test_without_structure_each_section_opens_with_its_own_title(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        texts = self.sections(run)
        self.assertIn(r"\section{Productos esperados}", texts["15_productos_esperados"])
        self.assertIn(r"\section{Vinculación de talento humano}", texts["36_talento_humano"])
        self.assertIn(r"\section{Indicadores de gestión y de producto}", texts["37_indicadores"])
        self.assertIn(r"\subsection{Indicadores de gestión}", texts["37_indicadores"])
        self.assertIn(r"\subsection{Indicadores de producto}", texts["37_indicadores"])

    def test_tdr_chapters_place_the_headings(self) -> None:
        run = self.run_with()
        structure = {"capitulos": [
            {"numero": 12, "titulo": "OBJETIVOS", "archivos": ["06_objetivo_general", "07_objetivos_especificos"]},
            {"numero": 20, "titulo": "VINCULACIÓN DE TALENTO HUMANO", "archivos": []},
            {"numero": 21, "titulo": "PRODUCTOS ESPERADOS", "archivos": ["15_productos_esperados"]},
            {"numero": 24, "titulo": "INDICADORES DE GESTIÓN", "archivos": []},
            {"numero": 25, "titulo": "INDICADORES DE PRODUCTO", "archivos": []},
        ]}
        (run / "artefactos" / "estructura_tdr.json").write_text(json.dumps(structure, ensure_ascii=False),
                                                               encoding="utf-8")
        self.mod.render_sections(run)
        texts = self.sections(run)
        self.assertIn(r"\section{PRODUCTOS ESPERADOS}", texts["15_productos_esperados"])
        self.assertIn(r"\section{VINCULACIÓN DE TALENTO HUMANO}", texts["36_talento_humano"])
        indicators = texts["37_indicadores"]
        self.assertIn(r"\section{INDICADORES DE GESTIÓN}", indicators)
        self.assertIn(r"\section{INDICADORES DE PRODUCTO}", indicators)
        self.assertEqual(indicators.count(r"\section{"), 2)
        self.assertNotIn(r"\subsection{Indicadores de producto}", indicators)

    def test_a_talent_chapter_opened_by_another_file_gets_a_subsection(self) -> None:
        run = self.run_with()
        structure = {"capitulos": [
            {"numero": 20, "titulo": "VINCULACIÓN DE TALENTO HUMANO", "archivos": ["09_equipo_trabajo"]},
            {"numero": 24, "titulo": "INDICADORES DE GESTIÓN", "archivos": []},
        ]}
        (run / "artefactos" / "estructura_tdr.json").write_text(json.dumps(structure, ensure_ascii=False),
                                                               encoding="utf-8")
        self.mod.render_sections(run)
        texts = self.sections(run)
        self.assertNotIn(r"\section{", texts["36_talento_humano"])
        self.assertIn(r"\subsection{Vinculación de talento humano}", texts["36_talento_humano"])
        self.assertIn(r"\section{INDICADORES DE GESTIÓN}", texts["37_indicadores"])
        self.assertIn(r"\subsection{Indicadores de producto}", texts["37_indicadores"])


class Registration(unittest.TestCase):
    """S4: the two stems are SGR sections wherever SGR sections are listed; base placement is unchanged."""

    LABELS = {"36_talento_humano": "§36 Vinculación de talento humano",
              "37_indicadores": "§37 Indicadores de gestión y de producto"}

    def test_check_run_lists_them_as_sgr_sections_only(self) -> None:
        check_run = _load("check_run_for_productos_tests", REPO / "scripts" / "check_run.py")
        self.assertLessEqual(set(STEMS), set(check_run.SGR_SECTIONS))
        self.assertFalse(set(STEMS) & set(check_run.CANONICAL_SECTIONS))

    def test_status_labels(self) -> None:
        sys.path.insert(0, str(REPO / "src"))
        from morfeo.core.status import SECTION_TITLES
        for stem, label in self.LABELS.items():
            self.assertEqual(SECTION_TITLES[stem], label)

    def test_assembler_places_them_in_their_chapters_in_sgr_only(self) -> None:
        assembler = _load("ensamblar_main_for_productos_tests", REPO / "scripts" / "ensamblar_main.py")
        data = {"capitulos": [
            {"numero": 12, "titulo": "OBJETIVOS", "archivos": ["06_objetivo_general", "07_objetivos_especificos"]},
            {"numero": 19, "titulo": "COMPONENTE TRANSVERSAL DE APROPIACIÓN SOCIAL DEL CONOCIMIENTO (ASC)",
             "archivos": ["18_apropiacion_social"]},
            {"numero": 20, "titulo": "VINCULACIÓN DE TALENTO HUMANO", "archivos": []},
            {"numero": 21, "titulo": "PRODUCTOS ESPERADOS", "archivos": ["15_productos_esperados"]},
            {"numero": 23, "titulo": "ANÁLISIS DE RIESGOS", "archivos": ["24_riesgos"]},
            {"numero": 24, "titulo": "INDICADORES DE GESTIÓN", "archivos": []},
            {"numero": 25, "titulo": "INDICADORES DE PRODUCTO", "archivos": []},
            {"numero": 26, "titulo": "ASPECTOS ÉTICOS", "archivos": ["12_consideraciones_eticas"]},
        ]}
        base = assembler.body(data, "base")
        for stem in STEMS:
            self.assertNotIn(stem, base)
        body = assembler.body(data, "sgr")
        order = [body.index(rf"\SeccionSiExiste{{{n}}}") for n in (
            "18_apropiacion_social", "36_talento_humano", "15_productos_esperados", "24_riesgos",
            "37_indicadores", "12_consideraciones_eticas")]
        self.assertEqual(order, sorted(order))
        chapters = {c["numero"]: c["archivos"] for c in assembler.placed_chapters(data, "sgr")}
        self.assertEqual(chapters[20], ["36_talento_humano"])
        self.assertEqual(chapters[24], ["37_indicadores"])
        self.assertEqual(chapters[25], [])

    def test_template_includes_them_after_the_component_sections(self) -> None:
        text = (REPO / "plantilla" / "main.tex").read_text(encoding="utf-8")
        names = ("15_productos_esperados", "35_medidas_diferenciales") + STEMS + ("16_bibliografia",)
        positions = [text.index(rf"\SeccionSiExiste{{{n}}}") for n in names]
        self.assertEqual(positions, sorted(positions))

    def test_rubric_evidence_and_minimums(self) -> None:
        def rubric(rid: str) -> dict:
            return json.loads((RUBRICS / f"{rid}.json").read_text(encoding="utf-8"))

        ev54 = {s["id"]: s["evidencia"] for c in rubric("conv54")["criterios"] for s in c["subcriterios"]}
        self.assertEqual(ev54["2.5"][:2], ["15_productos_esperados", "36_talento_humano"])
        talent = [(m["categoria"], m["cantidad"], m["texto"]) for m in rubric("conv54")["minimos_talento"]]
        self.assertEqual(talent, [
            ("posdoctorado", 1, "Un (1) doctor para la realización de una estancia posdoctoral."),
            ("maestria", 2, "Dos (2) estudiantes de maestría en modalidad de investigación."),
            ("joven_investigador", 6, "Seis (6) jóvenes investigadores e innovadores (pueden ser estudiantes de "
                                      "pregrado o profesionales recién graduados)."),
        ])
        self.assertEqual(rubric("conv56")["minimos_talento"], rubric("conv54")["minimos_talento"])
        products54 = {m["categoria"]: m["cantidad"] for m in rubric("conv54")["minimo_productos"]}
        products56 = {m["categoria"]: m["cantidad"] for m in rubric("conv56")["minimo_productos"]}
        self.assertEqual(products54, {"joven_investigador": 1, "maestria": 1, "posdoctorado": 2})
        self.assertEqual(products56, {"joven_investigador": 1, "maestria": 1, "posdoctorado": 1})
        postdoc = next(m["texto"] for m in rubric("conv54")["minimo_productos"] if m["categoria"] == "posdoctorado")
        self.assertIn("entregará dos (2) productos tipo TOP o tipo A", postdoc)


class KitCopy(unittest.TestCase):
    def test_kit_copies_are_byte_identical(self) -> None:
        for rel in ("scripts/productos_sgr.py", "scripts/check_run.py", "scripts/ensamblar_main.py",
                    "plantilla/main.tex", "scripts/rubricas_sgr/conv54.json", "scripts/rubricas_sgr/conv56.json",
                    "scripts/juez_sgr.py", "scripts/sgr/lexico_sgr.json", "scripts/estilo_sgr.py",
                    "guiaProyectosIA_Agente_Regalias.md", ".claude/skills/estilo-sgr/SKILL.md"):
            with self.subTest(file=rel):
                kit = REPO / "src" / "morfeo" / "_kit" / rel
                self.assertEqual(kit.read_bytes(), (REPO / rel).read_bytes())


if __name__ == "__main__":
    unittest.main()
