"""
预设样式。

本模块封装了文档样例与集成测试常用的几种 :class:`~cedarkit.plots.style.Style`
实例（温度填充、降水填充、气压等值线、风羽）。让示例代码不必每次
重复给出色表与等级。
"""
from __future__ import annotations

import numpy as np
from cedarkit.plots.palette import get_palette
from cedarkit.plots.style import ContourStyle, BarbStyle


def temperature_style() -> ContourStyle:
    """CEMC summer temperature with native discrete colors (degrees Celsius)."""
    return ContourStyle(
        colors=get_palette("cemc.t2m.cn_summer"),
        levels=[-12, -8, -4, 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44],
        fill=True, extend="both",
    )


def precipitation_style() -> ContourStyle:
    """CEMC 24-hour precipitation with a transparent under color."""
    return ContourStyle(
        colors=get_palette("cemc.rain.cn"),
        levels=[0.1, 10, 25, 50, 100, 200], fill=True, extend="both",
    )


def pressure_contour_style() -> ContourStyle:
    """海平面气压等值线样式（蓝色实线，每 5 hPa 一根）。"""
    levels = np.arange(980, 1045, 5)
    return ContourStyle(colors="blue", levels=levels, linewidths=1.0, fill=False)


def wind_barb_style() -> BarbStyle:
    """风羽样式（蓝色）。"""
    return BarbStyle(length=5, linewidth=0.4, barbcolor="blue", flagcolor="blue")


def wind_barb_style_black() -> BarbStyle:
    """风羽样式（黑色，便于叠加在填充图上）。"""
    return BarbStyle(length=4, linewidth=0.3, barbcolor="black", flagcolor="black")
