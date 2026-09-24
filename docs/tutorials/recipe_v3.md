---
mystnb:
  execution_mode: 'off'
---

# v3 workflow recipe 与命令行

直接绘图只需要基础安装；静态编译、数据 provider 与 workflow CLI 使用可选依赖：

```bash
pip install 'cedarkit-plots[workflow]'
```

`cedarkit-plots recipe` 只接受 `api_version: cedarkit.plots/v3`。不读取旧 schema、
不提供 v1/v2 自动升级，也不再走旧 engine 路径。一个最小温度配方如下：

```yaml
api_version: cedarkit.plots/v3
kind: PlotRecipe
metadata:
  name: example.t2m
spec:
  data:
    temperature:
      field: {parameter: cedarkit.t2m}
      units: degC
      temperature_kind: absolute
  content:
    charts:
      - id: main
        plots:
          - id: temperature
            method: contourf
            field: temperature
            style: cemc.t2m:cn_summer
            targets: all
            data_crs: plate_carree
        titles:
          - {id: heading, text: "2 m Temperature (°C)"}
    colorbars:
      - id: temperature
        plots: [{chart: main, plot: temperature}]
        label: "°C"
  display:
    template: east_asia
```

`spec.data` 声明字段请求、单位准备和诊断运算；`spec.content` 用稳定 ID 声明
Chart、绘图方法、样式、标题和色标；`spec.display` 只声明模板及布局/子图配置。
recipe 不保存 dataset、文件路径、凭据或运行时 provider。加载和静态编译会检查
引用与算子，不读取字段数值、不创建 Figure。

## 校验和查看计划

```bash
cedarkit-plots recipe validate recipe.yaml
cedarkit-plots recipe validate path/to/recipes --json
cedarkit-plots recipe validate - --json < recipe.yaml
cedarkit-plots recipe plan recipe.yaml --forecast-time 24h
cedarkit-plots recipe plan recipe.yaml --forecast-time 24h --format json
```

`validate` 接受文件、stdin 或目录中的 YAML 文件。`plan` 接受一个配方，以及
`--start-time`、`--forecast-time` 和重复使用的 `--param NAME=VALUE`。计划会解析
参数元数据、请求和算子签名，但不会创建数据源、获取场值或渲染。

JSON 计划使用 `plan_schema_version: 3`，包含 recipe/compiler/descriptor 标识、
上下文、顺序节点、字段绑定、内容与展示声明、问题及批次读取信息；不含 provider、
可调用对象或凭据。命令行输出可用于预览和审计，运行数据仍由 workflow provider
执行。

## 插件发现

workflow 通过 `cedarkit.plots.ops`、`cedarkit.plots.domains` 和
`cedarkit.plots.recipes` entry point group 发现算子、展示预设和包内 recipe 资源。
发现顺序稳定；重复 ID 会报告冲突注册项及其来源。第三方产品包可提供 v3 recipe，
无需在底层绘图库中建立上层业务数据路径。

cedar-graph 使用相同的 v3 schema 与编译/执行协议；app 的任务文件另有
`cemc.plots/v2` 版本，两种 schema 各自描述不同对象，不能混用。见
`cedar-graph` 和 `cemc-plots-kit` 的配套文档。
