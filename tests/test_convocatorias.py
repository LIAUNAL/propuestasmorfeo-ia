"""scripts/convocatorias.py: funding-call profile, validation, Colombian eligibility rules and ranking
(odd/tasks/convocatorias-explorador.md, T1: S2, S3, S4 and the Contracts section; scopes, lab
experience, requirements, effort, weighted match and map from odd/tasks/convocatorias-mapa.md, T1: S2, S3).

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
MANDATORY_SOURCES = [s["id"] for s in json.loads(SOURCES.read_text(encoding="utf-8"))["fuentes"]
                     if s.get("obligatoria") is True]


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
        "fuente": "busqueda:example.org",
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

    def banco(self, **overrides) -> Path:
        data = {"schema": "morfeo.perfil-convocatorias/v1", "actualizado": "2026-11-20", "alcance": "banco",
                "titulo": "Banco LIA", "idea": None, "aplicantes": ["grupo"], "temas": [],
                "palabras_clave": {"es": [], "en": []}, "financiadores_previos": [],
                "idiomas": ["es", "en"], "ambitos": ["colombia", "latam", "internacional"],
                "institucion": {"nombre": None, "pais": "CO", "tipo": None}, "experiencia": []}
        data.update(overrides)
        return self.write("perfil_banco.json", data)

    def calls(self, calls: list[dict], **overrides) -> Path:
        # Every mandatory national source consulted, `n` counting the calls registered from it
        # (odd/tasks/convocatorias-nacional.md, S1).
        consulted = [{"fuente": source_id, "url": f"https://example.org/{source_id}", "fecha": "2026-11-20",
                      "resultado": "ok", "n": sum(1 for c in calls if isinstance(c, dict) and c.get("fuente") == source_id)}
                     for source_id in MANDATORY_SOURCES]
        data = {"schema": "morfeo.oportunidades/v1", "actualizado": "2026-11-20",
                "fuentes_consultadas": consulted, "oportunidades": calls}
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
        # convocatorias-mapa S3 replaces the puntaje ordering with `match`: the far deadline gives
        # alta-lejana a full time component (match 56) while alta-cercana gets 16 (match 43).
        self.ws.calls([
            _call(id="cerrada-alta", estado="cerrada", puntaje_agente=100),
            _call(id="no-elegible-alta", rol_colombia="no_elegible", puntaje_agente=100),
            _call(id="baja", puntaje_agente=10),
            _call(id="alta-lejana", puntaje_agente=90, cierre="2027-03-01"),
            _call(id="alta-cercana", puntaje_agente=90, cierre="2026-12-01"),
        ])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        self.assertEqual([o["id"] for o in view["oportunidades"]],
                         ["alta-lejana", "alta-cercana", "baja", "no-elegible-alta", "cerrada-alta"])
        self.assertEqual([self.item(view, i)["match"] for i in ("alta-lejana", "alta-cercana", "baja")],
                         [56, 43, 33])

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
            self.assertIn(source["metodo"], {"api", "rss", "html", "pdf", "navegador", "busqueda", "sesion"}, source["id"])
            self.assertIn(source["ambito"], {"colombia", "latam", "internacional"}, source["id"])


def _exp(exp_id: str, temas=(), financiadores=(), nombre: str | None = None) -> dict:
    return {"id": exp_id, "nombre": nombre or f"Línea {exp_id}", "detalle": None,
            "temas": list(temas), "financiadores": list(financiadores)}


class ScopeProfileTest(Base):
    """convocatorias-mapa S2: the two profiles and `perfil --alcance`."""

    def test_perfil_alcance_banco_creates_banco_file_and_never_overwrites(self):
        (self.ws.root / "idea.md").write_text("Pérdidas de energía en redes rurales.\n", encoding="utf-8")
        result = _cli("perfil", str(self.ws.run), "--alcance", "banco")
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.ws.root.resolve() / "convocatorias" / "perfil_banco.json"
        self.assertIn(str(target), result.stdout)
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "morfeo.perfil-convocatorias/v1")
        self.assertEqual(data["alcance"], "banco")
        self.assertEqual(data["titulo"], "Plataforma de IA para energía")
        self.assertIsNone(data["idea"])
        self.assertEqual(data["experiencia"], [])
        self.assertFalse((self.ws.root / "convocatorias" / "perfil.json").exists())
        target.write_text(json.dumps(dict(data, temas=["visión"]), ensure_ascii=False), encoding="utf-8")
        before = target.read_text(encoding="utf-8")
        again = _cli("perfil", str(self.ws.root), "--alcance", "banco")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("ya existe", again.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), before)
        self.assertEqual(self.mod.init_profile(self.ws.root, alcance="banco"), (target, False))
        self.assertEqual(self.codes(self.mod.check(self.ws.root), "error"), [])

    def test_perfil_default_is_proyecto_with_alcance(self):
        (self.ws.root / "idea.md").write_text("Pérdidas de energía en redes rurales.\n", encoding="utf-8")
        path, created = self.mod.init_profile(self.ws.root)
        self.assertTrue(created)
        self.assertEqual(path.name, "perfil.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["alcance"], "proyecto")
        self.assertEqual(data["experiencia"], [])
        self.assertIn("Pérdidas de energía", data["idea"])
        self.assertFalse((self.ws.root / "convocatorias" / "perfil_banco.json").exists())

    def test_view_carries_the_profile_title_of_the_scope(self):
        self.ws.profile(titulo="IA para redes rurales")
        self.ws.banco(titulo="Laboratorio de IA")
        self.ws.calls([])
        self.assertEqual(self.mod.vista(self.ws.root, hoy=HOY)["perfil"]["titulo"], "IA para redes rurales")
        self.assertEqual(self.mod.vista(self.ws.root, hoy=HOY, alcance="banco")["perfil"]["titulo"], "Laboratorio de IA")

    def test_invalid_alcance_is_exit_2(self):
        for args in (("perfil", str(self.ws.root), "--alcance", "todo"),
                     ("datos", str(self.ws.root), "--alcance", "todo")):
            result = _cli(*args)
            self.assertEqual(result.returncode, 2, args)
        self.assertFalse((self.ws.root / "convocatorias").exists())
        with self.assertRaises(self.mod.InputError):
            self.mod.vista(self.ws.root, hoy=HOY, alcance="todo")
        with self.assertRaises(self.mod.InputError):
            self.mod.init_profile(self.ws.root, alcance="todo")


class ScopeViewTest(Base):
    """convocatorias-mapa S2/S3: `datos --alcance` and the top-level scope keys."""

    def test_datos_scores_against_the_chosen_profile(self):
        self.ws.profile(temas=["historia del arte"])
        self.ws.banco(temas=["visión por computador"])
        self.ws.calls([_call(id="vision", titulo="Visión por computador aplicada", puntaje_agente=None)])
        proyecto = self.mod.vista(self.ws.root, hoy=HOY)
        self.assertEqual(proyecto["alcance"], "proyecto")
        self.assertEqual(proyecto["perfil"]["alcance"], "proyecto")
        self.assertEqual(self.item(proyecto, "vision")["lexico"], 0)
        banco = self.mod.vista(self.ws.root, hoy=HOY, alcance="banco")
        self.assertEqual(banco["alcance"], "banco")
        self.assertEqual(banco["perfil"]["alcance"], "banco")
        self.assertEqual(self.item(banco, "vision")["lexico"], 100)
        for view in (proyecto, banco):
            self.assertEqual(view["perfiles"], {"proyecto": True, "banco": True})
        result = _cli("datos", str(self.ws.run), "--alcance", "banco", "--json", "--hoy", "2026-11-20")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["alcance"], "banco")
        self.assertEqual(self.item(data, "vision")["lexico"], 100)

    def test_default_is_banco_when_only_banco_exists(self):
        self.ws.banco(temas=["visión por computador"])
        self.ws.calls([_call(id="vision", titulo="Visión por computador", puntaje_agente=None)])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        self.assertEqual(view["alcance"], "banco")
        self.assertEqual(view["perfiles"], {"proyecto": False, "banco": True})
        self.assertTrue(view["perfil"]["existe"])
        self.assertEqual(self.item(view, "vision")["lexico"], 100)
        result = _cli("datos", str(self.ws.root), "--json", "--hoy", "2026-11-20")
        self.assertEqual(json.loads(result.stdout)["alcance"], "banco")

    def test_default_is_proyecto_without_profiles(self):
        view = self.mod.vista(self.ws.root, hoy=HOY)
        self.assertEqual(view["alcance"], "proyecto")
        self.assertEqual(view["perfil"]["alcance"], "proyecto")
        self.assertEqual(view["perfiles"], {"proyecto": False, "banco": False})
        self.assertEqual(view["mapa"], {"temas": [], "experiencia": []})

    def test_requested_scope_without_its_profile_is_reported(self):
        self.ws.profile()
        view = self.mod.vista(self.ws.root, hoy=HOY, alcance="banco")
        self.assertEqual(view["alcance"], "banco")
        self.assertFalse(view["perfil"]["existe"])
        self.assertIn("sin-perfil", self.codes(view["hallazgos"], "info"))


class CheckMapFieldsTest(Base):
    """convocatorias-mapa S2: `check` over the new optional profile and call fields."""

    def full_call(self, **overrides) -> dict:
        fields = {"titulo_corto": "Convocatoria corta", "esfuerzo": "alto", "relacionados_banco": ["vision-lia"],
                  "requisitos": [{"tipo": "consorcio", "estado": "por_verificar", "texto": "Consorcio de tres países."},
                                 {"tipo": "idioma", "estado": "cumple", "texto": "Propuesta en inglés."}]}
        fields.update(overrides)
        return _call(**fields)

    def assert_check(self, severity, code, calls=None, **profile_overrides):
        self.ws.profile(**{"alcance": "proyecto", "experiencia": [_exp("vision-lia", ["visión"])],
                           **profile_overrides})
        self.ws.calls(calls if calls is not None else [self.full_call()])
        findings = self.mod.check(self.ws.root)
        self.assertIn(code, self.codes(findings, severity), findings)
        result = _cli("check", str(self.ws.root))
        self.assertEqual(result.returncode, 1 if severity == "error" else 0, result.stdout + result.stderr)
        self.assertIn(f"{severity} {code}", result.stdout)

    def test_accepts_the_new_fields(self):
        self.ws.profile(alcance="proyecto", experiencia=[_exp("vision-lia", ["visión"], ["Minciencias"])])
        self.ws.banco(experiencia=[_exp("salud-lia", ["salud"])])
        self.ws.calls([self.full_call(), self.full_call(id="dos", relacionados_banco=["salud-lia"],
                                                      url="https://example.org/c2")])
        findings = self.mod.check(self.ws.root)
        self.assertEqual(self.codes(findings, "error"), [])
        self.assertNotIn("experiencia-desconocida", self.codes(findings))
        self.assertEqual(_cli("check", str(self.ws.root)).returncode, 0)

    def test_rejects_bad_call_values(self):
        cases = [
            ("texto-largo", self.full_call(titulo_corto="x" * 33)),
            ("valor-invalido", self.full_call(titulo_corto=12)),
            ("valor-invalido", self.full_call(esfuerzo="enorme")),
            ("valor-invalido", self.full_call(requisitos=[{"tipo": "visa", "estado": "cumple", "texto": "t"}])),
            ("valor-invalido", self.full_call(requisitos=[{"tipo": "aval", "estado": "quizas", "texto": "t"}])),
            ("texto-largo", self.full_call(requisitos=[{"tipo": "aval", "estado": "cumple", "texto": "y" * 201}])),
            ("campo-faltante", self.full_call(requisitos=[{"tipo": "aval", "estado": "cumple"}])),
            ("valor-invalido", self.full_call(requisitos="consorcio")),
            ("valor-invalido", self.full_call(relacionados_banco="vision-lia")),
        ]
        for code, call in cases:
            with self.subTest(code=code, call={k: call.get(k) for k in
                                                ("titulo_corto", "esfuerzo", "requisitos", "relacionados_banco")}):
                self.assert_check("error", code, [call])

    def test_rejects_bad_profile_values(self):
        self.assert_check("error", "valor-invalido", alcance="mundo")
        self.ws.profile(experiencia=[_exp("Vision LIA"), _exp("ok"), _exp("ok"), {"id": "sin-nombre", "temas": "x"}])
        codes = self.codes(self.mod.check(self.ws.root), "error")
        for code in ("id-invalido", "id-repetido", "campo-faltante", "valor-invalido"):
            self.assertIn(code, codes)
        self.ws.profile()
        self.ws.banco(alcance="banco", experiencia="no-lista")
        self.assertIn("valor-invalido", self.codes(self.mod.check(self.ws.root), "error"))

    def test_unknown_relacionados_banco_is_a_warning(self):
        self.assert_check("warning", "experiencia-desconocida", [self.full_call(relacionados_banco=["no-existe"])])


class MapViewTest(Base):
    """convocatorias-mapa S3: per-call scores, alerts and the map in the view."""

    def view(self, calls, **profile_overrides):
        if profile_overrides:
            self.ws.profile(**profile_overrides)
        self.ws.calls(calls)
        return self.mod.vista(self.ws.root, hoy=HOY)

    def test_titulo_corto_given_or_derived_at_a_word_boundary(self):
        view = self.view([
            _call(id="dada", titulo="Un título larguísimo que no se recorta nunca", titulo_corto="MSCA Staff Exchanges"),
            _call(id="corta", titulo="Fulbright Scholar"),
            _call(id="larga", titulo="Programa de becas para investigación avanzada"),
            _call(id="justa", titulo="abcdefghij abcdefghij abcdef xyz"),
            _call(id="palabra", titulo="Supercalifragilisticoespialidoso de verdad"),
        ])
        self.assertEqual(self.item(view, "dada")["titulo_corto"], "MSCA Staff Exchanges")
        self.assertEqual(self.item(view, "corta")["titulo_corto"], "Fulbright Scholar")
        self.assertEqual(self.item(view, "larga")["titulo_corto"], "Programa de becas para…")
        self.assertEqual(self.item(view, "justa")["titulo_corto"], "abcdefghij abcdefghij abcdef…")
        self.assertEqual(self.item(view, "palabra")["titulo_corto"], "Supercalifragilisticoespiali…")
        for call in view["oportunidades"]:
            self.assertLessEqual(len(call["titulo_corto"].rstrip("…")), 28 if call["id"] != "dada" else 32)

    def test_temas_match_is_accent_insensitive_with_peso(self):
        view = self.view([_call(id="c", titulo="ENERGIA para VISION POR COMPUTADOR", temas=["redes"])],
                         temas=["Energía renovable", "Visión por computador", "Salud pública",
                                "redes neuronales profundas"])
        self.assertEqual(self.item(view, "c")["temas_match"],
                         [{"tema": "Visión por computador", "peso": 1.0}, {"tema": "Energía renovable", "peso": 0.5}])

    def test_experiencia_via_temas_and_relacionados_banco(self):
        view = self.view(
            [_call(id="c", titulo="Visión por computador", relacionados_banco=["salud-lia", "desconocida"]),
             _call(id="otra", titulo="Historia del arte")],
            temas=["visión por computador"],
            experiencia=[_exp("vision-lia", ["VISION POR COMPUTADOR"]), _exp("salud-lia", ["salud pública"]),
                         _exp("agro-lia", ["agricultura"])])
        self.assertEqual(self.item(view, "c")["experiencia"], ["vision-lia", "salud-lia"])
        self.assertEqual(self.item(view, "otra")["experiencia"], [])

    def test_historial_via_financiadores_previos_and_experiencia(self):
        view = self.view(
            [_call(id="previo", financiador="MINCIENCIAS Colombia"),
             _call(id="experiencia", financiador="Comision Europea"),
             _call(id="nuevo", financiador="Fundación Desconocida")],
            financiadores_previos=["Minciencias"],
            experiencia=[_exp("e1", financiadores=["Comisión Europea"])])
        self.assertTrue(self.item(view, "previo")["historial"])
        self.assertTrue(self.item(view, "experiencia")["historial"])
        self.assertFalse(self.item(view, "nuevo")["historial"])

    def test_componente_tematica_and_experiencia(self):
        experiencia = [_exp(f"e{i}", ["visión por computador"]) for i in range(1, 5)]
        calls = [_call(id="previo", titulo="Visión por computador", financiador="Minciencias"),
                 _call(id="nuevo", titulo="Visión por computador", financiador="Otro")]
        for items, previo, nuevo in ((experiencia, 100, 100), (experiencia[:2], 85, 60), (experiencia[:1], 55, 30)):
            view = self.view(calls, temas=["visión por computador"], financiadores_previos=["Minciencias"],
                             experiencia=items)
            self.assertEqual(self.item(view, "previo")["componentes"]["experiencia"], previo, len(items))
            self.assertEqual(self.item(view, "nuevo")["componentes"]["experiencia"], nuevo, len(items))
            for call in view["oportunidades"]:
                self.assertEqual(call["componentes"]["tematica"], call["puntaje"])

    def test_componente_elegibilidad_by_final_role(self):
        expected = {"lider": 100, "socio": 70, "coaplicante": 70, "anfitrion_exterior": 40,
                    "desconocido": 50, "no_elegible": 0}
        view = self.view([_call(id=role.replace("_", "-"), rol_colombia=role) for role in expected])
        for role, value in expected.items():
            self.assertEqual(self.item(view, role.replace("_", "-"))["componentes"]["elegibilidad"], value, role)
        horizon = self.view([_call(id="he", programa="Horizon Europe", rol_colombia="lider")])
        self.assertEqual(self.item(horizon, "he")["componentes"]["elegibilidad"], 70)

    def test_componente_tiempo(self):
        view = self.view([
            _call(id="cerrada", cierre="2026-11-10"),
            _call(id="pausada", estado="pausada"),
            _call(id="sin-cierre", cierre=None, cierre_tipo="continuo"),
            _call(id="bajo", esfuerzo="bajo", cierre="2026-11-30"),
            _call(id="alto", esfuerzo="alto", cierre="2027-03-20"),
            _call(id="medio-lejos", cierre="2027-02-28"),
        ])
        expected = {"cerrada": 0, "pausada": 10, "sin-cierre": 50, "bajo": 44, "alto": 89, "medio-lejos": 100}
        for call_id, value in expected.items():
            self.assertEqual(self.item(view, call_id)["componentes"]["tiempo"], value, call_id)

    def test_match_weights_and_cap(self):
        view = self.view([
            _call(id="base", puntaje_agente=80),
            _call(id="no-elegible", puntaje_agente=80, rol_colombia="no_elegible"),
            _call(id="cerrada", puntaje_agente=100, estado="cerrada"),
        ])
        base = self.item(view, "base")
        self.assertEqual(base["componentes"], {"tematica": 40, "experiencia": 0, "elegibilidad": 100, "tiempo": 44})
        self.assertEqual(base["match"], 46)
        self.assertEqual(self.item(view, "no-elegible")["match"], 20)
        self.assertEqual(self.item(view, "cerrada")["match"], 20)
        self.assertEqual(self.item(view, "cerrada")["puntaje"], 50)

    def test_esfuerzo_and_preparar_desde(self):
        view = self.view([_call(id="bajo", esfuerzo="bajo"), _call(id="alto", esfuerzo="alto"),
                          _call(id="medio"), _call(id="sin-cierre", cierre=None)])
        self.assertEqual(self.item(view, "bajo")["preparar_desde"], "2026-12-05")
        self.assertEqual(self.item(view, "alto")["preparar_desde"], "2026-09-21")
        self.assertEqual(self.item(view, "medio")["esfuerzo"], "medio")
        self.assertEqual(self.item(view, "medio")["preparar_desde"], "2026-11-05")
        self.assertIsNone(self.item(view, "sin-cierre")["preparar_desde"])

    def test_alertas(self):
        view = self.view([
            _call(id="requisitos", cierre="2026-11-30", requisitos=[
                {"tipo": "consorcio", "estado": "no_cumple", "texto": "Exige consorcio de tres países."},
                {"tipo": "idioma", "estado": "por_verificar", "texto": "Propuesta en inglés."},
                {"tipo": "aval", "estado": "cumple", "texto": "Aval institucional."}]),
            _call(id="estimado", cierre="2027-06-01", cierre_tipo="estimado"),
            _call(id="sin-fecha", cierre=None, cierre_tipo="desconocido"),
            _call(id="pausada", estado="pausada", cierre=None),
            _call(id="holgada", cierre="2027-06-01"),
            _call(id="he", programa="Horizon Europe", rol_colombia="lider", cierre="2027-06-01"),
        ])
        self.assertEqual(self.item(view, "requisitos")["alertas"], [
            {"severidad": "error", "texto": "Cierra en 10 días y el esfuerzo estimado es medio (unos 45 días)"},
            {"severidad": "error", "texto": "Exige consorcio de tres países."},
            {"severidad": "warning", "texto": "Propuesta en inglés."},
        ])
        self.assertEqual(self.item(view, "estimado")["alertas"], [{"severidad": "info", "texto": "Cierre estimado"}])
        self.assertEqual(self.item(view, "sin-fecha")["alertas"],
                         [{"severidad": "info", "texto": "Sin fecha de cierre publicada"}])
        self.assertEqual(self.item(view, "pausada")["alertas"], [{"severidad": "error", "texto": "Programa pausado"}])
        self.assertEqual(self.item(view, "holgada")["alertas"], [])
        horizon = self.item(view, "he")
        self.assertTrue(horizon["aviso"])
        self.assertEqual(horizon["alertas"], [])

    def test_mapa_counts(self):
        view = self.view(
            [_call(id="c1", titulo="Energía renovable y visión por computador"),
             _call(id="c2", titulo="Energía renovable rural"),
             _call(id="c3", titulo="Historia del arte", relacionados_banco=["e2"])],
            temas=["Energía renovable", "Visión por computador", "Salud pública"],
            experiencia=[_exp("e1", ["energia renovable"]), _exp("e2", ["salud publica"], nombre="Salud LIA")])
        self.assertEqual(view["mapa"]["temas"], [{"tema": "Energía renovable", "n": 2},
                                                 {"tema": "Visión por computador", "n": 1},
                                                 {"tema": "Salud pública", "n": 0}])
        self.assertEqual([(e["id"], e["n"]) for e in view["mapa"]["experiencia"]], [("e1", 2), ("e2", 1)])
        self.assertEqual(view["mapa"]["experiencia"][1]["nombre"], "Salud LIA")
        self.assertEqual(view["mapa"]["experiencia"][1]["temas"], ["salud publica"])

    def test_ordering_by_match(self):
        view = self.view([
            _call(id="cerrada", estado="cerrada", puntaje_agente=100),
            _call(id="no-elegible", rol_colombia="no_elegible", puntaje_agente=100, cierre="2027-03-01"),
            _call(id="desconocido-hoy", rol_colombia="desconocido", puntaje_agente=0, cierre="2026-11-20"),
            _call(id="lider-cercana", puntaje_agente=100, cierre="2026-11-21"),
            _call(id="lider-lejana", puntaje_agente=60, cierre="2027-03-01"),
            _call(id="lider-lejana-antes", puntaje_agente=60, cierre="2027-02-28"),
        ])
        self.assertEqual([o["id"] for o in view["oportunidades"]],
                         ["lider-lejana-antes", "lider-lejana", "lider-cercana", "desconocido-hoy",
                          "no-elegible", "cerrada"])
        self.assertEqual([o["match"] for o in view["oportunidades"]], [51, 51, 43, 13, 20, 20])
        self.assertGreater(self.item(view, "lider-cercana")["puntaje"], self.item(view, "lider-lejana")["puntaje"])

    def test_old_files_without_the_new_fields_still_give_a_valid_view(self):
        self.ws.profile(temas=["energía"])
        self.ws.calls([_call(id="vieja", titulo="Energía para todos", puntaje_agente=40, cierre="2027-06-01")])
        self.assertEqual(self.codes(self.mod.check(self.ws.root), "error"), [])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        call = self.item(view, "vieja")
        for key in ("estado", "dias_restantes", "vigente", "rol_colombia", "rol_agente", "regla", "aviso",
                    "lexico", "puntaje"):
            self.assertIn(key, call)
        self.assertEqual(call["puntaje"], 70)
        self.assertEqual(call["titulo_corto"], "Energía para todos")
        self.assertEqual(call["temas_match"], [{"tema": "energía", "peso": 1.0}])
        self.assertEqual(call["experiencia"], [])
        self.assertFalse(call["historial"])
        self.assertEqual(call["esfuerzo"], "medio")
        self.assertEqual(set(call["componentes"]), {"tematica", "experiencia", "elegibilidad", "tiempo"})
        self.assertIsInstance(call["match"], int)
        self.assertEqual(call["alertas"], [])
        self.assertEqual(view["alcance"], "proyecto")
        self.assertEqual(view["perfil"]["alcance"], "proyecto")
        self.assertEqual(view["mapa"], {"temas": [{"tema": "energía", "n": 1}], "experiencia": []})
        result = _cli("datos", str(self.ws.root), "--hoy", "2026-11-20")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Energía para todos", result.stdout)


if __name__ == "__main__":
    unittest.main()
