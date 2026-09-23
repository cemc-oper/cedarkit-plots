from __future__ import annotations

import json

import pytest

from cedarkit.plots.cli import main


V3 = """\
api_version: cedarkit.plots/v3
kind: PlotRecipe
metadata: {name: test.t2m}
spec:
  data:
    t2m: {field: {parameter: cedarkit.t2m}, units: degC, temperature_kind: absolute}
  content:
    charts:
      - id: main
        plots: [{id: t2m, method: contourf, field: t2m, style: cemc.t2m:cn_summer}]
"""


def test_validate_accepts_v3_directory_and_stdin(tmp_path, capsys, monkeypatch):
    (tmp_path / "one.yaml").write_text(V3, encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "two.yml").write_text(V3, encoding="utf-8")
    assert main(["recipe", "validate", str(tmp_path), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert [item["path"] for item in result] == [str(tmp_path / "nested" / "two.yml"), str(tmp_path / "one.yaml")]
    assert all(item["version"] == "cedarkit.plots/v3" and item["name"] == "test.t2m" for item in result)

    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(V3))
    assert main(["validate", "-", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["path"] == "<stdin>"


def test_plan_previews_v3_workflow_without_executing(tmp_path, capsys):
    recipe = tmp_path / "one.yaml"
    recipe.write_text(V3, encoding="utf-8")
    assert main(["recipe", "plan", str(recipe), "--start-time", "2024-07-01T00:00Z",
                 "--forecast-time", "24h", "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["plan_schema_version"] == 3
    assert result["recipe"] == {"api_version": "cedarkit.plots/v3", "identity": "test.t2m"}
    assert result["context"]["forecast_time"] == "P1DT0H0M0S"
    assert [node["kind"] for node in result["nodes"]] == ["read", "convert_units"]
    assert result["content"]["charts"][0]["plots"][0]["id"] == "t2m"
    assert main(["plan", str(recipe)]) == 0
    assert "WorkflowPlan(recipe='test.t2m'" in capsys.readouterr().out


def test_v1_v2_and_migrate_command_are_rejected(tmp_path, capsys):
    recipe = tmp_path / "old.yaml"
    recipe.write_text(V3.replace("cedarkit.plots/v3", "cedarkit.plots/v2"), encoding="utf-8")
    assert main(["validate", str(recipe)]) == 2
    assert "unsupported api_version" in capsys.readouterr().err
    assert main(["plan", str(recipe)]) == 2
    assert "unsupported api_version" in capsys.readouterr().err
    with pytest.raises(SystemExit) as caught:
        main(["migrate", str(recipe)])
    assert caught.value.code == 2
