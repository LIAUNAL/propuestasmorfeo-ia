"""scripts/novedad.py: novelty pillars, hypotheses and the project matrix (odd/tasks/tablero-juez-novedad.md, T5: S4).

The investigador (MODE=novedad) writes a draft with the novelty pillars, the
hypotheses and their experiments, actions, implementations, interventions or
transfers, linked to the direct causes and specific objectives of the trees.
The script validates the draft strictly, dates it and writes
artefactos/novedad/novedad.json (schema morfeo.novedad/v1) atomically; `matriz`
derives the value-chain matrix, one row per specific objective. The tests run
the real script as a subprocess (public interface).
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "novedad.py"

CAUSAS = [
    {"id": "CD1", "texto": "Procesado multimodal de biomarcadores de salud mental"},
    {"id": "CD2", "texto": "Despliegue portable en terreno posdesastre"},
    {"id": "CD3", "texto": "Transferencia y evidencia local"},
]
OBJETIVOS = [
    {"id": "OE1", "causa": "CD1",
     "texto": "Desarrollar una estrategia de procesado multimodal que alinee instancias del habla con patrones de depresión."},
    {"id": "OE2", "causa": "CD2",
     "texto": "Diseñar un esquema de despliegue portable con inferencia local sobre dispositivos móviles."},
    {"id": "OE3", "causa": "CD3",
     "texto": "Implementar la transferencia del sistema a los estudiantes universitarios afectados por el sismo."},
]
PROBLEMA = "Identificación tardía de patrones de depresión en la población estudiantil afectada por el sismo."
GENERAL = "Desarrollar un sistema portable que identifique patrones de depresión en estudiantes afectados por el sismo."


def experiment(eid: str, tipo: str, titulo: str) -> dict:
    return {
        "id": eid, "tipo": tipo, "titulo": titulo,
        "descripcion": f"Descripción de {titulo.lower()} con su diseño y su población.",
        "metrica": f"Indicador de {titulo.lower()}",
        "producto": f"Producto de {titulo.lower()}",
        "resultado_esperado": f"Evidencia verificable de {titulo.lower()}.",
    }


DRAFT = {
    "schema": "morfeo.novedad/v1",
    "problema_central": PROBLEMA,
    "objetivo_general": GENERAL,
    "causas": CAUSAS,
    "objetivos": OBJETIVOS,
    "pilares": [
        {"id": "P1", "nombre": "Alineación instancia y síntoma", "resumen": "Cada instancia del habla se asocia a un ítem del PHQ-8.",
         "detalle": "La agregación deja de ser implícita y pasa a ser supervisada por ítem.", "objetivos": ["OE1"], "causas": ["CD1"]},
        {"id": "P2", "nombre": "Inferencia local sin conectividad", "resumen": "El modelo corre en el dispositivo sin depender de la nube.",
         "detalle": "La compresión del modelo se ajusta al hardware disponible en campo.", "objetivos": ["OE2"], "causas": ["CD2"]},
        {"id": "P3", "nombre": "Apropiación en la comunidad universitaria", "resumen": "Bienestar universitario adopta el tamizaje en su ruta de atención.",
         "detalle": "La transferencia incluye protocolos, formación y seguimiento.", "objetivos": ["OE3", "OE2"], "causas": ["CD3"]},
    ],
    "hipotesis": [
        {"id": "H1", "titulo": "La alineación mejora la detección",
         "enunciado": "Si cada instancia se alinea con su síntoma, la detección de patrones de depresión es más sensible que con la agregación implícita.",
         "pilares": ["P1"], "objetivos": ["OE1"], "experimentos": [experiment("E1", "experimento", "Comparación de agregaciones")]},
        {"id": "H2", "titulo": "El despliegue local conserva el desempeño",
         "enunciado": "Un modelo comprimido que corre en el dispositivo conserva el desempeño del modelo completo en las condiciones de campo.",
         "pilares": ["P2"], "objetivos": ["OE2"], "experimentos": [experiment("E2", "implementacion", "Aplicación móvil de tamizaje")]},
        {"id": "H3", "titulo": "La transferencia sostiene el uso",
         "enunciado": "Una ruta de atención que integra el tamizaje portable aumenta el uso sostenido por parte de bienestar universitario.",
         "pilares": ["P3", "P2"], "objetivos": ["OE3"],
         "experimentos": [experiment("E3", "transferencia", "Protocolo con bienestar universitario"),
                          experiment("E4", "intervencion", "Jornadas de tamizaje en los campus")]},
    ],
    "efectos": [{"id": "EF1", "texto": "Subdiagnóstico de la sintomatología depresiva en la ventana posdesastre."}],
}


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=REPO)


def make_run(tmp: str) -> Path:
    run = Path(tmp) / "proposals" / "run-novedad"
    (run / "artefactos").mkdir(parents=True)
    return run


def draft_path(run: Path) -> Path:
    return run / "artefactos" / "novedad" / "novedad_borrador.json"


def record_path(run: Path) -> Path:
    return run / "artefactos" / "novedad" / "novedad.json"


def write_draft(run: Path, data) -> Path:
    path = draft_path(run)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def write_trees(run: Path, *, objective_texts: list[str] | None = None, groups: int = 3,
                trunk: str = PROBLEMA, general: str = GENERAL) -> None:
    spec = {
        "kind": "arbol",
        "groups": [{"id": f"SP{i + 1}", "title": f"SP{i + 1} · {CAUSAS[i % 3]['texto'].replace(' ', chr(10), 1)}",
                    "causes": [{"id": f"r{i + 1}", "text": "Causa indirecta del subproblema."}]} for i in range(groups)],
        "trunk": {"label": "PROBLEMA CENTRAL", "text": trunk},
        "branches": [{"id": "b1", "text": "Subdiagnóstico y detección tardía."},
                     {"id": "b2", "text": "Sobrecarga del personal especializado."}],
        "crown": {"label": "EFECTO FINAL", "text": "Deterioro del bienestar de la comunidad universitaria."},
    }
    specs = run / "redaccion" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / "arbol_problemas.spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    texts = objective_texts if objective_texts is not None else [o["texto"] for o in OBJETIVOS]
    tree = {
        "groups": [{"id": f"OE{i + 1}", "from": f"SP{i + 1}", "title": f"OE{i + 1}", "objective": text, "means": []}
                   for i, text in enumerate(texts)],
        "trunk": {"label": "OBJETIVO GENERAL", "text": general},
        "branches": [], "crown": {"label": "FIN ÚLTIMO", "text": None},
    }
    arboles = run / "artefactos" / "arboles"
    arboles.mkdir(parents=True, exist_ok=True)
    (arboles / "arbol_objetivos.json").write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")


def validate(run: Path, data) -> tuple[int, list[str]]:
    write_draft(run, data)
    proc = run_cli("validar", str(run), "--borrador", str(draft_path(run)), "--json")
    return proc.returncode, json.loads(proc.stdout)["errores"]


class TestRegister(unittest.TestCase):
    def test_a_valid_draft_is_recorded_dated_and_the_draft_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            write_draft(run, DRAFT)
            proc = run_cli("registrar", str(run))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            record = json.loads(record_path(run).read_text(encoding="utf-8"))
            self.assertEqual(record["schema"], "morfeo.novedad/v1")
            self.assertRegex(record["fecha"], r"^\d{4}-\d{2}-\d{2}$")
            for key in ("problema_central", "objetivo_general", "causas", "objetivos", "pilares", "hipotesis", "efectos"):
                self.assertEqual(record[key], DRAFT[key], key)
            self.assertFalse(draft_path(run).exists())
            self.assertEqual(run_cli("validar", str(run)).returncode, 0)

    def test_an_invalid_draft_writes_nothing_and_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            bad = copy.deepcopy(DRAFT)
            bad["hipotesis"][0]["experimentos"] = []
            write_draft(run, bad)
            proc = run_cli("registrar", str(run))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("H1", proc.stderr)
            self.assertFalse(record_path(run).exists())
            self.assertTrue(draft_path(run).exists())

    def test_a_missing_draft_or_run_is_exit_code_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            self.assertEqual(run_cli("registrar", str(run)).returncode, 2)
            self.assertEqual(run_cli("registrar", str(run / "nope")).returncode, 2)
            self.assertEqual(run_cli("matriz", str(run)).returncode, 2)

    def test_the_draft_cannot_carry_the_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, errors = validate(make_run(tmp), {**DRAFT, "fecha": "2026-01-01"})
            self.assertEqual(code, 1)
            self.assertTrue(any("fecha" in e for e in errors), errors)


class TestValidation(unittest.TestCase):
    def assertRejected(self, mutate, *needles: str) -> None:
        data = copy.deepcopy(DRAFT)
        mutate(data)
        with tempfile.TemporaryDirectory() as tmp:
            code, errors = validate(make_run(tmp), data)
        self.assertEqual(code, 1, f"accepted: {needles}")
        joined = " | ".join(errors)
        for needle in needles:
            self.assertIn(needle, joined)

    def test_the_valid_fixture_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(validate(make_run(tmp), DRAFT), (0, []))

    def test_every_reference_must_resolve(self):
        cases = {
            "objective cause": (lambda d: d["objetivos"][0].update(causa="CD9"), "CD9"),
            "pillar objective": (lambda d: d["pilares"][0]["objetivos"].append("OE9"), "OE9"),
            "pillar cause": (lambda d: d["pilares"][0]["causas"].append("CD7"), "CD7"),
            "hypothesis pillar": (lambda d: d["hipotesis"][0]["pilares"].append("P9"), "P9"),
            "hypothesis objective": (lambda d: d["hipotesis"][0]["objetivos"].append("OE8"), "OE8"),
        }
        for name, (mutate, needle) in cases.items():
            with self.subTest(name):
                self.assertRejected(mutate, needle)

    def test_ids_follow_their_format_and_are_unique(self):
        cases = {
            "pillar id": (lambda d: d["pilares"][0].update(id="X1"), "X1"),
            "duplicate hypothesis": (lambda d: d["hipotesis"][1].update(id="H1"), "H1"),
            "duplicate experiment across hypotheses": (lambda d: d["hipotesis"][1]["experimentos"][0].update(id="E1"), "E1"),
            "cause id": (lambda d: d["causas"][0].update(id="SP1"), "SP1"),
        }
        for name, (mutate, needle) in cases.items():
            with self.subTest(name):
                self.assertRejected(mutate, needle)

    def test_each_objective_needs_a_pillar_and_a_hypothesis(self):
        def no_pillar(d):
            d["pilares"][1]["objetivos"] = ["OE1"]
            d["pilares"][2]["objetivos"] = ["OE3"]

        self.assertRejected(no_pillar, "OE2", "pilar")
        self.assertRejected(lambda d: d["hipotesis"][1].update(objetivos=["OE1"]), "OE2", "hipótesis")

    def test_each_hypothesis_needs_an_experiment_or_action_of_a_known_type(self):
        self.assertRejected(lambda d: d["hipotesis"][1].update(experimentos=[]), "H2")
        self.assertRejected(lambda d: d["hipotesis"][0]["experimentos"][0].update(tipo="simulacion"), "simulacion")

    def test_each_pillar_supports_a_hypothesis(self):
        def orphan(d):
            d["hipotesis"][2]["pilares"] = ["P3"]
            d["hipotesis"][1]["pilares"] = ["P1"]

        self.assertRejected(orphan, "P2")

    def test_causes_and_objectives_map_one_to_one(self):
        self.assertRejected(lambda d: d["objetivos"][1].update(causa="CD1"), "CD1")
        self.assertRejected(lambda d: d["causas"].append({"id": "CD4", "texto": "Una cuarta causa directa"}), "causas")

    def test_unknown_fields_and_length_caps(self):
        self.assertRejected(lambda d: d["pilares"][0].update(color="#fff"), "color")
        self.assertRejected(lambda d: d["hipotesis"][0].update(titulo="x"), "titulo")
        self.assertRejected(lambda d: d["pilares"][0].update(resumen="r" * 2000), "resumen")

    def test_objectives_and_hypotheses_stay_qualitative_without_percent_targets_or_trl(self):
        self.assertRejected(lambda d: d.update(objetivo_general=GENERAL[:-1] + " con un 80 % de exactitud."),
                            "objetivo_general", "%")
        self.assertRejected(lambda d: d["objetivos"][0].update(texto=OBJETIVOS[0]["texto"][:-1] + " al 90%."), "OE1", "%")
        self.assertRejected(lambda d: d["hipotesis"][0].update(enunciado=d["hipotesis"][0]["enunciado"][:-1]
                                                                + " en un 15,5 %."), "H1", "%")
        self.assertRejected(lambda d: d["objetivos"][2].update(texto=OBJETIVOS[2]["texto"][:-1] + " hasta TRL 6."),
                            "OE3", "TRL")


class TestTrees(unittest.TestCase):
    def test_matching_trees_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            write_trees(run)
            self.assertEqual(validate(run, DRAFT), (0, []))

    def test_texts_that_differ_from_the_trees_are_rejected_with_the_expected_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            write_trees(run, objective_texts=["Otro objetivo uno.", OBJETIVOS[1]["texto"], OBJETIVOS[2]["texto"]])
            code, errors = validate(run, DRAFT)
            self.assertEqual(code, 1)
            joined = " | ".join(errors)
            self.assertIn("OE1", joined)
            self.assertIn("Otro objetivo uno.", joined)
            write_trees(run, trunk="Otro problema central del árbol.")
            code, errors = validate(run, DRAFT)
            self.assertTrue(any("problema_central" in e for e in errors), errors)
            write_trees(run, general="Otro objetivo general.")
            code, errors = validate(run, DRAFT)
            self.assertTrue(any("objetivo_general" in e for e in errors), errors)

    def test_a_cause_that_differs_from_its_tree_group_is_rejected(self):
        data = copy.deepcopy(DRAFT)
        data["causas"][1]["texto"] = "Una causa que el árbol no tiene"
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            write_trees(run)
            code, errors = validate(run, data)
            self.assertEqual(code, 1)
            self.assertTrue(any("CD2" in e and "Despliegue portable en terreno posdesastre" in e for e in errors), errors)

    def test_the_number_of_causes_follows_the_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            write_trees(run, groups=4, objective_texts=[o["texto"] for o in OBJETIVOS] + ["Cuarto objetivo."])
            code, errors = validate(run, DRAFT)
            self.assertEqual(code, 1)
            self.assertTrue(any("4" in e and "causas" in e for e in errors), errors)


class TestMatrix(unittest.TestCase):
    def _matrix(self, run: Path) -> dict:
        write_draft(run, DRAFT)
        self.assertEqual(run_cli("registrar", str(run)).returncode, 0)
        proc = run_cli("matriz", str(run))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_one_row_per_objective_follows_the_value_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            matrix = self._matrix(make_run(tmp))
        self.assertEqual(matrix["problema_central"], PROBLEMA)
        self.assertEqual(matrix["objetivo_general"], GENERAL)
        self.assertEqual([r["objetivo"]["id"] for r in matrix["filas"]], ["OE1", "OE2", "OE3"])
        oe2 = matrix["filas"][1]
        self.assertEqual(oe2["causa"], {"id": "CD2", "texto": CAUSAS[1]["texto"]})
        self.assertEqual(oe2["objetivo"]["texto"], OBJETIVOS[1]["texto"])
        self.assertEqual([p["id"] for p in oe2["pilares"]], ["P2", "P3"])
        self.assertEqual([h["id"] for h in oe2["hipotesis"]], ["H2"])
        self.assertEqual([(e["id"], e["tipo"], e["hipotesis"]) for e in oe2["experimentos"]], [("E2", "implementacion", "H2")])
        self.assertEqual(oe2["productos"], ["Producto de aplicación móvil de tamizaje"])
        self.assertEqual(oe2["indicadores"], ["Indicador de aplicación móvil de tamizaje"])
        self.assertEqual(oe2["resultados"], ["Evidencia verificable de aplicación móvil de tamizaje."])
        oe3 = matrix["filas"][2]
        self.assertEqual([e["tipo"] for e in oe3["experimentos"]], ["transferencia", "intervencion"])
        self.assertEqual(matrix["totales"], {
            "objetivos": 3, "pilares": 3, "hipotesis": 3, "experimentos": 4,
            "por_tipo": {"experimento": 1, "intervencion": 1, "transferencia": 1, "implementacion": 1, "accion": 0},
        })

    def test_effects_come_from_the_problem_tree_when_it_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            without = self._matrix(run)
            self.assertEqual(without["fuente_efectos"], "novedad")
            self.assertEqual([e["id"] for e in without["efectos"]], ["EF1"])
            self.assertEqual(without["filas"][0]["efectos"], ["EF1"])
            write_trees(run)
            proc = run_cli("matriz", str(run))
            matrix = json.loads(proc.stdout)
        self.assertEqual(matrix["fuente_efectos"], "arbol")
        self.assertEqual([(e["id"], e["texto"]) for e in matrix["efectos"]],
                         [("b1", "Subdiagnóstico y detección tardía."), ("b2", "Sobrecarga del personal especializado.")])
        self.assertEqual(matrix["efecto_final"], "Deterioro del bienestar de la comunidad universitaria.")
        self.assertTrue(all(row["efectos"] == ["b1", "b2"] for row in matrix["filas"]))


class TestScriptStaysStdlib(unittest.TestCase):
    def test_only_the_standard_library_is_imported(self):
        text = SCRIPT.read_text(encoding="utf-8")
        modules = set(re.findall(r"^(?:from|import)\s+([a-zA-Z_][\w]*)", text, re.M))
        self.assertTrue(modules <= {"__future__", "argparse", "datetime", "importlib", "json", "os", "re", "sys",
                                    "tempfile", "unicodedata", "pathlib", "typing"}, modules)


if __name__ == "__main__":
    unittest.main()
