"""A v3 recipe traverses the only new compile, execute and render path."""

import matplotlib

matplotlib.use("Agg")

import numpy as np
import xarray as xr
import yaml

from cedarkit.plots.workflow.discovery import discover_workflow
from cedarkit.plots.workflow.plan import compile_recipe
from cedarkit.plots.workflow.recipe import load_recipe
from cedarkit.plots.workflow.render import render_result


def test_temperature_document_to_saved_panel(tmp_path):
    document = {
        "api_version": "cedarkit.plots/v3", "kind": "PlotRecipe",
        "metadata": {"name": "temperature"},
        "spec": {
            "data": {"temperature": {"field": {"parameter": "cedarkit.t2m"},
                                     "units": "degC", "temperature_kind": "absolute"}},
            "content": {"charts": [{"id": "main", "plots": [{"id": "temperature", "method": "contourf",
                            "field": "temperature", "style": "cemc.t2m:cn_summer"}],
                            "titles": [{"id": "heading", "text": "{metadata.name}"}]}]},
            "display": {"template": "xy"},
        },
    }
    path = tmp_path / "temperature.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    discovered = discover_workflow(entry_points={})
    plan = compile_recipe(load_recipe(path), registry=discovered.ops)

    class Provider:
        fetches = 0
        closed = False

        def fetch_many(self, requests):
            self.fetches += 1
            field = xr.DataArray(273.15 + np.add.outer(np.arange(4), np.arange(5)),
                                 dims=("y", "x"), attrs={"units": "K", "standard_name": "air_temperature"})
            return [field for _ in requests]

    provider = Provider()
    result = plan.execute(provider, registry=discovered.ops)
    assert float(result.outputs["temperature"].values[0, 0]) == 0.0
    assert result.content.charts[0].titles[0].text == "temperature"
    panel = render_result(result, domains=discovered.domains)
    try:
        output = tmp_path / "temperature.png"
        panel.save(output)
        assert output.stat().st_size > 0
        assert panel.charts["main"].layers["temperature"].id == "temperature"
    finally:
        panel.close()
    assert provider.fetches == 1
    assert not provider.closed
