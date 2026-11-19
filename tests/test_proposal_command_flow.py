#!/usr/bin/env python3
"""
Proposal Command Flow Test Suite for the pi agent runtime.

Validates that the .pi/commands/propuesta-*.md files produce a coherent,
step-by-step user experience: correct NEXT STEPS banners, consistent
next-command references, scope boundary enforcement, step-table alignment,
and actionable precondition error messages.

These tests parse the generated markdown files — they do NOT invoke the
pi agent runtime itself.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
# The Pi port writes dispatchable subagents to .pi/agents/ and every command
# (including the frontmatter-less step table) to .pi/prompts/.
PI_COMMANDS_DIR = REPO_ROOT / ".pi" / "prompts"
PI_AGENTS_DIR = REPO_ROOT / ".pi" / "agents"

# ── Expected command files ─────────────────────────────────────────────
EXPECTED_COMMAND_FILES = [
    "propuesta.md",
    "propuesta-init.md",
    "propuesta-insumos.md",
    "propuesta-analizar.md",
    "propuesta-continuar.md",
    "propuesta-limpiar.md",
    "propuesta-juez.md",
]

STEP_TABLE_FILE = PI_COMMANDS_DIR / "_propuesta-steps.md"


# ── Helpers ────────────────────────────────────────────────────────────

def load_frontmatter(path: Path) -> dict[str, str]:
    """Parse YAML frontmatter from a markdown file.

    Splits on ``---`` delimiters and extracts key: value pairs from the
    first block.  Returns an empty dict if no frontmatter is found.
    """
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm_block = parts[1].strip()
    result: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def parse_step_ids_from_step_table(path: Path) -> set[str]:
    """Extract the set of post-intake ``next_step`` IDs from the canonical
    step table in ``_propuesta-steps.md``.

    Looks for lines matching ``| `<id>` |`` inside the "Step sequence
    (post-intake)" section, stopping before the "Pre-intake units" section.
    """
    text = path.read_text(encoding="utf-8")
    ids: set[str] = set()
    in_section = False
    for line in text.splitlines():
        if "Step sequence (post-intake)" in line:
            in_section = True
            continue
        # Stop at the next heading OR the pre-intake section
        if in_section and (line.startswith("#") or "Pre-intake" in line):
            break
        if in_section:
            m = re.match(r"\|\s*`(\w+)`\s*\|", line)
            if m:
                ids.add(m.group(1))
    return ids


def parse_continuar_step_ids(path: Path) -> set[str]:
    """Extract step IDs from the mapping table in ``propuesta-continuar.md``.

    Looks for lines matching ``| `<id>` |`` after the "Mapeo id" heading.
    """
    text = path.read_text(encoding="utf-8")
    ids: set[str] = set()
    in_section = False
    for line in text.splitlines():
        if "Mapeo id" in line or "Ejecutar solo la unidad" in line:
            in_section = True
            continue
        if in_section and line.startswith("##"):
            break
        if in_section:
            m = re.match(r"\|\s*`(\w+)`\s*\|", line)
            if m:
                ids.add(m.group(1))
    return ids


def read_command(name: str) -> str:
    """Return the full text of a ``.pi/commands/<name>`` file."""
    return (PI_COMMANDS_DIR / name).read_text(encoding="utf-8")


# ── Test classes ───────────────────────────────────────────────────────

class TestCommandFileExistence(unittest.TestCase):
    """Verify that all expected command and reference files exist."""

    def test_all_expected_command_files_exist(self):
        """Every canonical propuesta-*.md file must be present under .pi/prompts/."""
        for fname in EXPECTED_COMMAND_FILES:
            path = PI_COMMANDS_DIR / fname
            self.assertTrue(
                path.is_file(),
                f"Expected command file missing: {path}",
            )

    def test_no_propuesta_auto_alias_file_exists(self):
        """`propuesta-auto.md` MUST NOT exist in any harness directory.

        `/propuesta` is the canonical full-pipeline command. `propuesta-auto.md`
        was a rename of the same monolith and was dropped on merge, so keeping a
        copy anywhere would mean two 1400-line bodies to keep in sync.
        """
        harness_alias_paths = [
            REPO_ROOT / ".claude" / "commands" / "propuesta-auto.md",
            REPO_ROOT / ".opencode" / "commands" / "propuesta-auto.md",
            REPO_ROOT / ".pi" / "prompts" / "propuesta-auto.md",
            REPO_ROOT / ".agent" / "workflows" / "propuesta-auto.md",
        ]
        for path in harness_alias_paths:
            self.assertFalse(
                path.is_file(),
                f"Dropped alias file still exists: {path}",
            )

    def test_step_table_reference_exists_across_all_harnesses(self):
        """_propuesta-steps.md must exist across all 4 harness directories."""
        harness_step_paths = [
            REPO_ROOT / ".claude" / "commands" / "_propuesta-steps.md",
            REPO_ROOT / ".opencode" / "commands" / "_propuesta-steps.md",
            REPO_ROOT / ".pi" / "prompts" / "_propuesta-steps.md",
            REPO_ROOT / ".agent" / "workflows" / "_propuesta-steps.md",
        ]
        for path in harness_step_paths:
            self.assertTrue(
                path.is_file(),
                f"Step table reference missing in harness: {path}",
            )

    def test_step_table_has_required_columns(self):
        """The step table must contain a markdown table with the expected
        column headers."""
        text = STEP_TABLE_FILE.read_text(encoding="utf-8")
        self.assertIn("next_step", text, "Step table missing 'next_step' column")
        self.assertIn("Unit", text, "Step table missing 'Unit' column")

    def test_every_command_has_valid_frontmatter(self):
        """Every propuesta-*.md file must have YAML frontmatter with a
        non-empty ``description``."""
        for fname in EXPECTED_COMMAND_FILES:
            path = PI_COMMANDS_DIR / fname
            if not path.is_file():
                self.skipTest(f"File missing (covered by existence test): {fname}")
            fm = load_frontmatter(path)
            self.assertIn(
                "description",
                fm,
                f"{fname}: YAML frontmatter missing 'description' field",
            )
            self.assertTrue(
                len(fm["description"]) > 0,
                f"{fname}: 'description' field is empty",
            )


class TestNextStepsBanners(unittest.TestCase):
    """Verify the 🎯 NEXT STEPS banners reference the correct next command."""

    def test_insumos_banner_references_analizar(self):
        """propuesta-insumos.md NEXT STEPS must point to /propuesta-analizar."""
        text = read_command("propuesta-insumos.md")
        self.assertIn("🎯 NEXT STEPS", text,
                       "propuesta-insumos.md missing 🎯 NEXT STEPS banner")
        # Find the NEXT STEPS section and verify it references analizar
        idx = text.index("🎯 NEXT STEPS")
        section = text[idx:]
        self.assertIn("/propuesta-analizar", section,
                       "propuesta-insumos.md NEXT STEPS does not reference "
                       "/propuesta-analizar")

    def test_init_closes_pointing_at_the_pipeline(self):
        """propuesta-init.md must tell the operator what to run next.

        Unlike the drop-zone command it has no NEXT STEPS banner, so the
        contract checked here is that its closing step names both the inputs
        folder and a pipeline entry point.
        """
        text = read_command("propuesta-init.md")
        self.assertIn("insumos/", text,
                       "propuesta-init.md must name the run's insumos/ folder")
        self.assertTrue(
            "/propuesta " in text or "/propuesta-analizar" in text,
            "propuesta-init.md must point at a pipeline entry point",
        )

    def test_analizar_banner_references_continuar(self):
        """propuesta-analizar.md NEXT STEPS must point to /propuesta-continuar."""
        text = read_command("propuesta-analizar.md")
        self.assertIn("🎯 NEXT STEPS", text,
                       "propuesta-analizar.md missing 🎯 NEXT STEPS banner")
        idx = text.index("🎯 NEXT STEPS")
        section = text[idx:]
        self.assertIn("/propuesta-continuar", section,
                       "propuesta-analizar.md NEXT STEPS does not reference "
                       "/propuesta-continuar")

    def test_continuar_banner_references_continuar_or_build(self):
        """propuesta-continuar.md NEXT STEPS must reference
        /propuesta-continuar or build.sh."""
        text = read_command("propuesta-continuar.md")
        self.assertIn("🎯 NEXT STEPS", text,
                       "propuesta-continuar.md missing 🎯 NEXT STEPS banner")
        idx = text.index("🎯 NEXT STEPS")
        section = text[idx:]
        has_continuar = "/propuesta-continuar" in section
        has_build = "build.sh" in section
        self.assertTrue(
            has_continuar or has_build,
            "propuesta-continuar.md NEXT STEPS references neither "
            "/propuesta-continuar nor build.sh",
        )


class TestScopeBoundaries(unittest.TestCase):
    """Verify that each command does NOT offer actions beyond its scope."""

    def _get_nunca_section(self, text: str) -> str:
        """Extract the 'Qué nunca hace este comando' section."""
        marker = "Qué nunca hace este comando"
        if marker not in text:
            return ""
        idx = text.index(marker)
        return text[idx:]

    def test_insumos_never_writes_estado_or_runid(self):
        """propuesta-insumos.md's 'Qué nunca hace' must exclude
        estado_propuesta, run-id, and insumos-observador.

        Drop zones are pure staging: assigning the run-id and writing run state
        belong to /propuesta-init and the pipeline itself.
        """
        text = read_command("propuesta-insumos.md")
        nunca = self._get_nunca_section(text)
        self.assertTrue(len(nunca) > 0,
                        "propuesta-insumos.md missing 'Qué nunca hace' section")
        self.assertIn("estado_propuesta", nunca,
                       "propuesta-insumos.md 'nunca' must mention estado_propuesta")
        self.assertIn("run-id", nunca,
                       "propuesta-insumos.md 'nunca' must mention run-id")
        self.assertIn("insumos-observador", nunca,
                       "propuesta-insumos.md 'nunca' must mention insumos-observador")

    def test_analizar_never_runs_fase1a(self):
        """propuesta-analizar.md must NOT offer to execute fase1a, and its
        'Qué nunca hace' must list the exclusion of fases 1a–7."""
        text = read_command("propuesta-analizar.md")
        nunca = self._get_nunca_section(text)
        self.assertTrue(len(nunca) > 0,
                        "propuesta-analizar.md missing 'Qué nunca hace' section")
        # The nunca section must mention fase1a exclusion
        self.assertIn("fase1a", nunca,
                       "propuesta-analizar.md 'nunca' must exclude fase1a")

        # The step 7 instruction must say to NOT dispatch bibliografo scope
        self.assertIn("DETENTE", text,
                       "propuesta-analizar.md must contain a DETENTE instruction "
                       "before fase1a")

    def test_continuar_never_reruns_intake(self):
        """propuesta-continuar.md must NOT re-execute intake, and its
        'Qué nunca hace' must list the exclusion."""
        text = read_command("propuesta-continuar.md")
        nunca = self._get_nunca_section(text)
        self.assertTrue(len(nunca) > 0,
                        "propuesta-continuar.md missing 'Qué nunca hace' section")
        # Must mention it does not re-execute intake
        self.assertIn("intake", nunca.lower(),
                       "propuesta-continuar.md 'nunca' must mention "
                       "intake exclusion")


class TestStepIdAlignment(unittest.TestCase):
    """Verify that step IDs in propuesta-continuar.md match the canonical
    step table in _propuesta-steps.md."""

    @classmethod
    def setUpClass(cls):
        cls.canonical_ids = parse_step_ids_from_step_table(STEP_TABLE_FILE)
        cls.continuar_ids = parse_continuar_step_ids(
            PI_COMMANDS_DIR / "propuesta-continuar.md"
        )

    def test_canonical_table_is_not_empty(self):
        """Sanity: the canonical step table must yield at least 10 IDs."""
        self.assertGreaterEqual(
            len(self.canonical_ids), 10,
            f"Canonical step table too small: {self.canonical_ids}",
        )

    def test_continuar_mapping_is_not_empty(self):
        """Sanity: the continuar step mapping must yield at least 10 IDs."""
        self.assertGreaterEqual(
            len(self.continuar_ids), 10,
            f"Continuar mapping too small: {self.continuar_ids}",
        )

    def test_every_continuar_id_in_canonical_table(self):
        """Every step ID in propuesta-continuar.md must exist in the
        canonical step table."""
        missing = self.continuar_ids - self.canonical_ids
        self.assertEqual(
            missing,
            set(),
            f"Continuar references step IDs not in canonical table: {missing}",
        )

    def test_every_post_intake_canonical_id_in_continuar(self):
        """Every post-intake step ID in the canonical table must appear
        in propuesta-continuar.md's mapping (excluding 'done')."""
        # 'done' is a terminal state, not a step to execute
        post_intake = self.canonical_ids - {"done"}
        missing = post_intake - self.continuar_ids
        self.assertEqual(
            missing,
            set(),
            f"Canonical post-intake IDs missing from continuar mapping: {missing}",
        )


class TestPreconditionMessages(unittest.TestCase):
    """Verify that precondition error messages in propuesta-continuar.md
    reference the correct recovery commands."""

    @classmethod
    def setUpClass(cls):
        cls.text = read_command("propuesta-continuar.md")

    def test_missing_state_references_analizar(self):
        """When intake is incomplete, the precondition message must
        reference /propuesta-analizar or /propuesta."""
        # The precondition table is in section "1. Precondiciones"
        precond_marker = "Precondiciones"
        self.assertIn(precond_marker, self.text,
                       "propuesta-continuar.md missing precondiciones section")
        idx = self.text.index(precond_marker)
        # Find the next major section
        next_section = self.text.find("\n## ", idx + 1)
        section = self.text[idx:next_section] if next_section > 0 else self.text[idx:]

        has_analizar = "/propuesta-analizar" in section
        has_auto = "/propuesta" in section
        self.assertTrue(
            has_analizar or has_auto,
            "Missing-state precondition does not reference /propuesta-analizar "
            "or /propuesta as recovery",
        )

    def test_done_state_references_build_and_limpiar(self):
        """When next_step is 'done', the precondition message must
        reference build.sh and /propuesta-limpiar."""
        precond_marker = "Precondiciones"
        idx = self.text.index(precond_marker)
        next_section = self.text.find("\n## ", idx + 1)
        section = self.text[idx:next_section] if next_section > 0 else self.text[idx:]

        self.assertIn("build.sh", section,
                       "Done-state precondition does not reference build.sh")
        self.assertIn("/propuesta-limpiar", section,
                       "Done-state precondition does not reference "
                       "/propuesta-limpiar")



class TestJuezCommand(unittest.TestCase):
    """`/propuesta-juez` judges SGR runs, stops in the base flow and stays advisory."""

    CANONICAL = REPO_ROOT / ".claude" / "commands" / "propuesta-juez.md"

    def setUp(self):
        if not self.CANONICAL.is_file():
            self.fail(f"falta el comando canonico {self.CANONICAL}")
        self.text = self.CANONICAL.read_text(encoding="utf-8")

    def _section(self, heading: str) -> str:
        start = self.text.index(heading)
        end = self.text.find("\n## ", start + 1)
        return self.text[start:end if end > 0 else len(self.text)]

    def test_sgr_flow_dispatches_the_judge_and_its_script(self):
        section = self._section("## 3. Flujo `sgr`")
        self.assertIn("juez-sgr", section)
        self.assertIn("scripts/juez_sgr.py preparar <RUN_ROOT>", section)
        self.assertIn("scripts/juez_sgr.py calificar <RUN_ROOT>", section)
        self.assertIn("artefactos/juez/evaluacion.json", section)

    def test_base_flow_announces_a_later_delivery_and_stops(self):
        section = self._section("## 2. Flujo `base`")
        self.assertIn("entrega posterior", section)
        self.assertIn("Detenete", section)
        self.assertNotIn("juez-sgr", section)

    def test_actions_go_to_their_agent_then_the_auditor(self):
        section = self._section("## 4. Flujo `sgr`: aplicar acciones")
        self.assertIn("grant-flow-auditor", section)
        self.assertIn("usuario", section)
        self.assertIn("/propuesta-juez", section)

    def test_it_never_changes_the_reviewer_verdict(self):
        self.assertIn("No cambia el VEREDICTO PASS/FAIL del `revisor`", self.text)

    def test_the_sgr_final_phase_runs_the_judge_as_an_advisory_step(self):
        body = (REPO_ROOT / ".claude" / "commands" / "propuesta.md").read_text(encoding="utf-8")
        start = body.index("SOLO flujo SGR (`\"flujo\": \"sgr\"`), después de la pasada de")
        step = body[start:body.index("```", start)]
        self.assertIn("Task → juez-sgr", step)
        self.assertIn("NUNCA altera el VEREDICTO PASS/FAIL", step)
        self.assertIn("Con el flujo `base` este paso no corre.", step)



class TestSgrValueChainRecipe(unittest.TestCase):
    """SGR-only value chain unit and style reviewer swap (odd/tasks/sgr-cadena-estilo.md, S1, S5, S6)."""

    CANONICAL = REPO_ROOT / ".claude" / "commands" / "propuesta.md"
    STEPS = REPO_ROOT / ".claude" / "commands" / "_propuesta-steps.md"

    def setUp(self):
        self.text = self.CANONICAL.read_text(encoding="utf-8")

    def _block(self, start: str, end: str) -> str:
        i = self.text.index(start)
        return self.text[i:self.text.index(end, i + len(start))]

    def test_one_rule_swaps_the_auditor_for_the_sgr_style_reviewer(self):
        rule = self._block("**Regla del flujo SGR para la auditoría de estilo.**", "\n## ")
        self.assertIn("`grant-flow-auditor`", rule)
        self.assertIn("`revisor-estilo-sgr`", rule)
        self.assertIn("Con el\nflujo `base` nada cambia: sigue `grant-flow-auditor`.", rule)
        roster = self._block("## Roster de subagentes", "\n## ")
        self.assertIn("`revisor-estilo-sgr` (solo flujo SGR)", roster)
        gate_rule = self._block("- **Auditoría de prosa antes del gate (`grant-flow-auditor`).**", "\n- **")
        self.assertIn("En el flujo SGR este paso lo hace\n  `revisor-estilo-sgr` en lugar de `grant-flow-auditor`",
                      gate_rule)

    def test_value_chain_unit_runs_only_in_the_sgr_flow(self):
        block = self._block("Fase 4 SGR [COMPUERTA G4.cv]", "\nFase 5  ")
        self.assertIn("SOLO flujo SGR", block)
        self.assertIn("con el flujo `base` esta unidad no corre", block)
        self.assertIn("python3 scripts/cadena_valor_sgr.py init <RUN_ROOT>", block)
        self.assertIn("Task → investigador", block)
        self.assertIn("python3 scripts/cadena_valor_sgr.py check <RUN_ROOT>", block)
        self.assertIn("GATE Task → revisor", block)
        self.assertIn("pestaña «Cadena de\n        valor»", block)
        self.assertIn("| G4.cv | APROBADA |", block)
        self.assertLess(self.text.index("Fase 4  Task → investigador"), self.text.index("Fase 4 SGR [COMPUERTA G4.cv]"))

    def test_sgr_methodology_budget_and_annex_use_the_value_chain(self):
        methodology = self._block("Fase 5.5 [NUEVO]", "\nFase 6  ")
        self.assertIn("código de la cadena de valor", methodology)
        budget = self._block("Fase 6.4 [COMPUERTA INTERACTIVA", "\nFase 6.45 ")
        self.assertIn("SOLO flujo SGR", budget)
        self.assertIn("`costo` de cada actividad\n        por su código", budget)
        annex = self._block("Fase 6.47 [SOLO FLUJO SGR]", "\nFase 6.5 ")
        self.assertIn("python3 scripts/cadena_valor_sgr.py render <RUN_ROOT>", annex)
        self.assertIn("no lo\n        escribe el redactor", annex)
        redactor_files = annex[:annex.index("El anexo A23")]
        self.assertNotIn("23_cadena_valor.tex", redactor_files)

    def test_base_flow_blocks_never_name_the_sgr_style_reviewer(self):
        for start, end in (("Fase 3  Task → redactor", "\nFase 4  "), ("Fase 4  Task → investigador", "\nFase 4 SGR "),
                           ("Fase 6.46 Task → redactor", "\nFase 6.47 ")):
            with self.subTest(block=start):
                self.assertNotIn("revisor-estilo-sgr", self._block(start, end))
                self.assertNotIn("cadena_valor_sgr.py", self._block(start, end))

    def test_step_table_declares_the_unit_and_the_swap(self):
        steps = self.STEPS.read_text(encoding="utf-8")
        self.assertIn("| `fase4` | §6–§7 objetivos + grant-flow-auditor + revisor | G4 | "
                      "`fase4_sgr` (flujo SGR) o `fase5` (flujo base) |", steps)
        row = next(line for line in steps.splitlines() if line.startswith("| `fase4_sgr` |"))
        self.assertIn("el flujo base la salta", row)
        self.assertIn("| G cadena | `fase5` |", row)
        self.assertIn("cada fila que nombra `grant-flow-auditor` despacha `revisor-estilo-sgr`", steps)

    def test_agents_carry_their_sgr_only_duties(self):
        agents = REPO_ROOT / ".claude" / "agents"
        investigador = (agents / "investigador.md").read_text(encoding="utf-8")
        self.assertIn("## Cadena de valor SGR (Fase 4 SGR, compuerta G4.cv)\n\nSGR flow only", investigador)
        presupuestador = (agents / "presupuestador.md").read_text(encoding="utf-8")
        self.assertIn("**SGR flow only, costs per activity code.**", presupuestador)


if __name__ == "__main__":
    unittest.main()
