"""Metadata-only availability checks over concrete plan requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .provider import BoundFieldRequest


@dataclass(frozen=True)
class RequestAvailability:
    node_id: str
    status: str
    consumers: tuple[str, ...]
    origin: str
    detail: str | None = None


@dataclass(frozen=True)
class AvailabilityReport:
    requests: tuple[RequestAvailability, ...]

    @property
    def executable(self) -> bool:
        return all(item.status == "available" for item in self.requests)

    @property
    def skippable(self) -> bool:
        return not self.executable and all(item.status in {"missing", "unknown"} for item in self.requests)

    def to_dict(self) -> dict[str, Any]:
        return {"executable": self.executable, "skippable": self.skippable, "requests": [item.__dict__ for item in self.requests]}


def check_available(plan: Any, provider: Any | None) -> AvailabilityReport:
    nodes = [node for node in plan.nodes if node.kind == "read" and node.request]
    requests = [BoundFieldRequest(node.id, node.request, node.origin) for node in nodes]
    if provider is None or not hasattr(provider, "check_many"):
        return AvailabilityReport(tuple(RequestAvailability(node.id, "unknown", plan.consumers(node.id), node.origin, "provider has no metadata availability capability") for node in nodes))
    try:
        statuses = list(provider.check_many(tuple(requests)))
        if len(statuses) != len(nodes):
            raise ValueError("provider returned wrong availability result length")
    except Exception as exc:
        return AvailabilityReport(tuple(RequestAvailability(node.id, "provider_error", plan.consumers(node.id), node.origin, str(exc)) for node in nodes))
    result = []
    for node, status in zip(nodes, statuses):
        if isinstance(status, str):
            state, detail = status, None
        else:
            state, detail = getattr(status, "status", "unknown"), getattr(status, "detail", None)
        if state not in {"available", "missing", "multiple", "invalid", "unknown", "provider_error"}:
            state = "unknown"
        result.append(RequestAvailability(node.id, state, plan.consumers(node.id), node.origin, detail))
    return AvailabilityReport(tuple(result))
