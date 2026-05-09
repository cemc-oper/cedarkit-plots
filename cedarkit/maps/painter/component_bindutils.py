from typing import List, Optional

import pandas as pd
import matplotlib as mpl
import matplotlib.axes
import matplotlib.figure
import matplotlib.colorbar
import matplotlib.text
import matplotlib.colors as mcolors
import cartopy.mpl.geoaxes

from cedarkit.maps.types import GraphTitle, GraphColorbar


def fill_graph_title(
        graph_title: GraphTitle,
        graph_name: str,
        system_name: str,
        start_time: pd.Timestamp,
        forecast_time: pd.Timedelta,
) -> GraphTitle:
    """
    Fill four corner titles in ``GraphTitle`` object.

    graph_name                                   system_name
    ————————————————————————————————————————————————————————
    |                                                      |
    |                                                      |
    |                     Axes box                         |
    |                                                      |
    |                                                      |
    ————————————————————————————————————————————————————————
    start time + forecast hour (UTC)        valid time (UTC)
    start time + forecast hour (CST)        valid time (CST)


    Parameters
    ----------
    graph_title
    graph_name
    system_name
    start_time
    forecast_time

    Returns
    -------
    GraphTitle
    """
    utc_start_time_label = start_time.strftime('%Y%m%d%H')
    utc_valid_time_label = (start_time + forecast_time).strftime('%Y%m%d%H')
    cst_start_time_label = (start_time + pd.Timedelta(hours=8)).strftime('%Y%m%d%H')
    cst_valid_time_label = (start_time + forecast_time + pd.Timedelta(hours=8)).strftime('%Y%m%d%H')
    forecast_time_label = f"{int(forecast_time / pd.Timedelta(hours=1)):02}"
    graph_title.top_left_label = graph_name
    graph_title.top_right_label = system_name
    graph_title.bottom_left_label = f"{utc_start_time_label}+{forecast_time_label}h\n{cst_start_time_label}+{forecast_time_label}h"
    graph_title.bottom_right_label = f"{utc_valid_time_label}(UTC)\n{cst_valid_time_label}(CST)"

    return graph_title


def set_map_box_title(
        ax: matplotlib.axes.Axes,
        graph_title: GraphTitle,
        fontsize: Optional[float] = None,
        main_fontsize: Optional[float] = None,
) -> List[matplotlib.text.Text]:
    """
    为图形边框设置标题

    Parameters
    ----------
    ax
    graph_title
    fontsize

    Returns
    -------
    List[matplotlib.text.Text]
    """
    if fontsize is None:
        fontsize = 7
    if main_fontsize is None:
        main_fontsize = 10

    left = graph_title.left
    bottom = graph_title.bottom
    top = graph_title.top
    right = graph_title.right
    main_pos = graph_title.main_pos

    top_left = graph_title.top_left_label
    top_right = graph_title.top_right_label
    bottom_left = graph_title.bottom_left_label
    bottom_right = graph_title.bottom_right_label
    main_title = graph_title.main_title_label

    if top_left is None:
        top_left_text = None
    else:
        top_left_text = ax.text(
            left,
            top,
            top_left,
            verticalalignment="bottom",
            horizontalalignment='left',
            transform=ax.transAxes,
            fontsize=fontsize,
        )

    if top_right is None:
        top_right_text = None
    else:
        top_right_text = ax.text(
            right,
            top,
            top_right,
            verticalalignment="bottom",
            horizontalalignment='right',
            transform=ax.transAxes,
            fontsize=fontsize,
        )

    if bottom_left is None:
        bottom_left_text = None
    else:
        bottom_left_text = ax.text(
            left,
            bottom,
            bottom_left,
            verticalalignment='top',
            horizontalalignment='left',
            transform=ax.transAxes,
            fontsize=fontsize
        )

    if bottom_right is None:
        bottom_right_text = None
    else:
        bottom_right_text = ax.text(
            right,
            bottom,
            bottom_right,
            verticalalignment='top',
            horizontalalignment='right',
            transform=ax.transAxes,
            fontsize=fontsize
        )

    if main_title is None:
        main_title_text = None
    else:
        main_title_text = ax.text(
            main_pos[0], main_pos[1],
            main_title,
            verticalalignment="bottom",
            horizontalalignment='center',
            transform=ax.transAxes,
            fontsize=main_fontsize,
        )

    return [top_left_text, top_right_text, bottom_left_text, bottom_right_text, main_title_text]



def add_map_box_colorbar(
        graph_colorbar: GraphColorbar,
        ax: Optional[matplotlib.axes.Axes] = None,
        fig: Optional[matplotlib.figure.Figure] = None,
        tick_fontsize: Optional[float] = None,
        tick_pad: Optional[float] = None,
) -> matplotlib.colorbar.Colorbar:
    """
    Add colorbar for an axes.

    Parameters
    ----------
    graph_colorbar
    ax
        if ax is set, colorbar is added based on ax according to ``box`` attribute in ``graph_colorbar``.
    fig
        if fig is set, colorbar is added based on figure according to ``box`` attribute in ``graph_colorbar``.

    Returns
    -------
    matplotlib.colorbar.Colorbar
    """
    colorbar_box = graph_colorbar.box
    levels = graph_colorbar.levels
    colormap = graph_colorbar.colormap

    orientation = graph_colorbar.orientation

    if tick_fontsize is None:
        tick_fontsize = 7
    if tick_pad is None:
        tick_pad = 7

    label_levels = graph_colorbar.label_levels
    if label_levels is None:
        label_levels = levels

    if ax is not None:
        cax = ax.inset_axes(colorbar_box)
    elif fig is not None:
        cax = fig.add_axes(colorbar_box)
    else:
        raise ValueError(f"either ax or fig should be provided.")

    norm = mcolors.BoundaryNorm(levels, colormap.N, extend="both")
    cbar = cax.get_figure().colorbar(
        mpl.cm.ScalarMappable(norm=norm, cmap=colormap),
        cax=cax,
        orientation=orientation,
        spacing='uniform',
        ticks=label_levels,
        drawedges=True,
        extendrect=True,
        extendfrac='auto',  # 延伸相同长度
    )
    cbar.ax.tick_params(
        "both",
        which="major",
        left=False,
        right=False,
        labelsize=tick_fontsize
    )
    # ticklabs = cbar.ax.get_yticklabels()
    if orientation == "vertical":
        cbar.ax.set_yticklabels(label_levels, ha='center')
        cbar.ax.yaxis.set_tick_params(pad=tick_pad)
    elif orientation == "horizontal":
        cbar.ax.set_xticklabels(label_levels, ha='center')
        cbar.ax.xaxis.set_tick_params(pad=tick_pad)
    else:
        ...

    if graph_colorbar.label is not None:
        if graph_colorbar.label_loc is not None:
            label_loc = graph_colorbar.label_loc
        else:
            label_loc = None
        cbar.set_label(
            label=graph_colorbar.label,
            loc=label_loc,
        )

    return cbar


def add_map_info_text(
        ax: cartopy.mpl.geoaxes.GeoAxes,
        x: float,
        y: float,
        text: str
):
    text_box = ax.text(
        x, y, text,
        verticalalignment='bottom',
        horizontalalignment='right',
        transform=ax.transAxes,
        fontsize=3,
        bbox=dict(
            boxstyle="round",
            edgecolor="black",
            facecolor="white",
            linewidth=0.5,
        )
    )
    return text_box
