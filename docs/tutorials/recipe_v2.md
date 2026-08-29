---
mystnb:
  execution_mode: 'off'
---

# Recipe v2、PlotPlan 与扩展

Recipe v2 是稳定的、只含数据的绘图声明。它使用封闭的 op 词汇表，
不执行 YAML 中的 Python 表达式。每份文档必须有固定 envelope：

```yaml
api_version: cedarkit.plots/v2
kind: PlotRecipe
metadata: {name: example.t2m, title: 2 m temperature}
spec:
  domain: {default: east_asia, area: cn_area}
  data:
    t2m:
      field: {parameter: cedarkit.t2m}
      units: degC
  layers: [{field: t2m, style: t2m:cn_summer}]
  title: {graph_name: 2 m temperature}
```

`metadata.name` 和 op 名称是稳定标识；未知字段、`api_version`、`kind`
都会失败。`data` 条目恰好有一个 `field` 或 `compute`。`field.parameter`
是参数注册表中的稳定 ID；可选 `level` 是查询限定条件。`units` 是数据
目标单位，编译器会把必要换算表示为 `convert_units` 节点并更新运行时 attrs。

`compute` 声明 `op`、`inputs` 和可选 `outputs`；它可以写在输入之前。
`transforms` 只能引用 transform op，`repeat` 至少为 1。图层按 `layers`
列表的声明顺序绘制，`field` 与 `vector: {u, v}` 二选一。样式的
`expected_units` **只校验**数据单位，绝不进行第二次转换。

## 从 v1 迁移与兼容窗口

加载器仍接受完整的历史 v1 形状，并在内存中纯函数、确定性地规范化为 v2；
重复迁移不会改变结果。部分 v2 envelope 不会回退为 v1。v1 的
`style_units`/style 单位行为保留为 `legacy_unit_compatibility`，仅作为
迁移期间的兼容边界；新 recipe 应声明 `data.<name>.units`。

```bash
# 只读检查：若仍为 v1 或需要迁移，退出码为 1
cedarkit-plots recipe migrate path/to/recipes --check

# 输出规范化 v2；写回必须显式确认
cedarkit-plots recipe migrate old.yaml --output new.yaml
cedarkit-plots recipe migrate old.yaml --in-place --force

# 单文件、目录或标准输入的 schema 路由检查
cedarkit-plots recipe validate path/to/recipes
cedarkit-plots recipe validate - --json < recipe.yaml
```

v1 reader 与 `PlotModuleAdapter` 是已发布的兼容接口；弃用通知会先在
changelog 中给出，不会把 v1 模块悄然改为 v2 的语义。

## 编译、预览与执行边界

`compile_recipe` 只构建不可变 `PlotPlan`，不接触 provider、不读取字段。
`RequestKey` 包含 provider slot、完整 `FieldQuery`、时间绑定与 cardinality，
因此只有完全等价的请求才会合并。未被图层消费的节点会作为 `dead_node`
诊断并从可执行节点中裁剪；`CompileContext(strict=True)` 会把它变成错误。
unknown ref、循环、重复输出、未知 op、输入/输出数量或单位不匹配都在编译期
给出带路径的结构化诊断。

```bash
cedarkit-plots recipe plan recipe.yaml \
  --start-time 2024-07-01T00:00Z --forecast-time 24h --format json
```

`plan` 自动发现已安装的 op 插件，输出的 JSON 是版本化的 public snapshot：
`plan_schema_version`、recipe/compiler/descriptor identity、context、nodes、
outputs、layers、issues 与 executable node IDs。它不含 callable、provider、
凭证或本地 source 路径。省略 `--format json` 可得到有界的 `summary()`。
之后由 `plan.execute(provider)` 执行；executor 只消费该 plan，运行时 op
没有 provider/read 能力。`plan.check_available(provider)` 仅分析请求，返回
按 RequestKey 列出的 `AvailabilityReport`/`RequestAvailability`，而不是取数。

## Op 与插件作者指南

用 `OpDescriptor(name, kind, input_count, output_count, callable, ...)` 发布 op。
`kind` 是 `transform` 或 `compute`；输入/输出 arity、pure/reusable 声明及
可选 planner 都是契约的一部分。planner 只能扩展静态图（例如 `time_diff`
增加较早时次 read），不得访问 provider。重名注册默认失败；仅测试可使用
显式 scoped override。

通过 entry point 发布 provider，而不是在 import 时修改全局注册表：

```toml
[project.entry-points."cedarkit.plots.ops"]
my_product = "my_product.recipes:op_descriptors"
```

provider 返回 descriptor 的可迭代对象。`cedarkit.plots.recipes` 返回
`importlib.resources` 的 Traversable recipe root，`cedarkit.plots.domains`
返回 `DomainDescriptor`；发现顺序稳定，来源会进入 registry manifest。
插件缺失时 core 仍可使用，依赖其资源的 recipe 在验证/编译时明确失败。
