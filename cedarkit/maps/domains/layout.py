from dataclasses import dataclass
from typing import Optional


@dataclass
class LayoutConfig:
    """地图模板布局配置。

    将 MapTemplate 中散落的布局属性（width、height、aspect、
    xticks_interval、yticks_interval）集中为独立的数据类，
    通过组合方式注入模板，支持灵活定制。

    Parameters
    ----------
    width : float
        主图层宽度（相对于 figure），默认 0.75。
    height : float
        主图层高度（相对于 figure），默认 0.6。
    aspect : float or None
        主图层长宽比，默认 None。
    xticks_interval : float
        经度刻度间隔，默认 10。
    yticks_interval : float
        纬度刻度间隔，默认 5。
    """
    width: float = 0.75
    height: float = 0.6
    aspect: Optional[float] = None
    xticks_interval: float = 10
    yticks_interval: float = 5

    @classmethod
    def east_asia(cls) -> "LayoutConfig":
        """东亚/中国底图默认布局。"""
        return cls(width=0.75, height=0.6, aspect=1.25, xticks_interval=10, yticks_interval=5)

    @classmethod
    def cn_area(cls) -> "LayoutConfig":
        """中国区域底图默认布局。"""
        return cls(width=0.8, height=0.6, aspect=1.25, xticks_interval=4, yticks_interval=2)

    @classmethod
    def europe_asia(cls) -> "LayoutConfig":
        """欧亚底图默认布局。"""
        return cls(width=0.75, height=0.6, xticks_interval=10, yticks_interval=5)

    @classmethod
    def north_polar(cls) -> "LayoutConfig":
        """北极投影底图默认布局。"""
        return cls(width=0.75, height=0.8)

    @classmethod
    def global_default(cls) -> "LayoutConfig":
        """全球底图默认布局。"""
        return cls(width=0.8, height=0.6, xticks_interval=30, yticks_interval=30)

    @classmethod
    def global_area(cls) -> "LayoutConfig":
        """全球区域底图默认布局。"""
        return cls(width=0.8, height=0.6, xticks_interval=10, yticks_interval=10)
