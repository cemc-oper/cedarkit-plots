---
mystnb:
  execution_mode: 'off'
---

# 样式库编写指南

cedarkit-plots 的要素样式库把"某个气象要素该怎么画"（色标、层次、
特征线、单位换算）从 Python 代码中抽离为 YAML 样式文件，由
{class}`~cedarkit.plots.style.registry.StyleRegistry` 统一加载、
匹配与构建。本文介绍样式文件的结构与编写方法。

```{note}
业务色标（CEMC 各要素）集中在 cedar-graph 的
`cedar_graph/styles/cn/` 下，经 entry point 注入；cedarkit-plots
自带 `style/builtin/` 中的通用样式。本文以两者为例。
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
    units: dagpm
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

`step` 形式需要在构建样式时传入数据（`get_style(..., data=field)`），
用于随数据范围变化的层次。

### colormap：四种来源 + matplotlib 名称

```yaml
colormap: viridis                            # matplotlib 色表名（裸字符串）
colormap: { ncl: BlAqGrYeOrReVi200, index: [2, 18, 34], index_offset: -2 }
colormap: { rgb_table: cn_hgt20, index: 14 } # 共享 RGB 表（register_rgb_table 注册）
colormap: { colors: ["#ff0000", "#00ff00"] } # 颜色列表
colormap: { ncl_colors: [...] }              # NCL 颜色名列表
```

四种来源必须**恰好设置一个**。`index` / `index_offset` / `count` /
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

### units：单位换算

变体可声明 `units`，值为内置换算表的目标单位：

| `units` | 假定源单位 | 换算 |
|---|---|---|
| `celsius` | K | `x - 273.15` |
| `hPa` | Pa | `x / 100` |
| `dagpm` | gpm | `x / 10` |
| `mm` | m | `x * 1000` |

声明后，配方的 `style_units` transform（或
{meth}`~cedarkit.plots.style.registry.StyleRegistry.get_transform`）
会把数据换算到目标单位再画图。写表外的单位名会在加载期报错。

## 加载与优先级

{meth}`~cedarkit.plots.style.registry.StyleRegistry.default`
按以下顺序组装搜索路径，**后加载的覆盖先加载的**（同 id 后者胜）：

1. cedarkit-plots 内置 `style/builtin/`；
2. `cedarkit.plots.styles` entry point（cedar-graph 经此注入
   `cedar_graph/styles/cn/`；entry point 模块须定义 `STYLE_PATHS`）；
3. 环境变量 `CEDARKIT_STYLE_PATH`（`os.pathsep` 分隔的目录列表）。

匹配（`style="auto"`）按相反顺序检查，业务样式优先于内置样式。

## 在 Panel 上使用

```python
panel.plot(field)                       # style 缺省 = "auto"：按 attrs 匹配 optimal 变体
panel.plot(field, style="h_500")        # 指定 id，用 optimal 变体
panel.plot(field, style="h_500:cn_ws")  # 指定 id:variant
panel.plot(field, style=my_style)       # 直接给 Style 对象
```

`"auto"` 的匹配元数据由
{func}`~cedarkit.plots.style.registry.metadata_from_field`
从 reki 读出的 `DataArray`（attrs + 层次坐标）构造。

## 校验与错误定位

{func}`~cedarkit.plots.style.schema.load_style_file` 在加载期做完整
schema 校验：未知键（`extra=forbid`）、非法 YAML（报错含文件路径与
行/列号）、`id` 与文件名不一致、colormap 来源不唯一、`optimal`
未在 `styles` 中定义等，都会抛出
{class}`~cedarkit.plots.style.schema.StyleFileError`。
