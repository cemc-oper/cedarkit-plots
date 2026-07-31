"""Unit tests for the op registry and built-in ops (cedarkit.plots.engine.ops)."""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from cedarkit.plots.engine.ops import OpContext, OpRegistry
from cedarkit.plots.engine.recipe import Recipe, RecipeError
from cedarkit.plots.style import StyleRegistry


@pytest.fixture
def field() -> xr.DataArray:
    values = np.arange(12, dtype=float).reshape(3, 4)
    return xr.DataArray(
        values,
        dims=("latitude", "longitude"),
        coords={"latitude": [30.0, 40.0, 50.0], "longitude": [100.0, 110.0, 120.0, 130.0]},
    )


def make_context(**overrides) -> OpContext:
    context = OpContext(
        recipe=None,
        data_key="t2m",
        metadata=None,
        style_registry=None,
        loader=None,
    )
    for key, value in overrides.items():
        setattr(context, key, value)
    return context


class TestRegistry:
    def test_builtins_registered(self):
        registry = OpRegistry.builtins()
        for name in ("style_units", "unit_scale", "unit_offset", "smth9", "time_diff"):
            assert registry.has(name)
            assert registry.kind(name) == "transform"

    def test_unknown_op_raises(self):
        registry = OpRegistry.builtins()
        with pytest.raises(KeyError, match="unknown op"):
            registry.get("not_an_op")
        with pytest.raises(KeyError, match="unknown op"):
            registry.kind("not_an_op")

    def test_register_custom_op(self, field):
        registry = OpRegistry.builtins()
        registry.register("double", lambda f, context: f * 2)
        result = registry.apply_transform("double", field, [], {}, 1, make_context())
        np.testing.assert_allclose(result.values, field.values * 2)

    def test_register_compute_op(self, field):
        registry = OpRegistry.builtins()
        registry.register("add_fields", lambda a, b, context: a + b, kind="compute")
        result = registry.apply_compute("add_fields", [field, field], [], {}, make_context())
        np.testing.assert_allclose(result.values, field.values * 2)

    def test_invalid_kind_rejected(self):
        registry = OpRegistry.builtins()
        with pytest.raises(ValueError, match="kind"):
            registry.register("x", lambda f, context: f, kind="bogus")

    def test_compute_op_in_transform_position_rejected(self, field):
        registry = OpRegistry.builtins()
        registry.register("add_fields", lambda a, b, context: a + b, kind="compute")
        with pytest.raises(RecipeError, match="cannot be used in transforms"):
            registry.apply_transform("add_fields", field, [], {}, 1, make_context())

    def test_repeat(self, field):
        registry = OpRegistry.builtins()
        calls = []

        def counting_op(f, context):
            calls.append(1)
            return f + 1

        registry.register("counting", counting_op)
        result = registry.apply_transform("counting", field, [], {}, 3, make_context())
        assert len(calls) == 3
        np.testing.assert_allclose(result.values, field.values + 3)


class TestBuiltinOps:
    def test_unit_scale(self, field):
        registry = OpRegistry.builtins()
        result = registry.apply_transform("unit_scale", field, [0.1], {}, 1, make_context())
        np.testing.assert_allclose(result.values, field.values * 0.1)

    def test_unit_offset(self, field):
        registry = OpRegistry.builtins()
        result = registry.apply_transform("unit_offset", field, [-273.15], {}, 1, make_context())
        np.testing.assert_allclose(result.values, field.values - 273.15)

    def test_smth9_changes_values(self, field):
        registry = OpRegistry.builtins()
        # a linear ramp is invariant under smth9; add a spike to see the effect
        spiked = field.copy()
        spiked.values[1, 2] = 100.0
        result = registry.apply_transform("smth9", spiked, [0.5, 0.25, False], {}, 1, make_context())
        assert result.shape == spiked.shape
        assert not np.allclose(result.values, spiked.values)

    def test_time_diff(self, field):
        registry = OpRegistry.builtins()
        previous = field - 3
        loader_calls = []

        def loader(data_key, forecast_time):
            loader_calls.append((data_key, forecast_time))
            return previous

        context = make_context(loader=loader)
        context.metadata = type("M", (), {"forecast_time": pd.Timedelta(hours=24)})()
        result = registry.apply_transform(
            "time_diff", field, [pd.Timedelta(hours=24)], {}, 1, context,
        )
        np.testing.assert_allclose(result.values, field.values - previous.values)
        assert loader_calls == [("t2m", pd.Timedelta(hours=0))]

    def test_time_diff_accepts_string_interval(self, field):
        registry = OpRegistry.builtins()
        context = make_context(loader=lambda key, fct: field - 1)
        context.metadata = type("M", (), {"forecast_time": pd.Timedelta(hours=24)})()
        result = registry.apply_transform("time_diff", field, ["24h"], {}, 1, context)
        np.testing.assert_allclose(result.values, np.ones_like(field.values))

    def test_style_units(self, field, tmp_path):
        style_dir = tmp_path / "styles"
        style_dir.mkdir()
        (style_dir / "t2m.yml").write_text("""
id: t2m
criteria:
  - cemc_name: t2m
styles:
  cn:
    type: contour
    levels: [0, 10]
    colormap: viridis
    units: celsius
""", encoding="utf-8")
        style_registry = StyleRegistry([style_dir])
        recipe = Recipe.model_validate({
            "name": "x",
            "domain": {"default": "east_asia", "area": "cn_area"},
            "data": {"t2m": {"field": "t2m"}},
            "layers": [{"field": "t2m", "style": "t2m:cn"}],
            "title": {"graph_name": "x"},
        })
        context = make_context(recipe=recipe, style_registry=style_registry)
        kelvin = field + 273.15
        result = OpRegistry.builtins().apply_transform("style_units", kelvin, [], {}, 1, context)
        np.testing.assert_allclose(result.values, field.values)

    def test_style_units_without_layer_is_noop(self, field):
        recipe = Recipe.model_validate({
            "name": "x",
            "domain": {"default": "east_asia", "area": "cn_area"},
            "data": {"t2m": {"field": "t2m"}},
            "layers": [{"field": "t2m", "style": "t2m:cn"}],
            "title": {"graph_name": "x"},
        })
        context = make_context(recipe=recipe, data_key="other", style_registry=None)
        result = OpRegistry.builtins().apply_transform("style_units", field, [], {}, 1, context)
        np.testing.assert_allclose(result.values, field.values)
