from typing import Optional, TYPE_CHECKING

from cartopy import crs as ccrs

from cedarkit.maps.types import AreaRange
from cedarkit.maps.painter.map_painter import MapPainter, MapInfo
from cedarkit.maps.painter.axes_component_painter import (
    AxesComponentPainter, MapBoxOption, ColorBarOption,
)
from cedarkit.maps.painter.presets import (
    create_china_map_painter,
    create_south_china_sea_painter,
)

from .layout import LayoutConfig
from .map_template import MapTemplate, SubMapConfig

if TYPE_CHECKING:
    from cedarkit.maps.chart import Chart, Panel


#: 东亚默认区域（70°E–140°E, 15°N–55°N）
EAST_ASIA_AREA = AreaRange(
    start_longitude=70,
    end_longitude=140,
    start_latitude=15,
    end_latitude=55,
)

#: 南海子图区域（105°E–123°E, 2°N–23°N）
SOUTH_CHINA_SEA_AREA = AreaRange(
    start_longitude=105,
    end_longitude=123,
    start_latitude=2,
    end_latitude=23,
)


class EastAsiaMapTemplate(MapTemplate):
    """
    东亚/中国底图布局，带南海子图。

    使用 PlateCarree 投影，默认区域为 70°E–140°E, 15°N–55°N，
    可选在左下角叠加南海子图（105°E–123°E, 2°N–23°N）。

    Parameters
    ----------
    area : AreaRange or None
        主图区域范围。默认为东亚区域（70–140°E, 15–55°N）。
    with_sub_area : bool
        是否显示南海子图，默认为 True。
    layout_config : LayoutConfig or None
        布局配置。默认为 ``LayoutConfig.east_asia()``。
    axes_component_painter : AxesComponentPainter or None
        坐标轴组件配置。默认为东亚区域标准布局。
    main_map_painter : MapPainter or None
        主图地图绑定器。默认在 ``load_map()`` 中使用中国区域预设创建。
    sub_map_painter : MapPainter or None
        南海子图地图绑定器。默认在 ``load_map()`` 中使用南海预设创建。
    """
    def __init__(
            self,
            area: Optional[AreaRange] = None,
            with_sub_area: bool = True,
            layout_config: Optional[LayoutConfig] = None,
            axes_component_painter: Optional[AxesComponentPainter] = None,
            main_map_painter: Optional[MapPainter] = None,
            sub_map_painter: Optional[MapPainter] = None,
    ):
        if area is None:
            area = EAST_ASIA_AREA

        if layout_config is None:
            layout_config = LayoutConfig.east_asia()

        super().__init__(
            projection=ccrs.PlateCarree(),
            area=area,
            layout_config=layout_config,
        )

        self.with_sub_area = with_sub_area

        # 南海子图层配置
        self.sub_map_config = SubMapConfig(
            area=SOUTH_CHINA_SEA_AREA,
            width=0.1,
            height=0.14,
        )

        # 注入的 MapPainter（如果提供）
        if main_map_painter is not None:
            self.main_map_painter = main_map_painter
        if sub_map_painter is not None:
            self.sub_map_painter = sub_map_painter
        else:
            self.sub_map_painter = None

        # 坐标轴组件
        if axes_component_painter is not None:
            self.axes_component_painter = axes_component_painter
        else:
            self.axes_component_painter = AxesComponentPainter(
                map_box_option=MapBoxOption(
                    bottom_left_point=(-0.06, -0.05),
                    top_right_point=(1.03, 1.03),
                ),
                color_bar_option=ColorBarOption(
                    orientation="vertical",
                    bottom_left_point=(1.05, -0.02),
                    top_right_point=(1.07, 1.02),
                ),
            )

    def total_area(self) -> AreaRange:
        """
        获取总区域范围，包含主图和南海子图的合并区域。

        Returns
        -------
        AreaRange
            如果不包含南海子图，返回主图区域；
            否则返回主图与南海子图的最小外接矩形区域。
        """
        main_area = self.area
        if not self.with_sub_area:
            return main_area

        sub_area = self.sub_map_config.area
        return AreaRange(
            start_longitude=min(main_area.start_longitude, sub_area.start_longitude),
            end_longitude=max(main_area.end_longitude, sub_area.end_longitude),
            start_latitude=min(main_area.start_latitude, sub_area.start_latitude),
            end_latitude=max(main_area.end_latitude, sub_area.end_latitude),
        )

    def load_map(self):
        """
        创建主图和南海子图的 MapPainter。

        如果构造函数中已注入了 painter，则跳过对应的创建。
        主图使用中国区域预设（含海岸线、湖泊、省界等），
        南海子图使用南海预设（含海岸线、省界等，无湖泊）。
        """
        if self.main_map_painter is None:
            self.main_map_painter = create_china_map_painter(
                map_info=MapInfo(
                    x=0.998,
                    y=0.0022,
                    text="Scale 1:20000000 No:GS (2019) 1786",
                ),
            )
        if self.sub_map_painter is None:
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


class CnAreaMapTemplate(EastAsiaMapTemplate):
    """
    中国区域底图布局，例如华北、华中、华南等。

    继承自 ``EastAsiaMapTemplate``，使用更密的刻度间隔和更宽的主图。
    默认不显示南海子图。

    Parameters
    ----------
    area : AreaRange or None
        区域范围。默认继承 ``EastAsiaMapTemplate`` 的东亚区域。
    with_sub_area : bool
        是否显示南海子图，默认为 False。
    layout_config : LayoutConfig or None
        布局配置。默认为 ``LayoutConfig.cn_area()``。
    axes_component_painter : AxesComponentPainter or None
        坐标轴组件配置。默认继承 ``EastAsiaMapTemplate`` 的配置。
    main_map_painter : MapPainter or None
        主图地图绑定器。默认继承 ``EastAsiaMapTemplate`` 的预设。
    sub_map_painter : MapPainter or None
        南海子图地图绑定器。默认继承 ``EastAsiaMapTemplate`` 的预设。
    """
    def __init__(
            self,
            area: Optional[AreaRange] = None,
            with_sub_area: bool = False,
            layout_config: Optional[LayoutConfig] = None,
            axes_component_painter: Optional[AxesComponentPainter] = None,
            main_map_painter: Optional[MapPainter] = None,
            sub_map_painter: Optional[MapPainter] = None,
    ):
        if layout_config is None:
            layout_config = LayoutConfig.cn_area()

        super().__init__(
            area=area,
            with_sub_area=with_sub_area,
            layout_config=layout_config,
            axes_component_painter=axes_component_painter,
            main_map_painter=main_map_painter,
            sub_map_painter=sub_map_painter,
        )
