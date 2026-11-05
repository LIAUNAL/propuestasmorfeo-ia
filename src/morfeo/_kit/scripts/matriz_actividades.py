#!/usr/bin/env python3
"""Turn the activities workbook into a checked matrix and per-person packages.

SGR projects coordinate their researchers with a workbook: one sheet per
specific objective or activity, each with one or more blocks headed by

    Responsable | Tareas | Resultados | Medio de Verificación

Blocks may start at any column, sit under "Apunta a OE1" and "Actividad 2"
label rows, and repeat within a sheet. The responsible cell is usually merged
over the rows of that person, some of which are still empty. Optional
`Meses`/`Mes` and `Presupuesto` columns fill those fields. Headers match
without case or accents, so column order may vary. Sheets lacking the required
headers (instructions, notes) are listed under `hojas_omitidas`.

`importar` writes `artefactos/matriz_actividades.json`:

    {"fuente": "<file name>", "max_tareas": 5, "hojas_omitidas": [...],
     "actividades": [{"hoja", "oe", "objetivo", "actividad",
                      "responsables_sin_tareas": [...],
                      "tareas": [{"id", "responsable", "tarea", "resultado",
                                  "verificacion", "meses", "presupuesto"}]}],
     "avisos": [{"tipo", "mensaje"}]}

`id` is the product code leading the result (`OE1-1.5.2.1`), or null.
`responsables_sin_tareas` keeps people whose rows are still empty, because they
are the ones who most need a package.

`paquetes` writes one Markdown file per person into `artefactos/paquetes/`. A
cell naming several people ("A + B") reaches each package. Existing packages
with the same name are overwritten.

`chequear` validates the JSON structure and recomputes the warnings.

ID numbers, emails and links are dropped at import and again when packages are
rendered, so a hand-edited JSON cannot leak them. In the responsible column any
long number goes; elsewhere only numbers announced as an ID document or bare
runs of 8 to 10 digits, because a dotted figure there may be a real quantity.

Usage: matriz_actividades.py importar <RUN_ROOT> <archivo.xlsx> [--max-tareas 5] [--json]
       matriz_actividades.py paquetes <RUN_ROOT> [--json]
       matriz_actividades.py chequear <RUN_ROOT> [--json]
Exit codes: 0 ok (warnings allowed), 1 validation error, 2 missing/invalid input.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

MATRIX = Path("artefactos") / "matriz_actividades.json"
PACKAGES = Path("artefactos") / "paquetes"
DEFAULT_MAX_TASKS = 5
MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

REQUIRED = {"responsable": "responsable", "tareas": "tarea", "resultados": "resultado",
            "medio de verificacion": "verificacion"}
OPTIONAL = {"meses": "meses", "mes": "meses", "presupuesto": "presupuesto"}
TEXT_FIELDS = ("responsable", "tarea", "resultado", "verificacion")
TASK_KEYS = (*TEXT_FIELDS, "id", "meses", "presupuesto")

OBJECTIVE_LABEL_RE = re.compile(r"^apunta a\b")
ACTIVITY_LABEL_RE = re.compile(r"^actividad\s*(?:oe\s*-?\s*\d+)?\s*-?\s*(?:\d+|n)?$")
OE_RE = re.compile(r"\boe\s*-?\s*(\d+)", re.IGNORECASE)
SHEET_OE_RE = re.compile(r"^oe\s*-?\s*(\d+)", re.IGNORECASE)
PRODUCT_ID_RE = re.compile(r"^\s*(OE\d+-\d+(?:\.\d+)*)")
PLACEHOLDER_RE = re.compile(r"\bX{2,}\b|\bx{3,}\b|\.{3,}|…")
NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
CELL_REF_RE = re.compile(r"^([A-Z]+)(\d+)$")

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LINK_RE = re.compile(
    r"\b(?:https?://|www\.)\S+"
    r"|\b(?:orcid\.org|linkedin\.com|researchgate\.net|scholar\.google\.[a-z.]+|scienti\.minciencias\.gov\.co)/\S*"
    r"|\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b",
    re.IGNORECASE)
ANNOUNCED_ID_RE = re.compile(
    r"\b(?:c\.?\s*c\.?|c[eé]dula(?:\s+de\s+ciudadan[ií]a)?|documento(?:\s+de\s+identidad)?|identificaci[oó]n)"
    r"\s*(?:n[o°º.]*\s*)?[:#]?\s*\d[\d.\s]{4,}\d",
    re.IGNORECASE)
BARE_ID_RE = re.compile(r"(?<![\w.,$-])\d{8,10}(?![\w-])")
ANY_NUMBER_RE = re.compile(r"(?<![\w.-])(?:\d{6,12}|\d{1,3}(?:[.\s]\d{3}){1,3})(?![\w-])")
# Cell layouts separate name, team and role with hyphens, line breaks or runs of spaces.
BREAK_RE = re.compile(r"\.?[ \t]*\n\s*|\.\s{2,}|\s{3,}")
DASH_RE = re.compile(r"\s+[-–—]\s*|\s*[-–—]\s+")
PEOPLE_RE = re.compile(r"\s*[+/;]\s*|\s+y\s+")
PROSE_DASH_RE = re.compile(r"\s*(?:—|-{2,})\s*")


class InputError(Exception):
    pass


def norm(text: str) -> str:
    """Case- and accent-free form used to compare headers and repeated text."""
    plain = unicodedata.normalize("NFKD", text)
    return " ".join("".join(c for c in plain if not unicodedata.combining(c)).casefold().split())


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(name)).strip("-")[:80].rstrip("-")


def tidy(text: str) -> str:
    text = " ".join(text.split())
    text = re.sub(r"\s+([,;:.])", r"\1", text)
    text = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", text)
    return text.strip(" ,;:-")


def scrub(text: str, responsible: bool = False) -> str:
    """Drop ID numbers, emails and links; a clean text comes back unchanged."""
    clean = ANNOUNCED_ID_RE.sub(" ", LINK_RE.sub(" ", EMAIL_RE.sub(" ", text)))
    clean = (ANY_NUMBER_RE if responsible else BARE_ID_RE).sub(" ", clean)
    return text if clean == text else tidy(clean)


def responsible_layout(raw: str) -> str:
    """Canonical "Name - Team - Role" form of a responsible cell."""
    return tidy(DASH_RE.sub(" - ", BREAK_RE.sub(" - ", raw.strip())))


def people_in(responsible: str) -> list[tuple[str, str]]:
    """(slug, name) of each person; only the name part may list several."""
    head = responsible.split(" - ")[0]
    people = []
    for name in PEOPLE_RE.split(head):
        name = name.strip(" .")
        if slugify(name):
            people.append((slugify(name), name))
    return people


# --- workbook reading ------------------------------------------------------

def column_index(letters: str) -> int:
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - 64
    return index - 1


def split_ref(ref: str) -> tuple[int, int]:
    match = CELL_REF_RE.match(ref)
    if not match:
        raise ValueError(f"referencia de celda inválida: {ref}")
    return int(match.group(2)), column_index(match.group(1))


def string_item(item: ET.Element) -> str:
    """Text of a <si> or <is>: plain or rich runs, leaving out phonetic hints."""
    parts = [node.text or "" for node in item.findall(f"{MAIN}t")]
    parts += [node.text or "" for run in item.findall(f"{MAIN}r") for node in run.findall(f"{MAIN}t")]
    return "".join(parts)


def cell_text(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        inline = cell.find(f"{MAIN}is")
        return string_item(inline) if inline is not None else ""
    value = cell.find(f"{MAIN}v")
    if value is None or value.text is None or kind == "e":
        return ""
    if kind == "s":
        return shared[int(value.text)]
    if kind in ("str", "b"):
        return value.text
    number = float(value.text)
    return str(int(number)) if number.is_integer() else repr(number)


def read_grid(root: ET.Element, shared: list[str]) -> dict[int, dict[int, str]]:
    """Non-empty cells by row and column, merged rows filled down from their anchor."""
    grid: dict[int, dict[int, str]] = {}
    row_number = 0
    for row in root.iter(f"{MAIN}row"):
        row_number = int(row.get("r") or row_number + 1)
        column = -1
        for cell in row.findall(f"{MAIN}c"):
            ref = cell.get("r")
            column = split_ref(ref)[1] if ref else column + 1
            text = cell_text(cell, shared)
            if text.strip():
                grid.setdefault(row_number, {})[column] = text
    for merge in root.iter(f"{MAIN}mergeCell"):
        first, _, last = (merge.get("ref") or "").partition(":")
        if not last:
            continue
        top, left = split_ref(first)
        bottom = split_ref(last)[0]
        anchor = grid.get(top, {}).get(left)
        if anchor is None:
            continue
        # Only downwards: a label merged across columns must not become a row of cells.
        for number in range(top + 1, bottom + 1):
            grid.setdefault(number, {}).setdefault(left, anchor)
    return grid


def read_workbook(path: Path) -> list[tuple[str, dict[int, dict[int, str]]]]:
    if not path.is_file():
        raise InputError(f"no existe el archivo {path.name}")
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            shared = []
            if "xl/sharedStrings.xml" in names:
                table = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = [string_item(item) for item in table.findall(f"{MAIN}si")]
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            links = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            targets = {link.get("Id"): link.get("Target") or "" for link in links}
            sheets = []
            for sheet in workbook.iter(f"{MAIN}sheet"):
                target = targets[sheet.get(REL_ID)]
                member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(f"xl/{target}")
                sheets.append((sheet.get("name") or "", read_grid(ET.fromstring(archive.read(member)), shared)))
    except (zipfile.BadZipFile, ET.ParseError, KeyError, ValueError, IndexError) as exc:
        raise InputError(f"{path.name} no es un libro xlsx legible: {exc}") from exc
    return sheets


# --- sheet parsing ---------------------------------------------------------

def header_columns(row: dict[int, str]) -> dict[str, int] | None:
    columns: dict[str, int] = {}
    for column, text in sorted(row.items()):
        field = {**REQUIRED, **OPTIONAL}.get(norm(text))
        if field:
            columns.setdefault(field, column)
    return columns if set(REQUIRED.values()) <= set(columns) else None


def text_after(row: dict[int, str], column: int) -> str:
    return next((text for col, text in sorted(row.items()) if col > column), "")


def scalar(text: str | None) -> str | int | float | None:
    if text is None or not text.strip():
        return None
    text = text.strip()
    if NUMBER_RE.match(text):
        return float(text) if "." in text else int(text)
    return " ".join(text.split())


def parse_sheet(name: str, grid: dict[int, dict[int, str]]) -> tuple[list[dict], int]:
    """Activities of one sheet and how many cells lost personal data."""
    activities: list[dict] = []
    activity: dict | None = None
    columns: dict[str, int] | None = None
    oe: str | None = None
    objective: str | None = None
    label: tuple[str, str] | None = None
    responsible = ""
    scrubbed = 0

    def field_text(text: str) -> str:
        nonlocal scrubbed
        plain = " ".join(text.split())
        clean = scrub(plain)
        scrubbed += clean != plain
        return clean

    def responsible_field(text: str) -> str:
        nonlocal scrubbed
        layout = responsible_layout(text)
        clean = scrub(layout, responsible=True)
        scrubbed += clean != layout
        return clean

    for number in sorted(grid):
        row = grid[number]
        labels = [(col, text) for col, text in sorted(row.items())
                  if columns is None or col == columns["responsable"]]
        marker = next(((col, text) for col, text in labels
                       if OBJECTIVE_LABEL_RE.match(norm(text)) or ACTIVITY_LABEL_RE.match(norm(text))), None)
        if marker:
            col, text = marker
            columns = None
            if OBJECTIVE_LABEL_RE.match(norm(text)):
                found = OE_RE.search(text)
                oe = f"OE{found.group(1)}" if found else oe
                objective = field_text(text_after(row, col)) or None
            else:
                label = (text, field_text(text_after(row, col)))
            continue
        found_columns = header_columns(row)
        if found_columns:
            columns = found_columns
            responsible = ""
            if label or activity is None:
                raw_label, title = label or ("", "")
                by_label = OE_RE.search(raw_label)
                by_sheet = SHEET_OE_RE.match(name)
                sheet_oe = f"OE{(by_label or by_sheet).group(1)}" if by_label or by_sheet else None
                activity = {"hoja": name, "oe": oe or sheet_oe, "objetivo": objective,
                            "actividad": title or " ".join(raw_label.split()) or name,
                            "responsables_sin_tareas": [], "tareas": []}
                activities.append(activity)
                label = None
            continue
        if columns is None or activity is None:
            continue
        cell = row.get(columns["responsable"])
        if cell:
            responsible = responsible_field(cell)
        values = {key: field_text(row.get(columns[key], "")) for key in ("tarea", "resultado", "verificacion")}
        if not any(values.values()):
            pending = activity["responsables_sin_tareas"]
            if responsible and responsible not in pending:
                pending.append(responsible)
            continue
        identifier = PRODUCT_ID_RE.match(values["resultado"]) or PRODUCT_ID_RE.match(values["tarea"])
        activity["tareas"].append({
            "id": identifier.group(1) if identifier else None,
            "responsable": responsible,
            **values,
            "meses": scalar(row.get(columns["meses"])) if "meses" in columns else None,
            "presupuesto": scalar(row.get(columns["presupuesto"])) if "presupuesto" in columns else None,
        })
    for item in activities:
        served = {task["responsable"] for task in item["tareas"]}
        item["responsables_sin_tareas"] = [p for p in item["responsables_sin_tareas"] if p not in served]
    return activities, scrubbed


# --- warnings --------------------------------------------------------------

def warning(kind: str, message: str) -> dict:
    return {"tipo": kind, "mensaje": message}


def where(activity: dict) -> str:
    return f"hoja {activity['hoja']}, «{activity['actividad']}»"


def short(text: str, size: int = 60) -> str:
    return text if len(text) <= size else text[:size].rstrip() + "…"


def placeholder_warnings(activity: dict) -> list[dict]:
    found = []
    for label, text in (("objetivo", activity.get("objetivo")), ("actividad", activity["actividad"])):
        if text and PLACEHOLDER_RE.search(text):
            found.append(warning("relleno", f"{where(activity)}: texto de relleno en {label}"))
    for person in activity.get("responsables_sin_tareas", []):
        if PLACEHOLDER_RE.search(person):
            found.append(warning("relleno", f"{where(activity)}: texto de relleno en responsable"))
    for position, task in enumerate(activity["tareas"], start=1):
        for field in TEXT_FIELDS:
            if PLACEHOLDER_RE.search(task[field]):
                found.append(warning("relleno", f"{where(activity)}, tarea {position}: texto de relleno en {field}"))
        if not task["resultado"]:
            found.append(warning("relleno", f"{where(activity)}, tarea {position}: resultado vacío"))
    return found


def collect_warnings(data: dict) -> list[dict]:
    limit = data.get("max_tareas", DEFAULT_MAX_TASKS)
    found: list[dict] = []
    tasks = [(activity, task) for activity in data["actividades"] for task in activity["tareas"]]
    for activity in data["actividades"]:
        counts: Counter[str] = Counter()
        names: dict[str, str] = {}
        for position, task in enumerate(activity["tareas"], start=1):
            people = people_in(task["responsable"])
            if not people:
                found.append(warning("sin_responsable", f"{where(activity)}, tarea {position}: no tiene responsable"))
            for slug, name in people:
                counts[slug] += 1
                names.setdefault(slug, name)
            if task["resultado"] and not task["verificacion"]:
                found.append(warning("sin_verificacion",
                                     f"{where(activity)}, tarea {position}: el producto no tiene medio de verificación"))
        for slug, count in counts.items():
            if count > limit:
                found.append(warning("tareas_de_mas", f"{names[slug]} tiene {count} tareas en {where(activity)}; "
                                                      f"el máximo es {limit}"))
        if activity.get("responsables_sin_tareas") or not activity["tareas"]:
            pending = len(activity.get("responsables_sin_tareas", []))
            found.append(warning("sin_tareas", f"{where(activity)}: {pending} responsables sin tareas diligenciadas"
                                 if pending else f"{where(activity)}: la actividad no tiene tareas"))
        found.extend(placeholder_warnings(activity))
    without_months = sum(task["meses"] is None for _, task in tasks)
    without_budget = sum(task["presupuesto"] is None for _, task in tasks)
    if without_months or without_budget:
        found.append(warning("meses_presupuesto", f"{without_months} de {len(tasks)} tareas sin meses y "
                                                  f"{without_budget} de {len(tasks)} sin presupuesto"))
    for field in ("tarea", "resultado", "verificacion"):
        seen: dict[str, list[dict]] = {}
        for activity, task in tasks:
            if task[field]:
                seen.setdefault(norm(task[field]), []).append({"hoja": activity["hoja"], "texto": task[field]})
        for rows in seen.values():
            if len(rows) > 1:
                sheets = ", ".join(dict.fromkeys(row["hoja"] for row in rows))
                found.append(warning("texto_repetido", f"«{short(rows[0]['texto'])}» se repite en {len(rows)} filas "
                                                       f"de la columna {field} (hojas: {sheets})"))
    ids = Counter(task["id"] for _, task in tasks if task["id"])
    for identifier, count in ids.items():
        if count > 1:
            sheets = ", ".join(dict.fromkeys(a["hoja"] for a, t in tasks if t["id"] == identifier))
            found.append(warning("id_duplicado", f"el ID {identifier} aparece {count} veces (hojas: {sheets})"))
    return found


# --- validation ------------------------------------------------------------

def is_scalar(value: object) -> bool:
    return value is None or (isinstance(value, (str, int, float)) and not isinstance(value, bool))


def task_errors(task: object, place: str) -> list[str]:
    if not isinstance(task, dict):
        return [f"{place}: debe ser un objeto"]
    errors = [f"{place}: falta la clave {key}" for key in TASK_KEYS if key not in task]
    errors += [f"{place}: {key} debe ser texto" for key in TEXT_FIELDS
               if key in task and not isinstance(task[key], str)]
    if "id" in task and not (task["id"] is None or isinstance(task["id"], str)):
        errors.append(f"{place}: id debe ser texto o null")
    errors += [f"{place}: {key} debe ser número, texto o null" for key in ("meses", "presupuesto")
               if key in task and not is_scalar(task[key])]
    return errors


def structure_errors(data: object) -> list[str]:
    if not isinstance(data, dict):
        return ["la matriz debe ser un objeto JSON"]
    errors = []
    if not isinstance(data.get("fuente"), str):
        errors.append("falta 'fuente' como texto")
    for key in ("avisos", "hojas_omitidas"):
        if not isinstance(data.get(key), list):
            errors.append(f"falta '{key}' como lista")
    limit = data.get("max_tareas", DEFAULT_MAX_TASKS)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        errors.append("'max_tareas' debe ser un entero mayor que cero")
    activities = data.get("actividades")
    if not isinstance(activities, list) or not activities:
        return [*errors, "'actividades' debe ser una lista no vacía"]
    for position, activity in enumerate(activities, start=1):
        place = f"actividad {position}"
        if not isinstance(activity, dict):
            errors.append(f"{place}: debe ser un objeto")
            continue
        errors += [f"{place}: falta la clave {key}" for key in ("hoja", "oe", "actividad", "tareas") if key not in activity]
        for key in ("hoja", "actividad"):
            if key in activity and not isinstance(activity[key], str):
                errors.append(f"{place}: {key} debe ser texto")
        for key in ("oe", "objetivo"):
            if not (activity.get(key) is None or isinstance(activity[key], str)):
                errors.append(f"{place}: {key} debe ser texto o null")
        pending = activity.get("responsables_sin_tareas", [])
        if not isinstance(pending, list) or not all(isinstance(person, str) for person in pending):
            errors.append(f"{place}: responsables_sin_tareas debe ser una lista de textos")
        tasks = activity.get("tareas")
        if "tareas" in activity and not isinstance(tasks, list):
            errors.append(f"{place}: tareas debe ser una lista")
        elif isinstance(tasks, list):
            for number, task in enumerate(tasks, start=1):
                errors += task_errors(task, f"{place}, tarea {number}")
    return errors


def load_matrix(root: Path) -> object:
    path = root / MATRIX
    if not path.is_file():
        raise InputError(f"no existe {MATRIX.as_posix()}; corra primero 'importar'")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InputError(f"{MATRIX.as_posix()} no es JSON válido: {exc}") from exc


# --- packages --------------------------------------------------------------

def rendered(text: str | None, responsible: bool = False) -> str:
    """Cell text as it may appear in a package."""
    clean = scrub(" ".join((text or "").split()), responsible)
    return PROSE_DASH_RE.sub(", ", clean)


def table_cell(text: str) -> str:
    return rendered(text).replace("|", "\\|")


def task_block(number: int, task: dict | None) -> list[str]:
    title = rendered(task["tarea"]) if task else ""
    product = table_cell(task["resultado"]) if task else ""
    check = table_cell(task["verificacion"]) if task else ""
    heading = f"### Tarea {number}. {title}".rstrip(" .") if title else f"### Tarea {number}"
    return [heading, "", "Método (uno o dos párrafos):", "", "", "",
            "| Productos esperados | Verificación |", "|---|---|", f"| {product} | {check} |", ""]


def package_text(name: str, entries: list[dict], source: str, limit: int) -> str:
    lines = [
        f"# Paquete de tareas de {rendered(name, responsible=True)}",
        "",
        f"Tareas a su cargo según la matriz de actividades ({rendered(source)}).",
        "",
        "## Cómo diligenciarlo",
        "",
        f"- Cada responsable lleva máximo {limit} tareas por actividad.",
        "- Piense cada tarea desde su producto: qué se entrega y cómo se verifica, y después cómo se hace.",
        "- Explique el método de cada tarea en uno o dos párrafos.",
        "- No incluya cédulas, correos ni enlaces personales.",
        "",
    ]
    for entry in entries:
        activity = entry["actividad"]
        prefix = f"{activity['oe']}. " if activity.get("oe") else ""
        lines += [f"## {prefix}{rendered(activity['actividad'])}", ""]
        if activity.get("objetivo"):
            lines += [f"Objetivo: {rendered(activity['objetivo'])}", ""]
        roles = "; ".join(dict.fromkeys(rendered(role, responsible=True) for role in entry["encargos"]))
        lines += [f"A cargo: {roles}", ""]
        if not entry["tareas"]:
            lines += ["Esta actividad aún no tiene tareas diligenciadas.", ""]
        for number, task in enumerate(entry["tareas"] or [None], start=1):
            lines += task_block(number, task)
    return "\n".join(lines).rstrip() + "\n"


def group_by_person(data: dict) -> tuple[dict[str, dict], int]:
    people: dict[str, dict] = {}
    orphans = 0

    def entry_for(slug: str, name: str, activity: dict, role: str) -> dict:
        person = people.setdefault(slug, {"nombre": name, "entradas": []})
        entries = person["entradas"]
        if not entries or entries[-1]["actividad"] is not activity:
            entries.append({"actividad": activity, "encargos": [], "tareas": []})
        entries[-1]["encargos"].append(role)
        return entries[-1]

    for activity in data["actividades"]:
        for task in activity["tareas"]:
            cell = scrub(task["responsable"], responsible=True)
            found = people_in(cell)
            orphans += not found
            for slug, name in found:
                entry_for(slug, name, activity, cell)["tareas"].append(task)
        for pending in activity.get("responsables_sin_tareas", []):
            cell = scrub(pending, responsible=True)
            for slug, name in people_in(cell):
                entry_for(slug, name, activity, cell)
    return people, orphans


# --- commands --------------------------------------------------------------

def run_root(path: Path) -> Path:
    root = path.resolve()
    if not root.is_dir():
        raise InputError(f"no existe la carpeta de la corrida: {path}")
    return root


def importar(root: Path, source: Path, limit: int) -> tuple[int, dict]:
    if limit < 1:
        raise InputError("--max-tareas debe ser mayor que cero")
    activities: list[dict] = []
    skipped: list[str] = []
    scrubbed = 0
    for name, grid in read_workbook(source):
        found, cleaned = parse_sheet(name, grid)
        if found:
            activities += found
            scrubbed += cleaned
        else:
            skipped.append(name)
    if not activities:
        raise InputError(f"ninguna hoja de {source.name} trae las columnas "
                         "Responsable, Tareas, Resultados y Medio de Verificación")
    data = {"fuente": source.name, "max_tareas": limit, "hojas_omitidas": skipped, "actividades": activities}
    data["avisos"] = collect_warnings(data)
    if scrubbed:
        data["avisos"].append(warning("datos_personales",
                                      f"se retiraron cédulas, correos o enlaces de {scrubbed} celdas"))
    target = root / MATRIX
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0, {"matriz": MATRIX.as_posix(), "actividades": len(activities),
               "tareas": sum(len(activity["tareas"]) for activity in activities),
               "hojas_omitidas": skipped, "avisos": data["avisos"]}


def paquetes(root: Path) -> tuple[int, dict]:
    data = load_matrix(root)
    errors = structure_errors(data)
    if errors:
        return 1, {"errores": errors}
    people, orphans = group_by_person(data)
    folder = root / PACKAGES
    folder.mkdir(parents=True, exist_ok=True)
    limit = data.get("max_tareas", DEFAULT_MAX_TASKS)
    written = []
    for slug, person in sorted(people.items()):
        name = f"{slug}.md"
        (folder / name).write_text(package_text(person["nombre"], person["entradas"], data["fuente"], limit),
                                   encoding="utf-8")
        written.append(name)
    return 0, {"carpeta": PACKAGES.as_posix(), "paquetes": written, "tareas_sin_responsable": orphans}


def chequear(root: Path) -> tuple[int, dict]:
    data = load_matrix(root)
    errors = structure_errors(data)
    if errors:
        return 1, {"errores": errors, "avisos": []}
    kept = [item for item in data["avisos"] if isinstance(item, dict) and item.get("tipo") == "datos_personales"]
    return 0, {"errores": [], "avisos": collect_warnings(data) + kept}


def print_result(command: str, code: int, result: dict) -> None:
    for error in result.get("errores", []):
        print(f"error: {error}", file=sys.stderr)
    if code:
        return
    if command == "importar":
        print(f"matriz: {result['matriz']} ({result['actividades']} actividades, {result['tareas']} tareas, "
              f"{len(result['hojas_omitidas'])} hojas omitidas)")
    elif command == "paquetes":
        print(f"paquetes: {len(result['paquetes'])} en {result['carpeta']}")
        if result["tareas_sin_responsable"]:
            print(f"tareas sin responsable, fuera de los paquetes: {result['tareas_sin_responsable']}")
    for item in result.get("avisos", []):
        print(f"aviso: {item['mensaje']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("run_root", type=Path, help="run folder (proposals/<run-id>)")
    shared.add_argument("--json", action="store_true", help="print the result as JSON")
    load = commands.add_parser("importar", parents=[shared], help=f"write {MATRIX.as_posix()} from the workbook")
    load.add_argument("archivo", type=Path, help="activities workbook (.xlsx)")
    load.add_argument("--max-tareas", type=int, default=DEFAULT_MAX_TASKS,
                      help="tasks allowed per person and activity (default: 5)")
    commands.add_parser("paquetes", parents=[shared], help=f"write one Markdown package per person in {PACKAGES.as_posix()}")
    commands.add_parser("chequear", parents=[shared], help="validate the matrix JSON")
    args = parser.parse_args(argv)
    try:
        root = run_root(args.run_root)
        if args.command == "importar":
            code, result = importar(root, args.archivo, args.max_tareas)
        else:
            code, result = (paquetes if args.command == "paquetes" else chequear)(root)
    except InputError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False) if args.json else f"error: {exc}",
              file=sys.stdout if args.json else sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print_result(args.command, code, result)
    return code


if __name__ == "__main__":
    sys.exit(main())
