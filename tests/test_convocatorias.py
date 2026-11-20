"""scripts/convocatorias.py: funding-call profile, validation, Colombian eligibility rules and ranking
(odd/tasks/convocatorias-explorador.md, T1: S2, S3, S4 and the Contracts section).

Every test builds a throwaway workspace (`.morfeo/config.json`) outside the
repository and goes through the public functions or the CLI.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "convocatorias.py"
RULES = REPO / "scripts" / "convocatorias" / "reglas_co.json"
SOURCES = REPO / "scripts" / "convocatorias" / "fuentes.json"
HOY = datetime.date(2026, 11, 20)


def _load():
    spec = importlib.util.spec_from_file_location("_test_convocatorias", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(**overrides) -> dict:
    call = {
        "id": "convocatoria-uno",
        "titulo": "Convocatoria de prueba",
        "financiador": "Financiador Neutro",
        "programa": None,
        "url": "https://example.org/c1",
        "fuente": "prueba",
        "ambito": "internacional",
        "idioma": "en",
        "aplicantes": ["investigador"],
        "rol_colombia": "lider",
        "estado": "abierta",
        "apertura": "2026-10-01",
        "cierre": "2026-12-20",
        "cierre_tipo": "fijo",
        "monto": {"min": None, "max": 100000, "moneda": "EUR"},
        "temas": [],
        "resumen": "Resumen propio de la convocatoria.",
        "elegibilidad": None,
        "puntaje_agente": 50,
        "evidencia": [{"texto": "Deadline 20 December 2026.", "url": "https://example.org/c1"}],
        "encontrada": "2026-11-19",
    }
    call.update(overrides)
    return call


class Workspace:
    """A temporary workspace with a run folder; removed on cleanup."""

    def __init__(self, title: str | None = "Plataforma de IA para energía"):
        self.root = Path(tempfile.mkdtemp(prefix="convocatorias-test-"))
        (self.root / ".morfeo").mkdir()
        (self.root / ".morfeo" / "config.json").write_text(
            json.dumps({"title": title, "flujo": "base", "lang": "es"}), encoding="utf-8")
        self.run = self.root / "proposals" / "2026-11-20-run"
        (self.run / "insumos" / "ideas").mkdir(parents=True)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, name: str, data) -> Path:
        path = self.root / "convocatorias" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        path.write_text(text, encoding="utf-8")
        return path

    def profile(self, **overrides) -> Path:
        data = {"schema": "morfeo.perfil-convocatorias/v1", "actualizado": "2026-11-20",
                "titulo": "T", "idea": None, "aplicantes": ["investigador"], "temas": [],
                "palabras_clave": {"es": [], "en": []}, "financiadores_previos": [],
                "idiomas": ["es", "en"], "ambitos": ["colombia", "latam", "internacional"],
                "institucion": {"nombre": None, "pais": "CO", "tipo": None}}
        data.update(overrides)
        return self.write("perfil.json", data)

    def calls(self, calls: list[dict], **overrides) -> Path:
        data = {"schema": "morfeo.oportunidades/v1", "actualizado": "2026-11-20",
                "fuentes_consultadas": [{"fuente": "minciencias", "url": "https://minciencias.gov.co",
                                         "fecha": "2026-11-20", "resultado": "ok", "n": len(calls)}],
                "oportunidades": calls}
        data.update(overrides)
        return self.write("oportunidades.json", data)


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load()

    def setUp(self):
        self.ws = Workspace()
        self.addCleanup(self.ws.cleanup)

    def codes(self, findings, severity=None):
        return [f["codigo"] for f in findings if severity is None or f["severidad"] == severity]

    def item(self, view, call_id):
        return next(o for o in view["oportunidades"] if o["id"] == call_id)


class WorkspaceTest(Base):
    def test_walks_up_from_a_run_dir(self):
        self.assertEqual(self.mod.find_workspace(self.ws.run / "insumos").resolve(), self.ws.root.resolve())

    def test_marco_config_is_accepted(self):
        other = Path(tempfile.mkdtemp(prefix="convocatorias-test-"))
        self.addCleanup(shutil.rmtree, other, True)
        (other / ".marco").mkdir()
        (other / ".marco" / "config.json").write_text("{}", encoding="utf-8")
        (other / "sub").mkdir()
        self.assertEqual(self.mod.find_workspace(other / "sub").resolve(), other.resolve())

    def test_no_workspace_is_exit_2(self):
        bare = Path(tempfile.mkdtemp(prefix="convocatorias-test-"))
        self.addCleanup(shutil.rmtree, bare, True)
        result = _cli("datos", str(bare))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("error", result.stderr)


class ProfileTest(Base):
    def test_skeleton_from_config_and_workspace_idea(self):
        (self.ws.root / "idea.md").write_text(
            "# Idea\n\n<!-- comentario -->\n## Problema\nPérdidas de energía en redes rurales.\n", encoding="utf-8")
        path, created = self.mod.init_profile(self.ws.run)
        self.assertTrue(created)
        self.assertEqual(path, self.ws.root.resolve() / "convocatorias" / "perfil.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "morfeo.perfil-convocatorias/v1")
        self.assertEqual(data["titulo"], "Plataforma de IA para energía")
        self.assertIn("Pérdidas de energía en redes rurales.", data["idea"])
        self.assertNotIn("<!--", data["idea"])
        self.assertNotIn("#", data["idea"])
        self.assertEqual(data["idiomas"], ["es", "en"])
        self.assertEqual(data["ambitos"], ["colombia", "latam", "internacional"])
        for key in ("aplicantes", "temas", "financiadores_previos"):
            self.assertEqual(data[key], [], key)
        self.assertEqual(data["palabras_clave"], {"es": [], "en": []})
        self.assertEqual(data["institucion"]["pais"], "CO")
        self.assertEqual(self.codes(self.mod.check(self.ws.root), "error"), [])

    def test_idea_falls_back_to_active_run_and_is_trimmed(self):
        (self.ws.root / "idea.md").write_text("# Idea\n\n## Problema\n<!-- vacío -->\n", encoding="utf-8")
        (self.ws.root / "proposals" / ".current-run").write_text("2026-11-20-run\n", encoding="utf-8")
        (self.ws.run / "insumos" / "ideas" / "idea.md").write_text("Idea de la corrida. " * 400, encoding="utf-8")
        path, _ = self.mod.init_profile(self.ws.root)
        idea = json.loads(path.read_text(encoding="utf-8"))["idea"]
        self.assertTrue(idea.startswith("Idea de la corrida."))
        self.assertLessEqual(len(idea), 2001)

    def test_never_overwrites_and_cli_prints_path(self):
        existing = self.ws.profile(temas=["energía"])
        before = existing.read_text(encoding="utf-8")
        result = _cli("perfil", str(self.ws.run))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(existing.resolve()), result.stdout)
        self.assertEqual(existing.read_text(encoding="utf-8"), before)
        _, created = self.mod.init_profile(self.ws.root)
        self.assertFalse(created)

    def test_title_missing_gives_null(self):
        ws = Workspace(title=None)
        self.addCleanup(ws.cleanup)
        path, _ = self.mod.init_profile(ws.root)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsNone(data["titulo"])
        self.assertIsNone(data["idea"])


class CheckTest(Base):
    def assert_error(self, code, calls=None, **file_overrides):
        self.ws.calls(calls if calls is not None else [_call()], **file_overrides)
        findings = self.mod.check(self.ws.root)
        self.assertIn(code, self.codes(findings, "error"), findings)
        result = _cli("check", str(self.ws.run))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"error {code}", result.stdout)

    def test_valid_files_exit_0(self):
        self.ws.profile()
        self.ws.calls([_call()])
        self.assertEqual(self.codes(self.mod.check(self.ws.root), "error"), [])
        result = _cli("check", str(self.ws.root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_schema(self):
        self.assert_error("esquema", schema="otra/v1")

    def test_profile_schema_and_enum(self):
        self.ws.profile(schema="x", aplicantes=["astronauta"])
        codes = self.codes(self.mod.check(self.ws.root), "error")
        self.assertIn("esquema", codes)
        self.assertIn("valor-invalido", codes)

    def test_invalid_json(self):
        self.ws.write("oportunidades.json", "{no es json")
        self.assertIn("json-invalido", self.codes(self.mod.check(self.ws.root), "error"))

    def test_enum(self):
        self.assert_error("valor-invalido", [_call(ambito="planeta")])

    def test_date(self):
        self.assert_error("fecha-invalida", [_call(cierre="20/12/2026")])

    def test_duplicate_id(self):
        self.assert_error("id-repetido", [_call(), _call(titulo="Otra")])

    def test_missing_required_field(self):
        self.assert_error("campo-faltante", [_call(financiador=None)])

    def test_length_limits(self):
        self.assert_error("texto-largo", [_call(resumen="x" * 601)])
        self.assert_error("texto-largo", [_call(evidencia=[{"texto": "y" * 201, "url": "https://e.org"}])])

    def test_score_range(self):
        self.assert_error("puntaje-fuera-de-rango", [_call(puntaje_agente=101)])

    def test_cierre_before_apertura(self):
        self.assert_error("cierre-antes-de-apertura", [_call(apertura="2026-12-01", cierre="2026-11-30")])

    def test_warnings_do_not_fail(self):
        self.ws.calls([_call(evidencia=[], rol_colombia="desconocido", cierre=None)])
        findings = self.mod.check(self.ws.root)
        warnings = self.codes(findings, "warning")
        for code in ("sin-evidencia", "rol-desconocido", "abierta-sin-cierre"):
            self.assertIn(code, warnings)
        self.assertEqual(self.codes(findings, "error"), [])
        self.assertEqual(_cli("check", str(self.ws.root)).returncode, 0)


class ViewTest(Base):
    def test_no_file_is_info_and_exit_0(self):
        view = self.mod.vista(self.ws.run, hoy=HOY)
        self.assertEqual(view["schema"], "morfeo.convocatorias-vista/v1")
        self.assertEqual(view["oportunidades"], [])
        self.assertEqual(view["resumen"]["total"], 0)
        self.assertEqual(view["resumen"]["por_ambito"], {"colombia": 0, "latam": 0, "internacional": 0})
        self.assertIn("sin-oportunidades", self.codes(view["hallazgos"], "info"))
        self.assertFalse(view["perfil"]["existe"])
        result = _cli("datos", str(self.ws.root), "--json", "--hoy", "2026-11-20")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hoy"], "2026-11-20")

    def test_past_cierre_is_cerrada_and_days(self):
        self.ws.calls([_call(id="pasada", cierre="2026-11-10", apertura="2026-10-01", estado="abierta"),
                       _call(id="futura", cierre="2026-11-30"),
                       _call(id="sin-fecha", cierre=None, cierre_tipo="continuo")])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        past = self.item(view, "pasada")
        self.assertEqual(past["estado"], "cerrada")
        self.assertFalse(past["vigente"])
        self.assertEqual(past["dias_restantes"], -10)
        self.assertEqual(self.item(view, "futura")["dias_restantes"], 10)
        self.assertTrue(self.item(view, "futura")["vigente"])
        self.assertIsNone(self.item(view, "sin-fecha")["dias_restantes"])
        self.assertEqual(view["resumen"]["vigentes"], 2)

    def test_ordering(self):
        self.ws.calls([
            _call(id="cerrada-alta", estado="cerrada", puntaje_agente=100),
            _call(id="no-elegible-alta", rol_colombia="no_elegible", puntaje_agente=100),
            _call(id="baja", puntaje_agente=10),
            _call(id="alta-lejana", puntaje_agente=90, cierre="2027-03-01"),
            _call(id="alta-cercana", puntaje_agente=90, cierre="2026-12-01"),
        ])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        self.assertEqual([o["id"] for o in view["oportunidades"]],
                         ["alta-cercana", "alta-lejana", "baja", "no-elegible-alta", "cerrada-alta"])

    def test_combined_score_with_and_without_agent(self):
        self.ws.profile(temas=["energía"], palabras_clave={"es": ["redes eléctricas"], "en": ["machine learning"]})
        self.ws.calls([
            _call(id="con-agente", titulo="Machine learning para energía en redes eléctricas", puntaje_agente=40),
            _call(id="sin-agente", titulo="Machine learning para energía en redes eléctricas", puntaje_agente=None),
        ])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        with_agent, without = self.item(view, "con-agente"), self.item(view, "sin-agente")
        self.assertEqual(without["lexico"], 100)
        self.assertEqual(without["puntaje"], 100)
        self.assertEqual(with_agent["puntaje"], 70)

    def test_lexical_match_across_accents_and_english(self):
        self.ws.profile(temas=["Energía"], palabras_clave={"es": ["optimización"], "en": ["deep learning"]})
        self.ws.calls([
            _call(id="acentos", titulo="ENERGIA y OPTIMIZACION", puntaje_agente=None),
            _call(id="ingles", titulo="Deep Learning Fellowship", puntaje_agente=None),
            _call(id="nada", titulo="Historia del arte", puntaje_agente=None),
        ])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        self.assertEqual(self.item(view, "acentos")["lexico"], 50)
        self.assertEqual(self.item(view, "ingles")["lexico"], 50)
        self.assertEqual(self.item(view, "nada")["lexico"], 0)
        self.assertEqual(view["perfil"]["n_palabras_clave"], 3)

    def test_stopwords_do_not_count(self):
        self.ws.profile(temas=["la energía de los ríos"])
        self.ws.calls([_call(id="stop", titulo="La historia de los mapas", temas=[], puntaje_agente=None)])
        self.assertEqual(self.item(self.mod.vista(self.ws.root, hoy=HOY), "stop")["lexico"], 0)

    def test_text_output_one_line_per_call(self):
        self.ws.calls([_call(id="a"), _call(id="b", titulo="Segunda")])
        result = _cli("datos", str(self.ws.root), "--hoy", "2026-11-20")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn("Segunda", result.stdout)
        self.assertIn("abierta", lines[0])


class RulesTest(Base):
    def test_horizon_europe_is_socio_with_aviso(self):
        self.ws.calls([_call(id="he", financiador="Comisión Europea", programa="Horizon Europe",
                             rol_colombia="lider")])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        call = self.item(view, "he")
        self.assertEqual(call["rol_colombia"], "socio")
        self.assertEqual(call["rol_agente"], "lider")
        self.assertEqual(call["regla"]["id"], "horizon-europe")
        self.assertIn("socio", call["aviso"])
        self.assertIn("regla-rol-distinto", self.codes(view["hallazgos"]))

    def test_msca_global_is_no_elegible(self):
        self.ws.calls([_call(id="msca", financiador="European Commission",
                             programa="HORIZON-MSCA Postdoctoral Fellowships",
                             titulo="MSCA Global Postdoctoral Fellowships 2026", rol_colombia="lider")])
        call = self.item(self.mod.vista(self.ws.root, hoy=HOY), "msca")
        self.assertEqual(call["rol_colombia"], "no_elegible")
        self.assertEqual(call["regla"]["id"], "msca-global")

    def test_georg_forster_is_pausada(self):
        self.ws.calls([_call(id="forster", financiador="Alexander von Humboldt-Stiftung",
                             titulo="Georg Forster Research Fellowship", estado="abierta")])
        call = self.item(self.mod.vista(self.ws.root, hoy=HOY), "forster")
        self.assertEqual(call["estado"], "pausada")
        self.assertFalse(call["vigente"])
        self.assertEqual(call["rol_colombia"], "lider")
        self.assertIn("pausó", call["aviso"])

    def test_a_rule_without_role_keeps_the_agent_role_and_adds_its_notice(self):
        self.ws.calls([_call(id="nih-r01", financiador="National Institutes of Health", programa="R01",
                             rol_colombia="socio"),
                       _call(id="nih-k43", financiador="NIH Fogarty International Center",
                             titulo="Emerging Global Leader Award (K43)", rol_colombia="desconocido")])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        for cid, role in (("nih-r01", "socio"), ("nih-k43", "desconocido")):
            call = self.item(view, cid)
            self.assertEqual(call["rol_colombia"], role, cid)
            self.assertEqual(call["regla"]["id"], "nih", cid)
            self.assertIn("NOT-OD-25-104", call["aviso"], cid)
        self.assertNotIn("regla-rol-distinto", self.codes(view["hallazgos"]))

    def test_rule_never_upgrades_agent_no_elegible(self):
        self.ws.calls([_call(id="he", programa="Horizon Europe", rol_colombia="no_elegible")])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        call = self.item(view, "he")
        self.assertEqual(call["rol_colombia"], "no_elegible")
        self.assertEqual(call["rol_agente"], "no_elegible")
        self.assertEqual(call["regla"]["id"], "horizon-europe")

    def test_no_rule_keeps_agent_role(self):
        self.ws.calls([_call(id="libre", rol_colombia="coaplicante")])
        call = self.item(self.mod.vista(self.ws.root, hoy=HOY), "libre")
        self.assertEqual(call["rol_colombia"], "coaplicante")
        self.assertIsNone(call["regla"])
        self.assertIsNone(call["aviso"])

    def test_rules_file_schema_and_patterns(self):
        data = json.loads(RULES.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "morfeo.reglas-elegibilidad-co/v1")
        roles = {"lider", "socio", "coaplicante", "anfitrion_exterior", "no_elegible"}
        ids = [rule["id"] for rule in data["reglas"]]
        self.assertEqual(len(ids), len(set(ids)))
        for rule in data["reglas"]:
            self.assertIn(rule["rol"], roles | {None}, rule["id"])
            self.assertTrue(rule["aviso"] and rule["fuente_url"].startswith("https://"), rule["id"])


class SourcesTest(Base):
    def test_fuentes_json_lists_minciencias_html(self):
        result = _cli("fuentes", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["schema"], "morfeo.fuentes-convocatorias/v1")
        minciencias = next(f for f in data["fuentes"] if f["id"] == "minciencias")
        self.assertEqual(minciencias["metodo"], "html")
        self.assertIn("10", minciencias["notas"])
        self.assertEqual(self.mod.load_sources(), json.loads(SOURCES.read_text(encoding="utf-8")))

    def test_sources_file_enums(self):
        data = json.loads(SOURCES.read_text(encoding="utf-8"))
        for source in data["fuentes"]:
            self.assertIn(source["metodo"], {"api", "rss", "html", "pdf", "navegador", "busqueda"}, source["id"])
            self.assertIn(source["ambito"], {"colombia", "latam", "internacional"}, source["id"])


if __name__ == "__main__":
    unittest.main()
