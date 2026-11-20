"""scripts/presupuesto_sgr.py: the SGR budget as data (odd/tasks/sgr-presupuesto-gantt.md, S2 and S3).

`artefactos/sgr/presupuesto.json` is validated by `check`, split across the
value chain activities by `sync-cadena` (even shares, whole pesos, remainder on
the last activity), rendered by `render` into the SGR §13 and the new §30
(Anexo 2 cap. 29) and summarised by `resumen` and `datos`. A base run's §13 is
never touched (S1).
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
SCRIPT = REPO / "scripts" / "presupuesto_sgr.py"
RUBRICS = REPO / "scripts" / "rubricas_sgr"
HEADER = "% GENERADO por scripts/presupuesto_sgr.py"
sys.path.insert(0, str(REPO / "tests"))

from test_alianza_territorio_sgr import _alliance  # noqa: E402
from test_cadena_valor_sgr import TREE, _valid_chain  # noqa: E402

SCHEDULE_STUB = '''
def proyeccion(run_root):
    return {"anios": [{"anio": 1, "valor": 700000000, "pct": 62.5},
                      {"anio": 2, "valor": 420000000, "pct": 37.5}],
            "por_actividad": {}}
'''


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _item(iid: str, rubro: str, insumo: str, entidad: str, fuente: str, valor: int, actividades: list[str],
          **changes) -> dict:
    data = {"id": iid, "rubro": rubro, "insumo_mga": insumo, "descripcion": f"Ítem {iid}",
            "justificacion": f"Financia las actividades {', '.join(actividades)}.", "entidad": entidad,
            "fuente": fuente, "componente": None, "cantidad": 1, "valor_unitario": valor, "talento": None,
            "actividades": actividades, "cotizaciones": 0, "soporte": None}
    data.update(changes)
    return data


def _budget() -> dict:
    """1 000 000 000 SGR plus the 120 000 000 in kind of _alliance(); every rule passes."""
    return {
        "schema": "morfeo.presupuesto-sgr/v1", "duracion_meses": 24, "tope_sgr": None, "semanas_por_mes": 4,
        "factor_prestacional": None,
        "items": [
            _item("P1", "talento_humano", "mano_obra_calificada", "E1", "sgr", 0, ["1.1.1", "1.1.2", "2.1.1"],
                  cantidad=None, valor_unitario=None,
                  talento={"perfil": "Investigador principal", "horas_semana": 20, "valor_hora": 100000,
                           "meses": 24}),
            _item("P2", "equipos_software", "maquinaria_equipo", "E1", "sgr", 50_000_000, ["2.1.1"], cantidad=3,
                  cotizaciones=2),
            _item("P3", "seguimiento", "servicios_empresas", "E1", "sgr", 30_000_000, ["1.1.4"],
                  componente="seguimiento"),
            _item("P4", "gastos_viaje", "transporte", "E1", "sgr", 1_000_000, ["2.2.2"], cantidad=10),
            _item("P5", "servicios_tecnologicos_pruebas", "servicios_empresas", "E2", "sgr", 20_000_000,
                  ["2.2.1", "2.2.2"], componente="transferencia", cotizaciones=3),
            _item("P6", "materiales_insumos_documentacion", "materiales", "E1", "sgr", 598_000_000,
                  ["1.1.1", "1.1.2", "1.1.3"]),
            _item("P7", "talento_humano", "mano_obra_calificada", "E1", "especie", 100_000_000, ["1.1.3"]),
            _item("P8", "infraestructura", "edificios", "E2", "especie", 20_000_000, ["2.1.2"]),
        ],
    }


EXPECTED_COSTS = {"1.1.1": 263_333_333, "1.1.2": 263_333_333, "1.1.3": 299_333_334, "1.1.4": 30_000_000,
                  "2.1.1": 214_000_000, "2.1.2": 20_000_000, "2.2.1": 10_000_000, "2.2.2": 20_000_000,
                  "2.2.3": 0, "2.2.4": 0}


def _write(run: Path, name: str, data) -> Path:
    path = run / "artefactos" / "sgr" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _make_run(tmp: Path, budget: dict | None = None, flujo: str | None = "sgr", chain: bool = True,
              alliance: bool = True) -> Path:
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
    _write(run, "presupuesto.json", budget if budget is not None else _budget())
    return run


def _cli(*args: str, script: Path = SCRIPT) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)


def _codes(findings: list[dict], severity: str | None = None) -> list[str]:
    return [f["code"] for f in findings if severity is None or f["severity"] == severity]


def _chain_costs(run: Path) -> dict[str, int]:
    chain = json.loads((run / "artefactos" / "sgr" / "cadena_valor.json").read_text(encoding="utf-8"))
    return {a["codigo"]: a["costo"] for o in chain["objetivos"] for p in o["productos"] for a in p["actividades"]}


class _Case(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.mod = _load("presupuesto_sgr_under_test", SCRIPT)

    def run_with(self, budget: dict | None = None, **kwargs) -> Path:
        return _make_run(self.tmp, budget, **kwargs)

    def synced(self, budget: dict | None = None, **kwargs) -> Path:
        run = self.run_with(budget, **kwargs)
        self.mod.sync_cadena(run)
        return run

    def isolated(self, with_schedule: bool) -> Path:
        """presupuesto_sgr and its siblings in their own folder, with or without a stub cronograma_sgr."""
        scripts = self.tmp / "aislado"
        scripts.mkdir(exist_ok=True)
        for name in ("presupuesto_sgr.py", "cadena_valor_sgr.py", "check_run.py", "ensamblar_main.py"):
            shutil.copy(REPO / "scripts" / name, scripts / name)
        if with_schedule:
            (scripts / "cronograma_sgr.py").write_text(SCHEDULE_STUB, encoding="utf-8")
        return scripts / "presupuesto_sgr.py"


class NumberToWords(unittest.TestCase):
    """S3: the amounts of §30 go in letters and numbers."""

    CASES = {
        0: "CERO PESOS M/CTE",
        1: "UN PESO M/CTE",
        21: "VEINTIÚN PESOS M/CTE",
        100: "CIEN PESOS M/CTE",
        101: "CIENTO UN PESOS M/CTE",
        200: "DOSCIENTOS PESOS M/CTE",
        1_000: "MIL PESOS M/CTE",
        21_000: "VEINTIÚN MIL PESOS M/CTE",
        1_000_000: "UN MILLÓN DE PESOS M/CTE",
        1_001_000: "UN MILLÓN MIL PESOS M/CTE",
        21_000_000: "VEINTIÚN MILLONES DE PESOS M/CTE",
        1_000_000_000: "MIL MILLONES DE PESOS M/CTE",
        17_177_626_246: ("DIECISIETE MIL CIENTO SETENTA Y SIETE MILLONES SEISCIENTOS VEINTISÉIS MIL "
                         "DOSCIENTOS CUARENTA Y SEIS PESOS M/CTE"),
    }

    def test_edge_values(self) -> None:
        mod = _load("presupuesto_sgr_words", SCRIPT)
        for value, words in self.CASES.items():
            with self.subTest(value=value):
                self.assertEqual(mod.pesos_en_letras(value), words)

    def test_plain_cardinal_keeps_uno(self) -> None:
        mod = _load("presupuesto_sgr_words", SCRIPT)
        self.assertEqual(mod.number_words(31), "treinta y uno")
        self.assertEqual(mod.number_words(31_000), "treinta y un mil")
        self.assertEqual(mod.number_words(1_000_000_000_000), "un billón")

    def test_negative_or_fractional_is_rejected(self) -> None:
        mod = _load("presupuesto_sgr_words", SCRIPT)
        for bad in (-1, 1.5):
            with self.assertRaises(ValueError):
                mod.number_words(bad)


class Check(_Case):
    def test_clean_budget_after_sync_has_no_findings(self) -> None:
        self.assertEqual(self.mod.findings(self.synced()), [])

    def test_findings_follow_the_check_run_shape(self) -> None:
        budget = _budget()
        budget["items"][0]["rubro"] = "viaticos"
        for f in self.mod.findings(self.run_with(budget)):
            self.assertEqual(set(f), {"severity", "code", "message", "node"})
            self.assertTrue(f["code"].startswith("presupuesto-"))

    def test_no_file_means_no_findings_and_check_reports_it(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "presupuesto.json").unlink()
        self.assertEqual(self.mod.findings(run), [])
        result = _cli("check", str(run), "--json")
        self.assertEqual(result.returncode, 2)

    def test_schema_and_invalid_json(self) -> None:
        budget = _budget()
        budget["schema"] = "otro"
        self.assertEqual(_codes(self.mod.findings(self.run_with(budget))), ["presupuesto-esquema"])
        run = self.run_with()
        _write(run, "presupuesto.json", "{no es json")
        self.assertEqual(_codes(self.mod.findings(run)), ["presupuesto-json-invalido"])

    def test_enums_are_validated(self) -> None:
        budget = _budget()
        budget["items"][0]["rubro"] = "viaticos"
        budget["items"][1]["insumo_mga"] = "equipos"
        budget["items"][2]["fuente"] = "regalias"
        budget["items"][3]["componente"] = "difusion"
        found = self.mod.findings(self.synced(budget))
        for code, node in (("presupuesto-rubro-invalido", "P1"), ("presupuesto-insumo-invalido", "P2"),
                           ("presupuesto-fuente-invalida", "P3"), ("presupuesto-componente-invalido", "P4")):
            hit = [f for f in found if f["code"] == code]
            self.assertEqual([(f["severity"], f["node"]) for f in hit], [("error", node)], code)

    def test_entity_must_exist_in_the_alliance(self) -> None:
        budget = _budget()
        budget["items"][3]["entidad"] = "E9"
        found = self.mod.findings(self.synced(budget))
        self.assertIn(("presupuesto-entidad-desconocida", "P4"),
                      [(f["code"], f["node"]) for f in found if f["severity"] == "error"])

    def test_without_the_alliance_entities_are_not_checked(self) -> None:
        budget = _budget()
        budget["items"][3]["entidad"] = "E9"
        found = self.mod.findings(self.synced(budget, alliance=False))
        self.assertNotIn("presupuesto-entidad-desconocida", _codes(found))
        self.assertIn("presupuesto-alianza-faltante", _codes(found, "warning"))

    def test_every_item_finances_known_activities(self) -> None:
        budget = _budget()
        budget["items"][7]["actividades"] = []
        budget["items"][6]["actividades"] = ["1.1.3", "9.9.9"]
        found = self.mod.findings(self.run_with(budget))
        self.assertIn(("presupuesto-sin-actividades", "P8"), [(f["code"], f["node"]) for f in found])
        unknown = next(f for f in found if f["code"] == "presupuesto-actividad-desconocida")
        self.assertEqual((unknown["severity"], unknown["node"]), ("error", "P7"))
        self.assertIn("9.9.9", unknown["message"])

    def test_without_the_value_chain_codes_are_not_checked(self) -> None:
        budget = _budget()
        budget["items"][6]["actividades"] = ["9.9.9"]
        found = self.mod.findings(self.run_with(budget, chain=False))
        self.assertNotIn("presupuesto-actividad-desconocida", _codes(found))
        self.assertIn("presupuesto-cadena-faltante", _codes(found, "warning"))

    def test_sgr_total_over_the_declared_cap_is_an_error(self) -> None:
        budget = _budget()
        budget["tope_sgr"] = 999_999_999
        found = self.mod.findings(self.synced(budget))
        self.assertIn("presupuesto-tope-superado", _codes(found, "error"))
        budget["tope_sgr"] = 1_000_000_000
        self.assertNotIn("presupuesto-tope-superado", _codes(self.mod.findings(self.synced(budget))))

    def test_without_tope_sgr_the_rubric_cap_applies(self) -> None:
        run = self.synced()
        juez = run / "artefactos" / "juez"
        juez.mkdir(parents=True)
        rubric = json.loads((RUBRICS / "conv54.json").read_text(encoding="utf-8"))
        rubric["tope_solicitud_sgr"] = 900_000_000
        (juez / "rubrica.json").write_text(json.dumps(rubric, ensure_ascii=False), encoding="utf-8")
        hit = next(f for f in self.mod.findings(run) if f["code"] == "presupuesto-tope-superado")
        self.assertIn("conv54", hit["message"])
        self.assertEqual(self.mod.resumen(run)["tope_sgr"], 900_000_000)
        budget = _budget()
        budget["tope_sgr"] = 2_000_000_000
        _write(run, "presupuesto.json", budget)
        self.assertNotIn("presupuesto-tope-superado", _codes(self.mod.findings(run)))

    def test_without_cap_or_rubric_there_is_no_cap_check(self) -> None:
        run = self.synced()
        self.assertIsNone(self.mod.resumen(run)["tope_sgr"])
        self.assertNotIn("presupuesto-tope-superado", _codes(self.mod.findings(run)))

    def test_seguimiento_with_sgr_money_is_required(self) -> None:
        budget = _budget()
        budget["items"][2]["fuente"] = "especie"
        budget["items"][6]["valor_unitario"] = 70_000_000
        found = self.mod.findings(self.synced(budget))
        self.assertIn("presupuesto-seguimiento-faltante", _codes(found, "error"))

    def test_equipment_and_services_need_two_quotes(self) -> None:
        budget = _budget()
        budget["items"][1]["cotizaciones"] = 1
        budget["items"][4]["cotizaciones"] = None
        found = [f for f in self.mod.findings(self.synced(budget)) if f["code"] == "presupuesto-cotizaciones"]
        self.assertEqual([(f["severity"], f["node"]) for f in found], [("warning", "P2"), ("warning", "P5")])

    def test_mobility_over_two_percent_is_a_warning(self) -> None:
        budget = _budget()
        budget["items"][3]["cantidad"] = 21
        budget["items"][5]["valor_unitario"] = 587_000_000
        found = self.mod.findings(self.synced(budget))
        self.assertIn("presupuesto-movilidad-alta", _codes(found, "warning"))
        self.assertNotIn("presupuesto-movilidad-alta", _codes(self.mod.findings(self.synced())))

    def test_transfer_under_one_percent_is_a_warning(self) -> None:
        budget = _budget()
        budget["items"][4]["componente"] = None
        self.assertIn("presupuesto-transferencia-baja", _codes(self.mod.findings(self.synced(budget)), "warning"))

    def test_entity_counterpart_must_match_the_alliance(self) -> None:
        budget = _budget()
        budget["items"][6]["valor_unitario"] = 90_000_000
        budget["items"][7]["fuente"] = "efectivo"
        found = [f for f in self.mod.findings(self.synced(budget)) if f["code"] == "presupuesto-contrapartida-no-cuadra"]
        self.assertEqual({(f["severity"], f["node"]) for f in found}, {("error", "E1"), ("error", "E2")})
        self.assertEqual(len(found), 3)  # E1 especie, E2 especie and E2 efectivo

    def test_undeclared_counterpart_is_not_compared(self) -> None:
        run = self.run_with()
        alliance = _alliance()
        alliance["entidades"][0]["aporte_especie"] = None
        _write(run, "alianza.json", alliance)
        budget = _budget()
        budget["items"][6]["valor_unitario"] = 90_000_000
        _write(run, "presupuesto.json", budget)
        self.mod.sync_cadena(run)
        found = self.mod.findings(run)
        self.assertNotIn(("presupuesto-contrapartida-no-cuadra", "E1"), [(f["code"], f["node"]) for f in found])

    def test_drift_after_sync_is_an_error(self) -> None:
        run = self.synced()
        chain = json.loads((run / "artefactos" / "sgr" / "cadena_valor.json").read_text(encoding="utf-8"))
        chain["objetivos"][0]["productos"][0]["actividades"][0]["costo"] = 1
        _write(run, "cadena_valor.json", chain)
        hit = [f for f in self.mod.findings(run) if f["code"] == "presupuesto-costo-desincronizado"]
        self.assertEqual([(f["severity"], f["node"]) for f in hit], [("error", "1.1.1")])

    def test_an_unsynced_chain_is_a_warning(self) -> None:
        run = self.run_with()
        chain = _valid_chain()
        for o in chain["objetivos"]:
            for p in o["productos"]:
                for a in p["actividades"]:
                    a["costo"] = None
        _write(run, "cadena_valor.json", chain)
        found = self.mod.findings(run)
        self.assertIn("presupuesto-cadena-sin-sincronizar", _codes(found, "warning"))
        self.assertNotIn("presupuesto-costo-desincronizado", _codes(found))

    def test_numbers_are_not_negative(self) -> None:
        budget = _budget()
        budget["items"][1]["cantidad"] = -3
        budget["items"][0]["talento"]["valor_hora"] = "mucho"
        budget["items"][2]["cotizaciones"] = -1
        budget["factor_prestacional"] = -1
        found = [(f["code"], f["node"]) for f in self.mod.findings(self.run_with(budget))]
        for expected in (("presupuesto-valor-negativo", "P2"), ("presupuesto-valor-invalido", "P1"),
                         ("presupuesto-valor-negativo", "P3"), ("presupuesto-valor-negativo", "presupuesto")):
            self.assertIn(expected, found)

    def test_duplicate_item_ids(self) -> None:
        budget = _budget()
        budget["items"][1]["id"] = "P1"
        self.assertIn("presupuesto-id-duplicado", _codes(self.mod.findings(self.synced(budget)), "error"))

    def test_check_cli_exit_codes_and_json(self) -> None:
        run = self.synced()
        ok = _cli("check", str(run))
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("presupuesto: 0 errores, 0 avisos", ok.stdout)
        budget = _budget()
        budget["items"][0]["rubro"] = "viaticos"
        _write(run, "presupuesto.json", budget)
        bad = _cli("check", str(run), "--json")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("presupuesto-rubro-invalido", _codes(json.loads(bad.stdout)["findings"]))


class Values(_Case):
    def test_item_value_and_talent_formula(self) -> None:
        budget = _budget()
        self.assertEqual(self.mod.item_value(budget["items"][0], budget), 192_000_000)
        self.assertEqual(self.mod.item_value(budget["items"][1], budget), 150_000_000)
        budget["factor_prestacional"] = 1.5
        budget["semanas_por_mes"] = 4.33
        self.assertEqual(self.mod.item_value(budget["items"][0], budget), 311_760_000)

    def test_even_split_puts_the_remainder_on_the_last_activity(self) -> None:
        self.assertEqual(self.mod.split(598_000_000, ["a", "b", "c"]),
                         [("a", 199_333_333), ("b", 199_333_333), ("c", 199_333_334)])
        self.assertEqual(self.mod.split(100, ["a", "b", "c"]), [("a", 33), ("b", 33), ("c", 34)])
        self.assertEqual(self.mod.split(200, ["a", "b", "c"]), [("a", 67), ("b", 67), ("c", 66)])
        self.assertEqual(self.mod.split(5, []), [])


class SyncCadena(_Case):
    def test_sync_writes_exact_costs_and_keeps_every_other_field(self) -> None:
        run = self.run_with()
        path = run / "artefactos" / "sgr" / "cadena_valor.json"
        before = json.loads(path.read_text(encoding="utf-8"))
        before["objetivos"][0]["productos"][0]["actividades"][0]["etapa"] = "preinversion"
        _write(run, "cadena_valor.json", before)
        self.mod.sync_cadena(run)
        after = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(_chain_costs(run), EXPECTED_COSTS)
        self.assertEqual(sum(EXPECTED_COSTS.values()), self.mod.resumen(run)["total"])
        stripped = copy.deepcopy(after)
        for o_a, o_b in zip(stripped["objetivos"], before["objetivos"]):
            for p_a, p_b in zip(o_a["productos"], o_b["productos"]):
                for a_a, a_b in zip(p_a["actividades"], p_b["actividades"]):
                    self.assertEqual(list(a_a), list(a_b))  # same keys, same order
                    a_a["costo"] = a_b["costo"]
        self.assertEqual(stripped, before)

    def test_sync_cli_and_refusal(self) -> None:
        run = self.run_with()
        ok = _cli("sync-cadena", str(run))
        self.assertEqual(ok.returncode, 0, ok.stderr)
        budget = _budget()
        budget["items"][0]["actividades"] = ["9.9.9"]
        _write(run, "presupuesto.json", budget)
        before = (run / "artefactos" / "sgr" / "cadena_valor.json").read_bytes()
        bad = _cli("sync-cadena", str(run))
        self.assertEqual(bad.returncode, 1)
        self.assertIn("presupuesto-actividad-desconocida", bad.stderr)
        self.assertEqual((run / "artefactos" / "sgr" / "cadena_valor.json").read_bytes(), before)

    def test_sync_without_the_chain_is_bad_input(self) -> None:
        self.assertEqual(_cli("sync-cadena", str(self.run_with(chain=False))).returncode, 2)


class Resumen(_Case):
    def test_resumen_shape_and_values(self) -> None:
        data = self.mod.resumen(self.synced())
        self.assertEqual(set(data), {"total_sgr", "total_especie", "total_efectivo", "total", "tope_sgr",
                                     "por_rubro", "por_insumo", "por_entidad", "cofinanciacion_pct",
                                     "transferencia_pct", "movilidad_pct", "seguimiento", "cotizaciones_faltantes",
                                     "por_actividad"})
        self.assertEqual((data["total_sgr"], data["total_especie"], data["total_efectivo"], data["total"]),
                         (1_000_000_000, 120_000_000, 0, 1_120_000_000))
        self.assertEqual(data["por_rubro"]["talento_humano"], {"sgr": 192_000_000, "especie": 100_000_000,
                                                                "efectivo": 0})
        self.assertEqual(list(data["por_rubro"])[0], "talento_humano")
        self.assertEqual(data["por_insumo"]["servicios_empresas"]["sgr"], 50_000_000)
        self.assertEqual(data["por_entidad"]["E2"], {"sgr": 20_000_000, "especie": 20_000_000, "efectivo": 0})
        self.assertEqual((data["cofinanciacion_pct"], data["transferencia_pct"], data["movilidad_pct"]),
                         (12.0, 2.0, 1.0))
        self.assertIs(data["seguimiento"], True)
        self.assertEqual(data["cotizaciones_faltantes"], 0)
        self.assertEqual(data["por_actividad"], EXPECTED_COSTS)

    def test_missing_quotes_are_counted(self) -> None:
        budget = _budget()
        budget["items"][1]["cotizaciones"] = 0
        self.assertEqual(self.mod.resumen(self.run_with(budget))["cotizaciones_faltantes"], 1)

    def test_resumen_without_the_file_is_none(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "presupuesto.json").unlink()
        self.assertIsNone(self.mod.resumen(run))

    def test_resumen_cli(self) -> None:
        result = _cli("resumen", str(self.synced()), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["total"], 1_120_000_000)


class Datos(_Case):
    def test_money_part_of_datos_sgr(self) -> None:
        data = self.mod.datos(self.synced())
        self.assertEqual(data["schema"], "morfeo.datos-sgr/v1")
        self.assertEqual(data["monto_sgr"]["valor"], 1_000_000_000)
        self.assertIn("presupuesto.json", data["monto_sgr"]["fuente"])
        self.assertEqual(data["transferencia_valor"], 20_000_000)
        self.assertEqual(data["aportes_entidades"][0], {
            "entidad": "E1", "sgr": 980_000_000, "contrapartida_especie": 100_000_000, "contrapartida_efectivo": 0,
            "fuente": "artefactos/sgr/presupuesto.json (ítems de E1)"})
        self.assertEqual([(t["documento"], t["concepto"], t["valor"]) for t in data["totales_declarados"]],
                         [("presupuesto", "sgr", 1_000_000_000), ("presupuesto", "contrapartida", 120_000_000),
                          ("presupuesto", "total", 1_120_000_000)])
        self.assertEqual(data["fuente"], ["artefactos/sgr/presupuesto.json"])

    def test_missing_file_gives_null_facts(self) -> None:
        run = self.run_with()
        (run / "artefactos" / "sgr" / "presupuesto.json").unlink()
        data = self.mod.datos(run)
        self.assertIsNone(data["monto_sgr"])
        self.assertEqual(data["fuente"], [])
        result = _cli("datos", str(run), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(json.loads(result.stdout)["totales_declarados"])


class Render(_Case):
    def sections(self, run: Path) -> tuple[str, str]:
        base = run / "redaccion" / "sections"
        return ((base / "13_presupuesto.tex").read_text(encoding="utf-8"),
                (base / "30_fuentes_financiacion.tex").read_text(encoding="utf-8"))

    def test_render_writes_both_sections_with_the_header(self) -> None:
        run = self.synced()
        result = _cli("render", str(run), script=self.isolated(with_schedule=False))
        self.assertEqual(result.returncode, 0, result.stderr)
        budget_tex, sources_tex = self.sections(run)
        for text in (budget_tex, sources_tex):
            self.assertEqual(text.splitlines()[0], HEADER)
            self.assertIn(r"\begin{xltabular}", text)
        self.assertIn("cronograma_sgr.py", result.stderr)  # the projection note

    def test_budget_section_has_the_two_views_and_the_items(self) -> None:
        run = self.synced()
        self.mod.render_sections(run)
        text, _ = self.sections(run)
        self.assertIn(r"\section{Presupuesto}", text)
        self.assertIn(r"\label{tab:presupuesto}", text)
        self.assertIn(r"\textbf{Talento humano} & \textbf{\$\,192.000.000} & \textbf{\$\,100.000.000} & "
                      r"\textbf{\$\,0} & \textbf{\$\,292.000.000} \\", text)
        self.assertIn(r"\hspace{1em}Universidad Nacional de Colombia & \$\,192.000.000", text)
        self.assertIn(r"\textbf{Total} & \textbf{\$\,1.000.000.000} & \textbf{\$\,120.000.000} & \textbf{\$\,0} & "
                      r"\textbf{\$\,1.120.000.000} \\", text)
        self.assertIn(r"\label{tab:presupuesto_entidades}", text)
        self.assertIn(r"Universidad Tecnológica de Pereira & \$\,20.000.000 & \$\,20.000.000", text)
        self.assertIn(r"\subsection{Presupuesto por insumo de la MGA}", text)
        self.assertIn(r"Servicios a empresas y a la producción & \$\,50.000.000", text)
        self.assertIn(r"\subsection{Justificación de los ítems}", text)
        self.assertIn("1.1.1, 1.1.2, 2.1.1", text)
        self.assertIn("Perfil: Investigador principal; 20 horas por semana durante 24 meses.", text)
        self.assertIn(r"\subsection{Proyección financiera anual}", text)

    def test_projection_table_when_the_schedule_module_exists(self) -> None:
        run = self.synced()
        result = _cli("render", str(run), script=self.isolated(with_schedule=True))
        self.assertEqual(result.returncode, 0, result.stderr)
        text, _ = self.sections(run)
        self.assertIn(r"Año 1 & \$\,700.000.000 & 62,50\,\% \\", text)
        self.assertIn(r"Año 2 & \$\,420.000.000 & 37,50\,\% \\", text)
        self.assertIn(r"\label{tab:presupuesto_proyeccion}", text)
        self.assertNotIn("nota:", result.stderr)

    def test_sources_section_has_the_three_literal_lines(self) -> None:
        run = self.synced()
        self.mod.render_sections(run)
        _, text = self.sections(run)
        self.assertIn(r"\section{Resumen de fuentes de financiación}", text)
        self.assertIn(r"\textbf{Entidad} & \textbf{Fuente de recursos} & \textbf{Valor} \\", text)
        self.assertIn(r"Universidad Nacional de Colombia & Sistema General de Regalías (SGR) & \$\,980.000.000", text)
        self.assertIn(r"Universidad Tecnológica de Pereira & Contrapartida en especie & \$\,20.000.000", text)
        self.assertIn("Valor total de recursos solicitados a la Asignación de CTeI/ Asignación de CTeI Ambiental "
                      "del SGR – Sistema General de Regalías: MIL MILLONES DE PESOS M/CTE (\\$\\,1.000.000.000).",
                      text)
        self.assertIn("Valor total contrapartida (en efectivo y en especie): CIENTO VEINTE MILLONES DE PESOS M/CTE "
                      "(\\$\\,120.000.000).", text)
        self.assertIn("Valor total del proyecto: MIL CIENTO VEINTE MILLONES DE PESOS M/CTE (\\$\\,1.120.000.000).",
                      text)

    def test_render_is_deterministic(self) -> None:
        run = self.synced()
        self.mod.render_sections(run)
        first = self.sections(run)
        self.mod.render_sections(run)
        self.assertEqual(self.sections(run), first)

    def test_latex_specials_are_escaped(self) -> None:
        budget = _budget()
        budget["items"][5]["descripcion"] = "Reactivos & kits al 100% #1"
        run = self.synced(budget)
        self.mod.render_sections(run)
        text, _ = self.sections(run)
        self.assertIn(r"Reactivos \& kits al 100\% \#1", text)

    def test_render_refuses_on_error_findings(self) -> None:
        budget = _budget()
        budget["items"][0]["rubro"] = "viaticos"
        run = self.synced(budget)
        result = _cli("render", str(run))
        self.assertEqual(result.returncode, 1)
        self.assertIn("presupuesto-rubro-invalido", result.stderr)
        self.assertFalse((run / "redaccion" / "sections" / "13_presupuesto.tex").exists())

    def test_base_run_section_13_is_never_touched(self) -> None:
        run = self.run_with(flujo="base")
        self.mod.sync_cadena(run)
        tex = run / "redaccion" / "sections" / "13_presupuesto.tex"
        tex.write_text("\\section{Presupuesto}\nA mano.\n", encoding="utf-8")
        result = _cli("render", str(run))
        self.assertEqual(result.returncode, 2)
        self.assertIn("flujo SGR", result.stderr)
        self.assertEqual(tex.read_text(encoding="utf-8"), "\\section{Presupuesto}\nA mano.\n")
        self.assertFalse((run / "redaccion" / "sections" / "30_fuentes_financiacion.tex").exists())

    def test_tdr_chapter_titles_the_sources_section(self) -> None:
        run = self.synced()
        structure = {"capitulos": [
            {"numero": 22, "titulo": "CRONOGRAMA", "archivos": ["14_cronograma_actividades"]},
            {"numero": 29, "titulo": "RESUMEN DE FUENTES DE FINANCIACIÓN", "archivos": []},
        ]}
        (run / "artefactos" / "estructura_tdr.json").write_text(json.dumps(structure, ensure_ascii=False),
                                                               encoding="utf-8")
        self.mod.render_sections(run)
        budget_tex, sources_tex = self.sections(run)
        self.assertIn(r"\section{RESUMEN DE FUENTES DE FINANCIACIÓN}", sources_tex)
        self.assertIn(r"\section{Presupuesto}", budget_tex)


class KitCopy(unittest.TestCase):
    def test_kit_copy_is_byte_identical(self) -> None:
        kit = REPO / "src" / "morfeo" / "_kit" / "scripts" / "presupuesto_sgr.py"
        self.assertEqual(kit.read_bytes(), SCRIPT.read_bytes())


if __name__ == "__main__":
    unittest.main()
