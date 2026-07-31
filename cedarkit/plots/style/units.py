"""Built-in unit conversion table for the style library.

The table is intentionally small and explicit; no pint integration.
A style YAML ``units`` entry declares the *target* unit of the plot;
the engine assumes the data arrives in the listed source unit and
applies the conversion. Units metadata carried by the data itself is
not consulted.
"""
from typing import Callable, Optional, Tuple, Dict


# target units -> (assumed source unit, conversion function)
UNIT_TRANSFORMS: Dict[str, Tuple[str, Callable]] = {
    "celsius": ("K", lambda x: x - 273.15),
    "hPa": ("Pa", lambda x: x / 100),
    "dagpm": ("gpm", lambda x: x / 10),
    "mm": ("m", lambda x: x * 1000),
}


def get_unit_transform(units: Optional[str]) -> Optional[Callable]:
    """
    Return the data conversion function for a declared target unit.

    Parameters
    ----------
    units
        units string declared in a style YAML. ``None`` means no conversion.

    Returns
    -------
    Optional[Callable]
        conversion function, or ``None`` when no conversion is declared.

    Raises
    ------
    ValueError
        if ``units`` is not in the built-in conversion table.
    """
    if units is None:
        return None
    if units not in UNIT_TRANSFORMS:
        known = ", ".join(sorted(UNIT_TRANSFORMS))
        raise ValueError(f"unknown style units: {units!r}; known units: {known}")
    return UNIT_TRANSFORMS[units][1]
