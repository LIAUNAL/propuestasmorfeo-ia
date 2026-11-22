"""scripts/juez_avance.py: validation and recording of the stage judge (odd/tasks/tablero-juez-novedad.md, S2).

The juez-avance agent writes a draft; the script validates it and records the
round in artefactos/juez/avance_<etapa>.json (schema morfeo.juez-avance/v1),
appending the previous round to `historial`. The tests run the real script as
a subprocess (public interface) and import it only to force a failed write.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "juez_avance.py"

DRAFT = {
    "puntaje": 68,
    "veredicto": "Idea pertinente con árbol coherente; falta la magnitud con fuente.",
    "resumen_idea": "Plataforma de monitoreo hídrico con IA para los municipios de Caldas, apoyada en sensores comunitarios.",
    "fortalezas": [
        {"texto": "El problema central conserva la variable medible del TDR.",
         "evidencia": "redaccion/specs/arbol_problemas.spec.json, tronco"},
    ],
    "debilidades": [
        {"texto": "La magnitud del problema no cita su fuente.",
         "evidencia": "artefactos/mga_resumido.md, Magnitud del problema",
         "accion": "Agregar la cifra del IDEAM con año y enlace en la tabla de indicadores."},
    ],
    "alertas": [
        {"nivel": "alta", "texto": "La causa directa 2 repite la 1 con otras palabras.",
         "donde": "árbol de problemas, SP2"},
        {"nivel": "baja", "texto": "El efecto final está redactado como solución.", "donde": "copa del árbol"},
    ],
}


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=REPO)


def make_run(tmp: str) -> Path:
    run = Path(tmp) / "proposals" / "run-avance"
    (run / "artefactos").mkdir(parents=True)
    return run


def write_draft(run: Path, data, etapa: str = "arbol") -> Path:
    path = run / "artefactos" / "juez" / f"avance_{etapa}_borrador.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def record_path(run: Path, etapa: str = "arbol") -> Path:
    return run / "artefactos" / "juez" / f"avance_{etapa}.json"


def load_module():
    spec = importlib.util.spec_from_file_location("juez_avance_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRegistrar(unittest.TestCase):
    def test_a_valid_draft_becomes_round_one_with_the_schema_and_an_iso_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            draft = write_draft(run, DRAFT)
            proc = run_cli("registrar", str(run), "--etapa", "arbol")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("ronda 1", proc.stdout)
            data = json.loads(record_path(run).read_text(encoding="utf-8"))
            self.assertEqual(data["schema"], "morfeo.juez-avance/v1")
            self.assertEqual(data["etapa"], "arbol")
            self.assertEqual(data["ronda"], 1)
            self.assertRegex(data["fecha"], r"^\d{4}-\d{2}-\d{2}$")
            for key in ("puntaje", "veredicto", "resumen_idea", "fortalezas", "debilidades", "alertas"):
                self.assertEqual(data[key], DRAFT[key], key)
            self.assertEqual(data["historial"], [])
            self.assertFalse(draft.exists(), "a registered draft is removed so it cannot be recorded twice")

    def test_a_second_round_appends_the_first_to_the_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            write_draft(run, DRAFT)
            self.assertEqual(run_cli("registrar", str(run), "--etapa", "arbol").returncode, 0)
            second = copy.deepcopy(DRAFT)
            second["puntaje"] = 81
            second["veredicto"] = "La magnitud ya tiene fuente."
            write_draft(run, second)
            proc = run_cli("registrar", str(run), "--etapa", "arbol", "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["ronda"], 2)
            data = json.loads(record_path(run).read_text(encoding="utf-8"))
            self.assertEqual((data["ronda"], data["puntaje"]), (2, 81))
            self.assertEqual([h["ronda"] for h in data["historial"]], [1])
            first = data["historial"][0]
            self.assertEqual(first["puntaje"], 68)
            self.assertEqual(first["veredicto"], DRAFT["veredicto"])
            self.assertEqual(first["fortalezas"], DRAFT["fortalezas"])
            self.assertNotIn("historial", first)
            self.assertNotIn("schema", first)
            write_draft(run, DRAFT)
            self.assertEqual(run_cli("registrar", str(run), "--etapa", "arbol").returncode, 0)
            data = json.loads(record_path(run).read_text(encoding="utf-8"))
            self.assertEqual([h["ronda"] for h in data["historial"]], [1, 2])
            self.assertEqual(data["ronda"], 3)

    def test_each_stage_keeps_its_own_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            write_draft(run, DRAFT, etapa="novedad")
            proc = run_cli("registrar", str(run), "--etapa", "novedad")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(record_path(run, "novedad").is_file())
            self.assertFalse(record_path(run, "arbol").exists())
            self.assertEqual(json.loads(record_path(run, "novedad").read_text(encoding="utf-8"))["etapa"], "novedad")

    def test_an_explicit_draft_path_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            other = Path(tmp) / "otro.json"
            other.write_text(json.dumps(DRAFT, ensure_ascii=False), encoding="utf-8")
            proc = run_cli("registrar", str(run), "--etapa", "arbol", "--borrador", str(other))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(record_path(run).read_text(encoding="utf-8"))["puntaje"], 68)

    def test_an_invalid_draft_writes_nothing_and_lists_the_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            bad = copy.deepcopy(DRAFT)
            bad["puntaje"] = 140
            draft = write_draft(run, bad)
            proc = run_cli("registrar", str(run), "--etapa", "arbol")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("puntaje", proc.stderr)
            self.assertFalse(record_path(run).exists())
            self.assertTrue(draft.exists(), "an invalid draft stays for the agent to fix")

    def test_an_invalid_draft_leaves_the_previous_record_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            write_draft(run, DRAFT)
            self.assertEqual(run_cli("registrar", str(run), "--etapa", "arbol").returncode, 0)
            before = record_path(run).read_bytes()
            write_draft(run, {**DRAFT, "fortalezas": []})
            self.assertEqual(run_cli("registrar", str(run), "--etapa", "arbol").returncode, 1)
            self.assertEqual(record_path(run).read_bytes(), before)

    def test_missing_draft_or_unknown_stage_exit_with_code_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            proc = run_cli("registrar", str(run), "--etapa", "arbol")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("avance_arbol_borrador.json", proc.stderr)
            write_draft(run, DRAFT)
            self.assertEqual(run_cli("registrar", str(run), "--etapa", "final").returncode, 2)
            self.assertEqual(run_cli("registrar", str(Path(tmp) / "no-existe"), "--etapa", "arbol").returncode, 2)

    def test_a_corrupt_previous_record_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            write_draft(run, DRAFT)
            record_path(run).write_text("{roto", encoding="utf-8")
            proc = run_cli("registrar", str(run), "--etapa", "arbol")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("avance_arbol.json", proc.stderr)
            self.assertEqual(record_path(run).read_text(encoding="utf-8"), "{roto")

    def test_the_write_is_atomic_a_failed_replace_keeps_the_old_file_and_leaves_no_temp(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "avance_arbol.json"
            target.write_text('{"viejo": true}', encoding="utf-8")
            with mock.patch.object(module.os, "replace", side_effect=OSError("disco lleno")):
                with self.assertRaises(OSError):
                    module.write_atomic(target, {"nuevo": True})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"viejo": True})
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["avance_arbol.json"])


class TestValidar(unittest.TestCase):
    def _errors(self, run: Path, data) -> tuple[int, list[str]]:
        write_draft(run, data)
        proc = run_cli("validar", str(run), "--etapa", "arbol", "--borrador",
                       str(run / "artefactos" / "juez" / "avance_arbol_borrador.json"), "--json")
        return proc.returncode, json.loads(proc.stdout)["errores"]

    def test_the_reference_draft_is_valid_and_validar_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            code, errors = self._errors(run, DRAFT)
            self.assertEqual((code, errors), (0, []))
            self.assertFalse(record_path(run).exists())

    def test_empty_alerts_are_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            self.assertEqual(self._errors(run, {**DRAFT, "alertas": []}), (0, []))

    def test_each_rule_is_reported(self):
        cases = {
            "puntaje": [{"puntaje": -1}, {"puntaje": 101}, {"puntaje": 70.5}, {"puntaje": True}, {"puntaje": "70"}],
            "veredicto": [{"veredicto": ""}, {"veredicto": "x" * 300}, {"veredicto": 3}],
            "resumen_idea": [{"resumen_idea": "corto"}, {"resumen_idea": "x" * 3000}],
            "fortalezas": [{"fortalezas": []}, {"fortalezas": "texto"}, {"fortalezas": [{"texto": "Algo bueno aquí"}]},
                           {"fortalezas": [{"texto": "Algo bueno aquí", "evidencia": "§3", "extra": 1}]},
                           {"fortalezas": [{"texto": "Algo", "evidencia": "§3"}] * 11}],
            "debilidades": [{"debilidades": []}, {"debilidades": [{"texto": "Falta la fuente", "evidencia": "§3"}]}],
            "alertas": [{"alertas": [{"nivel": "critica", "texto": "Algo grave", "donde": "§3"}]},
                        {"alertas": [{"nivel": "alta", "texto": "Algo grave"}]}, {"alertas": None}],
            "etapa": [{"etapa": "novedad"}],
            "schema": [{"schema": "otro/v1"}],
            "desconocido": [{"desconocido": 1}],
            "ronda": [{"ronda": 4}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            for field, variants in cases.items():
                for variant in variants:
                    with self.subTest(field=field, variant=str(variant)[:60]):
                        code, errors = self._errors(run, {**DRAFT, **variant})
                        self.assertEqual(code, 1)
                        self.assertTrue(any(field in e for e in errors), errors)
            code, errors = self._errors(run, ["no", "objeto"])
            self.assertEqual(code, 1)
            code, errors = self._errors(run, {k: v for k, v in DRAFT.items() if k != "resumen_idea"})
            self.assertEqual(code, 1)
            self.assertTrue(any("resumen_idea" in e for e in errors), errors)

    def test_validar_without_draft_checks_the_recorded_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            write_draft(run, DRAFT)
            self.assertEqual(run_cli("registrar", str(run), "--etapa", "arbol").returncode, 0)
            proc = run_cli("validar", str(run), "--etapa", "arbol")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(record_path(run).read_text(encoding="utf-8"))
            data["historial"] = [{"ronda": 5}]
            record_path(run).write_text(json.dumps(data), encoding="utf-8")
            proc = run_cli("validar", str(run), "--etapa", "arbol")
            self.assertEqual(proc.returncode, 1)
            self.assertRegex(proc.stderr, re.compile("historial", re.I))


if __name__ == "__main__":
    unittest.main()
