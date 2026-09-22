"""Shared value-level EastAsia domain defaults.

This module contains only immutable-or-snapshot-friendly declarations.  It
does not import the legacy template execution chain or load map resources.
"""

from __future__ import annotations

from cartopy import crs as ccrs

from cedarkit.plots.painter.map_painter import MapInfo
from cedarkit.plots.types import AreaRange

from .domain import Domain


EAST_ASIA_AREA = AreaRange(
    start_longitude=70,
    end_longitude=140,
    start_latitude=15,
    end_latitude=55,
)

SOUTH_CHINA_SEA_AREA = AreaRange(
    start_longitude=105,
    end_longitude=123,
    start_latitude=2,
    end_latitude=23,
)

EAST_ASIA_DOMAIN = Domain(
    extent=EAST_ASIA_AREA.to_tuple(),
    extent_crs=ccrs.PlateCarree(),
    map_crs=ccrs.PlateCarree(),
)

SOUTH_CHINA_SEA_DOMAIN = Domain(
    extent=SOUTH_CHINA_SEA_AREA.to_tuple(),
    extent_crs=ccrs.PlateCarree(),
    map_crs=ccrs.PlateCarree(),
)

EAST_ASIA_MAP_INFO = MapInfo(
    x=0.998,
    y=0.0022,
    text="Scale 1:20000000 No:GS (2019) 1786",
)

SOUTH_CHINA_SEA_MAP_INFO = MapInfo(
    x=0.99,
    y=0.01,
    text="Scale 1:40000000",
)


__all__ = [
    "EAST_ASIA_AREA",
    "EAST_ASIA_DOMAIN",
    "EAST_ASIA_MAP_INFO",
    "SOUTH_CHINA_SEA_AREA",
    "SOUTH_CHINA_SEA_DOMAIN",
    "SOUTH_CHINA_SEA_MAP_INFO",
]
