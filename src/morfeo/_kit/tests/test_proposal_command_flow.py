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
        self.assertIn("`costo` de cada\n        actividad por su código", budget)
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


class TestSgrAllianceRecipe(unittest.TestCase):
    """SGR-only alliance and territory unit (odd/tasks/sgr-alianza-territorio.md, S1, S5)."""

    COMMANDS = REPO_ROOT / ".claude" / "commands"

    def setUp(self):
        self.text = (self.COMMANDS / "propuesta.md").read_text(encoding="utf-8")

    def _block(self, start: str, end: str, text: str | None = None) -> str:
        text = self.text if text is None else text
        i = text.index(start)
        return " ".join(text[i:text.index(end, i + len(start))].split())

    def test_alliance_unit_runs_only_in_the_sgr_flow_between_trees_and_corpus(self):
        block = self._block("Fase 1b SGR [COMPUERTA GTerritorio]", "\nFase 1c ")
        self.assertIn("SOLO flujo SGR", block)
        self.assertIn("con el flujo `base` esta unidad no corre", block)
        self.assertIn("Task → insumos-observador", block)
        self.assertIn("Task → investigador", block)
        self.assertIn("python3 scripts/alianza_territorio_sgr.py check <RUN_ROOT>", block)
        self.assertIn("GATE Task → revisor", block)
        self.assertIn("pestaña «Alianza y territorio»", block)
        self.assertIn("| GTerritorio | APROBADA |", block)
        self.assertIn("artefactos/pipeline/11-fase1b_sgr.md", block)
        self.assertIn("artefactos/sgr/alianza.json", block)
        self.assertIn("artefactos/sgr/territorio.json", block)
        self.assertIn("textual", block)
        self.assertLess(self.text.index("Fase 1b [G1b]"), self.text.index("Fase 1b SGR [COMPUERTA GTerritorio]"))
        self.assertLess(self.text.index("Fase 1b SGR [COMPUERTA GTerritorio]"), self.text.index("Fase 1c [COMPUERTA"))

    def test_value_chain_and_annex_phases_complete_the_alliance_data(self):
        chain = self._block("Fase 4 SGR [COMPUERTA G4.cv]", "\nFase 5  ")
        self.assertIn("artefactos/sgr/territorio.json", chain)
        self.assertIn("`actividades` y `productos` de cada demanda", chain)
        annex = self._block("Fase 6.47 [SOLO FLUJO SGR]", "\nFase 6.5 ")
        self.assertIn("python3 scripts/alianza_territorio_sgr.py render <RUN_ROOT>", annex)
        self.assertIn("29_idoneidad_trayectoria.tex", annex)
        self.assertIn("en tercera persona", annex)
        for stem in ("26_identificacion", "27_demandas_territoriales", "28_matriz_responsabilidades"):
            self.assertIn(stem, annex)

    def test_base_flow_blocks_never_run_the_alliance_script(self):
        for start, end in (("Fase 1b [G1b]", "\nFase 1b SGR "), ("Fase 1c [COMPUERTA", "\nFase 1  "),
                           ("Fase 4  Task → investigador", "\nFase 4 SGR ")):
            with self.subTest(block=start):
                self.assertNotIn("alianza_territorio_sgr.py", self._block(start, end))

    def test_step_table_and_continuar_declare_the_unit(self):
        steps = (self.COMMANDS / "_propuesta-steps.md").read_text(encoding="utf-8")
        row = next(line for line in steps.splitlines() if line.startswith("| `fase1b` |"))
        self.assertTrue(row.endswith("| G1b | `fase1b_sgr` (flujo SGR) o `fase1c` (flujo base) |"), row)
        row = next(line for line in steps.splitlines() if line.startswith("| `fase1b_sgr` |"))
        self.assertIn("el flujo base la salta", row)
        self.assertIn("| G territorio | `fase1c` |", row)
        continuar = (self.COMMANDS / "propuesta-continuar.md").read_text(encoding="utf-8")
        self.assertIn("| `fase1b_sgr` | Fase 1b SGR [GTerritorio] (solo flujo SGR) |", continuar)
        note = self._block("### Gate PASS o unidad sin gate completada", "```", continuar)
        self.assertIn("tras `fase1b`, `fase1b_sgr` con `sgr` y `fase1c` con `base`", note)

    def test_agents_carry_their_sgr_only_alliance_duties(self):
        agents = REPO_ROOT / ".claude" / "agents"
        heading = "## Alianza y territorio SGR (Fase 1b SGR, compuerta GTerritorio)\n\nSGR flow only"
        observer = (agents / "insumos-observador.md").read_text(encoding="utf-8")
        self.assertIn(heading, observer)
        self.assertIn("`null`", observer[observer.index(heading):])
        investigador = (agents / "investigador.md").read_text(encoding="utf-8")
        self.assertIn(heading, investigador)
        self.assertIn("`articulacion`", investigador[investigador.index(heading):])
        redactor = (agents / "redactor.md").read_text(encoding="utf-8")
        self.assertIn("`29_idoneidad_trayectoria`", redactor)
        juez = (agents / "juez-sgr.md").read_text(encoding="utf-8")
        self.assertIn("python3 scripts/alianza_territorio_sgr.py datos <RUN_ROOT> --json", juez)


class TestSgrBudgetScheduleRecipe(unittest.TestCase):
    """SGR budget as data and schedule from the value chain (odd/tasks/sgr-presupuesto-gantt.md, S1, S5)."""

    COMMANDS = REPO_ROOT / ".claude" / "commands"

    def setUp(self):
        self.raw = (self.COMMANDS / "propuesta.md").read_text(encoding="utf-8")

    def _block(self, start: str, end: str) -> str:
        i = self.raw.index(start)
        return " ".join(self.raw[i:self.raw.index(end, i + len(start))].split())

    def _sgr_part(self, block: str, marker: str) -> str:
        return block[block.index(marker):]

    def test_sgr_budget_is_data_checked_synced_rendered_and_approved_in_the_tab(self):
        budget = self._sgr_part(self._block("Fase 6.4 [COMPUERTA INTERACTIVA", "\nFase 6.45 "),
                                "SOLO flujo SGR")
        steps = ["Task → presupuestador", "artefactos/sgr/presupuesto.json",
                 "python3 scripts/presupuesto_sgr.py check <RUN_ROOT>",
                 "python3 scripts/presupuesto_sgr.py sync-cadena <RUN_ROOT>",
                 "python3 scripts/cadena_valor_sgr.py check <RUN_ROOT>",
                 "python3 scripts/presupuesto_sgr.py render <RUN_ROOT>", "revisor",
                 "pestaña «Presupuesto y cronograma»", "G6.4"]
        positions = [budget.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("nunca escribe `13_presupuesto.tex` a mano", budget)

    def test_sgr_schedule_is_rendered_from_the_value_chain_and_the_milestones(self):
        schedule = self._sgr_part(self._block("Fase 6.45 Task → redactor", "\nFase 6.46 "), "SOLO flujo SGR")
        steps = ["Task → investigador", "artefactos/sgr/hitos.json",
                 "python3 scripts/cronograma_sgr.py check <RUN_ROOT>",
                 "python3 scripts/cronograma_sgr.py render <RUN_ROOT>"]
        positions = [schedule.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("cada 3 meses como máximo", schedule)
        self.assertIn("medio de verificación", schedule)
        self.assertIn("§14 nunca lo escribe el redactor", schedule)

    def test_sgr_annex_renders_the_financing_sources_and_the_final_audit_is_deterministic(self):
        annex = self._block("Fase 6.47 [SOLO FLUJO SGR]", "\nFase 6.5 ")
        self.assertIn("30_fuentes_financiacion", annex)
        self.assertIn("python3 scripts/presupuesto_sgr.py render <RUN_ROOT>", annex)
        final = self._block("Fase 7  ──→", "\n## Bucle de figuras")
        sgr = self._sgr_part(final, "En el flujo SGR ese cruce")
        self.assertIn("python3 scripts/presupuesto_sgr.py check <RUN_ROOT>", sgr)
        self.assertIn("python3 scripts/cronograma_sgr.py check <RUN_ROOT>", sgr)

    def test_base_flow_text_of_the_budget_and_schedule_is_unchanged(self):
        budget = self._block("Fase 6.4 [COMPUERTA INTERACTIVA", "\nFase 6.45 ")
        self.assertIn("(a) Task → presupuestador (MODE=tdr | MODE=base) → primer borrador de "
                      "`redaccion/sections/13_presupuesto.tex`", budget)
        base_part = budget[:budget.index("SOLO flujo SGR")]
        self.assertNotIn("presupuesto_sgr.py", base_part)
        schedule = self._block("Fase 6.45 Task → redactor", "\nFase 6.46 ")
        self.assertTrue(schedule.startswith("Fase 6.45 Task → redactor → §14 cronograma de actividades (Gantt)"))
        self.assertNotIn("cronograma_sgr.py", schedule[:schedule.index("SOLO flujo SGR")])
        self.assertIn("Presupuesto (§13) ↔ Cronograma de actividades (§14) diferida desde la Fase 6.4",
                      self._block("Fase 7  ──→", "\n## Bucle de figuras"))

    def test_step_table_names_the_sgr_budget_and_schedule_data(self):
        steps = (self.COMMANDS / "_propuesta-steps.md").read_text(encoding="utf-8")
        rows = {cells[0]: line for line in steps.splitlines() if line.startswith("| `")
                for cells in [[c.strip(" `") for c in line.strip("|").split("|")]]}
        self.assertIn("presupuesto_sgr.py", rows["fase6_4"])
        self.assertIn("| G budget | `fase6_45` |", rows["fase6_4"])
        self.assertIn("cronograma_sgr.py render", rows["fase6_45"])
        self.assertIn("30 fuentes de financiación", rows["fase6_47"])

    def test_agents_carry_their_sgr_budget_and_schedule_duties(self):
        agents = REPO_ROOT / ".claude" / "agents"
        investigador = (agents / "investigador.md").read_text(encoding="utf-8")
        heading = "## Hitos y etapas SGR (Fase 6.45)\n\nSGR flow only"
        self.assertIn(heading, investigador)
        section = investigador[investigador.index(heading):]
        self.assertIn("`artefactos/sgr/hitos.json`", section)
        self.assertIn("`etapa`", section)
        redactor = " ".join((agents / "redactor.md").read_text(encoding="utf-8").split())
        self.assertIn("never write `13_presupuesto`, `14_cronograma_actividades` or `30_fuentes_financiacion`",
                      redactor)
        juez = " ".join((agents / "juez-sgr.md").read_text(encoding="utf-8").split())
        for command in ("python3 scripts/presupuesto_sgr.py datos <RUN_ROOT> --json",
                        "python3 scripts/presupuesto_sgr.py resumen <RUN_ROOT> --json",
                        "python3 scripts/cronograma_sgr.py check <RUN_ROOT> --json"):
            self.assertIn(command, juez)


class TestSgrComponentsRecipe(unittest.TestCase):
    """SGR-only TRL and transversal components unit (odd/tasks/sgr-trl-componentes.md, S1, S5)."""

    COMMANDS = REPO_ROOT / ".claude" / "commands"

    def setUp(self):
        self.raw = (self.COMMANDS / "propuesta.md").read_text(encoding="utf-8")

    def _block(self, start: str, end: str, text: str | None = None) -> str:
        text = self.raw if text is None else text
        i = text.index(start)
        return " ".join(text[i:text.index(end, i + len(start))].split())

    def _sgr_part(self, block: str) -> str:
        return block[block.index("SOLO flujo SGR"):]

    def test_components_unit_runs_only_in_the_sgr_flow_between_methodology_and_results(self):
        block = self._block("Fase 5.5 SGR [COMPUERTA GComponentes]", "\nFase 6  ")
        self.assertIn("SOLO flujo SGR", block)
        self.assertIn("con el flujo `base` esta unidad no corre", block)
        steps = ["Task → investigador", "Task → redactor", "Task → revisor-estilo-sgr",
                 "python3 scripts/componentes_sgr.py check <RUN_ROOT>",
                 "python3 scripts/componentes_sgr.py render <RUN_ROOT>", "GATE Task → revisor",
                 "pestaña «TRL y componentes»", "| GComponentes | APROBADA |",
                 "artefactos/pipeline/65-fase5_5_sgr.md"]
        positions = [block.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("artefactos/sgr/componentes.json", block)
        for field in ("`trl`", "`transferencia`", "`uso_posterior`", "`introduccion`", "`asc`",
                      "`sostenibilidad`", "`diferencial`"):
            self.assertIn(field, block)
        self.assertIn("siete elementos", block)
        self.assertIn("tercera persona", block)
        for stem in ("31_trl", "32_sostenibilidad", "33_uso_posterior", "34_transferencia",
                     "35_medidas_diferenciales"):
            self.assertIn(stem, block)
        self.assertLess(self.raw.index("Fase 5.5 [NUEVO]"), self.raw.index("Fase 5.5 SGR [COMPUERTA GComponentes]"))
        self.assertLess(self.raw.index("Fase 5.5 SGR [COMPUERTA GComponentes]"), self.raw.index("\nFase 6  "))

    def test_budget_schedule_and_communities_use_the_components_in_sgr(self):
        budget = self._sgr_part(self._block("Fase 6.4 [COMPUERTA INTERACTIVA", "\nFase 6.45 "))
        self.assertIn("`componente`", budget)
        self.assertIn("python3 scripts/componentes_sgr.py check <RUN_ROOT>", budget)
        schedule = self._sgr_part(self._block("Fase 6.45 Task → redactor", "\nFase 6.46 "))
        self.assertIn("hitos de la ruta del TRL", schedule)
        communities = self._block("Fase 6.46 Task → redactor", "\nFase 6.47 ")
        sgr = self._sgr_part(communities)
        self.assertIn("solo §17", sgr)
        self.assertIn("python3 scripts/componentes_sgr.py render <RUN_ROOT>", sgr)
        self.assertIn("18_apropiacion_social.tex", sgr)

    def test_base_flow_text_never_runs_the_components_script(self):
        methodology = self._block("Fase 5.5 [NUEVO]", "\nFase 5.5 SGR ")
        self.assertNotIn("componentes_sgr.py", methodology)
        self.assertNotIn("componentes_sgr.py", self._block("Fase 6  Task → redactor", "\nFase 6.4 "))
        for start, end in (("Fase 6.4 [COMPUERTA INTERACTIVA", "\nFase 6.45 "),
                           ("Fase 6.45 Task → redactor", "\nFase 6.46 "),
                           ("Fase 6.46 Task → redactor", "\nFase 6.47 ")):
            with self.subTest(block=start):
                block = self._block(start, end)
                self.assertNotIn("componentes_sgr.py", block[:block.index("SOLO flujo SGR")])
        communities = self._block("Fase 6.46 Task → redactor", "\nFase 6.47 ")
        self.assertTrue(communities.startswith(
            "Fase 6.46 Task → redactor → §17 Estrategia de articulación con comunidades y actores territoriales "
            "(redaccion/sections/17_articulacion_comunidades.tex) y §18 Estrategia de acceso"), communities)

    def test_step_table_and_continuar_declare_the_unit(self):
        steps = (self.COMMANDS / "_propuesta-steps.md").read_text(encoding="utf-8")
        rows = {cells[0]: line for line in steps.splitlines() if line.startswith("| `")
                for cells in [[c.strip(" `") for c in line.strip("|").split("|")]]}
        self.assertTrue(rows["fase5_5"].endswith("| G5.5 | `fase5_5_sgr` (flujo SGR) o `fase6` (flujo base) |"),
                        rows["fase5_5"])
        self.assertIn("el flujo base la salta", rows["fase5_5_sgr"])
        self.assertIn("| G componentes | `fase6` |", rows["fase5_5_sgr"])
        self.assertIn("componentes_sgr.py check", rows["fase5_5_sgr"])
        self.assertIn("componentes_sgr.py check", rows["fase6_4"])
        self.assertIn("ruta del TRL", rows["fase6_45"])
        self.assertIn("componentes_sgr.py render", rows["fase6_46"])
        self.assertTrue(rows["fase6_46"].startswith(
            "| `fase6_46` | §17 articulación con comunidades + §18 apropiación social + grant-flow-auditor + revisor"))
        continuar = (self.COMMANDS / "propuesta-continuar.md").read_text(encoding="utf-8")
        self.assertIn("| `fase5_5_sgr` | Fase 5.5 SGR [GComponentes] (solo flujo SGR) |", continuar)
        note = self._block("### Gate PASS o unidad sin gate completada", "```", continuar)
        self.assertIn("tras `fase5_5`, `fase5_5_sgr` con `sgr` y `fase6` con `base`", note)

    def test_agents_carry_their_sgr_only_components_duties(self):
        agents = REPO_ROOT / ".claude" / "agents"
        heading = "## TRL y componentes SGR (Fase 5.5 SGR, compuerta GComponentes)\n\nSGR flow only"
        investigador = (agents / "investigador.md").read_text(encoding="utf-8")
        self.assertIn(heading, investigador)
        section = " ".join(investigador[investigador.index(heading):].split())
        for field in ("`trl`", "`transferencia`", "`uso_posterior`", "`evidencia_entrada`", "`verificacion`"):
            self.assertIn(field, section)
        self.assertIn("never declare a TRL", section)
        redactor = (agents / "redactor.md").read_text(encoding="utf-8")
        self.assertIn(heading, redactor)
        section = " ".join(redactor[redactor.index(heading):].split())
        for field in ("`introduccion`", "`asc`", "`sostenibilidad`", "`diferencial`"):
            self.assertIn(field, section)
        self.assertIn("seven elements", section)
        self.assertIn("third person", section)
        self.assertIn("never write `18_apropiacion_social`", section)
        presupuestador = " ".join((agents / "presupuestador.md").read_text(encoding="utf-8").split())
        self.assertIn("artefactos/sgr/componentes.json", presupuestador)
        self.assertIn("python3 scripts/componentes_sgr.py check <RUN_ROOT>", presupuestador)
        juez = " ".join((agents / "juez-sgr.md").read_text(encoding="utf-8").split())
        for command in ("python3 scripts/componentes_sgr.py datos <RUN_ROOT> --json",
                        "python3 scripts/componentes_sgr.py check <RUN_ROOT> --json"):
            self.assertIn(command, juez)


class TestSgrProductsRecipe(unittest.TestCase):
    """SGR-only products, talent and indicators unit (odd/tasks/sgr-productos-indicadores.md, S1, S5)."""

    COMMANDS = REPO_ROOT / ".claude" / "commands"

    def setUp(self):
        self.raw = (self.COMMANDS / "propuesta.md").read_text(encoding="utf-8")

    def _block(self, start: str, end: str, text: str | None = None) -> str:
        text = self.raw if text is None else text
        i = text.index(start)
        return " ".join(text[i:text.index(end, i + len(start))].split())

    def _sgr_part(self, block: str) -> str:
        return block[block.index("SOLO flujo SGR"):]

    def test_products_unit_runs_only_in_the_sgr_flow_between_team_and_methodology(self):
        block = self._block("Fase 5 SGR [COMPUERTA GProductos]", "\nFase 5.5 [NUEVO]")
        self.assertIn("SOLO flujo SGR", block)
        self.assertIn("con el flujo `base` esta unidad no corre", block)
        steps = ["Task → investigador", "Task → redactor", "Task → revisor-estilo-sgr",
                 "python3 scripts/productos_sgr.py check <RUN_ROOT>",
                 "python3 scripts/productos_sgr.py render <RUN_ROOT>", "GATE Task → revisor",
                 "pestaña «Productos e indicadores»", "| GProductos | APROBADA |",
                 "artefactos/pipeline/60-fase5_sgr.md"]
        positions = [block.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("artefactos/sgr/productos.json", block)
        for field in ("`productos_ctei`", "`divulgacion`", "`indicadores_gestion`", "`talento`",
                      "`adicional`", "`categoria`", "`producto_cadena`", "`introduccion`"):
            self.assertIn(field, block)
        for duty in ("mínimo de la convocatoria", "costeada", "supervisión", "informes técnico-financieros",
                     "periodicidad", "mínimos de talento"):
            self.assertIn(duty, block)
        for stem in ("15_productos_esperados", "36_talento_humano", "37_indicadores"):
            self.assertIn(stem, block)
        self.assertLess(self.raw.index("\nFase 5  Task → investigador"),
                        self.raw.index("Fase 5 SGR [COMPUERTA GProductos]"))
        self.assertLess(self.raw.index("Fase 5 SGR [COMPUERTA GProductos]"), self.raw.index("Fase 5.5 [NUEVO]"))

    def test_budget_and_section_15_use_the_products_in_sgr(self):
        budget = self._sgr_part(self._block("Fase 6.4 [COMPUERTA INTERACTIVA", "\nFase 6.45 "))
        self.assertIn("artefactos/sgr/productos.json", budget)
        self.assertIn("bloque `talento`", budget)
        self.assertIn("python3 scripts/productos_sgr.py check <RUN_ROOT>", budget)
        self.assertIn("python3 scripts/productos_sgr.py render <RUN_ROOT>", budget)
        self.assertLess(budget.index("sync-cadena"), budget.index("python3 scripts/productos_sgr.py render <RUN_ROOT>"))
        schedule = self._sgr_part(self._block("Fase 6.45 Task → redactor", "\nFase 6.46 "))
        self.assertIn("§15 nunca lo escribe el redactor", schedule)
        self.assertIn("python3 scripts/productos_sgr.py render <RUN_ROOT>", schedule)
        self.assertIn("15_productos_esperados.tex", schedule)

    def test_base_flow_text_never_runs_the_products_script(self):
        team = self._block("Fase 5  Task → investigador", "\nFase 5 SGR ")
        self.assertNotIn("productos_sgr.py", team)
        self.assertTrue(team.endswith("incluye además los campos de uso acumulados de la fase (ver \"Telemetría de uso por fase\")."), team[-200:])
        self.assertNotIn("productos_sgr.py", self._block("Fase 5.5 [NUEVO]", "\nFase 5.5 SGR "))
        for start, end in (("Fase 6.4 [COMPUERTA INTERACTIVA", "\nFase 6.45 "),
                           ("Fase 6.45 Task → redactor", "\nFase 6.46 ")):
            with self.subTest(block=start):
                block = self._block(start, end)
                self.assertNotIn("productos_sgr.py", block[:block.index("SOLO flujo SGR")])
        schedule = self._block("Fase 6.45 Task → redactor", "\nFase 6.46 ")
        self.assertIn("Task → redactor → §15 productos esperados (ídem, sin gate propio).", schedule)

    def test_step_table_and_continuar_declare_the_unit(self):
        steps = (self.COMMANDS / "_propuesta-steps.md").read_text(encoding="utf-8")
        rows = {cells[0]: line for line in steps.splitlines() if line.startswith("| `")
                for cells in [[c.strip(" `") for c in line.strip("|").split("|")]]}
        self.assertTrue(rows["fase5"].endswith("| G5 | `fase5_sgr` (flujo SGR) o `fase5_5` (flujo base) |"),
                        rows["fase5"])
        self.assertTrue(rows["fase5"].startswith("| `fase5` | §8 marco + §9 equipo + grant-flow-auditor + revisor |"))
        self.assertIn("el flujo base la salta", rows["fase5_sgr"])
        self.assertIn("| G productos | `fase5_5` |", rows["fase5_sgr"])
        self.assertIn("productos_sgr.py check", rows["fase5_sgr"])
        self.assertIn("productos_sgr.py check", rows["fase6_4"])
        self.assertIn("productos_sgr.py render", rows["fase6_45"])
        self.assertTrue(rows["fase6_45"].startswith(
            "| `fase6_45` | §14 cronograma + §15 productos (xltabular) + §16 bib + grant-flow-auditor (no own gate)"))
        continuar = (self.COMMANDS / "propuesta-continuar.md").read_text(encoding="utf-8")
        self.assertIn("| `fase5_sgr` | Fase 5 SGR [GProductos] (solo flujo SGR) |", continuar)
        self.assertLess(continuar.index("| `fase5` | Fase 5 |"), continuar.index("| `fase5_sgr` |"))
        note = self._block("### Gate PASS o unidad sin gate completada", "```", continuar)
        self.assertIn("tras `fase5`, `fase5_sgr` con `sgr` y `fase5_5` con `base`", note)

    def test_agents_carry_their_sgr_only_products_duties(self):
        agents = REPO_ROOT / ".claude" / "agents"
        heading = "## Productos, talento e indicadores SGR (Fase 5 SGR, compuerta GProductos)\n\nSGR flow only"
        investigador = (agents / "investigador.md").read_text(encoding="utf-8")
        self.assertIn(heading, investigador)
        start = investigador.index(heading)
        section = " ".join(investigador[start:investigador.index("\n## ", start)].split())
        for field in ("`productos_ctei`", "`divulgacion`", "`indicadores_gestion`", "`adicional`",
                      "`categoria`", "`producto_cadena`", "`periodicidad`", "`costeada`"):
            self.assertIn(field, section)
        self.assertIn("call minimum", section)
        redactor = (agents / "redactor.md").read_text(encoding="utf-8")
        self.assertIn(heading, redactor)
        start = redactor.index(heading)
        section = " ".join(redactor[start:redactor.index("\n## ", start)].split())
        self.assertIn("`talento`", section)
        self.assertIn("call minimums", section)
        self.assertIn("never write `15_productos_esperados`, `36_talento_humano` or `37_indicadores`", section)
        presupuestador = " ".join((agents / "presupuestador.md").read_text(encoding="utf-8").split())
        self.assertIn("artefactos/sgr/productos.json", presupuestador)
        self.assertIn("python3 scripts/productos_sgr.py check <RUN_ROOT>", presupuestador)
        juez = " ".join((agents / "juez-sgr.md").read_text(encoding="utf-8").split())
        for command in ("python3 scripts/productos_sgr.py datos <RUN_ROOT> --json",
                        "python3 scripts/productos_sgr.py check <RUN_ROOT> --json"):
            self.assertIn(command, juez)
        self.assertIn("2.5", juez)
        self.assertIn("`36_*` y `37_*`", juez)


class TestSgrRequirementsRecipe(unittest.TestCase):
    """SGR-only requirements and annexes unit (odd/tasks/sgr-requisitos-anexos.md, S1, S6)."""

    COMMANDS = REPO_ROOT / ".claude" / "commands"
    AGENTS = REPO_ROOT / ".claude" / "agents"
    HEADING = "## Requisitos y anexos SGR (Fase 6.9 SGR, compuerta GRequisitos)\n\nSGR flow only"

    def setUp(self):
        self.raw = (self.COMMANDS / "propuesta.md").read_text(encoding="utf-8")

    def _block(self, start: str, end: str, text: str | None = None) -> str:
        text = self.raw if text is None else text
        i = text.index(start)
        return " ".join(text[i:text.index(end, i + len(start))].split())

    def _sgr_part(self, block: str) -> str:
        return block[block.index("SOLO flujo SGR"):]

    def _rows(self) -> dict[str, str]:
        steps = (self.COMMANDS / "_propuesta-steps.md").read_text(encoding="utf-8")
        return {cells[0]: line for line in steps.splitlines() if line.startswith("| `")
                for cells in [[c.strip(" `") for c in line.strip("|").split("|")]]}

    def _agent_section(self, name: str, heading: str | None = None) -> str:
        raw = (self.AGENTS / f"{name}.md").read_text(encoding="utf-8")
        heading = self.HEADING if heading is None else heading
        self.assertIn(heading, raw, name)
        start = raw.index(heading)
        end = raw.find("\n## ", start + len(heading))
        return " ".join(raw[start:end if end != -1 else len(raw)].split())

    def test_requirements_unit_runs_only_in_the_sgr_flow_between_front_matter_and_final_audit(self):
        block = self._block("Fase 6.9 SGR [COMPUERTA GRequisitos]", "\nFase 7  ──→")
        self.assertIn("SOLO flujo SGR", block)
        self.assertIn("con el flujo `base` esta unidad no corre", block)
        steps = ["python3 scripts/requisitos_sgr.py init <RUN_ROOT>", "Task → investigador",
                 "Task → redactor", "Task → revisor-estilo-sgr", "pestaña «Requisitos y anexos»",
                 "python3 scripts/requisitos_sgr.py check <RUN_ROOT>",
                 "python3 scripts/requisitos_sgr.py render <RUN_ROOT>", "GATE Task → revisor",
                 "| GRequisitos | APROBADA |", "artefactos/pipeline/75-fase6_9_sgr.md"]
        positions = [block.index(step) for step in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("idempotente", block)
        self.assertIn("nunca sobrescribe", block)
        self.assertIn("artefactos/sgr/requisitos.json", block)
        self.assertIn("morfeo.requisitos-sgr/v1", block)
        for field in ("`licencias`", "`introduccion`", "`items`", "`cifras`", "`aval_institucional`",
                      "`listo`", "`no_aplica`", "`justificacion`", "`momento`"):
            self.assertIn(field, block)
        for stem in ("38_licencias_permisos", "39_anexos"):
            self.assertIn(stem, block)
        self.assertIn("ANEXOS REQUISITOS SECTORIALES QUE LE SEAN APLICABLES.", block)
        for figure in ("SIGP", "Anexo 1", "Anexo 3", "MGA Web"):
            self.assertIn(figure, block)
        self.assertIn("### SGR A28", block)
        self.assertLess(self.raw.index("\nFase 6.5 Task → redactor"),
                        self.raw.index("\nFase 6.9 SGR [COMPUERTA GRequisitos]"))
        self.assertLess(self.raw.index("\nFase 6.9 SGR [COMPUERTA GRequisitos]"), self.raw.index("\nFase 7  ──→"))

    def test_sgr_final_audit_checks_the_requirements_and_the_new_sections(self):
        final = self._block("Fase 7  ──→", "\n## Bucle de figuras")
        sgr = self._sgr_part(final)
        self.assertIn("python3 scripts/requisitos_sgr.py check <RUN_ROOT> --final", sgr)
        self.assertIn("aplicable que no esté `listo`", sgr)
        self.assertIn("`38_licencias_permisos.tex` y `39_anexos.tex`", sgr)
        self.assertIn("python3 scripts/check_run.py <RUN_ROOT> --final", sgr)
        self.assertIn("pestaña «Requisitos y anexos»", sgr)
        self.assertLess(sgr.index("requisitos_sgr.py check <RUN_ROOT> --final"), sgr.index("Task → juez-sgr"))

    def test_base_flow_text_never_runs_the_requirements_script(self):
        front = self._block("Fase 6.5 Task → redactor", "\nFase 6.9 SGR ")
        self.assertNotIn("requisitos_sgr.py", front)
        self.assertTrue(front.endswith("incluye además los campos de uso acumulados de la fase (ver "
                                       "\"Telemetría de uso por fase\")."), front[-200:])
        final = self._block("Fase 7  ──→", "\n## Bucle de figuras")
        # Base text of Fase 7: everything outside its SGR paragraphs (the
        # deterministic §13↔§14 cross-check, the requirements check and the judge).
        sgr_start = final.index("En el flujo SGR ese cruce")
        base = (final[:sgr_start]
                + final[final.index("──→ [NUEVO] DISPATCHER: pipeline-graph: escribe `artefactos/pipeline/80-fase7.md`"):
                        final.index("[NUEVO] SOLO flujo SGR (`\"flujo\": \"sgr\"`), después de la pasada de pixelshot")])
        self.assertNotIn("SGR", base.replace("en el flujo SGR, si existe `artefactos/juez/evaluacion.json`", ""))
        self.assertNotIn("requisitos_sgr.py", base)
        self.assertNotIn("38_licencias_permisos", base)
        self.assertIn("correr `python3 scripts/check_run.py <RUN_ROOT> --final` hasta que salga sin errores.", base)
        self.assertIn("Presupuesto (§13) ↔ Cronograma de actividades (§14) diferida desde la Fase 6.4", base)
        annex = self._block("Fase 6.47 [SOLO FLUJO SGR]", "\nFase 6.5 ")
        self.assertNotIn("requisitos_sgr.py", annex)

    def test_step_table_and_continuar_declare_the_unit(self):
        rows = self._rows()
        self.assertTrue(rows["fase6_5"].startswith(
            "| `fase6_5` | Front-matter (Resumen, Resumen ejecutivo, Palabras clave; sin sección cuerpo de título)"
            " + grant-flow-auditor + revisor |"), rows["fase6_5"])
        self.assertTrue(rows["fase6_5"].endswith("| G front | `fase6_9_sgr` (flujo SGR) o `fase7` (flujo base) |"),
                        rows["fase6_5"])
        row = rows["fase6_9_sgr"]
        self.assertTrue(row.startswith("| `fase6_9_sgr` | Solo flujo SGR:"), row)
        self.assertIn("el flujo base la salta", row)
        self.assertIn("| G requisitos | `fase7` |", row)
        for fragment in ("artefactos/sgr/requisitos.json", "requisitos_sgr.py init", "requisitos_sgr.py check",
                         "requisitos_sgr.py render", "revisor-estilo-sgr", "pestaña Requisitos y anexos",
                         "§38 y §39"):
            self.assertIn(fragment, row)
        self.assertTrue(rows["fase7"].startswith(
            "| `fase7` | Final audit + assemble `main.tex` (\\setcounter{section}{1}, xltabular, bibliografía limpia);"
            " flujo SGR:"), rows["fase7"])
        self.assertIn("requisitos_sgr.py check --final", rows["fase7"])
        self.assertIn("juez-sgr asesor tras el ensamble", rows["fase7"])
        self.assertTrue(rows["fase7"].endswith("| G final | `done` |"), rows["fase7"])
        continuar = (self.COMMANDS / "propuesta-continuar.md").read_text(encoding="utf-8")
        self.assertIn("| `fase6_9_sgr` | Fase 6.9 SGR [GRequisitos] (solo flujo SGR) |", continuar)
        self.assertLess(continuar.index("| `fase6_5` | Fase 6.5 |"), continuar.index("| `fase6_9_sgr` |"))
        self.assertLess(continuar.index("| `fase6_9_sgr` |"), continuar.index("| `fase7` | Fase 7 |"))
        note = self._block("### Gate PASS o unidad sin gate completada", "```", continuar)
        self.assertIn("tras `fase6_5`, `fase6_9_sgr` con `sgr` y `fase7` con `base`", note)
        self.assertIn("tras `fase6_46`, `fase6_47` con `sgr` y `fase6_5` con `base`", note)

    def test_agents_carry_their_sgr_only_requirements_duties(self):
        investigador = self._agent_section("investigador")
        for field in ("`licencias.items`", "`licencia`", "`norma`", "`aplica`", "`justificacion`",
                      "`responsable`", "`momento`", "`previo`", "`ejecucion`"):
            self.assertIn(field, investigador)
        self.assertIn("consulta previa", investigador)
        self.assertIn("scripts/requisitos_sgr.py check", investigador)
        redactor = self._agent_section("redactor")
        self.assertIn("`licencias.introduccion`", redactor)
        self.assertIn("### SGR A28", redactor)
        self.assertIn("never write `38_licencias_permisos` or `39_anexos`", redactor)
        juez = " ".join((self.AGENTS / "juez-sgr.md").read_text(encoding="utf-8").split())
        for command in ("python3 scripts/requisitos_sgr.py datos <RUN_ROOT> --json",
                        "python3 scripts/requisitos_sgr.py check <RUN_ROOT> --json"):
            self.assertIn(command, juez)
        self.assertIn("`cifras_coherentes`", juez)
        self.assertIn("`pendientes`", juez)
        self.assertIn("1.4", juez)
        self.assertIn("`38_*` y `39_*`", juez)
        revisor = " ".join((self.AGENTS / "revisor.md").read_text(encoding="utf-8").split())
        self.assertIn("**Requisitos y anexos — only at GRequisitos and in the Fase 7 final audit of an SGR run:**",
                      revisor)
        coordinador = (self.AGENTS / "coordinador-propuesta.md").read_text(encoding="utf-8")
        self.assertIn("`fase6_5` → [`fase6_9_sgr`, solo flujo SGR] → `fase7` → `done`", coordinador)
        self.assertIn("\nFase 6.9 SGR [solo flujo SGR]", coordinador)

    def test_agent_text_outside_the_sgr_requirements_blocks_is_unchanged(self):
        # The new duties live only in SGR-labelled blocks: no other part of an
        # agent mentions the requirements script or the new section stems.
        for name in ("investigador", "redactor"):
            with self.subTest(agent=name):
                raw = (self.AGENTS / f"{name}.md").read_text(encoding="utf-8")
                start = raw.index(self.HEADING)
                end = raw.index("\n## ", start + len(self.HEADING))
                rest = raw[:start] + raw[end:]
                for token in ("requisitos_sgr", "38_licencias_permisos", "39_anexos", "GRequisitos"):
                    self.assertNotIn(token, rest)
        revisor = (self.AGENTS / "revisor.md").read_text(encoding="utf-8")
        item = revisor.index("10. **Requisitos y anexos")
        rest = revisor[:item] + revisor[revisor.index("\n## ", item):]
        self.assertNotIn("requisitos_sgr", rest)
        self.assertIn("9. **Juez SGR alerts — only in the Fase 7 final audit of an SGR run:**", rest)
        coordinador = (self.AGENTS / "coordinador-propuesta.md").read_text(encoding="utf-8")
        self.assertIn("\nFase 6.5  redactor → front-matter (Resumen, Resumen ejecutivo, Palabras\n", coordinador)
        self.assertIn("\nFase 7  [NUEVO] refresh del índice del vault sobre el vault completo + bloque\n", coordinador)


if __name__ == "__main__":
    unittest.main()
