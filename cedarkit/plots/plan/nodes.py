"""Immutable, diagnostic-only nodes emitted by the recipe compiler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from reki import FieldQuery


@dataclass(frozen=True)
class TimeBinding:
    start_time: str | None
    forecast_time: str | None
    member: Any = None


@dataclass(frozen=True)
class RequestKey:
    """The complete identity of a provider request within one plan."""
    provider_slot: str
    query: FieldQuery
    time_binding: TimeBinding
    cardinality: Literal["one", "first", "all"] = "one"


@dataclass(frozen=True)
class PlanNode:
    id: str
    kind: Literal["read", "compute", "transform", "convert_units", "output"]
    dependencies: tuple[str, ...]
    origin: str
    bindings: tuple[str, ...]
    args: tuple[Any, ...] = ()
    kwargs: tuple[tuple[str, Any], ...] = ()
    descriptor: str | None = None
    output_count: int = 1
    pure: bool = True
    reusable: bool = True
    request: RequestKey | None = None

