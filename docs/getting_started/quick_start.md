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

# 快速上手

下面这段代码用 `cedarkit-plots` 在东亚地图模板上画一张
2 米温度填充图。绘图所需的合成数据来自
{mod}`cedarkit.plots.testing`。

```{code-cell} python
import pandas as pd

from cedarkit.plots.chart import Panel
from cedarkit.plots.domains import EastAsiaMapTemplate
from cedarkit.plots.testing import (
    east_asia_temperature_field,
    temperature_style,
)

# 1. 准备数据与样式
field = east_asia_temperature_field()
style = temperature_style()

# 2. 选择一个地图模板，构造绘图面板
domain = EastAsiaMapTemplate()
panel = Panel(domain=domain)

# 3. 把数据画到面板上
panel.plot(field, style=style)

# 4. 添加标题和色标
panel.set_title(
    graph_name="2m Temperature (°C)",
    system_name="cedarkit-plots demo",
    start_time=pd.Timestamp("2024-11-09 00:00:00"),
    forecast_time=pd.Timedelta("24h"),
)
panel.add_colorbar(style=style)

# 5. 显示（在脚本里也可以用 panel.save("out.png")）
panel.show()
```

整张图由四个对象协作完成：

- 数据 `field` 是一个二维 {class}`xarray.DataArray`；
- 样式 `style` 描述等值线层级、色表、是否填充；
- 模板 `domain` 决定地图投影、坐标范围、标题与色标位置；
- 面板 `panel` 把上述对象组合起来，最后产出一张 matplotlib 图。

后续教程会从这四个对象出发，分别介绍如何替换合成数据、
切换地图模板、定制样式与色表。
