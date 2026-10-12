#!/usr/bin/env python3
"""Deterministic, zero-LLM-call generator that ports the dispatched
.claude/agents/*.md subagents, the .claude/commands/*.md commands and the
.claude/skills/**/SKILL.md skills into .pi/agents/*.md, .pi/prompts/*.md and
.pi/skills/**/SKILL.md (Pi's project-level subagent, prompt-template and skill
directories).

Read-only with respect to everything under .claude/. All the actual
mapping/substitution/drift-detection data lives in
scripts/gen-pi.rules.json -- this script is pure logic, no project-specific
data. Extend the port by editing the rules file, not this file.

Usage (from repo root, or anywhere -- the repo root is resolved via
__file__):

    python3 scripts/gen-pi.py            # write .pi/
    python3 scripts/gen-pi.py --check    # dry-run, no writes; non-zero exit
                                         #   if output would change or drift
                                         #   is found
    python3 scripts/gen-pi.py --root DIR # write DIR/.pi instead of the repo's;
                                         #   used by `marco init/upgrade` to
                                         #   generate the port inside a
                                         #   portable project (sources are
                                         #   always read from this repo)

Exit codes: 0 ok; 1 usage; 2 source missing; 3 drift found.

Why these output paths (verified against the installed Pi docs and the
gentle-pi subagent loader on this machine):
  * `.pi/agents/*.md` is a project-level subagent root, so `subagent_run`
    discovers the ported agents with no extra setup.
  * `.pi/prompts/*.md` is Pi's project prompt-template directory, so each
    command file becomes a `/<filename>` slash command.
  * `.pi/skills/**/SKILL.md` is Pi's project skills directory, so each ported
    skill is advertised by name+description and loadable with `/skill:<name>`.
  * All load only after project trust is granted (`pi --approve`, or the
    interactive trust prompt). Approval gates need an interactive or resumed
    session; `pi -p` cannot stop to wait for a human at a gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent   # where the .claude/ sources live
OUTPUT_ROOT = KIT_ROOT                              # overridden by --root
RULES_PATH = Path(__file__).resolve().parent / "gen-pi.rules.json"
# Committed single source of truth for the Pi model / thinking level of every
# ported agent. Read by this generator so the declared frontmatter fallback and
# the runtime profile store (.pi/subagents.json) can never disagree.
AGENT_MODELS_PATH = Path(__file__).resolve().parent / "agent-models.json"


class GeneratorError(Exception):
    """Fatal error that should abort the run with a clear message."""


# --------------------------------------------------------------------------
# Rules loading
# --------------------------------------------------------------------------


def load_rules() -> dict:
    if not RULES_PATH.is_file():
        raise GeneratorError(f"rules file not found: {RULES_PATH}")
    with RULES_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# Frontmatter / body split
# --------------------------------------------------------------------------


def split_frontmatter(text: str, source_path: Path) -> tuple[dict, str]:
    """Split a Claude markdown file into (frontmatter dict, body str).

    Frontmatter is a flat `key: value` block between two `---` lines -- no
    PyYAML needed, no nesting in any of the source files.
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


def load_agent_models() -> dict:
    """Read scripts/agent-models.json and validate it against the ported agents."""
    if not AGENT_MODELS_PATH.is_file():
        raise GeneratorError(f"missing agent-model source of truth: {AGENT_MODELS_PATH}")
    try:
        data = json.loads(AGENT_MODELS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GeneratorError(f"{AGENT_MODELS_PATH}: invalid JSON: {exc}") from exc

    tiers = data.get("tiers")
    agents = data.get("agents")
    if not isinstance(tiers, dict) or not tiers:
        raise GeneratorError(f"{AGENT_MODELS_PATH}: 'tiers' must be a non-empty object")
    if not isinstance(agents, dict) or not agents:
        raise GeneratorError(f"{AGENT_MODELS_PATH}: 'agents' must be a non-empty object")

    allow_claude = bool(data.get("allow_claude_bridge"))
    for tier_name, tier in tiers.items():
        for field in ("model", "thinking"):
            if not tier.get(field):
                raise GeneratorError(
                    f"{AGENT_MODELS_PATH}: tier '{tier_name}' missing '{field}'"
                )
        # `claude-bridge/*` is a bridge to the Claude Agent SDK: an external
        # Claude dependency, which this framework must not acquire by default.
        # Refusing here (rather than silently writing it) keeps the port honest;
        # an operator who really wants it must flip `allow_claude_bridge`.
        if tier["model"].startswith("claude-bridge/") and not allow_claude:
            raise GeneratorError(
                f"{AGENT_MODELS_PATH}: tier '{tier_name}' points at "
                f"'{tier['model']}', a Claude-bridge model. Set "
                "'allow_claude_bridge': true deliberately, or use a Pi-native "
                "model id from `pi --list-models`."
            )
    for agent_name, tier_name in agents.items():
        if tier_name not in tiers:
            raise GeneratorError(
                f"{AGENT_MODELS_PATH}: agent '{agent_name}' references unknown tier "
                f"'{tier_name}' (declared tiers: {sorted(tiers)})"
            )
    return data


def resolve_agent_model(agent_name: str, models: dict, source_path: Path) -> tuple[str, str]:
    """Return (model, thinking) for one ported agent, from the committed SSOT."""
    tier_name = models["agents"].get(agent_name)
    if tier_name is None:
        raise GeneratorError(
            f"{source_path}: agent '{agent_name}' has no tier in "
            f"{AGENT_MODELS_PATH} -- add it so the port never falls back to a "
            "hardcoded model"
        )
    tier = models["tiers"][tier_name]
    return tier["model"], tier["thinking"]


def map_agent_frontmatter(fm: dict, source_path: Path, rules: dict, models: dict) -> dict:
    out: dict = {}

    if "name" not in fm:
        raise GeneratorError(f"{source_path}: agent frontmatter missing 'name'")
    if "description" not in fm:
        raise GeneratorError(f"{source_path}: agent frontmatter missing 'description'")
    # Pi keeps `name`: it is the subagent id `subagent_run` dispatches by.
    out["name"] = fm["name"]
    out["description"] = fm["description"]

    # The Claude source declares a TIER (`sonnet`/`opus`), which is what Claude
    # Code resolves natively. The Pi port must not inherit that name, because
    # `claude-bridge/*` is an external Claude dependency. Resolution is
    # therefore per AGENT, from the committed agent-models.json, reconciled
    # against the operator's active gentle profile at /propuesta-init.
    if not fm.get("model"):
        raise GeneratorError(f"{source_path}: agent frontmatter missing 'model'")
    out["model"], out["thinking"] = resolve_agent_model(
        out["name"], models, source_path
    )

    tools_map = rules["tools_map"]
    claude_tools = fm.get("tools")
    lookup_key = claude_tools if claude_tools else "__no_tools_field__"
    if lookup_key not in tools_map:
        raise GeneratorError(
            f"{source_path}: tools value {claude_tools!r} has no entry in "
            "rules.json tools_map -- refusing to guess a tool set (never "
            "narrow beyond the Claude original)"
        )
    tools = tools_map[lookup_key]
    if tools is not None:
        out["tools"] = tools
    # tools is None => omit the key entirely, so the ported agent keeps Pi's
    # default tool set, mirroring a Claude agent with no `tools:` field.
    return out


def map_command_frontmatter(fm: dict, source_path: Path, rules: dict) -> dict:
    out: dict = {}
    if "description" not in fm:
        raise GeneratorError(f"{source_path}: command frontmatter missing 'description'")
    out["description"] = fm["description"]
    # Pi supports argument-hint on prompt templates, so it is preserved when
    # the source declares one.
    if "argument-hint" in fm:
        out["argument-hint"] = fm["argument-hint"]
    return out


def map_skill_frontmatter(fm: dict, source_path: Path, rules: dict) -> dict:
    """Map a Claude skill's frontmatter to Pi's Agent Skills subset.

    Pi requires `name` + `description`; the remaining allowed keys are copied
    only when present (`license`, `compatibility`, `metadata`, `allowed-tools`,
    `disable-model-invocation`). Unknown keys are dropped rather than guessed.
    """
    if "name" not in fm:
        raise GeneratorError(f"{source_path}: skill frontmatter missing 'name'")
    if "description" not in fm:
        raise GeneratorError(f"{source_path}: skill frontmatter missing 'description'")
    out: dict = {}
    for key in rules["frontmatter"]["skill_key_order"]:
        if key in fm:
            out[key] = fm[key]
    return out


def render_frontmatter(fm: dict, key_order: list[str]) -> str:
    lines = ["---"]
    for key in key_order:
        if key not in fm:
            continue
        lines.append(f"{key}: {fm[key]}")
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
                    "-- add a rule to gen-pi.rules.json or fix source."
                )
    return messages


# --------------------------------------------------------------------------
# Non-mutating write helper
# --------------------------------------------------------------------------


def write_output(
    relpath: str, text: str, output_roots: tuple[str, ...], check: bool
) -> bool:
    """Write `text` to `<repo_root>/relpath`, hard-asserting relpath is under
    one of `output_roots`. Returns True when the file content changed.

    In --check mode, does not write; only reports whether it would change.
    """
    if not any(relpath.startswith(root) for root in output_roots):
        raise GeneratorError(
            f"refusing to write outside allowed output roots {output_roots}: {relpath}"
        )
    if relpath.startswith(".claude/") or "/.claude/" in relpath:
        raise GeneratorError(f"refusing to write under .claude/: {relpath}")

    dest = OUTPUT_ROOT / relpath
    previous = dest.read_text(encoding="utf-8") if dest.is_file() else None
    changed = previous != text

    if not check and changed:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")

    return changed


# --------------------------------------------------------------------------
# Per-file pipeline (BUILD phase -- pure, no filesystem writes)
# --------------------------------------------------------------------------


def build_agent(filename: str, rules: dict, models: dict) -> tuple[str, str]:
    """Return (output_relpath, output_text) for one agent. No writes."""
    paths = rules["paths"]
    source_path = KIT_ROOT / paths["source_agents_dir"] / filename
    if not source_path.is_file():
        raise GeneratorError(f"source agent missing: {source_path}")

    text = source_path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text, source_path)
    out_fm = map_agent_frontmatter(fm, source_path, rules, models)
    out_body = apply_substitutions(body, filename, rules)

    rendered_fm = render_frontmatter(out_fm, rules["frontmatter"]["agent_key_order"])
    return f"{paths['output_agents_dir']}/{filename}", rendered_fm + out_body


def build_subagents_json(rules: dict, models: dict) -> tuple[str, str]:
    """Return (.pi/subagents.json, text) built from the same SSOT as the agents.

    `.pi/subagents.json` is Pi's PROJECT-scope subagent profile store; the
    resolver in pi-subagents reads `<cwd>/.pi/subagents.json` and gives a
    project profile precedence over the agent's own `model:` frontmatter. That
    precedence is why this file must exist and be versioned: without it, a
    fresh clone falls back to whatever the agent file declares, and before this
    generator existed that fallback was `claude-bridge/*`.

    Emitting both from one source means the declared fallback and the effective
    profile cannot drift apart.
    """
    runtime = models.get("runtime", {})
    profiles = {}
    for agent_name, tier_name in sorted(models["agents"].items()):
        tier = models["tiers"][tier_name]
        profiles[agent_name] = {"model": tier["model"], "effort": tier["thinking"]}

    # `default_model` is the tier used by any agent this project did not
    # enumerate; the reasoning tier is the safe default for unlisted work.
    default_tier = models["tiers"]["reasoning"]
    payload = {
        "_generated_by": "scripts/gen-pi.py",
        "_source_of_truth": "scripts/agent-models.json",
        "_reconciled_against": models.get("reconciled_against", {}),
        "default_model": default_tier["model"],
        "default_effort": default_tier["thinking"],
        "default_mode": runtime.get("default_mode", "task"),
        "stall_timeout_ms": runtime.get("stall_timeout_ms", 600000),
        "model_profiles": profiles,
    }
    return ".pi/subagents.json", json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def build_command(filename: str, rules: dict) -> tuple[str, str]:
    """Return (output_relpath, output_text) for one command. No writes."""
    paths = rules["paths"]
    source_path = KIT_ROOT / paths["source_commands_dir"] / filename
    if not source_path.is_file():
        raise GeneratorError(f"source command missing: {source_path}")

    text = source_path.read_text(encoding="utf-8")

    # Reference fragments (e.g. `_propuesta-steps.md`) are not slash commands and
    # carry no frontmatter: they are shared step tables the real commands point
    # at. Copy them through with substitutions applied and no frontmatter
    # synthesised, so Pi sees the same fragment the Claude sources reference.
    if not text.startswith("---\n"):
        out_body = apply_substitutions(text, filename, rules)
        return f"{paths['output_commands_dir']}/{filename}", out_body

    fm, body = split_frontmatter(text, source_path)
    out_fm = map_command_frontmatter(fm, source_path, rules)
    out_body = apply_substitutions(body, filename, rules)

    rendered_fm = render_frontmatter(out_fm, rules["frontmatter"]["command_key_order"])
    return f"{paths['output_commands_dir']}/{filename}", rendered_fm + out_body


def build_skill(relpath: str, rules: dict) -> tuple[str, str]:
    """Return (output_relpath, output_text) for one skill. No writes.

    `relpath` is skill-dir-relative (e.g. `estilo-natural-es/SKILL.md`), so the
    Pi port mirrors the nested source layout under .pi/skills/.
    """
    paths = rules["paths"]
    source_path = KIT_ROOT / paths["source_skills_dir"] / relpath
    if not source_path.is_file():
        raise GeneratorError(f"source skill missing: {source_path}")

    text = source_path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text, source_path)
    out_fm = map_skill_frontmatter(fm, source_path, rules)
    out_body = apply_substitutions(body, relpath, rules)

    rendered_fm = render_frontmatter(out_fm, rules["frontmatter"]["skill_key_order"])
    return f"{paths['output_skills_dir']}/{relpath}", rendered_fm + out_body


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    global OUTPUT_ROOT
    check = False
    args = argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--check":
            check = True
        elif arg == "--root":
            if i + 1 >= len(args):
                print("error: --root requires a directory", file=sys.stderr)
                return 1
            OUTPUT_ROOT = Path(args[i + 1]).resolve()
            i += 1
        elif arg.startswith("--root="):
            OUTPUT_ROOT = Path(arg.split("=", 1)[1]).resolve()
        else:
            print(f"usage: {argv[0]} [--check] [--root DIR]", file=sys.stderr)
            return 1
        i += 1

    try:
        rules = load_rules()
        models = load_agent_models()
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    paths = rules["paths"]
    excluded = set(paths.get("excluded_agents", []))

    # BUILD phase: compute every output file's text in memory first. No writes
    # happen here, so a drift hit on file N never leaves files 1..N-1 written
    # to disk -- drift-lint covers the WHOLE output set before any write.
    built: list[tuple[str, str]] = []
    try:
        for filename in paths["agent_files"]:
            if filename in excluded:
                continue
            built.append(build_agent(filename, rules, models))
        for filename in paths["command_files"]:
            built.append(build_command(filename, rules))
        for relpath in paths.get("skill_files", []):
            built.append(build_skill(relpath, rules))
        built.append(build_subagents_json(rules, models))
    except GeneratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # DRIFT-LINT phase: scan every built output before writing anything.
    all_drift: list[str] = []
    for output_relpath, output_text in built:
        all_drift.extend(drift_lint(output_text, output_relpath, rules["drift_patterns"]))

    if all_drift:
        for msg in all_drift:
            print(msg, file=sys.stderr)
        return 3

    # WRITE phase: only reached when the entire output set is drift-free.
    allowed_roots = (
        ".pi/",
        paths["output_agents_dir"],
        paths["output_commands_dir"],
        paths["output_skills_dir"],
    )
    try:
        for output_relpath, output_text in built:
            changed = write_output(output_relpath, output_text, allowed_roots, check)
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
