"""Built-in operation descriptors for workflow recipes."""

from __future__ import annotations

from typing import Any
import json

import numpy as np
import xarray as xr

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


def time_diff(field: Any, previous: Any, *, accumulation_hours: float | None = None,
              since_initialization: bool = False, context: Any = None) -> Any:
    """Subtract planned endpoints; optionally enforce a cumulative amount contract."""
    if since_initialization:
        return _accumulation_difference(field, previous, accumulation_hours)
    result = field - previous
    result.attrs = dict(field.attrs)
    if accumulation_hours is not None:
        result.attrs["accumulation_hours"] = accumulation_hours
    return result



def _accumulation_difference(field, previous, hours):
    """Validate two since-initialization amounts before subtracting their values."""
    def evidence(array, key):
        try:
            return json.loads(array.attrs[key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"accumulation endpoint requires {key}") from exc

    identities = [evidence(a, "field_identity") for a in (field, previous)]
    intervals = [evidence(a, "statistical_interval") for a in (field, previous)]
    encoding = [evidence(a, "value_encoding") for a in (field, previous)]
    current, prior = identities
    if not current.get("parameter", "").endswith(".since-initialization"):
        raise ValueError("accumulation needs an explicit since-initialization parameter")
    semantic = {"parameter", "time", "level_type", "level", "layer", "member", "member_role"}
    if any(current.get(k) != prior.get(k) for k in semantic):
        raise ValueError("accumulation endpoints have different reference/parameter/vertical/member identities")
    origin = pd.Timestamp(current["time"])
    steps = [pd.Timedelta(i["step"]) for i in identities]
    if hours is None or steps[1] < pd.Timedelta(0) or steps[0] - steps[1] != pd.Timedelta(hours=hours):
        raise ValueError("accumulation endpoints do not span the requested window")
    for identity, interval, step in zip(identities, intervals, steps):
        if (pd.Timestamp(interval["start"]) != origin or pd.Timestamp(interval["end"]) != origin + step
                or pd.Timestamp(identity["valid_time"]) != origin + step):
            raise ValueError("accumulation endpoint has reset or inconsistent cumulative clocks")
    if field.dims != previous.dims:
        raise ValueError("accumulation endpoint dimensions differ")
    xr.align(field, previous, join="exact", copy=False)
    for name, coordinate in field.coords.items():
        if coordinate.ndim and (name not in previous.coords or not coordinate.variable.identical(previous.coords[name].variable)):
            raise ValueError("accumulation endpoint spatial coordinates differ")
    if field.attrs.get("units") != "mm" or previous.attrs.get("units") != "mm":
        raise ValueError("reviewed accumulation amounts require mm endpoints")
    errors = [e["quantization_error"] for e in encoding]
    if any(e.get("unit") != "mm" or not np.isfinite(v) or v < 0 for e, v in zip(encoding, errors)):
        raise ValueError("accumulation quantization evidence is invalid or has different units")
    if steps[1] == pd.Timedelta(0) and np.any(np.abs(previous.values) > errors[1]):
        raise ValueError("zero-hour accumulation must be an initialization zero")
    result = field - previous
    tolerance = float(sum(errors))
    if np.isinf(result.values).any() or np.any(result.values < -tolerance):
        raise ValueError("accumulation decreased beyond encoded quantization bounds; reset or inconsistent endpoints")
    # Keep small negative differences and missing points exactly as decoded.
    # The endpoint reports remain input evidence, never a completeness claim for this derived field.
    result = result.assign_coords({name: coordinate for name, coordinate in field.coords.items() if coordinate.ndim == 0})
    result.attrs = {
        "units": "mm", "long_name": f"{hours:g}-hour total precipitation",
        "accumulation_hours": hours,
        "accumulation_start": (origin + steps[1]).isoformat(),
        "accumulation_end": (origin + steps[0]).isoformat(),
        "negative_difference_bound": tolerance,
        "negative_difference_points": int(np.count_nonzero(result.values < 0)),
        "negative_difference_policy": "retain within encoded quantization bounds; reject larger decreases",
        "source_field_identities": json.dumps(identities, sort_keys=True),
        "source_references": json.dumps([evidence(a, "source_reference") for a in (field, previous)], sort_keys=True),
        "source_query_reports": json.dumps([evidence(a, "cedarkit_query_report") for a in (field, previous)], sort_keys=True),
    }
    return result


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
    OpDescriptor("time_diff", "transform", 1, 1, time_diff, planner=plan_time_diff, contract_version=2),
)
