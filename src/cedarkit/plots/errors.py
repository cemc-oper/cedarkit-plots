"""Errors and immutable diagnostics used by the new plotting API.

The configuration layer deliberately keeps diagnostics independent from
Matplotlib and from the template package.  The same values can therefore be
used by a future ``Panel`` without making configuration parsing a rendering
operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Issue:
    """A structured, read-only configuration diagnostic."""

    code: str
    message: str
    path: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("Issue.code must be a non-empty string")
        if not isinstance(self.message, str):
            raise TypeError("Issue.message must be a string")
        object.__setattr__(self, "path", tuple(str(item) for item in self.path))

    @property
    def location(self) -> str:
        """A dotted path suitable for concise error messages."""

        return ".".join(self.path)


class ConfigError(ValueError):
    """Raised when configuration cannot be accepted or completed."""

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str = "invalid_config",
        path: Iterable[str] = (),
        issues: Iterable[Issue] = (),
    ) -> None:
        collected = tuple(issues)
        if not collected:
            collected = (Issue(code=code, message=message or code, path=tuple(path)),)
        self.issues = collected
        self.code = collected[0].code
        self.path = collected[0].path
        if message is None:
            message = "; ".join(issue.message for issue in collected)
        super().__init__(message)


class _IssueError(ValueError):
    """Base for user-facing value errors carrying structured issues."""

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str = "invalid_content",
        path: Iterable[str] = (),
        issues: Iterable[Issue] = (),
    ) -> None:
        collected = tuple(issues)
        if not collected:
            collected = (Issue(code=code, message=message or code, path=tuple(path)),)
        self.issues = collected
        self.code = collected[0].code
        self.path = collected[0].path
        super().__init__(message or "; ".join(issue.message for issue in collected))


class ContentError(_IssueError):
    """Raised when a logical plotting content operation is invalid."""


class RenderError(RuntimeError):
    """Raised when a rendering operation fails after configuration succeeds."""

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        chart_id: str | None = None,
        layer_id: str | None = None,
        target_id: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.stage = stage
        self.chart_id = chart_id
        self.layer_id = layer_id
        self.target_id = target_id
        self.cause = cause
        super().__init__(message)


class RenderRequiredError(RuntimeError):
    """Raised when a caller reads results that need a successful render."""


class ClosedError(RuntimeError):
    """Raised when an operation targets a closed plotting container."""


__all__ = [
    "ClosedError",
    "ConfigError",
    "ContentError",
    "Issue",
    "RenderError",
    "RenderRequiredError",
]
