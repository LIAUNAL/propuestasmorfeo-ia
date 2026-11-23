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

from tests.test_convocatorias import HOY, RULES, SOURCES, Base, _call, _cli

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


def _consulted(calls: list[dict], *, skip=(), extra=(), result="ok") -> list[dict]:
    """Every mandatory source consulted, with `n` = the calls registered from it."""
    rows = []
    for source_id in sorted(MANDATORY - set(skip)):
        rows.append({"fuente": source_id, "url": f"https://example.org/{source_id}", "fecha": "2026-11-20",
                     "resultado": result, "n": sum(1 for c in calls if c.get("fuente") == source_id)})
    return rows + list(extra)


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


class CoverageCheckTest(Base):
    def write(self, calls, consulted=None):
        self.ws.profile()
        self.ws.calls(calls, fuentes_consultadas=_consulted(calls) if consulted is None else consulted)

    def errors(self):
        return [f for f in self.mod.check(self.ws.root) if f["severidad"] == "error"]

    def test_a_complete_national_search_passes(self):
        calls = [_call(id="mc", fuente="minciencias", ambito="colombia", nivel="nacional", url="https://minciencias.gov.co/c/1"),
                 _call(id="ruta", fuente="busqueda:rutanmedellin.org", ambito="colombia", nivel="local",
                       url="https://rutanmedellin.org/ofertas/reto")]
        self.write(calls)
        self.assertEqual(self.errors(), [])
        self.assertEqual(_cli("check", str(self.ws.root)).returncode, 0)

    def test_a_mandatory_source_not_consulted_fails(self):
        self.write([_call()], _consulted([_call()], skip=["unal-vri"]))
        found = [f for f in self.errors() if f["codigo"] == "fuente-obligatoria-sin-consultar"]
        self.assertEqual(len(found), 1, found)
        self.assertIn("unal-vri", found[0]["mensaje"])
        result = _cli("check", str(self.ws.root))
        self.assertEqual(result.returncode, 1)
        self.assertIn("error fuente-obligatoria-sin-consultar", result.stdout)

    def test_blocked_and_session_results_count_as_consulted(self):
        rows = _consulted([], skip=["atenea"]) + [{"fuente": "atenea", "url": "https://agenciaatenea.gov.co/convocatorias",
                                                    "fecha": "2026-11-20", "resultado": "requiere_sesion", "n": 0}]
        rows[0]["resultado"] = "bloqueado"
        self.write([_call()], rows)
        self.assertEqual(self.errors(), [])

    def test_without_colombia_in_the_profile_the_national_sources_are_not_required(self):
        self.ws.profile(ambitos=["internacional"])
        self.ws.calls([_call()], fuentes_consultadas=[])
        self.assertNotIn("fuente-obligatoria-sin-consultar", self.codes(self.mod.check(self.ws.root)))

    def test_the_reported_count_must_match_the_registered_calls(self):
        calls = [_call(id="mc", fuente="minciencias", url="https://minciencias.gov.co/c/1")]
        rows = _consulted(calls)
        next(r for r in rows if r["fuente"] == "minciencias")["n"] = 2
        self.write(calls, rows)
        found = [f for f in self.errors() if f["codigo"] == "conteo-fuente"]
        self.assertEqual(len(found), 1, found)
        self.assertIn("minciencias", found[0]["mensaje"])
        self.write(calls)
        self.assertEqual(self.errors(), [])

    def test_a_call_from_a_catalogue_source_that_was_not_reported_fails(self):
        calls = [_call(id="fb", fuente="fulbright-colombia")]
        self.write(calls)
        self.assertIn("conteo-fuente", [f["codigo"] for f in self.errors()])

    def test_search_hosts_are_counted_only_when_reported(self):
        calls = [_call(id="a", fuente="busqueda:example.org"), _call(id="b", fuente="busqueda:example.org",
                                                                      url="https://example.org/c2")]
        self.write(calls)
        self.assertEqual(self.errors(), [])
        extra = [{"fuente": "busqueda:example.org", "url": "https://example.org", "fecha": "2026-11-20",
                  "resultado": "ok", "n": 3}]
        self.write(calls, _consulted(calls, extra=extra))
        self.assertIn("conteo-fuente", [f["codigo"] for f in self.errors()])
        extra[0]["n"] = 2
        self.write(calls, _consulted(calls, extra=extra))
        self.assertEqual(self.errors(), [])

    def test_a_fuente_outside_the_catalogue_fails_with_a_fix_hint(self):
        self.write([_call(fuente="eu-sedia (CORDIS)", url="https://cordis.europa.eu/x")])
        found = [f for f in self.errors() if f["codigo"] == "fuente-desconocida"]
        self.assertEqual(len(found), 1, found)
        self.assertIn("«eu-sedia»", found[0]["mensaje"])
        self.write([_call(fuente="lo que vi en la web", url="https://www.ruta.org/x")])
        message = next(f["mensaje"] for f in self.errors() if f["codigo"] == "fuente-desconocida")
        self.assertIn("busqueda:www.ruta.org", message)
        for bad in ("busqueda:", "busqueda:Example.org", None):
            self.write([_call(fuente=bad)])
            self.assertIn("fuente-desconocida", [f["codigo"] for f in self.errors()], bad)

    def test_a_consulted_entry_outside_the_catalogue_fails(self):
        extra = [{"fuente": "Minciencias (listado)", "url": "https://minciencias.gov.co", "fecha": "2026-11-20",
                  "resultado": "ok", "n": 0}]
        self.write([_call()], _consulted([_call()], extra=extra))
        self.assertIn("fuente-desconocida", [f["codigo"] for f in self.errors()])

    def test_two_calls_with_the_same_normalized_url_fail(self):
        calls = [_call(id="a", url="https://Example.org/c1/?utm_source=x&utm_medium=y#top"),
                 _call(id="b", url="HTTPS://example.org/c1")]
        self.write(calls)
        found = [f for f in self.errors() if f["codigo"] == "url-repetida"]
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0]["id"], "b")
        self.assertIn("a", found[0]["mensaje"])
        calls[1]["url"] = "https://example.org/c1?page=2"
        self.write(calls)
        self.assertEqual(self.errors(), [])

    def test_url_normalization(self):
        norm = self.mod.normalize_url
        self.assertEqual(norm("HTTPS://Example.ORG:443/a/b/?b=2&a=1&utm_campaign=z&fbclid=q#x"),
                         "https://example.org/a/b?a=1&b=2")
        self.assertEqual(norm("http://example.org/"), "http://example.org")
        self.assertNotEqual(norm("https://example.org/a?id=1"), norm("https://example.org/a?id=2"))
        self.assertEqual(norm("  "), "")

    def test_requiere_sesion_is_a_valid_result(self):
        rows = _consulted([_call()]) + [{"fuente": "hermes", "url": "http://www.hermes.unal.edu.co/",
                                         "fecha": "2026-11-20", "resultado": "requiere_sesion", "n": 0}]
        self.write([_call()], rows)
        self.assertEqual(self.errors(), [])
        rows[-1]["resultado"] = "pendiente"
        self.write([_call()], rows)
        self.assertIn("valor-invalido", [f["codigo"] for f in self.errors()])

    def test_level_is_validated_and_missing_on_colombian_calls_warns(self):
        self.write([_call(nivel="municipal")])
        self.assertIn("valor-invalido", [f["codigo"] for f in self.errors()])
        self.write([_call(ambito="colombia")])
        findings = self.mod.check(self.ws.root)
        self.assertIn("sin-nivel", self.codes(findings, "warning"))
        self.assertEqual(self.codes(findings, "error"), [])
        self.write([_call(ambito="colombia", nivel="institucional"), _call(id="int", url="https://example.org/i")])
        findings = self.mod.check(self.ws.root)
        self.assertNotIn("sin-nivel", self.codes(findings))


class ViewTest(Base):
    def test_the_view_exposes_level_and_coverage(self):
        calls = [_call(id="mc", fuente="minciencias", ambito="colombia", url="https://minciencias.gov.co/c/1"),
                 _call(id="ruta", fuente="busqueda:rutanmedellin.org", ambito="colombia", nivel="local",
                       url="https://rutanmedellin.org/ofertas/reto"),
                 _call(id="int", url="https://example.org/int", fuente="prueba")]
        rows = _consulted(calls, skip=["atenea", "mineducacion"])
        next(r for r in rows if r["fuente"] == "innpulsa")["n"] = 4
        self.ws.profile()
        self.ws.calls(calls, fuentes_consultadas=rows)
        view = self.mod.vista(self.ws.root, hoy=HOY)
        self.assertEqual(self.item(view, "mc")["nivel"], "nacional", "inferred from the catalogue source")
        self.assertEqual(self.item(view, "ruta")["nivel"], "local")
        self.assertIsNone(self.item(view, "int")["nivel"])
        self.assertEqual(view["resumen"]["por_nivel"],
                         {"nacional": 1, "regional": 0, "local": 1, "institucional": 0})
        cov = view["cobertura"]
        self.assertTrue(cov["requerida"])
        self.assertEqual([f["id"] for f in cov["faltantes"]], ["mineducacion", "atenea"], "catalogue order")
        self.assertTrue(all(f["nombre"] and f["url"].startswith("https://") for f in cov["faltantes"]))
        self.assertEqual(cov["descuadres"], [{"fuente": "innpulsa", "n": 4, "registradas": 0}])
        self.assertEqual(cov["desconocidas"], ["int"])
        self.assertEqual(len(cov["obligatorias"]), len(MANDATORY))
        self.assertFalse(cov["completa"])
        self.assertIn("fuente-obligatoria-sin-consultar", self.codes(view["hallazgos"], "error"))

    def test_text_output_reports_the_coverage_gaps(self):
        self.ws.profile()
        self.ws.calls([_call(fuente="busqueda:example.org")], fuentes_consultadas=_consulted([], skip=["atenea"]))
        result = _cli("datos", str(self.ws.root), "--hoy", "2026-11-20")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cobertura nacional: falta 1 fuente obligatoria: atenea", result.stdout)
        self.ws.calls([_call(fuente="busqueda:example.org")], fuentes_consultadas=_consulted([]))
        result = _cli("datos", str(self.ws.root), "--hoy", "2026-11-20")
        self.assertNotIn("cobertura", result.stdout)

    def test_an_old_file_without_the_new_fields_still_loads(self):
        """A file written before the national search (free-text fuente, no nivel) keeps loading."""
        old = [_call(id="eu", fuente="eu-sedia (CORDIS)", url="https://cordis.europa.eu/x", programa="Horizon Europe"),
               _call(id="cy", fuente="cyted", ambito="latam", url="https://www.cyted.org/g.pdf")]
        for c in old:
            c.pop("nivel", None)
        self.ws.profile(temas=["energía"])
        self.ws.calls(old, fuentes_consultadas=[
            {"fuente": "minciencias", "url": "https://minciencias.gov.co/c", "fecha": "2026-11-22", "resultado": "ok", "n": 1},
            {"fuente": "cyted", "url": "https://www.cyted.org", "fecha": "2026-11-22", "resultado": "ok", "n": 1}])
        view = self.mod.vista(self.ws.root, hoy=HOY)
        self.assertEqual(sorted(c["id"] for c in view["oportunidades"]), ["cy", "eu"])
        self.assertEqual(self.item(view, "eu")["rol_colombia"], "socio")
        self.assertIsNone(self.item(view, "eu")["nivel"])
        self.assertEqual(view["resumen"]["por_ambito"], {"colombia": 0, "latam": 1, "internacional": 1})
        errors = set(self.codes(view["hallazgos"], "error"))
        self.assertEqual(errors, {"fuente-obligatoria-sin-consultar", "conteo-fuente", "fuente-desconocida"})
        atlas = self.mod.constelacion(self.ws.root, hoy=HOY)
        self.assertEqual(atlas["total"], 2)
        result = _cli("datos", str(self.ws.root), "--json", "--hoy", "2026-11-20")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(_cli("check", str(self.ws.root)).returncode, 1)


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
