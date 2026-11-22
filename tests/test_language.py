"""Project writing language (S3 of idioma-tablero-traduccion).

`"lang"` in `.morfeo/config.json` is the single source of truth (`es` by
default). `morfeo init --lang` sets it, `morfeo config lang` reads and changes
it afterwards and refuses English on the SGR flow, and each run records the
language it was created with so a later project change never mixes languages
inside one run.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from morfeo.cli import main  # noqa: E402
from morfeo.core import language  # noqa: E402
from morfeo.core.status import get_project_status  # noqa: E402

SCRIPT = REPO / "scripts" / "language.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("kit_language", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as exc:  # argparse errors
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def _project(root: Path, **config) -> Path:
    for marker in (".morfeo", ".marco"):
        (root / marker).mkdir(parents=True, exist_ok=True)
        (root / marker / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    return root


def _run(project: Path, run_id: str, manifest: str | None) -> Path:
    run = project / "proposals" / run_id
    run.mkdir(parents=True)
    if manifest is not None:
        (run / "_run.md").write_text(manifest, encoding="utf-8")
    return run


SPANISH_RUN = "| run-id | `a` |\n| flujo | base |\n"
ENGLISH_RUN = "| run-id | `a` |\n| flujo | base |\n| idioma | en |\n"


class ProjectLanguageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.script = _load_script()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _both(self, path: Path) -> tuple[str, str]:
        return language.read_project_lang(path), self.script.project_lang(path)

    def test_missing_config_is_spanish(self) -> None:
        self.assertEqual(self._both(self.root), ("es", "es"))

    def test_lang_en_is_english(self) -> None:
        _project(self.root, lang="en", flujo="base")
        self.assertEqual(self._both(self.root), ("en", "en"))

    def test_unknown_value_is_spanish(self) -> None:
        _project(self.root, lang="fr")
        self.assertEqual(self._both(self.root), ("es", "es"))

    def test_the_sgr_flow_is_always_spanish(self) -> None:
        _project(self.root, lang="en", flujo="sgr")
        self.assertEqual(self._both(self.root), ("es", "es"))

    def test_legacy_marco_config_is_read(self) -> None:
        (self.root / ".marco").mkdir()
        (self.root / ".marco" / "config.json").write_text('{"lang": "en"}', encoding="utf-8")
        self.assertEqual(self._both(self.root), ("en", "en"))

    def test_the_script_cli_prints_the_language(self) -> None:
        _project(self.root, lang="en")
        run = _run(self.root, "2026-01-a", ENGLISH_RUN)
        for argv, expected in ((["project", str(self.root)], "en"), (["run", str(run)], "en")):
            result = subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True)
            self.assertEqual((result.returncode, result.stdout.strip()), (0, expected), result.stderr)


class RunLanguageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.script = _load_script()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _both(self, run: Path) -> tuple[str, str]:
        return language.read_run_lang(run), self.script.run_lang(run)

    def test_a_run_keeps_the_language_it_was_created_with(self) -> None:
        _project(self.root, lang="en")
        spanish = _run(self.root, "2026-01-es", SPANISH_RUN)
        english = _run(self.root, "2026-01-en", ENGLISH_RUN)
        self.assertEqual(self._both(spanish), ("es", "es"))
        self.assertEqual(self._both(english), ("en", "en"))

    def test_an_english_run_stays_english_after_the_project_goes_back_to_spanish(self) -> None:
        _project(self.root, lang="es")
        self.assertEqual(self._both(_run(self.root, "2026-01-en", ENGLISH_RUN)), ("en", "en"))

    def test_a_run_without_manifest_follows_the_project(self) -> None:
        _project(self.root, lang="en")
        self.assertEqual(self._both(_run(self.root, "2026-01-x", None)), ("en", "en"))

    def test_an_sgr_run_is_spanish_even_with_an_english_row(self) -> None:
        _project(self.root, lang="en", flujo="sgr")
        self.assertEqual(self._both(_run(self.root, "2026-01-x", ENGLISH_RUN)), ("es", "es"))


class ConfigCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _configs(self) -> list[dict]:
        return [json.loads((self.root / m / "config.json").read_text(encoding="utf-8")) for m in (".morfeo", ".marco")]

    def test_reading_prints_the_current_language(self) -> None:
        _project(self.root, lang="es", flujo="base")
        code, out, _ = _cli("config", "lang", "--dir", str(self.root))
        self.assertEqual((code, out.strip()), (0, "es"))

    def test_setting_english_writes_both_configs_and_keeps_other_keys(self) -> None:
        _project(self.root, version="0.9.1", lang="es", preset="claude", tools=["claude"], title="T", flujo="base")
        code, out, err = _cli("config", "lang", "en", "--dir", str(self.root))
        self.assertEqual(code, 0, err)
        for config in self._configs():
            self.assertEqual(config["lang"], "en")
            self.assertEqual((config["preset"], config["title"], config["flujo"]), ("claude", "T", "base"))
        self.assertIn("en", out)
        self.assertIn("conservan", out)
        self.assertEqual(language.read_project_lang(self.root), "en")

    def test_the_sgr_flow_refuses_english(self) -> None:
        _project(self.root, lang="es", flujo="sgr")
        code, out, err = _cli("config", "lang", "en", "--dir", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("SGR", err)
        self.assertIn("español", err)
        self.assertEqual([c["lang"] for c in self._configs()], ["es", "es"])

    def test_the_sgr_flow_accepts_spanish(self) -> None:
        _project(self.root, lang="es", flujo="sgr")
        code, _, err = _cli("config", "lang", "es", "--dir", str(self.root))
        self.assertEqual(code, 0, err)

    def test_an_unknown_language_is_refused(self) -> None:
        _project(self.root, lang="es")
        code, _, err = _cli("config", "lang", "fr", "--dir", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("es, en", err)
        self.assertEqual([c["lang"] for c in self._configs()], ["es", "es"])

    def test_a_folder_that_is_not_a_project_is_refused(self) -> None:
        code, _, err = _cli("config", "lang", "en", "--dir", str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("proyecto Morfeo", err)

    def test_the_help_names_the_command(self) -> None:
        code, out, _ = _cli("config", "--help")
        self.assertEqual(code, 0)
        self.assertIn("lang", out)
        self.assertIn("SGR", out)


class InitLanguageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_init_refuses_english_on_the_sgr_flow(self) -> None:
        target = self.root / "ws"
        code, _, err = _cli("init", str(target), "--tools", "claude", "--sgr", "--lang", "en")
        self.assertEqual(code, 2)
        self.assertIn("SGR", err)
        self.assertFalse((target / ".morfeo").exists())

    def test_init_with_english_writes_lang_and_status_reports_it(self) -> None:
        target = self.root / "ws"
        code, _, err = _cli("init", str(target), "--tools", "claude", "--lang", "en")
        self.assertEqual(code, 0, err)
        self.assertEqual(language.read_project_lang(target), "en")
        self.assertEqual(get_project_status(target, force_refresh=True)["lang"], "en")

    def test_init_without_flag_stays_spanish(self) -> None:
        target = self.root / "ws"
        code, _, err = _cli("init", str(target), "--tools", "claude", "--sgr")
        self.assertEqual(code, 0, err)
        self.assertEqual(get_project_status(target, force_refresh=True)["lang"], "es")


if __name__ == "__main__":
    unittest.main()
