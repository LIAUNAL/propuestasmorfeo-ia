"""The «Convocatorias» constellation drawn with the SOTA 3D viewer
(odd/tasks/tablero-juez-novedad.md, T7, S7).

`scripts/convocatorias.py` maps the view (`morfeo.convocatorias-vista/v1`) to
an atlas-shaped scene: one system per call, one for the search profile and
one per banco LIA line the old map drew; families are the panel's groups and
links its affinity relations. `scripts/render_atlas.py` draws it with the
"convocatorias" scene profile, and `/api/convocatorias/atlas` serves the
page. The SOTA profile keeps its exact output (pinned by the SOTA tests).
The click behavior of the page is pinned under jsdom in
``tests/js/convocatorias-atlas.test.mjs``.

Stdlib only, offline.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from morfeo.core import value_chain  # noqa: E402
from morfeo.core.opportunities import render_opportunities_atlas  # noqa: E402

DATA_OPEN = '<script type="application/json" id="atlas-data">'


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONV = load(REPO / "scripts" / "convocatorias.py", "conv_atlas_under_test")
RENDER = load(REPO / "scripts" / "render_atlas.py", "render_atlas_conv_under_test")


def scene_of(page: str) -> dict:
    start = page.index(DATA_OPEN) + len(DATA_OPEN)
    return json.loads(page[start:page.index("</script>", start)])


def call(**overrides) -> dict:
    base = {
        "id": "sgr-salud", "titulo": "Convocatoria SGR CTeI · Salud y bienestar regional",
        "titulo_corto": "SGR Salud regional", "financiador": "Minciencias", "programa": "Asignación CTeI",
        "url": "https://minciencias.gov.co/sgr", "ambito": "colombia", "idioma": "es",
        "aplicantes": ["universidad", "grupo"], "rol_colombia": "lider", "aviso": None, "estado": "abierta",
        "apertura": "2026-10-23", "cierre": "2026-12-11", "cierre_tipo": "fijo", "dias_restantes": 21,
        "vigente": True, "monto": {"min": None, "max": 4500000000, "moneda": "COP"},
        "elegibilidad": "Universidades colombianas con grupo reconocido.",
        "evidencia": [{"texto": "Términos de referencia", "url": "https://minciencias.gov.co/tdr.pdf"}],
        "match": 78, "puntaje": 70,
        "temas_match": [{"tema": "salud mental", "peso": 1}, {"tema": "eeg", "peso": 0.5}],
        "experiencia": ["lia-eeg", "lia-salud"], "esfuerzo": "alto", "preparar_desde": "2026-09-12",
    }
    base.update(overrides)
    return base


CALLS = [
    call(),
    call(id="horizon-cl1", titulo="Horizon Europe Cluster 1 · Mental health", titulo_corto="Horizon CL1",
         financiador="Comisión Europea", ambito="internacional", idioma="en", rol_colombia="socio",
         aviso="Participa como socio financiado.", match=64, monto={}, elegibilidad=None, evidencia=[],
         temas_match=[{"tema": "eeg", "peso": 0.6}, {"tema": "salud mental", "peso": 0.9}], experiencia=["lia-dl"]),
    call(id="msca-global", titulo="MSCA Global Postdoctoral Fellowships", titulo_corto="MSCA Global PF",
         financiador="Comisión Europea", ambito="internacional", rol_colombia="no_elegible", match=18,
         temas_match=[], experiencia=[], url="javascript:alert(1)", evidencia=[], monto=None, elegibilidad=None),
    call(id="sin-ambito", titulo="Otra convocatoria", titulo_corto="Otra", ambito="marte", rol_colombia="raro",
         match=None, puntaje=40, temas_match=[{"tema": "Educación", "peso": 1}], experiencia=[], evidencia=[]),
]

MAPA = {
    "temas": [{"tema": "salud mental", "n": 2}, {"tema": "eeg", "n": 2}, {"tema": "educacion", "n": 1}],
    "experiencia": [
        {"id": "lia-eeg", "nombre": "Análisis de EEG", "detalle": "Proyectos con Minciencias",
         "temas": ["eeg"], "financiadores": ["Minciencias"], "n": 1},
        {"id": "lia-salud", "nombre": "Salud digital", "detalle": None, "temas": ["salud mental"],
         "financiadores": [], "n": 1},
        {"id": "lia-dl", "nombre": "Aprendizaje profundo", "detalle": None, "temas": [], "financiadores": [], "n": 1},
    ],
}


def vista(**overrides) -> dict:
    base = {
        "schema": "morfeo.convocatorias-vista/v1", "hoy": "2026-11-20", "alcance": "proyecto",
        "perfil": {"existe": True, "alcance": "proyecto", "titulo": "IA para la detección temprana de depresión",
                   "aplicantes": ["investigador"], "idiomas": ["es", "en"], "ambitos": ["colombia"],
                   "n_palabras_clave": 6},
        "oportunidades": CALLS, "mapa": MAPA,
    }
    base.update(overrides)
    return base


def systems(built: dict) -> dict:
    return {s["id"]: s for s in built["atlas"]["systems"]}


def slots(system: dict) -> list[str]:
    return [p["slot"] for p in system["planets"]]


def family(system: dict) -> str:
    return next(p["label"] for p in system["planets"] if p["slot"] == "family")


class TestSceneBuilder(unittest.TestCase):
    def test_one_system_per_call_one_for_the_profile_and_one_per_banco_line(self):
        built = CONV.atlas_de_vista(vista())
        ids = sorted(systems(built))
        self.assertEqual(ids, sorted(["cv-sgr-salud", "cv-horizon-cl1", "cv-msca-global", "cv-sin-ambito",
                                      "perfil", "exp-lia-eeg", "exp-lia-salud", "exp-lia-dl"]))
        kinds = {sid: s["kind"] for sid, s in systems(built).items()}
        self.assertEqual(kinds["cv-sgr-salud"], "convocatoria")
        self.assertEqual(kinds["perfil"], "perfil")
        self.assertEqual(kinds["exp-lia-dl"], "experiencia")
        self.assertEqual(systems(built)["cv-sgr-salud"]["call_id"], "sgr-salud")
        self.assertEqual(built["schema"], "morfeo.convocatorias-constelacion/v1")
        self.assertEqual((built["total"], built["mostradas"]), (4, 4))

    def test_a_call_carries_planets_only_for_the_base_fields_it_has(self):
        full = systems(CONV.atlas_de_vista(vista()))["cv-sgr-salud"]
        self.assertEqual(slots(full), ["sun", "funder", "region", "amount", "deadline", "role", "eligibility",
                                       "topic", "topic", "family", "evidence", "link"])
        sun = full["planets"][0]
        self.assertEqual(sun["label"], "SGR Salud regional")
        self.assertEqual(full["title"], "Convocatoria SGR CTeI · Salud y bienestar regional")
        planet = {p["slot"]: p for p in full["planets"]}
        self.assertEqual(planet["funder"]["label"], "Minciencias")
        self.assertEqual(planet["region"]["label"], "Colombia")
        self.assertEqual(planet["amount"]["label"], "Hasta 4.500.000.000 COP")
        self.assertEqual(planet["deadline"]["label"], "Cierra en 21 d")
        self.assertIn("2026-12-11", planet["deadline"]["detail"])
        self.assertEqual(planet["role"]["label"], "Puede liderar")
        self.assertEqual(planet["link"]["evidence"]["origin"], "https://minciencias.gov.co/sgr")
        self.assertEqual(planet["evidence"]["evidence"], {"origin": "https://minciencias.gov.co/tdr.pdf",
                                                         "quote": "Términos de referencia"})
        bare = systems(CONV.atlas_de_vista(vista()))["cv-msca-global"]
        self.assertEqual(slots(bare), ["sun", "funder", "region", "deadline", "role", "family"],
                         "no monto, elegibilidad, temas, evidencia or http(s) link: no planets for them")
        self.assertNotIn("origin", bare["planets"][0].get("evidence") or {}, "a javascript: url never travels")
        facts = CONV.atlas_de_vista(vista())["fichas"]
        self.assertNotIn("link", facts["cv-msca-global"])
        self.assertEqual(facts["cv-sgr-salud"]["link"], "https://minciencias.gov.co/sgr")
        self.assertEqual(facts["cv-sgr-salud"]["match"], "78/100")
        self.assertEqual(facts["cv-sgr-salud"]["aplicantes"], "Universidad, Grupo de investigación")

    def test_a_call_without_short_title_gets_the_script_fallback(self):
        built = CONV.atlas_de_vista(vista(oportunidades=[call(id="horizon-cl1", titulo_corto=None,
                                                              titulo="Horizon Europe Cluster 1 · Mental health")]))
        self.assertEqual(systems(built)["cv-horizon-cl1"]["planets"][0]["label"], "Horizon Europe Cluster 1…")

    def test_deadline_urgency_follows_the_map(self):
        def label(**kw):
            built = CONV.atlas_de_vista(vista(oportunidades=[call(**kw)]))
            return next(p["label"] for p in systems(built)["cv-sgr-salud"]["planets"] if p["slot"] == "deadline")
        self.assertEqual(label(dias_restantes=0), "Cierra hoy")
        self.assertEqual(label(dias_restantes=None, cierre=None), "Sin fecha")
        self.assertEqual(label(vigente=False, estado="cerrada"), "Cerrada")
        self.assertEqual(label(vigente=False, estado="pausada"), "Pausada")

    def test_families_are_the_panel_groups_for_each_grouping(self):
        def families(agrupar):
            return {sid: family(s) for sid, s in systems(CONV.atlas_de_vista(vista(), agrupar=agrupar)).items()
                    if s["kind"] == "convocatoria"}
        # tema: the heaviest matched tema, named and capitalised as the profile names it
        # («Educación» folds to the profile's «educacion»); none means «Sin tema del perfil».
        self.assertEqual(families("tema"), {"cv-sgr-salud": "Salud mental", "cv-horizon-cl1": "Salud mental",
                                            "cv-msca-global": "Sin tema del perfil", "cv-sin-ambito": "Educacion"})
        self.assertEqual(families("ambito"), {"cv-sgr-salud": "Colombia", "cv-horizon-cl1": "Internacional",
                                              "cv-msca-global": "Internacional", "cv-sin-ambito": "Otro ámbito"})
        self.assertEqual(families("rol"), {"cv-sgr-salud": "Puede liderar", "cv-horizon-cl1": "Solo como socio",
                                           "cv-msca-global": "No elegible desde Colombia",
                                           "cv-sin-ambito": "Rol por confirmar"})
        built = systems(CONV.atlas_de_vista(vista()))
        self.assertEqual(family(built["perfil"]), "Proyecto en formulación")
        self.assertEqual(family(built["exp-lia-eeg"]), "Experiencia del banco LIA")
        with self.assertRaises(CONV.InputError):
            CONV.atlas_de_vista(vista(), agrupar="color")

    def test_links_are_the_affinity_relations_of_the_map(self):
        links = {(l["from_system"], l["from"], l["to_system"], l["to"], l["rel"])
                 for l in CONV.atlas_de_vista(vista())["atlas"]["links"]}
        perfil = systems(CONV.atlas_de_vista(vista()))["perfil"]
        tema_id = {p["label"]: p["id"] for p in perfil["planets"] if p["slot"] == "topic"}
        self.assertEqual(sorted(tema_id), ["Educacion", "Eeg", "Salud mental"])
        sgr = systems(CONV.atlas_de_vista(vista()))["cv-sgr-salud"]
        sgr_tema = {p["label"]: p["id"] for p in sgr["planets"] if p["slot"] == "topic"}
        self.assertIn(("perfil", tema_id["Salud mental"], "cv-sgr-salud", sgr_tema["Salud mental"], "afinidad"), links)
        self.assertIn(("perfil", tema_id["Eeg"], "cv-sgr-salud", sgr_tema["Eeg"], "afinidad"), links)
        self.assertIn(("exp-lia-eeg", "sun", "cv-sgr-salud", "sun", "experiencia"), links)
        self.assertIn(("exp-lia-salud", "sun", "cv-sgr-salud", "sun", "experiencia"), links)
        self.assertIn(("exp-lia-dl", "sun", "cv-horizon-cl1", "sun", "experiencia"), links)
        self.assertFalse(any(l[2] == "cv-msca-global" for l in links), "a call with no temas or experiencia stays alone")
        # «Educación» folds to the profile tema «educacion».
        self.assertTrue(any(l[2] == "cv-sin-ambito" and l[0] == "perfil" for l in links))
        self.assertEqual(len(links), 8)

    def test_ids_keep_only_the_calls_the_filters_left(self):
        built = CONV.atlas_de_vista(vista(), ids=["horizon-cl1"])
        self.assertEqual(sorted(s for s in systems(built) if s.startswith("cv-")), ["cv-horizon-cl1"])
        self.assertEqual((built["total"], built["mostradas"]), (4, 1))
        self.assertIn("perfil", systems(built))

    def test_at_most_twelve_banco_lines_busiest_first(self):
        many = [{"id": f"lia-{i}", "nombre": f"Línea {i}", "temas": [], "n": i % 4} for i in range(20)]
        built = CONV.atlas_de_vista(vista(mapa={"temas": MAPA["temas"], "experiencia": many}))
        shown = [sid for sid in systems(built) if sid.startswith("exp-")]
        self.assertEqual(len(shown), 12)
        self.assertIn("exp-lia-3", shown)
        self.assertNotIn("exp-lia-0", shown)

    def test_the_profile_system_carries_the_idea_and_the_banco_scope(self):
        built = CONV.atlas_de_vista(vista(), idea="Detectar depresión con EEG portátil.")
        perfil = systems(built)["perfil"]
        self.assertEqual(perfil["planets"][0]["label"], "IA para la detección temprana de depresión")
        idea = next(p for p in perfil["planets"] if p["slot"] == "idea")
        self.assertEqual(idea["label"], "Detectar depresión con EEG portátil.")
        long_idea = "palabra " * 60
        idea = next(p for p in systems(CONV.atlas_de_vista(vista(), idea=long_idea))["perfil"]["planets"]
                    if p["slot"] == "idea")
        self.assertTrue(idea["label"].endswith("…") and len(idea["label"]) <= 120)
        self.assertEqual(idea["detail"], long_idea.strip(), "the whole idea stays in the detail")
        banco = systems(CONV.atlas_de_vista(vista(alcance="banco", perfil={"existe": False})))
        self.assertEqual(banco["perfil"]["planets"][0]["label"], "Banco LIA")
        self.assertEqual(family(banco["perfil"]), "Banco LIA")
        self.assertNotIn("idea", slots(banco["perfil"]))

    def test_constelacion_reads_the_workspace_and_its_idea(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / ".morfeo").mkdir()
            (ws / ".morfeo" / "config.json").write_text("{}", encoding="utf-8")
            (ws / "convocatorias").mkdir()
            (ws / "convocatorias" / "perfil.json").write_text(json.dumps({
                "schema": "morfeo.perfil-convocatorias/v1", "alcance": "proyecto", "titulo": "Demo",
                "idea": "Una idea corta.", "temas": ["salud"], "aplicantes": ["investigador"]}), encoding="utf-8")
            (ws / "convocatorias" / "oportunidades.json").write_text(json.dumps({
                "schema": "morfeo.oportunidades/v1", "oportunidades": [{
                    "id": "c1", "titulo": "Salud digital", "financiador": "F", "url": "https://f.org", "ambito": "colombia",
                    "temas": ["salud"], "cierre": "2027-01-10", "estado": "abierta"}]}), encoding="utf-8")
            before = sorted(p.name for p in ws.rglob("*"))
            built = CONV.constelacion(ws, hoy=CONV.datetime.date(2026, 11, 20))
            self.assertEqual(sorted(p.name for p in ws.rglob("*")), before, "never writes")
        perfil = systems(built)["perfil"]
        self.assertEqual(next(p for p in perfil["planets"] if p["slot"] == "idea")["label"], "Una idea corta.")
        self.assertIn("cv-c1", systems(built))
        self.assertEqual(family(systems(built)["cv-c1"]), "Salud")


HOSTILE = '<img src=x onerror="window.__pwned=1"></script><script>window.__pwned=1</script>'


class TestConvocatoriasProfile(unittest.TestCase):
    def page(self, view=None, **kw):
        built = CONV.atlas_de_vista(view or vista(), **kw)
        return RENDER.render(built["atlas"], viewer="/* viewer */", papers=built["fichas"],
                             profile="convocatorias"), built

    def test_the_page_uses_the_convocatorias_vocabulary(self):
        page, _ = self.page()
        self.assertIn("<title>Constelación de convocatorias</title>", page)
        self.assertIn("<em>Grupos:</em>", page)
        self.assertIn("tema compartido con el perfil", page)
        self.assertIn('aria-label="Ficha del nodo"', page)
        self.assertIn("'Evidencia citada'", page)
        self.assertIn("convocatoria-iniciar", page)
        self.assertNotIn("Papers enlazados", page)
        self.assertNotIn("resumen del paper", page)
        self.assertNotIn("@@", page.replace("/* viewer */", ""))
        scene = scene_of(page)
        self.assertEqual(scene["slot_colors"], RENDER.CONVOCATORIAS_SLOT_COLORS)
        self.assertEqual({e["rel"] for e in scene["edges"]}, {"afinidad", "experiencia"})
        self.assertTrue(all(e["inter"] for e in scene["edges"]))
        self.assertIn("<h3>Grupo: Salud mental</h3>", page)
        self.assertNotIn("<h3>Evidencias</h3>", page)

    def test_the_sota_profile_is_the_default_and_unknown_profiles_are_refused(self):
        page, _ = self.page()
        self.assertNotIn("Constelación SOTA", page)
        with self.assertRaises(ValueError):
            RENDER.render(CONV.atlas_de_vista(vista())["atlas"], viewer="", profile="otro")

    def test_hostile_titles_and_urls_cannot_break_out_of_the_data_island(self):
        evil = call(id="evil", titulo=HOSTILE, titulo_corto="@@DATA@@ <b>x</b>", financiador=HOSTILE,
                    url="javascript:window.__pwned=1", evidencia=[{"texto": HOSTILE, "url": "data:text/html,x"}])
        page, _ = self.page(vista(oportunidades=[evil], mapa={"temas": [], "experiencia": []}))
        data = page[page.index(DATA_OPEN):]
        data = data[:data.index("</script>") + len("</script>")]
        self.assertEqual(data.lower().count("</script"), 1, "only the data island's own closing tag")
        self.assertNotIn("<img", data)
        self.assertNotIn("javascript:", json.dumps(scene_of(page)["papers"]))
        cited = [p for s in scene_of(page)["atlas"]["systems"] for p in s["planets"] if p["slot"] == "evidence"]
        self.assertEqual(cited[0]["evidence"].get("origin"), None, "a data: url is not a web link")
        study = page[page.index('<aside id="study"'):page.index("</aside>", page.index('<aside id="study"'))]
        self.assertNotIn("<img", study)
        self.assertIn("&lt;img", study)
        evil_sun = next(s for s in scene_of(page)["atlas"]["systems"] if s["id"] == "cv-evil")["planets"][0]
        self.assertEqual(evil_sun["label"], "@@DATA@@ <b>x</b>", "placeholders inside data stay data")


class TestAtlasRoute(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "ws"
        (self.ws / ".morfeo").mkdir(parents=True)
        (self.ws / ".morfeo" / "config.json").write_text("{}", encoding="utf-8")
        patcher = mock.patch.object(value_chain, "_script_candidates", lambda name: [REPO / "scripts" / name])
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_calls(self, calls, profile=True, banco=False):
        folder = self.ws / "convocatorias"
        folder.mkdir(exist_ok=True)
        if profile:
            (folder / "perfil.json").write_text(json.dumps({
                "schema": "morfeo.perfil-convocatorias/v1", "alcance": "proyecto", "titulo": "Proyecto demo",
                "temas": ["salud"]}), encoding="utf-8")
        if banco:
            (folder / "perfil_banco.json").write_text(json.dumps({
                "schema": "morfeo.perfil-convocatorias/v1", "alcance": "banco", "titulo": "Laboratorio",
                "temas": ["salud"], "experiencia": [{"id": "lia-1", "nombre": "Línea uno", "temas": ["salud"]}]}),
                encoding="utf-8")
        (folder / "oportunidades.json").write_text(json.dumps({
            "schema": "morfeo.oportunidades/v1", "oportunidades": calls}), encoding="utf-8")

    def serve(self) -> str:
        from morfeo.dashboard.server import MorfeoDashboardHandler
        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": self.ws})
        handler.log_message = lambda *a, **k: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    @staticmethod
    def get(url: str) -> tuple[int, str, dict]:
        try:
            with urllib.request.urlopen(url) as resp:
                return resp.status, resp.read().decode("utf-8"), dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode("utf-8"), dict(err.headers)

    def test_filled_view_returns_the_self_contained_page_without_cache(self):
        self.write_calls([{"id": "c1", "titulo": "Salud digital", "financiador": "F", "url": "https://f.org",
                           "ambito": "colombia", "temas": ["salud"], "estado": "abierta"}])
        code, body, headers = self.get(self.serve() + "/api/convocatorias/atlas?alcance=proyecto")
        self.assertEqual(code, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertIn('id="atlas-data"', body)
        self.assertIn("<title>Constelación de convocatorias</title>", body)
        self.assertIn("Proyecto en formulación", body)
        self.assertIn("cv-c1", body)

    def test_empty_view_returns_an_empty_state_page(self):
        code, body, _ = self.get(self.serve() + "/api/convocatorias/atlas")
        self.assertEqual(code, 200)
        self.assertNotIn('id="atlas-data"', body)
        self.assertIn("Todavía no hay convocatorias", body)

    def test_banco_scope_draws_the_banco_lines(self):
        self.write_calls([{"id": "c1", "titulo": "Salud digital", "financiador": "F", "url": "https://f.org",
                           "ambito": "colombia", "temas": ["salud"], "estado": "abierta",
                           "relacionados_banco": ["lia-1"]}], banco=True)
        code, body, _ = self.get(self.serve() + "/api/convocatorias/atlas?alcance=banco&agrupar=rol")
        self.assertEqual(code, 200)
        scene = scene_of(body)
        ids = {s["id"] for s in scene["atlas"]["systems"]}
        self.assertEqual(ids, {"cv-c1", "perfil", "exp-lia-1"})
        self.assertIn("Banco LIA", body)
        self.assertIn({"from": "exp-lia-1.sun", "to": "cv-c1.sun"},
                      [{"from": e["from"], "to": e["to"]} for e in scene["edges"]])

    def test_ids_filter_and_invalid_parameters(self):
        self.write_calls([{"id": f"c{i}", "titulo": f"Convocatoria {i}", "financiador": "F", "url": "https://f.org",
                           "ambito": "colombia", "estado": "abierta"} for i in (1, 2)])
        base = self.serve() + "/api/convocatorias/atlas"
        code, body, _ = self.get(base + "?ids=c2")
        self.assertEqual(code, 200)
        self.assertEqual({s["id"] for s in scene_of(body)["atlas"]["systems"]} - {"perfil"}, {"cv-c2"})
        for query in ("?alcance=otro", "?agrupar=color", "?ids=C%201", "?alcance=proyecto&alcance=banco"):
            code, body, headers = self.get(base + query)
            self.assertEqual(code, 400, query)
            self.assertIn("text/html", headers["Content-Type"])
            self.assertNotIn("<script", body)

    def test_post_is_not_a_route(self):
        req = urllib.request.Request(self.serve() + "/api/convocatorias/atlas", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 404)

    def test_missing_scripts_answer_an_error_page(self):
        with mock.patch.object(value_chain, "_script_candidates", lambda name: []):
            page = render_opportunities_atlas(self.ws)
        self.assertIn("convocatorias.py", page)
        self.assertNotIn('id="atlas-data"', page)


if __name__ == "__main__":
    unittest.main()
