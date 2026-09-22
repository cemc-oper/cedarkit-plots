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

# 快绘：单图、风羽和 facet

`cedarkit.plots.quickplot` 使用普通 Panel/Chart 内容模型。返回结果包含
Panel、Chart/PlotLayer 句柄和单位转换记录，支持继续更新图层或切换模板。
成功调用已经完成渲染；使用 with 关闭结果，不会关闭输入数据源或其他 Figure。

## 单图：明确准备单位，然后匹配样式

```{code-cell} python
import numpy as np
import xarray as xr
from cedarkit.plots import quickplot

x, y = np.meshgrid(np.linspace(-1, 1, 20), np.linspace(-1, 1, 16))
kelvin = xr.DataArray(
    273.15 + 15 + 20*x + 5*np.sin(3*y), dims=("y", "x"),
    attrs={"units": "K", "temperature_kind": "absolute",
           "cemc_name": "t2m", "standard_name": "air_temperature"},
)
with quickplot.plot(kelvin, units="degC", title="2m temperature",
                    colorbar_label="degC", output="quick-temperature.png") as result:
    print(result.conversions[0][0])
    assert result.layer.method == "contourf"
    # 更换样式不会再次进行 K→degC 转换。
    result.layer.update(style="cemc.t2m:cn_winter")
    result.panel.save("quick-temperature-winter.png")
assert kelvin.attrs["units"] == "K"
```

`method="contour"` 明确选择等值线；不会根据 Style.fill 切换方法。
style=None/"auto" 按准备后 metadata 匹配默认 CEMC 样式。
可传 `style="cemc.t2m:cn_summer"`、显式 ContourStyle，或传自定义
StyleRegistry。其他 profile/generic fallback 必须由 registry 显式选择。
注册表变体可用 `style_overrides={"levels": ..., ...}` 覆盖；显式 Style 对象
应直接配置，不接受 style_overrides。标量样式必须有固定等级或 LevelStep。

不传任何单位准备参数时直接绑定原字段，没有转换记录；不会为了匹配
Style 偷做转换。source_units/temperature_kind 遵循 [单位准备](./units.md)。
单图只接二维 DataArray，不自动 squeeze，不接 Dataset、列表或 generator。

## 显式风羽

```{code-cell} python
u = kelvin.copy(data=36 + 20*y).assign_attrs(
    units="km/h", cemc_name="u", temperature_kind=None, standard_name="eastward_wind")
v = kelvin.copy(data=3 + 4*x).assign_attrs(
    units="m/s", cemc_name="v", temperature_kind=None, standard_name="northward_wind")
with quickplot.barbs(u, v, units="m/s", title="Wind", output="quick-wind.png") as result:
    assert len(result.conversions[0]) == 2
```

两分量独立校验与转换，必须二维、维度/坐标/形状相符。不从 tuple 或 Dataset
猜 u/v。自动样式身份用 u 匹配，两分量均校验；可显式给 `style="cemc.wind"`。
`vector_basis="grid"|"earth"`、data_crs、subplots 交由核心验证。没有 quiver 或风羽色标。

## facet：真实成员身份与共享色阶

```{code-cell} python
from cedarkit.plots.config import LayoutSpec

cube = xr.concat([kelvin, kelvin+4, kelvin+8], dim=xr.IndexVariable("number", [0, 1, 7]))
cube.attrs = dict(kelvin.attrs)
with quickplot.facet(
    cube, dim="number", ids=["ctl", "mem01", "mem07"],
    roles=["control", "member", "member"], units="degC",
    level_policy="shared", colorbar_label="degC",
    layout=LayoutSpec(rows=1, columns=3, figsize=(12, 4)),
    output="quick-facet.png",
) as result:
    assert tuple(result.panel.charts) == ("ctl", "mem01", "mem07")
    original = result.charts
    result.panel.configure(layout=LayoutSpec(rows=3, columns=1))
    result.panel.render()
    assert tuple(result.panel.charts.values()) == original
```

DataArray 必须显式指定一个 facet 维度，切片后保留两个字段维度。默认 ID 是
维度坐标转成的字符串，不能重复或包含空白；无维度坐标时须提供 ids。
roles 默认全部 member，包括坐标 0，不自动创建 CTL/MAX 或计算统计量。

有限 generator/列表使用 `FacetItem(id, field, role="member", title=None)`：

```{code-cell} python
items = (quickplot.FacetItem(f"member-{n}", kelvin+n) for n in (1, 2, 7))
with quickplot.facet(items, units="degC", colorbar=False) as result:
    assert len(result.charts) == 3
```

每个 iterable 恰好消费一次，空输入/重复 ID/坏成员/消费异常明确报错，
不会静默跳过成员。此形式不能再传 dim/ids/roles。

- `level_policy="per_chart"`：LevelStep 按各字段范围求值，各 Chart 独立色标。
- `level_policy="shared"`：复用 Panel.share_scale，LevelStep 使用全组范围；
  固定 CEMC 等级不会改变。数据须声明相同规范单位、温度语义和 standard_name，
  样式也须满足核心共享条件；不能共享时直接报错。

## 配置与所有权

template/layout/theme/chart_defaults/chart_rules/decorations 直接传给 Panel。
facet 未给布局且模板未声明布局时采用最多三列、自动行数；此默认值放在模板层，后续切换模板可替换它。显式布局或模板负责其容量。
地图必须显式 data_crs；多目标由 subplots 选择。色标绑定同一层的所有选定目标。

colorbar=None 在 contourf 开启、contour 关闭；可显式覆盖。单图/共享色标 ID 为
colorbar_id（默认 colorbar），逐图色标为 `<colorbar_id>_<member_id>`。
使用带色标配置的模板时，可传对应 ID，如 ens_cn 的 `ens_cn_colorbar`。
颜色与阈值来自图层 mappable，不另建绘图路径。

output=None 只 render；给路径则由 Panel.save 输出，调用者负责目录存在。
save_kwargs 可指定 dpi/format/bbox_inches/transparent，必须与 output 一起传。
工厂不自动 show，不在成功保存后关闭结果；可用 result.panel.show() 主动显示。
异常会清理本次创建的 Panel/Figure，再抛出原有核心错误。

QuickPlotResult.charts/layers/conversions 均按输入顺序保存，单成员可用 .chart/.layer。
conversions 只描述初次准备，不追踪调用者后续 update。返回的内容句柄在重绘和
重排后保持身份；Axes/Subplot 仍遵循核心的代际有效性规则。
