"""Pestaña «Productos e indicadores» (odd/tasks/sgr-productos-indicadores.md, S1 y S6).

El script del kit `productos_sgr.py` se sustituye por un doble escrito en una
carpeta temporal y se carga por la misma importación dinámica que usa el
tablero para `cadena_valor_sgr.py`.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from morfeo.core import value_chain
from morfeo.core.products import approve, build_adjust_prompt, load_products

PRODUCTOS = {
    "schema": "morfeo.productos-sgr/v1",
    "talento": [
        {"categoria": "joven_investigador", "cantidad": 4, "entidad": "E1", "perfil": "Joven investigador",
         "formacion": "Pregrado en ingeniería", "actividades": ["1.1.1"], "duracion_meses": 12,
         "valor_mensual": 3000000, "producto_final": "Informe"},
        {"categoria": "maestria", "cantidad": 2, "entidad": "E1", "perfil": "Estudiante de maestría",
         "formacion": "Ingeniería", "actividades": ["1.1.2"], "duracion_meses": 24,
         "valor_mensual": 4000000, "producto_final": "Tesis"},
    ],
    "productos_ctei": [
        {"tipo": "nuevo_conocimiento", "subtipo": "Artículo", "categoria": "A", "cantidad": 2, "adicional": True,
         "producto_cadena": "1.1", "descripcion": "Artículos Q1"},
    ],
    "divulgacion": {"introduccion": "", "publicos": ["Comunidad"], "medios": ["Radio"], "productos": ["Podcast"],
                    "responsable": "E1", "cronograma": [{"mes": 6, "accion": "Emisión"}], "costeada": True},
    "indicadores_gestion": [
        {"indicador": "Informes de supervisión", "codigo": None, "meta": 8, "unidad": "Número",
         "formula": "Informes entregados", "tipo_fuente": "Documento", "periodicidad": "Trimestral"},
    ],
}

CADENA = {
    "schema": "morfeo.cadena-valor-sgr/v1",
    "duracion_meses": 24,
    "objetivos": [
        {"id": "OE1", "texto": "Medir la calidad del agua", "productos": [
            {"codigo": "1.1", "codigo_dnp": "3906001", "nombre": "Servicio de monitoreo",
             "medido_a_traves_de": "Número de sistemas", "indicador": "Sistemas implementados", "unidad": "Número",
             "meta": 2, "actividades": [{"codigo": "1.1.1", "nombre": "Levantar datos"},
                                        {"codigo": "1.1.2", "nombre": "Transferir"}]}]},
        {"id": "OE2", "texto": "Transferir", "productos": [
            {"codigo": "2.1", "codigo_dnp": None, "nombre": "Documentos", "medido_a_traves_de": "",
             "indicador": "", "unidad": "", "meta": None, "actividades": []}]},
    ],
}

ALIANZA = {"schema": "morfeo.alianza-sgr/v1", "entidades": [
    {"id": "E1", "nombre": "Universidad Nacional"}, {"id": "E2", "nombre": "Acueducto"}]}

RUBRICA = {
    "schema": "morfeo.rubrica-sgr/v1", "id": "conv54",
    "minimos_talento": [
        {"categoria": "posdoctorado", "cantidad": 1, "texto": "Un (1) doctor para la realización de una estancia posdoctoral"},
        {"categoria": "maestria", "cantidad": 2, "texto": "Dos (2) estudiantes de maestría en modalidad de investigación"},
        {"categoria": "joven_investigador", "cantidad": 6, "texto": "Seis (6) jóvenes investigadores e innovadores"},
    ],
    "minimo_productos": {"cantidad": 1, "texto": "Un producto de nuevo conocimiento"},
}

PRODUCTS_STUB = '''
import json
from pathlib import Path

def findings(run_root):
    if (Path(run_root) / "stub_falla").exists():
        raise RuntimeError("productos ilegibles")
    path = Path(run_root) / "stub_productos_findings.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []

def datos(run_root):
    return {"productos_adicionales": {"total": 2, "top_o_a": 2, "fuente": "productos.json"},
            "fuente": "productos.json", "talento": {"joven_investigador": 4, "maestria": 2}}
'''


def make_workspace(tmp: Path, flujo: str | None = "sgr") -> tuple[Path, Path]:
    workspace = Path(tmp)
    if flujo:
        (workspace / ".morfeo").mkdir()
        (workspace / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = workspace / "proposals" / "run-productos"
    (run / "artefactos").mkdir(parents=True)
    (workspace / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
    return workspace, run


def write_file(run: Path, name: str, data: dict | str, folder: str = "sgr") -> None:
    target = run / "artefactos" / folder
    target.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    (target / name).write_text(text, encoding="utf-8")


def write_all(run: Path) -> None:
    write_file(run, "productos.json", PRODUCTOS)
    write_file(run, "cadena_valor.json", CADENA)
    write_file(run, "alianza.json", ALIANZA)


def write_stub(run: Path, name: str, data) -> None:
    (run / name).write_text(json.dumps(data), encoding="utf-8")


class StubScripts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        scripts = self.tmp / "kit-scripts"
        scripts.mkdir()
        (scripts / "productos_sgr.py").write_text(PRODUCTS_STUB, encoding="utf-8")
        self.scripts = scripts
        patcher = mock.patch.object(value_chain, "_script_candidates", lambda name: [scripts / name])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ws = self.new_dir("ws")

    def new_dir(self, name: str) -> Path:
        path = self.tmp / name
        path.mkdir()
        return path


class TestLoadProducts(StubScripts):
    def test_base_flow_is_not_available_and_loads_nothing(self):
        _, run = make_workspace(self.ws, flujo=None)
        write_all(run)
        write_file(run, "rubrica.json", RUBRICA, folder="juez")
        write_stub(run, "stub_productos_findings.json", [{"severity": "error", "code": "productos-x"}])
        data = load_products(run)
        self.assertEqual(data["flujo"], "base")
        self.assertFalse(data["disponible"])
        for key in ("productos", "datos", "hash", "revision"):
            self.assertIsNone(data[key], key)
        self.assertEqual((data["hallazgos"], data["errores"]), ([], []))
        self.assertEqual((data["cadena_productos"], data["minimos_talento"], data["entidades"]), ([], [], {}))
        self.assertFalse(data["aprobado"])

    def test_sgr_without_files_is_not_available_and_has_no_errors(self):
        _, run = make_workspace(self.ws)
        data = load_products(run)
        self.assertEqual(data["flujo"], "sgr")
        self.assertFalse(data["disponible"])
        self.assertIsNone(data["hash"])
        self.assertIsNone(data["datos"])
        self.assertEqual(data["errores"], [])

    def test_sgr_returns_products_findings_chain_entities_and_facts(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        finding = {"severity": "warning", "code": "productos-divulgacion", "message": "Sin cronograma", "node": "divulgacion"}
        write_stub(run, "stub_productos_findings.json", [finding])
        data = load_products(run)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["productos"], PRODUCTOS)
        self.assertEqual(data["hallazgos"], [finding])
        self.assertEqual(data["entidades"], {"E1": "Universidad Nacional", "E2": "Acueducto"})
        self.assertEqual(data["datos"]["productos_adicionales"], {"total": 2, "top_o_a": 2, "fuente": "productos.json"})
        self.assertEqual(data["cadena_productos"], [
            {"oe": "OE1", "oe_texto": "Medir la calidad del agua", "codigo": "1.1", "codigo_dnp": "3906001",
             "nombre": "Servicio de monitoreo", "medido_a_traves_de": "Número de sistemas",
             "indicador": "Sistemas implementados", "unidad": "Número", "meta": 2},
            {"oe": "OE2", "oe_texto": "Transferir", "codigo": "2.1", "codigo_dnp": None, "nombre": "Documentos",
             "medido_a_traves_de": "", "indicador": "", "unidad": "", "meta": None},
        ])
        self.assertIsInstance(data["hash"], str)
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["errores"], [])

    def test_talent_minimums_come_from_the_rubric_with_committed_counts(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        write_file(run, "rubrica.json", RUBRICA, folder="juez")
        data = load_products(run)
        self.assertEqual(data["minimos_talento"], [
            {"categoria": "posdoctorado", "requerido": 1, "comprometido": 0, "cumple": False,
             "texto": "Un (1) doctor para la realización de una estancia posdoctoral"},
            {"categoria": "maestria", "requerido": 2, "comprometido": 2, "cumple": True,
             "texto": "Dos (2) estudiantes de maestría en modalidad de investigación"},
            {"categoria": "joven_investigador", "requerido": 6, "comprometido": 4, "cumple": False,
             "texto": "Seis (6) jóvenes investigadores e innovadores"},
        ])
        self.assertEqual(data["minimo_productos"], RUBRICA["minimo_productos"])

    def test_minimums_accept_a_category_map_and_are_empty_without_rubric(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        self.assertEqual(load_products(run)["minimos_talento"], [])
        write_file(run, "rubrica.json", {**RUBRICA, "minimos_talento": {"maestria": 3}}, folder="juez")
        self.assertEqual(load_products(run)["minimos_talento"], [
            {"categoria": "maestria", "requerido": 3, "comprometido": 2, "cumple": False, "texto": ""}])

    def test_the_hash_covers_the_products_but_not_the_chain_alliance_or_rubric(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        first = load_products(run)["hash"]
        write_file(run, "cadena_valor.json", {**CADENA, "duracion_meses": 36})
        write_file(run, "alianza.json", {**ALIANZA, "entidades": []})
        write_file(run, "rubrica.json", RUBRICA, folder="juez")
        self.assertEqual(load_products(run)["hash"], first)
        changed = json.loads(json.dumps(PRODUCTOS))
        changed["talento"][0]["cantidad"] = 6
        write_file(run, "productos.json", changed)
        self.assertNotEqual(load_products(run)["hash"], first)

    def test_missing_script_shows_the_data_without_findings_or_facts(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        (self.scripts / "productos_sgr.py").unlink()
        data = load_products(run)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["hallazgos"], [])
        self.assertIsNone(data["datos"])
        self.assertEqual(data["errores"], [])

    def test_failing_script_is_reported_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        (run / "stub_falla").write_text("", encoding="utf-8")
        data = load_products(run)
        self.assertTrue(data["disponible"])
        self.assertIn("productos ilegibles", " ".join(data["errores"]))

    def test_corrupt_or_foreign_files_return_errors_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_file(run, "productos.json", "{roto")
        data = load_products(run)
        self.assertFalse(data["disponible"])
        self.assertIn("productos.json", " ".join(data["errores"]))
        write_file(run, "productos.json", {"schema": "otro/v1"})
        data = load_products(run)
        self.assertFalse(data["disponible"])
        self.assertIn("morfeo.productos-sgr/v1", " ".join(data["errores"]))
        write_file(run, "rubrica.json", "{roto", folder="juez")
        self.assertIn("rubrica.json", " ".join(load_products(run)["errores"]))


class TestApprove(StubScripts):
    def test_error_findings_block_the_approval(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        write_stub(run, "stub_productos_findings.json",
                   [{"severity": "error", "code": "productos-talento-minimo", "message": "m", "node": "talento"}])
        result = approve(run)
        self.assertFalse(result["ok"])
        self.assertIn("productos-talento-minimo", result["error"])
        self.assertFalse((run / "artefactos" / "sgr" / "revision.json").exists())

    def test_approval_preserves_other_keys_and_expires_when_the_file_changes(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        review = run / "artefactos" / "sgr" / "revision.json"
        others = {"cadena_valor": {"aprobado": True, "hash": "cafe", "fecha": "2026-11-18T10:00:00"},
                  "alianza_territorio": {"aprobado": True, "hash": "beef", "fecha": "2026-11-18T11:00:00"},
                  "presupuesto": {"aprobado": True, "hash": "f00d", "fecha": "2026-11-18T12:00:00"},
                  "componentes": {"aprobado": True, "hash": "d00d", "fecha": "2026-11-18T13:00:00"}}
        review.write_text(json.dumps(others), encoding="utf-8")
        current = load_products(run)["hash"]
        result = approve(run, current)
        self.assertTrue(result["ok"])
        saved = json.loads(review.read_text(encoding="utf-8"))
        for key, value in others.items():
            self.assertEqual(saved[key], value, key)
        self.assertEqual(set(saved["productos"]), {"aprobado", "hash", "fecha"})
        self.assertEqual(saved["productos"]["hash"], current)
        self.assertTrue(load_products(run)["aprobado"])

        changed = json.loads(json.dumps(PRODUCTOS))
        changed["divulgacion"]["costeada"] = False
        write_file(run, "productos.json", changed)
        data = load_products(run)
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["revision"]["hash"], current)

    def test_a_stale_hash_is_refused(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        result = approve(run, "0000000000000000")
        self.assertFalse(result["ok"])
        self.assertIn("cambi", result["error"])

    def test_missing_file_and_base_flow_are_refused(self):
        _, empty = make_workspace(self.ws)
        result = approve(empty)
        self.assertFalse(result["ok"])
        self.assertIn("fase5_sgr", result["error"])
        self.assertIn("productos_sgr.py check", result["error"])
        _, base = make_workspace(self.new_dir("base"), flujo=None)
        write_all(base)
        result = approve(base)
        self.assertFalse(result["ok"])
        self.assertIn("SGR", result["error"])

    def test_corrupt_review_is_never_overwritten(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        review = run / "artefactos" / "sgr" / "revision.json"
        review.write_text("{roto", encoding="utf-8")
        data = load_products(run)
        self.assertIn("revision.json", " ".join(data["errores"]))
        self.assertFalse(approve(run, data["hash"])["ok"])
        self.assertEqual(review.read_text(encoding="utf-8"), "{roto")


class TestAdjustPrompt(StubScripts):
    def test_prompt_carries_the_note_file_agents_and_the_check(self):
        _, run = make_workspace(self.ws)
        prompt = build_adjust_prompt(run, "Suma un artículo\nTOP")
        self.assertIn("«Suma un artículo TOP»", prompt)
        self.assertIn("proposals/run-productos/artefactos/sgr/productos.json", prompt)
        self.assertIn("morfeo.productos-sgr/v1", prompt)
        investigador = prompt.index("investigador")
        redactor = prompt.index("redactor")
        check = prompt.index("productos_sgr.py check proposals/run-productos")
        self.assertLess(investigador, check)
        self.assertLess(redactor, check)
        for block in ("productos_ctei", "divulgacion", "indicadores_gestion", "talento", "cadena_valor.json"):
            self.assertIn(block, prompt)
        self.assertNotIn("\n", prompt)

    def test_empty_note_or_base_flow_raise_value_error(self):
        _, run = make_workspace(self.ws)
        with self.assertRaises(ValueError):
            build_adjust_prompt(run, "  ")
        with self.assertRaises(ValueError):
            build_adjust_prompt(run, None)
        _, base = make_workspace(self.new_dir("base"), flujo=None)
        with self.assertRaises(ValueError):
            build_adjust_prompt(base, "algo")


class TestProductsHttpApi(StubScripts):
    def _serve(self, workspace: Path):
        from morfeo.dashboard.server import MorfeoDashboardHandler

        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": workspace})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    @staticmethod
    def _request(url: str, payload: dict | None = None, raw: bytes | None = None) -> tuple[int, dict]:
        data = raw if raw is not None else (json.dumps(payload).encode("utf-8") if payload is not None else None)
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                     method="POST" if data is not None else "GET")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_get_approve_and_adjust_over_http(self):
        workspace, run = make_workspace(self.ws)
        write_all(run)
        base = self._serve(workspace)

        code, data = self._request(base + "/api/products")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["run"], run.name)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["productos"], PRODUCTOS)

        code, bad = self._request(base + "/api/products/approve", {"hash": "0000000000000000"})
        self.assertEqual(code, 409)
        self.assertFalse(bad["ok"])

        code, ok = self._request(base + "/api/products/approve", {"hash": data["hash"]})
        self.assertEqual(code, 200)
        self.assertTrue(ok["ok"])
        self.assertTrue(self._request(base + "/api/products")[1]["aprobado"])

        code, adj = self._request(base + "/api/products/adjust", {"nota": "Agrega un indicador"})
        self.assertEqual(code, 200)
        self.assertEqual(adj, {"ok": True, "prompt": build_adjust_prompt(run, "Agrega un indicador")})

        code, bad = self._request(base + "/api/products/adjust", {"nota": ""})
        self.assertEqual(code, 400)
        code, bad = self._request(base + "/api/products/adjust", raw=b"{roto")
        self.assertEqual(code, 400)
        self.assertFalse(bad["ok"])

    def test_error_findings_answer_409_on_approve(self):
        workspace, run = make_workspace(self.ws)
        write_all(run)
        write_stub(run, "stub_productos_findings.json",
                   [{"severity": "error", "code": "productos-minimo-ctei", "message": "m", "node": "productos_ctei"}])
        base = self._serve(workspace)
        code, bad = self._request(base + "/api/products/approve", {})
        self.assertEqual(code, 409)
        self.assertIn("productos-minimo-ctei", bad["error"])

    def test_base_flow_routes_report_unavailable(self):
        workspace, run = make_workspace(self.ws, flujo=None)
        write_all(run)
        base = self._serve(workspace)
        code, data = self._request(base + "/api/products")
        self.assertEqual(code, 200)
        self.assertEqual((data["flujo"], data["disponible"], data["productos"]), ("base", False, None))
        code, _ = self._request(base + "/api/products/adjust", {"nota": "x"})
        self.assertEqual(code, 400)
        code, _ = self._request(base + "/api/products/approve", {})
        self.assertEqual(code, 409)

    def test_without_active_run_the_routes_answer_404(self):
        (self.ws / "proposals").mkdir()
        base = self._serve(self.ws)
        for path, payload in (("/api/products", None), ("/api/products/approve", {}),
                              ("/api/products/adjust", {"nota": "x"})):
            code, bad = self._request(base + path, payload)
            self.assertEqual(code, 404, path)
            self.assertFalse(bad["ok"])


if __name__ == "__main__":
    unittest.main()
