"""Workflow field requests enter the common query protocol without node identity."""

from dataclasses import replace

import pytest

from cedarkit_query import Query, QueryError, Request
from cedarkit.plots.workflow.plan import BoundFieldRequest, public_request_from_field_request
from cedarkit.plots.workflow.plan.model import FieldRequest


def _field():
    return FieldRequest("default", "cedarkit.t2m", Query(parameter="cedarkit.t2m",
                        level_type="height_above_ground", level=2, level_unit="m"),
                        "2026-08-30T00:00:00Z", "P1DT0H0M0S", "one")


def test_resolved_product_field_maps_to_current_request_without_opening_file(tmp_path):
    key = _field()
    source = {"kind": "file", "path": str(tmp_path / "arbitrary.grib2")}
    direct = public_request_from_field_request(key, source=source)
    bound = public_request_from_field_request(BoundFieldRequest("read:one", key, "recipe"),
                                              source=source)
    assert direct == bound
    assert direct.queries[0].parameter == "cedarkit.t2m"
    assert direct.queries[0].level_type == "height_above_ground"
    assert direct.queries[0].level == 2
    assert direct.queries[0].step == "PT86400S"
    assert direct.queries[0].time == "2026-08-30T00:00:00Z"
    assert direct.queries[0].valid_time == "2026-08-31T00:00:00Z"
    assert direct.completeness == "available"
    assert set(direct.to_dict()) == {"api_version", "source", "queries", "completeness"}
    assert "read:one" not in str(direct.to_dict())
    assert not (tmp_path / "arbitrary.grib2").exists()
    for extension in ("json", "yaml"):
        path = tmp_path / f"request.{extension}"
        direct.dump(path)
        assert Request.load(path) == direct


@pytest.mark.parametrize("cardinality", ("one", "first", "all"))
def test_cardinality_is_an_execution_choice_and_timestamp_forecast_is_bound(cardinality, tmp_path):
    key = _field()
    request = public_request_from_field_request(replace(key, cardinality=cardinality,
        forecast_time="2026-08-31T00:00:00Z"), source={"kind": "file", "path": str(tmp_path / "field.grib")})
    assert request.queries[0].step == "PT86400S"
    assert "policy" not in request.to_dict()


def test_unbound_time_and_conflicting_query_are_structured_errors(tmp_path):
    source = {"kind": "file", "path": str(tmp_path / "field.grib")}
    with pytest.raises(QueryError) as caught:
        public_request_from_field_request(replace(_field(), start_time=None), source=source)
    assert caught.value.code == "invalid_query"
    conflicting = replace(_field(), query=Query(parameter="cedarkit.t2m", member=3, step="PT6H"))
    with pytest.raises(QueryError) as caught:
        public_request_from_field_request(conflicting, source=source)
    assert caught.value.code == "constraint_conflict"
