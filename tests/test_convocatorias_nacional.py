"""National (Colombia) coverage of the funding-call search (odd/tasks/convocatorias-nacional.md, T1: S1).

The source catalogue lists the verified Colombian listings with their level,
whether the national search must consult them, crawl limits and query
templates; `check` catches coverage gaps (a mandatory source not consulted, a
count that does not match the registered calls, a `fuente` outside the
catalogue, two calls with the same normalized URL); the eligibility rules
cover Colombian funders; `vista` exposes the level and the coverage, and old
files without the new fields still load. Every test builds a throwaway
workspace outside the repository and goes through the public functions or the CLI.
"""

from __future__ import annotations

import json
import re
import urllib.parse

from tests.test_convocatorias import HOY, RULES, SOURCES, Base, _call

LEVELS = {"nacional", "regional", "local", "institucional"}
METHODS = {"api", "rss", "html", "pdf", "navegador", "busqueda", "sesion"}
PLACEHOLDERS = {"tema", "año", "ciudad", "departamento"}
MANDATORY = {"minciencias", "sgr-plan-bienal", "sgr-ocad-paz", "innpulsa", "unal-vri", "unal-vri-externas",
             "mineducacion", "atenea"}
FOREIGN_IDS = {"eu-sedia", "grants-gov", "ukri", "humboldt", "fundsforngos", "opportunity-desk", "scholars4dev",
               "profellow", "euraxess", "cyted", "idb-lab", "idrc", "google-research"}
FOREIGN_RULES = ["msca-global", "msca-staff-exchanges-doctoral-networks", "msca-postdoctoral", "erc",
                 "horizon-europe", "erasmus-cbhe", "erasmus-ka171", "wellcome-discovery",
                 "twas-owsd-paises-rezagados", "idrc-ai4d", "nsf", "ukri-ispf",
                 "royal-society-international-exchanges", "newton-international-fellowships",
                 "british-academy-international-fellowships", "humboldt-georg-forster", "nih"]


def _catalogue() -> dict:
    return json.loads(SOURCES.read_text(encoding="utf-8"))


def _colombian() -> list[dict]:
    return [s for s in _catalogue()["fuentes"] if s["ambito"] == "colombia"]


class CatalogueTest(Base):
    def test_every_colombian_source_declares_level_mandatory_method_and_crawl_delay(self):
        for source in _colombian():
            with self.subTest(source=source["id"]):
                self.assertIn(source["nivel"], LEVELS)
                self.assertIsInstance(source["obligatoria"], bool)
                self.assertIn(source["metodo"], METHODS)
                self.assertTrue(source["crawl_delay"] is None or isinstance(source["crawl_delay"], int))
                self.assertRegex(source["url"], r"^https?://")

    def test_the_mandatory_set_is_the_national_one(self):
        self.assertEqual({s["id"] for s in _colombian() if s["obligatoria"]}, MANDATORY)
        self.assertTrue(all(s.get("obligatoria") in (None, False) for s in _catalogue()["fuentes"]
                            if s["ambito"] != "colombia"))

    def test_mandatory_sources_point_at_listings_not_home_pages(self):
        for source in _colombian():
            if not source["obligatoria"]:
                continue
            with self.subTest(source=source["id"]):
                self.assertNotEqual(source["metodo"], "busqueda")
                self.assertNotIn(urllib.parse.urlsplit(source["url"]).path, ("", "/"))

    def test_minciencias_keeps_its_crawl_delay_and_feed(self):
        by_id = {s["id"]: s for s in _colombian()}
        for source_id in ("minciencias", "sgr-plan-bienal"):
            self.assertEqual(by_id[source_id]["crawl_delay"], 10, source_id)
        self.assertEqual(by_id["minciencias"]["url"], "https://minciencias.gov.co/convocatorias/todas")
        self.assertEqual(by_id["minciencias"]["feed"], "https://minciencias.gov.co/rss.xml")
        self.assertIn("end_date", by_id["innpulsa"]["filtro"])
        self.assertEqual(by_id["innpulsa"]["metodo"], "api")
        self.assertIn("CM-MEN", by_id["mineducacion"]["filtro"])

    def test_hermes_needs_a_session_and_the_vri_api_stands_in(self):
        by_id = {s["id"]: s for s in _colombian()}
        self.assertEqual(by_id["hermes"]["metodo"], "sesion")
        self.assertFalse(by_id["hermes"]["obligatoria"])
        self.assertIn("unal-vri", by_id["hermes"]["notas"])
        for source_id in ("unal-vri", "unal-vri-externas"):
            self.assertEqual(by_id[source_id]["metodo"], "api", source_id)
            self.assertIn("/wp-json/wp/v2/", by_id[source_id]["url"], source_id)

    def test_local_and_regional_sources_name_their_regions(self):
        for source in _colombian():
            if source["nivel"] in ("local", "regional"):
                with self.subTest(source=source["id"]):
                    self.assertTrue(source["regiones"] and all(isinstance(r, str) for r in source["regiones"]))

    def test_search_sources_carry_query_templates_with_known_placeholders(self):
        templates = [q for s in _colombian() for q in s.get("consultas") or []]
        templates += [q["plantilla"] for q in _catalogue()["consultas_colombia"]]
        for source in _colombian():
            if source["metodo"] == "busqueda":
                self.assertTrue(source["consultas"], source["id"])
        for template in templates:
            with self.subTest(template=template):
                self.assertTrue(set(re.findall(r"\{([^}]+)\}", template)) <= PLACEHOLDERS)
        general = _catalogue()["consultas_colombia"]
        self.assertTrue(all(q["nivel"] in LEVELS for q in general))
        self.assertTrue(any("{ciudad}" in q["plantilla"] or "{departamento}" in q["plantilla"] for q in general))
        self.assertTrue(any("reto" in q["plantilla"] for q in general))

    def test_business_challenges_and_the_profile_region_are_covered(self):
        ids = {s["id"] for s in _colombian()}
        for source_id in ("ruta-n", "ccb", "cc-manizales", "connect-bogota", "ecopetrol-econova", "epm",
                          "gobernacion-caldas", "alcaldia-manizales", "fondo-emprender", "unal-extension"):
            self.assertIn(source_id, ids)

    def test_existing_ids_are_kept(self):
        ids = {s["id"] for s in _catalogue()["fuentes"]}
        self.assertTrue(FOREIGN_IDS | {"minciencias", "sgr-plan-bienal", "innpulsa", "fulbright-colombia"} <= ids)
        self.assertEqual(len(ids), len(_catalogue()["fuentes"]))


class ColombianRulesTest(Base):
    def role(self, **fields):
        self.ws.calls([_call(id="c", rol_colombia="desconocido", ambito="colombia", **fields)])
        call = self.item(self.mod.vista(self.ws.root, hoy=HOY), "c")
        return call["rol_colombia"], (call["regla"] or {}).get("id"), call["aviso"]

    def test_minciencias_calls_ask_for_a_recognized_group_and_endorsement(self):
        role, rule, notice = self.role(financiador="Ministerio de Ciencia, Tecnología e Innovación (Minciencias)",
                                       titulo="Convocatoria para proyectos de I+D en IA 2026")
        self.assertEqual((role, rule), ("lider", "minciencias"))
        self.assertIn("aval institucional", notice)

    def test_sgr_ctei_calls_win_over_minciencias(self):
        role, rule, notice = self.role(financiador="Minciencias", programa="Asignación para la CTeI del SGR",
                                       titulo="Convocatoria 45 del Sistema General de Regalías")
        self.assertEqual((role, rule), ("lider", "sgr-ctei"))
        self.assertIn("entidad territorial", notice)

    def test_unal_internal_calls_need_faculty_endorsement(self):
        role, rule, notice = self.role(financiador="Universidad Nacional de Colombia",
                                       programa="Vicerrectoría de Investigación",
                                       titulo="Convocatoria de apoyo a proyectos de investigación 2026")
        self.assertEqual((role, rule), ("lider", "unal-interna"))
        self.assertIn("planta", notice)

    def test_innpulsa_and_business_challenges_need_a_company_proponent(self):
        for fields in ({"financiador": "iNNpulsa Colombia", "titulo": "Convocatoria Escalamiento 2026"},
                       {"financiador": "Ruta N", "titulo": "Reto de innovación abierta 2026"},
                       {"financiador": "Ecopetrol", "programa": "Econova", "titulo": "Retos 2026"},
                       {"financiador": "Cámara de Comercio de Manizales por Caldas", "titulo": "Reto empresarial"}):
            with self.subTest(fields=fields):
                role, rule, notice = self.role(**fields)
                self.assertEqual((role, rule), ("socio", "innpulsa-retos-empresariales"))
                self.assertIn("empresa", notice)

    def test_fondo_emprender_is_not_for_research_groups(self):
        role, rule, notice = self.role(financiador="SENA", programa="Fondo Emprender", titulo="Convocatoria nacional")
        self.assertEqual((role, rule), ("no_elegible", "fondo-emprender"))
        self.assertIn("grupo", notice)

    def test_foreign_rules_keep_their_order_and_come_first(self):
        data = json.loads(RULES.read_text(encoding="utf-8"))
        ids = [rule["id"] for rule in data["reglas"]]
        self.assertEqual(ids[:len(FOREIGN_RULES)], FOREIGN_RULES)
        self.assertEqual(set(ids[len(FOREIGN_RULES):]),
                         {"fondo-emprender", "sgr-ctei", "minciencias", "unal-interna", "innpulsa-retos-empresariales"})

    def test_foreign_calls_still_match_their_rules(self):
        for fields, expected in (({"programa": "Horizon Europe"}, "horizon-europe"),
                                 ({"financiador": "National Institutes of Health"}, "nih"),
                                 ({"titulo": "MSCA Global Postdoctoral Fellowships"}, "msca-global"),
                                 ({"financiador": "Fundación Neutra", "titulo": "Grant"}, None)):
            with self.subTest(expected=expected):
                self.assertEqual(self.role(**fields)[1], expected)
