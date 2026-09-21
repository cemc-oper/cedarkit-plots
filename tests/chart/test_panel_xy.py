"""D04 stable content handles and the minimal XY render lifecycle."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest
import xarray as xr

from cedarkit.plots import Panel, PlotLayer
from cedarkit.plots.config import LayoutSpec
from cedarkit.plots.errors import ClosedError, ContentError, RenderRequiredError
from cedarkit.plots.style import BarbStyle, ContourStyle


def field(offset: float = 0) -> xr.DataArray:
    x = np.linspace(0, 4, 5)
    y = np.linspace(0, 3, 4)
    values = np.add.outer(y, x) + offset
    return xr.DataArray(values, dims=("y", "x"), coords={"x": x, "y": y})


def style() -> ContourStyle:
    return ContourStyle(levels=(0, 2, 4, 6, 8), colors="viridis")


def test_registration_is_logical_and_first_render_creates_the_figure():
    panel = Panel(layout=LayoutSpec(rows=1, columns=1))
    chart = panel.add_chart(id="weather")
    source_style = style()
    layer = chart.contourf(field(), id="temperature", style=source_style)

    assert panel.fig is None
    assert isinstance(layer, PlotLayer)
    assert layer.style is not source_style
    with pytest.raises(RenderRequiredError):
        layer.results

    figure = panel.render()
    assert panel.fig is figure
    assert len(figure.axes) == 1
    assert tuple(layer.results) == ("main",)
    assert layer.results["main"].generation == 1
    assert chart.main.ax is figure.axes[0]

    assert panel.render() is figure
    assert len(figure.axes) == 1
    assert panel.rendered_revision == panel.revision
    panel.close()


def test_append_update_remove_and_handles_are_stable():
    panel = Panel()
    chart = panel.add_chart(id="weather")
    filled = chart.contourf(field(), id="temperature", style=style())
    panel.render()
    original_chart = chart
    original_layer = filled

    lines = chart.contour(
        field(), id="isotherms",
        style=ContourStyle(levels=(1, 3, 5), colors=("black",)),
    )
    assert chart is original_chart
    assert filled is original_layer
    assert panel.dirty
    with pytest.raises(RenderRequiredError):
        filled.results
    panel.render()
    assert tuple(chart.layers) == ("temperature", "isotherms")
    assert len(lines.results) == 1

    old_data = filled.data
    filled.update(data=field(1))
    assert filled.data is not old_data
    assert panel.dirty
    panel.render()
    assert filled.results["main"].generation == 3

    lines.remove()
    assert tuple(chart.layers) == ("temperature",)
    panel.render()
    with pytest.raises(ContentError):
        lines.remove()
    assert tuple(chart.layers) == ("temperature",)
    panel.close()


def test_invalid_update_does_not_change_logical_layer():
    panel = Panel()
    chart = panel.add_chart(id="weather")
    layer = chart.contourf(field(), id="temperature", style=style())
    original_data = layer.data
    with pytest.raises(ContentError):
        layer.update(data=np.ones((4, 5)))
    assert layer.data is original_data
    assert tuple(chart.layers) == ("temperature",)
    panel.close()


def test_barbs_register_and_render_on_xy_axes():
    panel = Panel()
    chart = panel.add_chart(id="wind")
    u = field()
    v = field(.5)
    layer = chart.barbs(u, v, id="wind", style=BarbStyle())
    panel.render()
    assert layer.results["main"].mappable is None
    assert layer.results["main"].artists
    panel.close()


def test_context_manager_save_and_close_are_owned_by_panel(tmp_path):
    with Panel() as panel:
        chart = panel.add_chart(id="weather")
        chart.contourf(field(), id="temperature", style=style())
        output = tmp_path / "xy.png"
        panel.save(output)
        assert output.exists() and output.stat().st_size > 0
    assert panel.closed
    with pytest.raises(ClosedError):
        panel.render()
    assert plt.get_fignums() == []
