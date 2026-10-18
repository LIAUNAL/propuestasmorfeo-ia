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
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        if path == "/api/pdf/execute":
            self.handle_pdf_execute()
        elif path == "/api/graph/build":
            self.handle_graph_build()
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
            scripts_dir = self.workspace_dir / "scripts"
            if not (scripts_dir / "build_manuscript_graph.py").is_file():
                repo_root = Path(__file__).resolve().parent.parent.parent.parent
                scripts_dir = repo_root / "scripts"

            import sys
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from build_manuscript_graph import build_manuscript_graph
            payload = build_manuscript_graph(run_dir)
            body = json.dumps({
                "ok": True,
                "nodes": len(payload.get("nodes", [])),
                "edges": len(payload.get("edges", [])),
                "corpus": payload.get("corpus", "manuscript")
            }, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
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
            content = html_file.read_bytes()
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

    def handle_terminal_ws(self) -> None:
        upgrade = self.headers.get("Upgrade", "").strip().lower()
        if upgrade != "websocket":
            self.send_error(400, "WebSocket Upgrade required")
            return

        key = self.headers.get("Sec-WebSocket-Key", "")
        if not key:
            self.send_error(400, "Missing Sec-WebSocket-Key")
            return

        from .terminal import run_pty_session, ws_handshake_accept

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
        agent = qs.get("agent", ["claude"])[0]
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

        graph_path = self.workspace_dir / "proposals" / active_run / "grafos" / filename
        if not graph_path.is_file():
            fallback = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Grafo no disponible</title></head>
<body style="background:#0f172a;color:#94a3b8;font-family:-apple-system,BlinkMacSystemFont,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;">
  <div style="background:#1e293b;padding:2.5rem;border-radius:12px;border:1px solid #334155;max-width:520px;box-shadow:0 10px 25px rgba(0,0,0,0.5);">
    <div style="font-size:2.5rem;margin-bottom:0.75rem;">🌌</div>
    <h3 style="color:#38bdf8;margin:0 0 0.5rem 0;font-size:1.25rem;">Grafo no disponible para esta corrida</h3>
    <p style="font-size:0.9rem;line-height:1.5;margin:0 0 1rem 0;">El reporte <code>{filename}</code> aún no ha sido generado en el directorio <code>grafos/</code> de la corrida activa.</p>
    <p style="font-size:0.8rem;color:#64748b;margin:0;">Se compila automáticamente durante el pipeline con la herramienta <code>codebase-memory</code> o con <code>scripts/graph_html.py</code>.</p>
  </div>
</body>
</html>""".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(fallback)))
            self.end_headers()
            self.wfile.write(fallback)
            return

        content = graph_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run_server(workspace_dir: Path, port: int = 8080, host: str = "127.0.0.1") -> None:
    handler = type("ConfiguredHandler", (MorfeoDashboardHandler,), {"workspace_dir": workspace_dir})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"==> Morfeo Command Center UI activo en: http://{host}:{port}/")
    print("    Presiona Ctrl+C para detener el servidor.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor Morfeo UI detenido.")
        server.server_close()
