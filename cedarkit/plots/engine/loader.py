"""Plot definition loader.

Loads a plot definition by name and fills metadata objects from plain
settings dicts. A plot definition (Python module today, YAML recipe in
a later phase) exposes a uniform interface::

    PlotMetadata   — dataclass, filled by the engine from user kwargs
    load_data(data_loader, **metadata) -> PlotData
    plot(plot_data, plot_metadata) -> Panel

This module is business-agnostic: system name mappings and data source
creation stay in the calling package (e.g. cedar-graph) and are
injected by the caller.
"""

import importlib
import types
from dataclasses import dataclass, fields
from typing import Any, Callable, Union

import pandas as pd

from ..types import AreaRange


@dataclass
class Metadata:
    """Generic metadata container filled from a settings dict."""
    ...


def get_plot_module(plot_type: str, base_module_name: str) -> types.ModuleType:
    """
    Return plot module based on plot type.

    Parameters
    ----------
    plot_type
        plot type, a module path relative to ``base_module_name``,
        e.g. ``"cn.t_2m.default"``.
    base_module_name
        base module name, e.g. ``"cedar_graph.plots"``.

    Returns
    -------
    types.ModuleType
        plot module
    """
    plot_module = importlib.import_module(f"{base_module_name}.{plot_type}")
    return plot_module


def get_metadata_class(plot_module: types.ModuleType):
    """
    get ``PlotMetadata`` class from plot module.

    Parameters
    ----------
    plot_module

    Returns
    -------
    PlotMetadata
        A ``PlotMetadata`` class from ``plot_module``.
    """
    metadata_class = plot_module.PlotMetadata
    return metadata_class


def convert_metadata(from_metadata, to_metadata):
    """
    Fill one metadata object (``to_metadata``) properties with
    corresponding properties in another metadata (``from_metadata``).

    Parameters
    ----------
    from_metadata
    to_metadata
    """
    names = set([f.name for f in fields(to_metadata)])
    for k, v in from_metadata.__dict__.items():
        if k in names:
            setattr(to_metadata, k, v)


def create_metadata(metadata_class, plot_settings: dict[str, Any], processor_map: dict[str, Callable]):
    """
    Create a Metadata object, fill properties with all keys in dict.

    Parameters
    ----------
    metadata_class
        metadata class reference.
    plot_settings
        Properties to be filled in Metadata object. No nested dict.
    processor_map
        A function mapper to process item in dict.

    Returns
    -------
    Metadata
        A Metadata object with properties from dict.
    """
    metadata = metadata_class()

    for key in plot_settings.keys():
        value = plot_settings[key]
        if key in processor_map:
            parsed_value = processor_map[key](value)
        else:
            parsed_value = value
        setattr(metadata, key, parsed_value)

    return metadata


def process_start_time(item: Union[str, pd.Timestamp]) -> pd.Timestamp:
    """
    convert item to timestamp object.

    Parameters
    ----------
    item

    Returns
    -------
    pd.Timestamp
    """
    parsed_item = None
    if isinstance(item, str):
        if len(item) == 10:
            parsed_item = pd.to_datetime(item, format="%Y%m%d%H")
        elif len(item) == 12:
            parsed_item = pd.to_datetime(item, format="%Y%m%d%H%M")
        else:
            parsed_item = pd.to_datetime(item)
    elif isinstance(item, pd.Timestamp):
        parsed_item = item
    else:
        raise ValueError("type is not supported")

    return parsed_item


def process_forecast_time(item: Union[str, pd.Timedelta]) -> pd.Timedelta:
    """
    convert item to timedelta object.

    Parameters
    ----------
    item

    Returns
    -------
    pd.Timedelta
    """
    parsed_item = None
    if isinstance(item, str):
        parsed_item = pd.to_timedelta(item)
    elif isinstance(item, pd.Timestamp):
        parsed_item = item
    else:
        raise ValueError("type is not supported")

    return parsed_item


def process_area_range(item: Union[dict, AreaRange]) -> AreaRange:
    """
    convert item to ``AreaRange`` object.

    Parameters
    ----------
    item

    Returns
    -------
    AreaRange
    """
    parsed_item = None
    if isinstance(item, dict):
        parsed_item = AreaRange(**item)
    elif isinstance(item, AreaRange):
        parsed_item = item
    else:
        raise ValueError("type is not supported")

    return parsed_item


item_processor_map = dict(
    start_time=process_start_time,
    forecast_time=process_forecast_time,
    area_range=process_area_range,
    interval=process_forecast_time,
)
