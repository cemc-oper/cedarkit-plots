"""Strict, provenance-aware registry of new Panel presentation presets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..registry import DuplicateRegistrationError, RegistryProvenance


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

    def has(self, name: str) -> bool:
        return name in self._domains

    def provenance(self, name: str) -> RegistryProvenance:
        self.get(name)
        return self._provenance[name]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._domains))

    def create(self, name: str, metadata: Any = None) -> Any:
        from ..templates import PanelTemplate

        value = self.get(name).factory(metadata)
        if not isinstance(value, PanelTemplate):
            raise TypeError(f"domain {name!r} must create a PanelTemplate, got {type(value).__name__}")
        return value

    @classmethod
    def builtins(cls) -> "DomainRegistry":
        """Return the built-in value-based presentation presets."""
        from .. import templates

        registry = cls()
        for name in ("xy", "east_asia", "cn_area", "europe_asia", "global_area",
                     "global_map", "north_polar"):
            factory = getattr(templates, name)
            registry.register_descriptor(DomainDescriptor(name, lambda _metadata, f=factory: f()))
        return registry
