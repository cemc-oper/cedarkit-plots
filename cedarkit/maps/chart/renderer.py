from abc import ABC, abstractmethod
from typing import Any, Dict, Type, TYPE_CHECKING

from cedarkit.maps.style import Style, ContourStyle, BarbStyle

if TYPE_CHECKING:
    from .layer import Layer


class PlotRenderer(ABC):
    """绘图渲染器接口。"""

    @abstractmethod
    def render(self, layer: "Layer", data: Any, style: "Style", **kwargs) -> Any:
        ...


class ContourRenderer(PlotRenderer):
    """等值线渲染器，根据 style.fill 决定使用 contourf 或 contour。"""

    def render(self, layer: "Layer", data: Any, style: "ContourStyle", **kwargs) -> Any:
        if style.fill:
            return layer.contourf(data=data, style=style, **kwargs)
        else:
            return layer.contour(data=data, style=style, **kwargs)


class BarbRenderer(PlotRenderer):
    """风羽渲染器，使用 data[0] 和 data[1] 作为 x 和 y 分量。"""

    def render(self, layer: "Layer", data: Any, style: "BarbStyle", **kwargs) -> Any:
        return layer.barb(x=data[0], y=data[1], style=style, **kwargs)


# 全局注册表
_renderer_registry: Dict[Type[Style], PlotRenderer] = {}


def register_renderer(style_type: Type[Style], renderer: PlotRenderer) -> None:
    """注册 Style 类型对应的 PlotRenderer。"""
    _renderer_registry[style_type] = renderer


def get_renderer(style: Style) -> PlotRenderer:
    """根据 Style 实例获取对应的 PlotRenderer。"""
    renderer = _renderer_registry.get(type(style))
    if renderer is None:
        raise NotImplementedError(
            f"No PlotRenderer registered for style type: {type(style).__name__}. "
            f"Use register_renderer() to register a renderer."
        )
    return renderer


# 默认注册
register_renderer(ContourStyle, ContourRenderer())
register_renderer(BarbStyle, BarbRenderer())
