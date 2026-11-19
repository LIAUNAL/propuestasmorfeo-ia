"""Cadena de valor SGR de una corrida, para la pestaña «Cadena de valor».

Solo existe en el flujo SGR: en el flujo base no se lee nada y el tablero oculta
la pestaña. `scripts/cadena_valor_sgr.py init` siembra
`artefactos/sgr/cadena_valor.json` (esquema `morfeo.cadena-valor-sgr/v1`) desde
el árbol de objetivos aprobado y su `check` produce los hallazgos `cadena-*` con
la forma de check_run (`{severity, code, message, node}`). Este módulo carga ese
script desde el kit, como `trees` carga las reglas de `check_run.py`: si falta,
la cadena se muestra sin hallazgos y el tablero nunca se cae.

La aprobación vive en `artefactos/sgr/revision.json` con la misma semántica que
la de los árboles: queda atada al hash del contenido aprobado, caduca si el
archivo cambia y una cadena con hallazgos de error no se puede aprobar.
"""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .trees import _detect_flujo, _hash, _workspace_path

SGR_DIR = Path("artefactos") / "sgr"
CADENA_FILE = SGR_DIR / "cadena_valor.json"
REVIEW_FILE = SGR_DIR / "revision.json"
CADENA_SCHEMA = "morfeo.cadena-valor-sgr/v1"
CADENA_SCRIPT = "cadena_valor_sgr.py"
# Nombres que puede tener la función de reglas del script, en orden de preferencia.
CADENA_RULE_NAMES = ("findings", "check_findings")

_REVIEW_LOCK = threading.Lock()
_SCRIPT_CACHE: dict[str, tuple[float, Any]] = {}
_SCRIPT_LOCK = threading.Lock()


def _script_candidates(name: str) -> list[Path]:
    """Rutas donde buscar un script del kit: el kit instalado y luego el repositorio."""
    paths = []
    try:
        from morfeo.kit import get_kit_root

        paths.append(get_kit_root() / "scripts" / name)
    except Exception:
        pass
    paths.append(Path(__file__).resolve().parents[3] / "scripts" / name)
    return paths


def load_kit_script(name: str, required: tuple[str, ...]) -> Any:
    """Módulo del primer candidato que existe y expone alguna función de `required`.

    Un script ausente o que falla al importarse devuelve None. Solo se guarda en
    caché lo que cargó bien, por ruta y fecha de modificación: un script que
    aparece o cambia con el tablero abierto se toma en la siguiente lectura.
    """
    for path in _script_candidates(name):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        key = str(path)
        with _SCRIPT_LOCK:
            cached = _SCRIPT_CACHE.get(key)
            if cached and cached[0] == mtime:
                return cached[1]
            try:
                spec = importlib.util.spec_from_file_location(f"_morfeo_{path.stem}", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception:
                continue
            if any(callable(getattr(module, attr, None)) for attr in required):
                _SCRIPT_CACHE[key] = (mtime, module)
                return module
    return None


class ReviewFileError(Exception):
    """`revision.json` existe pero no se puede leer: nunca se sobrescribe."""


def _read_review(run_dir: Path) -> dict[str, Any]:
    path = run_dir / REVIEW_FILE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        raise ReviewFileError(
            f"{REVIEW_FILE.as_posix()} está dañado y no se puede leer; restáuralo o bórralo para reiniciar la revisión."
        )
    return data


def _write_review(run_dir: Path, review: dict[str, Any]) -> None:
    """Escritura atómica, como la revisión de los árboles."""
    path = run_dir / REVIEW_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".revision.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(review, indent=2, ensure_ascii=False))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read_cadena(run_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    """(cadena, error). Un archivo ausente no es un error: aún no se siembra."""
    path = run_dir / CADENA_FILE
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as err:
        return None, f"{CADENA_FILE.as_posix()} no es un JSON válido: {err}"
    if not isinstance(data, dict):
        return None, f"{CADENA_FILE.as_posix()} debe ser un objeto JSON."
    if data.get("schema") != CADENA_SCHEMA:
        return None, f"{CADENA_FILE.as_posix()} no declara el esquema {CADENA_SCHEMA} (declara {data.get('schema')!r})."
    return data, None


def _findings(run_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    module = load_kit_script(CADENA_SCRIPT, CADENA_RULE_NAMES)
    if module is None:
        return [], None
    fn = next(getattr(module, n) for n in CADENA_RULE_NAMES if callable(getattr(module, n, None)))
    try:
        raw = fn(run_dir)
    except Exception as err:
        return [], f"{CADENA_SCRIPT} no pudo revisar la cadena: {err}"
    found = []
    for f in raw if isinstance(raw, list) else []:
        if isinstance(f, dict):
            found.append({
                "severity": str(f.get("severity") or "warning"),
                "code": str(f.get("code") or ""),
                "message": str(f.get("message") or ""),
                "node": str(f.get("node") or ""),
            })
    return found, None


def _activities(cadena: dict[str, Any]):
    for oe in cadena.get("objetivos") or []:
        if not isinstance(oe, dict):
            continue
        for prod in oe.get("productos") or []:
            if not isinstance(prod, dict):
                continue
            for act in prod.get("actividades") or []:
                if isinstance(act, dict):
                    yield oe, act


def _total_costos(cadena: dict[str, Any]) -> float | int:
    total: float | int = 0
    for _, act in _activities(cadena):
        cost = act.get("costo")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            total += cost
    return total


def load_value_chain(run_dir: Path | str) -> dict[str, Any]:
    """Estado de la cadena para el tablero; nunca lanza hacia la capa HTTP."""
    run_dir = Path(run_dir)
    flujo = _detect_flujo(run_dir)
    result: dict[str, Any] = {
        "flujo": flujo, "disponible": False, "fuente": CADENA_FILE.as_posix(), "cadena": None,
        "hallazgos": [], "aprobado": False, "hash": None, "total_costos": None, "revision": None, "errores": [],
    }
    if flujo != "sgr":
        return result
    try:
        entry = _read_review(run_dir).get("cadena_valor")
        result["revision"] = entry if isinstance(entry, dict) else None
    except ReviewFileError as err:
        result["errores"].append(str(err))
    cadena, err = _read_cadena(run_dir)
    if err:
        result["errores"].append(err)
    if cadena is None:
        return result
    current = _hash(cadena)
    findings, err = _findings(run_dir)
    if err:
        result["errores"].append(err)
    revision = result["revision"] or {}
    result.update({
        "disponible": True,
        "cadena": cadena,
        "hash": current,
        "hallazgos": findings,
        "total_costos": _total_costos(cadena),
        "aprobado": bool(revision.get("aprobado")) and revision.get("hash") == current,
    })
    return result


def approve(run_dir: Path | str, expected_hash: str | None = None) -> dict[str, Any]:
    """Aprueba la cadena vigente. `expected_hash` es el que vio quien aprueba:
    si el archivo cambió desde entonces, la aprobación se rechaza."""
    run_dir = Path(run_dir)
    with _REVIEW_LOCK:
        try:
            review = _read_review(run_dir)
        except ReviewFileError as err:
            return {"ok": False, "error": str(err)}
        state = load_value_chain(run_dir)
        if state["flujo"] != "sgr":
            return {"ok": False, "error": "La cadena de valor solo existe en el flujo SGR."}
        if not state["disponible"]:
            error = "; ".join(state["errores"]) or (
                f"Todavía no hay cadena de valor: se siembra con scripts/{CADENA_SCRIPT} init "
                "después de aprobar los objetivos.")
            return {"ok": False, "error": error}
        if expected_hash and expected_hash != state["hash"]:
            return {"ok": False, "error": "La cadena cambió desde que la abriste: revisa la versión nueva antes de aprobarla."}
        errors = sorted({f["code"] for f in state["hallazgos"] if f.get("severity") == "error"})
        if errors:
            return {"ok": False, "error": "Corrige los hallazgos de error de la cadena antes de aprobarla: " + ", ".join(errors) + "."}
        fecha = datetime.now().isoformat(timespec="seconds")
        review["cadena_valor"] = {"aprobado": True, "hash": state["hash"], "fecha": fecha}
        _write_review(run_dir, review)
        return {"ok": True, "hash": state["hash"], "fecha": fecha}


def build_adjust_prompt(run_dir: Path | str, nota: Any) -> str:
    """Instrucción de una línea para la terminal del agente. Una nota vacía o una
    corrida del flujo base levantan `ValueError`."""
    run_dir = Path(run_dir)
    if not isinstance(nota, str) or not nota.strip():
        raise ValueError("La solicitud de ajuste está vacía: escribe qué cambiar en la cadena de valor.")
    if _detect_flujo(run_dir) != "sgr":
        raise ValueError("La cadena de valor solo existe en el flujo SGR.")
    nota = " ".join(nota.split())
    cadena = _workspace_path(run_dir, CADENA_FILE)
    run = f"proposals/{run_dir.name}" if run_dir.parent.name == "proposals" else "."
    return (
        f"Ajusta la cadena de valor SGR de la corrida activa según esta indicación del tablero: «{nota}». "
        f"Despacha a investigador para editar solo {cadena} con el esquema {CADENA_SCHEMA}: "
        "el texto de cada objetivo específico se copia literal del árbol de objetivos aprobado; los productos "
        "llevan el código <oe>.<p> y las actividades <oe>.<p>.<a>, consecutivos y coherentes con su padre; cada "
        "producto tiene al menos dos actividades técnicas y el último producto de cada objetivo una actividad de "
        "administración y una de supervisión; ningún nombre de actividad abre con un verbo vetado por la MGA; los "
        "meses quedan dentro de la duración y el costo nunca es negativo. "
        f"Después corre python3 scripts/{CADENA_SCRIPT} check {run}, corrige los hallazgos de error y avísame "
        "cuando el tablero muestre la nueva versión. Si el ajuste cambia un objetivo específico, pregúntame antes: "
        "viene del árbol de objetivos aprobado."
    )
