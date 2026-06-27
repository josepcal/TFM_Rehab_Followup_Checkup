"""Unit tests for the norms endpoints (UC-09 extension).

All tests use a FakeSession — no live DB required. They exercise the router
functions directly, injecting fakes for db and principal (bypassing FastAPI
dependency injection).
"""

import uuid

import pytest
from fastapi import HTTPException

from app.norms import router as norms_router
from app.norms.schemas import MetricNormOut


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MEDICAL = {"sub": "doc-sub", "role": "medical"}
PATIENT = {"sub": "pat-sub", "role": "patient"}
TECHNICIAN = {"sub": "tec-sub", "role": "technician"}
ANONYMOUS = {}


NORM_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Fake session
# ---------------------------------------------------------------------------


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, scalar_value=None, scalars_rows=None):
        self._scalar_value = scalar_value
        self._scalars_rows = scalars_rows or []

    def scalar(self, _statement):
        return self._scalar_value

    def scalars(self, _statement):
        return FakeScalarResult(self._scalars_rows)


# ---------------------------------------------------------------------------
# Fake ORM rows
# ---------------------------------------------------------------------------


def _norm_row(
    metric_code: str = "jitter_local_pct",
    direction: str = "lower_better",
    good_min=None,
    good_max: float = 1.04,
    poor_min: float = 3.0,
    poor_max=None,
    label: str = "Jitter (local)",
    unit: str = "%",
):
    return type(
        "MetricNorm",
        (),
        {
            "norm_id": NORM_ID,
            "metric_code": metric_code,
            "label": label,
            "unit": unit,
            "direction": direction,
            "sex": None,
            "age_min": None,
            "age_max": None,
            "good_min": good_min,
            "good_max": good_max,
            "poor_min": poor_min,
            "poor_max": poor_max,
            "source": "dysarthria_analysis_v1",
            "version": 1,
            "created_at": None,
        },
    )()


# ---------------------------------------------------------------------------
# GET /norms
# ---------------------------------------------------------------------------


class TestListNorms:
    def test_returns_200_with_list(self):
        row = _norm_row()
        session = FakeSession(scalars_rows=[row])
        result = norms_router.list_norms(MEDICAL, session)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_empty_list_when_no_norms(self):
        session = FakeSession(scalars_rows=[])
        result = norms_router.list_norms(MEDICAL, session)
        assert result == []

    def test_patient_can_access(self):
        session = FakeSession(scalars_rows=[])
        result = norms_router.list_norms(PATIENT, session)
        assert isinstance(result, list)

    def test_technician_can_access(self):
        session = FakeSession(scalars_rows=[])
        result = norms_router.list_norms(TECHNICIAN, session)
        assert isinstance(result, list)

    def test_result_items_are_metric_norm_out(self):
        row = _norm_row()
        session = FakeSession(scalars_rows=[row])
        result = norms_router.list_norms(MEDICAL, session)
        assert isinstance(result[0], MetricNormOut)

    def test_direction_field_preserved(self):
        row = _norm_row(direction="lower_better")
        session = FakeSession(scalars_rows=[row])
        result = norms_router.list_norms(MEDICAL, session)
        assert result[0].direction == "lower_better"


# ---------------------------------------------------------------------------
# GET /norms/{metric_code}
# ---------------------------------------------------------------------------


class TestGetNorm:
    def test_returns_norm_when_found(self):
        row = _norm_row(metric_code="jitter_local_pct")
        session = FakeSession(scalar_value=row)
        result = norms_router.get_norm("jitter_local_pct", MEDICAL, session)
        assert isinstance(result, MetricNormOut)
        assert result.metric_code == "jitter_local_pct"

    def test_returns_404_when_not_found(self):
        session = FakeSession(scalar_value=None)
        with pytest.raises(HTTPException) as exc:
            norms_router.get_norm("nonexistent_xyz_metric", MEDICAL, session)
        assert exc.value.status_code == 404
        assert "nonexistent_xyz_metric" in exc.value.detail

    def test_404_detail_contains_metric_code(self):
        session = FakeSession(scalar_value=None)
        with pytest.raises(HTTPException) as exc:
            norms_router.get_norm("unknown_metric_abc", MEDICAL, session)
        assert "unknown_metric_abc" in exc.value.detail

    def test_higher_better_norm_fields(self):
        row = _norm_row(
            metric_code="hnr_db",
            direction="higher_better",
            good_min=20.0,
            good_max=None,
            poor_min=None,
            poor_max=7.0,
            label="HNR",
            unit="dB",
        )
        session = FakeSession(scalar_value=row)
        result = norms_router.get_norm("hnr_db", MEDICAL, session)
        assert result.direction == "higher_better"
        assert result.good_min == 20.0
        assert result.good_max is None
        assert result.poor_min is None
        assert result.poor_max == 7.0

    def test_patient_can_access(self):
        row = _norm_row()
        session = FakeSession(scalar_value=row)
        result = norms_router.get_norm("jitter_local_pct", PATIENT, session)
        assert result.metric_code == "jitter_local_pct"
