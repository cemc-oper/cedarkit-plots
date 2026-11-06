---
mystnb:
  execution_mode: 'off'
---

# `cedarkit.plots.workflow`

v3 recipe 校验、静态编译、数据执行和渲染桥接。绘图基本功能无需安装 workflow 可选依赖；运行本模块需安装 `cedarkit-plots[workflow]`。

`public_request_from_field_request()` 将一个 `FieldRequest` 或 `BoundFieldRequest`
转换为当前公共 `cedarkit.request/v1`，使用 `source`、可选 `context`、
`queries` 和 `completeness`。调用方直接传入 `source={"kind": "file",
"path": "/data/arbitrary.grib2"}` 即可声明任意文件，无需登记文件路径。
dataset、参数定义和映射是否需要提供，由该源的参数语义决定；编译阶段不打开文件。
`FieldRequest.query` 使用 `cedarkit_query.Query` 的 `level_type`、`level_unit`、
`layer`、`member`、`member_role` 和 `native.grib` 原语。工作流起报与预报时间在
转换时绑定为 `time`、`step` 和 `valid_time`；缺少明确时间或已有条件冲突会报结构化错误。
节点 ID 和 `one` / `first` / `all` 执行选择留在工作流/provider，不进入公共 Request。

静态编译可以传入 `CompileContext(parameters=effective_parameters)`，其中索引按
稳定 parameter ID 组织，包含已应用继承的参数定义。编译器用它解析名称/别名、
核验固定条件并推导源单位。未提供时保留合法参数声明，待 provider 按所选源绑定；
不会使用某个产品的全局默认目录。单位可以由 recipe 的 `source_units` 显式声明，
否则在执行时使用数据的单位元信息。绝对温度 K → degC 仍需声明
`temperature_kind: absolute`，避免将温差当作绝对温度换算。

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
