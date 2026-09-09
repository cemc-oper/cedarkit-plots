"""Compiler errors and structured non-fatal diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


class RecipeCompileError(ValueError):
    def __init__(self, message: str, *, origin: str = "<memory>", code: str = "compile_error"):
        self.origin, self.code = origin, code
        super().__init__(f"{origin}: {message}")


@dataclass(frozen=True)
class PlanIssue:
    code: str
    message: str
    origin: str = ""
    severity: str = "warning"

