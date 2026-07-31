"""Unit tests for the plot definition loader (cedarkit.plots.engine.loader)."""
import types
from dataclasses import dataclass

import pandas as pd
import pytest

from cedarkit.plots.engine.loader import (
    Metadata,
    convert_metadata,
    create_metadata,
    get_metadata_class,
    get_plot_module,
    item_processor_map,
    process_area_range,
    process_forecast_time,
    process_start_time,
)
from cedarkit.plots.types import AreaRange


class TestGetPlotModule:
    def test_loads_module_by_plot_type(self):
        module = get_plot_module("types", base_module_name="cedarkit.plots")
        assert isinstance(module, types.ModuleType)
        assert module.__name__ == "cedarkit.plots.types"

    def test_nested_plot_type(self):
        module = get_plot_module(
            "engine.loader", base_module_name="cedarkit.plots"
        )
        assert module.__name__ == "cedarkit.plots.engine.loader"

    def test_unknown_plot_type_raises(self):
        with pytest.raises(ModuleNotFoundError):
            get_plot_module("no_such_plot", base_module_name="cedarkit.plots")


class TestGetMetadataClass:
    def test_returns_plot_metadata_attribute(self):
        @dataclass
        class PlotMetadata:
            system_name: str = ""

        module = types.SimpleNamespace(PlotMetadata=PlotMetadata)
        assert get_metadata_class(module) is PlotMetadata


class TestCreateMetadata:
    def test_fills_all_settings(self):
        metadata = create_metadata(
            metadata_class=Metadata,
            plot_settings={"system_name": "CMA-GFS", "some_key": 1},
            processor_map={},
        )
        assert metadata.system_name == "CMA-GFS"
        assert metadata.some_key == 1

    def test_applies_processor_for_mapped_keys(self):
        metadata = create_metadata(
            metadata_class=Metadata,
            plot_settings={
                "start_time": "2024111300",
                "forecast_time": "24h",
                "area_range": {
                    "start_longitude": 70, "end_longitude": 140,
                    "start_latitude": 15, "end_latitude": 55,
                },
                "interval": "3h",
            },
            processor_map=item_processor_map,
        )
        assert metadata.start_time == pd.Timestamp("2024-11-13 00:00")
        assert metadata.forecast_time == pd.Timedelta(hours=24)
        assert metadata.area_range == AreaRange(70, 140, 15, 55)
        assert metadata.interval == pd.Timedelta(hours=3)

    def test_unmapped_keys_pass_through(self):
        metadata = create_metadata(
            metadata_class=Metadata,
            plot_settings={"start_time": "not-a-time"},
            processor_map={},
        )
        assert metadata.start_time == "not-a-time"


class TestConvertMetadata:
    def test_copies_only_matching_fields(self):
        @dataclass
        class PlotMetadata:
            system_name: str = ""
            forecast_time: object = None

        from_metadata = Metadata()
        from_metadata.system_name = "CMA-GFS"
        from_metadata.forecast_time = pd.Timedelta(hours=24)
        from_metadata.unrelated = "ignored"

        to_metadata = PlotMetadata()
        convert_metadata(from_metadata=from_metadata, to_metadata=to_metadata)

        assert to_metadata.system_name == "CMA-GFS"
        assert to_metadata.forecast_time == pd.Timedelta(hours=24)
        assert not hasattr(to_metadata, "unrelated")


class TestProcessors:
    @pytest.mark.parametrize("item,expected", [
        ("2024111300", pd.Timestamp("2024-11-13 00:00")),
        ("202411130030", pd.Timestamp("2024-11-13 00:30")),
        ("2024-11-13 06:00:00", pd.Timestamp("2024-11-13 06:00")),
    ])
    def test_process_start_time_from_string(self, item, expected):
        assert process_start_time(item) == expected

    def test_process_start_time_passthrough(self):
        ts = pd.Timestamp("2024-11-13")
        assert process_start_time(ts) is ts

    def test_process_start_time_rejects_other_types(self):
        with pytest.raises(ValueError, match="type is not supported"):
            process_start_time(2024111300)

    def test_process_forecast_time_from_string(self):
        assert process_forecast_time("24h") == pd.Timedelta(hours=24)

    def test_process_forecast_time_rejects_other_types(self):
        with pytest.raises(ValueError, match="type is not supported"):
            process_forecast_time(24)

    def test_process_area_range_from_dict(self):
        area = process_area_range({
            "start_longitude": 70, "end_longitude": 140,
            "start_latitude": 15, "end_latitude": 55,
        })
        assert area == AreaRange(70, 140, 15, 55)

    def test_process_area_range_passthrough(self):
        area = AreaRange(70, 140, 15, 55)
        assert process_area_range(area) is area

    def test_process_area_range_rejects_other_types(self):
        with pytest.raises(ValueError, match="type is not supported"):
            process_area_range("70,140,15,55")

    def test_item_processor_map_covers_documented_keys(self):
        assert set(item_processor_map) == {
            "start_time", "forecast_time", "area_range", "interval",
        }
        assert item_processor_map["interval"] is process_forecast_time
