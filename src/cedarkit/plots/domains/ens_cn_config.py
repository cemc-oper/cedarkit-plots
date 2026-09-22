"""Shared value-level configuration for the EnsCN presentation preset."""

from __future__ import annotations

from cartopy import crs as ccrs

from cedarkit.plots.types import AreaRange

from .domain import Domain


ENS_CN_AREA = AreaRange(
    start_longitude=73,
    end_longitude=135,
    start_latitude=16,
    end_latitude=56,
)

ENS_CN_DOMAIN = Domain(
    extent=ENS_CN_AREA.to_tuple(),
    extent_crs=ccrs.PlateCarree(),
    map_crs=ccrs.PlateCarree(),
)


__all__ = ["ENS_CN_AREA", "ENS_CN_DOMAIN"]
