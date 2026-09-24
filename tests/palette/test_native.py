"""Native palette resources match the reviewed conversion snapshots."""
import json
from pathlib import Path
import subprocess
import sys

import matplotlib.colors as mcolors
import numpy as np
import pytest

from cedarkit.plots.palette import (
    get_named_color,
    get_palette,
    get_palette_info,
    palette_names,
)
from cedarkit.plots.style import StyleRegistry

ROOT = Path(__file__).resolve().parents[2]
SOURCES = json.loads((ROOT / "tools/palette_sources.json").read_text())["sources"]
AUDIT = json.loads((ROOT / "tools/palette_audit.json").read_text())


@pytest.mark.parametrize("name", sorted(AUDIT))
def test_every_palette_matches_reviewed_rgba_snapshot(name):
    audit = AUDIT[name]
    expected = np.asarray(
        [mcolors.to_rgba(row["new_rgba"]) for row in audit["rows"]]
    )
    cmap = get_palette(name)

    assert cmap.N == audit["count"] == len(expected)
    np.testing.assert_array_equal(mcolors.to_rgba_array(cmap.colors), expected)
    np.testing.assert_array_equal(cmap.get_under(), expected[0])
    np.testing.assert_array_equal(cmap.get_over(), expected[-1])
    np.testing.assert_array_equal(cmap.get_bad(), [0, 0, 0, 0])


def test_palette_catalog_count_matches_audit():
    assert len(palette_names()) == len(AUDIT) == 51
    assert set(palette_names()) == set(AUDIT)
    assert sum(entry["count"] for entry in AUDIT.values()) == 1766


def test_count_sampling_default_end_reverse_single_and_duplicates():
    colors = np.array(get_palette("cemc.cn_cr19").colors)
    np.testing.assert_array_equal(get_palette("cemc.cn_cr19", count=4).colors, colors[[0, 6, 12, 18]])
    np.testing.assert_array_equal(get_palette("cemc.cn_cr19", count=4, start=18, end=0).colors, colors[[18, 12, 6, 0]])
    np.testing.assert_array_equal(get_palette("cemc.cn_cr19", count=1, start=7).colors, colors[[7]])
    np.testing.assert_array_equal(get_palette("cemc.cn_cr19", count=5, start=0, end=2).colors, colors[[0, 0, 1, 2, 2]])
    assert get_palette("cemc.cape.cn_line", count=4).N == 4
    assert get_palette("cemc.cn_cr19", count=np.int64(2)).N == 2


@pytest.mark.parametrize("kwargs,error", [
    ({"count": 0}, ValueError), ({"count": -1}, ValueError),
    ({"count": True}, TypeError), ({"count": 1.5}, TypeError),
    ({"start": 1}, ValueError), ({"end": 1}, ValueError),
    ({"count": 2, "start": -1}, ValueError),
    ({"count": 2, "end": 19}, ValueError),
    ({"count": 1, "end": 99}, ValueError),
    ({"count": 2, "start": False}, TypeError),
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
    original.colors[0] = (1, 0, 0, 0)
    info = get_palette_info("cemc.cn_cr19")
    info["colors"][0] = "#00000000"
    info["provenance"]["cn_cr19"]["license"] = "changed"
    assert get_palette_info("cemc.cn_cr19")["colors"][0] == "#ffffffff"
    assert get_palette_info("cemc.cn_cr19")["provenance"]["cn_cr19"]["license"] == "Apache-2.0"
    np.testing.assert_array_equal(get_palette("cemc.cn_cr19").get_bad(), [0, 0, 0, 0])


def test_transparent_and_case_insensitive_names():
    assert get_named_color("transparent") == (1, 1, 1, 0)
    assert get_named_color("FORESTGREEN") == get_named_color("forestgreen")
    assert get_named_color("forestgreen") == (34 / 255, 139 / 255, 34 / 255, 1)
    for item in SOURCES["named_colors"]["excluded"]:
        with pytest.raises(KeyError):
            get_named_color(item["name"])
    for source, spec in SOURCES.items():
        if spec["status"] == "unused":
            prefix = "cemc." if source.startswith("cn_") else "source."
            assert prefix + source not in palette_names()


def test_palette_derivation_records_clamped_indices_and_migrated_overlays():
    info = get_palette_info("cemc.kidx.cn_fill")
    assert info["derivation"]["requested_indices"][-1] == 100
    assert info["derivation"]["resolved_indices"][-1] == 99
    np.testing.assert_array_equal(get_palette("cemc.kidx.cn_fill").colors[-1], get_palette("source.WhBlGrYeRe").colors[-1])
    mapping = json.loads((ROOT / "tools/style_palette_map.json").read_text())
    assert mapping["cemc.h_500.cn_dagpm"]["label_rgba"] == ["#ff0000ff"]
    assert mapping["cemc.h_500.cn_dagpm"]["highlights"][0]["color"] == "#000000ff"
    assert mapping["cemc.t_dew_t.cn_line"]["highlights"][0]["color"] == "#ff00ffff"
    assert mapping["cemc.t_dew_t.cn_t"]["highlights"][0]["color"] == [0, 0, 0, 0]


def test_native_style_loads_palette_without_external_resources(tmp_path):
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


def test_reproducible_offline_conversion_uses_reviewed_snapshots():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/convert_palettes.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_packaged_notice_links_exist():
    resource = ROOT / "src/cedarkit/plots/resources/palettes"
    for name in palette_names():
        info = get_palette_info(name)
        assert info["interpolation"] == "listed"
        for source in info["provenance"].values():
            assert (resource / source["notice"]).is_file()
            assert source["version"] and source["url"]
