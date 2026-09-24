"""D11 configuration presets for remaining map and XY entries."""

from __future__ import annotations

from datetime import datetime

import matplotlib

matplotlib.use("Agg")

import cartopy.crs as ccrs
import numpy as np
import xarray as xr

from cedarkit.plots import Panel
from cedarkit.plots.config import BasemapSpec, TimeStepFormatter, UNSET
from cedarkit.plots.domains import (
    CN_AREA_DOMAIN,
    EUROPE_ASIA_DOMAIN,
    GLOBAL_DOMAIN,
    NORTH_POLAR_DOMAIN,
)
from cedarkit.plots.map import MapLoader, MapType
from cedarkit.plots.style import ContourStyle
from cedarkit.plots.templates import (
    cn_area,
    cn_area_chart,
    europe_asia,
    europe_asia_chart,
    global_area,
    global_area_chart,
    global_chart,
    global_map,
    north_polar,
    north_polar_chart,
    time_profile,
    time_profile_chart,
    xy,
    xy_chart,
)


class EmptyLoader(MapLoader):
    def get_feature(self, name: str, **kwargs):
        return []


def empty_basemap(map_type: MapType = MapType.Portrait) -> BasemapSpec:
    return BasemapSpec(loader=EmptyLoader, map_type=map_type, features=())


def field() -> xr.DataArray:
    return xr.DataArray(
        np.arange(20, dtype=float).reshape(4, 5),
        dims=("level", "step"),
        coords={"level": np.array([1000, 850, 700, 500]), "step": np.array([0, 6, 12, 18, 24])},
    )


def test_remaining_map_factories_preserve_domain_projection_and_features():
    cn = cn_area_chart()
    assert cn.subplots["main"].domain == CN_AREA_DOMAIN
    assert cn.subplots["main"].aspect == 1.25
    assert cn.subplots["main"].axis.xticks == tuple(float(value) for value in range(70, 141, 4))
    assert tuple(item.name for item in cn.subplots["main"].basemap.features) == (
        "coastline",
        "lakes",
        "china_coastline",
        "china_borders",
        "china_provinces",
        "china_rivers",
        "china_nine_lines",
    )

    europe = europe_asia_chart()
    assert europe.subplots["main"].domain == EUROPE_ASIA_DOMAIN
    assert isinstance(europe.subplots["main"].map_crs, ccrs.LambertConformal)
    assert europe.subplots["main"].axis.xticks is None
    assert europe.subplots["main"].axis.gridlines.xlocators == tuple(float(value) for value in range(20, 170, 10))

    global_default = global_chart()
    assert global_default.subplots["main"].domain == GLOBAL_DOMAIN
    assert global_default.subplots["main"].domain.boundary == "global"
    assert global_default.subplots["main"].basemap.map_type is MapType.Portrait
    assert tuple(item.name for item in global_default.subplots["main"].basemap.features) == (
        "coastline",
        "land",
    )

    global_dense = global_area_chart()
    assert global_dense.subplots["main"].basemap.map_type is MapType.Global
    assert "global_borders" in tuple(
        item.name for item in global_dense.subplots["main"].basemap.features
    )

    north = north_polar_chart()
    assert north.subplots["main"].domain == NORTH_POLAR_DOMAIN
    assert north.subplots["main"].domain.boundary == "circle"
    assert isinstance(north.subplots["main"].map_crs, ccrs.NorthPolarStereo)
    assert len(north.subplots["main"].annotations) == 12


def test_panel_presets_only_configure_caller_owned_chart():
    for template in (
        cn_area(main_basemap=empty_basemap()),
        europe_asia(main_basemap=empty_basemap()),
        global_map(basemap=empty_basemap()),
        global_area(basemap=empty_basemap(MapType.Global)),
        north_polar(basemap=empty_basemap()),
        xy(),
        time_profile([0, 12, 24], [1000, 850], datetime(2026, 9, 22)),
    ):
        panel = Panel(template=template)
        assert panel.charts == {}
        chart = panel.add_chart(id="caller")
        assert panel.charts["caller"] is chart
        panel.close()


def test_map_presets_render_with_existing_loader_protocol():
    presets = (
        (cn_area(with_inset=True, main_basemap=empty_basemap(), sub_basemap=empty_basemap(MapType.SouthChinaSea)), 2),
        (europe_asia(with_inset=True, main_basemap=empty_basemap(), sub_basemap=empty_basemap(MapType.SouthChinaSea)), 2),
        (global_map(basemap=empty_basemap()), 1),
        (global_area(basemap=empty_basemap(MapType.Global)), 1),
        (north_polar(basemap=empty_basemap()), 1),
    )
    for template, axes_count in presets:
        panel = Panel(template=template)
        chart = panel.add_chart(id="map")
        panel.render()
        assert len(panel.fig.axes) == axes_count
        assert chart.main.ax.figure is panel.fig
        panel.close()


def test_xy_and_time_profile_are_normal_subplots_with_declarative_formatter():
    assert xy_chart().subplots["main"].kind == "xy"
    assert xy_chart().subplots["main"].domain is UNSET
    time_chart = time_profile_chart([0, 12, 24], [1000, 850], datetime(2026, 9, 22))
    formatter = time_chart.subplots["main"].axis.xformatter
    assert isinstance(formatter, TimeStepFormatter)
    assert formatter.last_step == 24

    panel = Panel(template=time_profile([0, 12, 24], [1000, 850], datetime(2026, 9, 22)))
    chart = panel.add_chart(id="profile")
    chart.contour(
        field(),
        id="line",
        style=ContourStyle(levels=(0, 5, 10, 15, 20), colors=("black",)),
    )
    panel.render()
    labels = [label.get_text() for label in chart.main.ax.get_xticklabels()]
    assert labels == ["00Z\n22SEP", "12Z", "00Z\n23SEP\n2026"]
    panel.close()


def test_global_chart_accepts_direct_custom_basemap():
    custom = empty_basemap()
    preset = global_chart(main_basemap=custom, map_info=None)
    assert preset.subplots["main"].basemap == custom
