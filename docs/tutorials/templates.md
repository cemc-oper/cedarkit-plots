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

# 地图模板（MapTemplate）

`cedarkit.plots.domains` 内置了几种常用区域的预设模板，
封装了投影、范围、标题与色标位置等布局信息。本节列出每种模板的
最简使用方式，更完整的样例请见
{doc}`../gallery/index`。

```{code-cell} python
import pandas as pd

start_time = pd.Timestamp("2024-11-09 00:00:00")
forecast_time = pd.Timedelta("24h")
```

## 东亚

```{code-cell} python
from cedarkit.plots.chart import Panel
from cedarkit.plots.domains import EastAsiaMapTemplate
from cedarkit.plots.testing import (
    east_asia_temperature_field,
    temperature_style,
)

style = temperature_style()
panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(east_asia_temperature_field(), style=style)
panel.set_title(
    graph_name="2m Temperature (°C)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=style)
panel.show()
```

`EastAsiaMapTemplate` 自带一个右下角的中国南海副图，可以通过
`with_sub_area=False` 关闭：

```{code-cell} python
panel = Panel(domain=EastAsiaMapTemplate(with_sub_area=False))
panel.plot(east_asia_temperature_field(), style=style)
panel.set_title(
    graph_name="2m Temperature (°C, 不带副图)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=style)
panel.show()
```

## 中国子区域 (`CnAreaMapTemplate`)

需要画到具体的省/区时，使用 `CnAreaMapTemplate` 并传一个
`AreaRange`：

```{code-cell} python
from cedarkit.plots.domains import CnAreaMapTemplate
from cedarkit.plots.types import AreaRange

panel = Panel(
    domain=CnAreaMapTemplate(area=AreaRange.from_tuple((108, 137, 37, 55))),
)
panel.plot(east_asia_temperature_field(), style=style)
panel.set_title(
    graph_name="NorthEast 2m Temperature (°C)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=style)
panel.show()
```

## 全球

```{code-cell} python
from cedarkit.plots.domains import GlobalMapTemplate
from cedarkit.plots.testing import global_temperature_field

panel = Panel(domain=GlobalMapTemplate())
panel.plot(global_temperature_field(), style=style)
panel.set_title(
    graph_name="Global 2m Temperature (°C)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=style)
panel.show()
```

## 北极

```{code-cell} python
from cedarkit.plots.domains import NorthPolarMapTemplate
from cedarkit.plots.testing import north_polar_temperature_field

panel = Panel(domain=NorthPolarMapTemplate())
panel.plot(north_polar_temperature_field(), style=style)
panel.set_title(
    graph_name="Polar 2m Temperature (°C)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=style)
panel.show()
```

## 集合预报中国区域 (`EnsCNMapTemplate`)

`EnsCNMapTemplate` 一次创建 15 个 chart（CTL + 14 个扰动成员），
对应输入也是一个长度 15 的 `DataArray` 列表；
开启 `enable_max=True` 后会变成 16 个 chart（再加 MAX）。

```{code-cell} python
from cedarkit.plots.domains import EnsCNMapTemplate
from cedarkit.plots.testing import ens_cn_temperature_fields

fields = ens_cn_temperature_fields()

domain = EnsCNMapTemplate()
panel = Panel(domain=domain)
panel.plot(fields, style=style)
domain.set_title(
    panel=panel,
    graph_name="2m Temperature (°C)",
    system_name="EPS demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
domain.add_colorbar(panel=panel, style=style)
panel.show()
```
