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

- {doc}`getting_started/index`：安装、快速上手和核心概念。
- {doc}`tutorials/index`：绘图配置、快绘入口、样式、色表和 workflow 教程。
- {doc}`gallery/index`：可运行的产品与展示样例。
- {doc}`reference/index`：公开 API 和变更记录。

```{toctree}
:hidden:
:caption: 入门

getting_started/index
```

```{toctree}
:hidden:
:caption: 教程

tutorials/index
```

```{toctree}
:hidden:
:caption: 图集

gallery/index
```

```{toctree}
:hidden:
:caption: 参考

reference/index
```
