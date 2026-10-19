"""Árboles de problemas y objetivos de una corrida, y su ciclo de revisión.

El árbol de problemas es la spec que Fase 1 ya produce
(`redaccion/specs/arbol_problemas.spec.json`). El árbol de objetivos es su
espejo según el marco lógico: cada causa pasa a ser un medio, cada subproblema
su objetivo específico, el problema central el objetivo general y cada efecto
un fin. Mientras el agente no escriba `artefactos/arboles/arbol_objetivos.json`,
el espejo se deriva aquí y toma el texto de §6 y §7 si ya existen; los medios y
los fines quedan pendientes, porque redactarlos es trabajo del agente y no de
una transformación mecánica.

La revisión vive en `artefactos/arboles/revision.json`. Cada aprobación guarda
el hash del contenido aprobado: si el árbol cambia después, la aprobación
caduca en lugar de seguir afirmando algo que ya no es cierto.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

PROBLEM_SPEC = Path("redaccion") / "specs" / "arbol_problemas.spec.json"
OBJECTIVES_FILE = Path("artefactos") / "arboles" / "arbol_objetivos.json"
REVIEW_FILE = Path("artefactos") / "arboles" / "revision.json"
TREE_KEYS = ("problemas", "objetivos")

# El tablero sirve con un servidor multihilo: leer, numerar y reescribir la
# revisión es una sola sección crítica, o dos solicitudes simultáneas toman el
# mismo número de iteración y una de las dos se pierde.
_REVIEW_LOCK = threading.Lock()


class ReviewFileError(Exception):
    """`revision.json` existe pero no se puede leer: nunca se sobrescribe."""


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _hash(tree: dict[str, Any]) -> str:
    raw = json.dumps(tree, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _latex_to_text(text: str) -> str:
    text = re.sub(r"\\(textbf|textit|emph|texttt|mbox)\{([^{}]*)\}", r"\2", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", "", text)
    text = text.replace("~", " ").replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()


def _strip_comments(tex: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in tex.splitlines())


def _general_objective(run_dir: Path) -> str | None:
    path = run_dir / "redaccion" / "sections" / "06_objetivo_general.tex"
    if not path.is_file():
        return None
    tex = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    tex = re.sub(r"\\(section|label)\*?\{[^{}]*\}", "", tex)
    text = _latex_to_text(tex)
    return text or None


def _specific_objectives(run_dir: Path) -> list[str]:
    path = run_dir / "redaccion" / "sections" / "07_objetivos_especificos.tex"
    if not path.is_file():
        return []
    tex = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    tex = re.split(r"\\end\{enumerate\}", tex)[0]
    items = re.split(r"\\item\b", tex)[1:]
    return [t for t in (_latex_to_text(i) for i in items) if t]


def _problem_tree(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "caption": spec.get("caption") or "",
        "groups": [
            {
                "id": g.get("id"),
                "title": g.get("title") or g.get("id"),
                "causes": [{"id": c.get("id"), "text": c.get("text")} for c in g.get("causes") or []],
            }
            for g in spec.get("groups") or []
        ],
        "trunk": spec.get("trunk") or {"label": "PROBLEMA CENTRAL", "text": None},
        "branches": [{"id": b.get("id"), "text": b.get("text")} for b in spec.get("branches") or []],
        "crown": spec.get("crown") or {"label": "SOLUCIÓN", "text": None},
    }


def _derive_objectives(problem: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    specificos = _specific_objectives(run_dir)
    groups = []
    medio = 0
    for i, g in enumerate(problem["groups"]):
        means = []
        for c in g["causes"]:
            medio += 1
            means.append({"id": f"m{medio}", "from": c["id"], "text": None})
        groups.append({
            "id": f"OE{i + 1}",
            "from": g["id"],
            "title": f"OE{i + 1}",
            "objective": specificos[i] if i < len(specificos) else None,
            "means": means,
        })
    return {
        "groups": groups,
        "trunk": {"label": "OBJETIVO GENERAL", "text": _general_objective(run_dir)},
        "branches": [
            {"id": f"f{i + 1}", "from": b["id"], "text": None}
            for i, b in enumerate(problem["branches"])
        ],
        "crown": {"label": "IMPACTO", "text": (problem.get("crown") or {}).get("text")},
    }


def _missing_objective_texts(tree: dict[str, Any]) -> list[str]:
    missing = []
    if not (tree.get("trunk") or {}).get("text"):
        missing.append("objetivo general")
    for g in tree.get("groups") or []:
        if not g.get("objective"):
            missing.append(f"objetivo {g.get('id')}")
        missing += [f"medio {m.get('id')}" for m in g.get("means") or [] if not m.get("text")]
    missing += [f"fin {b.get('id')}" for b in tree.get("branches") or [] if not b.get("text")]
    return missing


def _read_review(run_dir: Path) -> dict[str, Any]:
    """Lee la revisión. Un archivo dañado levanta ReviewFileError en lugar de
    leerse como vacío: tratarlo como vacío borraría en la siguiente escritura
    todas las aprobaciones e iteraciones."""
    path = run_dir / REVIEW_FILE
    data: dict[str, Any] = {}
    if path.is_file():
        data = _read_json(path)
        if data is None:
            raise ReviewFileError(
                f"{REVIEW_FILE.as_posix()} está dañado y no se puede leer; restáuralo o bórralo para reiniciar la revisión."
            )
    return {k: data.get(k) or {"iterations": []} for k in TREE_KEYS}


def _write_review(run_dir: Path, review: dict[str, Any]) -> None:
    """Escritura atómica: archivo temporal en la misma carpeta y `os.replace`,
    de modo que un corte a mitad de escritura nunca deja el JSON a medias."""
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


def _validate_comments(comments: Any) -> list[dict[str, str]] | None:
    """Comentarios por nodo: lista de objetos con `node` y `text` de texto."""
    if comments is None:
        return []
    if not isinstance(comments, list):
        return None
    valid = []
    for c in comments:
        if not isinstance(c, dict) or not isinstance(c.get("text"), str) or not isinstance(c.get("node", ""), str):
            return None
        if c["text"].strip():
            valid.append({"node": c.get("node") or "", "text": c["text"]})
    return valid


def _review_status(entry: dict[str, Any], current_hash: str | None) -> dict[str, Any]:
    iterations = entry.get("iterations") or []
    if entry.get("approved_hash"):
        status = "aprobado" if entry["approved_hash"] == current_hash else "desactualizado"
    elif iterations:
        status = "por_revisar" if iterations[-1].get("hash") != current_hash else "en_ajuste"
    else:
        status = "pendiente"
    return {
        "status": status,
        "approved_at": entry.get("approved_at"),
        "iterations": iterations,
    }


def load_trees(run_dir: Path) -> dict[str, Any]:
    review_error = None
    try:
        review = _read_review(run_dir)
    except ReviewFileError as err:
        review_error = str(err)
        review = {k: {"iterations": []} for k in TREE_KEYS}
    spec = _read_json(run_dir / PROBLEM_SPEC)

    if spec is None:
        problem = {
            "available": False,
            "source": PROBLEM_SPEC.as_posix(),
            "hint": f"El árbol de problemas se construye en la Fase 1: disenador-tikz escribe {PROBLEM_SPEC.as_posix()} a partir de los subproblemas de §3.",
            "tree": None,
            "hash": None,
            "review": _review_status(review["problemas"], None),
        }
        objectives = {
            "available": False,
            "derived": True,
            "source": OBJECTIVES_FILE.as_posix(),
            "hint": "El árbol de objetivos se deriva del árbol de problemas: primero hay que construir ese.",
            "tree": None,
            "hash": None,
            "missing": [],
            "review": _review_status(review["objetivos"], None),
        }
        return {"problem": problem, "objectives": objectives, "stage": "sin_arbol", "review_error": review_error}

    ptree = _problem_tree(spec)
    phash = _hash(ptree)
    problem = {
        "available": True,
        "source": PROBLEM_SPEC.as_posix(),
        "hint": None,
        "tree": ptree,
        "hash": phash,
        "review": _review_status(review["problemas"], phash),
    }

    agent_tree = _read_json(run_dir / OBJECTIVES_FILE)
    otree = agent_tree if agent_tree is not None else _derive_objectives(ptree, run_dir)
    ohash = _hash(otree)
    objectives = {
        "available": True,
        "derived": agent_tree is None,
        "source": OBJECTIVES_FILE.as_posix(),
        "hint": None if agent_tree is not None else
            "Espejo propuesto del árbol de problemas: los medios y los fines los redacta el agente.",
        "tree": otree,
        "hash": ohash,
        "missing": _missing_objective_texts(otree),
        "review": _review_status(review["objetivos"], ohash),
    }

    if problem["review"]["status"] != "aprobado":
        stage = "problemas"
    elif objectives["review"]["status"] != "aprobado":
        stage = "objetivos"
    else:
        stage = "aprobados"
    return {"problem": problem, "objectives": objectives, "stage": stage, "review_error": review_error}


def _node_text(tree: dict[str, Any] | None, node_id: str) -> str | None:
    if not tree:
        return None
    for key in ("trunk", "crown"):
        if node_id == key:
            return (tree.get(key) or {}).get("text")
    for b in tree.get("branches") or []:
        if b.get("id") == node_id:
            return b.get("text")
    for g in tree.get("groups") or []:
        if g.get("id") == node_id:
            return g.get("objective") or g.get("title")
        for n in (g.get("causes") or []) + (g.get("means") or []):
            if n.get("id") == node_id:
                return n.get("text")
    return None


def _workspace_path(run_dir: Path, rel: Path) -> str:
    """Ruta que el agente puede abrir desde la raíz del espacio de trabajo."""
    if run_dir.parent.name == "proposals":
        return f"proposals/{run_dir.name}/{rel.as_posix()}"
    return rel.as_posix()


def record_feedback(run_dir: Path, tree: str, comments: Any, general: Any = "") -> dict[str, Any]:
    if tree not in TREE_KEYS:
        return {"ok": False, "error": f"Árbol desconocido: {tree}"}
    comments = _validate_comments(comments)
    if comments is None:
        return {"ok": False, "error": "Los comentarios deben ser una lista de objetos con «node» y «text» de texto."}
    if not isinstance(general, str):
        return {"ok": False, "error": "La indicación general debe ser texto."}
    general = general.strip()
    if not comments and not general:
        return {"ok": False, "error": "La solicitud de ajuste está vacía: comenta un nodo o escribe una indicación general."}

    with _REVIEW_LOCK:
        try:
            review = _read_review(run_dir)
        except ReviewFileError as err:
            return {"ok": False, "error": str(err)}
        trees = load_trees(run_dir)
        current = trees["problem"] if tree == "problemas" else trees["objectives"]
        return _record_feedback_locked(run_dir, tree, comments, general, current, review)


def _record_feedback_locked(
    run_dir: Path, tree: str, comments: list[dict[str, str]], general: str,
    current: dict[str, Any], review: dict[str, Any],
) -> dict[str, Any]:
    entry = review[tree]
    n = len(entry.get("iterations") or []) + 1
    now = datetime.now().isoformat(timespec="seconds")

    rel = Path("artefactos") / "arboles" / f"ajuste_{tree}_{n:02d}.md"
    nombre = "árbol de problemas" if tree == "problemas" else "árbol de objetivos"
    lines = [f"# Ajuste {n:02d} del {nombre}", "", f"Solicitado desde el tablero el {now}.", ""]
    if general:
        lines += ["## Indicación general", "", general, ""]
    if comments:
        lines += ["## Comentarios por nodo", ""]
        for c in comments:
            node = str(c.get("node") or "")
            actual = _node_text(current["tree"], node)
            # Los títulos llevan saltos de línea para la figura: en la lista van en una.
            actual = " ".join(actual.split()) if actual else actual
            lines.append(f"- **{node}**" + (f" (texto actual: «{actual}»)" if actual else "") + f": {str(c['text']).strip()}")
        lines.append("")
    path = run_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")

    entry.setdefault("iterations", []).append({
        "n": n,
        "at": now,
        "request": rel.as_posix(),
        "hash": current["hash"],
        "comments": len(comments),
    })
    entry.pop("approved_hash", None)
    entry.pop("approved_at", None)
    _write_review(run_dir, review)

    req = _workspace_path(run_dir, rel)
    if tree == "problemas":
        spec = _workspace_path(run_dir, PROBLEM_SPEC)
        prompt = (
            f"Ajusta el árbol de problemas de la corrida activa según {req}. "
            f"Despacha a disenador-tikz para editar solo {spec} (si aún no existe, que lo proponga desde los subproblemas de §3), "
            "corre python3 scripts/figura.py arbol_problemas y avísame cuando el tablero muestre la nueva versión. "
            "Si un ajuste cambia el problema central o los subproblemas de §3, pregúntame antes de tocar la sección."
        )
    else:
        obj = _workspace_path(run_dir, OBJECTIVES_FILE)
        prompt = (
            f"Ajusta el árbol de objetivos de la corrida activa según {req}. "
            f"Despacha a investigador para escribir {obj} con el esquema {{groups:[{{id,from,title,objective,means:[{{id,from,text}}]}}],trunk:{{label,text}},branches:[{{id,from,text}}],crown:{{label,text}}}}: "
            "cada causa del árbol de problemas se vuelve un medio, cada efecto un fin, el problema central el objetivo general y cada subproblema su objetivo específico, "
            "coherente con §6 y §7. Aplica estilo-natural-es. No modifiques §6 ni §7 sin preguntarme."
        )
    return {"ok": True, "request": rel.as_posix(), "prompt": prompt, "iteration": n}


def approve_tree(run_dir: Path, tree: str) -> dict[str, Any]:
    if tree not in TREE_KEYS:
        return {"ok": False, "error": f"Árbol desconocido: {tree}"}
    with _REVIEW_LOCK:
        try:
            review = _read_review(run_dir)
        except ReviewFileError as err:
            return {"ok": False, "error": str(err)}
        return _approve_tree_locked(run_dir, tree, review)


def _approve_tree_locked(run_dir: Path, tree: str, review: dict[str, Any]) -> dict[str, Any]:
    trees = load_trees(run_dir)
    current = trees["problem"] if tree == "problemas" else trees["objectives"]
    if not current["available"]:
        return {"ok": False, "error": current["hint"]}
    if tree == "objetivos":
        if trees["problem"]["review"]["status"] != "aprobado":
            return {"ok": False, "error": "Primero hay que aprobar el árbol de problemas: el de objetivos es su espejo."}
        if current["missing"]:
            return {"ok": False, "error": "Faltan textos por redactar (" + ", ".join(current["missing"]) + "); pide al agente que complete los medios y los fines."}

    review[tree]["approved_hash"] = current["hash"]
    review[tree]["approved_at"] = datetime.now().isoformat(timespec="seconds")
    _write_review(run_dir, review)
    return {"ok": True, "approved_at": review[tree]["approved_at"]}
