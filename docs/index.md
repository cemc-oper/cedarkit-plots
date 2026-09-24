---
mystnb:
  execution_mode: 'off'
---

# cedarkit-plots

`cedarkit-plots` 是面向气象场的底层绘图库。核心 API 将稳定的逻辑内容
（`Panel`、`Chart`、`PlotLayer`）与每次绘制产生的 Matplotlib 对象
（`Subplot` 和 artists）分开。`PanelTemplate` 与 `ChartTemplate` 是可选的展示
配置预设；不使用模板也能直接配置和绘图。

本文档示例使用固定的合成数据与 Agg 后端，不读取业务数据。内容包括内置
CEMC/通用样式、风羽、集合 facet、原生色表、地图资源和 v3 workflow recipe。

## 从这里开始

- {doc}`getting_started/install`：安装包及 workflow、文档可选依赖。
- {doc}`getting_started/quick_start`：显式准备单位并绘制 CEMC 温度图。
- {doc}`getting_started/concepts`：理解内容句柄、展示配置和渲染生命周期。
- {doc}`tutorials/templates`：直接配置 XY/地图图表、主图/附图和模板切换。
- {doc}`tutorials/quickplot`：使用单场、向量和 facet 快绘入口。
- {doc}`tutorials/styles` 与 {doc}`tutorials/colormap`：选择 CEMC/通用样式和原生色表。
- {doc}`tutorials/recipe_v3`：校验并预览声明式 v3 workflow recipe。
- {doc}`gallery/index`：可运行的产品与展示样例。
- {doc}`api/index`：公开 Python 接口。

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
tutorials/templates
tutorials/quickplot
tutorials/styles
tutorials/style_library
tutorials/colormap
tutorials/units
tutorials/recipe_v3
```

```{toctree}
:hidden:
:caption: 图集

gallery/index
```

```{toctree}
:hidden:
:caption: 参考

api/index
changelog
```
