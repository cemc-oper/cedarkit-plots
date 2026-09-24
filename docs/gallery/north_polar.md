---
mystnb:
  execution_mode: 'off'
---

# 北极地图

`north_polar()` 只提供北极区域、投影和地图子图设置。调用方仍需创建 Chart 并
选择绘图方法、数据坐标系和样式。

```python
import cartopy.crs as ccrs
from cedarkit.plots import Panel
from cedarkit.plots.templates import north_polar
from cedarkit.plots.testing import north_polar_temperature_field, temperature_style

field = north_polar_temperature_field()
with Panel(template=north_polar()) as panel:
    chart = panel.add_chart(id="temperature")
    layer = chart.contourf(field, style=temperature_style(),
                           data_crs=ccrs.PlateCarree(), subplots="all")
    chart.set_title("North Polar synthetic temperature")
    chart.colorbar(layer, label="°C")
    panel.save("north-polar-temperature.png")
```

如果使用自定义 `Domain`，要分别声明域范围的 CRS、显示投影和字段 `data_crs`。
