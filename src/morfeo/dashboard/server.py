"""Lightweight Command Center server for Morfeo workspaces.

Serves the interactive dashboard, JSON APIs, graph views, and PDF previews.
Uses Python's standard library (http.server) to guarantee zero external dependencies.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..core.pdf_annotator import apply_pdf_annotations
from ..core.status import get_project_status
from ..core.trees import approve_tree, load_trees, record_feedback


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


class MorfeoDashboardHandler(SimpleHTTPRequestHandler):
    workspace_dir: Path

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        if path in ("/", "/index.html"):
            self.serve_dashboard()
        elif path.startswith("/static/"):
            self.serve_static_asset(path)
        elif path in ("/favicon.ico", "/favicon.png"):
            self.serve_favicon(path)
        elif path == "/api/status":
            self.serve_api_status()
        elif path == "/api/terminal/agents":
            self.serve_terminal_agents()
        elif path == "/api/terminal/tools":
            self.serve_terminal_tools()
        elif path == "/ws/terminal":
            self.handle_terminal_ws()
        elif path == "/api/flow":
            self.serve_flow()
        elif path == "/api/pdf":
            self.serve_pdf()
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
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        if path == "/api/run/select":
            self.handle_run_select()
        elif path == "/api/pdf/execute":
            self.handle_pdf_execute()
        elif path == "/api/graph/build":
            self.handle_graph_build()
        elif path == "/api/terminal/launch-external":
            self.handle_launch_external_terminal()
        elif path == "/api/trees/feedback":
            self.handle_trees_feedback()
        elif path == "/api/trees/approve":
            self.handle_trees_approve()
        else:
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
        self.send_header("Cache-Control", "public, max-age=86400")
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
        # The packaged kit goes first: a portable project's scripts/ is a copy
        # frozen at the kit version it was created with, and rendering with it
        # would hide every graph fix shipped since.
        kit_scripts = Path(__file__).resolve().parent.parent / "_kit" / "scripts"
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        for candidate in (kit_scripts, self.workspace_dir / "scripts", repo_root / "scripts"):
            if (candidate / "build_manuscript_graph.py").is_file():
                return candidate
        return self.workspace_dir / "scripts"

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

    def serve_api_status(self) -> None:
        response_data = get_project_status(self.workspace_dir)
        body = json.dumps(response_data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_terminal_agents(self) -> None:
        from .terminal import get_available_agents
        agents = get_available_agents()
        body = json.dumps({"ok": True, "agents": agents}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_terminal_tools(self) -> None:
        from .terminal import detect_terminal_tools, get_current_agent_pane_id
        tools = detect_terminal_tools(self.workspace_dir)
        tools["monitored_path"] = str(self.workspace_dir.resolve())
        tools["active_pane"] = get_current_agent_pane_id(self.workspace_dir)
        body = json.dumps({"ok": True, "tools": tools}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_launch_external_terminal(self) -> None:
        from .terminal import launch_external_terminal
        res = launch_external_terminal(self.workspace_dir)
        body = json.dumps(res, ensure_ascii=False).encode("utf-8")
        self.send_response(200 if res.get("ok") else 400)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_terminal_ws(self) -> None:
        upgrade = self.headers.get("Upgrade", "").strip().lower()
        if upgrade != "websocket":
            self.send_error(400, "WebSocket Upgrade required")
            return

        key = self.headers.get("Sec-WebSocket-Key", "")
        if not key:
            self.send_error(400, "Missing Sec-WebSocket-Key")
            return

        from .terminal import (
            find_executable,
            get_current_agent_pane_id,
            run_pane_mirror_session,
            run_pty_session,
            ws_handshake_accept,
        )

        accept_token = ws_handshake_accept(key)
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_token}\r\n\r\n"
        )
        self.wfile.write(response.encode("ascii"))
        self.wfile.flush()

        import urllib.parse
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        agent = qs.get("agent", ["herdr"])[0]
        try:
            cols = int(qs.get("cols", [80])[0])
        except (ValueError, TypeError):
            cols = 80
        try:
            rows = int(qs.get("rows", [24])[0])
        except (ValueError, TypeError):
            rows = 24

        self.close_connection = True

        run_pty_session(
            sock=self.request,
            workspace_dir=self.workspace_dir,
            agent_id=agent,
            init_rows=rows,
            init_cols=cols,
        )

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

        stat = pdf_path.stat()
        file_size = stat.st_size
        etag = f'"{int(stat.st_mtime)}-{file_size}"'

        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Accept-Ranges", "bytes")
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


def run_server(workspace_dir: Path, port: int = 8080, host: str = "127.0.0.1") -> None:
    handler = type("ConfiguredHandler", (MorfeoDashboardHandler,), {"workspace_dir": workspace_dir})
    try:
        server = ThreadingHTTPServer((host, port), handler)
    except OSError as err:
        if err.errno in (48, 98):
            print(f"Error: El puerto {port} ya está en uso por otro proceso o tablero Morfeo.")
            print("Puedes especificar otro puerto usando: morfeo ui --port <nuevo_puerto>")
            return
        raise
    print(f"==> Morfeo Command Center UI activo en: http://{host}:{port}/")
    print("    Presiona Ctrl+C para detener el servidor.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor Morfeo UI detenido.")
        server.server_close()
