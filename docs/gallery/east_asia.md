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

# 东亚：主图与南海附图

EastAsia 展示预设为一个已创建的 Chart 提供主地图及可选南海附图。温度层可以
指向全部子图，风羽层只绘制到主图。以下固定合成场在文档构建时执行，图像直接
显示在页面中，不写入仓库文件。风向杆每隔约 3° 取样一次，以减少对底图的遮挡。

```{code-cell} python
%matplotlib inline
import matplotlib as mpl
import numpy as np
import cartopy.crs as ccrs
from IPython.display import display
from cedarkit.plots import Panel
from cedarkit.plots.templates import east_asia
from cedarkit.plots.testing import east_asia_temperature_field, east_asia_wind_fields

mpl.rcParams["font.family"] = "DejaVu Sans"

temperature = east_asia_temperature_field(
    coords=(np.arange(70, 141, 1), np.arange(0, 61, 1)),
).assign_attrs(
    temperature_kind="absolute",
    standard_name="air_temperature",
    cemc_name="t2m",
)
wind_longitudes = np.r_[np.arange(70.0, 140.0, 3.0), 140.0]
wind_latitudes = np.r_[np.arange(15.0, 55.0, 3.0), 55.0]
u, v = east_asia_wind_fields(coords=(wind_longitudes, wind_latitudes))

with Panel(template=east_asia(with_inset=True)) as panel:
    chart = panel.add_chart(id="weather")
    layer = chart.contourf(
        temperature,
        style="cemc.t2m:cn_summer",
        data_crs=ccrs.PlateCarree(),
        subplots="all",
    )
    chart.barbs(
        u,
        v,
        style="cemc.wind:cn",
        data_crs=ccrs.PlateCarree(),
        vector_basis="earth",
        subplots="main",
    )
    chart.set_title("2 m temperature and 10 m wind")
    chart.colorbar(layer, label="°C")
    display(panel.render())

    stable_chart = panel.charts["weather"]
    stable_layer = stable_chart.layers[layer.id]
    panel.apply_template(east_asia(with_inset=False))
    display(panel.render())
    assert panel.charts["weather"] is stable_chart
    assert stable_chart.layers[layer.id] is stable_layer
```

模板只提供展示配置；数据、Chart 和图层由调用方建立。第二次渲染关闭附图，验证
模板切换后内容句柄仍保持稳定。
