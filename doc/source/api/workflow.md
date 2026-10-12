---
mystnb:
  execution_mode: 'off'
---

# `cedarkit.plots.workflow`

v3 recipe 校验、静态编译、数据执行和渲染桥接。绘图基本功能无需安装 workflow 可选依赖；运行本模块需安装 `cedarkit-plots[workflow]`。

`public_request_from_field_request()` 将一个 `FieldRequest` 或 `BoundFieldRequest`
转换为规范的公共 `cedarkit.request/v1`。调用方需给稳定 dataset 和已核验的
原生参数 shortName；成员还需显式角色映射。节点 ID 留在 workflow，不进入
公共 Query。无明确时间、未映射原生条件或旧 `first` 基数策略会失败；现有
recipe 格式与 `FieldRequest` 构造方式不变。

```{eval-rst}
.. automodule:: cedarkit.plots.workflow.recipe
   :members:
```

```{eval-rst}
.. automodule:: cedarkit.plots.workflow.plan
   :members:
```

```{eval-rst}
.. automodule:: cedarkit.plots.workflow.runtime
   :members:
```

```{eval-rst}
.. automodule:: cedarkit.plots.workflow.render
   :members:
```
