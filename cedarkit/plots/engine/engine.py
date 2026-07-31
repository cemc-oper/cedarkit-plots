"""Plot engine: execute recipe YAMLs through one drawing pipeline.

The engine adapts a :class:`~cedarkit.plots.engine.recipe.Recipe` to the
same three-piece interface as Python plot modules (``PlotMetadata`` /
``load_data`` / ``plot``), so the quick_plot loader treats ``.yaml`` and
``.py`` plot definitions uniformly (design section 4.4).

Pipeline (implemented once here, replacing the per-module skeleton):

1. pick the domain template by ``metadata.area_range``;
2. prepare data (nearest-neighbour sampling / area extraction via reki
   operators);
3. draw layers in order (style specs incl. ``select`` rules resolved
   against metadata);
4. title (template interpolation + area prefix) and colorbar.
"""

import inspect
from dataclasses import make_dataclass, field as dataclass_field, fields as dataclass_fields
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd
import xarray as xr

from ..chart import Panel
from ..domains import CnAreaMapTemplate, EastAsiaMapTemplate
from ..style import Style, StyleRegistry, get_default_registry
from ..style.schema import LEVEL_TYPE_CODE_TO_NAME
from ..types import AreaRange
from .ops import OpContext, OpRegistry
from .recipe import (
    Recipe,
    RecipeError,
    StyleSelectHolder,
    StyleSpec,
    load_recipe_file,
)


# ---------------------------------------------------------------------------
# domain registry
# ---------------------------------------------------------------------------

class DomainRegistry:
    """Map domain template names to factories.

    A factory receives the plot metadata and returns a domain template
    instance. Selection rule: ``metadata.area_range is None`` → the
    recipe's ``domain.default``, otherwise ``domain.area``.
    """

    def __init__(self):
        self._factories: Dict[str, Callable[[Any], Any]] = {}

    def register(self, name: str, factory: Callable[[Any], Any]) -> None:
        self._factories[name] = factory

    def has(self, name: str) -> bool:
        return name in self._factories

    def create(self, name: str, metadata: Any):
        if name not in self._factories:
            raise KeyError(f"unknown domain {name!r}; registered: {sorted(self._factories)}")
        return self._factories[name](metadata)

    @classmethod
    def defaults(cls) -> "DomainRegistry":
        registry = cls()
        registry.register("east_asia", lambda metadata: EastAsiaMapTemplate())
        registry.register("cn_area", lambda metadata: CnAreaMapTemplate(area=metadata.area_range))
        return registry


# ---------------------------------------------------------------------------
# style spec resolution
# ---------------------------------------------------------------------------

def _resolve_selector_value(path: str, metadata: Any) -> Any:
    """Resolve a dotted ``by`` path against the plot metadata.

    ``pd.Timedelta`` results compare as integer hours; integral floats
    compare as ints (so ``850.0`` matches case key ``"850"``).
    """
    value = metadata
    for part in path.split("."):
        if not hasattr(value, part):
            raise RecipeError("<recipe>", f"select path {path!r}: no attribute {part!r}")
        value = getattr(value, part)
    if isinstance(value, pd.Timedelta):
        value = int(value / pd.Timedelta(hours=1))
    elif isinstance(value, float) and value.is_integer():
        value = int(value)
    return value


def _parse_style_ref(ref: str) -> Tuple[str, Optional[str]]:
    style_id, _, variant = ref.partition(":")
    return style_id, variant or None


def layer_style_target(style: StyleSpec, metadata: Any) -> Tuple[str, Optional[str]]:
    """Resolve a layer style spec to a concrete ``(style_id, variant)``."""
    if isinstance(style, str):
        return _parse_style_ref(style)
    if isinstance(style, StyleSelectHolder):
        value = _resolve_selector_value(style.select.by, metadata)
        for case_key, target in style.select.cases.items():
            if case_key == "else":
                continue
            if str(value) in [item.strip() for item in case_key.split(",")]:
                return _parse_style_ref(target)
        return _parse_style_ref(style.select.cases["else"])
    raise RecipeError("<recipe>", f"unsupported style spec: {style!r}")


# ---------------------------------------------------------------------------
# template resolution
# ---------------------------------------------------------------------------

def resolve_templates(value: Any, metadata: Any) -> Any:
    """
    Resolve ``"{param}"`` placeholders in args/level values against the
    plot metadata. A full-string placeholder keeps the metadata value's
    type (e.g. ``pd.Timedelta``); embedded placeholders are
    string-formatted.
    """
    if isinstance(value, str):
        if value.startswith("{") and value.endswith("}") and value.count("{") == 1:
            name = value[1:-1]
            if not hasattr(metadata, name):
                raise RecipeError("<recipe>", f"template references unknown param {name!r}")
            return getattr(metadata, name)
        return value.format(**vars(metadata))
    if isinstance(value, list):
        return [resolve_templates(item, metadata) for item in value]
    if isinstance(value, dict):
        return {k: resolve_templates(v, metadata) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------------

#: level type names reki accepts as shorthand for GRIB2 code 100.
_LEVEL_TYPE_ALIASES = {"isobaricInhPa": "pl"}


class PlotEngine:
    """
    Load recipes and adapt them to the plot module interface.

    Parameters
    ----------
    style_registry
        style library; defaults to the process-wide default registry.
    op_registry
        op registry; defaults to the engine built-ins.
    field_registry
        mapping of business field names (recipe ``data.*.field``) to
        field info objects understood by the caller's data loader
        (e.g. cedar-graph ``FieldInfo``). Objects are deep-copied and
        get ``level_type``/``level`` set when the recipe declares a
        ``level``.
    domain_registry
        domain template registry; defaults to east_asia/cn_area.
    """

    def __init__(
            self,
            style_registry: Optional[StyleRegistry] = None,
            op_registry: Optional[OpRegistry] = None,
            field_registry: Optional[Dict[str, Any]] = None,
            domain_registry: Optional[DomainRegistry] = None,
    ):
        self.style_registry = style_registry if style_registry is not None else get_default_registry()
        self.op_registry = op_registry if op_registry is not None else OpRegistry.builtins()
        self.field_registry = field_registry if field_registry is not None else {}
        self.domain_registry = domain_registry if domain_registry is not None else DomainRegistry.defaults()

    # -- loading ------------------------------------------------------

    def load_recipe(self, path: Union[str, Path]) -> Recipe:
        """
        Load a recipe file and check cross references: unknown op, field
        or style id fails at load time (design section 6).
        """
        recipe = load_recipe_file(path)
        self.check_recipe(recipe, path)
        return recipe

    def check_recipe(self, recipe: Recipe, path: Union[str, Path] = "<recipe>") -> None:
        for data_key, spec in recipe.data.items():
            if spec.field is not None and spec.field not in self.field_registry:
                raise RecipeError(
                    path,
                    f"data entry {data_key!r} references unknown field {spec.field!r}; "
                    f"registered: {sorted(self.field_registry)}",
                )
            for transform in spec.transforms:
                self._check_op(transform.op, "transform", path, data_key)
            if spec.compute is not None:
                self._check_op(spec.compute.op, "compute", path, data_key)
        for index, layer in enumerate(recipe.layers):
            for ref in _style_refs(layer.style):
                style_id, variant = _parse_style_ref(ref)
                if style_id not in self.style_registry.style_ids:
                    raise RecipeError(
                        path,
                        f"layer {index} references unknown style id {style_id!r}; "
                        f"loaded: {self.style_registry.style_ids}",
                    )
                if variant is not None:
                    try:
                        self.style_registry.get_style(style_id, variant)
                    except KeyError as e:
                        raise RecipeError(path, f"layer {index}: {e}") from e
        for domain_name in (recipe.domain.default, recipe.domain.area):
            if not self.domain_registry.has(domain_name):
                raise RecipeError(path, f"unknown domain {domain_name!r}")

    def _check_op(self, name: str, expected_kind: str, path, data_key: str) -> None:
        if not self.op_registry.has(name):
            raise RecipeError(
                path,
                f"data entry {data_key!r} references unknown op {name!r}; "
                f"registered: {self.op_registry.op_names}",
            )
        kind = self.op_registry.kind(name)
        if kind != expected_kind:
            raise RecipeError(
                path,
                f"data entry {data_key!r}: op {name!r} is a {kind} op, "
                f"not valid in a {expected_kind} position",
            )

    def build_module(self, recipe: Recipe) -> "PlotModuleAdapter":
        """Adapt a recipe to the plot module interface."""
        return PlotModuleAdapter(self, recipe)

    # -- data loading -------------------------------------------------

    def _resolve_field_info(self, spec, metadata: Any):
        """Deep-copy the registered field info and apply the level spec."""
        from copy import deepcopy

        field_info = deepcopy(self.field_registry[spec.field])
        if spec.level is not None:
            level_name = LEVEL_TYPE_CODE_TO_NAME.get(spec.level.first_level_type)
            if level_name is None:
                raise RecipeError(
                    "<recipe>",
                    f"unknown first_level_type code {spec.level.first_level_type}",
                )
            field_info.level_type = _LEVEL_TYPE_ALIASES.get(level_name, level_name)
            field_info.level = resolve_templates(spec.level.first_level, metadata)
        return field_info

    def load_field(self, recipe: Recipe, data_key: str, data_loader: Any, metadata: Any) -> xr.DataArray:
        """Load the raw field of a data entry (no transforms)."""
        spec = recipe.data[data_key]
        field_info = self._resolve_field_info(spec, metadata)
        return data_loader.load(
            field_info=field_info,
            start_time=metadata.start_time,
            forecast_time=metadata.forecast_time,
        )

    # -- prepare (pipeline step 2) -------------------------------------

    def prepare_data(self, plot_data: Any, metadata: Any, total_area: AreaRange) -> Any:
        """
        Sample/extract every ``xr.DataArray`` field of ``plot_data``
        according to the metadata flags (nearest-neighbour sampling first,
        then area extraction padded by one grid step so contour lines stay
        complete at the boundary — same semantics as the plot modules).
        """
        from reki.operator import extract_region, sample_nearest

        field_names = [
            f.name for f in dataclass_fields(plot_data)
            if isinstance(getattr(plot_data, f.name), xr.DataArray)
        ]

        if getattr(metadata, "auto_sample_nearest", False):
            step = metadata.sample_step
            for name in field_names:
                field = getattr(plot_data, name)
                setattr(plot_data, name, sample_nearest(field, longitude_step=step, latitude_step=step))

        if getattr(metadata, "auto_extract_area", False):
            for name in field_names:
                field = getattr(plot_data, name)
                lat_step = abs(field.latitude.values[1] - field.latitude.values[0])
                lon_step = abs(field.longitude.values[1] - field.longitude.values[0])
                setattr(plot_data, name, extract_region(
                    field,
                    start_longitude=total_area.start_longitude - lon_step,
                    end_longitude=total_area.end_longitude + lon_step,
                    start_latitude=total_area.start_latitude - lat_step,
                    end_latitude=total_area.end_latitude + lat_step,
                ))
        return plot_data

    # -- plot (pipeline steps 1/3/4) ------------------------------------

    def create_domain(self, recipe: Recipe, metadata: Any):
        if metadata.area_range is None:
            return self.domain_registry.create(recipe.domain.default, metadata)
        return self.domain_registry.create(recipe.domain.area, metadata)

    def build_layer_style(self, layer, metadata: Any, data: Optional[xr.DataArray] = None) -> Style:
        style_id, variant = layer_style_target(layer.style, metadata)
        return self.style_registry.get_style(style_id, variant, data=data)

    def build_graph_name(self, recipe: Recipe, metadata: Any) -> str:
        context = dict(vars(metadata))
        forecast_time = metadata.forecast_time
        context["forecast_hour"] = int(forecast_time / pd.Timedelta(hours=1))
        interval = getattr(metadata, "interval", None)
        interval_hours = int(interval / pd.Timedelta(hours=1)) if interval is not None else 24
        context["interval_hour"] = interval_hours
        context["previous_forecast_hour"] = context["forecast_hour"] - interval_hours
        graph_name = recipe.title.graph_name.format(**context)
        if recipe.title.area_prefix and metadata.area_range is not None:
            graph_name = f"{metadata.area_name} {graph_name}"
        return graph_name


def _style_refs(style: StyleSpec) -> List[str]:
    if isinstance(style, str):
        return [style]
    if isinstance(style, StyleSelectHolder):
        return list(style.select.cases.values())
    return []


# ---------------------------------------------------------------------------
# adapter
# ---------------------------------------------------------------------------

_PARAM_TYPES = {
    "float": float,
    "int": int,
    "str": str,
    "timedelta": pd.Timedelta,
}


class PlotModuleAdapter:
    """
    Present a recipe through the Python plot module interface
    (``PlotMetadata`` / ``PlotData`` / ``load_data`` / ``plot``) so the
    quick_plot loader treats recipes and modules uniformly.
    """

    def __init__(self, engine: PlotEngine, recipe: Recipe):
        self.engine = engine
        self.recipe = recipe
        self.PlotMetadata = self._build_metadata_class()
        self.PlotData = self._build_data_class()
        self.load_data = self._build_load_data()

    # -- generated dataclasses -------------------------------------------

    def _build_metadata_class(self):
        recipe = self.recipe
        spec: List[Any] = [
            ("start_time", pd.Timestamp, dataclass_field(default=None)),
            ("forecast_time", pd.Timedelta, dataclass_field(default=None)),
            ("system_name", str, dataclass_field(default=None)),
            ("area_name", Optional[str], dataclass_field(default=None)),
            ("area_range", Optional[AreaRange], dataclass_field(default=None)),
            ("auto_extract_area", bool, dataclass_field(default=True)),
            ("auto_sample_nearest", bool, dataclass_field(default=True)),
            ("sample_step", float, dataclass_field(default=0.09)),
        ]
        for param_name, param in recipe.params.items():
            param_type = _PARAM_TYPES[param.type]
            default = param.default
            if default is not None and param.type == "timedelta":
                default = pd.to_timedelta(default)
            spec.append((param_name, param_type, dataclass_field(default=default)))
        return make_dataclass("PlotMetadata", spec)

    def _build_data_class(self):
        keys: List[str] = []
        for key, spec in self.recipe.data.items():
            if spec.compute is not None and spec.compute.outputs:
                keys.extend(spec.compute.outputs)
            else:
                keys.append(key)
        spec = [(key, xr.DataArray, dataclass_field(default=None)) for key in keys]
        return make_dataclass("PlotData", spec)

    # -- load_data ---------------------------------------------------------

    def _build_load_data(self):
        engine = self.engine
        recipe = self.recipe

        def load_data(data_loader, start_time, forecast_time, **param_values):
            metadata = self.PlotMetadata(start_time=start_time, forecast_time=forecast_time)
            for param_name, param in recipe.params.items():
                value = param_values.get(param_name, getattr(metadata, param_name))
                if value is None:
                    if param.required:
                        raise RecipeError("<recipe>", f"required param {param_name!r} is missing")
                    continue
                value = self._coerce_param(param, value)
                setattr(metadata, param_name, value)

            def raw_loader(data_key: str, at_forecast_time: pd.Timedelta) -> xr.DataArray:
                spec = recipe.data[data_key]
                field_info = engine._resolve_field_info(spec, metadata)
                return data_loader.load(
                    field_info=field_info,
                    start_time=start_time,
                    forecast_time=at_forecast_time,
                )

            data: Dict[str, xr.DataArray] = {}
            for data_key, spec in recipe.data.items():
                context = OpContext(
                    recipe=recipe,
                    data_key=data_key,
                    metadata=metadata,
                    style_registry=engine.style_registry,
                    loader=raw_loader,
                )
                if spec.compute is not None:
                    compute = spec.compute
                    inputs = [data[input_key] for input_key in compute.inputs]
                    args = resolve_templates(compute.args, metadata)
                    kwargs = resolve_templates(compute.kwargs, metadata)
                    result = engine.op_registry.apply_compute(
                        compute.op, inputs, args, kwargs, context,
                    )
                    if compute.outputs:
                        if len(compute.outputs) == 1:
                            result = (result,)
                        if len(result) != len(compute.outputs):
                            raise RecipeError(
                                "<recipe>",
                                f"compute op {compute.op!r} returned {len(result)} fields, "
                                f"expected {len(compute.outputs)}",
                            )
                        for output_key, output_field in zip(compute.outputs, result):
                            data[output_key] = output_field
                        field = None
                    else:
                        field = result
                else:
                    field = engine.load_field(recipe, data_key, data_loader, metadata)
                if field is not None:
                    for transform in spec.transforms:
                        field = engine.op_registry.apply_transform(
                            transform.op,
                            field,
                            resolve_templates(transform.args, metadata),
                            resolve_templates(transform.kwargs, metadata),
                            transform.repeat,
                            context,
                        )
                    data[data_key] = field
            return self.PlotData(**{key: data.get(key) for key in self._plot_data_keys()})

        parameters = [
            inspect.Parameter("data_loader", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("start_time", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("forecast_time", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        ]
        for param_name, param in recipe.params.items():
            if param.required:
                parameters.append(inspect.Parameter(param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD))
            else:
                default = param.default
                if default is not None and param.type == "timedelta":
                    default = pd.to_timedelta(default)
                parameters.append(
                    inspect.Parameter(param_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=default)
                )
        load_data.__signature__ = inspect.Signature(parameters)
        return load_data

    def _plot_data_keys(self) -> List[str]:
        return [f.name for f in dataclass_fields(self.PlotData)]

    @staticmethod
    def _coerce_param(param, value):
        if param.type == "timedelta" and not isinstance(value, pd.Timedelta):
            return pd.to_timedelta(value)
        if param.type == "float" and not isinstance(value, float):
            return float(value)
        if param.type == "int" and not isinstance(value, int):
            return int(value)
        if param.type == "str" and not isinstance(value, str):
            return str(value)
        return value

    # -- plot ----------------------------------------------------------------

    def plot(self, plot_data, plot_metadata) -> Panel:
        engine = self.engine
        recipe = self.recipe

        domain = engine.create_domain(recipe, plot_metadata)
        total_area = domain.total_area()
        plot_data = engine.prepare_data(plot_data, plot_metadata, total_area)

        panel = Panel(domain=domain)
        layer_styles: List[Style] = []
        for layer in recipe.layers:
            if layer.field is not None:
                field = getattr(plot_data, layer.field)
                style = engine.build_layer_style(layer, plot_metadata, data=field)
                panel.plot(field, style=style, layer=layer.layer)
            else:
                field_u = getattr(plot_data, layer.vector.u)
                field_v = getattr(plot_data, layer.vector.v)
                style = engine.build_layer_style(layer, plot_metadata, data=field_u)
                panel.plot([[field_u, field_v]], style=style, layer=layer.layer)
            layer_styles.append(style)

        domain.set_title(
            panel=panel,
            graph_name=engine.build_graph_name(recipe, plot_metadata),
            system_name=plot_metadata.system_name,
            start_time=plot_metadata.start_time,
            forecast_time=plot_metadata.forecast_time,
        )
        if recipe.colorbar is not None:
            colorbar_styles = [layer_styles[index] for index in recipe.colorbar.layers]
            domain.add_colorbar(
                panel=panel,
                style=colorbar_styles[0] if len(colorbar_styles) == 1 else colorbar_styles,
            )
        return panel
