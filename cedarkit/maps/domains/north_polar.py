from typing import Optional, TYPE_CHECKING

import numpy as np
from cartopy import crs as ccrs
import matplotlib.path as mpath

from cedarkit.maps.chart import Layer
from cedarkit.maps.types import AreaRange
from cedarkit.maps.painter.map_painter import MapPainter, MapInfo
from cedarkit.maps.painter.axes_component_painter import (
    AxesComponentPainter, MapBoxOption, ColorBarOption,
)
from cedarkit.maps.painter.presets import create_china_map_painter

from .layout import LayoutConfig
from .map_template import MapTemplate

if TYPE_CHECKING:
    from cedarkit.maps.chart import Chart, Panel


#: 北极投影默认区域（全球北半球）
NORTH_POLAR_AREA = AreaRange(
    start_longitude=-180,
    end_longitude=180,
    start_latitude=0,
    end_latitude=90,
)


class NorthPolarMapTemplate(MapTemplate):
    """
    北极投影底图布局。

    使用 NorthPolarStereo 投影，中心经度 110°E，默认区域为全球北半球，带圆形边界裁剪。

    Parameters
    ----------
    area : AreaRange or None
        地图区域范围。默认为北半球全域 (-180°–180°E, 0°–90°N)。
    layout_config : LayoutConfig or None
        布局配置。默认为 ``LayoutConfig.north_polar()``。
    axes_component_painter : AxesComponentPainter or None
        坐标轴组件配置。默认为北极投影标准布局。
    main_map_painter : MapPainter or None
        主图地图绑定器。默认在 ``load_map()`` 中使用中国区域预设创建。
    """
    def __init__(
            self,
            area: Optional[AreaRange] = None,
            layout_config: Optional[LayoutConfig] = None,
            axes_component_painter: Optional[AxesComponentPainter] = None,
            main_map_painter: Optional[MapPainter] = None,
    ):
        self.central_longitude = 110

        if area is None:
            area = NORTH_POLAR_AREA

        if layout_config is None:
            layout_config = LayoutConfig.north_polar()

        projection = ccrs.PlateCarree()
        map_projection = ccrs.NorthPolarStereo(
            central_longitude=self.central_longitude,
        )
        super().__init__(
            area=area,
            projection=projection,
            map_projection=map_projection,
            layout_config=layout_config,
        )

        # 坐标轴组件
        if axes_component_painter is not None:
            self.axes_component_painter = axes_component_painter
        else:
            self.axes_component_painter = AxesComponentPainter(
                map_box_option=MapBoxOption(
                    bottom_left_point=(-0.05, -0.05),
                    top_right_point=(1.07, 1.03),
                ),
                color_bar_option=ColorBarOption(
                    orientation="vertical",
                    bottom_left_point=(1.09, -0.02),
                    top_right_point=(1.11, 1.02),
                ),
            )

        # 注入的 MapPainter（如果提供）
        if main_map_painter is not None:
            self.main_map_painter = main_map_painter

    def load_map(self):
        """
        创建主图的 MapPainter。

        如果构造函数中已注入了 painter，则跳过创建。
        使用中国区域预设（含海岸线、湖泊、省界等）。
        """
        if self.main_map_painter is None:
            self.main_map_painter = create_china_map_painter(
                map_info=MapInfo(
                    x=1.065,
                    y=-0.045,
                    text="Scale 1:20000000 No:GS (2019) 1786",
                ),
            )

    def setup_bindaxis(self, layer: Layer):
        """
        设置北极投影的坐标轴标签。

        北极投影无法使用常规的 ``set_xticks``/``set_yticks``，改为在赤道附近手动放置经度文本标签。

        Parameters
        ----------
        layer : Layer
            图层对象。
        """
        ax = layer.ax
        ticks = np.arange(0, 180 + 30, 30)
        etick = ['0'] + [
            r'%dE' % tick for tick in ticks if (tick != 0) & (tick != 180)
        ] + ['180']
        wtick = [r'%dW' % tick for tick in ticks if (tick != 0) & (tick != 180)]
        labels = etick + wtick[::-1]
        xticks = np.arange(0, 360, 30)
        yticks = np.full_like(xticks, -4)
        for xtick, ytick, label in zip(xticks, yticks, labels):
            if label == "60W":
                ax.text(
                    xtick, -0.5, label,
                    fontsize=8,
                    horizontalalignment='center',
                    verticalalignment='bottom',
                    transform=ccrs.Geodetic(),
                )
            else:
                ax.text(
                    xtick, ytick, label,
                    fontsize=8,
                    horizontalalignment='center',
                    verticalalignment='center',
                    transform=ccrs.Geodetic(),
                )

    def setup_boundary(self, layer: Layer):
        """
        设置圆形边界裁剪。

        在 axes 坐标系中绘制圆形路径，将地图裁剪为圆形显示。

        Parameters
        ----------
        layer : Layer
            图层对象。
        """
        ax = layer.ax
        theta = np.linspace(0, 2 * np.pi, 100)
        center, radius = [0.5, 0.5], 0.5
        verts = np.vstack([np.sin(theta), np.cos(theta)]).T
        circle = mpath.Path(verts * radius + center)
        ax.set_boundary(circle, transform=ax.transAxes)

    def get_gridline_locators(self):
        """
        获取北极投影的网格线位置。

        经度每 30° 一条，纬度每 15° 一条。

        Returns
        -------
        tuple of ndarray
            ``(xlocator, ylocator)``。
        """
        xlocator = np.arange(-180, 180, 30)
        ylocator = np.arange(0, 90, 15)
        return xlocator, ylocator

    def get_gridline_kwargs(self) -> dict:
        """
        获取网格线额外参数。

        Returns
        -------
        dict
            北极投影使用黑色网格线。
        """
        return dict(color="k")

    def render_main_layer(self, chart: "Chart") -> "Layer":
        """
        渲染北极投影主图层。

        渲染顺序与基类不同::

            创建图层 → 坐标轴标签 → 圆形边界 → 网格线 → 设置区域 → 绘制地图

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
        self.setup_bindaxis(layer)
        self.setup_boundary(layer)
        self._apply_gridlines(layer)
        layer.set_area(area=self.area)
        self._apply_map(layer)
        return layer
