"""Strict, provenance-aware domain descriptor registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..ops.registry import DuplicateRegistrationError, RegistryProvenance


@dataclass(frozen=True)
class DomainDescriptor:
    name: str
    factory: Callable[[Any], Any]

    def __post_init__(self) -> None:
        if not self.name or not callable(self.factory):
            raise ValueError("domain descriptor needs a name and callable factory")


class DomainRegistry:
    def __init__(self) -> None:
        self._domains: dict[str, DomainDescriptor] = {}
        self._provenance: dict[str, RegistryProvenance] = {}

    def register_descriptor(self, descriptor: DomainDescriptor, *, provenance: RegistryProvenance | None = None) -> None:
        if descriptor.name in self._domains:
            raise DuplicateRegistrationError(f"duplicate domain {descriptor.name!r}: "
                                             f"{self._provenance[descriptor.name].public_dict()} conflicts with "
                                             f"{(provenance or RegistryProvenance()).public_dict()}")
        self._domains[descriptor.name] = descriptor
        self._provenance[descriptor.name] = provenance or RegistryProvenance()

    def get(self, name: str) -> DomainDescriptor:
        try:
            return self._domains[name]
        except KeyError as exc:
            raise KeyError(f"unknown domain {name!r}; registered: {sorted(self._domains)}") from exc
