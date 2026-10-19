"""Manifest, hashing, templates and model preset declarations."""

from __future__ import annotations

import hashlib
from fnmatch import fnmatch
from pathlib import Path
import shutil
import stat

# ---------------------------------------------------------------------------
# Model presets
# ---------------------------------------------------------------------------

MODEL_PRESETS: dict[str, dict[str, str]] = {
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

VALID_PRESETS = frozenset(MODEL_PRESETS.keys())


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def matches_preserve(rel_path: str, patterns: list[str]) -> bool:
    """Return True if rel_path matches any preserve glob pattern."""
    for pat in patterns:
        if fnmatch(rel_path, pat):
            return True
    return False


def _is_script(path: Path) -> bool:
    if path.suffix == ".sh":
        return True
    try:
        with path.open("rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def copy_kit_file(src: Path, dst: Path) -> None:
    """Copy one kit file, leaving scripts executable.

    Wheels do not reliably carry file modes, so the mode is decided by what the
    file is rather than copied from the installed kit.
    """
    shutil.copyfile(src, dst)
    if _is_script(dst):
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def copy_kit_entry(src_root: Path, dst_root: Path, kit_path: str) -> list[dict]:
    """Copy one manifest entry from src_root to dst_root."""
    src = src_root / kit_path
    if not src.exists():
        return []

    dst = dst_root / kit_path
    copied: list[dict] = []

    if src.is_dir():
        for item in src.rglob("*"):
            if item.is_file():
                rel = item.relative_to(src_root).as_posix()
                item_dst = dst_root / rel
                item_dst.parent.mkdir(parents=True, exist_ok=True)
                copy_kit_file(item, item_dst)
                copied.append({"path": rel, "sha256": compute_sha256(item_dst)})
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        copy_kit_file(src, dst)
        copied.append({"path": kit_path, "sha256": compute_sha256(dst)})

    return copied


def idea_template(lang: str = "es") -> str:
    if lang == "en":
        return """# Proposal idea

## Problem
<!-- Describe the problem or opportunity addressed by the proposal -->

## Approach
<!-- Describe proposed method, tech innovation and solution -->

## Beneficiaries
<!-- Who benefits directly and indirectly? -->

## Constraints / Alignment
<!-- Technical, budget, or timeline constraints; funding call alignment -->

## Open questions
<!-- Key questions to resolve before starting the pipeline -->
"""
    return """# Idea de propuesta

## Problema
<!-- Describe el problema u oportunidad que aborda la propuesta -->

## Enfoque
<!-- Describe el enfoque de solución propuesto (método, tecnología, innovación) -->

## Beneficiarios
<!-- ¿Quiénes se benefician directa e indirectamente? -->

## Restricciones / Alineación
<!-- Restricciones técnicas, presupuestales, de tiempo; alineación con convocatoria -->

## Preguntas abiertas
<!-- Lista de preguntas que necesitan respuesta antes de iniciar el pipeline -->
"""


def decisions_template(lang: str = "es") -> str:
    if lang == "en":
        return """# Project decisions

## Decisions
<!-- Decision log: date, decision, owner, rationale -->

## User clarifications
<!-- Items where operator clarified requirements or scope -->

## Do / Don't
<!-- What is in and out of scope -->

## Open questions
<!-- Pending questions requiring operator or team input -->
"""
    return """# Decisiones del proyecto

## Decisiones
<!-- Registro de decisiones tomadas: fecha, decisión, responsable, justificación -->

## Aclaraciones del usuario
<!-- Puntos donde el operador aclaró requisitos o alcance -->

## Hacer / No hacer
<!-- Lista de lo que está dentro y fuera del alcance -->

## Preguntas abiertas
<!-- Preguntas pendientes que requieren respuesta del operador o del equipo -->
"""


def journal_readme(lang: str = "es") -> str:
    if lang == "en":
        return """# Journal — Event log

Append-only event log for proposal milestones, decisions and reviews.
"""
    return """# Journal — Bitácora de eventos

Directorio con registro append-only de eventos de la propuesta.
"""


def project_readme(
    title: str | None,
    tools: set[str],
    lang: str = "es",
    preset_name: str = "claude",
    version: str = "0.5.0",
) -> str:
    lines = [
        f"# {title if title else 'Propuesta Morfeo IA'}",
        "",
        "Espacio de trabajo estructurado para la formulación asistida de propuestas de investigación en IA.",
        "",
        f"**Versión Morfeo:** {version}",
        f"**Configuración:** language={lang}, model_preset={preset_name}",
        "",
        "## Comandos del pipeline",
        "",
        "| Comando | Propósito |",
        "|---------|-----------|",
        "| `/propuesta-init <idea>` | Crea y activa una corrida: `proposals/<run-id>/` |",
        "| `/propuesta-insumos` | Configura zonas de depósito en `insumos/` (TDR, draft, background, ideas) |",
        "| `/propuesta-analizar [idea]` | Inicia el análisis e ingesta de insumos (Fase 0) |",
        "| `/propuesta-continuar` | Ejecuta el siguiente paso del pipeline |",
        "| `/propuesta` | Pipeline completo con compuertas interactivas |",
        "| `/propuesta-limpiar` | Cierra y archiva la corrida activa |",
        "| `/compilar-pdf` | Compila `main.pdf` |",
        "| `/compilar-docx` | Exporta a Word `main.docx` |",
        "",
        "## Tablero de control (UI)",
        "",
        "Para iniciar el tablero de monitoreo visual en tu navegador:",
        "",
        "```bash",
        "morfeo ui .",
        "```",
        "",
        "## Estructura del proyecto",
        "",
        "```",
        ".morfeo/             # Marcador, configuración y hashes de integridad",
        ".claude/             # Agentes y comandos para Claude Code",
    ]
    if "opencode" in tools:
        lines.append(".opencode/           # Superficie para OpenCode")
    if "pi" in tools:
        lines.append(".pi/                 # Superficie para Pi")
    if "antigravity" in tools:
        lines.append(".agent/              # Habilidades y flujos para Google Antigravity")
    lines.extend([
        "plantilla/           # Esqueleto LaTeX versionado",
        "proposals/           # Corridas de propuestas generadas",
        "idea.md              # Borrador inicial de la idea",
        "DECISIONS.md         # Registro de decisiones",
        "journal/             # Bitácora de eventos",
        "README.md            # Este documento",
        "```",
        "",
    ])
    return "\n".join(lines) + "\n"
