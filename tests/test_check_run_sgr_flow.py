"""check_run in the SGR flow: value chain and SGR style findings (odd/tasks/sgr-cadena-estilo.md, S1 and S6).

The SGR flow adds the `cadena-*` findings of scripts/cadena_valor_sgr.py, a
warning when a run past the objectives gate has no value chain, an error when
annex A23 was written by hand or is older than its data, and the
`sgr-estilo-*` findings of scripts/estilo_sgr.py as warnings. A base run gets
none of them (S1).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))

from test_alianza_territorio_sgr import _alliance, _territory  # noqa: E402
from test_cadena_valor_sgr import TREE, _valid_chain  # noqa: E402
from test_componentes_sgr import _components  # noqa: E402
from test_presupuesto_sgr import _budget  # noqa: E402

CHECK = REPO / "scripts" / "check_run.py"
NEW_PREFIXES = ("cadena-", "sgr-estilo-", "alianza-", "territorio-", "presupuesto-", "cronograma-", "componentes-")
BUDGET_HEADER = "% GENERADO por scripts/presupuesto_sgr.py"
COMPONENTS_HEADER = "% GENERADO por scripts/componentes_sgr.py"
COMPONENT_STEMS = ("31_trl", "32_sostenibilidad", "33_uso_posterior", "34_transferencia", "35_medidas_diferenciales")

STUB_CRONOGRAMA = '''
def findings(run_root):
    return [{"severity": "warning", "code": "cronograma-sin-hitos", "message": "Más de tres meses sin hito.",
             "node": "1.1"}]
'''

STUB_PRESUPUESTO = '''
def findings(run_root):
    return [{"severity": "error", "code": "presupuesto-stub", "message": "Stub.", "node": "P1"}]
'''
ALLIANCE_STEMS = ("26_identificacion", "27_demandas_territoriales", "28_matriz_responsabilidades",
                  "29_idoneidad_trayectoria")

STUB_ESTILO = '''
def findings(run_root, section=None):
    return [{"severity": "advertencia", "code": "sgr-estilo-primera-persona",
             "message": "Primera persona en prosa SGR.", "archivo": "redaccion/sections/02_justificacion.tex",
             "linea": 3, "extracto": "nosotros proponemos", "regla": "primera-persona"},
            {"severity": "info", "code": "sgr-estilo-expresion-favorecida",
             "message": "Expresión favorecida ausente.", "archivo": "redaccion/sections/02_justificacion.tex",
             "linea": None, "extracto": "", "regla": "expresion-favorecida"}]
'''


def _make_run(tmp: Path) -> Path:
    run = tmp / "run"
    (run / "redaccion" / "sections").mkdir(parents=True)
    (run / "artefactos" / "arboles").mkdir(parents=True)
    (run / "artefactos" / "arboles" / "arbol_objetivos.json").write_text(json.dumps(TREE, ensure_ascii=False),
                                                                          encoding="utf-8")
    (run / "redaccion" / "sections" / "02_justificacion.tex").write_text(
        "\\section{Justificación}\nEl proyecto atiende la detección temprana.\n", encoding="utf-8")
    return run


def _write_chain(run: Path, chain: dict) -> Path:
    path = run / "artefactos" / "sgr" / "cadena_valor.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chain, ensure_ascii=False), encoding="utf-8")
    return path


def _findings(run: Path, flujo: str, check: Path = CHECK) -> list[dict]:
    out = subprocess.run([sys.executable, str(check), str(run), "--json", "--flujo", flujo],
                         capture_output=True, text=True)
    return json.loads(out.stdout)["findings"]


def _findings_final(run: Path, flujo: str, check: Path = CHECK) -> list[dict]:
    out = subprocess.run([sys.executable, str(check), str(run), "--json", "--final", "--flujo", flujo],
                         capture_output=True, text=True)
    return json.loads(out.stdout)["findings"]


def _write_sgr(run: Path, name: str, data: dict) -> Path:
    path = run / "artefactos" / "sgr" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _codes(findings: list[dict], severity: str | None = None) -> list[str]:
    return [f["code"] for f in findings if severity is None or f["severity"] == severity]


class Base(unittest.TestCase):
    """S1: a base run produces the same findings as before, whatever SGR files it holds."""

    def test_base_run_gets_no_new_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _make_run(Path(tmp))
            before = _findings(run, "base")
            chain = _valid_chain()
            chain["objetivos"][0]["productos"][0]["actividades"][0]["nombre"] = "Implementar la plataforma"
            _write_chain(run, chain)
            sections = run / "redaccion" / "sections"
            (sections / "23_cadena_valor.tex").write_text("\\section{Cadena de valor}\nA mano.\n", encoding="utf-8")
            (run / "artefactos" / "estado_propuesta.md").write_text("| G4 | APROBADA |\n", encoding="utf-8")
            after = _findings(run, "base")
            self.assertFalse([c for c in _codes(after) if c.startswith(NEW_PREFIXES)])
            self.assertEqual(after, before)

    def test_base_run_ignores_the_alliance_and_territory_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _make_run(Path(tmp))
            before = _findings(run, "base")
            before_final = _findings_final(run, "base")
            alliance = _alliance()
            alliance["entidades"][0]["proponente"] = False
            _write_sgr(run, "alianza.json", alliance)
            sections = run / "redaccion" / "sections"
            for stem in ALLIANCE_STEMS:
                (sections / f"{stem}.tex").write_text("\\section{A mano}\nTexto.\n", encoding="utf-8")
            (run / "artefactos" / "estado_propuesta.md").write_text("| GTerritorio | APROBADA |\n", encoding="utf-8")
            self.assertEqual(_findings(run, "base"), before)
            self.assertEqual(_findings_final(run, "base"), before_final)

    def test_base_run_ignores_the_budget_and_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            check = _isolated_check(Path(tmp), with_stub=False, extra={"cronograma_sgr.py": STUB_CRONOGRAMA,
                                                                       "presupuesto_sgr.py": STUB_PRESUPUESTO})
            run = _make_run(Path(tmp))
            before = _findings(run, "base", check)
            before_final = _findings_final(run, "base", check)
            _write_sgr(run, "presupuesto.json", _budget())
            sections = run / "redaccion" / "sections"
            for stem in ("13_presupuesto", "30_fuentes_financiacion"):
                (sections / f"{stem}.tex").write_text("\\section{A mano}\nTexto.\n", encoding="utf-8")
            (run / "artefactos" / "estado_propuesta.md").write_text("| G6.4 | APROBADA |\n", encoding="utf-8")
            (sections / "13_presupuesto.tex").unlink()
            self.assertEqual(_findings(run, "base", check), before)
            self.assertEqual(_findings_final(run, "base", check), before_final)

    def test_base_run_ignores_the_components(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = _make_run(Path(tmp))
            sections = run / "redaccion" / "sections"
            (sections / "18_apropiacion_social.tex").write_text("\\section{Apropiación}\nA mano.\n", encoding="utf-8")
            before = _findings(run, "base")
            before_final = _findings_final(run, "base")
            components = _components()
            components["diferencial"]["barreras"] = []
            _write_sgr(run, "componentes.json", components)
            for stem in COMPONENT_STEMS:
                (sections / f"{stem}.tex").write_text("\\section{A mano}\nTexto.\n", encoding="utf-8")
            (run / "artefactos" / "estado_propuesta.md").write_text("| GComponentes | APROBADA |\n", encoding="utf-8")
            self.assertEqual(_findings(run, "base"), before)
            self.assertEqual(_findings_final(run, "base"), before_final)
            (run / "artefactos" / "sgr" / "componentes.json").unlink()
            self.assertEqual(_findings(run, "base"), before)

    def test_base_run_never_calls_the_style_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            check = _isolated_check(Path(tmp), with_stub=True)
            run = _make_run(Path(tmp))
            self.assertFalse([c for c in _codes(_findings(run, "base", check)) if c.startswith(NEW_PREFIXES)])


def _isolated_check(tmp: Path, with_stub: bool, extra: dict[str, str] | None = None) -> Path:
    """check_run and cadena_valor_sgr copied to their own folder, with or without a stub estilo_sgr
    (and the other stub modules of `extra`, by file name)."""
    scripts = tmp / "scripts"
    scripts.mkdir()
    for name in ("check_run.py", "cadena_valor_sgr.py"):
        shutil.copy(REPO / "scripts" / name, scripts / name)
    if with_stub:
        (scripts / "estilo_sgr.py").write_text(STUB_ESTILO, encoding="utf-8")
    for name, text in (extra or {}).items():
        (scripts / name).write_text(text, encoding="utf-8")
    return scripts / "check_run.py"


class Sgr(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.run = _make_run(self.tmp)
        self.sections = self.run / "redaccion" / "sections"

    def test_value_chain_findings_are_included(self) -> None:
        chain = _valid_chain()
        chain["objetivos"][0]["productos"][0]["actividades"][0]["nombre"] = "Implementar la plataforma"
        chain["objetivos"][0]["productos"][0]["codigo_dnp"] = None
        _write_chain(self.run, chain)
        found = _findings(self.run, "sgr")
        verb = next(f for f in found if f["code"] == "cadena-verbo-prohibido")
        self.assertEqual(verb["severity"], "error")
        self.assertEqual(verb["file"], "artefactos/sgr/cadena_valor.json")
        self.assertEqual(verb["node"], "1.1.1")
        self.assertIn("cadena-codigo-dnp-faltante", _codes(found, "warning"))

    def test_a_clean_value_chain_adds_nothing(self) -> None:
        _write_chain(self.run, _valid_chain())
        self.assertFalse([c for c in _codes(_findings(self.run, "sgr")) if c.startswith("cadena-")])

    def test_missing_value_chain_warns_only_past_the_objectives_gate(self) -> None:
        self.assertNotIn("cadena-valor-faltante", _codes(_findings(self.run, "sgr")))
        (self.run / "artefactos" / "estado_propuesta.md").write_text(
            "| Compuerta | Estado |\n|---|---|\n| G4 | APROBADA |\n", encoding="utf-8")
        self.assertIn("cadena-valor-faltante", _codes(_findings(self.run, "sgr"), "warning"))

    def test_a_later_section_also_means_past_the_objectives_gate(self) -> None:
        (self.sections / "08_marco_conceptual.tex").write_text("\\section{Marco}\nTexto.\n", encoding="utf-8")
        self.assertIn("cadena-valor-faltante", _codes(_findings(self.run, "sgr"), "warning"))

    def test_approving_only_the_value_chain_gate_is_not_g4(self) -> None:
        (self.run / "artefactos" / "estado_propuesta.md").write_text("| G4.cv | PENDIENTE |\n", encoding="utf-8")
        self.assertNotIn("cadena-valor-faltante", _codes(_findings(self.run, "sgr")))

    def test_hand_written_annex_is_an_error(self) -> None:
        _write_chain(self.run, _valid_chain())
        (self.sections / "23_cadena_valor.tex").write_text("\\section{Cadena de valor}\nA mano.\n", encoding="utf-8")
        self.assertIn("cadena-anexo-manual", _codes(_findings(self.run, "sgr"), "error"))

    def test_annex_older_than_its_data_is_an_error(self) -> None:
        chain_path = _write_chain(self.run, _valid_chain())
        render = subprocess.run([sys.executable, str(REPO / "scripts" / "cadena_valor_sgr.py"), "render",
                                 str(self.run)], capture_output=True, text=True)
        self.assertEqual(render.returncode, 0, render.stderr)
        tex = self.sections / "23_cadena_valor.tex"
        self.assertFalse([c for c in _codes(_findings(self.run, "sgr")) if c.startswith("cadena-anexo")])
        stamp = tex.stat().st_mtime
        os.utime(chain_path, (stamp + 10, stamp + 10))
        self.assertIn("cadena-anexo-desactualizado", _codes(_findings(self.run, "sgr"), "error"))

    def test_style_findings_come_in_as_warnings_when_the_module_exists(self) -> None:
        check = _isolated_check(self.tmp, with_stub=True)
        found = [f for f in _findings(self.run, "sgr", check) if f["code"].startswith("sgr-estilo-")]
        self.assertEqual(_codes(found), ["sgr-estilo-primera-persona", "sgr-estilo-expresion-favorecida"])
        self.assertEqual({f["severity"] for f in found}, {"warning"})
        self.assertEqual(found[0]["file"], "redaccion/sections/02_justificacion.tex")
        self.assertEqual(found[0]["line"], 3)
        self.assertIn("nosotros proponemos", found[0]["message"])

    def test_without_the_style_module_there_are_no_style_findings(self) -> None:
        check = _isolated_check(self.tmp, with_stub=False)
        self.assertFalse([c for c in _codes(_findings(self.run, "sgr", check)) if c.startswith("sgr-estilo-")])


class SgrAllianceTerritory(unittest.TestCase):
    """S3/S4: alliance and territory findings, their absence after GTerritorio and the rendered sections."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = _make_run(Path(tmp.name))
        self.sections = self.run / "redaccion" / "sections"
        _write_chain(self.run, _valid_chain())

    def write_both(self, alliance: dict | None = None) -> tuple[Path, Path]:
        return (_write_sgr(self.run, "alianza.json", alliance or _alliance()),
                _write_sgr(self.run, "territorio.json", _territory()))

    def test_findings_are_included_with_their_file(self) -> None:
        alliance = _alliance()
        alliance["entidades"][0]["proponente"] = False
        alliance["entidades"][4]["departamento"] = "Antioquia"
        self.write_both(alliance)
        found = _findings(self.run, "sgr")
        proponent = next(f for f in found if f["code"] == "alianza-proponente")
        self.assertEqual((proponent["severity"], proponent["file"]), ("error", "artefactos/sgr/alianza.json"))
        outside = next(f for f in found if f["code"] == "alianza-departamento-fuera")
        self.assertEqual((outside["severity"], outside["node"]), ("warning", "E5"))

    def test_territory_findings_point_to_the_territory_file(self) -> None:
        _write_sgr(self.run, "alianza.json", _alliance())
        territory = _territory()
        territory["demandas"][0]["objetivos"] = ["OE9"]
        _write_sgr(self.run, "territorio.json", territory)
        found = next(f for f in _findings(self.run, "sgr") if f["code"] == "territorio-objetivo-desconocido")
        self.assertEqual(found["file"], "artefactos/sgr/territorio.json")

    def test_clean_data_adds_nothing(self) -> None:
        self.write_both()
        self.assertFalse([c for c in _codes(_findings(self.run, "sgr")) if c.startswith(("alianza-", "territorio-"))])

    def test_missing_data_warns_only_past_gterritorio(self) -> None:
        codes = _codes(_findings(self.run, "sgr"))
        self.assertNotIn("alianza-datos-faltantes", codes)
        (self.run / "artefactos" / "estado_propuesta.md").write_text(
            "| Compuerta | Estado |\n|---|---|\n| GTerritorio | APROBADA |\n", encoding="utf-8")
        warnings = _codes(_findings(self.run, "sgr"), "warning")
        self.assertIn("alianza-datos-faltantes", warnings)
        self.assertIn("territorio-datos-faltantes", warnings)

    def test_hand_written_section_is_an_error(self) -> None:
        self.write_both()
        (self.sections / "27_demandas_territoriales.tex").write_text("\\section{Demandas}\nA mano.\n",
                                                                      encoding="utf-8")
        (self.sections / "29_idoneidad_trayectoria.tex").write_text("\\section{Idoneidad}\nTexto.\n",
                                                                     encoding="utf-8")
        errors = _codes(_findings(self.run, "sgr"), "error")
        self.assertIn("territorio-anexo-manual", errors)
        self.assertNotIn("alianza-anexo-manual", errors)

    def test_section_older_than_its_data_is_an_error(self) -> None:
        alliance_path, _ = self.write_both()
        render = subprocess.run([sys.executable, str(REPO / "scripts" / "alianza_territorio_sgr.py"), "render",
                                 str(self.run)], capture_output=True, text=True)
        self.assertEqual(render.returncode, 0, render.stderr)
        self.assertFalse([c for c in _codes(_findings(self.run, "sgr")) if "-anexo-" in c])
        stamp = (self.sections / "28_matriz_responsabilidades.tex").stat().st_mtime
        os.utime(alliance_path, (stamp + 10, stamp + 10))
        found = [f for f in _findings(self.run, "sgr") if f["code"] == "alianza-anexo-desactualizado"]
        self.assertEqual({f["file"].rsplit("/", 1)[-1] for f in found},
                         {"26_identificacion.tex", "28_matriz_responsabilidades.tex"})

    def test_final_sgr_run_requires_the_new_sections(self) -> None:
        missing = [f["message"] for f in _findings_final(self.run, "sgr") if f["code"] == "sgr-anexo-faltante"]
        for stem in ALLIANCE_STEMS:
            self.assertTrue(any(stem in m for m in missing), stem)


class SgrBudgetSchedule(unittest.TestCase):
    """S3/S4: budget and schedule findings, the absence of presupuesto.json after G6.4, sections 13 and 30."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.run = _make_run(self.tmp)
        self.sections = self.run / "redaccion" / "sections"
        _write_chain(self.run, _valid_chain())
        _write_sgr(self.run, "alianza.json", _alliance())

    def write_budget(self, budget: dict | None = None) -> Path:
        path = _write_sgr(self.run, "presupuesto.json", budget or _budget())
        module = subprocess.run([sys.executable, str(REPO / "scripts" / "presupuesto_sgr.py"), "sync-cadena",
                                 str(self.run)], capture_output=True, text=True)
        self.assertEqual(module.returncode, 0, module.stderr)
        return path

    def generated(self, stem: str) -> Path:
        tex = self.sections / f"{stem}.tex"
        tex.write_text(f"{BUDGET_HEADER}\n\\section{{Generada}}\n", encoding="utf-8")
        return tex

    def test_budget_findings_are_included_with_their_file(self) -> None:
        budget = _budget()
        budget["items"][0]["rubro"] = "viaticos"
        self.write_budget(budget)
        hit = next(f for f in _findings(self.run, "sgr") if f["code"] == "presupuesto-rubro-invalido")
        self.assertEqual((hit["severity"], hit["file"], hit["node"]), ("error", "artefactos/sgr/presupuesto.json", "P1"))

    def test_clean_budget_adds_nothing(self) -> None:
        self.write_budget()
        self.assertFalse([c for c in _codes(_findings(self.run, "sgr")) if c.startswith("presupuesto-")])

    def test_missing_budget_warns_only_past_g64(self) -> None:
        estado = self.run / "artefactos" / "estado_propuesta.md"
        self.assertNotIn("presupuesto-datos-faltantes", _codes(_findings(self.run, "sgr")))
        estado.write_text("| G6.45 | APROBADA |\n| G6.4 | PENDIENTE |\n", encoding="utf-8")
        self.assertNotIn("presupuesto-datos-faltantes", _codes(_findings(self.run, "sgr")))
        estado.write_text("| Compuerta | Estado |\n|---|---|\n| G6.4 | APROBADA |\n", encoding="utf-8")
        self.assertIn("presupuesto-datos-faltantes", _codes(_findings(self.run, "sgr"), "warning"))

    def test_hand_written_sources_section_is_an_error(self) -> None:
        (self.sections / "30_fuentes_financiacion.tex").write_text("\\section{Fuentes}\nA mano.\n",
                                                                     encoding="utf-8")
        hit = [f for f in _findings(self.run, "sgr") if f["code"] == "presupuesto-anexo-manual"]
        self.assertEqual([f["file"] for f in hit], ["redaccion/sections/30_fuentes_financiacion.tex"])

    def test_hand_written_budget_section_is_an_error_only_with_the_json(self) -> None:
        (self.sections / "13_presupuesto.tex").write_text("\\section{Presupuesto}\nA mano.\n", encoding="utf-8")
        self.assertNotIn("presupuesto-anexo-manual", _codes(_findings(self.run, "sgr")))
        self.write_budget()
        hit = [f for f in _findings(self.run, "sgr") if f["code"] == "presupuesto-anexo-manual"]
        self.assertEqual([(f["severity"], f["file"]) for f in hit], [("error", "redaccion/sections/13_presupuesto.tex")])

    def test_section_older_than_its_data_is_an_error(self) -> None:
        budget_path = self.write_budget()
        budget_tex, sources_tex = self.generated("13_presupuesto"), self.generated("30_fuentes_financiacion")
        self.assertFalse([c for c in _codes(_findings(self.run, "sgr")) if c.startswith("presupuesto-anexo")])
        stamp = sources_tex.stat().st_mtime
        os.utime(budget_path, (stamp + 10, stamp + 10))
        found = [f for f in _findings(self.run, "sgr") if f["code"] == "presupuesto-anexo-desactualizado"]
        self.assertEqual({f["file"].rsplit("/", 1)[-1] for f in found},
                         {"13_presupuesto.tex", "30_fuentes_financiacion.tex"})
        os.utime(budget_path, (stamp - 10, stamp - 10))
        os.utime(self.run / "artefactos" / "sgr" / "cadena_valor.json", (stamp + 10, stamp + 10))
        found = [f for f in _findings(self.run, "sgr") if f["code"] == "presupuesto-anexo-desactualizado"]
        self.assertEqual([f["file"].rsplit("/", 1)[-1] for f in found], ["13_presupuesto.tex"])
        self.assertTrue(budget_tex.is_file())

    def test_schedule_findings_come_in_when_the_module_exists(self) -> None:
        check = _isolated_check(self.tmp, with_stub=False, extra={"cronograma_sgr.py": STUB_CRONOGRAMA})
        hit = [f for f in _findings(self.run, "sgr", check) if f["code"].startswith("cronograma-")]
        self.assertEqual([(f["code"], f["severity"], f["file"], f["node"]) for f in hit],
                         [("cronograma-sin-hitos", "warning", "artefactos/sgr/cadena_valor.json", "1.1")])

    def test_without_the_schedule_module_there_are_no_schedule_findings(self) -> None:
        check = _isolated_check(self.tmp, with_stub=False)
        self.assertFalse([c for c in _codes(_findings(self.run, "sgr", check)) if c.startswith("cronograma-")])

    def test_a_broken_schedule_module_is_a_warning(self) -> None:
        check = _isolated_check(self.tmp, with_stub=False,
                                extra={"cronograma_sgr.py": "def findings(run_root):\n    raise RuntimeError('x')\n"})
        self.assertIn("cronograma-no-verificable", _codes(_findings(self.run, "sgr", check), "warning"))

    def test_final_sgr_run_requires_the_sources_section(self) -> None:
        missing = [f["message"] for f in _findings_final(self.run, "sgr") if f["code"] == "sgr-anexo-faltante"]
        self.assertTrue(any("30_fuentes_financiacion" in m for m in missing))


class SgrComponents(unittest.TestCase):
    """S3/S4: component findings, the absence of componentes.json after GComponentes, sections 31 to 35 and §18."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.run = _make_run(self.tmp)
        self.sections = self.run / "redaccion" / "sections"
        _write_chain(self.run, _valid_chain())
        _write_sgr(self.run, "alianza.json", _alliance())

    def generated(self, stem: str) -> Path:
        tex = self.sections / f"{stem}.tex"
        tex.write_text(f"{COMPONENTS_HEADER}\n\\section{{Generada}}\n", encoding="utf-8")
        return tex

    def test_component_findings_are_included_with_their_file(self) -> None:
        components = _components()
        components["trl"]["ruta"][0]["actividades"] = ["9.9.9"]
        _write_sgr(self.run, "componentes.json", components)
        hit = next(f for f in _findings(self.run, "sgr") if f["code"] == "componentes-actividad-desconocida")
        self.assertEqual((hit["severity"], hit["file"], hit["node"]),
                         ("error", "artefactos/sgr/componentes.json", "trl.ruta[1]"))

    def test_clean_components_add_nothing(self) -> None:
        _write_sgr(self.run, "componentes.json", _components())
        self.assertFalse([c for c in _codes(_findings(self.run, "sgr")) if c.startswith("componentes-")])

    def test_missing_components_warn_only_past_gcomponentes(self) -> None:
        estado = self.run / "artefactos" / "estado_propuesta.md"
        self.assertNotIn("componentes-datos-faltantes", _codes(_findings(self.run, "sgr")))
        estado.write_text("| GComponentes | PENDIENTE |\n", encoding="utf-8")
        self.assertNotIn("componentes-datos-faltantes", _codes(_findings(self.run, "sgr")))
        estado.write_text("| Compuerta | Estado |\n|---|---|\n| GComponentes | APROBADA |\n", encoding="utf-8")
        self.assertIn("componentes-datos-faltantes", _codes(_findings(self.run, "sgr"), "warning"))

    def test_hand_written_component_section_is_an_error(self) -> None:
        (self.sections / "34_transferencia.tex").write_text("\\section{Transferencia}\nA mano.\n", encoding="utf-8")
        hit = [f for f in _findings(self.run, "sgr") if f["code"] == "componentes-anexo-manual"]
        self.assertEqual([(f["severity"], f["file"]) for f in hit],
                         [("error", "redaccion/sections/34_transferencia.tex")])

    def test_hand_written_section_18_is_an_error_only_with_the_json(self) -> None:
        (self.sections / "18_apropiacion_social.tex").write_text("\\section{Apropiación}\nA mano.\n",
                                                                  encoding="utf-8")
        self.assertNotIn("componentes-anexo-manual", _codes(_findings(self.run, "sgr")))
        _write_sgr(self.run, "componentes.json", _components())
        hit = [f for f in _findings(self.run, "sgr") if f["code"] == "componentes-anexo-manual"]
        self.assertEqual([f["file"] for f in hit], ["redaccion/sections/18_apropiacion_social.tex"])

    def test_section_older_than_its_data_is_an_error(self) -> None:
        data = _write_sgr(self.run, "componentes.json", _components())
        texs = [self.generated(stem) for stem in COMPONENT_STEMS + ("18_apropiacion_social",)]
        self.assertFalse([c for c in _codes(_findings(self.run, "sgr")) if c.startswith("componentes-anexo")])
        stamp = max(t.stat().st_mtime for t in texs)
        os.utime(data, (stamp + 10, stamp + 10))
        found = [f for f in _findings(self.run, "sgr") if f["code"] == "componentes-anexo-desactualizado"]
        self.assertEqual({f["file"].rsplit("/", 1)[-1] for f in found},
                         {f"{s}.tex" for s in COMPONENT_STEMS + ("18_apropiacion_social",)})
        os.utime(data, (stamp - 10, stamp - 10))
        budget = _write_sgr(self.run, "presupuesto.json", _budget())
        os.utime(budget, (stamp + 10, stamp + 10))
        os.utime(self.run / "artefactos" / "sgr" / "cadena_valor.json", (stamp - 10, stamp - 10))
        os.utime(self.run / "artefactos" / "sgr" / "alianza.json", (stamp - 10, stamp - 10))
        found = [f for f in _findings(self.run, "sgr") if f["code"] == "componentes-anexo-desactualizado"]
        self.assertEqual([f["file"].rsplit("/", 1)[-1] for f in found], ["34_transferencia.tex"])

    def test_a_broken_components_module_is_a_warning(self) -> None:
        _write_sgr(self.run, "componentes.json", _components())
        check = _isolated_check(self.tmp, with_stub=False,
                                extra={"componentes_sgr.py": "def findings(run_root):\n    raise RuntimeError('x')\n"})
        self.assertIn("componentes-no-verificable", _codes(_findings(self.run, "sgr", check), "warning"))

    def test_final_sgr_run_requires_the_component_sections(self) -> None:
        missing = [f["message"] for f in _findings_final(self.run, "sgr") if f["code"] == "sgr-anexo-faltante"]
        for stem in COMPONENT_STEMS:
            self.assertTrue(any(stem in m for m in missing), stem)


class KitCopy(unittest.TestCase):
    def test_kit_copy_is_byte_identical(self) -> None:
        kit = REPO / "src" / "morfeo" / "_kit" / "scripts" / "check_run.py"
        self.assertEqual(kit.read_bytes(), CHECK.read_bytes())


if __name__ == "__main__":
    unittest.main()
