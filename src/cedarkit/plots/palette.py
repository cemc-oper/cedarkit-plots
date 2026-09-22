"""Native, discrete palettes. Runtime reads JSON only; conversion is offline."""
from copy import deepcopy
from functools import lru_cache
from importlib import resources
import json
from numbers import Integral
from typing import Any

import matplotlib.colors as mcolors
import numpy as np


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    path = resources.files("cedarkit.plots").joinpath("resources/palettes/catalog.json")
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 1:
        raise ValueError("unsupported native palette catalog schema")
    for name, spec in catalog["palettes"].items():
        if spec["interpolation"] != "listed" or not spec["colors"]:
            raise ValueError(f"palette {name!r} must contain discrete colors")
        for color in [*spec["colors"], spec["under"], spec["over"], spec["bad"]]:
            if not isinstance(color, str) or len(color) != 9 or not color.startswith("#"):
                raise ValueError(f"palette {name!r} requires #RRGGBBAA values")
            mcolors.to_rgba(color)
    return catalog


def palette_names() -> tuple[str, ...]:
    """Return sorted, exact (case-sensitive) native palette IDs."""
    return tuple(sorted(_catalog()["palettes"]))


def get_palette_info(name: str) -> dict[str, Any]:
    """Return independent colors, special colors, derivation and provenance."""
    try:
        spec = _catalog()["palettes"][name]
    except KeyError:
        raise KeyError(f"unknown native palette {name!r}") from None
    result = deepcopy(spec)
    result["provenance"] = {
        key: deepcopy(_catalog()["provenance"][key]) for key in spec["sources"]
    }
    return result


def get_named_color(name: str) -> tuple[float, float, float, float]:
    """Resolve a verified color name case-insensitively, including transparent."""
    if not isinstance(name, str):
        raise TypeError("color name must be a string")
    try:
        color = _catalog()["named_colors"][name.lower()]
    except KeyError:
        raise KeyError(f"unknown native color name {name!r}") from None
    return mcolors.to_rgba(color)


def _integer(value: Any, label: str, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{label} must be an integer")
    value = int(value)
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{label} is outside [{minimum}, {maximum if maximum is not None else 'infinity'}]")
    return value


def get_palette(
    name: str, *, count: int | None = None, start: int | None = None, end: int | None = None,
) -> mcolors.ListedColormap:
    """Create an independent discrete colormap from a native palette.

    Optional count samples inclusive zero-based start/end indices using
    nearest-even rounding. Reversal and repeated indices are supported;
    count=1 selects start. Special colors retain the palette's declarations.
    This function never interpolates, reads NCL resources or imports graph.
    """
    spec = get_palette_info(name)
    colors = spec["colors"]
    if count is None:
        if start is not None or end is not None:
            raise ValueError("start/end require count")
    else:
        count = _integer(count, "count", 1)
        start = 0 if start is None else _integer(start, "start", 0, len(colors) - 1)
        end = len(colors) - 1 if end is None else _integer(end, "end", 0, len(colors) - 1)
        indices = np.rint(np.linspace(start, end, count)).astype(int)
        colors = [colors[index] for index in indices]
    cmap = mcolors.ListedColormap([mcolors.to_rgba(c) for c in colors], name=name)
    cmap.set_under(spec["under"])
    cmap.set_over(spec["over"])
    cmap.set_bad(spec["bad"])
    return cmap
