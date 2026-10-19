#!/usr/bin/env python3
"""Check that every framework agent runs on a reachable model from the ACTIVE profile.

Why this exists
---------------
Three model tables have to agree, and nothing used to check that they did:

  * `scripts/agent-models.json` — the framework's source of truth (committed);
  * `.pi/agents/*.md` frontmatter + `.pi/subagents.json` — what Pi actually
    resolves at dispatch time (generated from the file above);
  * `~/.pi/gentle-ai/profiles.json` — the operator's ACTIVE `gentle:profiles`
    profile, which governs the rest of their environment.

They did disagree: the port pinned all 10 agents to `claude-bridge/*`, a bridge
to the Claude Agent SDK, while the active profile was Pi-native. `/propuesta-init`
now runs this check so the divergence is caught at session start instead of
mid-pipeline, where it shows up as a subagent returning no report after minutes.

What it verifies
----------------
1. Every ported agent has a tier in the source of truth (no silent fallback).
2. `frontmatter` == `subagents.json` == source of truth, per agent.
3. Every model id is **reachable** according to `pi --list-models` (skipped, not
   assumed, when the Pi CLI is unavailable).
4. No bridge model unless `allow_claude_bridge` is set deliberately.
5. The provider family the framework uses is one the ACTIVE profile also uses,
   so a project cannot quietly run on a provider the operator has stopped using.

Usage
-----
    check-agent-models.py [--project DIR] [--profiles PATH] [--json]

Exit codes: 0 all checks pass; 1 mismatches; 2 could not read an input.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

DEFAULT_PROFILES = pathlib.Path("~/.pi/gentle-ai/profiles.json").expanduser()
BRIDGE_PREFIX = "claude-bridge/"


def load_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: {path} no es JSON válido: {exc}") from exc


def frontmatter_model(agent_file: pathlib.Path) -> tuple[str | None, str | None]:
    """Return (model, thinking) from an agent file's YAML frontmatter."""
    model = thinking = None
    for line in agent_file.read_text(encoding="utf-8").splitlines()[1:40]:
        if line.strip() == "---":
            break
        if line.startswith("model:"):
            model = line.split(":", 1)[1].strip()
        elif line.startswith("thinking:"):
            thinking = line.split(":", 1)[1].strip()
    return model, thinking


def reachable_models() -> set[str] | None:
    """Model ids `pi --list-models` reports, or None when unavailable."""
    if not shutil.which("pi"):
        return None
    try:
        proc = subprocess.run(
            ["pi", "--list-models"], capture_output=True, text=True, timeout=120
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0:
        return None
    found: set[str] = set()
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and not parts[0].startswith("-"):
            found.add(f"{parts[0]}/{parts[1]}")
    return found or None


def provider_of(model: str) -> str:
    return model.split("/", 1)[0] if "/" in model else model


def check(project: pathlib.Path, profiles_path: pathlib.Path) -> dict:
    problems: list[str] = []
    notes: list[str] = []

    source = load_json(project / "scripts" / "agent-models.json")
    if source is None:
        raise SystemExit("error: falta scripts/agent-models.json (fuente de verdad)")

    project_profiles = load_json(project / ".pi" / "subagents.json")
    if project_profiles is None:
        problems.append(
            ".pi/subagents.json no existe o no es JSON: sin él Pi cae al frontmatter "
            "del agente y se pierde la política de modelos"
        )
        project_profiles = {"model_profiles": {}}

    tiers = source.get("tiers", {})
    agents = source.get("agents", {})
    allow_bridge = bool(source.get("allow_claude_bridge"))
    if not tiers or not agents:
        raise SystemExit("error: agent-models.json sin 'tiers' o sin 'agents'")

    # --- 1 + 2: source of truth vs. the two generated outputs ---------------
    agent_dir = project / ".pi" / "agents"
    ported = {p.stem for p in agent_dir.glob("*.md")} if agent_dir.is_dir() else set()
    if not ported:
        problems.append(f"no hay agentes portados en {agent_dir}")

    for agent, tier_name in sorted(agents.items()):
        if tier_name not in tiers:
            problems.append(f"{agent}: tier '{tier_name}' no existe en 'tiers'")
            continue
        tier = tiers[tier_name]
        model, thinking = tier["model"], tier["thinking"]

        profile = (project_profiles.get("model_profiles") or {}).get(agent)
        if not profile:
            problems.append(f"{agent}: sin perfil en .pi/subagents.json")
        elif profile.get("model") != model or profile.get("effort") != thinking:
            problems.append(
                f"{agent}: .pi/subagents.json dice "
                f"{profile.get('model')}@{profile.get('effort')} y la fuente de verdad "
                f"dice {model}@{thinking}"
            )

        if agent in ported:
            fm_model, fm_thinking = frontmatter_model(agent_dir / f"{agent}.md")
            if fm_model != model or fm_thinking != thinking:
                problems.append(
                    f"{agent}: el frontmatter dice {fm_model}@{fm_thinking} y la fuente "
                    f"de verdad dice {model}@{thinking}"
                )
        else:
            problems.append(f"{agent}: declarado en la fuente de verdad pero no portado")

    for agent in sorted(ported - set(agents)):
        problems.append(f"{agent}: portado pero sin tier en la fuente de verdad")

    # --- 3: reachability ---------------------------------------------------
    reachable = reachable_models()
    if reachable is None:
        notes.append(
            "no se pudo consultar 'pi --list-models'; la alcanzabilidad NO se verificó "
            "(no se asume accesible)"
        )
    else:
        for tier_name, tier in sorted(tiers.items()):
            if tier["model"] not in reachable:
                problems.append(
                    f"tier '{tier_name}': '{tier['model']}' no aparece en "
                    "`pi --list-models`"
                )

    # --- 4: bridge guard ---------------------------------------------------
    for tier_name, tier in sorted(tiers.items()):
        if tier["model"].startswith(BRIDGE_PREFIX) and not allow_bridge:
            problems.append(
                f"tier '{tier_name}': '{tier['model']}' es un puente a otro agente de "
                "código y allow_claude_bridge está en false"
            )

    # --- 5: provider family vs. the ACTIVE gentle profile ------------------
    active_name = None
    profile_providers: set[str] = set()
    orchestrator = None
    if not profiles_path.is_file():
        notes.append(
            f"no existe el almacén de perfiles {profiles_path}; no se pudo contrastar "
            "contra el perfil activo"
        )
    else:
        store = load_json(profiles_path) or {}
        active_name = store.get("active")
        profiles = store.get("profiles") or {}
        if not active_name:
            problems.append("el almacén de perfiles no declara 'active'")
        elif active_name not in profiles:
            problems.append(f"perfil activo '{active_name}' no existe en el almacén")
        else:
            entries = profiles[active_name]
            orchestrator = (entries.get("orchestrator") or {}).get("model")
            profile_providers = {
                provider_of(cfg["model"])
                for key, cfg in entries.items()
                if key != "orchestrator" and isinstance(cfg, dict) and cfg.get("model")
            }
            framework_providers = {provider_of(t["model"]) for t in tiers.values()}
            unknown = sorted(framework_providers - profile_providers)
            if unknown:
                problems.append(
                    f"el marco usaría el proveedor {unknown}, que el perfil activo "
                    f"'{active_name}' no usa (usa {sorted(profile_providers)})"
                )

    return {
        "verdict": "PASS" if not problems else "FAIL",
        "source_of_truth": "scripts/agent-models.json",
        "active_gentle_profile": active_name,
        "orchestrator_model": orchestrator,
        "framework_providers": sorted({provider_of(t["model"]) for t in tiers.values()}),
        "active_profile_providers": sorted(profile_providers),
        "reachability_checked": reachable is not None,
        "notes": notes,
        "problems": problems,
        "agents": {
            agent: f"{tiers[tier]['model']}@{tiers[tier]['thinking']}"
            for agent, tier in sorted(agents.items())
            if tier in tiers
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", type=pathlib.Path, default=pathlib.Path.cwd())
    ap.add_argument("--profiles", type=pathlib.Path, default=DEFAULT_PROFILES)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = check(args.project.resolve(), args.profiles.expanduser())

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"MODELOS {report['verdict']}")
        print(f"  fuente de verdad   : {report['source_of_truth']}")
        print(f"  perfil gentle activo: {report['active_gentle_profile']}")
        print(f"  orquestador         : {report['orchestrator_model']}")
        print(
            f"  proveedores         : marco={report['framework_providers']} "
            f"perfil={report['active_profile_providers']}"
        )
        print(
            "  alcanzabilidad      : "
            + ("verificada con `pi --list-models`" if report["reachability_checked"]
               else "NO verificada")
        )
        print("  agentes:")
        for agent, model in report["agents"].items():
            print(f"    {agent:24s} {model}")
        for note in report["notes"]:
            print(f"  [nota] {note}")
        for problem in report["problems"]:
            print(f"  [FALLA] {problem}")
        if report["verdict"] == "FAIL":
            print(
                "  -> corrige scripts/agent-models.json y corre "
                "`python3 scripts/gen-pi.py`"
            )

    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
