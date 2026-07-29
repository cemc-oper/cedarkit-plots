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

`cedarkit-plots` 自带从 [NCL](https://github.com/NCAR/ncl) 拷贝过来的
RGB 色表文件，可以直接通过名字使用。色表加载在
{mod}`cedarkit.plots.colormap` 中。

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
