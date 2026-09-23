"""Execution-local values and traces."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ..plan.model import PlanIssue
from ..recipe.schema import Content, Display


@dataclass(frozen=True)
class NodeTrace:
    node_id: str
    kind: str
    status: str
    origin: str


class PlanExecutionError(RuntimeError):
    def __init__(self, node_id: str, recipe_identity: str, origin: str, message: str,
                 *, trace: tuple[NodeTrace, ...] = (), cause: Exception | None = None):
        self.node_id, self.recipe_identity, self.origin = node_id, recipe_identity, origin
        self.trace, self.cause = trace, cause
        super().__init__(f"product={recipe_identity} node={node_id} at {origin}: {message}")


@dataclass(frozen=True)
class WorkflowResult:
    recipe_identity: str
    values: Mapping[str, Any]
    outputs: Mapping[str, Any]
    content: Content
    display: Display
    trace: tuple[NodeTrace, ...]
    issues: tuple[PlanIssue, ...]

    @classmethod
    def create(cls, recipe_identity: str, values: Mapping[str, Any], outputs: Mapping[str, Any],
               content: Content, display: Display, trace: tuple[NodeTrace, ...],
               issues: tuple[PlanIssue, ...]) -> "WorkflowResult":
        return cls(recipe_identity, MappingProxyType(dict(values)), MappingProxyType(dict(outputs)),
                   content.model_copy(deep=True), display.model_copy(deep=True), trace, issues)
