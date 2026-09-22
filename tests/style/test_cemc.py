"""Full built-in catalog and rendered CEMC color/label contracts."""
import json
from pathlib import Path

import matplotlib.colors as colors
import numpy as np
import pytest
import xarray as xr

from cedarkit.plots import Panel
from cedarkit.plots.config import LayoutSpec
from cedarkit.plots.errors import ContentError
from cedarkit.plots.palette import get_palette
from cedarkit.plots.style import BarbStyle, StyleRegistry
from cedarkit.plots.style import registry as module
from cedarkit.plots.style.schema import StyleVariant

ROOT = Path(__file__).resolve().parents[2]
RECIPES = json.loads((ROOT / 'tools/palette_recipes.json').read_text())['styles']
HANDOFF = json.loads((ROOT / 'tools/style_palette_map.json').read_text())
IDS = 'bli cape cdbz cin div h_500 kidx psl pte_diff qdiv rain rain_snow rh2m sf shr t2m t_dew_t wind ws_10m ws_850'.split()


@pytest.fixture
def registry(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('built-in CEMC must not read NCL or registered graph tables')
    monkeypatch.setattr(module, 'get_ncl_colormap', forbidden)
    monkeypatch.setattr(module, 'generate_colormap_using_ncl_colors', forbidden)
    monkeypatch.setattr(module, 'get_rgb_table', forbidden)
    monkeypatch.setattr(module.importlib.metadata, 'entry_points', lambda **kwargs: [])
    monkeypatch.delenv('CEDARKIT_STYLE_PATH', raising=False)
    return StyleRegistry.default()


def field(style):
    levels = np.asarray(style.levels)
    values = np.linspace(levels[0] - 1, levels[-1] + 1, 120).reshape(10, 12)
    attrs = {} if style.expected_units is None else {'units': style.expected_units}
    return xr.DataArray(values, dims=('y', 'x'), attrs=attrs)


def test_complete_catalog(registry):
    assert registry.style_ids == sorted(IDS)
    assert sum(len(registry._lookup(i)[1].styles) for i in IDS) == 37
    assert registry.get_style('generic.t').levels.step == 4
    wind = registry.get_style('wind')
    assert isinstance(wind, BarbStyle)
    assert (wind.length, wind.linewidth, wind.pivot, wind.barbcolor, wind.flagcolor) == (4, .3, 'middle', 'black', 'black')
    assert wind.barb_increments == dict(half=2, full=4, flag=20)


@pytest.mark.parametrize('name', sorted(RECIPES))
def test_every_variant_settings_and_rendered_colors(name, registry):
    _, identifier, variant = name.split('.')
    # Shear levels are supplied by the product; no invented fixed thresholds.
    overrides = {'levels': list(range(16))} if identifier == 'shr' else None
    style = registry.get_style(identifier, variant, overrides=overrides)
    old = StyleVariant.model_validate(RECIPES[name])
    expected_levels = np.arange(16) if identifier == 'shr' else module.evaluate_levels(old.levels)
    np.testing.assert_array_equal(style.levels, expected_levels)
    assert style.expected_units == old.expected_units
    assert style.fill == old.fill
    assert style.linestyles == old.linestyles
    assert style.label == (old.label is not None)
    if old.label:
        for key in ('fontsize', 'inline', 'inline_spacing', 'background_color', 'manual', 'zorder'):
            assert getattr(style.label_style, key) == getattr(old.label, key)
        if old.label.fmt:
            assert style.label_style.fmt(588) == old.label.fmt.format(588)
    if old.colorbar:
        assert style.colorbar_style.label == old.colorbar.label
    palette = get_palette(name)
    with Panel() as panel:
        chart = panel.add_chart()
        method = chart.contourf if style.fill else chart.contour
        layer = method(field(style), style=style)
        panel.render()
        artist = layer.results['main'].mappable
        if style.label:
            assert artist.labelTexts
            if old.label.fontsize is not None:
                assert all(text.get_fontsize() == old.label.fontsize for text in artist.labelTexts)
            if old.label.background_color is not None:
                assert all(text.get_bbox_patch() is not None for text in artist.labelTexts)
            if name == 'cemc.h_500.cn_dagpm':
                assert all(colors.to_rgba(text.get_color()) == colors.to_rgba('red') for text in artist.labelTexts)
                assert all(text.get_text().isdigit() for text in artist.labelTexts)
        else:
            assert not artist.labelTexts
        if style.fill:
            assert style.extend == artist.extend == 'both'
            probes = np.r_[expected_levels[0]-1, (expected_levels[:-1]+expected_levels[1:])/2, expected_levels[-1]+1, np.nan]
            # Independent baseline: original business colorbar's extended
            # BoundaryNorm, using the already audited D12-03 RGBA table.
            norm = colors.BoundaryNorm(expected_levels, palette.N, extend='both')
            expected = palette(norm(np.ma.masked_invalid(probes)))
            np.testing.assert_allclose(artist.to_rgba(np.ma.masked_invalid(probes)), expected)
            assert artist.cmap.N == len(expected_levels)-1
        else:
            expected = palette(np.arange(len(expected_levels)) % palette.N)
            for rule in HANDOFF[name].get('highlights', []):
                if 'color' in rule:
                    expected[np.isclose(expected_levels, rule['level'])] = colors.to_rgba(rule['color'])
            np.testing.assert_allclose(artist.get_edgecolors(), expected)
            baseline = old.linewidth if old.linewidth is not None else .7
            widths = np.full(len(expected_levels), baseline)
            for rule in HANDOFF[name].get('highlights', []):
                if rule.get('linewidth') is not None:
                    widths[np.isclose(expected_levels, rule['level'])] = rule['linewidth']
            if old.linewidth is not None or old.highlight:
                np.testing.assert_allclose(artist.get_linewidths(), widths)


def test_labels_and_transparent_feature(registry):
    height = registry.get_style('h_500')
    assert colors.to_rgba(height.label_style.colors) == colors.to_rgba('red')
    np.testing.assert_array_equal(height.colors[-1], colors.to_rgba('black'))
    dew = registry.get_style('t_dew_t:cn_t')
    zero = list(dew.levels).index(0)
    np.testing.assert_array_equal(dew.colors[zero], [0, 0, 0, 0])
    np.testing.assert_array_equal(dew.label_style.colors, dew.colors)
    for variant in ('cn', 'cn_prep', 'cn_24h'):
        assert registry.get_style('rain', variant).colors.get_under()[3] == 0


def test_native_shared_scale_and_atomic_rejection(registry):
    summer = registry.get_style('t2m:cn_summer')
    data = field(summer)
    data.attrs["standard_name"] = "air_temperature"
    with Panel(layout=LayoutSpec(rows=1, columns=2)) as panel:
        first = panel.add_chart().contourf(data, style=summer)
        second = panel.add_chart().contourf(data, style=registry.get_style('t2m:cn_summer'))
        panel.share_scale([first, second])
        panel.render()
        figure, revision = panel.fig, panel.revision
        with pytest.raises(ContentError):
            second.update(style=registry.get_style('t2m:cn_winter'))
        assert panel.fig is figure and panel.revision == revision
        np.testing.assert_array_equal(first.results['main'].mappable.cmap.colors, second.results['main'].mappable.cmap.colors)


def test_default_user_override_preserves_other_builtin_ids(tmp_path, registry):
    user = tmp_path / 'cemc'
    user.mkdir()
    (user / 't2m.yml').write_text('id: t2m\ncriteria: [{cemc_name: t2m}]\noptimal: local\nstyles:\n  local: {type: contour, colormap: viridis, levels: [0, 1, 2], fill: true}\n')
    overridden = StyleRegistry.default(user_paths=[tmp_path])
    assert overridden.get_style('t2m').colors.name == 'viridis'
    assert overridden.get_style('rain').fill
    with pytest.raises(KeyError):
        overridden.get_style('t2m:cn_summer')


def test_testing_helpers_use_native_styles(registry):
    from cedarkit.plots.testing.styles import temperature_style, precipitation_style
    assert temperature_style().extend == 'both'
    assert precipitation_style().colors.get_under()[3] == 0
