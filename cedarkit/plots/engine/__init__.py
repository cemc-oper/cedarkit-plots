"""Plot engine: unified loading and rendering of plot definitions.

Provides the *loader* (dynamic loading of plot definitions plus metadata
creation/filling) and the *engine* (recipe YAML schema, op registry and
the ``PlotEngine`` pipeline). Recipes (``.yaml``) and Python plot
modules (``.py``) expose the same three-piece interface and are loaded
through :func:`get_plot_definition`, recipes taking precedence.
"""

from .engine import (
    DomainRegistry,
    PlotEngine,
    PlotModuleAdapter,
    layer_style_target,
    resolve_templates,
)
from .loader import (
    Metadata,
    convert_metadata,
    create_metadata,
    find_recipe_file,
    get_metadata_class,
    get_plot_definition,
    get_plot_module,
    item_processor_map,
    process_area_range,
    process_forecast_time,
    process_start_time,
)
from .ops import OpContext, OpRegistry
from .recipe import Recipe, RecipeError, load_recipe_file

__all__ = [
    "DomainRegistry",
    "Metadata",
    "OpContext",
    "OpRegistry",
    "PlotEngine",
    "PlotModuleAdapter",
    "Recipe",
    "RecipeError",
    "convert_metadata",
    "create_metadata",
    "find_recipe_file",
    "get_metadata_class",
    "get_plot_definition",
    "get_plot_module",
    "item_processor_map",
    "layer_style_target",
    "load_recipe_file",
    "process_area_range",
    "process_forecast_time",
    "process_start_time",
    "resolve_templates",
]
