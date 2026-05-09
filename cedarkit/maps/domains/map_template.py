from dataclasses import dataclass, field
from typing import List, Optional, Union, Tuple, TYPE_CHECKING

import numpy as np
import pandas as pd
import cartopy.crs as ccrs

from cedarkit.maps.style import ContourStyle
from cedarkit.maps.types import AreaRange, AxesRect, GraphTitle
from cedarkit.maps.painter.component_bindutils import fill_graph_title
from cedarkit.maps.map import get_map_loader_class
from cedarkit.maps.template import XYTemplate
from cedarkit.maps.domains.layout import LayoutConfig

if TYPE_CHECKING:
    from cedarkit.maps.chart import Chart, Panel, Layer
    from cedarkit.maps.painter.map_painter import MapPainter
    from cedarkit.maps.painter.axes_component_painter import AxesComponentPainter


@dataclass
class SubMapConfig:
    """
    子图（如南海子图）的配置。

    Attributes
    ----------
    area : AreaRange
        子图区域范围。
    width : float
        子图宽度（相对于 figure）。
    height : float
        子图高度（相对于 figure）。
    aspect : float or None
        子图长宽比，默认为 ``width / height``。
    xlocator : list
        子图经度网格线位置。
    ylocator : list
        子图纬度网格线位置。
    gridline_width : float
        子图网格线线宽。
    """
    area: AreaRange
    width: float = 0.1
    height: float = 0.14
    aspect: Optional[float] = None
    xlocator: list = field(default_factory=lambda: [110, 120])
    ylocator: list = field(default_factory=lambda: [10, 20])
    gridline_width: float = 0.2


class MapTemplate(XYTemplate):
    """
    地图模板基类，提供地图渲染的通用流程。

    通用流程::

        render_panel → load_map → render_chart → render_main_layer [-> render_sub_layer]

    子类通过覆盖参数和钩子方法来定制行为。

    Parameters
    ----------
    projection : ccrs.Projection
        数据投影，用于数据坐标转换。
    area : AreaRange or tuple
        地图区域范围。
    map_projection : ccrs.Projection or None
        地图投影，用于 GeoAxes 的显示投影。默认与 ``projection`` 相同。
    layout_config : LayoutConfig or None
        布局配置。默认为 ``LayoutConfig()``。

    Attributes
    ----------
    axes_component_painter : AxesComponentPainter or None
        坐标轴组件绑定器，用于绑定标题、色标、地图边框等。子类在 ``__init__`` 中初始化。
    main_map_painter : MapPainter or None
        主地图绑定器。子类在 ``load_map`` 中初始化。
    layout_config : LayoutConfig
        布局配置，包含 width、height、aspect、xticks_interval、yticks_interval。
    """

    def __init__(
            self,
            projection: ccrs.Projection,
            area: Union[AreaRange, Tuple[float, float, float, float]],
            map_projection: Optional[ccrs.Projection] = None,
            layout_config: Optional[LayoutConfig] = None,
    ):
        super().__init__()

        # 区域
        if isinstance(area, AreaRange):
            self._area = area
        elif isinstance(area, tuple):
            self._area = AreaRange.from_tuple(area)
        else:
            raise ValueError("area must be AreaRange or tuple")

        # 投影
        self._projection = projection
        if map_projection is None:
            self._map_projection = self._projection
        else:
            self._map_projection = map_projection

        # 布局配置
        if layout_config is None:
            self.layout_config = LayoutConfig()
        else:
            self.layout_config = layout_config

        # painter，子类初始化
        self.axes_component_painter: Optional["AxesComponentPainter"] = None
        self.main_map_painter: Optional["MapPainter"] = None
        self.map_loader_class = get_map_loader_class()

    # =====================
    # 布局属性（向后兼容代理）
    # =====================
    # 子类目前直接设置 self.width 等属性。
    # 这些 property 将读写代理到 self.layout_config，
    # 确保子类在 task 5.3 更新前仍能正常工作。

    @property
    def width(self) -> float:
        """float : 主图层宽度（相对于 figure）。"""
        return self.layout_config.width

    @width.setter
    def width(self, value: float):
        self.layout_config.width = value

    @property
    def height(self) -> float:
        """float : 主图层高度（相对于 figure）。"""
        return self.layout_config.height

    @height.setter
    def height(self, value: float):
        self.layout_config.height = value

    @property
    def main_aspect(self) -> Optional[float]:
        """float or None : 主图层长宽比。"""
        return self.layout_config.aspect

    @main_aspect.setter
    def main_aspect(self, value: Optional[float]):
        self.layout_config.aspect = value

    @property
    def main_xticks_interval(self) -> float:
        """float : 主图层经度刻度间隔。"""
        return self.layout_config.xticks_interval

    @main_xticks_interval.setter
    def main_xticks_interval(self, value: float):
        self.layout_config.xticks_interval = value

    @property
    def main_yticks_interval(self) -> float:
        """float : 主图层纬度刻度间隔。"""
        return self.layout_config.yticks_interval

    @main_yticks_interval.setter
    def main_yticks_interval(self, value: float):
        self.layout_config.yticks_interval = value

    # =====================
    # 属性
    # =====================

    @property
    def area(self) -> AreaRange:
        """AreaRange : 地图区域范围。"""
        return self._area

    @property
    def projection(self) -> ccrs.Projection:
        """ccrs.Projection : 数据投影。"""
        return self._projection

    @property
    def map_projection(self) -> ccrs.Projection:
        """ccrs.Projection : 地图显示投影。"""
        return self._map_projection


    # =========================================
    # 外部接口（供 Panel 和用户代码调用）
    # =========================================

    def total_area(self) -> AreaRange:
        """
        获取总区域范围（含子图），用于截取数据。

        子类可重写以合并主图和子图的区域。

        Returns
        -------
        AreaRange
            总区域范围。
        """
        return self._area

    def set_title(
            self,
            panel: "Panel",
            graph_name: str,
            system_name: str,
            start_time: pd.Timestamp,
            forecast_time: pd.Timedelta,
    ):
        """
        设置图表标题。

        子类可重写以定制标题格式。

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
        fill_graph_title(
            graph_title=graph_title,
            graph_name=graph_name,
            system_name=system_name,
            start_time=start_time,
            forecast_time=forecast_time,
        )
        self._add_title_to_panel(panel=panel, graph_title=graph_title)

    def add_colorbar(self, panel: "Panel", style: Union[ContourStyle, List[ContourStyle]]):
        """
        添加颜色条。

        子类可重写以定制颜色条布局。

        Parameters
        ----------
        panel : Panel
            面板对象。
        style : ContourStyle or list of ContourStyle
            等值线样式，用于确定色标的颜色和级别。

        Returns
        -------
        list
            颜色条对象列表。
        """
        color_bars = self.axes_component_painter.add_colorbar(
            layer=panel.charts[0].layers[0],
            style=style,
        )
        return color_bars

    # =========================================
    # 渲染底图（子类可重写以定制）
    # =========================================

    def render_panel(self, panel: "Panel"):
        """
        渲染入口，默认只包含一个子图 (Chart)。

        如果图中包含多个 chart，子类需要重写。

        流程：创建 Chart → 加载地图 → 渲染 Chart。

        Parameters
        ----------
        panel : Panel
            面板对象。
        """
        chart = panel.add_chart(domain=self)
        self.load_map()
        self.render_chart(chart=chart)

    def render_chart(self, chart: "Chart"):
        """
        渲染子图 (Chart)：渲染主图层 + 绘制地图边框。

        子类可通过 ``super().render_chart()`` 复用基类流程，再追加子图层等。

        Parameters
        ----------
        chart : Chart
            Chart 对象。
        """
        self.render_main_layer(chart=chart)
        if self.axes_component_painter is not None:
            self.axes_component_painter.draw_map_box(layer=chart.layers[0])

    def render_main_layer(self, chart: "Chart") -> "Layer":
        """
        渲染主图层。

        默认流程适用于 EastAsia 等 PlateCarree 投影模板::

            创建图层 → 设置区域 → 设置坐标轴 → 网格线 → 绘制地图

        使用非默认投影的子类（Global、EuropeAsia、NorthPolar）应重写此方法，
        利用 ``_create_main_layer`` / ``_apply_gridlines`` / ``_apply_map``
        等辅助方法组装自己的渲染顺序。

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
        layer.set_area(area=self.area, aspect=self.layout_config.aspect)
        self.setup_bindaxis(layer)
        self._apply_gridlines(layer)
        self._apply_map(layer)
        return layer

    def render_sub_layer(
            self,
            chart: "Chart",
            config: SubMapConfig,
            map_painter: "MapPainter",
    ) -> "Layer":
        """
        渲染子图层，一般用作南海子图。

        Parameters
        ----------
        chart : Chart
            Chart 对象。
        config : SubMapConfig
            子图配置。
        map_painter : MapPainter
            子图的地图绑定器。

        Returns
        -------
        Layer
            创建的子图层。
        """
        rect = self._create_rect(config.width, config.height)
        aspect = config.aspect
        if aspect is None:
            aspect = config.width / config.height

        layer = chart.create_layer(
            rect=rect,
            projection=self.projection,
        )
        layer.set_area(area=config.area, aspect=aspect)
        layer.gridlines(
            xlocator=config.xlocator,
            ylocator=config.ylocator,
            linewidth=config.gridline_width,
        )
        self._apply_map(layer=layer, map_painter=map_painter)
        return layer


    # =========================================
    # 钩子方法（子类按需重写）
    # =========================================

    def load_map(self):
        """
        加载地图资源，创建 MapPainter。

        子类必须重写此方法，在其中初始化 ``self.main_map_painter``。

        Raises
        ------
        NotImplementedError
            基类未实现。
        """
        raise NotImplementedError

    def setup_bindaxis(self, layer: "Layer"):
        """
        设置坐标轴。

        默认根据 ``area`` 和 ``layout_config.xticks_interval`` / ``layout_config.yticks_interval`` 生成。
        NorthPolar、Global 等需要特殊坐标轴的子类应重写。

        Parameters
        ----------
        layer : Layer
            图层对象。
        """
        area = self.area
        xticks = np.arange(
            area.start_longitude,
            area.end_longitude + self.layout_config.xticks_interval / 10,
            self.layout_config.xticks_interval,
        )
        yticks = np.arange(
            area.start_latitude,
            area.end_latitude + self.layout_config.yticks_interval / 10,
            self.layout_config.yticks_interval,
        )
        layer.set_axis(xticks=xticks, yticks=yticks)

    def setup_boundary(self, layer: "Layer"):
        """
        设置图形边界形状。默认不做任何事。

        NorthPolar（圆形边界）、EuropeAsia（矩形投影边界）等子类应重写。

        Parameters
        ----------
        layer : Layer
            图层对象。
        """
        pass

    def get_gridline_locators(self):
        """
        获取网格线位置。默认与坐标轴刻度一致。

        Returns
        -------
        tuple of ndarray
            ``(xlocator, ylocator)``，分别为经度和纬度网格线位置。
        """
        area = self.area
        xticks = np.arange(
            area.start_longitude,
            area.end_longitude + self.layout_config.xticks_interval / 10,
            self.layout_config.xticks_interval,
        )
        yticks = np.arange(
            area.start_latitude,
            area.end_latitude + self.layout_config.yticks_interval / 10,
            self.layout_config.yticks_interval,
        )
        return xticks, yticks

    def get_gridline_kwargs(self) -> dict:
        """
        获取网格线额外参数。默认返回空字典。

        子类可重写以添加 ``color`` 等参数。

        Returns
        -------
        dict
            传递给 ``layer.gridlines()`` 的额外关键字参数。
        """
        return {}

    # =========================================
    # 内部辅助方法（不应被子类重写）
    # =========================================

    def _add_title_to_panel(self, panel: "Panel", graph_title: GraphTitle):
        """
        将标题添加到面板的第一个 Chart 的第一个 Layer 上。

        Parameters
        ----------
        panel : Panel
            面板对象。
        graph_title : GraphTitle
            标题对象。
        """
        self.axes_component_painter.add_title(
            layer=panel.charts[0].layers[0],
            graph_title=graph_title,
        )

    def _create_main_layer(self, chart: "Chart") -> "Layer":
        """
        创建主图层。

        Parameters
        ----------
        chart : Chart
            Chart 对象。

        Returns
        -------
        Layer
            创建的图层。
        """
        rect = self._create_rect(self.layout_config.width, self.layout_config.height)
        return chart.create_layer(
            rect=rect,
            projection=self.projection,
            map_projection=self.map_projection,
        )

    def _create_rect(self, width: float, height: float) -> AxesRect:
        """
        计算图层的 AxesRect，以主图尺寸居中定位。

        Parameters
        ----------
        width : float
            图层宽度。
        height : float
            图层高度。

        Returns
        -------
        AxesRect
            图层的位置和尺寸。
        """
        return AxesRect(
            left=(1 - self.layout_config.width) / 2,
            bottom=(1 - self.layout_config.height) / 2,
            width=width,
            height=height,
        )

    def _apply_gridlines(self, layer: "Layer"):
        """
        应用网格线到图层。

        Parameters
        ----------
        layer : Layer
            图层对象。
        """
        xlocator, ylocator = self.get_gridline_locators()
        gridline_kwargs = self.get_gridline_kwargs()
        if xlocator is not None:
            layer.gridlines(
                xlocator=xlocator,
                ylocator=ylocator,
                **gridline_kwargs,
            )

    def _apply_map(self, layer: "Layer", map_painter: Optional["MapPainter"] = None):
        """
        渲染地图到图层，并绘制地图信息标注。

        Parameters
        ----------
        layer : Layer
            图层对象。
        map_painter : MapPainter or None
            地图绑定器。默认使用 ``self.main_map_painter``。
        """
        if map_painter is None:
            map_painter = self.main_map_painter
        if map_painter is not None:
            map_painter.add_map_info(layer=layer)
            map_painter.render_layer(layer=layer)
