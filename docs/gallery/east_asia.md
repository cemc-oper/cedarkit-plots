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

# 东亚（`EastAsiaMapTemplate`）

```{code-cell} python
import pandas as pd

from cedarkit.plots.chart import Panel
from cedarkit.plots.domains import EastAsiaMapTemplate
from cedarkit.plots.testing import (
    east_asia_temperature_field,
    east_asia_pressure_field,
    east_asia_wind_fields,
    east_asia_precipitation_field,
    temperature_style,
    precipitation_style,
    pressure_contour_style,
    wind_barb_style,
    wind_barb_style_black,
)

start_time = pd.Timestamp("2024-11-09 00:00:00")
forecast_time = pd.Timedelta("24h")

t_style = temperature_style()
rain_style = precipitation_style()
p_style = pressure_contour_style()
barb_style_blue = wind_barb_style()
barb_style_black = wind_barb_style_black()

t = east_asia_temperature_field()
p = east_asia_pressure_field()
u, v = east_asia_wind_fields()
rain = east_asia_precipitation_field()
```

## 温度填充

```{code-cell} python
panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(t, style=t_style)
panel.set_title(
    graph_name="2m Temperature (°C)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=t_style)
panel.show()
```

## 24 小时降水填充

```{code-cell} python
panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(rain, style=rain_style)
panel.set_title(
    graph_name="24h Precipitation (mm)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=rain_style)
panel.show()
```

## 海平面气压等值线

```{code-cell} python
panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(p, style=p_style)
panel.set_title(
    graph_name="MSLP (hPa)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.show()
```

## 10 米风场风羽

```{code-cell} python
panel = Panel(domain=EastAsiaMapTemplate())
panel.plot([[u, v]], style=barb_style_blue, layer=[0])
panel.set_title(
    graph_name="10m Wind (m/s)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.show()
```

## 温度填充 + 风羽叠加

```{code-cell} python
panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(t, style=t_style)
panel.plot([[u, v]], style=barb_style_black, layer=[0])
panel.set_title(
    graph_name="2m Temperature (°C) & 10m Wind",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=t_style)
panel.show()
```

## 温度填充 + 海平面气压等值线

```{code-cell} python
panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(t, style=t_style)
panel.plot(p, style=p_style)
panel.set_title(
    graph_name="MSLP (hPa) & 2m Temperature (°C)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=t_style)
panel.show()
```

## 关闭右下角副图

```{code-cell} python
panel = Panel(domain=EastAsiaMapTemplate(with_sub_area=False))
panel.plot(t, style=t_style)
panel.set_title(
    graph_name="2m Temperature (°C, 不带副图)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=t_style)
panel.show()
```
