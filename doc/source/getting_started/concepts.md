---
mystnb:
  execution_mode: 'off'
---

# 核心概念

绘图 API 将图形的逻辑内容与每次绘制所创建的对象分开管理。

## 内容句柄

- `Panel` 管理逻辑 Chart、展示配置以及最近一次成功渲染创建的
  Matplotlib `Figure`。
- `Chart` 是布局中的稳定逻辑图表，持有一个或多个 `PlotLayer`，并可将图层
  定向到多个命名子图。
- `PlotLayer` 保存稳定 ID、数据引用、显式绘图方法（`contourf`、`contour` 或
  `barbs`）、样式快照及目标子图。
- `Subplot` 和 Matplotlib artists 是一次渲染的结果。布局或模板改变后这些
  结果可以替换；`Chart` 与 `PlotLayer` 句柄保持稳定。

创建 Chart 或 PlotLayer 只登记逻辑内容。`Panel.render()`、`Panel.save()` 与
`Panel.show()` 根据当前状态绘制。渲染器不会从样式推断绘图方法，也不会执行
数据 provider 或 workflow 运算。

## 配置值

`LayoutSpec` 描述 Panel 网格与位置；`ChartSpec` 和 `SubplotSpec` 描述 XY/地图
目标、区域、投影和底图；`Theme` 与 `DecorationSpec` 保存外观配置。调用方可以
直接传入这些配置，也可以将其组合为可选的 `PanelTemplate` 或 `ChartTemplate`。
模板只选择展示方式，不创建 Chart、图层或数据。

## 样式与数据准备

`ContourStyle` 与 `BarbStyle` 描述单个图层的外观，以及适用时的单位或累计时段
约束。`StyleRegistry.default()` 已包含 CEMC 样式；`generic.t` 可显式选择。
样式只检查准备后的数据，不负责数值转换。需要转换时，先调用
`cedarkit.plots.units.prepare_field()` 或 `prepare_vector()`。

## 可选 workflow

`cedarkit.plots[workflow]` 增加版本化的 `cedarkit.plots/v3` recipe、静态计划、
provider、注册算子和渲染桥接。直接使用 Panel/Chart 不依赖 workflow recipe。
cedar-graph 等上层产品使用 workflow 将数据请求与计算连接到底层绘图模型。

直接配置、地图主附图与模板切换见 {doc}`../tutorials/templates`；单场、向量和
facet 快绘见 {doc}`../tutorials/quickplot`。
