from typing import Optional, TYPE_CHECKING

import xarray as xr
import numpy as np
import matplotlib.axes
import matplotlib.colors as mcolors
import matplotlib.contour
import matplotlib.quiver
import cartopy.crs as ccrs

from cedarkit.plots.style import ContourStyle, BarbStyle, ContourLabelStyle
from cedarkit.plots.graph import (
    add_contourf,
    add_contour,
    add_contour_label,
    add_barb,
)
from cedarkit.plots.types import AreaRange
from cedarkit.plots.bindutils import (
    set_map_box_area,
    set_map_box_axis,
    draw_map_box_gridlines,
)

if TYPE_CHECKING:
    from cedarkit.plots.chart import Chart


class Layer:
    """
    A layer is a map box in a ``Chart``. Each layer has a ``matplotlib.axes.Axes`` attribute to draw plots.

    Attributes
    ----------
    ax
        axes to draw plots, which is created outside ``Layer`` object.
    projection
        ``ccrs.Projection`` for all plots in this layer.
    chart
        ``Chart`` who owns this ``Layer``.
    """
    def __init__(
            self,
            projection: Optional[ccrs.Projection] = None,
            chart: Optional["Chart"] = None
    ):
        self.ax: Optional[matplotlib.axes.Axes] = None
        self.projection = projection

        if chart is not None:
            self.set_chart(chart)
        else:
            self.chart = None

    def set_axes(self, ax: matplotlib.axes.Axes):
        self.ax = ax

    def set_chart(self, chart: "Chart"):
        """
        Add ``Layer`` to a ``Chart``.

        Parameters
        ----------
        chart
        """
        self.chart = chart
        self.chart.add_layer(self)

    def set_area(self, area: AreaRange, aspect: Optional[float] = None):
        """
        Set map area range and aspect of width and height

        Parameters
        ----------
        area
        aspect
        """
        ax = self.ax
        set_map_box_area(
            ax,
            area=area,
            projection=self.projection,
            aspect=aspect,
        )

    def set_axis(self, xticks: np.ndarray, yticks: np.ndarray):
        ax = self.ax
        set_map_box_axis(
            ax,
            xticks=xticks,
            yticks=yticks,
            projection=self.projection
        )

    def gridlines(
            self,
            xlocator: Optional[np.ndarray] = None,
            ylocator: Optional[np.ndarray] = None,
            **kwargs
    ):
        ax = self.ax
        draw_map_box_gridlines(
            ax,
            projection=self.projection,
            xlocator=xlocator,
            ylocator=ylocator,
            **kwargs
        )

    # ---------------
    # Plot methods
    # ---------------

    def contourf(self, data: xr.DataArray, style: ContourStyle, **kwargs) -> matplotlib.contour.QuadContourSet:
        contour = add_contourf(
            self.ax,
            field=data,
            levels=style.levels,
            projection=self.projection,
            cmap=style.colors,
            **kwargs
        )
        if style.label:
            label = Layer.contour_label(self.ax, contour, style.label_style)
        return contour

    def contour(self, data: xr.DataArray, style: ContourStyle, **kwargs) -> matplotlib.contour.QuadContourSet:
        # matplotlib's contour() expects colors as a sequence, not a Colormap.
        # Convert ListedColormap/Colormap to a color list for compatibility.
        colors = style.colors
        if isinstance(colors, mcolors.Colormap):
            colors = [colors(i) for i in range(colors.N)]

        contour = add_contour(
            self.ax,
            field=data,
            levels=style.levels,
            projection=self.projection,
            colors=colors,
            linewidths=style.linewidths,
            linestyles=style.linestyles,
            **kwargs
        )
        if style.label:
            label = Layer.contour_label(self.ax, contour, style.label_style)

        return contour

    @classmethod
    def contour_label(cls, ax, contour, style: ContourLabelStyle):
        kwargs = dict(
            levels=style.levels,
            fontsize=style.fontsize,
            inline=style.inline,
            inline_spacing=style.inline_spacing,
            fmt=style.fmt,
            colors=style.colors,
            background_color=style.background_color,
            manual=style.manual,
            zorder=style.zorder,
        )

        labels = add_contour_label(
            ax,
            contour=contour,
            **kwargs
        )
        return labels

    def barb(self, x: xr.DataArray, y: xr.DataArray, style: BarbStyle, **kwargs) -> matplotlib.quiver.Barbs:
        additional_kwargs = dict()
        if self.projection is not None:
            additional_kwargs["regrid_shape"] = 20

        barb = add_barb(
            self.ax,
            x_field=x,
            y_field=y,
            projection=self.projection,
            barb_increments=style.barb_increments,
            length=style.length,
            linewidth=style.linewidth,
            pivot=style.pivot,
            barbcolor=style.barbcolor,
            flagcolor=style.flagcolor,
            **additional_kwargs,
            **kwargs,
        )
        return barb

