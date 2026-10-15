"""El inventario de unidades del pipeline y la tabla de pasos no pueden divergir.

La tabla de `.claude/commands/_propuesta-steps.md` se declara a sí misma SSOT, y
sin embargo `status.py` mantenía una lista canónica de compuertas que no coincidía
con ella: le faltaban `G1a` y `G1b`, que la corrida de referencia sí pasó, y
llevaba `G6` y `G6.45`, que la tabla declara sin compuerta. Estas pruebas fijan el
inventario y atan las dos piezas, de modo que la divergencia vuelva a fallar aquí
y no en el tablero.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from morfeo.core.pipeline_units import (  # noqa: E402
    GATE_ALIASES,
    LEGACY_GATELESS_LABELS,
    PIPELINE_UNITS,
    canonical_gates,
    normalise_gate,
)

STEPS_DOC = REPO / ".claude" / "commands" / "_propuesta-steps.md"

STEP_UNITS_EXPECTED = 14

# Valores de compuerta observados en los artefactos de la corrida de referencia,
# incluidos los que la tabla no reconoce. El inventario tiene que ubicarlos todos:
# o son un id canónico, o están declarados como etiqueta sin compuerta.
OBSERVED_IN_ARTIFACTS = (
    "G0.5",
    "G1a",
    "G1b",
    "G1",
    "G2",
    "G3",
    "G4",
    "G5",
    "G5.5",
    "G6",
    "G6.4",
    "G6.45",
    "G6.46",
    "G6.5",
    "G7",
    "G-Presupuesto",
    "G budget",
    "G comunidades",
    "G front",
    "G final",
)


def _step_table_gates() -> dict[str, str | None]:
    """Lee la columna Gate de la tabla de pasos, normalizada por los alias.

    Se ciñe a la sección de la tabla de pasos: la de unidades pre-intake tiene
    otras columnas y contaminaría la lectura.
    """
    text = STEPS_DOC.read_text(encoding="utf-8")
    start = text.index("## Step sequence (post-intake)")
    end = text.index("\n## ", start + 10)
    rows: dict[str, str | None] = {}
    for line in text[start:end].splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        unit = cells[0].strip("` ")
        if unit == "done" or not unit.startswith("fase"):
            continue
        raw = cells[2].strip()
        rows[unit] = None if raw in ("—", "-", "") else normalise_gate(raw)
    return rows


class TestPipelineUnits(unittest.TestCase):
    def test_step_table_is_readable_and_complete(self) -> None:
        gates = _step_table_gates()
        self.assertEqual(
            len(gates),
            STEP_UNITS_EXPECTED,
            f"la tabla debe declarar {STEP_UNITS_EXPECTED} unidades, leí {sorted(gates)}",
        )

    def test_inventory_matches_the_step_table_exactly(self) -> None:
        declared = {u["id"]: u["gate"] for u in PIPELINE_UNITS if u["kind"] == "step"}
        self.assertEqual(
            declared,
            _step_table_gates(),
            "el inventario y la tabla de pasos divergen en unidades o compuertas",
        )

    def test_no_unit_invents_a_gate_it_does_not_have(self) -> None:
        # Solo las unidades de paso: `g0_5` es pre-intake y tampoco tiene
        # compuerta, lo cual es correcto.
        sin_gate = sorted(
            u["id"]
            for u in PIPELINE_UNITS
            if u["kind"] == "step" and u["gate"] is None
        )
        self.assertEqual(
            sin_gate,
            ["fase6", "fase6_45"],
            "solo esas dos unidades se quedan sin compuerta, según la tabla de pasos",
        )
        canonical = {g["id"] for g in canonical_gates()}
        for phantom in ("G6", "G6.45"):
            self.assertNotIn(
                phantom, canonical, f"{phantom} no es compuerta de ninguna unidad"
            )

    def test_the_gates_the_reference_run_passed_are_canonical(self) -> None:
        canonical = {g["id"] for g in canonical_gates()}
        for real in (
            "G0.5", "G1a", "G1b", "G1", "G2", "G3", "G4",
            "G5", "G5.5", "G6.4", "G6.46", "G6.5", "G7",
        ):
            self.assertIn(real, canonical, f"falta {real} en las compuertas canónicas")
        self.assertEqual(len(canonical), 13, "las compuertas canónicas son trece")

    def test_alias_map_places_every_observed_value(self) -> None:
        canonical = {g["id"] for g in canonical_gates()}
        for value in OBSERVED_IN_ARTIFACTS:
            resolved = normalise_gate(value)
            if resolved is None:
                self.assertIn(
                    value,
                    LEGACY_GATELESS_LABELS,
                    f"{value!r} cae a None sin estar declarado como etiqueta sin compuerta",
                )
            else:
                self.assertIn(
                    resolved, canonical, f"{value!r} resolvió a {resolved}, no canónico"
                )

    def test_a_unit_without_a_gate_normalises_to_none(self) -> None:
        for label in LEGACY_GATELESS_LABELS:
            self.assertIsNone(normalise_gate(label))

    def test_canonical_gate_metadata_is_complete(self) -> None:
        for gate in canonical_gates():
            for field in ("id", "name", "phase", "reviewer", "criteria"):
                self.assertTrue(
                    gate.get(field), f"la compuerta {gate.get('id')} no declara {field}"
                )

    def test_every_unit_declares_what_it_produces(self) -> None:
        for unit in PIPELINE_UNITS:
            self.assertTrue(unit.get("name"), f"{unit.get('id')} sin nombre")
            self.assertIsInstance(unit.get("sections"), list, unit.get("id"))
            self.assertIsInstance(unit.get("agents"), list, unit.get("id"))

    def test_gate_ids_are_unique(self) -> None:
        ids = [g["id"] for g in canonical_gates()]
        self.assertEqual(len(ids), len(set(ids)), "hay compuertas canónicas repetidas")

    def test_no_section_is_claimed_by_two_units(self) -> None:
        seen: dict[str, str] = {}
        for unit in PIPELINE_UNITS:
            for section in unit.get("sections") or []:
                self.assertNotIn(
                    section,
                    seen,
                    f"{section} aparece en {seen.get(section)} y en {unit['id']}",
                )
                seen[section] = unit["id"]

    def test_prose_gate_names_resolve_to_their_canonical_id(self) -> None:
        """Los nombres en prosa de la tabla (`G budget`, `G front`) tienen que
        resolver al id canónico, y seguir apareciendo en la tabla."""
        text = STEPS_DOC.read_text(encoding="utf-8")
        for prose, canonical in GATE_ALIASES.items():
            self.assertEqual(
                normalise_gate(prose), canonical, f"{prose!r} debe resolver a {canonical}"
            )
            if prose != canonical:
                self.assertIn(prose, text, f"{prose!r} ya no aparece en la tabla de pasos")


if __name__ == "__main__":
    unittest.main()
