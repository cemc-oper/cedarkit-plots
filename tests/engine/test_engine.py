"""Tests for PlotEngine + PlotModuleAdapter (cedarkit.plots.engine.engine)."""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from cedarkit.plots.engine import (
    DomainRegistry,
    OpRegistry,
    PlotEngine,
    RecipeError,
    find_recipe_file,
    get_plot_definition,
    layer_style_target,
    resolve_templates,
)
from cedarkit.plots.style import StyleRegistry
from cedarkit.plots.testing import synthetic_data
from cedarkit.plots.types import AreaRange


@dataclass
class FakeFieldInfo:
    """Stand-in for cedar_graph FieldInfo (engine is business-agnostic)."""
    name: str
    level_type: Optional[str] = None
    level: Optional[float] = None


class FakeDataLoader:
    """Returns deterministic synthetic fields; records load calls."""

    def __init__(self):
        self.calls = []

    def load(self, field_info, start_time, forecast_time):
        self.calls.append((field_info.name, field_info.level_type, field_info.level, forecast_time))
        if field_info.name == "t2m":
            field = synthetic_data.east_asia_temperature_field()
        else:
            field = synthetic_data.east_asia_pressure_field()
        return field


@pytest.fixture(scope="module")
def style_registry(tmp_path_factory) -> StyleRegistry:
    style_dir = tmp_path_factory.mktemp("styles")
    (style_dir / "t2m.yml").write_text("""
id: t2m
criteria:
  - cemc_name: t2m
optimal: cn_summer
styles:
  cn_summer:
    type: contour
    levels: [0, 10, 20]
    colormap: { colors: ["#fde725", "#21918c", "#440154", "#3b528b"] }
    fill: true
    units: celsius
  cn_winter:
    type: contour
    levels: [-20, -10, 0]
    colormap: { colors: ["#0d0887", "#7e03a8", "#cc4778", "#f89540"] }
    fill: true
    units: celsius
""", encoding="utf-8")
    (style_dir / "wind.yml").write_text("""
id: wind
criteria:
  - cemc_name: u
styles:
  cn:
    type: barb
    barbcolor: black
""", encoding="utf-8")
    return StyleRegistry([style_dir])


@pytest.fixture
def engine(style_registry) -> PlotEngine:
    op_registry = OpRegistry.builtins()
    op_registry.register(
        "wind_speed",
        lambda u, v, context: (u * u + v * v) ** 0.5,
        kind="compute",
    )
    return PlotEngine(
        style_registry=style_registry,
        op_registry=op_registry,
        field_registry={"t2m": FakeFieldInfo("t2m"), "u": FakeFieldInfo("u"), "v": FakeFieldInfo("v")},
    )


def write_recipe(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


T2M_RECIPE = """
name: "2m Temperature (C)"
domain: { default: east_asia, area: cn_area }

data:
  t2m:
    field: t2m
    transforms:
      - { op: style_units }

layers:
  - field: t2m
    style:
      select:
        by: start_time.month
        cases:
          "5,6,7,8,9": t2m:cn_summer
          else: t2m:cn_winter

title: { graph_name: "2m Temperature (C)" }
colorbar: { layer: 0 }
"""


class TestLoadRecipeChecks:
    def test_unknown_op_rejected(self, engine, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  t2m:
    field: t2m
    transforms: [{ op: not_an_op }]
layers:
  - { field: t2m, style: t2m }
title: { graph_name: x }
""")
        with pytest.raises(RecipeError, match="unknown op"):
            engine.load_recipe(path)

    def test_unknown_field_rejected(self, engine, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  xx: { field: not_a_field }
layers:
  - { field: xx, style: t2m }
title: { graph_name: x }
""")
        with pytest.raises(RecipeError, match="unknown field"):
            engine.load_recipe(path)

    def test_unknown_style_rejected(self, engine, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  t2m: { field: t2m }
layers:
  - { field: t2m, style: not_a_style }
title: { graph_name: x }
""")
        with pytest.raises(RecipeError, match="unknown style id"):
            engine.load_recipe(path)

    def test_unknown_style_variant_rejected(self, engine, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  t2m: { field: t2m }
layers:
  - { field: t2m, style: "t2m:not_a_variant" }
title: { graph_name: x }
""")
        with pytest.raises(RecipeError, match="variant"):
            engine.load_recipe(path)

    def test_select_style_refs_checked(self, engine, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  t2m: { field: t2m }
layers:
  - field: t2m
    style:
      select:
        by: start_time.month
        cases:
          "5": t2m:cn_summer
          else: bogus:cn
title: { graph_name: x }
""")
        with pytest.raises(RecipeError, match="unknown style id"):
            engine.load_recipe(path)

    def test_unknown_domain_rejected(self, engine, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: nowhere, area: cn_area }
data:
  t2m: { field: t2m }
layers:
  - { field: t2m, style: t2m }
title: { graph_name: x }
""")
        with pytest.raises(RecipeError, match="unknown domain"):
            engine.load_recipe(path)


class TestHelpers:
    def test_layer_style_target_string(self):
        assert layer_style_target("t2m:cn_summer", None) == ("t2m", "cn_summer")
        assert layer_style_target("t2m", None) == ("t2m", None)

    def test_layer_style_target_select_by_month(self, engine, tmp_path):
        recipe = engine.load_recipe(write_recipe(tmp_path, "t2m.yaml", T2M_RECIPE))
        module = engine.build_module(recipe)
        metadata = module.PlotMetadata(start_time=pd.Timestamp("2024-07-01"))
        assert layer_style_target(recipe.layers[0].style, metadata) == ("t2m", "cn_summer")
        metadata = module.PlotMetadata(start_time=pd.Timestamp("2024-01-01"))
        assert layer_style_target(recipe.layers[0].style, metadata) == ("t2m", "cn_winter")

    def test_select_timedelta_compares_as_hours(self):
        from cedarkit.plots.engine.engine import _resolve_selector_value
        metadata = type("M", (), {"interval": pd.Timedelta(hours=3)})()
        assert _resolve_selector_value("interval", metadata) == 3

    def test_resolve_templates_full_placeholder_keeps_type(self):
        metadata = type("M", (), {"interval": pd.Timedelta(hours=24), "wind_level": 850.0})()
        assert resolve_templates("{interval}", metadata) == pd.Timedelta(hours=24)
        assert resolve_templates("{wind_level}", metadata) == 850.0
        assert resolve_templates(["{wind_level}", 1], metadata) == [850.0, 1]

    def test_resolve_templates_unknown_param(self):
        metadata = type("M", (), {})()
        with pytest.raises(RecipeError, match="unknown param"):
            resolve_templates("{missing}", metadata)


class TestAdapter:
    def test_metadata_class_has_engine_and_param_fields(self, engine, tmp_path):
        path = write_recipe(tmp_path, "k.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
params:
  wind_level: { type: float, required: true }
data:
  t2m: { field: t2m }
layers:
  - { field: t2m, style: t2m }
title: { graph_name: x }
""")
        module = engine.build_module(engine.load_recipe(path))
        metadata = module.PlotMetadata()
        assert metadata.auto_extract_area is True
        assert metadata.sample_step == 0.09
        assert metadata.wind_level is None

    def test_load_data_signature_exposes_params(self, engine, tmp_path):
        import inspect
        path = write_recipe(tmp_path, "k.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
params:
  wind_level: { type: float, required: true }
  interval: { type: timedelta, default: 24h }
data:
  t2m: { field: t2m }
layers:
  - { field: t2m, style: t2m }
title: { graph_name: x }
""")
        module = engine.build_module(engine.load_recipe(path))
        params = list(inspect.signature(module.load_data).parameters)
        assert params == ["data_loader", "start_time", "forecast_time", "wind_level", "interval"]

    def test_required_param_missing_raises(self, engine, tmp_path):
        path = write_recipe(tmp_path, "k.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
params:
  wind_level: { type: float, required: true }
data:
  t2m: { field: t2m }
layers:
  - { field: t2m, style: t2m }
title: { graph_name: x }
""")
        module = engine.build_module(engine.load_recipe(path))
        with pytest.raises(RecipeError, match="required param"):
            module.load_data(
                data_loader=FakeDataLoader(),
                start_time=pd.Timestamp("2024-07-01"),
                forecast_time=pd.Timedelta(hours=24),
            )

    def test_load_data_applies_level_and_units(self, engine, tmp_path):
        path = write_recipe(tmp_path, "t.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
params:
  wind_level: { type: float, required: true }
data:
  t2m:
    field: t2m
    level: { first_level_type: 100, first_level: "{wind_level}" }
    transforms: [{ op: style_units }]
layers:
  - { field: t2m, style: t2m }
title: { graph_name: x }
""")
        module = engine.build_module(engine.load_recipe(path))
        loader = FakeDataLoader()
        raw = synthetic_data.east_asia_temperature_field()
        plot_data = module.load_data(
            data_loader=loader,
            start_time=pd.Timestamp("2024-07-01"),
            forecast_time=pd.Timedelta(hours=24),
            wind_level=500,
        )
        # level template resolved and coerced to float, type code -> "pl"
        assert loader.calls[0][1] == "pl"
        assert loader.calls[0][2] == 500.0
        # style_units: celsius transform (x - 273.15) applied
        np.testing.assert_allclose(plot_data.t2m.values, raw.values - 273.15)

    def test_compute_op_multi_inputs(self, engine, tmp_path):
        path = write_recipe(tmp_path, "ws.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  u: { field: u }
  v: { field: v }
  ws:
    compute: { op: wind_speed, inputs: [u, v] }
layers:
  - { field: ws, style: t2m }
title: { graph_name: x }
""")
        module = engine.build_module(engine.load_recipe(path))
        plot_data = module.load_data(
            data_loader=FakeDataLoader(),
            start_time=pd.Timestamp("2024-07-01"),
            forecast_time=pd.Timedelta(hours=24),
        )
        raw = synthetic_data.east_asia_pressure_field()
        np.testing.assert_allclose(plot_data.ws.values, (raw.values ** 2 + raw.values ** 2) ** 0.5)

    def test_time_diff_reloads_raw_field(self, engine, tmp_path):
        path = write_recipe(tmp_path, "rain.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
params:
  interval: { type: timedelta, default: 24h }
data:
  rain:
    field: t2m
    transforms: [{ op: time_diff, args: ["{interval}"] }]
layers:
  - { field: rain, style: t2m }
title: { graph_name: x }
""")
        module = engine.build_module(engine.load_recipe(path))
        loader = FakeDataLoader()
        module.load_data(
            data_loader=loader,
            start_time=pd.Timestamp("2024-07-01"),
            forecast_time=pd.Timedelta(hours=24),
        )
        forecast_times = [call[3] for call in loader.calls]
        assert forecast_times == [pd.Timedelta(hours=24), pd.Timedelta(hours=0)]

    def test_full_plot_pipeline(self, engine, tmp_path):
        """Recipe -> adapter -> load_data -> plot -> saved PNG."""
        import matplotlib
        matplotlib.use("Agg")
        module = engine.build_module(engine.load_recipe(write_recipe(tmp_path, "t2m.yaml", T2M_RECIPE)))
        loader = FakeDataLoader()
        start_time = pd.Timestamp("2024-07-01 00:00")
        plot_data = module.load_data(
            data_loader=loader,
            start_time=start_time,
            forecast_time=pd.Timedelta(hours=24),
        )
        metadata = module.PlotMetadata(
            start_time=start_time,
            forecast_time=pd.Timedelta(hours=24),
            system_name="CMA-GFS",
        )
        panel = module.plot(plot_data=plot_data, plot_metadata=metadata)
        output_path = tmp_path / "t2m.png"
        panel.save(output_path)
        assert output_path.exists()

    def test_graph_name_template_and_area_prefix(self, engine, tmp_path):
        path = write_recipe(tmp_path, "k.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
params:
  wind_level: { type: float, required: true }
data:
  t2m: { field: t2m }
layers:
  - { field: t2m, style: t2m }
title: { graph_name: "K index {wind_level}hPa", area_prefix: true }
""")
        module = engine.build_module(engine.load_recipe(path))
        metadata = module.PlotMetadata(wind_level=850.0, forecast_time=pd.Timedelta(hours=24))
        assert engine.build_graph_name(module.recipe, metadata) == "K index 850.0hPa"
        metadata.area_range = AreaRange(start_longitude=100, end_longitude=120, start_latitude=30, end_latitude=45)
        metadata.area_name = "CN"
        assert engine.build_graph_name(module.recipe, metadata) == "CN K index 850.0hPa"

    def test_graph_name_forecast_hours(self, engine, tmp_path):
        path = write_recipe(tmp_path, "r.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
params:
  interval: { type: timedelta, default: 24h }
data:
  t2m: { field: t2m }
layers:
  - { field: t2m, style: t2m }
title: { graph_name: "rain: {previous_forecast_hour:03d}-{forecast_hour:03d}h" }
""")
        module = engine.build_module(engine.load_recipe(path))
        metadata = module.PlotMetadata(forecast_time=pd.Timedelta(hours=48))
        assert engine.build_graph_name(module.recipe, metadata) == "rain: 024-048h"


class TestLoaderIntegration:
    def test_get_plot_definition_prefers_recipe(self, engine, tmp_path):
        recipe_dir = tmp_path / "recipes" / "cn"
        recipe_dir.mkdir(parents=True)
        (recipe_dir / "t2m.yaml").write_text(T2M_RECIPE, encoding="utf-8")
        (tmp_path / "recipes" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "recipes" / "cn" / "__init__.py").write_text("", encoding="utf-8")
        import sys
        sys.path.insert(0, str(tmp_path))
        try:
            recipe_file = find_recipe_file("cn.t2m", "recipes")
            assert recipe_file is not None
            definition = get_plot_definition(
                plot_type="cn.t2m",
                base_module_name="does.not.exist",
                recipe_base_module="recipes",
                engine=engine,
            )
            assert hasattr(definition, "PlotMetadata")
            assert hasattr(definition, "load_data")
            assert hasattr(definition, "plot")
        finally:
            sys.path.remove(str(tmp_path))
            sys.modules.pop("recipes", None)
            sys.modules.pop("recipes.cn", None)

    def test_get_plot_definition_falls_back_to_module(self, engine):
        definition = get_plot_definition(
            plot_type="testing",
            base_module_name="cedarkit.plots",
            recipe_base_module="cedarkit.plots",
            engine=engine,
        )
        import types
        assert isinstance(definition, types.ModuleType)

    def test_engine_required_for_recipe_lookup(self):
        with pytest.raises(ValueError, match="engine"):
            get_plot_definition("cn.t2m", "x", recipe_base_module="recipes")


@dataclass
class FakeTimeConfig:
    forecast_time: pd.Timedelta


@dataclass
class FakePlotConfig:
    plot_params: Optional[dict] = None


RAIN_RECIPE = """
name: x
domain: { default: east_asia, area: cn_area }
params:
  interval: { type: timedelta, required: true }
data:
  t2m:
    field: t2m
    transforms:
      - { op: time_diff, args: ["{interval}"] }
layers:
  - { field: t2m, style: t2m }
title: { graph_name: "rain" }
"""

RAIN_24H_RECIPE = """
name: x
domain: { default: east_asia, area: cn_area }
params:
  interval: { type: timedelta, default: 24h }
data:
  t2m:
    field: t2m
    transforms:
      - { op: time_diff, args: ["{interval}"] }
layers:
  - { field: t2m, style: t2m }
title: { graph_name: "rain" }
"""


class TestCheckAvailable:
    """Engine default check_available: forecast_time must cover time_diff intervals."""

    def test_no_time_diff_always_available(self, engine, tmp_path):
        module = engine.build_module(engine.load_recipe(write_recipe(tmp_path, "t2m.yaml", T2M_RECIPE)))
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=0))) is True
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=24))) is True

    def test_static_interval(self, engine, tmp_path):
        module = engine.build_module(engine.load_recipe(write_recipe(tmp_path, "r.yaml", RAIN_24H_RECIPE)))
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=0))) is False
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=12))) is False
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=24))) is True
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=48))) is True

    def test_param_interval_from_plot_params(self, engine, tmp_path):
        module = engine.build_module(engine.load_recipe(write_recipe(tmp_path, "r.yaml", RAIN_RECIPE)))
        plot_config = FakePlotConfig(plot_params={"interval": "3h"})
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=1)), plot_config) is False
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=3)), plot_config) is True
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=6)), plot_config) is True

    def test_param_interval_accepts_timedelta_value(self, engine, tmp_path):
        module = engine.build_module(engine.load_recipe(write_recipe(tmp_path, "r.yaml", RAIN_RECIPE)))
        plot_config = FakePlotConfig(plot_params={"interval": pd.Timedelta(hours=6)})
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=3)), plot_config) is False
        assert module.check_available(FakeTimeConfig(pd.Timedelta(hours=6)), plot_config) is True

    def test_missing_required_param_raises(self, engine, tmp_path):
        module = engine.build_module(engine.load_recipe(write_recipe(tmp_path, "r.yaml", RAIN_RECIPE)))
        with pytest.raises(RecipeError, match="interval"):
            module.check_available(FakeTimeConfig(pd.Timedelta(hours=24)), FakePlotConfig())

    def test_none_time_config_is_available(self, engine, tmp_path):
        module = engine.build_module(engine.load_recipe(write_recipe(tmp_path, "r.yaml", RAIN_24H_RECIPE)))
        assert module.check_available() is True
