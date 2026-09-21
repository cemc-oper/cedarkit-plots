from .layer import Layer
from .core import Chart, LayerResult, MapSubplot, Panel, PlotLayer, Subplot


def __getattr__(name):
    if name == "Schema":
        from .panel import Schema

        globals()[name] = Schema
        return Schema
    raise AttributeError(name)


__all__ = [
    "Chart",
    "Layer",
    "LayerResult",
    "MapSubplot",
    "Panel",
    "PlotLayer",
    "Schema",
    "Subplot",
]
