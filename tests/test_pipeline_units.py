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

STEP_UNITS_EXPECTED = 22

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
        # Catorce del flujo base más las siete del flujo SGR: GCausas (causas
        # directas, tras G1a), GTerritorio (alianza y territorio, tras G1b),
        # G4.cv (cadena de valor, tras G4), GProductos (productos, talento e
        # indicadores, tras G5), GComponentes (TRL y componentes
        # transversales, tras G5.5), G6.47 (anexos MGA) y GRequisitos
        # (requisitos y anexos, tras G6.5).
        self.assertIn("G6.47", canonical)
        self.assertIn("GCausas", canonical)
        self.assertIn("GTerritorio", canonical)
        self.assertIn("G4.cv", canonical)
        self.assertIn("GProductos", canonical)
        self.assertIn("GComponentes", canonical)
        self.assertIn("GRequisitos", canonical)
        self.assertEqual(len(canonical), 21, "las compuertas canónicas son veintiuna")

    def test_early_units_run_scoping_trees_corpus_then_mga_summary(self) -> None:
        # The trees come right after the subproblems (in SGR, after the GCausas
        # gate on the direct causes) and before the SOTA corpus; Fase 1 writes
        # the MGA summary and §3 from it.
        expected = {
            "base": ["fase0", "fase1a", "fase1b", "fase1c", "fase1", "fase2"],
            "sgr": ["fase0", "fase1a", "fase1a_sgr", "fase1b", "fase1b_sgr", "fase1c", "fase1", "fase2"],
        }
        for flujo in ("base", "sgr"):
            by_id = {u["id"]: u for u in units_for_flujo(flujo)}
            chain = ["fase0"]
            while chain[-1] != "fase2":
                chain.append(by_id[chain[-1]]["next"])
            self.assertEqual(chain, expected[flujo], flujo)
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

    def test_only_the_sgr_final_audit_lists_the_sgr_judge(self) -> None:
        final = {f: next(u for u in units_for_flujo(f) if u["id"] == "fase7") for f in ("base", "sgr")}
        self.assertEqual(final["base"]["agents"], ["revisor", "coordinador-propuesta"])
        self.assertEqual(final["sgr"]["agents"], ["revisor", "coordinador-propuesta", "juez-sgr"])
        self.assertNotIn("agents_flujo", final["sgr"])
        canonical = next(u for u in PIPELINE_UNITS if u["id"] == "fase7")
        self.assertEqual(canonical["agents"], ["revisor", "coordinador-propuesta"])

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
        self.assertEqual(annex["sections"],
                         ["19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30"])
        self.assertIn("G6.47", {g["id"] for g in canonical_gates("sgr")})

    def test_unknown_flow_is_the_base_flow(self) -> None:
        self.assertEqual(self._ids(units_for_flujo("otro")), self._ids(units_for_flujo("base")))

    def test_filtering_never_mutates_the_inventory(self) -> None:
        before = [dict(u) for u in PIPELINE_UNITS]
        units_for_flujo("base")
        units_for_flujo("sgr")
        self.assertEqual([dict(u) for u in PIPELINE_UNITS], before)

    def test_value_chain_unit_runs_only_in_the_sgr_flow_after_the_objectives(self) -> None:
        base = {u["id"]: u for u in units_for_flujo("base")}
        self.assertNotIn("fase4_sgr", base)
        self.assertEqual(base["fase4"]["next"], "fase5")
        self.assertNotIn("G4.cv", {g["id"] for g in canonical_gates("base")})
        sgr = units_for_flujo("sgr")
        ids = self._ids(sgr)
        self.assertEqual(ids.index("fase4_sgr"), ids.index("fase4") + 1)
        by_id = {u["id"]: u for u in sgr}
        self.assertEqual(by_id["fase4"]["next"], "fase4_sgr")
        unit = by_id["fase4_sgr"]
        self.assertEqual(unit["next"], "fase5")
        self.assertEqual(unit["name"], "Cadena de valor")
        self.assertEqual(unit["gate"], "G4.cv")
        self.assertEqual(unit["artifacts"], ["artefactos/sgr/cadena_valor.json"])
        self.assertEqual(unit["agents"], ["investigador", "revisor"])
        self.assertEqual(unit["sections"], [])
        self.assertIn("G4.cv", {g["id"] for g in canonical_gates("sgr")})
        self.assertEqual(normalise_gate("G cadena"), "G4.cv")

    def test_alliance_unit_runs_only_in_the_sgr_flow_between_trees_and_corpus(self) -> None:
        base = {u["id"]: u for u in units_for_flujo("base")}
        self.assertNotIn("fase1b_sgr", base)
        self.assertEqual(base["fase1b"]["next"], "fase1c")
        self.assertNotIn("GTerritorio", {g["id"] for g in canonical_gates("base")})
        sgr = units_for_flujo("sgr")
        ids = self._ids(sgr)
        self.assertEqual(ids.index("fase1b_sgr"), ids.index("fase1b") + 1)
        by_id = {u["id"]: u for u in sgr}
        self.assertEqual(by_id["fase1b"]["next"], "fase1b_sgr")
        unit = by_id["fase1b_sgr"]
        self.assertEqual(unit["next"], "fase1c")
        self.assertEqual(unit["name"], "Alianza y territorio")
        self.assertEqual(unit["gate"], "GTerritorio")
        self.assertEqual(unit["artifacts"], ["artefactos/sgr/alianza.json", "artefactos/sgr/territorio.json"])
        self.assertEqual(unit["agents"], ["insumos-observador", "investigador", "revisor"])
        self.assertEqual(unit["sections"], [])
        self.assertIn("GTerritorio", {g["id"] for g in canonical_gates("sgr")})
        self.assertEqual(normalise_gate("G territorio"), "GTerritorio")
        gate = next(g for g in canonical_gates("sgr") if g["id"] == "GTerritorio")
        self.assertEqual(gate["phase"], "Fase 1b SGR")
        self.assertIn("Alianza y territorio", gate["name"])
        self.assertIn("alianza_territorio_sgr.py check", gate["criteria"])

    def test_components_unit_runs_only_in_the_sgr_flow_between_methodology_and_results(self) -> None:
        base = {u["id"]: u for u in units_for_flujo("base")}
        self.assertNotIn("fase5_5_sgr", base)
        self.assertEqual(base["fase5_5"]["next"], "fase6")
        self.assertNotIn("GComponentes", {g["id"] for g in canonical_gates("base")})
        self.assertNotIn("31", {s for u in base.values() for s in u["sections"]})
        self.assertEqual(base["fase6_46"]["sections"], ["17", "18"])
        sgr = units_for_flujo("sgr")
        ids = self._ids(sgr)
        self.assertEqual(ids.index("fase5_5_sgr"), ids.index("fase5_5") + 1)
        by_id = {u["id"]: u for u in sgr}
        self.assertEqual(by_id["fase5_5"]["next"], "fase5_5_sgr")
        unit = by_id["fase5_5_sgr"]
        self.assertEqual(unit["next"], "fase6")
        self.assertEqual(unit["name"], "TRL y componentes transversales")
        self.assertEqual(unit["gate"], "GComponentes")
        self.assertEqual(unit["artifacts"], ["artefactos/sgr/componentes.json"])
        self.assertEqual(unit["agents"], ["investigador", "redactor", "revisor-estilo-sgr", "revisor"])
        self.assertEqual(unit["sections"], ["31", "32", "33", "34", "35"])
        self.assertEqual(by_id["fase6_46"]["sections"], ["17", "18"])
        self.assertEqual(normalise_gate("G componentes"), "GComponentes")
        gate = next(g for g in canonical_gates("sgr") if g["id"] == "GComponentes")
        self.assertEqual(gate["phase"], "Fase 5.5 SGR")
        self.assertIn("TRL y componentes transversales", gate["name"])
        self.assertIn("componentes_sgr.py check", gate["criteria"])

    def test_products_unit_runs_only_in_the_sgr_flow_between_team_and_methodology(self) -> None:
        base = {u["id"]: u for u in units_for_flujo("base")}
        self.assertNotIn("fase5_sgr", base)
        self.assertEqual(base["fase5"]["next"], "fase5_5")
        self.assertNotIn("GProductos", {g["id"] for g in canonical_gates("base")})
        self.assertFalse({"36", "37"} & {s for u in base.values() for s in u["sections"]})
        self.assertEqual(base["fase6_45"]["sections"], ["14", "15", "16"])
        sgr = units_for_flujo("sgr")
        ids = self._ids(sgr)
        self.assertEqual(ids.index("fase5_sgr"), ids.index("fase5") + 1)
        self.assertEqual(ids.index("fase5_5"), ids.index("fase5_sgr") + 1)
        by_id = {u["id"]: u for u in sgr}
        self.assertEqual(by_id["fase5"]["next"], "fase5_sgr")
        unit = by_id["fase5_sgr"]
        self.assertEqual(unit["next"], "fase5_5")
        self.assertEqual(unit["name"], "Productos, talento e indicadores")
        self.assertEqual(unit["gate"], "GProductos")
        self.assertEqual(unit["artifacts"], ["artefactos/sgr/productos.json"])
        self.assertEqual(unit["agents"], ["investigador", "redactor", "revisor-estilo-sgr", "revisor"])
        self.assertEqual(unit["sections"], ["36", "37"])
        # §15 stays with the unit that writes it today, in both flows.
        self.assertEqual(by_id["fase6_45"]["sections"], ["14", "15", "16"])
        self.assertEqual(normalise_gate("G productos"), "GProductos")
        gate = next(g for g in canonical_gates("sgr") if g["id"] == "GProductos")
        self.assertEqual(gate["phase"], "Fase 5 SGR")
        self.assertIn("Productos, talento e indicadores", gate["name"])
        self.assertIn("productos_sgr.py check", gate["criteria"])
        order = [g["id"] for g in canonical_gates("sgr")]
        self.assertEqual(order.index("GProductos"), order.index("G5") + 1)
        self.assertEqual(order.index("G5.5"), order.index("GProductos") + 1)

    def test_requirements_unit_runs_only_in_the_sgr_flow_between_front_matter_and_final_audit(self) -> None:
        sgr = units_for_flujo("sgr")
        ids = self._ids(sgr)
        self.assertEqual(ids.index("fase6_9_sgr"), ids.index("fase6_5") + 1)
        self.assertEqual(ids.index("fase7"), ids.index("fase6_9_sgr") + 1)
        by_id = {u["id"]: u for u in sgr}
        self.assertEqual(by_id["fase6_5"]["next"], "fase6_9_sgr")
        unit = by_id["fase6_9_sgr"]
        self.assertEqual(unit["kind"], "step")
        self.assertEqual(unit["next"], "fase7")
        self.assertEqual(unit["name"], "Requisitos y anexos")
        self.assertEqual(unit["gate"], "GRequisitos")
        self.assertEqual(unit["artifacts"], ["artefactos/sgr/requisitos.json"])
        self.assertEqual(unit["agents"], ["investigador", "redactor", "revisor-estilo-sgr", "revisor"])
        self.assertEqual(unit["sections"], ["38", "39"])
        self.assertIn("requisitos_sgr.py check", unit["desc"])
        self.assertIn("pestaña Requisitos y anexos", unit["desc"])
        self.assertEqual(normalise_gate("G requisitos"), "GRequisitos")
        gate = next(g for g in canonical_gates("sgr") if g["id"] == "GRequisitos")
        self.assertEqual(gate["phase"], "Fase 6.9 SGR")
        self.assertIn("Requisitos y anexos", gate["name"])
        self.assertIn("requisitos_sgr.py check", gate["criteria"])
        order = [g["id"] for g in canonical_gates("sgr")]
        self.assertEqual(order.index("GRequisitos"), order.index("G6.5") + 1)
        self.assertEqual(order.index("G7"), order.index("GRequisitos") + 1)

    def test_base_flow_goes_straight_from_the_front_matter_to_the_final_audit(self) -> None:
        base = units_for_flujo("base")
        by_id = {u["id"]: u for u in base}
        self.assertNotIn("fase6_9_sgr", by_id)
        self.assertEqual(by_id["fase6_5"]["next"], "fase7")
        self.assertNotIn("GRequisitos", {g["id"] for g in canonical_gates("base")})
        self.assertFalse({"38", "39"} & {s for u in base for s in u["sections"]})
        self.assertNotIn("artefactos/sgr/requisitos.json", {a for u in base for a in u["artifacts"]})

    def test_base_flow_unit_order_and_gates_are_unchanged(self) -> None:
        self.assertEqual(self._ids(units_for_flujo("base")), [
            "fase0", "g0_5", "fase1a", "fase1b", "fase1c", "fase1", "fase2", "fase3", "fase4",
            "fase5", "fase5_5", "fase6", "fase6_4", "fase6_45", "fase6_46", "fase6_5", "fase7",
        ])
        self.assertEqual([g["id"] for g in canonical_gates("base")], [
            "G0.5", "G1a", "G1b", "G1c", "G1", "G2", "G3", "G4", "G5", "G5.5",
            "G6.4", "G6.46", "G6.5", "G7",
        ])

    def test_existing_sgr_units_keep_their_order(self) -> None:
        ids = [i for i in self._ids(units_for_flujo("sgr")) if i != "fase6_9_sgr"]
        self.assertEqual(ids, [
            "fase0", "g0_5", "fase1a", "fase1a_sgr", "fase1b", "fase1b_sgr", "fase1c", "fase1",
            "fase2", "fase3", "fase4", "fase4_sgr", "fase5", "fase5_sgr", "fase5_5", "fase5_5_sgr",
            "fase6", "fase6_4", "fase6_45", "fase6_46", "fase6_47", "fase6_5", "fase7",
        ])

    def test_sgr_flow_swaps_the_auditor_for_the_sgr_style_reviewer(self) -> None:
        for unit in units_for_flujo("sgr"):
            self.assertNotIn("grant-flow-auditor", unit["agents"], unit["id"])
        swapped = {u["id"]: u["agents"] for u in units_for_flujo("sgr")}
        canonical = {u["id"]: u["agents"] for u in PIPELINE_UNITS}
        for uid, agents in canonical.items():
            if "grant-flow-auditor" in agents:
                expected = ["revisor-estilo-sgr" if a == "grant-flow-auditor" else a for a in agents]
                self.assertEqual(swapped[uid], expected, uid)
        self.assertEqual(swapped["fase3"], ["redactor", "revisor-estilo-sgr", "revisor"])

    def test_base_flow_keeps_every_unit_agent_list(self) -> None:
        canonical = {u["id"]: u["agents"] for u in PIPELINE_UNITS}
        for unit in units_for_flujo("base"):
            self.assertEqual(unit["agents"], canonical[unit["id"]], unit["id"])
            self.assertNotIn("revisor-estilo-sgr", unit["agents"], unit["id"])
        self.assertIn("grant-flow-auditor", {a for u in units_for_flujo("base") for a in u["agents"]})

    def test_sgr_budget_and_schedule_units_add_their_data_files_only_in_the_sgr_flow(self) -> None:
        expected = {"fase6_4": ["artefactos/sgr/presupuesto.json"], "fase6_45": ["artefactos/sgr/hitos.json"]}
        sgr = {u["id"]: u for u in units_for_flujo("sgr")}
        base = {u["id"]: u for u in units_for_flujo("base")}
        canonical = {u["id"]: u for u in PIPELINE_UNITS}
        for uid, files in expected.items():
            self.assertEqual(sgr[uid]["artifacts"], files, uid)
            self.assertEqual(base[uid]["artifacts"], [], uid)
            self.assertEqual(canonical[uid]["artifacts"], [], uid)
            self.assertNotIn("artifacts_flujo", sgr[uid])
            self.assertNotIn("artifacts_flujo", base[uid])
        for uid, unit in base.items():
            self.assertEqual(unit["artifacts"], canonical[uid]["artifacts"], uid)
            self.assertEqual(unit["sections"], canonical[uid]["sections"], uid)

    def test_without_a_flow_every_gate_is_listed(self) -> None:
        """Llamar `canonical_gates()` sin flujo conserva el comportamiento previo."""
        self.assertIn("G6.47", {g["id"] for g in canonical_gates()})


if __name__ == "__main__":
    unittest.main()
