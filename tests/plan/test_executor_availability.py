from __future__ import annotations

import pytest
import pandas as pd
import xarray as xr

from cedarkit.plots.ops import OpRegistry
from cedarkit.plots.plan import CompileContext, PlanExecutionError, compile_recipe
from cedarkit.plots.recipe import load_recipe


def _recipe(data, *, params=None):
    return load_recipe({"api_version": "cedarkit.plots/v2", "kind": "PlotRecipe", "metadata": {"name": "test.execution"}, "spec": {"params": params or {}, "domain": {"default": "x", "area": "y"}, "data": data, "layers": [{"field": "result", "style": "test"}], "title": {"graph_name": "test"}}})


class Provider:
    def __init__(self, statuses=None): self.calls, self.statuses = [], statuses
    def fetch_many(self, requests):
        self.calls.append(tuple(requests))
        return [pd.Timestamp(request.key.time_binding.forecast_time) for request in requests]
    def check_many(self, requests): return self.statuses or ["available"] * len(requests)


def test_time_diff_planner_makes_previous_request_visible_and_executes_in_one_batch():
    loaded = _recipe({"result": {"field": {"parameter": "cedarkit.t2m"}, "transforms": [{"op": "time_diff", "args": ["24h"]}]}})
    plan = compile_recipe(loaded, CompileContext(forecast_time="2026-01-03T00:00Z"))
    reads = [node for node in plan.nodes if node.kind == "read"]
    assert len(reads) == 2
    assert {node.request.time_binding.forecast_time for node in reads} == {"2026-01-03T00:00:00Z", "2026-01-02T00:00:00Z"}
    provider = Provider()
    result = plan.execute(provider)
    assert len(provider.calls) == 2  # different time bindings form separate batch groups
    assert result.outputs["result"] == pd.Timedelta("24h")


def test_equivalent_reads_are_deduplicated_for_execution_and_fallback_fetch():
    loaded = _recipe({
        "result": {"field": {"parameter": "cedarkit.t2m"}},
        "same": {"field": {"parameter": "cedarkit.t2m"}},
    })
    plan = compile_recipe(loaded, CompileContext())

    class FetchOnlyProvider:
        def __init__(self): self.calls = []
        def fetch(self, request):
            self.calls.append(request)
            return "value"

    provider = FetchOnlyProvider()
    result = plan.execute(provider)
    assert len(provider.calls) == 1
    assert result.outputs["result"] == result.outputs["same"] == "value"


def test_dead_subtree_never_reaches_provider_or_executor():
    loaded = _recipe({
        "result": {"field": {"parameter": "cedarkit.t2m"}},
        "dead": {"field": {"parameter": "cedarkit.rain"}, "transforms": [{"op": "smth9"}]},
    })
    plan = compile_recipe(loaded, CompileContext())
    provider = Provider()
    result = plan.execute(provider)
    assert len(provider.calls) == 1
    assert len(provider.calls[0]) == 1
    assert "dead" not in result.outputs
    assert all(trace.kind != "transform" for trace in result.trace)


def test_availability_checks_each_deduplicated_read_once_and_reports_consumers():
    loaded = _recipe({"result": {"field": {"parameter": "cedarkit.t2m"}}, "same": {"field": {"parameter": "cedarkit.t2m"}}})
    plan = compile_recipe(loaded, CompileContext())
    provider = Provider(["missing"])
    report = plan.check_available(provider)
    assert not report.executable
    assert report.requests[0].status == "missing"
    assert report.requests[0].consumers == ("result", "same")


def test_time_diff_invalid_interval_is_compile_error():
    loaded = _recipe({"result": {"field": {"parameter": "cedarkit.t2m"}, "transforms": [{"op": "time_diff", "args": ["0h"]}]}})
    with pytest.raises(ValueError, match="positive"):
        compile_recipe(loaded, CompileContext(forecast_time="2026-01-03T00:00Z"))


def test_declared_data_units_become_an_explicit_conversion_node():
    loaded = _recipe({"result": {"field": {"parameter": "cedarkit.t2m"}, "units": "degC"}})
    plan = compile_recipe(loaded, CompileContext())
    assert [node.kind for node in plan.nodes] == ["read", "convert_units"]

    class KelvinProvider:
        def fetch(self, request): return xr.DataArray([273.15], attrs={"units": "K", "long_name": "temperature"})

    value = plan.execute(KelvinProvider()).outputs["result"]
    assert value.values.tolist() == [0.0]
    assert value.attrs == {"units": "degC", "long_name": "temperature"}


def test_multi_output_compute_binds_each_declared_output_slot():
    loaded = _recipe({
        "source": {"field": {"parameter": "cedarkit.rain"}},
        "classification": {
            "compute": {
                "op": "classify", "inputs": ["source"],
                "outputs": ["result", "snow", "mixed"],
            },
        },
    })
    registry = OpRegistry.builtins()
    registry.register("classify", lambda _source: ("rain", "snow", "mixed"), kind="compute", output_count=3)
    plan = compile_recipe(loaded, CompileContext(), registry=registry)
    result = plan.execute(Provider(), registry=registry)
    assert result.outputs["result"] == "rain"
    assert result.outputs["snow"] == "snow"
    assert result.outputs["mixed"] == "mixed"
