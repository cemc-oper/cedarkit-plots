"""D10 EnsCN ordering, identity, and caller-owned statistical Charts."""

import matplotlib

matplotlib.use("Agg")

import cartopy.crs as ccrs
import pytest

from cedarkit.plots import Panel
from cedarkit.plots.config import BasemapSpec, Cell, MapFeatureSpec, Rect, UNSET
from cedarkit.plots.errors import ConfigError
from cedarkit.plots.map import MapLoader, MapType
from cedarkit.plots.templates import ens_cn, ens_cn_chart, ens_cn_layout


class EmptyLoader(MapLoader):
    def get_feature(self, name: str, **kwargs):
        return []


def empty_basemap() -> BasemapSpec:
    return BasemapSpec(loader=EmptyLoader, map_type=MapType.Portrait, features=())


def add_members(panel: Panel, count: int = 15):
    charts = []
    for index in range(count):
        if index == 0:
            chart = panel.add_chart(id="ctl", role="control")
        else:
            chart = panel.add_chart(id=f"mem{index:02d}", role="member")
        charts.append(chart)
    return charts


def test_fifteen_charts_reflow_from_five_to_three_columns_without_identity_changes():
    panel = Panel(template=ens_cn(basemap=empty_basemap()))
    charts = add_members(panel)

    assert len(panel.charts) == 15
    assert panel.effective_config.layout.rows == 3
    assert panel.effective_config.layout.columns == 5
    assert panel.validate(complete=True) == ()

    first_figure = panel.render()
    assert len(first_figure.axes) == 15

    panel.apply_template(ens_cn(columns=3, basemap=empty_basemap()))
    assert panel.effective_config.layout.rows == 5
    assert panel.effective_config.layout.columns == 3
    assert tuple(panel.charts.values()) == tuple(charts)
    assert panel.validate(complete=True) == ()
    second_figure = panel.render()
    assert second_figure is not first_figure
    assert len(second_figure.axes) == 15
    panel.close()


def test_direct_layout_and_panel_preset_have_the_same_effective_collection_config():
    chart_template = ens_cn_chart(basemap=empty_basemap())
    panel_template = ens_cn(basemap=empty_basemap())
    direct = Panel(
        layout=ens_cn_layout(),
        theme=panel_template.theme,
        chart_defaults=chart_template,
        decorations=panel_template.decorations,
    )
    preset = Panel(template=panel_template)
    add_members(direct)
    add_members(preset)

    assert direct.effective_config.layout == preset.effective_config.layout
    assert direct.effective_config.theme == preset.effective_config.theme
    assert direct.effective_config.charts == preset.effective_config.charts
    assert direct.effective_config.decorations == preset.effective_config.decorations
    direct.close()
    preset.close()


def test_max_is_optional_caller_owned_and_never_created_by_the_template():
    panel = Panel(template=ens_cn(basemap=empty_basemap()))
    charts = add_members(panel)
    assert len(panel.charts) == 15
    assert "max" not in panel.charts
    assert tuple(panel.charts.values()) == tuple(charts)

    max_chart = panel.add_chart(id="max", role="max")
    assert panel.charts["max"] is max_chart
    assert len(panel.charts) == 16
    assert panel.effective_config.layout.rows == 4
    panel.close()

    required = Panel(template=ens_cn(require_max=True, basemap=empty_basemap()))
    add_members(required)
    assert any(issue.code == "missing_target" for issue in required.effective_config.pending)
    with pytest.raises(ConfigError, match="required layout order selector"):
        required.validate(complete=True)
    required.close()


def test_fixed_control_and_max_positions_and_empty_slots_are_ordinary_layout_values():
    layout = ens_cn_layout(
        columns=5,
        control_id="control-from-data",
        max_id="max-from-data",
        control_position=Cell(row=1, column=0),
        max_position=Cell(row=1, column=1),
        empty_slots={"reserved": Cell(row=0, column=4)},
    )

    assert layout.placements["control-from-data"] == Cell(row=1, column=0)
    assert layout.placements["max-from-data"] == Cell(row=1, column=1)
    assert layout.slots["reserved"].position == Cell(row=0, column=4)
    assert layout.slots["reserved"].kind is UNSET
    assert tuple(selector.id for selector in layout.order[:2]) == (
        "control-from-data",
        "max-from-data",
    )

    with pytest.raises(ConfigError, match="same Chart"):
        ens_cn_layout(control_id="same", max_id="same")
    with pytest.raises(ConfigError, match="requires control_id"):
        ens_cn_layout(control_position=Cell(row=0, column=0))

    panel = Panel(template=ens_cn(empty_slots={"reserved": Cell(row=0, column=4)}))
    panel.add_chart(id="ctl", role="control")
    assert panel.effective_config.layout.slots["reserved"].kind == "empty"
    panel.close()


def test_shared_colorbar_position_can_use_a_colorbar_slot_without_creating_one():
    template = ens_cn(
        colorbar_slot=("shared", Cell(row=3, column=0, colspan=5)),
        colorbar_position=Rect(
            space="slot",
            slot="shared",
            bounds=(.1, .25, .8, .5),
        ),
        basemap=empty_basemap(),
    )
    panel = Panel(template=template)
    add_members(panel)

    assert len(panel.charts) == 15
    assert "ens_cn_colorbar" in panel.effective_config.decorations.colorbars
    colorbar = panel.effective_config.decorations.colorbars["ens_cn_colorbar"]
    assert colorbar.position.space == "slot"
    assert colorbar.position.slot == "shared"
    assert panel.effective_config.layout.slots["shared"].kind == "colorbar"
    assert panel.effective_config.layout.rows == 4
    panel.close()


def test_ens_cn_defaults_preserve_legacy_region_and_feature_order():
    panel = Panel(template=ens_cn())
    panel.add_chart(id="ctl", role="control")
    subplot = panel.effective_config.charts["ctl"].subplots["main"]

    assert subplot.domain.extent == (73.0, 135.0, 16.0, 56.0)
    assert subplot.domain.extent_crs == ccrs.PlateCarree()
    assert subplot.basemap.map_type is MapType.Portrait
    assert subplot.basemap.map_info is None
    assert tuple(feature.name for feature in subplot.basemap.features) == (
        "coastline",
        "china_coastline",
        "china_borders",
        "china_provinces",
        "china_rivers",
        "china_nine_lines",
    )
    panel.close()
