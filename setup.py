"""Build shim: refresh the bundled kit before setuptools assembles the wheel.

The kit (``src/morfeo/_kit``) is a generated snapshot of the framework's
copy-on-init assets. Refreshing it here means ``pip install .`` or ``pipx install .``
always ships a kit that matches the checkout, with no manual step to forget.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent


class BuildPyWithKit(build_py):
    def run(self) -> None:
        build_kit = ROOT / "scripts" / "build-kit.py"
        if build_kit.is_file():
            subprocess.run(
                [sys.executable, str(build_kit), "--quiet"],
                cwd=ROOT,
                check=True,
            )
        super().run()


setup(cmdclass={"build_py": BuildPyWithKit})
