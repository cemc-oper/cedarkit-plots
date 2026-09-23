"""Immutable descriptions of planned work; no data values or drawing objects."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from reki import FieldQuery

from ..recipe.schema import Content, Display


class RecipeCompileError(ValueError):
    def __init__(self, message: str, *, origin: str, code: str, node_id: str | None = None,
                 binding: str | None = None):
        self.origin, self.code, self.node_id, self.binding = origin, code, node_id, binding
        context = f" node={node_id}" if node_id else ""
        context += f" binding={binding}" if binding else ""
        super().__init__(f"{origin}{context}: {message}")


@dataclass(frozen=True)
class PlanIssue:
    code: str
    message: str
    origin: str
    node_id: str | None = None
    binding: str | None = None


@dataclass(frozen=True)
class FieldRequest:
    provider_slot: str
    parameter_id: str
    query: FieldQuery
    start_time: str | None
    forecast_time: str | None
    cardinality: str


@dataclass(frozen=True)
class BoundFieldRequest:
    node_id: str
    key: FieldRequest
    origin: str


@dataclass(frozen=True)
class PlanNode:
    id: str
    kind: str
    dependencies: tuple[str, ...]
    origin: str
    bindings: tuple[str, ...]
    descriptor: str | None = None
    args: tuple[Any, ...] = ()
    kwargs: tuple[tuple[str, Any], ...] = ()
    request: FieldRequest | None = None
    output_count: int = 1
    pure: bool = True
    reusable: bool = True


@dataclass(frozen=True)
class RequestAvailability:
    node_id: str
    status: str
    consumers: tuple[str, ...]
    origin: str
    detail: str | None = None
    recipe_identity: str = ""


@dataclass(frozen=True)
class AvailabilityReport:
    requests: tuple[RequestAvailability, ...]

    @property
    def executable(self) -> bool:
        return all(item.status == "available" for item in self.requests)


@dataclass(frozen=True)
class WorkflowPlan:
    recipe_identity: str
    recipe_version: str
    compiler_version: str
    descriptor_identity: str
    context: Mapping[str, Any]
    nodes: tuple[PlanNode, ...]
    outputs: Mapping[str, str]
    output_slots: Mapping[str, int]
    content: Content
    display: Display
    issues: tuple[PlanIssue, ...]
    read_batches: tuple[tuple[str, ...], ...]

    @classmethod
    def create(cls, *, recipe_identity: str, descriptor_identity: str,
               context: Mapping[str, Any], nodes: tuple[PlanNode, ...], outputs: Mapping[str, str],
               output_slots: Mapping[str, int],
               content: Content, display: Display, issues: tuple[PlanIssue, ...],
               read_batches: tuple[tuple[str, ...], ...]) -> "WorkflowPlan":
        return cls(recipe_identity, "cedarkit.plots/v3", "cedarkit.plots.workflow.compiler/v1",
                   descriptor_identity, MappingProxyType(dict(context)), nodes,
                   MappingProxyType(dict(outputs)), MappingProxyType(dict(output_slots)),
                   content, display, issues, read_batches)

    @property
    def read_count(self) -> int:
        return sum(node.kind == "read" for node in self.nodes)

    def consumers(self, node_id: str) -> tuple[str, ...]:
        descendants = {node_id}
        for node in self.nodes:
            if any(dependency in descendants for dependency in node.dependencies):
                descendants.add(node.id)
        return tuple(sorted(name for name, output in self.outputs.items() if output in descendants))

    def check_available(self, provider: Any | None = None) -> AvailabilityReport:
        """Ask only for request metadata. Providers must implement check_many."""
        reads = [node for node in self.nodes if node.kind == "read"]
        if not reads:
            return AvailabilityReport(())
        if provider is None or not hasattr(provider, "check_many"):
            return AvailabilityReport(tuple(RequestAvailability(node.id, "unknown", self.consumers(node.id),
                node.origin, "provider has no metadata availability capability", self.recipe_identity) for node in reads))
        requests = tuple(BoundFieldRequest(node.id, node.request, node.origin) for node in reads)
        try:
            statuses = tuple(provider.check_many(requests))
            if len(statuses) != len(reads):
                raise ValueError("provider returned wrong availability result length")
        except Exception as exc:
            return AvailabilityReport(tuple(RequestAvailability(node.id, "provider_error", self.consumers(node.id),
                node.origin, str(exc), self.recipe_identity) for node in reads))
        result = []
        for node, status in zip(reads, statuses):
            value, detail = (status, None) if isinstance(status, str) else (
                getattr(status, "status", "unknown"), getattr(status, "detail", None))
            if value not in {"available", "missing", "multiple", "invalid", "unknown", "provider_error"}:
                value = "unknown"
            result.append(RequestAvailability(node.id, value, self.consumers(node.id), node.origin, detail,
                                              self.recipe_identity))
        return AvailabilityReport(tuple(result))
