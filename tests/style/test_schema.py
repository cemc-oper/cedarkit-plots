"""Unit tests for the style YAML schema (cedarkit.plots.style.schema)."""
import pytest

from cedarkit.plots.style.schema import (
    ColormapSpec,
    CriteriaEntry,
    HighlightEntry,
    LabelSpec,
    StyleFile,
    StyleFileError,
    StyleVariant,
    load_style_file,
)


def write_style(tmp_path, name: str, text: str):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


class TestCriteriaEntry:
    def test_single_key(self):
        entry = CriteriaEntry(cemc_name="t2m")
        assert entry.cemc_name == "t2m"

    def test_numeric_level_type(self):
        entry = CriteriaEntry(eccodes_name="t", first_level_type=103, first_level=2)
        assert entry.first_level_type == 103

    def test_string_level_type_rejected(self):
        with pytest.raises(ValueError):
            CriteriaEntry(first_level_type="heightAboveGround")

    def test_empty_entry_rejected(self):
        with pytest.raises(ValueError, match="at least one key"):
            CriteriaEntry()

    def test_unknown_key_rejected(self):
        with pytest.raises(ValueError):
            CriteriaEntry(shortName="2t")


class TestColormapSpec:
    def test_ncl_source(self):
        spec = ColormapSpec(ncl="BlAqGrYeOrReVi200", index=[2, 18], index_offset=-2)
        assert spec.ncl == "BlAqGrYeOrReVi200"

    def test_exactly_one_source(self):
        with pytest.raises(ValueError, match="exactly one source"):
            ColormapSpec(ncl="a", rgb_table="b")
        with pytest.raises(ValueError, match="exactly one source"):
            ColormapSpec()

    def test_index_only_with_ncl_or_rgb_table(self):
        with pytest.raises(ValueError, match="only valid with ncl"):
            ColormapSpec(colors=["red"], index=[1])
        with pytest.raises(ValueError, match="only valid with ncl"):
            ColormapSpec(ncl_colors=["White"], count=3)

    def test_count_only_with_ncl(self):
        with pytest.raises(ValueError, match="only valid with ncl"):
            ColormapSpec(rgb_table="t", count=3)
        spec = ColormapSpec(ncl="WhBlGrYeRe", count=10, spread_start=98, spread_end=0)
        assert spec.count == 10


class TestHighlightEntry:
    def test_linewidth_only(self):
        entry = HighlightEntry(level=588, linewidth=1.4)
        assert entry.level == 588

    def test_no_effect_rejected(self):
        with pytest.raises(ValueError, match="must set"):
            HighlightEntry(level=588)

    def test_color_exclusive(self):
        with pytest.raises(ValueError, match="both"):
            HighlightEntry(level=588, color="red", color_index=1)


class TestLabelSpec:
    def test_color_exclusive(self):
        with pytest.raises(ValueError, match="only one"):
            LabelSpec(color="black", color_index=15)
        with pytest.raises(ValueError, match="only one"):
            LabelSpec(color="black", line_colors=True)


class TestStyleVariant:
    def test_contour_defaults(self):
        variant = StyleVariant(type="contour")
        assert variant.fill is False

    def test_units_known(self):
        variant = StyleVariant(type="contour", units="celsius")
        assert variant.units == "celsius"

    def test_units_unknown_rejected(self):
        with pytest.raises(ValueError, match="unknown units"):
            StyleVariant(type="contour", units="fahrenheit")

    def test_barb_rejects_contour_keys(self):
        with pytest.raises(ValueError, match="contour keys"):
            StyleVariant(type="barb", fill=True)
        with pytest.raises(ValueError, match="contour keys"):
            StyleVariant(type="barb", label=LabelSpec())

    def test_contour_rejects_barb_keys(self):
        with pytest.raises(ValueError, match="barb keys"):
            StyleVariant(type="contour", barbcolor="black")


class TestStyleFile:
    def test_optimal_must_exist(self):
        with pytest.raises(ValueError, match="optimal"):
            StyleFile(
                id="t2m",
                criteria=[{"cemc_name": "t2m"}],
                optimal="missing",
                styles={"cn": {"type": "contour"}},
            )

    def test_levels_forms(self):
        variant = StyleVariant(type="contour", levels=[-12, -8, 0])
        assert variant.levels == [-12, -8, 0]
        variant = StyleVariant(type="contour", levels={"range": [-40, 41, 2]})
        assert variant.levels.range == [-40, 41, 2]
        variant = StyleVariant(type="contour", levels={"linspace": [500, 588, 23]})
        assert variant.levels.linspace == [500, 588, 23]
        variant = StyleVariant(type="contour", levels={"step": 4.0, "reference": 0.0})
        assert variant.levels.step == 4.0

    def test_levels_invalid_form(self):
        with pytest.raises(ValueError):
            StyleVariant(type="contour", levels={"arange": [1, 2, 3]})


class TestLoadStyleFile:
    def test_load_valid(self, tmp_path):
        path = write_style(tmp_path, "t2m.yml", """
id: t2m
criteria:
  - cemc_name: t2m
  - eccodes_name: 2t
optimal: cn
styles:
  cn:
    type: contour
    levels: [-12, 0, 12]
    fill: true
    units: celsius
""")
        style_file = load_style_file(path)
        assert style_file.id == "t2m"
        assert len(style_file.criteria) == 2
        assert style_file.styles["cn"].units == "celsius"

    def test_id_must_match_file_name(self, tmp_path):
        path = write_style(tmp_path, "t2m.yml", """
id: other
criteria:
  - cemc_name: t2m
styles:
  cn: { type: contour }
""")
        with pytest.raises(StyleFileError, match="does not match file name"):
            load_style_file(path)

    def test_invalid_yaml_reports_file_and_line(self, tmp_path):
        path = write_style(tmp_path, "bad.yml", "id: bad\ncriteria:\n  - cemc_name: x\n   bad indent\n")
        with pytest.raises(StyleFileError) as exc_info:
            load_style_file(path)
        message = str(exc_info.value)
        assert "bad.yml" in message
        assert "line" in message

    def test_schema_error_reports_file(self, tmp_path):
        path = write_style(tmp_path, "bad.yml", """
id: bad
criteria:
  - cemc_name: x
styles:
  cn:
    type: contour
    units: fahrenheit
""")
        with pytest.raises(StyleFileError) as exc_info:
            load_style_file(path)
        message = str(exc_info.value)
        assert "bad.yml" in message
        assert "validation failed" in message

    def test_non_mapping_rejected(self, tmp_path):
        path = write_style(tmp_path, "bad.yml", "- just\n- a\n- list\n")
        with pytest.raises(StyleFileError, match="mapping"):
            load_style_file(path)
