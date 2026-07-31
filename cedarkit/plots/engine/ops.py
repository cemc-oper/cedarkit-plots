"""Transform/compute op registry for recipe processing.

Ops are the only way recipes manipulate data (design decision D4: a
closed vocabulary, no expression evaluation in YAML). Two kinds exist:

* ``transform`` ops map one field to one field and run inside a data
  entry's ``transforms`` chain, e.g. ``smth9`` smoothing.
* ``compute`` ops derive one or more fields from other data entries and
  run in a data entry's ``compute`` section, e.g. ``wind_speed``.

Every op receives an :class:`OpContext` keyword argument giving access
to the style registry, plot metadata and raw-field reloading (needed by
``time_diff``). Business packages (cedar-graph) register diagnostic ops
on top of the engine built-ins.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import xarray as xr

from .recipe import Recipe, RecipeError


@dataclass
class OpContext:
    """Runtime context handed to every op call.

    Attributes
    ----------
    recipe
        the recipe being executed.
    data_key
        key of the data entry currently being processed.
    metadata
        filled plot metadata (start_time/forecast_time/params/...).
    style_registry
        style registry used to resolve ``style_units`` transforms.
    loader
        callable ``loader(data_key, forecast_time) -> xr.DataArray``
        reloading the raw field of another (or the same) data entry at a
        different forecast time, without applying its transforms.
    """

    recipe: Recipe
    data_key: str
    metadata: Any
    style_registry: Any
    loader: Callable[[str, pd.Timedelta], xr.DataArray]

    def style_transform(self) -> Optional[Callable]:
        """
        Units transform declared by the style of the layer plotting this
        data entry (first matching layer), or ``None``.
        """
        from .engine import layer_style_target

        for layer in self.recipe.layers:
            if layer.field != self.data_key:
                continue
            style_id, variant = layer_style_target(layer.style, self.metadata)
            return self.style_registry.get_transform(style_id, variant)
        return None


#: transform op: func(field, *args, context=..., **kwargs) -> field
#: compute op:   func(*fields, *args, context=..., **kwargs) -> field or tuple of fields
_OP_KINDS = ("transform", "compute")


class OpRegistry:
    """Named ops referenced by recipes."""

    def __init__(self):
        self._ops: Dict[str, Callable] = {}
        self._kinds: Dict[str, str] = {}

    def register(self, name: str, func: Callable, kind: str = "transform") -> None:
        if kind not in _OP_KINDS:
            raise ValueError(f"op kind must be one of {_OP_KINDS}, got {kind!r}")
        self._ops[name] = func
        self._kinds[name] = kind

    def has(self, name: str) -> bool:
        return name in self._ops

    def kind(self, name: str) -> str:
        if name not in self._ops:
            raise KeyError(f"unknown op {name!r}; registered: {sorted(self._ops)}")
        return self._kinds[name]

    def get(self, name: str) -> Callable:
        if name not in self._ops:
            raise KeyError(f"unknown op {name!r}; registered: {sorted(self._ops)}")
        return self._ops[name]

    @property
    def op_names(self) -> List[str]:
        return sorted(self._ops)

    def apply_transform(
            self,
            name: str,
            field: xr.DataArray,
            args: List[Any],
            kwargs: Dict[str, Any],
            repeat: int,
            context: OpContext,
    ) -> xr.DataArray:
        kind = self.kind(name)
        if kind != "transform":
            raise RecipeError(
                "<recipe>",
                f"op {name!r} is a {kind} op and cannot be used in transforms",
            )
        func = self._ops[name]
        for _ in range(repeat):
            field = func(field, *args, context=context, **kwargs)
        return field

    def apply_compute(
            self,
            name: str,
            fields: List[xr.DataArray],
            args: List[Any],
            kwargs: Dict[str, Any],
            context: OpContext,
    ):
        kind = self.kind(name)
        if kind != "compute":
            raise RecipeError(
                "<recipe>",
                f"op {name!r} is a {kind} op and cannot be used in compute",
            )
        func = self._ops[name]
        return func(*fields, *args, context=context, **kwargs)

    @classmethod
    def builtins(cls) -> "OpRegistry":
        """Registry with the engine built-in ops."""
        registry = cls()
        registry.register("style_units", _op_style_units)
        registry.register("unit_scale", _op_unit_scale)
        registry.register("unit_offset", _op_unit_offset)
        registry.register("smth9", _op_smth9)
        registry.register("time_diff", _op_time_diff)
        return registry


# ---------------------------------------------------------------------------
# built-in ops
# ---------------------------------------------------------------------------

def _op_style_units(field: xr.DataArray, context: OpContext) -> xr.DataArray:
    """Apply the units conversion declared by the field's style library entry."""
    transform = context.style_transform()
    if transform is None:
        return field
    return transform(field)


def _op_unit_scale(field: xr.DataArray, scale: float, context: OpContext) -> xr.DataArray:
    """Multiply field values by ``scale``."""
    return field * scale


def _op_unit_offset(field: xr.DataArray, offset: float, context: OpContext) -> xr.DataArray:
    """Add ``offset`` to field values."""
    return field + offset


def _op_smth9(field: xr.DataArray, p: float, q: float, wrap: bool, context: OpContext) -> xr.DataArray:
    """NCL smth9 nine-point smoothing (cedarkit-comp)."""
    from cedarkit.comp.smooth import smth9
    from cedarkit.comp.util import apply_to_xarray_values

    return apply_to_xarray_values(field, lambda x: smth9(x, p, q, wrap))


def _op_time_diff(field: xr.DataArray, interval: pd.Timedelta, context: OpContext) -> xr.DataArray:
    """
    Difference against the same field at an earlier forecast time
    (``forecast_time - interval``), e.g. turn accumulated precipitation
    into an interval amount.
    """
    if not isinstance(interval, pd.Timedelta):
        interval = pd.to_timedelta(interval)
    previous = context.loader(context.data_key, context.metadata.forecast_time - interval)
    return field - previous
