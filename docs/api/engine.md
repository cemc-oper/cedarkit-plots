---
mystnb:
  execution_mode: 'off'
---

# `cedarkit.plots.engine`

绘图引擎：配方（`.yaml`）与 Python 绘图模块（`.py`）的统一加载与渲染。
配方经 {class}`~cedarkit.plots.engine.engine.PlotEngine` 适配为与
Python 模块相同的三件套接口（`PlotMetadata` / `load_data` / `plot`），
装载器 {func}`~cedarkit.plots.engine.loader.get_plot_definition`
先查配方、再查模块，对调用方透明。

## 顶层接口

```{eval-rst}
.. automodule:: cedarkit.plots.engine
   :members:
   :undoc-members:
   :show-inheritance:
```

## 引擎与适配器

```{eval-rst}
.. automodule:: cedarkit.plots.engine.engine
   :members:
   :undoc-members:
   :show-inheritance:
```

## 配方 schema

```{eval-rst}
.. automodule:: cedarkit.plots.engine.recipe
   :members:
   :undoc-members:
   :show-inheritance:
```

## op 注册表

```{eval-rst}
.. automodule:: cedarkit.plots.engine.ops
   :members:
   :undoc-members:
   :show-inheritance:
```

## 装载器

```{eval-rst}
.. automodule:: cedarkit.plots.engine.loader
   :members:
   :undoc-members:
   :show-inheritance:
```
