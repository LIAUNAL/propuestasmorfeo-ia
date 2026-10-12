"""Exception hierarchy for Morfeo IA."""

from __future__ import annotations


class MorfeoError(Exception):
    """Base exception for all Morfeo errors."""

    exit_code: int = 1

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class UserError(MorfeoError):
    """User input or configuration defect."""

    exit_code: int = 2


class SourceError(MorfeoError):
    """Missing or corrupted kit source asset."""

    exit_code: int = 3


class KitError(MorfeoError):
    """Kit integrity failure or manifest mismatch."""

    exit_code: int = 4
