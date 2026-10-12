"""Guards for PyPI publishing metadata, bundle completeness, and release workflow."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYPROJECT = REPO / "pyproject.toml"
WORKFLOW = REPO / ".github" / "workflows" / "publish.yml"

KIT_SENTINELS = (
    "morfeo/_kit/kit-manifest.json",
    "morfeo/_kit/requirements.txt",
    "morfeo/_kit/.claude/agents/bibliografo-propuesta.md",
    "morfeo/_kit/.gitignore",
    "morfeo/_kit/.mcp.json",
)


def pyproject() -> dict:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


class PublishingMetadataTests(unittest.TestCase):
    """The fields that decide what a stranger sees on the project page."""

    def setUp(self) -> None:
        self.project = pyproject()["project"]

    def test_names_who_publishes_it(self) -> None:
        authors = self.project.get("authors")
        self.assertTrue(authors, "pyproject declares no authors")
        for author in authors:
            self.assertTrue(author.get("name"), f"author entry without a name: {author!r}")

    def test_declares_a_licence_the_index_can_read(self) -> None:
        licence = self.project.get("license")
        self.assertTrue(licence, "pyproject declares no license")
        self.assertTrue((REPO / "LICENSE").is_file(), "declared licence has no LICENSE file")

    def test_carries_the_readme_as_the_long_description(self) -> None:
        readme = self.project.get("readme")
        self.assertTrue(readme, "pyproject declares no readme")
        name = readme if isinstance(readme, str) else readme.get("file", "")
        self.assertTrue((REPO / name).is_file(), f"readme {name!r} does not exist")

    def test_points_at_its_own_source(self) -> None:
        urls = self.project.get("urls") or {}
        self.assertTrue(urls, "pyproject declares no project URLs")
        joined = " ".join(urls.values())
        self.assertIn("github.com", joined, "no project URL points at the source repository")

    def test_classifies_itself_for_the_index(self) -> None:
        classifiers = self.project.get("classifiers") or []
        self.assertTrue(classifiers, "pyproject declares no classifiers")
        prefixes = {value.split(" :: ")[0] for value in classifiers}
        for required in ("Programming Language", "Intended Audience", "Topic"):
            self.assertIn(required, prefixes, f"no {required} classifier")

    def test_states_the_licence_once(self) -> None:
        classifiers = self.project.get("classifiers") or []
        legacy = [value for value in classifiers if value.startswith("License ::")]
        self.assertEqual(legacy, [], "legacy License :: classifier conflicts with SPDX license")

    def test_still_derives_the_version_rather_than_restating_it(self) -> None:
        self.assertIn("version", pyproject()["project"].get("dynamic", []))
        self.assertNotIn("version", pyproject()["project"])


class BuiltArtifactsCarryTheKitTests(unittest.TestCase):
    """Ensure built wheel and sdist actually carry the full kit and dotfiles."""

    @classmethod
    def setUpClass(cls) -> None:
        build_kit = REPO / "scripts" / "build-kit.py"
        subprocess.run([sys.executable, str(build_kit), "--quiet"], cwd=REPO, check=True)

        cls._tmp = tempfile.mkdtemp(prefix="morfeo-dist-")
        result = subprocess.run(
            ["uv", "build", "--out-dir", cls._tmp],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(f"`uv build` failed:\n{result.stdout}\n{result.stderr}")
        out = Path(cls._tmp)
        cls.wheel = next(iter(sorted(out.glob("*.whl"))), None)
        cls.sdist = next(iter(sorted(out.glob("*.tar.gz"))), None)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "_tmp"):
            shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_a_wheel_and_an_sdist_were_produced(self) -> None:
        self.assertIsNotNone(self.wheel, "no wheel was built")
        self.assertIsNotNone(self.sdist, "no sdist was built")

    def test_the_wheel_carries_the_generated_kit(self) -> None:
        with zipfile.ZipFile(self.wheel) as archive:
            names = set(archive.namelist())
        for sentinel in KIT_SENTINELS:
            self.assertIn(sentinel, names, f"the wheel has no {sentinel}")

    def test_the_sdist_carries_the_generated_kit(self) -> None:
        with tarfile.open(self.sdist) as archive:
            names = set(archive.getnames())
        for sentinel in KIT_SENTINELS:
            self.assertTrue(
                any(name.endswith(sentinel.replace("morfeo/", "src/morfeo/")) or name.endswith(sentinel) for name in names),
                f"the sdist has no {sentinel}",
            )

    def test_every_file_stays_under_the_index_limit(self) -> None:
        limit = 100 * 1024 * 1024
        for artifact in (self.wheel, self.sdist):
            size = artifact.stat().st_size
            self.assertLess(size, limit, f"{artifact.name} exceeds 100 MB")


class PublishingWorkflowTests(unittest.TestCase):
    """The workflow has to build the kit and authenticate securely."""

    def setUp(self) -> None:
        if not WORKFLOW.is_file():
            self.fail(f"no publishing workflow at {WORKFLOW.relative_to(REPO)}")
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_builds_the_kit_before_packaging(self) -> None:
        self.assertIn("scripts/build-kit.py", self.text)
        kit_at = self.text.index("scripts/build-kit.py")
        build_at = min(
            (self.text.index(token) for token in ("python -m build", "uv build") if token in self.text),
            default=-1,
        )
        self.assertNotEqual(build_at, -1, "workflow never builds the package")
        self.assertLess(kit_at, build_at, "kit must be built before package")

    def test_authenticates_without_a_long_lived_secret(self) -> None:
        self.assertIn("id-token: write", self.text)
        for forbidden in ("PYPI_API_TOKEN", "password:"):
            self.assertNotIn(forbidden, self.text, f"workflow references forbidden secret {forbidden}")

    def test_is_triggered_by_a_release_or_dispatch(self) -> None:
        head = self.text.split("jobs:", 1)[0]
        self.assertTrue("release:" in head or "workflow_dispatch:" in head)
        self.assertNotIn("branches:\n      - main", head)


if __name__ == "__main__":
    unittest.main()
