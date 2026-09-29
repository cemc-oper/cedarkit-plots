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

# 北极地图

北极预设声明北半球区域、North Polar Stereo 投影和经纬网格。示例使用固定的
2 米温度合成场，并在文档页面中直接显示绘图结果。模板保持近圆投影比例，将色标
放在地图框右侧，默认不显示地图说明。
经度标签显示在圆形地图边界与主图矩形边框之间的留白中。

```{code-cell} python
%matplotlib inline
import matplotlib as mpl
import cartopy.crs as ccrs
from IPython.display import display
from cedarkit.plots import Panel
from cedarkit.plots.templates import north_polar
from cedarkit.plots.testing import north_polar_temperature_field, temperature_style

mpl.rcParams["font.family"] = "DejaVu Sans"

field = north_polar_temperature_field()
with Panel(template=north_polar()) as panel:
    chart = panel.add_chart(id="temperature")
    layer = chart.contourf(
        field,
        style=temperature_style(),
        data_crs=ccrs.PlateCarree(),
        subplots="all",
    )
    chart.set_title("North Polar 2 m temperature")
    chart.colorbar(layer, label="°C")
    display(panel.render())
```

自定义区域时，需分别设置 `Domain` 的范围 CRS、显示投影和字段的 `data_crs`。
