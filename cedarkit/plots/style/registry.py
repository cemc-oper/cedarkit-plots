"""StyleRegistry: load, match and build styles from style YAML files.

Search path order (later paths override earlier ones on duplicate ids):

1. built-in styles shipped with cedarkit-plots (``style/builtin/``)
2. styles from packages exposing the ``cedarkit.plots.styles`` entry point
   (e.g. cedar-graph's business style library)
3. directories listed in the ``CEDARKIT_STYLE_PATH`` environment variable
   (separated by ``os.pathsep``)

Entry point modules are imported when the default registry is created, which
is where they register their named RGB tables via :func:`register_rgb_table`.
"""
import importlib.metadata
import math
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union

import numpy as np
import matplotlib
import matplotlib.colors as mcolors
import xarray as xr

from . import BarbStyle, ColorbarStyle, ContourLabelStyle, ContourStyle, Style
from ..colormap import generate_colormap_using_ncl_colors, get_ncl_colormap
from .schema import (
    ColormapSpec,
    CriteriaEntry,
    HighlightEntry,
    LabelSpec,
    LEVEL_TYPE_NAME_TO_CODE,
    LinspaceLevels,
    RangeLevels,
    StepLevels,
    StyleFile,
    StyleFileError,
    StyleVariant,
    load_style_file,
)
from .units import get_unit_transform


# ---------------------------------------------------------------------------
# named RGB tables
# ---------------------------------------------------------------------------

_rgb_tables: Dict[str, mcolors.ListedColormap] = {}


def register_rgb_table(name: str, colors: Union[Sequence, mcolors.ListedColormap]) -> None:
    """Register a named RGB table for ``colormap.rgb_table`` references."""
    if isinstance(colors, mcolors.ListedColormap):
        _rgb_tables[name] = colors
    else:
        _rgb_tables[name] = mcolors.ListedColormap(list(colors), name=name)


def get_rgb_table(name: str) -> mcolors.ListedColormap:
    try:
        return _rgb_tables[name]
    except KeyError:
        known = ", ".join(sorted(_rgb_tables)) or "<none>"
        raise KeyError(f"unknown rgb_table {name!r}; registered tables: {known}") from None


# ---------------------------------------------------------------------------
# levels evaluation
# ---------------------------------------------------------------------------

def evaluate_levels(levels_spec, data: Optional[xr.DataArray] = None) -> Optional[np.ndarray]:
    """Evaluate a levels spec into an array. ``step`` form requires ``data``."""
    if levels_spec is None:
        return None
    if isinstance(levels_spec, list):
        # keep integer dtype: tick labels of int levels render like the
        # original hardcoded styles ("-12", not "-12.0")
        return np.asarray(levels_spec)
    if isinstance(levels_spec, RangeLevels):
        start, stop, step = levels_spec.range
        return np.arange(start, stop, step)
    if isinstance(levels_spec, LinspaceLevels):
        start, stop, num = levels_spec.linspace
        return np.linspace(start, stop, int(num))
    if isinstance(levels_spec, StepLevels):
        if data is None:
            raise ValueError(
                "levels {step: ...} is data-driven; pass the field via data= "
                "when building the style"
            )
        step = levels_spec.step
        reference = levels_spec.reference
        values = np.asarray(data.values, dtype=float)
        vmin = float(np.nanmin(values))
        vmax = float(np.nanmax(values))
        start = np.floor((vmin - reference) / step) * step + reference
        stop = np.ceil((vmax - reference) / step) * step + reference
        return np.arange(start, stop + step * 0.5, step)
    raise TypeError(f"unsupported levels spec: {levels_spec!r}")


# ---------------------------------------------------------------------------
# colormap building
# ---------------------------------------------------------------------------

class _ColorSource:
    """Intermediate result of a colormap spec.

    ``colors`` is the value for ``ContourStyle.colors`` when no per-level
    expansion is needed. ``table``/``index`` keep the underlying indexed
    source for highlight/label expansion; ``index`` may be scalar (broadcast
    to all levels) or an explicit per-level list.
    """

    def __init__(
            self,
            colors: Any,
            table: Optional[mcolors.ListedColormap] = None,
            index: Optional[Union[int, np.ndarray]] = None,
    ):
        self.colors = colors
        self.table = table
        self.index = index


def _resolve_color_source(spec: Union[str, ColormapSpec], name: str) -> _ColorSource:
    if isinstance(spec, str):
        return _ColorSource(colors=spec)

    if spec.colors is not None:
        colors = spec.colors
        if len(colors) == 1:
            return _ColorSource(colors=colors[0])
        return _ColorSource(colors=mcolors.ListedColormap(colors, name=name))

    if spec.ncl_colors is not None:
        return _ColorSource(colors=generate_colormap_using_ncl_colors(spec.ncl_colors, name=name))

    if spec.ncl is not None:
        if spec.count is not None:
            cmap = get_ncl_colormap(
                spec.ncl,
                count=spec.count,
                spread_start=spec.spread_start,
                spread_end=spec.spread_end,
            )
            return _ColorSource(colors=cmap)
        table = get_ncl_colormap(spec.ncl)
        if table is None:
            raise ValueError(f"ncl colormap not found: {spec.ncl!r}")
        if spec.index is None:
            return _ColorSource(colors=table, table=table)
        index = np.atleast_1d(np.asarray(spec.index)) + spec.index_offset
        colors = mcolors.ListedColormap(table(index), name=name)
        if isinstance(spec.index, int):
            return _ColorSource(colors=colors, table=table, index=int(index[0]))
        return _ColorSource(colors=colors, table=table, index=index)

    if spec.rgb_table is not None:
        table = get_rgb_table(spec.rgb_table)
        if spec.index is None:
            return _ColorSource(colors=table, table=table)
        index = np.atleast_1d(np.asarray(spec.index)) + spec.index_offset
        colors = mcolors.ListedColormap(table(index), name=name)
        if isinstance(spec.index, int):
            return _ColorSource(colors=colors, table=table, index=int(index[0]))
        return _ColorSource(colors=colors, table=table, index=index)

    raise ValueError(f"invalid colormap spec: {spec!r}")


def _expand_per_level_colors(
        source: _ColorSource,
        levels: np.ndarray,
        highlights: List[HighlightEntry],
        style_name: str,
) -> Any:
    """Expand base colors + highlight rules into per-level colors."""
    n = len(levels)

    if source.table is not None and source.index is not None:
        if isinstance(source.index, (int, np.integer)):
            index_array = np.full(n, source.index, dtype=int)
        else:
            index_array = np.asarray(source.index, dtype=int)
            if len(index_array) not in (n, n + 1):
                raise ValueError(
                    f"style {style_name!r}: highlight with per-level colors needs "
                    f"one color index per level ({n}, or {n + 1}), got {len(index_array)}"
                )
        rgba = [tuple(source.table(i)) for i in index_array]
    elif isinstance(source.colors, mcolors.ListedColormap):
        rgba = [tuple(c) for c in source.colors.colors]
        if len(rgba) == 1:
            rgba = rgba * n
    elif isinstance(source.colors, str):
        rgba = [source.colors] * n
    elif source.colors is None:
        rgba = [None] * n
    else:
        rgba = list(source.colors)

    if len(rgba) not in (n, n + 1):
        raise ValueError(
            f"style {style_name!r}: color count {len(rgba)} does not match "
            f"levels count {n} (or {n + 1} for fill)"
        )

    changed = False
    for highlight in highlights:
        positions = np.nonzero(np.isclose(levels, highlight.level))[0]
        if len(positions) == 0:
            raise ValueError(
                f"style {style_name!r}: highlight level {highlight.level} "
                f"is not in levels"
            )
        for pos in positions:
            if highlight.color_index is not None:
                if source.table is None:
                    raise ValueError(
                        f"style {style_name!r}: highlight color_index requires "
                        f"an indexed colormap source (ncl/rgb_table)"
                    )
                rgba[pos] = tuple(source.table(highlight.color_index))
            elif highlight.color is not None:
                rgba[pos] = highlight.color
            changed = True

    if not changed and source.table is None:
        return source.colors
    return mcolors.ListedColormap(rgba, name=style_name)


def _expand_linewidths(
        variant: StyleVariant,
        levels: Optional[np.ndarray],
        highlights: List[HighlightEntry],
        style_name: str,
) -> Optional[Union[float, np.ndarray]]:
    if not any(h.linewidth is not None for h in highlights):
        return variant.linewidth
    if levels is None:
        raise ValueError(
            f"style {style_name!r}: highlight linewidth requires levels"
        )
    # CEMC charts draw feature levels thicker than the 0.7 base line width.
    base = variant.linewidth if variant.linewidth is not None else 0.7
    linewidths = np.full(len(levels), base, dtype=float)
    for highlight in highlights:
        if highlight.linewidth is None:
            continue
        positions = np.nonzero(np.isclose(levels, highlight.level))[0]
        if len(positions) == 0:
            raise ValueError(
                f"style {style_name!r}: highlight level {highlight.level} "
                f"is not in levels"
            )
        linewidths[positions] = highlight.linewidth
    return linewidths


def _build_label_style(
        label_spec: LabelSpec,
        source: Optional[_ColorSource],
        style_name: str,
        line_colors: Any = None,
) -> ContourLabelStyle:
    colors = label_spec.color
    if label_spec.line_colors:
        if isinstance(line_colors, mcolors.Colormap):
            colors = list(line_colors.colors)
        else:
            colors = line_colors
    elif label_spec.color_index is not None:
        if source is None or source.table is None:
            raise ValueError(
                f"style {style_name!r}: label color_index requires an indexed "
                f"colormap source (ncl/rgb_table)"
            )
        index = np.atleast_1d(label_spec.color_index)
        colors = source.table(index)
    fmt = label_spec.fmt
    if fmt is not None:
        fmt = fmt.format
    return ContourLabelStyle(
        inline=label_spec.inline,
        inline_spacing=label_spec.inline_spacing,
        fontsize=label_spec.fontsize,
        fmt=fmt,
        colors=colors,
        background_color=label_spec.background_color,
        manual=label_spec.manual,
        zorder=label_spec.zorder,
    )


def build_style(
        style_id: str,
        variant_name: str,
        variant: StyleVariant,
        data: Optional[xr.DataArray] = None,
) -> Style:
    """Build a ``ContourStyle``/``BarbStyle`` from a style variant spec."""
    style_name = f"{style_id}:{variant_name}"

    if variant.type == "barb":
        kwargs = {}
        if variant.length is not None:
            kwargs["length"] = variant.length
        if variant.linewidth is not None:
            kwargs["linewidth"] = variant.linewidth
        if variant.pivot is not None:
            kwargs["pivot"] = variant.pivot
        if variant.barbcolor is not None:
            kwargs["barbcolor"] = variant.barbcolor
        if variant.flagcolor is not None:
            kwargs["flagcolor"] = variant.flagcolor
        if variant.barb_increments is not None:
            kwargs["barb_increments"] = dict(variant.barb_increments)
        return BarbStyle(**kwargs)

    levels = evaluate_levels(variant.levels, data=data)

    highlights = []
    if variant.highlight is not None:
        if isinstance(variant.highlight, list):
            highlights = list(variant.highlight)
        else:
            highlights = [variant.highlight]

    source: Optional[_ColorSource] = None
    colors = None
    if variant.colormap is not None:
        source = _resolve_color_source(variant.colormap, name=style_name)
        colors = source.colors
    if variant.fill and isinstance(colors, str):
        # bare-string colormap (matplotlib name): resolve to a colormap
        # object so fill colorbars can read ``.N`` — line contours keep
        # the string as a per-line color name. Raises on unknown names.
        colors = matplotlib.colormaps[colors]


    if highlights and any(h.color is not None or h.color_index is not None for h in highlights):
        if levels is None:
            raise ValueError(f"style {style_name!r}: highlight colors require levels")
        if source is None:
            source = _ColorSource(colors=None)
        colors = _expand_per_level_colors(source, levels, highlights, style_name)
    elif (
            source is not None
            and isinstance(source.index, (int, np.integer))
            and levels is not None
            and not variant.fill
    ):
        # scalar color index on a line contour: broadcast to per-level colors
        colors = _expand_per_level_colors(source, levels, [], style_name)

    linewidths = _expand_linewidths(variant, levels, highlights, style_name)

    label = variant.label is not None
    label_style = None
    if label:
        label_style = _build_label_style(variant.label, source, style_name, line_colors=colors)

    colorbar_style = None
    if variant.colorbar is not None:
        colorbar_style = ColorbarStyle(
            loc=variant.colorbar.loc,
            label=variant.colorbar.label,
            label_levels=variant.colorbar.label_levels,
        )

    return ContourStyle(
        colors=colors,
        levels=levels,
        linewidths=linewidths,
        linestyles=variant.linestyles,
        fill=variant.fill,
        label=label,
        label_style=label_style,
        colorbar_style=colorbar_style,
    )


# ---------------------------------------------------------------------------
# criteria matching
# ---------------------------------------------------------------------------

def _normalize_level_type(value: Any) -> Any:
    if isinstance(value, str):
        return LEVEL_TYPE_NAME_TO_CODE.get(value, value)
    return value


def _values_equal(expected: Any, actual: Any) -> bool:
    if actual is None:
        return False
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-12)
    return expected == actual


def _entry_matches(entry: CriteriaEntry, metadata: Mapping[str, Any]) -> bool:
    for key in (
            "cemc_name", "eccodes_name", "wgrib2_name",
            "first_level_type", "first_level",
            "second_level_type", "second_level",
            "discipline", "category", "number",
    ):
        expected = getattr(entry, key)
        if expected is None:
            continue
        actual = metadata.get(key)
        if key.endswith("level_type"):
            actual = _normalize_level_type(actual)
        if not _values_equal(expected, actual):
            return False
    return True


_NON_LEVEL_COORDS = {
    "latitude", "longitude", "time", "valid_time", "step", "number",
}


def metadata_from_field(field: xr.DataArray) -> Dict[str, Any]:
    """
    Build a match metadata mapping from a reki-loaded ``xarray.DataArray``.

    Uses the identity attrs reki attaches (``cemc_name``/``eccodes_name``/
    ``wgrib2_name``, ``GRIB_discipline``/``GRIB_parameterCategory``/
    ``GRIB_parameterNumber``) and the level coordinate (name is the
    ``typeOfLevel`` string, value is the level value).
    """
    metadata: Dict[str, Any] = {}
    attrs = field.attrs
    for key in ("cemc_name", "eccodes_name", "wgrib2_name"):
        value = attrs.get(key)
        if value is not None:
            metadata[key] = value
    for grib_key, key in (
            ("GRIB_discipline", "discipline"),
            ("GRIB_parameterCategory", "category"),
            ("GRIB_parameterNumber", "number"),
    ):
        value = attrs.get(grib_key)
        if value is not None:
            metadata[key] = value

    for name, coord in field.coords.items():
        if name in _NON_LEVEL_COORDS:
            continue
        metadata["first_level_type"] = name
        try:
            metadata["first_level"] = float(coord.values)
        except (TypeError, ValueError):
            pass
        break
    return metadata


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

_BUILTIN_STYLE_DIR = Path(__file__).parent / "builtin"

_ENTRY_POINT_GROUP = "cedarkit.plots.styles"


class StyleRegistry:
    """
    Load style YAML files from search paths, match data metadata to style
    ids, and build ``Style`` objects.
    """

    def __init__(self, search_paths: Sequence[Union[str, Path]]):
        self._styles: Dict[str, StyleFile] = {}
        self._paths: Dict[str, Path] = {}
        for search_path in search_paths:
            self.load_path(search_path)

    def load_path(self, search_path: Union[str, Path]) -> None:
        """Load all style YAML files in a directory (override on duplicate ids)."""
        search_path = Path(search_path)
        if not search_path.is_dir():
            return
        files = sorted(search_path.glob("*.yml")) + sorted(search_path.glob("*.yaml"))
        for file_path in files:
            style_file = load_style_file(file_path)
            self._styles[style_file.id] = style_file
            self._paths[style_file.id] = file_path

    @classmethod
    def default(cls) -> "StyleRegistry":
        """
        Built-in styles + styles from ``cedarkit.plots.styles`` entry points
        (e.g. cedar-graph, if installed) + ``CEDARKIT_STYLE_PATH`` directories.
        """
        search_paths: List[Union[str, Path]] = [_BUILTIN_STYLE_DIR]

        for entry_point in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP):
            module = entry_point.load()
            style_paths = getattr(module, "STYLE_PATHS", None)
            if style_paths is None:
                raise StyleFileError(
                    entry_point.name,
                    f"entry point module {module.__name__!r} does not define STYLE_PATHS",
                )
            search_paths.extend(style_paths)

        env_path = os.environ.get("CEDARKIT_STYLE_PATH")
        if env_path:
            search_paths.extend(env_path.split(os.pathsep))

        return cls(search_paths)

    @property
    def style_ids(self) -> List[str]:
        return sorted(self._styles)

    def match(self, metadata: Mapping[str, Any]) -> Optional[str]:
        """
        Match data metadata against style criteria; return the style id of
        the first style file with a matching entry, or ``None``.

        Styles are checked from the highest-priority search path backwards
        (``CEDARKIT_STYLE_PATH`` → entry points → built-in), so specific
        business styles win over generic built-in ones.
        """
        for style_id, style_file in reversed(list(self._styles.items())):
            for entry in style_file.criteria:
                if _entry_matches(entry, metadata):
                    return style_id
        return None

    def get_style(
            self,
            field_id: str,
            variant: Optional[str] = None,
            data: Optional[xr.DataArray] = None,
    ) -> Style:
        """
        Build the ``Style`` for ``field_id`` and ``variant`` (default:
        ``optimal``). Handles levels expression evaluation (data-driven
        ``step`` form needs ``data``), highlight expansion and colormap
        building.
        """
        style_file = self._styles.get(field_id)
        if style_file is None:
            raise KeyError(
                f"style id {field_id!r} not found; loaded ids: {self.style_ids}"
            )
        if variant is None:
            variant = style_file.optimal
            if variant is None:
                raise ValueError(
                    f"style {field_id!r} has no optimal variant; "
                    f"specify one of {sorted(style_file.styles)}"
                )
        variant_spec = style_file.styles.get(variant)
        if variant_spec is None:
            raise KeyError(
                f"style {field_id!r} has no variant {variant!r}; "
                f"available: {sorted(style_file.styles)}"
            )
        return build_style(style_file.id, variant, variant_spec, data=data)

    def get_transform(
            self,
            field_id: str,
            variant: Optional[str] = None,
    ) -> Optional[Callable]:
        """
        Return the data conversion function declared by the variant's
        ``units`` entry (built-in conversion table), or ``None``.
        """
        style_file = self._styles.get(field_id)
        if style_file is None:
            raise KeyError(
                f"style id {field_id!r} not found; loaded ids: {self.style_ids}"
            )
        if variant is None:
            variant = style_file.optimal
        variant_spec = style_file.styles.get(variant)
        if variant_spec is None:
            raise KeyError(
                f"style {field_id!r} has no variant {variant!r}; "
                f"available: {sorted(style_file.styles)}"
            )
        return get_unit_transform(variant_spec.units)


_default_registry: Optional[StyleRegistry] = None


def get_default_registry() -> StyleRegistry:
    """Process-wide default registry, created lazily by ``StyleRegistry.default()``."""
    global _default_registry
    if _default_registry is None:
        _default_registry = StyleRegistry.default()
    return _default_registry


def _representative_field(data: Any) -> xr.DataArray:
    """Find the first ``xr.DataArray`` in (possibly nested) plot data."""
    if isinstance(data, xr.DataArray):
        return data
    if isinstance(data, (list, tuple)):
        for item in data:
            try:
                return _representative_field(item)
            except TypeError:
                continue
    raise TypeError(
        f"cannot resolve a style from data of type {type(data).__name__}; "
        f"expected an xarray.DataArray (possibly nested in lists)"
    )


def resolve_style(
        style: Union[Style, str, None],
        data: Any,
        registry: Optional[StyleRegistry] = None,
) -> Style:
    """
    Resolve a style spec into a ``Style`` object.

    * ``Style`` instance — returned unchanged.
    * ``"auto"`` or ``None`` — match the data metadata against the registry
      and build the optimal variant.
    * ``"id"`` / ``"id:variant"`` — explicit style id and optional variant.
    """
    if isinstance(style, Style):
        return style
    if registry is None:
        registry = get_default_registry()
    field = _representative_field(data)
    if style is None or style == "auto":
        metadata = metadata_from_field(field)
        field_id = registry.match(metadata)
        if field_id is None:
            raise ValueError(
                f"no style matched field metadata {metadata!r}; "
                f"loaded ids: {registry.style_ids}"
            )
        return registry.get_style(field_id, data=field)
    field_id, _, variant = style.partition(":")
    return registry.get_style(field_id, variant or None, data=field)
