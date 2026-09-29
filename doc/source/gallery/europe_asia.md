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

# 欧亚地图

此示例在欧亚 Lambert Conformal 投影上绘制固定的 2 米温度合成场。数据与
`Chart` 由调用方创建，模板提供区域、投影和底图配置，并将色标放在主图右侧；
默认不显示右下角地图说明。
主图外缘与矩形边框之间保留少量留白，避免轮廓与边框相接。

```{code-cell} python
%matplotlib inline
import matplotlib as mpl
import cartopy.crs as ccrs
from IPython.display import display
from cedarkit.plots import Panel
from cedarkit.plots.templates import europe_asia
from cedarkit.plots.testing import europe_asia_temperature_field, temperature_style

mpl.rcParams["font.family"] = "DejaVu Sans"

field = europe_asia_temperature_field()
with Panel(template=europe_asia()) as panel:
    chart = panel.add_chart(id="temperature")
    layer = chart.contourf(
        field,
        style=temperature_style(),
        data_crs=ccrs.PlateCarree(),
        subplots="all",
    )
    chart.set_title("2 m temperature over Europe and Asia")
    chart.colorbar(layer, label="°C")
    display(panel.render())
```

调用方可替换合成场或传入自定义 `Domain`，然后通过 `Panel.render()` 重新绘制。
