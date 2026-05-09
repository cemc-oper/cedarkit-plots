from dataclasses import dataclass
from typing import Optional, Tuple, Union, List, Literal

from cedarkit.maps.chart import Layer
from cedarkit.maps.types import GraphTitle, GraphColorbar
from cedarkit.maps.bindutils import draw_map_box
from cedarkit.maps.painter.component_bindutils import (
    set_map_box_title,
    add_map_box_colorbar,
)
from cedarkit.maps.style import ContourStyle


@dataclass
class TitleOption:
    """标题样式配置。"""
    fontsize: float = 7
    main_pos: Tuple[float, float] = (0.5, 1.05)
    main_fontsize: float = 10


@dataclass
class MapBoxOption:
    bottom_left_point: Tuple[float, float]
    top_right_point: Tuple[float, float]
    linewidth: float = 1.3
    edgecolor: str = "black"


@dataclass
class ColorBarOption:
    orientation: Literal["vertical", "horizontal"]
    bottom_left_point: Tuple[float, float]
    top_right_point: Tuple[float, float]
    tick_fontsize: float = 7
    tick_pad: float = 7


@dataclass
class AxesComponentPainter:
    map_box_option: MapBoxOption
    color_bar_option: ColorBarOption
    title_option: Optional[TitleOption] = None

    def __post_init__(self):
        if self.title_option is None:
            self.title_option = TitleOption()

    def draw_map_box(self, layer: Layer):
        ax = layer.ax
        draw_map_box(
            ax,
            bottom_left_point=self.map_box_option.bottom_left_point,
            top_right_point=self.map_box_option.top_right_point,
            linewidth=self.map_box_option.linewidth,
            edgecolor=self.map_box_option.edgecolor,
        )

    def add_title(self, layer: Layer, graph_title: GraphTitle):
        graph_title.left = self.map_box_option.bottom_left_point[0]
        graph_title.bottom = self.map_box_option.bottom_left_point[1] - 0.005
        graph_title.top = self.map_box_option.top_right_point[1]
        graph_title.right = self.map_box_option.top_right_point[0]
        graph_title.main_pos = self.title_option.main_pos

        ax = layer.ax
        set_map_box_title(
            ax,
            graph_title=graph_title,
            fontsize=self.title_option.fontsize,
            main_fontsize=self.title_option.main_fontsize,
        )

    def add_colorbar(self, layer: Layer, style: Union[ContourStyle, List[ContourStyle]]):
        color_bar_option = self.color_bar_option
        if color_bar_option.orientation == "vertical":
            self.add_colorbar_vertical(layer=layer, style=style)
        elif color_bar_option.orientation == "horizontal":
            self.add_colorbar_horizontal(layer=layer, style=style)
        else:
            raise NotImplemented("horizontal is not supported")

    def add_colorbar_vertical(self, layer: Layer, style: Union[ContourStyle, List[ContourStyle]]):
        """
                                 |  | left_padding_to_map_box_right_bound
                                    ---
        --------------------------  | |
        |                        |  | |
        |                        |  | |
        |                        |  | |
        |                        |  | |   colorbar
        |                        |  | |
        |                        |  | |
        |                        |  | |
        --------------------------  | |  --
               map box              ---  -- bottom_padding_to_map_box_bottom_bound


        """
        ax = layer.ax
        color_bar_option = self.color_bar_option

        if isinstance(style, ContourStyle):
            style = [style]
        count = len(style)

        total_height = color_bar_option.top_right_point[1] - color_bar_option.bottom_left_point[1]
        width = color_bar_option.top_right_point[0] - color_bar_option.bottom_left_point[0]

        if count > 0:
            height_padding = 0.02
        else:
            height_padding = 0

        height = total_height / count

        color_bars = []

        for index, current_style in enumerate(style):
            colorbar_box = [
                color_bar_option.bottom_left_point[0],
                color_bar_option.bottom_left_point[1] + index * height,
                width, height - height_padding
            ]

            graph_colorbar = GraphColorbar(
                colormap=current_style.colors,
                levels=current_style.levels,
                box=colorbar_box,
            )

            colorbar_style = current_style.colorbar_style
            if colorbar_style is not None:
                if colorbar_style.label is not None:
                    graph_colorbar.label = colorbar_style.label
                if colorbar_style.loc is not None:
                    graph_colorbar.label_loc = colorbar_style.loc
                if colorbar_style.label_levels is not None:
                    graph_colorbar.label_levels = colorbar_style.label_levels

            color_bar = add_map_box_colorbar(
                graph_colorbar=graph_colorbar,
                ax=ax,
                tick_fontsize=self.color_bar_option.tick_fontsize,
                tick_pad=self.color_bar_option.tick_pad,
            )

            color_bars.append(color_bar)
        return color_bars

    def add_colorbar_horizontal(self, layer: Layer, style: Union[ContourStyle, List[ContourStyle]]):
        """
                                 |  | left_padding_to_map_box_right_bound

        --------------------------
        |                        |
        |                        |
        |                        |
        |                        |  map box
        |                        |
        |                        |
        |                        |
        --------------------------  -- top_padding_to_map_box_bottom_bound
           ---------------------    --
           |                   |
           ---------------------
        | | left_padding_to_map_box_left_bound


        """
        ax = layer.ax
        color_bar_option = self.color_bar_option

        if isinstance(style, ContourStyle):
            style = [style]
        count = len(style)

        height = color_bar_option.top_right_point[1] - color_bar_option.bottom_left_point[1]
        total_width = color_bar_option.top_right_point[0] - color_bar_option.bottom_left_point[0]

        if count > 0:
            width_padding = 0.02
        else:
            width_padding = 0

        width = total_width / count

        color_bars = []

        for index, current_style in enumerate(style):
            colorbar_box = [
                color_bar_option.bottom_left_point[0] + index * width,
                color_bar_option.bottom_left_point[1],
                width - width_padding, height
            ]

            graph_colorbar = GraphColorbar(
                colormap=current_style.colors,
                levels=current_style.levels,
                box=colorbar_box,
                orientation="horizontal",
            )

            colorbar_style = current_style.colorbar_style
            if colorbar_style is not None:
                if colorbar_style.label is not None:
                    graph_colorbar.label = colorbar_style.label
                if colorbar_style.loc is not None:
                    graph_colorbar.label_loc = colorbar_style.loc
                if colorbar_style.label_levels is not None:
                    graph_colorbar.label_levels = colorbar_style.label_levels

            color_bar = add_map_box_colorbar(
                graph_colorbar=graph_colorbar,
                ax=ax,
                tick_fontsize=self.color_bar_option.tick_fontsize,
                tick_pad=self.color_bar_option.tick_pad,
            )

            color_bars.append(color_bar)

        return color_bars
