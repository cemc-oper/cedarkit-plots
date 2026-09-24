---
mystnb:
  execution_mode: 'off'
---

# 全球地图

全球预设可直接用于单 Chart，也可以拆分为 `global_chart()` 后装入自定义 Panel。
示例中的经纬度场由项目合成数据工具生成。

```python
import cartopy.crs as ccrs
from cedarkit.plots import Panel
from cedarkit.plots.templates import global_map
from cedarkit.plots.testing import global_temperature_field, temperature_style

field = global_temperature_field()
with Panel(template=global_map()) as panel:
    chart = panel.add_chart(id="temperature")
    layer = chart.contourf(field, style=temperature_style(),
                           data_crs=ccrs.PlateCarree(), subplots="all")
    chart.set_title("Global synthetic temperature")
    chart.colorbar(layer, label="°C")
    panel.save("global-temperature.png")
```

数据坐标系通过 `data_crs` 明确传入，与地图显示投影和区域范围配置相互独立。
