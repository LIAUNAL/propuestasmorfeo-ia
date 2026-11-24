"""Translated version of a run's manuscript, for the dashboard.

`scripts/traducir.py` (a kit script, standard library only) owns the
translation: blocks, fragments, the fidelity gate, the build and the compile
under `redaccion/traducciones/<lang>/`. This module loads that script from the
workspace's kit and reads its status for the «Versión del documento» fold of
the PDF preview (GET /api/traducciones), compiles the built translation (POST
/api/traduccion/compilar) and locates its PDF (GET /api/pdf?traduccion=<lang>).

The target language travels as `traduccion=<lang>`, never as `lang`: the
dashboard's i18n runtime adds `?lang=<ui language>` to every /api/ request,
and the interface language says nothing about the manuscript's.

A refusal of the script (an unknown or same-language target, nothing planned,
an incomplete build) comes back as `{"ok": False, "code", "error"}`; nothing
here raises for a missing or damaged file.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path
from typing import Any

TRANSLATE_COMMAND = "/propuesta-traducir"
LANGS = ("es", "en")
TRANSLATION_DIR = Path("redaccion") / "traducciones"

_LOCK = threading.Lock()
_ENGINES: dict[tuple[str, int], Any] = {}


def engine(scripts_dir: Path):
    """`scripts/traducir.py` of the kit at `scripts_dir`, loaded once per version of the file."""
    path = Path(scripts_dir) / "traducir.py"
    try:
        key = (str(path.resolve()), path.stat().st_mtime_ns)
    except OSError as exc:
        raise ValueError(f"No se encontró {path}: actualiza el kit del proyecto con `morfeo upgrade`.") from exc
    with _LOCK:
        module = _ENGINES.get(key)
        if module is None:
            name = f"_morfeo_traducir_{abs(hash(key))}"
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            _ENGINES[key] = module
    return module


def other_language(lang: str) -> str:
    return "en" if lang == "es" else "es"


def target_language(run_dir: Path, scripts_dir: Path, requested: str | None) -> tuple[str, str]:
    """(source, target): the run's writing language and the requested target,
    the other language when none is requested. ValueError for an unknown one."""
    source = engine(scripts_dir).source_language(Path(run_dir))
    target = (requested or "").strip() or other_language(source)
    if target not in LANGS:
        raise ValueError(f"Idioma de traducción desconocido {target!r}: usa es o en.")
    return source, target


def build_run_command(target: str) -> str:
    """Slash command the dashboard types into the agent's terminal."""
    if target not in LANGS:
        raise ValueError(f"Idioma de traducción desconocido {target!r}: usa es o en.")
    return f"{TRANSLATE_COMMAND} {target}"


def _refusal(exc) -> dict[str, Any]:
    return {"ok": False, "code": getattr(exc, "code", "TRANSLATION_ERROR"), "error": getattr(exc, "message", str(exc))}


def load_translation(run_dir: Path, scripts_dir: Path, requested: str | None = None) -> dict[str, Any]:
    """Status of the translation of the run at `run_dir` for the fold."""
    run_dir = Path(run_dir)
    try:
        source, target = target_language(run_dir, scripts_dir, requested)
    except ValueError as exc:
        return {"ok": False, "code": "TRANSLATION_LANGUAGE_UNSUPPORTED", "error": str(exc)}
    result: dict[str, Any] = {"ok": True, "run": run_dir.name, "source_language": source, "lang": target,
                              "command": build_run_command(target) if target != source else None,
                              "available": False, "status": None, "errores": []}
    module = engine(scripts_dir)
    if not (run_dir / "redaccion").is_dir():
        result["errores"].append("La corrida todavía no tiene redaccion/.")
        return result
    try:
        status = module.status(run_dir, target)
    except module.Refused as exc:
        return {**result, **_refusal(exc)}
    except (OSError, ValueError) as exc:
        result["errores"].append(f"No se pudo leer la traducción: {exc}")
        return result
    result["status"] = status
    result["available"] = bool(status.get("pdf"))
    return result


def compile_translation(run_dir: Path, scripts_dir: Path, requested: str | None = None) -> dict[str, Any]:
    """Compiles the built translation; the script refuses an unbuilt one."""
    try:
        _, target = target_language(Path(run_dir), scripts_dir, requested)
    except ValueError as exc:
        return {"ok": False, "code": "TRANSLATION_LANGUAGE_UNSUPPORTED", "error": str(exc)}
    module = engine(scripts_dir)
    try:
        return module.compile_translation(Path(run_dir), target)
    except module.Refused as exc:
        return _refusal(exc)


def translated_pdf(run_dir: Path, target: str) -> Path | None:
    """`redaccion/traducciones/<target>/main.pdf`, or None for an unknown language."""
    if target not in LANGS:
        return None
    return Path(run_dir) / TRANSLATION_DIR / target / "main.pdf"
