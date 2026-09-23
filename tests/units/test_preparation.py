"""D12-05 value preparation, metadata contracts and no implicit conversion."""
from dataclasses import FrozenInstanceError, asdict

import numpy as np
import pytest
import xarray as xr

from cedarkit.plots import Panel
from cedarkit.plots.errors import ContentError
from cedarkit.plots.style import BarbStyle, ContourStyle, StyleRegistry
from cedarkit.plots.units import canonical_unit, conversion_rule, prepare_field, prepare_vector


def field(values=(0., 1., 2., 3.), units='K', **attrs):
    if units is not None:
        attrs['units'] = units
    return xr.DataArray(np.array(values).reshape(2, 2), dims=('y', 'x'),
                        coords={'y': [0, 1], 'x': [0, 1]}, name='sample', attrs=attrs)


@pytest.mark.parametrize('source,target,kind,values,expected', [
    ('K', 'degC', 'absolute', [273.15, 274.15, 300, np.nan], [0, 1, 26.85, np.nan]),
    ('K', 'degC', 'difference', [0, 1, -10, np.nan], [0, 1, -10, np.nan]),
    ('degC', 'K', 'absolute', [0, 1, -10, 100], [273.15, 274.15, 263.15, 373.15]),
    ('degC', 'K', 'difference', [0, 1, -10, 100], [0, 1, -10, 100]),
    ('degF', 'degC', 'absolute', [32, 212, -40, 50], [0, 100, -40, 10]),
    ('degF', 'K', 'difference', [0, 18, -18, 180], [0, 10, -10, 100]),
    ('Pa', 'hPa', None, [100000, 101000, 0, np.nan], [1000, 1010, 0, np.nan]),
    ('hPa', 'Pa', None, [1000, 1010, 0, np.nan], [100000, 101000, 0, np.nan]),
    ('m', 'mm', None, [.001, .01, 0, np.nan], [1, 10, 0, np.nan]),
    ('gpm', 'dagpm', None, [5000, 5880, 0, 6000], [500, 588, 0, 600]),
    ('km/h', 'm/s', None, [36, 72, -36, 0], [10, 20, -10, 0]),
    ('knots', 'm/s', None, [1, 10, -1, 0], [1852/3600, 1852/360, -1852/3600, 0]),
    ('1', '%', None, [0, .5, 1, .7], [0, 50, 100, 70]),
    ('s^-1', '10^-5 s^-1', None, [0, -1e-5, 2e-5, 5e-5], [0, -1, 2, 5]),
    ('g/(hPa cm^2 s)', '10^-7 g/(hPa cm^2 s)', None, [0, 1e-7, -1e-7, 1e-6], [0, 1, -1, 10]),
])
def test_known_numeric_conversions_preserve_input(source, target, kind, values, expected):
    original = field(values, source, note={'tags': ['input']})
    saved = original.copy(deep=True)
    result = prepare_field(original, units=target, temperature_kind=kind)
    np.testing.assert_allclose(result.field.values.ravel(), expected, atol=1e-12)
    xr.testing.assert_identical(original, saved)
    assert result.field.name == original.name
    assert result.field.coords.equals(original.coords)
    assert result.field.attrs['units'] == target
    assert not np.shares_memory(result.field.values, original.values)
    result.field.attrs['note']['tags'].append('output')
    assert original.attrs['note']['tags'] == ['input']
    assert asdict(result.conversion)['source_units'] == canonical_unit(source)
    with pytest.raises(FrozenInstanceError):
        result.conversion.offset = 5


@pytest.mark.parametrize('unit', ['mystery', '', 'kg/m2', None, 123])
def test_unknown_units_never_become_identity(unit):
    with pytest.raises(ValueError):
        canonical_unit(unit)
    with pytest.raises(ValueError):
        conversion_rule(unit, unit)


@pytest.mark.parametrize('source,target', [('K', 'm/s'), ('Pa', 'mm'), ('gpm', 'm'), ('J/kg', 'K'), ('dBZ', '1')])
def test_dimension_mismatch_is_rejected(source, target):
    with pytest.raises(ValueError, match='incompatible'):
        prepare_field(field(units=source), units=target)


def test_aliases_identity_and_missing_source():
    value = field(units='m s-1')
    result = prepare_field(value, units='m/s')
    assert not result.conversion.applied
    assert value.attrs['units'] == 'm s-1'
    assert result.field.attrs['units'] == 'm/s'
    assert not np.shares_memory(result.field.values, value.values)
    missing = field(units=None)
    with pytest.raises(ValueError, match='missing'):
        prepare_field(missing, units='mm')
    result = prepare_field(missing, units='mm', source_units='m')
    assert result.conversion.source_from == 'explicit'
    assert 'units' not in missing.attrs
    with pytest.raises(ValueError, match='contradicts'):
        prepare_field(value, source_units='knots', units='m/s')


def test_temperature_semantics_are_explicit_not_inferred_from_name_or_style():
    value = field(units='K', standard_name='air_temperature')
    with pytest.raises(ValueError, match='temperature_kind'):
        prepare_field(value, units='degC')
    diff = value.assign_attrs(temperature_kind='difference')
    np.testing.assert_array_equal(prepare_field(diff, units='degC').field, diff)
    with pytest.raises(ValueError, match='contradicts'):
        prepare_field(diff, units='degC', temperature_kind='absolute')
    with pytest.raises(ValueError, match='temperature unit'):
        prepare_field(field(units='m'), units='mm', temperature_kind='difference')
    with pytest.raises(ValueError, match='temperature_kind'):
        prepare_field(value, temperature_kind='invalid')


def test_repeat_preparation_does_not_repeat_conversion():
    original = field([273.15]*4, 'K', temperature_kind='absolute')
    once = prepare_field(original, units='degC')
    twice = prepare_field(once.field, units='degC')
    assert once.conversion.applied and not twice.conversion.applied
    xr.testing.assert_identical(once.field, twice.field)
    with pytest.raises(ValueError, match='contradicts'):
        prepare_field(once.field, source_units='K', units='degC')


def test_vector_conversion_validates_each_component():
    u, v = field([36]*4, 'km/h'), field([10]*4, 'm/s')
    before_u, before_v = u.copy(deep=True), v.copy(deep=True)
    with pytest.raises(ValueError, match='units differ'):
        prepare_vector(u, v)
    result = prepare_vector(u, v, units='m/s')
    np.testing.assert_allclose(result.u, 10)
    np.testing.assert_allclose(result.v, 10)
    assert [r.applied for r in result.conversions] == [True, False]
    xr.testing.assert_identical(u, before_u)
    xr.testing.assert_identical(v, before_v)
    with pytest.raises(ValueError, match='missing'):
        prepare_vector(u, field(units=None), units='m/s')
    with pytest.raises(ValueError, match='coordinates'):
        prepare_vector(u, v.assign_coords(x=[1, 2]), units='m/s')
    with pytest.raises(ValueError):
        prepare_vector(field(units='Pa'), field(units='Pa'))
    missing = field([36]*4, None)
    explicit = prepare_vector(missing, v, units='m/s', source_units=('km/h', None))
    assert explicit.conversions[0].source_from == 'explicit'


def test_core_style_switch_never_converts_values(monkeypatch):
    from cedarkit.plots import units as module
    def forbidden(*args, **kwargs):
        raise AssertionError('rendering performed data preparation')
    prepared = prepare_field(field([273.15, 280, 290, 300], 'K'), units='degC', temperature_kind='absolute')
    before = prepared.field.copy(deep=True)
    monkeypatch.setattr(module, 'prepare_field', forbidden)
    monkeypatch.setattr(module, 'conversion_rule', forbidden)
    with Panel() as panel:
        chart = panel.add_chart()
        layer = chart.contourf(prepared.field, style='cemc.t2m:cn_summer')
        panel.render()
        layer.update(style='cemc.t2m:cn_winter')
        panel.render()
        xr.testing.assert_identical(layer.data, before)
        figure, revision = panel.fig, panel.revision
        with pytest.raises(ContentError, match='expects units'):
            layer.update(style=ContourStyle(levels=[0, 1], expected_units='K'))
        assert panel.fig is figure and panel.revision == revision
        xr.testing.assert_identical(prepared.field, before)


def test_style_canonical_validation_without_numeric_conversion():
    style = ContourStyle(levels=[0, 1, 2], expected_units='celsius', expected_temperature_kind='absolute')
    assert style.expected_units == 'degC'
    data = field(units='C', temperature_kind='absolute')
    with Panel() as panel:
        panel.add_chart().contourf(data, style=style)
        panel.render()
        assert data.attrs['units'] == 'C'
    with Panel() as panel:
        with pytest.raises(ContentError):
            panel.add_chart().contourf(data.assign_attrs(temperature_kind='difference'), style=style)
    with pytest.raises(ValueError, match='unknown unit'):
        ContourStyle(expected_units='unknown')


def test_core_vector_missing_component_units_and_aliases():
    with Panel() as panel:
        chart = panel.add_chart()
        with pytest.raises(ContentError, match='different units'):
            chart.barbs(field(units='m/s'), field(units=None), style=BarbStyle())
        chart.barbs(field(units='m/s'), field(units='m s-1'), style='cemc.wind')
        panel.render()


def test_business_duration_and_temperature_cannot_silently_match():
    registry = StyleRegistry.default()
    assert registry.explain({'cemc_name':'t2m', 'units':'degC'})['status'] == 'blocked'
    assert registry.match({'cemc_name':'t2m', 'units':'C', 'temperature_kind':'absolute'}) == 't2m'
    assert registry.explain({'cemc_name':'rain', 'units':'mm'})['status'] == 'blocked'
    assert registry.match({'cemc_name':'rain', 'units':'mm', 'accumulation_hours':24}) == 'rain'
    for variant, hours in [('cn',24),('cn_prep',24),('cn_1h',1),('cn_3h',3),('cn_6h',6),('cn_12h',12),('cn_24h',24)]:
        data = field(units='mm', accumulation_hours=hours)
        style = registry.get_style('rain', variant, data=data)
        assert style.accumulation_hours == hours
        with pytest.raises(ValueError, match='accumulation_hours'):
            registry.get_style('rain', variant, data=data.assign_attrs(accumulation_hours=2))
    assert registry.get_style('t_dew_t:cn_fill').expected_temperature_kind == 'difference'
    assert registry.get_style('t_dew_t:cn_t').expected_temperature_kind == 'absolute'


@pytest.mark.parametrize('identifier,unit', [
    ('bli','K'), ('cape','J/kg'), ('cdbz','dBZ'), ('cin','J/kg'),
    ('div','10^-5 s^-1'), ('h_500','dagpm'), ('kidx','K'), ('psl','hPa'),
    ('pte_diff','K'), ('qdiv','10^-7 g/(hPa cm^2 s)'), ('rain','mm'),
    ('rain_snow','mm'), ('rh2m','%'), ('sf','mm'), ('shr','m/s'),
    ('t2m','degC'), ('t_dew_t','K'), ('wind','m/s'), ('ws_10m','m/s'), ('ws_850','m/s'),
])
def test_all_cemc_variants_declare_known_units(identifier, unit):
    registry = StyleRegistry.default()
    spec = registry._lookup(identifier)[1]
    for name, variant in spec.styles.items():
        assert variant.expected_units == ('degC' if (identifier, name) == ('t_dew_t','cn_t') else unit)
        assert "units" not in type(variant).model_fields  # no style-driven conversion hook
    if identifier in ('sf', 'rain_snow'):
        assert spec.styles['cn'].accumulation_hours == 24


def test_core_rejects_non_speed_vectors_and_unknown_field_units():
    with Panel() as panel:
        chart = panel.add_chart()
        with pytest.raises(ContentError, match='speed'):
            chart.barbs(field(units='Pa'), field(units='Pa'), style=BarbStyle())
        with pytest.raises(ContentError, match='unknown unit'):
            chart.contourf(field(units='mystery'), style=ContourStyle(levels=[0,1,2]))


def test_style_selection_does_not_convert_source_kelvin():
    original = field([273.15]*4, 'K', temperature_kind='absolute')
    with pytest.raises(ValueError, match="expected 'degC'"):
        StyleRegistry.default().get_style('t2m', data=original)
    np.testing.assert_array_equal(original, 273.15)
    assert original.attrs['units'] == 'K'


def test_rule_resolution_is_metadata_only(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('rule planning accessed values')
    monkeypatch.setattr(xr.DataArray, 'values', property(forbidden))
    rule = conversion_rule('K', 'degC', temperature_kind='absolute')
    assert rule.offset == -273.15


def test_shared_scale_checks_units_and_temperature_semantics():
    style = ContourStyle(levels=[0, 1, 2])
    with Panel() as panel:
        chart = panel.add_chart()
        first = chart.contourf(field(units='C', standard_name='air_temperature', temperature_kind='absolute'), style=style)
        second = chart.contourf(field(units='degC', standard_name='air_temperature', temperature_kind='absolute'), style=style)
        panel.share_scale([first, second])
        panel.render()
        with pytest.raises(ContentError, match='temperature_kind'):
            second.update(data=second.data.assign_attrs(temperature_kind='difference'))
