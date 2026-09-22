"""D09 EastAsia value presets and direct-configuration equivalence."""

import matplotlib

matplotlib.use("Agg")

import cartopy.crs as ccrs
import numpy as np
import pytest
import xarray as xr

from cedarkit.plots import Panel
from cedarkit.plots.config import (
    AxisSpec,
    BasemapSpec,
    ChartSpec,
    DecorationSpec,
    GridlineSpec,
    LayoutSpec,
    MapFeatureSpec,
    Rect,
    SubplotSpec,
    Theme,
)
from cedarkit.plots.domains import (
    EAST_ASIA_DOMAIN,
    SOUTH_CHINA_SEA_DOMAIN,
)
from cedarkit.plots.errors import ConfigError
from cedarkit.plots.map import MapLoader, MapType
from cedarkit.plots.painter.map_painter import MapInfo
from cedarkit.plots.style import ContourStyle
from cedarkit.plots.templates import east_asia, east_asia_chart


class EmptyLoader(MapLoader):
    calls: list[tuple[str, dict]] = []

    def get_feature(self, name: str, **kwargs):
        self.calls.append((name, dict(kwargs)))
        return []


def field() -> xr.DataArray:
    longitude = np.linspace(100, 130, 5)
    latitude = np.linspace(20, 50, 4)
    return xr.DataArray(
        np.add.outer(latitude, longitude),
        dims=("latitude", "longitude"),
        coords={"longitude": longitude, "latitude": latitude},
        attrs={"units": "K", "standard_name": "air_temperature"},
    )


def custom_basemaps() -> tuple[BasemapSpec, BasemapSpec]:
    main = BasemapSpec(
        loader=EmptyLoader,
        map_type=MapType.Portrait,
        features=(MapFeatureSpec(name="main_feature"),),
        map_info=MapInfo(text="main", x=.98, y=.02),
    )
    sub = BasemapSpec(
        loader=EmptyLoader,
        map_type=MapType.SouthChinaSea,
        features=(MapFeatureSpec(name="sub_feature"),),
        map_info=MapInfo(text="sub", x=.97, y=.03),
    )
    return main, sub


def direct_chart_spec(main: BasemapSpec, sub: BasemapSpec) -> ChartSpec:
    main_ticks = tuple(range(70, 141, 10))
    main_latitudes = tuple(range(15, 56, 5))
    return ChartSpec(
        subplots={
            "main": SubplotSpec(
                kind="map",
                domain=EAST_ASIA_DOMAIN,
                map_crs=ccrs.PlateCarree(),
                position=Rect(space="chart", bounds=(.125, .2, .75, .6)),
                aspect=1.25,
                axis=AxisSpec(
                    xticks=main_ticks,
                    yticks=main_latitudes,
                    gridlines=GridlineSpec(
                        xlocators=main_ticks,
                        ylocators=main_latitudes,
                    ),
                ),
                basemap=main,
            ),
            "south_china_sea": SubplotSpec(
                kind="map",
                domain=SOUTH_CHINA_SEA_DOMAIN,
                map_crs=ccrs.PlateCarree(),
                position=Rect(
                    space="subplot",
                    subplot="main",
                    bounds=(0.0, 0.0, .1 / .75, .14 / .6),
                ),
                aspect=.1 / .14,
                axis=AxisSpec(
                    xticks=(110, 120),
                    yticks=(10, 20),
                    gridlines=GridlineSpec(
                        xlocators=(110, 120),
                        ylocators=(10, 20),
                        linewidth=.2,
                    ),
                ),
                basemap=sub,
            ),
        }
    )


def add_layer(panel: Panel, *, layer_id: str = "temperature"):
    chart = panel.add_chart(id="weather")
    layer = chart.contourf(
        field(),
        id=layer_id,
        style=ContourStyle(levels=(120, 130, 140, 150, 160), colors="viridis"),
        subplots="all",
        data_crs=ccrs.PlateCarree(),
    )
    return chart, layer


def test_east_asia_factory_preserves_shared_regions_features_and_map_info():
    preset = east_asia_chart()
    assert tuple(preset.subplots) == ("main", "south_china_sea")
    assert preset.subplots["main"].domain == EAST_ASIA_DOMAIN
    assert preset.subplots["south_china_sea"].domain == SOUTH_CHINA_SEA_DOMAIN

    main = preset.subplots["main"].basemap
    sub = preset.subplots["south_china_sea"].basemap
    assert main.map_type is MapType.Portrait
    assert sub.map_type is MapType.SouthChinaSea
    assert tuple(item.name for item in main.features) == (
        "coastline", "lakes", "china_coastline", "china_borders",
        "china_provinces", "china_rivers", "china_nine_lines",
    )
    assert tuple(item.name for item in sub.features) == (
        "coastline", "china_coastline", "china_borders",
        "china_provinces", "china_rivers", "china_nine_lines",
    )
    assert main.map_info.text == "Scale 1:20000000 No:GS (2019) 1786"
    assert sub.map_info.text == "Scale 1:40000000"
    assert east_asia(with_inset=False).layout.expected_charts == 1
    assert tuple(east_asia(with_inset=False).chart_defaults.subplots) == ("main",)


def test_direct_and_panel_preset_entries_have_equal_effective_map_configuration():
    EmptyLoader.calls.clear()
    main, sub = custom_basemaps()
    preset_panel = Panel(
        template=east_asia(
            main_basemap=main,
            sub_basemap=sub,
        )
    )
    direct_panel = Panel(
        layout=LayoutSpec(rows=1, columns=1, expected_charts=1),
        theme=Theme(),
        chart_defaults=direct_chart_spec(main, sub),
        decorations=DecorationSpec(),
    )
    preset_chart, preset_layer = add_layer(preset_panel)
    direct_chart, direct_layer = add_layer(direct_panel)

    preset_figure = preset_panel.render()
    direct_figure = direct_panel.render()
    assert preset_panel.effective_config.layout == direct_panel.effective_config.layout
    assert preset_panel.effective_config.charts["weather"] == direct_panel.effective_config.charts["weather"]
    assert len(preset_figure.axes) == len(direct_figure.axes) == 2
    assert set(preset_layer.results) == set(direct_layer.results) == {"main", "south_china_sea"}
    assert {text.get_text() for text in preset_chart.main.ax.texts} == {"main"}
    assert {text.get_text() for text in direct_chart.main.ax.texts} == {"main"}
    assert EmptyLoader.calls == [("main_feature", {}), ("sub_feature", {})] * 2
    preset_panel.close()
    direct_panel.close()


def test_inset_switch_keeps_layer_identity_and_rejects_fixed_target():
    main, sub = custom_basemaps()
    panel = Panel(template=east_asia(main_basemap=main, sub_basemap=sub))
    chart, layer = add_layer(panel)
    panel.render()
    assert len(layer.results) == 2
    data_ref = layer.data
    fixed = chart.contour(
        field(),
        id="fixed_inset",
        style=ContourStyle(levels=(120, 130, 140), colors=("black",)),
        subplots=("south_china_sea",),
        data_crs=ccrs.PlateCarree(),
    )
    old_figure = panel.render()
    old_revision = panel.revision
    with pytest.raises(ConfigError) as caught:
        panel.apply_template(east_asia(with_inset=False, main_basemap=main, sub_basemap=sub))
    assert caught.value.code == "missing_target"
    assert panel.fig is old_figure
    assert panel.revision == old_revision
    assert layer.data is data_ref
    assert fixed.chart is chart

    fixed.remove()
    panel.apply_template(east_asia(with_inset=False, main_basemap=main, sub_basemap=sub))
    panel.render()
    assert len(layer.results) == 1
    assert panel.charts["weather"] is chart
    panel.close()


def test_one_chart_preset_is_reusable_across_multiple_charts():
    main, sub = custom_basemaps()
    region = east_asia_chart(main_basemap=main, sub_basemap=sub)
    panel = Panel(layout=LayoutSpec(rows=1, columns=2), chart_defaults=region)
    first = panel.add_chart(id="first")
    second = panel.add_chart(id="second")
    assert tuple(panel.effective_config.charts[first.id].subplots) == (
        "main", "south_china_sea",
    )
    assert tuple(panel.effective_config.charts[second.id].subplots) == (
        "main", "south_china_sea",
    )
    assert len(panel.charts) == 2
    panel.close()


def test_basemap_info_overrides_factory_info_and_explicit_none_disables_it():
    custom = BasemapSpec(loader=EmptyLoader, map_info=MapInfo(text="from basemap", x=.9, y=.1))
    preset = east_asia_chart(
        main_basemap=custom,
        main_map_info=MapInfo(text="from argument", x=.8, y=.2),
    )
    assert preset.subplots["main"].basemap.map_info.text == "from basemap"

    disabled = BasemapSpec(loader=EmptyLoader, map_info=None)
    preset = east_asia_chart(main_basemap=disabled)
    assert preset.subplots["main"].basemap.map_info is None
