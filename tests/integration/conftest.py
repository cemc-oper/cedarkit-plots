"""
集成测试共享 fixtures。

合成数据与样式的实际生成函数定义在 :mod:`cedarkit.plots.testing` 中，
便于文档站点中的可执行样例直接复用。本文件仅把这些函数包装成
pytest fixture。
"""
from pathlib import Path

import pandas as pd
import pytest
import matplotlib

matplotlib.use("Agg")  # 使用非交互式后端，避免弹出窗口

from cedarkit.plots.testing import synthetic_data as _sd
from cedarkit.plots.testing import styles as _styles


@pytest.fixture
def sample_start_time():
    """模拟起报时间。"""
    return pd.Timestamp("2024-11-09 00:00:00")


@pytest.fixture
def sample_forecast_time():
    """模拟预报时效。"""
    return pd.Timedelta("24h")


@pytest.fixture(scope="module")
def output_dir() -> Path:
    """测试图片输出目录。"""
    output_path = Path(__file__).parent.parent / "output"
    output_path.mkdir(exist_ok=True)
    return output_path


# ==================== 样式 ====================

@pytest.fixture
def temperature_style():
    return _styles.temperature_style()


@pytest.fixture
def precipitation_style():
    return _styles.precipitation_style()


@pytest.fixture
def wind_barb_style():
    return _styles.wind_barb_style()


@pytest.fixture
def wind_barb_style_black():
    return _styles.wind_barb_style_black()


@pytest.fixture
def pressure_contour_style():
    return _styles.pressure_contour_style()


# ==================== 东亚区域 ====================

@pytest.fixture
def east_asia_coords():
    return _sd.east_asia_coords()


@pytest.fixture
def east_asia_temperature_field(east_asia_coords):
    return _sd.east_asia_temperature_field(east_asia_coords)


@pytest.fixture
def east_asia_pressure_field(east_asia_coords):
    return _sd.east_asia_pressure_field(east_asia_coords)


@pytest.fixture
def east_asia_wind_fields(east_asia_coords):
    return _sd.east_asia_wind_fields(east_asia_coords)


@pytest.fixture
def east_asia_precipitation_field(east_asia_coords):
    return _sd.east_asia_precipitation_field(east_asia_coords)


# ==================== 北极区域 ====================

@pytest.fixture
def north_polar_coords():
    return _sd.north_polar_coords()


@pytest.fixture
def north_polar_temperature_field(north_polar_coords):
    return _sd.north_polar_temperature_field(north_polar_coords)


@pytest.fixture
def north_polar_pressure_field(north_polar_coords):
    return _sd.north_polar_pressure_field(north_polar_coords)


@pytest.fixture
def north_polar_wind_fields(north_polar_coords):
    return _sd.north_polar_wind_fields(north_polar_coords)


# ==================== 欧亚区域 ====================

@pytest.fixture
def europe_asia_coords():
    return _sd.europe_asia_coords()


@pytest.fixture
def europe_asia_temperature_field(europe_asia_coords):
    return _sd.europe_asia_temperature_field(europe_asia_coords)


@pytest.fixture
def europe_asia_pressure_field(europe_asia_coords):
    return _sd.europe_asia_pressure_field(europe_asia_coords)


@pytest.fixture
def europe_asia_wind_fields(europe_asia_coords):
    return _sd.europe_asia_wind_fields(europe_asia_coords)


# ==================== 全球 ====================

@pytest.fixture
def global_coords():
    return _sd.global_coords()


@pytest.fixture
def global_temperature_field(global_coords):
    return _sd.global_temperature_field(global_coords)


@pytest.fixture
def global_pressure_field(global_coords):
    return _sd.global_pressure_field(global_coords)


@pytest.fixture
def global_wind_fields(global_coords):
    return _sd.global_wind_fields(global_coords)


# ==================== 集合预报中国区域 ====================

@pytest.fixture
def ens_cn_coords():
    return _sd.ens_cn_coords()


@pytest.fixture
def ens_cn_temperature_fields(ens_cn_coords):
    return _sd.ens_cn_temperature_fields(ens_cn_coords)


@pytest.fixture
def ens_cn_temperature_fields_with_max(ens_cn_coords):
    return _sd.ens_cn_temperature_fields_with_max(ens_cn_coords)
