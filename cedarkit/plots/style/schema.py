"""pydantic models for style YAML files (G2 style library).

A style YAML file describes one field (element), including:

* ``id`` — style id, aligned with the cemc element name (``t2m``, ``psl``...)
  or ``cemc_name + "_" + level value`` for element+level styles (``h_500``).
* ``criteria`` — identity rules used to match data metadata. A list of
  entries: entries are OR-ed, keys within one entry are AND-ed. Keys use the
  same vocabulary as reki's ``param_registry.yaml``; ``first_level_type`` is
  the GRIB2 numeric level type code (code table 4.5), not a string alias.
* ``optimal`` — default variant id.
* ``styles`` — named style variants mapping to ``ContourStyle``/``BarbStyle``.
"""
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .units import UNIT_TRANSFORMS


# GRIB2 code table 4.5: fixed surface type code -> ecCodes typeOfLevel name.
# Only common codes are listed; unknown codes still match numerically.
LEVEL_TYPE_CODE_TO_NAME: Dict[int, str] = {
    1: "surface",
    2: "cloudBase",
    3: "cloudTop",
    4: "zeroDegLevel",
    6: "maxWind",
    7: "tropopause",
    8: "nominalTop",
    9: "seaBottom",
    10: "entireAtmosphere",
    100: "isobaricInhPa",
    101: "meanSea",
    102: "heightAboveSea",
    103: "heightAboveGround",
    104: "sigma",
    105: "hybrid",
    106: "depthBelowLandLayer",
    107: "theta",
    108: "pressureDifference",
    109: "potentialVorticity",
    111: "eta",
    113: "logHybrid",
    115: "sigmaHeight",
    117: "mixedLayerDepth",
    118: "hybridHeight",
    119: "hybridPressure",
    160: "depthBelowSea",
}

LEVEL_TYPE_NAME_TO_CODE: Dict[str, int] = {
    name: code for code, name in LEVEL_TYPE_CODE_TO_NAME.items()
}
# reki shorthand alias for pressure levels.
LEVEL_TYPE_NAME_TO_CODE["pl"] = 100


class StyleFileError(ValueError):
    """Raised when a style YAML file fails to load or validate."""

    def __init__(self, path: Union[str, Path], message: str):
        self.path = Path(path)
        super().__init__(f"{self.path}: {message}")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CriteriaEntry(StrictModel):
    """One identity entry; all set keys must match (AND)."""

    cemc_name: Optional[str] = None
    eccodes_name: Optional[str] = None
    wgrib2_name: Optional[str] = None
    first_level_type: Optional[int] = None
    first_level: Optional[float] = None
    second_level_type: Optional[int] = None
    second_level: Optional[float] = None
    discipline: Optional[int] = None
    category: Optional[int] = None
    number: Optional[int] = None

    @model_validator(mode="after")
    def at_least_one_key(self) -> "CriteriaEntry":
        if all(
            getattr(self, key) is None
            for key in (
                "cemc_name", "eccodes_name", "wgrib2_name",
                "first_level_type", "first_level",
                "second_level_type", "second_level",
                "discipline", "category", "number",
            )
        ):
            raise ValueError("criteria entry must set at least one key")
        return self


class RangeLevels(StrictModel):
    """``np.arange(start, stop, step)``."""
    range: List[Union[int, float]] = Field(min_length=3, max_length=3)


class LinspaceLevels(StrictModel):
    """``np.linspace(start, stop, num)``."""
    linspace: List[Union[int, float]] = Field(min_length=3, max_length=3)


class StepLevels(StrictModel):
    """Levels generated from the data range at ``step`` intervals aligned to ``reference``."""
    step: float = Field(gt=0)
    reference: float = 0.0


# keep ints as ints (pydantic smart union): integer level lists render
# integer tick labels like the original hardcoded styles.
LevelsSpec = Union[List[Union[int, float]], RangeLevels, LinspaceLevels, StepLevels]


class ColormapSpec(StrictModel):
    """
    Colormap source. Exactly one of ``ncl`` / ``rgb_table`` / ``colors`` /
    ``ncl_colors`` must be set. A plain matplotlib colormap name is written
    as a bare string instead of this mapping.
    """

    ncl: Optional[str] = None
    rgb_table: Optional[str] = None
    colors: Optional[List[Any]] = None
    ncl_colors: Optional[List[str]] = None

    index: Optional[Union[int, List[int]]] = None
    index_offset: int = 0
    count: Optional[int] = None
    spread_start: Optional[int] = None
    spread_end: Optional[int] = None

    @model_validator(mode="after")
    def exactly_one_source(self) -> "ColormapSpec":
        sources = [
            name
            for name in ("ncl", "rgb_table", "colors", "ncl_colors")
            if getattr(self, name) is not None
        ]
        if len(sources) != 1:
            raise ValueError(
                f"colormap must set exactly one source "
                f"(ncl/rgb_table/colors/ncl_colors), got: {sources}"
            )
        if self.colors is not None or self.ncl_colors is not None:
            for key in ("index", "index_offset", "count", "spread_start", "spread_end"):
                value = getattr(self, key)
                if key == "index_offset":
                    if value != 0:
                        raise ValueError(f"colormap.{key} is only valid with ncl/rgb_table")
                elif value is not None:
                    raise ValueError(f"colormap.{key} is only valid with ncl/rgb_table")
        if self.rgb_table is not None:
            for key in ("count", "spread_start", "spread_end"):
                if getattr(self, key) is not None:
                    raise ValueError(f"colormap.{key} is only valid with ncl")
        return self


class HighlightEntry(StrictModel):
    """Feature level rule, expanded to per-level linewidths/colors."""

    level: float
    linewidth: Optional[float] = None
    color: Optional[Any] = None
    color_index: Optional[int] = None

    @model_validator(mode="after")
    def has_effect(self) -> "HighlightEntry":
        if self.linewidth is None and self.color is None and self.color_index is None:
            raise ValueError("highlight entry must set linewidth, color or color_index")
        if self.color is not None and self.color_index is not None:
            raise ValueError("highlight entry cannot set both color and color_index")
        return self


class LabelSpec(StrictModel):
    """Contour label settings; presence enables labelling."""

    inline: bool = True
    inline_spacing: float = 5
    fontsize: Optional[Union[str, float]] = None
    fmt: Optional[str] = None
    color: Optional[Any] = None
    color_index: Optional[Union[int, List[int]]] = None
    line_colors: bool = False
    background_color: Optional[Any] = None
    manual: bool = False
    zorder: Optional[float] = None

    @model_validator(mode="after")
    def color_exclusive(self) -> "LabelSpec":
        used = [
            self.color is not None,
            self.color_index is not None,
            self.line_colors,
        ]
        if sum(used) > 1:
            raise ValueError("label can set only one of color / color_index / line_colors")
        return self


class ColorbarSpec(StrictModel):
    loc: Optional[str] = None
    label: Optional[str] = None
    label_levels: Optional[List[float]] = None


class StyleVariant(StrictModel):
    """One named style variant, built into ``ContourStyle`` or ``BarbStyle``."""

    type: Literal["contour", "barb"]

    # contour (linewidth is shared with barb)
    colormap: Optional[Union[str, ColormapSpec]] = None
    levels: Optional[LevelsSpec] = None
    linewidth: Optional[float] = None
    linestyles: Optional[str] = None
    fill: bool = False
    label: Optional[LabelSpec] = None
    highlight: Optional[Union[HighlightEntry, List[HighlightEntry]]] = None
    colorbar: Optional[ColorbarSpec] = None

    # barb
    length: Optional[float] = None
    pivot: Optional[str] = None
    barbcolor: Optional[str] = None
    flagcolor: Optional[str] = None
    barb_increments: Optional[Dict[str, float]] = None

    # unit conversion applied to the data (built-in table in style/units.py)
    units: Optional[str] = None
    # v2 data values are already converted; styles only state their contract.
    expected_units: Optional[str] = None

    @field_validator("units")
    @classmethod
    def known_units(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in UNIT_TRANSFORMS:
            known = ", ".join(sorted(UNIT_TRANSFORMS))
            raise ValueError(f"unknown units {value!r}; known units: {known}")
        return value

    @model_validator(mode="after")
    def check_type_fields(self) -> "StyleVariant":
        contour_keys = ("colormap", "levels", "linestyles", "label", "highlight", "colorbar")
        barb_keys = ("length", "pivot", "barbcolor", "flagcolor", "barb_increments")
        if self.type == "barb":
            used = [k for k in contour_keys if getattr(self, k) is not None]
            if self.fill or used:
                raise ValueError(f"barb variant cannot set contour keys: {used + (['fill'] if self.fill else [])}")
        else:
            used = [k for k in barb_keys if getattr(self, k) is not None]
            if used:
                raise ValueError(f"contour variant cannot set barb keys: {used}")
        return self


class StyleFile(StrictModel):
    """Root model of a style YAML file."""

    id: str
    criteria: List[CriteriaEntry] = Field(min_length=1)
    optimal: Optional[str] = None
    styles: Dict[str, StyleVariant] = Field(min_length=1)

    @model_validator(mode="after")
    def optimal_in_styles(self) -> "StyleFile":
        if self.optimal is not None and self.optimal not in self.styles:
            raise ValueError(
                f"optimal variant {self.optimal!r} is not defined in styles "
                f"({sorted(self.styles)})"
            )
        return self


def load_style_file(path: Union[str, Path]) -> StyleFile:
    """
    Load and validate a style YAML file.

    Raises
    ------
    StyleFileError
        on YAML syntax errors (with line/column) or schema violations.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise StyleFileError(path, f"cannot read file: {e}") from e

    try:
        raw = yaml.safe_load(text)
    except yaml.MarkedYAMLError as e:
        mark = e.problem_mark
        location = f"line {mark.line + 1}, column {mark.column + 1}" if mark else "unknown position"
        raise StyleFileError(path, f"invalid YAML at {location}: {e.problem}") from e
    except yaml.YAMLError as e:
        raise StyleFileError(path, f"invalid YAML: {e}") from e

    if not isinstance(raw, dict):
        raise StyleFileError(path, "style file must be a YAML mapping")

    try:
        style_file = StyleFile.model_validate(raw)
    except ValueError as e:
        raise StyleFileError(path, f"schema validation failed:\n{e}") from e

    if style_file.id != path.stem:
        raise StyleFileError(
            path,
            f"style id {style_file.id!r} does not match file name {path.stem!r}",
        )
    return style_file
