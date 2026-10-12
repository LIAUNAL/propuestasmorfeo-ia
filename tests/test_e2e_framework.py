#!/usr/bin/env python3
"""
End-to-End Test Suite for marco-propuestas-ia framework.
Verifies CLI commands, kit manifest integrity, generator scripts, and build operations.
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

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = REPO_ROOT / "scripts" / "marco_cli.py"
MANIFEST_FILE = REPO_ROOT / "scripts" / "kit-manifest.json"
BUILD_SCRIPT = REPO_ROOT / "plantilla" / "build.sh"


class TestKitManifestIntegrity(unittest.TestCase):
    """Verify kit-manifest.json file structure and kit path existence."""

    def test_manifest_file_exists(self):
        self.assertTrue(MANIFEST_FILE.is_file(), f"Manifest file missing: {MANIFEST_FILE}")

    def test_all_kit_paths_exist_in_source(self):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("version", manifest)
        self.assertIn("kit_paths", manifest)
        self.assertIsInstance(manifest["kit_paths"], list)

        missing_files = []
        for rel_path in manifest["kit_paths"]:
            full_path = REPO_ROOT / rel_path
            if not full_path.is_file():
                missing_files.append(rel_path)

        self.assertEqual(
            missing_files,
            [],
            f"The following kit_paths listed in manifest do not exist in repo: {missing_files}",
        )

    def test_manifest_version_format(self):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        version = manifest.get("version", "")
        parts = version.split(".")
        self.assertEqual(len(parts), 3, f"Manifest version '{version}' is not valid semver x.y.z")


class TestMarcoCliCommands(unittest.TestCase):
    """Verify marco CLI init, status, upgrade, and flags."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="marco_test_")
        self.project_dir = Path(self.temp_dir) / "test_project"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_cli(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(CLI_SCRIPT)] + args
        env = os.environ.copy()
        env["MARCO_KIT_ROOT"] = str(REPO_ROOT)
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if check and res.returncode != 0:
            self.fail(
                f"CLI command failed with exit code {res.returncode}:\n"
                f"CMD: {' '.join(cmd)}\n"
                f"STDOUT: {res.stdout}\n"
                f"STDERR: {res.stderr}"
            )
        return res

    def test_init_creates_full_portable_layout(self):
        res = self._run_cli(
            [
                "init",
                str(self.project_dir),
                "--title",
                "Test Title",
                "--lang",
                "es",
                "--model-preset",
                "claude",
            ]
        )
        self.assertEqual(res.returncode, 0)

        # Check required files and dirs
        self.assertTrue((self.project_dir / ".marco" / "version").is_file())
        self.assertTrue((self.project_dir / ".marco" / "manifest.json").is_file())
        self.assertTrue((self.project_dir / ".marco" / "config.json").is_file())
        self.assertTrue((self.project_dir / "AGENTS.md").is_file())
        self.assertTrue((self.project_dir / "DECISIONS.md").is_file())
        self.assertTrue((self.project_dir / "README.md").is_file())
        # The portable project gets the versioned LaTeX skeleton plus the run
        # scaffolder; runs themselves are created later by /propuesta-init.
        self.assertTrue((self.project_dir / "plantilla" / "build.sh").is_file())
        self.assertTrue((self.project_dir / "plantilla" / "scripts" / "compile_tikz.py").is_file())
        self.assertTrue((self.project_dir / "scripts" / "init-run.sh").is_file())
        # No run content at the project root.
        for stray in ("proposal", "vault", "info_data", "insumos", "artefactos", "grafos", "redaccion"):
            self.assertFalse(
                (self.project_dir / stray).exists(),
                f"portable project must not seed run content at its root: {stray}/",
            )
        self.assertTrue((self.project_dir / "scripts" / "marco_cli.py").is_file())
        self.assertTrue((self.project_dir / "scripts" / "apa.csl").is_file())
        self.assertTrue((self.project_dir / ".opencode").is_dir())
        self.assertTrue((self.project_dir / ".pi").is_dir())
        self.assertTrue((self.project_dir / ".agent").is_dir())

        # Verify config contents
        with open(self.project_dir / ".marco" / "config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg.get("language"), "es")
        self.assertEqual(cfg.get("model_preset"), "claude")

    def test_status_command(self):
        self._run_cli(["init", str(self.project_dir), "--lang", "es", "--model-preset", "claude"])
        res = self._run_cli(["status", str(self.project_dir)])
        self.assertEqual(res.returncode, 0)
        self.assertIn("DECISIONS.md", res.stdout)

    def test_status_outside_project_fails(self):
        non_project = Path(self.temp_dir) / "empty_dir"
        non_project.mkdir()
        res = self._run_cli(["status", str(non_project)], check=False)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("not a portable marco project", res.stderr + res.stdout)

    def test_upgrade_command(self):
        self._run_cli(["init", str(self.project_dir), "--lang", "es", "--model-preset", "claude"])
        res = self._run_cli(["upgrade", str(self.project_dir)])
        self.assertEqual(res.returncode, 0)

    def test_upgrade_with_tools_updates_config_and_scaffolds_runtimes(self):
        # Init with only claude
        self._run_cli(
            [
                "init",
                str(self.project_dir),
                "--tools",
                "claude",
                "--lang",
                "es",
                "--model-preset",
                "claude",
            ]
        )
        self.assertTrue((self.project_dir / ".claude").is_dir())
        self.assertFalse((self.project_dir / ".opencode").is_dir())
        self.assertFalse((self.project_dir / ".agent").is_dir())

        # Upgrade with --tools claude,antigravity,opencode
        res = self._run_cli(
            [
                "upgrade",
                str(self.project_dir),
                "--tools",
                "claude,antigravity,opencode",
            ]
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Tools: antigravity, claude, opencode", res.stdout)

        # Check config updated
        with open(self.project_dir / ".marco" / "config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg.get("tools"), ["antigravity", "claude", "opencode"])

        # Check new runtimes scaffolded
        self.assertTrue((self.project_dir / ".opencode").is_dir())
        self.assertTrue((self.project_dir / ".agent").is_dir())

    def test_upgrade_and_status_default_to_current_dir(self):
        # Init project in self.project_dir
        self._run_cli(["init", str(self.project_dir), "--lang", "es", "--model-preset", "claude"])

        # Run upgrade and status with cwd set to self.project_dir and no dir arg
        cmd = [sys.executable, str(CLI_SCRIPT), "upgrade"]
        env = os.environ.copy()
        env["MARCO_KIT_ROOT"] = str(REPO_ROOT)
        res_upg = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(self.project_dir))
        self.assertEqual(res_upg.returncode, 0)
        self.assertIn("marco upgrade", res_upg.stdout)

        cmd_st = [sys.executable, str(CLI_SCRIPT), "status"]
        res_st = subprocess.run(cmd_st, capture_output=True, text=True, env=env, cwd=str(self.project_dir))
        self.assertEqual(res_st.returncode, 0)
        self.assertIn("DECISIONS.md", res_st.stdout)

    def test_agent_command_interception(self):
        res = self._run_cli(["/propuesta-analizar"], check=False)
        self.assertEqual(res.returncode, 0)
        self.assertIn("ES UN COMANDO DE AGENTE DE IA", res.stdout)
        self.assertIn("pi .", res.stdout)

    def test_invalid_model_preset_fails(self):
        res = self._run_cli(
            ["init", str(self.project_dir), "--lang", "es", "--model-preset", "invalid_preset_name"], check=False
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("unknown model preset", (res.stderr + res.stdout).lower())



class TestGenerators(unittest.TestCase):
    """Verify runtime generator scripts execute cleanly against a project with .claude/ scaffolded."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="marco_gen_test_")
        self.target_dir = Path(self.temp_dir) / "target"

        # Initialize target with .claude/ directory
        cmd = [
            sys.executable,
            str(CLI_SCRIPT),
            "init",
            str(self.target_dir),
            "--tools",
            "claude",
            "--lang",
            "es",
            "--model-preset",
            "claude",
        ]
        env = os.environ.copy()
        env["MARCO_KIT_ROOT"] = str(REPO_ROOT)
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to initialize test project for generator test: {res.stderr}")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_opencode_generator(self):
        gen_script = REPO_ROOT / "scripts" / "gen-opencode.py"
        res = subprocess.run(
            [sys.executable, str(gen_script), "--root", str(self.target_dir)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"gen-opencode.py failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertTrue((self.target_dir / ".opencode").is_dir())

    def test_pi_generator(self):
        gen_script = REPO_ROOT / "scripts" / "gen-pi.py"
        res = subprocess.run(
            [sys.executable, str(gen_script), "--root", str(self.target_dir)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"gen-pi.py failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertTrue((self.target_dir / ".pi").is_dir())

    def test_antigravity_generator(self):
        gen_script = REPO_ROOT / "scripts" / "gen-antigravity.py"
        res = subprocess.run(
            [sys.executable, str(gen_script), "--root", str(self.target_dir)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"gen-antigravity.py failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertTrue((self.target_dir / ".agent").is_dir())

    def test_pi_generator_ports_skills(self):
        gen_script = REPO_ROOT / "scripts" / "gen-pi.py"
        res = subprocess.run(
            [sys.executable, str(gen_script), "--root", str(self.target_dir)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"gen-pi.py failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        skill = self.target_dir / ".pi" / "skills" / "estilo-natural-es" / "SKILL.md"
        self.assertTrue(skill.is_file(), "gen-pi.py did not port .claude/skills into .pi/skills/")
        text = skill.read_text(encoding="utf-8")
        self.assertIn("name: estilo-natural-es", text)
        self.assertIn("description:", text)

    def test_antigravity_generator_ports_skills(self):
        gen_script = REPO_ROOT / "scripts" / "gen-antigravity.py"
        res = subprocess.run(
            [sys.executable, str(gen_script), "--root", str(self.target_dir)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"gen-antigravity.py failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        skill = self.target_dir / ".agent" / "skills" / "estilo-natural-es" / "SKILL.md"
        self.assertTrue(skill.is_file(), "gen-antigravity.py did not port .claude/skills into .agent/skills/")
        self.assertIn("name: estilo-natural-es", skill.read_text(encoding="utf-8"))
        cmd_skill = self.target_dir / ".agent" / "skills" / "propuesta-continuar" / "SKILL.md"
        self.assertTrue(cmd_skill.is_file(), "gen-antigravity.py did not port slash commands into .agent/skills/")
        self.assertIn("name: propuesta-continuar", cmd_skill.read_text(encoding="utf-8"))


class TestGeneratorDrift(unittest.TestCase):
    """The committed ports must be byte-identical to what the generators emit."""

    def _check(self, script_name: str):
        script = REPO_ROOT / "scripts" / script_name
        res = subprocess.run(
            [sys.executable, str(script), "--check"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(
            res.returncode,
            0,
            f"{script_name} --check reported drift (exit {res.returncode}):\n"
            f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}",
        )

    def test_pi_port_is_current(self):
        self._check("gen-pi.py")

    def test_opencode_port_is_current(self):
        self._check("gen-opencode.py")

    def test_antigravity_port_is_current(self):
        self._check("gen-antigravity.py")

    def test_canonical_skill_exists_and_is_ported(self):
        canonical = REPO_ROOT / ".claude" / "skills" / "estilo-natural-es" / "SKILL.md"
        self.assertTrue(canonical.is_file(), "canonical skill missing")
        for ported in (
            REPO_ROOT / ".pi" / "skills" / "estilo-natural-es" / "SKILL.md",
            REPO_ROOT / ".agent" / "skills" / "estilo-natural-es" / "SKILL.md",
        ):
            self.assertTrue(ported.is_file(), f"skill not ported: {ported}")

    def test_canonical_skill_has_no_drift_paths(self):
        text = (REPO_ROOT / ".claude" / "skills" / "estilo-natural-es" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn(".claude/", text, "skill must not hardcode a runtime path")
        self.assertIn("never introduces deliberate typos", text)


class TestBuildScriptOptions(unittest.TestCase):
    """Verify redaccion/build.sh option handling and CSL validation."""

    def test_help_option(self):
        res = subprocess.run([str(BUILD_SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("build.sh", res.stdout)
        self.assertIn("--docx", res.stdout)

    def test_invalid_csl_option_fails(self):
        res = subprocess.run(
            [str(BUILD_SCRIPT), "--docx", "--csl", "non_existent_style.csl"],
            capture_output=True,
            text=True,
            cwd=str(BUILD_SCRIPT.parent),
        )
        self.assertNotEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
