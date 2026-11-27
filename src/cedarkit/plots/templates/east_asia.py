"""Value-only EastAsia presentation presets for the new plotting API."""

from __future__ import annotations

from typing import Any

import cartopy.crs as ccrs

from cedarkit.plots.config import (
    AxisSpec,
    BasemapSpec,
    DecorationSpec,
    GridlineSpec,
    LayoutSpec,
    MapFeatureSpec,
    MapInfo,
    Rect,
    SubplotSpec,
    TextPosition,
    Theme,
    TitleSpec,
)
from cedarkit.plots.errors import ConfigError
from cedarkit.plots.map import MapType

from cedarkit.plots.domains.east_asia_config import (
    EAST_ASIA_DOMAIN,
    EAST_ASIA_MAP_INFO,
    SOUTH_CHINA_SEA_DOMAIN,
    SOUTH_CHINA_SEA_MAP_INFO,
)

from . import ChartTemplate, PanelTemplate


_MAIN_POSITION = Rect(space="chart", bounds=(.025, .025, .91, .95))
_INSET_POSITION = Rect(
    space="subplot",
    subplot="main",
    bounds=(0.0, 0.0, .135, .235),
)


def _map_title(x: float, y: float, ha: str, va: str, fontsize: float) -> TitleSpec:
    return TitleSpec(
        position=TextPosition(space="subplot", subplot="main", xy=(x, y), ha=ha, va=va),
        fontsize=fontsize,
    )


def _require_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be bool", code="invalid_template", path=(name,))
    return value


def _require_map_info(value: Any, name: str) -> MapInfo | None:
    if value is not None and not isinstance(value, MapInfo):
        raise ConfigError(
            f"{name} must be MapInfo or None",
            code="invalid_template",
            path=(name,),
        )
    return value


def _require_basemap(value: Any, name: str) -> BasemapSpec | None:
    if value is not None and not isinstance(value, BasemapSpec):
        raise ConfigError(
            f"{name} must be BasemapSpec or None",
            code="invalid_template",
            path=(name,),
        )
    return value


def _main_basemap(map_info: MapInfo) -> BasemapSpec:
    return BasemapSpec(
        map_type=MapType.Portrait,
        features=(
            MapFeatureSpec(
                name="coastline",
                kwargs={"scale": "50m", "style": {"linewidth": .4}},
            ),
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
            ),
            MapFeatureSpec(name="china_coastline", style={"linewidth": .4}),
            MapFeatureSpec(name="china_borders", style={"linewidth": .55}),
            MapFeatureSpec(name="china_provinces", style={"linewidth": .3}),
            MapFeatureSpec(name="china_rivers", style={"linewidth": .28, "alpha": .75}),
            MapFeatureSpec(name="china_nine_lines", style={"linewidth": .4}),
        ),
        map_info=map_info,
    )


def _sub_basemap(map_info: MapInfo) -> BasemapSpec:
    return BasemapSpec(
        map_type=MapType.SouthChinaSea,
        features=(
            MapFeatureSpec(
                name="coastline",
                kwargs={"scale": "50m", "style": {"linewidth": .25}},
            ),
            MapFeatureSpec(name="china_coastline", style={"linewidth": .35}),
            MapFeatureSpec(name="china_borders", style={"linewidth": .4}),
            MapFeatureSpec(name="china_provinces", style={"linewidth": .2}),
            MapFeatureSpec(name="china_rivers", style={"linewidth": .2, "alpha": .75}),
            MapFeatureSpec(name="china_nine_lines", style={"linewidth": .35}),
        ),
        map_info=map_info,
    )


def _main_axis() -> AxisSpec:
    xticks = tuple(range(70, 141, 10))
    yticks = tuple(range(15, 56, 5))
    return AxisSpec(
        xticks=xticks,
        yticks=yticks,
        xformatter="longitude",
        yformatter="latitude",
        gridlines=GridlineSpec(
            xlocators=xticks,
            ylocators=yticks,
            color="#4f5964",
            linewidth=.35,
            alpha=.5,
        ),
    )


def _sub_axis() -> AxisSpec:
    return AxisSpec(
        # Keep coordinate labels on the main map only. The inset retains its
        # gridlines without duplicate labels along the shared lower-left edges.
        xticks=(),
        yticks=(),
        gridlines=GridlineSpec(
            xlocators=(110, 120),
            ylocators=(10, 20),
            linewidth=.2,
        ),
    )


def east_asia_chart(
    *,
    with_inset: bool = True,
    main_basemap: BasemapSpec | None = None,
    sub_basemap: BasemapSpec | None = None,
    main_map_info: MapInfo | None = None,
    sub_map_info: MapInfo | None = None,
) -> ChartTemplate:
    """Return a reusable EastAsia Chart presentation preset."""

    with_inset = _require_bool(with_inset, "with_inset")
    main_basemap = _require_basemap(main_basemap, "main_basemap")
    sub_basemap = _require_basemap(sub_basemap, "sub_basemap")
    main_map_info = _require_map_info(main_map_info, "main_map_info")
    sub_map_info = _require_map_info(sub_map_info, "sub_map_info")
    if main_map_info is None:
        main_map_info = EAST_ASIA_MAP_INFO
    if sub_map_info is None:
        sub_map_info = SOUTH_CHINA_SEA_MAP_INFO
    if main_basemap is None:
        main_basemap = _main_basemap(main_map_info)
    if with_inset and sub_basemap is None:
        sub_basemap = _sub_basemap(sub_map_info)

    subplots: dict[str, SubplotSpec] = {
        "main": SubplotSpec(
            kind="map",
            domain=EAST_ASIA_DOMAIN,
            map_crs=ccrs.PlateCarree(),
            position=_MAIN_POSITION,
            aspect=1.25,
            axis=_main_axis(),
            basemap=main_basemap,
        ),
    }
    if with_inset:
        subplots["south_china_sea"] = SubplotSpec(
            kind="map",
            domain=SOUTH_CHINA_SEA_DOMAIN,
            map_crs=ccrs.PlateCarree(),
            position=_INSET_POSITION,
            aspect="equal",
            anchor="SW",
            axis=_sub_axis(),
            basemap=sub_basemap,
        )
    return ChartTemplate(
        subplots=subplots,
        decorations=DecorationSpec(
            titles={
                "heading": _map_title(0, 1.018, "left", "bottom", 13),
                "model": _map_title(1, 1.018, "right", "bottom", 11),
                "init": _map_title(0, -.065, "left", "top", 9),
                "lead": _map_title(.5, -.065, "center", "top", 9),
                "valid": _map_title(1, -.065, "right", "top", 9),
            },
        ),
    )


def east_asia(
    *,
    with_inset: bool = True,
    main_basemap: BasemapSpec | None = None,
    sub_basemap: BasemapSpec | None = None,
    main_map_info: MapInfo | None = None,
    sub_map_info: MapInfo | None = None,
) -> PanelTemplate:
    """Return a single-Chart Panel preset using :func:`east_asia_chart`."""

    return PanelTemplate(
        layout=LayoutSpec(rows=1, columns=1, figsize=(8, 6.1), dpi=160,
                          margins=(.055, .115, .125, .09), expected_charts=1),
        theme=Theme(title_fontsize=14, tick_fontsize=9),
        chart_defaults=east_asia_chart(
            with_inset=with_inset,
            main_basemap=main_basemap,
            sub_basemap=sub_basemap,
            main_map_info=main_map_info,
            sub_map_info=sub_map_info,
        ),
        decorations=DecorationSpec(),
    )


__all__ = ["east_asia", "east_asia_chart"]
