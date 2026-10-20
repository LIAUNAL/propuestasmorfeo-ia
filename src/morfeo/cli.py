"""Morfeo command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core.audit import audit_project
from .core.compile import compile_proposal
from .core.export import export_project
from .core.import_project import import_project
from .core.init import init_project
from .core.status import status_project
from .core.ui import start_ui
from .core.upgrade import upgrade_project
from .errors import MorfeoError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="morfeo",
        description="Morfeo IA — Orquestador de espacios de trabajo para formulación de propuestas de investigación.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="<comando>")

    # --- init ---
    p_init = sub.add_parser("init", help="Crea un nuevo espacio de trabajo independiente para una propuesta.")
    p_init.add_argument("dir", type=Path, help="Ruta del directorio a crear")
    p_init.add_argument(
        "--tools",
        default="claude,opencode,pi,antigravity",
        help="Herramientas a habilitar (separadas por coma: claude,opencode,pi,antigravity)",
    )
    p_init.add_argument("--preset", default="claude", choices=["claude", "gpt", "opencode-go"], help="Preset de modelos")
    p_init.add_argument("--lang", default="es", choices=["es", "en"], help="Idioma del scaffolding")
    p_init.add_argument("--title", default=None, help="Título inicial de la propuesta")
    p_init.add_argument("--force", action="store_true", help="Inicializar aunque el directorio no esté vacío")
    p_init.add_argument(
        "--sgr",
        action="store_true",
        help="El proyecto sigue el flujo del Sistema General de Regalías (MGA)",
    )

    # --- upgrade ---
    p_upgrade = sub.add_parser("upgrade", help="Actualiza los componentes del kit preservando el contenido del usuario.")
    p_upgrade.add_argument("dir", nargs="?", type=Path, default=Path("."), help="Directorio del proyecto (default: actual)")
    p_upgrade.add_argument("--force", action="store_true", help="Sobrescribir archivos protegidos")

    # --- audit ---
    p_audit = sub.add_parser("audit", help="Audita la integridad del kit contra el manifiesto SHA-256.")
    p_audit.add_argument("dir", nargs="?", type=Path, default=Path("."), help="Directorio del proyecto (default: actual)")
    p_audit.add_argument("--json", action="store_true", help="Emitir reporte en formato JSON")

    # --- status ---
    p_status = sub.add_parser("status", help="Muestra el estado de la propuesta activa, corridas y compuertas.")
    p_status.add_argument("dir", nargs="?", type=Path, default=Path("."), help="Directorio del proyecto (default: actual)")
    p_status.add_argument("--json", action="store_true", help="Emitir reporte en formato JSON")

    # --- compile ---
    p_compile = sub.add_parser("compile", help="Compila la propuesta activa a PDF o DOCX.")
    p_compile.add_argument("dir", nargs="?", type=Path, default=Path("."), help="Directorio del proyecto (default: actual)")
    p_compile.add_argument("--docx", action="store_true", help="Compilar a Word (DOCX) en lugar de PDF")
    p_compile.add_argument("--run", default=None, help="ID de la corrida a compilar (default: activa)")

    # --- ui ---
    p_ui = sub.add_parser("ui", help="Inicia el Command Center / Tablero de monitoreo visual en el navegador.")
    p_ui.add_argument("dir", nargs="?", type=Path, default=Path("."), help="Directorio del proyecto (default: actual)")
    p_ui.add_argument("--port", type=int, default=None, help="Puerto HTTP (default: 8080 o siguiente libre)")
    p_ui.add_argument("--no-open", action="store_true", help="No abrir automáticamente el navegador")

    # --- export ---
    p_export = sub.add_parser("export", help="Empaqueta y exporta un proyecto o corrida para compartir con sus artefactos.")
    p_export.add_argument("dir", nargs="?", type=Path, default=Path("."), help="Directorio del proyecto (default: actual)")
    p_export.add_argument("-o", "--output", type=Path, default=None, help="Ruta del archivo de salida (.tar.gz o .zip)")
    p_export.add_argument("--run", default=None, help="ID de la corrida a exportar (default: activa)")
    p_export.add_argument("--all-runs", action="store_true", help="Exportar todas las corridas de proposals/")
    p_export.add_argument("--format", choices=["tar.gz", "zip"], default="tar.gz", help="Formato de compresión (default: tar.gz)")

    # --- import ---
    p_import = sub.add_parser("import", help="Importa y desempaca un proyecto Morfeo compartido con sus artefactos.")
    p_import.add_argument("archive", type=Path, help="Archivo comprimido a importar (.tar.gz o .zip)")
    p_import.add_argument("dir", nargs="?", type=Path, default=None, help="Directorio de destino (default: nombre del proyecto)")
    p_import.add_argument("--force", action="store_true", help="Sobrescribir si el directorio de destino ya existe")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "init":
            tools_set = {t.strip() for t in args.tools.split(",") if t.strip()}
            return init_project(
                target_dir=args.dir,
                tools=tools_set,
                lang=args.lang,
                preset_name=args.preset,
                title=args.title,
                force=args.force,
                flujo="sgr" if args.sgr else "base",
            )
        elif args.command == "upgrade":
            return upgrade_project(target_dir=args.dir, force=args.force)
        elif args.command == "audit":
            return audit_project(target_dir=args.dir, as_json=args.json)
        elif args.command == "status":
            return status_project(target_dir=args.dir, as_json=args.json)
        elif args.command == "compile":
            return compile_proposal(target_dir=args.dir, docx=args.docx, run_id=args.run)
        elif args.command == "ui":
            return start_ui(target_dir=args.dir, port=args.port, no_open=args.no_open)
        elif args.command == "export":
            export_project(
                target_dir=args.dir,
                output_path=args.output,
                run_id=args.run,
                all_runs=args.all_runs,
                archive_format=args.format,
            )
            return 0
        elif args.command == "import":
            import_project(
                archive_path=args.archive,
                target_dir=args.dir,
                force=args.force,
            )
            return 0
        else:
            parser.print_help()
            return 1
    except MorfeoError as exc:
        print(f"morfeo: error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\nmorfeo: interrumpido", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
