"""
Testing 工具模块。

本子包提供一组用于生成合成气象场和绘图样式的辅助函数，既被
``cedarkit-plots`` 的集成测试套件使用，也被文档站点中的
绘图样例复用。所有函数都不依赖真实的 NWP 数据，可以在任何
有 numpy/xarray 的环境下生成 :class:`xarray.DataArray`。
"""
from .synthetic_data import (
    east_asia_temperature_field,
    east_asia_pressure_field,
    east_asia_wind_fields,
    east_asia_precipitation_field,
    europe_asia_temperature_field,
    europe_asia_pressure_field,
    europe_asia_wind_fields,
    global_temperature_field,
    global_pressure_field,
    global_wind_fields,
    north_polar_temperature_field,
    north_polar_pressure_field,
    north_polar_wind_fields,
    ens_cn_temperature_fields,
    ens_cn_temperature_fields_with_max,
)
from .styles import (
    temperature_style,
    precipitation_style,
    pressure_contour_style,
    wind_barb_style,
    wind_barb_style_black,
)

__all__ = [
    "east_asia_temperature_field",
    "east_asia_pressure_field",
    "east_asia_wind_fields",
    "east_asia_precipitation_field",
    "europe_asia_temperature_field",
    "europe_asia_pressure_field",
    "europe_asia_wind_fields",
    "global_temperature_field",
    "global_pressure_field",
    "global_wind_fields",
    "north_polar_temperature_field",
    "north_polar_pressure_field",
    "north_polar_wind_fields",
    "ens_cn_temperature_fields",
    "ens_cn_temperature_fields_with_max",
    "temperature_style",
    "precipitation_style",
    "pressure_contour_style",
    "wind_barb_style",
    "wind_barb_style_black",
]
