"""R01 regression probes: exact mappings, input contracts and atomic state."""
import copy

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import numpy as np
import pytest
import xarray as xr

from cedarkit.plots import Panel
from cedarkit.plots.config import (
    AnnotationSpec, ChartRule, ChartSelector, ChartSpec, LayoutSpec,
    BasemapSpec, Rect, SubplotSpec, TextPosition,
)
from cedarkit.plots.domains import Domain
from cedarkit.plots.errors import ConfigError, ContentError
from cedarkit.plots.style import BarbStyle, ContourStyle
from cedarkit.plots.templates import PanelTemplate, north_polar


@pytest.fixture(autouse=True)
def cleanup():
    yield
    plt.close("all")


def field(x=(0, 3), y=(0, 3), units=None):
    return xr.DataArray(np.arange(16).reshape(4, 4), dims=("lat", "lon"),
                        coords={"lon": np.linspace(*x, 4), "lat": np.linspace(*y, 4)},
                        attrs={} if units is None else {"units": units, "standard_name": "air_temperature"})


def style(cmap="viridis", levels=(0, 3, 6, 9), **kwargs):
    return ContourStyle(colors=cmap, levels=levels, **kwargs)


def map_spec(extent=(0, 3, 0, 3), **kwargs):
    return SubplotSpec(kind="map", domain=Domain(extent=extent, extent_crs=ccrs.PlateCarree()),
                       basemap=BasemapSpec(features=(), map_info=None), **kwargs)


def test_discrete_mapping_special_colors_and_continuous_map():
    cmap = colors.ListedColormap(["red", "green", "blue"])
    cmap.set_under("cyan")
    cmap.set_over("yellow")
    cmap.set_bad("magenta")
    with Panel() as panel:
        chart = panel.add_chart()
        layer = chart.contourf(field(), style=style(cmap, extend="both"))
        panel.render()
        mappable = layer.results["main"].mappable
        np.testing.assert_allclose(mappable.to_rgba([1, 4, 7]), colors.to_rgba_array(["red", "green", "blue"]))
        np.testing.assert_allclose(mappable.to_rgba(np.ma.masked_invalid([-1, 10, np.nan])), colors.to_rgba_array(["cyan", "yellow", "magenta"]))
        layer.update(style=style("jet"))
        panel.render()
        mappable = layer.results["main"].mappable
        np.testing.assert_allclose(mappable.to_rgba([1, 4, 7]), plt.get_cmap("jet")([0, 127, 255]))
        old = panel.fig
        with pytest.raises(ContentError, match="insufficient colors"):
            layer.update(style=style(colors.ListedColormap(["red", "blue"])))
        assert panel.fig is old


@pytest.mark.parametrize("extend,palette", [("neither", ("red", "green", "blue")),
    ("both", ("cyan", "red", "green", "blue", "yellow"))])
def test_filled_color_tuple(extend, palette):
    with Panel() as panel:
        layer = panel.add_chart().contourf(field(), style=style(palette, extend=extend))
        panel.render()
        mappable = layer.results["main"].mappable
        np.testing.assert_allclose(mappable.to_rgba([1, 4, 7]), colors.to_rgba_array(["red", "green", "blue"]))
        if extend == "both":
            np.testing.assert_allclose(mappable.to_rgba([-1, 10]), colors.to_rgba_array(["cyan", "yellow"]))
        with pytest.raises(ContentError, match="needs 3 colors"):
            layer.update(style=style(("red", "blue")))


def test_full_palette_comparison_and_atomic_scale_update():
    cmap = colors.ListedColormap(["red"] * 256, name="same")
    altered = list(cmap.colors)
    altered[100] = "blue"
    bad = colors.ListedColormap(altered, name="same")
    with Panel() as panel:
        chart = panel.add_chart()
        first = chart.contourf(field(units="K"), style=style(cmap, tuple(range(257))))
        second = chart.contourf(field(units="K"), style=style(copy.deepcopy(cmap), tuple(range(257))))
        scale = panel.share_scale((first, second))
        panel.render()
        old, revision = panel.fig, panel.revision
        with pytest.raises(ContentError, match="identical|incompatible"):
            second.update(style=style(bad, tuple(range(257))))
        assert panel.revision == revision and panel.fig is old and not panel.dirty
        assert second.results["main"].mappable is not None
        panel.remove_scale(scale)
        second.update(style=style(bad, tuple(range(257))))
        with pytest.raises(ContentError):
            panel.share_scale((first, second))
        panel.colorbar((first, second))
        with pytest.raises(ContentError):
            panel.render()
        assert panel.fig is old


@pytest.mark.parametrize("units", [None, "m/s"])
def test_barb_units_and_atomic_update(units):
    with Panel() as panel:
        chart = panel.add_chart()
        u, v = field(units=units), field(units=units)
        layer = chart.barbs(u, v, style=BarbStyle())
        panel.render()
        revision, old = panel.revision, panel.fig
        with pytest.raises(ContentError) as caught:
            layer.update(data=(field(units="m/s"), field(units="knots")))
        assert caught.value.code == "unit_mismatch"
        assert layer.data[0] is u and layer.data[1] is v
        assert panel.revision == revision and panel.fig is old and not panel.dirty
        with pytest.raises(ContentError):
            chart.barbs(field(units="m/s"), field(units="knots"), style=BarbStyle())
        with pytest.raises(ContentError):
            chart.barbs(u, v, style=BarbStyle(expected_units="knots"))
        chart.barbs(field(units="m/s"), field(units="m/s"), style=BarbStyle(expected_units="m/s"))
        panel.render()


@pytest.mark.parametrize("palette", ["viridis", plt.get_cmap("viridis"), ("red",), ("red", "green", "blue", "black")])
def test_contour_palette_and_explicit_line_colors(palette):
    with Panel() as panel:
        layer = panel.add_chart().contour(field(), style=style(palette))
        panel.render()
        result = layer.results["main"].mappable
        if isinstance(palette, (str, colors.Colormap)):
            cmap = plt.get_cmap(palette) if isinstance(palette, str) else palette
            expected = cmap(colors.BoundaryNorm((0, 3, 6, 9), cmap.N)([0, 3, 6, 9]))
        else:
            expected = colors.to_rgba_array(palette * 4 if len(palette) == 1 else palette)
        np.testing.assert_allclose(result.get_edgecolors(), expected)
        with pytest.raises(ContentError):
            layer.update(style=style(("red", "blue")))


def test_geographic_polar_annotations_match_legacy_after_resize_and_reuse():
    template = north_polar(basemap=BasemapSpec(features=(), map_info=None))
    for size in [(8, 8), (12, 6)]:
        with Panel(template=template, layout=LayoutSpec(figsize=size)) as panel:
            chart = panel.add_chart()
            for _ in range(2):
                panel.render(force=True)
                ax = chart.main.ax
                labels = {text.get_text(): text for text in ax.texts}
                assert len(labels) == 12
                points = []
                for longitude, annotation in template.chart_defaults.subplots["main"].annotations.items():
                    artist = labels[annotation.text]
                    lon = float(longitude.removeprefix("longitude_"))
                    lat = -.5 if annotation.text == "60W" else -4
                    expected = ax.transData.transform(ax.projection.transform_point(lon, lat, ccrs.Geodetic()))
                    actual = artist.get_transform().transform(artist.get_position())
                    np.testing.assert_allclose(actual, expected, atol=1e-7)
                    assert artist.get_va() == ("bottom" if annotation.text == "60W" else "center")
                    points.append(actual)
                assert np.ptp(np.array(points)[:, 1]) > 100


@pytest.mark.parametrize("extent", [(10, 13, 10, 13), (0, 4, 0, 3)])
def test_coverage_rejects_disjoint_and_partial_and_retains_old_figure(extent):
    with Panel(chart_defaults=ChartSpec(subplots={"main": map_spec()})) as panel:
        chart = panel.add_chart()
        layer = chart.contourf(field(), style=style(), data_crs=ccrs.PlateCarree())
        old = panel.render()
        chart.configure(subplots={"main": map_spec(extent)})
        with pytest.raises(ContentError) as caught:
            panel.render()
        assert caught.value.code == "insufficient_coverage"
        assert layer.id in caught.value.path and "domain" in caught.value.path
        assert panel.fig is old and layer.data.shape == (4, 4)


def test_coverage_checks_each_inset():
    with Panel(chart_defaults=ChartSpec(subplots={"main": map_spec(), "inset": map_spec((0, 4, 0, 3), position=Rect(space="chart", bounds=(.6, .1, .3, .3)))})) as panel:
        panel.add_chart().contourf(field(), style=style(), data_crs=ccrs.PlateCarree(), subplots="all")
        with pytest.raises(ContentError) as caught:
            panel.render()
        assert caught.value.path[-1] == "inset"


@pytest.mark.parametrize("extent,x", [((170, 190, 0, 3), (-180, 180)), ((-180, 180, 0, 90), (0, 3))])
def test_uncertain_seam_and_polar_coverage_not_rejected(extent, x):
    with Panel(chart_defaults=ChartSpec(subplots={"main": map_spec(extent)})) as panel:
        panel.add_chart().contourf(field(x=x), style=style(), data_crs=ccrs.PlateCarree())
        panel.render()


@pytest.mark.parametrize("target", ["main", ("inset",)])
def test_pending_map_and_fixed_target_become_same_rendered_layer(target):
    with Panel() as panel:
        chart = panel.add_chart()
        layer = chart.contourf(field(), style=style(), data_crs=ccrs.PlateCarree(), subplots=target)
        assert panel.validate() and panel.fig is None
        with pytest.raises(ConfigError):
            panel.validate(complete=True)
        with pytest.raises(ConfigError):
            panel.render()
        specs = {"main": map_spec()}
        if target != "main":
            specs["inset"] = map_spec(position=Rect(space="chart", bounds=(.6, .1, .3, .3)))
        panel.apply_template(PanelTemplate(chart_defaults=ChartSpec(subplots=specs)))
        assert not panel.validate()
        panel.render()
        assert chart.layers[layer.id] is layer and len(layer.results) == 1
        revision, old = panel.revision, panel.fig
        with pytest.raises(ConfigError):
            panel.apply_template(None)
        assert panel.revision == revision and panel.fig is old and not panel.dirty


@pytest.mark.parametrize("source", ["template", "rule", "defaults", "chart"])
def test_explicit_empty_subplots_disallow_pending(source):
    spec = ChartSpec(subplots={})
    kwargs = {"template": PanelTemplate(chart_defaults=spec)} if source == "template" else {}
    if source == "defaults":
        kwargs["chart_defaults"] = spec
    if source == "rule":
        kwargs["chart_rules"] = (ChartRule(selector=ChartSelector(id="test"), spec=spec),)
    with Panel(**kwargs) as panel:
        chart = panel.add_chart(id="test")
        if source == "chart":
            chart.configure(subplots={})
        revision = panel.revision
        with pytest.raises(ContentError):
            chart.contourf(field(), style=style(), data_crs=ccrs.PlateCarree())
        with pytest.raises(ContentError):
            chart.contourf(field(), style=style(), subplots=("missing",))
        assert not chart.layers and panel.revision == revision


def test_geographic_annotation_configuration_validation():
    with pytest.raises(ConfigError):
        AnnotationSpec(text="label", crs="EPSG:4326")
    with pytest.raises(ConfigError):
        AnnotationSpec(text="label", crs=ccrs.Geodetic(), position=TextPosition(space="figure", xy=(0, 0)))
    with pytest.raises(ConfigError):
        Panel(chart_defaults=ChartSpec(subplots={"main": SubplotSpec(annotations={"label": AnnotationSpec(text="label", crs=ccrs.Geodetic(), position=TextPosition(space="subplot", xy=(0, 0)))})})).add_chart()


@pytest.mark.parametrize("special", ["under", "over", "bad"])
def test_shared_palette_checks_special_colors_and_equal_copies(special):
    cmap = colors.ListedColormap(["red", "green", "blue"])
    with Panel() as panel:
        chart = panel.add_chart()
        first = chart.contourf(field(units="K"), style=style(cmap))
        second = chart.contourf(field(units="K"), style=style(copy.deepcopy(cmap)))
        panel.colorbar((first, second))
        old = panel.render()
        changed = copy.deepcopy(cmap)
        getattr(changed, f"set_{special}")("cyan")
        second.update(style=style(changed))
        with pytest.raises(ContentError):
            panel.share_scale((first, second))
        with pytest.raises(ContentError):
            panel.render()
        assert panel.fig is old


def test_explicit_target_update_and_configure_fail_atomically():
    with Panel(chart_defaults=ChartSpec(subplots={"main": map_spec()})) as panel:
        chart = panel.add_chart()
        layer = chart.contourf(field(), style=style(), data_crs=ccrs.PlateCarree())
        old = panel.render()
        revision = panel.revision
        with pytest.raises(ContentError):
            layer.update(subplots=("missing",))
        with pytest.raises(ConfigError):
            chart.configure(subplots={"main": SubplotSpec(enabled=False)})
        assert layer.subplots == "main"
        assert panel.revision == revision and panel.fig is old and not panel.dirty


def test_coverage_different_crs_is_not_proved_by_raw_bounds():
    with Panel(chart_defaults=ChartSpec(subplots={"main": map_spec((10, 13, 10, 13))})) as panel:
        panel.add_chart().contourf(field(), style=style(), data_crs=ccrs.Mercator())
        panel.render()


def test_geographic_annotation_default_targets_own_map_subplot():
    annotation = AnnotationSpec(text="inset label", crs=ccrs.Geodetic(),
                                position=TextPosition(space="subplot", xy=(1, 2)))
    with Panel(chart_defaults=ChartSpec(subplots={"main": map_spec(), "inset": map_spec(
        position=Rect(space="chart", bounds=(.6, .1, .3, .3)), annotations={"label": annotation})})) as panel:
        chart = panel.add_chart()
        panel.render()
        assert not chart.main.ax.texts
        artist = chart.subplots["inset"].ax.texts[0]
        ax = chart.subplots["inset"].ax
        expected = ax.transData.transform(ax.projection.transform_point(1, 2, ccrs.Geodetic()))
        np.testing.assert_allclose(artist.get_transform().transform(artist.get_position()), expected)
