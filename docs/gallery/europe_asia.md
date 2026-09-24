---
mystnb:
  execution_mode: 'off'
---

# 欧亚地图

`europe_asia()` 返回单 Chart 的 Panel 展示预设。区域或附图需要调整时，可将
区域/底图配置作为工厂参数传入；外层 Panel 布局仍由调用方决定。

```python
import cartopy.crs as ccrs
from cedarkit.plots import Panel
from cedarkit.plots.templates import europe_asia
from cedarkit.plots.testing import europe_asia_temperature_field
from cedarkit.plots.testing import temperature_style

field = europe_asia_temperature_field()
with Panel(template=europe_asia()) as panel:
    chart = panel.add_chart(id="temperature")
    layer = chart.contourf(field, style=temperature_style(),
                           data_crs=ccrs.PlateCarree(), subplots="all")
    chart.set_title("Europe and Asia synthetic temperature")
    chart.colorbar(layer, label="°C")
    panel.save("europe-asia.png")
```

调用方可使用相同逻辑 Chart 与图层替换区域预设，然后通过 `Panel.render()` 重绘。
