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

# 全球（`GlobalMapTemplate`）

```{code-cell} python
import pandas as pd

from cedarkit.plots.chart import Panel
from cedarkit.plots.domains import GlobalMapTemplate
from cedarkit.plots.testing import (
    global_temperature_field,
    global_pressure_field,
    global_wind_fields,
    temperature_style,
    pressure_contour_style,
    wind_barb_style,
    wind_barb_style_black,
)

start_time = pd.Timestamp("2024-11-09 00:00:00")
forecast_time = pd.Timedelta("24h")

t_style = temperature_style()
p_style = pressure_contour_style()

t = global_temperature_field()
p = global_pressure_field()
u, v = global_wind_fields()
```

## 温度填充

```{code-cell} python
panel = Panel(domain=GlobalMapTemplate())
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

## 海平面气压等值线

```{code-cell} python
panel = Panel(domain=GlobalMapTemplate())
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
panel = Panel(domain=GlobalMapTemplate())
panel.plot([[u, v]], style=wind_barb_style())
panel.set_title(
    graph_name="10m Wind (m/s)",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.show()
```

## 温度 + 海平面气压组合

```{code-cell} python
panel = Panel(domain=GlobalMapTemplate())
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

## 温度 + 风羽组合

```{code-cell} python
panel = Panel(domain=GlobalMapTemplate())
panel.plot(t, style=t_style)
panel.plot([[u, v]], style=wind_barb_style_black())
panel.set_title(
    graph_name="2m Temperature (°C) & 10m Wind",
    system_name="cedarkit-plots demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
panel.add_colorbar(style=t_style)
panel.show()
```
