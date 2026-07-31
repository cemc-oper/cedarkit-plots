"""Plot engine: unified loading and rendering of plot definitions.

Currently provides the *loader* (moved from ``cedar_graph.quickplot``):
dynamic loading of plot modules plus metadata creation/filling. The
``PlotEngine`` pipeline and YAML recipe support are added in a later
phase; the loader is structured so recipe (``.yaml``) dispatch slots in
alongside module (``.py``) loading.
"""

from .loader import (
    Metadata,
    convert_metadata,
    create_metadata,
    get_metadata_class,
    get_plot_module,
    item_processor_map,
    process_area_range,
    process_forecast_time,
    process_start_time,
)

__all__ = [
    "Metadata",
    "convert_metadata",
    "create_metadata",
    "get_metadata_class",
    "get_plot_module",
    "item_processor_map",
    "process_area_range",
    "process_forecast_time",
    "process_start_time",
]
