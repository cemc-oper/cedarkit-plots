"""D06 map subplots, CRS transforms and multi-target layer results."""

import hashlib

import matplotlib

matplotlib.use("Agg")

import cartopy.crs as ccrs
import numpy as np
import pytest
import xarray as xr

from cedarkit.plots import MapSubplot, Panel
from cedarkit.plots.config import (
    BasemapSpec,
    LayoutSpec,
    MapInfo,
    MapFeatureSpec,
    Rect,
    SubplotSpec,
)
from cedarkit.plots.domains import Domain
from cedarkit.plots.errors import ContentError
from cedarkit.plots.map import MapLoader, MapType
from cedarkit.plots.map.default import DefaultMapLoader
from cedarkit.plots.style import BarbStyle, ContourStyle


class RecordingLoader(MapLoader):
    calls: list[tuple[str, dict]] = []

    def get_feature(self, name: str, **kwargs):
        self.calls.append((name, dict(kwargs)))
        return []


def test_default_china_features_match_resource_baseline():
    expected = {
        "china_coastline": (0, 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        "china_borders": (1, 1367, "8d17d094bf2707e6e05c05f3422137ab999781cd98ea36b5ce522b5f42ebe663"),
        "china_provinces": (0, 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        "china_rivers": (0, 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        "china_nine_lines": (1, 10, "14464135431ee7f6d7558721c46294fa5891609a509b07b4dac2011b91f6796b"),
        "global_borders": (0, 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    }
    loader = DefaultMapLoader()
    for name, (feature_count, geometry_count, expected_hash) in expected.items():
        features = loader.get_feature(name)
        geometries = [geometry for feature in features for geometry in feature.geometries()]
        digest = hashlib.sha256(b"".join(geometry.wkb for geometry in geometries)).hexdigest()
        assert (len(features), len(geometries), digest) == (
            feature_count, geometry_count, expected_hash,
        )


def field(offset: float = 0) -> xr.DataArray:
    lon = np.linspace(60, 150, 5)
    lat = np.linspace(0, 65, 4)
    return xr.DataArray(
        np.add.outer(lat, lon) + offset,
        dims=("lat", "lon"),
        coords={"lon": lon, "lat": lat},
    )


def map_domain(map_crs=ccrs.PlateCarree()) -> Domain:
    return Domain(
        extent=(100, 130, 20, 50),
        extent_crs=ccrs.PlateCarree(),
        map_crs=map_crs,
    )


def map_spec(domain: Domain, *, map_info=None) -> SubplotSpec:
    return SubplotSpec(
        kind="map",
        domain=domain,
        basemap=BasemapSpec(
            loader=RecordingLoader,
            map_type=MapType.Portrait,
            features=(
                MapFeatureSpec(
                    name="china_borders",
                    kwargs={"scale": "50m"},
                ),
            ),
            map_info=map_info,
        ),
    )


def configure_main_and_inset(chart, *, map_crs=ccrs.PlateCarree()):
    main_domain = map_domain(map_crs)
    inset_domain = Domain(
        extent=(108, 122, 4, 24),
        extent_crs=ccrs.PlateCarree(),
        map_crs=ccrs.PlateCarree(),
    )
    chart.configure(
        subplots={
            "main": map_spec(
                main_domain,
                map_info=MapInfo(text="main", x=.98, y=.02),
            ),
            "south_china_sea": SubplotSpec(
                kind="map",
                domain=inset_domain,
                position=Rect(
                    space="subplot",
                    subplot="main",
                    bounds=(.68, .06, .28, .3),
                ),
                basemap=BasemapSpec(
                    loader=RecordingLoader,
                    map_type=MapType.SouthChinaSea,
                ),
            ),
        }
    )


def test_map_subplots_use_relative_inset_and_preserve_crs_roles():
    RecordingLoader.calls.clear()
    panel = Panel(layout=LayoutSpec(rows=1, columns=1))
    chart = panel.add_chart(id="weather")
    configure_main_and_inset(chart, map_crs=ccrs.Mercator())
    layer = chart.contourf(
        field(),
        id="temperature",
        style=ContourStyle(levels=(120, 130, 140, 150, 160), colors="viridis"),
        subplots="all",
        data_crs=ccrs.PlateCarree(),
    )

    figure = panel.render()

    assert len(figure.axes) == 2
    assert isinstance(chart.subplots["main"], MapSubplot)
    assert isinstance(chart.subplots["south_china_sea"], MapSubplot)
    assert chart.subplots["main"].map_crs == ccrs.Mercator()
    assert set(layer.results) == {"main", "south_china_sea"}
    assert all(result.mappable is not None for result in layer.results.values())
    assert chart.subplots["south_china_sea"].ax.get_position().width < chart.main.ax.get_position().width
    assert any(text.get_text() == "main" for text in chart.main.ax.texts)
    assert RecordingLoader.calls == [("china_borders", {"scale": "50m"})]
    panel.close()


def test_four_charts_each_render_main_and_inset_targets():
    RecordingLoader.calls.clear()
    panel = Panel(layout=LayoutSpec(rows=2, columns=2))
    charts = []
    layers = []
    for index in range(4):
        chart = panel.add_chart(id=f"chart_{index}")
        configure_main_and_inset(chart)
        charts.append(chart)
        layers.append(
            chart.contour(
                field(),
                id="isotherms",
                style=ContourStyle(levels=(120, 130, 140, 150), colors=("black",)),
                subplots="all",
                data_crs=ccrs.PlateCarree(),
            )
        )

    figure = panel.render()

    assert len(figure.axes) == 8
    assert all(set(layer.results) == {"main", "south_china_sea"} for layer in layers)
    assert all(chart.subplots["main"].chart is chart for chart in charts)
    panel.close()


def test_map_barbs_transform_and_earth_basis_validation():
    panel = Panel()
    chart = panel.add_chart(id="wind")
    configure_main_and_inset(chart)
    u = field()
    v = field(.5)
    layer = chart.barbs(
        u,
        v,
        id="wind",
        style=BarbStyle(),
        subplots="all",
        data_crs=ccrs.PlateCarree(),
        vector_basis="earth",
    )

    panel.render()

    assert set(layer.results) == {"main", "south_china_sea"}
    assert all(result.artists for result in layer.results.values())
    panel.close()

    invalid_panel = Panel()
    invalid_chart = invalid_panel.add_chart(id="invalid_wind")
    configure_main_and_inset(invalid_chart)
    with pytest.raises(ContentError, match="PlateCarree"):
        invalid_chart.barbs(
            u,
            v,
            style=BarbStyle(),
            data_crs=ccrs.Mercator(),
            vector_basis="earth",
        )
    invalid_panel.close()
