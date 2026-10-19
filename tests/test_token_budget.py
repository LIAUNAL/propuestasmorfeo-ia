"""Guards for the token savings measured on the reference run.

The reference run spent 55M tokens. AGENTS.md is loaded into every subagent
call, the bibliographer had no search budget (31.8% of the total), the stepped
runner re-read the whole 26k-token pipeline file on every unit, and the figure
agents ran on a tier their short, specified jobs do not need. These assertions
keep those savings from eroding silently.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AGENTS_MD_BUDGET = 24_000


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


class TokenBudgetTest(unittest.TestCase):
    def test_agents_md_stays_within_its_budget(self) -> None:
        size = len(read("AGENTS.md"))
        self.assertLessEqual(size, AGENTS_MD_BUDGET, f"AGENTS.md is {size} chars; dispatcher-only material "
                             "belongs in docs/operacion-pipeline.md")
        self.assertIn("docs/operacion-pipeline.md", read("AGENTS.md"))
        for heading in ("## Flujo del pipeline", "## Bucle de figuras", "## Dispatch directo"):
            self.assertIn(heading, read("docs/operacion-pipeline.md"))

    def test_bibliographer_has_a_search_budget(self) -> None:
        text = read(".claude/agents/bibliografo-propuesta.md")
        self.assertIn("At most **25 search\n   calls**", text)

    def test_stepped_runner_reads_only_its_phase(self) -> None:
        text = read(".claude/commands/propuesta-continuar.md")
        self.assertIn("Leé solo lo que la unidad usa", text)
        self.assertIn("grep -n '^Fase \\|^## '", text)

    def test_figure_agents_run_on_the_light_tier_everywhere(self) -> None:
        for agent in ("tikz-optimizer", "revisor-figuras"):
            self.assertIn("\nmodel: haiku\n", read(f".claude/agents/{agent}.md"))
        model_map = json.loads(read("scripts/gen-opencode.rules.json"))["model_map"]
        self.assertIn("haiku", model_map, "OpenCode would receive a raw 'haiku' model id")

    def test_auditor_runs_once_per_unit(self) -> None:
        self.assertIn("**El auditor\n  corre una sola vez por unidad**", read(".claude/commands/propuesta.md"))


if __name__ == "__main__":
    unittest.main()
