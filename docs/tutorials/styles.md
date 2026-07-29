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

`cedarkit-plots` 把"等值线层级、色表、是否填充"这些绘图参数集中在
{mod}`cedarkit.plots.style` 中的样式对象里。常用的是
{class}`~cedarkit.plots.style.ContourStyle` 和
{class}`~cedarkit.plots.style.BarbStyle`。

下面分别画一张"温度填充 + 海平面气压等值线 + 风羽"的组合图，
逐步演示样式的搭配。

```{code-cell} python
import pandas as pd

start_time = pd.Timestamp("2024-11-09 00:00:00")
forecast_time = pd.Timedelta("24h")
```

## 起手：填充图

```{code-cell} python
from cedarkit.plots.chart import Panel
from cedarkit.plots.domains import EastAsiaMapTemplate
from cedarkit.plots.testing import (
    east_asia_temperature_field,
    temperature_style,
)

t_style = temperature_style()
panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(east_asia_temperature_field(), style=t_style)
panel.set_title(
    graph_name="2m Temperature (°C)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=t_style)
panel.show()
```

## 叠加等值线

把一张等值线（`fill=False` 的 `ContourStyle`）叠在填充层之上即可。
预设里 {func}`cedarkit.plots.testing.pressure_contour_style`
返回的就是这种样式。

```{code-cell} python
from cedarkit.plots.testing import (
    east_asia_pressure_field,
    pressure_contour_style,
)

p_style = pressure_contour_style()
panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(east_asia_temperature_field(), style=t_style)
panel.plot(east_asia_pressure_field(), style=p_style)
panel.set_title(
    graph_name="MSLP (hPa) & 2m Temperature (°C)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=t_style)
panel.show()
```

## 再叠加风羽

风羽用 {class}`~cedarkit.plots.style.BarbStyle`，调用
`panel.plot([[u, v]], style=barb_style)`。注意 ``u, v`` 要包成
``[[u, v]]`` 这种嵌套列表，外层对应每个 chart，内层对应该 chart 上的
``(u, v)`` 二元组。

```{code-cell} python
from cedarkit.plots.testing import (
    east_asia_wind_fields,
    wind_barb_style_black,
)

u, v = east_asia_wind_fields()
barb_style = wind_barb_style_black()

panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(east_asia_temperature_field(), style=t_style)
panel.plot(east_asia_pressure_field(), style=p_style)
panel.plot([[u, v]], style=barb_style, layer=[0])
panel.set_title(
    graph_name="2m Temperature (°C) + MSLP + 10m Wind",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=t_style)
panel.show()
```

## 自己定制样式

预设只是开场白。下面演示如何手工构造一个等值线样式：把降水的
等级改成 `[5, 25, 50, 100]`，从 NCL 命名颜色拼一个新色表。

```{code-cell} python
import numpy as np

from cedarkit.plots.colormap import generate_colormap_using_ncl_colors
from cedarkit.plots.style import ContourStyle
from cedarkit.plots.testing import east_asia_precipitation_field

custom_cmap = generate_colormap_using_ncl_colors(
    ["transparent", "PaleGreen2", "ForestGreen", "Blue", "Magenta"],
    name="custom_rain",
)
custom_style = ContourStyle(
    colors=custom_cmap,
    levels=np.array([5, 25, 50, 100]),
    fill=True,
)

panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(east_asia_precipitation_field(), style=custom_style)
panel.set_title(
    graph_name="Custom precip levels",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=custom_style)
panel.show()
```
