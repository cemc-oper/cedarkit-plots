import numpy as np
import pytest
import xarray as xr

from cedarkit.plots.ops import OpDescriptor, OpRegistry
from cedarkit.plots.workflow.plan import CompileContext, compile_recipe
from cedarkit.plots.workflow.recipe import load_recipe
from cedarkit.plots.workflow.runtime import PlanExecutionError


def recipe(data, field="result"):
    return load_recipe({"api_version": "cedarkit.plots/v3", "kind": "PlotRecipe",
                        "metadata": {"name": "test.runtime"},
                        "spec": {"data": data, "content": {"charts": [{"id": "main", "plots": [
                            {"id": "plot", "method": "contourf", "field": field,
                             "style": "cemc.t2m:cn_summer"}]}]}}})


def array(value, units, *, size=2):
    return xr.DataArray(np.full((size, size), value, dtype=float), dims=("y", "x"),
                        coords={"y": range(size), "x": range(size)}, attrs={"units": units})


class Provider:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def fetch_many(self, requests):
        self.calls.append(tuple(requests))
        return [self.values[request.key.parameter_id] for request in requests]


def test_temperature_conversion_once_per_execution_and_task_isolation():
    source = array(273.15, "K")
    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.t2m"},
                                               "units": "degC", "temperature_kind": "absolute"}}))
    provider = Provider({"cedarkit.t2m": source})
    first = plan.execute(provider)
    second = plan.execute(provider)
    np.testing.assert_allclose(first.outputs["result"], 0)
    assert first.outputs["result"].attrs["units"] == "degC"
    assert source.attrs == {"units": "K"}
    np.testing.assert_allclose(source, 273.15)
    assert len([trace for trace in first.trace if trace.kind == "convert_units"]) == 1
    first.outputs["result"].values[:] = 999
    np.testing.assert_allclose(second.outputs["result"], 0)
    assert len(provider.calls) == 2


def test_accumulation_time_difference_uses_two_reads_without_mutation():
    current, previous = array(10, "mm"), array(3, "mm")
    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.rain"},
                                               "transforms": [{"op": "time_diff", "args": ["24h"]}],
                                               "units": "mm", "source_units": "mm"}}),
                          CompileContext(forecast_time="48h"))

    class TimedProvider:
        def __init__(self):
            self.times = []

        def fetch_many(self, requests):
            self.times.extend(request.key.forecast_time for request in requests)
            return [current if request.key.forecast_time == "P2DT0H0M0S" else previous
                    for request in requests]

    provider = TimedProvider()
    result = plan.execute(provider)
    np.testing.assert_allclose(result.outputs["result"], 7)
    assert set(provider.times) == {"P2DT0H0M0S", "P1DT0H0M0S"}
    np.testing.assert_allclose(current, 10)
    np.testing.assert_allclose(previous, 3)


def test_temperature_difference_has_no_absolute_offset():
    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.t2m"},
                                               "transforms": [{"op": "time_diff", "args": ["24h"]}],
                                               "units": "degC", "source_units": "K",
                                               "temperature_kind": "difference"}}),
                          CompileContext(forecast_time="48h"))

    class TimedProvider:
        def fetch_many(self, requests):
            return [array(283.15 if request.key.forecast_time == "P2DT0H0M0S" else 273.15, "K")
                    for request in requests]

    result = plan.execute(TimedProvider())
    np.testing.assert_allclose(result.outputs["result"], 10)
    assert result.outputs["result"].attrs["temperature_kind"] == "difference"


def test_time_difference_rejects_mismatched_source_units():
    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.t2m"},
                                               "transforms": [{"op": "time_diff", "args": ["24h"]}],
                                               "units": "degC", "source_units": "K",
                                               "temperature_kind": "difference"}}),
                          CompileContext(forecast_time="48h"))

    class TimedProvider:
        def fetch_many(self, requests):
            return [array(283.15, "K") if request.key.forecast_time == "P2DT0H0M0S"
                    else array(10, "degC") for request in requests]

    with pytest.raises(PlanExecutionError, match="time_diff") as caught:
        plan.execute(TimedProvider())
    assert caught.value.trace[-1].kind == "transform"


def test_scale_smooth_and_wind_speed_compute_use_registered_algorithms():
    # The diagnostic stays with the business package; workflow invokes its descriptor.
    def wind_speed(u, v, *, context=None):
        return np.hypot(u, v)

    registry = OpRegistry.builtins()
    registry.register_descriptor(OpDescriptor("wind_speed", "compute", 2, 1, wind_speed))
    data = {
        "u": {"field": {"parameter": "cedarkit.u"},
              "transforms": [{"op": "unit_scale", "args": [2]},
                             {"op": "smth9", "args": [0.5, 0.25, False]}]},
        "v": {"field": {"parameter": "cedarkit.v"}},
        "result": {"compute": {"op": "wind_speed", "inputs": ["u", "v"]},
                   "units": "m/s", "source_units": "m/s"},
    }
    plan = compile_recipe(recipe(data), registry=registry)
    provider = Provider({"cedarkit.u": array(3, "m/s", size=5),
                         "cedarkit.v": array(8, "m/s", size=5)})
    result = plan.execute(provider, registry=registry)
    np.testing.assert_allclose(result.outputs["result"].sel(y=2, x=2), 10)
    assert result.outputs["result"].attrs["units"] == "m/s"
    assert [trace.kind for trace in result.trace].count("transform") == 2
    np.testing.assert_allclose(provider.values["cedarkit.u"], 3)


def test_unit_mismatch_fails_with_node_product_trace_and_no_source_mutation():
    source = array(273.15, "degC")
    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.t2m"},
                                               "units": "degC", "source_units": "K",
                                               "temperature_kind": "absolute"}}))
    with pytest.raises(PlanExecutionError, match="product=test.runtime.*operation failed") as caught:
        plan.execute(Provider({"cedarkit.t2m": source}))
    error = caught.value
    assert error.node_id.startswith("convert_units:")
    assert error.trace[-1].status == "error"
    assert error.origin == "spec.data.result.units"
    assert source.attrs == {"units": "degC"}


def test_bad_provider_result_reports_read_node_and_prior_trace():
    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.t2m"}}}))
    with pytest.raises(PlanExecutionError, match="invalid field value") as caught:
        plan.execute(Provider({"cedarkit.t2m": None}))
    assert caught.value.node_id.startswith("read:")
    assert caught.value.trace[-1].status == "error"


def test_multi_output_slot_flows_to_downstream_compute():
    def split(value):
        return value + 1, value + 2

    def add(left, right):
        return left + right

    registry = OpRegistry((OpDescriptor("split", "compute", 1, 2, split),
                           OpDescriptor("add", "compute", 2, 1, add)))
    data = {"source": {"field": {"parameter": "cedarkit.t2m"}},
            "both": {"compute": {"op": "split", "inputs": ["source"],
                                 "outputs": ["low", "high"]}},
            "result": {"compute": {"op": "add", "inputs": ["low", "high"]}}}
    plan = compile_recipe(recipe(data), registry=registry)
    output = plan.execute(Provider({"cedarkit.t2m": array(1, "K")}), registry=registry)
    np.testing.assert_allclose(output.outputs["result"], 5)
    np.testing.assert_allclose(output.outputs["high"], 3)


def test_source_units_without_target_is_a_real_validation_node():
    source = array(1000, "Pa")
    source.attrs.clear()
    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.psl"},
                                               "source_units": "Pa"}}))
    result = plan.execute(Provider({"cedarkit.psl": source}))
    assert result.outputs["result"].attrs["units"] == "Pa"
    assert source.attrs == {}


def cumulative_endpoint(hour, value, *, error=0.0, origin="2026-11-02T12:00:00Z"):
    import json
    import pandas as pd
    start = pd.Timestamp(origin)
    end = start + pd.Timedelta(hours=hour)
    a = array(value, "mm").assign_coords(time=start.tz_localize(None), step=np.timedelta64(hour, "h"), valid_time=end.tz_localize(None))
    identity = {"parameter": "cedarkit.rain.since-initialization", "time": start.isoformat(),
                "step": pd.Timedelta(hours=hour).isoformat(), "valid_time": end.isoformat(), "level_type": "surface"}
    a.attrs.update(field_identity=json.dumps(identity), statistical_interval=json.dumps({"start": start.isoformat(), "end": end.isoformat()}),
                   value_encoding=json.dumps({"quantization_error": error, "unit": "mm"}),
                   source_reference=json.dumps({"hour": hour}), cedarkit_query_report=json.dumps({"overall": {"status": "unchecked"}}))
    return a


def test_reviewed_accumulation_retains_small_negatives_and_input_reports():
    import json
    from cedarkit.plots.ops.builtin import time_diff
    current = cumulative_endpoint(48, 3.0 - 0.000032, error=0.000032)
    previous = cumulative_endpoint(24, 3.0, error=0.000016)
    current.values[0, 1] = np.nan
    result = time_diff(current, previous, accumulation_hours=24.0, since_initialization=True)
    np.testing.assert_array_equal(result.values, current.values - previous.values)
    assert result.attrs["negative_difference_points"] == 3
    assert result.attrs["negative_difference_bound"] == pytest.approx(0.000048)
    assert result.attrs["accumulation_start"].startswith("2026-11-03T12:00:00")
    assert result.step == current.step
    assert "field_identity" not in result.attrs and "cedarkit_query_report" not in result.attrs
    assert len(json.loads(result.attrs["source_query_reports"])) == 2
    assert previous.values[0, 0] == 3.0


@pytest.mark.parametrize("case", ["reset", "cycle", "grid", "initialization", "decrease", "unknown_precision"])
def test_reviewed_accumulation_refuses_inconsistent_endpoints(case):
    import json
    from cedarkit.plots.ops.builtin import time_diff
    current = cumulative_endpoint(48, 10.0)
    previous = cumulative_endpoint(24, 3.0)
    if case == "reset":
        current.attrs["statistical_interval"] = json.dumps({"start": "2026-11-03T12:00:00Z", "end": "2026-11-04T12:00:00Z"})
    elif case == "cycle":
        previous = cumulative_endpoint(24, 3.0, origin="2026-11-03T12:00:00Z")
    elif case == "grid":
        previous = previous.assign_coords(x=[1, 2])
    elif case == "initialization":
        previous = cumulative_endpoint(0, 1.0)
        current = cumulative_endpoint(24, 10.0)
    elif case == "decrease":
        current.values[:] = 1.0
    else:
        del previous.attrs["value_encoding"]
    with pytest.raises(ValueError):
        time_diff(current, previous, accumulation_hours=24.0, since_initialization=True)


def test_reviewed_accumulation_rejects_before_render_with_transform_location():
    plan = compile_recipe(recipe({"result": {"field": {"parameter": "cedarkit.rain.since-initialization"},
        "transforms": [{"op": "time_diff", "args": ["24h"], "kwargs": {"since_initialization": True}}]}}),
        CompileContext(start_time="2026-11-02T12:00:00Z", forecast_time="48h"))
    class Endpoints:
        def fetch_many(self, requests):
            return [cumulative_endpoint(48, 1.0) if "P2D" in r.key.forecast_time else cumulative_endpoint(24, 3.0) for r in requests]
    with pytest.raises(PlanExecutionError, match="decreased beyond") as caught:
        plan.execute(Endpoints())
    assert caught.value.trace[-1].kind == "transform"
    assert caught.value.origin == "spec.data.result.transforms.0"
