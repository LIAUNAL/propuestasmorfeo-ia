"""Hallazgos de estilo SGR por sección, para la columna «Estilo SGR» de Secciones.

Solo en el flujo SGR. `scripts/estilo_sgr.py` expone
`findings(run_root, section=None)` con hallazgos
`{severity, code, message, archivo, linea, extracto, regla}`; este módulo lo
carga desde el kit como `value_chain` carga `cadena_valor_sgr.py` y los agrupa
por sección (el stem del archivo, p. ej. `02_justificacion`). Un script ausente
deja la columna sin datos; un fallo del script se informa en `errores`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .trees import _detect_flujo
from .value_chain import load_kit_script

STYLE_SCRIPT = "estilo_sgr.py"


def _section_of(finding: dict[str, Any]) -> str:
    archivo = str(finding.get("archivo") or "").replace("\\", "/")
    return Path(archivo).stem if archivo else ""


def load_style(run_dir: Path | str) -> dict[str, Any]:
    run_dir = Path(run_dir)
    flujo = _detect_flujo(run_dir)
    result: dict[str, Any] = {"flujo": flujo, "disponible": False, "por_seccion": {}, "errores": []}
    if flujo != "sgr":
        return result
    module = load_kit_script(STYLE_SCRIPT, ("findings",))
    if module is None:
        return result
    try:
        raw = module.findings(run_dir)
    except Exception as err:
        result["errores"].append(f"{STYLE_SCRIPT} no pudo revisar el estilo: {err}")
        return result
    por_seccion: dict[str, dict[str, Any]] = {}
    for f in raw if isinstance(raw, list) else []:
        if not isinstance(f, dict):
            continue
        stem = _section_of(f)
        if not stem:
            continue
        entry = por_seccion.setdefault(stem, {"total": 0, "advertencias": 0, "info": 0, "hallazgos": []})
        severity = "info" if f.get("severity") == "info" else "advertencia"
        entry["total"] += 1
        entry["advertencias" if severity == "advertencia" else "info"] += 1
        entry["hallazgos"].append({
            "severity": severity,
            "code": str(f.get("code") or ""),
            "regla": str(f.get("regla") or ""),
            "linea": f.get("linea") if isinstance(f.get("linea"), int) else None,
            "extracto": str(f.get("extracto") or ""),
            "message": str(f.get("message") or ""),
        })
    result["por_seccion"] = por_seccion
    result["disponible"] = True
    return result
