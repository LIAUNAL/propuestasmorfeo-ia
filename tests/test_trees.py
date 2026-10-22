"""Árboles de problemas y objetivos de la pestaña del tablero."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from morfeo.core.trees import approve_tree, load_trees, record_feedback

SPEC = {
    "kind": "arbol",
    "caption": "Árbol de problemas de prueba.",
    "groups": [
        {"id": "SP1", "title": "SP1 · Uno", "causes": [{"id": "r1", "text": "Causa uno"}, {"id": "r2", "text": "Causa dos"}]},
        {"id": "SP2", "title": "SP2 · Dos", "causes": [{"id": "r3", "text": "Causa tres"}]},
    ],
    "trunk": {"label": "PROBLEMA CENTRAL", "text": "Baja cobertura del servicio de prueba."},
    "branches": [{"id": "b1", "text": "Efecto uno"}],
    "crown": {"label": "SOLUCIÓN", "text": "Sistema propuesto."},
}

OBJ_GENERAL = r"""% comentario que no es objetivo
\section{Objetivo general}
\label{sec:objetivo-general}

Desarrollar un sistema \textbf{portable} de prueba.
"""

OBJ_ESPECIFICOS = r"""% comentario
\section{Objetivos específicos}
\begin{enumerate}[label=OE\arabic*.]
  \item Desarrollar la estrategia uno.

  \item Diseñar el esquema dos.
\end{enumerate}
"""


def make_run(tmp: Path, spec: dict | None = SPEC) -> Path:
    run = tmp / "run"
    (run / "redaccion" / "specs").mkdir(parents=True)
    (run / "redaccion" / "sections").mkdir(parents=True)
    (run / "artefactos").mkdir(parents=True)
    if spec is not None:
        (run / "redaccion" / "specs" / "arbol_problemas.spec.json").write_text(
            json.dumps(spec, ensure_ascii=False), encoding="utf-8"
        )
    return run


def write_objectives_sections(run: Path) -> None:
    sections = run / "redaccion" / "sections"
    (sections / "06_objetivo_general.tex").write_text(OBJ_GENERAL, encoding="utf-8")
    (sections / "07_objetivos_especificos.tex").write_text(OBJ_ESPECIFICOS, encoding="utf-8")


def write_agent_objectives(run: Path, trunk: str = "Aumentar la cobertura del servicio de prueba") -> None:
    """Objective tree that mirrors SPEC and follows the SGR rules."""
    arboles = run / "artefactos" / "arboles"
    arboles.mkdir(parents=True, exist_ok=True)
    (arboles / "arbol_objetivos.json").write_text(json.dumps({
        "groups": [
            {"id": "OE1", "from": "SP1", "title": "OE1", "objective": "Lograr el objetivo uno",
             "means": [{"id": "m1", "from": "r1", "text": "Atender la causa uno"},
                       {"id": "m2", "from": "r2", "text": "Atender la causa dos"}]},
            {"id": "OE2", "from": "SP2", "title": "OE2", "objective": "Lograr el objetivo dos",
             "means": [{"id": "m3", "from": "r3", "text": "Atender la causa tres"}]},
        ],
        "trunk": {"label": "OBJETIVO GENERAL", "text": trunk},
        "branches": [{"id": "f1", "from": "b1", "text": "Reducir el efecto uno"}],
        "crown": {"label": "FIN ÚLTIMO", "text": "Mejorar el bienestar"},
    }, ensure_ascii=False), encoding="utf-8")


class TestLoadTrees(unittest.TestCase):
    def test_without_spec_the_problem_tree_is_not_available_and_explains_why(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp), spec=None)
            trees = load_trees(run)
            self.assertFalse(trees["problem"]["available"])
            self.assertIn("arbol_problemas.spec.json", trees["problem"]["hint"])
            self.assertFalse(trees["objectives"]["available"])
            self.assertEqual(trees["stage"], "sin_arbol")

    def test_problem_tree_comes_from_the_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            trees = load_trees(run)
            problem = trees["problem"]
            self.assertTrue(problem["available"])
            self.assertEqual(problem["tree"]["trunk"]["text"], "Baja cobertura del servicio de prueba.")
            self.assertEqual([g["id"] for g in problem["tree"]["groups"]], ["SP1", "SP2"])
            self.assertEqual(problem["review"]["status"], "pendiente")
            self.assertEqual(trees["stage"], "problemas")

    def test_objectives_tree_is_derived_in_mirror_with_pending_means(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            obj = load_trees(run)["objectives"]
            self.assertTrue(obj["available"])
            self.assertTrue(obj["derived"])
            groups = obj["tree"]["groups"]
            self.assertEqual([g["from"] for g in groups], ["SP1", "SP2"])
            self.assertEqual([m["from"] for m in groups[0]["means"]], ["r1", "r2"])
            self.assertIsNone(groups[0]["means"][0]["text"])
            self.assertIsNone(obj["tree"]["trunk"]["text"])
            self.assertEqual(obj["tree"]["branches"][0]["from"], "b1")

    def test_the_derived_mirror_does_not_copy_sections_6_and_7(self):
        # S3: this mirror used to copy §6 and §7. In the base flow §6 and §7 keep
        # their AI verbs and differ from the tree by design, so the copy was
        # removed on purpose: every positive text waits for the investigador.
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            write_objectives_sections(run)
            obj = load_trees(run)["objectives"]
            tree = obj["tree"]
            self.assertIsNone(tree["trunk"]["text"])
            self.assertEqual(tree["trunk"]["label"], "OBJETIVO GENERAL")
            self.assertEqual([g["objective"] for g in tree["groups"]], [None, None])
            self.assertEqual([g["title"] for g in tree["groups"]], ["OE1", "OE2"])
            self.assertEqual(tree["crown"], {"label": "FIN ÚLTIMO", "text": None})
            self.assertIn("fin último", obj["missing"])
            self.assertIn("investigador", obj["hint"])
            self.assertEqual(obj["findings"], [])

    def test_magnitude_passes_through_on_trunk_groups_and_branches(self):
        magnitude = {"indicador": "Tasa de deserción", "valor": "12 %", "fuente": "SIMAT 2024"}
        spec = json.loads(json.dumps(SPEC))
        spec["trunk"]["magnitude"] = magnitude
        spec["groups"][0]["magnitude"] = magnitude
        spec["branches"][0]["magnitude"] = magnitude
        with tempfile.TemporaryDirectory() as tmp:
            tree = load_trees(make_run(Path(tmp), spec=spec))["problem"]["tree"]
            self.assertEqual(tree["trunk"]["magnitude"], magnitude)
            self.assertEqual(tree["groups"][0]["magnitude"], magnitude)
            self.assertNotIn("magnitude", tree["groups"][1])
            self.assertEqual(tree["branches"][0]["magnitude"], magnitude)

    def test_the_default_crown_is_the_final_effect_not_the_solution(self):
        spec = {k: v for k, v in SPEC.items() if k not in ("crown", "trunk")}
        with tempfile.TemporaryDirectory() as tmp:
            tree = load_trees(make_run(Path(tmp), spec=spec))["problem"]["tree"]
            self.assertEqual(tree["crown"]["label"], "EFECTO FINAL")
            self.assertEqual(tree["trunk"]["label"], "PROBLEMA CENTRAL")

    def test_the_payload_carries_the_findings_of_the_sgr_rules(self):
        spec = dict(SPEC, trunk={"label": "PROBLEMA CENTRAL", "text": "Falta de un sistema de alerta"})
        with tempfile.TemporaryDirectory() as tmp:
            trees = load_trees(make_run(Path(tmp), spec=spec))
            codes = {f["code"] for f in trees["problem"]["findings"]}
            self.assertIn("arbol-ausencia-de-solucion", codes)
            self.assertIn("arbol-sin-magnitud", codes)
            self.assertEqual(trees["objectives"]["findings"], [])

    def test_objective_findings_come_from_the_agent_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            write_agent_objectives(run, trunk="Aumentar la cobertura del servicio de prueba mediante un sistema de IA")
            codes = {f["code"] for f in load_trees(run)["objectives"]["findings"]}
            self.assertEqual(codes, {"objetivo-general-con-medio"})

    def test_the_payload_reports_the_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            self.assertEqual(load_trees(run)["flujo"], "base")
            (Path(tmp) / ".morfeo").mkdir()
            (Path(tmp) / ".morfeo" / "config.json").write_text('{"flujo": "sgr"}', encoding="utf-8")
            self.assertEqual(load_trees(run)["flujo"], "sgr")

    def test_objectives_file_written_by_the_agent_wins_over_the_derivation(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            arboles = run / "artefactos" / "arboles"
            arboles.mkdir()
            agent_tree = {
                "groups": [{"id": "OE1", "from": "SP1", "title": "OE1", "objective": "Obj",
                            "means": [{"id": "m1", "from": "r1", "text": "Medio uno"}]}],
                "trunk": {"label": "OBJETIVO GENERAL", "text": "General"},
                "branches": [{"id": "f1", "from": "b1", "text": "Fin uno"}],
                "crown": {"label": "IMPACTO", "text": "Impacto"},
            }
            (arboles / "arbol_objetivos.json").write_text(json.dumps(agent_tree), encoding="utf-8")
            obj = load_trees(run)["objectives"]
            self.assertFalse(obj["derived"])
            self.assertEqual(obj["tree"]["groups"][0]["means"][0]["text"], "Medio uno")


class TestReviewCycle(unittest.TestCase):
    def test_feedback_writes_a_request_and_returns_a_one_line_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            result = record_feedback(
                run, "problemas", [{"node": "r1", "text": "Más específica"}], "Revisar ramas"
            )
            self.assertTrue(result["ok"])
            request = run / result["request"]
            body = request.read_text(encoding="utf-8")
            self.assertIn("Más específica", body)
            self.assertIn("Causa uno", body, "la solicitud cita el texto actual del nodo")
            self.assertIn("Revisar ramas", body)
            self.assertNotIn("\n", result["prompt"])
            self.assertIn("disenador-tikz", result["prompt"])
            self.assertIn(result["request"], result["prompt"])
            self.assertEqual(load_trees(run)["problem"]["review"]["status"], "en_ajuste")

    def test_a_multiline_node_is_quoted_on_one_line(self):
        """Los títulos de subproblema llevan saltos de línea para la figura; citados
        tal cual rompían la lista Markdown de la solicitud."""
        with tempfile.TemporaryDirectory() as tmp:
            spec = dict(SPEC, groups=[dict(SPEC["groups"][0], title="SP1 · Uno\ny dos")] + SPEC["groups"][1:])
            run = make_run(Path(tmp), spec=spec)
            result = record_feedback(run, "problemas", [{"node": "SP1", "text": "Acortar"}])
            body = (run / result["request"]).read_text(encoding="utf-8")
            self.assertIn("- **SP1** (texto actual: «SP1 · Uno y dos»): Acortar", body)

    def test_a_new_version_after_feedback_is_ready_for_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            record_feedback(run, "problemas", [], "Ajustar")
            spec = dict(SPEC, trunk={"label": "PROBLEMA CENTRAL", "text": "Nuevo problema."})
            (run / "redaccion" / "specs" / "arbol_problemas.spec.json").write_text(
                json.dumps(spec), encoding="utf-8"
            )
            self.assertEqual(load_trees(run)["problem"]["review"]["status"], "por_revisar")

    def test_empty_feedback_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            result = record_feedback(run, "problemas", [], "  ")
            self.assertFalse(result["ok"])

    def test_approval_expires_when_the_tree_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            self.assertTrue(approve_tree(run, "problemas")["ok"])
            self.assertEqual(load_trees(run)["problem"]["review"]["status"], "aprobado")
            spec = dict(SPEC, branches=[{"id": "b1", "text": "Efecto cambiado"}])
            (run / "redaccion" / "specs" / "arbol_problemas.spec.json").write_text(
                json.dumps(spec), encoding="utf-8"
            )
            self.assertEqual(load_trees(run)["problem"]["review"]["status"], "desactualizado")

    def test_objectives_cannot_be_approved_before_the_problem_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            result = approve_tree(run, "objetivos")
            self.assertFalse(result["ok"])
            self.assertIn("árbol de problemas", result["error"])

    def test_objectives_with_pending_means_cannot_be_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            write_objectives_sections(run)
            approve_tree(run, "problemas")
            result = approve_tree(run, "objetivos")
            self.assertFalse(result["ok"])
            self.assertIn("medios", result["error"])

    def test_objectives_feedback_targets_the_investigator(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            result = record_feedback(run, "objetivos", [], "Proponer medios")
            self.assertIn("investigador", result["prompt"])
            self.assertIn("arbol_objetivos.json", result["prompt"])

    def test_both_approved_closes_the_stage(self):
        # The agent tree now has to mirror SPEC and follow the SGR rules,
        # otherwise its error findings block the approval.
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            write_agent_objectives(run)
            approve_tree(run, "problemas")
            self.assertTrue(approve_tree(run, "objetivos")["ok"])
            self.assertEqual(load_trees(run)["stage"], "aprobados")

    def test_a_tree_with_error_findings_cannot_be_approved(self):
        spec = dict(SPEC, trunk={"label": "PROBLEMA CENTRAL", "text": "Ausencia de un sistema de alerta"})
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp), spec=spec)
            result = approve_tree(run, "problemas")
            self.assertFalse(result["ok"])
            self.assertIn("Corrige los hallazgos de la guía SGR antes de aprobar", result["error"])
            self.assertIn("arbol-ausencia-de-solucion", result["error"])

        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            write_agent_objectives(run, trunk="Aumentar la cobertura del servicio de prueba en un 30 %")
            approve_tree(run, "problemas")
            result = approve_tree(run, "objetivos")
            self.assertFalse(result["ok"])
            self.assertIn("objetivo-general-con-meta", result["error"])

    def test_warnings_do_not_block_the_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            self.assertEqual({f["severity"] for f in load_trees(run)["problem"]["findings"]}, {"warning"})
            self.assertTrue(approve_tree(run, "problemas")["ok"])

    def test_feedback_prompts_carry_the_sgr_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            problem = record_feedback(run, "problemas", [], "Ajustar")["prompt"]
            self.assertIn("estado negativo", problem)
            self.assertIn("falta de", problem)
            self.assertIn("efecto indirecto", problem)
            self.assertIn("magnitud", problem)
            self.assertIn("una sola variable", problem)
            self.assertIn("no vacíos de la literatura", problem)
            base = record_feedback(run, "objetivos", [], "Ajustar")["prompt"]
            self.assertIn("cada causa directa se vuelve", base)
            self.assertIn("title es el rótulo OE<n>, nunca el texto de la causa", base)
            self.assertIn("No modifiques §6 ni §7 sin preguntarme; deben conservar la variable del árbol.", base)
            self.assertNotIn("\n", base)
            (Path(tmp) / ".morfeo").mkdir()
            (Path(tmp) / ".morfeo" / "config.json").write_text('{"flujo": "sgr"}', encoding="utf-8")
            sgr = record_feedback(run, "objetivos", [], "Ajustar")["prompt"]
            self.assertIn("En el flujo SGR §6 y §7 son literalmente los textos de este árbol", sgr)
            self.assertNotIn("deben conservar la variable del árbol", sgr)


class TestReviewFileRobustness(unittest.TestCase):
    def test_concurrent_feedback_keeps_every_iteration(self):
        """El servidor es multihilo: dos solicitudes simultáneas no pueden tomar
        el mismo número de iteración ni perder una entrada."""
        import threading

        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            results = []
            barrier = threading.Barrier(8)

            def send(i: int) -> None:
                barrier.wait()
                results.append(record_feedback(run, "problemas", [], f"ajuste {i}"))

            threads = [threading.Thread(target=send, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertTrue(all(r["ok"] for r in results))
            self.assertEqual(sorted(r["iteration"] for r in results), list(range(1, 9)))
            iterations = load_trees(run)["problem"]["review"]["iterations"]
            self.assertEqual(sorted(it["n"] for it in iterations), list(range(1, 9)))
            self.assertEqual(len(list((run / "artefactos" / "arboles").glob("ajuste_problemas_*.md"))), 8)

    def test_a_corrupt_review_file_is_not_silently_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            approve_tree(run, "problemas")
            review = run / "artefactos" / "arboles" / "revision.json"
            review.write_text('{"problemas": {"approved_hash": ', encoding="utf-8")

            result = approve_tree(run, "problemas")
            self.assertFalse(result["ok"])
            self.assertIn("revision.json", result["error"])
            self.assertFalse(record_feedback(run, "problemas", [], "x")["ok"])
            self.assertEqual(review.read_text(encoding="utf-8"), '{"problemas": {"approved_hash": ')
            self.assertIn("revision.json", load_trees(run)["review_error"])

    def test_writes_leave_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            approve_tree(run, "problemas")
            names = sorted(p.name for p in (run / "artefactos" / "arboles").iterdir())
            self.assertEqual(names, ["revision.json"])


class TestFeedbackValidation(unittest.TestCase):
    def test_malformed_comments_are_rejected_with_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(Path(tmp))
            for bad in ("texto suelto", ["texto suelto"], {"node": "r1"}, [{"node": "r1", "text": 3}]):
                result = record_feedback(run, "problemas", bad, "")
                self.assertFalse(result["ok"], bad)
                self.assertIn("comentarios", result["error"])
            self.assertFalse((run / "artefactos" / "arboles" / "revision.json").exists())


class TestTreesHttpApi(unittest.TestCase):
    def test_get_feedback_and_approve_over_http(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer

        from morfeo.dashboard.server import MorfeoDashboardHandler

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "proposals").mkdir()
            run = make_run(workspace / "proposals")
            (workspace / "proposals" / ".current-run").write_text(run.name, encoding="utf-8")
            handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": workspace})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{server.server_address[1]}"

            def post(path: str, payload: dict) -> tuple[int, dict]:
                req = urllib.request.Request(
                    base + path, data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                try:
                    with urllib.request.urlopen(req) as resp:
                        return resp.status, json.loads(resp.read())
                except urllib.error.HTTPError as err:
                    return err.code, json.loads(err.read())

            try:
                with urllib.request.urlopen(base + "/api/trees") as resp:
                    data = json.loads(resp.read())
                self.assertTrue(data["ok"])
                self.assertEqual(data["stage"], "problemas")

                code, fb = post("/api/trees/feedback", {"tree": "problemas", "general": "Ajustar"})
                self.assertEqual(code, 200)
                self.assertIn("disenador-tikz", fb["prompt"])
                self.assertIn(f"proposals/{run.name}/artefactos/arboles/ajuste_problemas_01.md", fb["prompt"])

                code, bad = post("/api/trees/approve", {"tree": "objetivos"})
                self.assertEqual(code, 409)
                self.assertFalse(bad["ok"])

                code, ok = post("/api/trees/approve", {"tree": "problemas"})
                self.assertEqual(code, 200)
                self.assertTrue(ok["ok"])

                code, bad = post("/api/trees/feedback", {"tree": "problemas", "comments": "texto suelto"})
                self.assertEqual(code, 400)
                self.assertFalse(bad["ok"])
                self.assertIn("comentarios", bad["error"])

                # El sondeo de la pestaña no reconstruye el estado completo del proyecto.
                from unittest import mock
                with mock.patch("morfeo.dashboard.server.get_project_status", side_effect=AssertionError("estado completo")):
                    with urllib.request.urlopen(base + "/api/trees") as resp:
                        self.assertEqual(resp.status, 200)
                        self.assertTrue(json.loads(resp.read())["ok"])
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
