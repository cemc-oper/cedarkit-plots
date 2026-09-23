"""Small neutral provenance values shared by plugin-backed registries."""

from __future__ import annotations

from dataclasses import dataclass


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
