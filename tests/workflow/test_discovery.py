from copy import deepcopy

import pytest
import yaml

from cedarkit.plots.domains.registry import DomainDescriptor, DomainRegistry
from cedarkit.plots.ops import OpDescriptor
from cedarkit.plots.registry import DuplicateRegistrationError
from cedarkit.plots.plugins import PluginDiscoveryError
from cedarkit.plots.templates import PanelTemplate
from cedarkit.plots.workflow.discovery import discover_workflow
from cedarkit.plots.workflow.plan import CompileContext, RecipeCompileError, compile_recipe
from cedarkit.plots.workflow.recipe import load_recipe


class EntryPoint:
    def __init__(self, name, value, provider, distribution="sample"):
        self.name, self.value, self.provider = name, value, provider
        self.dist = type("Distribution", (), {"metadata": {"Name": distribution}, "version": "1.0"})()

    def load(self):
        return self.provider


def test_discovery_sorts_plugins_records_sources_and_uses_new_presets(tmp_path):
    recipe = {"api_version": "cedarkit.plots/v3", "kind": "PlotRecipe",
              "metadata": {"name": "example"}, "spec": {"data": {"result": {"field": {"parameter": "cedarkit.t2m"}}},
              "content": {"charts": [{"id": "main", "plots": [{"id": "plot", "method": "contourf",
              "field": "result", "style": "cemc.t2m:cn_summer"}]}]}}}
    root = tmp_path / "recipes"
    root.mkdir()
    (root / "example.yaml").write_text(yaml.safe_dump(recipe), encoding="utf-8")
    ops = [EntryPoint("z", "b:ops", lambda: (OpDescriptor("extra_z", "compute", 1, 1, lambda x: x),), "z-dist"),
           EntryPoint("a", "a:ops", lambda: (OpDescriptor("extra_a", "compute", 1, 1, lambda x: x),), "a-dist")]
    points = {"cedarkit.plots.ops": ops,
              "cedarkit.plots.recipes": [EntryPoint("recipes", "recipes:root", lambda: root)]}
    found = discover_workflow(entry_points=points)
    reverse = discover_workflow(entry_points={**points, "cedarkit.plots.ops": list(reversed(ops))})
    assert found.ops.manifest() == reverse.ops.manifest()
    assert found.ops.provenance("extra_a").distribution == "a-dist"
    assert found.ops.provenance("extra_a").entry_point == "a"
    assert found.recipes.names == ("example",)
    assert found.recipes.get("example").provenance.entry_point == "recipes"
    assert found.recipes.load("example").recipe.metadata.name == "example"
    for name in ("xy", "east_asia", "cn_area"):
        assert isinstance(found.domains.create(name), PanelTemplate)
        assert found.domains.provenance(name).source == "builtin"


def test_duplicate_ids_report_both_sources(tmp_path):
    descriptor = lambda: (OpDescriptor("wind_speed", "compute", 2, 1, lambda u, v: u),)
    first = EntryPoint("wind_a", "a:ops", descriptor, "a-dist")
    second = EntryPoint("wind_b", "b:ops", descriptor, "b-dist")
    with pytest.raises(DuplicateRegistrationError, match="wind_speed") as caught:
        discover_workflow(entry_points={"cedarkit.plots.ops": [second, first]})
    assert "a-dist" in str(caught.value) and "b-dist" in str(caught.value)

    root_a, root_b = tmp_path / "a", tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "same.yaml").write_text("api_version: cedarkit.plots/v3", encoding="utf-8")
    (root_b / "same.yml").write_text("api_version: cedarkit.plots/v3", encoding="utf-8")
    with pytest.raises(DuplicateRegistrationError, match="duplicate recipe 'same'") as caught:
        discover_workflow(entry_points={"cedarkit.plots.recipes": [
            EntryPoint("a", "a:recipes", lambda: root_a, "a-dist"),
            EntryPoint("b", "b:recipes", lambda: root_b, "b-dist")]})
    assert "a-dist" in str(caught.value) and "b-dist" in str(caught.value)

    domains = DomainRegistry.builtins()
    with pytest.raises(DuplicateRegistrationError, match="east_asia"):
        domains.register_descriptor(DomainDescriptor("east_asia", lambda _: None))


def test_provider_failure_retains_source_and_strict_mode():
    def broken():
        raise RuntimeError("provider failed")

    points = {"cedarkit.plots.ops": [EntryPoint("broken", "broken:ops", broken, "broken-dist")]}
    with pytest.raises(PluginDiscoveryError, match="broken-dist"):
        discover_workflow(entry_points=points)
    found = discover_workflow(entry_points=points, strict=False)
    assert found.failures[0].distribution == "broken-dist"
    assert "provider failed" in found.failures[0].cause


def test_metadata_placeholders_use_one_formatter_for_args_and_titles():
    raw = {"api_version": "cedarkit.plots/v3", "kind": "PlotRecipe", "metadata": {"name": "example"},
           "spec": {"params": {"level": {"type": "int", "default": 2}},
                    "data": {"result": {"field": {"parameter": "cedarkit.t2m",
                                                   "level": {"level": "{params.level}"}}}},
                    "content": {"charts": [{"id": "main", "plots": [{"id": "plot", "method": "contourf",
                               "field": "result", "style": "cemc.t2m:cn_summer"}],
                               "titles": [{"id": "title", "text": "{metadata.name} {context.forecast_time}"}]}],
                               "titles": [{"id": "heading", "text": "Level {params.level}"}]}}}
    plan = compile_recipe(load_recipe(raw), CompileContext(forecast_time="2026-01-01T00:00Z"))
    assert plan.content.charts[0].titles[0].text == "example 2026-01-01T00:00:00Z"
    assert plan.content.titles[0].text == "Level 2"
    assert next(node.request for node in plan.nodes if node.request).query.level == 2

    broken = deepcopy(raw)
    broken["spec"]["content"]["titles"][0]["text"] = "{metadata.missing}"
    with pytest.raises(RecipeCompileError, match="unknown placeholder metadata.missing") as caught:
        compile_recipe(load_recipe(broken))
    assert caught.value.code == "template"
