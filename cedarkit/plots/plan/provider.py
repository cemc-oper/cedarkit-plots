"""Provider contracts for executing and inspecting compiled plan requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence, runtime_checkable

from .nodes import RequestKey


@dataclass(frozen=True)
class BoundFieldRequest:
    """A source-neutral request already bound to the plan time context."""

    node_id: str
    key: RequestKey
    origin: str


@runtime_checkable
class PlanDataProvider(Protocol):
    def fetch(self, request: BoundFieldRequest) -> Any: ...


@runtime_checkable
class BatchPlanDataProvider(PlanDataProvider, Protocol):
    def fetch_many(self, requests: Sequence[BoundFieldRequest]) -> Sequence[Any]: ...


@runtime_checkable
class AvailabilityProvider(Protocol):
    def check_many(self, requests: Sequence[BoundFieldRequest]) -> Sequence[Any]: ...
