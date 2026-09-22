"""Explicit data preparation shared by quick plotting and workflow execution.

No styles, providers or plotting objects are consulted. The supported unit
vocabulary is deliberately finite; unknown units never imply an identity map.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

import xarray as xr

TemperatureKind = Literal['absolute', 'difference']

# Canonical name -> (dimension, scale to base, absolute offset to base).
_UNITS = {
    'K': ('temperature', 1., 0.),
    'degC': ('temperature', 1., 273.15),
    'degF': ('temperature', 5 / 9, 255.3722222222222),
    'Pa': ('pressure', 1., 0.), 'hPa': ('pressure', 100., 0.),
    'm': ('length', 1., 0.), 'mm': ('length', .001, 0.),
    'gpm': ('geopotential_height', 1., 0.), 'dagpm': ('geopotential_height', 10., 0.),
    'm/s': ('speed', 1., 0.), 'km/h': ('speed', 1 / 3.6, 0.),
    'knots': ('speed', 1852 / 3600, 0.),
    '1': ('ratio', 1., 0.), '%': ('ratio', .01, 0.),
    'J/kg': ('specific_energy', 1., 0.), 'dBZ': ('reflectivity', 1., 0.),
    's^-1': ('divergence', 1., 0.), '10^-5 s^-1': ('divergence', 1e-5, 0.),
    'g/(hPa cm^2 s)': ('moisture_divergence', 1., 0.),
    '10^-7 g/(hPa cm^2 s)': ('moisture_divergence', 1e-7, 0.),
}
_ALIASES = {
    'kelvin': 'K', 'celsius': 'degC', 'C': 'degC', '°C': 'degC',
    'degree_Celsius': 'degC', 'degrees_Celsius': 'degC',
    'fahrenheit': 'degF', '°F': 'degF', 'Gpm': 'gpm',
    'm s-1': 'm/s', 'm s^-1': 'm/s', 'm s**-1': 'm/s',
    'km h-1': 'km/h', 'kt': 'knots', 'knot': 'knots',
    'percent': '%', 'J kg-1': 'J/kg', 'J kg^-1': 'J/kg',
    'dbz': 'dBZ', 's-1': 's^-1', 's**-1': 's^-1',
}


def canonical_unit(unit: str) -> str:
    """Normalize a supported unit spelling; do not convert a value."""
    if not isinstance(unit, str) or not unit.strip():
        raise ValueError(f'unit must be a non-empty string, got {unit!r}')
    result = _ALIASES.get(unit.strip(), unit.strip())
    if result not in _UNITS:
        raise ValueError(f'unknown unit {unit!r}')
    return result


def unit_dimension(unit: str) -> str:
    """Return the physical dimension of a supported unit."""
    return _UNITS[canonical_unit(unit)][0]


def validate_temperature_kind(kind: TemperatureKind | None, unit: str | None = None) -> None:
    if kind is not None and kind not in ('absolute', 'difference'):
        raise ValueError(f'unknown temperature_kind {kind!r}')
    if kind is not None and unit is not None and _UNITS[canonical_unit(unit)][0] != 'temperature':
        raise ValueError('temperature_kind requires a temperature unit')


@dataclass(frozen=True)
class UnitConversion:
    source_units: str
    target_units: str
    scale: float
    offset: float
    temperature_kind: TemperatureKind | None
    source_from: Literal['metadata', 'explicit'] = 'metadata'

    @property
    def applied(self) -> bool:
        return (self.scale, self.offset) != (1., 0.)


@dataclass(frozen=True)
class PreparedField:
    field: xr.DataArray
    conversion: UnitConversion


@dataclass(frozen=True)
class PreparedVector:
    u: xr.DataArray
    v: xr.DataArray
    conversions: tuple[UnitConversion, UnitConversion]


def conversion_rule(source_units: str, units: str, *, temperature_kind: TemperatureKind | None = None,
                    source_from: Literal['metadata', 'explicit'] = 'metadata') -> UnitConversion:
    """Resolve an affine conversion without reading a field or array.

    Temperature conversions require an explicit absolute/difference semantic,
    even for identity conversions. Differences never receive an absolute zero-point offset.
    """
    if source_from not in ("metadata", "explicit"):
        raise ValueError("source_from must be metadata or explicit")
    source, target = canonical_unit(source_units), canonical_unit(units)
    dimension, source_scale, source_offset = _UNITS[source]
    target_dimension, target_scale, target_offset = _UNITS[target]
    if dimension != target_dimension:
        raise ValueError(f'incompatible units {source!r} -> {target!r}')
    validate_temperature_kind(temperature_kind, source)
    if dimension == 'temperature' and temperature_kind is None:
        raise ValueError('temperature_kind must explicitly be absolute or difference')
    scale = source_scale / target_scale
    offset = (source_offset - target_offset) / target_scale
    if temperature_kind == 'difference':
        offset = 0.
    return UnitConversion(source, target, scale, offset, temperature_kind, source_from)


def prepare_field(field: xr.DataArray, *, units: str | None = None,
                  source_units: str | None = None,
                  temperature_kind: TemperatureKind | None = None) -> PreparedField:
    """Validate and copy a field, optionally converting to explicit ``units``.

    ``source_units`` supplies missing metadata, never overrides contradictory
    metadata. Temperature semantics come from an explicit argument or the
    field's ``temperature_kind`` attribute, never from a style or field name.
    The result owns its values and attributes; the input is not modified.
    """
    if not isinstance(field, xr.DataArray):
        raise TypeError('prepare_field requires an xarray.DataArray')
    declared = field.attrs.get('units')
    if declared is None and source_units is None:
        raise ValueError('source units are missing; supply source_units explicitly')
    source = canonical_unit(declared if declared is not None else source_units)
    if source_units is not None and canonical_unit(source_units) != source:
        raise ValueError(f'source_units {source_units!r} contradicts metadata units {declared!r}')
    declared_kind = field.attrs.get('temperature_kind')
    if declared_kind is not None:
        validate_temperature_kind(declared_kind, source)
    if temperature_kind is not None and declared_kind is not None and temperature_kind != declared_kind:
        raise ValueError('temperature_kind contradicts field metadata')
    kind = temperature_kind if temperature_kind is not None else declared_kind
    rule = conversion_rule(source, units if units is not None else source, temperature_kind=kind,
                           source_from='metadata' if declared is not None else 'explicit')
    result = field.copy(deep=True)
    if rule.applied:
        result = result * rule.scale + rule.offset
    result.attrs = deepcopy(field.attrs)
    result.attrs['units'] = rule.target_units
    if kind is not None:
        result.attrs['temperature_kind'] = kind
    return PreparedField(result, rule)


def prepare_vector(u: xr.DataArray, v: xr.DataArray, *, units: str | None = None,
                   source_units: tuple[str | None, str | None] | None = None) -> PreparedVector:
    """Prepare two aligned speed components independently, without mutation.

    Without a target, both components must already declare equivalent units.
    Missing units must be supplied separately for each component.
    """
    if not isinstance(u, xr.DataArray) or not isinstance(v, xr.DataArray):
        raise TypeError('prepare_vector requires two xarray.DataArray components')
    if u.dims != v.dims or u.shape != v.shape or not u.coords.equals(v.coords):
        raise ValueError('vector components must have matching dimensions and coordinates')
    if source_units is not None and (not isinstance(source_units, tuple) or len(source_units) != 2):
        raise ValueError('source_units must be a (u_units, v_units) tuple')
    sources = source_units if source_units is not None else (None, None)
    first = prepare_field(u, units=units, source_units=sources[0])
    second = prepare_field(v, units=units, source_units=sources[1])
    if any(_UNITS[item.conversion.source_units][0] != 'speed' for item in (first, second)):
        raise ValueError('vector components require speed units')
    if first.conversion.target_units != second.conversion.target_units:
        raise ValueError('vector units differ; supply an explicit target units')
    return PreparedVector(first.field, second.field, (first.conversion, second.conversion))
