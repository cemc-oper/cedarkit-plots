from typing import Optional, TYPE_CHECKING

import numpy as np
import pandas as pd
from cartopy import crs as ccrs

from cedarkit.maps.chart import Layer
from cedarkit.maps.map import MapType
from cedarkit.maps.types import AreaRange, GraphTitle
from cedarkit.maps.painter.map_painter import MapPainter, MapInfo
from cedarkit.maps.painter.axes_component_painter import (
    AxesComponentPainter, MapBoxOption, ColorBarOption,
)
from cedarkit.maps.painter.presets import create_global_map_painter

from .layout import LayoutConfig
from .map_template import MapTemplate

if TYPE_CHECKING:
    from cedarkit.maps.chart import Chart, Panel


#: 全球默认区域
GLOBAL_AREA = AreaRange(
    start_longitude=-180,
    end_longitude=180,
    start_latitude=-90,
    end_latitude=90,
)


class GlobalMapTemplate(MapTemplate):
    """
    全球底图布局。

    使用 PlateCarree 投影，中心经度 80°E，
    默认区域为全球范围 (-180°–180°E, -90°–90°N)，水平颜色条。

    Parameters
    ----------
    area : AreaRange or None
        地图区域范围。默认为全球范围。
    layout_config : LayoutConfig or None
        布局配置。默认为 ``LayoutConfig.global_default()``。
    axes_component_painter : AxesComponentPainter or None
        坐标轴组件配置。默认为水平色标布局。
    main_map_painter : MapPainter or None
        主图地图绑定器。默认在 ``load_map()`` 中使用全球地图预设创建。
    """
    def __init__(
            self,
            area: Optional[AreaRange] = None,
            layout_config: Optional[LayoutConfig] = None,
            axes_component_painter: Optional[AxesComponentPainter] = None,
            main_map_painter: Optional[MapPainter] = None,
    ):
        if area is None:
            area = GLOBAL_AREA

        if layout_config is None:
            layout_config = LayoutConfig.global_default()

        self.central_longitude = 80

        projection = ccrs.PlateCarree()
        map_projection = ccrs.PlateCarree(
            central_longitude=self.central_longitude,
        )
        super().__init__(
            projection=projection,
            area=area,
            map_projection=map_projection,
            layout_config=layout_config,
        )

        # 坐标轴组件
        if axes_component_painter is not None:
            self.axes_component_painter = axes_component_painter
        else:
            self.axes_component_painter = AxesComponentPainter(
                map_box_option=MapBoxOption(
                    bottom_left_point=(0, 0),
                    top_right_point=(1, 1),
                ),
                color_bar_option=ColorBarOption(
                    orientation="horizontal",
                    bottom_left_point=(0.1, -0.12),
                    top_right_point=(0.9, -0.1),
                ),
            )

        # 注入的 MapPainter（如果提供）
        if main_map_painter is not None:
            self.main_map_painter = main_map_painter

    def load_map(self):
        """
        创建主图的 MapPainter。

        如果构造函数中已注入了 painter，则跳过创建。
        使用全球地图预设（含海岸线、陆地填充）。
        """
        if self.main_map_painter is None:
            self.main_map_painter = create_global_map_painter(
                map_info=MapInfo(
                    x=0.998,
                    y=0.0022,
                    text="Scale 1:20000000 No:GS (2019) 1786",
                ),
                with_land=True,
            )

    def render_chart(self, chart: "Chart"):
        """
        渲染 Chart，不绘制地图边框。

        Parameters
        ----------
        chart : Chart
            Chart 对象。
        """
        self.render_main_layer(chart=chart)

    def render_main_layer(self, chart: "Chart") -> Layer:
        """
        渲染全球地图主图层。

        渲染顺序::

            创建图层 → set_global → 绘制地图 → 坐标轴 → 网格线

        使用 ``set_global()`` 替代 ``set_extent()``，避免 ``central_longitude`` 偏移导致的 NaN 问题。

        Parameters
        ----------
        chart : Chart
            Chart 对象。

        Returns
        -------
        Layer
            创建的主图层。
        """
        layer = self._create_main_layer(chart)
        layer.ax.set_global()
        self._apply_map(layer)
        self.setup_bindaxis(layer)
        self._apply_gridlines(layer)
        return layer

    def setup_bindaxis(self, layer: Layer):
        """
        设置全球地图坐标轴。

        使用 ``LongitudeFormatter`` / ``LatitudeFormatter`` 格式化标签，
        排除投影边界经度和极点纬度，避免 cartopy 转换时产生 NaN。

        Parameters
        ----------
        layer : Layer
            图层对象。
        """
        from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter

        ax = layer.ax
        xticks = self._get_global_xticks()
        yticks = np.arange(
            -90 + self.main_yticks_interval,
            90,
            self.main_yticks_interval,
        )

        ax.set_xticks(xticks, crs=self.projection)
        ax.set_yticks(yticks, crs=self.projection)

        ax.xaxis.set_major_formatter(LongitudeFormatter(
            zero_direction_label=True,
            degree_symbol="",
        ))
        ax.yaxis.set_major_formatter(LatitudeFormatter(
            degree_symbol="",
        ))

        ax.tick_params(axis='both', which='major', bottom=True, left=True, labelsize=5)
        ax.tick_params(axis='both', which='minor', bottom=True, left=True)

    def get_gridline_locators(self):
        """
        获取全球地图网格线位置，排除投影边界和极点。

        Returns
        -------
        tuple of ndarray
            ``(xlocator, ylocator)``。
        """
        xticks = self._get_global_xticks()
        yticks = np.arange(
            -90 + self.main_yticks_interval,
            90,
            self.main_yticks_interval,
        )
        return xticks, yticks

    def set_title(
            self,
            panel: "Panel",
            graph_name: str,
            system_name: str,
            start_time: pd.Timestamp,
            forecast_time: pd.Timedelta,
    ):
        """
        设置图表标题，使用全球地图专用格式。

        标题格式::

            左上: "{start_time} UTC Forecast t+{hours}"
            右上: "{system_name}"
            中间: "{graph_name}"

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
        graph_title = GraphTitle()
        graph_title.top_right_label = system_name
        start_time_label = start_time.strftime("%Y%m%d%H")
        forecast_hour = int(forecast_time / pd.Timedelta(hours=1))
        graph_title.top_left_label = f"{start_time_label} UTC Forecast t+{forecast_hour:03d}"
        graph_title.main_title_label = graph_name
        self._add_title_to_panel(panel=panel, graph_title=graph_title)

    def _get_global_xticks(self) -> np.ndarray:
        """
        生成全球经度 tick 位置。

        从 ``central_longitude`` 向两侧按 ``main_xticks_interval`` 生成，
        排除投影边界经度 (``central_longitude ± 180``)，并归一化到 [-180, 180] 范围。

        Returns
        -------
        ndarray
            排序后的经度 tick 数组。
        """
        cl = self.central_longitude
        interval = self.main_xticks_interval
        east = np.arange(cl, cl + 180, interval)
        west = np.arange(cl - interval, cl - 180, -interval)[::-1]
        ticks = np.concatenate([west, east])
        ticks = np.where(ticks > 180, ticks - 360, ticks)
        ticks = np.where(ticks < -180, ticks + 360, ticks)
        return np.unique(ticks)


class GlobalAreaMapTemplate(GlobalMapTemplate):
    """
    全球区域底图布局。

    继承自 ``GlobalMapTemplate``，使用更密的刻度间隔，
    并启用全球国界线。

    Parameters
    ----------
    area : AreaRange or None
        区域范围。默认继承 ``GlobalMapTemplate`` 的全球范围。
    layout_config : LayoutConfig or None
        布局配置。默认为 ``LayoutConfig.global_area()``。
    axes_component_painter : AxesComponentPainter or None
        坐标轴组件配置。默认继承 ``GlobalMapTemplate`` 的配置。
    main_map_painter : MapPainter or None
        主图地图绑定器。默认在 ``load_map()`` 中使用全球地图预设创建。
    """
    def __init__(
            self,
            area: Optional[AreaRange] = None,
            layout_config: Optional[LayoutConfig] = None,
            axes_component_painter: Optional[AxesComponentPainter] = None,
            main_map_painter: Optional[MapPainter] = None,
    ):
        if layout_config is None:
            layout_config = LayoutConfig.global_area()

        super().__init__(
            area=area,
            layout_config=layout_config,
            axes_component_painter=axes_component_painter,
            main_map_painter=main_map_painter,
        )

    def load_map(self):
        """
        创建主图的 MapPainter。

        如果构造函数中已注入了 painter，则跳过创建。
        使用全球地图预设（含海岸线、全球国界线）。
        """
        if self.main_map_painter is None:
            self.main_map_painter = create_global_map_painter(
                map_type=MapType.Global,
                map_info=MapInfo(
                    x=0.998,
                    y=0.0022,
                    text="Scale 1:20000000 No:GS (2019) 1786",
                ),
                with_global_borders=True,
            )
