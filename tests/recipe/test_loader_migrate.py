from pathlib import Path

import pytest

from cedarkit.plots.recipe import RecipeLoadError, dump_recipe, load_recipe


V1 = """
name: Rain
domain: {default: east_asia, area: cn_area}
params: {interval: {type: timedelta, default: 24h}}
data: {rain: {field: cedarkit.rain, transforms: [{op: time_diff, args: ['{interval}']}]}}
layers: [{field: rain, style: rain:cn}]
title: {graph_name: Rain}
"""


def test_v1_normalizes_to_v2_and_is_idempotent():
    loaded = load_recipe(V1)
    assert loaded.source_version == 1
    assert loaded.recipe.spec.data["rain"].field.parameter == "cedarkit.rain"
    assert loaded.recipe.spec.data["rain"].transforms[0].args == ["{params.interval}"]
    assert load_recipe(dump_recipe(loaded.recipe)).recipe == loaded.recipe


def test_multiline_yaml_is_not_probed_as_a_path(monkeypatch):
    def unexpected_path_probe(self):
        raise AssertionError(f"YAML text must not be tested as a path: {self}")

    monkeypatch.setattr(Path, "exists", unexpected_path_probe)
    assert load_recipe(V1).source_version == 1


def test_partial_envelope_never_falls_back_to_v1():
    with pytest.raises(RecipeLoadError, match="partial v2 envelope"):
        load_recipe({"api_version": "cedarkit.plots/v2"})
