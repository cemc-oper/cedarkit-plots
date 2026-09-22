"""Profile-scoped style loading with deterministic matching and source explanations."""
import importlib.metadata
import math
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union

import numpy as np
import matplotlib
import matplotlib.colors as mcolors
import xarray as xr

from . import BarbStyle, ColorbarStyle, ContourLabelStyle, ContourStyle, LevelStep, Style
from ..colormap import generate_colormap_using_ncl_colors, get_ncl_colormap
from ..palette import get_palette
from .schema import (
    ColormapSpec,
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

    if spec.palette is not None:
        table = get_palette(spec.palette)
        return _ColorSource(colors=table, table=table)

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
        return BarbStyle(expected_units=variant.expected_units, accumulation_hours=variant.accumulation_hours, **kwargs)

    levels = (LevelStep(variant.levels.step, variant.levels.reference)
              if isinstance(variant.levels, StepLevels) else evaluate_levels(variant.levels))

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
            and not isinstance(levels, LevelStep)
            and not variant.fill
    ):
        # scalar color index on a line contour: broadcast to per-level colors
        colors = _expand_per_level_colors(source, levels, [], style_name)

    # Native palette rows describe discrete regions, including extension rows.
    # Compile them into the core's interval cmap + special-color contract.
    # Line palettes are positional: the final extra row in legacy tables is
    # unused by contour(), never interpolated across the level range.
    native = isinstance(variant.colormap, ColormapSpec) and variant.colormap.palette is not None
    if native and levels is not None and not isinstance(levels, LevelStep):
        if variant.fill and variant.extend != "neither":
            norm = mcolors.BoundaryNorm(levels, colors.N, extend=variant.extend)
            midpoints = (np.asarray(levels[:-1]) + np.asarray(levels[1:])) / 2
            compiled = mcolors.ListedColormap(colors(norm(midpoints)), name=style_name)
            compiled.set_under(colors.get_under())
            compiled.set_over(colors.get_over())
            compiled.set_bad(colors.get_bad())
            colors = compiled
        elif not variant.fill:
            colors = [tuple(colors(i % colors.N)) for i in range(len(levels))]

    if native and not variant.fill and levels is None:
        colors = list(colors.colors)

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
        expected_units=variant.expected_units,
        accumulation_hours=variant.accumulation_hours,
        colors=colors,
        levels=levels,
        linewidths=linewidths,
        linestyles=variant.linestyles,
        fill=variant.fill,
        extend=variant.extend,
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
        if isinstance(actual, bool):
            return False
        return math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-12)
    return expected == actual


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
    for key in ("cemc_name", "eccodes_name", "wgrib2_name", "units", "accumulation_hours"):
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
        if name in _NON_LEVEL_COORDS or name not in LEVEL_TYPE_NAME_TO_CODE or coord.ndim != 0:
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


class StyleMatchError(ValueError):
    """An ambiguous match or an unresolved business constraint."""

    def __init__(self, explanation: Dict[str, Any]):
        self.explanation = explanation
        details = "; ".join(
            f"{c['id']} ({c['source']}): {', '.join(c['reasons']) or c['status']}"
            for c in explanation["candidates"] if c["status"] != "mismatch"
        )
        super().__init__(f"style match {explanation['status']}: {details}")


def _profile_name(value: str) -> str:
    if not isinstance(value, str) or not value or any(c in value for c in ".:/\\") or any(c.isspace() for c in value):
        raise ValueError(f"invalid profile name: {value!r}")
    return value


class StyleRegistry:
    """Load profile roots, with separate base and user override tiers.

    A root contains ``<profile>/*.yml``. A flat directory explicitly supplied
    to the constructor belongs to the active profile (including existing
    plugin STYLE_PATHS). Paths within a tier have equal priority.
    """

    def __init__(
        self, search_paths: Sequence[Union[str, Path]] = (), *, profile: str = "cemc",
        user_paths: Sequence[Union[str, Path]] = (), generic_fallback: Sequence[str] = (),
    ):
        self.profile = _profile_name(profile)
        if isinstance(generic_fallback, str):
            raise TypeError("generic_fallback must be a sequence of generic style IDs")
        self.generic_fallback = frozenset(generic_fallback)
        if any(not isinstance(i, str) or not i or any(c in i for c in ".:") for i in self.generic_fallback):
            raise ValueError("generic_fallback contains an invalid style ID")
        self._records: Dict[tuple[str, str, bool], tuple[StyleFile, Path]] = {}
        for path in search_paths:
            self.load_path(path)
        for path in user_paths:
            self.load_path(path, user=True)

    def load_path(self, search_path: Union[str, Path], *, user: bool = False) -> None:
        """Atomically add a root; duplicate IDs in the same tier are errors."""
        root = Path(search_path)
        if not root.is_dir():
            return
        pending = dict(self._records)
        directories = [(self.profile, root)] + [
            (_profile_name(p.name), p) for p in sorted(root.iterdir()) if p.is_dir()
        ]
        for profile, directory in directories:
            for path in sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")]):
                spec = load_style_file(path)
                key = (profile, spec.id, bool(user))
                if key in pending:
                    other = pending[key][1]
                    raise StyleFileError(path, f"duplicate {profile}.{spec.id} in {'user' if user else 'base'} tier: {other} and {path}")
                pending[key] = (spec, path)
        self._records = pending

    @classmethod
    def default(
        cls, *, profile: str = "cemc", user_paths: Sequence[Union[str, Path]] = (),
        generic_fallback: Sequence[str] = (),
    ) -> "StyleRegistry":
        paths = [_BUILTIN_STYLE_DIR]
        for ep in sorted(importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP), key=lambda e: (e.name, e.value)):
            module = ep.load()
            style_paths = getattr(module, "STYLE_PATHS", None)
            if style_paths is None:
                raise StyleFileError(ep.name, f"entry point module {module.__name__!r} does not define STYLE_PATHS")
            # Existing graph flat STYLE_PATHS are CEMC, independently of the
            # caller's selected profile. Load them below with that scope.
            paths.extend(style_paths)
        registry = cls(profile="cemc", generic_fallback=generic_fallback)
        for path in paths:
            registry.load_path(path)
        registry.profile = _profile_name(profile)
        env = os.environ.get("CEDARKIT_STYLE_PATH", "")
        for path in [*(p for p in env.split(os.pathsep) if p), *user_paths]:
            registry.load_path(path, user=True)
        return registry

    @property
    def style_ids(self) -> List[str]:
        """IDs in the active profile; qualified references can access others."""
        return sorted({i for p, i, user in self._records if p == self.profile})

    def _lookup(self, reference: str, variant: Optional[str] = None):
        field_id, colon, inline_variant = reference.partition(":")
        if colon:
            if not inline_variant or ":" in inline_variant or (variant is not None and variant != inline_variant):
                raise ValueError(f"invalid or conflicting style variant: {reference!r}, {variant!r}")
            variant = inline_variant
        if "." in field_id:
            profile, field_id = field_id.split(".", 1)
        else:
            profile = self.profile
        _profile_name(profile)
        for user in (True, False):
            record = self._records.get((profile, field_id, user))
            if record is not None:
                spec, path = record
                break
        else:
            raise KeyError(f"style id {profile}.{field_id!s} not found; loaded ids: {self.style_ids}")
        variant = variant if variant is not None else spec.optimal
        if variant is None:
            raise ValueError(f"style {profile}.{field_id!s} has no optimal variant; specify one of {sorted(spec.styles)}")
        if variant not in spec.styles:
            raise KeyError(f"style {profile}.{field_id!s} has no variant {variant!r}; available: {sorted(spec.styles)}; source: {path}")
        return profile, spec, variant, spec.styles[variant], path

    @staticmethod
    def _constraints(variant: StyleVariant, metadata: Mapping[str, Any]) -> List[str]:
        reasons = []
        for key, expected in (("units", variant.expected_units), ("accumulation_hours", variant.accumulation_hours)):
            if expected is not None and not _values_equal(expected, metadata.get(key)):
                reasons.append(f"{key}: expected {expected!r}, got {metadata.get(key)!r}")
        return reasons

    def explain(self, metadata: Mapping[str, Any]) -> Dict[str, Any]:
        """Return selection, scores, sources and rejection reasons; never build."""
        if not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        candidates = []
        scopes = [(self.profile, True), (self.profile, False)]
        if self.profile != "generic" and self.generic_fallback:
            scopes += [("generic", True), ("generic", False)]
        selected = None
        status = "no_match"
        for profile, user in scopes:
            tier_candidates = []
            for (p, field_id, u), (spec, path) in sorted(self._records.items()):
                if (p, u) != (profile, user):
                    continue
                if profile != self.profile and field_id not in self.generic_fallback:
                    continue
                if not user and (p, field_id, True) in self._records:
                    candidates.append(dict(id=f"{p}.{field_id}", source=str(path), tier="base",
                                           specificity=0, status="shadowed", reasons=["replaced by user profile file"]))
                    continue
                entries = []
                for entry in spec.criteria:
                    conditions = entry.model_dump(exclude_none=True)
                    missing, mismatches = [], []
                    for key, expected in conditions.items():
                        actual = metadata.get(key)
                        if key.endswith("level_type"):
                            actual = _normalize_level_type(actual)
                        if actual is None:
                            missing.append(key)
                        elif not _values_equal(expected, actual):
                            mismatches.append(key)
                    # Missing identity is not evidence that this business style
                    # applies; missing level information after identity is.
                    identity = set(conditions) & {"cemc_name", "eccodes_name", "wgrib2_name", "discipline", "category", "number"}
                    relevant = bool(identity) and not (identity & set(missing))
                    state = "mismatch" if mismatches or (missing and not relevant) else "blocked" if missing else "matched"
                    entries.append((state, len(conditions), missing, mismatches, conditions))
                matches = [e for e in entries if e[0] == "matched"]
                partial = [e for e in entries if e[0] == "blocked"]
                state, score, missing, mismatches, conditions = max(matches or partial or entries, key=lambda e: e[1])
                reasons = [f"missing metadata: {', '.join(missing)}"] if missing else []
                if mismatches:
                    reasons.append(f"criteria mismatch: {', '.join(mismatches)}")
                variant = spec.styles.get(spec.optimal)
                if variant is not None:
                    score += int(variant.expected_units is not None) + int(variant.accumulation_hours is not None)
                if state == "matched":
                    if variant is None:
                        state, reasons = "blocked", ["no optimal variant; select an explicit variant"]
                    else:
                        constraints = self._constraints(variant, metadata)
                        if constraints:
                            state, reasons = "blocked", constraints
                row = dict(id=f"{p}.{field_id}" + (f":{spec.optimal}" if spec.optimal else ""),
                           source=str(path), tier="user" if user else "base", specificity=score,
                           status=state, reasons=reasons, criteria=conditions,
                           constraints={"units": variant.expected_units, "accumulation_hours": variant.accumulation_hours}
                           if variant is not None else {})
                candidates.append(row)
                if state != "mismatch":
                    tier_candidates.append(row)
            if selected is not None or status in {"blocked", "conflict"}:
                continue
            if tier_candidates:
                best = max(c["specificity"] for c in tier_candidates)
                winners = [c for c in tier_candidates if c["specificity"] == best]
                if any(c["status"] == "blocked" for c in winners):
                    status = "blocked"
                elif len(winners) > 1:
                    status = "conflict"
                else:
                    status, selected = "selected", winners[0]["id"]
        return {"profile": self.profile, "generic_fallback": sorted(self.generic_fallback),
                "status": status, "selected": selected, "candidates": candidates}

    def match(self, metadata: Mapping[str, Any]) -> Optional[str]:
        result = self.explain(metadata)
        if result["status"] in {"blocked", "conflict"}:
            raise StyleMatchError(result)
        selected = result["selected"]
        if selected is None:
            return None
        field_id = selected.split(":", 1)[0]
        return field_id.removeprefix(self.profile + ".")

    def get_style(
        self, field_id: str, variant: Optional[str] = None, data: Optional[xr.DataArray] = None,
        *, metadata: Optional[Mapping[str, Any]] = None, overrides: Optional[Mapping[str, Any]] = None,
    ) -> Style:
        profile, spec, variant_name, variant_spec, path = self._lookup(field_id, variant)
        if overrides:
            variant_spec = StyleVariant.model_validate({**variant_spec.model_dump(), **overrides})
        if data is not None:
            if metadata is not None:
                raise ValueError("pass metadata or data, not both")
            metadata = metadata_from_field(data)
        # A constructed unit contract can be validated later by Chart. A
        # duration constraint must be satisfied here before selecting a style.
        if metadata is not None or variant_spec.accumulation_hours is not None:
            reasons = self._constraints(variant_spec, metadata or {})
            if reasons:
                raise ValueError(f"style {profile}.{spec.id}:{variant_name} ({path}): {'; '.join(reasons)}")
        return build_style(f"{profile}.{spec.id}", variant_name, variant_spec)

    def get_transform(self, field_id: str, variant: Optional[str] = None) -> Optional[Callable]:
        """Existing workflow conversion hook; removed with D13's old engine."""
        _, _, _, variant_spec, _ = self._lookup(field_id, variant)
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
        *,
        overrides: Optional[Mapping[str, Any]] = None,
) -> Style:
    """
    Resolve a style spec into a ``Style`` object.

    * ``Style`` instance — returned unchanged.
    * ``"auto"`` or ``None`` — match the data metadata against the registry
      and build the optimal variant.
    * ``"id"`` / ``"id:variant"`` — explicit style id and optional variant.
    """
    if isinstance(style, Style):
        if overrides:
            raise ValueError("configure explicit Style objects directly; overrides apply to registry variants")
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
        return registry.get_style(field_id, data=field, overrides=overrides)
    return registry.get_style(style, data=field, overrides=overrides)
