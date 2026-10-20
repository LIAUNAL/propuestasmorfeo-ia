#!/usr/bin/env python3
"""Tests for the deterministic figure pipeline and the Pi model policy.

Two framework invariants are protected here.

**Figure latency.** A figure's geometry used to be hand-authored by a model, and
the measured cost was ~28.8 minutes per figure for one diagram (three
`disenador-tikz` dispatches that exhausted their output budget without emitting a
report). The replacement is deterministic: a JSON spec goes in, and
render -> compile -> overfull autofix -> mechanical audit comes out. These tests
pin the contract that made that possible -- byte-identical renders, validated
specs, a bounded autofix loop, and a hard wall-clock budget -- and they run the
real pipeline, not a mock, whenever the poppler/TeX toolchain is present.

**No Claude dependency.** `.pi/` used to pin every proposal agent to
`claude-bridge/*`, which is a bridge to the Claude Agent SDK, and the file that
held the working Pi-native profiles (`.pi/subagents.json`) was untracked. These
tests pin the fix: one committed source of truth, the same models in the agent
frontmatter and in the profile store, and no bridge model anywhere in the port.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANTILLA_SCRIPTS = REPO_ROOT / "plantilla" / "scripts"
FIGURE_SCRIPTS = {
    name: PLANTILLA_SCRIPTS / f"{name}.py"
    for name in ("render_tikz", "audit_tikz", "figura", "compile_tikz")
}

_TOOLCHAIN = all(
    shutil.which(tool) for tool in ("pdflatex", "pdftoppm", "pdftocairo")
)


def load_render_module():
    """Import render_tikz.py by path so its module-level data can be inspected."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "render_tikz_under_test", FIGURE_SCRIPTS["render_tikz"]
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arbol_spec(**overrides) -> dict:
    spec = {
        "kind": "arbol",
        "groups": [
            {"id": "SP1", "title": "SP1 · Grupo uno",
             "causes": [{"id": "r1", "text": "Primera causa raíz del problema."}]},
            {"id": "SP2", "title": "SP2 · Grupo dos",
             "causes": [{"id": "r2", "text": "Segunda causa raíz del problema."}]},
        ],
        "trunk": {"label": "PROBLEMA CENTRAL (TRONCO)", "text": "Problema central del estudio."},
        "branches": [
            {"id": "b1", "text": "Primer efecto observado."},
            {"id": "b2", "text": "Segundo efecto observado."},
        ],
        "crown": {"label": "EFECTO FINAL", "text": "Efecto indirecto de mayor nivel."},
    }
    spec.update(overrides)
    return spec


def estado_arte_spec() -> dict:
    return {
        "kind": "estado_arte",
        "closing": "Frase transversal de cierre del mapa.",
        "links": [["c1", "c2"]],
        "clusters": [
            {"title": "Clúster uno", "limitation": "Limitante breve uno.",
             "papers": [{"id": "c1n1", "author": "Autor et al., 2025", "concept": "Concepto corto"}]},
            {"title": "Clúster dos", "limitation": "Limitante breve dos.",
             "papers": [{"id": "c2n6", "author": "Otra et al., 2024", "concept": "Otro concepto"}]},
        ],
    }


def metodologico_spec() -> dict:
    return {
        "kind": "metodologico",
        "trl": {"start": "TRL 3", "end": "TRL 6/7"},
        "beneficiaries": ["Estudiantes afectados"],
        "phases": [{"id": "f1", "title": "Fase 1 · Inicio", "text": "Texto de la fase.",
                    "novelty": "Novedad de la fase"}],
    }


class ProjectFixtureMixin:
    """A throwaway LaTeX project laid out like a real run."""

    def make_project(self, tmp: str) -> Path:
        project = Path(tmp) / "redaccion"
        (project / "sections").mkdir(parents=True)
        (project / "specs").mkdir(parents=True)
        (project / "scripts").mkdir(parents=True)
        for name in ("render_tikz", "audit_tikz", "figura", "compile_tikz"):
            shutil.copy2(FIGURE_SCRIPTS[name], project / "scripts" / f"{name}.py")
        return project

    def write_spec(self, project: Path, name: str, spec: dict) -> Path:
        path = project / "specs" / f"{name}.spec.json"
        path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def render(self, project: Path, name: str, extra: list[str] | None = None):
        return subprocess.run(
            [sys.executable, str(project / "scripts" / "render_tikz.py"),
             str(project / "specs" / f"{name}.spec.json"), "-o",
             str(project / "sections" / f"diag_{name}.tex")] + (extra or []),
            capture_output=True, text=True, cwd=str(project),
        )


class TestRenderDeterminism(unittest.TestCase, ProjectFixtureMixin):
    """The same spec must always produce byte-identical LaTeX."""

    def test_render_is_byte_identical_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            first = self.render(project, "arbol_problemas")
            self.assertEqual(first.returncode, 0, first.stderr)
            text_a = (project / "sections" / "diag_arbol_problemas.tex").read_text(encoding="utf-8")
            second = self.render(project, "arbol_problemas")
            self.assertEqual(second.returncode, 0, second.stderr)
            text_b = (project / "sections" / "diag_arbol_problemas.tex").read_text(encoding="utf-8")
            self.assertEqual(text_a, text_b, "el render no es determinista")

    def test_render_emits_the_contract_the_pipeline_depends_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            self.assertEqual(self.render(project, "arbol_problemas").returncode, 0)
            text = (project / "sections" / "diag_arbol_problemas.tex").read_text(encoding="utf-8")
            # In-file hyphenation off (survives being \input{} into main.tex).
            self.assertIn(r"\hyphenpenalty=10000", text)
            self.assertIn(r"\exhyphenpenalty=10000", text)
            # Canonical palette defined locally so standalone and inline agree.
            for colour in ("azulUNAL", "grisLabIA", "verdeGCPDS", "rojoLimitante"):
                self.assertIn(colour, text)
            # The copa never connects to a raíz.
            for draw in text.splitlines():
                if draw.strip().startswith(r"\draw") and "(copa" in draw:
                    self.assertNotRegex(draw, r"\(r\d+\)")
            # The line map the autofix resolves against exists and maps the trunk.
            line_map = json.loads((project / "sections" / "diag_arbol_problemas.map.json").read_text())
            self.assertIn("tronco", line_map.values())

    def test_tree_legend_names_the_mga_levels_not_a_solution(self):
        # MGA: the crown of a problem tree is the final indirect effect, never the solution.
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            self.assertEqual(self.render(project, "arbol_problemas").returncode, 0)
            text = (project / "sections" / "diag_arbol_problemas.tex").read_text(encoding="utf-8")
            self.assertNotIn("SOLUCIÓN", text)
            flat = re.sub(r"\s+", " ", text.replace("\\", " "))
            for word in ("EFECTO FINAL", "EFECTOS DIRECTOS", "PROBLEMA CENTRAL", "CAUSAS"):
                self.assertIn(word, flat)

    def test_all_three_kinds_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            for name, spec in (
                ("arbol_problemas", arbol_spec()),
                ("estado_arte", estado_arte_spec()),
                ("metodologico", metodologico_spec()),
            ):
                with self.subTest(kind=name):
                    self.write_spec(project, name, spec)
                    res = self.render(project, name)
                    self.assertEqual(res.returncode, 0, res.stderr)


class TestSpecValidation(unittest.TestCase, ProjectFixtureMixin):
    """A malformed spec must fail early with a message that names the field."""

    def test_duplicate_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            spec = arbol_spec()
            spec["groups"][1]["causes"][0]["id"] = "r1"  # duplicate
            self.write_spec(project, "arbol_problemas", spec)
            res = self.render(project, "arbol_problemas")
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("repetidos", res.stdout + res.stderr)

    def test_unknown_link_endpoint_is_rejected(self):
        """Inter-cluster links name CLUSTERS; an unknown one must be caught.

        A paper id here is a plausible authoring mistake (the cluster/pair
        distinction is easy to get wrong) and used to surface as
        `No shape named 'c4n1' is known` from deep inside pgf, so the message
        must name the offender.
        """
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            spec = estado_arte_spec()
            spec["links"] = [["c1", "c99"]]
            self.write_spec(project, "estado_arte", spec)
            res = self.render(project, "estado_arte")
            self.assertNotEqual(res.returncode, 0)
            combined = res.stdout + res.stderr
            self.assertIn("c99", combined)
            self.assertIn("enlace", combined)

    def test_unknown_arrow_endpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            spec = estado_arte_spec()
            spec["clusters"][0]["arrows"] = [["c1n1", "c2n6"]]
            self.write_spec(project, "estado_arte", spec)
            res = self.render(project, "estado_arte")
            self.assertNotEqual(res.returncode, 0)
            combined = res.stdout + res.stderr
            self.assertIn("c2n6", combined)
            self.assertIn("arista", combined)

    def test_unknown_kind_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "raro", {"kind": "no_existe"})
            res = self.render(project, "raro")
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("kind", res.stdout + res.stderr)


class TestStyleTemplatesAreBalanced(unittest.TestCase):
    """An unbalanced brace in a style template fails the whole compile."""

    def test_every_style_template_has_balanced_braces(self):
        module = load_render_module()
        for kind, template in module.PREAMBLE_STYLES.items():
            with self.subTest(kind=kind):
                depth = 0
                for line in template.splitlines():
                    depth += line.count("{") - line.count("}")
                self.assertEqual(depth, 0, f"estilos desbalanceados en {kind}")

    def test_every_style_role_is_declared_in_font(self):
        """A style that names an undeclared role ships a literal brace to TeX.

        `_styles` fills templates by textual replacement, so a placeholder whose
        role is absent from `FONT` is never substituted. It reaches the `.tex` as
        `\fontsize{{FP_ETIQUETA}}`, TeX reads `{FP_ETIQUETA}` as the numeric
        argument and dies with `Missing number, treated as zero` tens of lines
        from the cause. That is what happened to the `etiqueta` and `benef`
        styles of the `metodologico` template: the kind had never been rendered,
        so nothing caught it until the first real diagram of that kind.
        """
        module = load_render_module()
        declared = set(module.FONT)
        for kind, template in module.PREAMBLE_STYLES.items():
            used = {
                m.group(1).lower()
                for m in re.finditer(r"\{\{(?:FP|FS)_([A-Z_]+)\}\}", template)
            }
            with self.subTest(kind=kind):
                self.assertTrue(
                    used <= declared,
                    f"los estilos de {kind} referencian roles ausentes de FONT: "
                    f"{sorted(used - declared)}",
                )

    def test_node_role_mapping(self):
        module = load_render_module()
        for node_id, role in (
            ("tSP1", "gtitulo"), ("r7", "raiz"), ("b3", "rama"),
            ("tronco", "tronco"), ("copa", "copa"),
            ("c2t", "ctitulo"), ("c2lim", "limitex"),
            ("c1n5", "paper"), ("f2", "fase"), ("f2n", "novedad"),
        ):
            with self.subTest(node=node_id):
                self.assertEqual(module.role_for_node(node_id), role)


@unittest.skipUnless(_TOOLCHAIN, "requiere pdflatex + pdftoppm + pdftocairo")
class TestFigurePipelineBudget(unittest.TestCase, ProjectFixtureMixin):
    """End-to-end: the real pipeline must PASS well inside the 3-minute ceiling."""

    def _run_figura(self, project: Path, name: str, budget: float = 180.0):
        return subprocess.run(
            [sys.executable, str(project / "scripts" / "figura.py"), name,
             "--spec", str(project / "specs" / f"{name}.spec.json"),
             "--project", str(project), "--budget-s", str(budget), "--json"],
            capture_output=True, text=True, cwd=str(project),
        )

    def test_clean_run_passes_within_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            res = self._run_figura(project, "arbol_problemas")
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            report = json.loads(res.stdout)
            self.assertEqual(report["verdict"], "PASS")
            self.assertTrue(report["within_budget"])
            # The whole point of the change: the ceiling is 180 s and the real
            # cost must be a small fraction of it.
            self.assertLess(report["elapsed_s"], 60, "el pipeline de figura se degradó")
            self.assertIn("arbol_problemas-1.png", report["outputs"]["png"])
            self.assertIsNotNone(report["outputs"]["svg"])

    def test_overfull_is_fixed_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            # Seed impossible widths so the first compile really overflows. The
            # overrides file is authoritative (it is the autofix's own memory),
            # so these widths are used verbatim instead of the fit heuristic.
            # 0.9 cm cannot hold a ~1.2 cm word, which is what forces the
            # `Overfull \hbox` the loop has to resolve.
            (project / "specs" / "arbol_problemas.overrides.json").write_text(
                json.dumps({"widths": {"raiz": 0.9, "gtitulo": 0.9,
                                        "rama": 0.9, "tronco": 1.5, "copa": 1.5}}),
                encoding="utf-8",
            )
            res = self._run_figura(project, "arbol_problemas")
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            report = json.loads(res.stdout)
            self.assertEqual(report["verdict"], "PASS")
            # It needed more than one compile, and the fix came from the autofix
            # loop rather than from a model.
            self.assertGreater(report["iterations"], 1)
            self.assertIn("no_overfull",
                          [c["id"] for c in report["audit"]["checks"] if c["ok"]])
            overrides = json.loads(
                (project / "specs" / "arbol_problemas.overrides.json").read_text(encoding="utf-8")
            )
            self.assertGreater(overrides["widths"]["raiz"], 0.9)

    def test_page_fit_is_reported_but_not_enforced_by_default(self):
        """The size is always reported; the budget is opt-in.

        Enforcing it by default would fail every figure that `main.tex`
        legitimately scales with a resizebox, which is a supported (if
        suboptimal) assembly choice.
        """
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            res = self._run_figura(project, "arbol_problemas")
            report = json.loads(res.stdout)
            self.assertEqual(report["verdict"], "PASS")
            check_ids = {c["id"] for c in report["audit"]["checks"]}
            self.assertIn("figure_size", check_ids)
            self.assertNotIn("fits_page", check_ids)
            self.assertIsNone(report["page_fit_cm"])

    def test_an_impossible_page_budget_fails_with_a_named_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            res = subprocess.run(
                [sys.executable, str(project / "scripts" / "figura.py"),
                 "arbol_problemas", "--spec",
                 str(project / "specs" / "arbol_problemas.spec.json"),
                 "--project", str(project), "--page-fit", "2x2", "--json"],
                capture_output=True, text=True, cwd=str(project),
            )
            self.assertNotEqual(res.returncode, 0)
            report = json.loads(res.stdout)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("fits_page", report["audit"]["failed"])
            self.assertEqual(report["page_fit_cm"], [2.0, 2.0])
            # The size is still reported, so the fix is a number, not a guess.
            size = next(
                c["detail"] for c in report["audit"]["checks"] if c["id"] == "figure_size"
            )
            self.assertIn("x", size)

    def test_legibility_proxy_reports_the_smallest_printed_size(self):
        """The audit measures legibility instead of leaving it to a model.

        The failure the operator hit was a map scaled to 74 %, which printed
        audited 12/14 pt type at ~9 pt. That is a number, so it is checked.
        """
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            res = self._run_figura(project, "arbol_problemas")
            report = json.loads(res.stdout)
            check = next(
                c for c in report["audit"]["checks"] if c["id"] == "legibility_min_font_pt"
            )
            self.assertTrue(check["ok"], check["detail"])
            self.assertIn("pt", check["detail"])

    def test_legibility_floor_fails_below_the_canonical_minimum(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            spec = arbol_spec()
            spec["fonts"] = {"rama": [4, 5]}
            self.write_spec(project, "arbol_problemas", spec)
            res = self._run_figura(project, "arbol_problemas")
            self.assertNotEqual(res.returncode, 0)
            report = json.loads(res.stdout)
            self.assertIn("legibility_min_font_pt", report["audit"]["failed"])

    def test_page_fit_detail_quantifies_the_required_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            res = subprocess.run(
                [sys.executable, str(project / "scripts" / "figura.py"),
                 "arbol_problemas", "--spec",
                 str(project / "specs" / "arbol_problemas.spec.json"),
                 "--project", str(project), "--page-fit", "4x4", "--json"],
                capture_output=True, text=True, cwd=str(project),
            )
            report = json.loads(res.stdout)
            detail = next(
                c["detail"] for c in report["audit"]["checks"] if c["id"] == "fits_page"
            )
            self.assertIn("escalar al", detail)

    def test_a_hand_edit_of_the_tex_is_overwritten_by_the_next_render(self):
        """The spec is the only authoring surface; `.tex` is generated output.

        This is the property that makes hand-tuning impossible to rely on: if
        someone edits the generated LaTeX, the next pipeline run silently
        restores the spec-derived version. The audit's own hyphenation check is
        exercised directly on a doctored file below, because going through
        `figura.py` can never observe a hand edit.
        """
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            self.assertEqual(self._run_figura(project, "arbol_problemas").returncode, 0)
            tex = project / "sections" / "diag_arbol_problemas.tex"
            generated = tex.read_text(encoding="utf-8")
            tex.write_text(generated.replace(r"\hyphenpenalty=10000", ""), encoding="utf-8")
            self.assertEqual(self._run_figura(project, "arbol_problemas").returncode, 0)
            self.assertEqual(
                tex.read_text(encoding="utf-8"), generated,
                "un edit manual del .tex debe ser sobrescrito por el siguiente render",
            )

    def test_audit_rejects_a_tex_without_the_hyphenation_guard(self):
        """The audit flags a diagram source whose hyphenation guard is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(tmp)
            self.write_spec(project, "arbol_problemas", arbol_spec())
            self.assertEqual(self._run_figura(project, "arbol_problemas").returncode, 0)
            tex = project / "sections" / "diag_arbol_problemas.tex"
            tex.write_text(
                tex.read_text(encoding="utf-8").replace(r"\hyphenpenalty=10000", ""),
                encoding="utf-8",
            )
            compile_out = subprocess.run(
                [sys.executable, str(project / "scripts" / "compile_tikz.py"),
                 "arbol_problemas:tikz"],
                capture_output=True, text=True, cwd=str(project),
            )
            stdout_file = project / "compile_stdout.txt"
            stdout_file.write_text(compile_out.stdout + compile_out.stderr, encoding="utf-8")
            audit = subprocess.run(
                [sys.executable, str(project / "scripts" / "audit_tikz.py"),
                 "arbol_problemas", "--project", str(project),
                 "--spec", str(project / "specs" / "arbol_problemas.spec.json"),
                 "--compile-stdout", str(stdout_file), "--json"],
                capture_output=True, text=True, cwd=str(project),
            )
            report = json.loads(audit.stdout)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("hyphenation_off", report["failed"])


class TestPiModelPolicy(unittest.TestCase):
    """The Pi port must never acquire an external Claude dependency."""

    def setUp(self):
        self.models = json.loads(
            (REPO_ROOT / "scripts" / "agent-models.json").read_text(encoding="utf-8")
        )

    def test_no_bridge_model_in_the_port(self):
        bridge = subprocess.run(
            ["grep", "-rl", "claude-bridge/", str(REPO_ROOT / ".pi" / "agents"),
             str(REPO_ROOT / ".pi" / "subagents.json")],
            capture_output=True, text=True,
        )
        self.assertEqual(
            bridge.stdout.strip(), "",
            f"un modelo de puente a Claude sobrevivió en el puerto Pi: {bridge.stdout}",
        )

    def test_frontmatter_and_profile_store_agree(self):
        profiles = json.loads(
            (REPO_ROOT / ".pi" / "subagents.json").read_text(encoding="utf-8")
        )["model_profiles"]
        for agent, tier_name in self.models["agents"].items():
            with self.subTest(agent=agent):
                tier = self.models["tiers"][tier_name]
                text = (REPO_ROOT / ".pi" / "agents" / f"{agent}.md").read_text(encoding="utf-8")
                self.assertIn(f"model: {tier['model']}", text)
                self.assertIn(f"thinking: {tier['thinking']}", text)
                self.assertEqual(profiles[agent]["model"], tier["model"])
                self.assertEqual(profiles[agent]["effort"], tier["thinking"])

    def test_every_ported_agent_has_a_tier(self):
        ported = {p.stem for p in (REPO_ROOT / ".pi" / "agents").glob("*.md")}
        declared = set(self.models["agents"])
        self.assertEqual(
            ported - declared, set(),
            "un agente portado no tiene tier en scripts/agent-models.json",
        )

    def test_profile_store_travels_with_the_repo(self):
        """It must not be gitignored and must be installed by the kit.

        Checked with `git check-ignore` rather than `git ls-files` so the
        invariant holds in a working tree too: the requirement is that the file
        travels with the repository, not that it is already committed.
        """
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", ".pi/subagents.json"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        self.assertNotEqual(
            ignored.returncode, 0,
            ".pi/subagents.json está en .gitignore: sin él un clon nuevo cae al "
            "frontmatter del agente y pierde los modelos Pi-nativos",
        )
        kit = json.loads(
            (REPO_ROOT / "scripts" / "kit-manifest.json").read_text(encoding="utf-8")
        )["kit_paths"]
        self.assertIn(
            "scripts/agent-models.json", kit,
            "el manifiesto debe instalar la fuente de verdad de modelos",
        )
        self.assertIn(
            "scripts/gen-pi.py", kit,
            "el manifiesto debe instalar el generador que escribe .pi/subagents.json",
        )

    def test_kit_manifest_excludes_runtime_ports_but_ships_their_generators(self):
        kit = json.loads(
            (REPO_ROOT / "scripts" / "kit-manifest.json").read_text(encoding="utf-8")
        )["kit_paths"]
        for runtime in (".pi/", ".opencode/", ".agent/"):
            self.assertFalse(
                [k for k in kit if k.startswith(runtime)],
                f"{runtime} no puede estar en kit_paths: `marco init --tools` los genera",
            )
        for generator in ("scripts/gen-pi.py", "scripts/gen-opencode.py",
                          "scripts/gen-antigravity.py", "scripts/agent-models.json"):
            self.assertIn(generator, kit)

    def test_kit_manifest_ships_the_annex_converter(self):
        kit = json.loads(
            (REPO_ROOT / "scripts" / "kit-manifest.json").read_text(encoding="utf-8")
        )["kit_paths"]
        self.assertIn("plantilla/scripts/anexos_a_pdf.sh", kit)

    def test_kit_manifest_ships_the_figure_pipeline(self):
        kit = json.loads(
            (REPO_ROOT / "scripts" / "kit-manifest.json").read_text(encoding="utf-8")
        )["kit_paths"]
        for script in ("plantilla/scripts/compile_tikz.py",
                       "plantilla/scripts/render_tikz.py",
                       "plantilla/scripts/audit_tikz.py",
                       "plantilla/scripts/figura.py"):
            self.assertIn(script, kit)


class TestAgentModelReconciliation(unittest.TestCase):
    """The three model tables must agree and match the ACTIVE gentle profile.

    They did not: the port pinned every agent to `claude-bridge/*` while the
    active profile was Pi-native, and nothing detected it. These tests pin the
    checker that now runs at `/propuesta-init`.
    """

    CHECKER = REPO_ROOT / "scripts" / "check-agent-models.py"

    def _run(self, project: Path, profiles: Path):
        return subprocess.run(
            [sys.executable, str(self.CHECKER), "--project", str(project),
             "--profiles", str(profiles), "--json"],
            capture_output=True, text=True,
        )

    def _fixture(self, tmp: str) -> tuple[Path, Path]:
        """A minimal project tree: SSOT + the two generated artifacts."""
        project = Path(tmp) / "proj"
        (project / "scripts").mkdir(parents=True)
        (project / ".pi" / "agents").mkdir(parents=True)
        shutil.copy2(REPO_ROOT / "scripts" / "agent-models.json",
                     project / "scripts" / "agent-models.json")
        shutil.copy2(REPO_ROOT / ".pi" / "subagents.json",
                     project / ".pi" / "subagents.json")
        for ported in (REPO_ROOT / ".pi" / "agents").glob("*.md"):
            shutil.copy2(ported, project / ".pi" / "agents" / ported.name)
        profiles = Path(tmp) / "profiles.json"
        profiles.write_text(json.dumps({
            "kind": "gentle-pi.agent_model_profiles", "version": 1, "active": "test",
            "profiles": {"test": {
                "orchestrator": {"model": "nan/deepseek-v4-flash", "thinking": "high"},
                "sdd-spec": {"model": "nan/glm5.3-flash", "thinking": "high"},
            }},
        }, indent=2) + "\n", encoding="utf-8")
        return project, profiles

    def test_the_real_repository_reconciles(self):
        res = subprocess.run(
            [sys.executable, str(self.CHECKER), "--project", str(REPO_ROOT),
             "--json"],
            capture_output=True, text=True,
        )
        report = json.loads(res.stdout)
        self.assertEqual(res.returncode, 0, report["problems"])
        self.assertEqual(report["verdict"], "PASS")
        if report["active_profile_providers"]:
            self.assertEqual(report["framework_providers"],
                             report["active_profile_providers"])

    def test_a_frontmatter_that_disagrees_with_the_source_of_truth_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, profiles = self._fixture(tmp)
            target = project / ".pi" / "agents" / "revisor.md"
            target.write_text(
                target.read_text(encoding="utf-8").replace(
                    "model: nan/glm5.3-flash", "model: claude-bridge/claude-sonnet-5"
                ),
                encoding="utf-8",
            )
            res = self._run(project, profiles)
            self.assertNotEqual(res.returncode, 0)
            report = json.loads(res.stdout)
            self.assertTrue(
                any("frontmatter" in problem for problem in report["problems"]),
                report["problems"],
            )

    def test_a_provider_the_active_profile_does_not_use_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, profiles = self._fixture(tmp)
            source = json.loads(
                (project / "scripts" / "agent-models.json").read_text(encoding="utf-8")
            )
            source["tiers"]["reasoning"]["model"] = "openai-codex/gpt-5.6-luna"
            (project / "scripts" / "agent-models.json").write_text(
                json.dumps(source, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            res = self._run(project, profiles)
            self.assertNotEqual(res.returncode, 0)
            report = json.loads(res.stdout)
            self.assertTrue(
                any("proveedor" in problem for problem in report["problems"]),
                report["problems"],
            )

    def test_an_agent_without_a_tier_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, profiles = self._fixture(tmp)
            source = json.loads(
                (project / "scripts" / "agent-models.json").read_text(encoding="utf-8")
            )
            del source["agents"]["revisor"]
            (project / "scripts" / "agent-models.json").write_text(
                json.dumps(source, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            res = self._run(project, profiles)
            self.assertNotEqual(res.returncode, 0)
            report = json.loads(res.stdout)
            self.assertTrue(
                any("sin tier" in problem for problem in report["problems"]),
                report["problems"],
            )

    def test_a_missing_profile_store_is_a_note_not_a_failure(self):
        """A machine without `gentle:profiles` must not block the pipeline."""
        with tempfile.TemporaryDirectory() as tmp:
            project, _ = self._fixture(tmp)
            res = self._run(project, Path(tmp) / "no-existe.json")
            report = json.loads(res.stdout)
            self.assertEqual(report["verdict"], "PASS")
            self.assertTrue(any("perfil activo" in note for note in report["notes"]))


class TestNoExternalMemoryDependency(unittest.TestCase):
    """A fresh clone must run with no memory server available."""

    def test_insumos_cache_is_filesystem_primary(self):
        text = (REPO_ROOT / ".claude" / "agents" / "insumos-observador.md").read_text(encoding="utf-8")
        self.assertIn("artefactos/insumos-cache/", text,
                      "la caché de insumos debe vivir en el sistema de archivos de la corrida")
        self.assertIn("Disco (primario)", text,
                      "el disco debe declararse como fuente primaria de la caché")
        self.assertIn("espejo opcional", text.lower(),
                      "la memoria debe declararse como espejo opcional, no como fuente")

    def test_no_duplicated_artefactos_path_in_canonical_sources(self):
        offenders = subprocess.run(
            ["grep", "-rl", "artefactos/artefactos", str(REPO_ROOT / ".claude")],
            capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(offenders, "", f"ruta con artefactos/ duplicado: {offenders}")


if __name__ == "__main__":
    unittest.main()
