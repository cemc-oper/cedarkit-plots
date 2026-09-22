"""D08 reusable templates, precedence and atomic switching."""

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest
import xarray as xr

from cedarkit.plots import Panel
from cedarkit.plots.config import (
    RESET,
    ChartRule,
    ChartSelector,
    ChartSpec,
    LayoutSpec,
    Rect,
    SubplotSpec,
    Theme,
)
from cedarkit.plots.errors import ConfigError
from cedarkit.plots.style import ContourStyle
from cedarkit.plots.templates import ChartTemplate, PanelTemplate


def field() -> xr.DataArray:
    return xr.DataArray(
        np.arange(20, dtype=float).reshape(4, 5),
        dims=("y", "x"),
        coords={"x": np.arange(5), "y": np.arange(4)},
        name="temperature",
        attrs={"units": "K", "standard_name": "air_temperature"},
    )


def inset(enabled=True) -> SubplotSpec:
    return SubplotSpec(
        enabled=enabled,
        position=Rect(space="subplot", subplot="main", bounds=(.58, .58, .35, .35)),
    )


def chart_template(*, with_inset: bool, title_fontsize: float) -> ChartTemplate:
    subplots = {"main": SubplotSpec()}
    if with_inset:
        subplots["inset"] = inset()
    return ChartTemplate(subplots=subplots, theme=Theme(title_fontsize=title_fontsize))


def test_template_switch_preserves_content_and_changes_targets_atomically():
    template_a = PanelTemplate(
        layout=LayoutSpec(rows=1, columns=1, expected_charts=1),
        chart_defaults=chart_template(with_inset=True, title_fontsize=12),
        theme=Theme(font_size=10),
    )
    template_b = PanelTemplate(
        layout=LayoutSpec(rows=1, columns=1, expected_charts=1),
        chart_defaults=chart_template(with_inset=False, title_fontsize=10),
        theme=Theme(font_size=9),
    )

    panel = Panel(template=template_a)
    assert panel.charts == {}
    chart = panel.add_chart(id="weather")
    style = ContourStyle(levels=(0, 5, 10, 15, 20), colors="viridis")
    layer = chart.contourf(field(), style=style, id="temperature", subplots="all")
    chart.set_title("Same logical content")
    panel.configure(theme=Theme(title_fontsize=16))
    data_ref = layer.data
    style_ref = layer.style

    for template, result_count in ((template_a, 2), (template_b, 1), (template_a, 2)):
        panel.apply_template(template)
        panel.render()
        assert panel.charts["weather"] is chart
        assert chart.layers["temperature"] is layer
        assert layer.data is data_ref
        assert layer.style == style_ref
        assert len(layer.results) == result_count
        assert panel.effective_config.theme.title_fontsize == 16

    fixed = chart.contour(
        field(),
        style=ContourStyle(levels=(0, 5, 10, 15, 20), colors=("black",)),
        id="fixed_inset",
        subplots=("inset",),
    )
    old_figure = panel.render()
    old_revision = panel.revision
    with pytest.raises(ConfigError) as caught:
        panel.apply_template(template_b)
    assert caught.value.code == "missing_target"
    assert panel.fig is old_figure
    assert panel.revision == old_revision
    assert panel.effective_config.charts["weather"].subplots["inset"].enabled is True
    assert fixed.chart is chart

    fixed.remove()
    panel.configure(theme=Theme(title_fontsize=RESET))
    assert panel.effective_config.theme.title_fontsize == 12
    chart.configure(subplots={"inset": SubplotSpec(enabled=False)})
    panel.apply_template(None)
    panel.render()
    assert len(layer.results) == 1
    panel.close()


def test_template_sources_follow_rule_and_user_override_precedence():
    template_rule = ChartRule(
        selector=ChartSelector(role="member"),
        spec=ChartTemplate(theme=Theme(title_fontsize=14)),
    )
    template = PanelTemplate(
        chart_defaults=ChartTemplate(
            subplots={"main": SubplotSpec(), "inset": inset()},
            theme=Theme(title_fontsize=10),
        ),
        chart_rules=(template_rule,),
        theme=Theme(title_fontsize=12),
    )
    panel = Panel(template=template)
    chart = panel.add_chart(id="member_1", role="member")
    assert panel.effective_config.theme.title_fontsize == 12
    assert panel.effective_config.charts[chart.id].theme.title_fontsize == 14

    panel.configure(
        theme=Theme(title_fontsize=16),
        chart_defaults=ChartSpec(
            subplots={"inset": SubplotSpec(enabled=False)},
            theme=Theme(title_fontsize=18),
        ),
    )
    effective = panel.effective_config.charts[chart.id]
    assert effective.theme.title_fontsize == 18
    assert effective.subplots["inset"].enabled is False

    chart.configure(theme=Theme(title_fontsize=20))
    assert panel.effective_config.charts[chart.id].theme.title_fontsize == 20

    user_rule = ChartRule(
        selector=ChartSelector(role="member"),
        spec=ChartTemplate(theme=Theme(title_fontsize=21)),
    )
    panel.configure(chart_rules=(user_rule,))
    assert panel.effective_config.charts[chart.id].theme.title_fontsize == 20
    chart.configure(theme=RESET)
    assert panel.effective_config.charts[chart.id].theme.title_fontsize == 21
    panel.close()


def test_template_values_are_immutable_reusable_and_do_not_accept_reset():
    subplots = {"main": SubplotSpec()}
    template = PanelTemplate(chart_defaults=ChartTemplate(subplots=subplots))
    subplots.clear()
    first = Panel(template=template)
    second = Panel(template=template)
    first_chart = first.add_chart(id="first")
    second_chart = second.add_chart(id="second")
    assert "main" in first.effective_config.charts[first_chart.id].subplots
    assert "main" in second.effective_config.charts[second_chart.id].subplots
    first.configure(theme=Theme(title_fontsize=18))
    assert second.effective_config.theme.title_fontsize == 12
    first.close()
    second.close()

    with pytest.raises(ConfigError, match="RESET"):
        ChartTemplate(theme=Theme(title_fontsize=RESET))
    with pytest.raises(ConfigError, match="PanelTemplate"):
        PanelTemplate(chart_defaults=object())


def test_empty_panel_can_hold_pending_required_role_until_content_is_complete():
    template = PanelTemplate(
        layout=LayoutSpec(rows=1, columns=2),
        chart_rules=(
            ChartRule(
                selector=ChartSelector(role="control", required=True),
                spec=ChartTemplate(theme=Theme(title_fontsize=13)),
            ),
        ),
    )
    panel = Panel(template=template)
    member = panel.add_chart(id="member", role="member")
    assert any(issue.code == "missing_target" for issue in panel.effective_config.pending)
    with pytest.raises(ConfigError, match="required chart rule"):
        panel.apply_template(template)
    assert panel.charts["member"] is member

    control = panel.add_chart(id="control", role="control")
    assert panel.effective_config.pending == ()
    assert panel.effective_config.charts[control.id].theme.title_fontsize == 13
    panel.close()
