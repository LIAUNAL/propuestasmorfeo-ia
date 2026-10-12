"""Implementation of 'morfeo audit'."""

from __future__ import annotations

import json
from pathlib import Path

from ..errors import UserError
from .manifest import compute_sha256


def audit_project(
    target_dir: Path,
    as_json: bool = False,
) -> int:
    target_dir = target_dir.resolve()
    marker = target_dir / ".morfeo"
    if not marker.is_dir():
        marker = target_dir / ".marco"
    if not marker.is_dir():
        raise UserError(f"No es un espacio de trabajo Morfeo válido: {target_dir}")

    manifest_file = marker / "manifest.json"
    if not manifest_file.is_file():
        raise UserError(f"No se encontró manifest.json en {marker}")

    with manifest_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    installed_files = data.get("files", [])
    results: list[dict] = []
    drift_count = 0
    missing_count = 0

    for item in installed_files:
        rel = item["path"]
        expected_sha = item["sha256"]
        target_path = target_dir / rel

        if not target_path.exists():
            missing_count += 1
            results.append({"path": rel, "status": "missing", "expected": expected_sha})
        else:
            current_sha = compute_sha256(target_path)
            if current_sha != expected_sha:
                drift_count += 1
                results.append({"path": rel, "status": "modified", "current": current_sha, "expected": expected_sha})
            else:
                results.append({"path": rel, "status": "clean"})

    summary = {
        "version": data.get("version", "unknown"),
        "total_audited": len(installed_files),
        "clean": len(installed_files) - drift_count - missing_count,
        "modified": drift_count,
        "missing": missing_count,
        "details": results,
    }

    if as_json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"==> Auditoría de integridad de Morfeo ({summary['version']})")
        print(f"    Archivos auditados: {summary['total_audited']}")
        print(f"    Limpios (sin drift): {summary['clean']}")
        if drift_count:
            print(f"    Modificados: {drift_count}")
            for r in results:
                if r["status"] == "modified":
                    print(f"      [MODIFICADO] {r['path']}")
        if missing_count:
            print(f"    Faltantes: {missing_count}")
            for r in results:
                if r["status"] == "missing":
                    print(f"      [FALTANTE]   {r['path']}")

        if drift_count == 0 and missing_count == 0:
            print("\n[OK] El kit se encuentra 100% íntegro (0 drift).")
        else:
            print("\n[WARN] Se detectó drift respecto al manifiesto instalado. Usa 'morfeo upgrade .' para sincronizar.")

    return 1 if (drift_count or missing_count) else 0
