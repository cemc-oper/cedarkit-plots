"""Assemble one workflow registry set from the existing plugin groups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..domains.registry import DomainDescriptor, DomainRegistry
from ..ops import OpDescriptor, OpRegistry
from ..plugins import PluginDiscoveryError, PluginFailure, discover
from .recipe import RecipeCatalog


@dataclass(frozen=True)
class WorkflowDiscovery:
    ops: OpRegistry
    domains: DomainRegistry
    recipes: RecipeCatalog
    failures: tuple[PluginFailure, ...]


def discover_workflow(*, entry_points: Mapping[str, Iterable[Any]] | None = None,
                      strict: bool = True) -> WorkflowDiscovery:
    """Discover workflow providers in stable order."""
    ops = OpRegistry.builtins()
    domains = DomainRegistry.builtins()
    recipes = RecipeCatalog()
    failures: list[PluginFailure] = []
    for group in ("cedarkit.plots.ops", "cedarkit.plots.domains", "cedarkit.plots.recipes"):
        found = discover(group, entry_points=None if entry_points is None else entry_points.get(group, ()),
                         strict=strict)
        failures.extend(found.failures)
        for provider, provenance in found.providers:
            try:
                value = provider() if callable(provider) else provider
            except Exception as exc:
                failure = PluginFailure(group, provenance.distribution, provenance.version,
                                        provenance.entry_point or "<unknown>", f"{type(exc).__name__}: {exc}")
                if strict:
                    raise PluginDiscoveryError(f"failed to call plugin {failure}") from exc
                failures.append(failure)
                continue
            if group == "cedarkit.plots.ops":
                for descriptor in value:
                    if not isinstance(descriptor, OpDescriptor):
                        raise TypeError(f"{provenance.public_dict()}: ops provider must yield OpDescriptor")
                    ops.register_descriptor(descriptor, provenance=provenance)
            elif group == "cedarkit.plots.domains":
                for descriptor in value:
                    if not isinstance(descriptor, DomainDescriptor):
                        raise TypeError(f"{provenance.public_dict()}: domain provider must yield DomainDescriptor")
                    domains.register_descriptor(descriptor, provenance=provenance)
            else:
                recipes.register_root(value, provenance=provenance)
    return WorkflowDiscovery(ops, domains, recipes, tuple(failures))
