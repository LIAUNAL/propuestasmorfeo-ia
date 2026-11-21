"""Lightweight Command Center server for Morfeo workspaces.

Serves the interactive dashboard, JSON APIs, graph views, and PDF previews.
Uses Python's standard library (http.server) to guarantee zero external dependencies.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..core.compile import compile_run_pdf, pdf_version
from ..core.pdf_annotator import apply_pdf_annotations
from ..core.presentation import ASSET_TYPES, build_presentation, resolve_asset
from ..core.sgr_panel import load_style_report, load_tdr_chapters
from ..core.sgr_rules import load_sgr_blocks
from ..core import board
from ..core.status import get_project_status, read_flujo, record_server_start
from ..core.judge import EVALUACION_FILE, JUDGE_COMMAND, build_action_prompt, load_judge
from ..core.trees import _workspace_path, approve_tree, load_trees, record_feedback
from ..core.style_sgr import load_style
from ..core.value_chain import approve as approve_value_chain, build_adjust_prompt, load_value_chain
from ..core.alliance import approve as approve_alliance, build_adjust_prompt as build_alliance_prompt, load_alliance
from ..core.budget import approve as approve_budget, build_adjust_prompt as build_budget_prompt, load_budget
from ..core.components import approve as approve_components, build_adjust_prompt as build_components_prompt, load_components
from ..core.products import approve as approve_products, build_adjust_prompt as build_products_prompt, load_products
from ..core.annex2 import load_annex2
from ..core.opportunities import build_search_prompt, build_start_prompt, load_opportunities
from ..core.requirements import (
    MAX_BODY_BYTES as REQUIREMENTS_MAX_BODY,
    approve as approve_requirements,
    build_adjust_prompt as build_requirements_prompt,
    load_requirements,
    update_item as update_requirement,
)
from . import terminal_routes


def parse_estado_propuesta(estado_file: Path) -> dict[str, Any]:
    """Parse gate and phase progress from artefactos/estado_propuesta.md."""
    if not estado_file.is_file():
        return {}

    content = estado_file.read_text(encoding="utf-8", errors="replace")
    gates: dict[str, str] = {}
    phases: list[dict[str, str]] = []

    # Match rows like | G1 | pass | or | Fase 1 | ...
    for line in content.splitlines():
        if "|" in line:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 2:
                col0, col1 = parts[0], parts[1]
                if col0.startswith("G") or "gate" in col0.lower():
                    gates[col0] = col1.lower()
                elif col0.startswith("Fase") or col0.startswith("Paso"):
                    phases.append({"phase": col0, "status": col1})

    return {
        "raw_gates": gates,
        "phases": phases,
    }


def parse_telemetria(telemetria_file: Path) -> list[dict[str, Any]]:
    """Parse usage metrics from artefactos/pipeline/_estado.md."""
    if not telemetria_file.is_file():
        return []

    content = telemetria_file.read_text(encoding="utf-8", errors="replace")
    rows: list[dict[str, Any]] = []

    for line in content.splitlines():
        if "|" in line:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 4 and not parts[0].startswith("---") and parts[0] != "Fase":
                rows.append({
                    "fase": parts[0],
                    "tokens": parts[1],
                    "tool_uses": parts[2],
                    "duracion": parts[3],
                })

    return rows


def flatten_idea(markdown: str) -> str:
    """One-line idea for `/propuesta-analizar`: "Heading: text" per filled section.

    The `idea.md` template has only headings and HTML comments; that yields "".
    """
    markdown = re.sub(r"<!--.*?-->", "", markdown, flags=re.S)
    parts: list[str] = []
    heading: str | None = None
    lines: list[str] = []

    def flush() -> None:
        body = " ".join(" ".join(lines).split())
        if body:
            parts.append(f"{heading}: {body}" if heading else body)

    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match:
            flush()
            lines = []
            # The level-1 title names the document, not a section of the idea.
            heading = match.group(2).strip() if len(match.group(1)) > 1 else None
            continue
        lines.append(line)
    flush()
    return " ".join(parts)


BRAND_ASSETS = frozenset({"favicon.ico", "favicon.png", "morfeo-logo.png"})
# Page code moved out of index.html: it must stay as fresh as the page that
# loads it, so a cached copy never runs against a newer index.html.
PAGE_SCRIPTS = frozenset({"cli-console.js", "board-refresh.js", "convocatorias-map.js"})

# Origins a loopback server answers from: the browser may name it either way.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


# build.sh escribe en la misma carpeta: dos compilaciones a la vez se pisan.
_COMPILE_LOCK = threading.Lock()


class MorfeoDashboardHandler(SimpleHTTPRequestHandler):
    workspace_dir: Path

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if terminal_routes.dispatch(self, "GET", path):
            return

        if path in ("/", "/index.html"):
            self.serve_dashboard()
        elif path.startswith("/static/"):
            self.serve_static_asset(path)
        elif path in ("/favicon.ico", "/favicon.png"):
            self.serve_favicon(path)
        elif path == "/api/status":
            self.serve_api_status()
        elif path == "/api/idea":
            self.serve_idea()
        elif path == "/api/flow":
            self.serve_flow()
        elif path == "/api/pdf":
            self.serve_pdf()
        elif path == "/api/pdf/version":
            self.serve_pdf_version()
        elif path == "/presentacion":
            self.serve_presentation()
        elif path == "/api/presentation/asset":
            self.serve_presentation_asset()
        elif path == "/api/pdf/annotations":
            self.serve_pdf_annotations()
        elif path.startswith("/api/graph/"):
            graph_key = path[len("/api/graph/"):].strip("/")
            filename = graph_key if graph_key.endswith(".html") else f"{graph_key}-graph.html"
            self.serve_graph(filename)
        elif path == "/api/artifact":
            self.serve_artifact()
        elif path == "/api/trees":
            self.serve_trees()
        elif path == "/api/guide/sgr":
            self.serve_sgr_guide()
        elif path == "/api/tdr/capitulos":
            self.serve_tdr_chapters()
        elif path == "/api/estilo":
            self.serve_style_report()
        elif path == "/api/judge":
            self.serve_judge()
        elif path == "/api/value-chain":
            self.serve_value_chain()
        elif path == "/api/alliance":
            self.serve_alliance()
        elif path == "/api/budget":
            self.serve_budget()
        elif path == "/api/components":
            self.serve_components()
        elif path == "/api/products":
            self.serve_products()
        elif path == "/api/requirements":
            self.serve_requirements()
        elif path == "/api/anexo2":
            self.serve_annex2()
        elif path == "/api/style-sgr":
            self.serve_style_sgr()
        elif path == "/api/convocatorias":
            self.serve_opportunities()
        elif path == "/api/board/summary":
            self.serve_board_summary()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        if terminal_routes.dispatch(self, "POST", path):
            return
        if path == "/api/run/select":
            self.handle_run_select()
        elif path == "/api/pdf/execute":
            self.handle_pdf_execute()
        elif path == "/api/pdf/compile":
            self.handle_pdf_compile()
        elif path == "/api/graph/build":
            self.handle_graph_build()
        elif path == "/api/trees/feedback":
            self.handle_trees_feedback()
        elif path == "/api/trees/approve":
            self.handle_trees_approve()
        elif path == "/api/estilo/auditar":
            self.handle_style_audit()
        elif path == "/api/judge/send":
            self.handle_judge_send()
        elif path == "/api/judge/run":
            self.handle_judge_run()
        elif path == "/api/value-chain/approve":
            self.handle_value_chain_approve()
        elif path == "/api/value-chain/adjust":
            self.handle_value_chain_adjust()
        elif path == "/api/alliance/approve":
            self.handle_alliance_approve()
        elif path == "/api/alliance/adjust":
            self.handle_alliance_adjust()
        elif path == "/api/budget/approve":
            self.handle_budget_approve()
        elif path == "/api/budget/adjust":
            self.handle_budget_adjust()
        elif path == "/api/components/approve":
            self.handle_components_approve()
        elif path == "/api/components/adjust":
            self.handle_components_adjust()
        elif path == "/api/products/approve":
            self.handle_products_approve()
        elif path == "/api/products/adjust":
            self.handle_products_adjust()
        elif path == "/api/requirements/approve":
            self.handle_requirements_approve()
        elif path == "/api/requirements/adjust":
            self.handle_requirements_adjust()
        elif path == "/api/requirements/item":
            self.handle_requirements_item()
        elif path == "/api/convocatorias/buscar":
            self.handle_opportunities_search()
        elif path == "/api/convocatorias/iniciar":
            self.handle_opportunities_start()
        elif path == "/api/board/refresh":
            self.handle_board_refresh()
        else:
            self.send_error(404, "Not Found")

    def do_DELETE(self) -> None:
        path = self.path.split("?")[0]
        if not terminal_routes.dispatch(self, "DELETE", path):
            self.send_error(404, "Not Found")

    def serve_static_asset(self, req_path: str) -> None:
        rel_path = req_path.replace("/static/", "", 1)
        static_dir = (Path(__file__).resolve().parent / "static").resolve()
        target = (static_dir / rel_path).resolve()
        try:
            target.relative_to(static_dir)
        except ValueError:
            self.send_error(403, "Access denied")
            return

        if not target.is_file():
            self.send_error(404, "Asset not found")
            return

        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".ico": "image/x-icon",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".json": "application/json",
        }
        content_type = content_types.get(target.suffix.lower(), "application/octet-stream")
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        # The brand images share paths with other local dashboards; revalidate
        # them so a port reused by another tool never shows its cached icon.
        if target.name in BRAND_ASSETS or target.name in PAGE_SCRIPTS:
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(content)

    def serve_favicon(self, req_path: str = "/favicon.ico") -> None:
        static_dir = (Path(__file__).resolve().parent / "static").resolve()
        target = static_dir / ("favicon.ico" if req_path == "/favicon.ico" else "favicon.png")
        if not target.is_file():
            target = static_dir / "favicon.png"
        if not target.is_file():
            self.send_error(404, "Favicon not found")
            return
        content = target.read_bytes()
        content_type = "image/x-icon" if target.suffix == ".ico" else "image/png"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def serve_vendor_asset(self, req_path: str) -> None:
        self.serve_static_asset(req_path)

    def serve_pdf_annotations(self) -> None:
        data = get_project_status(self.workspace_dir)
        active_run = data.get("active_run")
        if not active_run:
            self.send_error(404, "No active run")
            return

        ann_file = self.workspace_dir / "proposals" / active_run / "artefactos" / "pipeline" / "anotaciones_pdf.json"
        if not ann_file.is_file():
            ann_file = self.workspace_dir / "proposals" / active_run / "artefactos" / "anotaciones_pdf.json"

        if ann_file.is_file():
            body = ann_file.read_bytes()
        else:
            body = json.dumps({"timestamp": None, "annotations": [], "applied": {}}).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_run_select(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception as e:
            err_body = json.dumps({"ok": False, "error": f"JSON payload inválido: {e}"}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)
            return

        run_id = str(payload.get("run_id", "")).strip()
        proposals_dir = self.workspace_dir / "proposals"
        current_pointer = proposals_dir / ".current-run"

        if not run_id:
            if current_pointer.is_file():
                try:
                    current_pointer.unlink()
                except Exception:
                    pass
            get_project_status(self.workspace_dir, force_refresh=True)
            body = json.dumps({"ok": True, "active_run": None}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        target_run_dir = proposals_dir / run_id
        if not target_run_dir.is_dir() or not (target_run_dir / "_run.md").is_file():
            err_body = json.dumps({"ok": False, "error": f"Corrida '{run_id}' no encontrada o sin _run.md"}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)
            return

        proposals_dir.mkdir(parents=True, exist_ok=True)
        current_pointer.write_text(f"{run_id}\n", encoding="utf-8")
        get_project_status(self.workspace_dir, force_refresh=True)

        body = json.dumps({"ok": True, "active_run": run_id}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_pdf_execute(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception as e:
            err_body = json.dumps({"ok": False, "error": f"JSON payload inválido: {e}"}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)
            return

        annotations = payload.get("annotations", [])
        process_pending = payload.get("process_pending", True)
        data = get_project_status(self.workspace_dir)
        active_run = data.get("active_run")
        if not active_run:
            err_body = json.dumps({"ok": False, "error": "No hay una corrida activa seleccionada"}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)
            return

        run_dir = self.workspace_dir / "proposals" / active_run
        result = apply_pdf_annotations(run_dir, annotations, process_pending=process_pending)

        status_code = 200 if result.get("ok") else 500
        body = json.dumps(result, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _resolve_scripts_dir(self) -> Path:
        # The packaged kit goes first (see board.resolve_scripts_dir).
        return board.resolve_scripts_dir(self.workspace_dir)

    # --- «⟳ Actualizar tablero» ---------------------------------------------

    def handle_board_refresh(self) -> None:
        # Same-origin is enforced for every POST by terminal_routes.dispatch.
        result = board.refresher_for(self.workspace_dir).run()
        if result is None:
            self._send_json(409, {"ok": False, "busy": True,
                                  "error": "Ya hay una actualización del tablero en curso"})
            return
        self._send_json(200, result)

    def serve_board_summary(self) -> None:
        # Read-only: the status as it stands plus the last refresh (the start-up
        # one or the button's), so the page can report it once.
        self._send_json(200, board.refresher_for(self.workspace_dir).current_summary())

    def handle_graph_build(self) -> None:
        data = get_project_status(self.workspace_dir)
        active_run = data.get("active_run")
        if not active_run:
            body = json.dumps({"ok": False, "error": "No hay una corrida activa seleccionada"}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        run_dir = self.workspace_dir / "proposals" / active_run
        try:
            scripts_dir = self._resolve_scripts_dir()

            import sys
            import urllib.parse
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from build_manuscript_graph import (
                build_manuscript_graph,
                build_papers_graph,
                build_vault_graph,
                build_all_graphs,
            )

            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            corpus = qs.get("corpus", ["all"])[0].lower()

            all_res = build_all_graphs(run_dir)
            corpora_stats = {
                k: {
                    "nodes": len(v.get("nodes", [])),
                    "edges": len(v.get("edges", [])),
                }
                for k, v in all_res.items()
            }

            if corpus in all_res:
                target_payload = all_res[corpus]
                nodes_count = len(target_payload.get("nodes", []))
                edges_count = len(target_payload.get("edges", []))
            else:
                nodes_count = sum(s["nodes"] for s in corpora_stats.values())
                edges_count = sum(s["edges"] for s in corpora_stats.values())

            body = json.dumps({
                "ok": True,
                "nodes": nodes_count,
                "edges": edges_count,
                "corpus": corpus,
                "corpora": corpora_stats,
                "active_run": active_run,
            }, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            body = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def serve_dashboard(self) -> None:
        html_file = Path(__file__).resolve().parent / "static" / "index.html"
        if html_file.is_file():
            raw_html = html_file.read_text(encoding="utf-8", errors="replace")
            try:
                import html as _html
                status = get_project_status(self.workspace_dir)
                details = status.get("run_details") or {}
                project_name = (
                    details.get("title")
                    or details.get("idea")
                    or status.get("workspace_title")
                    or status.get("active_run")
                    or self.workspace_dir.name
                )
                if project_name:
                    safe_title = _html.escape(f"Morfeo IA: {project_name}")
                    raw_html = re.sub(
                        r"<title>.*?</title>",
                        f"<title>{safe_title}</title>",
                        raw_html,
                        count=1,
                    )
                    raw_html = re.sub(
                        r'<h1 id="topbarProjectTitle"[^>]*>.*?</h1>',
                        f'<h1 id="topbarProjectTitle" title="{safe_title}">{safe_title}</h1>',
                        raw_html,
                        count=1,
                    )
            except Exception:
                pass
            content = raw_html.encode("utf-8")
        else:
            content = b"<h1>Morfeo Dashboard</h1>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        # The page and its scripts change together on an upgrade: revalidate.
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def serve_flow(self) -> None:
        flow_path = self.workspace_dir / "docs" / "diagrams" / "morfeo-pipeline-flow.html"
        if not flow_path.is_file():
            flow_path = Path(__file__).resolve().parent / "static" / "morfeo-pipeline-flow.html"
        if not flow_path.is_file():
            self.send_error(404, "Diagrama Archify no encontrado. Genera con: node docs/diagrams/morfeo-flow.build.mjs")
            return

        content = flow_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def serve_artifact(self) -> None:
        import urllib.parse
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        rel_file = params.get("file", [""])[0]

        if not rel_file:
            self.send_error(400, "Missing 'file' parameter")
            return

        data = get_project_status(self.workspace_dir)
        active_run = data.get("active_run")
        if not active_run:
            self.send_error(404, "No active run")
            return

        run_dir = self.workspace_dir / "proposals" / active_run
        target = (run_dir / rel_file).resolve()

        # Security check: must be strictly within run_dir
        try:
            target.relative_to(run_dir.resolve())
        except ValueError:
            self.send_error(403, "Access denied")
            return

        if not target.is_file():
            self.send_error(404, "File not found")
            return

        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    # --- Árboles de problemas y objetivos -----------------------------------

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _active_run_dir(self) -> Path | None:
        # Solo hace falta el nombre de la corrida: se lee el puntero en lugar de
        # reconstruir el estado completo, porque la pestaña sondea cada 4 s.
        proposals = self.workspace_dir / "proposals"
        try:
            active_run = (proposals / ".current-run").read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not active_run or "/" in active_run or active_run in (".", ".."):
            return None
        run_dir = proposals / active_run
        return run_dir if run_dir.is_dir() else None

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def serve_trees(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        self._send_json(200, {"ok": True, "run": run_dir.name, **load_trees(run_dir)})

    def handle_trees_feedback(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        result = record_feedback(
            run_dir, str(payload.get("tree") or ""), payload.get("comments") or [], str(payload.get("general") or "")
        )
        self._send_json(200 if result.get("ok") else 400, result)

    def handle_trees_approve(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        result = approve_tree(run_dir, str(payload.get("tree") or ""))
        # 409: el flujo todavía no permite aprobar (falta el árbol previo o textos).
        self._send_json(200 if result.get("ok") else 409, result)

    # El juez final: como en «Enviar ajuste al agente» de los árboles, el servidor
    # arma el prompt y el tablero lo entrega a la terminal con sendTerminalPrompt.
    def serve_judge(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        self._send_json(200, {"ok": True, "run": run_dir.name, **load_judge(run_dir)})

    def handle_judge_send(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        judge = load_judge(run_dir)
        if judge["evaluacion"] is None:
            # 409: todavía no hay una evaluación de la que salgan acciones.
            error = "; ".join(judge["errores"]) or f"No hay evaluación del juez: corre {JUDGE_COMMAND} primero."
            self._send_json(409, {"ok": False, "error": error})
            return
        accion_id = str(payload.get("accion_id") or "")
        try:
            prompt = build_action_prompt(judge["evaluacion"], accion_id,
                                         fuente=_workspace_path(run_dir, EVALUACION_FILE))
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        self._send_json(200, {"ok": True, "accion_id": accion_id, "prompt": prompt})

    def handle_judge_run(self) -> None:
        if self._active_run_dir() is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        self._send_json(200, {"ok": True, "prompt": JUDGE_COMMAND})

    # Cadena de valor y estilo SGR (solo flujo SGR; en el base responden sin datos).
    # El ajuste, como en los árboles y el juez, devuelve el prompt y el tablero lo
    # entrega a la terminal con sendTerminalPrompt.
    def serve_value_chain(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        self._send_json(200, {"ok": True, "run": run_dir.name, **load_value_chain(run_dir)})

    def handle_value_chain_approve(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        result = approve_value_chain(run_dir, str(payload.get("hash") or "") or None)
        # 409: la cadena no se puede aprobar todavía (hallazgos de error o cambió).
        self._send_json(200 if result.get("ok") else 409, result)

    def handle_value_chain_adjust(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        try:
            prompt = build_adjust_prompt(run_dir, payload.get("nota"))
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        self._send_json(200, {"ok": True, "prompt": prompt})

    # Alianza y territorio (solo flujo SGR), con las convenciones de la cadena de valor.
    def serve_alliance(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        self._send_json(200, {"ok": True, "run": run_dir.name, **load_alliance(run_dir)})

    def handle_alliance_approve(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        result = approve_alliance(run_dir, str(payload.get("hash") or "") or None)
        self._send_json(200 if result.get("ok") else 409, result)

    def handle_alliance_adjust(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        try:
            prompt = build_alliance_prompt(run_dir, payload.get("nota"))
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        self._send_json(200, {"ok": True, "prompt": prompt})

    # Presupuesto y cronograma (solo flujo SGR), con las convenciones de la alianza.
    def serve_budget(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        self._send_json(200, {"ok": True, "run": run_dir.name, **load_budget(run_dir)})

    def handle_budget_approve(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        result = approve_budget(run_dir, str(payload.get("hash") or "") or None)
        self._send_json(200 if result.get("ok") else 409, result)

    def handle_budget_adjust(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        try:
            prompt = build_budget_prompt(run_dir, payload.get("nota"))
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        self._send_json(200, {"ok": True, "prompt": prompt})

    # TRL y componentes transversales (solo flujo SGR), con las convenciones del presupuesto.
    def serve_components(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        self._send_json(200, {"ok": True, "run": run_dir.name, **load_components(run_dir)})

    def handle_components_approve(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        result = approve_components(run_dir, str(payload.get("hash") or "") or None)
        self._send_json(200 if result.get("ok") else 409, result)

    def handle_components_adjust(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        try:
            prompt = build_components_prompt(run_dir, payload.get("nota"))
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        self._send_json(200, {"ok": True, "prompt": prompt})

    # Productos, talento e indicadores (solo flujo SGR), con las convenciones de los componentes.
    def serve_products(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        self._send_json(200, {"ok": True, "run": run_dir.name, **load_products(run_dir)})

    def handle_products_approve(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        result = approve_products(run_dir, str(payload.get("hash") or "") or None)
        self._send_json(200 if result.get("ok") else 409, result)

    def handle_products_adjust(self) -> None:
        payload = self._read_json_body()
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        try:
            prompt = build_products_prompt(run_dir, payload.get("nota"))
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        self._send_json(200, {"ok": True, "prompt": prompt})

    # Requisitos, licencias y cifras de los anexos (solo flujo SGR), con las convenciones de los
    # productos y un tope al cuerpo de los POST: una edición en línea es un puñado de campos.
    def _read_requirements_body(self) -> tuple[dict[str, Any] | None, bool]:
        """(payload, demasiado_grande). Un cuerpo por encima del tope se descarta sin guardarse."""
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            return None, False
        if length > REQUIREMENTS_MAX_BODY:
            # Se descarta por trozos, sin guardarlo, para que el cliente reciba el 413
            # en vez de un reinicio de la conexión; la conexión se cierra después.
            remaining = min(length, 64 * REQUIREMENTS_MAX_BODY)
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, REQUIREMENTS_MAX_BODY))
                if not chunk:
                    break
                remaining -= len(chunk)
            self.close_connection = True
            return None, True
        return self._read_json_body(), False

    def _requirements_body_or_error(self) -> tuple[dict[str, Any] | None, Path | None]:
        payload, too_large = self._read_requirements_body()
        if too_large:
            self._send_json(413, {"ok": False, "error": f"El cuerpo supera {REQUIREMENTS_MAX_BODY // 1024} KB."})
            return None, None
        run_dir = self._active_run_dir()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return None, None
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return None, None
        return payload, run_dir

    def serve_requirements(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        self._send_json(200, {"ok": True, "run": run_dir.name, **load_requirements(run_dir)})

    def handle_requirements_approve(self) -> None:
        payload, run_dir = self._requirements_body_or_error()
        if run_dir is None:
            return
        result = approve_requirements(run_dir, str(payload.get("hash") or "") or None)
        self._send_json(200 if result.get("ok") else 409, result)

    def handle_requirements_adjust(self) -> None:
        payload, run_dir = self._requirements_body_or_error()
        if run_dir is None:
            return
        try:
            prompt = build_requirements_prompt(run_dir, payload.get("nota"))
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        self._send_json(200, {"ok": True, "prompt": prompt})

    def handle_requirements_item(self) -> None:
        payload, run_dir = self._requirements_body_or_error()
        if run_dir is None:
            return
        try:
            result = update_requirement(run_dir, payload)
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        except Exception as err:
            self._send_json(500, {"ok": False, "error": f"No se pudo guardar el requisito: {err}"})
            return
        if not result.get("ok"):
            self._send_json(409, result)
            return
        self._send_json(200, {"run": run_dir.name, **result})

    # Vista del Anexo 2 (solo flujo SGR, solo lectura): en el flujo base responde 409.
    def serve_annex2(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        data = load_annex2(run_dir)
        if data["flujo"] != "sgr":
            self._send_json(409, {"ok": False, "run": run_dir.name, **data})
            return
        self._send_json(200, {"ok": True, "run": run_dir.name, **data})

    # Convocatorias (ambos flujos, nivel de espacio de trabajo, solo lectura): no
    # necesita corrida activa. Los botones devuelven el prompt y el tablero lo
    # entrega a la terminal con sendTerminalPrompt, como el juez.
    # `?alcance=proyecto|banco` elige el perfil; sin él decide el script.
    def serve_opportunities(self) -> None:
        values = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query, keep_blank_values=True).get("alcance")
        if values is not None and len(values) != 1:
            self._send_json(400, {"ok": False, "error": "El alcance debe ser «proyecto» o «banco»."})
            return
        try:
            data = load_opportunities(self.workspace_dir, values[0] if values else None)
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        self._send_json(200, {"ok": True, **data})

    def handle_opportunities_search(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        try:
            prompt = build_search_prompt(payload.get("alcance"))
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        self._send_json(200, {"ok": True, "prompt": prompt})

    def handle_opportunities_start(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "JSON payload inválido"})
            return
        try:
            prompt = build_start_prompt(payload.get("id"))
        except ValueError as err:
            self._send_json(400, {"ok": False, "error": str(err)})
            return
        self._send_json(200, {"ok": True, "prompt": prompt})

    def serve_style_sgr(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        self._send_json(200, {"ok": True, "run": run_dir.name, **load_style(run_dir)})

    def serve_idea(self) -> None:
        candidates = [self.workspace_dir / "idea.md"]
        pointer = self.workspace_dir / "proposals" / ".current-run"
        run = pointer.read_text(encoding="utf-8").strip() if pointer.is_file() else ""
        if re.fullmatch(r"[A-Za-z0-9._-]+", run) and run not in (".", ".."):
            candidates.append(self.workspace_dir / "proposals" / run / "insumos" / "ideas" / "idea.md")
        text, source = "", None
        for path in candidates:
            if path.is_file():
                text = flatten_idea(path.read_text(encoding="utf-8", errors="replace"))
                if text:
                    source = path.relative_to(self.workspace_dir).as_posix()
                    break
        body = json.dumps({"ok": True, "text": text, "source": source}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def serve_sgr_guide(self) -> None:
        # Bloques «### SGR §N» de la guía del proyecto para el panel Secciones.
        blocks, source = load_sgr_blocks(self.workspace_dir)
        self._send_json(200, {"ok": True, "flujo": read_flujo(self.workspace_dir), "source": source, "blocks": blocks})

    def serve_tdr_chapters(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(200, {"ok": True, "fuente": None, "capitulos": []})
            return
        self._send_json(200, {"ok": True, **load_tdr_chapters(run_dir)})

    def serve_style_report(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(200, {"ok": True, "disponible": False})
            return
        self._send_json(200, {"ok": True, **load_style_report(run_dir)})

    def handle_style_audit(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        script = self._resolve_scripts_dir() / "estilo_es.py"
        try:
            done = subprocess.run(
                [sys.executable, str(script), "auditar", str(run_dir), "--todo"],
                capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            self._send_json(504, {"ok": False, "error": "La auditoría de estilo tardó demasiado"})
            return
        if done.returncode != 0:
            self._send_json(500, {"ok": False, "error": done.stderr.strip()[-400:] or "Falló la auditoría de estilo"})
            return
        self._send_json(200, {"ok": True, **load_style_report(run_dir)})

    def serve_api_status(self) -> None:
        response_data = get_project_status(self.workspace_dir)
        # Compacto: el tablero lo pide cada 2 a 5 s, y la sangría solo engordaba el cuerpo.
        body = json.dumps(response_data, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_presentation(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self.send_error(404, "No active run")
            return
        body = build_presentation(run_dir).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def serve_presentation_asset(self) -> None:
        from urllib.parse import parse_qs, urlparse

        run_dir = self._active_run_dir()
        if run_dir is None:
            self.send_error(404, "No active run")
            return
        rel = (parse_qs(urlparse(self.path).query).get("path") or [""])[0]
        target, status = resolve_asset(run_dir, rel)
        if target is None:
            self.send_error(status, "Access denied" if status == 403 else "Asset not found")
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ASSET_TYPES[target.suffix.lower()])
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def serve_pdf_version(self) -> None:
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        version = pdf_version(run_dir / "redaccion" / "main.pdf")
        self._send_json(200, {"ok": True, "exists": version is not None, "version": version})

    def handle_pdf_compile(self) -> None:
        """Recompila main.pdf con build.sh; una compilación a la vez por servidor."""
        run_dir = self._active_run_dir()
        if run_dir is None:
            self._send_json(404, {"ok": False, "error": "No hay una corrida activa seleccionada"})
            return
        redaccion = run_dir / "redaccion"
        if not (redaccion / "build.sh").is_file():
            self._send_json(404, {"ok": False, "error": "La corrida no tiene redaccion/build.sh"})
            return
        if not _COMPILE_LOCK.acquire(blocking=False):
            self._send_json(409, {"ok": False, "error": "Ya hay una compilación en curso"})
            return
        try:
            result = compile_run_pdf(redaccion)
        finally:
            _COMPILE_LOCK.release()
        self._send_json(200 if result["ok"] else 500, result)

    def serve_pdf(self) -> None:
        data = get_project_status(self.workspace_dir)
        active_run = data.get("active_run")
        if not active_run:
            self.send_error(404, "No active run")
            return

        pdf_path = self.workspace_dir / "proposals" / active_run / "redaccion" / "main.pdf"
        if not pdf_path.is_file():
            self.send_error(404, "main.pdf not found")
            return

        file_size = pdf_path.stat().st_size
        etag = f'"{pdf_version(pdf_path)}"'

        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return

        content = pdf_path.read_bytes()

        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            try:
                parts = range_header[6:].split("-")
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if parts[1] else file_size - 1
                end = min(end, file_size - 1)
                chunk_len = max(0, end - start + 1)

                self.send_response(206)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(chunk_len))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content[start:end+1])
                return
            except Exception:
                pass

        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def serve_graph(self, filename: str) -> None:
        data = get_project_status(self.workspace_dir)
        active_run = data.get("active_run")
        if not active_run:
            self.send_error(404, "No active run")
            return

        run_dir = self.workspace_dir / "proposals" / active_run
        graph_path = run_dir / "grafos" / filename
        if not graph_path.is_file():
            try:
                scripts_dir = self._resolve_scripts_dir()
                import sys
                if str(scripts_dir) not in sys.path:
                    sys.path.insert(0, str(scripts_dir))
                from build_manuscript_graph import build_all_graphs
                build_all_graphs(run_dir)
            except Exception:
                pass

        if not graph_path.is_file():
            fallback = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Grafo no disponible</title></head>
<body style="background:#0f172a;color:#94a3b8;font-family:-apple-system,BlinkMacSystemFont,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;">
  <div style="background:#1e293b;padding:2.5rem;border-radius:12px;border:1px solid #334155;max-width:520px;box-shadow:0 10px 25px rgba(0,0,0,0.5);">
    <div style="font-size:2.5rem;margin-bottom:0.75rem;">🌌</div>
    <h3 style="color:#38bdf8;margin:0 0 0.5rem 0;font-size:1.25rem;">Grafo no disponible para esta corrida</h3>
    <p style="font-size:0.9rem;line-height:1.5;margin:0 0 1rem 0;">El reporte <code>{filename}</code> aún no ha sido generado en el directorio <code>grafos/</code> de la corrida activa.</p>
    <p style="font-size:0.8rem;color:#64748b;margin:0;">Pulsa <strong>⚡ Regenerar Grafo</strong> arriba a la derecha para construirlo.</p>
  </div>
</body>
</html>""".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(fallback)))
            self.end_headers()
            self.wfile.write(fallback)
            return

        content = graph_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def bind_dashboard(workspace_dir: Path, port: int, host: str = "127.0.0.1",
                   server_cls: type = ThreadingHTTPServer):
    """Bind the dashboard for `workspace_dir`; None, with the reason printed,
    when the port is already taken."""
    handler = type("ConfiguredHandler", (MorfeoDashboardHandler,), {"workspace_dir": workspace_dir})
    try:
        return server_cls((host, port), handler)
    except OSError as err:
        if err.errno in (48, 98):
            print(f"Error: El puerto {port} ya está en uso por otro proceso o tablero Morfeo.")
            print("Puedes especificar otro puerto usando: morfeo ui --port <nuevo_puerto>")
            return None
        raise


def start_board_refresh(workspace_dir: Path) -> None:
    """Run the board refresh once in the background."""
    threading.Thread(target=board.refresher_for(workspace_dir).run_quietly,
                     name="board-refresh", daemon=True).start()


def run_server(workspace_dir: Path, port: int = 8080, host: str = "127.0.0.1",
               refresh: bool = True) -> None:
    """Serve the dashboard. `refresh` runs the board refresh once in the
    background when the server starts, so the first visit shows the project as
    it stands. `morfeo ui` (core.ui.start_ui) uses the same two helpers and
    adds the CLI activation link and the browser opening."""
    server = bind_dashboard(workspace_dir, port, host)
    if server is None:
        return
    record_server_start()
    if refresh:
        start_board_refresh(workspace_dir)
    print(f"==> Morfeo Command Center UI activo en: http://{host}:{port}/")
    print("    Presiona Ctrl+C para detener el servidor.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor Morfeo UI detenido.")
    finally:
        server.server_close()
