"""Deterministic discovery for controlled recipe, op and domain plugins."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any, Iterable

from .ops.registry import RegistryProvenance

PLUGIN_GROUPS = ("cedarkit.plots.recipes", "cedarkit.plots.ops", "cedarkit.plots.domains")


class PluginDiscoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class PluginFailure:
    group: str
    distribution: str | None
    version: str | None
    entry_point: str
    cause: str


@dataclass(frozen=True)
class PluginDiscovery:
    providers: tuple[Any, ...]
    failures: tuple[PluginFailure, ...]


def _distribution(entry_point: Any) -> tuple[str | None, str | None]:
    dist = getattr(entry_point, "dist", None)
    if dist is None:
        return None, None
    return dist.metadata.get("Name"), getattr(dist, "version", None)


def discover(group: str, *, entry_points: Iterable[Any] | None = None, strict: bool = True) -> PluginDiscovery:
    if group not in PLUGIN_GROUPS:
        raise ValueError(f"unsupported plugin group {group!r}")
    candidates = list(entry_points) if entry_points is not None else list(metadata.entry_points(group=group))
    def ordering(item: Any) -> tuple[str, str]:
        distribution, _ = _distribution(item)
        return ((distribution or "").lower(), item.name)
    providers, failures = [], []
    for entry_point in sorted(candidates, key=ordering):
        distribution, version = _distribution(entry_point)
        try:
            providers.append((entry_point.load(), RegistryProvenance("plugin", distribution, version, entry_point.name)))
        except Exception as exc:
            failure = PluginFailure(group, distribution, version, entry_point.name, f"{type(exc).__name__}: {exc}")
            if strict:
                raise PluginDiscoveryError(f"failed to load plugin {failure}") from exc
            failures.append(failure)
    return PluginDiscovery(tuple(providers), tuple(failures))
