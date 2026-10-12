"""Workflow field requests enter the common query protocol without node identity."""

from dataclasses import replace

import pytest

from cedarkit_query import QueryError
from reki.readers.grib.config import resolve_parameter
from cedarkit.plots.workflow.plan import BoundFieldRequest, public_request_from_field_request
from cedarkit.plots.workflow.plan.model import FieldRequest


def _field():
    return FieldRequest("default", "cedarkit.t2m", resolve_parameter("cedarkit.t2m").query,
                        "2026-08-30T00:00:00Z", "P1DT0H0M0S", "one")


def test_resolved_product_field_maps_to_one_canonical_request():
    key = _field()
    direct = public_request_from_field_request(key, dataset="grid", native_parameter="2t")
    bound = public_request_from_field_request(BoundFieldRequest("read:one", key, "recipe"),
                                              dataset="grid", native_parameter="2t")
    assert direct == bound
    assert direct.query.parameter == "cedarkit.t2m"
    assert direct.query.vertical == {"type": "heightAboveGround", "unit": "m", "values": 2}
    assert direct.query.lead_time == "PT86400S"
    assert "read:one" not in str(direct.to_dict())


def test_unmapped_native_selector_and_legacy_first_fail():
    key = _field()
    with pytest.raises(QueryError, match="verified mapping"):
        public_request_from_field_request(key, dataset="grid")
    with pytest.raises(QueryError) as caught:
        public_request_from_field_request(replace(key, cardinality="first"),
                                          dataset="grid", native_parameter="2t")
    assert caught.value.code == "unsupported"
