from typing import List, Optional, Tuple
from dataclasses import dataclass

import matplotlib.colors as mcolors


@dataclass
class AxesRect:
    left: float
    bottom: float
    width: float
    height: float


@dataclass
class AreaRange:
    start_longitude: float
    end_longitude: float
    start_latitude: float
    end_latitude: float

    def to_tuple(self) -> Tuple[float, float, float, float]:
        return self.start_longitude, self.end_longitude, self.start_latitude, self.end_latitude

    @classmethod
    def from_tuple(cls, area: Tuple[float, float, float, float]) -> 'AreaRange':
        return cls(area[0], area[1], area[2], area[3])


@dataclass
class GraphTitle:
    """
    Graph title in four corners of box.

                         main_label
    top_left_label                           top_right_label
    ————————————————————————————————————————————————————————
    |                                                      |
    |                                                      |
    |                     Axes box                         |
    |                                                      |
    |                                                      |
    ————————————————————————————————————————————————————————
    bottom_left_label                     bottom_right_label
    """
    top_left_label: Optional[str] = None
    top_right_label: Optional[str] = None
    bottom_left_label: Optional[str] = None
    bottom_right_label: Optional[str] = None
    main_title_label: Optional[str] = None

    left: Optional[float] = None
    bottom: Optional[float] = None
    top: Optional[float] = None
    right: Optional[float] = None
    main_pos: Optional[Tuple[float, float]] = None


@dataclass
class GraphColorbar:
    colormap: Optional[mcolors.ListedColormap] = None
    levels: Optional[List] = None
    box: Optional[List] = None
    label: Optional[str] = None
    label_loc: Optional[str] = None
    label_levels: Optional[List] = None
    orientation: str = "vertical"
