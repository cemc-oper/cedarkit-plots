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

# 使用合成数据

`cedarkit-plots` 在生产环境中通常配合 `reki` 读取真实
GRIB2 数据，但在文档与单元测试里我们希望任何环境都能直接画出
图来。{mod}`cedarkit.plots.testing` 子包就为此而生：里面定义了
一组 lat/lon 网格上的解析式合成场，本文档里所有可执行示例
都使用它们。

集成测试 (`tests/integration/`) 与本文档使用的是同一份函数，
所以"文档里看到的画图行为"与"CI 中跑过的画图行为"是一致的。

## 合成场一览

每个区域提供一组配套字段：温度、海平面气压、风场、必要时
还有降水。下面把东亚区域的几个字段画出来，看看合成数据长什么样。

```{code-cell} python
import matplotlib.pyplot as plt

from cedarkit.plots.testing import (
    east_asia_temperature_field,
    east_asia_pressure_field,
    east_asia_precipitation_field,
)

t = east_asia_temperature_field()
p = east_asia_pressure_field()
rain = east_asia_precipitation_field()

fig, axes = plt.subplots(1, 3, figsize=(14, 3))
t.plot(ax=axes[0]); axes[0].set_title("Temperature (°C)")
p.plot(ax=axes[1]); axes[1].set_title("MSLP (hPa)")
rain.plot(ax=axes[2]); axes[2].set_title("24h precip (mm)")
fig.tight_layout()
plt.show()
```

## 字段速查表

| 函数 | 区域与分辨率 | 单位 | 备注 |
|------|------------|------|------|
| {func}`~cedarkit.plots.testing.east_asia_temperature_field` | 70°E–140°E, 15°N–55°N, 1° | °C | 南暖北冷 + 经向波动 |
| {func}`~cedarkit.plots.testing.east_asia_pressure_field`    | 同上 | hPa | 区域中心一个低压 |
| {func}`~cedarkit.plots.testing.east_asia_wind_fields`       | 同上 | m/s | 西风带 + 气旋环流 |
| {func}`~cedarkit.plots.testing.east_asia_precipitation_field` | 同上 | mm | 多个降水中心 |
| {func}`~cedarkit.plots.testing.europe_asia_temperature_field` | 20°E–170°E, 0°N–70°N, 5° | °C | |
| {func}`~cedarkit.plots.testing.europe_asia_pressure_field`    | 同上 | hPa | |
| {func}`~cedarkit.plots.testing.europe_asia_wind_fields`       | 同上 | m/s | |
| {func}`~cedarkit.plots.testing.global_temperature_field`     | 全球 5° | °C | 赤道暖、两极冷 |
| {func}`~cedarkit.plots.testing.global_pressure_field`        | 同上 | hPa | 副热带高压带 + 极地低压 |
| {func}`~cedarkit.plots.testing.global_wind_fields`           | 同上 | m/s | 信风 + 西风 |
| {func}`~cedarkit.plots.testing.north_polar_temperature_field` | 北半球 5° | °C | |
| {func}`~cedarkit.plots.testing.north_polar_pressure_field`    | 同上 | hPa | 极涡 |
| {func}`~cedarkit.plots.testing.north_polar_wind_fields`       | 同上 | m/s | 极涡环流 |
| {func}`~cedarkit.plots.testing.ens_cn_temperature_fields`     | 73°E–133°E, 16°N–56°N, 5° | °C | 15 个集合成员 |
| {func}`~cedarkit.plots.testing.ens_cn_temperature_fields_with_max` | 同上 | °C | 15 + MAX |

## 自定义网格

每个函数都接受 `coords` 参数（一对 ``(lons, lats)`` 数组），
便于在更高/更低分辨率上生成场。例如把东亚分辨率提高到 0.5°：

```{code-cell} python
import numpy as np

from cedarkit.plots.testing.synthetic_data import east_asia_temperature_field

lons = np.arange(70.0, 140.0 + 0.5, 0.5)
lats = np.arange(15.0, 55.0 + 0.5, 0.5)
hi_res = east_asia_temperature_field((lons, lats))
hi_res.shape
```
