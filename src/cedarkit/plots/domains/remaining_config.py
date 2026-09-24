"""Shared geographic domain values for the regional presentation presets."""

from __future__ import annotations

from cartopy import crs as ccrs

from cedarkit.plots.types import AreaRange

from .domain import Domain
from .east_asia_config import EAST_ASIA_AREA


CN_AREA_DOMAIN = Domain(
    extent=EAST_ASIA_AREA.to_tuple(),
    extent_crs=ccrs.PlateCarree(),
    map_crs=ccrs.PlateCarree(),
)

EUROPE_ASIA_AREA = AreaRange(
    start_longitude=20,
    end_longitude=170,
    start_latitude=0,
    end_latitude=70,
)
EUROPE_ASIA_DOMAIN = Domain(
    extent=EUROPE_ASIA_AREA.to_tuple(),
    extent_crs=ccrs.PlateCarree(),
    map_crs=ccrs.LambertConformal(
        central_longitude=95,
        standard_parallels=(30, 60),
    ),
)

GLOBAL_AREA = AreaRange(
    start_longitude=-180,
    end_longitude=180,
    start_latitude=-90,
    end_latitude=90,
)
GLOBAL_DOMAIN = Domain(
    extent=GLOBAL_AREA.to_tuple(),
    extent_crs=ccrs.PlateCarree(),
    map_crs=ccrs.PlateCarree(central_longitude=80),
    boundary="global",
)

NORTH_POLAR_AREA = AreaRange(
    start_longitude=-180,
    end_longitude=180,
    start_latitude=0,
    end_latitude=90,
)
NORTH_POLAR_DOMAIN = Domain(
    extent=NORTH_POLAR_AREA.to_tuple(),
    extent_crs=ccrs.PlateCarree(),
    map_crs=ccrs.NorthPolarStereo(central_longitude=110),
    boundary="circle",
)


__all__ = [
    "CN_AREA_DOMAIN",
    "EUROPE_ASIA_AREA",
    "EUROPE_ASIA_DOMAIN",
    "GLOBAL_AREA",
    "GLOBAL_DOMAIN",
    "NORTH_POLAR_AREA",
    "NORTH_POLAR_DOMAIN",
]
