"""Verify an installed wheel with ``python -I`` outside the source checkout.

This is an acceptance check, not an installer. Pass the exact wheel and sdist
used for installation. --hide-legacy additionally proves the native path works
without the transitional NCL files; the original artifacts remain untouched.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import importlib.metadata as metadata
import importlib.resources as resources
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_environment():
    import cedarkit.plots
    prefix = Path(sys.prefix).resolve()
    assert sys.prefix != sys.base_prefix, 'a separate virtual environment is required'
    assert sys.flags.isolated, 'run with python -I'
    assert Path(cedarkit.plots.__file__).resolve().is_relative_to(prefix)
    assert importlib.util.find_spec('cedar_graph') is None
    packages = {}
    for dist in metadata.distributions():
        name = dist.metadata['Name']
        assert name.lower().replace('_', '-') != 'cedar-graph'
        assert Path(dist.locate_file('')).resolve().is_relative_to(prefix), name
        direct = json.loads(dist.read_text('direct_url.json') or '{}')
        assert not direct.get('dir_info', {}).get('editable', False), name
        packages[name] = dist.version
    return {'python': sys.version, 'prefix': str(prefix),
            'plots_origin': cedarkit.plots.__file__, 'packages': dict(sorted(packages.items())),
            'graph_installed': False, 'editable_installs': False}


def check_artifacts(wheel, sdist, map_baseline):
    root = resources.files('cedarkit.plots')
    hashes = {}
    with zipfile.ZipFile(wheel) as z, tarfile.open(sdist) as t:
        prefix = t.getnames()[0].split('/')[0] + '/'
        names = z.namelist()
        legacy = [n for n in names if '/resources/colormap/ncl/' in n]
        targets = [n for n in names if n.startswith((
            'cedarkit/plots/resources/palettes/', 'cedarkit/plots/style/builtin/'))]
        assert len([n for n in targets if '/builtin/cemc/' in n]) == 20
        assert 'cedarkit/plots/style/builtin/generic/t.yml' in targets
        assert len([n for n in targets if '/palettes/' in n]) == 5
        for name in targets:
            data = z.read(name)
            relative = name.removeprefix('cedarkit/plots/')
            assert root.joinpath(relative).read_bytes() == data, name
            assert t.extractfile(prefix + 'src/' + name).read() == data, name
            hashes[relative] = digest(data)
        for name in ('NOTICE.txt', 'NCAR-NCL-LICENSE.txt', 'Apache-2.0.txt', 'CEDAR-GRAPH-NOTICE.txt'):
            assert root.joinpath('resources/palettes', name).read_text().strip()
        baseline = json.loads(map_baseline.read_text())
        maps = {k: v for k, v in baseline.items() if k.startswith('resources/map/')}
        assert len(maps) == 21
        for name, sha in maps.items():
            assert digest(z.read('cedarkit/plots/' + name)) == sha
            assert digest(root.joinpath(name).read_bytes()) == sha
            assert digest(t.extractfile(prefix + 'src/cedarkit/plots/' + name).read()) == sha
        audit = json.load(t.extractfile(prefix + 'tools/palette_audit.json'))
    return {'wheel': str(wheel), 'wheel_sha256': digest(wheel.read_bytes()),
            'sdist': str(sdist), 'sdist_sha256': digest(sdist.read_bytes()),
            'resource_sha256': hashes, 'unchanged_map_files': len(maps),
            'transitional_ncl_files': legacy, 'release_cleanup_required': bool(legacy)}, audit


@contextmanager
def hide_legacy(enabled):
    path = Path(str(resources.files('cedarkit.plots').joinpath('resources/colormap/ncl')))
    hidden = path.with_name('ncl.d12-acceptance-hidden')
    moved = enabled and path.exists()
    if moved:
        assert not hidden.exists()
        path.rename(hidden)
    try:
        if enabled:
            assert not path.exists()
        yield
    finally:
        if moved:
            hidden.rename(path)


def check_palettes(audit):
    import matplotlib.colors as colors
    import numpy as np
    from cedarkit.plots.palette import get_named_color, get_palette, palette_names
    assert len(palette_names()) == 51
    count = 0
    for name in palette_names():
        cmap = get_palette(name)
        expected = np.array([colors.to_rgba(row['new_rgba']) for row in audit[name]['rows']])
        assert cmap.N == len(expected)
        np.testing.assert_allclose(cmap(np.arange(cmap.N)), expected, rtol=0, atol=1e-15)
        count += cmap.N
    assert count == 1766
    assert get_named_color('transparent') == (1, 1, 1, 0)
    return {'palettes': 51, 'rgba_rows': count, 'transparent': [1, 1, 1, 0]}


def check_styles():
    import numpy as np
    import xarray as xr
    import yaml
    from cedarkit.plots import quickplot
    from cedarkit.plots.style import BarbStyle, StyleRegistry
    from cedarkit.plots.style import registry as registry_module
    from cedarkit.plots import colormap

    def forbidden(*args, **kwargs):
        raise AssertionError('native styles called a legacy color reader')

    for module in (colormap, registry_module):
        module.get_ncl_colormap = forbidden
        module.generate_colormap_using_ncl_colors = forbidden
    registry_module.get_rgb_table = forbidden
    registry = StyleRegistry.default()
    expected_ids = 'bli cape cdbz cin div h_500 kidx psl pte_diff qdiv rain rain_snow rh2m sf shr t2m t_dew_t wind ws_10m ws_850'.split()
    assert registry.style_ids == sorted(expected_ids)
    rendered = []
    for resource in sorted(resources.files('cedarkit.plots').joinpath('style/builtin/cemc').iterdir(), key=lambda p: p.name):
        config = yaml.safe_load(resource.read_text())
        for variant, spec in config['styles'].items():
            identifier = f"cemc.{config['id']}:{variant}"
            attrs = {'units': spec['expected_units']}
            for key in ('expected_temperature_kind', 'accumulation_hours'):
                if spec.get(key) is not None:
                    attrs[key.replace('expected_', '')] = spec[key]
            overrides = {'levels': list(range(16))} if config['id'] == 'shr' else None
            style = registry.get_style(identifier, metadata=attrs, overrides=overrides)
            if isinstance(style, BarbStyle):
                assert (style.length, style.linewidth, style.pivot) == (4, .3, 'middle')
                assert style.barb_increments == {'half': 2, 'full': 4, 'flag': 20}
                u = xr.DataArray(np.ones((8, 10))*8, dims=('y', 'x'), attrs=attrs)
                with quickplot.barbs(u, u, style=style) as result:
                    assert result.layer.results['main'].artists
            else:
                levels = np.asarray(style.levels)
                expected = overrides['levels'] if overrides else spec['levels']
                if isinstance(expected, dict):
                    if 'range' in expected:
                        expected = np.arange(*expected['range'])
                    else:
                        assert set(expected) == {'linspace'}
                        expected = np.linspace(*expected['linspace'])
                np.testing.assert_array_equal(levels, expected)
                data = xr.DataArray(np.linspace(levels[0]-1, levels[-1]+1, 80).reshape(8, 10), dims=('y', 'x'), attrs=attrs)
                with quickplot.plot(data, method='contourf' if style.fill else 'contour', style=style) as result:
                    artist = result.layer.results['main'].mappable
                    np.testing.assert_array_equal(artist.levels, levels)
                    if style.label:
                        assert artist.labelTexts, identifier
            rendered.append(identifier)
    assert len(rendered) == 37
    return rendered


def check_examples(output):
    import matplotlib.pyplot as plt
    import numpy as np
    import xarray as xr
    import yaml
    from cedarkit.plots import quickplot
    from cedarkit.plots.config import LayoutSpec
    from cedarkit.plots.style import StyleRegistry, ContourStyle
    x, y = np.meshgrid(np.linspace(-1, 1, 30), np.linspace(-1, 1, 24))
    raw = xr.DataArray(273.15+16+20*x+8*np.sin(3*y), dims=('y', 'x'),
                       attrs={'units': 'K', 'temperature_kind': 'absolute', 'cemc_name': 't2m',
                              'standard_name': 'air_temperature'})
    original = raw.copy(deep=True)
    levels = np.arange(-12, 48, 4)
    reports = {}
    with quickplot.plot(raw, units='degC', title='Installed wheel: CEMC temperature',
                        colorbar_label='degC', output=output/'temperature.png') as result:
        np.testing.assert_allclose(result.layer.data.values, raw.values-273.15, rtol=0, atol=1e-12)
        np.testing.assert_array_equal(result.layer.results['main'].mappable.levels, levels)
        reports['temperature'] = {'levels': levels.tolist(), 'conversion': asdict(result.conversions[0][0])}
        assert reports['temperature']['conversion']['offset'] == -273.15
        prepared = result.layer.data.values.copy()
        result.layer.update(style='cemc.t2m:cn_winter')
        result.panel.render()
        np.testing.assert_array_equal(result.layer.data.values, prepared)
    u = raw.copy(data=36+20*y).assign_attrs(units='km/h', temperature_kind=None, cemc_name='u', standard_name='eastward_wind')
    v = raw.copy(data=3+4*x).assign_attrs(units='m/s', temperature_kind=None, cemc_name='v', standard_name='northward_wind')
    before_u, before_v = u.copy(deep=True), v.copy(deep=True)
    with quickplot.barbs(u, v, units='m/s', title='Installed wheel: mixed-unit wind', output=output/'wind.png') as result:
        np.testing.assert_allclose(result.layer.data[0].values, u.values/3.6, rtol=0, atol=1e-12)
        np.testing.assert_array_equal(result.layer.data[1].values, v.values)
        reports['wind'] = {'conversions': [asdict(r) for r in result.conversions[0]]}
        assert result.conversions[0][0].scale == 1/3.6
        assert result.conversions[0][1].scale == 1
    cube = xr.concat([raw, raw+4, raw+8], dim=xr.IndexVariable('number', [0, 1, 7]))
    cube.attrs = dict(raw.attrs)
    with quickplot.facet(cube, dim='number', ids=['ctl', 'mem01', 'mem07'],
                         roles=['control', 'member', 'member'], units='degC', level_policy='shared',
                         layout=LayoutSpec(rows=1, columns=3, figsize=(12, 4)),
                         colorbar_label='degC', output=output/'facet.png') as result:
        assert [c.id for c in result.charts] == ['ctl', 'mem01', 'mem07']
        assert [c.role for c in result.charts] == ['control', 'member', 'member']
        assert result.scale_id == 'shared'
        for i, layer in enumerate(result.layers):
            np.testing.assert_allclose(layer.data.values, cube.isel(number=i).values-273.15, rtol=0, atol=1e-12)
            np.testing.assert_array_equal(layer.results['main'].mappable.levels, levels)
        handles = result.charts
        result.panel.configure(layout=LayoutSpec(rows=3, columns=1))
        result.panel.render()
        assert tuple(result.panel.charts.values()) == handles
        reports['facet'] = {'ids': [c.id for c in handles], 'roles': [c.role for c in handles], 'levels': levels.tolist()}
    with quickplot.plot(raw, style='generic.t') as result:
        np.testing.assert_array_equal(result.layer.data.values, raw.values)
        np.testing.assert_array_equal(np.diff(result.layer.results['main'].mappable.levels), 4)
        reports['generic'] = {'step': 4, 'explicit': True}
    user = output/'user-profile/cemc'
    user.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load(resources.files('cedarkit.plots').joinpath('style/builtin/cemc/t2m.yml').read_text())
    for variant in config['styles'].values():
        variant.update(colormap='viridis', levels=[-20, 0, 20, 40, 60])
    (user/'t2m.yml').write_text(yaml.safe_dump(config))
    registry = StyleRegistry.default(user_paths=[user.parent])
    with quickplot.plot(raw, units='degC', registry=registry) as result:
        np.testing.assert_array_equal(result.layer.style.levels, [-20, 0, 20, 40, 60])
        assert result.layer.style.colors.name == 'viridis'
    assert registry.get_style('t2m', overrides={'colormap': 'plasma'}).colors.name == 'plasma'
    assert registry.get_style('t2m').colors.name == 'viridis'
    assert StyleRegistry.default().get_style('t2m').colors.name != 'viridis'
    with quickplot.plot(raw, style=ContourStyle(levels=[200, 250, 300, 350], colors='plasma'), registry=registry):
        pass
    reports['user_override'] = {'palette': 'viridis', 'explicit_override': 'plasma', 'isolated': True}
    for actual, expected in ((raw, original), (u, before_u), (v, before_v)):
        xr.testing.assert_identical(actual, expected)
    assert not plt.get_fignums()
    assert not any(n == 'cedar_graph' or n.startswith('cedar_graph.') for n in sys.modules)
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--sdist', type=Path, required=True)
    parser.add_argument('--map-baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hide-legacy', action='store_true')
    parser.add_argument('--require-no-legacy', action='store_true', help='D15 release gate')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'environment': check_environment()}
    report['artifacts'], audit = check_artifacts(args.wheel, args.sdist, args.map_baseline)
    if args.require_no_legacy:
        assert not report['artifacts']['transitional_ncl_files'], 'D14/D15 NCL cleanup is still required'
    with hide_legacy(args.hide_legacy):
        report['legacy_resources_hidden'] = args.hide_legacy
        report['palettes'] = check_palettes(audit)
        report['rendered_variants'] = check_styles()
        report['examples'] = check_examples(args.output)
    report['status'] = 'passed'
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS: installed wheel; 20 CEMC styles / 37 variants; 51 palettes / 1766 RGBA rows; generic, overrides, 3 examples')


if __name__ == '__main__':
    main()
