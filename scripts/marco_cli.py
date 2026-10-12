#!/usr/bin/env python3
"""
marco — Portable project CLI for the marco-propuestas-ia framework.

Kit manifest format note:
This CLI uses JSON (scripts/kit-manifest.json) instead of YAML to keep the
script stdlib-only. The design's open question about YAML vs JSON is resolved
in favor of JSON for zero-dependency operation.

Commands:
  marco init <dir>     — Create a portable project folder with the full agent kit
  marco upgrade <dir>  — Refresh kit files from the monorepo (preserves operator content)
  marco status <dir>   — Print project state snapshot

Environment:
  MARCO_KIT_ROOT       Override kit source root (default: parent of scripts/ directory)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path


# ---------------------------------------------------------------------------
# Model presets
# ---------------------------------------------------------------------------

_MODEL_PRESETS: dict[str, dict[str, str]] = {
    "claude": {
        "investigador": "opus",
        "redactor": "opus",
        "bibliografo-propuesta": "sonnet",
        "revisor": "sonnet",
        "presupuestador": "sonnet",
        "insumos-observador": "sonnet",
        "disenador-tikz": "sonnet",
        "tikz-optimizer": "sonnet",
        "revisor-figuras": "sonnet",
        "coordinador-propuesta": "sonnet",
    },
    "gpt": {
        "investigador": "gpt-5.6-sol",
        "redactor": "gpt-5.6-sol",
        "bibliografo-propuesta": "gpt-5.6-terra",
        "revisor": "gpt-5.6-terra",
        "presupuestador": "gpt-5.6-terra",
        "insumos-observador": "gpt-5.6-terra",
        "disenador-tikz": "gpt-5.6-terra",
        "tikz-optimizer": "gpt-5.6-terra",
        "revisor-figuras": "gpt-5.6-terra",
        "coordinador-propuesta": "gpt-5.6-terra",
    },
    "opencode-go": {
        "investigador": "opencode-go/glm-5.2",
        "redactor": "opencode-go/glm-5.2",
        "bibliografo-propuesta": "opencode-go/glm-5.2",
        "revisor": "opencode-go/glm-5.2",
        "presupuestador": "opencode-go/glm-5.2",
        "insumos-observador": "opencode-go/glm-5.2",
        "disenador-tikz": "opencode-go/glm-5.2",
        "tikz-optimizer": "opencode-go/glm-5.2",
        "revisor-figuras": "opencode-go/glm-5.2",
        "coordinador-propuesta": "opencode-go/glm-5.2",
    },
}

_VALID_PRESETS = frozenset(_MODEL_PRESETS.keys())

# ---------------------------------------------------------------------------
# Translations (operator-facing scaffolding templates)
# ---------------------------------------------------------------------------

_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "es": {
        "idea": {
            "title": "Idea de propuesta",
            "problem": "Problema",
            "approach": "Enfoque",
            "beneficiaries": "Beneficiarios",
            "constraints": "Restricciones / Alineación",
            "questions": "Preguntas abiertas",
        },
        "decisions": {
            "title": "Decisiones del proyecto",
            "decisions": "Decisiones",
            "user_clarifications": "Aclaraciones del usuario",
            "do_dont": "Hacer / No hacer",
            "open_questions": "Preguntas abiertas",
        },
    },
    "en": {
        "idea": {
            "title": "Proposal idea",
            "problem": "Problem",
            "approach": "Approach",
            "beneficiaries": "Beneficiaries",
            "constraints": "Constraints / Alignment",
            "questions": "Open questions",
        },
        "decisions": {
            "title": "Project decisions",
            "decisions": "Decisions",
            "user_clarifications": "User clarifications",
            "do_dont": "Do / Don't",
            "open_questions": "Open questions",
        },
    },
}


def _idea_template(lang: str) -> str:
    t = _TRANSLATIONS.get(lang, _TRANSLATIONS["es"])["idea"]
    return f"""# {t['title']}

## {t['problem']}
<!-- Describe el problema u oportunidad que aborda la propuesta -->

## {t['approach']}
<!-- Describe el enfoque de solución propuesto (método, tecnología, innovación) -->

## {t['beneficiaries']}
<!-- ¿Quiénes se benefician directa e indirectamente? -->

## {t['constraints']}
<!-- Restricciones técnicas, presupuestales, de tiempo; alineación con convocatoria -->

## {t['questions']}
<!-- Lista de preguntas que necesitan respuesta antes de iniciar el pipeline -->
"""


def _decisions_template(lang: str) -> str:
    t = _TRANSLATIONS.get(lang, _TRANSLATIONS["es"])["decisions"]
    return f"""# {t['title']}

## {t['decisions']}
<!-- Registro de decisiones tomadas: fecha, decisión, responsable, justificación -->

## {t['user_clarifications']}
<!-- Puntos donde el operador aclaró requisitos o alcance -->

## {t['do_dont']}
<!-- Lista de lo que está dentro y fuera del alcance -->

## {t['open_questions']}
<!-- Preguntas pendientes que requieren respuesta del operador o del equipo -->
"""


def _journal_readme(lang: str) -> str:
    if lang == "en":
        return _JOURNAL_README_EN
    return _JOURNAL_README_ES


_JOURNAL_README_ES = """# Journal — Bitácora de eventos

Este directorio contiene un registro **append-only** de eventos materiales del
proyecto. Cada archivo sigue la convención:

    YYYYMMDD-HHMM-<evento>.md

Ejemplos:
- `20260719-1030-gate-PASS.md` — Gate de revisión aprobado
- `20260719-1430-scope-change.md` — Cambio de alcance aprobado
- `20260719-1600-budget-override.md` — Sobrescritura de presupuesto

Cada entrada debe incluir:
- Fecha y hora del evento
- Descripción del evento
- Decisión tomada (si aplica)
- Próximos pasos

**No edites ni elimines entradas existentes.** Este diario es la fuente de
verdad del historial del proyecto.
"""

_JOURNAL_README_EN = """# Journal — Event log

This directory contains an **append-only** record of material project events.
Each file follows the convention:

    YYYYMMDD-HHMM-<event>.md

Examples:
- `20260719-1030-gate-PASS.md` — Gate review approved
- `20260719-1430-scope-change.md` — Scope change approved
- `20260719-1600-budget-override.md` — Budget override

Each entry MUST include:
- Event date and time
- Event description
- Decision made (if applicable)
- Next steps

**Do not edit or delete existing entries.** This journal is the source of
truth for the project history.
"""


def _project_readme(
    title: str | None,
    tools: set[str],
    lang: str = "es",
    preset_name: str = "claude",
) -> str:
    lines = [
        "# Portable marco project",
        "",
        "This folder is a **self-contained portable marco project** — a complete",
        "research-proposal writing environment.",
        "",
        f"**Kit version:** {{kit_version}}",
        f"**Configuration:** language={lang}, model_preset={preset_name}",
        f"                  (.marco/config.json)",
    ]
    if title:
        lines.append(f"**Title:** {title}")
    lines.extend([
        "",
        "## Getting started",
        "",
        "1. Open your runtime (Claude Code / OpenCode / pi) with CWD set to this folder.",
        "2. Use slash commands to work the pipeline:",
        "",
        "   | Command | Purpose |",
        "   |---------|---------|",
        "   | `/propuesta-init <idea>` | Create and activate a run: proposals/<run-id>/ |",
        "   | `/propuesta-insumos` | Drop zones inside the run's insumos/ (tdr, draft, ...) |",
        "   | `/propuesta-analizar [idea]` | Start intake (idea from arg or insumos/ideas/) |",
        "   | `/propuesta-continuar` | Next pipeline step |",
        "   | `/propuesta` | Full pipeline in one session |",
        "   | `/propuesta-limpiar` | Close the active run |",
        "",
        "## Structure",
        "",
        "```",
        ".marco/              # Marker + manifest + config (version, checksums, config.json)",
        ".claude/             # Agent kit (commands + agents for Claude Code)",
    ])
    if "opencode" in tools:
        lines.append(".opencode/           # Generated OpenCode surface")
    if "pi" in tools:
        lines.append(".pi/                 # Generated pi surface")
    if "antigravity" in tools:
        lines.append(".agent/              # Generated Google Antigravity skills & workflows")
    lines.extend([
        "plantilla/           # Versioned LaTeX skeleton, copied into each run's redaccion/",
        "scripts/init-run.sh  # Creates proposals/<run-id>/ (insumos artefactos grafos redaccion)",
        "proposals/           # One folder per run + local registry (never versioned)",
        "idea.md              # Scratch note for your research idea (optional)",
        "DECISIONS.md         # Live decision log",
        "journal/             # Append-only event journal",
        "README.md            # This file",
        "```",
        "",
        "## Commands",
        "",
        "- `marco status .` — show project state (estado, last decision, last journal entry)",
        "- `marco upgrade .` — refresh kit files from the marco monorepo (preserves operator content)",
        "",
        "## Notes",
        "",
        "- All paths are relative; you can copy this folder anywhere and it will work.",
        "- `.mcp.json` is copied verbatim from the kit — review it for secrets before sharing.",
        "- The whole `proposals/` tree (runs, local registry, pointer), plus",
        "  `DECISIONS.md` and `journal/`, are preserved on upgrade.",
        "- `.marco/config.json` records language and model preset; it persists across upgrade.",
        "",
    ])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_kit_root() -> Path:
    """Return kit root: MARCO_KIT_ROOT env override, else the repo root
    (parent of the directory containing this script)."""
    env = os.environ.get("MARCO_KIT_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent


def load_kit_manifest() -> dict:
    """Load kit-manifest.json from scripts/ directory."""
    manifest_path = Path(__file__).resolve().parent / "kit-manifest.json"
    if not manifest_path.is_file():
        print(f"error: kit manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def matches_preserve(rel_path: str, patterns: list[str]) -> bool:
    """Return True if *rel_path* matches any preserve glob pattern."""
    for pat in patterns:
        if fnmatch(rel_path, pat):
            return True
    return False


def copy_kit_entry(src_root: Path, dst_root: Path, kit_path: str) -> list[dict]:
    """Copy one manifest entry from *src_root* to *dst_root*.
    Returns a list of ``{"path": rel_path, "sha256": hex_digest}`` dicts
    for every file actually copied.
    """
    src = src_root / kit_path
    if not src.exists():
        print(f"  [warn] kit source missing: {kit_path}", file=sys.stderr)
        return []

    installed: list[dict] = []

    if src.is_dir():
        for item in sorted(src.rglob("*")):
            if not item.is_file():
                continue
            rel = item.relative_to(src_root)
            dest = dst_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            installed.append({"path": str(rel), "sha256": compute_sha256(dest)})
    else:
        dest = dst_root / kit_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        installed.append({"path": kit_path, "sha256": compute_sha256(dest)})

    return installed


def load_project_manifest(project_dir: Path) -> dict:
    """Read and return ``.marco/manifest.json`` from *project_dir*."""
    mf = project_dir / ".marco" / "manifest.json"
    if not mf.is_file():
        print(
            f"error: {_rel(project_dir, project_dir / '.marco' / 'manifest.json')} not found",
            file=sys.stderr,
        )
        sys.exit(1)
    with mf.open("r", encoding="utf-8") as f:
        return json.load(f)


def _rel(project_dir: Path, path: Path) -> str:
    """Return *path* as relative to *project_dir* when possible."""
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)


def _run_generator(kit_root: Path, target: Path, script_name: str) -> None:
    """Run a generator (gen-opencode.py or gen-pi.py) against *target*.
    Prints a warning on failure but does not abort.
    """
    script = kit_root / "scripts" / script_name
    if not script.is_file():
        print(f"  [warn] generator not found: {script}", file=sys.stderr)
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(target)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  [warn] {script_name} exited with code {result.returncode}", file=sys.stderr)
            for line in result.stderr.strip().splitlines():
                print(f"    {line}", file=sys.stderr)
        else:
            for line in result.stdout.strip().splitlines():
                print(f"    {line}")
    except subprocess.TimeoutExpired:
        print(f"  [warn] {script_name} timed out after 120s", file=sys.stderr)
    except Exception as exc:
        print(f"  [warn] {script_name} failed: {exc}", file=sys.stderr)


def _prompt_if_tty(prompt: str, options: list[str], default: str) -> str:
    """On a TTY, print a numbered menu and read a line.
    Empty input returns the default option.
    On non-TTY, return the default without reading stdin.
    """
    if not sys.stdin.isatty():
        return default
    print(prompt)
    for i, opt in enumerate(options, start=1):
        marker = " (default)" if opt == default else ""
        print(f"  {i}. {opt}{marker}")
    try:
        line = (input("Enter number (or press Enter for default): ") or "").strip()
    except (EOFError, KeyboardInterrupt):
        return default
    if not line:
        return default
    try:
        idx = int(line)
        if 1 <= idx <= len(options):
            return options[idx - 1]
    except ValueError:
        pass
    # Re-prompt on invalid input
    return _prompt_if_tty("Invalid selection.", options, default)


def _build_config_json(lang: str, preset_name: str, tools: list[str] | set[str] | None = None) -> dict:
    """Return the config dict for .marco/config.json."""
    now = datetime.now(timezone.utc).isoformat()
    cfg = {
        "language": lang,
        "model_preset": preset_name,
        "agent_models": dict(_MODEL_PRESETS[preset_name]),
        "created_at": now,
        "updated_at": now,
    }
    if tools is not None:
        cfg["tools"] = sorted(list(tools))
    return cfg


def _load_project_config(project_dir: Path) -> dict | None:
    """Read .marco/config.json from *project_dir*. Returns None if absent."""
    cfg = project_dir / ".marco" / "config.json"
    if not cfg.is_file():
        return None
    try:
        with cfg.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _apply_config_to_claude_copies(target: Path, config: dict) -> None:
    """Rewrite model: frontmatter in .claude/agents/*.md and AGENTS.md
    rule #1 text to match the project config.  No-op on missing files."""
    agents_dir = target / ".claude" / "agents"
    agent_models = config.get("agent_models", {})
    lang = config.get("language", "es")

    # Rewrite model: line in each agent file
    if agents_dir.is_dir():
        for agent_file in sorted(agents_dir.glob("*.md")):
            name = agent_file.stem
            model = agent_models.get(name)
            if model is None:
                continue
            text = agent_file.read_text(encoding="utf-8")
            lines = text.splitlines(keepends=True)
            rewritten = False
            for i, line in enumerate(lines):
                if line.startswith("model:"):
                    lines[i] = f"model: {model}\n"
                    rewritten = True
                    break
            if rewritten:
                agent_file.write_text("".join(lines), encoding="utf-8")

    # Rewrite AGENTS.md rule #1: replace "español" with the language code
    agents_md = target / "AGENTS.md"
    if agents_md.is_file():
        text = agents_md.read_text(encoding="utf-8")
        # Rule #1 line: "toda la salida del documento (propuesta) debe redactarse en español"
        old = "español"
        new = lang
        if old in text:
            text = text.replace(old, new)
            agents_md.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> None:
    """``marco init <dir> [--title ...] [--tools ...] [--lang ...] [--model-preset ...]``"""
    target = Path(args.dir).resolve()
    kit_root = get_kit_root()
    manifest = load_kit_manifest()

    kit_version: str = manifest["version"]
    drop_zones: list[str] = manifest["drop_zones"]
    vault_subdirs: list[str] = manifest["vault_subdirs"]
    kit_paths: list[str] = manifest["kit_paths"]

    tools = set(args.tools.split(",")) if args.tools else {"claude", "opencode", "pi", "antigravity"}

    # --- Resolve language ---
    if args.lang is not None:
        lang = args.lang
    else:
        lang = _prompt_if_tty(
            "Select proposal language:",
            ["es", "en"],
            "es",
        )

    # --- Resolve model preset ---
    if args.model_preset is not None:
        preset_name = args.model_preset
    else:
        preset_name = _prompt_if_tty(
            "Select model preset:",
            sorted(_VALID_PRESETS),
            "claude",
        )

    # Validate preset (reject BEFORE touching filesystem)
    if preset_name not in _VALID_PRESETS:
        print(
            f"error: unknown model preset '{preset_name}'. "
            f"Valid presets: {', '.join(sorted(_VALID_PRESETS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Create target ---
    target.mkdir(parents=True, exist_ok=True)

    all_installed: list[dict] = []

    # --- Copy kit ---
    for kp in kit_paths:
        all_installed.extend(copy_kit_entry(kit_root, target, kp))

    # --- .marco directory ---
    marco_dir = target / ".marco"
    marco_dir.mkdir(parents=True, exist_ok=True)
    (marco_dir / "version").write_text(kit_version + "\n", encoding="utf-8")

    marco_manifest: dict = {
        "version": kit_version,
        "kit_root": str(kit_root),
        "files": all_installed,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (marco_dir / "manifest.json").write_text(
        json.dumps(marco_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # --- .marco/config.json ---
    config = _build_config_json(lang, preset_name, tools=tools)
    (marco_dir / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # --- No run content at the project root. -----------------------------
    # A portable project has the same run model as the framework repo: the kit
    # ships plantilla/ (LaTeX skeleton) and scripts/init-run.sh, and every run
    # lives in proposals/<run-id>/ with its own insumos/, artefactos/, grafos/
    # and redaccion/. Drop zones belong inside a run's insumos/ (created by
    # /propuesta-insumos), so seeding them at the root would contradict the
    # single rule that all run content resolves inside RUN_ROOT.
    # drop_zones / vault_subdirs stay in the manifest because /propuesta-insumos
    # and the vault mirror consume them per run.
    _ = (drop_zones, vault_subdirs)

    # --- idea.md at the project root (only if missing) -------------------
    # Scratch note the operator can fill before deciding a run-id; it is not
    # run content, so it stays outside proposals/.
    idea_path = target / "idea.md"
    if not idea_path.exists():
        idea_path.write_text(_idea_template(lang), encoding="utf-8")

    # --- DECISIONS.md (only if missing) ---
    decisions_path = target / "DECISIONS.md"
    if not decisions_path.exists():
        decisions_path.write_text(_decisions_template(lang), encoding="utf-8")

    # --- journal/README.md ---
    journal_dir = target / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    (journal_dir / "README.md").write_text(_journal_readme(lang), encoding="utf-8")

    # --- Project README.md ---
    readme_path = target / "README.md"
    readme_text = _project_readme(args.title, tools, lang, preset_name).replace(
        "{kit_version}", kit_version
    )
    readme_path.write_text(readme_text, encoding="utf-8")

    # --- Config re-apply to Claude copies ---
    _apply_config_to_claude_copies(target, config)

    # --- Generators ---
    if "opencode" in tools:
        print("  Generating .opencode/ ...")
        _run_generator(kit_root, target, "gen-opencode.py")
    if "pi" in tools:
        print("  Generating .pi/ ...")
        _run_generator(kit_root, target, "gen-pi.py")
    if "antigravity" in tools:
        print("  Generating .agent/ ...")
        _run_generator(kit_root, target, "gen-antigravity.py")

    # --- Summary ---
    installed_count = len(all_installed)
    print(f"\nmarco init: portable project created at {target}")
    print(f"  Kit version: {kit_version}")
    print(f"  Files installed: {installed_count}")
    print(f"  Tools: {', '.join(sorted(tools))}")
    print(f"  Language: {lang}")
    print(f"  Model preset: {preset_name}")
    print(f"\n  Next: cd {target} && open your runtime (Claude Code / OpenCode / pi)")
    print(f"        with CWD set to this folder and start with /propuesta-init")
    if args.title:
        print(f"  Title: {args.title}")


def cmd_upgrade(args: argparse.Namespace) -> None:
    """``marco upgrade <dir> [--tools TOOLS]``"""
    target = Path(args.dir).resolve()
    kit_root = get_kit_root()
    manifest = load_kit_manifest()

    kit_version: str = manifest["version"]
    kit_paths: list[str] = manifest["kit_paths"]
    preserve_patterns: list[str] = manifest["preserve_paths"]

    # Require existing project
    existing = load_project_manifest(target)
    old_version = existing.get("version", "unknown")

    updated: list[dict] = []

    for kp in kit_paths:
        # Check if any file under this path is preserved
        if matches_preserve(kp, preserve_patterns):
            print(f"  skip (preserved): {kp}")
            continue
        updated.extend(copy_kit_entry(kit_root, target, kp))

    # --- Re-apply config if present (backward compat) ---
    config = _load_project_config(target)

    # Resolve active tools
    if getattr(args, "tools", None):
        tools_set = set(args.tools.split(","))
        if config is None:
            config = _build_config_json("es", "claude", tools=tools_set)
        else:
            config["tools"] = sorted(list(tools_set))
            config["updated_at"] = datetime.now(timezone.utc).isoformat()
        marco_dir = target / ".marco"
        marco_dir.mkdir(parents=True, exist_ok=True)
        (marco_dir / "config.json").write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        active_tools = tools_set
    elif config is not None and "tools" in config:
        active_tools = set(config["tools"])
    else:
        active_tools = {"claude"}
        if (target / ".opencode").is_dir():
            active_tools.add("opencode")
        if (target / ".pi").is_dir():
            active_tools.add("pi")
        if (target / ".agent").is_dir():
            active_tools.add("antigravity")

    if config is not None:
        # Backfill missing agents
        agent_models = config.get("agent_models", {})
        preset_name = config.get("model_preset", "claude")
        preset_models = _MODEL_PRESETS.get(preset_name, _MODEL_PRESETS["claude"])
        agents_dir = target / ".claude" / "agents"
        if agents_dir.is_dir():
            for agent_file in sorted(agents_dir.glob("*.md")):
                name = agent_file.stem
                if name not in agent_models and name in preset_models:
                    agent_models[name] = preset_models[name]
                    print(f"  [warn] added missing agent '{name}' with model '{preset_models[name]}'")
        if agent_models != config.get("agent_models"):
            config["agent_models"] = agent_models
            config["updated_at"] = datetime.now(timezone.utc).isoformat()
            (target / ".marco" / "config.json").write_text(
                json.dumps(config, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        # Apply config to .claude/ copies
        _apply_config_to_claude_copies(target, config)

    # Re-run generators for active tools
    if "opencode" in active_tools:
        print("  Generating .opencode/ ...")
        _run_generator(kit_root, target, "gen-opencode.py")
    if "pi" in active_tools:
        print("  Generating .pi/ ...")
        _run_generator(kit_root, target, "gen-pi.py")
    if "antigravity" in active_tools:
        print("  Generating .agent/ ...")
        _run_generator(kit_root, target, "gen-antigravity.py")

    # Rewrite .marco/version
    (target / ".marco" / "version").write_text(kit_version + "\n", encoding="utf-8")

    # Rewrite .marco/manifest.json
    marco_manifest: dict = {
        "version": kit_version,
        "kit_root": str(kit_root),
        "files": updated,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "previous_version": old_version,
    }
    (target / ".marco" / "manifest.json").write_text(
        json.dumps(marco_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\nmarco upgrade: {target}")
    print(f"  Version: {old_version} -> {kit_version}")
    print(f"  Files updated: {len(updated)}")
    print(f"  Tools: {', '.join(sorted(active_tools))}")
    if config is not None:
        print(f"  Language: {config.get('language', 'es')}")
        print(f"  Model preset: {config.get('model_preset', 'claude')}")


def cmd_status(args: argparse.Namespace) -> None:
    """``marco status <dir>``"""
    target = Path(args.dir).resolve()

    version_file = target / ".marco" / "version"
    if not version_file.is_file():
        print(
            f"warning: {target} is not a portable marco project "
            f"(no .marco/version)",
            file=sys.stderr,
        )
        sys.exit(1)

    kit_version = version_file.read_text(encoding="utf-8").strip()
    print(f"Kit version: {kit_version}")

    # --- Config ---
    config = _load_project_config(target)
    if config is not None:
        print(f"Language: {config.get('language', 'es')}")
        print(f"Model preset: {config.get('model_preset', 'claude')}")

    # --- estado_propuesta.md ---
    run_root = _active_run_root(target)
    estado_path = (
        run_root / "artefactos" / "estado_propuesta.md"
        if run_root is not None
        else target / "proposals" / "__no-active-run__" / "artefactos" / "estado_propuesta.md"
    )
    if estado_path.is_file():
        text = estado_path.read_text(encoding="utf-8")
        ctrl = _parse_control_block(text)
        if ctrl:
            print("\n--- estado_propuesta.md (control block) ---")
            for key in ("mode", "next_step", "next_command", "last_completed", "intake_complete"):
                val = ctrl.get(key)
                if val is not None:
                    print(f"  {key}: {val}")
        else:
            print("\n--- estado_propuesta.md (first 20 lines) ---")
            lines = text.splitlines()
            for line in lines[:20]:
                print(f"  {line}")
    else:
        print("\n  (no artefactos/estado_propuesta.md)")

    # --- DECISIONS.md tail ---
    decisions_path = target / "DECISIONS.md"
    if decisions_path.is_file():
        lines = decisions_path.read_text(encoding="utf-8").splitlines()
        tail = lines[-30:] if len(lines) > 30 else lines
        print("\n--- DECISIONS.md (last 30 lines) ---")
        for line in tail:
            print(f"  {line}")
    else:
        print("\n  (no DECISIONS.md)")

    # --- Journal ---
    journal_dir = target / "journal"
    if journal_dir.is_dir():
        entries = sorted(journal_dir.glob("*.md"))
        # Exclude README.md
        entries = [e for e in entries if e.name != "README.md"]
        if entries:
            latest = entries[-1]
            print(f"\n--- Journal: latest entry ({latest.name}) ---")
            content = latest.read_text(encoding="utf-8")
            lines = content.splitlines()
            for line in lines[:20]:
                print(f"  {line}")
        else:
            print("\n  (no journal entries)")
    else:
        print("\n  (no journal/ directory)")

    # --- Recommended Next Action ---
    print("\n" + "=" * 60)
    print(" 🎯 RECOMENDACIÓN DE PRÓXIMO PASO")
    print("=" * 60)
    if estado_path.is_file():
        text = estado_path.read_text(encoding="utf-8")
        ctrl = _parse_control_block(text)
        if ctrl and ctrl.get("next_step"):
            ns = ctrl.get("next_step")
            cmd = ctrl.get("next_command", "/propuesta-continuar")
            print(f"  Paso actual pendiente: {ns}")
            print(f"  Ejecuta en tu agente:  👉 {cmd}")
        else:
            print("  Ingreso finalizado o listo para iniciar. Ejecuta `/propuesta-analizar` en tu agente.")
    else:
        print("  Sin corrida activa. Ejecuta `/propuesta-init <idea>` en tu agente para crear")
        print("  `proposals/<run-id>/`, y luego `/propuesta-analizar`.")
    print("=" * 60)


def cmd_guide(args: argparse.Namespace) -> None:
    """``marco guide [dir]`` — Interactive onboarding wizard for proposal creation."""
    target = Path(args.dir if args.dir else ".").resolve()
    version_file = target / ".marco" / "version"
    if not version_file.is_file():
        print(f"warning: {target} is not a portable marco project (no .marco/version)", file=sys.stderr)
        print("Tip: Run `marco init <dir>` first to create a portable project.", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print(" 🚀 MARCO DE PROPUESTAS DE IA — GUÍA DE INICIO Y FLUJO")
    print("=" * 60)
    print(f"\nProyecto activo: {target}")

    run_root = _active_run_root(target)
    if run_root is None:
        print("\nSin corrida activa todavía.")
        print("  1) Edita `idea.md` con tu problema y enfoque de solución (opcional).")
        print("  2) En tu agente: 👉 `/propuesta-init <idea>`  (crea proposals/<run-id>/)")
        print("  3) Luego:        👉 `/propuesta-insumos`      (zonas de depósito)")
        print("\n" + "=" * 60)
        return

    print(f"Corrida activa: {run_root.name}")
    idea_file = run_root / "insumos" / "ideas" / "idea.md"
    tdr_dir = run_root / "insumos" / "tdr"
    draft_dir = run_root / "insumos" / "draft"

    tdr_files = [f for f in tdr_dir.glob("*") if f.name != ".gitkeep"] if tdr_dir.is_dir() else []
    draft_files = [f for f in draft_dir.glob("*") if f.name != ".gitkeep"] if draft_dir.is_dir() else []

    has_idea = idea_file.is_file() and len(idea_file.read_text(encoding="utf-8").strip()) > 100

    print("\n1. Estado de Insumos (Drop Zones):")
    print(f"   - Idea de Investigación: {'✅ Lista (insumos/ideas/idea.md)' if has_idea else '⚠️  Pendiente (editar insumos/ideas/idea.md)'}")
    print(f"   - Convocatoria / TDR:    {'✅ ' + str(len(tdr_files)) + ' archivo(s) en insumos/tdr/' if tdr_files else 'ℹ️  Opcional (insumos/tdr/)'}")
    print(f"   - Borrador previo:       {'✅ ' + str(len(draft_files)) + ' archivo(s) en insumos/draft/' if draft_files else 'ℹ️  Opcional (insumos/draft/)'}")

    print("\n2. Pasos recomendados para iniciar la propuesta:")
    print("   a) Abre tu agente de IA (Claude Code, Google Antigravity, OpenCode, o pi) en esta carpeta.")
    if not has_idea:
        print("   b) Edita `insumos/ideas/idea.md` de la corrida con tu problema y enfoque.")
    print("   c) Ejecuta el comando de inicio en tu agente:")
    print("      👉 `/propuesta-analizar` (inicia el análisis de insumos e idea)")
    print("   d) Avanza paso a paso ejecutando:")
    print("      👉 `/propuesta-continuar` (ejecuta la siguiente fase del pipeline)")
    print("   e) O ejecuta la sesión completa en un solo comando:")
    print("      👉 `/propuesta` (pipeline interactivo completo)")
    print("\n" + "=" * 60)


def _active_run_root(project_dir: Path) -> Path | None:
    """Return the active run folder of *project_dir*, or None if there is none.

    Mirrors scripts/init-run.sh: the active run-id lives in
    ``proposals/.current-run`` and its folder is ``proposals/<run-id>/``. Run
    content is never at the project root, so every status/guide lookup goes
    through here instead of hardcoding a path.
    """
    pointer = project_dir / "proposals" / ".current-run"
    if not pointer.is_file():
        return None
    run_id = pointer.read_text(encoding="utf-8").strip()
    if not run_id:
        return None
    run_root = project_dir / "proposals" / run_id
    return run_root if run_root.is_dir() else None


def _parse_control_block(text: str) -> dict | None:
    """Best-effort parse YAML-ish frontmatter from estado_propuesta.md.
    Returns a dict of fields, or None if no frontmatter found.
    """
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    block = text[4:end]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields if fields else None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="marco",
        description="Portable project CLI for the marco-propuestas-ia framework",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List built-in model presets with per-agent lineups and exit",
    )
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Create a portable project folder")
    p_init.add_argument("dir", help="Target directory path")
    p_init.add_argument("--title", default=None, help="Optional proposal title")
    p_init.add_argument(
        "--tools",
        default="claude,opencode,pi,antigravity",
        help="Comma-separated list of runtimes to scaffold (default: claude,opencode,pi,antigravity)",
    )
    p_init.add_argument(
        "--lang",
        default=None,
        help="Proposal language BCP-47 code (default: es). "
        "Prompts interactively on TTY when omitted.",
    )
    p_init.add_argument(
        "--model-preset",
        default=None,
        help="Model preset name (default: claude). "
        f"Valid: {', '.join(sorted(_VALID_PRESETS))}. "
        "Prompts interactively on TTY when omitted.",
    )

    # upgrade
    p_upg = sub.add_parser("upgrade", help="Refresh kit files in an existing project")
    p_upg.add_argument("dir", nargs="?", default=".", help="Portable project directory (default: current directory)")
    p_upg.add_argument(
        "--tools",
        default=None,
        help="Comma-separated list of tools/runtimes to enable or update (claude, opencode, pi, antigravity)",
    )

    # status
    p_st = sub.add_parser("status", help="Print project state snapshot")
    p_st.add_argument("dir", nargs="?", default=".", help="Portable project directory (default: current directory)")

    # guide
    p_gd = sub.add_parser("guide", help="Interactive onboarding guide and walkthrough")
    p_gd.add_argument("dir", nargs="?", default=".", help="Portable project directory (default: current directory)")

    return parser


def _print_presets() -> None:
    """Print all built-in model presets with per-agent lineups."""
    agents_order = [
        "investigador", "redactor", "bibliografo-propuesta", "revisor",
        "presupuestador", "insumos-observador", "disenador-tikz",
        "tikz-optimizer", "revisor-figuras", "coordinador-propuesta",
    ]
    print("Built-in model presets")
    print("=" * 60)
    for name, lineup in _MODEL_PRESETS.items():
        print(f"\n  {name}:")
        for agent in agents_order:
            print(f"    {agent}: {lineup.get(agent, '?')}")


def _handle_agent_command_misuse(cmd_str: str) -> None:
    """Print a clear explanation when an operator tries to run an agent slash command
    (e.g., /propuesta-analizar or propuesta-analizar) directly in the terminal shell.
    """
    clean_cmd = "/" + cmd_str.lstrip("/")
    target = Path(".").resolve()
    print("\n" + "=" * 65)
    print(f" ℹ️  '{cmd_str}' ES UN COMANDO DE AGENTE DE IA (SLASH COMMAND)")
    print("=" * 65)
    print(f"\nEl comando '{clean_cmd}' no es una suborden de terminal para la herramienta 'marco'.")
    print("Es un slash command diseñado para ejecutarse DENTRO del chat de tu agente de IA.")
    print("\nCómo ejecutarlo correctamente:")
    print(f"  1. Abrí la terminal en el directorio de tu propuesta:\n     cd {target}")
    print("  2. Inicia la sesión de tu agente de IA:")
    print("     • pi:          pi .")
    print("     • Claude Code: claude")
    print("     • OpenCode:    opencode .")
    print("     • Antigravity: agy / antigravity")
    print("  3. Escribí el comando dentro de la ventana de chat del agente:")
    print(f"     👉 {clean_cmd}")

    cmd_basename = clean_cmd.lstrip('/')
    prompts_found = []
    pi_c = target / ".pi" / "commands" / f"{cmd_basename}.md"
    pi_p = target / ".pi" / "prompts" / f"{cmd_basename}.md"
    claude_c = target / ".claude" / "commands" / f"{cmd_basename}.md"
    opencode_c = target / ".opencode" / "commands" / f"{cmd_basename}.md"
    antigravity_w = target / ".agent" / "workflows" / f"{cmd_basename}.md"
    antigravity_s = target / ".agent" / "skills" / cmd_basename / "SKILL.md"

    if pi_c.is_file():
        prompts_found.append(f"  • pi:          .pi/commands/{cmd_basename}.md")
    elif pi_p.is_file():
        prompts_found.append(f"  • pi:          .pi/prompts/{cmd_basename}.md")
    if claude_c.is_file():
        prompts_found.append(f"  • Claude Code: .claude/commands/{cmd_basename}.md")
    if opencode_c.is_file():
        prompts_found.append(f"  • OpenCode:    .opencode/commands/{cmd_basename}.md")
    if antigravity_s.is_file():
        prompts_found.append(f"  • Antigravity: .agent/skills/{cmd_basename}/SKILL.md")
    elif antigravity_w.is_file():
        prompts_found.append(f"  • Antigravity: .agent/workflows/{cmd_basename}.md")

    if prompts_found:
        print("\nArchivos de definición del comando encontrados en este proyecto:")
        for pf in prompts_found:
            print(pf)
    print("=" * 65 + "\n")


def main(argv: list[str] | None = None) -> None:
    raw_args = sys.argv[1:] if argv is None else argv
    if raw_args:
        first = raw_args[0].lstrip("/")
        if first.startswith("propuesta") or first == "propuesta":
            _handle_agent_command_misuse(raw_args[0])
            return

    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "list_presets", False):
        _print_presets()
        return

    if args.command == "init":
        cmd_init(args)
    elif args.command == "upgrade":
        cmd_upgrade(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "guide":
        cmd_guide(args)


if __name__ == "__main__":
    main()

