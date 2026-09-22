"""D12-03 native palettes versus the retained pre-migration implementation."""
import json
from pathlib import Path
import subprocess
import sys

import matplotlib.colors as mcolors
import numpy as np
import pytest

from cedarkit.plots.colormap import get_ncl_colormap, generate_colormap_using_ncl_colors
from cedarkit.plots.palette import get_named_color, get_palette, get_palette_info, palette_names
from cedarkit.plots.style import StyleRegistry
from cedarkit.plots.style import registry
from cedarkit.plots.style.schema import ColormapSpec

ROOT = Path(__file__).resolve().parents[2]
SOURCES = json.loads((ROOT / "tools/palette_sources.json").read_text())["sources"]
RECIPES = json.loads((ROOT / "tools/palette_recipes.json").read_text())
AUDIT = json.loads((ROOT / "tools/palette_audit.json").read_text())


@pytest.mark.parametrize("name", [name for name, s in SOURCES.items() if s["status"] == "verified" and not name.startswith("cn_")])
def test_every_original_color_matches_old_reader(name):
    expected = get_ncl_colormap(name)
    actual = get_palette("source." + name)
    assert actual.N == expected.N == SOURCES[name]["parsed_color_count"]
    np.testing.assert_array_equal(mcolors.to_rgba_array(actual.colors), mcolors.to_rgba_array(expected.colors))
    np.testing.assert_array_equal(actual.get_under(), expected.get_under())
    np.testing.assert_array_equal(actual.get_over(), expected.get_over())
    np.testing.assert_array_equal(actual.get_bad(), expected.get_bad())


@pytest.fixture
def old_rgb_tables():
    saved = registry._rgb_tables.copy()
    for name in ("cn_hgt20", "cn_ws15", "cn_cr19"):
        registry.register_rgb_table(name, np.array(SOURCES[name]["colors"]) / 255)
    pte = get_ncl_colormap("BkBlAqGrYeOrReViWh200", index=np.array([175,160,156,140,125,110,100,90,80,60])-2)
    registry.register_rgb_table("cn_pte", list(pte.colors) + [[1,1,1,1]])
    tdew = get_ncl_colormap("testcmap")
    registry.register_rgb_table("cn_tdew", list(tdew.colors) + [(1,0,1), (77/255,77/255,77/255)])
    shr = get_ncl_colormap("WhViBlGrYeOrRe")
    extra = generate_colormap_using_ncl_colors(RECIPES["shr_names"], "old-shr")
    registry.register_rgb_table("cn_shr", np.concatenate((shr.colors, extra.colors)))
    yield
    registry._rgb_tables.clear()
    registry._rgb_tables.update(saved)


@pytest.mark.parametrize("name", sorted(RECIPES["styles"]))
def test_every_style_palette_matches_legacy_except_transparency(name, old_rgb_tables):
    spec = RECIPES["styles"][name]["colormap"]
    old = registry._resolve_color_source(ColormapSpec.model_validate(spec), name).colors
    colors = mcolors.to_rgba_array(old.colors if isinstance(old, mcolors.Colormap) else old)
    expected = colors.copy()
    for i, color in enumerate(spec.get("ncl_colors", [])):
        if color.lower() == "transparent":
            expected[i, 3] = 0
    actual = get_palette(name)
    assert actual.N == len(expected)
    np.testing.assert_array_equal(actual.colors, expected)
    np.testing.assert_array_equal(actual.get_under(), expected[0])
    np.testing.assert_array_equal(actual.get_over(), expected[-1])
    np.testing.assert_array_equal(actual.get_bad(), [0,0,0,0])
    audit = AUDIT[name]
    assert audit["count"] == len(expected)
    for row, old_rgba, new_rgba in zip(audit["rows"], colors, expected):
        np.testing.assert_array_equal(mcolors.to_rgba(row["old_rgba"]), old_rgba)
        np.testing.assert_array_equal(mcolors.to_rgba(row["new_rgba"]), new_rgba)


@pytest.mark.parametrize("name,count", [("cn_hgt20",20),("cn_ws15",15),("cn_cr19",19),("cn_pte",11),("cn_tdew",201),("cn_shr",119)])
def test_handwritten_and_composite_tables(name, count, old_rgb_tables):
    cmap = get_palette("cemc." + name)
    assert cmap.N == count
    np.testing.assert_array_equal(cmap.colors, mcolors.to_rgba_array(registry.get_rgb_table(name).colors))


def test_count_sampling_default_end_reverse_single_and_duplicates():
    colors = np.array(get_palette("cemc.cn_cr19").colors)
    np.testing.assert_array_equal(get_palette("cemc.cn_cr19", count=4).colors, colors[[0,6,12,18]])
    np.testing.assert_array_equal(get_palette("cemc.cn_cr19", count=4, start=18, end=0).colors, colors[[18,12,6,0]])
    np.testing.assert_array_equal(get_palette("cemc.cn_cr19", count=1, start=7).colors, colors[[7]])
    np.testing.assert_array_equal(get_palette("cemc.cn_cr19", count=5, start=0, end=2).colors, colors[[0,0,1,2,2]])
    assert get_palette("cemc.cape.cn_line", count=4).N == 4
    assert get_palette("cemc.cn_cr19", count=np.int64(2)).N == 2


@pytest.mark.parametrize("kwargs,error", [
    ({"count":0},ValueError), ({"count":-1},ValueError), ({"count":True},TypeError),
    ({"count":1.5},TypeError), ({"start":1},ValueError), ({"end":1},ValueError),
    ({"count":2,"start":-1},ValueError), ({"count":2,"end":19},ValueError),
    ({"count":1,"end":99},ValueError), ({"count":2,"start":False},TypeError),
])
def test_invalid_sampling_is_explicit(kwargs, error):
    with pytest.raises(error):
        get_palette("cemc.cn_cr19", **kwargs)


def test_specials_and_resources_do_not_mutate_across_calls():
    original = get_palette("cemc.cn_cr19")
    sampled = get_palette("cemc.cn_cr19", count=2, start=3, end=5)
    np.testing.assert_array_equal(sampled.get_under(), original.get_under())
    np.testing.assert_array_equal(sampled.get_over(), original.get_over())
    sampled.set_bad("red")
    original.colors[0] = (1,0,0,0)
    info = get_palette_info("cemc.cn_cr19")
    info["colors"][0] = "#00000000"
    info["provenance"]["cn_cr19"]["license"] = "changed"
    assert get_palette_info("cemc.cn_cr19")["colors"][0] == "#ffffffff"
    assert get_palette_info("cemc.cn_cr19")["provenance"]["cn_cr19"]["license"] == "Apache-2.0"
    np.testing.assert_array_equal(get_palette("cemc.cn_cr19").get_bad(), [0,0,0,0])


def test_transparent_and_case_insensitive_names():
    assert get_named_color("transparent") == (1,1,1,0)
    assert get_named_color("FORESTGREEN") == get_named_color("forestgreen")
    assert get_named_color("forestgreen") == (34/255,139/255,34/255,1)
    for item in SOURCES["named_colors"]["excluded"]:
        with pytest.raises(KeyError):
            get_named_color(item["name"])
    for source, spec in SOURCES.items():
        if spec["status"] == "unused":
            assert "source." + source not in palette_names()


def test_legacy_over_index_and_highlight_label_source_indices_are_recorded():
    info = get_palette_info("cemc.kidx.cn_fill")
    assert info["derivation"]["requested_indices"][-1] == 100
    assert info["derivation"]["resolved_indices"][-1] == 99
    np.testing.assert_array_equal(get_palette("cemc.kidx.cn_fill").colors[-1], get_palette("source.WhBlGrYeRe").colors[-1])
    mapping = json.loads((ROOT / "tools/style_palette_map.json").read_text())
    assert mapping["cemc.h_500.cn_dagpm"]["label_rgba"] == ["#ff0000ff"]
    assert mapping["cemc.h_500.cn_dagpm"]["highlights"][0]["color"] == "#000000ff"
    assert mapping["cemc.t_dew_t.cn_line"]["highlights"][0]["color"] == "#ff00ffff"
    assert mapping["cemc.t_dew_t.cn_t"]["highlights"][0]["color"] == [0,0,0,0]


def test_native_style_path_never_calls_ncl_reader(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("native palette used NCL reader")
    monkeypatch.setattr(registry, "get_ncl_colormap", forbidden)
    monkeypatch.setattr(registry, "generate_colormap_using_ncl_colors", forbidden)
    (tmp_path / "native.yml").write_text('''id: native
criteria: [{cemc_name: t}]
optimal: default
styles:
  default:
    type: contour
    fill: true
    levels: [0, 1, 2]
    colormap: {palette: cemc.rain.cn}
''')
    style = StyleRegistry([tmp_path]).get_style("native")
    assert style.colors.name == "cemc.rain.cn"
    assert style.colors.colors[0][3] == 0


@pytest.mark.parametrize("extra", [{"index":[0]}, {"count":2}, {"index_offset":-2}, {"spread_start":0}])
def test_native_style_transformations_require_named_derivatives(extra):
    with pytest.raises(ValueError, match="named derived palette"):
        ColormapSpec.model_validate({"palette":"cemc.rain.cn", **extra})


def test_reproducible_offline_conversion():
    result = subprocess.run([sys.executable, str(ROOT / "tools/convert_palettes.py"), "--check",
                             "--source-dir", str(ROOT / "src/cedarkit/plots/resources/colormap/ncl")],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout


def test_packaged_notice_links_exist():
    resource = ROOT / "src/cedarkit/plots/resources/palettes"
    for name in palette_names():
        info = get_palette_info(name)
        assert info["interpolation"] == "listed"
        for source in info["provenance"].values():
            assert (resource / source["notice"]).is_file()
            assert source["version"] and source["url"]
