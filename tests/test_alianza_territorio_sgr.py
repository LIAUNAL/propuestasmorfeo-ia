"""scripts/alianza_territorio_sgr.py: alliance and territory of an SGR project as data
(odd/tasks/sgr-alianza-territorio.md, S3 and S4).

`artefactos/sgr/alianza.json` and `artefactos/sgr/territorio.json` are
validated by `check`, rendered by `render` into the SGR sections
26_identificacion, 27_demandas_territoriales and 28_matriz_responsabilidades,
previewed against the counted rubric criteria by `puntaje` (with
juez_sgr.compute_conteo) and turned into the partial datos_sgr the judge
starts from by `datos`. 29_idoneidad_trayectoria is written by the redactor.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "alianza_territorio_sgr.py"
RUBRICS = REPO / "scripts" / "rubricas_sgr"
sys.path.insert(0, str(REPO / "tests"))

from test_cadena_valor_sgr import TREE, _valid_chain  # noqa: E402

RENDERED = ("26_identificacion", "27_demandas_territoriales", "28_matriz_responsabilidades")
HEADER = "% GENERADO por scripts/alianza_territorio_sgr.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entity(eid: str, nombre: str, tipo: str, departamento: str | None, **changes) -> dict:
    data = {
        "id": eid, "nombre": nombre, "nit": None, "tipo": tipo, "proponente": False,
        "departamento": departamento, "rol": "Aliado", "posicion": "cooperante", "interes": None,
        "responsabilidades": ["Facilitar el acceso a la información territorial"], "actividades": [],
        "aporte_especie": 0, "aporte_efectivo": 0, "domicilio_en_region": None, "tipo_diverso": None,
        "grupos": [], "trayectoria": [],
    }
    data.update(changes)
    return data


def _alliance() -> dict:
    """Six members that meet the minimum composition and the basic alliance of Conv 54."""
    return {
        "schema": "morfeo.alianza-sgr/v1",
        "monto_sgr_solicitado": 1_000_000_000,
        "duracion_meses": 24,
        "entidades": [
            _entity("E1", "Universidad Nacional de Colombia", "IES", "Caldas", proponente=True, nit="899999063",
                    rol="Entidad proponente y ejecutora", responsabilidades=["Formular y ejecutar el proyecto"],
                    actividades=["1.1.1", "1.1.3"], aporte_especie=100_000_000, domicilio_en_region=True,
                    tipo_diverso=False,
                    grupos=[{"nombre": "Grupo de Control y Procesamiento Digital de Señales",
                             "codigo_gruplac": "COL0053581", "clasificacion": "A1",
                             "lineas": ["Aprendizaje automático", "Procesamiento de señales"]}],
                    trayectoria=[{"nombre": "Monitoreo de salud mental universitaria", "codigo": "BPIN 2022000100",
                                  "financiador": "SGR", "anio": 2022, "sgr_o_elegible": True},
                                 {"nombre": "Tamizaje digital de ansiedad", "codigo": None,
                                  "financiador": "Minciencias", "anio": 2021, "sgr_o_elegible": False}]),
            _entity("E2", "Universidad Tecnológica de Pereira", "IES", "Risaralda", rol="Aliado académico",
                    actividades=["2.1.1"], aporte_especie=20_000_000,
                    trayectoria=[{"nombre": "Plataforma de alertas tempranas", "codigo": None, "financiador": None,
                                  "anio": 2020, "sgr_o_elegible": False}]),
            _entity("E3", "Gobernación de Caldas", "entidad_territorial", "Caldas"),
            _entity("E4", "Alcaldía de Pereira", "entidad_territorial", "Risaralda"),
            _entity("E5", "Hospital Departamental de Caldas", "usuario_adoptante", "Caldas", posicion="beneficiario"),
            _entity("E6", "Red de Salud de Risaralda", "usuario_adoptante", "Risaralda", posicion="beneficiario"),
        ],
        "gobernanza": {
            "toma_decisiones": "Un comité directivo con un delegado por entidad decide por mayoría simple.",
            "instancias": ["Comité directivo", "Comité técnico"],
            "propiedad_intelectual": "La titularidad se reparte según los aportes registrados en el Anexo 3.",
            "seguimiento": "El comité técnico revisa los indicadores cada trimestre.",
        },
    }


DEMAND_1 = "Fortalecer la detección temprana de trastornos mentales en adolescentes del departamento"
DEMAND_2 = "Ampliar la cobertura de servicios digitales de salud mental en los municipios"


def _territory() -> dict:
    return {
        "schema": "morfeo.territorio-sgr/v1",
        "region_sgr": "Eje Cafetero",
        "departamentos": [{"nombre": "Caldas", "municipios": ["Manizales", "Villamaría"]},
                          {"nombre": "Risaralda", "municipios": ["Pereira"]}],
        "demandas": [
            {"codigo": "CAL-01", "texto": DEMAND_1, "departamento": "Caldas", "fuente": "Anexo 4, Caldas",
             "causas": ["c1"], "objetivos": ["OE1"], "actividades": ["1.1.1"], "productos": ["1.1"],
             "articulacion": "El OE1 aporta documentos de investigación a la Gobernación de Caldas."},
            {"codigo": "RIS-01", "texto": DEMAND_2, "departamento": "Risaralda", "fuente": "Anexo 4, Risaralda",
             "causas": ["c2"], "objetivos": ["OE2"], "actividades": ["2.1.1"], "productos": ["2.1"],
             "articulacion": "Mediante la actividad 2.1.1, el proyecto entrega el servicio de información."},
        ],
        "configuracion_regional": [
            {"actor": "Gobernación de Caldas", "departamento": "Caldas",
             "pertinencia": "Coordina la política departamental de salud mental del OE1."},
            {"actor": "Alcaldía de Pereira", "departamento": "Risaralda",
             "pertinencia": "Integra el servicio del OE2 en la red municipal."},
        ],
    }


def _write(run: Path, name: str, data) -> Path:
    path = run / "artefactos" / "sgr" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _make_run(tmp: Path, chain: bool = True, alliance: dict | None = None, territory: dict | None = None) -> Path:
    run = tmp / "run"
    (run / "redaccion" / "sections").mkdir(parents=True, exist_ok=True)
    (run / "artefactos" / "arboles").mkdir(parents=True, exist_ok=True)
    (run / "artefactos" / "arboles" / "arbol_objetivos.json").write_text(json.dumps(TREE, ensure_ascii=False),
                                                                          encoding="utf-8")
    if chain:
        _write(run, "cadena_valor.json", _valid_chain())
    _write(run, "alianza.json", alliance if alliance is not None else _alliance())
    _write(run, "territorio.json", territory if territory is not None else _territory())
    return run


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def _codes(findings: list[dict], severity: str | None = None) -> list[str]:
    return [f["code"] for f in findings if severity is None or f["severity"] == severity]


class _Case(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.mod = _load("alianza_territorio_sgr_under_test", SCRIPT)

    def run_with(self, alliance: dict | None = None, territory: dict | None = None, chain: bool = True) -> Path:
        return _make_run(self.tmp, chain, alliance, territory)

    def findings(self, alliance: dict | None = None, territory: dict | None = None, chain: bool = True) -> list[dict]:
        return self.mod.findings(self.run_with(alliance, territory, chain))


class Check(_Case):
    def test_complete_data_is_clean(self) -> None:
        self.assertEqual(self.findings(), [])

    def test_findings_follow_the_check_run_shape(self) -> None:
        alliance = _alliance()
        alliance["entidades"][0]["tipo"] = "universidad"
        found = self.findings(alliance)
        self.assertTrue(found)
        for f in found:
            self.assertEqual(set(f), {"severity", "code", "message", "node"})
            self.assertIn(f["severity"], ("error", "warning"))
            self.assertTrue(f["code"].startswith(("alianza-", "territorio-")))

    def test_wrong_schema_and_invalid_json(self) -> None:
        alliance = _alliance()
        alliance["schema"] = "otra/v1"
        self.assertIn("alianza-esquema", _codes(self.findings(alliance), "error"))
        run = self.run_with()
        _write(run, "territorio.json", "{no es json")
        self.assertIn("territorio-json-invalido", _codes(self.mod.findings(run), "error"))

    def test_exactly_one_proponent(self) -> None:
        alliance = _alliance()
        alliance["entidades"][1]["proponente"] = True
        self.assertIn("alianza-proponente", _codes(self.findings(alliance), "error"))
        alliance["entidades"][0]["proponente"] = alliance["entidades"][1]["proponente"] = False
        self.assertIn("alianza-proponente", _codes(self.findings(alliance), "error"))

    def test_entity_type_and_position_are_known(self) -> None:
        alliance = _alliance()
        alliance["entidades"][2]["tipo"] = "gobierno"
        alliance["entidades"][3]["posicion"] = "aliado"
        found = self.findings(alliance)
        self.assertIn("alianza-tipo-invalido", _codes(found, "error"))
        self.assertIn("alianza-posicion-invalida", _codes(found, "error"))
        alliance = _alliance()
        alliance["entidades"][3]["posicion"] = None
        self.assertNotIn("alianza-posicion-invalida", _codes(self.findings(alliance)))

    def test_minimum_composition_is_an_error(self) -> None:
        alliance = _alliance()
        alliance["entidades"] = [e for e in alliance["entidades"] if e["tipo"] != "usuario_adoptante"]
        found = [f for f in self.findings(alliance) if f["code"] == "alianza-composicion-minima"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "error")
        self.assertIn("usuario", found[0]["message"])

    def test_a_second_ies_counts_as_the_other_sncti_entity(self) -> None:
        alliance = _alliance()
        alliance["entidades"][1]["tipo"] = "SNCTI"
        self.assertNotIn("alianza-composicion-minima", _codes(self.findings(alliance)))
        alliance["entidades"][1]["tipo"] = "otro"
        self.assertIn("alianza-composicion-minima", _codes(self.findings(alliance), "error"))

    def test_every_execution_department_has_a_territorial_entity(self) -> None:
        territory = _territory()
        territory["departamentos"].append({"nombre": "Quindío", "municipios": ["Armenia"]})
        found = [f for f in self.findings(territory=territory) if f["code"] == "territorio-departamento-sin-entidad"]
        self.assertEqual([(f["severity"], f["node"]) for f in found], [("warning", "Quindío")])

    def test_entity_departments_are_execution_departments(self) -> None:
        alliance = _alliance()
        alliance["entidades"][4]["departamento"] = "Antioquia"
        found = [f for f in self.findings(alliance) if f["code"] == "alianza-departamento-fuera"]
        self.assertEqual([(f["severity"], f["node"]) for f in found], [("warning", "E5")])

    def test_every_demand_has_text_source_and_an_objective(self) -> None:
        territory = _territory()
        territory["demandas"][0]["texto"] = ""
        territory["demandas"][0]["fuente"] = None
        territory["demandas"][1]["objetivos"] = []
        found = [f for f in self.findings(territory=territory) if f["code"] == "territorio-demanda-incompleta"]
        self.assertEqual({f["node"] for f in found}, {"CAL-01", "RIS-01"})
        self.assertEqual({f["severity"] for f in found}, {"error"})
        self.assertIn("texto", found[0]["message"])

    def test_demand_activities_and_products_exist_in_the_value_chain(self) -> None:
        territory = _territory()
        territory["demandas"][0]["actividades"] = ["9.9.9"]
        territory["demandas"][0]["productos"] = ["9.9"]
        territory["demandas"][1]["actividades"] = []
        territory["demandas"][1]["productos"] = []
        found = self.findings(territory=territory)
        self.assertIn("territorio-actividad-desconocida", _codes(found, "error"))
        self.assertIn("territorio-producto-desconocido", _codes(found, "error"))
        self.assertIn("territorio-demanda-sin-actividad", _codes(found, "warning"))
        self.assertIn("territorio-demanda-sin-producto", _codes(found, "warning"))

    def test_without_the_value_chain_activities_and_products_are_not_checked(self) -> None:
        territory = _territory()
        territory["demandas"][0]["actividades"] = ["9.9.9"]
        territory["demandas"][1]["productos"] = []
        alliance = _alliance()
        alliance["entidades"][0]["actividades"] = ["9.9.9"]
        found = self.findings(alliance, territory, chain=False)
        self.assertFalse([c for c in _codes(found) if "actividad" in c or "producto" in c])

    def test_objective_ids_exist_in_the_objective_tree(self) -> None:
        territory = _territory()
        territory["demandas"][0]["objetivos"] = ["OE7"]
        found = [f for f in self.findings(territory=territory) if f["code"] == "territorio-objetivo-desconocido"]
        self.assertEqual([(f["severity"], f["node"]) for f in found], [("error", "CAL-01")])

    def test_contributions_are_not_negative(self) -> None:
        alliance = _alliance()
        alliance["entidades"][2]["aporte_efectivo"] = -5
        alliance["entidades"][3]["aporte_especie"] = "mucho"
        found = self.findings(alliance)
        self.assertIn("alianza-aporte-negativo", _codes(found, "error"))
        self.assertIn("alianza-aporte-invalido", _codes(found, "error"))

    def test_entity_activities_exist_in_the_value_chain(self) -> None:
        alliance = _alliance()
        alliance["entidades"][1]["actividades"] = ["2.1.1", "4.4.4"]
        found = [f for f in self.findings(alliance) if f["code"] == "alianza-actividad-desconocida"]
        self.assertEqual([(f["severity"], f["node"]) for f in found], [("error", "E2")])
        self.assertIn("4.4.4", found[0]["message"])

    def test_missing_governance_is_a_warning(self) -> None:
        alliance = _alliance()
        alliance["gobernanza"] = None
        self.assertIn("alianza-gobernanza-faltante", _codes(self.findings(alliance), "warning"))

    def test_the_same_trajectory_project_listed_twice_is_a_warning(self) -> None:
        alliance = _alliance()
        alliance["entidades"][1]["trayectoria"].append(
            {"nombre": "Otro nombre del proyecto", "codigo": "bpin 2022000100", "financiador": "SGR", "anio": 2022,
             "sgr_o_elegible": True})
        found = [f for f in self.findings(alliance) if f["code"] == "alianza-trayectoria-duplicada"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "warning")
        self.assertIn("E1", found[0]["message"])
        self.assertIn("E2", found[0]["message"])

    def test_only_one_file_still_checks_that_file(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "territorio.json").unlink()
        alliance = _alliance()
        alliance["entidades"][0]["proponente"] = False
        _write(run, "alianza.json", alliance)
        found = self.mod.findings(run)
        self.assertIn("alianza-proponente", _codes(found))
        self.assertFalse([c for c in _codes(found) if c.startswith("territorio-")])

    def test_no_files_means_no_findings(self) -> None:
        run = self.run_with()
        for name in ("alianza.json", "territorio.json"):
            (run / "artefactos" / "sgr" / name).unlink()
        self.assertEqual(self.mod.findings(run), [])


class CheckCli(_Case):
    def test_check_exits_1_on_errors_and_reports_json(self) -> None:
        alliance = _alliance()
        alliance["entidades"][0]["proponente"] = False
        run = self.run_with(alliance)
        result = _cli("check", str(run), "--json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("alianza-proponente", _codes(json.loads(result.stdout)["findings"]))

    def test_check_exits_0_on_clean_data(self) -> None:
        result = _cli("check", str(self.run_with()))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 errores", result.stdout)

    def test_check_reports_a_missing_file_as_an_error(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "territorio.json").unlink()
        result = _cli("check", str(run), "--json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("territorio-archivo-faltante", _codes(json.loads(result.stdout)["findings"], "error"))

    def test_check_without_any_file_is_bad_input(self) -> None:
        run = self.run_with()
        for name in ("alianza.json", "territorio.json"):
            (run / "artefactos" / "sgr" / name).unlink()
        self.assertEqual(_cli("check", str(run)).returncode, 2)


class Render(_Case):
    def sections(self, run: Path) -> Path:
        return run / "redaccion" / "sections"

    def test_render_writes_the_three_table_sections(self) -> None:
        run = self.run_with()
        result = _cli("render", str(run))
        self.assertEqual(result.returncode, 0, result.stderr)
        for stem in RENDERED:
            text = (self.sections(run) / f"{stem}.tex").read_text(encoding="utf-8")
            with self.subTest(stem=stem):
                self.assertEqual(text.splitlines()[0], HEADER)
                self.assertIn(r"\begin{xltabular}", text)
        self.assertFalse((self.sections(run) / "29_idoneidad_trayectoria.tex").exists())

    def test_identification_lists_entities_departments_demands_and_groups(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        text = (self.sections(run) / "26_identificacion.tex").read_text(encoding="utf-8")
        self.assertIn(r"\section{Identificación del proyecto}", text)
        self.assertIn("Tipo de entidad y rol en la alianza", text)
        self.assertIn("Universidad Nacional de Colombia", text)
        self.assertIn("Entidad proponente y ejecutora", text)
        self.assertIn("Manizales, Villamaría", text)
        self.assertIn("CAL-01", text)
        self.assertIn(f"«{DEMAND_1}»", text)
        self.assertIn("COL0053581", text)
        self.assertIn("Eje Cafetero", text)

    def test_demands_table_and_regional_configuration(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        text = (self.sections(run) / "27_demandas_territoriales.tex").read_text(encoding="utf-8")
        self.assertIn(r"\textbf{Demanda territorial} & \textbf{Descripción} & "
                      r"\textbf{Articulación y contribución del proyecto}", text)
        self.assertIn(f"«{DEMAND_2}»", text)
        self.assertIn("Mediante la actividad 2.1.1", text)
        self.assertIn(r"\subsection{Configuración regional", text)
        self.assertIn("Coordina la política departamental", text)

    def test_responsibility_matrix_and_governance(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        text = (self.sections(run) / "28_matriz_responsabilidades.tex").read_text(encoding="utf-8")
        for column in ("Entidad", "Tipo de aliado", "Posición", "Rol", "Responsabilidades u obligaciones",
                       "Aportes (especie / efectivo)"):
            self.assertIn(rf"\textbf{{{column}}}", text)
        self.assertIn("Actividades: 1.1.1, 1.1.3", text)
        self.assertIn(r"\$\,100.000.000", text)
        self.assertIn("Beneficiario", text)
        self.assertIn(r"\subsection{Modelo de gobernanza}", text)
        self.assertIn("Comité directivo; Comité técnico", text)

    def test_missing_governance_renders_without_its_subsection(self) -> None:
        alliance = _alliance()
        alliance["gobernanza"] = None
        run = self.run_with(alliance)
        self.mod.render_sections(run)
        text = (self.sections(run) / "28_matriz_responsabilidades.tex").read_text(encoding="utf-8")
        self.assertNotIn("Modelo de gobernanza}", text)

    def test_render_is_deterministic(self) -> None:
        run = self.run_with()
        self.mod.render_sections(run)
        first = {s: (self.sections(run) / f"{s}.tex").read_bytes() for s in RENDERED}
        self.mod.render_sections(run)
        self.assertEqual(first, {s: (self.sections(run) / f"{s}.tex").read_bytes() for s in RENDERED})

    def test_latex_specials_are_escaped(self) -> None:
        alliance = _alliance()
        alliance["entidades"][5]["nombre"] = "Red 100% R&D {Salud}_#1"
        run = self.run_with(alliance)
        self.mod.render_sections(run)
        text = (self.sections(run) / "28_matriz_responsabilidades.tex").read_text(encoding="utf-8")
        self.assertIn(r"Red 100\% R\&D \{Salud\}\_\#1", text)

    def test_render_refuses_on_error_findings(self) -> None:
        alliance = _alliance()
        alliance["entidades"][0]["proponente"] = False
        run = self.run_with(alliance)
        result = _cli("render", str(run))
        self.assertEqual(result.returncode, 1)
        self.assertIn("alianza-proponente", result.stderr)
        for stem in RENDERED:
            self.assertFalse((self.sections(run) / f"{stem}.tex").exists())

    def test_render_without_both_files_is_bad_input(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "alianza.json").unlink()
        self.assertEqual(_cli("render", str(run)).returncode, 2)

    def test_tdr_chapters_set_the_heading_level(self) -> None:
        run = self.run_with()
        (self.tmp / ".morfeo").mkdir()
        (self.tmp / ".morfeo" / "config.json").write_text(json.dumps({"flujo": "sgr"}), encoding="utf-8")
        structure = {"capitulos": [
            {"numero": 1, "titulo": "IDENTIFICACIÓN DEL PROYECTO", "archivos": []},
            {"numero": 8, "titulo": "ARTICULACIÓN DEL PROYECTO CON LAS DEMANDAS TERRITORIALES",
             "archivos": ["27_demandas_territoriales", "17_articulacion_comunidades"]},
            {"numero": 10, "titulo": "ANÁLISIS DE PARTICIPANTES", "archivos": ["20_participantes"]},
        ]}
        (run / "artefactos" / "estructura_tdr.json").write_text(json.dumps(structure, ensure_ascii=False),
                                                                 encoding="utf-8")
        self.mod.render_sections(run)
        ident = (self.sections(run) / "26_identificacion.tex").read_text(encoding="utf-8")
        demands = (self.sections(run) / "27_demandas_territoriales.tex").read_text(encoding="utf-8")
        matrix = (self.sections(run) / "28_matriz_responsabilidades.tex").read_text(encoding="utf-8")
        self.assertIn(r"\section{IDENTIFICACIÓN DEL PROYECTO}", ident)
        self.assertIn(r"\section{ARTICULACIÓN DEL PROYECTO CON LAS DEMANDAS TERRITORIALES}", demands)
        self.assertNotIn(r"\section{", matrix)
        self.assertIn(r"\subsection{Matriz de responsabilidades", matrix)


class Assembly(unittest.TestCase):
    """S4: the new sections assemble in SGR runs only; the base output does not change (S1)."""

    def setUp(self) -> None:
        self.assembler = _load("ensamblar_main_under_test", REPO / "scripts" / "ensamblar_main.py")
        self.data = {"capitulos": [
            {"numero": 1, "titulo": "IDENTIFICACIÓN DEL PROYECTO", "archivos": ["tdr01_identificacion"]},
            {"numero": 5, "titulo": "IDENTIFICACIÓN Y DESCRIPCIÓN DEL PROBLEMA", "archivos": ["03_descripcion_problema"]},
            {"numero": 8, "titulo": "ARTICULACIÓN DEL PROYECTO CON LAS DEMANDAS TERRITORIALES ATENDIDAS",
             "archivos": ["17_articulacion_comunidades"]},
            {"numero": 10, "titulo": "ANÁLISIS DE PARTICIPANTES", "archivos": ["20_participantes"]},
            {"numero": 27, "titulo": "IDONEIDAD Y TRAYECTORIA DE LA ENTIDAD PROPONENTE Y DEMÁS PARTICIPANTES",
             "archivos": []},
        ]}

    def test_base_body_is_unchanged(self) -> None:
        body = self.assembler.body(self.data)
        self.assertEqual(body, self.assembler.body(self.data, "base"))
        for stem in RENDERED + ("29_idoneidad_trayectoria",):
            self.assertNotIn(stem, body)

    def test_sgr_body_places_each_section_in_its_tdr_chapter(self) -> None:
        body = self.assembler.body(self.data, "sgr")
        order = [body.index(rf"\SeccionSiExiste{{{name}}}") for name in (
            "tdr01_identificacion", "26_identificacion", "03_descripcion_problema", "17_articulacion_comunidades",
            "27_demandas_territoriales", "20_participantes", "28_matriz_responsabilidades",
            "29_idoneidad_trayectoria")]
        self.assertEqual(order, sorted(order))

    def test_a_section_the_structure_already_lists_is_not_repeated(self) -> None:
        self.data["capitulos"][3]["archivos"].insert(0, "28_matriz_responsabilidades")
        body = self.assembler.body(self.data, "sgr")
        self.assertEqual(body.count(r"\SeccionSiExiste{28_matriz_responsabilidades}"), 1)

    def test_template_includes_the_new_sections_after_the_annexes(self) -> None:
        text = (REPO / "plantilla" / "main.tex").read_text(encoding="utf-8")
        names = ("25_marco_logico", "26_identificacion", "27_demandas_territoriales",
                 "28_matriz_responsabilidades", "29_idoneidad_trayectoria", "16_bibliografia")
        positions = [text.index(rf"\SeccionSiExiste{{{n}}}") for n in names]
        self.assertEqual(positions, sorted(positions))


class Puntaje(_Case):
    EXPECTED_54 = {"2.2": 3, "3.1": 4, "3.2": 3, "3.3": 2, "3.4": 0, "4.3": 3}

    def test_preview_with_the_rubric_copied_into_the_run(self) -> None:
        run = self.run_with()
        juez = run / "artefactos" / "juez"
        juez.mkdir(parents=True)
        shutil.copyfile(RUBRICS / "conv54.json", juez / "rubrica.json")
        rows = self.mod.puntaje(run)
        self.assertEqual({r["subcriterio"]: r["puntaje"] for r in rows}, self.EXPECTED_54)
        for row in rows:
            self.assertEqual(set(row), {"subcriterio", "nombre", "puntaje", "max", "incompleto", "calculo"})
        by_id = {r["subcriterio"]: r for r in rows}
        self.assertEqual(by_id["3.2"]["max"], 5)
        self.assertIn("alianza basica", by_id["3.2"]["calculo"])
        self.assertIn("2 departamento", by_id["2.2"]["calculo"])
        self.assertIn("12.00 %", by_id["4.3"]["calculo"])
        self.assertFalse(any(r["incompleto"] for r in rows))

    def test_preview_with_the_rubric_detected_from_the_tdr(self) -> None:
        run = self.run_with()
        (run / "insumos" / "tdr").mkdir(parents=True)
        (run / "insumos" / "tdr" / "tdr.txt").write_text("Términos de referencia CONVOCATORIA 54 del SGR",
                                                         encoding="utf-8")
        result = _cli("puntaje", str(run), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({r["subcriterio"]: r["puntaje"] for r in json.loads(result.stdout)}, self.EXPECTED_54)

    def test_advanced_alliance_and_international_ally(self) -> None:
        alliance = _alliance()
        alliance["entidades"] += [
            _entity("E7", "Instituto de Investigación Regional", "SNCTI", "Caldas"),
            _entity("E8", "Gobernación de Risaralda", "entidad_territorial", "Risaralda"),
            _entity("E9", "Cooperativa de usuarios", "usuario_adoptante", "Caldas"),
            _entity("E10", "University of Toronto", "internacional", None, aporte_efectivo=5_000_000),
        ]
        run = self.run_with(alliance)
        (run / "artefactos" / "juez").mkdir()
        shutil.copyfile(RUBRICS / "conv54.json", run / "artefactos" / "juez" / "rubrica.json")
        rows = {r["subcriterio"]: r["puntaje"] for r in self.mod.puntaje(run)}
        self.assertEqual(rows["3.2"], 5)
        self.assertEqual(rows["3.4"], 1)

    def test_unknown_contribution_marks_the_preview_incomplete(self) -> None:
        alliance = _alliance()
        alliance["entidades"][3]["aporte_especie"] = None
        run = self.run_with(alliance)
        (run / "artefactos" / "juez").mkdir()
        shutil.copyfile(RUBRICS / "conv54.json", run / "artefactos" / "juez" / "rubrica.json")
        rows = {r["subcriterio"]: r for r in self.mod.puntaje(run)}
        self.assertTrue(rows["4.3"]["incompleto"])

    def test_without_a_rubric_the_preview_is_empty_with_a_note(self) -> None:
        run = self.run_with()
        self.assertEqual(self.mod.puntaje(run), [])
        result = _cli("puntaje", str(run), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
        self.assertIn("rúbrica", result.stderr)


class Datos(_Case):
    def test_partial_datos_shape(self) -> None:
        data = self.mod.datos(self.run_with())
        self.assertEqual(data["schema"], "morfeo.datos-sgr/v1")
        self.assertEqual(data["monto_sgr"]["valor"], 1_000_000_000)
        self.assertEqual(data["duracion_meses"], 24)
        self.assertEqual([d["nombre"] for d in data["departamentos_ejecucion"]], ["Caldas", "Risaralda"])
        self.assertEqual(data["proponente"]["nombre"], "Universidad Nacional de Colombia")
        self.assertEqual(data["proponente"]["tipo"], "IES")
        self.assertIs(data["proponente"]["domicilio_en_region"], True)
        self.assertEqual(len(data["aliados"]), 5)
        self.assertEqual(data["aliados"][0]["contrapartida_especie"], 20_000_000)
        self.assertEqual(data["trayectoria"]["proyectos_adicionales"], 3)
        self.assertEqual(data["trayectoria"]["proyectos_sgr_o_elegibles"], 1)
        self.assertIs(data["aliado_internacional_con_aporte"], False)
        self.assertEqual(data["fuente"], ["artefactos/sgr/alianza.json", "artefactos/sgr/territorio.json"])
        self.assertIn("alianza.json", data["monto_sgr"]["fuente"])
        self.assertIn("territorio.json", data["departamentos_ejecucion"][0]["fuente"])

    def test_trajectory_listed_by_two_entities_counts_once(self) -> None:
        alliance = _alliance()
        alliance["entidades"][1]["trayectoria"] += [
            {"nombre": "Nombre distinto", "codigo": "bpin 2022000100", "financiador": "SGR", "anio": 2022,
             "sgr_o_elegible": True},
            {"nombre": "  tamizaje DIGITAL de ansiedad ", "codigo": None, "financiador": None, "anio": None,
             "sgr_o_elegible": False},
        ]
        data = self.mod.datos(self.run_with(alliance))
        self.assertEqual(data["trayectoria"]["proyectos_adicionales"], 3)
        self.assertEqual(data["trayectoria"]["proyectos_sgr_o_elegibles"], 1)

    def test_missing_files_give_null_facts(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "territorio.json").unlink()
        data = self.mod.datos(run)
        self.assertIsNone(data["departamentos_ejecucion"])
        self.assertEqual(data["fuente"], ["artefactos/sgr/alianza.json"])

    def test_datos_cli_prints_json(self) -> None:
        result = _cli("datos", str(self.run_with()), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["schema"], "morfeo.datos-sgr/v1")


class Registration(unittest.TestCase):
    """S4: the four stems are SGR sections wherever SGR sections are listed."""

    STEMS = {"26_identificacion": "§26 Identificación del proyecto",
             "27_demandas_territoriales": "§27 Demandas territoriales y configuración regional",
             "28_matriz_responsabilidades": "§28 Matriz de responsabilidades y gobernanza",
             "29_idoneidad_trayectoria": "§29 Idoneidad y trayectoria"}

    def test_check_run_lists_them_as_sgr_sections_only(self) -> None:
        check_run = _load("check_run_for_alianza_tests", REPO / "scripts" / "check_run.py")
        self.assertLessEqual(set(self.STEMS), set(check_run.SGR_SECTIONS))
        self.assertFalse(set(self.STEMS) & set(check_run.CANONICAL_SECTIONS))

    def test_status_labels(self) -> None:
        sys.path.insert(0, str(REPO / "src"))
        from morfeo.core.status import SECTION_TITLES
        for stem, label in self.STEMS.items():
            self.assertEqual(SECTION_TITLES[stem], label)


class KitCopy(unittest.TestCase):
    def test_kit_copies_are_byte_identical(self) -> None:
        for rel in ("scripts/alianza_territorio_sgr.py", "scripts/ensamblar_main.py", "plantilla/main.tex",
                    "scripts/rubricas_sgr/conv54.json", "scripts/rubricas_sgr/conv56.json"):
            with self.subTest(file=rel):
                kit = REPO / "src" / "morfeo" / "_kit" / rel
                self.assertEqual(kit.read_bytes(), (REPO / rel).read_bytes())


class RubricEvidence(unittest.TestCase):
    """S4: the rubric evidence keys of the counted and alliance criteria point to the new sections."""

    def evidence(self, rid: str) -> dict[str, list[str]]:
        rubric = json.loads((RUBRICS / f"{rid}.json").read_text(encoding="utf-8"))
        return {s["id"]: s["evidencia"] for c in rubric["criterios"] for s in c["subcriterios"]}

    def test_conv54(self) -> None:
        ev = self.evidence("conv54")
        expected = {"2.1": "27_demandas_territoriales", "2.2": "27_demandas_territoriales",
                    "3.1": "29_idoneidad_trayectoria", "3.2": "28_matriz_responsabilidades",
                    "3.3": "26_identificacion", "3.4": "28_matriz_responsabilidades",
                    "4.1": "28_matriz_responsabilidades", "4.3": "28_matriz_responsabilidades"}
        for sid, stem in expected.items():
            self.assertIn(stem, ev[sid], sid)

    def test_conv56(self) -> None:
        ev = self.evidence("conv56")
        self.assertIn("27_demandas_territoriales", ev["2.2"])
        self.assertIn("28_matriz_responsabilidades", ev["4"])
        self.assertIn("29_idoneidad_trayectoria", ev["4"])
        self.assertIn("28_matriz_responsabilidades", ev["7"])


if __name__ == "__main__":
    unittest.main()
