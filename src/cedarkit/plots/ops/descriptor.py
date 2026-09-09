"""Operation contracts consumed by the compiler and executor."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Literal

_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True)
class OpRuntimeContext:
    """Read-only runtime metadata.  It intentionally has no loader/provider."""
    recipe_identity: str
    node_id: str
    metadata: Any


@dataclass(frozen=True)
class OpDescriptor:
    name: str
    kind: Literal["transform", "compute"]
    input_count: int
    output_count: int
    callable: Callable[..., Any]
    pure: bool = True
    reusable: bool = True
    planner: Callable[..., Any] | None = None
    contract_version: int = 1

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name):
            raise ValueError(f"invalid op name {self.name!r}")
        if self.kind not in {"transform", "compute"}:
            raise ValueError("kind must be 'transform' or 'compute'")
        if not isinstance(self.input_count, int) or self.input_count < 1:
            raise ValueError("input_count must be a positive exact integer")
        if not isinstance(self.output_count, int) or self.output_count < 1:
            raise ValueError("output_count must be a positive exact integer")
        if not callable(self.callable):
            raise TypeError("callable must be callable")
        if self.planner is not None and not callable(self.planner):
            raise TypeError("planner must be callable")
