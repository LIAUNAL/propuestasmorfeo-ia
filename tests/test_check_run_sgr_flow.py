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

from test_cadena_valor_sgr import TREE, _valid_chain  # noqa: E402

CHECK = REPO / "scripts" / "check_run.py"
NEW_PREFIXES = ("cadena-", "sgr-estilo-")

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

    def test_base_run_never_calls_the_style_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            check = _isolated_check(Path(tmp), with_stub=True)
            run = _make_run(Path(tmp))
            self.assertFalse([c for c in _codes(_findings(run, "base", check)) if c.startswith(NEW_PREFIXES)])


def _isolated_check(tmp: Path, with_stub: bool) -> Path:
    """check_run and cadena_valor_sgr copied to their own folder, with or without a stub estilo_sgr."""
    scripts = tmp / "scripts"
    scripts.mkdir()
    for name in ("check_run.py", "cadena_valor_sgr.py"):
        shutil.copy(REPO / "scripts" / name, scripts / name)
    if with_stub:
        (scripts / "estilo_sgr.py").write_text(STUB_ESTILO, encoding="utf-8")
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


class KitCopy(unittest.TestCase):
    def test_kit_copy_is_byte_identical(self) -> None:
        kit = REPO / "src" / "morfeo" / "_kit" / "scripts" / "check_run.py"
        self.assertEqual(kit.read_bytes(), CHECK.read_bytes())


if __name__ == "__main__":
    unittest.main()
