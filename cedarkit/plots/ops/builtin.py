"""Built-in operation descriptors (without legacy style-driven conversion)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .descriptor import OpDescriptor


def unit_scale(field: Any, scale: float, *, context: Any = None) -> Any:
    return field * scale


def unit_offset(field: Any, offset: float, *, context: Any = None) -> Any:
    return field + offset


def smth9(field: Any, p: float, q: float, wrap: bool, *, context: Any = None) -> Any:
    from cedarkit.comp.smooth import smth9 as implementation
    from cedarkit.comp.util import apply_to_xarray_values
    return apply_to_xarray_values(field, lambda values: implementation(values, p, q, wrap))


def time_diff(field: Any, previous: Any, *, context: Any = None) -> Any:
    """Numeric half of time_diff; planning supplies the earlier read."""
    return field - previous


def plan_time_diff(builder: Any, call: Any, context: Any) -> Any:
    """Planner hook protocol: delegated builder creates prior read/subtraction nodes."""
    interval = call.args[0] if call.args else None
    if interval is None:
        raise ValueError("time_diff requires an interval")
    return builder.time_difference(call, pd.to_timedelta(interval), context)


BUILTIN_DESCRIPTORS = (
    OpDescriptor("unit_scale", "transform", 1, 1, unit_scale),
    OpDescriptor("unit_offset", "transform", 1, 1, unit_offset),
    OpDescriptor("smth9", "transform", 1, 1, smth9),
    # Planner expansion presents current and prior values to the numeric primitive.
    OpDescriptor("time_diff", "transform", 1, 1, time_diff, planner=plan_time_diff),
)
