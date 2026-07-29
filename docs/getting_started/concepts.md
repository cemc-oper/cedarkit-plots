---
mystnb:
  execution_mode: 'off'
---

# 核心概念

`cedarkit-plots` 把"画一张气象图"这件事拆成了若干个互相协作
的小组件。理解它们之间的关系，对阅读 `cedar-graph` 等上层包
也很有帮助。

## Panel / Chart / Layer

```
┌───────────────────────── Panel ──────────────────────────┐
│  ┌──────── Chart ────────┐  ┌──────── Chart ────────┐    │
│  │  Layer 0：地图底图    │  │  Layer 0：地图底图    │ …  │
│  │  Layer 1：等值线      │  │  Layer 1：填充        │    │
│  │  Layer 2：风羽        │  │  Layer 2：等值线      │    │
│  └────────────────────── ┘  └─────────────────────── ┘    │
└──────────────────────────────────────────────────────────┘
```

- {class}`~cedarkit.plots.chart.Panel`：与 matplotlib `Figure` 一一对应，
  对外暴露统一的绘图、加标题、加色标接口。
- {class}`~cedarkit.plots.chart.Chart`：一个面板内的一张子图（地图框），
  对应一个 matplotlib `Axes`。常规情况下面板里只有一个 chart，
  但集合预报模板（`EnsCNMapTemplate`）会一次性放 15~16 个 chart。
- {class}`~cedarkit.plots.chart.Layer`：在 chart 上的一层绘图——填充、
  等值线、风羽……可以叠加多层。

## MapTemplate / 模板

`MapTemplate` 是"区域 + 投影 + 标题/色标布局"的一组预设。
`cedarkit.plots.domains` 内置了几种常用模板：

| 模板 | 作用 |
|------|------|
| {class}`~cedarkit.plots.domains.EastAsiaMapTemplate` | 中国东亚区域，可叠加副图 |
| {class}`~cedarkit.plots.domains.CnAreaMapTemplate`   | 中国子区域（按需指定 `area`） |
| {class}`~cedarkit.plots.domains.EuropeAsiaMapTemplate`| 欧亚区域 |
| {class}`~cedarkit.plots.domains.GlobalMapTemplate`    | 全球 |
| {class}`~cedarkit.plots.domains.GlobalAreaMapTemplate`| 全球子区域 |
| {class}`~cedarkit.plots.domains.NorthPolarMapTemplate`| 北极立体投影 |
| {class}`~cedarkit.plots.domains.EnsCNMapTemplate`     | 集合预报中国区域（多 chart） |

当系统提供的模板不够用时，可以继承
{class}`~cedarkit.plots.domains.MapTemplate` 自己实现一个新的。

## Style

样式（{mod}`cedarkit.plots.style`）描述"这一层应该怎么画"：

- {class}`~cedarkit.plots.style.ContourStyle`：等值线/填充。
  `fill=True` 走 `contourf`，`fill=False` 走 `contour`。
- {class}`~cedarkit.plots.style.BarbStyle`：风羽，含色、长度、增量等参数。
- {class}`~cedarkit.plots.style.ColorbarStyle`：色标的标签与位置。
- {class}`~cedarkit.plots.style.ContourLabelStyle`：等值线标签字号、
  填色背景等。

## Colormap / Resources

- {func}`~cedarkit.plots.colormap.get_ncl_colormap` 从内置的 NCL `.rgb`
  色表文件中获取 `ListedColormap`，支持索引、抽样、附加颜色等参数。
- {func}`~cedarkit.plots.colormap.generate_colormap_using_ncl_colors`
  按 NCL 命名颜色拼一个新色表。
- 中国 shapefile、NCL 色表等资源都打包在
  `cedarkit/plots/resources/` 内，通过 `importlib.resources` 加载，
  无需手动指定路径。
