from dataclasses import dataclass
from typing import Union, Optional, List, Dict, Callable, Any

import numpy as np
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker


def _validate_accumulation_hours(value):
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not np.isfinite(value) or value <= 0
    ):
        raise ValueError("accumulation_hours must be finite and positive")


@dataclass
class Style:
    def validate(self):
        """子类重写以实现具体验证逻辑。"""
        pass


@dataclass(frozen=True)
class LevelStep:
    """A reference-aligned, data-driven contour level rule."""

    step: float
    reference: float = 0.0

    def __post_init__(self):
        if isinstance(self.step, bool) or not isinstance(self.step, (int, float)):
            raise TypeError("LevelStep.step must be a finite positive number")
        if not np.isfinite(float(self.step)) or self.step <= 0:
            raise ValueError("LevelStep.step must be a finite positive number")
        if isinstance(self.reference, bool) or not isinstance(self.reference, (int, float)):
            raise TypeError("LevelStep.reference must be finite")
        if not np.isfinite(float(self.reference)):
            raise ValueError("LevelStep.reference must be finite")
        object.__setattr__(self, "step", float(self.step))
        object.__setattr__(self, "reference", float(self.reference))


@dataclass
class ColorbarStyle(Style):
    loc: Optional[str] = None
    label: Optional[str] = None
    label_levels: Optional[Union[List, np.ndarray]] = None


@dataclass
class ContourLabelStyle(Style):
    levels: Optional[Union[List, np.ndarray]] = None
    fontsize: Optional[Union[str, float]] = None
    inline: bool = True
    inline_spacing: float = 5
    fmt: Optional[Union[mticker.Formatter, str, Callable]] = None
    colors: Optional[Any] = None
    background_color: Optional[Any] = None
    manual: bool = False
    zorder: Optional[float] = None


@dataclass
class ContourStyle(Style):
    colors: Optional[Union[str, List, mcolors.ListedColormap]] = None
    levels: Optional[Union[List, np.ndarray, LevelStep]] = None
    linewidths: Optional[Union[List, np.ndarray, float]] = None
    linestyles: Optional[Union[List, str]] = None
    fill: bool = False
    label: bool = False
    label_style: Optional[ContourLabelStyle] = None
    colorbar_style: Optional[ColorbarStyle] = None
    norm: str = "boundary"
    extend: str = "neither"
    expected_units: Optional[str] = None
    accumulation_hours: Optional[float] = None

    def __post_init__(self):
        self.validate()

    def validate(self):
        _validate_accumulation_hours(self.accumulation_hours)
        if self.levels is not None and not isinstance(self.levels, LevelStep):
            levels = np.asarray(self.levels)
            if levels.ndim == 1 and len(levels) > 1:
                if not np.all(np.diff(levels) > 0):
                    raise ValueError(
                        f"ContourStyle.levels must be monotonically increasing, "
                        f"got: {self.levels}"
                    )
        if self.norm not in {"boundary", "linear", "log"}:
            raise ValueError("ContourStyle.norm must be boundary, linear or log")
        if self.extend not in {"neither", "min", "max", "both"}:
            raise ValueError("ContourStyle.extend must be neither, min, max or both")
        if self.expected_units is not None and not isinstance(self.expected_units, str):
            raise TypeError("ContourStyle.expected_units must be a string or None")


@dataclass
class BarbStyle(Style):
    length: float = 4
    linewidth: float = 0.5
    pivot: str = "middle"
    barbcolor: str = "red"
    flagcolor: Optional[str] = "red"
    barb_increments: Optional[Dict] = None
    colorbar_style: Optional[ContourLabelStyle] = None
    expected_units: Optional[str] = None
    accumulation_hours: Optional[float] = None

    def __post_init__(self):
        if self.barb_increments is None:
            self.barb_increments = dict(half=2, full=4, flag=20)
        self.validate()

    def validate(self):
        _validate_accumulation_hours(self.accumulation_hours)
        if self.barb_increments is not None:
            required_keys = {"half", "full", "flag"}
            missing = required_keys - set(self.barb_increments.keys())
            if missing:
                raise ValueError(
                    f"BarbStyle.barb_increments must contain keys {required_keys}, "
                    f"missing: {missing}"
                )
        if self.expected_units is not None and not isinstance(self.expected_units, str):
            raise TypeError("BarbStyle.expected_units must be a string or None")


from .registry import (  # noqa: E402
    StyleRegistry,
    StyleMatchError,
    build_style,
    evaluate_levels,
    get_default_registry,
    get_rgb_table,
    metadata_from_field,
    register_rgb_table,
    resolve_style,
)
from .schema import StyleFile, StyleFileError, load_style_file  # noqa: E402
from .units import get_unit_transform  # noqa: E402
