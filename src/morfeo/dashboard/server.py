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

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        if path in ("/", "/index.html"):
            self.serve_dashboard()
        elif path == "/api/status":
            self.serve_api_status()
        elif path == "/api/pdf":
            self.serve_pdf()
        elif path == "/api/graph/papers":
            self.serve_graph("papers-graph.html")
        elif path == "/api/graph/vault":
            self.serve_graph("vault-graph.html")
        else:
            self.send_error(404, "Not Found")

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

    def serve_api_status(self) -> None:
        data = get_project_status(self.workspace_dir)
        active_run = data.get("active_run")

        parsed_gates = {}
        telemetria = []
        if active_run:
            run_dir = self.workspace_dir / "proposals" / active_run
            estado_file = run_dir / "artefactos" / "estado_propuesta.md"
            parsed_gates = parse_estado_propuesta(estado_file)

            telemetria_file = run_dir / "artefactos" / "pipeline" / "_estado.md"
            telemetria = parse_telemetria(telemetria_file)

        response_data = {
            **data,
            "pipeline_state": parsed_gates,
            "telemetria": telemetria,
        }

        body = json.dumps(response_data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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

        content = pdf_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(content)))
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
            self.send_error(404, f"{filename} not found")
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
