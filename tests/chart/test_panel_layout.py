"""D05 grid and absolute layout execution."""

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest
import xarray as xr

from cedarkit.plots import Panel
from cedarkit.plots.config import Cell, ChartSelector, LayoutSpec, Rect, SlotSpec, SubplotSpec
from cedarkit.plots.errors import ConfigError
from cedarkit.plots.style import ContourStyle


def field() -> xr.DataArray:
    return xr.DataArray(
        np.arange(20, dtype=float).reshape(4, 5),
        dims=("y", "x"),
    )


def style() -> ContourStyle:
    return ContourStyle(levels=(0, 5, 10, 15, 20), colors="viridis")


def add_field(panel: Panel, chart_id: str, **kwargs):
    chart = panel.add_chart(id=chart_id, **kwargs)
    layer = chart.contourf(field(), id=f"{chart_id}_field", style=style())
    return chart, layer


def test_grid_layout_supports_cross_cell_charts_and_reserved_slots():
    panel = Panel(
        layout=LayoutSpec(
            rows=2,
            columns=3,
            slots={
                "title": SlotSpec(
                    position=Cell(row=0, column=2),
                    kind="title",
                ),
                "colorbar": SlotSpec(
                    position=Cell(row=1, column=1),
                    kind="colorbar",
                ),
                "empty": SlotSpec(
                    position=Cell(row=1, column=2),
                    kind="empty",
                ),
            },
        )
    )
    wide, _ = add_field(panel, "wide", row=0, column=0, colspan=2)
    single, _ = add_field(panel, "single")

    figure = panel.render()

    assert len(figure.axes) == 2
    assert wide.main.ax.get_position().width > single.main.ax.get_position().width
    panel.close()


def test_auto_rows_reserve_slots_before_filling_unplaced_charts():
    panel = Panel(
        layout=LayoutSpec(
            rows="auto",
            columns=2,
            slots={
                "reserved": SlotSpec(
                    position=Cell(row=0, column=0),
                    kind="colorbar",
                )
            },
        )
    )
    charts = [add_field(panel, chart_id)[0] for chart_id in ("a", "b", "c")]

    figure = panel.render()

    assert panel.effective_config.layout.rows == 2
    assert len(figure.axes) == 3
    assert charts[0].main.ax.get_position().x0 > charts[1].main.ax.get_position().x0
    panel.close()


def test_explicit_layout_conflict_is_atomic():
    panel = Panel(layout=LayoutSpec(rows=1, columns=2))
    first, _ = add_field(panel, "first", row=0, column=0, colspan=2)

    with pytest.raises(ConfigError):
        panel.add_chart(id="conflict", row=0, column=1)

    assert tuple(panel.charts) == ("first",)
    assert first.id == "first"
    panel.close()


def test_layout_change_reuses_logical_handles_and_repositions_axes():
    panel = Panel(layout=LayoutSpec(rows=1, columns=2))
    first, _ = add_field(panel, "first")
    second, _ = add_field(panel, "second")
    panel.render()
    first_handle, second_handle = first, second
    old_first_position = first.main.ax.get_position().bounds

    panel.configure(layout=LayoutSpec(rows=2, columns=1))
    panel.render()

    assert first is first_handle
    assert second is second_handle
    assert first.main.ax.get_position().bounds != old_first_position
    assert first.main.ax.get_position().width > old_first_position[2]
    panel.close()


def test_absolute_layout_uses_figure_rects():
    panel = Panel(
        layout=LayoutSpec(
            mode="absolute",
            placements={
                "left": Rect(space="figure", bounds=(.1, .1, .35, .8)),
                "right": Rect(space="figure", bounds=(.55, .1, .35, .8)),
            },
        )
    )
    left, _ = add_field(panel, "left")
    right, _ = add_field(panel, "right")

    figure = panel.render()

    assert len(figure.axes) == 2
    assert left.main.ax.get_position().x0 < right.main.ax.get_position().x0
    panel.close()


def test_layout_order_selectors_control_automatic_chart_positions():
    panel = Panel(
        layout=LayoutSpec(
            rows=1,
            columns=2,
            order=(ChartSelector(role="right"), ChartSelector(role="left")),
        )
    )
    left, _ = add_field(panel, "left", role="left")
    right, _ = add_field(panel, "right", role="right")

    panel.render()

    assert right.main.ax.get_position().x0 < left.main.ax.get_position().x0
    panel.close()


def test_subplot_rects_are_relative_to_the_chart_or_parent_subplot():
    panel = Panel()
    chart = panel.add_chart(id="weather")
    chart.configure(
        subplots={
            "inset": SubplotSpec(
                position=Rect(
                    space="subplot",
                    subplot="main",
                    bounds=(.55, .55, .35, .35),
                )
            )
        }
    )
    layer = chart.contourf(
        field(),
        id="temperature",
        style=style(),
        subplots=("main", "inset"),
    )

    figure = panel.render()

    assert len(figure.axes) == 2
    assert set(layer.results) == {"main", "inset"}
    assert chart.subplots["inset"].ax.get_position().width < chart.main.ax.get_position().width
    panel.close()
