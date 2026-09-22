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

# 快速上手

下面用内置 CEMC 样式绘制合成温度场。示例采用 XY 坐标，不需要下载地图资源。

```{code-cell} python
import numpy as np
import xarray as xr
from cedarkit.plots import quickplot

x, y = np.meshgrid(np.linspace(-1, 1, 30), np.linspace(-1, 1, 24))
temperature = xr.DataArray(
    273.15 + 15 + 20*x + 8*np.sin(3*y), dims=("y", "x"),
    attrs={"units": "K", "temperature_kind": "absolute",
           "cemc_name": "t2m", "standard_name": "air_temperature"},
)
with quickplot.plot(temperature, units="degC", title="2m temperature",
                    colorbar_label="degC", output="temperature.png") as result:
    print(result.conversions[0][0])
    # result.panel / result.chart / result.layer 是可继续配置和更新的句柄。
```

显式 units= 先校验并准备数据，再匹配样式。输入字段保持 K，不被修改。
成功返回的 Panel 保持打开；with 退出时关闭。若不使用 with，请调用 result.close()。
不传 output 时仍完成渲染，可通过 result.panel.show() 主动显示。

风羽用 `quickplot.barbs(u, v)`，成员图用 `quickplot.facet(data, dim="number")`。
完整的单位、角色、共享色阶和模板用法见 [快绘教程](../tutorials/quickplot.md)。
需要叠加多个图层时，继续使用返回的 Chart，或直接创建 Panel/Chart；无需另一套渲染 API。
