---
mystnb:
  execution_mode: 'off'
---

# 直接配置、地图子图与展示预设

`PanelTemplate` 和 `ChartTemplate` 是值对象形式的可选预设。它们为现有内容
提供布局和子图配置，不创建 Chart 或图层。每个 Chart 都可以直接通过配置值
建立；两个入口使用同一解析和渲染路径。

## 不使用模板的 XY 图

下面的确定性示例可由仓库脚本完整运行：
[`render_plot_examples.py`](../examples/render_plot_examples.py)。

```python
from cedarkit.plots import Panel
from cedarkit.plots.testing import east_asia_temperature_field

field = east_asia_temperature_field().assign_attrs(temperature_kind="absolute")
panel = Panel()
chart = panel.add_chart(id="temperature")
layer = chart.contourf(field, style="cemc.t2m:cn_summer")
chart.set_title("2 m temperature (°C)")
chart.colorbar(layer, label="°C")
try:
    panel.save("temperature-xy.png")
finally:
    panel.close()
```

更多网格、槽位和配置字段见 {doc}`../api/chart`。

## 地图主图、南海附图与目标选择

```python
import cartopy.crs as ccrs
import numpy as np

from cedarkit.plots import Panel
from cedarkit.plots.templates import east_asia
from cedarkit.plots.testing import east_asia_temperature_field, east_asia_wind_fields

temperature = east_asia_temperature_field(
    coords=(np.arange(70, 141, 1), np.arange(0, 61, 1)),
).assign_attrs(temperature_kind="absolute")
u, v = east_asia_wind_fields()
panel = Panel(template=east_asia(with_inset=True))
chart = panel.add_chart(id="weather")
temperature_layer = chart.contourf(
    temperature,
    style="cemc.t2m:cn_summer",
    subplots="all",
    data_crs=ccrs.PlateCarree(),
)
chart.barbs(
    u, v,
    style="cemc.wind:cn",
    subplots="main",
    data_crs=ccrs.PlateCarree(),
    vector_basis="earth",
)
chart.set_title("CEMC 2 m temperature and 10 m wind")
chart.colorbar(temperature_layer, label="°C")
try:
    panel.save("east-asia-main-inset.png")
finally:
    panel.close()
```

`subplots="all"` 会将温度层绘制到当前模板声明的主图和附图；字段范围必须覆盖
这两个区域。风羽层只指向 `main`。也可以传一个或多个固定子图 ID。地图数据必须给出 `data_crs`；向量
分量必须分别传入，且坐标和单位相容。

## 配置对象与模板切换

XY 图不依赖地图模板。定制布局可直接传入 `LayoutSpec`，或在建图后通过
`Panel.configure()` 更新展示配置。地图区域预设包括 `east_asia()`、
`cn_area()`、`europe_asia()`、`global_map()`、`global_area()` 和
`north_polar()`；对应的 `*_chart()` 工厂只返回一个 Chart 的展示配置。

```python
from cedarkit.plots import Panel
from cedarkit.plots.config import LayoutSpec
from cedarkit.plots.templates import xy
from cedarkit.plots.testing import east_asia_temperature_field

field = east_asia_temperature_field().assign_attrs(
    temperature_kind="absolute",
    standard_name="air_temperature",
    cemc_name="t2m",
)
panel = Panel(template=xy())
chart = panel.add_chart(id="temperature")
layer = chart.contourf(field, style="cemc.t2m:cn_summer")
chart.colorbar(layer, label="°C")
panel.render()

panel.configure(layout=LayoutSpec(rows=1, columns=1, figsize=(10, 6)))
panel.apply_template(xy())
panel.render()
assert panel.charts["temperature"] is chart
assert chart.layers["plot_1"] is layer
panel.close()
```

模板切换在校验成功后整体提交。若新模板遗漏固定目标、容量不足或目标类型与
图层方法不匹配，会报告配置错误并保留此前有效配置。模板不执行 provider、单位
转换或诊断计算；数据层只在数据准备阶段运行一次。

集合布局使用 {func}`~cedarkit.plots.templates.ens_cn` 声明现有成员的排列规则。
成员 Chart、control 和 MAX 由调用方的数据流程创建；模板不会假造缺失成员或
计算统计量。完整 facet 入口与共享色阶语义见 {doc}`quickplot`。

## 重绘与资源生命周期

`render()` 在内容或配置改变后整图重绘。成功重绘后，`Chart` 与 `PlotLayer`
句柄保持稳定，`Subplot` 和 artists 则属于本次渲染代次，旧引用不应继续使用。
重复 `save()` 会复用干净渲染；配置更新后的 `save()` 会绘制当前状态。

推荐使用上下文管理器或显式 `close()` 释放 Panel 拥有的 Figure 和绘图结果：

```python
with Panel() as panel:
    chart = panel.add_chart(id="temperature")
    chart.contourf(field, style="cemc.t2m:cn_summer")
    panel.save("temperature.png")
```

关闭 Panel 不会关闭调用方拥有的 xarray 数据源。renderer 不会重新读取数据，
也不会回放 Matplotlib 底层对象上的临时修改；持久化展示定制应写入配置。

文档构建时会动态运行 Notebook 单元格，生成的图像作为站点构建产物输出。固定字体、合成场和运行依赖由上述
辅助导出脚本集中定义；默认输出到仓库外的临时目录。使用仓库锁文件运行：

```bash
uv sync --extra test
MPLBACKEND=Agg MPLCONFIGDIR=/tmp/cedarkit-plots-docs-mpl \
  uv run python docs/examples/render_plot_examples.py /tmp/cedarkit-plots-docs
```
