"""scripts/juez_sgr.py: deterministic half of the SGR judge.

The juez-sgr agent reads the proposal and writes one evaluation round; this
script prepares the rubric and the mechanical checks, validates the round
against the official rubric, computes the count-based subcriteria from
datos_sgr.json, cross-checks the money figures, sums and decides eligibility.
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
SCRIPT = REPO / "scripts" / "juez_sgr.py"
RUBRICS = REPO / "scripts" / "rubricas_sgr"


def _load_module():
    spec = importlib.util.spec_from_file_location("juez_sgr", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rubric(rid: str) -> dict:
    return json.loads((RUBRICS / f"{rid}.json").read_text(encoding="utf-8"))


def _sub(rubric: dict, sid: str) -> dict:
    for criterion in rubric["criterios"]:
        for sub in criterion["subcriterios"]:
            if sub["id"] == sid:
                return sub
    raise KeyError(sid)


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


_TEMP_ROOTS: list[Path] = []


def tearDownModule() -> None:
    for root in _TEMP_ROOTS:
        shutil.rmtree(root, ignore_errors=True)


def _make_run(flujo: str = "sgr", tdr: str | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="juez-sgr-"))
    _TEMP_ROOTS.append(root)
    (root / ".morfeo").mkdir()
    (root / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = root / "proposals" / "r1"
    sections = run / "redaccion" / "sections"
    sections.mkdir(parents=True)
    (run / "artefactos").mkdir()
    (run / "insumos" / "tdr").mkdir(parents=True)
    (sections / "10_metodologia.tex").write_text(
        "La metodología parte de TRL 4 de entrada y llega a TRL 6 de salida.\n"
        "\\begin{figure}\\caption{}\\label{fig:a}\\end{figure}\n", encoding="utf-8")
    (sections / "13_presupuesto.tex").write_text("Presupuesto por rubros. \\label{fig:a}\n", encoding="utf-8")
    if tdr is not None:
        (run / "insumos" / "tdr" / "tdr.txt").write_text(tdr, encoding="utf-8")
    return run


def _round(rubric: dict, n: int = 1, overrides: dict | None = None) -> dict:
    """A valid round that gives every non-count subcriterion its maximum."""
    overrides = overrides or {}
    criteria = []
    exceptions = rubric["justificacion"]["excepciones"]
    for criterion in rubric["criterios"]:
        for sub in criterion["subcriterios"]:
            low, _high = exceptions.get(sub["id"], exceptions.get(criterion["id"],
                                        [rubric["justificacion"]["min_chars"], 0]))
            entry = {"id": sub["id"], "puntaje": None, "componentes": None, "nivel_descriptor": "",
                     "justificacion": "J" * (low + 10), "evidencia": [{"ubicacion": "§10", "cita": "texto"}],
                     "para_subir": None}
            if sub["modo"] == "niveles":
                entry["puntaje"] = max(level["puntos"] for level in sub["niveles"])
            elif sub["modo"] == "acumulable":
                entry["componentes"] = {c["id"]: c["max"] for c in sub["componentes"]}
            entry.update(overrides.get(sub["id"], {}))
            criteria.append(entry)
    return {"ronda": n, "fecha": "2026-11-19", "rubrica": rubric["id"], "criterios": criteria,
            "alertas": [], "acciones": [{"id": "A1", "criterios": ["1.1"], "agente": "redactor",
                                         "secciones": ["10_metodologia"], "instruccion": "Precisar hitos.",
                                         "impacto_estimado": 2, "prioridad": 1}],
            "concepto": " ".join(["palabra"] * 310), "recomienda": True}


def _ally(tipo: str, especie: float = 0, efectivo: float = 0, nombre: str = "") -> dict:
    return {"nombre": nombre or tipo, "tipo": tipo, "departamento": "D1", "contrapartida_especie": especie,
            "contrapartida_efectivo": efectivo, "fuente": "Anexo 1"}


def _datos(**changes) -> dict:
    data = {
        "schema": "morfeo.datos-sgr/v1",
        "monto_sgr": {"valor": 1_000_000_000, "fuente": "Anexo 3"},
        "duracion_meses": 36,
        "departamentos_ejecucion": [{"nombre": "D1", "fuente": "SIGP"}, {"nombre": "D2", "fuente": "SIGP"},
                                    {"nombre": "D3", "fuente": "SIGP"}],
        "proponente": {"nombre": "P", "tipo": "IES", "domicilio_en_region": True, "tipo_diverso": True,
                       "fuente": "Anexo 1"},
        "aliados": [_ally("SNCTI", 20_000_000, 10_000_000), _ally("entidad_territorial", 20_000_000),
                    _ally("entidad_territorial", 20_000_000), _ally("usuario_adoptante", 10_000_000),
                    _ally("usuario_adoptante", 10_000_000), _ally("SNCTI", 10_000_000),
                    _ally("usuario_adoptante", 5_000_000), _ally("IES", 5_000_000),
                    _ally("internacional", 1_000_000)],
        "trayectoria": {"proyectos_adicionales": 4, "proyectos_sgr_o_elegibles": 1, "fuente": "Anexo 5"},
        "aliado_internacional_con_aporte": True,
        "transferencia_valor": 20_000_000,
        "trl": {"tipologia": "B", "entrada": 4, "salida": 6, "fuente": "§2"},
        "productos_adicionales": {"total": 3, "top_o_a": 2, "fuente": "§15"},
        "totales_declarados": [{"documento": "Anexo 2", "concepto": "sgr", "valor": 1_000_000_000},
                               {"documento": "Anexo 3", "concepto": "sgr", "valor": 1_000_000_000},
                               {"documento": "Anexo 3", "concepto": "contrapartida", "valor": 111_000_000}],
    }
    data.update(changes)
    return data


def _prepare_for_scoring(run: Path, rid: str, rounds: list[dict], datos: dict | None) -> None:
    juez = run / "artefactos" / "juez"
    juez.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RUBRICS / f"{rid}.json", juez / "rubrica.json")
    if datos is not None:
        (juez / "datos_sgr.json").write_text(json.dumps(datos), encoding="utf-8")
    for data in rounds:
        (juez / f"evaluacion_ronda_{data['ronda']}.json").write_text(json.dumps(data), encoding="utf-8")


def _evaluation(run: Path) -> dict:
    return json.loads((run / "artefactos" / "juez" / "evaluacion.json").read_text(encoding="utf-8"))


def _alert_codes(evaluation: dict) -> set[str]:
    return {alert["codigo"] for alert in evaluation["verificaciones"]}


class RubricFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.juez = _load_module()

    def test_rubrics_validate_and_sum_to_100_with_tdr_maxima(self) -> None:
        expected = {"conv54": [40, 30, 15, 15], "conv56": [30, 20, 23, 10, 5, 10, 2]}
        for rid, maxima in expected.items():
            rubric = _rubric(rid)
            self.assertEqual(self.juez.validate_rubric(rubric), [], rid)
            self.assertEqual(rubric["total"], 100)
            self.assertEqual([c["max"] for c in rubric["criterios"]], maxima, rid)
            self.assertEqual(sum(s["max"] for c in rubric["criterios"] for s in c["subcriterios"]), 100, rid)

    def test_modes_follow_the_tdr(self) -> None:
        conv54, conv56 = _rubric("conv54"), _rubric("conv56")
        modes54 = {s["id"]: s["modo"] for c in conv54["criterios"] for s in c["subcriterios"]}
        self.assertEqual({k for k, v in modes54.items() if v == "acumulable"}, {"1.2", "1.3", "1.4", "2.5"})
        self.assertEqual({k for k, v in modes54.items() if v == "conteo"},
                         {"2.2", "3.1", "3.2", "3.3", "3.4", "4.3"})
        modes56 = {s["id"]: s["modo"] for c in conv56["criterios"] for s in c["subcriterios"]}
        self.assertEqual({k for k, v in modes56.items() if v == "conteo"}, {"2.2", "7"})
        self.assertEqual(conv54["elegibilidad"]["minimos"], [{"criterio": "1", "minimo": 24}])
        self.assertEqual(conv56["justificacion"]["excepciones"], {"7": [150, 300]})

    def test_every_family_has_guidance(self) -> None:
        guide = json.loads((RUBRICS / "_guia_comun.json").read_text(encoding="utf-8"))
        self.assertEqual(guide["schema"], "morfeo.guia-juez-sgr/v1")
        for rid in ("conv54", "conv56"):
            for criterion in _rubric(rid)["criterios"]:
                for sub in criterion["subcriterios"]:
                    family = guide["familias"].get(sub["familia"])
                    self.assertIsNotNone(family, f"{rid} {sub['id']} {sub['familia']}")
        for name, family in guide["familias"].items():
            for key in ("preguntas_par", "senales_alerta", "evidencia_minima", "fuentes"):
                self.assertTrue(family[key], f"{name}.{key}")
            for source in family["fuentes"]:
                self.assertIn(source, guide["fuentes_catalogo"], name)


class PrepararTest(unittest.TestCase):
    def test_refuses_a_base_run_unless_forced(self) -> None:
        run = _make_run("base", tdr="CONVOCATORIA 54 CONVOCATORIA ESPECIAL")
        result = _cli("preparar", run)
        self.assertEqual(result.returncode, 2)
        self.assertIn("sgr", (result.stdout + result.stderr).lower())
        self.assertFalse((run / "artefactos" / "juez" / "rubrica.json").exists())
        self.assertEqual(_cli("preparar", run, "--forzar").returncode, 0)

    def test_detects_the_call_from_the_tdr_text(self) -> None:
        for text, rid in (("TÉRMINOS DE REFERENCIA (TdR) CONVOCATORIA 54", "conv54"),
                          ("en el marco del Decreto Legislativo 1414 de 2026", "conv56")):
            run = _make_run(tdr=text)
            result = _cli("preparar", run, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["rubrica"], rid)
            copied = json.loads((run / "artefactos" / "juez" / "rubrica.json").read_text(encoding="utf-8"))
            self.assertEqual(copied["id"], rid)

    def test_flag_wins_over_detection_and_unknown_call_lists_ids(self) -> None:
        run = _make_run(tdr="CONVOCATORIA 54")
        result = _cli("preparar", run, "--rubrica", "conv56", "--json")
        self.assertEqual(json.loads(result.stdout)["rubrica"], "conv56")
        # The rubric already copied into the run wins over detection on the next call.
        self.assertEqual(json.loads(_cli("preparar", run, "--json").stdout)["rubrica"], "conv56")

        unknown = _make_run(tdr="Convocatoria sin número reconocible")
        failed = _cli("preparar", unknown)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("conv54", failed.stderr)
        self.assertIn("conv56", failed.stderr)

    def test_writes_verifications_and_announces_the_next_round(self) -> None:
        run = _make_run(tdr="CONVOCATORIA 54")
        _prepare_for_scoring(run, "conv54", [_round(_rubric("conv54"), 1)], None)
        result = _cli("preparar", run, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["ronda_siguiente"], 2)
        self.assertIn("artefactos/juez/evaluacion_ronda_2.json", out["archivos"])
        checks = json.loads((run / "artefactos" / "juez" / "verificaciones.json").read_text(encoding="utf-8"))
        coverage = {c["subcriterio"]: c for c in checks["cobertura"]}
        methodology = {e["clave"]: e for e in coverage["1.1"]["evidencia"]}
        self.assertTrue(methodology["10_metodologia"]["existe"])
        self.assertGreater(methodology["10_metodologia"]["palabras"], 5)
        self.assertFalse(methodology["03_descripcion_problema"]["existe"])
        self.assertIn("fig:a", {d["label"] for d in checks["latex"]["labels_duplicados"]})
        self.assertEqual(len(checks["latex"]["captions_vacios"]), 1)
        self.assertEqual(checks["trl"]["entrada"], [4])
        self.assertEqual(checks["trl"]["salida"], [6])
        self.assertIn("hallazgos", checks["check_run"])
        text = _cli("preparar", run)
        self.assertIn("evaluacion_ronda_2.json", text.stdout)


class ConteoRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.juez = _load_module()
        self.c54, self.c56 = _rubric("conv54"), _rubric("conv56")

    def _score(self, rubric: dict, sid: str, datos: dict) -> dict:
        return self.juez.compute_conteo(_sub(rubric, sid), datos)

    def test_departments(self) -> None:
        deps = [{"nombre": f"D{i}", "fuente": "SIGP"} for i in range(3)]
        self.assertEqual(self._score(self.c54, "2.2", _datos(departamentos_ejecucion=deps))["puntaje"], 6)
        self.assertEqual(self._score(self.c54, "2.2", _datos(departamentos_ejecucion=deps[:2]))["puntaje"], 3)
        self.assertEqual(self._score(self.c54, "2.2", _datos(departamentos_ejecucion=deps[:1]))["puntaje"], 0)
        self.assertEqual(self._score(self.c56, "2.2", _datos(departamentos_ejecucion=deps[:2]))["puntaje"], 3)
        self.assertEqual(self._score(self.c56, "2.2", _datos(departamentos_ejecucion=deps[:1]))["puntaje"], 0)

    def test_trajectory_edge_cases(self) -> None:
        cases = {(4, 1): 6, (4, 0): 3, (5, 0): 3, (3, 0): 3, (3, 1): 4, (2, 0): 1, (2, 2): 3, (1, 1): 0,
                 (0, 0): 0, (3, 3): 6, (6, 4): 6}
        for (extra, sgr), expected in cases.items():
            datos = _datos(trayectoria={"proyectos_adicionales": extra, "proyectos_sgr_o_elegibles": sgr,
                                        "fuente": "x"})
            self.assertEqual(self._score(self.c54, "3.1", datos)["puntaje"], expected, (extra, sgr))

    def test_alliance_categories_count_the_proponent(self) -> None:
        basic = [_ally("SNCTI"), _ally("entidad_territorial"), _ally("usuario_adoptante"),
                 _ally("usuario_adoptante"), _ally("otro")]          # 5 allies + IES proponent = 6
        self.assertEqual(self._score(self.c54, "3.2", _datos(aliados=basic[:4]))["puntaje"], 0)
        self.assertEqual(self._score(self.c54, "3.2", _datos(aliados=basic))["puntaje"], 3)
        media = basic + [_ally("entidad_territorial"), _ally("SNCTI")]  # 8 members
        self.assertEqual(self._score(self.c54, "3.2", _datos(aliados=media))["puntaje"], 4)
        self.assertEqual(self._score(self.c54, "3.2", _datos(aliados=media + [_ally("otro")]))["puntaje"], 4)
        advanced = media + [_ally("otro"), _ally("internacional")]  # 10 members
        self.assertEqual(self._score(self.c54, "3.2", _datos(aliados=advanced))["puntaje"], 5)
        one_territorial = [a for a in advanced if a["tipo"] != "entidad_territorial"][:-1] + [
            _ally("entidad_territorial"), _ally("usuario_adoptante"), _ally("otro")]
        self.assertEqual(len(one_territorial), 9)
        self.assertEqual(self._score(self.c54, "3.2", _datos(aliados=one_territorial))["puntaje"], 3)

    def test_rooting_international_cofinancing_and_cash(self) -> None:
        proponent = {"nombre": "P", "tipo": "IES", "domicilio_en_region": True, "tipo_diverso": False, "fuente": "x"}
        self.assertEqual(self._score(self.c54, "3.3", _datos(proponente=proponent))["puntaje"], 2)
        self.assertEqual(self._score(self.c54, "3.3", _datos())["puntaje"], 3)
        self.assertEqual(self._score(self.c54, "3.4", _datos())["puntaje"], 1)
        self.assertEqual(self._score(self.c54, "3.4", _datos(aliado_internacional_con_aporte=False))["puntaje"], 0)
        for amount, expected in ((110_000_000, 3), (100_000_000, 1), (50_000_000, 1), (49_000_000, 0)):
            datos = _datos(aliados=[_ally("SNCTI", amount)])
            self.assertEqual(self._score(self.c54, "4.3", datos)["puntaje"], expected, amount)
        for cash, expected in ((10_000_000, 2), (9_000_000, 0)):
            datos = _datos(aliados=[_ally("SNCTI", 50_000_000, cash)])
            self.assertEqual(self._score(self.c56, "7", datos)["puntaje"], expected, cash)

    def test_null_data_scores_zero_and_marks_incomplete(self) -> None:
        result = self._score(self.c54, "3.1", _datos(trayectoria={"proyectos_adicionales": None,
                                                                 "proyectos_sgr_o_elegibles": None, "fuente": None}))
        self.assertEqual((result["puntaje"], result["incompleto"]), (0, True))
        self.assertTrue(self._score(self.c54, "2.2", _datos(departamentos_ejecucion=None))["incompleto"])
        self.assertFalse(self._score(self.c54, "2.2", _datos())["incompleto"])


class CalificarTest(unittest.TestCase):
    def test_valid_round_sums_and_is_eligible(self) -> None:
        run = _make_run()
        _prepare_for_scoring(run, "conv54", [_round(_rubric("conv54"))], _datos())
        result = _cli("calificar", run)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        evaluation = _evaluation(run)
        self.assertEqual(evaluation["schema"], "morfeo.evaluacion-sgr-consolidada/v1")
        self.assertEqual(evaluation["errores_validacion"], [])
        self.assertEqual(evaluation["subtotales"], {"1": 40, "2": 30, "3": 15, "4": 15})
        self.assertEqual(evaluation["total"], 100)
        self.assertTrue(evaluation["elegible"])
        self.assertFalse(evaluation["incompleto"])
        scores = {c["id"]: c["puntaje"] for c in evaluation["criterios"]}
        self.assertEqual(scores["3.1"], 6)
        self.assertEqual(scores["1.2"], 10)
        markdown = (run / "artefactos" / "juez" / "evaluacion.md").read_text(encoding="utf-8")
        self.assertIn("| Criterio | Máx. | Puntaje |", markdown)
        self.assertIn("100/100", markdown)

    def test_rejects_a_level_outside_the_scale_and_a_short_justification(self) -> None:
        rubric = _rubric("conv54")
        bad = _round(rubric, overrides={"1.1": {"puntaje": 7}, "2.1": {"justificacion": "corta"}})
        run = _make_run()
        _prepare_for_scoring(run, "conv54", [bad], _datos())
        result = _cli("calificar", run)
        self.assertEqual(result.returncode, 1)
        errors = _evaluation(run)["errores_validacion"]
        self.assertTrue(any("1.1" in e and "7" in e for e in errors), errors)
        self.assertTrue(any("2.1" in e and "caracteres" in e for e in errors), errors)
        self.assertIn("1.1", result.stdout + result.stderr)

    def test_rejects_bad_components_missing_or_repeated_items_agents_and_short_concept(self) -> None:
        rubric = _rubric("conv54")
        bad = _round(rubric, overrides={"1.2": {"componentes": {"rigor": 4, "novedad": 3, "replicabilidad": 3,
                                                                "equipo": 1}}})
        bad["criterios"] = [c for c in bad["criterios"] if c["id"] != "4.4"] + [copy.deepcopy(bad["criterios"][0])]
        bad["acciones"][0]["agente"] = "revisor"
        bad["concepto"] = "muy corto"
        run = _make_run()
        _prepare_for_scoring(run, "conv54", [bad], _datos())
        self.assertEqual(_cli("calificar", run).returncode, 1)
        errors = " ".join(_evaluation(run)["errores_validacion"])
        for fragment in ("rigor", "Falta el subcriterio 4.4", "1.1 aparece 2 veces", "revisor", "concepto final"):
            self.assertIn(fragment, errors)

    def test_conv56_criterion_7_uses_its_own_justification_range(self) -> None:
        rubric = _rubric("conv56")
        run = _make_run()
        _prepare_for_scoring(run, "conv56", [_round(rubric, overrides={"7": {"justificacion": "J" * 200}})],
                             _datos(trl={"tipologia": None, "entrada": 6, "salida": 9, "fuente": "x"}))
        self.assertEqual(_cli("calificar", run).returncode, 0)
        long = _make_run()
        _prepare_for_scoring(long, "conv56", [_round(rubric, overrides={"7": {"justificacion": "J" * 1200}})],
                             _datos())
        self.assertEqual(_cli("calificar", long).returncode, 1)

    def test_null_data_flags_incomplete_with_an_alert(self) -> None:
        run = _make_run()
        _prepare_for_scoring(run, "conv54", [_round(_rubric("conv54"))], _datos(departamentos_ejecucion=None))
        self.assertEqual(_cli("calificar", run).returncode, 0)
        evaluation = _evaluation(run)
        self.assertTrue(evaluation["incompleto"])
        entry = next(c for c in evaluation["criterios"] if c["id"] == "2.2")
        self.assertEqual((entry["puntaje"], entry["incompleto"]), (0, True))
        self.assertIn("dato-faltante", _alert_codes(evaluation))

    def test_cross_checks(self) -> None:
        rubric = _rubric("conv54")
        cases = {
            "tope-solicitud": _datos(monto_sgr={"valor": 18_000_000_000, "fuente": "Anexo 3"}),
            "totales-distintos": _datos(totales_declarados=[
                {"documento": "Anexo 2", "concepto": "sgr", "valor": 1_000_000_000},
                {"documento": "SIGP", "concepto": "sgr", "valor": 1_000_000_001},
                {"documento": "Anexo 3", "concepto": "contrapartida", "valor": 111_000_000}]),
            "contrapartida-no-cuadra": _datos(totales_declarados=[
                {"documento": "Anexo 3", "concepto": "contrapartida", "valor": 150_000_000}]),
            "transferencia-baja": _datos(transferencia_valor=5_000_000),
        }
        for code, datos in cases.items():
            run = _make_run()
            _prepare_for_scoring(run, "conv54", [_round(rubric)], datos)
            _cli("calificar", run)
            evaluation = _evaluation(run)
            alert = next((a for a in evaluation["verificaciones"] if a["codigo"] == code), None)
            self.assertIsNotNone(alert, f"{code}: {evaluation['verificaciones']}")
            self.assertEqual(alert["severidad"], "advertencia" if code == "transferencia-baja" else "error")
            if code == "tope-solicitud":
                self.assertTrue(alert["inhabilitante"])
                self.assertFalse(evaluation["elegible"])
        clean = _make_run()
        _prepare_for_scoring(clean, "conv54", [_round(rubric)], _datos())
        _cli("calificar", clean)
        self.assertFalse({"tope-solicitud", "totales-distintos", "contrapartida-no-cuadra",
                          "transferencia-baja"} & _alert_codes(_evaluation(clean)))

    def test_conv56_trl_level_must_match_the_declared_exit(self) -> None:
        run = _make_run()
        _prepare_for_scoring(run, "conv56", [_round(_rubric("conv56"))],
                             _datos(trl={"tipologia": None, "entrada": 6, "salida": 7, "fuente": "x"}))
        _cli("calificar", run)
        alert = next(a for a in _evaluation(run)["verificaciones"] if a["codigo"] == "trl-inconsistente")
        self.assertEqual(alert["severidad"], "advertencia")
        self.assertEqual(alert["criterios"], ["3.1"])

    def test_conv54_criterion_1_minimum_blocks_eligibility(self) -> None:
        rubric = _rubric("conv54")
        low = _round(rubric, overrides={
            "1.1": {"puntaje": 4}, "1.5": {"puntaje": 2},
            "1.2": {"componentes": {"rigor": 2, "novedad": 2, "replicabilidad": 2, "equipo": 0}},
            "1.3": {"componentes": {"partida": 2, "ruta": 2, "verificacion": 2}},
            "1.4": {"componentes": {"correspondencia": 2, "razonabilidad": 2, "cifras": 0}}})
        run = _make_run()
        _prepare_for_scoring(run, "conv54", [low], _datos())
        self.assertEqual(_cli("calificar", run).returncode, 0)
        evaluation = _evaluation(run)
        self.assertEqual(evaluation["subtotales"]["1"], 22)
        self.assertGreaterEqual(evaluation["total"], 75)
        self.assertFalse(evaluation["elegible"])
        self.assertTrue(any("24" in reason for reason in evaluation["motivos_no_elegible"]))

    def test_history_accumulates_across_rounds(self) -> None:
        rubric = _rubric("conv54")
        run = _make_run()
        first = _round(rubric, 1, overrides={"1.1": {"puntaje": 6}})
        _prepare_for_scoring(run, "conv54", [first], _datos())
        self.assertEqual(_cli("calificar", run).returncode, 0)
        second = _round(rubric, 2)
        second["fecha"] = "2026-11-20"
        _prepare_for_scoring(run, "conv54", [second], None)
        self.assertEqual(_cli("calificar", run).returncode, 0)
        evaluation = _evaluation(run)
        self.assertEqual(evaluation["ronda"], 2)
        self.assertEqual([(h["ronda"], h["total"]) for h in evaluation["historial"]], [(1, 96), (2, 100)])


class EstadoTest(unittest.TestCase):
    def test_reports_missing_and_existing_evaluation(self) -> None:
        run = _make_run()
        empty = _cli("estado", run)
        self.assertEqual(empty.returncode, 0)
        self.assertIn("no hay evaluación", empty.stdout)
        self.assertFalse(json.loads(_cli("estado", run, "--json").stdout)["existe"])

        _prepare_for_scoring(run, "conv54", [_round(_rubric("conv54"))],
                             _datos(monto_sgr={"valor": 18_000_000_000, "fuente": "Anexo 3"}))
        _cli("calificar", run)
        total = _evaluation(run)["total"]
        text = _cli("estado", run).stdout
        self.assertIn("conv54", text)
        self.assertIn(f"{total}/100", text)
        self.assertIn("no elegible", text)
        data = json.loads(_cli("estado", run, "--json").stdout)
        self.assertEqual((data["existe"], data["total"], data["elegible"]), (True, total, False))
        self.assertGreaterEqual(data["alertas_error"], 1)


if __name__ == "__main__":
    unittest.main()
