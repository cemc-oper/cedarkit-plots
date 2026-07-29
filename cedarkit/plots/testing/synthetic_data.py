"""
合成气象场。

本模块提供一组用解析公式构造的 :class:`xarray.DataArray`，
模拟温度、海平面气压、风场、降水等常见气象要素。
所有函数都接收一对一维经纬度坐标数组，返回二维 ``DataArray``。

每一个函数内部都使用一个固定的随机种子，从而保证多次调用结果
完全一致——这是文档构建可重复、测试可断言的前提。
"""
from __future__ import annotations

from typing import Tuple, List

import numpy as np
import xarray as xr


# --------------------------------------------------------------------------- #
# 通用坐标网格
# --------------------------------------------------------------------------- #


def east_asia_coords(resolution: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """东亚区域 1° 经纬网（70°E–140°E, 15°N–55°N）。"""
    lons = np.arange(70.0, 140.0 + resolution, resolution)
    lats = np.arange(15.0, 55.0 + resolution, resolution)
    return lons, lats


def europe_asia_coords(resolution: float = 5.0) -> Tuple[np.ndarray, np.ndarray]:
    """欧亚区域 5° 经纬网（20°E–170°E, 0°N–70°N）。"""
    lons = np.arange(20.0, 170.0 + resolution, resolution)
    lats = np.arange(0.0, 70.0 + resolution, resolution)
    return lons, lats


def global_coords(resolution: float = 5.0) -> Tuple[np.ndarray, np.ndarray]:
    """全球 5° 经纬网。"""
    lons = np.arange(-180.0, 180.0 + resolution, resolution)
    lats = np.arange(-90.0, 90.0 + resolution, resolution)
    return lons, lats


def north_polar_coords(resolution: float = 5.0) -> Tuple[np.ndarray, np.ndarray]:
    """北极区域 5° 经纬网（全经度，0°N–90°N）。"""
    lons = np.arange(-180.0, 180.0 + resolution, resolution)
    lats = np.arange(0.0, 90.0 + resolution, resolution)
    return lons, lats


def ens_cn_coords(resolution: float = 5.0) -> Tuple[np.ndarray, np.ndarray]:
    """集合预报中国区域 5° 经纬网（73°E–133°E, 16°N–56°N）。"""
    lons = np.arange(73.0, 133.0 + resolution, resolution)
    lats = np.arange(16.0, 56.0 + resolution, resolution)
    return lons, lats


# --------------------------------------------------------------------------- #
# 内部辅助
# --------------------------------------------------------------------------- #


def _build_da(values, lats, lons, *, units, long_name) -> xr.DataArray:
    return xr.DataArray(
        values,
        dims=["latitude", "longitude"],
        coords={"latitude": lats, "longitude": lons},
        attrs={"units": units, "long_name": long_name},
    )


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


# --------------------------------------------------------------------------- #
# 东亚区域
# --------------------------------------------------------------------------- #


def east_asia_temperature_field(coords=None) -> xr.DataArray:
    """模拟东亚 2 米温度（°C），呈现南暖北冷的分布。"""
    lons, lats = coords if coords is not None else east_asia_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(11)

    base = 30.0 - 0.8 * (lat2d - lats.min())
    lon_eff = 5.0 * np.sin(np.radians(lon2d - lons.min()) * 2.0)
    noise = rng.standard_normal(base.shape) * 2.0
    return _build_da(base + lon_eff + noise, lats, lons,
                     units="degC", long_name="2m Temperature")


def east_asia_pressure_field(coords=None) -> xr.DataArray:
    """模拟东亚海平面气压（hPa），含一个低压中心。"""
    lons, lats = coords if coords is not None else east_asia_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(12)

    cx = (lons.min() + lons.max()) / 2.0
    cy = (lats.min() + lats.max()) / 2.0
    base = 1013.25
    distance = np.sqrt((lon2d - cx) ** 2 + (lat2d - cy) ** 2)
    anomaly = -15.0 * np.exp(-(distance ** 2) / 200.0)
    noise = rng.standard_normal(lon2d.shape) * 0.5
    return _build_da(base + anomaly + noise, lats, lons,
                     units="hPa", long_name="Mean Sea Level Pressure")


def east_asia_wind_fields(coords=None) -> Tuple[xr.DataArray, xr.DataArray]:
    """模拟东亚 ``(u, v)`` 风场，叠加西风与气旋环流。"""
    lons, lats = coords if coords is not None else east_asia_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(13)

    cx = (lons.min() + lons.max()) / 2.0
    cy = (lats.min() + lats.max()) / 2.0

    dx = lon2d - cx
    dy = lat2d - cy
    distance = np.sqrt(dx ** 2 + dy ** 2) + 0.1

    u_base = 5.0 + 0.2 * (lat2d - lats.min())
    wind_speed = 10.0 * np.exp(-(distance ** 2) / 300.0)
    u_cyc = wind_speed * dy / distance
    v_cyc = -wind_speed * dx / distance

    u = u_base + u_cyc + rng.standard_normal(lon2d.shape)
    v = v_cyc + rng.standard_normal(lon2d.shape)

    u_da = _build_da(u, lats, lons, units="m/s", long_name="U component of wind")
    v_da = _build_da(v, lats, lons, units="m/s", long_name="V component of wind")
    return u_da, v_da


def east_asia_precipitation_field(coords=None) -> xr.DataArray:
    """模拟东亚 24 小时降水（mm），由若干降水中心叠加而成。"""
    lons, lats = coords if coords is not None else east_asia_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(14)

    lon_min, lon_max = lons.min(), lons.max()
    lat_min, lat_max = lats.min(), lats.max()
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min
    centers = [
        (lon_min + 0.6 * lon_range, lat_min + 0.4 * lat_range),
        (lon_min + 0.7 * lon_range, lat_min + 0.25 * lat_range),
        (lon_min + 0.5 * lon_range, lat_min + 0.5 * lat_range),
    ]
    precip = np.zeros_like(lon2d)
    for cx, cy in centers:
        distance = np.sqrt((lon2d - cx) ** 2 + (lat2d - cy) ** 2)
        precip += 50.0 * np.exp(-(distance ** 2) / 50.0)
    precip = np.maximum(precip + rng.standard_normal(lon2d.shape) * 2.0, 0.0)
    return _build_da(precip, lats, lons, units="mm", long_name="24h Precipitation")


# --------------------------------------------------------------------------- #
# 欧亚区域
# --------------------------------------------------------------------------- #


def europe_asia_temperature_field(coords=None) -> xr.DataArray:
    lons, lats = coords if coords is not None else europe_asia_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(21)

    base = 30.0 - 0.6 * (lat2d - lats.min())
    lon_eff = 5.0 * np.sin(np.radians(lon2d - lons.min()) * 1.5)
    noise = rng.standard_normal(base.shape) * 2.0
    return _build_da(base + lon_eff + noise, lats, lons,
                     units="degC", long_name="2m Temperature")


def europe_asia_pressure_field(coords=None) -> xr.DataArray:
    lons, lats = coords if coords is not None else europe_asia_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(22)

    cx = (lons.min() + lons.max()) / 2.0
    cy = (lats.min() + lats.max()) / 2.0
    base = 1013.25
    distance = np.sqrt((lon2d - cx) ** 2 + (lat2d - cy) ** 2)
    anomaly = -12.0 * np.exp(-(distance ** 2) / 400.0)
    noise = rng.standard_normal(lon2d.shape) * 0.5
    return _build_da(base + anomaly + noise, lats, lons,
                     units="hPa", long_name="Mean Sea Level Pressure")


def europe_asia_wind_fields(coords=None) -> Tuple[xr.DataArray, xr.DataArray]:
    lons, lats = coords if coords is not None else europe_asia_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(23)

    cx = (lons.min() + lons.max()) / 2.0
    cy = (lats.min() + lats.max()) / 2.0
    dx = lon2d - cx
    dy = lat2d - cy
    distance = np.sqrt(dx ** 2 + dy ** 2) + 0.1

    u_base = 5.0 + 0.15 * (lat2d - lats.min())
    wind_speed = 8.0 * np.exp(-(distance ** 2) / 500.0)
    u_cyc = wind_speed * dy / distance
    v_cyc = -wind_speed * dx / distance

    u = u_base + u_cyc + rng.standard_normal(lon2d.shape)
    v = v_cyc + rng.standard_normal(lon2d.shape)
    return (
        _build_da(u, lats, lons, units="m/s", long_name="U component of wind"),
        _build_da(v, lats, lons, units="m/s", long_name="V component of wind"),
    )


# --------------------------------------------------------------------------- #
# 全球
# --------------------------------------------------------------------------- #


def global_temperature_field(coords=None) -> xr.DataArray:
    lons, lats = coords if coords is not None else global_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(31)

    base = 30.0 - 0.5 * np.abs(lat2d)
    lon_eff = 3.0 * np.sin(np.radians(lon2d) * 2.0)
    noise = rng.standard_normal(base.shape) * 2.0
    return _build_da(base + lon_eff + noise, lats, lons,
                     units="degC", long_name="2m Temperature")


def global_pressure_field(coords=None) -> xr.DataArray:
    lons, lats = coords if coords is not None else global_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(32)

    base = 1013.25
    subtropical = 8.0 * np.exp(-((np.abs(lat2d) - 30) ** 2) / 100.0)
    equatorial = -5.0 * np.exp(-(lat2d ** 2) / 50.0)
    polar = -10.0 * np.exp(-((np.abs(lat2d) - 90) ** 2) / 100.0)
    noise = rng.standard_normal(lon2d.shape) * 0.5
    return _build_da(base + subtropical + equatorial + polar + noise,
                     lats, lons,
                     units="hPa", long_name="Mean Sea Level Pressure")


def global_wind_fields(coords=None) -> Tuple[xr.DataArray, xr.DataArray]:
    lons, lats = coords if coords is not None else global_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(33)

    trade_u = -5.0 * np.exp(-((np.abs(lat2d) - 15) ** 2) / 100.0)
    westerly_u = 10.0 * np.exp(-((np.abs(lat2d) - 45) ** 2) / 150.0)
    u = trade_u + westerly_u + rng.standard_normal(lon2d.shape)
    v = rng.standard_normal(lon2d.shape) * 2.0
    return (
        _build_da(u, lats, lons, units="m/s", long_name="U component of wind"),
        _build_da(v, lats, lons, units="m/s", long_name="V component of wind"),
    )


# --------------------------------------------------------------------------- #
# 北极
# --------------------------------------------------------------------------- #


def north_polar_temperature_field(coords=None) -> xr.DataArray:
    lons, lats = coords if coords is not None else north_polar_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(41)

    base = 20.0 - 0.5 * lat2d
    lon_eff = 3.0 * np.sin(np.radians(lon2d) * 2.0)
    noise = rng.standard_normal(base.shape) * 2.0
    return _build_da(base + lon_eff + noise, lats, lons,
                     units="degC", long_name="2m Temperature")


def north_polar_pressure_field(coords=None) -> xr.DataArray:
    lons, lats = coords if coords is not None else north_polar_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(42)

    base = 1013.25
    polar_low = -20.0 * np.exp(-((lat2d - 90) ** 2) / 200.0)
    noise = rng.standard_normal(lon2d.shape) * 0.5
    return _build_da(base + polar_low + noise, lats, lons,
                     units="hPa", long_name="Mean Sea Level Pressure")


def north_polar_wind_fields(coords=None) -> Tuple[xr.DataArray, xr.DataArray]:
    lons, lats = coords if coords is not None else north_polar_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    rng = _rng(43)

    magnitude = 10.0 * np.sin(np.radians(lat2d)) * np.cos(np.radians(lat2d))
    u = magnitude * np.cos(np.radians(lon2d + 90.0)) + rng.standard_normal(lon2d.shape)
    v = magnitude * np.sin(np.radians(lon2d + 90.0)) + rng.standard_normal(lon2d.shape)
    return (
        _build_da(u, lats, lons, units="m/s", long_name="U component of wind"),
        _build_da(v, lats, lons, units="m/s", long_name="V component of wind"),
    )


# --------------------------------------------------------------------------- #
# 集合预报中国区域
# --------------------------------------------------------------------------- #


def ens_cn_temperature_fields(coords=None, member_count: int = 15) -> List[xr.DataArray]:
    """生成 ``member_count`` 个 2 米温度场，对应 CTL+扰动成员。"""
    lons, lats = coords if coords is not None else ens_cn_coords()
    lon2d, lat2d = np.meshgrid(lons, lats)
    base = 30.0 - 0.8 * (lat2d - lats.min())
    lon_eff = 5.0 * np.sin(np.radians(lon2d - lons.min()) * 2.0)
    base = base + lon_eff

    rng = np.random.RandomState(42)
    fields = []
    for i in range(member_count):
        perturbation = rng.randn(*base.shape) * (2.0 + i * 0.3)
        fields.append(_build_da(
            base + perturbation, lats, lons,
            units="degC", long_name=f"2m Temperature (member {i:02d})",
        ))
    return fields


def ens_cn_temperature_fields_with_max(coords=None, member_count: int = 15) -> List[xr.DataArray]:
    """在 :func:`ens_cn_temperature_fields` 基础上追加逐格点最大值场。"""
    fields = list(ens_cn_temperature_fields(coords=coords, member_count=member_count))
    stacked = xr.concat(fields, dim="member")
    max_field = stacked.max(dim="member")
    max_field.attrs = {"units": "degC", "long_name": "2m Temperature (MAX)"}
    fields.append(max_field)
    return fields
