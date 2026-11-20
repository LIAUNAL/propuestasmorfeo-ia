"""scripts/requisitos_sgr.py: enabling requirements, institutional endorsement, figure coherence, licences and
annexes of an SGR project (odd/tasks/sgr-requisitos-anexos.md, S2 to S5).

The call rubric carries the enabling requirements copied verbatim from the TdR
(Conv 54 numeral 11, Conv 56 numeral 10); `scripts/rubricas_sgr/_aval_institucional.json`
holds the UNAL VRI endorsement procedure. `artefactos/sgr/requisitos.json` is
seeded by `init`, validated by `check` against the rubric, the alliance and
the budget summary, rendered by `render` into sections 38 and 39, summarised
for the judge by `datos` and edited by the dashboard through `vista` and
`actualizar_item`. A base run is never touched (S1).
"""

from __future__ import annotations

import copy
import datetime
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "requisitos_sgr.py"
RUBRICS = REPO / "scripts" / "rubricas_sgr"
AVAL = RUBRICS / "_aval_institucional.json"
HEADER = "% GENERADO por scripts/requisitos_sgr.py"
STEMS = ("38_licencias_permisos", "39_anexos")
CONDITIONS = {None, "etica", "internacional", "sector_productivo", "sociedad_civil", "infraestructura", "inmuebles",
              "cofinanciacion", "desastre", "otro"}
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "src"))

from test_alianza_territorio_sgr import _alliance, _entity  # noqa: E402
from test_presupuesto_sgr import _budget, _item  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rubric(rid: str) -> dict:
    return json.loads((RUBRICS / f"{rid}.json").read_text(encoding="utf-8"))


def _write(run: Path, name: str, data) -> Path:
    path = run / "artefactos" / "sgr" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _make_run(tmp: Path, flujo: str | None = "sgr", rubric: str | dict | None = "conv54", alliance=True,
              budget=True) -> Path:
    if flujo:
        (tmp / ".morfeo").mkdir(exist_ok=True)
        (tmp / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = tmp / "run"
    (run / "redaccion" / "sections").mkdir(parents=True, exist_ok=True)
    (run / "artefactos").mkdir(parents=True, exist_ok=True)
    if rubric is not None:
        juez = run / "artefactos" / "juez"
        juez.mkdir(parents=True, exist_ok=True)
        data = rubric if isinstance(rubric, dict) else _rubric(rubric)
        (juez / "rubrica.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if alliance:
        _write(run, "alianza.json", alliance if isinstance(alliance, dict) else _alliance())
    if budget:
        _write(run, "presupuesto.json", budget if isinstance(budget, dict) else _budget())
    return run


def _cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def _codes(found: list[dict], severity: str | None = None) -> list[str]:
    return [f["code"] for f in found if severity is None or f["severity"] == severity]


class RubricData(unittest.TestCase):
    """S3: the enabling requirements and the endorsement procedure, verbatim, in the kit data."""

    def test_conv54_lists_11_1_to_11_28_with_the_marked_conditions(self) -> None:
        reqs = _rubric("conv54")["requisitos"]
        self.assertEqual([r["id"] for r in reqs], [f"11.{n}" for n in range(1, 29)])
        conditions = {r["id"]: r["condicion"] for r in reqs if r["condicion"]}
        self.assertEqual(conditions, {"11.10": "etica", "11.11": "internacional", "11.12": "sector_productivo",
                                      "11.13": "sociedad_civil", "11.19": "inmuebles"})
        by_id = {r["id"]: r for r in reqs}
        self.assertEqual(by_id["11.14"]["nombre"], "Proyecto de inversión formulado en MGA WEB Tipología D – PIIP")
        self.assertEqual(by_id["11.4"]["documento"], "Anexo 1")
        self.assertTrue(by_id["11.10"]["nombre"].endswith("(cuando aplique)"))
        self.assertIn("Sistema Integrado de Gestión de Proyectos - SIGP", by_id["11.1"]["texto"])

    def test_conv56_lists_10_1_to_10_21_with_the_marked_conditions(self) -> None:
        reqs = _rubric("conv56")["requisitos"]
        self.assertEqual([r["id"] for r in reqs], [f"10.{n}" for n in range(1, 22)])
        conditions = {r["id"]: r["condicion"] for r in reqs if r["condicion"]}
        self.assertEqual(conditions, {"10.10": "etica", "10.11": "internacional", "10.12": "sector_productivo",
                                      "10.13": "sociedad_civil", "10.17": "infraestructura"})
        by_id = {r["id"]: r for r in reqs}
        self.assertEqual(by_id["10.11"]["nombre"], "Carta entidad internacional (Si Aplica)")

    def test_every_requirement_has_the_contract_keys(self) -> None:
        for rid in ("conv54", "conv56"):
            for req in _rubric(rid)["requisitos"]:
                with self.subTest(rubric=rid, req=req["id"]):
                    self.assertEqual(set(req), {"id", "nombre", "texto", "condicion", "documento", "numeral_fuente"})
                    self.assertIn(req["condicion"], CONDITIONS)
                    for key in ("nombre", "texto", "documento", "numeral_fuente"):
                        self.assertTrue(isinstance(req[key], str) and req[key].strip(), key)
                    self.assertNotRegex(req["texto"], r"\w- \w", "hyphenation left from pdftotext")
                    self.assertIn(req["id"], req["numeral_fuente"])

    def test_conv54_figure_coherence_component_points_to_the_cifras_check(self) -> None:
        sub = next(s for c in _rubric("conv54")["criterios"] for s in c["subcriterios"] if s["id"] == "1.4")
        part = next(p for p in sub["componentes"] if p["id"] == "cifras")
        self.assertIn("requisitos_sgr.py", part["verificacion"])
        self.assertIn("cifras", part["verificacion"])

    def test_kit_json_round_trips_byte_identically(self) -> None:
        for path in (RUBRICS / "conv54.json", RUBRICS / "conv56.json", AVAL,
                     REPO / "scripts" / "sgr" / "lexico_sgr.json"):
            with self.subTest(path=path.name):
                raw = path.read_text(encoding="utf-8")
                self.assertEqual(json.dumps(json.loads(raw), ensure_ascii=False, indent=2) + "\n", raw)

    def test_endorsement_procedure_holds_the_vri_documents_and_milestones(self) -> None:
        data = json.loads(AVAL.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "morfeo.aval-institucional/v1")
        unal = data["instituciones"][0]
        self.assertEqual((unal["id"], unal["convocatorias"]), ("unal", ["conv54", "conv55"]))
        self.assertTrue(re.search(unal["patron_nombre"], "Universidad Nacional de Colombia", re.I))
        self.assertEqual([d["indice"] for d in unal["documentos"]], list(range(1, 8)))
        texts = [d["texto"] for d in unal["documentos"]]
        self.assertTrue(texts[0].startswith("Cartas de certificación de la contrapartida en especie"))
        self.assertIn("Certificados de no financiación con otras fuentes de recursos.", texts)
        self.assertTrue(any("(Si aplica)" in t for t in texts))
        for hito in unal["hitos"]:
            self.assertEqual(set(hito), {"actividad", "responsable", "fecha", "fecha_texto"})
            datetime.date.fromisoformat(hito["fecha"])
        dates = {h["actividad"]: h["fecha"] for h in unal["hitos"]}
        self.assertEqual(dates["Presentación de propuestas a través Sistema de Información Hermes"], "2026-11-09")
        self.assertEqual(max(dates.values()), "2026-11-13")

    def test_the_judge_still_accepts_both_rubrics(self) -> None:
        juez = _load("juez_for_requisitos", REPO / "scripts" / "juez_sgr.py")
        for rid in ("conv54", "conv56"):
            self.assertEqual(juez.validate_rubric(_rubric(rid)), [], rid)
        self.assertNotIn("_aval_institucional", juez.available_rubrics())


class Init(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.mod = _load("requisitos_sgr_init", SCRIPT)

    def test_init_seeds_every_rubric_requirement_as_pending(self) -> None:
        run = _make_run(self.tmp)
        result = _cli("init", run)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((run / "artefactos" / "sgr" / "requisitos.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "morfeo.requisitos-sgr/v1")
        self.assertEqual(data["convocatoria"], "conv54")
        self.assertEqual([i["id"] for i in data["items"]], [f"11.{n}" for n in range(1, 29)])
        self.assertEqual(data["items"][0], {"id": "11.1", "estado": "pendiente", "responsable": None,
                                            "archivo": None, "fecha": None, "nota": None, "justificacion": None})
        self.assertEqual(data["cifras"], {"sigp": None, "anexo1": None, "anexo3": None, "mga": None})
        self.assertIsNone(data["licencias"])
        self.assertEqual(data["aval_institucional"]["institucion"], "unal")
        self.assertEqual([d["indice"] for d in data["aval_institucional"]["documentos"]], list(range(1, 8)))
        self.assertTrue(all(d["estado"] == "pendiente" and d["archivo"] is None
                            for d in data["aval_institucional"]["documentos"]))

    def test_init_is_idempotent_and_never_overwrites(self) -> None:
        run = _make_run(self.tmp)
        self.mod.init(run)
        path = run / "artefactos" / "sgr" / "requisitos.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["items"][0]["estado"] = "en_tramite"
        data["items"] = [i for i in data["items"] if i["id"] != "11.5"]
        data["licencias"] = {"introduccion": "Texto.", "items": []}
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        _, added = self.mod.init(run)
        self.assertEqual(added, ["11.5"])
        again = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(again["items"][0]["estado"], "en_tramite")
        self.assertEqual(again["licencias"], {"introduccion": "Texto.", "items": []})
        self.assertIn("11.5", [i["id"] for i in again["items"]])
        before = path.read_bytes()
        self.assertEqual(self.mod.init(run)[1], [])
        self.assertEqual(path.read_bytes(), before)

    def test_init_refuses_a_base_run(self) -> None:
        run = _make_run(self.tmp, flujo="base")
        self.assertEqual(_cli("init", run).returncode, 2)
        self.assertFalse((run / "artefactos" / "sgr" / "requisitos.json").exists())

    def test_endorsement_is_null_for_another_proponent(self) -> None:
        alliance = _alliance()
        alliance["entidades"][0]["nombre"] = "Universidad de Caldas"
        run = _make_run(self.tmp, alliance=alliance)
        self.mod.init(run)
        data = json.loads((run / "artefactos" / "sgr" / "requisitos.json").read_text(encoding="utf-8"))
        self.assertIsNone(data["aval_institucional"])


class Check(unittest.TestCase):
    """S4: every rule of requisitos.json, one test per finding code."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.mod = _load("requisitos_sgr_check", SCRIPT)
        self.run = _make_run(self.tmp)
        self.mod.init(self.run)
        self.path = self.run / "artefactos" / "sgr" / "requisitos.json"
        self.presupuesto = _load("presupuesto_for_requisitos", REPO / "scripts" / "presupuesto_sgr.py")

    def data(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def item(self, data: dict, iid: str) -> dict:
        return next(i for i in data["items"] if i["id"] == iid)

    def found(self, final: bool = False) -> list[dict]:
        return self.mod.check_findings(self.run, final=final)

    def clean(self) -> dict:
        """Licences, declared figures equal to the budget and the alliance, and every endorsement entry."""
        data = self.data()
        summary = self.presupuesto.resumen(self.run)
        counterpart = summary["total_especie"] + summary["total_efectivo"]
        totals = {"total_sgr": summary["total_sgr"], "total_contrapartida": counterpart, "total": summary["total"]}
        data["cifras"] = {"sigp": dict(totals), "anexo3": dict(totals),
                          "mga": {"total_sgr": summary["total_sgr"], "total": summary["total"]},
                          "anexo1": {"por_entidad": {e["id"]: {"especie": e["aporte_especie"],
                                                               "efectivo": e["aporte_efectivo"]}
                                                     for e in _alliance()["entidades"]}}}
        data["licencias"] = {
            "introduccion": "La entidad proponente y las demás entidades aliadas se comprometen a cumplir la norma.",
            "items": [
                {"licencia": "Consentimiento informado", "norma": "Resolución 8430 de 1993", "aplica": True,
                 "justificacion": "El proyecto trabaja con participantes humanos.", "responsable": "E1",
                 "momento": "previo"},
                {"licencia": "Licencia ambiental", "norma": "Decreto 1076 de 2015", "aplica": False,
                 "justificacion": "Por la naturaleza del objetivo general, el proyecto no interviene el ambiente.",
                 "responsable": None, "momento": None},
            ]}
        self.save(data)
        return data

    def test_clean_data_has_no_errors_or_warnings(self) -> None:
        self.clean()
        self.assertEqual([f for f in self.found() if f["severity"] != "info"], [])

    def test_missing_item_is_a_warning(self) -> None:
        data = self.clean()
        data["items"] = [i for i in data["items"] if i["id"] != "11.7"]
        self.save(data)
        hit = next(f for f in self.found() if f["code"] == "requisitos-item-faltante")
        self.assertEqual((hit["severity"], hit["node"]), ("warning", "11.7"))

    def test_unknown_id_is_an_error(self) -> None:
        data = self.clean()
        data["items"].append({**self.item(data, "11.1"), "id": "11.99"})
        self.save(data)
        hit = next(f for f in self.found() if f["code"] == "requisitos-id-desconocido")
        self.assertEqual((hit["severity"], hit["node"]), ("error", "11.99"))

    def test_invalid_enum_or_date_is_an_error(self) -> None:
        data = self.clean()
        self.item(data, "11.1")["estado"] = "hecho"
        self.item(data, "11.2")["fecha"] = "20-11-2026"
        data["licencias"]["items"][0]["momento"] = "despues"
        self.save(data)
        nodes = {f["node"] for f in self.found() if f["code"] == "requisitos-valor-invalido"}
        self.assertLessEqual({"11.1", "11.2", "licencias.items[1]"}, nodes)

    def test_not_applicable_needs_a_justification(self) -> None:
        data = self.clean()
        self.item(data, "11.10")["estado"] = "no_aplica"
        self.save(data)
        self.assertIn("requisitos-justificacion-faltante", _codes(self.found(), "error"))
        self.item(data, "11.10")["justificacion"] = "El proyecto no trabaja con datos sensibles."
        self.save(data)
        self.assertNotIn("requisitos-justificacion-faltante", _codes(self.found()))

    def test_not_applicable_only_for_conditional_requirements(self) -> None:
        data = self.clean()
        self.item(data, "11.5").update(estado="no_aplica", justificacion="No se adjunta.")
        self.save(data)
        hit = next(f for f in self.found() if f["code"] == "requisitos-no-aplica-invalido")
        self.assertEqual((hit["severity"], hit["node"]), ("error", "11.5"))

    def test_a_derived_condition_that_applies_cannot_be_not_applicable(self) -> None:
        cases = {
            "internacional": ("11.11", lambda a, b: a["entidades"].append(
                _entity("E7", "University of Example", "internacional", None, aporte_especie=5_000_000)), None),
            "sector_productivo": ("11.12", lambda a, b: a["entidades"].append(
                _entity("E7", "Empresa de Software S.A.S.", "sector_productivo", "Caldas")), None),
            "infraestructura": ("10.17", lambda a, b: b["items"].append(
                _item("P9", "infraestructura", "edificios", "E1", "sgr", 10_000_000, ["2.1.2"])), "conv56"),
        }
        for condition, (iid, change, rubric) in cases.items():
            with self.subTest(condition=condition), tempfile.TemporaryDirectory() as tmp:
                alliance, budget = _alliance(), _budget()
                run = _make_run(Path(tmp), rubric=rubric or "conv54")
                self.mod.init(run)
                path = run / "artefactos" / "sgr" / "requisitos.json"
                data = json.loads(path.read_text(encoding="utf-8"))
                self.item(data, iid).update(estado="no_aplica", justificacion="No aplica.")
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                self.assertNotIn("requisitos-condicion-aplica", _codes(self.mod.check_findings(run)))
                self.assertFalse(self.mod.condiciones_derivadas(run)[condition])
                change(alliance, budget)
                _write(run, "alianza.json", alliance)
                _write(run, "presupuesto.json", budget)
                self.assertTrue(self.mod.condiciones_derivadas(run)[condition])
                hit = next(f for f in self.mod.check_findings(run) if f["code"] == "requisitos-condicion-aplica")
                self.assertEqual((hit["severity"], hit["node"]), ("error", iid))

    def test_cofinancing_applies_when_an_ally_declares_cash(self) -> None:
        rubric = _rubric("conv54")
        next(r for r in rubric["requisitos"] if r["id"] == "11.23")["condicion"] = "cofinanciacion"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        run = _make_run(Path(tmp.name), rubric=rubric)
        self.mod.init(run)
        self.assertFalse(self.mod.condiciones_derivadas(run)["cofinanciacion"])
        alliance = _alliance()
        alliance["entidades"][0]["aporte_efectivo"] = 50_000_000
        _write(run, "alianza.json", alliance)
        self.assertFalse(self.mod.condiciones_derivadas(run)["cofinanciacion"], "the proponent does not count")
        alliance["entidades"][1]["aporte_efectivo"] = 10_000_000
        _write(run, "alianza.json", alliance)
        self.assertTrue(self.mod.condiciones_derivadas(run)["cofinanciacion"])
        self.assertIsNone(self.mod.condiciones_derivadas(run)["etica"])

    def test_ready_item_with_a_missing_file_is_an_error_and_without_file_a_warning(self) -> None:
        data = self.clean()
        self.item(data, "11.4").update(estado="listo", archivo="insumos/requisitos/anexo1.pdf")
        self.item(data, "11.5").update(estado="listo")
        self.save(data)
        found = self.found()
        hit = next(f for f in found if f["code"] == "requisitos-archivo-inexistente")
        self.assertEqual((hit["severity"], hit["node"]), ("error", "11.4"))
        hit = next(f for f in found if f["code"] == "requisitos-sin-archivo")
        self.assertEqual((hit["severity"], hit["node"]), ("warning", "11.5"))
        target = self.run / "insumos" / "requisitos" / "anexo1.pdf"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"%PDF")
        self.assertNotIn("requisitos-archivo-inexistente", _codes(self.found()))

    def test_file_outside_the_run_is_invalid(self) -> None:
        data = self.clean()
        self.item(data, "11.4").update(estado="listo", archivo="../fuera.pdf")
        self.save(data)
        self.assertIn("11.4", {f["node"] for f in self.found() if f["code"] == "requisitos-valor-invalido"})

    def test_responsible_entities_exist_in_the_alliance(self) -> None:
        data = self.clean()
        self.item(data, "11.4")["responsable"] = "E99"
        data["licencias"]["items"][0]["responsable"] = "E98"
        self.save(data)
        nodes = {f["node"] for f in self.found() if f["code"] == "requisitos-entidad-desconocida"}
        self.assertEqual(nodes, {"11.4", "licencias.items[1]"})

    def test_declared_figures_must_match_the_budget_and_the_alliance(self) -> None:
        data = self.clean()
        data["cifras"]["sigp"]["total_sgr"] += 1
        self.save(data)
        self.assertNotIn("requisitos-cifras-distintas", _codes(self.found()), "one peso is tolerated")
        data["cifras"]["sigp"]["total_sgr"] += 1
        data["cifras"]["anexo1"]["por_entidad"]["E2"]["especie"] = 25_000_000
        self.save(data)
        nodes = {f["node"] for f in self.found() if f["code"] == "requisitos-cifras-distintas"}
        self.assertEqual(nodes, {"cifras.sigp.total_sgr", "cifras.anexo1.E2.especie"})

    def test_undeclared_figures_are_info(self) -> None:
        data = self.clean()
        data["cifras"]["mga"] = None
        self.save(data)
        hit = next(f for f in self.found() if f["code"] == "requisitos-cifras-sin-declarar")
        self.assertEqual((hit["severity"], hit["node"]), ("info", "cifras.mga"))

    def test_applicable_licence_needs_norm_responsible_and_moment(self) -> None:
        data = self.clean()
        data["licencias"]["items"][0].update(norma="", responsable=None)
        self.save(data)
        hit = next(f for f in self.found() if f["code"] == "requisitos-licencia-incompleta")
        self.assertEqual((hit["severity"], hit["node"]), ("error", "licencias.items[1]"))
        self.assertIn("norma", hit["message"])
        self.assertIn("responsable", hit["message"])

    def test_not_applicable_licence_needs_a_justification(self) -> None:
        data = self.clean()
        data["licencias"]["items"][1]["justificacion"] = " "
        self.save(data)
        hit = next(f for f in self.found() if f["code"] == "requisitos-licencia-sin-justificacion")
        self.assertEqual((hit["severity"], hit["node"]), ("error", "licencias.items[2]"))

    def test_missing_licences_block_is_a_warning(self) -> None:
        data = self.clean()
        data["licencias"] = None
        self.save(data)
        self.assertIn("requisitos-licencias-faltantes", _codes(self.found(), "warning"))

    def test_endorsement_documents_need_an_entry(self) -> None:
        data = self.clean()
        data["aval_institucional"]["documentos"] = data["aval_institucional"]["documentos"][:5]
        self.save(data)
        nodes = [f["node"] for f in self.found() if f["code"] == "requisitos-aval-documento-faltante"]
        self.assertEqual(nodes, ["aval_institucional.documentos[6]", "aval_institucional.documentos[7]"])
        self.assertEqual({f["severity"] for f in self.found() if f["code"] == "requisitos-aval-documento-faltante"},
                         {"warning"})

    def test_endorsement_is_not_checked_for_a_call_outside_the_procedure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _make_run(Path(tmp), rubric="conv56")
            self.mod.init(run)
            path = run / "artefactos" / "sgr" / "requisitos.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsNone(data["aval_institucional"])
            self.assertNotIn("requisitos-aval-documento-faltante", _codes(self.mod.check_findings(run)))

    def test_final_turns_applicable_pending_items_into_errors(self) -> None:
        data = self.clean()
        for item in data["items"]:
            item.update(estado="listo", archivo="insumos/requisitos/soporte.pdf")
        self.item(data, "11.10").update(estado="no_aplica", archivo=None, justificacion="Sin datos sensibles.")
        self.item(data, "11.11").update(estado="pendiente", archivo=None)
        self.item(data, "11.4").update(estado="en_tramite", archivo=None)
        self.save(data)
        target = self.run / "insumos" / "requisitos" / "soporte.pdf"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"%PDF")
        self.assertNotIn("requisitos-pendiente-final", _codes(self.found()))
        nodes = [f["node"] for f in self.found(final=True) if f["code"] == "requisitos-pendiente-final"]
        self.assertEqual(nodes, ["11.4"], "11.10 is not applicable and 11.11 has no international ally")

    def test_schema_and_invalid_json_are_errors(self) -> None:
        self.save({"schema": "otro"})
        self.assertEqual(_codes(self.found()), ["requisitos-esquema"])
        self.path.write_text("{", encoding="utf-8")
        self.assertEqual(_codes(self.found()), ["requisitos-json-invalido"])

    def test_check_cli_exit_codes_and_json(self) -> None:
        self.clean()
        result = _cli("check", self.run, "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("findings", json.loads(result.stdout))
        self.assertEqual(_cli("check", self.run, "--final").returncode, 1)
        data = self.data()
        self.item(data, "11.5").update(estado="no_aplica", justificacion="x")
        self.save(data)
        result = _cli("check", self.run)
        self.assertEqual(result.returncode, 1)
        self.assertIn("requisitos-no-aplica-invalido", result.stdout)
        self.path.unlink()
        self.assertEqual(_cli("check", self.run).returncode, 2)

    def test_findings_is_empty_without_the_file(self) -> None:
        self.path.unlink()
        self.assertEqual(self.mod.findings(self.run), [])


class Vista(unittest.TestCase):
    """S4/S7: the read model the dashboard tab renders."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.mod = _load("requisitos_sgr_vista", SCRIPT)
        self.run = _make_run(self.tmp)

    def test_vista_works_without_the_file(self) -> None:
        view = self.mod.vista(self.run)
        self.assertEqual(set(view), {"convocatoria", "requisitos", "progreso", "cifras", "licencias", "aval",
                                     "findings"})
        self.assertEqual(view["convocatoria"], "conv54")
        self.assertEqual(len(view["requisitos"]), 28)
        first = view["requisitos"][0]
        for key in ("id", "nombre", "texto", "condicion", "documento", "numeral_fuente", "estado", "responsable",
                    "archivo", "fecha", "nota", "justificacion", "aplica_derivada"):
            self.assertIn(key, first)
        self.assertEqual(first["estado"], "pendiente")
        self.assertIs(first["aplica_derivada"], True)
        by_id = {r["id"]: r for r in view["requisitos"]}
        self.assertIs(by_id["11.11"]["aplica_derivada"], False)
        self.assertIsNone(by_id["11.10"]["aplica_derivada"])
        self.assertEqual(view["progreso"], {"listos": 0, "aplicables": 26})
        self.assertFalse(self.run.joinpath("artefactos", "sgr", "requisitos.json").exists())

    def test_vista_reports_figures_endorsement_and_findings(self) -> None:
        self.mod.init(self.run)
        self.mod.actualizar_item(self.run, "cifras.sigp", {"total_sgr": 1, "total_contrapartida": 2, "total": 3})
        view = self.mod.vista(self.run)
        row = next(r for r in view["cifras"] if r["documento"] == "sigp" and r["campo"] == "total_sgr")
        self.assertEqual((row["declarado"], row["coincide"]), (1, False))
        self.assertIsInstance(row["esperado"], (int, float))
        undeclared = next(r for r in view["cifras"] if r["documento"] == "mga" and r["campo"] == "total")
        self.assertIsNone(undeclared["declarado"])
        self.assertIsNone(undeclared["coincide"])
        self.assertIn("requisitos-cifras-distintas", _codes(view["findings"]))
        self.assertEqual(view["aval"]["institucion"], "unal")
        self.assertEqual(len(view["aval"]["documentos"]), 7)
        self.assertIn("texto", view["aval"]["documentos"][0])
        hito = view["aval"]["hitos"][0]
        self.assertEqual(hito["dias_restantes"],
                         (datetime.date.fromisoformat(hito["fecha"]) - datetime.date.today()).days)


class ActualizarItem(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.mod = _load("requisitos_sgr_update", SCRIPT)
        self.run = _make_run(self.tmp)
        self.path = self.run / "artefactos" / "sgr" / "requisitos.json"

    def test_creates_the_file_and_returns_the_updated_item(self) -> None:
        item = self.mod.actualizar_item(self.run, "11.4", {"estado": "en_tramite", "responsable": "E1",
                                                            "fecha": "2026-11-20", "nota": "Firmas en curso."})
        self.assertEqual(item, {"id": "11.4", "estado": "en_tramite", "responsable": "E1", "archivo": None,
                                "fecha": "2026-11-20", "nota": "Firmas en curso.", "justificacion": None})
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["items"]), 28)
        self.assertEqual(next(i for i in data["items"] if i["id"] == "11.4"), item)

    def test_rejects_unknown_ids_fields_and_values(self) -> None:
        self.mod.init(self.run)
        before = self.path.read_bytes()
        bad = [("11.99", {"estado": "listo"}), ("11.4", {"color": "rojo"}), ("11.4", {"estado": "hecho"}),
               ("11.4", {"fecha": "2026-13-01"}), ("11.4", {"archivo": "/etc/passwd"}),
               ("11.4", {"archivo": "../../fuera.pdf"}), ("11.4", {"responsable": "E99"}),
               ("11.4", {"nota": 5}), ("cifras.otro", {"total": 1}), ("cifras.sigp", {"total": "mil"}),
               ("cifras.anexo1", {"por_entidad": {"E1": {"especie": "x"}}})]
        for iid, changes in bad:
            with self.subTest(iid=iid, changes=changes):
                with self.assertRaises(ValueError):
                    self.mod.actualizar_item(self.run, iid, changes)
                self.assertEqual(self.path.read_bytes(), before)

    def test_write_is_atomic(self) -> None:
        self.mod.init(self.run)
        before = self.path.read_bytes()
        with mock.patch.object(self.mod.os, "replace", side_effect=OSError("disco lleno")):
            with self.assertRaises(OSError):
                self.mod.actualizar_item(self.run, "11.4", {"estado": "listo"})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()),
                         ["alianza.json", "presupuesto.json", "requisitos.json"])

    def test_replaces_one_declared_figures_block(self) -> None:
        block = {"por_entidad": {"E1": {"especie": 100_000_000, "efectivo": 0}}}
        self.assertEqual(self.mod.actualizar_item(self.run, "cifras.anexo1", block), block)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["cifras"]["anexo1"], block)
        self.assertIsNone(self.mod.actualizar_item(self.run, "cifras.anexo1", None))


class Datos(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.mod = _load("requisitos_sgr_datos", SCRIPT)
        self.run = _make_run(self.tmp)

    def test_datos_summarises_requirements_and_figures(self) -> None:
        self.mod.init(self.run)
        self.mod.actualizar_item(self.run, "11.10", {"estado": "no_aplica", "justificacion": "Sin datos."})
        self.mod.actualizar_item(self.run, "11.1", {"estado": "listo"})
        result = _cli("datos", self.run, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["requisitos"]["aplicables"], 25)
        self.assertEqual(data["requisitos"]["listos"], 1)
        self.assertEqual(data["requisitos"]["no_aplica"], ["11.10"])
        self.assertNotIn("11.1", data["requisitos"]["pendientes"])
        self.assertNotIn("11.11", data["requisitos"]["pendientes"])
        self.assertIn("11.4", data["requisitos"]["pendientes"])
        self.assertIsNone(data["cifras_coherentes"])
        self.assertIn("artefactos/sgr/requisitos.json", data["fuente"])
        self.mod.actualizar_item(self.run, "cifras.mga", {"total_sgr": 1, "total": 2})
        data = self.mod.datos(self.run)
        self.assertIs(data["cifras_coherentes"], False)
        self.assertEqual([(d["documento"], d["campo"]) for d in data["cifras_diferencias"]],
                         [("mga", "total_sgr"), ("mga", "total")])

    def test_datos_without_rubric_or_file_is_null(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        run = _make_run(Path(tmp.name), rubric=None)
        data = self.mod.datos(run)
        self.assertIsNone(data["requisitos"])
        self.assertIsNone(data["cifras_coherentes"])


class Render(unittest.TestCase):
    """S5: sections 38 and 39, deterministic, only in SGR runs and without error findings."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.mod = _load("requisitos_sgr_render", SCRIPT)
        self.run = _make_run(self.tmp)
        self.mod.init(self.run)
        self.path = self.run / "artefactos" / "sgr" / "requisitos.json"
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["licencias"] = {
            "introduccion": "La entidad proponente y las demás entidades aliadas se comprometen a cumplir la norma.",
            "items": [{"licencia": "Consentimiento informado", "norma": "Resolución 8430 de 1993", "aplica": True,
                       "justificacion": "Participantes humanos.", "responsable": "E1", "momento": "previo"},
                      {"licencia": "Licencia ambiental", "norma": "Decreto 1076 de 2015", "aplica": False,
                       "justificacion": "No interviene el ambiente.", "responsable": None, "momento": None}]}
        next(i for i in data["items"] if i["id"] == "11.10").update(estado="no_aplica", justificacion="Sin datos.")
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.sections = self.run / "redaccion" / "sections"

    def test_render_writes_both_sections_with_the_header(self) -> None:
        result = _cli("render", self.run)
        self.assertEqual(result.returncode, 0, result.stderr)
        for stem in STEMS:
            text = (self.sections / f"{stem}.tex").read_text(encoding="utf-8")
            self.assertEqual(text.splitlines()[0], HEADER)
            self.assertIn("python3 scripts/requisitos_sgr.py render <RUN_ROOT>", text)

    def test_licences_section_has_the_introduction_and_the_table(self) -> None:
        self.mod.render_sections(self.run)
        text = (self.sections / "38_licencias_permisos.tex").read_text(encoding="utf-8")
        self.assertIn(r"\section{Análisis de licencias y permisos}", text)
        self.assertIn("se comprometen a cumplir la norma", text)
        self.assertIn(r"\begin{xltabular}", text)
        for column in ("Licencia o permiso", "Norma", "¿Aplica?", "Justificación", "Responsable",
                       "Momento del trámite"):
            self.assertIn(rf"\textbf{{{column}}}", text)
        self.assertIn("Universidad Nacional de Colombia", text)
        self.assertIn("Previo a la ejecución", text)

    def test_annexes_section_lists_the_applicable_documents_without_prose(self) -> None:
        self.mod.render_sections(self.run)
        text = (self.sections / "39_anexos.tex").read_text(encoding="utf-8")
        self.assertIn(r"\section{ANEXOS REQUISITOS SECTORIALES QUE LE SEAN APLICABLES.}", text)
        self.assertIn(r"\begin{itemize}", text)
        self.assertIn("Anexo 1", text)
        self.assertIn("MGA Web Tipología D – PIIP", text)
        self.assertNotIn("11.10", text, "not applicable")
        self.assertNotIn("11.11", text, "no international ally")
        body = text.split(r"\begin{itemize}")[0].split(r"\label{sec:anexos}")[1]
        self.assertEqual(body.strip(), "", "no prose before the list")

    def test_render_is_deterministic(self) -> None:
        self.mod.render_sections(self.run)
        first = [(self.sections / f"{s}.tex").read_bytes() for s in STEMS]
        self.mod.render_sections(self.run)
        self.assertEqual([(self.sections / f"{s}.tex").read_bytes() for s in STEMS], first)

    def test_render_uses_the_tdr_chapter_titles(self) -> None:
        structure = {"fuente": "Anexo 2", "capitulos": [
            {"numero": 27, "titulo": "IDONEIDAD Y TRAYECTORIA DE LA ENTIDAD PROPONENTE Y DEMÁS PARTICIPANTES",
             "archivos": []},
            {"numero": 28, "titulo": "ANÁLISIS DE LICENCIAS Y PERMISOS", "archivos": []},
            {"numero": 31, "titulo": "ANEXOS", "archivos": []}]}
        (self.run / "artefactos" / "estructura_tdr.json").write_text(json.dumps(structure, ensure_ascii=False),
                                                                     encoding="utf-8")
        self.mod.render_sections(self.run)
        self.assertIn(r"\section{ANÁLISIS DE LICENCIAS Y PERMISOS}",
                      (self.sections / "38_licencias_permisos.tex").read_text(encoding="utf-8"))
        self.assertIn(r"\section{ANEXOS}", (self.sections / "39_anexos.tex").read_text(encoding="utf-8"))

    def test_render_refuses_error_findings_and_base_runs(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        next(i for i in data["items"] if i["id"] == "11.5").update(estado="no_aplica", justificacion="x")
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = _cli("render", self.run)
        self.assertEqual(result.returncode, 1)
        self.assertIn("requisitos-no-aplica-invalido", result.stderr)
        self.assertFalse((self.sections / "39_anexos.tex").exists())
        with tempfile.TemporaryDirectory() as tmp:
            base = _make_run(Path(tmp), flujo="base")
            shutil.copy(self.path, base / "artefactos" / "sgr" / "requisitos.json")
            self.assertEqual(_cli("render", base).returncode, 2)
            self.assertFalse((base / "redaccion" / "sections" / "38_licencias_permisos.tex").exists())


class Wiring(unittest.TestCase):
    """S5: the new stems are registered wherever SGR sections are listed."""

    def test_assembler_places_38_and_39_in_their_chapters(self) -> None:
        assembler = _load("ensamblar_for_requisitos", REPO / "scripts" / "ensamblar_main.py")
        for titles in (("ANÁLISIS DE LAS ALTERNATIVAS", "ANÁLISIS DE LICENCIAS Y PERMISOS", "BIBLIOGRAFÍA", "ANEXOS"),
                       ("Análisis de las alternativas.", "Análisis de licencias y permisos.", "Bibliografía.",
                        "Anexos requisitos sectoriales que le sean aplicables.")):
            with self.subTest(titles=titles[1]):
                structure = {"capitulos": [{"numero": n, "titulo": t, "archivos": []}
                                           for n, t in enumerate(titles, start=1)]}
                placed = assembler.placed_chapters(structure, "sgr")
                self.assertEqual([c["archivos"] for c in placed],
                                 [[], ["38_licencias_permisos"], [], ["39_anexos"]])
                self.assertEqual([c["archivos"] for c in assembler.placed_chapters(structure, "base")],
                                 [[], [], [], []])

    def test_status_template_and_check_run_list_the_stems(self) -> None:
        from morfeo.core.status import SECTION_TITLES
        check_run = _load("check_run_for_requisitos", REPO / "scripts" / "check_run.py")
        template = (REPO / "plantilla" / "main.tex").read_text(encoding="utf-8")
        for stem in STEMS:
            with self.subTest(stem=stem):
                self.assertIn(stem, SECTION_TITLES)
                self.assertIn(stem, check_run.SGR_SECTIONS)
                self.assertIn(rf"\SeccionSiExiste{{{stem}}}", template)
        self.assertLess(template.index(r"\SeccionSiExiste{39_anexos}"),
                        template.index(r"\SeccionSiExiste{16_bibliografia}"))


if __name__ == "__main__":
    unittest.main()
