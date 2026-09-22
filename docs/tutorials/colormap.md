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

## 可执行色表预览

```{code-cell} python
import matplotlib.pyplot as plt
import numpy as np
from cedarkit.plots.palette import get_palette

cmap = get_palette("cemc.t2m.cn_summer")
fig, ax = plt.subplots(figsize=(8, 1))
ax.imshow(np.arange(cmap.N)[None, :], cmap=cmap, aspect="auto", interpolation="nearest")
ax.set_axis_off()
plt.show()
```

## 自定义颜色

```{code-cell} python
from cedarkit.plots.palette import get_named_color
from cedarkit.plots.style import ContourStyle

rain_style = ContourStyle(
    levels=[5, 25, 50, 100], fill=True, extend="both",
    colors=[get_named_color(name) for name in
            ["transparent", "PaleGreen2", "ForestGreen", "Blue", "Magenta"]],
)
```

显式颜色列表依次对应 under、三个内部区间、over；透明色 alpha 为 0。
使用完整业务等级时优先 `StyleRegistry.default().get_style("cemc.rain:cn",
metadata={"units": "mm", "accumulation_hours": 24})`。
原生 palette YAML 的固定填色等级结合 `extend` 编译为内部区间颜色与特殊颜色；
`get_palette` 本身返回原表，不隐式改变等级或保留扩展位置。
旧解析器和原始 NCL 文件仅供尚未迁移的下游调用，计划在 D14/D15 删除。
