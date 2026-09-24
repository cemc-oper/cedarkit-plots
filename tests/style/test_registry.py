"""Unit tests for StyleRegistry (cedarkit.plots.style.registry)."""
from pathlib import Path

import numpy as np
import pytest
import xarray as xr
import matplotlib.colors as mcolors

from cedarkit.plots.palette import get_palette
from cedarkit.plots.style import (
    BarbStyle,
    ContourStyle,
    StyleRegistry,
    evaluate_levels,
    metadata_from_field,
    resolve_style,
)
from cedarkit.plots.style.registry import _representative_field
from cedarkit.plots.style.schema import LinspaceLevels, RangeLevels, StepLevels


FIXTURE_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture(scope="module")
def registry():
    return StyleRegistry([FIXTURE_DIR])


class TestEvaluateLevels:
    def test_explicit_list(self):
        levels = evaluate_levels([-12, -8, 0])
        assert list(levels) == [-12, -8, 0]

    def test_range(self):
        levels = evaluate_levels(RangeLevels(range=[-40, 41, 2]))
        np.testing.assert_array_equal(levels, np.arange(-40, 41, 2))

    def test_linspace(self):
        levels = evaluate_levels(LinspaceLevels(linspace=[500, 588, 23]))
        np.testing.assert_allclose(levels, np.linspace(500, 588, 23))

    def test_step_aligned_to_reference(self):
        data = xr.DataArray(np.array([[3.0, 27.0]]), dims=("y", "x"))
        levels = evaluate_levels(StepLevels(step=4.0, reference=0.0), data=data)
        np.testing.assert_array_equal(levels, np.arange(0, 29, 4))

    def test_step_with_offset_reference(self):
        data = xr.DataArray(np.array([[3.0, 27.0]]), dims=("y", "x"))
        levels = evaluate_levels(StepLevels(step=4.0, reference=1.0), data=data)
        np.testing.assert_array_equal(levels, np.arange(1, 30, 4))

    def test_step_requires_data(self):
        with pytest.raises(ValueError, match="data-driven"):
            evaluate_levels(StepLevels(step=4.0))


class TestGetStyleH500:
    """Acceptance: get_style("h_500") expands the 588 feature line."""

    def test_levels(self, registry):
        style = registry.get_style("h_500")
        assert isinstance(style, ContourStyle)
        np.testing.assert_allclose(style.levels, np.linspace(500, 588, 23))
        assert style.fill is False

    def test_highlight_linewidths(self, registry):
        style = registry.get_style("h_500")
        expected = np.where(style.levels == 588, 1.4, 0.7)
        np.testing.assert_allclose(style.linewidths, expected)

    def test_highlight_colors(self, registry):
        style = registry.get_style("h_500")
        colors = np.asarray(mcolors.to_rgba_array(style.colors))
        expected = np.repeat(
            mcolors.to_rgba_array(get_palette("cemc.h_500.cn_dagpm").colors),
            len(style.levels),
            axis=0,
        )
        expected[np.asarray(style.levels) == 588] = mcolors.to_rgba("black")
        np.testing.assert_allclose(colors, expected)

    def test_label(self, registry):
        style = registry.get_style("h_500")
        assert style.label is True
        label_style = style.label_style
        assert label_style.inline is True
        assert label_style.fontsize == 7
        assert label_style.fmt(588) == "588"
        np.testing.assert_allclose(
            mcolors.to_rgba_array(label_style.colors), [mcolors.to_rgba("red")]
        )

class TestGetStyleT2m:
    def test_optimal_variant(self, registry):
        style = registry.get_style("t2m")
        assert list(style.levels) == [-12, -8, -4, 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44]
        assert style.fill is True

    def test_explicit_variant(self, registry):
        style = registry.get_style("t2m", "cn_winter")
        assert list(style.levels) == [-24, -20, -16, -12, -8, -4, 0, 4, 8, 12, 16, 20, 24, 28, 32]

    def test_colormap_matches_direct_construction(self, registry):
        style = registry.get_style("t2m", "cn_summer")
        expected = get_palette("cemc.t2m.cn_summer")
        np.testing.assert_allclose(
            mcolors.to_rgba_array(style.colors.colors),
            mcolors.to_rgba_array(expected.colors),
        )

class TestGetStyleBarb:
    def test_barb_style(self, registry):
        style = registry.get_style("wind")
        assert isinstance(style, BarbStyle)
        assert style.barbcolor == "black"
        assert style.flagcolor == "black"
        assert style.linewidth == 0.3


class TestBareStringColormap:
    """Bare-string colormap (matplotlib name): fill resolves to a colormap
    object (colorbar path needs ``.N``); line contour keeps the string."""

    def test_fill_resolves_to_colormap(self):
        from cedarkit.plots.style.registry import build_style
        from cedarkit.plots.style.schema import StyleVariant

        variant = StyleVariant(
            type="contour",
            colormap="coolwarm",
            levels=[0, 4, 8, 12],
            fill=True,
        )
        style = build_style("t", "default", variant)
        assert isinstance(style.colors, mcolors.Colormap)
        assert style.colors.name == "coolwarm"

    def test_line_keeps_string(self):
        from cedarkit.plots.style.registry import build_style
        from cedarkit.plots.style.schema import StyleVariant

        variant = StyleVariant(
            type="contour",
            colormap="blue",
            levels=[0, 4, 8, 12],
        )
        style = build_style("t", "line", variant)
        assert style.colors == "blue"

    def test_unknown_name_raises(self):
        from cedarkit.plots.style.registry import build_style
        from cedarkit.plots.style.schema import StyleVariant

        variant = StyleVariant(
            type="contour",
            colormap="no_such_colormap",
            levels=[0, 4, 8, 12],
            fill=True,
        )
        with pytest.raises(KeyError):
            build_style("t", "default", variant)


class TestMatch:
    def test_match_by_cemc_name(self, registry):
        assert registry.match({"cemc_name": "t2m"}) == "t2m"

    def test_match_or_entries(self, registry):
        assert registry.match({"eccodes_name": "2t"}) == "t2m"

    def test_match_and_within_entry(self, registry):
        metadata = {"eccodes_name": "t", "first_level_type": 103, "first_level": 2}
        assert registry.match(metadata) == "t2m"
        metadata = {"eccodes_name": "t", "first_level_type": 103, "first_level": 10}
        assert registry.match(metadata) != "t2m"

    def test_match_level_type_name_normalized(self, registry):
        metadata = {"cemc_name": "h", "first_level_type": "isobaricInhPa", "first_level": 500}
        assert registry.match(metadata) == "h_500"
        metadata["first_level_type"] = "pl"
        assert registry.match(metadata) == "h_500"

    def test_no_match(self, registry):
        assert registry.match({"cemc_name": "unknown_field"}) is None


class TestMetadataFromField:
    def make_field(self):
        field = xr.DataArray(
            np.zeros((3, 4)),
            dims=("latitude", "longitude"),
            coords={
                "latitude": np.arange(3),
                "longitude": np.arange(4),
                "time": np.datetime64("2024-11-13"),
                "step": np.timedelta64(24, "h"),
                "isobaricInhPa": 500.0,
            },
            attrs={
                "cemc_name": "h",
                "eccodes_name": "gh",
                "wgrib2_name": "HGT",
                "GRIB_discipline": 0,
                "GRIB_parameterCategory": 3,
                "GRIB_parameterNumber": 5,
            },
        )
        return field

    def test_attrs_and_level_coord(self):
        metadata = metadata_from_field(self.make_field())
        assert metadata["cemc_name"] == "h"
        assert metadata["eccodes_name"] == "gh"
        assert metadata["discipline"] == 0
        assert metadata["category"] == 3
        assert metadata["number"] == 5
        assert metadata["first_level_type"] == "isobaricInhPa"
        assert metadata["first_level"] == 500.0

    def test_matches_h500(self, registry):
        metadata = metadata_from_field(self.make_field())
        assert registry.match(metadata) == "h_500"


class TestResolveStyle:
    def test_style_passthrough(self, registry):
        style = ContourStyle(levels=[1, 2, 3])
        assert resolve_style(style, data=None, registry=registry) is style

    def test_id_and_variant(self, registry):
        field = xr.DataArray(np.zeros((2, 2)), dims=("y", "x"))
        style = resolve_style("t2m:cn_winter", field, registry=registry)
        assert isinstance(style, ContourStyle)

    def test_auto_match(self, registry):
        field = xr.DataArray(
            np.zeros((2, 2)),
            dims=("latitude", "longitude"),
            coords={"latitude": [0, 1], "longitude": [0, 1], "heightAboveGround": 2.0},
            attrs={"cemc_name": "t2m"},
        )
        style = resolve_style("auto", field, registry=registry)
        assert isinstance(style, ContourStyle)
        assert style.fill is True

    def test_auto_no_match(self, registry):
        field = xr.DataArray(np.zeros((2, 2)), dims=("y", "x"))
        with pytest.raises(ValueError, match="no style matched"):
            resolve_style("auto", field, registry=registry)

    def test_unknown_id(self, registry):
        field = xr.DataArray(np.zeros((2, 2)), dims=("y", "x"))
        with pytest.raises(KeyError, match="not found"):
            resolve_style("no_such_style", field, registry=registry)

    def test_unknown_variant(self, registry):
        field = xr.DataArray(np.zeros((2, 2)), dims=("y", "x"))
        with pytest.raises(KeyError, match="no variant"):
            resolve_style("t2m:no_such_variant", field, registry=registry)


class TestRepresentativeField:
    def test_direct(self):
        field = xr.DataArray(np.zeros((2, 2)), dims=("y", "x"))
        assert _representative_field(field) is field

    def test_nested(self):
        field = xr.DataArray(np.zeros((2, 2)), dims=("y", "x"))
        assert _representative_field([[field, field]]) is field

    def test_not_found(self):
        with pytest.raises(TypeError):
            _representative_field([1, 2, 3])


class TestRegistryLoading:
    def test_style_ids(self, registry):
        assert set(registry.style_ids) == {"t2m", "h_500", "wind"}

    def test_missing_dir_ignored(self):
        registry = StyleRegistry(["/no/such/dir", FIXTURE_DIR])
        assert "t2m" in registry.style_ids

    def test_explicit_user_path_overrides(self, tmp_path):
        override = tmp_path / "override"
        override.mkdir()
        (override / "wind.yml").write_text("""
id: wind
criteria:
  - cemc_name: u
styles:
  custom:
    type: barb
    barbcolor: blue
""", encoding="utf-8")
        registry = StyleRegistry([FIXTURE_DIR], user_paths=[override])
        style = registry.get_style("wind", "custom")
        assert style.barbcolor == "blue"

    def test_builtin_styles_in_default(self):
        default = StyleRegistry.default(profile="generic")
        assert "t" in default.style_ids

    def test_unknown_style_id(self, registry):
        with pytest.raises(KeyError, match="not found"):
            registry.get_style("no_such_id")

    def test_no_optimal_requires_variant(self, tmp_path):
        (tmp_path / "multi.yml").write_text("""
id: multi
criteria:
  - cemc_name: multi
styles:
  a: { type: contour }
  b: { type: contour }
""", encoding="utf-8")
        registry = StyleRegistry([tmp_path])
        with pytest.raises(ValueError, match="no optimal variant"):
            registry.get_style("multi")
