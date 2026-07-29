"""
预设样式。

本模块封装了文档样例与集成测试常用的几种 :class:`~cedarkit.plots.style.Style`
实例（温度填充、降水填充、气压等值线、风羽）。让示例代码不必每次
重复给出色表与等级。
"""
from __future__ import annotations

import numpy as np
import matplotlib.colors as mcolors

from cedarkit.plots.colormap import (
    get_ncl_colormap,
    generate_colormap_using_ncl_colors,
)
from cedarkit.plots.style import ContourStyle, BarbStyle


def temperature_style() -> ContourStyle:
    """温度填充样式（NCL ``BlAqGrYeOrReVi200`` 色表）。"""
    color_map = get_ncl_colormap("BlAqGrYeOrReVi200")
    levels = [-12, -8, -4, 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44]
    color_index = np.array(
        [2, 18, 34, 50, 66, 82, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200]
    ) - 2
    listed = mcolors.ListedColormap(color_map(color_index))
    return ContourStyle(colors=listed, levels=levels, fill=True)


def precipitation_style() -> ContourStyle:
    """24 小时降水填充样式（使用 NCL 命名颜色组合）。"""
    levels = np.array([0.1, 10, 25, 50, 100, 200])
    cmap = generate_colormap_using_ncl_colors(
        [
            "transparent",
            "White",
            "DarkOliveGreen3",
            "forestgreen",
            "deepSkyBlue",
            "Blue",
            "Magenta",
            "deeppink4",
        ],
        name="rain",
    )
    return ContourStyle(colors=cmap, levels=levels, fill=True)


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
