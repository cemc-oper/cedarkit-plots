from typing import Dict, Optional, Tuple, Any

import xarray as xr
import numpy as np
import matplotlib.axes
import matplotlib.contour
import matplotlib.quiver
import cartopy.crs as ccrs


def add_contourf(
        ax: matplotlib.axes.Axes,
        field: xr.DataArray,
        levels: np.ndarray,
        projection: Optional[ccrs.Projection] = None,
        y_invert: Optional[bool] = None,
        **kwargs
) -> matplotlib.contour.QuadContourSet:
    """
    添加填充图

    Parameters
    ----------
    ax
    field
        data field
    levels
        contour level list.
    projection
        map projection
    y_invert
        invert Y axis, specially for high profile plots.
    **kwargs

    Returns
    -------
    matplotlib.contour.QuadContourSet
    """
    # TODO: need change
    if isinstance(levels, np.ndarray):
        min_level = min(levels)
        max_level = max(levels)
    else:
        min_level = field.min().values
        max_level = field.max().values

    first_dim = field[field.dims[0]]
    max_dim_value = max(first_dim).values
    min_dim_value = min(first_dim).values
    if "ylim" in kwargs:
        ylim = kwargs.pop("ylim")
    else:
        if y_invert is not None and y_invert:
            ylim = (max_dim_value, min_dim_value)
        else:
            ylim = None

    c = field.plot.contourf(
        ax=ax,
        transform=projection,
        vmin=min_level,
        vmax=max_level,
        levels=levels,
        add_colorbar=False,
        add_labels=False,
        extend="both",
        ylim=ylim,
        **kwargs
    )
    return c


def add_contour(
        ax: matplotlib.axes.Axes,
        field: xr.DataArray,
        levels: np.ndarray,
        projection: Optional[ccrs.Projection] = None,
        linestyles: str = "solid",
        y_invert: Optional[bool] = None,
        **kwargs
) -> matplotlib.contour.QuadContourSet:
    """
    添加等直线图

    Parameters
    ----------
    ax
    field
        要素场
    projection
    levels
    linestyles
    y_invert
    **kwargs

    Returns
    -------
    matplotlib.contour.QuadContourSet
    """
    min_level = min(levels)
    max_level = max(levels)

    first_dim = field[field.dims[0]]
    max_dim_value = max(first_dim).values
    min_dim_value = min(first_dim).values
    if "ylim" in kwargs:
        ylim = kwargs.pop("ylim")
    else:
        if y_invert is not None and y_invert:
            ylim = (max_dim_value, min_dim_value)
        else:
            ylim = None

    c = field.plot.contour(
        ax=ax,
        transform=projection,
        vmin=min_level,
        vmax=max_level,
        levels=levels,
        add_colorbar=False,
        linestyles=linestyles,
        add_labels=False,
        ylim=ylim,
        **kwargs,
    )
    return c


def add_contour_label(
        ax: matplotlib.axes.Axes,
        contour: matplotlib.contour.QuadContourSet,
        fontsize: float = 7,
        manual: bool = False,
        inline: bool = True,
        fmt="{:.0f}".format,
        background_color: Optional[Any] = None,
        **kwargs,
):
    """
    添加等直线标签

    Parameters
    ----------
    ax
    contour
    fontsize
    manual
    inline
    fmt
    background_color
    **kwargs

    Returns
    -------

    """
    labels = ax.clabel(
        contour,
        fontsize=fontsize,
        manual=manual,
        inline=inline,
        fmt=fmt,
        **kwargs
    )
    if background_color is not None:
        for label in labels:
            label.set_bbox(dict(facecolor=background_color, edgecolor='none', pad=0.5))

    return labels


def add_barb(
        ax: matplotlib.axes.Axes,
        x_field: xr.DataArray,
        y_field: xr.DataArray,
        projection: Optional[ccrs.Projection] = None,
        length: float = 4,
        linewidth: float = 0.5,
        pivot: str = 'middle',
        barbcolor: str = "red",
        flagcolor: str = "red",
        barb_increments: Optional[Dict] = None,
        **kwargs
) -> matplotlib.quiver.Barbs:
    """
    添加风羽图

    Parameters
    ----------
    ax
    x_field
        u分量，东西风
    y_field
        v分量，南北风
    projection
    length
    linewidth
    pivot
    barbcolor
    flagcolor
    barb_increments

    Returns
    -------
    matplotlib.quiver.Barbs
    """
    x_dim_name = x_field.dims[-1]   # longitude
    y_dim_name = x_field.dims[-2]   # latitude

    # lons, lats = np.meshgrid(x_field.longitude, y_field.latitude)
    xx, yy = np.meshgrid(x_field[x_dim_name], x_field[y_dim_name])

    additional_args = dict()
    if projection is not None:
        additional_args["transform"] = projection

    # 风向杆
    barb = ax.barbs(
        xx, yy,
        x_field.data, y_field.data,
        barb_increments=barb_increments,
        length=length,
        linewidth=linewidth,
        pivot=pivot,
        barbcolor=barbcolor,
        flagcolor=flagcolor,
        # sizes=dict(
        #     width=0.35,
        #     spacing=0.14,
        # ),
        **additional_args,
        **kwargs
    )

    return barb
