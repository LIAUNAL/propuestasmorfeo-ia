"""Juez de avance del tablero: lectura de la ronda por etapa y comando para correrlo.

`scripts/juez_avance.py registrar` escribe `artefactos/juez/avance_<etapa>.json`
(esquema `morfeo.juez-avance/v1`) a partir del borrador del agente
`juez-avance`. Este módulo solo lo lee para los paneles que montan el juez
(«Árbol de problemas y objetivos» con la etapa `arbol`; «Novedad e hipótesis»
con `novedad`; el desplegable «Juez final» de la previsualización PDF, en el
flujo base, con `final`) y arma el comando que el tablero escribe en la
terminal. Nunca
lanza una excepción hacia la capa HTTP por un archivo ausente o dañado: eso se
informa en `errores`. Una etapa desconocida sí es un error del llamador
(`ValueError`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ETAPAS = ("arbol", "novedad", "final")
# «arbol, novedad o final»: la lista de etapas para los mensajes de error.
ETAPAS_TEXTO = f"{', '.join(ETAPAS[:-1])} o {ETAPAS[-1]}"
AVANCE_SCHEMA = "morfeo.juez-avance/v1"
JUDGE_AVANCE_COMMAND = "/propuesta-juez-avance"
JUDGE_DIR = Path("artefactos") / "juez"


def _check(etapa: str) -> str:
    if etapa not in ETAPAS:
        raise ValueError(f"Etapa desconocida {etapa!r}: usa {ETAPAS_TEXTO}.")
    return etapa


def avance_file(etapa: str) -> Path:
    """Ruta del registro de la etapa, relativa a la corrida."""
    return JUDGE_DIR / f"avance_{_check(etapa)}.json"


def build_run_command(etapa: str) -> str:
    """Comando de barra que el tablero entrega a la terminal del agente."""
    return f"{JUDGE_AVANCE_COMMAND} {_check(etapa)}"


def load_judge_avance(run_dir: Path | str, etapa: str) -> dict[str, Any]:
    """Estado del juez de avance de una etapa: la ronda vigente con su historial."""
    rel = avance_file(etapa)
    result: dict[str, Any] = {"etapa": etapa, "disponible": False, "evaluacion": None,
                              "archivo": rel.as_posix(), "errores": []}
    path = Path(run_dir) / rel
    if not path.is_file():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as err:
        result["errores"].append(f"{rel.as_posix()} no es un JSON válido: {err}")
        return result
    if not isinstance(data, dict):
        result["errores"].append(f"{rel.as_posix()} debe ser un objeto JSON.")
        return result
    if data.get("schema") != AVANCE_SCHEMA:
        result["errores"].append(
            f"{rel.as_posix()} no declara el esquema {AVANCE_SCHEMA} (declara {data.get('schema')!r}).")
        return result
    if data.get("etapa") != etapa:
        result["errores"].append(f"{rel.as_posix()} es de la etapa {data.get('etapa')!r}, no de {etapa!r}.")
        return result
    result["evaluacion"] = data
    result["disponible"] = True
    return result
