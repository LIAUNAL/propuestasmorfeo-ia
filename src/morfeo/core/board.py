"""The board refresh: regenerate what the dashboard derives, then say where the
project stands (port of papersmith-ai's ``board_refresh``).

``morfeo ui`` runs :func:`refresh_artifacts` once in the background when the
server starts (``run_server(..., refresh=False)`` skips it), and the topbar's
«⟳ Actualizar tablero» button runs it again through ``POST /api/board/refresh``.
Only local, keyless generators run here: the run's graphs (the same
``build_all_graphs`` the «Regenerar grafo» button calls, which also draws the
SOTA constellation when ``atlas.json`` exists) and the project status, read
again from disk. Nothing here calls a model: what an agent still has to write is
reported by :func:`summarize` as the current unit, its missing checks and the
slash command that runs it.

Each generator is isolated: one that raises is reported as ``failed`` and the
others still run.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .status import get_project_status

DETAIL_MAX = 300

#: Progress states that count a unit as passed (``unit_progress``).
PASSED_STATES = frozenset({"verified", "skipped"})

#: Morfeo has no transversal unit today (papersmith's cross-cutting audit has no
#: counterpart); a unit listed here would never be reported as the current one.
TRANSVERSAL_UNITS: frozenset[str] = frozenset()

#: The command that starts a run when the workspace has none.
INIT_COMMAND = "/propuesta-init"


def _entry(artifact: str, label: str, state: str, detail: Any = "") -> dict[str, Any]:
    return {"id": artifact, "label": label, "state": state, "detail": str(detail or "")[:DETAIL_MAX]}


def resolve_scripts_dir(workspace_dir: Path) -> Path:
    """Folder that holds ``build_manuscript_graph.py``.

    The packaged kit goes first: a portable project's scripts/ is a copy frozen
    at the kit version it was created with, and rendering with it would hide
    every graph fix shipped since.
    """
    package = Path(__file__).resolve().parent.parent
    kit_scripts = package / "_kit" / "scripts"
    repo_root = package.parent.parent
    for candidate in (kit_scripts, workspace_dir / "scripts", repo_root / "scripts"):
        if (candidate / "build_manuscript_graph.py").is_file():
            return candidate
    return workspace_dir / "scripts"


def _graph_builder(workspace_dir: Path) -> Any | None:
    """The ``build_manuscript_graph`` module, or None when it is not installed."""
    scripts_dir = resolve_scripts_dir(workspace_dir)
    if not (scripts_dir / "build_manuscript_graph.py").is_file():
        return None
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import build_manuscript_graph  # noqa: PLC0415 - lives in the kit's scripts/

    return build_manuscript_graph


def _active_run_dir(workspace_dir: Path) -> Path | None:
    proposals = workspace_dir / "proposals"
    try:
        active = (proposals / ".current-run").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not active or "/" in active or active in (".", ".."):
        return None
    run_dir = proposals / active
    return run_dir if run_dir.is_dir() else None


def _graphs(workspace_dir: Path) -> tuple[str, str]:
    run_dir = _active_run_dir(workspace_dir)
    if run_dir is None:
        return "skipped", "No hay una corrida activa: no hay grafos que regenerar"
    builder = _graph_builder(workspace_dir)
    if builder is None:
        return "skipped", "build_manuscript_graph.py no está instalado"
    corpora = builder.build_all_graphs(run_dir) or {}
    counts = ", ".join(f"{name}: {len(data.get('nodes', []))} nodos"
                       for name, data in corpora.items() if isinstance(data, dict))
    return "ok", counts or "sin corpus"


def _status(workspace_dir: Path) -> tuple[str, str]:
    data = get_project_status(workspace_dir, force_refresh=True)
    totals = data.get("totals") or {}
    return "ok", f"{totals.get('gates_passed', 0)}/{totals.get('gates_total', 0)} compuertas aprobadas"


#: ``(id, label, generator)`` in the order a refresh runs them. A generator
#: returns ``(state, detail)``; raising reports it as ``failed``.
GENERATORS: tuple[tuple[str, str, Callable[[Path], tuple[str, str]]], ...] = (
    ("grafos", "Grafos de la corrida", lambda ws: _graphs(ws)),
    ("estado", "Estado del proyecto", lambda ws: _status(ws)),
)


def refresh_artifacts(workspace_dir: Path | str) -> list[dict[str, Any]]:
    """Run each generator of :data:`GENERATORS`; one ``{id, label, state,
    detail}`` per generator, ``state`` being ``ok``, ``skipped`` (its input is
    not there yet) or ``failed``."""
    workspace_dir = Path(workspace_dir).expanduser().resolve()
    results = []
    for artifact, label, generator in GENERATORS:
        try:
            state, detail = generator(workspace_dir)
            results.append(_entry(artifact, label, state, detail))
        except Exception as exc:  # noqa: BLE001 - one generator never stops the others
            results.append(_entry(artifact, label, "failed", f"{type(exc).__name__}: {exc}"))
    return results


def _gate(gate: dict[str, Any]) -> dict[str, Any]:
    return {"id": gate.get("id", ""), "name": gate.get("name", ""),
            "status": gate.get("status", ""), "phase": gate.get("phase", "")}


def summarize(status: dict[str, Any], artifacts: list[dict[str, Any]] | None = None,
              last_refresh: dict[str, Any] | None = None) -> dict[str, Any]:
    """Where the project stands, from a ``/api/status`` payload.

    ``current`` is the first unit whose progress has not passed (``None`` when
    all have, or without an active run), ``missing`` its failed checks,
    ``open_gates`` the gates not decided yet and ``failed_gates`` the failed
    ones. ``tone`` is ``alert`` when a gate failed, ``warn`` when a generator
    failed, ``done`` when every unit passed and ``info`` otherwise.
    """
    units = [u for u in status.get("pipeline_units") or [] if isinstance(u, dict)]
    progress = status.get("unit_progress") or {}
    gates = [g for g in status.get("gates") or [] if isinstance(g, dict)]
    control = status.get("control") or {}
    active = bool(status.get("active_run"))

    tracked = [u for u in units if isinstance(progress.get(u.get("id")), dict)]
    passed = [u for u in tracked if progress[u["id"]].get("state") in PASSED_STATES]
    current = next((u for u in tracked
                    if u["id"] not in TRANSVERSAL_UNITS
                    and progress[u["id"]].get("state") not in PASSED_STATES), None)
    missing = [str(label) for label in (progress[current["id"]].get("missing") or [])] if current else []

    open_gates = [_gate(g) for g in gates if g.get("status") not in ("PASS", "FAIL")]
    failed_gates = [_gate(g) for g in gates if g.get("status") == "FAIL"]
    failed_artifacts = [{"id": a.get("id", ""), "label": a.get("label", ""), "detail": a.get("detail", "")}
                        for a in artifacts or [] if a.get("state") == "failed"]

    if failed_gates:
        tone = "alert"
    elif failed_artifacts:
        tone = "warn"
    elif active and tracked and current is None:
        tone = "done"
    else:
        tone = "info"

    if not active:
        next_command = INIT_COMMAND
    elif control.get("next_step") == "done":
        next_command = None
    else:
        next_command = control.get("next_command") or None

    current_info = None
    if current is not None:
        state = progress[current["id"]]
        current_info = {"id": current["id"], "name": current.get("name", ""),
                        "state": state.get("state", ""), "verdict": state.get("verdict"),
                        "gate": current.get("gate")}
    return {
        "active_run": status.get("active_run"),
        "current": current_info,
        "missing": missing,
        "open_gates": open_gates,
        "failed_gates": failed_gates,
        "failed_artifacts": failed_artifacts,
        "units_completed": len(passed),
        "units_total": len(tracked),
        "gates_passed": sum(1 for g in gates if g.get("status") == "PASS"),
        "gates_total": len(gates),
        "next_step": control.get("next_step"),
        "next_command": next_command,
        "tone": tone,
        "last_refresh": None if not last_refresh else {
            "started_at": last_refresh.get("started_at"),
            "finished_at": last_refresh.get("finished_at"),
        },
    }


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class BoardRefresher:
    """One workspace's refresh: one at a time, and the last result kept so the
    page can report the start-up refresh."""

    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = workspace_dir
        self.lock = threading.Lock()
        self.last: dict[str, Any] | None = None

    def run(self) -> dict[str, Any] | None:
        """Regenerate and summarize; ``None`` while another refresh runs."""
        if not self.lock.acquire(blocking=False):
            return None
        try:
            started = _utc_now()
            artifacts = refresh_artifacts(self.workspace_dir)
            result: dict[str, Any] = {"ok": True, "busy": False, "started_at": started,
                                      "finished_at": _utc_now(), "artifacts": artifacts}
            status = get_project_status(self.workspace_dir, force_refresh=True)
            result["summary"] = summarize(status, artifacts, result)
            self.last = result
            return result
        finally:
            self.lock.release()

    def run_quietly(self) -> None:
        """The start-up refresh; a failure only means the board shows what was on disk."""
        try:
            self.run()
        except Exception:  # noqa: BLE001 - the start-up refresh is best effort
            pass

    def current_summary(self) -> dict[str, Any]:
        last = self.last
        status = get_project_status(self.workspace_dir)
        return {"summary": summarize(status, (last or {}).get("artifacts"), last),
                "last_refresh": last,
                "refreshing": self.lock.locked()}


_REFRESHERS: dict[str, BoardRefresher] = {}
_REFRESHERS_LOCK = threading.Lock()


def refresher_for(workspace_dir: Path | str) -> BoardRefresher:
    """The refresher of a workspace, shared by every request of the server."""
    root = Path(workspace_dir).expanduser().resolve()
    with _REFRESHERS_LOCK:
        if str(root) not in _REFRESHERS:
            _REFRESHERS[str(root)] = BoardRefresher(root)
        return _REFRESHERS[str(root)]


def forget(workspace_dir: Path | str) -> None:
    """Drop a workspace's refresher (tests, and a server that stops)."""
    root = Path(workspace_dir).expanduser().resolve()
    with _REFRESHERS_LOCK:
        _REFRESHERS.pop(str(root), None)


__all__ = ["GENERATORS", "PASSED_STATES", "TRANSVERSAL_UNITS", "BoardRefresher", "forget",
           "refresh_artifacts", "refresher_for", "resolve_scripts_dir", "summarize"]
