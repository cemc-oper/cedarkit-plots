"""Execution result and compact node trace."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class NodeTrace:
    node_id: str
    kind: str
    status: str


@dataclass(frozen=True)
class PlanResult:
    values: Mapping[str, Any]
    outputs: Mapping[str, Any]
    layers: tuple[Mapping[str, Any], ...]
    trace: tuple[NodeTrace, ...]

    @classmethod
    def create(cls, values: Mapping[str, Any], outputs: Mapping[str, Any], layers: tuple[Mapping[str, Any], ...], trace: tuple[NodeTrace, ...]) -> "PlanResult":
        return cls(MappingProxyType(dict(values)), MappingProxyType(dict(outputs)), layers, trace)
