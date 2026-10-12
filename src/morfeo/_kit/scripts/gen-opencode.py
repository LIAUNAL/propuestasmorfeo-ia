#!/usr/bin/env python3
"""Deterministic, zero-LLM-call generator that ports the dispatched
.claude/agents/*.md subagents and .claude/commands/propuesta.md into
.opencode/agents/*.md and .opencode/commands/propuesta.md.

Read-only with respect to everything under .claude/. All the actual
mapping/substitution/drift-detection data lives in
scripts/gen-opencode.rules.json -- this script is pure logic, no
project-specific data. Extend the port by editing the rules file, not
this file.

Usage (from repo root, or anywhere -- the repo root is resolved via
__file__):

    python3 scripts/gen-opencode.py            # write .opencode/
    python3 scripts/gen-opencode.py --check     # dry-run, no writes;
                                                  non-zero exit if output
                                                  would change or drift
                                                  is found

Exit codes: 0 ok; 1 usage; 2 source missing; 3 drift found.

Manual one-time OpenCode setup (not automated by this script):
This generator only writes .opencode/agents/*.md and
.opencode/commands/propuesta.md. It does not create or edit any
opencode.json. To let OpenCode's primary agent dispatch the 9 ported
subagents via the `task` tool, allow-list them under `permission.task` in
your OpenCode config -- today that is a user-environment file
(~/.config/opencode/opencode.json), not something this repo commits. No
project-level opencode.json exists at the repo root as of this writing; if
one is ever added, it would live at <repo_root>/opencode.json and take the
same `permission.task` shape. Approval gates in the ported propuesta.md
dispatcher require an interactive/resumable OpenCode session -- headless
`opencode run` is not supported for those gates.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Default root is the repo root (parent of scripts/).  The --root CLI flag
# overrides this so marco init/upgrade can point the generator at the target
# portable-project folder instead of CWD.  All source reads (.claude/) and
# output writes (.opencode/) are relative to this root.
REPO_ROOT: Path = Path(__file__).resolve().parent.parent
RULES_PATH = Path(__file__).resolve().parent / "gen-opencode.rules.json"


class GeneratorError(Exception):
    """Fatal error that should abort the run with a clear message."""


class DriftError(Exception):
    """Drift-lint found an unmapped Claude-specific pattern in output."""


# --------------------------------------------------------------------------
# Rules loading
# --------------------------------------------------------------------------


def load_rules() -> dict:
    if not RULES_PATH.is_file():
        raise GeneratorError(f"rules file not found: {RULES_PATH}")
    with RULES_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)

# --------------------------------------------------------------------------
# Project config (.marco/config.json)
# --------------------------------------------------------------------------


def load_project_config(root: Path) -> dict | None:
    """Read ``<root>/.marco/config.json`` and return the dict, or None if
    the file is absent or unparseable (backward compat for legacy projects)."""
    config_path = root / ".marco" / "config.json"
    if not config_path.is_file():
        return None
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


# --------------------------------------------------------------------------
# Frontmatter / body split
# --------------------------------------------------------------------------



def split_frontmatter(text: str, source_path: Path) -> tuple[dict, str]:
    """Split a Claude markdown file into (frontmatter dict, body str).

    Frontmatter is a flat `key: value` block between two `---` lines --
    no PyYAML needed, no nesting in any of the 10 source files.
    """
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


# --------------------------------------------------------------------------
# Frontmatter mapping
# --------------------------------------------------------------------------


def map_agent_frontmatter(fm: dict, source_path: Path, rules: dict,
                          agent_name: str | None = None,
                          config: dict | None = None) -> dict:
    out: dict = {}

    if "description" not in fm:
        raise GeneratorError(f"{source_path}: agent frontmatter missing 'description'")
    out["description"] = fm["description"]

    out["mode"] = rules["frontmatter"]["constants"]["mode"]

    # Determine the source model id.  When a project config is present the
    # config's per-agent model is authoritative (it may be a Claude model
    # like "opus" or a runtime-native id like "gpt-5.6-sol").  When config
    # is absent we read the model from the .claude/ source file's
    # frontmatter (backward compat).
    model_map = rules["model_map"]
    if config is not None and agent_name is not None:
        agent_models: dict = config.get("agent_models", {})
        source_model = agent_models.get(agent_name)
    else:
        source_model = None

    if source_model is None:
        source_model = fm.get("model")
        if not source_model:
            raise GeneratorError(f"{source_path}: agent frontmatter missing 'model'")

    # Look up the source model in model_map.  If found, use the mapped
    # value (e.g. opus -> openai/gpt-5.4 for the OpenCode runtime).  If
    # not found (e.g. "gpt-5.6-sol" or "opencode-go/glm-5.2" which are
    # already OpenCode-native ids), use the source directly.
    if source_model in model_map:
        out["model"] = model_map[source_model]
    else:
        out["model"] = source_model

    permission_map = rules["permission_map"]
    claude_tools = fm.get("tools")
    lookup_key = claude_tools if claude_tools else "__no_tools_field__"
    if lookup_key not in permission_map:
        raise GeneratorError(
            f"{source_path}: tools value {claude_tools!r} has no entry in "
            "rules.json permission_map -- refusing to guess a permission "
            "(never narrow beyond the Claude original)"
        )
    permission = permission_map[lookup_key]
    if permission is not None:
        out["permission"] = permission

    # name is intentionally dropped -- OpenCode derives the agent id from
    # the output filename, which is 1:1 with the source filename.
    return out


def map_command_frontmatter(fm: dict, source_path: Path, rules: dict) -> dict:
    out: dict = {}
    if "description" not in fm:
        raise GeneratorError(f"{source_path}: command frontmatter missing 'description'")
    out["description"] = fm["description"]
    # argument-hint is intentionally dropped -- no OpenCode equivalent.
    return out


def render_frontmatter(fm: dict, key_order: list[str]) -> str:
    lines = ["---"]
    for key in key_order:
        if key not in fm:
            continue
        value = fm[key]
        if isinstance(value, dict):
            # permission:
            #   edit: allow|deny
            #   bash: allow|deny
            #
            # NOTE: OpenCode's markdown-frontmatter YAML parser rejects the
            # inline flow-map form `permission: {edit: allow, bash: deny}`
            # with "Expected PermissionActionConfig, got '{...}'" -- verified
            # against the installed CLI (opencode 1.17.15, `opencode agent
            # list`). Multi-line block form is what the real parser accepts.
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  {sub_key}: {sub_value}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Body substitution
# --------------------------------------------------------------------------


def apply_substitutions(body: str, filename: str, rules: dict) -> str:
    for rule in rules["substitutions"]:
        applies_to = rule.get("applies_to") or []
        if filename not in applies_to:
            continue
        if not rule.get("literal", True):
            raise GeneratorError(
                f"substitution rule {rule.get('id')!r}: non-literal rules are "
                "not supported by this generator"
            )
        find = rule["find"]
        if not find:
            continue
        body = body.replace(find, rule["replace"])
    return body


# --------------------------------------------------------------------------
# Drift lint
# --------------------------------------------------------------------------


def drift_lint(text: str, rel_output_path: str, patterns: list[str]) -> list[str]:
    messages = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            if pattern in line:
                messages.append(
                    f'DRIFT: {rel_output_path}:{lineno}: unmapped pattern "{pattern}" '
                    "-- add a rule to gen-opencode.rules.json or fix source."
                )
    return messages


# --------------------------------------------------------------------------
# Non-mutating write helper
# --------------------------------------------------------------------------


def write_output(relpath: str, text: str, output_roots: tuple[str, ...], check: bool) -> tuple[bool, str]:
    """Write `text` to `<repo_root>/relpath`, hard-asserting relpath is
    under one of `output_roots`. Returns (changed, previous_content).

    In --check mode, does not write; only reports whether it would change.
    """
    if not any(relpath.startswith(root) for root in output_roots):
        raise GeneratorError(
            f"refusing to write outside allowed output roots {output_roots}: {relpath}"
        )
    if relpath.startswith(".claude/") or "/.claude/" in relpath:
        raise GeneratorError(f"refusing to write under .claude/: {relpath}")

    dest = REPO_ROOT / relpath
    previous = dest.read_text(encoding="utf-8") if dest.is_file() else None
    changed = previous != text

    if not check and changed:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")

    return changed, (previous or "")


# --------------------------------------------------------------------------
# Config-driven overrides (.marco/config.json)
# --------------------------------------------------------------------------


def override_agent_models(built: list[tuple[str, str]], config: dict, agents_dir: str) -> list[tuple[str, str]]:
    """Rewrite the ``model:`` frontmatter line in every generated agent file
    to match ``config["agent_models"][<agent-name>]``.  Returns a new list
    with the overridden texts; files whose agent is not in the config map
    are left unchanged.
    """
    agent_models: dict = config.get("agent_models", {})
    if not agent_models:
        return built

    out: list[tuple[str, str]] = []
    for relpath, text in built:
        relpath_str = str(relpath)
        if relpath_str.startswith(agents_dir):
            filename = relpath_str[len(agents_dir) + 1 :]
            agent_name = filename.removesuffix(".md")
            expected = agent_models.get(agent_name)
            if expected is not None:
                text = re.sub(
                    r"^model:\s.*$",
                    f"model: {expected}",
                    text,
                    count=1,
                    flags=re.MULTILINE,
                )
        out.append((relpath, text))
    return out


def config_drift_lint(
    built: list[tuple[str, str]], config: dict, agents_dir: str, repo_root: Path
) -> list[str]:
    """Check each on-disk agent file's ``model:`` line against
    ``config["agent_models"]``.  Files that do not exist yet (first run)
    are not flagged -- the write phase will create them correctly.
    Returns a list of drift messages (empty = no drift).
    """
    agent_models: dict = config.get("agent_models", {})
    if not agent_models:
        return []

    messages: list[str] = []
    for relpath, _text in built:
        relpath_str = str(relpath)
        if not relpath_str.startswith(agents_dir):
            continue
        filename = relpath_str[len(agents_dir) + 1 :]
        agent_name = filename.removesuffix(".md")
        expected = agent_models.get(agent_name)
        if expected is None:
            continue
        dest = repo_root / relpath_str
        if not dest.is_file():
            continue  # not created yet -- not drift
        on_disk = dest.read_text(encoding="utf-8")
        found_model = False
        for line in on_disk.splitlines():
            if line.startswith("model:"):
                found_model = True
                actual = line[len("model:") :].strip()
                if actual != expected:
                    messages.append(
                        f'CONFIG-DRIFT: {relpath_str}: on-disk model is "{actual}", '
                        f'expected "{expected}" (from .marco/config.json)'
                    )
                break
        if not found_model:
            messages.append(
                f'CONFIG-DRIFT: {relpath_str}: missing "model:" line, '
                f'expected "{expected}" (from .marco/config.json)'
            )
    return messages


# --------------------------------------------------------------------------
# Per-file pipeline (BUILD phase -- pure, no filesystem writes)
# --------------------------------------------------------------------------


def build_agent(filename: str, rules: dict,
                config: dict | None = None) -> tuple[str, str]:
    """Return (output_relpath, output_text) for one agent. No writes."""
    paths = rules["paths"]
    source_path = REPO_ROOT / paths["source_agents_dir"] / filename
    if not source_path.is_file():
        raise GeneratorError(f"source agent missing: {source_path}")

    text = source_path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text, source_path)
    agent_name = filename.removesuffix(".md")
    out_fm = map_agent_frontmatter(fm, source_path, rules,
                                   agent_name=agent_name, config=config)
    out_body = apply_substitutions(body, filename, rules)

    rendered_fm = render_frontmatter(out_fm, rules["frontmatter"]["agent_key_order"])
    output_relpath = f"{paths['output_agents_dir']}/{filename}"
    return output_relpath, rendered_fm + out_body


def build_command(filename: str, rules: dict) -> tuple[str, str]:
    """Return (output_relpath, output_text) for one command. No writes."""
    paths = rules["paths"]
    source_path = REPO_ROOT / paths["source_commands_dir"] / filename
    if not source_path.is_file():
        raise GeneratorError(f"source command missing: {source_path}")

    text = source_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        out_body = apply_substitutions(text, filename, rules)
        output_relpath = f"{paths['output_commands_dir']}/{filename}"
        return output_relpath, out_body

    fm, body = split_frontmatter(text, source_path)
    out_fm = map_command_frontmatter(fm, source_path, rules)
    out_body = apply_substitutions(body, filename, rules)

    rendered_fm = render_frontmatter(out_fm, rules["frontmatter"]["command_key_order"])
    output_relpath = f"{paths['output_commands_dir']}/{filename}"
    return output_relpath, rendered_fm + out_body


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    check = False
    root = None
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--check":
            check = True
            i += 1
        elif arg == "--root":
            i += 1
            if i >= len(argv):
                print(f"error: --root requires an argument", file=sys.stderr)
                return 1
            root = Path(argv[i]).resolve()
            i += 1
        else:
            print(f"usage: {argv[0]} [--check] [--root DIR]", file=sys.stderr)
            return 1

    # Override REPO_ROOT when --root is given (backward compatible: no flag
    # keeps the original behaviour).
    global REPO_ROOT
    if root is not None:
        REPO_ROOT = root

    # Load project config (.marco/config.json) – may be None for legacy
    # projects, in which case we fall back to current behaviour.
    config = load_project_config(REPO_ROOT)

    try:
        rules = load_rules()
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    paths = rules["paths"]
    excluded = set(paths.get("excluded_agents", []))

    # BUILD phase: compute every output file's text in memory first. No
    # writes happen here, so a drift hit on file N never leaves files
    # 1..N-1 written to disk -- drift-lint covers the WHOLE output set
    # before any write commits.
    built: list[tuple[str, str]] = []
    try:
        for filename in paths["agent_files"]:
            if filename in excluded:
                continue
            built.append(build_agent(filename, rules, config=config))
        for filename in paths["command_files"]:
            built.append(build_command(filename, rules))
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # DRIFT-LINT phase: scan every built output before writing anything.
    agents_dir = paths["output_agents_dir"]
    all_drift: list[str] = []
    for output_relpath, output_text in built:
        all_drift.extend(drift_lint(output_text, output_relpath, rules["drift_patterns"]))

    # Config-drift check: if config is present, verify on-disk agent
    # model lines match the config.
    if config is not None:
        all_drift.extend(config_drift_lint(built, config, agents_dir, REPO_ROOT))

    if all_drift:
        for msg in all_drift:
            print(msg, file=sys.stderr)
        return 3

    # WRITE phase: only reached when the entire output set is drift-free.
    allowed_roots = (paths["output_agents_dir"], paths["output_commands_dir"])
    try:
        for output_relpath, output_text in built:
            changed, _ = write_output(output_relpath, output_text, allowed_roots, check)
            verb = "would write" if check and changed else ("wrote" if changed else "unchanged")
            print(f"{verb}: {output_relpath}")
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if check:
        print("--check: no drift, no writes performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
