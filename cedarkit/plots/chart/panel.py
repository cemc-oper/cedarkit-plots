from dataclasses import dataclass
from typing import Optional, Tuple, Union, List, Any, Iterable, TYPE_CHECKING

import matplotlib.pyplot as plt
import xarray as xr

from cedarkit.plots.style import Style
from cedarkit.plots.template import XYTemplate

from .chart import Chart


@dataclass
class Schema:
    figsize: Tuple[float, float] = (8, 8)
    dpi: float = 400


class Panel:
    """
    A plot ``Panel`` which contains several ``Chart``s.

    Attributes
    ----------
    domain : XYTemplate
        A ``XYDomain`` instance which is used to draw map and other items within a plot.
    schema : Schema
        panel settings, used to create ``matplotlib.pyplot.Figure``
    charts : List[Chart]
        chart list. each chart is a map box.
    """
    def __init__(
            self,
            domain: "XYTemplate",
            schema: Optional[Schema] = None,
    ):
        if schema is None:
            self.schema = Schema()
        else:
            self.schema = schema

        self._fig: Optional[plt.figure] = None

        self.charts = []

        # self.domain = parse_domain(domain)
        self.domain = domain
        self.domain.render_panel(self)

    @property
    def fig(self) -> plt.Figure:
        if self._fig is None:
            self._fig = plt.figure(
                figsize=self.schema.figsize,
                frameon=False,
                dpi=self.schema.dpi,
            )
        return self._fig

    def show(self):
        plt.show()

    def save(self, *args, bbox_inches="tight", **kwargs):
        return self.fig.savefig(*args, bbox_inches=bbox_inches, **kwargs)

    def add_chart(self, domain: XYTemplate) -> Chart:
        """
        Add a ``Chart`` to the panel

        Parameters
        ----------
        domain
            ``XYDomain``, different chart may use different domains.
        Returns
        -------
        Chart
        """
        chart = Chart(self, domain=domain)
        self.charts.append(chart)
        return chart

    def plot(
            self,
            data: Union[xr.DataArray, Iterable],
            style: Union[Style, str, None] = None,
            layer: Optional[List[Any]] = None,
    ) -> List[Any]:
        """
        Plot data in charts.

        Parameters
        ----------
        data
            iterable data, each ``Chart`` use one data to plot.
        style
            plot style: a ``Style`` object, or a style spec string resolved
            through the style registry — ``"auto"`` (or ``None``) matches the
            data metadata and builds the optimal variant, ``"id"`` /
            ``"id:variant"`` selects a style from the library explicitly.
            ``Layer`` use style to determine which plot method to use.
        layer
            layer index list, data will only be plotted in selected layers, default is all layers in chart.
        Returns
        -------
        List
            graphs list for each chart.
        """
        from cedarkit.plots.style import resolve_style

        graphs = []

        if isinstance(data, xr.DataArray):
            data = [data]

        style = resolve_style(style, data)

        for i, d in enumerate(data):
            graph = self.charts[i].plot(data=d, style=style, layer=layer)
            graphs.append(graph)

        return graphs

    def set_title(self, *args, **kwargs):
        return self.domain.set_title(panel=self, *args, **kwargs)

    def add_colorbar(self, *args, **kwargs):
        return self.domain.add_colorbar(panel=self, *args, **kwargs)
