from typing import Optional, TYPE_CHECKING

import numpy as np
from cartopy import crs as ccrs
import matplotlib.path as mpath

from cedarkit.maps.chart import Layer
from cedarkit.maps.util import AreaRange
from cedarkit.maps.painter.map_painter import MapInfo
from cedarkit.maps.painter.axes_component_painter import (
    AxesComponentPainter, MapBoxOption, ColorBarOption,
)
from cedarkit.maps.painter.presets import (
    create_china_map_painter,
    create_south_china_sea_painter,
)

from .east_asia import SOUTH_CHINA_SEA_AREA
from .map_template import MapTemplate, SubMapConfig

if TYPE_CHECKING:
    from cedarkit.maps.chart import Chart, Panel


#: 欧亚默认区域（20°E–170°E, 0°–70°N）
EUROPE_ASIA_AREA = AreaRange(
    start_longitude=20,
    end_longitude=170,
    start_latitude=0,
    end_latitude=70,
)


class EuropeAsiaMapTemplate(MapTemplate):
    """
    欧亚底图布局，Lambert 投影，可选南海子图。

    使用 LambertConformal 投影 (中心经度 95°E，标准纬线 30°N/60°N)，
    默认区域为 20°E–170°E, 0°–70°N，带矩形投影边界裁剪。

    Parameters
    ----------
    area : AreaRange or None
        主图区域范围。默认为欧亚区域 (20–170°E, 0–70°N)。
    with_sub_area : bool
        是否显示南海子图，默认为 False。
    """
    def __init__(
            self,
            area: Optional[AreaRange] = None,
            with_sub_area: bool = False,
    ):
        self.central_longitude = 95
        self.standard_parallels = (30, 60)

        if area is None:
            area = EUROPE_ASIA_AREA

        projection = ccrs.PlateCarree()
        map_projection = ccrs.LambertConformal(
            central_longitude=self.central_longitude,
            standard_parallels=self.standard_parallels,
        )
        super().__init__(
            area=area,
            projection=projection,
            map_projection=map_projection,
        )

        self.with_sub_area = with_sub_area

        # 布局参数
        self.width = 0.75
        self.height = 0.6
        self.main_xticks_interval = 10
        self.main_yticks_interval = 5

        # 南海子图配置
        self.sub_map_config = SubMapConfig(
            area=SOUTH_CHINA_SEA_AREA,
            width=0.1,
            height=0.14,
        )
        self.sub_map_painter = None

        # 坐标轴组件
        self.axes_component_painter = AxesComponentPainter(
            map_box_option=MapBoxOption(
                bottom_left_point=(-0.04, -0.04),
                top_right_point=(1.04, 1.04),
            ),
            color_bar_option=ColorBarOption(
                orientation="vertical",
                bottom_left_point=(1.07, -0.02),
                top_right_point=(1.09, 1.02),
            ),
        )

    def load_map(self):
        """
        创建主图和南海子图的 MapPainter。

        主图使用中国区域预设（含海岸线、湖泊、省界等），
        南海子图使用南海预设（含海岸线、省界等，无湖泊）。
        """
        self.main_map_painter = create_china_map_painter(
            map_info=MapInfo(
                x=1.035,
                y=-0.035,
                text="Scale 1:20000000 No:GS (2019) 1786",
            ),
        )
        self.sub_map_painter = create_south_china_sea_painter(
            map_info=MapInfo(
                x=0.99,
                y=0.01,
                text="Scale 1:40000000",
            ),
        )

    def render_chart(self, chart: "Chart"):
        """
        渲染主图层和南海子图层。

        先调用基类渲染主图层和地图边框，再根据 ``with_sub_area`` 追加南海子图。

        Parameters
        ----------
        chart : Chart
            Chart 对象。
        """
        super().render_chart(chart=chart)
        if self.with_sub_area:
            self.render_sub_layer(
                chart=chart,
                config=self.sub_map_config,
                map_painter=self.sub_map_painter,
            )

    def setup_bindaxis(self, layer: Layer):
        """
        设置坐标轴。

        Lambert 投影不使用常规的经纬度坐标轴，此方法为空实现。

        Parameters
        ----------
        layer : Layer
            图层对象。
        """
        pass

    def get_gridline_locators(self):
        """
        获取网格线位置。

        基于区域范围和刻度间隔生成，不包含边界值。

        Returns
        -------
        tuple of ndarray
            ``(xlocator, ylocator)``。
        """
        area = self.area
        xlocator = np.arange(
            area.start_longitude,
            area.end_longitude,
            self.main_xticks_interval,
        )
        ylocator = np.arange(
            area.start_latitude,
            area.end_latitude,
            self.main_yticks_interval,
        )
        return xlocator, ylocator

    def setup_boundary(self, layer: Layer):
        """
        设置 Lambert 投影的矩形边界裁剪。

        沿区域范围的四条边生成顶点路径，将其从 PlateCarree 坐标系
        转换到 axes 坐标系后设置为地图边界。

        Parameters
        ----------
        layer : Layer
            图层对象。
        """
        ax = layer.ax
        area = self.area
        lon_range = (area.start_longitude, area.end_longitude)
        lat_range = (area.start_latitude, area.end_latitude)

        res = 1
        vertices = [
            (lon, lat_range[0]) for lon in np.arange(lon_range[0], lon_range[1] + 1, res)
        ] + [
            (lon_range[1], lat) for lat in np.arange(lat_range[0], lat_range[1] + 1, res)
        ] + [
            (lon, lat_range[1]) for lon in np.arange(lon_range[1], lon_range[0] - 1, -res)
        ] + [
            (lon_range[0], lat) for lat in np.arange(lat_range[1], lat_range[0] - 1, -res)
        ]

        path = mpath.Path(vertices)
        proj_to_data = ccrs.PlateCarree()._as_mpl_transform(ax) - ax.transData
        ax.set_boundary(proj_to_data.transform_path(path))

    def render_main_layer(self, chart: "Chart") -> Layer:
        """
        渲染 Lambert 投影主图层。

        渲染顺序与基类不同::

            创建图层 → 网格线 → 设置区域 → 矩形边界裁剪 → 绘制地图

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
        self._apply_gridlines(layer)
        layer.set_area(area=self.area)
        self.setup_boundary(layer)
        self._apply_map(layer)
        return layer
