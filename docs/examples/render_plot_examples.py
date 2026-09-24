"""可选导出固定合成样例 PNG；默认写到仓库外的临时目录。

可执行文档会在 Sphinx 构建时动态渲染并显示图像。本脚本仅用于单独导出文件；字段
由 ``cedarkit.plots.testing`` 生成，不访问业务数据或远程服务。在仓库根目录运行
``uv run --extra test``。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib as mpl
import numpy as np
import xarray as xr

from cedarkit.plots import Panel
from cedarkit.plots.config import LayoutSpec
from cedarkit.plots.quickplot import facet, plot
from cedarkit.plots.style import StyleRegistry
from cedarkit.plots.templates import east_asia
from cedarkit.plots.testing import east_asia_temperature_field, east_asia_wind_fields


def _fields():
    # The source grid spans both the main map and the southern inset.
    temperature = east_asia_temperature_field(
        coords=(np.arange(70.0, 141.0, 1.0), np.arange(0.0, 61.0, 1.0)),
    ).assign_attrs(
        temperature_kind="absolute",
        standard_name="air_temperature",
        cemc_name="t2m",
    )
    u, v = east_asia_wind_fields()
    return temperature, u, v


def render(output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    mpl.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "figure.dpi": 100,
        "savefig.dpi": 120,
    })
    temperature, u, v = _fields()
    registry = StyleRegistry.default(profile="generic")
    generic_temperature = registry.get_style("t", data=temperature)

    # Direct Panel/Chart configuration, with no map or template dependency.
    direct = Panel(layout=LayoutSpec(rows=1, columns=2, figsize=(10, 4)))
    try:
        cemc_chart = direct.add_chart(id="cemc")
        cemc_layer = cemc_chart.contourf(
            temperature, style="cemc.t2m:cn_summer", id="temperature",
        )
        cemc_chart.set_title("CEMC temperature")
        cemc_chart.colorbar(cemc_layer, label="°C")

        generic_chart = direct.add_chart(id="generic")
        generic_layer = generic_chart.contourf(
            temperature, style=generic_temperature, id="temperature",
        )
        generic_chart.set_title("Generic temperature")
        generic_chart.colorbar(generic_layer, label="°C")
        direct.save(output / "direct-cemc-generic.png")
    finally:
        direct.close()

    # Map subplots are selected by a value-only preset; layer targets are explicit.
    map_panel = Panel(template=east_asia(with_inset=True))
    try:
        chart = map_panel.add_chart(id="weather")
        temperature_layer = chart.contourf(
            temperature,
            style="cemc.t2m:cn_summer",
            id="temperature",
            subplots="all",
            data_crs=ccrs.PlateCarree(),
        )
        chart.barbs(
            u,
            v,
            style="cemc.wind:cn",
            id="wind",
            subplots="main",
            data_crs=ccrs.PlateCarree(),
            vector_basis="earth",
        )
        chart.set_title("East Asia: 2 m temperature and 10 m wind")
        chart.colorbar(temperature_layer, label="°C")
        map_panel.save(output / "east-asia-main-inset.png")

        stable_chart = map_panel.charts["weather"]
        stable_layer = stable_chart.layers["temperature"]
        map_panel.apply_template(east_asia(with_inset=False))
        map_panel.render()
        assert map_panel.charts["weather"] is stable_chart
        assert stable_chart.layers["temperature"] is stable_layer
        map_panel.apply_template(east_asia(with_inset=True))
        map_panel.save(output / "east-asia-template-switch.png")
        assert map_panel.charts["weather"] is stable_chart
        assert stable_chart.layers["temperature"] is stable_layer
    finally:
        map_panel.close()

    # The quickplot facet helper keeps real member IDs and shares the scale.
    cube = xr.concat(
        [temperature, temperature + 4, temperature + 8],
        dim=xr.IndexVariable("number", [0, 1, 7]),
    )
    cube.attrs = dict(temperature.attrs)
    with facet(
        cube,
        dim="number",
        ids=["ctl", "mem01", "mem07"],
        roles=["control", "member", "member"],
        style="cemc.t2m:cn_summer",
        units="degC",
        level_policy="shared",
        colorbar_label="°C",
        layout=LayoutSpec(rows=1, columns=3, figsize=(12, 4)),
        output=output / "facet-shared-scale.png",
    ) as result:
        assert tuple(result.panel.charts) == ("ctl", "mem01", "mem07")

    # Explicit unit preparation is also exercised through the public quickplot helper.
    kelvin = temperature.copy(data=temperature + 273.15).assign_attrs(
        units="K", temperature_kind="absolute", cemc_name="t2m",
        standard_name="air_temperature",
    )
    with plot(
        kelvin,
        units="degC",
        title="Prepared 2 m temperature",
        colorbar_label="°C",
        output=output / "quickplot-temperature.png",
    ) as result:
        assert result.conversions[0][0].applied

    return sorted(output.glob("*.png"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, nargs="?", default=Path("/tmp/cedarkit-plots-docs"),
        help="独立 PNG 输出目录（默认：/tmp/cedarkit-plots-docs）",
    )
    args = parser.parse_args()
    for path in render(args.output):
        print(f"{path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
