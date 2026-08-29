---
mystnb:
  execution_mode: 'off'
---

# cedarkit-plots

`cedarkit-plots` 是构建在 Matplotlib + Cartopy 之上的低层
气象绘图库，提供面板（`Panel`）、子图（`Chart`）、地图模板
（`MapTemplate`）、绘图样式（`ContourStyle`、`BarbStyle` …）以及
NCL 色表与 shapefile 资源。它是 `cedar-graph` 等高层应用包
背后的"画图引擎"。

```{admonition} 文档约定
:class: tip

本文档中的所有图都在构建时由
{mod}`cedarkit.plots.testing` 中的合成数据函数生成，
无需访问任何业务数据。这套合成数据同时被集成测试套件复用，
确保文档示例与 CI 中跑过的代码一致——详见 {doc}`tutorials/synthetic_data`。
```

## 内容导览

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} 快速上手
:link: getting_started/quick_start
:link-type: doc

构造一个面板、添加一层填充图、打印保存。
:::

:::{grid-item-card} 核心概念
:link: getting_started/concepts
:link-type: doc

`Panel` / `Chart` / `Layer` / `Style` / `MapTemplate` 之间的关系。
:::

:::{grid-item-card} 绘图样例
:link: gallery/index
:link-type: doc

按地图模板（东亚、欧亚、全球、北极、集合预报）逐个展示绘图组合。
:::

:::{grid-item-card} API 参考
:link: api/index
:link-type: doc

`cedarkit.plots` 各子模块的自动生成参考。
:::

::::

## 安装

```bash
pip install cedarkit-plots
```

```{toctree}
:hidden:
:caption: 入门

getting_started/install
getting_started/quick_start
getting_started/concepts
```

```{toctree}
:hidden:
:caption: 教程

tutorials/synthetic_data
tutorials/styles
tutorials/style_library
tutorials/colormap
tutorials/templates
tutorials/recipe_v2
```

```{toctree}
:hidden:
:caption: 绘图样例

gallery/index
```

```{toctree}
:hidden:
:caption: 参考

api/index
changelog
```
