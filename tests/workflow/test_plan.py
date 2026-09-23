import pytest

from cedarkit.plots.ops import OpDescriptor, OpRegistry
from cedarkit.plots.workflow.plan import CompileContext, RecipeCompileError, compile_recipe
from cedarkit.plots.workflow.recipe import load_recipe


def recipe(data, field="result"):
    return load_recipe({
        "api_version": "cedarkit.plots/v3", "kind": "PlotRecipe",
        "metadata": {"name": "test.product"},
        "spec": {"data": data, "content": {"charts": [{"id": "main", "plots": [
            {"id": "plot", "method": "contourf", "field": field, "style": "cemc.t2m:cn_summer"}]}]}},
    })


def registry():
    return OpRegistry((OpDescriptor("add", "compute", 2, 1, lambda a, b: a + b),))


def test_static_dag_is_stable_and_deduplicates_reads():
    declarations = {
        "result": {"compute": {"op": "add", "inputs": ["left", "right"]}},
        "left": {"field": {"parameter": "cedarkit.t2m"}},
        "right": {"field": {"parameter": "cedarkit.t2m"}},
    }
    first = compile_recipe(recipe(declarations), CompileContext(forecast_time="2026-01-01T00:00Z"), registry=registry())
    reordered = {key: declarations[key] for key in reversed(declarations)}
    second = compile_recipe(recipe(reordered), CompileContext(forecast_time="2026-01-01T00:00Z"), registry=registry())
    assert [(node.id, node.kind, node.dependencies) for node in first.nodes] == [
        (node.id, node.kind, node.dependencies) for node in second.nodes]
    assert first.read_count == 1
    assert len(first.read_batches) == 1
    assert first.outputs["left"] == first.outputs["right"]
    assert first.nodes[-1].dependencies == (first.nodes[0].id, first.nodes[0].id)


def test_compile_and_preflight_use_metadata_only_and_never_construct_figure(monkeypatch):
    import matplotlib.figure

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Figure or field values must not be constructed")

    monkeypatch.setattr(matplotlib.figure, "Figure", forbidden)

    class MetadataOnlyProvider:
        def __init__(self):
            self.requests = ()

        fetch = forbidden
        fetch_many = forbidden

        def check_many(self, requests):
            self.requests = requests
            return ["missing"] * len(requests)

    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.t2m"},
                                             "units": "degC", "temperature_kind": "absolute"}}))
    provider = MetadataOnlyProvider()
    report = plan.check_available(provider)
    assert len(provider.requests) == 1
    assert not report.executable
    missing = report.requests[0]
    assert missing.status == "missing"
    assert missing.node_id.startswith("read:")
    assert missing.recipe_identity == "test.product"
    assert missing.consumers == ("result",)
    assert missing.origin == "spec.data.result.field"


def test_cycle_and_unknown_field_include_product_and_binding():
    cyclic = recipe({"result": {"compute": {"op": "add", "inputs": ["other", "other"]}},
                     "other": {"compute": {"op": "add", "inputs": ["result", "result"]}}})
    with pytest.raises(RecipeCompileError, match="other -> result -> other") as caught:
        compile_recipe(cyclic, registry=registry())
    assert "test.product" in str(caught.value)
    assert caught.value.binding == "other"

    missing = recipe({"result": {"field": {"parameter": "not.a.parameter"}}})
    with pytest.raises(RecipeCompileError, match="test.product.*cannot resolve field") as caught:
        compile_recipe(missing)
    assert caught.value.binding == "result"
    assert caught.value.code == "field_query"


def test_dead_subtree_is_pruned_and_reported():
    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.t2m"}},
                                  "unused": {"field": {"parameter": "cedarkit.rain"}}}))
    assert plan.read_count == 1
    assert plan.issues[0].code == "dead_node"
    with pytest.raises(RecipeCompileError, match="dead nodes found"):
        compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.t2m"}},
                               "unused": {"field": {"parameter": "cedarkit.rain"}}}), CompileContext(strict=True))


def test_time_difference_creates_prior_read_in_separate_batch():
    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.t2m"},
                                              "transforms": [{"op": "time_diff", "args": ["24h"]}]}}),
                          CompileContext(forecast_time="48h"))
    assert plan.read_count == 2
    assert len(plan.read_batches) == 2
    assert {node.request.forecast_time for node in plan.nodes if node.request} == {
        "P2DT0H0M0S", "P1DT0H0M0S"}

    timestamp_plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.t2m"},
                                                        "transforms": [{"op": "time_diff", "args": ["24h"]}]}}),
                                    CompileContext(start_time="2026-01-01T00:00Z", forecast_time="2026-01-03T00:00Z"))
    assert {node.request.forecast_time for node in timestamp_plan.nodes if node.request} == {
        "2026-01-03T00:00:00Z", "2026-01-02T00:00:00Z"}


def test_distinct_requests_at_one_time_share_batch_and_bad_op_has_context():
    data = {"left": {"field": {"parameter": "cedarkit.t2m"}},
            "right": {"field": {"parameter": "cedarkit.rain"}},
            "result": {"compute": {"op": "add", "inputs": ["left", "right"]}}}
    plan = compile_recipe(recipe(data), registry=registry())
    assert plan.read_count == 2
    assert len(plan.read_batches) == 1
    assert len(plan.read_batches[0]) == 2

    data["result"]["compute"]["op"] = "missing_op"
    with pytest.raises(RecipeCompileError, match="test.product.*missing_op") as caught:
        compile_recipe(recipe(data), registry=registry())
    assert caught.value.binding == "result"
    assert caught.value.code == "unknown_op"


@pytest.mark.parametrize("parameter,level,expected_type,expected_level", (
    ("cedarkit.h", {"first_level_type": 100, "first_level": 500}, "isobaricInhPa", 500),
    ("cedarkit.u", {"first_level_type": 103, "first_level": 10}, "heightAboveGround", 10),
    ("cedarkit.shr", {"first_level_type": 103, "first_level": 3000,
                      "second_level_type": 103, "second_level": 0}, "heightAboveGroundLayer", 3000),
))
def test_catalog_surface_levels_bind_to_searchable_query(parameter, level, expected_type, expected_level):
    plan = compile_recipe(recipe({"result": {"field": {"parameter": parameter, "level": level}}}))
    query = next(node.request.query for node in plan.nodes if node.request)
    assert query.level_type == expected_type
    assert query.level == expected_level
    assert "first_level" not in query.extra
    assert "second_level" not in query.extra


def test_multi_output_slots_are_stable():
    data = {"source": {"field": {"parameter": "cedarkit.t2m"}},
            "diagnostic": {"compute": {"op": "split", "inputs": ["source"],
                                       "outputs": ["low", "high"]}}}
    custom = OpRegistry((OpDescriptor("split", "compute", 1, 2, lambda value: (value, value)),))
    plan = compile_recipe(recipe(data, field="high"), registry=custom)
    assert plan.outputs["low"] == plan.outputs["high"]
    assert plan.output_slots["low"] == 0
    assert plan.output_slots["high"] == 1
