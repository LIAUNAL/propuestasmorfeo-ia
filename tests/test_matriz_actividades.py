"""The activity matrix travels from Excel to per-person packages (odd/tasks/sgr-flujo-convocatorias.md, S5).

`scripts/matriz_actividades.py` reads the activities workbook with the standard
library only, writes `artefactos/matriz_actividades.json`, warns about what
still has to be filled, and generates one Markdown package per responsible
person. Fixtures are built in code, with invented names.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "matriz_actividades.py"
HEADERS = ["Responsable", "Tareas", "Resultados", "Medio de Verificación"]
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def col_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def write_xlsx(path: Path, sheets: list[dict], inline: bool = False, shared_xml: str | None = None) -> Path:
    """Minimal workbook: each sheet is {"name", "rows", "merges"?}; None leaves a cell out."""
    shared: list[str] = []
    parts: dict[str, str] = {}
    entries, rels = [], []
    for number, sheet in enumerate(sheets, start=1):
        xml_rows = []
        for r, row in enumerate(sheet["rows"], start=1):
            cells = []
            for c, value in enumerate(row):
                ref = f"{col_name(c)}{r}"
                if value is None:
                    continue
                if isinstance(value, (int, float)):
                    cells.append(f'<c r="{ref}"><v>{value}</v></c>')
                elif inline:
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
                else:
                    shared.append(value)
                    cells.append(f'<c r="{ref}" t="s"><v>{len(shared) - 1}</v></c>')
            xml_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
        merges = sheet.get("merges", [])
        merge_xml = ""
        if merges:
            refs = "".join(f'<mergeCell ref="{ref}"/>' for ref in merges)
            merge_xml = f'<mergeCells count="{len(merges)}">{refs}</mergeCells>'
        parts[f"xl/worksheets/sheet{number}.xml"] = (
            f'<worksheet xmlns="{MAIN_NS}"><sheetData>{"".join(xml_rows)}</sheetData>{merge_xml}</worksheet>')
        entries.append(f'<sheet name="{escape(sheet["name"])}" sheetId="{number}" r:id="rId{number}"/>')
        rels.append(f'<Relationship Id="rId{number}" Type="{REL_NS}/worksheet" Target="worksheets/sheet{number}.xml"/>')
    parts["xl/workbook.xml"] = (
        f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><sheets>{"".join(entries)}</sheets></workbook>')
    parts["xl/_rels/workbook.xml.rels"] = f'<Relationships xmlns="{PKG_NS}">{"".join(rels)}</Relationships>'
    if shared_xml is not None:
        parts["xl/sharedStrings.xml"] = shared_xml
    elif shared:
        items = "".join(f'<si><t xml:space="preserve">{escape(text)}</t></si>' for text in shared)
        parts["xl/sharedStrings.xml"] = f'<sst xmlns="{MAIN_NS}">{items}</sst>'
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return path


def activity_rows(tasks: list[list], oe: str = "OE1", label: str = "Actividad 1", name: str = "Analizar el territorio",
                  headers: list[str] | None = None) -> list[list]:
    return [[f"Apunta a {oe}", "Objetivo de prueba"], [label, name], headers or HEADERS, *tasks]


def full_task(person: str, n: int) -> list:
    return [person, f"Revisar la fuente {n}", f"OE1-1.{n}.1 Informe {n}", f"MV1-1.{n}.1 Acta {n}"]


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.run_root = self.root / "corrida"
        (self.run_root / "artefactos").mkdir(parents=True)
        self.matrix = self.run_root / "artefactos" / "matriz_actividades.json"
        self.packages = self.run_root / "artefactos" / "paquetes"

    def cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)

    def xlsx(self, *sheets: dict, **kwargs) -> Path:
        return write_xlsx(self.root / "matriz.xlsx", list(sheets), **kwargs)

    def imported(self, *sheets: dict, extra: tuple = (), **kwargs) -> dict:
        result = self.cli("importar", self.run_root, self.xlsx(*sheets, **kwargs), *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.matrix.read_text(encoding="utf-8"))

    def warnings(self, data: dict, kind: str) -> list[dict]:
        return [w for w in data["avisos"] if w["tipo"] == kind]


class ImportTest(Base):
    def test_writes_the_documented_shape_from_shared_strings(self) -> None:
        data = self.imported({"name": "OE1_Mapa", "rows": activity_rows([full_task("Ana Prueba - Equipo Uno", 1)])})
        self.assertEqual(data["fuente"], "matriz.xlsx")
        self.assertEqual(data["hojas_omitidas"], [])
        (activity,) = data["actividades"]
        self.assertEqual((activity["hoja"], activity["oe"], activity["actividad"]),
                         ("OE1_Mapa", "OE1", "Analizar el territorio"))
        self.assertEqual(activity["tareas"], [{
            "id": "OE1-1.1.1", "responsable": "Ana Prueba - Equipo Uno", "tarea": "Revisar la fuente 1",
            "resultado": "OE1-1.1.1 Informe 1", "verificacion": "MV1-1.1.1 Acta 1", "meses": None, "presupuesto": None,
        }])

    def test_the_objective_falls_back_to_the_label_and_then_the_sheet_name(self) -> None:
        by_label = [["Actividad OE3-2", "Evaluar"], HEADERS, full_task("Ana Prueba", 1)]
        by_sheet = [["Actividad 1", "Socializar"], HEADERS, full_task("Ana Prueba", 2)]
        data = self.imported({"name": "Hoja", "rows": by_label}, {"name": "OE4_Apropiacion", "rows": by_sheet})
        self.assertEqual([a["oe"] for a in data["actividades"]], ["OE3", "OE4"])

    def test_reads_inline_strings(self) -> None:
        data = self.imported({"name": "OE1", "rows": activity_rows([full_task("Ana Prueba", 1)])}, inline=True)
        self.assertEqual(data["actividades"][0]["tareas"][0]["tarea"], "Revisar la fuente 1")

    def test_rich_text_joins_runs_and_leaves_out_phonetic_hints(self) -> None:
        shared = (f'<sst xmlns="{MAIN_NS}">'
                  + "".join(f"<si><t>{text}</t></si>" for text in HEADERS)
                  + "<si><r><t>Ana </t></r><r><t>Prueba</t></r><rPh><t>ignorar</t></rPh></si>"
                  + "<si><t>Tarea</t></si></sst>")
        path = self.root / "rico.xlsx"
        write_xlsx(path, [{"name": "OE1", "rows": []}], shared_xml=shared)
        sheet = (f'<worksheet xmlns="{MAIN_NS}"><sheetData><row r="1">'
                 + "".join(f'<c r="{col_name(i)}1" t="s"><v>{i}</v></c>' for i in range(4))
                 + '</row><row r="2"><c r="A2" t="s"><v>4</v></c><c r="B2" t="s"><v>5</v></c></row>'
                 + "</sheetData></worksheet>")
        rewritten = self.root / "rico2.xlsx"
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(rewritten, "w") as target:
            for name in source.namelist():
                target.writestr(name, sheet if name.endswith("sheet1.xml") else source.read(name))
        self.assertEqual(self.cli("importar", self.run_root, rewritten).returncode, 0)
        data = json.loads(self.matrix.read_text(encoding="utf-8"))
        self.assertEqual(data["actividades"][0]["tareas"][0]["responsable"], "Ana Prueba")

    def test_headers_match_without_case_or_accents_in_any_order(self) -> None:
        headers = ["MEDIO DE VERIFICACION", "presupuesto", "Tareas", "mes", "RESPONSABLE", "resultados"]
        row = ["Acta", 2500000, "Revisar", "1-6", "Ana Prueba", "Informe"]
        task = self.imported({"name": "OE1", "rows": activity_rows([row], headers=headers)})["actividades"][0]["tareas"][0]
        self.assertEqual((task["responsable"], task["tarea"], task["resultado"], task["verificacion"]),
                         ("Ana Prueba", "Revisar", "Informe", "Acta"))
        self.assertEqual((task["meses"], task["presupuesto"]), ("1-6", 2500000))

    def test_meses_header_fills_months_and_extra_columns_are_ignored(self) -> None:
        headers = [*HEADERS, "Líneas Temáticas", "Meses"]
        row = ["Ana Prueba", "Revisar", "Informe", "Acta", "Una línea", 6]
        task = self.imported({"name": "OE1", "rows": activity_rows([row], headers=headers)})["actividades"][0]["tareas"][0]
        self.assertEqual(task["meses"], 6)
        self.assertNotIn("Una línea", json.dumps(task, ensure_ascii=False))

    def test_shifted_columns_merged_responsible_and_several_blocks_per_sheet(self) -> None:
        rows = [
            ["nota suelta", "Apunta a OE2", "Mejorar las herramientas"],
            [None, "Actividad OE2-1", "Diseñar el sistema"],
            [None, *HEADERS],
            [None, "Ana Prueba - Equipo Uno", "Tarea uno", "Producto uno", "Medio uno"],
            [None, None, "Tarea dos", "Producto dos", "Medio dos"],
            [None, None, None, None, None],
            [None, "Actividad OE2-2", "Implementar el sistema"],
            [None, *HEADERS],
            [None, "Luis Ensayo", "Tarea tres", "Producto tres", "Medio tres"],
        ]
        data = self.imported({"name": "OE2_Sistema", "rows": rows, "merges": ["C1:E1", "C2:E2", "B4:B6", "C7:E7"]})
        first, second = data["actividades"]
        self.assertEqual((first["oe"], first["actividad"]), ("OE2", "Diseñar el sistema"))
        self.assertEqual((second["oe"], second["actividad"]), ("OE2", "Implementar el sistema"))
        self.assertEqual([t["responsable"] for t in first["tareas"]], ["Ana Prueba - Equipo Uno"] * 2)
        self.assertEqual([t["tarea"] for t in second["tareas"]], ["Tarea tres"])

    def test_a_responsible_cell_left_blank_without_merge_inherits_the_row_above(self) -> None:
        rows = activity_rows([["Ana Prueba", "Tarea uno", "Producto uno", "Medio uno"],
                              [None, "Tarea dos", "Producto dos", "Medio dos"]])
        tasks = self.imported({"name": "OE1", "rows": rows})["actividades"][0]["tareas"]
        self.assertEqual(tasks[1]["responsable"], "Ana Prueba")

    def test_a_repeated_header_without_activity_label_continues_the_activity(self) -> None:
        rows = activity_rows([["Ana Prueba", "Tarea uno", "Producto uno", "Medio uno"]])
        rows += [HEADERS, ["Luis Ensayo", "Tarea dos", "Producto dos", "Medio dos"]]
        data = self.imported({"name": "OE1", "rows": rows})
        self.assertEqual(len(data["actividades"]), 1)
        self.assertEqual(len(data["actividades"][0]["tareas"]), 2)

    def test_sheets_without_required_headers_are_skipped_and_listed(self) -> None:
        data = self.imported(
            {"name": "InstruccionesGenerales", "rows": [["Indicaciones generales"], [None, 1, "Diligenciar"]]},
            {"name": "Incompleta", "rows": [["Responsable", "Tareas", "Resultados"], ["Ana", "Tarea", "Producto"]]},
            {"name": "OE1", "rows": activity_rows([full_task("Ana Prueba", 1)])},
        )
        self.assertEqual(data["hojas_omitidas"], ["InstruccionesGenerales", "Incompleta"])
        self.assertEqual([a["hoja"] for a in data["actividades"]], ["OE1"])

    def test_product_ids_are_read_and_rows_without_one_stay_null(self) -> None:
        rows = activity_rows([["Ana Prueba", "Tarea uno", "OE1-1.5.2.1. Documento técnico", "MV1-1.5.2.1. Tesis"],
                              [None, "Tarea dos", "Modelo calibrado", "Informe"]])
        tasks = self.imported({"name": "OE1", "rows": rows})["actividades"][0]["tareas"]
        self.assertEqual([t["id"] for t in tasks], ["OE1-1.5.2.1", None])

    def test_a_person_with_empty_rows_is_kept_as_pending_and_warned(self) -> None:
        rows = activity_rows([["Ana Prueba - Equipo Uno", None, None, None], [None, None, None, None]])
        data = self.imported({"name": "OE1", "rows": rows, "merges": ["A4:A5"]})
        activity = data["actividades"][0]
        self.assertEqual(activity["tareas"], [])
        self.assertEqual(activity["responsables_sin_tareas"], ["Ana Prueba - Equipo Uno"])
        self.assertEqual(len(self.warnings(data, "sin_tareas")), 1)


class WarningTest(Base):
    def test_too_many_tasks_counts_per_person_and_activity(self) -> None:
        tasks = [full_task("Ana Prueba - Equipo Uno" if n == 1 else None, n) for n in range(1, 7)]
        tasks.append(full_task("Luis Ensayo", 7))
        data = self.imported({"name": "OE1", "rows": activity_rows(tasks)})
        (warning,) = self.warnings(data, "tareas_de_mas")
        self.assertIn("Ana Prueba", warning["mensaje"])
        self.assertIn("6", warning["mensaje"])

    def test_max_tareas_changes_the_limit(self) -> None:
        tasks = [full_task("Ana Prueba", 1), full_task(None, 2), full_task(None, 3)]
        sheet = {"name": "OE1", "rows": activity_rows(tasks)}
        self.assertEqual(self.warnings(self.imported(sheet), "tareas_de_mas"), [])
        self.assertEqual(len(self.warnings(self.imported(sheet, extra=("--max-tareas", "2")), "tareas_de_mas")), 1)

    def test_missing_months_and_budget_give_one_aggregated_warning(self) -> None:
        tasks = [full_task("Ana Prueba", n) for n in range(1, 5)]
        (warning,) = self.warnings(self.imported({"name": "OE1", "rows": activity_rows(tasks)}), "meses_presupuesto")
        self.assertIn("4 de 4", warning["mensaje"])

    def test_a_zero_budget_is_a_value_not_a_gap(self) -> None:
        headers = [*HEADERS, "Meses", "Presupuesto"]
        row = [*full_task("Ana Prueba", 1), "1-3", 0]
        data = self.imported({"name": "OE1", "rows": activity_rows([row], headers=headers)})
        self.assertEqual(data["actividades"][0]["tareas"][0]["presupuesto"], 0)
        self.assertEqual(self.warnings(data, "meses_presupuesto"), [])

    def test_placeholder_text_is_warned(self) -> None:
        rows = activity_rows([["Ana Prueba", "Revisar XXX", "Informe", "Acta"],
                              [None, "Otra tarea", "...", "Medio"],
                              [None, "Tarea sin producto", None, "Medio dos"],
                              ["Universidad XX", "Tarea tres", "Producto tres", "Medio tres"]],
                             name="Diseñar un sistema que abarque XXX")
        data = self.imported({"name": "OE1", "rows": rows})
        messages = [w["mensaje"] for w in self.warnings(data, "relleno")]
        self.assertEqual(len(messages), 5, messages)
        self.assertTrue(any("resultado vacío" in m for m in messages), messages)

    def test_placeholder_in_the_objective_is_warned(self) -> None:
        rows = activity_rows([full_task("Ana Prueba", 1)])
        rows[0][1] = "Generar conocimiento XXX"
        self.assertEqual(len(self.warnings(self.imported({"name": "OE1", "rows": rows}), "relleno")), 1)

    def test_a_word_with_x_is_not_a_placeholder(self) -> None:
        rows = activity_rows([["Ana Prueba", "Analizar México y XML", "Informe", "Acta"]])
        self.assertEqual(self.warnings(self.imported({"name": "OE1", "rows": rows}), "relleno"), [])

    def test_repeated_cell_text_across_rows_is_one_warning_per_text(self) -> None:
        rows = activity_rows([["Ana Prueba", "Tarea uno", "Modelos implementados", "Acta uno"],
                              [None, "Tarea dos", "Modelos  implementados", "Acta dos"],
                              [None, "Tarea tres", "modelos implementados", "Acta tres"]])
        (warning,) = self.warnings(self.imported({"name": "OE1", "rows": rows}), "texto_repetido")
        self.assertIn("3", warning["mensaje"])

    def test_product_without_verification_is_warned(self) -> None:
        rows = activity_rows([["Ana Prueba", "Tarea uno", "Producto", None]])
        self.assertEqual(len(self.warnings(self.imported({"name": "OE1", "rows": rows}), "sin_verificacion")), 1)

    def test_duplicate_ids_across_sheets_are_warned(self) -> None:
        data = self.imported({"name": "OE1_a", "rows": activity_rows([full_task("Ana Prueba", 1)])},
                             {"name": "OE1_b", "rows": activity_rows([["Luis Ensayo", "Otra", "OE1-1.1.1 Otro", "Otra acta"]])})
        (warning,) = self.warnings(data, "id_duplicado")
        self.assertIn("OE1-1.1.1", warning["mensaje"])

    def test_a_task_without_responsible_is_warned_and_left_out_of_packages(self) -> None:
        rows = activity_rows([[None, "Tarea huérfana", "Producto", "Medio"]])
        data = self.imported({"name": "OE1", "rows": rows})
        self.assertEqual(len(self.warnings(data, "sin_responsable")), 1)
        report = json.loads(self.cli("paquetes", self.run_root, "--json").stdout)
        self.assertEqual((report["paquetes"], report["tareas_sin_responsable"]), ([], 1))

    def test_a_complete_matrix_has_no_warnings(self) -> None:
        headers = [*HEADERS, "Meses", "Presupuesto"]
        rows = activity_rows([[*full_task("Ana Prueba", 1), "1-3", 100], [*full_task(None, 2), "4-6", 200]], headers=headers)
        self.assertEqual(self.imported({"name": "OE1", "rows": rows})["avisos"], [])


class PackageTest(Base):
    def packaged(self, *sheets: dict) -> dict[str, str]:
        self.imported(*sheets)
        result = self.cli("paquetes", self.run_root)
        self.assertEqual(result.returncode, 0, result.stderr)
        return {path.name: path.read_text(encoding="utf-8") for path in sorted(self.packages.glob("*"))}

    def test_one_file_per_person_with_tasks_slot_table_and_rules(self) -> None:
        files = self.packaged(
            {"name": "OE1_a", "rows": activity_rows([full_task("Ana Prueba - Equipo Uno", 1)])},
            {"name": "OE1_b", "rows": activity_rows([["Ana Prueba- Equipo Dos", "Tarea b", "Producto b", "Medio b"],
                                                     ["Luis Ensayo", "Tarea c", "Producto c", "Medio c"]],
                                                    name="Validar el modelo")},
        )
        self.assertEqual(sorted(files), ["ana-prueba.md", "luis-ensayo.md"])
        text = files["ana-prueba.md"]
        self.assertIn("Analizar el territorio", text)
        self.assertIn("Validar el modelo", text)
        self.assertIn("Revisar la fuente 1", text)
        self.assertNotIn("Tarea c", text)
        self.assertIn("uno o dos párrafos", text)
        self.assertIn("| Productos esperados | Verificación |", text)
        self.assertIn("| OE1-1.1.1 Informe 1 | MV1-1.1.1 Acta 1 |", text)
        self.assertIn("máximo 5 tareas", text)
        self.assertIn("desde su producto", text)

    def test_a_cell_naming_several_people_reaches_each_package(self) -> None:
        rows = activity_rows([["Ana Prueba + Luis Ensayo+ Eva Muestra", "Tarea común", "Producto", "Medio"]])
        files = self.packaged({"name": "OE1", "rows": rows})
        self.assertEqual(sorted(files), ["ana-prueba.md", "eva-muestra.md", "luis-ensayo.md"])
        self.assertTrue(all("Tarea común" in text for text in files.values()))

    def test_a_plus_sign_outside_the_name_does_not_create_a_person(self) -> None:
        rows = activity_rows([["Ana Prueba - Equipo Uno. Analizar Pob+infraestructura", "Tarea", "Producto", "Medio"]])
        self.assertEqual(sorted(self.packaged({"name": "OE1", "rows": rows})), ["ana-prueba.md"])

    def test_filenames_are_safe_slugs(self) -> None:
        rows = activity_rows([["../Ñandú Ávila/Ruiz", "Tarea", "Producto", "Medio"]])
        self.packaged({"name": "OE1", "rows": rows})
        names = [p.name for p in self.packages.iterdir()]
        self.assertTrue(names)
        self.assertTrue(all(re.fullmatch(r"[a-z0-9-]+\.md", name) for name in names), names)
        self.assertEqual(sorted(p.name for p in (self.run_root / "artefactos").iterdir()),
                         ["matriz_actividades.json", "paquetes"])

    def test_a_person_without_tasks_still_receives_a_package(self) -> None:
        rows = activity_rows([["Ana Prueba - Equipo Uno", None, None, None]])
        text = self.packaged({"name": "OE1", "rows": rows})["ana-prueba.md"]
        self.assertIn("Analizar el territorio", text)
        self.assertIn("| Productos esperados | Verificación |", text)

    def test_personal_data_never_reaches_json_or_packages(self) -> None:
        rows = activity_rows([
            ["Ana Prueba C.C. 1.036.222.333 ana.prueba@example.org https://scienti.minciencias.gov.co/cvlac/123 - Equipo Uno",
             "Revisar, contacto luis@example.org, cédula 71234567",
             "OE1-1.5.2.1. Informe para 1.000.000 habitantes, perfil orcid.org/0000-0002-1825-0097",
             "Acta 1036222333 en www.ejemplo.org/ana"]])
        data = self.imported({"name": "OE1", "rows": rows})
        self.assertEqual(len(self.warnings(data, "datos_personales")), 1)
        text = self.packaged({"name": "OE1", "rows": rows})["ana-prueba.md"]
        for content in (text, self.matrix.read_text(encoding="utf-8")):
            for secret in ("1.036.222.333", "1036222333", "71234567", "@example", "cvlac", "orcid", "www.ejemplo"):
                self.assertNotIn(secret, content)
            self.assertIn("OE1-1.5.2.1", content)
            self.assertIn("1.000.000 habitantes", content)

    def test_personal_data_added_to_the_json_by_hand_is_stripped_from_packages(self) -> None:
        self.imported({"name": "OE1", "rows": activity_rows([full_task("Ana Prueba", 1)])})
        data = json.loads(self.matrix.read_text(encoding="utf-8"))
        data["actividades"][0]["tareas"][0]["tarea"] = "Escribir a ana@example.org"
        self.matrix.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.cli("paquetes", self.run_root).returncode, 0)
        self.assertNotIn("@example", (self.packages / "ana-prueba.md").read_text(encoding="utf-8"))

    def test_cell_text_cannot_break_the_table_or_bring_em_dashes(self) -> None:
        rows = activity_rows([["Ana Prueba", "Tarea — con inciso", "Modelo | versión\ndos", "Medio -- final"]])
        text = self.packaged({"name": "OE1", "rows": rows})["ana-prueba.md"]
        self.assertNotIn("—", text)
        self.assertNotIn("--", text.replace("|---|---|", ""))
        self.assertIn("| Modelo \\| versión dos |", text)

    def test_the_limit_in_the_package_follows_max_tareas(self) -> None:
        sheet = {"name": "OE1", "rows": activity_rows([full_task("Ana Prueba", 1)])}
        self.imported(sheet, extra=("--max-tareas", "3"))
        self.assertEqual(self.cli("paquetes", self.run_root).returncode, 0)
        self.assertIn("máximo 3 tareas", (self.packages / "ana-prueba.md").read_text(encoding="utf-8"))


class ExitCodeTest(Base):
    def sheet(self) -> dict:
        return {"name": "OE1", "rows": activity_rows([full_task("Ana Prueba", 1)])}

    def test_chequear_passes_with_warnings_only(self) -> None:
        self.imported(self.sheet())
        result = self.cli("chequear", self.run_root, "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["errores"], [])
        self.assertTrue(report["avisos"])

    def test_chequear_fails_on_structural_errors(self) -> None:
        self.imported(self.sheet())
        data = json.loads(self.matrix.read_text(encoding="utf-8"))
        del data["actividades"][0]["tareas"][0]["verificacion"]
        self.matrix.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = self.cli("chequear", self.run_root, "--json")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any("verificacion" in e for e in json.loads(result.stdout)["errores"]))

    def test_chequear_fails_when_activities_are_not_a_list(self) -> None:
        self.matrix.write_text(json.dumps({"fuente": "x", "actividades": {}, "avisos": []}), encoding="utf-8")
        self.assertEqual(self.cli("chequear", self.run_root).returncode, 1)

    def test_paquetes_refuses_a_structurally_broken_matrix(self) -> None:
        self.matrix.write_text(json.dumps({"fuente": "x", "actividades": [{}], "avisos": []}), encoding="utf-8")
        self.assertEqual(self.cli("paquetes", self.run_root).returncode, 1)
        self.assertFalse(self.packages.exists())

    def test_missing_or_invalid_json_exits_two(self) -> None:
        self.assertEqual(self.cli("chequear", self.run_root).returncode, 2)
        self.assertEqual(self.cli("paquetes", self.run_root).returncode, 2)
        self.matrix.write_text("{no es json", encoding="utf-8")
        self.assertEqual(self.cli("chequear", self.run_root).returncode, 2)
        self.assertEqual(self.cli("paquetes", self.run_root).returncode, 2)

    def test_importar_exits_two_on_bad_input_without_writing(self) -> None:
        not_xlsx = self.root / "falso.xlsx"
        not_xlsx.write_text("texto", encoding="utf-8")
        no_sheets = write_xlsx(self.root / "vacio.xlsx", [{"name": "Notas", "rows": [["Nada"]]}])
        good = self.xlsx(self.sheet())
        cases = [
            (self.run_root, self.root / "no-existe.xlsx"),
            (self.run_root, not_xlsx),
            (self.run_root, no_sheets),
            (self.root / "sin-corrida", good),
        ]
        for run_root, path in cases:
            with self.subTest(path=path.name, run_root=run_root.name):
                result = self.cli("importar", run_root, path, "--json")
                self.assertEqual(result.returncode, 2)
                self.assertIn("error", json.loads(result.stdout))
        self.assertFalse(self.matrix.exists())

    def test_importar_rejects_a_limit_below_one(self) -> None:
        self.assertEqual(self.cli("importar", self.run_root, self.xlsx(self.sheet()), "--max-tareas", "0").returncode, 2)

    def test_json_output_reports_the_counts(self) -> None:
        result = self.cli("importar", self.run_root, self.xlsx(self.sheet()), "--json")
        report = json.loads(result.stdout)
        self.assertEqual((report["actividades"], report["tareas"]), (1, 1))
        report = json.loads(self.cli("paquetes", self.run_root, "--json").stdout)
        self.assertEqual(report["paquetes"], ["ana-prueba.md"])


if __name__ == "__main__":
    unittest.main()
