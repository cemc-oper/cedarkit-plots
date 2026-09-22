"""Configuration-only presets for the remaining D11 map templates.

Each factory returns ordinary configuration values.  It never creates a
Chart, Axes, Figure, Layer, or map resource; callers own content creation and
the Panel renderer owns execution.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import cartopy.crs as ccrs
import numpy as np

from cedarkit.plots.config import (
    AnnotationSpec,
    AxisSpec,
    BasemapSpec,
    DecorationSpec,
    GridlineSpec,
    LayoutSpec,
    MapFeatureSpec,
    Rect,
    SubplotSpec,
    TextPosition,
    Theme,
)
from cedarkit.plots.domains.domain import Domain
from cedarkit.plots.domains.east_asia_config import (
    EAST_ASIA_MAP_INFO,
    SOUTH_CHINA_SEA_DOMAIN,
    SOUTH_CHINA_SEA_MAP_INFO,
)
from cedarkit.plots.domains.remaining_config import (
    CN_AREA_DOMAIN,
    EUROPE_ASIA_DOMAIN,
    GLOBAL_DOMAIN,
    NORTH_POLAR_DOMAIN,
)
from cedarkit.plots.errors import ConfigError
from cedarkit.plots.map import MapType
from cedarkit.plots.painter.map_painter import MapInfo
from cedarkit.plots.types import AreaRange

from . import ChartTemplate, PanelTemplate


_EAST_ASIA_POSITION = Rect(space="chart", bounds=(.125, .2, .75, .6))
_CN_AREA_POSITION = Rect(space="chart", bounds=(.1, .2, .8, .6))
_EUROPE_ASIA_POSITION = _EAST_ASIA_POSITION
_GLOBAL_POSITION = _CN_AREA_POSITION
_NORTH_POLAR_POSITION = Rect(space="chart", bounds=(.125, .1, .75, .8))
_INSET_POSITION = Rect(
    space="subplot",
    subplot="main",
    bounds=(0.0, 0.0, .1 / .75, .14 / .6),
)

_EUROPE_ASIA_MAP_INFO = MapInfo(
    x=1.035,
    y=-.035,
    text="Scale 1:20000000 No:GS (2019) 1786",
)
_GLOBAL_MAP_INFO = MapInfo(
    x=.998,
    y=.0022,
    text="Scale 1:20000000 No:GS (2019) 1786",
)
_NORTH_POLAR_MAP_INFO = MapInfo(
    x=1.065,
    y=-.045,
    text="Scale 1:20000000 No:GS (2019) 1786",
)


def _invalid(message: str, name: str) -> None:
    raise ConfigError(message, code="invalid_template", path=(name,))


def _require_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        _invalid(f"{name} must be bool", name)
    return value


def _require_domain(value: Any, name: str = "domain") -> Domain:
    if not isinstance(value, Domain):
        _invalid(f"{name} must be Domain", name)
    return value


def _require_basemap(value: Any, name: str = "basemap") -> BasemapSpec | None:
    if value is not None and not isinstance(value, BasemapSpec):
        _invalid(f"{name} must be BasemapSpec or None", name)
    return value


def _require_map_info(value: Any, name: str) -> MapInfo | None:
    if value is not None and not isinstance(value, MapInfo):
        _invalid(f"{name} must be MapInfo or None", name)
    return value


def _domain_from_area(
    default: Domain,
    *,
    domain: Domain | None,
    area: AreaRange | Sequence[float] | None,
) -> Domain:
    if domain is not None and area is not None:
        raise ConfigError(
            "domain and area are mutually exclusive",
            code="invalid_template",
            path=("domain",),
        )
    if domain is not None:
        return _require_domain(domain)
    if area is None:
        return default
    if isinstance(area, AreaRange):
        extent = area.to_tuple()
    elif isinstance(area, Sequence) and not isinstance(area, (str, bytes)) and len(area) == 4:
        extent = tuple(area)
    else:
        _invalid("area must be AreaRange or a four-item sequence", "area")
    return Domain(
        extent=extent,
        extent_crs=default.extent_crs,
        map_crs=default.map_crs,
        boundary=default.boundary,
    )


def _with_sub_area(with_inset: bool, with_sub_area: bool | None) -> bool:
    with_inset = _require_bool(with_inset, "with_inset")
    if with_sub_area is None:
        return with_inset
    return _require_bool(with_sub_area, "with_sub_area")


def _ticks(start: float, end: float, step: float, *, include_end: bool) -> tuple[float, ...]:
    values = np.arange(start, end + (step / 10 if include_end else 0), step)
    return tuple(float(value) for value in values)


def _global_ticks(interval: float) -> tuple[float, ...]:
    central_longitude = 80
    east = np.arange(central_longitude, central_longitude + 180, interval)
    west = np.arange(
        central_longitude - interval,
        central_longitude - 180,
        -interval,
    )[::-1]
    ticks = np.concatenate([west, east])
    ticks = np.where(ticks > 180, ticks - 360, ticks)
    ticks = np.where(ticks < -180, ticks + 360, ticks)
    return tuple(float(value) for value in np.unique(ticks))


def _china_basemap(map_info: MapInfo, *, with_lakes: bool = True) -> BasemapSpec:
    features = [
        MapFeatureSpec(
            name="coastline",
            kwargs={"scale": "50m", "style": {"linewidth": .5}},
        ),
    ]
    if with_lakes:
        features.append(
            MapFeatureSpec(
                name="lakes",
                kwargs={
                    "scale": "50m",
                    "style": {
                        "linewidth": .25,
                        "facecolor": "none",
                        "edgecolor": "black",
                        "alpha": .5,
                    },
                },
            )
        )
    features.extend(
        MapFeatureSpec(name=name)
        for name in (
            "china_coastline",
            "china_borders",
            "china_provinces",
            "china_rivers",
            "china_nine_lines",
        )
    )
    return BasemapSpec(
        map_type=MapType.Portrait,
        features=tuple(features),
        map_info=map_info,
    )


def _south_basemap(map_info: MapInfo) -> BasemapSpec:
    return BasemapSpec(
        map_type=MapType.SouthChinaSea,
        features=(
            MapFeatureSpec(
                name="coastline",
                kwargs={"scale": "50m", "style": {"linewidth": .25}},
            ),
            MapFeatureSpec(name="china_coastline"),
            MapFeatureSpec(name="china_borders"),
            MapFeatureSpec(name="china_provinces"),
            MapFeatureSpec(name="china_rivers"),
            MapFeatureSpec(name="china_nine_lines"),
        ),
        map_info=map_info,
    )


def _global_basemap(
    map_info: MapInfo,
    *,
    with_global_borders: bool,
) -> BasemapSpec:
    features = [
        MapFeatureSpec(
            name="coastline",
            kwargs={"scale": "50m", "style": {"linewidth": .5}},
        ),
        MapFeatureSpec(
            name="land",
            kwargs={"scale": "50m", "style": {"zorder": -1}},
        ),
    ]
    if with_global_borders:
        features.append(MapFeatureSpec(name="global_borders"))
    return BasemapSpec(
        map_type=MapType.Global if with_global_borders else MapType.Portrait,
        features=tuple(features),
        map_info=map_info,
    )


def _main_axis(domain: Domain, *, xstep: float, ystep: float) -> AxisSpec:
    xlocators = _ticks(domain.extent[0], domain.extent[1], xstep, include_end=True)
    ylocators = _ticks(domain.extent[2], domain.extent[3], ystep, include_end=True)
    return AxisSpec(
        xticks=xlocators,
        yticks=ylocators,
        gridlines=GridlineSpec(xlocators=xlocators, ylocators=ylocators),
    )


def _inset_axis() -> AxisSpec:
    ticks_x = (110, 120)
    ticks_y = (10, 20)
    return AxisSpec(
        xticks=ticks_x,
        yticks=ticks_y,
        gridlines=GridlineSpec(
            xlocators=ticks_x,
            ylocators=ticks_y,
            linewidth=.2,
        ),
    )


def _panel_template(chart: ChartTemplate) -> PanelTemplate:
    return PanelTemplate(
        layout=LayoutSpec(rows=1, columns=1, expected_charts=1),
        theme=Theme(),
        chart_defaults=chart,
        decorations=DecorationSpec(),
    )


def cn_area_chart(
    *,
    domain: Domain | None = None,
    area: AreaRange | Sequence[float] | None = None,
    with_inset: bool = False,
    with_sub_area: bool | None = None,
    main_basemap: BasemapSpec | None = None,
    sub_basemap: BasemapSpec | None = None,
    main_map_info: MapInfo | None = None,
    sub_map_info: MapInfo | None = None,
) -> ChartTemplate:
    """Return the configuration equivalent of ``CnAreaMapTemplate``."""

    domain = _domain_from_area(CN_AREA_DOMAIN, domain=domain, area=area)
    with_inset = _with_sub_area(with_inset, with_sub_area)
    main_basemap = _require_basemap(main_basemap, "main_basemap")
    sub_basemap = _require_basemap(sub_basemap, "sub_basemap")
    main_map_info = _require_map_info(main_map_info, "main_map_info") or EAST_ASIA_MAP_INFO
    sub_map_info = _require_map_info(sub_map_info, "sub_map_info") or SOUTH_CHINA_SEA_MAP_INFO
    if main_basemap is None:
        main_basemap = _china_basemap(main_map_info)
    if with_inset and sub_basemap is None:
        sub_basemap = _south_basemap(sub_map_info)
    subplots: dict[str, SubplotSpec] = {
        "main": SubplotSpec(
            kind="map",
            domain=domain,
            map_crs=domain.map_crs,
            position=_CN_AREA_POSITION,
            aspect=1.25,
            axis=_main_axis(domain, xstep=4, ystep=2),
            basemap=main_basemap,
        ),
    }
    if with_inset:
        subplots["south_china_sea"] = SubplotSpec(
            kind="map",
            domain=SOUTH_CHINA_SEA_DOMAIN,
            map_crs=ccrs.PlateCarree(),
            position=_INSET_POSITION,
            aspect=.1 / .14,
            axis=_inset_axis(),
            basemap=sub_basemap,
        )
    return ChartTemplate(subplots=subplots)


def cn_area(
    *,
    domain: Domain | None = None,
    area: AreaRange | Sequence[float] | None = None,
    with_inset: bool = False,
    with_sub_area: bool | None = None,
    main_basemap: BasemapSpec | None = None,
    sub_basemap: BasemapSpec | None = None,
    main_map_info: MapInfo | None = None,
    sub_map_info: MapInfo | None = None,
) -> PanelTemplate:
    return _panel_template(
        cn_area_chart(
            domain=domain,
            area=area,
            with_inset=with_inset,
            with_sub_area=with_sub_area,
            main_basemap=main_basemap,
            sub_basemap=sub_basemap,
            main_map_info=main_map_info,
            sub_map_info=sub_map_info,
        )
    )


def europe_asia_chart(
    *,
    domain: Domain | None = None,
    area: AreaRange | Sequence[float] | None = None,
    with_inset: bool = False,
    with_sub_area: bool | None = None,
    main_basemap: BasemapSpec | None = None,
    sub_basemap: BasemapSpec | None = None,
    main_map_info: MapInfo | None = None,
    sub_map_info: MapInfo | None = None,
) -> ChartTemplate:
    """Return the LambertConformal Europe–Asia map configuration."""

    domain = _domain_from_area(EUROPE_ASIA_DOMAIN, domain=domain, area=area)
    with_inset = _with_sub_area(with_inset, with_sub_area)
    main_basemap = _require_basemap(main_basemap, "main_basemap")
    sub_basemap = _require_basemap(sub_basemap, "sub_basemap")
    main_map_info = _require_map_info(main_map_info, "main_map_info") or _EUROPE_ASIA_MAP_INFO
    sub_map_info = _require_map_info(sub_map_info, "sub_map_info") or SOUTH_CHINA_SEA_MAP_INFO
    if main_basemap is None:
        main_basemap = _china_basemap(main_map_info)
    if with_inset and sub_basemap is None:
        sub_basemap = _south_basemap(sub_map_info)
    xlocators = _ticks(domain.extent[0], domain.extent[1], 10, include_end=False)
    ylocators = _ticks(domain.extent[2], domain.extent[3], 5, include_end=False)
    subplots: dict[str, SubplotSpec] = {
        "main": SubplotSpec(
            kind="map",
            domain=domain,
            map_crs=domain.map_crs,
            position=_EUROPE_ASIA_POSITION,
            aspect="auto",
            axis=AxisSpec(
                xticks=None,
                yticks=None,
                gridlines=GridlineSpec(xlocators=xlocators, ylocators=ylocators),
            ),
            basemap=main_basemap,
        ),
    }
    if with_inset:
        subplots["south_china_sea"] = SubplotSpec(
            kind="map",
            domain=SOUTH_CHINA_SEA_DOMAIN,
            map_crs=ccrs.PlateCarree(),
            position=_INSET_POSITION,
            aspect=.1 / .14,
            axis=_inset_axis(),
            basemap=sub_basemap,
        )
    return ChartTemplate(subplots=subplots)


def europe_asia(
    *,
    domain: Domain | None = None,
    area: AreaRange | Sequence[float] | None = None,
    with_inset: bool = False,
    with_sub_area: bool | None = None,
    main_basemap: BasemapSpec | None = None,
    sub_basemap: BasemapSpec | None = None,
    main_map_info: MapInfo | None = None,
    sub_map_info: MapInfo | None = None,
) -> PanelTemplate:
    return _panel_template(
        europe_asia_chart(
            domain=domain,
            area=area,
            with_inset=with_inset,
            with_sub_area=with_sub_area,
            main_basemap=main_basemap,
            sub_basemap=sub_basemap,
            main_map_info=main_map_info,
            sub_map_info=sub_map_info,
        )
    )


def _global_chart(
    *,
    default_domain: Domain,
    interval: float,
    with_global_borders: bool,
    domain: Domain | None,
    area: AreaRange | Sequence[float] | None,
    basemap: BasemapSpec | None,
    map_info: MapInfo | None,
    main_basemap: BasemapSpec | None,
    main_map_info: MapInfo | None,
) -> ChartTemplate:
    domain = _domain_from_area(default_domain, domain=domain, area=area)
    if basemap is not None and main_basemap is not None:
        raise ConfigError(
            "basemap and main_basemap are mutually exclusive",
            code="invalid_template",
            path=("basemap",),
        )
    basemap = _require_basemap(main_basemap if main_basemap is not None else basemap)
    if map_info is not None and main_map_info is not None:
        raise ConfigError(
            "map_info and main_map_info are mutually exclusive",
            code="invalid_template",
            path=("map_info",),
        )
    map_info = _require_map_info(
        main_map_info if main_map_info is not None else map_info,
        "map_info",
    ) or _GLOBAL_MAP_INFO
    if basemap is None:
        basemap = _global_basemap(map_info, with_global_borders=with_global_borders)
    ticks_x = _global_ticks(interval)
    ticks_y = tuple(float(value) for value in np.arange(-90 + interval, 90, interval))
    return ChartTemplate(
        subplots={
            "main": SubplotSpec(
                kind="map",
                domain=domain,
                map_crs=domain.map_crs,
                position=_GLOBAL_POSITION,
                aspect="auto",
                axis=AxisSpec(
                    xticks=ticks_x,
                    yticks=ticks_y,
                    xformatter="longitude",
                    yformatter="latitude",
                    gridlines=GridlineSpec(
                        xlocators=ticks_x,
                        ylocators=ticks_y,
                    ),
                ),
                basemap=basemap,
            ),
        },
    )


def global_chart(
    *,
    domain: Domain | None = None,
    area: AreaRange | Sequence[float] | None = None,
    basemap: BasemapSpec | None = None,
    map_info: MapInfo | None = None,
    main_basemap: BasemapSpec | None = None,
    main_map_info: MapInfo | None = None,
) -> ChartTemplate:
    """Return the default global PlateCarree map configuration."""

    return _global_chart(
        default_domain=GLOBAL_DOMAIN,
        interval=30,
        with_global_borders=False,
        domain=domain,
        area=area,
        basemap=basemap,
        map_info=map_info,
        main_basemap=main_basemap,
        main_map_info=main_map_info,
    )


def global_area_chart(
    *,
    domain: Domain | None = None,
    area: AreaRange | Sequence[float] | None = None,
    basemap: BasemapSpec | None = None,
    map_info: MapInfo | None = None,
    main_basemap: BasemapSpec | None = None,
    main_map_info: MapInfo | None = None,
) -> ChartTemplate:
    """Return the denser global map configuration with world borders."""

    return _global_chart(
        default_domain=GLOBAL_DOMAIN,
        interval=10,
        with_global_borders=True,
        domain=domain,
        area=area,
        basemap=basemap,
        map_info=map_info,
        main_basemap=main_basemap,
        main_map_info=main_map_info,
    )


def global_map(**kwargs: Any) -> PanelTemplate:
    """Return a one-Chart Panel preset for :func:`global_chart`."""

    return _panel_template(global_chart(**kwargs))


def global_area(**kwargs: Any) -> PanelTemplate:
    """Return a one-Chart Panel preset for :func:`global_area_chart`."""

    return _panel_template(global_area_chart(**kwargs))


def north_polar_chart(
    *,
    domain: Domain | None = None,
    area: AreaRange | Sequence[float] | None = None,
    basemap: BasemapSpec | None = None,
    map_info: MapInfo | None = None,
    main_basemap: BasemapSpec | None = None,
    main_map_info: MapInfo | None = None,
) -> ChartTemplate:
    """Return the NorthPolarStereo map configuration."""

    domain = _domain_from_area(NORTH_POLAR_DOMAIN, domain=domain, area=area)
    if basemap is not None and main_basemap is not None:
        raise ConfigError(
            "basemap and main_basemap are mutually exclusive",
            code="invalid_template",
            path=("basemap",),
        )
    basemap = _require_basemap(main_basemap if main_basemap is not None else basemap)
    if map_info is not None and main_map_info is not None:
        raise ConfigError(
            "map_info and main_map_info are mutually exclusive",
            code="invalid_template",
            path=("map_info",),
        )
    map_info = _require_map_info(
        main_map_info if main_map_info is not None else map_info,
        "map_info",
    ) or _NORTH_POLAR_MAP_INFO
    if basemap is None:
        basemap = _china_basemap(map_info)

    labels: dict[str, AnnotationSpec] = {}
    east_labels = ["0"] + [f"{value}E" for value in range(30, 180, 30)] + ["180"]
    west_labels = [f"{value}W" for value in range(30, 180, 30)]
    labels_for_longitude = east_labels + west_labels[::-1]
    for longitude, label in zip(range(0, 360, 30), labels_for_longitude):
        y = .06 if label == "60W" else .035
        labels[f"longitude_{longitude}"] = AnnotationSpec(
            text=label,
            position=TextPosition(
                space="subplot",
                subplot="main",
                xy=(longitude / 360, y),
                ha="center",
                va="center",
            ),
            fontsize=8,
        )

    xlocators = tuple(float(value) for value in np.arange(-180, 180, 30))
    ylocators = tuple(float(value) for value in np.arange(0, 90, 15))
    return ChartTemplate(
        subplots={
            "main": SubplotSpec(
                kind="map",
                domain=domain,
                map_crs=domain.map_crs,
                position=_NORTH_POLAR_POSITION,
                aspect="auto",
                axis=AxisSpec(
                    xticks=None,
                    yticks=None,
                    gridlines=GridlineSpec(
                        xlocators=xlocators,
                        ylocators=ylocators,
                        color="k",
                    ),
                ),
                basemap=basemap,
                annotations=labels,
            ),
        },
    )


def north_polar(**kwargs: Any) -> PanelTemplate:
    """Return a one-Chart Panel preset for :func:`north_polar_chart`."""

    return _panel_template(north_polar_chart(**kwargs))


# Explicit aliases make the old ``GlobalMapTemplate`` name easy to map while
# keeping the public factories consistently named with the D09/D10 entries.
global_map_chart = global_chart


__all__ = [
    "cn_area",
    "cn_area_chart",
    "europe_asia",
    "europe_asia_chart",
    "global_area",
    "global_area_chart",
    "global_chart",
    "global_map",
    "global_map_chart",
    "north_polar",
    "north_polar_chart",
]
