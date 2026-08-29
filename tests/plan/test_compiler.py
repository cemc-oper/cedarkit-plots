from __future__ import annotations

import pytest

from cedarkit.plots.ops import OpDescriptor, OpRegistry
from cedarkit.plots.plan import CompileContext, RecipeCompileError, compile_recipe
from cedarkit.plots.recipe import load_recipe


def registry() -> OpRegistry:
    return OpRegistry((
        OpDescriptor("add", "compute", 2, 1, lambda left, right: left + right),
        OpDescriptor("identity", "transform", 1, 1, lambda value: value),
    ))


def recipe(data, layers=None):
    return load_recipe({"api_version": "cedarkit.plots/v2", "kind": "PlotRecipe",
                        "metadata": {"name": "test.recipe"},
                        "spec": {"domain": {"default": "x", "area": "y"}, "data": data,
                                 "layers": layers or [{"field": "result", "style": "test"}],
                                 "title": {"graph_name": "test"}}})


def test_compute_input_can_be_declared_after_compute_and_topology_is_stable():
    loaded = recipe({"result": {"compute": {"op": "add", "inputs": ["left", "right"]}},
                     "left": {"field": {"parameter": "cedarkit.t2m"}},
                     "right": {"field": {"parameter": "cedarkit.t2m"}}})
    plan = compile_recipe(loaded, CompileContext(forecast_time="2026-01-01T00:00Z"), registry=registry())
    assert [node.kind for node in plan.nodes] == ["read", "compute"]
    assert plan.read_count == 1
    assert plan.outputs["left"] == plan.outputs["right"]
    assert plan.to_dict() == compile_recipe(loaded, CompileContext(forecast_time="2026-01-01T00:00Z"), registry=registry()).to_dict()

    reordered = recipe({"right": {"field": {"parameter": "cedarkit.t2m"}},
                        "left": {"field": {"parameter": "cedarkit.t2m"}},
                        "result": {"compute": {"op": "add", "inputs": ["left", "right"]}}})
    assert plan.to_dict() == compile_recipe(reordered, CompileContext(forecast_time="2026-01-01T00:00Z"), registry=registry()).to_dict()


def test_cycle_is_a_compile_error_before_any_io():
    loaded = recipe({"left": {"compute": {"op": "add", "inputs": ["right", "right"]}},
                     "right": {"compute": {"op": "add", "inputs": ["left", "left"]}}}, layers=[{"field": "left", "style": "test"}])
    with pytest.raises(RecipeCompileError, match="left -> right -> left"):
        compile_recipe(loaded, CompileContext(), registry=registry())


def test_dead_nodes_are_pruned_and_strict_mode_rejects_them():
    loaded = recipe({"result": {"field": {"parameter": "cedarkit.t2m"}},
                     "unused": {"field": {"parameter": "cedarkit.t"}}})
    plan = compile_recipe(loaded, CompileContext(), registry=registry())
    assert plan.read_count == 1
    assert [issue.code for issue in plan.issues] == ["dead_node"]
    with pytest.raises(RecipeCompileError, match="dead nodes"):
        compile_recipe(loaded, CompileContext(strict=True), registry=registry())
