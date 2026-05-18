from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import pytest
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端，避免弹出窗口
import matplotlib.colors as mcolors

from cedarkit.maps.style import ContourStyle, BarbStyle
from cedarkit.maps.colormap import get_ncl_colormap, generate_colormap_using_ncl_colors


@pytest.fixture
def sample_start_time():
    """模拟起报时间"""
    return pd.Timestamp("2024-11-09 00:00:00")


@pytest.fixture
def sample_forecast_time():
    """模拟预报时效"""
    return pd.Timedelta("24h")


@pytest.fixture(scope="module")
def output_dir() -> Path:
    """测试图片输出目录"""
    output_path = Path(__file__).parent.parent / "output"
    output_path.mkdir(exist_ok=True)
    return output_path

# ==================== 样式 ================================

@pytest.fixture
def temperature_style():
    """温度场填充图样式 - 使用 NCL colormap"""
    color_map = get_ncl_colormap("BlAqGrYeOrReVi200")
    t_2m_level = [-12, -8, -4, 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44]
    color_index = np.array([2, 18, 34, 50, 66, 82, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200]) - 2
    t_2m_color_map = mcolors.ListedColormap(color_map(color_index))
    return ContourStyle(
        colors=t_2m_color_map,
        levels=t_2m_level,
        fill=True,
    )


@pytest.fixture
def precipitation_style():
    """降水场填充图样式 - 使用 NCL 命名颜色"""
    rain_contour_lev = np.array([0.1, 10, 25, 50, 100, 200])
    rain_color_map = generate_colormap_using_ncl_colors(
        [
            "transparent",
            "White",
            "DarkOliveGreen3",
            "forestgreen",
            "deepSkyBlue",
            "Blue",
            "Magenta",
            "deeppink4"
        ],
        name="rain"
    )
    return ContourStyle(
        colors=rain_color_map,
        levels=rain_contour_lev,
        fill=True,
    )


@pytest.fixture
def wind_barb_style():
    """风羽图样式"""
    return BarbStyle(
        length=5,
        linewidth=0.4,
        barbcolor="blue",
        flagcolor="blue",
    )


@pytest.fixture
def wind_barb_style_black():
    """风羽图样式 - 黑色（用于叠加图）"""
    return BarbStyle(
        length=4,
        linewidth=0.3,
        barbcolor="black",
        flagcolor="black",
    )


@pytest.fixture
def pressure_contour_style():
    """海平面气压等值线样式"""
    levels = np.arange(980, 1045, 5)
    return ContourStyle(
        colors="blue",
        levels=levels,
        linewidths=1,
        fill=False,
    )

# ==================== 东亚区域 fixtures ====================

@pytest.fixture
def east_asia_coords():
    """东亚区域坐标网格"""
    lons = np.linspace(70, 140, 71)  # 1.0度分辨率
    lats = np.linspace(15, 55, 41)
    return lons, lats


@pytest.fixture
def east_asia_temperature_field(east_asia_coords):
    """
    模拟 2m 温度场数据
    使用正弦函数模拟南北温度梯度 + 随机扰动
    """
    lons, lats = east_asia_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 从坐标派生参数
    lat_min, lat_max = lats.min(), lats.max()
    lon_min = lons.min()
    
    # 基础温度场：南暖北冷
    base_temp = 30 - 0.8 * (lat_grid - lat_min)
    # 添加经向变化
    lon_effect = 5 * np.sin(np.radians(lon_grid - lon_min) * 2)
    # 添加随机扰动
    noise = np.random.randn(*base_temp.shape) * 2
    
    temperature = base_temp + lon_effect + noise
    
    return xr.DataArray(
        temperature,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'degC', 'long_name': '2m Temperature'}
    )


@pytest.fixture
def east_asia_pressure_field(east_asia_coords):
    """
    模拟海平面气压场数据
    模拟一个低压中心
    """
    lons, lats = east_asia_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 从坐标派生低压中心位置（区域中心偏西）
    center_lon = (lons.min() + lons.max()) / 2
    center_lat = (lats.min() + lats.max()) / 2
    
    # 基础气压场
    base_pressure = 1013.25
    distance = np.sqrt((lon_grid - center_lon)**2 + (lat_grid - center_lat)**2)
    pressure_anomaly = -15 * np.exp(-distance**2 / 200)
    
    pressure = base_pressure + pressure_anomaly + np.random.randn(*lon_grid.shape) * 0.5
    
    return xr.DataArray(
        pressure,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'hPa', 'long_name': 'Mean Sea Level Pressure'}
    )


@pytest.fixture
def east_asia_wind_fields(east_asia_coords):
    """
    模拟风场数据 (u, v 分量)
    基于气压场模拟地转风
    """
    lons, lats = east_asia_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 从坐标派生参数
    lat_min = lats.min()
    center_lon = (lons.min() + lons.max()) / 2
    center_lat = (lats.min() + lats.max()) / 2
    
    # 模拟西风带 + 低压环流
    dx = lon_grid - center_lon
    dy = lat_grid - center_lat
    distance = np.sqrt(dx**2 + dy**2) + 0.1
    
    # 基础西风（随纬度增加）
    u_base = 5 + 0.2 * (lat_grid - lat_min)
    v_base = np.zeros_like(u_base)
    
    # 低压环流（逆时针）
    wind_speed = 10 * np.exp(-distance**2 / 300)
    u_cyclone = wind_speed * dy / distance
    v_cyclone = -wind_speed * dx / distance
    
    u = u_base + u_cyclone + np.random.randn(*lon_grid.shape) * 1
    v = v_base + v_cyclone + np.random.randn(*lon_grid.shape) * 1
    
    u_field = xr.DataArray(
        u,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'm/s', 'long_name': 'U component of wind'}
    )
    v_field = xr.DataArray(
        v,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'm/s', 'long_name': 'V component of wind'}
    )
    
    return u_field, v_field


@pytest.fixture
def east_asia_precipitation_field(east_asia_coords):
    """
    模拟降水场数据
    模拟几个降水中心
    """
    lons, lats = east_asia_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 从坐标派生降水中心位置
    lon_min, lon_max = lons.min(), lons.max()
    lat_min, lat_max = lats.min(), lats.max()
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min
    
    # 在区域内分布几个降水中心
    centers = [
        (lon_min + 0.6 * lon_range, lat_min + 0.4 * lat_range),  # 中部偏东偏南
        (lon_min + 0.7 * lon_range, lat_min + 0.25 * lat_range), # 东南部
        (lon_min + 0.5 * lon_range, lat_min + 0.5 * lat_range),  # 中部
    ]
    
    precipitation = np.zeros_like(lon_grid)
    for center_lon, center_lat in centers:
        distance = np.sqrt((lon_grid - center_lon)**2 + (lat_grid - center_lat)**2)
        precipitation += 50 * np.exp(-distance**2 / 50)
    
    # 确保非负
    precipitation = np.maximum(precipitation + np.random.randn(*lon_grid.shape) * 2, 0)
    
    return xr.DataArray(
        precipitation,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'mm', 'long_name': '24h Precipitation'}
    )

# ==================== 北极区域 fixtures ====================

@pytest.fixture
def north_polar_coords():
    """北极区域坐标网格（全球）"""
    lons = np.linspace(-180, 180, 73)  # 5度分辨率
    lats = np.linspace(0, 90, 19)
    return lons, lats


@pytest.fixture
def north_polar_temperature_field(north_polar_coords):
    """
    模拟北极区域温度场数据
    极地冷、低纬度暖
    """
    lons, lats = north_polar_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 基础温度场：极地冷、低纬度暖
    lat_max = lats.max()
    base_temp = 20 - 0.5 * lat_grid
    # 添加经向波动
    lon_effect = 3 * np.sin(np.radians(lon_grid) * 2)
    # 添加随机扰动
    noise = np.random.randn(*base_temp.shape) * 2
    
    temperature = base_temp + lon_effect + noise
    
    return xr.DataArray(
        temperature,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'degC', 'long_name': '2m Temperature'}
    )


@pytest.fixture
def north_polar_pressure_field(north_polar_coords):
    """
    模拟北极区域海平面气压场数据
    模拟极涡
    """
    lons, lats = north_polar_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 基础气压场
    base_pressure = 1013.25
    # 模拟极涡（极地低压）
    polar_low = -20 * np.exp(-((lat_grid - 90)**2) / 200)
    
    pressure = base_pressure + polar_low + np.random.randn(*lon_grid.shape) * 0.5
    
    return xr.DataArray(
        pressure,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'hPa', 'long_name': 'Mean Sea Level Pressure'}
    )


@pytest.fixture
def north_polar_wind_fields(north_polar_coords):
    """
    模拟北极区域风场数据 (u, v 分量)
    模拟极涡环流
    """
    lons, lats = north_polar_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 极涡环流（绕极地顺时针，北半球高空西风）
    # 风速随纬度变化，中纬度最强
    wind_magnitude = 10 * np.sin(np.radians(lat_grid)) * np.cos(np.radians(lat_grid))
    
    # u 分量（西风为正）
    u = wind_magnitude * np.cos(np.radians(lon_grid + 90))
    # v 分量
    v = wind_magnitude * np.sin(np.radians(lon_grid + 90))
    
    u = u + np.random.randn(*lon_grid.shape) * 1
    v = v + np.random.randn(*lon_grid.shape) * 1
    
    u_field = xr.DataArray(
        u,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'm/s', 'long_name': 'U component of wind'}
    )
    v_field = xr.DataArray(
        v,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'm/s', 'long_name': 'V component of wind'}
    )
    
    return u_field, v_field


# ==================== 欧亚区域 fixtures ====================

@pytest.fixture
def europe_asia_coords():
    """欧亚区域坐标网格"""
    lons = np.linspace(20, 170, 31)  # 5度分辨率
    lats = np.linspace(0, 70, 15)
    return lons, lats


@pytest.fixture
def europe_asia_temperature_field(europe_asia_coords):
    """
    模拟欧亚区域温度场数据
    """
    lons, lats = europe_asia_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    lat_min = lats.min()
    lon_min = lons.min()
    
    # 基础温度场：南暖北冷
    base_temp = 30 - 0.6 * (lat_grid - lat_min)
    # 添加经向变化
    lon_effect = 5 * np.sin(np.radians(lon_grid - lon_min) * 1.5)
    # 添加随机扰动
    noise = np.random.randn(*base_temp.shape) * 2
    
    temperature = base_temp + lon_effect + noise
    
    return xr.DataArray(
        temperature,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'degC', 'long_name': '2m Temperature'}
    )


@pytest.fixture
def europe_asia_pressure_field(europe_asia_coords):
    """
    模拟欧亚区域海平面气压场数据
    """
    lons, lats = europe_asia_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 从坐标派生低压中心位置
    center_lon = (lons.min() + lons.max()) / 2
    center_lat = (lats.min() + lats.max()) / 2
    
    base_pressure = 1013.25
    distance = np.sqrt((lon_grid - center_lon)**2 + (lat_grid - center_lat)**2)
    pressure_anomaly = -12 * np.exp(-distance**2 / 400)
    
    pressure = base_pressure + pressure_anomaly + np.random.randn(*lon_grid.shape) * 0.5
    
    return xr.DataArray(
        pressure,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'hPa', 'long_name': 'Mean Sea Level Pressure'}
    )


@pytest.fixture
def europe_asia_wind_fields(europe_asia_coords):
    """
    模拟欧亚区域风场数据
    """
    lons, lats = europe_asia_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    lat_min = lats.min()
    center_lon = (lons.min() + lons.max()) / 2
    center_lat = (lats.min() + lats.max()) / 2
    
    dx = lon_grid - center_lon
    dy = lat_grid - center_lat
    distance = np.sqrt(dx**2 + dy**2) + 0.1
    
    u_base = 5 + 0.15 * (lat_grid - lat_min)
    v_base = np.zeros_like(u_base)
    
    wind_speed = 8 * np.exp(-distance**2 / 500)
    u_cyclone = wind_speed * dy / distance
    v_cyclone = -wind_speed * dx / distance
    
    u = u_base + u_cyclone + np.random.randn(*lon_grid.shape) * 1
    v = v_base + v_cyclone + np.random.randn(*lon_grid.shape) * 1
    
    u_field = xr.DataArray(
        u,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'm/s', 'long_name': 'U component of wind'}
    )
    v_field = xr.DataArray(
        v,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'm/s', 'long_name': 'V component of wind'}
    )
    
    return u_field, v_field


# ==================== 全球区域 fixtures ====================

@pytest.fixture
def global_coords():
    """全球坐标网格"""
    lons = np.linspace(-180, 180, 73)  # 5度分辨率
    lats = np.linspace(-90, 90, 37)
    return lons, lats


@pytest.fixture
def global_temperature_field(global_coords):
    """
    模拟全球温度场数据
    赤道暖、两极冷
    """
    lons, lats = global_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 基础温度场：赤道暖、两极冷
    base_temp = 30 - 0.5 * np.abs(lat_grid)
    # 添加经向变化（大陆/海洋效应简化）
    lon_effect = 3 * np.sin(np.radians(lon_grid) * 2)
    # 添加随机扰动
    noise = np.random.randn(*base_temp.shape) * 2
    
    temperature = base_temp + lon_effect + noise
    
    return xr.DataArray(
        temperature,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'degC', 'long_name': '2m Temperature'}
    )


@pytest.fixture
def global_pressure_field(global_coords):
    """
    模拟全球海平面气压场数据
    模拟副热带高压带和极地低压
    """
    lons, lats = global_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    base_pressure = 1013.25
    # 副热带高压带（约30度）
    subtropical_high = 8 * np.exp(-((np.abs(lat_grid) - 30)**2) / 100)
    # 赤道低压槽
    equatorial_low = -5 * np.exp(-(lat_grid**2) / 50)
    # 极地低压
    polar_low = -10 * np.exp(-((np.abs(lat_grid) - 90)**2) / 100)
    
    pressure = base_pressure + subtropical_high + equatorial_low + polar_low
    pressure = pressure + np.random.randn(*lon_grid.shape) * 0.5
    
    return xr.DataArray(
        pressure,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'hPa', 'long_name': 'Mean Sea Level Pressure'}
    )


@pytest.fixture
def global_wind_fields(global_coords):
    """
    模拟全球风场数据
    模拟信风带、西风带
    """
    lons, lats = global_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    # 信风带（东风，0-30度）
    trade_wind_u = -5 * np.exp(-((np.abs(lat_grid) - 15)**2) / 100)
    # 西风带（西风，30-60度）
    westerly_u = 10 * np.exp(-((np.abs(lat_grid) - 45)**2) / 150)
    
    u = trade_wind_u + westerly_u + np.random.randn(*lon_grid.shape) * 1
    v = np.random.randn(*lon_grid.shape) * 2
    
    u_field = xr.DataArray(
        u,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'm/s', 'long_name': 'U component of wind'}
    )
    v_field = xr.DataArray(
        v,
        dims=['latitude', 'longitude'],
        coords={'latitude': lats, 'longitude': lons},
        attrs={'units': 'm/s', 'long_name': 'V component of wind'}
    )
    
    return u_field, v_field


# ==================== 集合预报中国区域 fixtures ====================

@pytest.fixture
def ens_cn_coords():
    """集合预报中国区域坐标网格（73°E–135°E, 16°N–56°N）"""
    lons = np.linspace(73, 133, 13)  # 5度分辨率
    lats = np.linspace(16, 56, 9)
    return lons, lats


@pytest.fixture
def ens_cn_temperature_fields(ens_cn_coords):
    """
    模拟集合预报 2m 温度场数据（15 个成员）。

    每个成员在基础场上叠加不同的随机扰动，模拟集合离散度。

    Returns
    -------
    list of xr.DataArray
        长度为 15 的温度场列表，对应 CTL + mem01~mem14。
    """
    lons, lats = ens_cn_coords
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    lat_min = lats.min()
    lon_min = lons.min()

    # 基础温度场：南暖北冷
    base_temp = 30 - 0.8 * (lat_grid - lat_min)
    lon_effect = 5 * np.sin(np.radians(lon_grid - lon_min) * 2)
    base = base_temp + lon_effect

    fields = []
    rng = np.random.RandomState(42)
    for i in range(15):
        # 每个成员加不同扰动
        perturbation = rng.randn(*base.shape) * (2 + i * 0.3)
        temperature = base + perturbation

        field = xr.DataArray(
            temperature,
            dims=['latitude', 'longitude'],
            coords={'latitude': lats, 'longitude': lons},
            attrs={'units': 'degC', 'long_name': f'2m Temperature (member {i:02d})'},
        )
        fields.append(field)

    return fields


@pytest.fixture
def ens_cn_temperature_fields_with_max(ens_cn_temperature_fields):
    """
    模拟集合预报温度场数据（15 个成员 + MAX）。

    MAX 为所有成员的逐格点最大值。

    Returns
    -------
    list of xr.DataArray
        长度为 16 的温度场列表，对应 CTL + mem01~mem14 + MAX。
    """
    fields = list(ens_cn_temperature_fields)
    stacked = xr.concat(fields, dim='member')
    max_field = stacked.max(dim='member')
    max_field.attrs = {'units': 'degC', 'long_name': '2m Temperature (MAX)'}
    fields.append(max_field)
    return fields
