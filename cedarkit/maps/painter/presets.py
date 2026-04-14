"""
MapPainter 预设配置工厂函数。

提供常用的 MapPainter 配置，消除各模板中 load_map 的重复代码。
"""
from typing import Optional

from cedarkit.maps.map import get_map_loader_class, MapType, MapLoader
from cedarkit.maps.painter.map_painter import (
    MapPainter, MapFeatureConfig, MapInfo
)


def create_china_map_painter(
        map_loader_class=None,
        map_type: MapType = MapType.Portrait,
        map_info: Optional[MapInfo] = None,
        coastline_linewidth: float = 0.5,
        with_lakes: bool = True,
) -> MapPainter:
    """
    中国区域常用的 MapPainter 预设。

    包含海岸线、湖泊、中国海岸线、中国边界、省界、河流、九段线。

    Parameters
    ----------
    map_loader_class
        地图加载器类，默认使用全局配置
    map_type
        地图类型
    map_info
        地图信息标注（审图号等）
    coastline_linewidth
        海岸线线宽
    with_lakes
        是否渲染湖泊
    """
    if map_loader_class is None:
        map_loader_class = get_map_loader_class()
    loader = map_loader_class(map_type=map_type)

    return MapPainter(
        map_loader=loader,
        coastline_config=MapFeatureConfig(
            loader=dict(
                scale="50m",
                style=dict(linewidth=coastline_linewidth),
            ),
            render=True,
        ),
        lakes_config=MapFeatureConfig(
            loader=dict(
                scale="50m",
                style=dict(
                    linewidth=0.25,
                    facecolor="none",
                    edgecolor="black",
                    alpha=0.5,
                ),
            ),
            render=with_lakes,
        ),
        china_coastline_config=MapFeatureConfig(render=True),
        china_borders_config=MapFeatureConfig(render=True),
        china_provinces_config=MapFeatureConfig(render=True),
        china_rivers_config=MapFeatureConfig(render=True),
        china_nine_lines_config=MapFeatureConfig(render=True),
        map_info=map_info,
    )


def create_south_china_sea_painter(
        map_loader_class=None,
        map_info: Optional[MapInfo] = None,
        coastline_linewidth: float = 0.25,
) -> MapPainter:
    """
    南海子图常用的 MapPainter 预设。

    包含海岸线、中国海岸线、中国边界、省界、河流、九段线。

    Parameters
    ----------
    map_loader_class
        地图加载器类，默认使用全局配置
    map_info
        地图信息标注
    coastline_linewidth
        海岸线线宽
    """
    if map_loader_class is None:
        map_loader_class = get_map_loader_class()
    loader = map_loader_class(map_type=MapType.SouthChinaSea)

    return MapPainter(
        map_loader=loader,
        coastline_config=MapFeatureConfig(
            loader=dict(
                scale="50m",
                style=dict(linewidth=coastline_linewidth),
            ),
            render=True,
        ),
        china_coastline_config=MapFeatureConfig(render=True),
        china_borders_config=MapFeatureConfig(render=True),
        china_provinces_config=MapFeatureConfig(render=True),
        china_rivers_config=MapFeatureConfig(render=True),
        china_nine_lines_config=MapFeatureConfig(render=True),
        map_info=map_info,
    )


def create_global_map_painter(
        map_loader_class=None,
        map_type: MapType = MapType.Portrait,
        map_info: Optional[MapInfo] = None,
        coastline_linewidth: float = 0.5,
        with_land: bool = False,
        with_global_borders: bool = False,
) -> MapPainter:
    """
    全球地图常用的 MapPainter 预设。

    Parameters
    ----------
    map_loader_class
        地图加载器类，默认使用全局配置
    map_type
        地图类型
    map_info
        地图信息标注
    coastline_linewidth
        海岸线线宽
    with_land
        是否渲染陆地
    with_global_borders
        是否渲染全球国界
    """
    if map_loader_class is None:
        map_loader_class = get_map_loader_class()
    loader = map_loader_class(map_type=map_type)

    return MapPainter(
        map_loader=loader,
        coastline_config=MapFeatureConfig(
            loader=dict(
                scale="50m",
                style=dict(linewidth=coastline_linewidth),
            ),
            render=True,
        ),
        land_config=MapFeatureConfig(
            loader=dict(
                scale="50m",
                style=dict(zorder=-1),
            ),
            render=with_land,
        ),
        global_borders_config=MapFeatureConfig(
            render=with_global_borders,
        ),
        map_info=map_info,
    )
