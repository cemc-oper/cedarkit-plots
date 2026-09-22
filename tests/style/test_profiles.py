"""D12-02 profile precedence, semantic guards and metadata-only resolution."""
import numpy as np
import pytest
import xarray as xr
import yaml

from cedarkit.plots import Panel
from cedarkit.plots.style import (
    BarbStyle, ContourStyle, LevelStep, StyleMatchError, StyleRegistry, resolve_style,
)
from cedarkit.plots.style.schema import StyleFileError


def write(root, profile="cemc", name="t", *, criteria=None, units=None, duration=None,
          color="coolwarm", variants=None, optimal="default"):
    path = root / profile / f"{name}.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    config = {"type": "contour", "fill": True, "colormap": color,
              "levels": {"step": 4}, "expected_units": units, "accumulation_hours": duration}
    path.write_text(yaml.safe_dump({"id": name, "criteria": criteria or [{"cemc_name": "t"}],
                                    "optimal": optimal, "styles": variants or {"default": config}}))
    return path


def test_profiles_are_isolated_and_generic_requires_declaration(tmp_path):
    write(tmp_path, "generic")
    write(tmp_path, "report", color="viridis")
    default = StyleRegistry([tmp_path])
    assert default.profile == "cemc"
    assert default.match({"cemc_name": "t"}) is None
    assert isinstance(default.get_style("generic.t").levels, LevelStep)
    assert StyleRegistry([tmp_path], profile="report").get_style("t").colors.name == "viridis"
    fallback = StyleRegistry([tmp_path], generic_fallback=["t"])
    assert fallback.match({"cemc_name": "t"}) == "generic.t"
    assert fallback.explain({"cemc_name": "t"})["selected"] == "generic.t:default"
    with pytest.raises(KeyError, match="not found"):
        fallback.get_style("t")


def test_user_then_current_then_generic_and_explicit_parameters(tmp_path):
    base, user = tmp_path / "base", tmp_path / "user"
    write(base)
    write(base, "generic")
    write(user, color="viridis")
    reg = StyleRegistry([base], user_paths=[user], generic_fallback=["t"])
    result = reg.explain({"cemc_name": "t"})
    assert result["selected"] == "cemc.t:default"
    assert any(c["status"] == "shadowed" for c in result["candidates"])
    assert reg.get_style("t").colors.name == "viridis"
    assert reg.get_style("t", overrides={"colormap": "plasma"}).colors.name == "plasma"
    assert reg.get_style("t").colors.name == "viridis"
    explicit = ContourStyle(colors="red")
    assert resolve_style(explicit, None, registry=reg) is explicit
    with pytest.raises(ValueError, match="configure explicit"):
        resolve_style(explicit, None, registry=reg, overrides={"fill": True})


@pytest.mark.parametrize("reverse", [False, True])
def test_specificity_and_ties_are_independent_of_path_order(tmp_path, reverse):
    a, b = tmp_path / "a", tmp_path / "b"
    write(a, name="general")
    specific = [{"cemc_name": "t", "first_level_type": 103, "first_level": 2}]
    write(b, name="surface", criteria=specific)
    paths = [a, b][::-1 if reverse else 1]
    reg = StyleRegistry(paths)
    metadata = {"cemc_name": "t", "first_level_type": "heightAboveGround", "first_level": 2}
    assert reg.match(metadata) == "surface"
    write(a, name="also_surface", criteria=specific)
    reg = StyleRegistry(paths)
    assert reg.explain(metadata)["status"] == "conflict"
    with pytest.raises(StyleMatchError) as exc:
        reg.match(metadata)
    assert "surface" in str(exc.value) and "also_surface" in str(exc.value)
    assert str(a) in str(exc.value) and str(b) in str(exc.value)


def test_user_tier_beats_more_specific_base(tmp_path):
    base, user = tmp_path / "base", tmp_path / "user"
    write(base, name="specific", criteria=[{"cemc_name": "t", "first_level": 2}])
    write(user, name="user")
    assert StyleRegistry([base], user_paths=[user]).match({"cemc_name": "t", "first_level": 2}) == "user"


@pytest.mark.parametrize("user", [False, True])
def test_duplicate_ids_report_both_sources_and_load_is_atomic(tmp_path, user):
    a, b = tmp_path / "a", tmp_path / "b"
    first = write(a)
    second = write(b)
    write(b, name="a_new")
    reg = StyleRegistry()
    reg.load_path(a, user=user)
    with pytest.raises(StyleFileError) as exc:
        reg.load_path(b, user=user)
    assert str(first) in str(exc.value) and str(second) in str(exc.value)
    assert reg.style_ids == ["t"]


def test_user_replaces_whole_file_not_a_variant_merge(tmp_path):
    base, user = tmp_path / "base", tmp_path / "user"
    write(base, variants={"default": {"type": "barb"}, "winter": {"type": "barb"}})
    write(user)
    reg = StyleRegistry([base], user_paths=[user])
    with pytest.raises(KeyError, match="no variant"):
        reg.get_style("t:winter")
    with pytest.raises(ValueError, match="conflicting"):
        reg.get_style("t:default", "winter")


@pytest.mark.parametrize("metadata", [
    {"cemc_name": "rain"},
    {"cemc_name": "rain", "units": "mm"},
    {"cemc_name": "rain", "units": "m", "accumulation_hours": 24},
    {"cemc_name": "rain", "units": "mm", "accumulation_hours": 6},
])
def test_business_constraint_failure_never_falls_back(tmp_path, metadata):
    write(tmp_path, name="rain", criteria=[{"cemc_name": "rain"}], units="mm", duration=24)
    write(tmp_path, "generic", name="rain", criteria=[{"cemc_name": "rain"}])
    reg = StyleRegistry([tmp_path], generic_fallback=["rain"])
    assert reg.explain(metadata)["status"] == "blocked"
    with pytest.raises(StyleMatchError, match="rain"):
        reg.match(metadata)
    with pytest.raises(ValueError, match="expected"):
        reg.get_style("rain", metadata=metadata)


def test_accumulation_and_missing_level_metadata(tmp_path):
    write(tmp_path, name="rain", units="mm", duration=24)
    reg = StyleRegistry([tmp_path])
    metadata = {"cemc_name": "t", "units": "mm", "accumulation_hours": 24}
    style = reg.get_style("cemc.rain:default", metadata=metadata)
    assert style.expected_units == "mm" and style.accumulation_hours == 24
    assert reg.match(metadata) == "rain"
    with pytest.raises(ValueError, match="accumulation_hours"):
        reg.get_style("rain")
    write(tmp_path, name="surface", criteria=[{"eccodes_name": "t", "first_level_type": 103, "first_level": 2}])
    write(tmp_path, "generic", criteria=[{"eccodes_name": "t"}])
    reg = StyleRegistry([tmp_path], generic_fallback=["t"])
    with pytest.raises(StyleMatchError, match="missing metadata"):
        reg.match({"eccodes_name": "t"})


def test_or_entries_count_most_specific_match_not_number_of_aliases(tmp_path):
    write(tmp_path, name="aliases", criteria=[{"cemc_name": "t"}, {"eccodes_name": "t"}])
    write(tmp_path, name="level", criteria=[{"cemc_name": "t", "first_level": 2}])
    assert StyleRegistry([tmp_path]).match({"cemc_name": "t", "eccodes_name": "t", "first_level": 2}) == "level"


def test_default_env_profile_and_no_plugins_required(tmp_path, monkeypatch):
    from cedarkit.plots.style import registry as module
    monkeypatch.setattr(module.importlib.metadata, "entry_points", lambda **kwargs: [])
    monkeypatch.setenv("CEDARKIT_STYLE_PATH", str(tmp_path))
    write(tmp_path, "report")
    reg = StyleRegistry.default(profile="report")
    assert reg.match({"cemc_name": "t"}) == "t"
    assert reg.get_style("generic.t").levels == LevelStep(4, 0)
    assert StyleRegistry.default().profile == "cemc"


def test_resolution_does_not_read_values_or_create_figures(tmp_path, monkeypatch):
    import matplotlib.pyplot as plt
    write(tmp_path, units="degC")
    reg = StyleRegistry([tmp_path])
    field = xr.DataArray(np.ones((2, 2)), dims=("y", "x"), attrs={"cemc_name": "t", "units": "degC"})
    def forbidden(*args, **kwargs):
        raise AssertionError("field values / Figure accessed during style resolution")
    monkeypatch.setattr(xr.DataArray, "values", property(forbidden))
    monkeypatch.setattr(plt, "figure", forbidden)
    style = resolve_style("auto", field, registry=reg)
    assert style.levels == LevelStep(4, 0)
    assert style.expected_units == "degC"


def test_barb_expected_units_and_overrides_are_validated(tmp_path):
    write(tmp_path, variants={"default": {"type": "barb", "expected_units": "m/s"}})
    reg = StyleRegistry([tmp_path])
    assert isinstance(reg.get_style("t"), BarbStyle)
    assert reg.get_style("t").expected_units == "m/s"
    with pytest.raises(ValueError, match="got 'knots'"):
        reg.get_style("t", metadata={"units": "knots"})
    with pytest.raises(ValueError):
        reg.get_style("t", overrides={"unknown": 1})


def test_chart_strings_preserve_rule_snapshot_and_revalidate_duration(tmp_path, monkeypatch):
    from cedarkit.plots.style import registry as module
    write(tmp_path, units="mm", duration=24)
    monkeypatch.setattr(module, "_default_registry", StyleRegistry([tmp_path]))
    data = xr.DataArray(np.arange(9).reshape(3, 3), dims=("y", "x"), attrs={"units": "mm", "accumulation_hours": 24})
    panel = Panel()
    try:
        chart = panel.add_chart(id="test")
        layer = chart.contourf(data, style="cemc.t:default")
        assert layer.style.levels == LevelStep(4)
        panel.render()
        previous = layer.style
        with pytest.raises(ValueError, match="accumulation_hours"):
            layer.update(data=data.assign_attrs(accumulation_hours=6))
        assert layer.style.levels == previous.levels
        assert layer.style.accumulation_hours == previous.accumulation_hours
        assert layer.data is data
        assert not panel.dirty
        layer.update(style="cemc.t:default")
        with pytest.raises(ValueError, match="explicit style"):
            chart.contourf(data, style="auto")
    finally:
        panel.close()


def test_explicit_variant_does_not_depend_on_optimal_constraints(tmp_path):
    write(tmp_path, name="rain", optimal="day", variants={
        "day": {"type": "contour", "expected_units": "mm", "accumulation_hours": 24},
        "hour": {"type": "contour", "expected_units": "mm", "accumulation_hours": 1},
    })
    reg = StyleRegistry([tmp_path])
    field = xr.DataArray(np.zeros((2, 2)), dims=("y", "x"), attrs={"units": "mm", "accumulation_hours": 1})
    assert resolve_style("cemc.rain:hour", field, registry=reg).accumulation_hours == 1
    with pytest.raises(ValueError, match="accumulation_hours"):
        resolve_style("cemc.rain:day", field, registry=reg)
    with pytest.raises(ValueError, match="variant"):
        resolve_style("cemc.rain:", field, registry=reg)


def test_unknown_business_and_generic_whitelist_do_not_match(tmp_path):
    write(tmp_path, "generic", name="t")
    reg = StyleRegistry([tmp_path], generic_fallback=["other"])
    assert reg.match({"cemc_name": "t"}) is None
    assert reg.match({}) is None


def test_known_level_mismatch_can_use_declared_generic(tmp_path):
    write(tmp_path, name="surface", criteria=[{"cemc_name": "t", "first_level": 2}])
    write(tmp_path, "generic")
    reg = StyleRegistry([tmp_path], generic_fallback=["t"])
    assert reg.match({"cemc_name": "t", "first_level": 500}) == "generic.t"


def test_default_plugins_remain_cemc_when_generic_selected(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from cedarkit.plots.style import registry as module
    source = write(tmp_path, name="wind", variants={"default": {"type": "barb"}})
    ep = SimpleNamespace(name="cn", value="test.styles", load=lambda: SimpleNamespace(STYLE_PATHS=[source.parent]))
    monkeypatch.setattr(module.importlib.metadata, "entry_points", lambda **kwargs: [ep])
    monkeypatch.delenv("CEDARKIT_STYLE_PATH", raising=False)
    reg = StyleRegistry.default(profile="generic")
    assert reg.style_ids == ["t"]
    assert isinstance(reg.get_style("cemc.wind"), BarbStyle)


@pytest.mark.parametrize("duration", [0, -1, float("inf"), float("nan")])
def test_invalid_duration_rejected_at_load(tmp_path, duration):
    write(tmp_path, duration=duration)
    with pytest.raises(StyleFileError, match="accumulation_hours"):
        StyleRegistry([tmp_path])
