---
mystnb:
  execution_mode: 'off'
---

# 样式库编写指南

cedarkit-plots 的要素样式库把"某个气象要素该怎么画"（色标、层次、
特征线、期望单位）从 Python 代码中抽离为 YAML 样式文件，由
{class}`~cedarkit.plots.style.registry.StyleRegistry` 统一加载、
匹配与构建。本文介绍样式文件的结构与编写方法。

```{note}
业务色标（CEMC 各要素）集中在 cedar-graph 的
`cedar_graph/styles/cn/` 下，经 entry point 注入；cedarkit-plots
自带 `style/builtin/generic/` 中的通用样式。CEMC 全量资源内置由 D12-04 完成。本文以两者为例。
```

## 一个完整的例子

以 500 hPa 位势高度（`h_500.yml`）为例：

```yaml
# 500 hPa 位势高度。highlight 展开 588 特征线（加粗、变色）。
id: h_500
criteria:
  - cemc_name: h
    first_level_type: 100   # isobaricInhPa
    first_level: 500
  - eccodes_name: gh
    first_level_type: 100
    first_level: 500
optimal: cn_dagpm

styles:
  cn_dagpm:                 # 500 hPa 高度场（蓝色线 + 588 黑色特征线）
    type: contour
    levels: { linspace: [500, 588, 23] }
    colormap: { rgb_table: cn_hgt20, index: 14 }
    label: { inline: true, fontsize: 7, fmt: "{:.0f}", color_index: 15 }
    highlight:
      level: 588
      linewidth: 1.4
      color_index: 1
    expected_units: dagpm
```

顶层四个键：

| 键 | 含义 |
|---|---|
| `id` | 样式 id，**必须与文件名一致**（`h_500.yml` → `h_500`）。命名约定：cemc 要素名（`t2m`、`psl`），要素+层次样式用"cemc 名 + 层次值"（`h_500`、`ws_850`） |
| `criteria` | 身份规则列表，用于 `style="auto"` 匹配数据元数据 |
| `optimal` | 默认变体 id；`get_style("h_500")` 不指定变体时使用 |
| `styles` | 命名变体字典，每个变体构建为一个 `ContourStyle` 或 `BarbStyle` |

## criteria：身份规则

`criteria` 是规则列表：**条目之间是或（OR），条目内的键之间是与（AND）**。
键词汇与 reki 的 `param_registry.yaml` 一致：

- `cemc_name` / `eccodes_name` / `wgrib2_name` — 要素名（三种命名体系）；
- `first_level_type` / `first_level`、`second_level_type` / `second_level` —
  层次。`first_level_type` 只接受 **GRIB2 码表 4.5 的数值码**
  （如 `100` = isobaricInhPa，`103` = heightAboveGround），写字符串会报错；
  注册表在数值码与 reki 归一化层次坐标名（`pl`、`heightAboveGround` 等）
  之间做双向归一匹配；
- `discipline` / `category` / `number` — GRIB2 参数三元组。

上面 `h_500` 的两条规则分别覆盖 cemc 命名（`h`）与 ecCodes
命名（`gh`）的 500 hPa 等压面场。

## styles：变体

每个变体必须声明 `type: contour` 或 `type: barb`，两组键互不混用
（schema 会拒绝 contour 变体里的 barb 键，反之亦然）。

### levels：四种写法

```yaml
levels: [-12, -8, -4, 0, 4, 8]        # 显式列表（整型保持整型，刻度标签为 "4" 而非 "4.0"）
levels: { range: [0, 100, 5] }        # np.arange(start, stop, step)
levels: { linspace: [500, 588, 23] }  # np.linspace(start, stop, num)
levels: { step: 4, reference: 0 }     # 按数据范围动态生成：以 reference 对齐、step 为间隔
```

`step` 构建为 `LevelStep` 规则，在新 Panel 的 render 阶段根据数据范围计算；
`get_style(..., data=field)` 只读取元数据，不读取字段值。动态 step 不与固定层次 highlight 混用。

### colormap：原生 palette 与其他来源

```yaml
colormap: { palette: cemc.t2m.cn_summer }      # 原生离散 palette
colormap: viridis                            # matplotlib 色表名（裸字符串）
colormap: { ncl: BlAqGrYeOrReVi200, index: [2, 18, 34], index_offset: -2 }
colormap: { rgb_table: cn_hgt20, index: 14 } # 共享 RGB 表（register_rgb_table 注册）
colormap: { colors: ["#ff0000", "#00ff00"] } # 颜色列表
colormap: { ncl_colors: [...] }              # NCL 颜色名列表
```

palette/ncl/rgb_table/colors/ncl_colors 必须**恰好设置一个**。
原生 palette 只接受具名表，不接受 index/count/offset 等二次变换；其 label/highlight
color_index 只指向实际选中表。迁移旧母表高亮/标签时使用 tools/style_palette_map.json
中的显式颜色。NCL 来源待 D12-04/D14 调用迁移后删除。`index` / `index_offset` / `count` /
`spread_start` / `spread_end` 只对 `ncl` / `rgb_table` 有效；
`count` / `spread_start` / `spread_end` 只对 `ncl` 有效
（schema 强制校验）。

### highlight：特征线

```yaml
highlight:
  level: 588
  linewidth: 1.4      # 基准线宽默认 0.7
  color_index: 1      # 或 color: "black"；两者互斥
```

构建时展开为逐层次（per-level）的线宽与颜色数组——`h_500` 的
588 dagpm 线因此加粗变色。`linewidth` / `color` / `color_index`
至少要设一个。

### label 与 colorbar

`label` 出现即开启等值线标注：`inline`、`fontsize`、`fmt`、
`color` / `color_index` / `line_colors`（三者互斥）等。
`colorbar` 支持 `loc` / `label` / `label_levels`。

### 单位与累计时段

`expected_units` 声明已准备数据的规范单位，匹配和显式解析读取
`attrs["units"]`，不相等或缺失即报错；没有声明时不猜源单位。
`accumulation_hours` 为有限正数，声明累计量实际覆盖的小时数，读取
同名 attrs，不从预报时效 `step` 或产品名称推断。两项约束会进入 Style
快照，在登记、更新和渲染时校验；不执行转换或时间差分。
旧 `units/get_transform/style_units` 暂由尚未迁移的 workflow 使用，D13 删除。

## profile 加载与优先级

目录根下按 `<profile>/<id>.yml` 存放，例如 `my_styles/cemc/t2m.yml`。
`StyleRegistry([root], profile="cemc", user_paths=[user_root], generic_fallback=())`
默认选 cemc；显式 `profile="generic"` 或用户 profile 名可切换目录。
显式传入的平铺目录归当前 profile；现有插件的平铺 STYLE_PATHS 在 default
加载中归 cemc。内置资源与插件同属 base 层，环境变量 `CEDARKIT_STYLE_PATH`
（os.pathsep 分隔）与 user_paths 同属 user 层。

优先级为显式 Style/参数 → user 当前 profile → base 当前 profile →
声明允许的 generic。`generic_fallback=("t",)` 仅允许自动匹配 generic.t，
默认不回退；显式 ID 拼写错误或 variant 缺失始终报错。
同 ID 的用户文件整体替换 base 文件，不合并 variants。
同层同 profile 重复 ID 在加载时报出两个来源，整次 load_path 不提交。

自动匹配先选来源层，再选 specificity：取成功 criteria OR 分支中最多的
已设置条件数，加上 optimal variant 的单位/累计时段约束数。
同级最高分平局抛 StyleMatchError，不能用文件或插件顺序裁决。
已识别字段却缺层次 metadata，或单位/时段约束失败的最高分候选阻止继续回退。
只有没有相关候选时才尝试下一来源层。自动匹配只选择 optimal；季节、时段等
产品规则应显式选择 variant。

`registry.explain(metadata)` 返回 profile、fallback 白名单、status、selected
及 candidates；每个候选含规范 ID、source、tier、specificity、status 和 reasons，
以及实际评估的 criteria 分支和 constraints（被用户替换的 base 候选只记录 shadowed 原因）。
整体 status 为 selected/no_match/blocked/conflict；explain 不抛匹配冲突也不建图。
`match` 在 blocked/conflict 时抛 StyleMatchError（带 explanation），无匹配返回 None。

## 在新 Chart 上使用

```python
from cedarkit.plots import Panel
from cedarkit.plots.style import StyleRegistry

registry = StyleRegistry.default(profile="generic")
style = registry.get_style("t", data=field, overrides={"colormap": "viridis"})
panel = Panel()
chart = panel.add_chart(id="temperature")
layer = chart.contourf(field, style=style)
# 也可直接写 chart.contourf(field, style="generic.t:default")
panel.render()
panel.close()
```

`get_style("profile.id:variant")` 与 `get_style("profile.id", "variant")` 等价；
未写 profile 用当前 profile，未写 variant 用 optimal，两个 variant 参数冲突时报错。
overrides 使用 YAML StyleVariant 字段，整字段替换、schema 校验后构建独立对象，
不修改注册内容；显式 Style 对象请直接构造其参数，不再叠加 overrides。
核心 Chart 要求显式 Style 或 ID，拒绝 auto/None。调用方可通过
`resolve_style("auto", field, registry=registry)` 单独执行自动选择。

## 校验与错误定位

{func}`~cedarkit.plots.style.schema.load_style_file` 在加载期做完整
schema 校验：未知键（`extra=forbid`）、非法 YAML（报错含文件路径与
行/列号）、`id` 与文件名不一致、colormap 来源不唯一、`optimal`
未在 `styles` 中定义等，都会抛出
{class}`~cedarkit.plots.style.schema.StyleFileError`。
