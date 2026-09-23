import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest
import xarray as xr

from cedarkit.plots.config import BasemapSpec, LayoutSpec
from cedarkit.plots.ops import OpDescriptor, OpRegistry
from cedarkit.plots.templates import east_asia, xy
from cedarkit.plots.workflow.plan import compile_recipe
from cedarkit.plots.workflow.recipe import load_recipe
from cedarkit.plots.workflow.render import WorkflowRenderError, render_result


def recipe(*, template=None, targets="main", data_crs=None, diagnostics=False):
    data = {"temperature": {"field": {"parameter": "cedarkit.t2m"},
                            "units": "degC", "temperature_kind": "absolute"}}
    if diagnostics:
        data["result"] = {"compute": {"op": "identity", "inputs": ["temperature"]}}
    source = "result" if diagnostics else "temperature"
    return load_recipe({
        "api_version": "cedarkit.plots/v3", "kind": "PlotRecipe",
        "metadata": {"name": "test.render"},
        "spec": {"data": data,
                 "content": {"charts": [{"id": "weather", "plots": [{
                     "id": "temperature", "method": "contourf", "field": source,
                     "style": "cemc.t2m:cn_summer", "targets": targets,
                     "data_crs": data_crs}],
                     "titles": [{"id": "heading", "text": "Temperature"}]}],
                     "colorbars": [{"id": "scale", "plots": [{"chart": "weather", "plot": "temperature"}],
                                    "label": "°C"}]},
                 "display": {"template": template} if template else {}},
    })


def field(*, map_data=False, covered=True):
    if map_data:
        x = np.linspace(40, 160, 13) if covered else np.linspace(100, 120, 5)
        y = np.linspace(-10, 70, 9) if covered else np.linspace(20, 40, 5)
    else:
        x, y = np.arange(5), np.arange(4)
    values = 273.15 + np.add.outer(np.linspace(0, 5, len(y)), np.linspace(0, 5, len(x)))
    return xr.DataArray(values, dims=("y", "x"), coords={"x": x, "y": y},
                        attrs={"units": "K", "standard_name": "air_temperature"})


class Provider:
    def __init__(self, data):
        self.data = data
        self.fetch_count = 0
        self.closed = False

    def fetch_many(self, requests):
        self.fetch_count += 1
        return [self.data] * len(requests)

    def close(self):
        self.closed = True


def test_xy_bridge_binds_logical_ids_and_repeated_output_does_not_reexecute(tmp_path, monkeypatch):
    import cedarkit.plots.workflow.runtime.executor as executor

    calls = {"diagnostic": 0, "conversion": 0}

    def identity(value):
        calls["diagnostic"] += 1
        return value

    original_prepare = executor.prepare_field

    def counted_prepare(*args, **kwargs):
        calls["conversion"] += 1
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(executor, "prepare_field", counted_prepare)
    registry = OpRegistry((OpDescriptor("identity", "compute", 1, 1, identity),))
    provider = Provider(field())
    plan = compile_recipe(recipe(diagnostics=True), registry=registry)
    result = plan.execute(provider, registry=registry)
    assert calls == {"diagnostic": 1, "conversion": 1}
    panel = render_result(result)
    chart = panel.charts["weather"]
    layer = chart.layers["temperature"]
    assert panel.fig is not None
    assert len(panel.fig.axes) == 2
    assert tuple(layer.results) == ("main",)
    assert chart.id == "weather" and layer.id == "temperature"
    assert calls == {"diagnostic": 1, "conversion": 1}

    first = panel.fig
    panel.save(tmp_path / "first.png")
    panel.apply_template(xy())
    panel.configure(layout=LayoutSpec(figsize=(9, 6)))
    panel.render()
    panel.save(tmp_path / "second.png")
    assert panel.charts["weather"] is chart
    assert chart.layers["temperature"] is layer
    assert panel.fig is not first
    assert calls == {"diagnostic": 1, "conversion": 1}
    assert provider.fetch_count == 1
    assert (tmp_path / "first.png").stat().st_size > 0
    assert (tmp_path / "second.png").stat().st_size > 0
    panel.close()
    assert not provider.closed


def test_map_all_targets_follow_template_switch_without_data_execution():
    empty = BasemapSpec(features=(), map_info=None)
    with_inset = east_asia(main_basemap=empty, sub_basemap=empty)
    no_inset = east_asia(with_inset=False, main_basemap=empty)
    provider = Provider(field(map_data=True))
    result = compile_recipe(recipe(template="map", targets="all", data_crs="plate_carree")).execute(provider)
    panel = render_result(result, templates={"map": with_inset})
    chart = panel.charts["weather"]
    layer = chart.layers["temperature"]
    assert tuple(layer.results) == ("main", "south_china_sea")
    assert len(panel.fig.axes) == 3  # main, inset, colorbar; title is text
    panel.apply_template(no_inset)
    panel.render()
    assert tuple(layer.results) == ("main",)
    assert panel.charts["weather"] is chart
    assert chart.layers["temperature"] is layer
    assert provider.fetch_count == 1
    panel.close()


def test_coverage_failure_closes_temporary_panel_and_keeps_provider_owned(monkeypatch):
    from cedarkit.plots import Panel

    empty = BasemapSpec(features=(), map_info=None)
    provider = Provider(field(map_data=True, covered=False))
    result = compile_recipe(recipe(template="map", data_crs="plate_carree")).execute(provider)
    closed = []
    original_close = Panel.close

    def close(panel):
        closed.append(panel)
        return original_close(panel)

    monkeypatch.setattr(Panel, "close", close)
    with pytest.raises(WorkflowRenderError, match="insufficient coverage") as caught:
        render_result(result, templates={"map": east_asia(with_inset=False, main_basemap=empty)})
    assert caught.value.path == "render"
    assert len(closed) == 1 and closed[0].closed
    assert not provider.closed
    np.testing.assert_allclose(provider.data.values, field(map_data=True, covered=False).values)


def test_fixed_missing_target_fails_with_product_context():
    result = compile_recipe(recipe(template="xy", targets="south_china_sea")).execute(Provider(field()))
    with pytest.raises(WorkflowRenderError, match="product=test.render") as caught:
        render_result(result)
    assert "south_china_sea" in str(caught.value)


def test_direct_display_layout_and_chart_override():
    document = {
        "api_version": "cedarkit.plots/v3", "kind": "PlotRecipe",
        "metadata": {"name": "facet"},
        "spec": {"data": {"t": {"field": {"parameter": "cedarkit.t2m"},
                              "units": "degC", "temperature_kind": "absolute"}},
                 "content": {"charts": [
                     {"id": name, "plots": [{"id": "t", "method": "contourf", "field": "t",
                                              "style": "cemc.t2m:cn_summer"}]}
                     for name in ("first", "second")]},
                 "display": {"layout": {"rows": 1, "columns": 2},
                             "charts": {"second": {"subplots": {"main": {"axis": {"xticks": [0, 2, 4]}}}}}}},
    }
    provider = Provider(field())
    panel = render_result(compile_recipe(load_recipe(document)).execute(provider))
    assert len(panel.fig.axes) == 2
    assert panel.effective_config.layout.columns == 2
    assert tuple(panel.charts["second"].main.ax.get_xticks()) == (0, 2, 4)
    assert provider.fetch_count == 1
    panel.close()


def test_vector_method_uses_two_named_bindings():
    document = {
        "api_version": "cedarkit.plots/v3", "kind": "PlotRecipe",
        "metadata": {"name": "wind"},
        "spec": {"data": {"u": {"field": {"parameter": "cedarkit.u"}},
                          "v": {"field": {"parameter": "cedarkit.v"}}},
                 "content": {"charts": [{"id": "wind", "plots": [{
                     "id": "barbs", "method": "barbs", "vector": {"u": "u", "v": "v"},
                     "style": "cemc.wind:cn", "vector_basis": "grid"}]}]}},
    }

    class WindProvider:
        def fetch_many(self, requests):
            return [field().copy(data=np.full((4, 5), 3 if request.key.parameter_id == "cedarkit.u" else 4))
                    .assign_attrs(units="m/s") for request in requests]

    panel = render_result(compile_recipe(load_recipe(document)).execute(WindProvider()))
    layer = panel.charts["wind"].layers["barbs"]
    assert layer.method == "barbs"
    assert tuple(layer.results) == ("main",)
    panel.close()
