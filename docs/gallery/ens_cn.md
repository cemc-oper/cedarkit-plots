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

# 集合预报中国区域（`EnsCNMapTemplate`）

`EnsCNMapTemplate` 是用于集合预报多成员展示的特殊模板，
一次性创建 15 个 chart（CTL + 14 个扰动成员）。
开启 `enable_max=True` 后再追加一个 MAX chart。

```{code-cell} python
import pandas as pd

from cedarkit.plots.chart import Panel
from cedarkit.plots.domains import EnsCNMapTemplate
from cedarkit.plots.testing import (
    ens_cn_temperature_fields,
    ens_cn_temperature_fields_with_max,
    temperature_style,
)

start_time = pd.Timestamp("2024-11-09 00:00:00")
forecast_time = pd.Timedelta("24h")
t_style = temperature_style()
```

## 15 个集合成员

```{code-cell} python
fields = ens_cn_temperature_fields()
print(f"member count: {len(fields)}")

domain = EnsCNMapTemplate()
panel = Panel(domain=domain)
panel.plot(fields, style=t_style)
domain.set_title(
    panel=panel,
    graph_name="2m Temperature (°C)",
    system_name="EPS demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
domain.add_colorbar(panel=panel, style=t_style)
panel.show()
```

## 15 个成员 + MAX

```{code-cell} python
fields_max = ens_cn_temperature_fields_with_max()
print(f"member + MAX count: {len(fields_max)}")

domain = EnsCNMapTemplate(enable_max=True)
panel = Panel(domain=domain)
panel.plot(fields_max, style=t_style)
domain.set_title(
    panel=panel,
    graph_name="2m Temperature (°C)",
    system_name="EPS demo",
    start_time=start_time,
    forecast_time=forecast_time,
)
domain.add_colorbar(panel=panel, style=t_style)
panel.show()
```
