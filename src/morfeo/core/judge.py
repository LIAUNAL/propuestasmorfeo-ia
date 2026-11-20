"""Juez final del tablero: lectura de la evaluación SGR y prompts de mejora.

`scripts/juez_sgr.py calificar` escribe `artefactos/juez/evaluacion.json`
(esquema `morfeo.evaluacion-sgr-consolidada/v1`) y la copia de la rúbrica
`artefactos/juez/rubrica.json` (`morfeo.rubrica-sgr/v1`). Este módulo solo los
lee para la pestaña «Juez final»: nunca lanza una excepción hacia la capa HTTP,
un archivo ausente o corrupto se informa en `errores`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .trees import _detect_flujo

JUDGE_DIR = Path("artefactos") / "juez"
EVALUACION_FILE = JUDGE_DIR / "evaluacion.json"
RUBRICA_FILE = JUDGE_DIR / "rubrica.json"
EVALUACION_SCHEMA = "morfeo.evaluacion-sgr-consolidada/v1"
RUBRICA_SCHEMA = "morfeo.rubrica-sgr/v1"
JUDGE_COMMAND = "/propuesta-juez"


def _read(run_dir: Path, rel: Path, schema: str) -> tuple[dict[str, Any] | None, str | None]:
    """(datos, error). Un archivo ausente no es un error: el juez aún no corrió."""
    path = run_dir / rel
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as err:
        return None, f"{rel.as_posix()} no es un JSON válido: {err}"
    if not isinstance(data, dict):
        return None, f"{rel.as_posix()} debe ser un objeto JSON."
    if data.get("schema") != schema:
        return None, f"{rel.as_posix()} no declara el esquema {schema} (declara {data.get('schema')!r})."
    return data, None


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _rubric_summary(rubrica: dict[str, Any]) -> dict[str, Any]:
    elegibilidad = rubrica.get("elegibilidad") if isinstance(rubrica.get("elegibilidad"), dict) else {}
    return {
        "id": rubrica.get("id"),
        "convocatoria": rubrica.get("convocatoria"),
        "umbral_total": elegibilidad.get("umbral_total"),
        "minimos": [{"criterio": str(m.get("criterio")), "minimo": m.get("minimo")}
                    for m in _dicts(elegibilidad.get("minimos"))],
        "criterios": [{
            "id": str(c.get("id")),
            "nombre": c.get("nombre"),
            "max": c.get("max"),
            "subcriterios": [{"id": str(s.get("id")), "nombre": s.get("nombre"), "max": s.get("max"),
                              "modo": s.get("modo")} for s in _dicts(c.get("subcriterios"))],
        } for c in _dicts(rubrica.get("criterios"))],
    }


def load_judge(run_dir: Path | str) -> dict[str, Any]:
    """Estado del juez para la corrida: flujo, evaluación consolidada y rúbrica."""
    run_dir = Path(run_dir)
    flujo = _detect_flujo(run_dir)
    result: dict[str, Any] = {"flujo": flujo, "disponible": False, "evaluacion": None, "rubrica": None, "errores": []}
    # El juez de propuestas de investigación (flujo base) llega en una entrega posterior.
    if flujo != "sgr":
        return result
    rubrica, err = _read(run_dir, RUBRICA_FILE, RUBRICA_SCHEMA)
    if err:
        result["errores"].append(err)
    elif rubrica is not None:
        result["rubrica"] = _rubric_summary(rubrica)
    evaluacion, err = _read(run_dir, EVALUACION_FILE, EVALUACION_SCHEMA)
    if err:
        result["errores"].append(err)
    elif evaluacion is not None:
        result["evaluacion"] = evaluacion
        result["disponible"] = True
    return result


def _one_line(value: Any) -> str:
    return " ".join(str(value or "").split())


def _join(values: Any) -> str:
    items = [_one_line(v) for v in values if _one_line(v)] if isinstance(values, list) else []
    return ", ".join(items)


def build_action_prompt(evaluacion: dict[str, Any], accion_id: Any, fuente: str | None = None) -> str:
    """Instrucción de una línea para la terminal del agente a partir de una acción del juez.

    `fuente` es la ruta de `evaluacion.json` que el agente puede abrir. Un id que no
    está entre las acciones de la evaluación levanta `ValueError`.
    """
    acciones = _dicts(evaluacion.get("acciones")) if isinstance(evaluacion, dict) else []
    wanted = str(accion_id)
    accion = next((a for a in acciones if str(a.get("id")) == wanted), None)
    if accion is None:
        raise ValueError(f"La evaluación no tiene la acción {wanted}.")

    ronda = evaluacion.get("ronda")
    origen = f"de la ronda {ronda} " if ronda not in (None, "") else ""
    ref = f" (detalle en {fuente})" if fuente else ""
    agente = _one_line(accion.get("agente")) or "usuario"
    secciones = _join(accion.get("secciones")) or "las secciones que correspondan"
    criterios = _join(accion.get("criterios"))
    crit = f" para el criterio {criterios}" if criterios and "," not in criterios else (
        f" para los criterios {criterios}" if criterios else "")
    instruccion = _one_line(accion.get("instruccion")).rstrip(".")

    head = f"Aplica la acción {wanted} del juez SGR {origen}en la corrida activa{ref}{crit}. "
    if agente == "usuario":
        body = (
            f"La acción le corresponde al usuario: explícame qué debo aportar o decidir en {secciones} "
            f"y ayúdame a incorporarlo. Instrucción del juez: {instruccion}. "
            "Si después se edita prosa, pasa el texto por grant-flow-auditor. "
        )
    else:
        body = (
            f"Despacha a {agente} para trabajar en {secciones}. Instrucción del juez: {instruccion}. "
            "Si edita prosa, pasa el texto resultante por grant-flow-auditor antes de cerrar. "
            "No cambies cifras, compromisos ni el problema central sin preguntarme. "
        )
    return head + body + f"Al terminar, vuelve a correr {JUDGE_COMMAND}."
