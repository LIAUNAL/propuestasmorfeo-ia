"""Whether each pipeline unit really completed, for the dashboard.

A PASS verdict alone is not enough: the unit counts as completed only when its
gate is PASS (or, for a unit without a gate, its event
`artefactos/pipeline/NN-<id>.md` exists), the execution control has moved past
it, and the artifacts and sections it produces exist. The dashboard lights a
card from this verdict and lists each check, so a PASS with a missing file shows
up as incomplete instead of done.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# A heartbeat older than this is a unit that was cut off, not one still running.
STALE_HEARTBEAT_HOURS = 6


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _artifact(run_dir: Path, rel: str) -> dict[str, Any]:
    """One declared artifact; `dir/*` exists when the folder holds any file."""
    if rel.endswith("/*"):
        folder = run_dir / rel[:-2]
        files = [f for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")] if folder.is_dir() else []
        newest = max((_mtime(f) or 0.0 for f in files), default=None)
        return {"path": rel, "exists": bool(files), "mtime": newest, "count": len(files)}
    path = run_dir / rel
    return {"path": rel, "exists": path.is_file(), "mtime": _mtime(path) if path.is_file() else None}


def _section(run_dir: Path, num: str) -> dict[str, Any]:
    matches = sorted((run_dir / "redaccion" / "sections").glob(f"{num}_*.tex"))
    if matches:
        rel = f"redaccion/sections/{matches[0].name}"
        return {"path": rel, "exists": True, "mtime": _mtime(matches[0])}
    return {"path": f"redaccion/sections/{num}_*.tex", "exists": False, "mtime": None}


def _event(run_dir: Path, unit_id: str) -> Path | None:
    matches = sorted((run_dir / "artefactos" / "pipeline").glob(f"*-{unit_id}.md"))
    return matches[0] if matches else None


def _verdict(unit: dict[str, Any], gates: list[dict[str, Any]], telemetria: list[dict[str, Any]]) -> str | None:
    gate = unit.get("gate")
    if gate:
        for g in gates:
            if g.get("id") == gate:
                return g.get("status") or "PENDING"
    for row in telemetria:
        if str(row.get("fase", "")).strip().lower().replace(".", "_") == unit["id"]:
            text = str(row.get("veredicto", "")).upper()
            if "PASS" in text or "APROBADA" in text:
                return "PASS"
            if "FAIL" in text:
                return "FAIL"
    return "PENDING" if gate else None


def _control_done(unit: dict[str, Any], units: list[dict[str, Any]], control: dict[str, Any] | None) -> bool | None:
    """True once the execution control left the unit behind; None without a control block."""
    if control is None:
        return None
    if unit.get("kind") == "pre":
        return bool(control.get("intake_complete"))
    nxt = control.get("next_step")
    if nxt == "done":
        return True
    steps = [u["id"] for u in units if u.get("kind") != "pre"]
    if nxt not in steps or unit["id"] not in steps:
        return False
    return steps.index(unit["id"]) < steps.index(nxt)


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.astimezone()


def heartbeat_is_stale(en_curso: dict[str, Any], units: list[dict[str, Any]], control: dict[str, Any] | None) -> bool:
    """A heartbeat left behind by a unit that already completed, or one too old to be live."""
    unit = next((u for u in units if u["id"] == en_curso.get("fase")), None)
    if unit is not None and _control_done(unit, units, control):
        return True
    started = _parse_iso(en_curso.get("inicio"))
    if started is None:
        return False
    age = datetime.now(timezone.utc) - started.astimezone(timezone.utc)
    return age.total_seconds() > STALE_HEARTBEAT_HOURS * 3600


def unit_progress(
    run_dir: Path,
    units: list[dict[str, Any]],
    gates: list[dict[str, Any]],
    telemetria: list[dict[str, Any]],
    control: dict[str, Any] | None,
    en_curso: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    running = en_curso.get("fase") if en_curso and not en_curso.get("stale") else None
    result: dict[str, dict[str, Any]] = {}
    for unit in units:
        uid = unit["id"]
        verdict = _verdict(unit, gates, telemetria)
        event = _event(run_dir, uid)
        done = _control_done(unit, units, control)
        files = [_artifact(run_dir, rel) for rel in unit.get("artifacts", [])]
        files += [_section(run_dir, num) for num in unit.get("sections", [])]

        checks: list[dict[str, Any]] = []
        if unit.get("gate"):
            checks.append({"id": "gate", "label": f"Compuerta {unit['gate']} en PASS", "ok": verdict == "PASS"})
        else:
            checks.append({"id": "event", "label": f"Evento artefactos/pipeline/NN-{uid}.md registrado", "ok": event is not None})
        if done is not None:
            label = ("Control de ejecución: intake_complete: true" if unit.get("kind") == "pre"
                     else "Control de ejecución: next_step ya avanzó más allá de la unidad")
            checks.append({"id": "control", "label": label, "ok": done})
        for f in files:
            checks.append({"id": "file", "label": f"{f['path']} existe", "ok": f["exists"], "path": f["path"]})

        missing = [c["label"] for c in checks if not c["ok"]]
        if uid == running:
            state = "running"
        elif not missing:
            state = "verified"
        elif verdict in ("FAIL", "BLOCKED"):
            state = "failed"
        elif uid == "g0_5" and done and not any(f["exists"] for f in files):
            # Optional unit: the intake closed without a TDR, so there was no guide to adjust.
            state = "skipped"
        elif verdict == "PASS" or done or event is not None:
            state = "partial"
        else:
            state = "pending"

        result[uid] = {
            "state": state,
            "verdict": verdict,
            "event": f"artefactos/pipeline/{event.name}" if event else None,
            "checks": checks,
            "missing": missing,
            "artifacts": files,
        }
    return result
