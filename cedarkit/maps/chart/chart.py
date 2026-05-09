from typing import List, Optional, Any, TYPE_CHECKING
from cartopy import crs as ccrs

from cedarkit.maps.style import Style
from cedarkit.maps.types import AxesRect
from cedarkit.maps.template import XYTemplate

from .layer import Layer
from .renderer import get_renderer

if TYPE_CHECKING:
    from .panel import Panel


class Chart:
    """
    A sub graph in a Panel.
    A ``Chart`` may contain several ``Layer``s, such as a main layer for China and a sub layer for North China Sea.

    Attributes
    ----------
    panel : Panel
    domain : XYTemplate
    layers : List[Layer]
        layer list. Each layer has a map.
    """
    def __init__(self, panel: "Panel", domain: "XYTemplate"):
        self.panel = panel
        self.domain = domain

        self.layers: List["Layer"] = []

    @property
    def fig(self):
        return self.panel.fig

    def add_layer(self, layer: Layer) -> Layer:
        """
        add an existing layer to Chart. 
        
        Parameters
        ----------
        layer

        Returns
        -------
        Layer
        """
        self.layers.append(layer)
        return layer

    def create_layer(
            self,
            rect: AxesRect,
            projection: Optional[ccrs.Projection] = None,
            map_projection: Optional[ccrs.Projection] = None,
    ) -> Layer:
        """
        Create a GeoAxes layer and add it to chart.

        Parameters
        ----------
        rect
            layer axes rect, using in ``Figure.add_axes``.
        projection
            data projection, default is None.
        map_projection
            map projection, default is same as projection.

        Returns
        -------
        Layer
            a new created layer.
        """
        if map_projection is None:
            map_projection = projection
        fig = self.fig
        layout = (rect.left, rect.bottom, rect.width, rect.height)
        ax = fig.add_axes(
            layout,
            projection=map_projection,
        )
        layer = Layer(projection=projection, chart=self)
        layer.set_axes(ax)
        return layer

    def plot(self, data, style: "Style", layer: Optional[List[Any]] = None) -> List[Any]:
        """
        Plot data with style in layers.

        Parameters
        ----------
        data
            plot data. Different plot method may require different type of data.
            Such as contour needs one field, and barb needs a list with two fields.
        style
            plot style which is used to select plot method.
        layer
            which layer to be plotted on. If not set then all layers will be plotted on.

        Returns
        -------
        List[Any]
            plot results for each used layer.
        """
        results = []
        if layer is None:
            layers = self.layers
        else:
            layers = [self.layers[i] for i in layer]
        for layer in layers:
            renderer = get_renderer(style)
            result = renderer.render(layer, data, style)
            results.append(result)
        return results
