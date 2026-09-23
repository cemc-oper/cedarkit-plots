from copy import deepcopy

import pytest

from cedarkit.plots.workflow.recipe import RecipeLoadError, load_recipe


BASE = {
    "api_version": "cedarkit.plots/v3",
    "kind": "PlotRecipe",
    "metadata": {"name": "temperature"},
    "spec": {
        "data": {"temperature": {"field": {"parameter": "t2m"}, "units": "degC"}},
        "content": {
            "charts": [{"id": "main", "plots": [{"id": "temperature", "method": "contourf", "field": "temperature", "style": "cemc.t2m:default", "targets": "all"}],
                        "titles": [{"id": "title", "text": "Temperature"}]}],
            "colorbars": [{"id": "temperature", "plots": [{"chart": "main", "plot": "temperature"}]}],
        },
        "display": {"template": "east_asia", "layout": {"columns": 1}, "charts": {"main": {"subplots": {"south_china_sea": {"enabled": False}}}}},
    },
}


def test_load_v3_content_and_display_without_runtime_imports():
    loaded = load_recipe(BASE)
    assert loaded.origin == "<memory>"
    assert loaded.recipe.spec.content.charts[0].plots[0].targets == "all"
    assert loaded.recipe.spec.display.charts["main"]["subplots"]["south_china_sea"]["enabled"] is False


@pytest.mark.parametrize("change, message", [
    (lambda x: x["spec"]["content"]["charts"].append(deepcopy(x["spec"]["content"]["charts"][0])), "duplicate chart ID"),
    (lambda x: x["spec"]["content"]["charts"][0]["plots"].append(deepcopy(x["spec"]["content"]["charts"][0]["plots"][0])), "duplicate plot ID"),
    (lambda x: x["spec"]["content"]["charts"][0]["plots"][0].update(field="missing"), "missing data"),
    (lambda x: x["spec"]["content"]["colorbars"][0]["plots"][0].update(plot="missing"), "missing plot"),
    (lambda x: x["spec"]["display"]["charts"].update(other={}), "missing chart"),
    (lambda x: x["spec"]["content"]["charts"][0]["plots"][0].update(layer=[0]), "Extra inputs"),
    (lambda x: x["spec"]["content"]["charts"][0]["plots"][0].update(method="quiver"), "method"),
    (lambda x: x["spec"]["content"]["charts"][0]["plots"][0].update(targets=["main", "main"]), "fixed targets"),
])
def test_rejects_invalid_references_and_legacy_fields(change, message):
    data = deepcopy(BASE)
    change(data)
    with pytest.raises(RecipeLoadError, match=message):
        load_recipe(data)


def test_rejects_duplicate_yaml_keys_and_prior_versions():
    with pytest.raises(RecipeLoadError, match="duplicate YAML key 'id'"):
        load_recipe("""api_version: cedarkit.plots/v3
kind: PlotRecipe
metadata: {name: temperature}
spec:
  data: {temperature: {field: {parameter: t2m}}}
  content:
    charts:
      - id: main
        id: other
""")
    data = deepcopy(BASE)
    data["api_version"] = "cedarkit.plots/v2"
    with pytest.raises(RecipeLoadError, match="unsupported api_version"):
        load_recipe(data)


def test_multi_output_binding_and_transform_repeat_are_explicit():
    data = deepcopy(BASE)
    data["spec"]["params"] = {"interval": {"type": "timedelta", "default": "24h"}}
    data["spec"]["data"]["diagnostic"] = {
        "compute": {"op": "diagnostic", "inputs": ["temperature"], "outputs": ["low", "high"]},
        "transforms": [{"op": "smooth", "repeat": 2}],
    }
    data["spec"]["content"]["charts"][0]["plots"][0]["field"] = "high"
    recipe = load_recipe(data).recipe
    assert recipe.spec.data["diagnostic"].compute.outputs == ("low", "high")
    assert recipe.spec.data["diagnostic"].transforms[0].repeat == 2

    data["spec"]["data"]["diagnostic"]["compute"]["outputs"] = ["high", "temperature"]
    with pytest.raises(RecipeLoadError, match="duplicate data/output ID"):
        load_recipe(data)
