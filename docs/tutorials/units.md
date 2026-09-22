# 显式单位准备

Style 声明期望单位，Chart 校验已准备数据，两者都不转换数值。
`cedarkit.plots.units` 不读取样式或业务参数，供快绘和 workflow 共用。

```python
from dataclasses import asdict
from cedarkit.plots.units import prepare_field, prepare_vector

prepared = prepare_field(kelvin_field, units="degC", temperature_kind="absolute")
celsius_field = prepared.field
record = asdict(prepared.conversion)  # 源/目标单位、scale、offset、语义及源声明位置

# 两个分量分别校验和转换；不把 u 的单位假定为 v 的单位。
wind = prepare_vector(u, v, units="m/s")
```

源单位从 `attrs['units']` 读取。缺失时可显式提供 `source_units=`；与已有
metadata 矛盾时拒绝，不允许用参数覆盖错误标签。向量参数是
`source_units=(u_units, v_units)`。目标 `units=` 不得从样式反推为源单位。
向量须具有相同维度、形状、坐标，且两分量为速度量纲；不指定目标时两分量
必须已经具有相同规范单位。

`prepare_field` 总是返回独立 DataArray，保留名称、坐标和深拷贝 attrs。
`units=None` 表示校验并规范化现有单位，不改变数值。恒等操作也返回不可变
`UnitConversion` 记录，`applied=False`；再次转换到相同目标不会重复偏移。
记录由调用者保存，不塞入 attrs，也不在 render/样式切换时重做转换。

## 绝对温度与温差

温度必须显式提供 `temperature_kind="absolute"|"difference"`，或在数据
`attrs['temperature_kind']` 中声明；两处声明不一致即拒绝。即便 K→K 也不猜测
语义，不依赖变量名、standard_name、样式名或产品名。

- 绝对温度 K→degC：减 273.15；温差 K→degC：数值不变。
- Fahrenheit 温差只按 5/9 缩放；绝对 Fahrenheit 还处理零点偏移。
- CEMC t2m 和 t_dew_t:cn_t 要求 degC / absolute。
- bli、kidx、pte_diff、t_dew_t 的 cn_fill/cn_line 要求 K / difference。

输入 attrs 保持原样。绘图时合法别名仅参与比较：例如 C 和 degC 等价；K 与
degC 不等价，Chart 不会自动转换。累计小时数是独立 metadata，不由单位换算
或 forecast lead time 生成；降水样式按其声明的 1/3/6/12/24 小时校验。

## 有限单位表

规范单位包含 K/degC/degF、Pa/hPa、m/mm、gpm/dagpm、m/s/km/h/knots、
1/%、J/kg、dBZ、s^-1/10^-5 s^-1、
g/(hPa cm^2 s)/10^-7 g/(hPa cm^2 s)。常用别名包括 celsius/C/°C、
m s-1、kt、percent、dbz；完整映射在 units.py。
未知单位即便源和目标同名也报错，不相容量纲报错。
不会将几何高度 m 当作位势高度 gpm，也不会自动把 kg/m² 当作 mm 雪水量。
qdiv 仅支持上述明确单位间缩放，实际源字段的单位确认留给下游产品验收。

## 快绘与 workflow 接入约定

D12-06 快绘的显式 `units=` 是目标单位：先准备数据，再选择/校验样式，
最后将准备结果绑定到 Chart。`source_units` 和 `temperature_kind` 遵循上述规则；
不传目标时不得为了匹配样式而自动转换。

D13 编译阶段可用 `conversion_rule(source, target, temperature_kind=...)`
检查声明并获得 scale/offset，不读字段值；执行阶段调用同一 `prepare_field`
并核对真实源 metadata，保留返回记录。向量使用 `prepare_vector`。
旧 plan/units.py 与 style.units/style_units 仅留给待替换的旧执行链，D13
应删除这些重复路径；新快绘不得调用它们。
