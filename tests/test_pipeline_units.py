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
    units_for_flujo,
)

STEPS_DOC = REPO / ".claude" / "commands" / "_propuesta-steps.md"

STEP_UNITS_EXPECTED = 16

# Valores de compuerta observados en los artefactos de la corrida de referencia,
# incluidos los que la tabla no reconoce. El inventario tiene que ubicarlos todos:
# o son un id canónico, o están declarados como etiqueta sin compuerta.
OBSERVED_IN_ARTIFACTS = (
    "G0.5",
    "G1a",
    "G1b",
    "G1c",
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
            "G0.5", "G1a", "G1b", "G1c", "G1", "G2", "G3", "G4",
            "G5", "G5.5", "G6.4", "G6.46", "G6.5", "G7",
        ):
            self.assertIn(real, canonical, f"falta {real} en las compuertas canónicas")
        # Catorce del flujo base más G6.47, la compuerta de los anexos MGA del flujo SGR.
        self.assertIn("G6.47", canonical)
        self.assertEqual(len(canonical), 15, "las compuertas canónicas son quince")

    def test_early_units_run_scoping_trees_corpus_then_mga_summary(self) -> None:
        # Same order in both flows: the trees come right after the subproblems and
        # before the SOTA corpus; Fase 1 writes the MGA summary and §3 from it.
        for flujo in ("base", "sgr"):
            by_id = {u["id"]: u for u in units_for_flujo(flujo)}
            chain = ["fase0"]
            while chain[-1] != "fase2":
                chain.append(by_id[chain[-1]]["next"])
            self.assertEqual(chain, ["fase0", "fase1a", "fase1b", "fase1c", "fase1", "fase2"], flujo)
            self.assertEqual(by_id["fase1b"]["gate"], "G1b")
            self.assertEqual(by_id["fase1c"]["gate"], "G1c")
            self.assertEqual(by_id["fase1"]["gate"], "G1")
            self.assertIn("Árbol de problemas y árbol de objetivos", by_id["fase1b"]["name"])
            self.assertIn("Corpus SOTA", by_id["fase1c"]["name"])
            self.assertIn("MGA resumido", by_id["fase1"]["name"])
            self.assertEqual(by_id["fase1"]["sections"], ["03"])

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



class TestUnitsByFlujo(unittest.TestCase):
    """La unidad de anexos MGA solo existe en el flujo SGR; el flujo base no la ve."""

    def _ids(self, units):
        return [u["id"] for u in units]

    def test_base_flow_skips_the_sgr_annexes(self) -> None:
        units = units_for_flujo("base")
        self.assertNotIn("fase6_47", self._ids(units))
        nxt = {u["id"]: u.get("next") for u in units}
        self.assertEqual(nxt["fase6_46"], "fase6_5")
        self.assertNotIn("G6.47", {g["id"] for g in canonical_gates("base")})

    def test_sgr_flow_runs_the_annexes_between_communities_and_front_matter(self) -> None:
        units = units_for_flujo("sgr")
        ids = self._ids(units)
        self.assertLess(ids.index("fase6_46"), ids.index("fase6_47"))
        self.assertLess(ids.index("fase6_47"), ids.index("fase6_5"))
        nxt = {u["id"]: u.get("next") for u in units}
        self.assertEqual(nxt["fase6_46"], "fase6_47")
        self.assertEqual(nxt["fase6_47"], "fase6_5")
        annex = next(u for u in units if u["id"] == "fase6_47")
        self.assertEqual(annex["gate"], "G6.47")
        self.assertEqual(annex["sections"], ["19", "20", "21", "22", "23", "24", "25"])
        self.assertIn("G6.47", {g["id"] for g in canonical_gates("sgr")})

    def test_unknown_flow_is_the_base_flow(self) -> None:
        self.assertEqual(self._ids(units_for_flujo("otro")), self._ids(units_for_flujo("base")))

    def test_filtering_never_mutates_the_inventory(self) -> None:
        before = [dict(u) for u in PIPELINE_UNITS]
        units_for_flujo("base")
        units_for_flujo("sgr")
        self.assertEqual([dict(u) for u in PIPELINE_UNITS], before)

    def test_without_a_flow_every_gate_is_listed(self) -> None:
        """Llamar `canonical_gates()` sin flujo conserva el comportamiento previo."""
        self.assertIn("G6.47", {g["id"] for g in canonical_gates()})


if __name__ == "__main__":
    unittest.main()
