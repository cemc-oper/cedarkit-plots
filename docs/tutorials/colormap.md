---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 色表（Colormap）

新代码使用 `cedarkit.plots.palette` 中的原生 JSON palette，运行时不读取 NCL 文件：

```python
from cedarkit.plots.palette import get_palette, get_palette_info, get_named_color, palette_names

summer = get_palette("cemc.t2m.cn_summer")
reversed_sample = get_palette("source.BlAqGrYeOrReVi200", count=8, start=199, end=0)
transparent = get_named_color("transparent")  # (1, 1, 1, 0)
info = get_palette_info("cemc.rain.cn")         # 颜色、特殊色、来源与派生过程
```

所有原生表均为离散 ListedColormap，返回对象可独立修改，不影响下次读取。
count 使用含端点的零基索引，默认 start=0、end=N−1，按最近偶数舍入选色；
允许倒序和重复，count=1 选择 start。非整数/bool、非正 count、越界端点报错；
没有 count 时不能传 start/end。采样保留原表声明的 under/over/bad，不自动重定义。

业务样式用 `colormap: {palette: cemc.t2m.cn_summer}`，固定索引、偏移、拼接
已固化为具名派生表，不在原生 YAML 引用中再组合这些操作。色阶/extend 仍由 Style
决定。母表名 `source.*` 保留经核实的来源身份，业务派生表名 `cemc.*` 与 profile 区分：
palette ID 为完整名称，不受 StyleRegistry 当前 profile 影响。

catalog 包含 51 个表；来源版本、逐文件 SHA256、MeteoSwiss/Gist 原始注记与许可通知
在包内 `resources/palettes/`。离线再生成用 `tools/convert_palettes.py --check`，
可加 `--source-dir src/cedarkit/plots/resources/colormap/ncl` 核验旧输入字节。

## 旧 NCL 入口（待调用迁移后删除）

以下入口仍供尚未迁移的 graph/testing 调用；原生读取器不调用它们。
旧 transparent 的不透明行为只在新原生表修正，旧函数不是新 palette 的兼容转发层。

## `get_ncl_colormap`

按名称加载一个 NCL 色表，返回 :class:`matplotlib.colors.ListedColormap`：

```{code-cell} python
import matplotlib.pyplot as plt
import numpy as np

from cedarkit.plots.colormap import get_ncl_colormap

cmap = get_ncl_colormap("BlAqGrYeOrReVi200")
print("color count:", cmap.N)

# 可视化整个色表
gradient = np.linspace(0, 1, cmap.N).reshape(1, -1)
plt.figure(figsize=(8, 1))
plt.imshow(gradient, aspect="auto", cmap=cmap)
plt.gca().set_axis_off()
plt.show()
```

### 索引子集

通过 `index` 参数从色表中抽出一个子集，
对应 NCL 中"`stride`"或"`spread`"的常见用法：

```{code-cell} python
import matplotlib.colors as mcolors

color_index = np.array([2, 18, 34, 50, 66, 82, 110, 130, 150, 170, 190]) - 2
sub = mcolors.ListedColormap(cmap(color_index))

gradient = np.linspace(0, 1, sub.N).reshape(1, -1)
plt.figure(figsize=(8, 1))
plt.imshow(gradient, aspect="auto", cmap=sub)
plt.gca().set_axis_off()
plt.show()
```

`get_ncl_colormap` 也支持直接传 `count`、`spread_start`、`spread_end`
让函数代你做线性等距抽样：

```python
get_ncl_colormap("WhBlGrYeRe", count=10, spread_start=98, spread_end=0)
```

## `generate_colormap_using_ncl_colors`

如果想按 NCL 命名颜色（"PaleGreen2"、"DeepSkyBlue" …）自由组合，
用 {func}`~cedarkit.plots.colormap.generate_colormap_using_ncl_colors`：

```{code-cell} python
from cedarkit.plots.colormap import generate_colormap_using_ncl_colors

rain_cmap = generate_colormap_using_ncl_colors(
    [
        "transparent",
        "White",
        "DarkOliveGreen3",
        "forestgreen",
        "deepSkyBlue",
        "Blue",
        "Magenta",
        "deeppink4",
    ],
    name="rain",
)

gradient = np.linspace(0, 1, rain_cmap.N).reshape(1, -1)
plt.figure(figsize=(8, 1))
plt.imshow(gradient, aspect="auto", cmap=rain_cmap)
plt.gca().set_axis_off()
plt.show()
```

字符串 `"transparent"` 会被识别成完全透明的白，便于做"低于阈值不上色"
的填色图（典型用法是降水图的 `0.1` mm 以下不显示）。
