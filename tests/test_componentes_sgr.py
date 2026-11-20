"""scripts/componentes_sgr.py: TRL route and transversal components as data (odd/tasks/sgr-trl-componentes.md, S3 and S4).

`artefactos/sgr/componentes.json` is validated by `check` against the value
chain, the alliance, the budget and the call's rubric, rendered by `render`
into sections 31 to 35 and the SGR §18, and summarised for the judge by
`datos`. A base run's §18 is never touched (S1).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "componentes_sgr.py"
RUBRICS = REPO / "scripts" / "rubricas_sgr"
HEADER = "% GENERADO por scripts/componentes_sgr.py"
STEMS = ("31_trl", "32_sostenibilidad", "33_uso_posterior", "34_transferencia", "35_medidas_diferenciales")
RENDERED = STEMS + ("18_apropiacion_social",)
sys.path.insert(0, str(REPO / "tests"))

from test_alianza_territorio_sgr import _alliance  # noqa: E402
from test_cadena_valor_sgr import TREE, _valid_chain  # noqa: E402
from test_presupuesto_sgr import _budget  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ELEMENTS = ("identificacion_problema", "vinculacion_actores", "diseno", "planeacion", "ejecucion", "seguimiento",
            "resultados_sostenibilidad")


def _components() -> dict:
    """Components that pass every rule against _valid_chain(), _alliance() and _budget()."""
    activities = ["1.1.1", "1.1.2", "2.1.1", "2.1.2", "2.2.1", "2.1.1", "2.1.2"]
    return {
        "schema": "morfeo.componentes-sgr/v1",
        "trl": {
            "introduccion": "El punto de partida tecnológico corresponde a un modelo validado en laboratorio.",
            "tipologia": "B", "entrada": 4, "salida": 7,
            "evidencia_entrada": ["Informe de validación previa en laboratorio (2024)"],
            "ruta": [
                {"hito": "Prototipo integrado", "mes": 12, "trl": 5, "actividades": ["2.1.1"],
                 "evidencia": "Acta de pruebas del prototipo"},
                {"hito": "Piloto en entorno operativo", "mes": 20, "trl": 7, "actividades": ["2.1.2"],
                 "evidencia": "Informe del piloto"},
            ],
            "verificacion": {"escenario": "Servicio de salud mental del hospital", "responsables": ["E1", "E5"],
                             "criterios_aceptacion": ["Sensibilidad igual o mayor que 0,8"],
                             "evidencias": ["Informe de validación firmado por el hospital"], "actor_usuario": "E5"},
        },
        "transferencia": {
            "introduccion": "El componente transversal de transferencia establecerá las condiciones de uso.",
            "resultados": [{"resultado": "Modelo de tamizaje validado", "usuarios": ["Hospital Departamental de Caldas"],
                            "proteccion_pi": "Registro de software"}],
            "ruta": [{"etapa": "Validación con usuarios", "mecanismo": "Licencia de uso",
                      "barreras": "Baja capacidad técnica del personal", "acciones": "Acompañamiento técnico"}],
            "actividades": ["2.2.1", "2.2.2"],
            "continuidad": "Una vez finalizado el proyecto, la Red de Salud mantendrá el servicio.",
        },
        "asc": {
            "introduccion": "La estrategia de ASC se concibe como un proceso transversal de participación.",
            "actores": [{"grupo": "Personal de salud", "relacion_problematica": "Atiende los casos",
                         "saberes": "Conocimiento clínico", "rol_momento": "Co-diseño, meses 3 a 6",
                         "incidencia": "Valida los criterios del tamizaje"}],
            "ruta": [{"elemento": e, "meses": [n + 1, n + 2], "que_se_hace": f"Trabajo con los actores {n}",
                      "actividades": [activities[n]]} for n, e in enumerate(ELEMENTS)],
            "productos": [{"producto": "Memorias de los talleres de co-creación", "descripcion": "Sistematización",
                           "medio_verificacion": "Actas y listados de asistencia", "mes": 10, "actividad": "1.1.2"}],
        },
        "sostenibilidad": {
            "introduccion": "La sostenibilidad se plantea desde la formulación.",
            "ods": [{"ods": "ODS 3, meta 3.4", "contribucion": "Detección temprana",
                     "productos": ["Documentos de investigación"]}],
            "actores": [{"actor": "Gobernación de Caldas", "funciones": "Articula la red",
                         "compromiso": "Incluye el servicio en su plan de salud"}],
            "ambiental": [],
        },
        "uso_posterior": {
            "introduccion": "Cada bien queda a cargo de una entidad de la alianza.",
            "bienes": [{"bien": "Servidor de cómputo", "valor_sgr": 150000000, "operador": "E1",
                        "financiacion": "Recursos propios de la universidad", "mantenimiento": "Soporte anual"}],
            "adopcion": [{"actor": "E5", "resultado": "Modelo de tamizaje", "condiciones": "Personal capacitado"}],
        },
        "diferencial": {
            "introduccion": "El proyecto identifica una barrera de acceso.",
            "barreras": [{"barrera": "Conectividad rural limitada", "poblacion": "Estudiantes rurales",
                          "medida": "Versión sin conexión", "actividades": ["2.2.2"], "indicador": "Sedes atendidas",
                          "meta": "10", "evidencia": "Registro de instalación"}],
            "justificacion_sin_barreras": None,
        },
    }


def _write(run: Path, name: str, data) -> Path:
    path = run / "artefactos" / "sgr" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _make_run(tmp: Path, components: dict | None = None, flujo: str | None = "sgr", budget: bool = False,
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
        _write(run, "presupuesto.json", budget if isinstance(budget, dict) else _budget())
    _write(run, "componentes.json", components if components is not None else _components())
    return run


def _rubric(run: Path, rid: str) -> None:
    folder = run / "artefactos" / "juez"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RUBRICS / f"{rid}.json", folder / "rubrica.json")


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def _codes(findings: list[dict], severity: str | None = None) -> list[str]:
    return [f["code"] for f in findings if severity is None or f["severity"] == severity]


class _Case(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.mod = _load("componentes_sgr_under_test", SCRIPT)

    def run_with(self, components: dict | None = None, **kwargs) -> Path:
        return _make_run(self.tmp, components, **kwargs)

    def found(self, change=None, **kwargs) -> list[dict]:
        data = _components()
        if change is not None:
            change(data)
        return self.mod.findings(self.run_with(data, **kwargs))


class Check(_Case):
    def test_valid_components_have_no_findings(self) -> None:
        self.assertEqual(self.found(), [])
        self.assertEqual(self.mod.findings(_make_run(Path(tempfile.mkdtemp(dir=self.tmp)), budget=True)), [])

    def test_missing_file_is_silent_for_check_run_and_an_error_for_the_cli(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "componentes.json").unlink()
        self.assertEqual(self.mod.findings(run), [])
        self.assertEqual(_codes(self.mod.check_findings(run)), ["componentes-archivo-faltante"])
        self.assertEqual(_cli("check", str(run)).returncode, 2)

    def test_schema_and_invalid_json(self) -> None:
        self.assertEqual(_codes(self.found(lambda d: d.update(schema="otro"))), ["componentes-esquema"])
        run = self.run_with()
        _write(run, "componentes.json", "{no es json")
        self.assertEqual(_codes(self.mod.findings(run)), ["componentes-json-invalido"])

    def test_every_block_is_required(self) -> None:
        found = self.found(lambda d: d.pop("asc"))
        hit = [f for f in found if f["code"] == "componentes-bloque-faltante"]
        self.assertEqual([(f["severity"], f["node"]) for f in hit], [("error", "asc")])

    def test_activity_codes_exist_in_the_value_chain(self) -> None:
        def change(d):
            d["trl"]["ruta"][0]["actividades"] = ["9.9.9"]
            d["diferencial"]["barreras"][0]["actividades"] = ["8.8.8"]
        hit = [f for f in self.found(change) if f["code"] == "componentes-actividad-desconocida"]
        self.assertEqual([(f["severity"], f["node"]) for f in hit],
                         [("error", "trl.ruta[1]"), ("error", "diferencial.barreras[1]")])
        self.assertIn("9.9.9", hit[0]["message"])

    def test_entity_ids_exist_in_the_alliance(self) -> None:
        def change(d):
            d["trl"]["verificacion"]["responsables"] = ["E1", "E99"]
            d["uso_posterior"]["bienes"][0]["operador"] = "E77"
        hit = [f for f in self.found(change) if f["code"] == "componentes-entidad-desconocida"]
        self.assertEqual({f["node"] for f in hit}, {"trl.verificacion", "uso_posterior.bienes[1]"})
        self.assertEqual({f["severity"] for f in hit}, {"error"})

    def test_without_chain_or_alliance_the_cross_checks_warn(self) -> None:
        data = _components()
        data["trl"]["ruta"][0]["actividades"] = ["9.9.9"]
        found = self.mod.findings(self.run_with(data, chain=False, alliance=False))
        self.assertIn("componentes-cadena-faltante", _codes(found, "warning"))
        self.assertIn("componentes-alianza-faltante", _codes(found, "warning"))
        self.assertNotIn("componentes-actividad-desconocida", _codes(found))

    def test_check_cli_exit_codes_and_json(self) -> None:
        run = self.run_with()
        result = _cli("check", str(run), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"findings": []})
        data = _components()
        data["trl"]["tipologia"] = "C"
        _write(run, "componentes.json", data)
        result = _cli("check", str(run))
        self.assertEqual(result.returncode, 1)
        self.assertIn("componentes-trl-tipologia", result.stdout)


class Trl(_Case):
    def test_tipologia_must_be_a_or_b(self) -> None:
        self.assertIn("componentes-trl-tipologia", _codes(self.found(lambda d: d["trl"].update(tipologia=None)), "error"))

    def test_entry_and_exit_levels_are_required(self) -> None:
        found = self.found(lambda d: d["trl"].update(entrada=None, salida=12))
        self.assertEqual(_codes(found, "error").count("componentes-trl-nivel"), 2)

    def test_exit_must_exceed_entry(self) -> None:
        def change(d):
            d["trl"].update(entrada=7, salida=7)
        self.assertIn("componentes-trl-salida-no-mayor", _codes(self.found(change), "error"))

    def test_route_months_stay_inside_the_duration(self) -> None:
        hit = [f for f in self.found(lambda d: d["trl"]["ruta"][1].update(mes=30)) if f["code"] == "componentes-mes-fuera"]
        self.assertEqual([(f["severity"], f["node"]) for f in hit], [("error", "trl.ruta[2]")])
        self.assertIn("24", hit[0]["message"])

    def test_route_must_reach_the_exit_level(self) -> None:
        self.assertIn("componentes-trl-ruta-incompleta",
                      _codes(self.found(lambda d: d["trl"]["ruta"][1].update(trl=6)), "error"))
        self.assertIn("componentes-trl-ruta-incompleta", _codes(self.found(lambda d: d["trl"].update(ruta=[])), "error"))

    def test_verification_plan_is_complete(self) -> None:
        def change(d):
            d["trl"]["verificacion"].update(escenario="", criterios_aceptacion=[])
        hit = next(f for f in self.found(change) if f["code"] == "componentes-trl-verificacion-incompleta")
        self.assertEqual(hit["severity"], "error")
        self.assertIn("escenario", hit["message"])
        self.assertIn("criterios de aceptación", hit["message"])

    def test_tipologia_b_needs_the_user_actor(self) -> None:
        found = self.found(lambda d: d["trl"]["verificacion"].update(actor_usuario=None))
        self.assertIn("componentes-trl-actor-usuario", _codes(found, "error"))

        def type_a(d):
            d["trl"].update(tipologia="A", entrada=3, salida=5)
            d["trl"]["ruta"][1]["trl"] = 5
            d["trl"]["verificacion"]["actor_usuario"] = None
        self.assertNotIn("componentes-trl-actor-usuario", _codes(self.found(type_a)))

    def _with_rubric(self, rid: str | None, change) -> list[dict]:
        data = _components()
        change(data)
        run = self.run_with(data)
        if rid:
            _rubric(run, rid)
        return self.mod.findings(run)

    @staticmethod
    def _type_a(entry: int, exit_: int, evidence: bool = True):
        def change(d):
            d["trl"].update(tipologia="A", entrada=entry, salida=exit_)
            d["trl"]["ruta"][1]["trl"] = exit_
            if not evidence:
                d["trl"]["evidencia_entrada"] = []
        return change

    def test_conv54_type_a_goes_up_to_trl_6_with_entry_evidence(self) -> None:
        self.assertEqual(self._with_rubric("conv54", self._type_a(3, 6)), [])
        self.assertIn("componentes-trl-rango-tdr", _codes(self._with_rubric("conv54", self._type_a(3, 7)), "error"))
        self.assertIn("componentes-trl-evidencia-entrada",
                      _codes(self._with_rubric("conv54", self._type_a(3, 6, evidence=False)), "error"))

    def test_conv54_type_b_enters_at_4_and_exits_between_7_and_9(self) -> None:
        self.assertEqual(self._with_rubric("conv54", lambda d: None), [])

        def low_entry(d):
            d["trl"]["entrada"] = 3
        self.assertIn("componentes-trl-rango-tdr", _codes(self._with_rubric("conv54", low_entry), "error"))

        def low_exit(d):
            d["trl"]["salida"] = 6
            d["trl"]["ruta"][1]["trl"] = 6
        self.assertIn("componentes-trl-rango-tdr", _codes(self._with_rubric("conv54", low_exit), "error"))

    def test_conv56_exit_below_7_is_a_warning(self) -> None:
        self.assertEqual(self._with_rubric("conv56", lambda d: None), [])
        found = self._with_rubric("conv56", self._type_a(3, 6, evidence=False))
        self.assertEqual([(f["code"], f["severity"]) for f in found if f["code"].startswith("componentes-trl-")],
                         [("componentes-trl-rango-tdr", "warning")])

    def test_without_a_rubric_there_is_no_range_check(self) -> None:
        found = self._with_rubric(None, self._type_a(3, 8, evidence=False))
        self.assertFalse([c for c in _codes(found) if c in ("componentes-trl-rango-tdr",
                                                            "componentes-trl-evidencia-entrada")])


class Transfer(_Case):
    def test_results_with_users_route_and_activities_are_required(self) -> None:
        def change(d):
            d["transferencia"]["resultados"][0]["usuarios"] = []
            d["transferencia"]["ruta"][0]["barreras"] = ""
            d["transferencia"]["actividades"] = []
        errors = _codes(self.found(change), "error")
        for code in ("componentes-transferencia-sin-resultados", "componentes-transferencia-sin-ruta",
                     "componentes-transferencia-sin-actividades"):
            self.assertIn(code, errors)

    def test_transfer_under_one_percent_of_the_budget_is_a_warning(self) -> None:
        budget = _budget()
        budget["items"][4]["valor_unitario"] = 5_000_000
        budget["items"][5]["valor_unitario"] = 613_000_000
        found = self.mod.findings(self.run_with(budget=budget))
        hit = next(f for f in found if f["code"] == "componentes-transferencia-presupuesto-bajo")
        self.assertEqual(hit["severity"], "warning")
        self.assertIn("0,50 %", hit["message"])

    def test_without_the_budget_there_is_no_budget_check(self) -> None:
        found = self.found(lambda d: d["transferencia"].update(actividades=["2.2.1"]))
        self.assertFalse([c for c in _codes(found) if "presupuesto" in c])

    def test_activities_must_match_the_budget_items_tagged_transfer(self) -> None:
        found = self.found(lambda d: d["transferencia"].update(actividades=["2.2.1", "2.1.1"]), budget=True)
        hit = next(f for f in found if f["code"] == "componentes-transferencia-presupuesto-desalineado")
        self.assertEqual(hit["severity"], "warning")
        self.assertIn("2.1.1", hit["message"])
        self.assertIn("2.2.2", hit["message"])


class Asc(_Case):
    def test_the_seven_elements_are_required(self) -> None:
        hit = next(f for f in self.found(lambda d: d["asc"]["ruta"].pop()) if f["code"] == "componentes-asc-elemento-faltante")
        self.assertEqual(hit["severity"], "error")
        self.assertIn("resultados y sostenibilidad", hit["message"])

    def test_unknown_element_and_element_without_activities(self) -> None:
        def change(d):
            d["asc"]["ruta"][0]["elemento"] = "socializacion"
            d["asc"]["ruta"][1]["actividades"] = []
        errors = _codes(self.found(change), "error")
        self.assertIn("componentes-asc-elemento-invalido", errors)
        self.assertIn("componentes-asc-elemento-sin-actividad", errors)
        self.assertIn("componentes-asc-elemento-faltante", errors)

    def test_a_product_with_verification_means_and_month_is_required(self) -> None:
        self.assertIn("componentes-asc-sin-productos", _codes(self.found(lambda d: d["asc"].update(productos=[])), "error"))
        found = self.found(lambda d: d["asc"]["productos"][0].update(medio_verificacion="", mes=None))
        self.assertIn("componentes-asc-sin-productos", _codes(found, "error"))

    def test_dissemination_only_activities_are_a_warning(self) -> None:
        def change(d):
            for step in d["asc"]["ruta"]:
                step["actividades"] = ["2.2.2"]
            d["asc"]["productos"][0]["actividad"] = "2.2.2"
        self.assertIn("componentes-asc-solo-divulgacion", _codes(self.found(change), "warning"))
        self.assertNotIn("componentes-asc-solo-divulgacion", _codes(self.found()))


class SustainabilityUseDifferential(_Case):
    def test_sustainability_needs_an_sdg_with_products_and_an_actor_with_commitment(self) -> None:
        def change(d):
            d["sostenibilidad"]["ods"][0]["productos"] = []
            d["sostenibilidad"]["actores"][0]["compromiso"] = ""
        errors = _codes(self.found(change), "error")
        self.assertIn("componentes-sostenibilidad-sin-ods", errors)
        self.assertIn("componentes-sostenibilidad-sin-actores", errors)

    def test_goods_bought_with_sgr_need_operator_and_funding(self) -> None:
        hit = [f for f in self.found(lambda d: d["uso_posterior"]["bienes"][0].update(operador=None, financiacion=""))
               if f["code"] == "componentes-uso-bien-incompleto"]
        self.assertEqual([(f["severity"], f["node"]) for f in hit], [("error", "uso_posterior.bienes[1]")])
        self.assertNotIn("componentes-uso-bien-incompleto", _codes(self.found(
            lambda d: d["uso_posterior"]["bienes"][0].update(valor_sgr=0, operador=None, financiacion=""))))

    def test_adoption_by_a_user_or_adopter_entity(self) -> None:
        self.assertIn("componentes-uso-sin-adopcion", _codes(self.found(
            lambda d: d["uso_posterior"]["adopcion"][0].update(actor="E3")), "warning"))
        self.assertIn("componentes-uso-sin-adopcion", _codes(self.found(
            lambda d: d["uso_posterior"].update(adopcion=[])), "warning"))

    def test_differential_needs_barriers_or_a_justification(self) -> None:
        self.assertIn("componentes-diferencial-vacio", _codes(self.found(
            lambda d: d["diferencial"].update(barreras=[])), "error"))
        self.assertEqual(self.found(lambda d: d["diferencial"].update(
            barreras=[], justificacion_sin_barreras="La población objetivo no enfrenta barreras de acceso.")), [])


class Datos(_Case):
    def test_trl_and_transfer_facts(self) -> None:
        data = self.mod.datos(self.run_with(budget=True))
        self.assertEqual(set(data), {"trl", "transferencia_valor", "fuente"})
        self.assertEqual(data["trl"], {"tipologia": "B", "entrada": 4, "salida": 7,
                                       "fuente": "artefactos/sgr/componentes.json (trl)"})
        self.assertEqual(data["transferencia_valor"], 20_000_000)
        self.assertEqual(data["fuente"], ["artefactos/sgr/componentes.json", "artefactos/sgr/presupuesto.json"])

    def test_missing_files_give_null_facts(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "componentes.json").unlink()
        self.assertEqual(self.mod.datos(run), {"trl": None, "transferencia_valor": None, "fuente": []})

    def test_datos_cli_prints_json(self) -> None:
        result = _cli("datos", str(self.run_with()), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["trl"]["salida"], 7)


class Render(_Case):
    def sections(self, run: Path) -> dict[str, str]:
        return {stem: (run / "redaccion" / "sections" / f"{stem}.tex").read_text(encoding="utf-8") for stem in RENDERED}

    def test_render_writes_the_six_sections_with_the_header(self) -> None:
        run = self.run_with()
        result = _cli("render", str(run))
        self.assertEqual(result.returncode, 0, result.stderr)
        for stem, text in self.sections(run).items():
            with self.subTest(stem=stem):
                self.assertEqual(text.splitlines()[0], HEADER)
                self.assertIn(r"\begin{xltabular}", text)
                self.assertNotIn("--", text.replace("---", ""))

    def test_trl_section_has_entry_route_and_verification(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        text = self.sections(run)["31_trl"]
        self.assertIn("El punto de partida tecnológico corresponde a un modelo validado en laboratorio.", text)
        for header in (r"\textbf{Hito} & \textbf{Mes} & \textbf{TRL} & \textbf{Actividades} & \textbf{Evidencia}",
                       r"\textbf{Escenario} & \textbf{Responsables} & \textbf{Criterios de aceptación} & "
                       r"\textbf{Evidencias}"):
            self.assertIn(header, text)
        self.assertIn("2.1.1 Construir los modelos de tamizaje", text)
        self.assertIn("Hospital Departamental de Caldas", text)
        self.assertIn(r"\subsection{Plan de verificación del TRL de salida}", text)

    def test_transfer_section_uses_the_chain_and_the_budget_shares(self) -> None:
        run = self.run_with(budget=True)
        self.mod.render_sections(run)
        text = self.sections(run)["34_transferencia"]
        for header in (r"\textbf{Resultado} & \textbf{Usuarios} & \textbf{Protección de PI}",
                       r"\textbf{Etapa} & \textbf{Mecanismo} & \textbf{Barreras} & \textbf{Acciones}",
                       r"\textbf{Actividad} & \textbf{Resultado} & \textbf{Producto} & \textbf{Indicador} & "
                       r"\textbf{Responsable} & \textbf{Periodo} & \textbf{Presupuesto}"):
            self.assertIn(header, text)
        self.assertIn("2.2.1 Redactar la guía de uso", text)
        self.assertIn("2.2 Documentos de lineamientos técnicos", text)
        self.assertIn("Meses 18 a 22", text)
        self.assertIn(r"\$\,10.000.000", text)
        self.assertIn(r"\textbf{\$\,30.000.000}", text)
        self.assertIn(r"\subsection{Continuidad del proceso}", text)

    def test_transfer_budget_column_without_the_budget(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        text = self.sections(run)["34_transferencia"]
        self.assertIn("Por definir", text)
        self.assertNotIn(r"\textbf{Total}", text)

    def test_asc_section_lists_the_route_in_element_order_with_products(self) -> None:
        data = _components()
        data["asc"]["ruta"].reverse()
        data["asc"]["ruta"][0]["meses"] = [3, 1, 2, 6]
        run = self.run_with(data)
        self.mod.render_sections(run)
        text = self.sections(run)["18_apropiacion_social"]
        positions = [text.index(label) for label in ("Identificación del problema", "Vinculación de actores",
                                                     "Planeación", "Resultados y sostenibilidad &")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("1 a 3, 6", text)
        self.assertIn(r"\textbf{Grupo y actores} & \textbf{Relación con la problemática}", text)
        self.assertIn("Memorias de los talleres de co-creación", text)

    def test_sustainability_use_and_differential_tables(self) -> None:
        data = _components()
        data["sostenibilidad"]["ambiental"] = [{"actividad": "2.1.1", "medio": "Energía", "efecto": "Consumo eléctrico",
                                                "manejo": "Servidores eficientes"}]
        run = self.run_with(data)
        self.mod.render_sections(run)
        texts = self.sections(run)
        self.assertIn(r"\textbf{ODS} & \textbf{Contribución del proyecto} & "
                      r"\textbf{Productos y resultados que la respaldan}", texts["32_sostenibilidad"])
        self.assertIn("2.1.1 Construir los modelos de tamizaje", texts["32_sostenibilidad"])
        self.assertIn(r"\textbf{Bienes adquiridos con SGR}", texts["33_uso_posterior"])
        self.assertIn(r"\$\,150.000.000", texts["33_uso_posterior"])
        self.assertIn(r"\textbf{Actor} & \textbf{Resultado que adoptará} & \textbf{Condiciones de adopción}",
                      texts["33_uso_posterior"])
        self.assertIn("Conectividad rural limitada", texts["35_medidas_diferenciales"])

    def test_differential_justification_without_barriers(self) -> None:
        data = _components()
        data["diferencial"].update(barreras=[], justificacion_sin_barreras="La población no enfrenta barreras.")
        run = self.run_with(data)
        self.mod.render_sections(run)
        text = self.sections(run)["35_medidas_diferenciales"]
        self.assertIn("La población no enfrenta barreras.", text)
        self.assertNotIn("xltabular", text)

    def test_render_is_deterministic(self) -> None:
        run = self.run_with(budget=True)
        self.mod.render_sections(run)
        first = self.sections(run)
        self.mod.render_sections(run)
        self.assertEqual(self.sections(run), first)

    def test_latex_specials_are_escaped(self) -> None:
        data = _components()
        data["trl"]["introduccion"] = "Precisión del 95% & costo #1 con_guion"
        run = self.run_with(data)
        self.mod.render_sections(run)
        self.assertIn(r"Precisión del 95\% \& costo \#1 con\_guion", self.sections(run)["31_trl"])

    def test_render_refuses_on_error_findings(self) -> None:
        data = _components()
        data["diferencial"]["barreras"] = []
        run = self.run_with(data)
        result = _cli("render", str(run))
        self.assertEqual(result.returncode, 1)
        self.assertIn("componentes-diferencial-vacio", result.stderr)
        for stem in RENDERED:
            self.assertFalse((run / "redaccion" / "sections" / f"{stem}.tex").exists(), stem)

    def test_base_run_section_18_is_never_rendered(self) -> None:
        run = self.run_with(flujo="base")
        tex = run / "redaccion" / "sections" / "18_apropiacion_social.tex"
        tex.write_text("\\section{Apropiación social}\nA mano.\n", encoding="utf-8")
        result = _cli("render", str(run))
        self.assertEqual(result.returncode, 2)
        self.assertIn("flujo SGR", result.stderr)
        self.assertEqual(tex.read_text(encoding="utf-8"), "\\section{Apropiación social}\nA mano.\n")
        for stem in STEMS:
            self.assertFalse((run / "redaccion" / "sections" / f"{stem}.tex").exists(), stem)

    def test_missing_file_is_bad_input(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "componentes.json").unlink()
        self.assertEqual(_cli("render", str(run)).returncode, 2)

    def test_without_structure_each_section_opens_with_its_own_title(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        texts = self.sections(run)
        self.assertIn(r"\section{Madurez tecnológica y verificación del TRL}", texts["31_trl"])
        self.assertIn(r"\section{Uso y operación posterior de los resultados}", texts["33_uso_posterior"])
        self.assertNotIn(r"\subsection{Uso y operación posterior", texts["33_uso_posterior"])
        self.assertIn(r"\section{Medidas diferenciales}", texts["35_medidas_diferenciales"])

    def test_tdr_chapters_place_the_headings(self) -> None:
        run = self.run_with()
        structure = {"capitulos": [
            {"numero": 14, "titulo": "METODOLOGÍA PARA DESARROLLAR LA ALTERNATIVA SELECCIONADA",
             "archivos": ["10_metodologia"]},
            {"numero": 16, "titulo": "SOSTENIBILIDAD SOCIAL Y AMBIENTAL DEL PROYECTO", "archivos": []},
            {"numero": 17, "titulo": "RESULTADOS E IMPACTOS PARA LA REGIÓN Y LOS DEPARTAMENTOS OBJETO DEL PROYECTO",
             "archivos": ["11_resultados_esperados"]},
            {"numero": 18, "titulo": "COMPONENTE TRANSVERSAL DE TRANSFERENCIA, ADOPCIÓN Y VALORACIÓN TECNOLÓGICA "
                                     "DEL CONOCIMIENTO", "archivos": []},
            {"numero": 19, "titulo": "COMPONENTE TRANSVERSAL DE APROPIACIÓN SOCIAL DEL CONOCIMIENTO (ASC)",
             "archivos": ["18_apropiacion_social"]},
            {"numero": 21, "titulo": "PRODUCTOS ESPERADOS", "archivos": ["15_productos_esperados"]},
        ]}
        (run / "artefactos" / "estructura_tdr.json").write_text(json.dumps(structure, ensure_ascii=False),
                                                               encoding="utf-8")
        self.mod.render_sections(run)
        texts = self.sections(run)
        self.assertNotIn(r"\section{", texts["31_trl"])
        self.assertIn(r"\subsection{Estado de desarrollo y madurez tecnológica de la solución}", texts["31_trl"])
        self.assertIn(r"\section{SOSTENIBILIDAD SOCIAL Y AMBIENTAL DEL PROYECTO}", texts["32_sostenibilidad"])
        self.assertNotIn(r"\section{", texts["33_uso_posterior"])
        self.assertIn(r"\subsection{Uso y operación posterior de los resultados}", texts["33_uso_posterior"])
        self.assertIn(r"\section{COMPONENTE TRANSVERSAL DE TRANSFERENCIA", texts["34_transferencia"])
        self.assertNotIn(r"\section{", texts["35_medidas_diferenciales"])
        self.assertIn(r"\subsection{Medidas diferenciales}", texts["35_medidas_diferenciales"])
        self.assertIn(r"\section{COMPONENTE TRANSVERSAL DE APROPIACIÓN SOCIAL DEL CONOCIMIENTO (ASC)}",
                      texts["18_apropiacion_social"])


class Registration(unittest.TestCase):
    """S4: the five stems are SGR sections wherever SGR sections are listed; base placement is unchanged."""

    LABELS = {"31_trl": "§31 TRL y verificación", "32_sostenibilidad": "§32 Sostenibilidad social y ambiental",
              "33_uso_posterior": "§33 Uso y operación posterior",
              "34_transferencia": "§34 Transferencia, adopción y valoración",
              "35_medidas_diferenciales": "§35 Medidas diferenciales"}

    def test_check_run_lists_them_as_sgr_sections_only(self) -> None:
        check_run = _load("check_run_for_componentes_tests", REPO / "scripts" / "check_run.py")
        self.assertLessEqual(set(STEMS), set(check_run.SGR_SECTIONS))
        self.assertFalse(set(STEMS) & set(check_run.CANONICAL_SECTIONS))

    def test_status_labels(self) -> None:
        sys.path.insert(0, str(REPO / "src"))
        from morfeo.core.status import SECTION_TITLES
        for stem, label in self.LABELS.items():
            self.assertEqual(SECTION_TITLES[stem], label)

    def test_assembler_places_them_in_their_chapters_in_sgr_only(self) -> None:
        assembler = _load("ensamblar_main_for_componentes_tests", REPO / "scripts" / "ensamblar_main.py")
        data = {"capitulos": [
            {"numero": 14, "titulo": "METODOLOGÍA PARA DESARROLLAR LA ALTERNATIVA SELECCIONADA",
             "archivos": ["10_metodologia"]},
            {"numero": 15, "titulo": "CADENA DE VALOR", "archivos": ["23_cadena_valor"]},
            {"numero": 16, "titulo": "SOSTENIBILIDAD SOCIAL Y AMBIENTAL DEL PROYECTO", "archivos": []},
            {"numero": 17, "titulo": "RESULTADOS E IMPACTOS PARA LA REGIÓN Y LOS DEPARTAMENTOS OBJETO DEL PROYECTO",
             "archivos": ["11_resultados_esperados"]},
            {"numero": 18, "titulo": "COMPONENTE TRANSVERSAL DE TRANSFERENCIA, ADOPCIÓN Y VALORACIÓN TECNOLÓGICA "
                                     "DEL CONOCIMIENTO", "archivos": []},
            {"numero": 19, "titulo": "COMPONENTE TRANSVERSAL DE APROPIACIÓN SOCIAL DEL CONOCIMIENTO (ASC)",
             "archivos": ["18_apropiacion_social"]},
            {"numero": 21, "titulo": "PRODUCTOS ESPERADOS", "archivos": ["15_productos_esperados"]},
            {"numero": 22, "titulo": "CRONOGRAMA", "archivos": ["14_cronograma_actividades"]},
        ]}
        base = assembler.body(data, "base")
        for stem in STEMS:
            self.assertNotIn(stem, base)
        body = assembler.body(data, "sgr")
        order = [body.index(rf"\SeccionSiExiste{{{n}}}") for n in (
            "10_metodologia", "31_trl", "23_cadena_valor", "32_sostenibilidad", "11_resultados_esperados",
            "33_uso_posterior", "34_transferencia", "18_apropiacion_social", "15_productos_esperados",
            "35_medidas_diferenciales", "14_cronograma_actividades")]
        self.assertEqual(order, sorted(order))

    def test_template_includes_them_after_the_sources_section(self) -> None:
        text = (REPO / "plantilla" / "main.tex").read_text(encoding="utf-8")
        names = ("30_fuentes_financiacion",) + STEMS + ("16_bibliografia",)
        positions = [text.index(rf"\SeccionSiExiste{{{n}}}") for n in names]
        self.assertEqual(positions, sorted(positions))

    def test_rubric_evidence_starts_with_the_new_sections(self) -> None:
        def evidence(rid: str) -> dict[str, list[str]]:
            rubric = json.loads((RUBRICS / f"{rid}.json").read_text(encoding="utf-8"))
            return {s["id"]: s["evidencia"] for c in rubric["criterios"] for s in c["subcriterios"]}

        ev54, ev56 = evidence("conv54"), evidence("conv56")
        expected54 = {"1.3": ["31_trl"], "2.3": ["34_transferencia"], "2.4": ["18_apropiacion_social"],
                      "4.2": ["32_sostenibilidad", "33_uso_posterior"], "4.4": ["35_medidas_diferenciales"]}
        expected56 = {"3.1": ["31_trl"], "3.2": ["32_sostenibilidad", "33_uso_posterior"],
                      "5": ["18_apropiacion_social"]}
        for ev, expected in ((ev54, expected54), (ev56, expected56)):
            for sid, stems in expected.items():
                with self.subTest(subcriterio=sid):
                    self.assertEqual(ev[sid][:len(stems)], stems)


class KitCopy(unittest.TestCase):
    def test_kit_copies_are_byte_identical(self) -> None:
        for rel in ("scripts/componentes_sgr.py", "scripts/ensamblar_main.py", "plantilla/main.tex",
                    "scripts/rubricas_sgr/conv54.json", "scripts/rubricas_sgr/conv56.json",
                    "scripts/sgr/lexico_sgr.json", "scripts/estilo_sgr.py", ".claude/skills/estilo-sgr/SKILL.md"):
            with self.subTest(file=rel):
                kit = REPO / "src" / "morfeo" / "_kit" / rel
                self.assertEqual(kit.read_bytes(), (REPO / rel).read_bytes())


if __name__ == "__main__":
    unittest.main()
