"""Pestaña «Requisitos y anexos» (odd/tasks/sgr-requisitos-anexos.md, S1 y S7).

El script del kit `requisitos_sgr.py` se sustituye por un doble escrito en una
carpeta temporal y se carga por la misma importación dinámica que usa el
tablero para `cadena_valor_sgr.py` y `productos_sgr.py`.
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
from morfeo.core.requirements import (
    MAX_BODY_BYTES,
    approve,
    build_adjust_prompt,
    load_requirements,
    update_item,
)

REQUISITOS = {
    "schema": "morfeo.requisitos-sgr/v1",
    "convocatoria": "conv54",
    "items": [
        {"id": "11.4", "estado": "listo", "responsable": "E1", "archivo": "insumos/requisitos/anexo1.pdf",
         "fecha": "2026-11-05", "nota": None, "justificacion": None},
        {"id": "11.10", "estado": "pendiente", "responsable": None, "archivo": None, "fecha": None,
         "nota": None, "justificacion": None},
    ],
    "cifras": {"sigp": {"total_sgr": 100, "total_contrapartida": 20, "total": 120},
               "anexo1": None, "anexo3": None, "mga": None},
    "licencias": None,
    "aval_institucional": None,
}

ALIANZA = {"schema": "morfeo.alianza-sgr/v1", "entidades": [
    {"id": "E1", "nombre": "Universidad Nacional"}, {"id": "E2", "nombre": "Acueducto"}]}

# Doble del script del kit con el contrato de la feature: `vista`, `findings`
# y `actualizar_item` (que valida y escribe requisitos.json).
REQUIREMENTS_STUB = '''
import json
from pathlib import Path

RUBRIC = [
    {"id": "11.4", "nombre": "Anexo 1", "texto": "Adjuntar el Anexo 1", "condicion": None,
     "documento": "Anexo 1", "numeral_fuente": "11.4"},
    {"id": "11.10", "nombre": "Aval de ética", "texto": "Aval del comité de ética cuando aplique",
     "condicion": "etica", "documento": "Aval de ética", "numeral_fuente": "11.10"},
]
FIELDS = ("estado", "responsable", "archivo", "fecha", "nota", "justificacion")
ESTADOS = ("pendiente", "en_tramite", "listo", "no_aplica")


class RequisitosError(ValueError):
    pass


def _path(run_root):
    return Path(run_root) / "artefactos" / "sgr" / "requisitos.json"


def _data(run_root):
    path = _path(run_root)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"schema": "morfeo.requisitos-sgr/v1", "convocatoria": "conv54", "items": [], "cifras": {},
            "licencias": None, "aval_institucional": None}


def findings(run_root):
    if (Path(run_root) / "stub_falla").exists():
        raise RuntimeError("requisitos ilegibles")
    path = Path(run_root) / "stub_requisitos_findings.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def vista(run_root):
    data = _data(run_root)
    items = {i["id"]: i for i in data.get("items") or []}
    rows = []
    for req in RUBRIC:
        item = items.get(req["id"]) or {"id": req["id"], "estado": "pendiente"}
        rows.append({**req, **item, "aplica_derivada": None})
    listos = sum(1 for r in rows if r.get("estado") == "listo")
    return {"convocatoria": data.get("convocatoria"), "requisitos": rows,
            "progreso": {"listos": listos, "aplicables": len(rows)},
            "cifras": [{"documento": "sigp", "campo": "total", "declarado": (data.get("cifras") or {}).get("sigp", {}) and data["cifras"]["sigp"].get("total"),
                        "esperado": 120, "coincide": True}],
            "licencias": data.get("licencias"),
            "aval": {"institucion": None, "documentos": [], "hitos": []},
            "findings": findings(run_root)}


def actualizar_item(run_root, id, cambios):
    data = _data(run_root)
    if id.startswith("cifras."):
        doc = id.split(".", 1)[1]
        data.setdefault("cifras", {})[doc] = cambios
        result = cambios
    else:
        if id not in {r["id"] for r in RUBRIC}:
            raise RequisitosError(f"Requisito desconocido: {id}")
        if "estado" in cambios and cambios["estado"] not in ESTADOS:
            raise RequisitosError(f"Estado inválido: {cambios['estado']}")
        items = data.setdefault("items", [])
        item = next((i for i in items if i["id"] == id), None)
        if item is None:
            item = {"id": id, **{f: None for f in FIELDS}, "estado": "pendiente"}
            items.append(item)
        item.update(cambios)
        result = item
    path = _path(run_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return result
'''


def make_workspace(tmp: Path, flujo: str | None = "sgr") -> tuple[Path, Path]:
    workspace = Path(tmp)
    if flujo:
        (workspace / ".morfeo").mkdir()
        (workspace / ".morfeo" / "config.json").write_text(json.dumps({"flujo": flujo}), encoding="utf-8")
    run = workspace / "proposals" / "run-requisitos"
    (run / "artefactos").mkdir(parents=True)
    (workspace / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
    return workspace, run


def write_file(run: Path, name: str, data: dict | str, folder: str = "sgr") -> None:
    target = run / "artefactos" / folder
    target.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    (target / name).write_text(text, encoding="utf-8")


def write_all(run: Path) -> None:
    write_file(run, "requisitos.json", REQUISITOS)
    write_file(run, "alianza.json", ALIANZA)


def write_stub(run: Path, name: str, data) -> None:
    (run / name).write_text(json.dumps(data), encoding="utf-8")


def saved(run: Path) -> dict:
    return json.loads((run / "artefactos" / "sgr" / "requisitos.json").read_text(encoding="utf-8"))


class StubScripts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        scripts = self.tmp / "kit-scripts"
        scripts.mkdir()
        (scripts / "requisitos_sgr.py").write_text(REQUIREMENTS_STUB, encoding="utf-8")
        self.scripts = scripts
        patcher = mock.patch.object(value_chain, "_script_candidates", lambda name: [scripts / name])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ws = self.new_dir("ws")

    def new_dir(self, name: str) -> Path:
        path = self.tmp / name
        path.mkdir()
        return path


class TestLoadRequirements(StubScripts):
    def test_base_flow_is_not_available_and_loads_nothing(self):
        _, run = make_workspace(self.ws, flujo=None)
        write_all(run)
        write_stub(run, "stub_requisitos_findings.json", [{"severity": "error", "code": "requisitos-x"}])
        data = load_requirements(run)
        self.assertEqual(data["flujo"], "base")
        self.assertFalse(data["disponible"])
        for key in ("requisitos", "vista", "hash", "revision"):
            self.assertIsNone(data[key], key)
        self.assertEqual((data["hallazgos"], data["errores"], data["entidades"]), ([], [], {}))
        self.assertFalse(data["aprobado"])

    def test_sgr_returns_the_view_findings_entities_and_hash(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        finding = {"severity": "warning", "code": "requisitos-sin-archivo", "message": "Listo sin archivo", "node": "11.4"}
        write_stub(run, "stub_requisitos_findings.json", [finding])
        data = load_requirements(run)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["requisitos"], REQUISITOS)
        self.assertEqual(data["vista"]["progreso"], {"listos": 1, "aplicables": 2})
        self.assertEqual([r["id"] for r in data["vista"]["requisitos"]], ["11.4", "11.10"])
        self.assertEqual(data["hallazgos"], [finding])
        self.assertEqual(data["entidades"], {"E1": "Universidad Nacional", "E2": "Acueducto"})
        self.assertIsInstance(data["hash"], str)
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["errores"], [])

    def test_missing_file_still_shows_the_view_with_pending_items(self):
        _, run = make_workspace(self.ws)
        data = load_requirements(run)
        self.assertTrue(data["disponible"])
        self.assertIsNone(data["requisitos"])
        self.assertIsNone(data["hash"])
        self.assertEqual({r["estado"] for r in data["vista"]["requisitos"]}, {"pendiente"})
        self.assertEqual(data["errores"], [])

    def test_missing_script_is_not_available_without_errors(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        (self.scripts / "requisitos_sgr.py").unlink()
        data = load_requirements(run)
        self.assertFalse(data["disponible"])
        self.assertIsNone(data["vista"])
        self.assertEqual(data["requisitos"], REQUISITOS)
        self.assertEqual(data["hallazgos"], [])
        self.assertEqual(data["errores"], [])

    def test_failing_script_is_reported_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        (run / "stub_falla").write_text("", encoding="utf-8")
        data = load_requirements(run)
        self.assertFalse(data["disponible"])
        self.assertIn("requisitos ilegibles", " ".join(data["errores"]))

    def test_corrupt_or_foreign_file_returns_errors_instead_of_raising(self):
        _, run = make_workspace(self.ws)
        write_file(run, "requisitos.json", "{roto")
        self.assertIn("requisitos.json", " ".join(load_requirements(run)["errores"]))
        write_file(run, "requisitos.json", {"schema": "otro/v1"})
        self.assertIn("morfeo.requisitos-sgr/v1", " ".join(load_requirements(run)["errores"]))


class TestApprove(StubScripts):
    def test_approval_is_tied_to_the_hash_and_expires_when_the_file_changes(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        review = run / "artefactos" / "sgr" / "revision.json"
        others = {"productos": {"aprobado": True, "hash": "cafe", "fecha": "2026-11-19T10:00:00"}}
        review.write_text(json.dumps(others), encoding="utf-8")
        current = load_requirements(run)["hash"]
        result = approve(run, current)
        self.assertTrue(result["ok"])
        stored = json.loads(review.read_text(encoding="utf-8"))
        self.assertEqual(stored["productos"], others["productos"])
        self.assertEqual(set(stored["requisitos"]), {"aprobado", "hash", "fecha"})
        self.assertEqual(stored["requisitos"]["hash"], current)
        self.assertTrue(load_requirements(run)["aprobado"])

        update_item(run, {"id": "11.10", "cambios": {"estado": "en_tramite"}})
        data = load_requirements(run)
        self.assertFalse(data["aprobado"])
        self.assertEqual(data["revision"]["hash"], current)

    def test_a_stale_hash_is_refused(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        result = approve(run, "0000000000000000")
        self.assertFalse(result["ok"])
        self.assertIn("cambi", result["error"])
        self.assertFalse((run / "artefactos" / "sgr" / "revision.json").exists())

    def test_error_findings_block_the_approval(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        write_stub(run, "stub_requisitos_findings.json",
                   [{"severity": "error", "code": "requisitos-no-aplica", "message": "m", "node": "11.4"}])
        result = approve(run)
        self.assertFalse(result["ok"])
        self.assertIn("requisitos-no-aplica", result["error"])

    def test_missing_file_and_base_flow_are_refused(self):
        _, empty = make_workspace(self.ws)
        result = approve(empty)
        self.assertFalse(result["ok"])
        self.assertIn("fase6_9_sgr", result["error"])
        self.assertIn("requisitos_sgr.py init", result["error"])
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
        data = load_requirements(run)
        self.assertIn("revision.json", " ".join(data["errores"]))
        self.assertFalse(approve(run, data["hash"])["ok"])
        self.assertEqual(review.read_text(encoding="utf-8"), "{roto")


class TestAdjustPrompt(StubScripts):
    def test_prompt_carries_the_note_file_agents_and_the_check(self):
        _, run = make_workspace(self.ws)
        prompt = build_adjust_prompt(run, "Agrega la licencia\nambiental")
        self.assertIn("«Agrega la licencia ambiental»", prompt)
        self.assertIn("proposals/run-requisitos/artefactos/sgr/requisitos.json", prompt)
        self.assertIn("morfeo.requisitos-sgr/v1", prompt)
        check = prompt.index("requisitos_sgr.py check proposals/run-requisitos")
        self.assertLess(prompt.index("investigador"), check)
        self.assertLess(prompt.index("redactor"), check)
        for text in ("licencias", "presupuesto.json", "alianza.json", "revisor-estilo-sgr"):
            self.assertIn(text, prompt)
        self.assertNotIn("\n", prompt)

    def test_empty_note_or_base_flow_raise_value_error(self):
        _, run = make_workspace(self.ws)
        for nota in ("  ", None):
            with self.assertRaises(ValueError):
                build_adjust_prompt(run, nota)
        _, base = make_workspace(self.new_dir("base"), flujo=None)
        with self.assertRaises(ValueError):
            build_adjust_prompt(base, "algo")


class TestUpdateItem(StubScripts):
    def test_valid_edit_writes_the_item_and_returns_the_refreshed_view(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        result = update_item(run, {"id": "11.10", "cambios": {"estado": "en_tramite", "responsable": "E2",
                                                              "nota": "Radicado en el comité"}})
        self.assertTrue(result["ok"])
        self.assertEqual(result["item"]["estado"], "en_tramite")
        self.assertEqual(result["item"]["responsable"], "E2")
        item = next(i for i in saved(run)["items"] if i["id"] == "11.10")
        self.assertEqual((item["estado"], item["nota"]), ("en_tramite", "Radicado en el comité"))
        row = next(r for r in result["vista"]["requisitos"] if r["id"] == "11.10")
        self.assertEqual(row["estado"], "en_tramite")
        self.assertEqual(result["hash"], load_requirements(run)["hash"])

    def test_null_clears_a_field(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        result = update_item(run, {"id": "11.4", "cambios": {"archivo": None}})
        self.assertTrue(result["ok"])
        self.assertIsNone(next(i for i in saved(run)["items"] if i["id"] == "11.4")["archivo"])

    def test_figures_id_replaces_one_declared_block(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        block = {"total_sgr": 90, "total_contrapartida": 30, "total": 120}
        result = update_item(run, {"id": "cifras.anexo3", "cambios": block})
        self.assertTrue(result["ok"])
        self.assertEqual(saved(run)["cifras"]["anexo3"], block)
        self.assertEqual(saved(run)["cifras"]["sigp"], REQUISITOS["cifras"]["sigp"])

    def test_body_shape_is_validated_before_touching_the_file(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        before = (run / "artefactos" / "sgr" / "requisitos.json").read_text(encoding="utf-8")
        cases = [
            ("id must be a string", {"id": 11, "cambios": {"estado": "listo"}}, "id"),
            ("id must not be empty", {"id": " ", "cambios": {"estado": "listo"}}, "id"),
            ("cambios must be an object", {"id": "11.4", "cambios": ["listo"]}, "cambios"),
            ("cambios must not be empty", {"id": "11.4", "cambios": {}}, "cambios"),
            ("unknown field", {"id": "11.4", "cambios": {"condicion": "etica"}}, "condicion"),
            ("value must be text or null", {"id": "11.4", "cambios": {"nota": 3}}, "nota"),
            ("unknown figures document", {"id": "cifras.sigq", "cambios": {"total": 1}}, "sigq"),
            ("figures must be an object", {"id": "cifras.sigp", "cambios": 120}, "cifras"),
            ("missing body", None, "cuerpo"),
        ]
        for label, payload, needle in cases:
            with self.subTest(label):
                with self.assertRaises(ValueError) as ctx:
                    update_item(run, payload)
                self.assertIn(needle, str(ctx.exception))
        self.assertEqual((run / "artefactos" / "sgr" / "requisitos.json").read_text(encoding="utf-8"), before)

    def test_script_validation_errors_become_value_errors_with_their_message(self):
        _, run = make_workspace(self.ws)
        write_all(run)
        with self.assertRaises(ValueError) as ctx:
            update_item(run, {"id": "11.4", "cambios": {"estado": "terminado"}})
        self.assertIn("Estado inválido: terminado", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            update_item(run, {"id": "99.9", "cambios": {"estado": "listo"}})
        self.assertIn("Requisito desconocido: 99.9", str(ctx.exception))

    def test_base_flow_and_missing_script_are_refused(self):
        _, base = make_workspace(self.new_dir("base"), flujo=None)
        result = update_item(base, {"id": "11.4", "cambios": {"estado": "listo"}})
        self.assertFalse(result["ok"])
        self.assertIn("SGR", result["error"])
        self.assertFalse((base / "artefactos" / "sgr" / "requisitos.json").exists())
        _, run = make_workspace(self.ws)
        (self.scripts / "requisitos_sgr.py").unlink()
        result = update_item(run, {"id": "11.4", "cambios": {"estado": "listo"}})
        self.assertFalse(result["ok"])
        self.assertIn("requisitos_sgr.py", result["error"])


class TestRequirementsHttpApi(StubScripts):
    def _serve(self, workspace: Path):
        from morfeo.dashboard.server import MorfeoDashboardHandler

        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": workspace})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    @staticmethod
    def _request(url: str, payload=None, raw: bytes | None = None) -> tuple[int, dict]:
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
        code, data = self._request(base + "/api/requirements")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["run"], run.name)
        self.assertTrue(data["disponible"])
        self.assertEqual(data["vista"]["progreso"], {"listos": 1, "aplicables": 2})

        code, bad = self._request(base + "/api/requirements/approve", {"hash": "0000000000000000"})
        self.assertEqual(code, 409)
        self.assertFalse(bad["ok"])
        code, ok = self._request(base + "/api/requirements/approve", {"hash": data["hash"]})
        self.assertEqual(code, 200)
        self.assertTrue(ok["ok"])
        self.assertTrue(self._request(base + "/api/requirements")[1]["aprobado"])

        code, adj = self._request(base + "/api/requirements/adjust", {"nota": "Revisa las licencias"})
        self.assertEqual(code, 200)
        self.assertEqual(adj, {"ok": True, "prompt": build_adjust_prompt(run, "Revisa las licencias")})
        code, _ = self._request(base + "/api/requirements/adjust", {"nota": ""})
        self.assertEqual(code, 400)

    def test_post_item_edits_and_returns_item_and_view(self):
        workspace, run = make_workspace(self.ws)
        write_all(run)
        base = self._serve(workspace)
        code, data = self._request(base + "/api/requirements/item",
                                   {"id": "11.10", "cambios": {"estado": "no_aplica", "justificacion": "Sin humanos"}})
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["item"]["estado"], "no_aplica")
        self.assertEqual(data["run"], run.name)
        row = next(r for r in data["vista"]["requisitos"] if r["id"] == "11.10")
        self.assertEqual(row["justificacion"], "Sin humanos")

    def test_post_item_validation_errors_answer_400_with_the_message(self):
        workspace, run = make_workspace(self.ws)
        write_all(run)
        base = self._serve(workspace)
        for payload, needle in (
            ({"id": "11.4", "cambios": {"estado": "terminado"}}, "Estado inválido"),
            ({"id": "11.4", "cambios": {"otro": "x"}}, "otro"),
            ({"id": 4, "cambios": {"estado": "listo"}}, "id"),
            ({"id": "11.4"}, "cambios"),
        ):
            code, bad = self._request(base + "/api/requirements/item", payload)
            self.assertEqual(code, 400, payload)
            self.assertFalse(bad["ok"])
            self.assertIn(needle, bad["error"])
        code, bad = self._request(base + "/api/requirements/item", raw=b"{roto")
        self.assertEqual(code, 400)
        self.assertFalse(bad["ok"])

    def test_oversize_body_answers_413_without_writing(self):
        workspace, run = make_workspace(self.ws)
        write_all(run)
        before = (run / "artefactos" / "sgr" / "requisitos.json").read_text(encoding="utf-8")
        base = self._serve(workspace)
        payload = {"id": "11.4", "cambios": {"nota": "x" * (MAX_BODY_BYTES + 1)}}
        for path in ("/api/requirements/item", "/api/requirements/adjust", "/api/requirements/approve"):
            code, bad = self._request(base + path, payload)
            self.assertEqual(code, 413, path)
            self.assertFalse(bad["ok"])
        self.assertEqual((run / "artefactos" / "sgr" / "requisitos.json").read_text(encoding="utf-8"), before)

    def test_base_flow_routes_report_unavailable(self):
        workspace, run = make_workspace(self.ws, flujo=None)
        write_all(run)
        base = self._serve(workspace)
        code, data = self._request(base + "/api/requirements")
        self.assertEqual(code, 200)
        self.assertEqual((data["flujo"], data["disponible"], data["vista"]), ("base", False, None))
        code, _ = self._request(base + "/api/requirements/adjust", {"nota": "x"})
        self.assertEqual(code, 400)
        code, _ = self._request(base + "/api/requirements/approve", {})
        self.assertEqual(code, 409)
        code, _ = self._request(base + "/api/requirements/item", {"id": "11.4", "cambios": {"estado": "listo"}})
        self.assertEqual(code, 409)
        self.assertEqual(json.loads((run / "artefactos" / "sgr" / "requisitos.json").read_text(encoding="utf-8")),
                         REQUISITOS)

    def test_base_flow_keeps_the_earlier_sgr_routes_unchanged(self):
        workspace, run = make_workspace(self.ws, flujo=None)
        base = self._serve(workspace)
        code, data = self._request(base + "/api/products")
        self.assertEqual(code, 200)
        self.assertEqual((data["flujo"], data["disponible"], data["productos"]), ("base", False, None))
        self.assertEqual(self._request(base + "/api/products/adjust", {"nota": "x"})[0], 400)
        self.assertEqual(self._request(base + "/api/products/approve", {})[0], 409)

    def test_without_active_run_the_routes_answer_404(self):
        (self.ws / "proposals").mkdir()
        base = self._serve(self.ws)
        for path, payload in (("/api/requirements", None), ("/api/requirements/approve", {}),
                              ("/api/requirements/adjust", {"nota": "x"}),
                              ("/api/requirements/item", {"id": "11.4", "cambios": {"estado": "listo"}})):
            code, bad = self._request(base + path, payload)
            self.assertEqual(code, 404, path)
            self.assertFalse(bad["ok"])


if __name__ == "__main__":
    unittest.main()
