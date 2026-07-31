"""Unit tests for the recipe YAML schema (cedarkit.plots.engine.recipe)."""
import pytest

from cedarkit.plots.engine.recipe import (
    ColorbarSpec,
    ComputeSpec,
    DataFieldSpec,
    LayerSpec,
    ParamSpec,
    Recipe,
    RecipeError,
    StyleSelectSpec,
    TransformSpec,
    load_recipe_file,
)


def write_recipe(tmp_path, name: str, text: str):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


VALID_RECIPE = """
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


class TestTransformSpec:
    def test_defaults(self):
        spec = TransformSpec(op="smth9", args=[0.5, 0.25, False])
        assert spec.repeat == 1
        assert spec.kwargs == {}

    def test_repeat_must_be_positive(self):
        with pytest.raises(ValueError):
            TransformSpec(op="smth9", repeat=0)


class TestDataFieldSpec:
    def test_field_form(self):
        spec = DataFieldSpec(field="h", level={"first_level_type": 100, "first_level": 500})
        assert spec.level.first_level_type == 100

    def test_level_template_value(self):
        spec = DataFieldSpec(field="u", level={"first_level_type": 100, "first_level": "{wind_level}"})
        assert spec.level.first_level == "{wind_level}"

    def test_compute_form(self):
        spec = DataFieldSpec(compute={"op": "wind_speed", "inputs": ["u", "v"]})
        assert spec.compute.inputs == ["u", "v"]

    def test_field_and_compute_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            DataFieldSpec(field="u", compute={"op": "x", "inputs": ["u"]})

    def test_neither_field_nor_compute_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            DataFieldSpec()

    def test_level_without_field_rejected(self):
        with pytest.raises(ValueError, match="only valid together with 'field'"):
            DataFieldSpec(
                level={"first_level_type": 100, "first_level": 500},
                compute={"op": "x", "inputs": ["u"]},
            )


class TestComputeSpec:
    def test_empty_inputs_rejected(self):
        with pytest.raises(ValueError, match="at least one input"):
            ComputeSpec(op="wind_speed", inputs=[])


class TestStyleSelectSpec:
    def test_else_required(self):
        with pytest.raises(ValueError, match="else"):
            StyleSelectSpec(by="start_time.month", cases={"5,6,7,8,9": "t2m:cn_summer"})

    def test_valid(self):
        spec = StyleSelectSpec(by="start_time.month", cases={"else": "t2m:cn_winter"})
        assert spec.cases["else"] == "t2m:cn_winter"


class TestLayerSpec:
    def test_scalar_field(self):
        layer = LayerSpec(field="t2m", style="t2m:cn_summer")
        assert layer.field == "t2m"

    def test_vector(self):
        layer = LayerSpec(vector={"u": "u10", "v": "v10"}, style="wind", layer=[0])
        assert layer.vector.u == "u10"
        assert layer.layer == [0]

    def test_field_and_vector_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            LayerSpec(field="t2m", vector={"u": "u", "v": "v"}, style="t2m")

    def test_select_style_form(self):
        layer = LayerSpec(
            field="t2m",
            style={"select": {"by": "start_time.month", "cases": {"else": "t2m:cn_winter"}}},
        )
        assert layer.style.select.by == "start_time.month"


class TestColorbarSpec:
    def test_single_layer(self):
        spec = ColorbarSpec(layer=0)
        assert spec.layers == [0]

    def test_layer_list(self):
        spec = ColorbarSpec(layer=[0, 2, 1])
        assert spec.layers == [0, 2, 1]

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            ColorbarSpec(layer=-1)


class TestParamSpec:
    def test_required_with_default_rejected(self):
        with pytest.raises(ValueError, match="required"):
            ParamSpec(type="float", required=True, default=850.0)


class TestRecipe:
    def test_valid_recipe(self, tmp_path):
        recipe = load_recipe_file(write_recipe(tmp_path, "t2m.yaml", VALID_RECIPE))
        assert recipe.name == "2m Temperature (C)"
        assert recipe.domain.default == "east_asia"
        assert recipe.data["t2m"].transforms[0].op == "style_units"
        assert recipe.colorbar.layers == [0]

    def test_unknown_compute_input_rejected(self, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  ws:
    compute: { op: wind_speed, inputs: [u_missing, v_missing] }
layers:
  - field: ws
    style: ws
title: { graph_name: x }
""")
        with pytest.raises(RecipeError, match="unknown input"):
            load_recipe_file(path)

    def test_compute_output_duplicate_rejected(self, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  u: { field: u }
  ws:
    compute: { op: wind_speed, inputs: [u], outputs: [u] }
layers:
  - field: ws
    style: ws
title: { graph_name: x }
""")
        with pytest.raises(RecipeError, match="duplicates"):
            load_recipe_file(path)

    def test_layer_unknown_data_ref_rejected(self, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  t2m: { field: t2m }
layers:
  - field: missing
    style: t2m
title: { graph_name: x }
""")
        with pytest.raises(RecipeError, match="unknown data entry"):
            load_recipe_file(path)

    def test_colorbar_layer_out_of_range(self, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  t2m: { field: t2m }
layers:
  - field: t2m
    style: t2m
title: { graph_name: x }
colorbar: { layer: 1 }
""")
        with pytest.raises(RecipeError, match="out of range"):
            load_recipe_file(path)

    def test_empty_sections_rejected(self, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data: {}
layers: []
title: { graph_name: x }
""")
        with pytest.raises(RecipeError):
            load_recipe_file(path)

    def test_invalid_yaml_reports_file_and_line(self, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", "name: x\ndata: [unclosed\n")
        with pytest.raises(RecipeError) as exc_info:
            load_recipe_file(path)
        message = str(exc_info.value)
        assert "bad.yaml" in message
        assert "line" in message

    def test_schema_error_reports_file(self, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", """
name: x
domain: { default: east_asia, area: cn_area }
data:
  t2m: { field: t2m, transforms: [{ op: style_units, bogus: 1 }] }
layers:
  - field: t2m
    style: t2m
title: { graph_name: x }
""")
        with pytest.raises(RecipeError) as exc_info:
            load_recipe_file(path)
        message = str(exc_info.value)
        assert "bad.yaml" in message
        assert "validation failed" in message

    def test_non_mapping_rejected(self, tmp_path):
        path = write_recipe(tmp_path, "bad.yaml", "- just\n- a\n- list\n")
        with pytest.raises(RecipeError, match="mapping"):
            load_recipe_file(path)
