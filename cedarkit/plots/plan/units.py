"""Small explicit source-to-target unit conversion registry."""

from __future__ import annotations

_ALIASES = {"celsius": "degC", "C": "degC", "K": "K", "Pa": "Pa", "hPa": "hPa", "gpm": "gpm", "Gpm": "gpm", "dagpm": "dagpm", "m": "m", "mm": "mm"}
_CONVERSIONS = {("K", "degC"): (1.0, -273.15), ("Pa", "hPa"): (0.01, 0.0), ("gpm", "dagpm"): (0.1, 0.0), ("m", "mm"): (1000.0, 0.0)}


def conversion(source: str, target: str) -> tuple[float, float, str]:
    source, target = _ALIASES.get(source, source), _ALIASES.get(target, target)
    if source == target:
        return 1.0, 0.0, target
    try:
        scale, offset = _CONVERSIONS[source, target]
    except KeyError as exc:
        raise ValueError(f"unsupported unit conversion {source!r} -> {target!r}") from exc
    return scale, offset, target
