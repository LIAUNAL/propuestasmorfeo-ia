#!/usr/bin/env python3
"""Invariants of the generated Pi port that no generator flag protected.

Three defect classes lived in `.pi/` because nothing asserted them.

**MCP configuration.** Pi reads project MCP servers from `<project>/.pi/mcp.json`
(its own `extensions/mcp/config.js`), never from `.mcp.json`, which is Claude
Code's convention. The port shipped `.mcp.json` only, so inside Pi the pipeline
lost six servers (consensus, openalex, semanticscholar, crossref, pubmed,
arxiv); codegraph, engram and context7 happened to work only because this
machine's user-level `~/.pi/agent/mcp.json` declares them too. A fresh clone or
another workstation would have lost the bibliographic retrieval tools silently.

**Dangling references.** The port rewrites `.claude/agents/<name>.md` into
`.pi/agents/<name>.md`. One source file mentions `coordinador-propuesta.md`, and
that agent is deliberately not ported (`paths.excluded_agents`), so the rewrite
produced a pointer to a file that does not exist.

**Documentation counts.** `.pi/README.md` is the only hand-written file in a
directory the port describes as "GENERATED, never hand-edited". Nothing compared
its declared counts with the directory, so it kept saying seven prompt templates
and one skill after there were ten and two.

The roster check at the end pins the canonical list of dispatchable agents in
every runtime copy, which is where the missing `grant-flow-auditor` survived.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GEN_PI = REPO / "scripts" / "gen-pi.py"
MCP_SOURCE = REPO / ".mcp.json"
PI_MCP = REPO / ".pi" / "mcp.json"

# `coordinador-propuesta` is the pipeline reference document, not a dispatchable
# subagent: `paths.excluded_agents` in gen-pi.rules.json keeps it out of `.pi/`.
NON_DISPATCHABLE_AGENTS = {"coordinador-propuesta"}

# A portable project installs only the runtimes it was created with (`marco init
# --tools`), so a check about `.pi/` or `.opencode/` is meaningful exactly while
# that port exists.
HAS_PI_PORT = (REPO / ".pi" / "agents").is_dir()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_generator(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GEN_PI), "--root", str(root)],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )


class TestPiProjectMcpConfig(unittest.TestCase):
    """`.pi/mcp.json` is the only file Pi reads for project MCP servers."""

    @unittest.skipUnless(HAS_PI_PORT, "este proyecto no instala el puerto Pi")
    def setUp(self):
        self.source_servers = _load_json(MCP_SOURCE)["mcpServers"]

    def test_the_repository_ships_the_pi_mcp_config(self):
        self.assertTrue(
            PI_MCP.is_file(),
            "falta .pi/mcp.json: dentro de Pi ningun servidor MCP del proyecto "
            "llega al pipeline (Pi lee .pi/mcp.json, no .mcp.json)",
        )
        servers = _load_json(PI_MCP)["mcpServers"]
        self.assertEqual(
            set(servers), set(self.source_servers),
            "los servidores de .pi/mcp.json no coinciden con .mcp.json",
        )

    def test_every_ported_server_equals_its_claude_source(self):
        servers = _load_json(PI_MCP)["mcpServers"]
        for name, entry in self.source_servers.items():
            with self.subTest(server=name):
                self.assertEqual(servers[name], entry)

    def test_it_travels_with_the_repository(self):
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", ".pi/mcp.json"],
            capture_output=True, text=True, cwd=str(REPO),
        )
        self.assertNotEqual(
            ignored.returncode, 0,
            ".pi/mcp.json está en .gitignore: sin él un clon nuevo pierde los "
            "servidores MCP del proyecto dentro de Pi",
        )

    def test_the_generator_writes_it_into_a_fresh_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            project.mkdir()
            shutil.copy2(MCP_SOURCE, project / ".mcp.json")
            res = _run_generator(project)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertTrue(
                (project / ".pi" / "mcp.json").is_file(),
                "gen-pi.py no escribió .pi/mcp.json en un proyecto nuevo",
            )
            servers = _load_json(project / ".pi" / "mcp.json")["mcpServers"]
            self.assertEqual(set(servers), set(self.source_servers))

    def test_marco_init_installs_it_into_a_portable_project(self):
        """The delivery path matters as much as this repository: `marco init`
        runs the bundled kit's `gen-pi.py`, so a project created with
        `--tools pi` must come out with a working Pi MCP configuration."""
        sys.path.insert(0, str(REPO / "src"))
        try:
            from morfeo.core.init import init_project
        except ImportError as exc:  # pragma: no cover - src/ is always present
            self.skipTest(f"morfeo no importable: {exc}")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "portable"
            self.assertEqual(
                init_project(project, tools={"claude", "pi"},
                             preset_name="claude", quiet=True),
                0,
            )
            self.assertTrue(
                (project / ".pi" / "mcp.json").is_file(),
                "un proyecto portable creado con --tools pi quedó sin .pi/mcp.json",
            )
            servers = _load_json(project / ".pi" / "mcp.json")["mcpServers"]
            self.assertEqual(set(servers), set(self.source_servers))

    def test_a_project_without_its_own_mcp_json_falls_back_to_the_kit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            project.mkdir()
            res = _run_generator(project)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            servers = _load_json(project / ".pi" / "mcp.json")["mcpServers"]
            self.assertEqual(set(servers), set(self.source_servers))

    def test_a_locally_added_server_survives_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            (project / ".pi").mkdir(parents=True)
            shutil.copy2(MCP_SOURCE, project / ".mcp.json")
            (project / ".pi" / "mcp.json").write_text(
                json.dumps({"mcpServers": {
                    "local-tool": {"command": "local-tool", "args": ["serve"]},
                }}, indent=2) + "\n",
                encoding="utf-8",
            )
            res = _run_generator(project)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            servers = _load_json(project / ".pi" / "mcp.json")["mcpServers"]
            self.assertIn(
                "local-tool", servers,
                "re-generar el puerto borró un servidor MCP añadido localmente",
            )
            self.assertEqual(set(self.source_servers) - set(servers), set())

    def test_a_server_with_a_global_only_key_is_refused(self):
        """Pi rejects `auth` outside the user-level file, so the port must not
        copy such an entry into a project file."""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            project.mkdir()
            (project / ".mcp.json").write_text(
                json.dumps({"mcpServers": {
                    "private": {"url": "https://example.test/mcp",
                                "auth": {"type": "oauth"}},
                }}, indent=2) + "\n",
                encoding="utf-8",
            )
            res = _run_generator(project)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("auth", res.stderr)
            self.assertFalse((project / ".pi" / "mcp.json").is_file())


class TestPiPortReferences(unittest.TestCase):
    """Every `.pi/agents/<name>.md` mentioned by the port must exist."""

    @unittest.skipUnless(HAS_PI_PORT, "este proyecto no instala el puerto Pi")
    def test_no_reference_points_at_a_missing_ported_agent(self):
        missing = {}
        for path in sorted((REPO / ".pi").rglob("*.md")):
            for name in re.findall(r"`\.pi/agents/([A-Za-z0-9_-]+)\.md`",
                                   path.read_text(encoding="utf-8")):
                if not (REPO / ".pi" / "agents" / f"{name}.md").is_file():
                    missing.setdefault(str(path.relative_to(REPO)), set()).add(name)
        self.assertEqual(
            missing, {},
            "el puerto Pi apunta a agentes que no porta (gen-pi.rules.json "
            "reescribe .claude/agents/ a .pi/agents/ sin filtrar excluded_agents)",
        )

    def test_the_step_table_points_at_the_pipeline_body(self):
        steps = (REPO / ".pi" / "prompts" / "_propuesta-steps.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`.pi/prompts/propuesta.md`", steps)
        self.assertNotIn("coordinador-propuesta.md`", steps)


class TestPiPortDocumentation(unittest.TestCase):
    """`.pi/README.md` counts and enumerates what the port actually contains."""

    def setUp(self):
        if not (REPO / ".pi" / "agents").is_dir():
            self.skipTest("este proyecto no instala el puerto Pi")
        self.readme = (REPO / ".pi" / "README.md").read_text(encoding="utf-8")
        self.actual = {
            ".pi/agents/*.md": sorted(p.name for p in (REPO / ".pi" / "agents").glob("*.md")),
            ".pi/prompts/*.md": sorted(p.name for p in (REPO / ".pi" / "prompts").glob("*.md")),
            ".pi/skills/**/SKILL.md": sorted(
                str(p.parent.relative_to(REPO / ".pi" / "skills"))
                for p in (REPO / ".pi" / "skills").rglob("SKILL.md")
            ),
        }

    def _declared_count(self, pattern: str) -> int:
        match = re.search(
            r"`" + re.escape(pattern) + r"` \((\d+) files?\)", self.readme,
        )
        if not match:
            self.fail(f".pi/README.md no declara el conteo de {pattern}")
        return int(match.group(1))

    def test_declared_counts_match_the_directory(self):
        for pattern, files in self.actual.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(
                    self._declared_count(pattern), len(files),
                    f".pi/README.md declara un conteo desactualizado de {pattern}",
                )

    def test_every_prompt_and_skill_is_named(self):
        for name in self.actual[".pi/prompts/*.md"]:
            with self.subTest(prompt=name):
                self.assertIn(name[:-3], self.readme)
        for name in self.actual[".pi/skills/**/SKILL.md"]:
            with self.subTest(skill=name):
                self.assertIn(name, self.readme)

    def test_it_documents_the_mcp_configuration(self):
        self.assertIn(".pi/mcp.json", self.readme)


class TestSubagentRoster(unittest.TestCase):
    """The canonical roster must name every dispatchable agent.

    It said "estos 9 nombres reales" and listed nine, while `grant-flow-auditor`
    was dispatchable too. The mistake lived in the canonical command and in
    every generated copy.
    """

    ROSTERS = (
        ".claude/commands/propuesta.md",
        ".pi/prompts/propuesta.md",
        ".opencode/commands/propuesta.md",
        ".agent/workflows/propuesta.md",
        ".agent/skills/propuesta/SKILL.md",
    )

    def setUp(self):
        self.dispatchable = sorted(
            p.stem for p in (REPO / ".claude" / "agents").glob("*.md")
            if p.stem not in NON_DISPATCHABLE_AGENTS
        )
        self.rosters = tuple(r for r in self.ROSTERS if (REPO / r).is_file())
        self.assertIn(
            self.ROSTERS[0], self.rosters,
            "falta el comando canonico .claude/commands/propuesta.md",
        )

    def _roster_block(self, relpath: str) -> str:
        text = (REPO / relpath).read_text(encoding="utf-8")
        start = text.find("## Roster de subagentes")
        self.assertNotEqual(start, -1, f"{relpath} no tiene el roster de subagentes")
        end = text.find("\n## ", start)
        return text[start:end if end != -1 else len(text)]

    def test_every_dispatchable_agent_is_listed(self):
        for relpath in self.rosters:
            block = self._roster_block(relpath)
            for agent in self.dispatchable:
                with self.subTest(roster=relpath, agent=agent):
                    self.assertIn(agent, block)

    def test_the_declared_count_matches_the_names_it_lists(self):
        for relpath in self.rosters:
            block = self._roster_block(relpath)
            match = re.search(r"estos (\d+) nombres reales", block)
            self.assertIsNotNone(
                match, f"{relpath}: el roster no declara cuántos nombres existen",
            )
            with self.subTest(roster=relpath):
                self.assertEqual(int(match.group(1)), len(self.dispatchable))

    def test_the_reference_document_is_not_presented_as_a_subagent(self):
        for relpath in self.rosters:
            with self.subTest(roster=relpath):
                self.assertIn("documento de referencia", self._roster_block(relpath))


if __name__ == "__main__":
    unittest.main()
