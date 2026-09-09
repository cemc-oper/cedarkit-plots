from typing import Optional, Tuple

import numpy as np
import matplotlib.axes
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import cartopy.mpl.geoaxes
import cartopy.mpl.gridliner
from cartopy import crs as ccrs
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter

from cedarkit.plots.types import AreaRange


def set_map_box_area(
        ax: cartopy.mpl.geoaxes.GeoAxes,
        area: AreaRange,
        projection: ccrs.Projection,
        aspect: Optional[float] = None
) -> cartopy.mpl.geoaxes.GeoAxes:
    """
    set map box area and aspect.

    Parameters
    ----------
    ax
    area
    projection
    aspect

    Returns
    -------
    cartopy.mpl.geoaxes.GeoAxes
    """
    area_tuple = area.to_tuple()
    east_lon, west_lon, south_lat, north_lat = area_tuple
    ax.set_extent(
        area_tuple,
        crs=projection
    )
    if aspect is None:
        return ax
    ax.set_aspect((abs(west_lon - east_lon) / aspect) / (abs(north_lat - south_lat) / 1.0), adjustable="box")
    return ax


def set_map_box_axis(
        ax: cartopy.mpl.geoaxes.GeoAxes,
        xticks: np.ndarray,
        yticks: np.ndarray,
        projection: ccrs.Projection
) -> cartopy.mpl.geoaxes.GeoAxes:
    """
    set axis ticks and tick labels for map box.

    Parameters
    ----------
    ax
    xticks
    yticks
    projection

    Returns
    -------
    cartopy.mpl.geoaxes.GeoAxes
    """
    # 坐标轴样式
    lon_formatter = LongitudeFormatter(
        zero_direction_label=True,
        degree_symbol="",
    )
    lat_formatter = LatitudeFormatter(
        degree_symbol=""
    )
    ax.xaxis.set_major_formatter(lon_formatter)
    ax.yaxis.set_major_formatter(lat_formatter)
    #   标签位置
    ax.set_xticks(xticks, crs=projection)
    ax.set_yticks(yticks, crs=projection)
    #   标签大小
    ax.tick_params(
        "both",
        which="major",
        bottom=False,
        top=False,
        left=False,
        right=False,
        labelsize=5
    )
    return ax


def draw_map_box_gridlines(
        ax: cartopy.mpl.geoaxes.GeoAxes,
        projection: ccrs.Projection,
        xlocator: Optional[np.ndarray] = None,
        ylocator: Optional[np.ndarray] = None,
        linewidth: float = 0.5,
        color: str = "grey",
        alpha: float = 0.5,
        linetyle: str = "--",
        **kwargs,
) -> cartopy.mpl.gridliner.Gridliner:
    """
    draw gridlines for map box

    Parameters
    ----------
    ax
    projection
    xlocator
    ylocator
    linewidth
    color
    alpha
    linetyle
    kwargs

    Returns
    -------
    cartopy.mpl.gridliner.Gridliner
    """
    gl = ax.gridlines(
        crs=projection,
        draw_labels=False,
        linewidth=linewidth,
        color=color,
        alpha=alpha,
        linestyle=linetyle,
        **kwargs,
    )
    if ylocator is not None:
        gl.ylocator = mticker.FixedLocator(ylocator)
    if xlocator is not None:
        gl.xlocator = mticker.FixedLocator(xlocator)
    return gl


def draw_map_box(
        ax: matplotlib.axes.Axes,
        bottom_left_point: Tuple[float, float],
        top_right_point: Tuple[float, float],
        edgecolor="black",
        fill=False,
        linewidth=1.3,
        zorder=1000,
        **kwargs,
) -> mpatches.Rectangle:
    """
    为图形添加矩形边框

    Parameters
    ----------
    ax
    bottom_left_point
    top_right_point
    edgecolor
    fill
    linewidth
    zorder
    kwargs

    Returns
    -------
    mpatches.Rectangle
    """
    width = top_right_point[0] - bottom_left_point[0]
    height = top_right_point[1] - bottom_left_point[1]

    rect = mpatches.Rectangle(
        bottom_left_point, width, height,
        transform=ax.transAxes,
        edgecolor=edgecolor,
        fill=fill,
        zorder=zorder,
        lw=linewidth,
        **kwargs
    )
    rect = ax.add_patch(rect)
    rect.set_clip_on(False)
    return rect
