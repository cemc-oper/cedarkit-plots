"""Quick plotting must use the normal content, unit and lifecycle contracts."""

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import numpy as np
import pytest
import xarray as xr

from cedarkit.plots import Panel, quickplot
from cedarkit.plots.config import BasemapSpec, ChartSpec, LayoutSpec, SubplotSpec
from cedarkit.plots.domains import Domain
from cedarkit.plots.errors import ContentError, ConfigError, RenderError
from cedarkit.plots.style import BarbStyle, ContourStyle, LevelStep, StyleRegistry
from cedarkit.plots.templates import PanelTemplate


def field(offset=0, *, units='degC', name='t2m', kind='absolute'):
    return xr.DataArray(np.arange(12).reshape(3, 4) + offset, dims=('y', 'x'),
                        coords={'y': [0.,1.,2.], 'x': [0.,1.,2.,3.]},
                        attrs={'units':units, 'cemc_name':name, 'temperature_kind':kind,
                               'standard_name':'air_temperature'})


def dynamic():
    return ContourStyle(levels=LevelStep(4), colors='viridis', fill=True)


def members():
    return [quickplot.FacetItem('ctl-real', field(), 'control'),
            quickplot.FacetItem('mem07', field(40), 'member')]


@pytest.fixture(autouse=True)
def no_leaked_figures():
    before = set(plt.get_fignums())
    yield
    extra = set(plt.get_fignums()) - before
    for number in extra:
        plt.close(number)
    assert not extra, f'leaked figures: {extra}'


def test_auto_cemc_return_handles_and_context_ownership(tmp_path):
    original = field()
    closed_sources = []
    original.set_close(lambda: closed_sources.append(True))
    external = plt.figure()
    try:
        with quickplot.plot(original, title='Temperature', output=tmp_path/'temperature.png') as result:
            assert result.panel.charts['main'] is result.chart
            assert result.chart.layers['field'] is result.layer
            assert result.layer.data is original
            assert result.layer.method == 'contourf'
            assert result.layer.style.expected_units == 'degC'
            assert result.conversions == ((),)
            assert not result.panel.closed
            assert result.panel.fig is not None
            assert (tmp_path/'temperature.png').stat().st_size > 0
            assert len(result.panel.fig.axes) == 2
        assert result.panel.closed
        assert closed_sources == []
        result.close()
        assert plt.fignum_exists(external.number)
    finally:
        plt.close(external)


def test_explicit_method_not_style_fill_and_singleton_input_rules():
    with quickplot.plot(field(), method='contour', style=dynamic()) as result:
        assert result.layer.method == 'contour'
        assert len(result.panel.fig.axes) == 1
    for value in ([field()], (item for item in [field()]), field().expand_dims(member=[0]), xr.Dataset({'t':field()})):
        with pytest.raises(TypeError, match='two-dimensional'):
            quickplot.plot(value, style=dynamic())


def test_units_before_auto_match_and_no_reconversion(monkeypatch):
    original = field(273.15, units='K')
    saved = original.copy(deep=True)
    with pytest.raises(ValueError, match="expected 'degC'"):
        quickplot.plot(original)
    with quickplot.plot(original, units='degC') as result:
        np.testing.assert_allclose(result.layer.data, saved-273.15)
        assert result.conversions[0][0].offset == -273.15
        assert result.conversions[0][0].applied
        def forbidden(*args, **kwargs):
            raise AssertionError('preparation repeated on update/render')
        monkeypatch.setattr(quickplot, 'prepare_field', forbidden)
        result.layer.update(style='cemc.t2m:cn_winter')
        result.panel.render()
        np.testing.assert_allclose(result.layer.data, saved-273.15)
    xr.testing.assert_identical(original, saved)


def test_explicit_generic_registry_and_style_overrides():
    with quickplot.plot(field(name='t'), registry=StyleRegistry.default(profile='generic'),
                        style_overrides={'levels': {'step':2}}) as result:
        assert result.layer.style.levels == LevelStep(2)
    with quickplot.plot(field(), method='contour', style='cemc.t2m', style_overrides={'linewidth': 3}) as result:
        assert result.layer.style.linewidths == 3
    with pytest.raises(ValueError, match='configure explicit Style'):
        quickplot.plot(field(), style=dynamic(), style_overrides={'levels':[0,1,2]})


def test_barbs_explicit_components_records_and_basis():
    u = field(0, units='km/h', name='u', kind=None)
    v = field(0, units='m/s', name='v', kind=None)
    with quickplot.barbs(u, v, units='m/s', vector_basis='earth') as result:
        assert result.layer.method == 'barbs'
        assert result.layer.vector_basis == 'earth'
        np.testing.assert_allclose(result.layer.data[0], u/3.6)
        np.testing.assert_allclose(result.layer.data[1], v)
        assert [record.applied for record in result.conversions[0]] == [True, False]
        assert len(result.panel.fig.axes) == 1
    with pytest.raises(ContentError, match='different units'):
        quickplot.barbs(u, v, style=BarbStyle())
    with pytest.raises(TypeError):
        quickplot.barbs((u,v))
    with pytest.raises(TypeError, match='BarbStyle'):
        quickplot.barbs(u, v, style=dynamic())
    with pytest.raises(TypeError, match='ContourStyle'):
        quickplot.plot(field(), style=BarbStyle())


@pytest.mark.parametrize('policy,expected', [('per_chart', ((0,12),(40,52))), ('shared', ((0,52),(0,52)))])
def test_dynamic_facet_level_policy_and_shared_colorbar(policy, expected):
    with quickplot.facet(members(), style=dynamic(), level_policy=policy) as result:
        assert tuple(c.id for c in result.charts) == ('ctl-real','mem07')
        assert tuple(c.role for c in result.charts) == ('control','member')
        assert len(result.panel.charts) == 2
        assert len(result.panel.fig.axes) == (4 if policy=='per_chart' else 3)
        for layer, (lo,hi) in zip(result.layers, expected):
            assert layer.style.levels == LevelStep(4)
            assert layer.results['main'].mappable.levels[0] == lo
            assert layer.results['main'].mappable.levels[-1] == hi
        assert (result.scale_id is not None) == (policy=='shared')
        with pytest.raises(ValueError, match='charts'):
            result.chart


def test_fixed_cemc_levels_not_changed_by_shared_policy():
    with quickplot.facet(members(), level_policy='shared') as result:
        assert tuple(result.layers[0].results['main'].mappable.levels) == tuple(range(-12,45,4))
        np.testing.assert_array_equal(result.layers[0].results['main'].mappable.levels,
                                      result.layers[1].results['main'].mappable.levels)


def test_dimension_facet_identity_roles_slices_and_generator_once():
    data = xr.concat([field(),field(40)], dim=xr.IndexVariable('number',[0,7]))
    with quickplot.facet(data, dim='number', style=dynamic(), colorbar=False) as result:
        assert tuple(result.panel.charts) == ('0','7')
        assert all(c.role == 'member' for c in result.charts)
        assert result.layers[1].data.coords['number'].item() == 7
        np.testing.assert_array_equal(result.layers[1].data, data.isel(number=1))
    with quickplot.facet(data, dim='number', ids=['actual-ctl','perturbed'], roles=['control','member'],
                        style=dynamic(), colorbar=False) as result:
        assert result.charts[0].id == 'actual-ctl'
        assert result.charts[0].role == 'control'
    seen = []
    def items():
        for item in members():
            seen.append(item.id)
            yield item
    with quickplot.facet(items(), style=dynamic(), colorbar=False) as result:
        result.panel.render(force=True)
        result.panel.configure(layout=LayoutSpec(rows=2,columns=1))
        result.panel.render()
        assert seen == ['ctl-real','mem07']
        assert result.panel.charts['mem07'] is result.charts[1]


@pytest.mark.parametrize('data,kwargs,error', [
    ([],{},ValueError),
    ([quickplot.FacetItem('same',field()),quickplot.FacetItem('same',field())],{},ValueError),
    ([field()],{},TypeError),
    ([quickplot.FacetItem('bad id',field())],{},ValueError),
    (field(),{'dim':'member'},ValueError),
    (field().expand_dims(member=[0]),{},ValueError),
    (field().expand_dims(member=[0]),{'dim':'member','ids':[]},ValueError),
    (field().expand_dims(member=[0]),{'dim':'member','roles':['a','b']},ValueError),
    (members(),{'dim':'member'},ValueError),
    (xr.Dataset({'t':field()}),{},TypeError),
])
def test_bad_facet_inputs_fail_without_a_panel(monkeypatch, data, kwargs, error):
    def forbidden(*args, **kwargs):
        raise AssertionError('created a Panel before validating members')
    monkeypatch.setattr(quickplot,'Panel',forbidden)
    with pytest.raises(error):
        quickplot.facet(data, style=dynamic(), **kwargs)


def test_generator_failure_does_not_create_panel(monkeypatch):
    def broken():
        yield members()[0]
        raise RuntimeError('stream failed')
    def forbidden(*args, **kwargs):
        raise AssertionError('created Panel')
    monkeypatch.setattr(quickplot,'Panel',forbidden)
    with pytest.raises(RuntimeError, match='stream failed'):
        quickplot.facet(broken(), style=dynamic())


def test_shared_metadata_conflict_and_missing_levels_are_errors():
    data = members()
    data[1].field.attrs['standard_name'] = 'another_quantity'
    with pytest.raises(ContentError, match='standard_name'):
        quickplot.facet(data, style=dynamic(), level_policy='shared')
    with pytest.raises(ValueError, match='levels'):
        quickplot.facet(members(), style=ContourStyle(colors='viridis'))


def test_failures_close_only_owned_panel(monkeypatch, tmp_path):
    external = plt.figure()
    panels = []
    def factory(**kwargs):
        panel = Panel(**kwargs)
        panels.append(panel)
        return panel
    monkeypatch.setattr(quickplot,'Panel',factory)
    try:
        with pytest.raises((IsADirectoryError, PermissionError)):
            quickplot.plot(field(), output=tmp_path, save_kwargs={'format':'png'})
        assert panels[-1].closed
        assert plt.fignum_exists(external.number)
        with pytest.raises(ConfigError):
            quickplot.facet(members(), style=dynamic(), layout=LayoutSpec(rows=1,columns=1))
        assert panels[-1].closed
        assert plt.fignum_exists(external.number)
    finally:
        plt.close(external)


def test_config_template_and_map_target_reuse():
    domain = Domain(extent=(0,3,0,2), extent_crs=ccrs.PlateCarree())
    map_spec = SubplotSpec(kind='map', domain=domain, map_crs=ccrs.PlateCarree(),
                           basemap=BasemapSpec(features=(),map_info=None))
    template = PanelTemplate(chart_defaults=ChartSpec(subplots={'main':map_spec}))
    with quickplot.plot(field(), template=template, data_crs=ccrs.PlateCarree(), colorbar=False) as result:
        chart, layer = result.chart, result.layer
        assert chart.main.domain.extent == (0,3,0,2)
        result.panel.apply_template(PanelTemplate(
            layout=LayoutSpec(figsize=(7,4)), chart_defaults=ChartSpec(subplots={"main":map_spec})))
        result.panel.render()
        assert result.chart is chart and result.layer is layer
    with quickplot.facet(members(), template=PanelTemplate(), style=dynamic(), colorbar=False) as result:
        assert result.panel.effective_config.layout.columns == 2


def test_one_member_shared_and_explicit_style_no_registry(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('explicit Style loaded registry')
    monkeypatch.setattr(StyleRegistry,'default',forbidden)
    with quickplot.facet(members()[:1], style=dynamic(), level_policy='shared') as result:
        assert result.chart is result.charts[0]
        assert result.scale_id is None
        assert len(result.panel.fig.axes) == 2


@pytest.mark.parametrize('kwargs,error', [
    ({'method':'quiver'},ValueError), ({'colorbar':'yes'},TypeError),
    ({'save_kwargs':{'dpi':80}},ValueError),
    ({'output':'unused.png','save_kwargs':{'bogus':1}},ValueError),
    ({'chart_id':''},ValueError),
])
def test_options_rejected_before_creation(kwargs,error):
    with pytest.raises(error):
        quickplot.plot(field(),style=dynamic(),**kwargs)


def test_vector_dimension_and_coordinate_failures_are_not_guessed():
    u, v = field(units='m/s', kind=None), field(units='m/s', kind=None)
    with pytest.raises((ContentError, ValueError)):
        quickplot.barbs(u, v.assign_coords(x=[0,2,4,6]), style=BarbStyle())
    with pytest.raises(TypeError, match='two-dimensional'):
        quickplot.barbs(u.expand_dims(member=[0]), v, style=BarbStyle())


def test_empty_dimension_duplicate_coordinates_and_explicit_ids():
    empty = field().expand_dims(member=[])
    with pytest.raises(ValueError, match='empty'):
        quickplot.facet(empty, dim='member')
    duplicate = xr.concat([field(),field()],dim=xr.IndexVariable('number',[1,1]))
    with pytest.raises(ValueError, match='duplicate'):
        quickplot.facet(duplicate,dim='number')
    with quickplot.facet(duplicate,dim='number',ids=['a','b'],colorbar=False) as result:
        assert tuple(result.panel.charts) == ('a','b')
    no_coordinate = duplicate.drop_vars('number')
    with pytest.raises(ValueError, match='coordinate'):
        quickplot.facet(no_coordinate,dim='number')
    with quickplot.facet(no_coordinate,dim='number',ids=['a','b'],colorbar=False) as result:
        assert tuple(result.panel.charts) == ('a','b')


def test_facet_conversion_records_align_with_members_and_input_is_preserved():
    data = xr.concat([field(273.15,units='K'),field(283.15,units='K')],dim=xr.IndexVariable('number',[2,5]))
    before = data.copy(deep=True)
    with quickplot.facet(data,dim='number',units='degC',level_policy='shared') as result:
        assert tuple(c.id for c in result.charts) == ('2','5')
        assert all(records[0].offset == -273.15 for records in result.conversions)
        np.testing.assert_allclose(result.layers[1].data, data.isel(number=1)-273.15)
    xr.testing.assert_identical(data,before)


def test_no_figures_or_data_sources_closed_on_render_failure(monkeypatch):
    from cedarkit.plots.chart import core
    calls = []
    data = field()
    data.set_close(lambda: calls.append('closed data'))
    before = data.copy(deep=True)
    external = plt.figure()
    existing_figures = set(plt.get_fignums())
    def fail(*args, **kwargs):
        raise RuntimeError('draw failed')
    monkeypatch.setattr(core,'_draw_layer',fail)
    try:
        with pytest.raises(RenderError, match='rendering failed') as caught:
            quickplot.plot(data)
        assert str(caught.value.__cause__) == 'draw failed'
        assert calls == []
        assert set(plt.get_fignums()) == existing_figures
        xr.testing.assert_identical(data,before)
    finally:
        plt.close(external)


def test_output_saves_once_without_showing(monkeypatch,tmp_path):
    from cedarkit.plots.chart import core
    calls = []
    original = core._draw_layer
    def draw(*args,**kwargs):
        calls.append('draw')
        return original(*args,**kwargs)
    def forbidden(*args,**kwargs):
        raise AssertionError('quickplot opened a GUI')
    monkeypatch.setattr(core,'_draw_layer',draw)
    monkeypatch.setattr(plt,'show',forbidden)
    with quickplot.plot(field(),output=tmp_path/'one.png',save_kwargs={'dpi':70}) as result:
        assert calls == ['draw']
        result.panel.save(tmp_path/'two.png')
        assert calls == ['draw']


def test_template_roles_and_layout_reflow_do_not_manufacture_statistics():
    from cedarkit.plots.templates import ens_cn_layout
    template = PanelTemplate(layout=ens_cn_layout(columns=2))
    with quickplot.facet(members(),template=template,level_policy='shared') as result:
        assert tuple(result.panel.charts) == ('ctl-real','mem07')
        charts, layers = result.charts, result.layers
        result.panel.apply_template(PanelTemplate(layout=ens_cn_layout(columns=1)))
        result.panel.render()
        assert tuple(result.panel.charts.values()) == charts
        assert result.layers == layers
        assert result.panel.effective_config.layout.rows == 2
    required = PanelTemplate(layout=ens_cn_layout(require_control=True))
    with pytest.raises(ConfigError, match='required'):
        quickplot.facet([quickplot.FacetItem('ordinary',field())],template=required)


def test_business_duration_missing_units_and_generic_fallback_remain_explicit():
    rain = field(units='mm',name='rain',kind=None)
    with pytest.raises(ValueError, match='accumulation_hours'):
        quickplot.plot(rain)
    with quickplot.plot(rain.assign_attrs(accumulation_hours=24)) as result:
        assert result.layer.style.accumulation_hours == 24
    with pytest.raises(ValueError, match='missing'):
        quickplot.plot(field().assign_attrs(units=None), units='degC')
    unknown = field(name='not-a-business-element').assign_attrs(eccodes_name='t').assign_coords(isobaricInhPa=500)
    with pytest.raises(ValueError, match='no style matched'):
        quickplot.plot(unknown)
    with quickplot.plot(unknown,registry=StyleRegistry.default(generic_fallback=['t'])) as result:
        assert result.layer.style.levels == LevelStep(4)


def test_render_interruption_releases_uncommitted_figure(monkeypatch):
    from cedarkit.plots.chart import core
    external = plt.figure()
    existing_figures = set(plt.get_fignums())
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(core,'_draw_layer',interrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            quickplot.plot(field())
        assert set(plt.get_fignums()) == existing_figures
    finally:
        plt.close(external)


def test_factory_grid_does_not_override_later_template_layout():
    template = PanelTemplate()
    with quickplot.facet(members(),style=dynamic(),template=template,colorbar=False) as result:
        assert result.panel.effective_config.layout.columns == 2
        charts = result.charts
        result.panel.apply_template(PanelTemplate(layout=LayoutSpec(rows=2,columns=1)))
        result.panel.render()
        assert result.panel.effective_config.layout.columns == 1
        assert result.panel.effective_config.layout.rows == 2
        assert tuple(result.panel.charts.values()) == charts
    from cedarkit.plots.config import UNSET
    assert template.layout is UNSET
