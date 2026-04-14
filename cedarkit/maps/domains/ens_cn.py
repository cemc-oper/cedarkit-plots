from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from cartopy import crs as ccrs

from cedarkit.maps.style import ContourStyle
from cedarkit.maps.chart import Layer
from cedarkit.maps.util import (
    GraphTitle,
    fill_graph_title,
    set_map_box_title,
    clear_axes,
    AreaRange,
)
from cedarkit.maps.painter.axes_component_painter import (
    AxesComponentPainter, MapBoxOption, ColorBarOption,
)
from cedarkit.maps.painter.presets import create_china_map_painter

from .map_template import MapTemplate

if TYPE_CHECKING:
    from cedarkit.maps.chart import Chart, Panel


#: 集合预报中国区域（73°E–135°E, 16°N–56°N）
ENS_CN_AREA = AreaRange(
    start_longitude=73,
    end_longitude=135,
    start_latitude=16,
    end_latitude=56,
)


class EnsCNMapTemplate(MapTemplate):
    """
    集合预报中国区域底图布局（多成员网格）。

    使用 PlateCarree 投影，将多个集合成员排列在网格中，
    每个成员共享相同的地图底图和区域范围。

    布局示意（15 个成员，CTL 为 mem00）::

        CTL  [MAX]  [标题区域]
         1    2    3    4    5
         6    7    8    9   10
        11   12   13   14

    Parameters
    ----------
    enable_max : bool
        是否在第一行第二列显示 MAX 成员，默认为 False。
    """
    def __init__(self, enable_max: bool = False):
        super().__init__(
            projection=ccrs.PlateCarree(),
            area=ENS_CN_AREA,
        )

        self.member_count = 15
        self.enable_max = enable_max

        self.ncols = 5
        self.nrows = 1 + int(np.ceil((self.member_count - 1) / self.ncols))

        # 坐标轴组件（用于 colorbar）
        self.axes_component_painter = AxesComponentPainter(
            map_box_option=MapBoxOption(
                bottom_left_point=(0, 0),
                top_right_point=(1, 1),
            ),
            color_bar_option=ColorBarOption(
                orientation="vertical",
                bottom_left_point=(1.05, 0.02),
                top_right_point=(1.07, 1.0),
            ),
        )

        self._gs = None
        self._main_box_ax = None

    def load_map(self):
        """
        创建主图的 MapPainter。

        使用中国区域预设 (含海岸线、省界等，无湖泊)，所有成员共享同一个 MapPainter。
        """
        self.main_map_painter = create_china_map_painter(
            with_lakes=False,
        )

    def render_panel(self, panel: "Panel"):
        """
        渲染多成员网格布局。

        完全重写基类方法，使用 GridSpec 创建网格，为每个成员创建独立的 Chart 和 Layer。

        Parameters
        ----------
        panel : Panel
            面板对象。
        """
        self.load_map()
        fig = panel.fig

        # 外框
        ax = fig.add_axes((0, 0, 1, 1))
        clear_axes(ax)
        rect = ax.patch
        rect.set_linewidth(2)
        rect.set_edgecolor('blue')

        # 主区域（用于标题和 colorbar 定位）
        self._main_box_ax = fig.add_axes((0.05, 0.1, 0.85, 0.8))
        clear_axes(self._main_box_ax)

        # GridSpec
        self._gs = fig.add_gridspec(
            nrows=self.nrows, ncols=self.ncols,
            left=0.05, right=0.9, top=0.9, bottom=0.1,
            wspace=0, hspace=0,
        )

        chart_count = self.member_count
        if self.enable_max:
            chart_count += 1
        for _ in range(chart_count):
            panel.add_chart(domain=self)

        # CTL
        self._create_member_layer(
            panel=panel, fig=fig,
            chart_index=0, row=0, col=0, name="CTL",
        )

        # mem01 ~ mem14
        for number in range(1, self.member_count):
            row = int((number - 1) / 5) + 1
            col = (number - 1) % 5
            self._create_member_layer(
                panel=panel, fig=fig,
                chart_index=number, row=row, col=col,
                name=f"mem{number:02d}",
            )

        # MAX
        if self.enable_max:
            self._create_member_layer(
                panel=panel, fig=fig,
                chart_index=self.member_count, row=0, col=1,
                name="MAX",
            )

    def render_chart(self, chart: "Chart"):
        """
        空实现。

        EnsCN 的渲染在 ``render_panel`` 中完成，不使用基类的逐 Chart 渲染流程。

        Parameters
        ----------
        chart : Chart
            Chart 对象（未使用）。
        """
        pass

    def set_title(
            self,
            panel: "Panel",
            graph_name: str,
            system_name: str,
            start_time: pd.Timestamp,
            forecast_time: pd.Timedelta,
    ):
        """
        设置集合预报标题。

        标题分两部分：

        - 底部：起报时间和预报时效（使用 ``main_box_ax``）
        - 右上角网格：系统名称和图表名称

        Parameters
        ----------
        panel : Panel
            面板对象。
        graph_name : str
            图表名称。
        system_name : str
            系统名称。
        start_time : pd.Timestamp
            起报时间。
        forecast_time : pd.Timedelta
            预报时效。
        """
        # 底部标题
        graph_title = GraphTitle(
            left=0, bottom=-0.05, top=1.05, right=1,
        )
        fill_graph_title(
            graph_title=graph_title,
            graph_name=graph_name,
            system_name=system_name,
            start_time=start_time,
            forecast_time=forecast_time,
        )
        graph_title.top_left_label = None
        graph_title.top_right_label = None

        set_map_box_title(
            self._main_box_ax,
            graph_title=graph_title,
            fontsize=10,
        )

        # 右上角标题区域
        row = 0
        col = 1
        if self.enable_max:
            col += 1
        fig = panel.fig
        ax = fig.add_subplot(self._gs[row, col:])
        clear_axes(ax)

        title_nrows = 2
        height = 1.0 / (title_nrows + 2)

        ax.text(
            0.5, 1 - height * 1.5,
            f"{system_name}",
            horizontalalignment="center",
            verticalalignment="center",
            fontsize=15,
            color="red",
        )
        ax.text(
            0.5, 1 - height * 2.5,
            f"{graph_name}",
            horizontalalignment="center",
            verticalalignment="center",
            fontsize=15,
            color="black",
        )

    def add_colorbar(self, panel: "Panel", style: ContourStyle):
        """
        添加色标。

        使用 ``main_box_ax`` 作为定位参考，通过 AxesComponentPainter 渲染。

        Parameters
        ----------
        panel : Panel
            面板对象。
        style : ContourStyle
            等值线样式，用于确定色标的颜色和级别。

        Returns
        -------
        list
            色标对象列表。
        """
        layer = Layer(projection=None)
        layer.set_axes(self._main_box_ax)

        color_bars = self.axes_component_painter.add_colorbar(
            layer=layer,
            style=style,
        )
        return color_bars

    # =========================================
    # 内部辅助方法
    # =========================================

    def _create_member_layer(self, panel, fig, chart_index, row, col, name):
        """
        创建单个成员的图层。

        在 GridSpec 的指定位置创建 GeoAxes，添加成员名标注，复用 MapPainter 渲染地图底图。

        Parameters
        ----------
        panel : Panel
            面板对象。
        fig : matplotlib.figure.Figure
            Figure 对象。
        chart_index : int
            Chart 在 ``panel.charts`` 中的索引。
        row : int
            GridSpec 行索引。
        col : int
            GridSpec 列索引。
        name : str
            成员名称（如 "CTL"、"mem01"、"MAX"）。
        """
        ax = fig.add_subplot(
            self._gs[row, col],
            projection=self.projection,
        )
        layer = Layer(
            chart=panel.charts[chart_index],
            projection=self.projection,
        )
        layer.set_axes(ax)

        # 成员名标注
        ax.text(
            0, 1, name,
            verticalalignment="top",
            horizontalalignment='left',
            transform=ax.transAxes,
            fontsize=7,
            color="r",
        )

        # 复用 MapPainter 渲染地图
        self.main_map_painter.render_layer(layer)

        # 设置区域
        layer.set_area(area=self.area)
        ax.set_aspect('auto')
