from __future__ import annotations

import json

from cedarkit.plots.cli import main


V2 = """\
api_version: cedarkit.plots/v2
kind: PlotRecipe
metadata: {name: test.t2m}
spec:
  domain: {default: east_asia, area: cn_area}
  data:
    t2m: {field: {parameter: cedarkit.t2m}, units: degC}
  layers: [{field: t2m, style: t2m:cn_summer}]
  title: {graph_name: t2m}
"""


def test_validate_accepts_a_recipe_directory(tmp_path, capsys):
    (tmp_path / "one.yaml").write_text(V2, encoding="utf-8")
    assert main(["recipe", "validate", str(tmp_path), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == [{"issues": [], "ok": True, "path": str(tmp_path / "one.yaml"), "version": 2}]


def test_plan_previews_duration_context_as_versioned_json(tmp_path, capsys):
    recipe = tmp_path / "one.yaml"
    recipe.write_text(V2, encoding="utf-8")
    assert main(["recipe", "plan", str(recipe), "--start-time", "2024-07-01T00:00Z",
                 "--forecast-time", "24h", "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["plan_schema_version"] == 2
    assert result["context"]["forecast_time"] == "P1DT0H0M0S"
    assert [node["kind"] for node in result["nodes"]] == ["read", "convert_units"]
