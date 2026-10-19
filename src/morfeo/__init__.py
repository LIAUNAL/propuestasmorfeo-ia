"""Morfeo IA — CLI workspace orchestrator for AI research grant proposals.

Developed at Laboratorio de Inteligencia Artificial (LIA)
Universidad Nacional de Colombia, Sede Manizales.
"""

from __future__ import annotations

__version__ = "0.5.4"
__author__ = "Laboratorio de Inteligencia Artificial UNAL"
__email__ = "amalvarezme@unal.edu.co"

from .core.export import export_project
from .core.import_project import import_project
from .errors import MorfeoError, UserError

__all__ = ["__version__", "MorfeoError", "UserError", "export_project", "import_project"]
