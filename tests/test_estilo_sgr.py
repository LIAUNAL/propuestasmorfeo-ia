"""scripts/estilo_sgr.py and scripts/sgr/lexico_sgr.json: the SGR style layer.

The SGR flow writes a public-investment project (MGA, DNP), not a research
proposal: third person about the project, no first person, a lexicon per
Anexo 2 chapter, the MGA activity-verb ban on activity names only, and texts
that must repeat verbatim (title, objectives, products, activities). The
checker reports what a regular expression can prove; the revisor-estilo-sgr
agent judges and edits the rest.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "estilo_sgr.py"
LEXICON = REPO / "scripts" / "sgr" / "lexico_sgr.json"
GUIDE = "guiaProyectosIA_Agente_Regalias.md"

sys.path.insert(0, str(REPO / "src"))
from morfeo.core.sgr_rules import parse_sgr_blocks  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


estilo = _load("estilo_sgr", SCRIPT)
check_run = _load("check_run_for_estilo_tests", REPO / "scripts" / "check_run.py")

ENTRY_KEYS = {"id", "tipo", "expresion", "regex", "motivo", "fuente", "aplica_a"}
OBJECTIVE = ("Incrementar la cobertura fundamental del monitoreo hídrico en los municipios ribereños "
             "del territorio de estudio")
OE1 = "Ampliar la cobertura de estaciones de medición en la cuenca media"


def _tex(body: str) -> str:
    return body.strip() + "\n"


class LexiconSchema(unittest.TestCase):
    def setUp(self) -> None:
        self.lex = json.loads(LEXICON.read_text(encoding="utf-8"))

    def _entries(self):
        yield from (("global", e) for e in self.lex["global"])
        for stem, entries in self.lex["secciones"].items():
            yield from ((stem, e) for e in entries)

    def test_top_level_shape(self) -> None:
        self.assertEqual(self.lex["schema"], "morfeo.lexico-sgr/v1")
        for key in ("voz", "global", "secciones", "exenciones", "repeticion_obligatoria",
                    "mapa_capitulos", "capitulos_sin_archivo"):
            self.assertIn(key, self.lex)

    def test_every_entry_has_the_contract_keys_and_values(self) -> None:
        ids = []
        for scope, entry in self._entries():
            with self.subTest(scope=scope, entry=entry.get("id")):
                self.assertEqual(set(entry), ENTRY_KEYS)
                self.assertIn(entry["tipo"], ("prohibida", "desaconsejada", "favorecida"))
                self.assertIn(entry["aplica_a"], ("prosa", "nombres_actividad", "tabla"))
                self.assertTrue(entry["motivo"] and entry["fuente"] and entry["expresion"])
                if entry["regex"] is not None:
                    self.assertIsNotNone(estilo.compile_rule(entry["regex"]))
            ids.append(entry["id"])
        self.assertEqual(len(ids), len(set(ids)), "ids repetidos en el léxico")

    def test_section_keys_are_morfeo_stems(self) -> None:
        stems = set(check_run.CANONICAL_SECTIONS) | set(check_run.SGR_SECTIONS)
        self.assertLessEqual(set(self.lex["secciones"]), stems)
        for item in self.lex["mapa_capitulos"]:
            self.assertLessEqual(set(item["secciones"]), stems)

    def test_every_anexo2_chapter_is_mapped_or_pending(self) -> None:
        mapped = {item["capitulo"] for item in self.lex["mapa_capitulos"]}
        pending = {item["capitulo"] for item in self.lex["capitulos_sin_archivo"]}
        self.assertEqual(mapped | pending, set(range(1, 32)))
        self.assertFalse(mapped & pending)

    def test_the_users_openings_are_favoured(self) -> None:
        openings = " ".join(self.lex["voz"]["aperturas_favorecidas"])
        self.assertIn("Este proyecto busca", openings)
        self.assertIn("La presente propuesta se enmarca", openings)

    def test_the_mga_verb_ban_targets_activity_names_only(self) -> None:
        verb = [e for _, e in self._entries() if e["id"] == "verbo-mga-actividad"]
        self.assertEqual(len(verb), 1)
        self.assertEqual(verb[0]["aplica_a"], "nombres_actividad")
        self.assertIn("p. 81", verb[0]["fuente"])

    def test_alliance_and_territory_sections_have_their_lexicon(self) -> None:
        for stem in ("26_identificacion", "27_demandas_territoriales", "28_matriz_responsabilidades",
                     "29_idoneidad_trayectoria"):
            with self.subTest(stem=stem):
                entries = self.lex["secciones"][stem]
                self.assertIn("favorecida", {e["tipo"] for e in entries})
                self.assertTrue(any(e["regex"] for e in entries))

    def test_chapters_1_8_10_and_27_map_to_the_new_sections(self) -> None:
        mapped = {item["capitulo"]: item["secciones"] for item in self.lex["mapa_capitulos"]}
        self.assertEqual(mapped[1], ["26_identificacion"])
        self.assertIn("27_demandas_territoriales", mapped[8])
        self.assertIn("28_matriz_responsabilidades", mapped[10])
        self.assertEqual(mapped[27], ["29_idoneidad_trayectoria"])
        pending = {item["capitulo"] for item in self.lex["capitulos_sin_archivo"]}
        self.assertFalse({1, 27} & pending)

    def test_whitelist_kinds(self) -> None:
        kinds = {item["tipo"] for item in self.lex["repeticion_obligatoria"]}
        for kind in ("titulo", "problema_central", "objetivo_general", "objetivos_especificos",
                     "productos", "actividades", "demandas", "entidades"):
            self.assertIn(kind, kinds)


class Findings(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.sections = self.root / "redaccion" / "sections"
        self.sections.mkdir(parents=True)

    def write(self, stem: str, body: str) -> None:
        (self.sections / f"{stem}.tex").write_text(_tex(body), encoding="utf-8")

    def codes(self, section: str | None = None) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for f in estilo.findings(self.root, section):
            out.setdefault(f["code"], []).append(f)
        return out

    def test_finding_shape(self) -> None:
        self.write("02_justificacion", "\\section{Justificación}\nNosotros proponemos un modelo.")
        found = estilo.findings(self.root)
        self.assertTrue(found)
        for f in found:
            self.assertEqual(set(f), {"severity", "code", "message", "archivo", "linea", "extracto", "regla"})
            self.assertIn(f["severity"], ("advertencia", "info"))
            self.assertTrue(f["code"].startswith("sgr-estilo-"))
            self.assertEqual(f["code"], f"sgr-estilo-{f['regla']}")

    def test_first_person_is_flagged_with_its_line(self) -> None:
        self.write("02_justificacion", "\\section{Justificación}\nEl proyecto atiende la cuenca.\n"
                                       "En esta etapa realizaremos campañas y hemos definido el alcance.")
        hits = self.codes()["sgr-estilo-primera-persona"]
        self.assertEqual({h["linea"] for h in hits}, {3})
        self.assertEqual(hits[0]["severity"], "advertencia")
        self.assertEqual(hits[0]["archivo"], "redaccion/sections/02_justificacion.tex")

    def test_third_person_and_quoted_plan_names_are_clean(self) -> None:
        self.write("19_alineacion_planes", "El proyecto se articula con el plan «Podemos Avanzar Juntos». "
                                           "Este proyecto busca reducir la brecha.")
        self.assertNotIn("sgr-estilo-primera-persona", self.codes())

    def test_latex_comments_and_citations_are_not_prose(self) -> None:
        self.write("08_marco_conceptual", "% nosotros proponemos esto\nEl concepto se define así "
                                          "\\citep{nosotros2020}.")
        self.assertNotIn("sgr-estilo-primera-persona", self.codes())

    def test_a_section_rule_fires_only_in_its_section(self) -> None:
        sentence = "Se hace necesario intervenir la cuenca."
        self.write("02_justificacion", sentence)
        self.write("08_marco_conceptual", sentence)
        hits = self.codes()["sgr-estilo-justificacion-necesidad-enfatica"]
        self.assertEqual({h["archivo"] for h in hits}, {"redaccion/sections/02_justificacion.tex"})

    def test_section_filter(self) -> None:
        self.write("02_justificacion", "Nosotros proponemos.")
        self.write("08_marco_conceptual", "Nosotros definimos.")
        archivos = {f["archivo"] for f in estilo.findings(self.root, "08_marco_conceptual")}
        self.assertEqual(archivos, {"redaccion/sections/08_marco_conceptual.tex"})

    def test_unknown_section_is_bad_input(self) -> None:
        with self.assertRaises(ValueError):
            estilo.findings(self.root, "99_inexistente")

    def test_mga_verb_flagged_in_an_activity_name_not_in_an_objective(self) -> None:
        self.write("07_objetivos_especificos", "\\begin{enumerate}\n\\item Fortalecer la red de monitoreo.\n"
                                               "\\end{enumerate}")
        self.write("10_metodologia", "\\begin{xltabular}{\\textwidth}{lX}\n"
                                     "No. & Actividad \\\\\n"
                                     "1.1.1 & Implementar el sistema de información \\\\\n"
                                     "1.1.2 & Realizar campañas de muestreo \\\\\n"
                                     "\\end{xltabular}\n"
                                     "Actividad 1.2: Fortalecer la mesa técnica.\n")
        self.write("14_cronograma_actividades", "\\begin{tabular}{ll}\n"
                                                "Actividad 2.1.1: Promover talleres & 1 \\\\\n"
                                                "\\end{tabular}")
        hits = self.codes().get("sgr-estilo-verbo-mga-actividad", [])
        located = {(h["archivo"].rsplit("/", 1)[-1], h["linea"]) for h in hits}
        self.assertEqual(located, {("10_metodologia.tex", 3), ("14_cronograma_actividades.tex", 2)})

    def test_mga_verb_in_the_value_chain_file(self) -> None:
        chain = self.root / "artefactos" / "sgr"
        chain.mkdir(parents=True)
        (chain / "cadena_valor.json").write_text(json.dumps({"objetivos": [{"id": "OE1", "texto": OE1, "productos": [
            {"codigo": "1.1", "nombre": "Servicio de información", "actividades": [
                {"codigo": "1.1.1", "nombre": "Desarrollar la plataforma"},
                {"codigo": "1.1.2", "nombre": "Ejecutar campañas de campo"}]}]}]}), encoding="utf-8")
        hits = self.codes("23_cadena_valor").get("sgr-estilo-verbo-mga-actividad", [])
        self.assertEqual([h["archivo"] for h in hits], ["artefactos/sgr/cadena_valor.json"])
        self.assertIn("1.1.1", hits[0]["message"])

    def test_official_name_exemption(self) -> None:
        self.write("09_equipo_trabajo", "El proyecto vincula seis Jóvenes Investigadores e Innovadores.")
        self.assertNotIn("sgr-estilo-promocional", self.codes())
        self.write("09_equipo_trabajo", "El proyecto ofrece soluciones innovadoras.")
        self.assertIn("sgr-estilo-promocional", self.codes())

    def test_whitelisted_verbatim_texts_are_not_rewritten_or_counted_as_redundancy(self) -> None:
        trees = self.root / "artefactos" / "arboles"
        trees.mkdir(parents=True)
        (trees / "arbol_objetivos.json").write_text(json.dumps({
            "trunk": {"text": OBJECTIVE}, "groups": [{"id": "OE1", "objective": OE1}]}), encoding="utf-8")
        # The objective holds "fundamental" (an inflation word) and repeats in two sections.
        self.write("06_objetivo_general", f"{OBJECTIVE}.")
        self.write("00_frontmatter", f"En respuesta, el proyecto tiene como propósito {OBJECTIVE.lower()}. "
                                     f"El primer objetivo es {OE1}.")
        self.write("10_metodologia", f"Objetivo específico 1 (OE1): {OE1}.")
        found = self.codes()
        self.assertNotIn("sgr-estilo-inflacion", found)
        self.assertNotIn("sgr-estilo-redundancia-entre-secciones", found)

    def test_copied_prose_between_sections_is_an_info_signal(self) -> None:
        copied = ("la cuenca media registra una cobertura de monitoreo de apenas cuatro estaciones activas "
                  "para una población ribereña dispersa en once veredas del territorio")
        self.write("03_descripcion_problema", f"En la actualidad {copied}.")
        self.write("02_justificacion", f"Como se describió, {copied}.")
        hits = self.codes()["sgr-estilo-redundancia-entre-secciones"]
        self.assertTrue(all(h["severity"] == "info" for h in hits))
        self.assertEqual({h["archivo"].rsplit("/", 1)[-1] for h in hits},
                         {"02_justificacion.tex", "03_descripcion_problema.tex"})

    def test_title_is_whitelisted(self) -> None:
        red = self.root / "redaccion"
        (red / "datos_proyecto.tex").write_text(
            "\\newcommand{\\TituloProyecto}{Desarrollo de una plataforma de vanguardia en la cuenca}\n",
            encoding="utf-8")
        self.write("02_justificacion", "El proyecto Desarrollo de una plataforma de vanguardia en la cuenca "
                                       "atiende el territorio.")
        self.assertNotIn("sgr-estilo-promocional", self.codes())

    def test_consecutive_sentences_with_the_same_connector(self) -> None:
        self.write("11_resultados_esperados", "El proyecto entrega datos. Asimismo, publica informes. "
                                              "Asimismo, forma talento.")
        self.assertIn("sgr-estilo-conectores-en-serie", self.codes())

    def test_el_presente_proyecto_more_than_once(self) -> None:
        self.write("02_justificacion", "El presente proyecto atiende la cuenca. "
                                       "El presente proyecto forma talento.")
        self.assertIn("sgr-estilo-presente-proyecto", self.codes())

    def test_idoneidad_brochure_language_is_flagged(self) -> None:
        self.write("29_idoneidad_trayectoria", "La universidad es un referente nacional de talla mundial. "
                                               "El grupo, reconocido por Minciencias en categoría A1, aporta datos.")
        found = self.codes("29_idoneidad_trayectoria")
        self.assertEqual(found["sgr-estilo-idoneidad-folleto"][0]["severity"], "advertencia")
        self.assertNotIn("sgr-estilo-idoneidad-reconocido", found)
        self.write("29_idoneidad_trayectoria", "El grupo es reconocido en la región.")
        self.assertIn("sgr-estilo-idoneidad-reconocido", self.codes("29_idoneidad_trayectoria"))

    def test_generic_responsibility_in_the_matrix_table(self) -> None:
        self.write("28_matriz_responsabilidades", "\\begin{xltabular}{\\textwidth}{lX}\n"
                                                  "Entidad & Responsabilidades \\\\\n"
                                                  "Gobernación & Apoyar el proyecto \\\\\n"
                                                  "\\end{xltabular}")
        self.assertIn("sgr-estilo-matriz-responsabilidad-generica", self.codes("28_matriz_responsabilidades"))

    def test_demand_texts_and_entity_names_are_whitelisted(self) -> None:
        demand = ("Reducir la brecha fundamental en el acceso a servicios de salud mental de los jóvenes rurales "
                  "del departamento de Caldas y de sus municipios ribereños")
        entity = "Corporación Líder en Salud Mental Comunitaria"
        sgr = self.root / "artefactos" / "sgr"
        sgr.mkdir(parents=True)
        self.write("27_demandas_territoriales", f"\\begin{{xltabular}}{{\\textwidth}}{{lX}}\n"
                                                f"CAL-01 & {demand} \\\\\n\\end{{xltabular}}")
        self.write("17_articulacion_comunidades", f"El proyecto atiende la demanda {demand}. {entity} coordina.")
        found = self.codes()
        self.assertIn("sgr-estilo-promocional", found)
        (sgr / "territorio.json").write_text(json.dumps({"demandas": [{"codigo": "CAL-01", "texto": demand}]}),
                                             encoding="utf-8")
        (sgr / "alianza.json").write_text(json.dumps({"entidades": [{"id": "E1", "nombre": entity}]}),
                                          encoding="utf-8")
        found = self.codes()
        for code in ("sgr-estilo-inflacion", "sgr-estilo-redundancia-entre-secciones", "sgr-estilo-promocional"):
            self.assertNotIn(code, found)

    def test_missing_sections_folder_means_no_findings(self) -> None:
        shutil.rmtree(self.root / "redaccion")
        self.assertEqual(estilo.findings(self.root), [])


class Cli(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        sections = self.root / "redaccion" / "sections"
        sections.mkdir(parents=True)
        (sections / "02_justificacion.tex").write_text("Nosotros proponemos.\n", encoding="utf-8")

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_json_output_and_exit_zero_with_findings(self) -> None:
        out = self.run_cli(str(self.root), "--json")
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertIn("sgr-estilo-primera-persona", {f["code"] for f in data["findings"]})

    def test_section_flag_and_text_output(self) -> None:
        out = self.run_cli(str(self.root), "--section", "02_justificacion")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("sgr-estilo-primera-persona", out.stdout)
        self.assertRegex(out.stdout, r"estilo_sgr: \d+ advertencias, \d+ notas")

    def test_bad_input_exits_two(self) -> None:
        self.assertEqual(self.run_cli(str(self.root), "--section", "99_x").returncode, 2)
        self.assertEqual(self.run_cli(str(self.root / "no-existe")).returncode, 2)


class GuideWritingPatterns(unittest.TestCase):
    """S2: every `### SGR` block gains a «Redacción» part the parser still returns."""

    EXPECTED = {"§2", "§3", "§6", "§7", "§10", "§11", "§13", "§14", "§15", "§17",
                "A19", "A20", "A21", "A22", "A23", "A24", "A25", "A26", "A27", "A28", "A29"}

    def setUp(self) -> None:
        self.text = (REPO / GUIDE).read_text(encoding="utf-8")
        self.blocks = parse_sgr_blocks(self.text)

    def test_every_block_is_still_parsed(self) -> None:
        self.assertEqual(set(self.blocks), self.EXPECTED)

    def test_every_block_has_its_writing_pattern(self) -> None:
        for key, body in self.blocks.items():
            with self.subTest(block=key):
                self.assertIn("**Redacción.**", body)
                self.assertRegex(body, r"(?s)\*\*Redacción\.\*\*.*(Evitar|evitar)")

    def test_section_3_drops_the_research_question_in_sgr(self) -> None:
        body = self.blocks["§3"]
        self.assertNotIn("La sección cierra con la pregunta de investigación", body)
        self.assertIn("no cierra con la pregunta de investigación", body)

    def test_kit_copy_is_identical(self) -> None:
        kit = REPO / "src" / "morfeo" / "_kit" / GUIDE
        if kit.is_file():
            self.assertEqual(kit.read_text(encoding="utf-8"), self.text)

    def test_evidence_base_carries_no_project_data(self) -> None:
        doc = (REPO / "docs" / "sgr" / "patrones_redaccion_sgr.md").read_text(encoding="utf-8")
        self.assertIn("C18", doc)
        self.assertIsNone(re.search(r"\$\s?\d|\b\d{3}\.\d{3}\.\d{3}\b|BPIN\s*\d", doc))


if __name__ == "__main__":
    unittest.main()
