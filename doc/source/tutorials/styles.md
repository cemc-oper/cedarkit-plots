---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 样式（Style）

CEMC 的 20 个样式、37 个变体已内置，无需安装 cedar-graph。
等级、标签、高亮和风羽参数由样式声明；产品负责选择变体和组合图层。
通用样式位于 `generic` profile，需由调用方显式选择。温度数据应先准备为 degC，样式不转换数据。

## 填色、等值线与风羽

下面使用合成数据和 XY 坐标展示样式，无需下载地图资源。

```{code-cell} python
%matplotlib inline
import matplotlib as mpl
import numpy as np
import xarray as xr
from IPython.display import display
from cedarkit.plots import Panel
from cedarkit.plots.style import StyleRegistry
from cedarkit.plots.units import prepare_field

mpl.rcParams["font.family"] = "DejaVu Sans"

x, y = np.meshgrid(np.linspace(-1, 1, 30), np.linspace(-1, 1, 24))
def field(values, units):
    return xr.DataArray(values, dims=("y", "x"), attrs={"units": units})

temperature = prepare_field(
    field(16 + 25 * x + 8 * np.sin(3 * y), "degC"),
    temperature_kind="absolute",
).field
height = field(560 + 40 * x + 15 * y, "dagpm")
u, v = field(8 + 4 * y, "m/s"), field(3 + 4 * x, "m/s")
registry = StyleRegistry.default()

with Panel() as panel:
    chart = panel.add_chart(id="weather")
    fill = chart.contourf(temperature, style="cemc.t2m:cn_summer")
    chart.contour(height, style="cemc.h_500:cn_dagpm")
    chart.barbs(u, v, style="cemc.wind:cn")
    chart.set_title("CEMC temperature, height and wind")
    chart.colorbar(fill, label="degC")
    display(panel.render())
```

温度夏/冬变体由调用者选择。500 hPa 高度标签为红色，588 线为黑色加粗。
`generic.t` 是显式通用样式，保留动态 step=4，不代替业务温度样式。

## 自定义离散颜色

显式列表可以完整声明 under、内部区间、over：

```{code-cell} python
from cedarkit.plots.palette import get_named_color
from cedarkit.plots.style import ContourStyle

rain_style = ContourStyle(
    levels=[5, 25, 50, 100], fill=True, extend="both",
    colors=[get_named_color(name) for name in
            ["transparent", "PaleGreen2", "ForestGreen", "Blue", "Magenta"]],
)
with Panel() as panel:
    chart = panel.add_chart()
    layer = chart.contourf(field(50 + 60 * x, "mm"), style=rain_style)
    chart.colorbar(layer, label="mm")
    display(panel.render())
```

这里三个内部区间分别为 `[5,25)`、`[25,50)`、`[50,100)`，低值透明。
完整 CEMC 降水样式可直接用 `registry.get_style("rain:cn", metadata={"units": "mm", "accumulation_hours": 24})`。
风切变 `shr` 的等级由产品计算后通过 `overrides={"levels": levels}` 提供，
可用同一组等级构建填色和线样式。单位显式准备见 [单位边界](./units.md)；累计时段必须由数据流程提供。

## 显式选择通用 profile

通用样式不作为识别到某个 CEMC 要素后的隐式回退。通过注册表明确选择
`generic.t`，然后将返回的样式绑定到普通 Chart：

```{code-cell} python
from IPython.display import display
from cedarkit.plots import Panel
from cedarkit.plots.style import StyleRegistry

generic = StyleRegistry.default(profile="generic")
generic_temperature = generic.get_style("t", data=temperature)
with Panel() as panel:
    chart = panel.add_chart(id="generic-temperature")
    layer = chart.contourf(temperature, style=generic_temperature)
    chart.set_title("Generic temperature")
    chart.colorbar(layer, label="degC")
    display(panel.render())
```

`StyleRegistry` 根据当前 profile 解析未限定 profile 的样式 ID；也可写成完整
ID `generic.t:default`。核心图层要求显式 Style 或样式 ID，不接受自动猜测。
