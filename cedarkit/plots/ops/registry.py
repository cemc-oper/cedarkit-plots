"""Strict descriptor registry with deterministic manifests."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from .descriptor import OpDescriptor


class DuplicateRegistrationError(ValueError):
    pass


@dataclass(frozen=True)
class RegistryProvenance:
    source: str = "builtin"
    distribution: str | None = None
    version: str | None = None
    entry_point: str | None = None

    def public_dict(self) -> dict[str, str | None]:
        return {"source": self.source, "distribution": self.distribution,
                "version": self.version, "entry_point": self.entry_point}


class OpRegistry:
    def __init__(self, descriptors: tuple[OpDescriptor, ...] | list[OpDescriptor] = ()):
        self._descriptors: dict[str, OpDescriptor] = {}
        self._provenance: dict[str, RegistryProvenance] = {}
        for descriptor in descriptors:
            self.register_descriptor(descriptor)

    def register_descriptor(self, descriptor: OpDescriptor, *, provenance: RegistryProvenance | None = None,
                            override: bool = False) -> None:
        if descriptor.name in self._descriptors and not override:
            old = self._provenance[descriptor.name].public_dict()
            new = (provenance or RegistryProvenance()).public_dict()
            raise DuplicateRegistrationError(f"duplicate op {descriptor.name!r}: {old} conflicts with {new}")
        self._descriptors[descriptor.name] = descriptor
        self._provenance[descriptor.name] = provenance or RegistryProvenance()

    def register(self, name: str, func: Callable[..., Any], *, kind: str = "transform",
                 input_count: int = 1, output_count: int = 1) -> None:
        """Compatibility facade; new callers should construct :class:`OpDescriptor`."""
        self.register_descriptor(OpDescriptor(name, kind, input_count, output_count, func))

    def get(self, name: str) -> OpDescriptor:
        try:
            return self._descriptors[name]
        except KeyError as exc:
            raise KeyError(f"unknown op {name!r}; registered: {sorted(self._descriptors)}") from exc

    def has(self, name: str) -> bool:
        return name in self._descriptors

    def kind(self, name: str) -> str:
        return self.get(name).kind

    @property
    def op_names(self) -> list[str]:
        return sorted(self._descriptors)

    def provenance(self, name: str) -> RegistryProvenance:
        self.get(name)
        return self._provenance[name]

    def manifest(self) -> dict[str, Any]:
        entries = [{"name": item.name, "kind": item.kind, "input_count": item.input_count,
                    "output_count": item.output_count, "pure": item.pure, "reusable": item.reusable,
                    "contract_version": item.contract_version,
                    "provenance": self._provenance[item.name].public_dict()}
                   for item in sorted(self._descriptors.values(), key=lambda value: value.name)]
        encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
        return {"identity": hashlib.sha256(encoded).hexdigest(), "descriptors": entries}

    @contextmanager
    def scoped_override(self, descriptor: OpDescriptor) -> Iterator[None]:
        """Test-only explicit replacement, restored even when the test fails."""
        old = self._descriptors.get(descriptor.name)
        old_source = self._provenance.get(descriptor.name)
        self.register_descriptor(descriptor, provenance=RegistryProvenance("test"), override=True)
        try:
            yield
        finally:
            if old is None:
                del self._descriptors[descriptor.name]
                del self._provenance[descriptor.name]
            else:
                self._descriptors[descriptor.name] = old
                self._provenance[descriptor.name] = old_source  # type: ignore[assignment]

    @classmethod
    def builtins(cls) -> "OpRegistry":
        from .builtin import BUILTIN_DESCRIPTORS
        return cls(BUILTIN_DESCRIPTORS)
