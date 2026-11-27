"""D07 titles, shared scales, colorbars and render transaction semantics."""

import matplotlib

matplotlib.use("Agg")

import cartopy.crs as ccrs
import numpy as np
import pytest
import xarray as xr

from cedarkit.plots import Panel
from cedarkit.plots.config import (
    BasemapSpec, ColorbarSpec, DecorationSpec, LayoutSpec, Rect, Theme, TitleSpec,
)
from cedarkit.plots.errors import ContentError, RenderRequiredError
from cedarkit.plots.style import ContourStyle, LevelStep
from cedarkit.plots.templates import east_asia


def field(offset: float = 0, *, name: str = "temperature") -> xr.DataArray:
    values = np.arange(20, dtype=float).reshape(4, 5) + offset
    return xr.DataArray(
        values,
        dims=("y", "x"),
        coords={"x": np.arange(5), "y": np.arange(4)},
        name=name,
        attrs={"units": "K", "standard_name": "air_temperature"},
    )


def fixed_style(levels=(0, 5, 10, 15, 20)) -> ContourStyle:
    return ContourStyle(levels=levels, colors="viridis")


def test_titles_and_colorbar_use_current_mappables_and_configured_scope():
    panel = Panel(
        decorations=DecorationSpec(
            titles={"report": TitleSpec(position=Rect(space="figure", bounds=(.1, .9, .8, .05)))},
            colorbars={
                "temperature": ColorbarSpec(
                    position=Rect(space="figure", bounds=(.9, .15, .03, .7)),
                    ticks=(0, 10, 20),
                )
            },
        )
    )
    chart = panel.add_chart(id="weather")
    layer = chart.contourf(field(), style=fixed_style(), id="temperature")
    panel.set_title("Forecast", id="report")
    chart.set_title("Temperature", id="chart_title")
    colorbar_id = panel.colorbar(layer, id="temperature", label="K")

    figure = panel.render()

    assert colorbar_id == "temperature"
    assert len(figure.axes) == 2
    assert {text.get_text() for text in figure.texts} == {"Forecast"}
    assert any(text.get_text() == "Temperature" for text in chart.main.ax.texts)
    assert tuple(figure.axes[-1].get_yticks()) == (0, 10, 20)
    assert layer.results["main"].mappable is not None

    old_subplot = chart.main
    panel.configure(layout=panel.effective_config.layout)
    new_figure = panel.render()
    assert new_figure is not figure
    with pytest.raises(RenderRequiredError):
        old_subplot.ax
    assert len(new_figure.axes) == 2
    assert layer.results["main"].generation == 2
    panel.close()


def test_shared_dynamic_scale_uses_all_prepared_fields():
    panel = Panel(layout=LayoutSpec(rows=1, columns=2))
    first = panel.add_chart(id="first")
    second = panel.add_chart(id="second")
    style = ContourStyle(levels=LevelStep(step=5, reference=0), colors="viridis")
    first_layer = first.contourf(field(-2), id="first_field", style=style)
    second_layer = second.contourf(field(101), id="second_field", style=style)

    scale_id = panel.share_scale((first_layer, second_layer), id="temperature_range")
    panel.colorbar((first_layer, second_layer), id="temperature", label="K")
    figure = panel.render()

    assert scale_id == "temperature_range"
    first_norm = first_layer.results["main"].mappable.norm
    second_norm = second_layer.results["main"].mappable.norm
    assert tuple(first_norm.boundaries) == tuple(second_norm.boundaries)
    assert min(first_norm.boundaries) <= -5
    assert max(first_norm.boundaries) >= 120
    assert len(figure.axes) == 3
    panel.close()


def test_incompatible_colorbar_fails_without_replacing_last_successful_figure():
    panel = Panel()
    chart = panel.add_chart(id="weather")
    first = chart.contourf(field(), id="first", style=fixed_style())
    second = chart.contourf(
        field(),
        id="second",
        style=ContourStyle(levels=(0, 4, 8, 12, 16, 20), colors="plasma"),
    )
    old_figure = panel.render()
    panel.colorbar((first, second), id="bad")

    with pytest.raises(ContentError, match="incompatible"):
        panel.render()

    assert panel.fig is old_figure
    assert panel.dirty
    with pytest.raises(RenderRequiredError):
        first.results
    panel.close()


def test_layer_references_must_be_removed_before_layer_removal():
    panel = Panel()
    chart = panel.add_chart(id="weather")
    layer = chart.contourf(field(), id="temperature", style=fixed_style())
    panel.colorbar(layer, id="temperature")
    with pytest.raises(ContentError, match="layer_in_use"):
        layer.remove()
    panel.remove_colorbar("temperature")
    layer.remove()
    panel.close()


@pytest.mark.parametrize("figsize", [(10, 4), (6, 9)])
def test_chart_colorbar_tracks_actual_map_frame_when_aspect_changes(figsize, tmp_path):
    template = east_asia(with_inset=False, main_basemap=BasemapSpec(features=()))
    with Panel(template=template, layout=LayoutSpec(figsize=figsize)) as panel:
        chart = panel.add_chart(id="map")
        chart.configure(decorations=DecorationSpec(
            colorbars={"local": ColorbarSpec(tick_fontsize=13)},
        ))
        data = field().rename(x="longitude", y="latitude").assign_coords(
            longitude=np.linspace(70, 140, 5), latitude=np.linspace(15, 55, 4),
        )
        layer = chart.contourf(data, style=fixed_style(), data_crs=ccrs.PlateCarree())
        chart.set_title("Map title")
        chart.colorbar(layer, id="local", label="Air temperature (K)")
        panel.save(tmp_path / "map.png", dpi=150)
        main = chart.main.ax
        bar = panel.fig.axes[-1]
        assert bar.bbox.y0 == pytest.approx(main.bbox.y0)
        assert bar.bbox.height == pytest.approx(main.bbox.height)
        right_edge = main.get_tightbbox(bbox_extra_artists=[]).x1
        assert bar.bbox.x0 - right_edge == pytest.approx(7 * panel.fig.dpi / 72)
        assert bar.get_ylabel() == "Air temperature (K)"
        assert bar.get_yticklabels()[0].get_fontsize() == 13
        assert main.texts[-1].get_window_extent().y0 > main.bbox.y1


def test_panel_defaults_leave_space_for_shared_horizontal_bar_and_respect_placements(tmp_path):
    with Panel(
        layout=LayoutSpec(rows=1, columns=2, figsize=(7, 3)),
        theme=Theme(tick_fontsize=14, font_size=15),
        decorations=DecorationSpec(colorbars={"shared": ColorbarSpec(orientation="horizontal")}),
    ) as panel:
        chart_a = panel.add_chart(id="a")
        chart_b = panel.add_chart(id="b")
        layers = [chart.contourf(field(), style=fixed_style()) for chart in (chart_a, chart_b)]
        panel.colorbar(layers, id="shared", label="Temperature (K)")
        panel.save(tmp_path / "shared.png")
        bar = panel.fig.axes[-1]
        assert bar.bbox.x0 == pytest.approx(chart_a.main.ax.bbox.x0)
        assert bar.bbox.x1 == pytest.approx(chart_b.main.ax.bbox.x1)
        assert bar.bbox.y1 < min(chart.main.ax.xaxis.get_tightbbox().y0 for chart in (chart_a, chart_b))
        assert bar.xaxis.label.get_fontsize() == 15

        bounds = (.15, .04, .7, .04)
        panel.configure(decorations=DecorationSpec(colorbars={"shared": ColorbarSpec(
            orientation="horizontal", position=Rect(space="figure", bounds=bounds),
        )}))
        assert panel.render().axes[-1].get_position().bounds == pytest.approx(bounds)
