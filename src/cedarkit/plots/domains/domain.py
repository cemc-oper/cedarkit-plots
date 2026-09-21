"""Value-level geographic domain used by the new configuration contract."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ..config import UNSET, _check_finite, _crs, _fail, _freeze, _is_declared


@dataclass(frozen=True, kw_only=True, slots=True)
class Domain:
    """A declared data extent and its coordinate reference system.

    ``map_crs`` and ``boundary`` retain ``UNSET`` until configuration
    resolution, which keeps an omitted field distinct from an explicit
    override while a Panel is being built incrementally.
    """

    extent: tuple[float, float, float, float]
    extent_crs: Any
    map_crs: Any = field(default=UNSET)
    boundary: str = field(default=UNSET)

    def __post_init__(self) -> None:
        if isinstance(self.extent, (str, bytes)) or len(self.extent) != 4:
            _fail("Domain.extent must be (xmin, xmax, ymin, ymax)", path=("extent",))
        extent = tuple(_check_finite(value, f"extent[{index}]") for index, value in enumerate(self.extent))
        if extent[0] >= extent[1] or extent[2] >= extent[3]:
            _fail("Domain.extent endpoints must be strictly ascending", path=("extent",))
        object.__setattr__(self, "extent", extent)
        _crs(self.extent_crs, "extent_crs")
        if _is_declared(self.map_crs):
            _crs(self.map_crs, "map_crs")
        if _is_declared(self.boundary) and self.boundary not in {"extent", "circle", "global"}:
            _fail("Domain.boundary must be extent, circle or global", path=("boundary",))
        object.__setattr__(self, "extent_crs", _freeze(self.extent_crs))
        if _is_declared(self.map_crs):
            object.__setattr__(self, "map_crs", _freeze(self.map_crs))


def resolve_domain(value: Domain) -> Domain:
    """Resolve optional domain fields without importing map resources."""

    if not isinstance(value, Domain):
        _fail("domain must be Domain", path=("domain",))
    return Domain(
        extent=value.extent,
        extent_crs=value.extent_crs,
        map_crs=None if not _is_declared(value.map_crs) else value.map_crs,
        boundary="extent" if not _is_declared(value.boundary) else value.boundary,
    )


__all__ = ["Domain", "resolve_domain"]
