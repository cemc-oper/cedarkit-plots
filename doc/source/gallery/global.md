---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.4
mystnb:
  execution_mode: 'force'
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 全球地图

全球预设可直接用于单 Chart，也可以拆分 `global_chart()` 后装入自定义 Panel。
以下单元格在居中经度为 80° 的 Plate Carrée 投影上绘制全球温度合成场。地图框保持
2:1 横纵比例，色标单独放置在主图右侧，默认不显示地图说明。

```{code-cell} python
%matplotlib inline
import matplotlib as mpl
import cartopy.crs as ccrs
from IPython.display import display
from cedarkit.plots import Panel
from cedarkit.plots.templates import global_map
from cedarkit.plots.testing import global_temperature_field, temperature_style

mpl.rcParams["font.family"] = "DejaVu Sans"

field = global_temperature_field()
with Panel(template=global_map()) as panel:
    chart = panel.add_chart(id="temperature")
    layer = chart.contourf(
        field,
        style=temperature_style(),
        data_crs=ccrs.PlateCarree(),
        subplots="all",
    )
    chart.set_title("Global 2 m temperature")
    chart.colorbar(layer, label="°C")
    display(panel.render())
```

数据坐标系通过 `data_crs` 显式传入，与地图显示投影和区域范围配置相互独立。
