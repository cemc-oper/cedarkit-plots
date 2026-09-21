"""D03 configuration values, parsing and static validation."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest
import cartopy.crs as ccrs

from cedarkit.plots.config import (
    RESET,
    UNSET,
    BasemapSpec,
    Cell,
    ChartRule,
    ChartSelector,
    ChartSpec,
    LayoutSpec,
    Rect,
    SubplotSpec,
    Theme,
    merge_config,
    resolve_basemap,
    resolve_config,
)
from cedarkit.plots.domains import Domain
from cedarkit.plots.errors import ConfigError


def test_raw_values_keep_unset_and_resolved_values_have_defaults():
    raw = LayoutSpec(columns=3)
    assert raw.rows is UNSET
    assert raw.columns == 3

    resolved = resolve_config(layout=raw)
    assert resolved.layout.rows == 1
    assert resolved.layout.columns == 3
    assert resolved.theme.title_fontsize == 12
    assert plt.get_fignums() == []


def test_containers_are_snapshots_and_mapping_is_read_only():
    placements = {"a": Cell(row=0, column=0)}
    layout = LayoutSpec(placements=placements)
    placements.clear()
    assert tuple(layout.placements) == ("a",)
    with pytest.raises(TypeError):
        layout.placements["b"] = Cell(row=0, column=1)


def test_merge_supports_reset_and_named_mapping_without_mutation():
    base = ChartSpec(subplots={"south": SubplotSpec(enabled=True)})
    patch = ChartSpec(subplots={"south": SubplotSpec(enabled=False)})
    changed = merge_config(base, patch)
    assert changed.subplots["south"].enabled is False
    assert base.subplots["south"].enabled is True

    reset = merge_config(changed, ChartSpec(subplots={"south": RESET}))
    assert "south" not in reset.subplots

    theme = merge_config(Theme(title_fontsize=15), Theme(title_fontsize=RESET))
    assert theme.title_fontsize is UNSET


def test_layout_conflict_is_reported_without_a_partial_result():
    with pytest.raises(ConfigError) as caught:
        resolve_config(
            layout=LayoutSpec(
                rows=1,
                columns=2,
                placements={
                    "a": Cell(row=0, column=0, colspan=2),
                    "b": Cell(row=0, column=1),
                },
            ),
            charts={"a": {}, "b": {}},
        )
    assert any(issue.code == "layout_overlap" for issue in caught.value.issues)


def test_pending_capacity_and_complete_validation():
    pending = resolve_config(
        layout=LayoutSpec(rows=1, columns=1), charts={"a": {}, "b": {}}
    )
    assert any(issue.code == "capacity" for issue in pending.pending)
    with pytest.raises(ConfigError) as caught:
        resolve_config(
            layout=LayoutSpec(rows=1, columns=1),
            charts={"a": {}, "b": {}},
            complete=True,
        )
    assert any(issue.code == "capacity" for issue in caught.value.issues)


def test_domain_and_map_configuration_are_values_only():
    crs = ccrs.PlateCarree()
    domain = Domain(extent=(70, 140, 15, 55), extent_crs=crs)
    result = resolve_config(
        charts={"weather": {"role": "member"}},
        chart_defaults=ChartSpec(
            subplots={"main": SubplotSpec(kind="map", domain=domain)}
        ),
    )
    main = result.charts["weather"].subplots["main"]
    assert main.domain.extent == (70.0, 140.0, 15.0, 55.0)
    assert isinstance(main.map_crs, ccrs.CRS)
    assert plt.get_fignums() == []


def test_map_loader_is_snapshotted_without_importing_the_loader_package(monkeypatch):
    import cedarkit.plots.map as map_module

    monkeypatch.setattr(map_module, "DEFAULT_MAP_LOADER_PACKAGE", "example.loader")
    resolved = resolve_basemap(BasemapSpec())
    assert resolved.loader == "example.loader"


def test_rule_conflict_and_fixed_target_diagnostics():
    rule_a = ChartRule(
        selector=ChartSelector(role="member"), spec=ChartSpec()
    )
    rule_b = ChartRule(
        selector=ChartSelector(id="m1"), spec=ChartSpec()
    )
    with pytest.raises(ConfigError) as caught:
        resolve_config(
            charts={"m1": {"role": "member"}},
            chart_rules=(rule_a, rule_b),
        )
    assert caught.value.code == "rule_conflict"


def test_absolute_layout_requires_figure_rects():
    result = resolve_config(
        layout=LayoutSpec(
            mode="absolute",
            placements={"a": Rect(space="figure", bounds=(0, 0, .5, .5))},
        ),
        charts={"a": {}},
    )
    assert result.pending == ()
