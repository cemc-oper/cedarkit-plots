---
mystnb:
  execution_mode: 'off'
---

# 集合成员布局

`ens_cn()` 只排列调用方已经创建的 Chart。成员身份通过 Chart ID 和 role 传入；
它不会生成成员、control 或 MAX。MAX 需要由产品数据流程按照明确的缺测和统计
规则计算后，再作为普通 Chart 添加。

```python
import cartopy.crs as ccrs
from cedarkit.plots import Panel
from cedarkit.plots.config import BasemapSpec
from cedarkit.plots.map import MapLoader, MapType
from cedarkit.plots.templates import ens_cn
from cedarkit.plots.testing import ens_cn_temperature_fields, temperature_style

class EmptyLoader(MapLoader):
    def get_feature(self, name, **kwargs):
        return []

fields = ens_cn_temperature_fields(member_count=4)
basemap = BasemapSpec(loader=EmptyLoader, map_type=MapType.Portrait, features=())
with Panel(template=ens_cn(columns=3, require_control=False, colorbar_id=None,
                           basemap=basemap)) as panel:
    for index, field in enumerate(fields, start=1):
        chart = panel.add_chart(id=f"mem{index:02d}", role="member")
        chart.contourf(field, style=temperature_style(), data_crs=ccrs.PlateCarree())
    panel.save("ensemble-members.png")
```

该样例用空底图 loader 使渲染不依赖 Natural Earth 下载。实际业务中应由数据层
根据返回成员列表创建对应 Chart，并单独决定是否存在 control 和 MAX。
