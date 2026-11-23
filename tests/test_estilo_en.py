"""Readability and redundancy scoring in English (S3 of idioma-tablero-traduccion).

`scripts/estilo_en.py` is the English counterpart of `scripts/estilo_es.py`: the
same engine and report schema (`artefactos/estilo/reporte.json`), with English
catalogs, connectors, word lists and fact patterns. `verify` is the only
command that fails. The skills `estilo-natural-en` and
`depuracion-redundancias-en` are its editorial side.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "estilo_en.py"
SPANISH = REPO / "scripts" / "estilo_es.py"
STYLE_SKILL = REPO / ".claude" / "skills" / "estilo-natural-en" / "SKILL.md"
REDUNDANCY_SKILL = REPO / ".claude" / "skills" / "depuracion-redundancias-en" / "SKILL.md"


def load_module():
    spec = importlib.util.spec_from_file_location("estilo_en_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cli(script: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)


def filler(sentences: int, start: int = 0) -> str:
    """Sentences of twelve invented words that never repeat, so no rule fires on them."""
    syllables = ("ba", "ce", "di", "fo", "gu", "la", "me", "ni", "po", "ru", "sa", "te", "vi", "zo")
    out, n = [], start
    for _ in range(sentences):
        words = []
        for _ in range(12):
            a, b = divmod(n, len(syllables))
            b2, c = divmod(a, len(syllables))
            words.append(syllables[b] + syllables[c] + syllables[b2 % len(syllables)] + "n")
            n += 1
        out.append(" ".join(words).capitalize() + ".")
    return " ".join(out)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def audit_text(self, text: str, script: Path = SCRIPT, command: str = "audit") -> dict:
        path = self.tmp / "text.txt"
        path.write_text(text, encoding="utf-8")
        result = cli(script, command, "--txt", path, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def categories(self, text: str) -> set:
        return {f["categoria"] for f in self.audit_text(text)["hallazgos"]}

    def make_run(self, sections: dict) -> Path:
        run = self.tmp / "run"
        (run / "redaccion" / "sections").mkdir(parents=True)
        (run / "artefactos").mkdir()
        for name, text in sections.items():
            (run / "redaccion" / "sections" / f"{name}.tex").write_text(text, encoding="utf-8")
        return run


class CategoryTests(Base):
    CASES = {
        "cliche": ("The platform plays a pivotal role in the region.", "The platform reduces the error in the region."),
        "comodin": ("We delve into the data.", "We examine the data."),
        "promocional": ("It is a groundbreaking approach.", "It is a new approach."),
        "atribucion_vaga": ("Recent studies show a three percent gain.", "Perez measures a three percent gain."),
        "perifrasis": ("Due to the fact that it fails, it restarts.", "Because it fails, it restarts."),
        "copula_evitada": ("The group serves as a reference.", "The group is a reference."),
        "calco": ("The investigation group trains students.", "The research group trains students."),
        "plantilla": ("It is worth noting that the system runs offline.", "The system runs offline."),
        "paralelismo_negativo": ("The system not only classifies but also explains.", "The system classifies and explains."),
        "falso_rango": ("It spans ranging from signal capture to territorial inclusion.", "It spans from 2020 to 2024."),
        "matizacion": ("The model could potentially reduce the error.", "The model reduces the error."),
        "gerundio_cierre": ("The model improves precision, highlighting its lasting impact.",
                            "The model improves precision and the impact lasts."),
        "raya": ("The model—trained in the field—improves.", "The model, trained in the field, improves."),
        "oracion_larga": (" ".join(["word"] * 46) + ".", " ".join(["word"] * 45) + "."),
        "triada": ("It demands innovation, rigor, and relevance. It measures capture, processing and evaluation.",
                   "It demands innovation and rigor. It measures capture and evaluation."),
        "conector_repeticion": ("Moreover, the team measures. The group records. Moreover, the panel reviews.",
                                "Moreover, the team measures. The group records. Then the panel reviews."),
        "apertura_repetida": ("The team measures the voice. The team records the voice.",
                              "The team measures the voice. Then it records the voice."),
        "demostrativo": ("This model measures. This task records. These data add. Such panel reviews.",
                         "The model measures. The task records. The data add. The panel reviews."),
        "causal_densidad": ("It fails because of noise. It drops because dust builds. It stops because heat rises.",
                            "It fails with noise. It drops with dust. It stops with heat."),
        "cola_relativa": ("It measures the voice, which helps. It records the rhythm, which serves.",
                          "It measures the voice and helps. It records the rhythm and serves."),
    }

    def test_each_category_fires_and_stays_silent(self) -> None:
        for category, (firing, silent) in self.CASES.items():
            with self.subTest(category=category):
                self.assertIn(category, self.categories(firing))
                self.assertNotIn(category, self.categories(silent))

    def test_the_spanish_script_does_not_read_english_as_its_own(self) -> None:
        """The English catalog is not the Spanish one: the same sentence is a
        finding in English and clean for estilo_es.py."""
        text = "It is worth noting that we delve into the data."
        english = {f["categoria"] for f in self.audit_text(text)["hallazgos"]}
        spanish = {f["categoria"] for f in self.audit_text(text, SPANISH, "auditar")["hallazgos"]}
        self.assertTrue({"plantilla", "comodin"} <= english)
        self.assertFalse({"plantilla", "comodin"} & spanish)

    def test_finding_has_location_category_and_guidance(self) -> None:
        finding = self.audit_text("First sentence without trouble.\n\nAnother clear one. "
                                  "It is worth noting that it fails.")["hallazgos"][0]
        self.assertEqual((finding["parrafo"], finding["oracion"], finding["categoria"]), (2, 3, "plantilla"))
        self.assertIn("It is worth noting that", finding["fragmento"])
        self.assertTrue(finding["orientacion"].isascii())

    def test_cited_attribution_is_not_vague(self) -> None:
        run = self.make_run({"02_justificacion": r"Recent studies show a gain \citep{perez2020}."})
        result = cli(SCRIPT, "audit", run, "--json")
        self.assertNotIn("atribucion_vaga", {f["categoria"] for f in json.loads(result.stdout)["hallazgos"]})

    def test_overused_word_stands_out_from_the_document(self) -> None:
        parts = [filler(1, start=i * 24)[:-1] + " leveraging " + filler(1, start=i * 24 + 12).lower()
                 for i in range(100)]
        found = [f for f in self.audit_text(" ".join(parts))["hallazgos"] if f["categoria"] == "sobreuso"]
        self.assertEqual([f["fragmento"] for f in found], ["leveraging"])

    def test_abbreviations_do_not_end_sentences(self) -> None:
        m = load_module()
        self.assertEqual(len(m.engine.split_sentences("As Perez et al. show, see Fig. 3 and e.g. Eq. 2 here. "
                                                      "Then it ends.")), 2)


class ReportTests(Base):
    def test_the_report_has_the_spanish_schema_plus_its_language(self) -> None:
        english = self.audit_text("The team measures the voice. Then it records the rhythm.")
        spanish = self.audit_text("El equipo mide la voz. Luego anota el ritmo.", SPANISH, "auditar")
        self.assertEqual(set(english) - {"idioma"}, set(spanish))
        self.assertEqual(english["idioma"], "en")
        self.assertNotIn("idioma", spanish)
        self.assertIn("readability", english["aviso"])

    def test_a_run_gets_json_and_markdown(self) -> None:
        run = self.make_run({"02_justificacion": "The team measures the voice. Then it records the rhythm."})
        result = cli(SCRIPT, "audit", run)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((run / "artefactos" / "estilo" / "reporte.json").read_text(encoding="utf-8"))
        self.assertEqual(data["idioma"], "en")
        self.assertIn("# Style report", (run / "artefactos" / "estilo" / "reporte.md").read_text(encoding="utf-8"))

    def test_spanish_command_names_are_accepted(self) -> None:
        run = self.make_run({"02_justificacion": "The team measures. It records.",
                             "04_estado_arte": "The panel reviews. It agrees."})
        result = cli(SCRIPT, "auditar", run, "--seccion", "2", "--todo", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["alcance"], "seccion_contra_documento")

    def test_a_missing_run_is_an_input_error(self) -> None:
        result = cli(SCRIPT, "audit", self.tmp / "nope")
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not exist", result.stderr)


class VerifyTests(Base):
    BEFORE = (r"In March 2025 the pilot \citep{perez2020} reached 42\% with \$1.000 million at TRL 6 to 7 "
              r"(see \cref{tab:x}).")

    def verify(self, after: str) -> subprocess.CompletedProcess:
        a, b = self.tmp / "a.tex", self.tmp / "b.tex"
        a.write_text(self.BEFORE, encoding="utf-8")
        b.write_text(after, encoding="utf-8")
        return cli(SCRIPT, "verify", a, b, "--json")

    def test_a_change_of_style_only_passes(self) -> None:
        result = self.verify(r"The pilot \citep{perez2020} reached 42\% in March 2025 with \$1.000 million at "
                             r"TRL 6 to 7 (see \cref{tab:x}).")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_each_fact_change_fails_and_names_its_class(self) -> None:
        for after, kind in (
            (self.BEFORE.replace("42", "43"), "numeros"),
            (self.BEFORE.replace("March", "April"), "fechas"),
            (self.BEFORE.replace("perez2020", "perez2021"), "citas"),
            (self.BEFORE.replace("1.000 million", "1.000 billion"), "dinero"),
            (self.BEFORE.replace("TRL 6 to 7", "TRL 6"), "trl"),
            (self.BEFORE.replace("tab:x", "tab:y"), "referencias"),
        ):
            with self.subTest(kind=kind):
                result = self.verify(after)
                self.assertEqual(result.returncode, 1)
                self.assertIn(kind, {d["clase"] for f in json.loads(result.stdout)["archivos"]
                                     for d in f["diferencias"]})

    def test_the_text_output_is_english(self) -> None:
        a, b = self.tmp / "a.tex", self.tmp / "b.tex"
        a.write_text("It reached 42.", encoding="utf-8")
        b.write_text("It reached 43.", encoding="utf-8")
        result = cli(SCRIPT, "verify", a, b)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Facts that had to stay identical changed", result.stdout)


class SkillTests(unittest.TestCase):
    BANNED = (
        "detección de ia", "detector", "detectability", "ai detection", "ai risk", "evasion", "perplexity",
        "burstiness", "generated by ai", "ai patterns", "signs of ai", "ai cleanup", "ai clichés", "ai-written",
        "sound human", "pass as human", "undetectable",
    )

    @classmethod
    def setUpClass(cls) -> None:
        cls.style = STYLE_SKILL.read_text(encoding="utf-8")
        cls.redundancy = REDUNDANCY_SKILL.read_text(encoding="utf-8")

    def test_no_ai_detection_framing(self) -> None:
        for path in (SCRIPT, STYLE_SKILL, REDUNDANCY_SKILL):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in self.BANNED:
                with self.subTest(path=path.name, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_frontmatter_names_the_skills(self) -> None:
        self.assertTrue(self.style.startswith("---\nname: estilo-natural-en\n"))
        self.assertTrue(self.redundancy.startswith("---\nname: depuracion-redundancias-en\n"))

    def test_the_skills_keep_the_spanish_guarantees(self) -> None:
        for text in (self.style, self.redundancy):
            self.assertRegex(text, r"8\D{1,6}15")
            self.assertRegex(text, r"25\D{1,6}40")
            self.assertIn("45", text)
            self.assertIn("estilo_en.py verify", text)
        self.assertIn("estilo_en.py audit", self.style)
        for needle in (r"\citep", "TRL", "em dash", "--", "delve", "tapestry", "not only", "estilo-natural-es"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.style)

    def test_the_spanish_skills_point_to_their_english_siblings(self) -> None:
        es = (REPO / ".claude" / "skills" / "estilo-natural-es" / "SKILL.md").read_text(encoding="utf-8")
        dep = (REPO / ".claude" / "skills" / "depuracion-redundancias-es" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("estilo-natural-en", es)
        self.assertIn("depuracion-redundancias-en", dep)


class RegistrationTests(unittest.TestCase):
    def test_kit_and_ports_carry_the_new_files(self) -> None:
        manifest = json.loads((REPO / "scripts" / "kit-manifest.json").read_text(encoding="utf-8"))["kit_paths"]
        for path in ("scripts/estilo_en.py", ".claude/skills/estilo-natural-en/SKILL.md",
                     ".claude/skills/depuracion-redundancias-en/SKILL.md"):
            self.assertIn(path, manifest)
        pi = json.loads((REPO / "scripts" / "gen-pi.rules.json").read_text(encoding="utf-8"))["paths"]["skill_files"]
        for skill in ("estilo-natural-en", "depuracion-redundancias-en"):
            self.assertIn(f"{skill}/SKILL.md", pi)
            self.assertTrue((REPO / ".pi" / "skills" / skill / "SKILL.md").is_file())
            self.assertTrue((REPO / ".agent" / "skills" / skill / "SKILL.md").is_file())
            self.assertIn(f"`{skill}`", (REPO / "AGENTS.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
