from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("cedarkit.plots")
except PackageNotFoundError:
    # package is not installed
    pass

from .chart import Chart, LayerResult, MapSubplot, Panel, PlotLayer, Subplot

__all__ = [
    "Chart",
    "LayerResult",
    "MapSubplot",
    "Panel",
    "PlotLayer",
    "Subplot",
]
