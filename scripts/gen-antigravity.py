#!/usr/bin/env python3
"""Deterministic, zero-LLM generator that ports canonical .claude/ agents and commands into Google Antigravity .agent/skills and .agent/workflows.

  python3 scripts/gen-antigravity.py           # write .agent/
  python3 scripts/gen-antigravity.py --check   # dry-run; exit 3 on drift

Exit codes: 0 ok; 1 usage; 2 source/rules error; 3 drift.
Never writes under .claude/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
RULES_PATH = Path(__file__).resolve().parent / "gen-antigravity.rules.json"


class GeneratorError(Exception):
    pass


class DriftError(Exception):
    pass


def load_rules() -> dict:
    if not RULES_PATH.is_file():
        raise GeneratorError(f"rules file not found: {RULES_PATH}")
    with RULES_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_project_config(root: Path) -> dict | None:
    config_path = root / ".marco" / "config.json"
    if not config_path.is_file():
        return None
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def split_frontmatter(text: str, source_path: Path) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise GeneratorError(f"{source_path}: missing frontmatter opening '---'")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise GeneratorError(f"{source_path}: missing frontmatter closing '---'")
    fm_block = text[4:end]
    body = text[end + 5 :]
    frontmatter: dict[str, str] = {}
    for line in fm_block.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise GeneratorError(f"{source_path}: malformed frontmatter line: {line!r}")
        key, _, value = line.partition(":")
        frontmatter[key.strip()] = value.strip()
    return frontmatter, body


def apply_substitutions(text: str, rules: dict) -> str:
    for rule in rules.get("substitutions_all") or []:
        find = rule.get("find") or ""
        if find:
            text = text.replace(find, rule.get("replace", ""))
    return text


def format_frontmatter_field(key: str, val: str) -> str:
    """Format a YAML frontmatter field, quoting if it contains special characters."""
    if ": " in val or "\n" in val or '"' in val or "'" in val or val.startswith(
        ("-", "?", ":", ",", "[", "]", "{", "}", "#", "&", "*", "!", "|", ">", "'", '"', "%", "@", "`")
    ):
        return f"{key}: {json.dumps(val, ensure_ascii=False)}"
    return f"{key}: {val}"


def build_skill(agent_file: Path, rules: dict, config: dict | None) -> tuple[str, str]:
    """Compile agent file into SKILL.md content."""
    text = agent_file.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text, agent_file)
    
    agent_name = agent_file.stem
    name = fm.get("name", agent_name)
    description = fm.get("description", f"Subagente {name}")

    if config and "agent_models" in config and agent_name in config["agent_models"]:
        fm["model"] = config["agent_models"][agent_name]

    lines = ["---", f"name: {name}", format_frontmatter_field("description", description)]
    if "model" in fm:
        lines.append(f"model: {fm['model']}")
    lines.append("---\n")

    body = apply_substitutions(body, rules)
    content = "\n".join(lines) + body
    return agent_name, content


def build_project_skill(skill_file: Path, rules: dict) -> str:
    """Compile a canonical .claude/skills/**/SKILL.md into an Antigravity skill.

    Unlike build_skill (which derives a skill from an agent), this copies a real
    skill: Pi/Antigravity skill frontmatter is `name` + `description` (plus an
    optional `model`).
    """
    text = skill_file.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text, skill_file)
    name = fm.get("name") or skill_file.parent.name
    description = fm.get("description")
    if not description:
        raise GeneratorError(f"{skill_file}: skill frontmatter missing 'description'")

    lines = ["---", f"name: {name}", format_frontmatter_field("description", description)]
    if "model" in fm:
        lines.append(f"model: {fm['model']}")
    lines.append("---\n")

    body = apply_substitutions(body, rules)
    return "\n".join(lines) + body


def build_workflow(cmd_file: Path, rules: dict) -> tuple[str, str]:
    """Compile command file into workflow markdown content."""
    text = cmd_file.read_text(encoding="utf-8")
    cmd_name = cmd_file.name
    if not text.startswith("---\n"):
        body = apply_substitutions(text, rules)
        return cmd_name, body

    fm, body = split_frontmatter(text, cmd_file)
    body = apply_substitutions(body, rules)

    description = fm.get("description", f"Workflow {cmd_file.stem}")
    header = f"# Workflow: {cmd_file.stem}\n\n> {description}\n\n"
    content = header + body
    return cmd_name, content


def build_command_skill(cmd_file: Path, rules: dict) -> tuple[str, str]:
    """Compile command file into an Antigravity SKILL.md for first-class slash-command execution."""
    text = cmd_file.read_text(encoding="utf-8")
    name = cmd_file.stem
    if not text.startswith("---\n"):
        description = f"Comando {name}"
        body = text
    else:
        fm, body = split_frontmatter(text, cmd_file)
        description = fm.get("description", f"Comando {name}")

    lines = ["---", f"name: {name}", format_frontmatter_field("description", description), "---\n"]
    body = apply_substitutions(body, rules)
    content = "\n".join(lines) + body
    return name, content


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate .agent/ skills and workflows")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Target project root directory")
    parser.add_argument("--check", action="store_true", help="Dry-run and exit non-zero on changes/drift")
    args = parser.parse_args()

    root: Path = args.root.resolve()
    try:
        rules = load_rules()
    except GeneratorError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    config = load_project_config(root)

    source_agents_dir = root / rules["paths"]["source_agents_dir"]
    source_commands_dir = root / rules["paths"]["source_commands_dir"]
    source_skills_dir = root / rules["paths"]["source_skills_dir"]
    target_skills_dir = root / rules["paths"]["target_skills_dir"]
    target_workflows_dir = root / rules["paths"]["target_workflows_dir"]

    if not source_agents_dir.is_dir() or not source_commands_dir.is_dir():
        print(f"error: source directory missing under {root}", file=sys.stderr)
        return 2

    skills_to_write: list[tuple[Path, str]] = []
    workflows_to_write: list[tuple[Path, str]] = []

    # Process agents
    for agent_file in sorted(source_agents_dir.glob("*.md")):
        agent_name, content = build_skill(agent_file, rules, config)
        skill_file = target_skills_dir / agent_name / "SKILL.md"
        skills_to_write.append((skill_file, content))

    # Process commands (both as legacy workflows and modern Antigravity skills for slash-command support)
    for cmd_name in rules.get("command_files", []):
        cmd_file = source_commands_dir / cmd_name
        if cmd_file.is_file():
            out_name, content = build_workflow(cmd_file, rules)
            workflow_file = target_workflows_dir / out_name
            workflows_to_write.append((workflow_file, content))

            if not cmd_name.startswith("_"):
                cmd_skill_name, cmd_skill_content = build_command_skill(cmd_file, rules)
                cmd_skill_file = target_skills_dir / cmd_skill_name / "SKILL.md"
                skills_to_write.append((cmd_skill_file, cmd_skill_content))

    # Process canonical skills (.claude/skills/**/SKILL.md), mirroring the
    # nested layout under .agent/skills/<skill-dir>/SKILL.md.
    if source_skills_dir.is_dir():
        for skill_file in sorted(source_skills_dir.glob("**/SKILL.md")):
            rel = skill_file.relative_to(source_skills_dir)
            skills_to_write.append(
                (target_skills_dir / rel, build_project_skill(skill_file, rules))
            )

    if args.check:
        drift = False
        for path, content in skills_to_write + workflows_to_write:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                print(f"DRIFT: {path} is outdated or missing", file=sys.stderr)
                drift = True
        return 3 if drift else 0

    # Write files
    for path, content in skills_to_write + workflows_to_write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    print(f"Generated {len(skills_to_write)} skills and {len(workflows_to_write)} workflows under {root}/.agent/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
