---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.4
mystnb:
  execution_mode: 'force'
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 集合成员布局

`ens_cn()` 只排列调用方创建的 Chart。下面绘制 4 个合成成员场，并使用共享色标；
示例不生成 control 或 MAX 成员。

```{code-cell} python
%matplotlib inline
import matplotlib as mpl
import cartopy.crs as ccrs
import numpy as np
from IPython.display import display
from cedarkit.plots import Panel
from cedarkit.plots.config import LayoutSpec
from cedarkit.plots.templates import ens_cn
from cedarkit.plots.testing import ens_cn_temperature_fields, temperature_style

mpl.rcParams["font.family"] = "DejaVu Sans"

longitudes = np.r_[np.arange(73.0, 134.0, 5.0), 135.0]
latitudes = np.arange(16.0, 57.0, 5.0)
fields = [
    field.assign_attrs(standard_name="air_temperature")
    for field in ens_cn_temperature_fields(
        coords=(longitudes, latitudes),
        member_count=4,
    )
]
layers = []
layout = LayoutSpec(
    figsize=(12, 8),
    dpi=160,
    margins=(.04, .12, .05, .05),
)
with Panel(
    template=ens_cn(columns=2, require_control=False),
    layout=layout,
) as panel:
    for index, field in enumerate(fields, start=1):
        chart = panel.add_chart(id=f"mem{index:02d}", role="member")
        layer = chart.contourf(
            field,
            style=temperature_style(),
            data_crs=ccrs.PlateCarree(),
        )
        chart.set_title(f"Member {index:02d}")
        layers.append(layer)
    panel.colorbar(layers, id="ens_cn_colorbar", label="°C")
    display(panel.render())
```

生产流程应根据实际成员列表创建 Chart，并明确处理 control、MAX 和缺测成员。
