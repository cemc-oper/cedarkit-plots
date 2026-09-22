"""Immutable configuration values and the D03 static configuration resolver.

This module intentionally contains no rendering code.  Configuration objects
are values: mutable mappings and sequences are copied at the boundary,
updates can be merged into a candidate value, and the candidate is committed
only after structural checks succeed.  The resolver does not import
``cedarkit.plots.templates`` or create Matplotlib objects.
"""

from __future__ import annotations

import copy
import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, TypeVar

import matplotlib.colors as mcolors

from .errors import ConfigError, Issue


class _ConfigSentinel:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name

    def __reduce__(self):  # pragma: no cover - defensive for multiprocessing
        return self.name


UNSET = _ConfigSentinel("UNSET")
RESET = _ConfigSentinel("RESET")


def _is_sentinel(value: Any) -> bool:
    return value is UNSET or value is RESET


def _is_declared(value: Any) -> bool:
    return value is not UNSET and value is not RESET


def _fail(message: str, *, code: str = "invalid_config", path: Iterable[str] = ()) -> None:
    raise ConfigError(message, code=code, path=path)


def _check_id(value: Any, field_name: str = "id") -> str:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        _fail(f"{field_name} must be a non-empty string without whitespace", path=(field_name,))
    return value


def _check_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{field_name} must be a bool", path=(field_name,))
    return value


def _check_int(value: Any, field_name: str, *, positive: bool = False, nonnegative: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{field_name} must be an integer", path=(field_name,))
    if positive and value <= 0:
        _fail(f"{field_name} must be positive", path=(field_name,))
    if nonnegative and value < 0:
        _fail(f"{field_name} must be non-negative", path=(field_name,))
    return value


def _check_finite(value: Any, field_name: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{field_name} must be a finite number", path=(field_name,))
    result = float(value)
    if not math.isfinite(result):
        _fail(f"{field_name} must be finite", path=(field_name,))
    if positive and result <= 0:
        _fail(f"{field_name} must be positive", path=(field_name,))
    if nonnegative and result < 0:
        _fail(f"{field_name} must be non-negative", path=(field_name,))
    return result


def _check_color(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not mcolors.is_color_like(value):
        _fail(f"{field_name} must be a Matplotlib color", path=(field_name,))
    return value


def _reject_runtime_object(value: Any) -> None:
    """Reject runtime handles while keeping Matplotlib imports non-constructive."""

    if callable(value):
        _fail("configuration cannot contain executable callbacks", code="runtime_object")
    try:
        from matplotlib.artist import Artist
        from matplotlib.axes import Axes
        from matplotlib.figure import Figure
        from matplotlib.gridspec import GridSpecBase

        if isinstance(value, (Artist, Axes, Figure, GridSpecBase)):
            _fail(
                "configuration cannot contain Figure, Axes, Artist or GridSpec objects",
                code="runtime_object",
            )
    except ImportError:  # pragma: no cover - Matplotlib is a package dependency
        pass


def _freeze(value: Any) -> Any:
    """Recursively make user-owned containers safe to retain."""

    if _is_sentinel(value) or value is None or isinstance(value, (str, bytes, bool, int, float)):
        return value
    _reject_runtime_object(value)
    if isinstance(value, Mapping):
        return MappingProxyType({copy.deepcopy(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    # Cartopy CRS instances and MapInfo values are treated as atomic values.
    try:
        return copy.deepcopy(value)
    except Exception:
        # A third-party immutable value may not implement deepcopy.  It is
        # still safer to retain it than to turn parsing into resource loading.
        return value


def _mapping(value: Any, field_name: str) -> Any:
    if _is_sentinel(value):
        return value
    if not isinstance(value, Mapping):
        _fail(f"{field_name} must be a mapping", path=(field_name,))
    return _freeze(value)


def _sequence(value: Any, field_name: str, *, strings: bool = False) -> Any:
    if _is_sentinel(value):
        return value
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{field_name} must be a sequence", path=(field_name,))
    if not strings and any(isinstance(item, (str, bytes)) for item in value):
        _fail(f"{field_name} must contain values, not strings", path=(field_name,))
    return tuple(_freeze(item) for item in value)


def _pair(value: Any, field_name: str, *, positive: bool = False, nonnegative: bool = False) -> Any:
    if _is_sentinel(value) or value is None:
        return value
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
        _fail(f"{field_name} must be a two-item sequence", path=(field_name,))
    return tuple(
        _check_finite(item, f"{field_name}[{index}]", positive=positive, nonnegative=nonnegative)
        for index, item in enumerate(value)
    )


def _quad(value: Any, field_name: str, *, nonnegative: bool = False) -> Any:
    if _is_sentinel(value):
        return value
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 4:
        _fail(f"{field_name} must be a four-item sequence", path=(field_name,))
    result = tuple(
        _check_finite(item, f"{field_name}[{index}]", nonnegative=nonnegative)
        for index, item in enumerate(value)
    )
    if result[0] + result[1] >= 1 or result[2] + result[3] >= 1:
        _fail(f"{field_name} horizontal and vertical margins must each sum below 1", path=(field_name,))
    return result


def _number_tuple(value: Any, field_name: str, *, allow_none: bool = True) -> Any:
    if _is_sentinel(value) or (value is None and allow_none):
        return value
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{field_name} must be a numeric sequence", path=(field_name,))
    return tuple(_check_finite(item, f"{field_name}[]") for item in value)


def _crs(value: Any, field_name: str) -> Any:
    if _is_sentinel(value) or value is None:
        return value
    try:
        import cartopy.crs as ccrs

        valid = isinstance(value, ccrs.CRS)
    except ImportError:  # pragma: no cover
        valid = False
    if not valid:
        _fail(f"{field_name} must be a Cartopy CRS or None", path=(field_name,))
    return _freeze(value)


@dataclass(frozen=True, kw_only=True, slots=True)
class Cell:
    row: int = field(default=UNSET)
    column: int = field(default=UNSET)
    rowspan: int = field(default=UNSET)
    colspan: int = field(default=UNSET)

    def __post_init__(self) -> None:
        if self.row is UNSET or self.column is UNSET:
            _fail("Cell requires row and column", code="missing_field", path=("cell",))
        _check_int(self.row, "row", nonnegative=True)
        _check_int(self.column, "column", nonnegative=True)
        if _is_declared(self.rowspan):
            _check_int(self.rowspan, "rowspan", positive=True)
        if _is_declared(self.colspan):
            _check_int(self.colspan, "colspan", positive=True)


@dataclass(frozen=True, kw_only=True, slots=True)
class Rect:
    space: str
    bounds: tuple[float, float, float, float]
    subplot: str | None = field(default=UNSET)
    slot: str | None = field(default=UNSET)

    def __post_init__(self) -> None:
        if self.space not in {"figure", "chart", "subplot", "slot"}:
            _fail("Rect.space must be figure, chart, subplot or slot", path=("space",))
        if isinstance(self.bounds, (str, bytes)) or not isinstance(self.bounds, Sequence) or len(self.bounds) != 4:
            _fail("Rect.bounds must contain left, bottom, width and height", path=("bounds",))
        bounds = tuple(_check_finite(value, f"bounds[{index}]") for index, value in enumerate(self.bounds))
        if bounds[2] <= 0 or bounds[3] <= 0:
            _fail("Rect width and height must be positive", path=("bounds",))
        object.__setattr__(self, "bounds", bounds)
        for name in ("subplot", "slot"):
            value = getattr(self, name)
            if _is_declared(value) and value is not None:
                _check_id(value, name)
        subplot = None if self.subplot is UNSET else self.subplot
        slot = None if self.slot is UNSET else self.slot
        if self.space == "subplot" and subplot is None:
            _fail("subplot-space Rect requires subplot", code="missing_field", path=("subplot",))
        if self.space == "slot" and slot is None:
            _fail("slot-space Rect requires slot", code="missing_field", path=("slot",))
        if self.space != "subplot" and subplot is not None:
            _fail("subplot is only valid for subplot-space Rect", path=("subplot",))
        if self.space != "slot" and slot is not None:
            _fail("slot is only valid for slot-space Rect", path=("slot",))


@dataclass(frozen=True, kw_only=True, slots=True)
class SlotSpec:
    position: Cell | Rect = field(default=UNSET)
    kind: str = field(default=UNSET)
    enabled: bool = field(default=UNSET)

    def __post_init__(self) -> None:
        if _is_declared(self.position) and not isinstance(self.position, (Cell, Rect)):
            _fail("SlotSpec.position must be Cell or Rect", path=("position",))
        if _is_declared(self.kind) and self.kind not in {"empty", "title", "colorbar"}:
            _fail("SlotSpec.kind must be empty, title or colorbar", path=("kind",))
        if _is_declared(self.enabled):
            _check_bool(self.enabled, "enabled")


@dataclass(frozen=True, kw_only=True, slots=True)
class ChartSelector:
    id: str | None = field(default=UNSET)
    role: str | None = field(default=UNSET)
    required: bool = field(default=UNSET)

    def __post_init__(self) -> None:
        has_id = self.id is not UNSET and self.id is not None
        has_role = self.role is not UNSET and self.role is not None
        if has_id == has_role:
            _fail("ChartSelector requires exactly one of id or role", code="invalid_selector")
        if has_id:
            _check_id(self.id, "id")
        if has_role:
            _check_id(self.role, "role")
        if _is_declared(self.required):
            _check_bool(self.required, "required")


@dataclass(frozen=True, kw_only=True, slots=True)
class Theme:
    font_family: str = field(default=UNSET)
    font_size: float = field(default=UNSET)
    title_fontsize: float = field(default=UNSET)
    tick_fontsize: float = field(default=UNSET)
    text_color: str = field(default=UNSET)
    figure_facecolor: str = field(default=UNSET)
    axes_facecolor: str = field(default=UNSET)

    def __post_init__(self) -> None:
        for name in ("font_size", "title_fontsize", "tick_fontsize"):
            value = getattr(self, name)
            if _is_declared(value):
                _check_finite(value, name, positive=True)
        for name in ("text_color", "figure_facecolor", "axes_facecolor"):
            value = getattr(self, name)
            if _is_declared(value):
                _check_color(value, name)
        if _is_declared(self.font_family) and not isinstance(self.font_family, str):
            _fail("font_family must be a string", path=("font_family",))


@dataclass(frozen=True, kw_only=True, slots=True)
class TextPosition:
    space: str
    xy: tuple[float, float]
    subplot: str | None = field(default=UNSET)
    slot: str | None = field(default=UNSET)
    ha: str = field(default=UNSET)
    va: str = field(default=UNSET)

    def __post_init__(self) -> None:
        if self.space not in {"figure", "chart", "subplot", "slot"}:
            _fail("TextPosition.space is invalid", path=("space",))
        pair = _pair(self.xy, "xy")
        object.__setattr__(self, "xy", pair)
        for name in ("subplot", "slot"):
            value = getattr(self, name)
            if _is_declared(value) and value is not None:
                _check_id(value, name)
        if self.space == "subplot" and self.subplot not in (UNSET, None):
            pass
        elif self.space != "subplot" and self.subplot not in (UNSET, None):
            _fail("subplot is only valid for subplot-space TextPosition", path=("subplot",))
        if self.space != "slot" and self.slot not in (UNSET, None):
            _fail("slot is only valid for slot-space TextPosition", path=("slot",))
        for name in ("ha", "va"):
            value = getattr(self, name)
            if _is_declared(value) and not isinstance(value, str):
                _fail(f"{name} must be a string", path=(name,))


@dataclass(frozen=True, kw_only=True, slots=True)
class TitleSpec:
    enabled: bool = field(default=UNSET)
    position: TextPosition | Rect = field(default=UNSET)
    fontsize: float = field(default=UNSET)
    color: str = field(default=UNSET)

    def __post_init__(self) -> None:
        if _is_declared(self.enabled):
            _check_bool(self.enabled, "enabled")
        if _is_declared(self.position) and not isinstance(self.position, (TextPosition, Rect)):
            _fail("TitleSpec.position must be TextPosition or Rect", path=("position",))
        if _is_declared(self.fontsize):
            _check_finite(self.fontsize, "fontsize", positive=True)
        if _is_declared(self.color):
            _check_color(self.color, "color")


@dataclass(frozen=True, kw_only=True, slots=True)
class ColorbarSpec:
    enabled: bool = field(default=UNSET)
    position: Rect | TextPosition = field(default=UNSET)
    orientation: str = field(default=UNSET)
    tick_fontsize: float = field(default=UNSET)
    ticks: tuple[float, ...] | None = field(default=UNSET)

    def __post_init__(self) -> None:
        if _is_declared(self.enabled):
            _check_bool(self.enabled, "enabled")
        if _is_declared(self.position) and not isinstance(self.position, (Rect, TextPosition)):
            _fail("ColorbarSpec.position must be Rect or TextPosition", path=("position",))
        if _is_declared(self.orientation) and self.orientation not in {"vertical", "horizontal"}:
            _fail("ColorbarSpec.orientation must be vertical or horizontal", path=("orientation",))
        if _is_declared(self.tick_fontsize):
            _check_finite(self.tick_fontsize, "tick_fontsize", positive=True)
        if _is_declared(self.ticks) and self.ticks is not None:
            object.__setattr__(self, "ticks", _number_tuple(self.ticks, "ticks", allow_none=False))


@dataclass(frozen=True, kw_only=True, slots=True)
class AnnotationSpec:
    text: str
    crs: Any = field(default=UNSET)
    position: TextPosition | None = field(default=UNSET)
    enabled: bool = field(default=UNSET)
    fontsize: float = field(default=UNSET)
    color: str = field(default=UNSET)
    bbox: Mapping[str, Any] | None = field(default=UNSET)

    def __post_init__(self) -> None:
        if _is_declared(self.crs) and self.crs is not None:
            object.__setattr__(self, "crs", _crs(self.crs, "crs"))
            if _is_declared(self.position) and self.position is not None and (
                not isinstance(self.position, TextPosition) or self.position.space != "subplot"
            ):
                _fail("geographic annotation requires subplot-space position", path=("position",))
        if not isinstance(self.text, str):
            _fail("AnnotationSpec.text must be a string", path=("text",))
        if _is_declared(self.position) and self.position is not None and not isinstance(self.position, TextPosition):
            _fail("AnnotationSpec.position must be TextPosition or None", path=("position",))
        if _is_declared(self.enabled):
            _check_bool(self.enabled, "enabled")
        if _is_declared(self.fontsize):
            _check_finite(self.fontsize, "fontsize", positive=True)
        if _is_declared(self.color):
            _check_color(self.color, "color")
        if _is_declared(self.bbox) and self.bbox is not None:
            object.__setattr__(self, "bbox", _mapping(self.bbox, "bbox"))


@dataclass(frozen=True, kw_only=True, slots=True)
class DecorationSpec:
    titles: Mapping[str, TitleSpec] = field(default=UNSET)
    colorbars: Mapping[str, ColorbarSpec] = field(default=UNSET)

    def __post_init__(self) -> None:
        for name in ("titles", "colorbars"):
            value = getattr(self, name)
            if _is_declared(value):
                value = _mapping(value, name)
                for key, item in value.items():
                    _check_id(key, f"{name} id")
                    if item is RESET:
                        continue
                    expected = TitleSpec if name == "titles" else ColorbarSpec
                    if not isinstance(item, expected):
                        _fail(f"{name}[{key!r}] must be {expected.__name__}", path=(name, str(key)))
                object.__setattr__(self, name, value)


@dataclass(frozen=True, kw_only=True, slots=True)
class TimeStepFormatter:
    start_time: Any
    last_step: float

    def __post_init__(self) -> None:
        if callable(self.start_time):
            _fail("TimeStepFormatter.start_time cannot be callable", code="runtime_object")
        _check_finite(self.last_step, "last_step", nonnegative=True)
        object.__setattr__(self, "start_time", _freeze(self.start_time))


@dataclass(frozen=True, kw_only=True, slots=True)
class GridlineSpec:
    xlocators: tuple[float, ...] | None = field(default=UNSET)
    ylocators: tuple[float, ...] | None = field(default=UNSET)
    color: str = field(default=UNSET)
    linewidth: float = field(default=UNSET)
    alpha: float = field(default=UNSET)
    labels: bool = field(default=UNSET)

    def __post_init__(self) -> None:
        for name in ("xlocators", "ylocators"):
            value = getattr(self, name)
            if _is_declared(value) and value is not None:
                object.__setattr__(self, name, _number_tuple(value, name, allow_none=False))
        if _is_declared(self.color):
            _check_color(self.color, "color")
        if _is_declared(self.linewidth):
            _check_finite(self.linewidth, "linewidth", nonnegative=True)
        if _is_declared(self.alpha):
            _check_finite(self.alpha, "alpha", nonnegative=True)
            if self.alpha > 1:
                _fail("alpha must be no greater than 1", path=("alpha",))
        if _is_declared(self.labels):
            _check_bool(self.labels, "labels")


@dataclass(frozen=True, kw_only=True, slots=True)
class BorderSpec:
    enabled: bool = field(default=UNSET)
    color: str = field(default=UNSET)
    linewidth: float = field(default=UNSET)

    def __post_init__(self) -> None:
        if _is_declared(self.enabled):
            _check_bool(self.enabled, "enabled")
        if _is_declared(self.color):
            _check_color(self.color, "color")
        if _is_declared(self.linewidth):
            _check_finite(self.linewidth, "linewidth", nonnegative=True)


@dataclass(frozen=True, kw_only=True, slots=True)
class AxisSpec:
    xticks: tuple[float, ...] | None = field(default=UNSET)
    yticks: tuple[float, ...] | None = field(default=UNSET)
    xlim: tuple[float, float] | None = field(default=UNSET)
    ylim: tuple[float, float] | None = field(default=UNSET)
    invert_y: bool = field(default=UNSET)
    xformatter: str | TimeStepFormatter | None = field(default=UNSET)
    yformatter: str | TimeStepFormatter | None = field(default=UNSET)
    gridlines: GridlineSpec | None = field(default=UNSET)
    border: BorderSpec = field(default=UNSET)

    def __post_init__(self) -> None:
        for name in ("xticks", "yticks"):
            value = getattr(self, name)
            if _is_declared(value) and value is not None:
                object.__setattr__(self, name, _number_tuple(value, name, allow_none=False))
        for name in ("xlim", "ylim"):
            value = getattr(self, name)
            if _is_declared(value) and value is not None:
                pair = _pair(value, name)
                if pair[0] == pair[1]:
                    _fail(f"{name} endpoints must differ", path=(name,))
                if pair[0] > pair[1]:
                    if name == "ylim" and self.invert_y is not True:
                        pair = (pair[1], pair[0])
                    else:
                        _fail(f"{name} must be ascending; use invert_y for display direction", code="axis_direction")
                object.__setattr__(self, name, pair)
        if _is_declared(self.invert_y):
            _check_bool(self.invert_y, "invert_y")
        for name in ("xformatter", "yformatter"):
            value = getattr(self, name)
            if _is_declared(value) and value is not None and not isinstance(value, (str, TimeStepFormatter)):
                _fail(f"{name} must be a format string or TimeStepFormatter", path=(name,))
        if _is_declared(self.gridlines) and self.gridlines is not None and not isinstance(self.gridlines, GridlineSpec):
            _fail("gridlines must be GridlineSpec or None", path=("gridlines",))
        if _is_declared(self.border) and not isinstance(self.border, BorderSpec):
            _fail("border must be BorderSpec", path=("border",))


@dataclass(frozen=True, kw_only=True, slots=True)
class MapFeatureSpec:
    name: str
    kwargs: Mapping[str, Any] = field(default=UNSET)
    enabled: bool = field(default=UNSET)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            _fail("MapFeatureSpec.name must be non-empty", path=("name",))
        if _is_declared(self.kwargs):
            object.__setattr__(self, "kwargs", _mapping(self.kwargs, "kwargs"))
        if _is_declared(self.enabled):
            _check_bool(self.enabled, "enabled")


@dataclass(frozen=True, kw_only=True, slots=True)
class BasemapSpec:
    loader: Any = field(default=UNSET)
    map_type: Any = field(default=UNSET)
    loader_kwargs: Mapping[str, Any] = field(default=UNSET)
    features: tuple[MapFeatureSpec, ...] = field(default=UNSET)
    map_info: Any = field(default=UNSET)

    def __post_init__(self) -> None:
        if _is_declared(self.loader):
            _validate_loader_value(self.loader)
        if _is_declared(self.loader_kwargs):
            object.__setattr__(self, "loader_kwargs", _mapping(self.loader_kwargs, "loader_kwargs"))
        if _is_declared(self.features):
            if isinstance(self.features, (str, bytes)) or not isinstance(self.features, Sequence):
                _fail("features must be an ordered sequence", path=("features",))
            features = tuple(self.features)
            if any(not isinstance(item, MapFeatureSpec) for item in features):
                _fail("features must contain MapFeatureSpec values", path=("features",))
            object.__setattr__(self, "features", features)
        if _is_declared(self.map_info):
            _reject_runtime_object(self.map_info)
            object.__setattr__(self, "map_info", _freeze(self.map_info))


@dataclass(frozen=True, kw_only=True, slots=True)
class SubplotSpec:
    enabled: bool = field(default=UNSET)
    kind: str = field(default=UNSET)
    domain: Any = field(default=UNSET)
    map_crs: Any = field(default=UNSET)
    position: Rect = field(default=UNSET)
    aspect: Any = field(default=UNSET)
    axis: AxisSpec = field(default=UNSET)
    basemap: BasemapSpec | None = field(default=UNSET)
    annotations: Mapping[str, AnnotationSpec] = field(default=UNSET)
    zorder: float = field(default=UNSET)

    def __post_init__(self) -> None:
        if _is_declared(self.enabled):
            _check_bool(self.enabled, "enabled")
        if _is_declared(self.kind) and self.kind not in {"xy", "map"}:
            _fail("SubplotSpec.kind must be xy or map", path=("kind",))
        if _is_declared(self.domain) and self.domain is not None:
            _validate_domain_value(self.domain)
        if _is_declared(self.map_crs):
            _crs(self.map_crs, "map_crs")
        if _is_declared(self.position) and not isinstance(self.position, Rect):
            _fail("position must be Rect", path=("position",))
        if _is_declared(self.aspect):
            if self.aspect not in {"auto", "equal"}:
                _check_finite(self.aspect, "aspect", positive=True)
        if _is_declared(self.axis) and not isinstance(self.axis, AxisSpec):
            _fail("axis must be AxisSpec", path=("axis",))
        if _is_declared(self.basemap) and self.basemap is not None and not isinstance(self.basemap, BasemapSpec):
            _fail("basemap must be BasemapSpec or None", path=("basemap",))
        if _is_declared(self.annotations):
            annotations = _mapping(self.annotations, "annotations")
            for key, item in annotations.items():
                _check_id(key, "annotation id")
                if item is RESET:
                    continue
                if not isinstance(item, AnnotationSpec):
                    _fail("annotations must contain AnnotationSpec values", path=("annotations", str(key)))
            object.__setattr__(self, "annotations", annotations)
        if _is_declared(self.zorder):
            _check_finite(self.zorder, "zorder")
        kind = "xy" if self.kind is UNSET else self.kind
        if kind == "xy":
            if self.domain not in (UNSET, None) or self.map_crs not in (UNSET, None):
                _fail("xy SubplotSpec cannot declare domain or map_crs", code="subplot_kind")
            if self.basemap not in (UNSET, None):
                _fail("xy SubplotSpec cannot declare basemap", code="subplot_kind")
            if _is_declared(self.axis) and self.axis is not None:
                if self.axis.xlim not in (UNSET, None) or self.axis.ylim not in (UNSET, None) or self.axis.invert_y is True:
                    # A map-only axis setting cannot be silently interpreted as XY.
                    pass


@dataclass(frozen=True, kw_only=True, slots=True)
class ChartSpec:
    _subplots_declared: bool = field(default=False, init=False, repr=False, compare=False)
    subplots: Mapping[str, SubplotSpec] = field(default=UNSET)
    theme: Theme = field(default=UNSET)
    decorations: DecorationSpec = field(default=UNSET)

    def __post_init__(self) -> None:
        if _is_declared(self.subplots):
            subplots = _mapping(self.subplots, "subplots")
            for key, item in subplots.items():
                _check_id(key, "subplot id")
                if key == "all":
                    _fail("subplot id 'all' is reserved", code="reserved_id", path=("subplots", str(key)))
                if item is RESET:
                    continue
                if not isinstance(item, SubplotSpec):
                    _fail("subplots must contain SubplotSpec values", path=("subplots", str(key)))
            object.__setattr__(self, "subplots", subplots)
        if _is_declared(self.theme) and not isinstance(self.theme, Theme):
            _fail("theme must be Theme", path=("theme",))
        if _is_declared(self.decorations) and not isinstance(self.decorations, DecorationSpec):
            _fail("decorations must be DecorationSpec", path=("decorations",))


@dataclass(frozen=True, kw_only=True, slots=True)
class ChartRule:
    selector: ChartSelector
    spec: ChartSpec

    def __post_init__(self) -> None:
        if not isinstance(self.selector, ChartSelector):
            _fail("ChartRule.selector must be ChartSelector", path=("selector",))
        if not isinstance(self.spec, ChartSpec):
            _fail("ChartRule.spec must be ChartSpec", path=("spec",))


@dataclass(frozen=True, kw_only=True, slots=True)
class LayoutSpec:
    mode: str = field(default=UNSET)
    rows: int | str = field(default=UNSET)
    columns: int = field(default=UNSET)
    figsize: tuple[float, float] = field(default=UNSET)
    dpi: float = field(default=UNSET)
    margins: tuple[float, float, float, float] = field(default=UNSET)
    wspace: float = field(default=UNSET)
    hspace: float = field(default=UNSET)
    placements: Mapping[str, Cell | Rect] = field(default=UNSET)
    order: tuple[ChartSelector, ...] = field(default=UNSET)
    slots: Mapping[str, SlotSpec] = field(default=UNSET)
    expected_charts: int | None = field(default=UNSET)

    def __post_init__(self) -> None:
        if _is_declared(self.mode) and self.mode not in {"grid", "absolute"}:
            _fail("LayoutSpec.mode must be grid or absolute", path=("mode",))
        if _is_declared(self.rows) and self.rows != "auto":
            _check_int(self.rows, "rows", positive=True)
        if _is_declared(self.columns):
            _check_int(self.columns, "columns", positive=True)
        if _is_declared(self.figsize):
            _pair(self.figsize, "figsize", positive=True)
        if _is_declared(self.dpi):
            _check_finite(self.dpi, "dpi", positive=True)
        if _is_declared(self.margins):
            _quad(self.margins, "margins", nonnegative=True)
        for name in ("wspace", "hspace"):
            value = getattr(self, name)
            if _is_declared(value):
                _check_finite(value, name, nonnegative=True)
        if _is_declared(self.placements):
            placements = _mapping(self.placements, "placements")
            for key, item in placements.items():
                _check_id(key, "placement id")
                if item is RESET:
                    continue
                if not isinstance(item, (Cell, Rect)):
                    _fail("placements values must be Cell or Rect", path=("placements", str(key)))
            object.__setattr__(self, "placements", placements)
        if _is_declared(self.order):
            if isinstance(self.order, (str, bytes)) or not isinstance(self.order, Sequence):
                _fail("order must be a sequence of ChartSelector", path=("order",))
            order = tuple(self.order)
            if any(not isinstance(item, ChartSelector) for item in order):
                _fail("order must contain ChartSelector values", path=("order",))
            object.__setattr__(self, "order", order)
        if _is_declared(self.slots):
            slots = _mapping(self.slots, "slots")
            for key, item in slots.items():
                _check_id(key, "slot id")
                if item is RESET:
                    continue
                if not isinstance(item, SlotSpec):
                    _fail("slots must contain SlotSpec values", path=("slots", str(key)))
            object.__setattr__(self, "slots", slots)
        if _is_declared(self.expected_charts) and self.expected_charts is not None:
            _check_int(self.expected_charts, "expected_charts", nonnegative=True)


def _validate_loader_value(value: Any) -> None:
    if isinstance(value, str):
        if not value:
            _fail("loader string cannot be empty", path=("loader",))
        return
    if value is None:
        return
    if not isinstance(value, type):
        _fail("loader must be a package name or MapLoader subclass", path=("loader",))
    from .map import MapLoader

    if not issubclass(value, MapLoader):
        _fail("loader class must subclass MapLoader", path=("loader",))


def _validate_domain_value(value: Any) -> None:
    from .domains.domain import Domain

    if not isinstance(value, Domain):
        _fail("domain must be cedarkit.plots.domains.Domain", path=("domain",))


@dataclass(frozen=True, kw_only=True, slots=True)
class EffectiveConfig:
    """Read-only result of static configuration resolution."""

    layout: LayoutSpec
    theme: Theme
    charts: Mapping[str, ChartSpec]
    decorations: DecorationSpec
    pending: tuple[Issue, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.layout, LayoutSpec) or not isinstance(self.theme, Theme):
            _fail("EffectiveConfig layout and theme have invalid types")
        if not isinstance(self.decorations, DecorationSpec):
            _fail("EffectiveConfig decorations have invalid type")
        object.__setattr__(self, "charts", MappingProxyType(dict(self.charts)))
        object.__setattr__(self, "pending", tuple(self.pending))


def _default_layout() -> LayoutSpec:
    return LayoutSpec(
        mode="grid", rows=1, columns=1, figsize=(8.0, 8.0), dpi=100.0,
        margins=(.1, .1, .1, .1), wspace=.2, hspace=.2,
        placements={}, order=(), slots={}, expected_charts=None,
    )


def _default_theme() -> Theme:
    return Theme(
        font_family="DejaVu Sans", font_size=10.0, title_fontsize=12.0,
        tick_fontsize=8.0, text_color="black", figure_facecolor="white",
        axes_facecolor="white",
    )


def _effective_cell(value: Cell) -> Cell:
    return Cell(
        row=value.row, column=value.column,
        rowspan=1 if value.rowspan is UNSET else value.rowspan,
        colspan=1 if value.colspan is UNSET else value.colspan,
    )


def _effective_rect(value: Rect) -> Rect:
    return Rect(
        space=value.space, bounds=value.bounds,
        subplot=None if value.subplot is UNSET else value.subplot,
        slot=None if value.slot is UNSET else value.slot,
    )


def _effective_slot(value: SlotSpec) -> SlotSpec:
    if value.position is UNSET:
        _fail("SlotSpec.position is required", code="missing_field", path=("slots", "position"))
    position = _effective_cell(value.position) if isinstance(value.position, Cell) else _effective_rect(value.position)
    return SlotSpec(
        position=position,
        kind="empty" if value.kind is UNSET else value.kind,
        enabled=True if value.enabled is UNSET else value.enabled,
    )


def resolve_layout(
    value: LayoutSpec | _ConfigSentinel = UNSET,
    *,
    chart_ids: Iterable[str] = (),
    chart_declarations: Iterable[tuple[str, str | None]] | None = None,
    complete: bool = False,
) -> tuple[LayoutSpec, tuple[Issue, ...]]:
    """Resolve layout defaults and perform static grid/absolute checks."""

    if value is RESET or value is UNSET:
        value = LayoutSpec()
    if not isinstance(value, LayoutSpec):
        _fail("layout must be LayoutSpec", path=("layout",))
    chart_ids = tuple(chart_ids)
    if chart_declarations is None:
        chart_declarations = tuple((chart_id, None) for chart_id in chart_ids)
    else:
        chart_declarations = tuple(chart_declarations)
        chart_ids = tuple(chart_id for chart_id, _ in chart_declarations)
    defaults = _default_layout()
    mode = defaults.mode if not _is_declared(value.mode) else value.mode
    rows = defaults.rows if not _is_declared(value.rows) else value.rows
    columns = defaults.columns if not _is_declared(value.columns) else value.columns
    figsize = defaults.figsize if not _is_declared(value.figsize) else value.figsize
    dpi = defaults.dpi if not _is_declared(value.dpi) else value.dpi
    margins = defaults.margins if not _is_declared(value.margins) else value.margins
    wspace = defaults.wspace if not _is_declared(value.wspace) else value.wspace
    hspace = defaults.hspace if not _is_declared(value.hspace) else value.hspace
    placements = {} if not _is_declared(value.placements) else {key: item for key, item in value.placements.items() if item is not RESET}
    order = () if not _is_declared(value.order) else tuple(value.order)
    slots_raw = {} if not _is_declared(value.slots) else {key: item for key, item in value.slots.items() if item is not RESET}
    slots = {key: _effective_slot(item) for key, item in slots_raw.items()}
    expected = defaults.expected_charts if not _is_declared(value.expected_charts) else value.expected_charts
    placements = {
        key: _effective_cell(item) if isinstance(item, Cell) else _effective_rect(item)
        for key, item in placements.items()
    }
    effective = LayoutSpec(
        mode=mode, rows=rows, columns=columns, figsize=figsize, dpi=dpi,
        margins=margins, wspace=wspace, hspace=hspace,
        placements=placements, order=order, slots=slots, expected_charts=expected,
    )
    chart_order, order_issues = _ordered_chart_ids(effective, chart_declarations)
    if effective.mode == "grid" and effective.rows == "auto":
        effective = LayoutSpec(
            mode=effective.mode, rows=_auto_grid_rows(effective, chart_order),
            columns=effective.columns, figsize=effective.figsize, dpi=effective.dpi,
            margins=effective.margins, wspace=effective.wspace, hspace=effective.hspace,
            placements=effective.placements, order=effective.order,
            slots=effective.slots, expected_charts=effective.expected_charts,
        )
    issues = order_issues + _layout_issues(effective, chart_ids, chart_order=chart_order)
    blocking = tuple(issue for issue in issues if issue.code not in {"capacity", "missing_target", "expected_charts"})
    if blocking or (complete and issues):
        raise ConfigError(issues=blocking or issues)
    return effective, tuple(issues)


def _cell_bounds(cell: Cell) -> tuple[int, int, int, int]:
    return cell.row, cell.column, cell.row + cell.rowspan, cell.column + cell.colspan


def _cells_overlap(left: Cell, right: Cell) -> bool:
    ltop, lleft, lbottom, lright = _cell_bounds(left)
    rtop, rleft, rbottom, rright = _cell_bounds(right)
    return ltop < rbottom and rtop < lbottom and lleft < rright and rleft < lright


def _auto_grid_rows(layout: LayoutSpec, chart_ids: tuple[str, ...]) -> int:
    """Compute deterministic minimum rows for an auto-height grid."""

    occupied = [item for item in layout.placements.values() if isinstance(item, Cell)]
    occupied.extend(
        slot.position
        for slot in layout.slots.values()
        if slot.enabled and isinstance(slot.position, Cell)
    )
    for chart_id in chart_ids:
        if chart_id in layout.placements:
            continue
        for row in range(0, len(chart_ids) + len(occupied) + 1):
            placed = False
            for column in range(layout.columns):
                candidate = _effective_cell(Cell(row=row, column=column))
                if any(_cells_overlap(candidate, item) for item in occupied):
                    continue
                occupied.append(candidate)
                placed = True
                break
            if placed:
                break
    return max(1, max((item.row + item.rowspan for item in occupied), default=1))


def _ordered_chart_ids(
    layout: LayoutSpec,
    chart_declarations: tuple[tuple[str, str | None], ...],
) -> tuple[tuple[str, ...], list[Issue]]:
    """Return deterministic placement order and order diagnostics."""

    chart_ids = tuple(chart_id for chart_id, _ in chart_declarations)
    if layout.mode != "grid" or not layout.order:
        return chart_ids, []
    ordered: list[str] = []
    seen: set[str] = set()
    issues: list[Issue] = []
    for index, selector in enumerate(layout.order):
        matches = [
            chart_id
            for chart_id, role in chart_declarations
            if _selector_matches(selector, chart_id, role)
        ]
        if not matches and _selector_required(selector):
            issues.append(
                Issue(
                    "missing_target",
                    f"required layout order selector {index} has no matching Chart",
                    ("layout", "order", str(index)),
                )
            )
        for chart_id in matches:
            if chart_id in seen:
                issues.append(
                    Issue(
                        "layout_order",
                        f"Chart {chart_id!r} appears more than once in layout order",
                        ("layout", "order", str(index)),
                    )
                )
                continue
            seen.add(chart_id)
            ordered.append(chart_id)
    ordered.extend(chart_id for chart_id in chart_ids if chart_id not in seen)
    return tuple(ordered), issues


def _layout_issues(
    layout: LayoutSpec,
    chart_ids: tuple[str, ...],
    *,
    chart_order: tuple[str, ...] | None = None,
) -> list[Issue]:
    issues: list[Issue] = []
    chart_set = set(chart_ids)
    if chart_order is None:
        chart_order = chart_ids
    if layout.mode == "grid":
        if any(isinstance(item, Rect) for item in layout.placements.values()):
            issues.append(Issue("layout_position", "grid placements must use Cell", ("layout", "placements")))
        positions: list[tuple[str, Cell]] = []
        for chart_id, item in layout.placements.items():
            if chart_id not in chart_set:
                issues.append(Issue("missing_target", f"placement references unknown Chart {chart_id!r}", ("layout", "placements", chart_id)))
            if isinstance(item, Cell):
                positions.append((chart_id, item))
        for slot_id, slot in layout.slots.items():
            if slot.enabled and not isinstance(slot.position, Cell):
                issues.append(Issue("layout_position", "grid slots must use Cell", ("layout", "slots", slot_id)))
            if slot.enabled and isinstance(slot.position, Cell):
                positions.append((f"slot:{slot_id}", slot.position))
        for index, (left_id, left) in enumerate(positions):
            for right_id, right in positions[index + 1:]:
                if _cells_overlap(left, right):
                    issues.append(Issue("layout_overlap", f"layout positions {left_id!r} and {right_id!r} overlap", ("layout",)))
        if layout.rows == "auto":
            # Auto rows expand for explicit row spans, but columns remain fixed.
            for item_id, cell in positions:
                if cell.column + cell.colspan > layout.columns:
                    issues.append(
                        Issue(
                            "layout_bounds",
                            f"{item_id!r} exceeds the fixed grid columns",
                            ("layout",),
                        )
                    )
        else:
            for item_id, cell in positions:
                if cell.row + cell.rowspan > layout.rows or cell.column + cell.colspan > layout.columns:
                    code = (
                        "layout_bounds"
                        if item_id in layout.placements or item_id.startswith("slot:")
                        else "capacity"
                    )
                    issues.append(Issue(code, f"{item_id!r} exceeds the fixed grid capacity", ("layout",)))
            occupied = list(cell for _, cell in positions)
            for chart_id in chart_order:
                if chart_id in layout.placements:
                    continue
                found = False
                for row in range(layout.rows):
                    for column in range(layout.columns):
                        candidate = _effective_cell(Cell(row=row, column=column))
                        if any(_cells_overlap(candidate, item) for item in occupied):
                            continue
                        occupied.append(candidate)
                        found = True
                        break
                    if found:
                        break
                if not found:
                    issues.append(Issue("capacity", f"no free cell remains for Chart {chart_id!r}", ("layout",)))
    else:
        if any(isinstance(item, Cell) for item in layout.placements.values()):
            issues.append(Issue("layout_position", "absolute placements must use Rect", ("layout", "placements")))
        rects: list[tuple[str, Rect]] = []
        for chart_id, item in layout.placements.items():
            if chart_id not in chart_set:
                issues.append(Issue("missing_target", f"placement references unknown Chart {chart_id!r}", ("layout", "placements", chart_id)))
            if isinstance(item, Rect):
                if item.space != "figure" or not _bounds_in_unit_square(item.bounds):
                    issues.append(Issue("layout_bounds", "absolute placement must be a figure Rect within [0, 1]", ("layout", "placements", chart_id)))
                rects.append((chart_id, item))
        for slot_id, slot in layout.slots.items():
            if slot.enabled:
                if not isinstance(slot.position, Rect) or slot.position.space != "figure" or not _bounds_in_unit_square(slot.position.bounds):
                    issues.append(Issue("layout_bounds", "absolute slot must be a figure Rect within [0, 1]", ("layout", "slots", slot_id)))
                elif isinstance(slot.position, Rect):
                    rects.append((f"slot:{slot_id}", slot.position))
        for index, (left_id, left) in enumerate(rects):
            for right_id, right in rects[index + 1:]:
                if _rects_overlap(left.bounds, right.bounds):
                    issues.append(Issue("layout_overlap", f"layout rectangles {left_id!r} and {right_id!r} overlap", ("layout",)))
        for chart_id in chart_ids:
            if chart_id not in layout.placements:
                issues.append(Issue("missing_target", f"absolute layout needs a placement for {chart_id!r}", ("layout", "placements", chart_id)))
    if layout.expected_charts is not None and len(chart_ids) != layout.expected_charts:
        issues.append(Issue("expected_charts", f"expected {layout.expected_charts} Charts, got {len(chart_ids)}", ("layout", "expected_charts")))
    return issues


def _bounds_in_unit_square(bounds: tuple[float, float, float, float]) -> bool:
    left, bottom, width, height = bounds
    return 0 <= left <= 1 and 0 <= bottom <= 1 and left + width <= 1 and bottom + height <= 1


def _rects_overlap(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> bool:
    ll, lb, lw, lh = left
    rl, rb, rw, rh = right
    return ll < rl + rw and rl < ll + lw and lb < rb + rh and rb < lb + lh


def resolve_theme(value: Theme | _ConfigSentinel = UNSET) -> Theme:
    if value is RESET or value is UNSET:
        return _default_theme()
    if not isinstance(value, Theme):
        _fail("theme must be Theme", path=("theme",))
    defaults = _default_theme()
    return Theme(**{
        name: getattr(value, name) if _is_declared(getattr(value, name)) else getattr(defaults, name)
        for name in ("font_family", "font_size", "title_fontsize", "tick_fontsize", "text_color", "figure_facecolor", "axes_facecolor")
    })


def resolve_axis(value: AxisSpec | _ConfigSentinel = UNSET, *, map_axis: bool = False) -> AxisSpec:
    if value is RESET or value is UNSET:
        value = AxisSpec()
    if not isinstance(value, AxisSpec):
        _fail("axis must be AxisSpec", path=("axis",))
    if map_axis and (_is_declared(value.xlim) and value.xlim is not None or _is_declared(value.ylim) and value.ylim is not None or value.invert_y is True):
        _fail("map axes do not accept xlim, ylim or invert_y", code="axis_not_applicable", path=("axis",))
    gridlines = value.gridlines
    if gridlines is RESET or gridlines is UNSET:
        gridlines = None
    elif gridlines is not None:
        gridlines = GridlineSpec(
            xlocators=None if not _is_declared(gridlines.xlocators) else gridlines.xlocators,
            ylocators=None if not _is_declared(gridlines.ylocators) else gridlines.ylocators,
            color="gray" if not _is_declared(gridlines.color) else gridlines.color,
            linewidth=.5 if not _is_declared(gridlines.linewidth) else gridlines.linewidth,
            alpha=.5 if not _is_declared(gridlines.alpha) else gridlines.alpha,
            labels=False if not _is_declared(gridlines.labels) else gridlines.labels,
        )
    border = value.border
    if border is RESET or border is UNSET:
        border = BorderSpec(enabled=True, color="black", linewidth=1.0)
    else:
        border = BorderSpec(
            enabled=True if not _is_declared(border.enabled) else border.enabled,
            color="black" if not _is_declared(border.color) else border.color,
            linewidth=1.0 if not _is_declared(border.linewidth) else border.linewidth,
        )
    return AxisSpec(
        xticks=None if not _is_declared(value.xticks) else value.xticks,
        yticks=None if not _is_declared(value.yticks) else value.yticks,
        xlim=None if not _is_declared(value.xlim) else value.xlim,
        ylim=None if not _is_declared(value.ylim) else value.ylim,
        invert_y=False if not _is_declared(value.invert_y) else value.invert_y,
        xformatter=None if not _is_declared(value.xformatter) else value.xformatter,
        yformatter=None if not _is_declared(value.yformatter) else value.yformatter,
        gridlines=gridlines,
        border=border,
    )


def resolve_basemap(value: BasemapSpec | _ConfigSentinel = UNSET) -> BasemapSpec | None:
    if value is RESET or value is UNSET or value is None:
        return None
    if not isinstance(value, BasemapSpec):
        _fail("basemap must be BasemapSpec or None", path=("basemap",))
    from .map import DEFAULT_MAP_LOADER_PACKAGE, MapType

    loader = value.loader
    if not _is_declared(loader) or loader is None:
        # Snapshot the package name only.  Importing the package/constructing
        # the loader remains a rendering responsibility.
        loader = DEFAULT_MAP_LOADER_PACKAGE
    map_type = MapType.Portrait if not _is_declared(value.map_type) else value.map_type
    if not isinstance(map_type, MapType):
        _fail("map_type must be an existing MapType", path=("map_type",))
    loader_kwargs = {} if not _is_declared(value.loader_kwargs) else dict(value.loader_kwargs)
    features = () if not _is_declared(value.features) else tuple(value.features)
    resolved_features = tuple(
        MapFeatureSpec(
            name=item.name,
            kwargs={} if not _is_declared(item.kwargs) else item.kwargs,
            enabled=True if not _is_declared(item.enabled) else item.enabled,
        )
        for item in features
    )
    map_info = None if not _is_declared(value.map_info) else value.map_info
    return BasemapSpec(
        loader=loader, map_type=map_type, loader_kwargs=loader_kwargs,
        features=resolved_features, map_info=map_info,
    )


def resolve_subplot(
    subplot_id: str,
    value: SubplotSpec,
    *,
    pending: list[Issue],
) -> SubplotSpec:
    kind = "xy" if not _is_declared(value.kind) else value.kind
    enabled = True if not _is_declared(value.enabled) else value.enabled
    raw_domain = value.domain
    domain = None if not _is_declared(raw_domain) or raw_domain is None else raw_domain
    if kind == "map" and domain is not None:
        # Domain is already validated at construction; importing the class is
        # harmless and does not load map resources.
        from .domains.domain import resolve_domain

        domain = resolve_domain(domain)
    map_crs = value.map_crs
    if kind == "map" and (not _is_declared(map_crs) or map_crs is None) and domain is not None:
        map_crs = domain.map_crs if _is_declared(domain.map_crs) else None
        if map_crs is None:
            map_crs = domain.extent_crs
    if kind == "map" and enabled:
        if domain is None:
            pending.append(Issue("missing_domain", f"map subplot {subplot_id!r} has no Domain", ("charts", subplot_id, "subplots", subplot_id, "domain")))
        if not _is_declared(map_crs) or map_crs is None:
            pending.append(Issue("missing_map_crs", f"map subplot {subplot_id!r} has no map CRS", ("charts", subplot_id, "subplots", subplot_id, "map_crs")))
    if kind == "xy" and _is_declared(map_crs) and map_crs is not None:
        _fail("xy subplot cannot resolve a map CRS", code="subplot_kind", path=("subplots", subplot_id, "map_crs"))
    position = value.position
    if not _is_declared(position):
        if subplot_id == "main":
            position = Rect(space="chart", bounds=(.12, .12, .72, .76))
        elif enabled:
            pending.append(Issue("missing_position", f"enabled subplot {subplot_id!r} needs a position", ("subplots", subplot_id, "position")))
            position = Rect(space="chart", bounds=(.12, .12, .72, .76))
        else:
            position = Rect(space="chart", bounds=(.12, .12, .72, .76))
    position = _effective_rect(position)
    if position.space not in {"chart", "subplot"}:
        _fail(
            "subplot position must use chart or subplot space",
            code="layout_position",
            path=("subplots", subplot_id, "position"),
        )
    left, bottom, width, height = position.bounds
    if left < 0 or bottom < 0 or left + width > 1 or bottom + height > 1:
        _fail(
            "subplot position must remain within its parent",
            code="layout_bounds",
            path=("subplots", subplot_id, "position"),
        )
    if subplot_id == "main" and position.space != "chart":
        _fail(
            "main subplot position must use chart space",
            code="layout_position",
            path=("subplots", subplot_id, "position"),
        )
    aspect = ("equal" if kind == "map" else "auto") if not _is_declared(value.aspect) else value.aspect
    axis = resolve_axis(value.axis, map_axis=kind == "map")
    basemap = resolve_basemap(value.basemap)
    annotations = {} if not _is_declared(value.annotations) else {key: item for key, item in value.annotations.items() if item is not RESET}
    resolved_annotations = {
        key: AnnotationSpec(
            text=item.text,
            crs=None if not _is_declared(item.crs) else item.crs,
            position=TextPosition(space="subplot", xy=(.5, .5)) if not _is_declared(item.position) or item.position is None else item.position,
            enabled=True if not _is_declared(item.enabled) else item.enabled,
            fontsize=10.0 if not _is_declared(item.fontsize) else item.fontsize,
            color="black" if not _is_declared(item.color) else item.color,
            bbox=None if not _is_declared(item.bbox) else item.bbox,
        )
        for key, item in annotations.items()
    }
    if kind != "map" and any(item.crs is not None for item in resolved_annotations.values()):
        _fail("geographic annotations require a map subplot", code="subplot_kind")
    zorder = (0.0 if subplot_id == "main" else 1.0) if not _is_declared(value.zorder) else value.zorder
    return SubplotSpec(
        enabled=enabled, kind=kind, domain=domain, map_crs=None if not _is_declared(map_crs) else map_crs,
        position=position, aspect=aspect, axis=axis, basemap=basemap,
        annotations=resolved_annotations, zorder=zorder,
    )


def resolve_chart_spec(value: ChartSpec | _ConfigSentinel = UNSET, *, pending: list[Issue], chart_id: str = "") -> ChartSpec:
    if value is RESET or value is UNSET:
        value = ChartSpec()
    if not isinstance(value, ChartSpec):
        _fail("chart_defaults and chart rule specs must be ChartSpec", path=("charts", chart_id))
    raw_subplots = {} if not _is_declared(value.subplots) else {key: item for key, item in value.subplots.items() if item is not RESET}
    if not raw_subplots:
        raw_subplots = {"main": SubplotSpec()}
    elif "main" not in raw_subplots:
        raw_subplots["main"] = SubplotSpec()
    resolved_subplots = {
        subplot_id: resolve_subplot(subplot_id, item, pending=pending)
        for subplot_id, item in raw_subplots.items()
    }
    for subplot_id, subplot in resolved_subplots.items():
        for annotation_id, annotation in subplot.annotations.items():
            if annotation.crs is None:
                continue
            target_id = annotation.position.subplot
            target_id = subplot_id if target_id in (UNSET, None) else target_id
            target = resolved_subplots.get(target_id)
            path = ("charts", chart_id, "subplots", subplot_id, "annotations", annotation_id)
            if target is None or not target.enabled:
                pending.append(Issue("missing_target", f"annotation targets missing subplot {target_id!r}", path))
            elif target.kind != "map":
                _fail("geographic annotation target must be a map subplot", code="subplot_kind", path=path)
        position = subplot.position
        if position.space != "subplot":
            continue
        parent_id = position.subplot
        if parent_id not in resolved_subplots or not resolved_subplots[parent_id].enabled:
            pending.append(
                Issue(
                    "missing_target",
                    f"subplot {subplot_id!r} references missing or disabled parent {parent_id!r}",
                    ("charts", chart_id, "subplots", subplot_id, "position"),
                )
            )
        if parent_id == subplot_id:
            _fail(
                f"subplot {subplot_id!r} cannot reference itself",
                code="layout_dependency",
                path=("charts", chart_id, "subplots", subplot_id, "position"),
            )
    visiting: set[str] = set()
    visited: set[str] = set()

    def check_parent_chain(subplot_id: str) -> None:
        if subplot_id in visited:
            return
        if subplot_id in visiting:
            _fail(
                "subplot positions contain a cycle",
                code="layout_dependency",
                path=("charts", chart_id, "subplots", subplot_id, "position"),
            )
        visiting.add(subplot_id)
        position = resolved_subplots[subplot_id].position
        if position.space == "subplot" and position.subplot in resolved_subplots:
            check_parent_chain(position.subplot)
        visiting.remove(subplot_id)
        visited.add(subplot_id)

    for subplot_id in resolved_subplots:
        check_parent_chain(subplot_id)
    main = resolved_subplots.get("main")
    if main is None or not main.enabled:
        _fail("each Chart must have one enabled main subplot", code="missing_main", path=("charts", chart_id))
    theme = resolve_theme(value.theme)
    decorations = resolve_decorations(value.decorations)
    result = ChartSpec(subplots=resolved_subplots, theme=theme, decorations=decorations)
    object.__setattr__(result, "_subplots_declared", _is_declared(value.subplots))
    return result


def resolve_title(value: TitleSpec) -> TitleSpec:
    return TitleSpec(
        enabled=True if not _is_declared(value.enabled) else value.enabled,
        position=UNSET if value.position is RESET else value.position,
        fontsize=UNSET if value.fontsize is RESET else value.fontsize,
        color=UNSET if value.color is RESET else value.color,
    )


def resolve_colorbar(value: ColorbarSpec) -> ColorbarSpec:
    return ColorbarSpec(
        enabled=True if not _is_declared(value.enabled) else value.enabled,
        position=UNSET if value.position is RESET else value.position,
        orientation="vertical" if not _is_declared(value.orientation) else value.orientation,
        tick_fontsize=UNSET if value.tick_fontsize is RESET else value.tick_fontsize,
        ticks=None if not _is_declared(value.ticks) else value.ticks,
    )


def resolve_decorations(value: DecorationSpec | _ConfigSentinel = UNSET) -> DecorationSpec:
    if value is RESET or value is UNSET:
        return DecorationSpec(titles={}, colorbars={})
    if not isinstance(value, DecorationSpec):
        _fail("decorations must be DecorationSpec", path=("decorations",))
    titles = {} if not _is_declared(value.titles) else {key: resolve_title(item) for key, item in value.titles.items() if item is not RESET}
    colorbars = {} if not _is_declared(value.colorbars) else {key: resolve_colorbar(item) for key, item in value.colorbars.items() if item is not RESET}
    return DecorationSpec(titles=titles, colorbars=colorbars)


def _chart_declarations(charts: Any) -> tuple[tuple[str, str | None], ...]:
    if charts is UNSET or charts is None:
        return ()
    if isinstance(charts, Mapping):
        items = charts.items()
    else:
        items = ((getattr(item, "id", UNSET), item) for item in charts)
    result: list[tuple[str, str | None]] = []
    for key, item in items:
        chart_id = key
        role = None
        if isinstance(item, Mapping):
            chart_id = item.get("id", chart_id)
            role = item.get("role")
        else:
            chart_id = getattr(item, "id", chart_id)
            role = getattr(item, "role", None)
        _check_id(chart_id, "chart id")
        if role is not None:
            _check_id(role, "role")
        if any(existing_id == chart_id for existing_id, _ in result):
            _fail(f"duplicate Chart id {chart_id!r}", code="duplicate_id", path=("charts", chart_id))
        result.append((chart_id, role))
    return tuple(result)


def _selector_required(selector: ChartSelector) -> bool:
    return False if selector.required is UNSET else selector.required


def _selector_matches(selector: ChartSelector, chart_id: str, role: str | None) -> bool:
    if selector.id is not UNSET and selector.id is not None:
        return selector.id == chart_id
    return selector.role == role


def _map_chart_specs(
    chart_declarations: tuple[tuple[str, str | None], ...],
    chart_defaults: ChartSpec | _ConfigSentinel,
    chart_rules: Any,
    chart_configs: Mapping[str, ChartSpec] | _ConfigSentinel = UNSET,
    panel_theme: Theme | _ConfigSentinel = UNSET,
    *,
    pending: list[Issue],
    template_chart_defaults: ChartSpec | _ConfigSentinel = UNSET,
    template_chart_rules: Any = UNSET,
    template_theme: Theme | _ConfigSentinel = UNSET,
    user_chart_defaults: ChartSpec | _ConfigSentinel = UNSET,
    user_chart_rules: Any = UNSET,
    user_theme: Theme | _ConfigSentinel = UNSET,
) -> dict[str, ChartSpec]:
    source_mode = any(
        value is not UNSET
        for value in (
            template_chart_defaults,
            template_chart_rules,
            template_theme,
            user_chart_defaults,
            user_chart_rules,
            user_theme,
        )
    )
    if chart_configs is not UNSET:
        if not isinstance(chart_configs, Mapping):
            _fail("chart_configs must be a mapping", path=("chart_configs",))
        for chart_id, spec in chart_configs.items():
            _check_id(chart_id, "chart config id")
            if not isinstance(spec, ChartSpec):
                _fail("chart_configs values must be ChartSpec", path=("chart_configs", chart_id))
    if source_mode:
        for name, spec in (
            ("template_chart_defaults", template_chart_defaults),
            ("user_chart_defaults", user_chart_defaults),
        ):
            if spec is not UNSET and spec is not RESET and not isinstance(spec, ChartSpec):
                _fail(f"{name} must be ChartSpec", path=(name,))
        template_rules = () if template_chart_rules is UNSET else template_chart_rules
        user_rules_declared = user_chart_rules is not UNSET
        selected_rules = user_chart_rules if user_rules_declared else template_rules
        if isinstance(selected_rules, (str, bytes)) or not isinstance(selected_rules, Sequence):
            _fail("chart_rules must be a sequence", path=("chart_rules",))
        for rule in selected_rules:
            if not isinstance(rule, ChartRule):
                _fail("chart_rules must contain ChartRule values", path=("chart_rules",))
        template_rules = tuple(template_rules)
        if user_rules_declared and (
            isinstance(user_chart_rules, (str, bytes)) or not isinstance(user_chart_rules, Sequence)
        ):
            _fail("chart_rules must be a sequence", path=("chart_rules",))
        user_rules = tuple(user_chart_rules) if user_rules_declared else ()
        if any(not isinstance(rule, ChartRule) for rule in user_rules):
            _fail("chart_rules must contain ChartRule values", path=("chart_rules",))
        matched: dict[str, list[ChartRule]] = {chart_id: [] for chart_id, _ in chart_declarations}
        for index, rule in enumerate(selected_rules):
            matches = [
                chart_id
                for chart_id, role in chart_declarations
                if _selector_matches(rule.selector, chart_id, role)
            ]
            if not matches and _selector_required(rule.selector):
                pending.append(
                    Issue(
                        "missing_target",
                        f"required chart rule {index} has no matching Chart",
                        ("chart_rules", str(index)),
                    )
                )
            for chart_id in matches:
                matched[chart_id].append(rule)

        template_matches: dict[str, list[ChartRule]] = {chart_id: [] for chart_id, _ in chart_declarations}
        user_matches: dict[str, list[ChartRule]] = {chart_id: [] for chart_id, _ in chart_declarations}
        if not user_rules_declared:
            template_matches = matched
        else:
            user_matches = matched
        for chart_id, rules_for_chart in (*template_matches.items(), *user_matches.items()):
            if len(rules_for_chart) > 1:
                _fail(
                    f"Chart {chart_id!r} matches more than one chart rule",
                    code="rule_conflict",
                    path=("chart_rules", chart_id),
                )

        def without_theme(spec: Any) -> Any:
            if spec is UNSET or spec is RESET:
                return spec
            return ChartSpec(subplots=spec.subplots, decorations=spec.decorations)

        def add_theme(base: Any, value: Any) -> Any:
            if value is UNSET or value is RESET:
                return base
            return merge_config(base, value)

        specs: dict[str, ChartSpec] = {}
        for chart_id, _ in chart_declarations:
            base = ChartSpec()
            template_default = template_chart_defaults
            user_default = user_chart_defaults
            if template_default is not UNSET and template_default is not RESET:
                base = merge_config(base, without_theme(template_default))
            template_rule = template_matches[chart_id][0] if template_matches[chart_id] else None
            user_rule = user_matches[chart_id][0] if user_matches[chart_id] else None
            if template_rule is not None:
                base = merge_config(base, without_theme(template_rule.spec))
            if user_default is not UNSET and user_default is not RESET:
                base = merge_config(base, without_theme(user_default))
            if user_rule is not None:
                base = merge_config(base, without_theme(user_rule.spec))
            if chart_configs is not UNSET and chart_id in chart_configs:
                base = merge_config(base, without_theme(chart_configs[chart_id]))

            effective_theme: Any = UNSET
            if not user_rules_declared:
                effective_theme = add_theme(effective_theme, template_theme)
                if template_default is not UNSET and template_default is not RESET:
                    effective_theme = add_theme(effective_theme, template_default.theme)
                if template_rule is not None:
                    effective_theme = add_theme(effective_theme, template_rule.spec.theme)
                effective_theme = add_theme(effective_theme, user_theme)
                if user_default is not UNSET and user_default is not RESET:
                    effective_theme = add_theme(effective_theme, user_default.theme)
            else:
                effective_theme = add_theme(effective_theme, template_theme)
                if template_default is not UNSET and template_default is not RESET:
                    effective_theme = add_theme(effective_theme, template_default.theme)
                effective_theme = add_theme(effective_theme, user_theme)
                if user_default is not UNSET and user_default is not RESET:
                    effective_theme = add_theme(effective_theme, user_default.theme)
                if user_rule is not None:
                    effective_theme = add_theme(effective_theme, user_rule.spec.theme)
            if chart_configs is not UNSET and chart_id in chart_configs:
                effective_theme = add_theme(effective_theme, chart_configs[chart_id].theme)
            base = merge_config(base, ChartSpec(theme=effective_theme))
            specs[chart_id] = resolve_chart_spec(base, pending=pending, chart_id=chart_id)
        return specs

    rules = () if chart_rules is UNSET else chart_rules
    if isinstance(rules, (str, bytes)) or not isinstance(rules, Sequence):
        _fail("chart_rules must be a sequence", path=("chart_rules",))
    for rule in rules:
        if not isinstance(rule, ChartRule):
            _fail("chart_rules must contain ChartRule values", path=("chart_rules",))
    matched: dict[str, list[ChartRule]] = {chart_id: [] for chart_id, _ in chart_declarations}
    for index, rule in enumerate(rules):
        matches = [chart_id for chart_id, role in chart_declarations if _selector_matches(rule.selector, chart_id, role)]
        if not matches and _selector_required(rule.selector):
            pending.append(Issue("missing_target", f"required chart rule {index} has no matching Chart", ("chart_rules", str(index))))
        for chart_id in matches:
            matched[chart_id].append(rule)
    specs: dict[str, ChartSpec] = {}
    for chart_id, rules_for_chart in matched.items():
        if len(rules_for_chart) > 1:
            _fail(f"Chart {chart_id!r} matches more than one chart rule", code="rule_conflict", path=("chart_rules", chart_id))
        base = ChartSpec()
        if chart_defaults is not UNSET:
            base = merge_config(base, chart_defaults)
        if rules_for_chart:
            base = merge_config(base, rules_for_chart[0].spec)
        if panel_theme is not UNSET and panel_theme is not RESET:
            base = _apply_theme_patch(base, panel_theme)
        if chart_configs is not UNSET and chart_id in chart_configs:
            base = merge_config(base, chart_configs[chart_id])
        specs[chart_id] = resolve_chart_spec(base, pending=pending, chart_id=chart_id)
    return specs


def resolve_config(
    *,
    layout: LayoutSpec | _ConfigSentinel = UNSET,
    theme: Theme | _ConfigSentinel = UNSET,
    chart_defaults: ChartSpec | _ConfigSentinel = UNSET,
    chart_rules: Sequence[ChartRule] | _ConfigSentinel = UNSET,
    chart_configs: Mapping[str, ChartSpec] | _ConfigSentinel = UNSET,
    decorations: DecorationSpec | _ConfigSentinel = UNSET,
    charts: Any = UNSET,
    complete: bool = False,
    template_chart_defaults: ChartSpec | _ConfigSentinel = UNSET,
    template_chart_rules: Sequence[ChartRule] | _ConfigSentinel = UNSET,
    template_theme: Theme | _ConfigSentinel = UNSET,
    user_chart_defaults: ChartSpec | _ConfigSentinel = UNSET,
    user_chart_rules: Sequence[ChartRule] | _ConfigSentinel = UNSET,
    user_theme: Theme | _ConfigSentinel = UNSET,
) -> EffectiveConfig:
    """Resolve ordinary configuration without importing templates or fields."""

    declarations = _chart_declarations(charts)
    pending: list[Issue] = []
    resolved_layout, layout_pending = resolve_layout(
        layout,
        chart_ids=(chart_id for chart_id, _ in declarations),
        chart_declarations=declarations,
        complete=False,
    )
    pending.extend(layout_pending)
    resolved_theme = resolve_theme(theme)
    resolved_decorations = resolve_decorations(decorations)
    resolved_charts = _map_chart_specs(
        declarations,
        chart_defaults,
        chart_rules,
        chart_configs,
        panel_theme=theme,
        pending=pending,
        template_chart_defaults=template_chart_defaults,
        template_chart_rules=template_chart_rules,
        template_theme=template_theme,
        user_chart_defaults=user_chart_defaults,
        user_chart_rules=user_chart_rules,
        user_theme=user_theme,
    )
    if resolved_layout.expected_charts is not None and len(declarations) != resolved_layout.expected_charts:
        # resolve_layout already reported this; retain one diagnostic only.
        pass
    pending.extend(_target_issues(resolved_layout, declarations))
    pending = _deduplicate_issues(pending)
    if complete and pending:
        raise ConfigError(issues=pending)
    return EffectiveConfig(
        layout=resolved_layout, theme=resolved_theme,
        charts=resolved_charts, decorations=resolved_decorations,
        pending=tuple(pending),
    )


def _apply_theme_patch(spec: ChartSpec, patch: Theme) -> ChartSpec:
    current = spec.theme
    values = {
        name: getattr(patch, name) if _is_declared(getattr(patch, name)) else getattr(current, name)
        for name in ("font_family", "font_size", "title_fontsize", "tick_fontsize", "text_color", "figure_facecolor", "axes_facecolor")
    }
    return ChartSpec(subplots=spec.subplots, theme=Theme(**values), decorations=spec.decorations)


def _target_issues(layout: LayoutSpec, declarations: tuple[tuple[str, str | None], ...]) -> list[Issue]:
    chart_ids = {chart_id for chart_id, _ in declarations}
    return [
        Issue("missing_target", f"placement references unknown Chart {chart_id!r}", ("layout", "placements", chart_id))
        for chart_id in layout.placements
        if chart_id not in chart_ids
    ]


def _deduplicate_issues(issues: Iterable[Issue]) -> list[Issue]:
    result: list[Issue] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for issue in issues:
        key = (issue.code, issue.message, issue.path)
        if key not in seen:
            result.append(issue)
            seen.add(key)
    return result


_T = TypeVar("_T")
_MAPPING_MERGE_FIELDS = {
    "subplots",
    "annotations",
    "titles",
    "colorbars",
    "placements",
    "slots",
}


def merge_config(base: _T, patch: _T | _ConfigSentinel) -> _T:
    """Recursively merge a configuration patch without mutating either value."""

    if patch is UNSET:
        return base
    if patch is RESET:
        return UNSET  # type: ignore[return-value]
    if not dataclasses.is_dataclass(patch):
        return _freeze(patch)
    compatible_chart_specs = isinstance(base, ChartSpec) and isinstance(patch, ChartSpec)
    if not dataclasses.is_dataclass(base) or (type(base) is not type(patch) and not compatible_chart_specs):
        return _freeze(patch)
    values: dict[str, Any] = {}
    for config_field in dataclasses.fields(patch):
        if not config_field.init:
            continue
        patch_value = getattr(patch, config_field.name)
        base_value = getattr(base, config_field.name)
        if patch_value is UNSET:
            values[config_field.name] = base_value
        elif patch_value is RESET:
            values[config_field.name] = UNSET
        elif (
            config_field.name in _MAPPING_MERGE_FIELDS
            and isinstance(patch_value, Mapping)
        ):
            values[config_field.name] = _merge_mapping(base_value, patch_value)
        elif dataclasses.is_dataclass(patch_value) and dataclasses.is_dataclass(base_value):
            values[config_field.name] = merge_config(base_value, patch_value)
        else:
            values[config_field.name] = _freeze(patch_value)
    return type(patch)(**values)


def _merge_mapping(base: Any, patch: Mapping[Any, Any]) -> MappingProxyType:
    result = {} if base in (UNSET, RESET) else dict(base)
    if not patch and base not in (UNSET, RESET):
        return MappingProxyType(result)
    for key, patch_value in patch.items():
        if patch_value is RESET:
            result.pop(key, None)
        elif key in result and dataclasses.is_dataclass(patch_value) and dataclasses.is_dataclass(result[key]):
            result[key] = merge_config(result[key], patch_value)
        else:
            result[key] = _freeze(patch_value)
    return MappingProxyType(result)


def validate_config(config: EffectiveConfig, *, complete: bool = False) -> tuple[Issue, ...]:
    """Return pending static issues, or reject them in complete mode."""

    if not isinstance(config, EffectiveConfig):
        _fail("validate_config requires EffectiveConfig", path=("config",))
    if complete and config.pending:
        raise ConfigError(issues=config.pending)
    return config.pending


# ``parse_config`` is the descriptive alias used by callers that think in
# terms of parsing rather than applying a configuration patch.
parse_config = resolve_config


__all__ = [
    "AnnotationSpec", "AxisSpec", "BasemapSpec", "BorderSpec", "Cell",
    "ChartRule", "ChartSelector", "ChartSpec", "ColorbarSpec", "DecorationSpec",
    "EffectiveConfig", "GridlineSpec", "LayoutSpec", "MapFeatureSpec", "Rect",
    "RESET", "SlotSpec", "SubplotSpec", "TextPosition", "Theme",
    "TimeStepFormatter", "TitleSpec", "UNSET", "merge_config", "parse_config",
    "resolve_axis", "resolve_basemap", "resolve_chart_spec", "resolve_config",
    "resolve_decorations", "resolve_layout", "resolve_theme", "validate_config",
]
