"""Tests for transparent pool reading predictions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.pool_tracker.const import (
    CONF_POOL_TYPE,
    CONF_TYPICALLY_COVERED,
    WATER_READING_CYA,
    WATER_READING_FREE_CHLORINE,
    WATER_READING_PH,
)
from custom_components.pool_tracker.models import build_water_test_record
from custom_components.pool_tracker.prediction import (
    PredictionContext,
    build_prediction,
)


def test_prediction_returns_none_without_readings() -> None:
    """A prediction needs at least one actual reading."""
    assert build_prediction([], WATER_READING_FREE_CHLORINE) is None


def test_single_reading_decays_and_uncertainty_grows() -> None:
    """Free chlorine decays from the latest actual reading over time."""
    start = datetime(2026, 6, 10, 12, tzinfo=UTC)
    prediction = build_prediction(
        [
            build_water_test_record(
                pool_id="pool",
                readings={WATER_READING_FREE_CHLORINE: 3.0},
                event_timestamp=start,
            )
        ],
        WATER_READING_FREE_CHLORINE,
        now=start + timedelta(days=2),
    )

    assert prediction is not None
    assert prediction.value < 3.0
    assert prediction.uncertainty > 0
    assert prediction.lower_bound < prediction.value < prediction.upper_bound


def test_actual_reading_resets_uncertainty_to_zero() -> None:
    """Actual reading points are exact anchors in the prediction series."""
    start = datetime(2026, 6, 10, 12, tzinfo=UTC)
    actual_time = start + timedelta(days=1)
    prediction = build_prediction(
        [
            build_water_test_record(
                pool_id="pool",
                readings={WATER_READING_FREE_CHLORINE: 3.0},
                event_timestamp=start,
                record_id="first",
            ),
            build_water_test_record(
                pool_id="pool",
                readings={WATER_READING_FREE_CHLORINE: 2.0},
                event_timestamp=actual_time,
                record_id="second",
            ),
        ],
        WATER_READING_FREE_CHLORINE,
        now=actual_time,
    )

    assert prediction is not None
    actual_point = next(
        point
        for point in prediction.series
        if point["timestamp"] == actual_time.isoformat()
    )
    assert actual_point["is_actual"] is True
    assert actual_point["uncertainty"] == 0
    assert prediction.uncertainty == 0


def test_past_prediction_error_increases_future_uncertainty() -> None:
    """A bad prior prediction makes later estimates less certain."""
    start = datetime(2026, 6, 10, 12, tzinfo=UTC)
    future_time = start + timedelta(days=2)
    baseline = build_prediction(
        [
            build_water_test_record(
                pool_id="pool",
                readings={WATER_READING_FREE_CHLORINE: 3.0},
                event_timestamp=start,
            )
        ],
        WATER_READING_FREE_CHLORINE,
        now=future_time,
    )
    learned = build_prediction(
        [
            build_water_test_record(
                pool_id="pool",
                readings={WATER_READING_FREE_CHLORINE: 3.0},
                event_timestamp=start,
            ),
            build_water_test_record(
                pool_id="pool",
                readings={WATER_READING_FREE_CHLORINE: 0.2},
                event_timestamp=start + timedelta(days=1),
            ),
        ],
        WATER_READING_FREE_CHLORINE,
        now=future_time,
    )

    assert baseline is not None
    assert learned is not None
    assert learned.uncertainty > baseline.uncertainty


def test_missing_context_matches_neutral_defaults() -> None:
    """Missing optional context is treated as neutral."""
    start = datetime(2026, 6, 10, 12, tzinfo=UTC)
    record = build_water_test_record(
        pool_id="pool",
        readings={WATER_READING_FREE_CHLORINE: 3.0},
        event_timestamp=start,
    )

    implicit = build_prediction(
        [record],
        WATER_READING_FREE_CHLORINE,
        now=start + timedelta(days=1),
    )
    explicit = build_prediction(
        [record],
        WATER_READING_FREE_CHLORINE,
        now=start + timedelta(days=1),
        context=PredictionContext(),
    )

    assert implicit == explicit


def test_cover_weather_and_usage_change_chlorine_prediction_directionally() -> None:
    """Context inputs alter free chlorine decay in expected directions."""
    start = datetime(2026, 6, 10, 12, tzinfo=UTC)
    records = [
        build_water_test_record(
            pool_id="pool",
            readings={WATER_READING_FREE_CHLORINE: 3.0},
            event_timestamp=start,
        )
    ]

    protected = build_prediction(
        records,
        WATER_READING_FREE_CHLORINE,
        now=start + timedelta(days=1),
        pool_profile={CONF_POOL_TYPE: "indoor", CONF_TYPICALLY_COVERED: True},
        context=PredictionContext(covered=True, sunlight=0, temperature_f=60, usage=0),
    )
    exposed = build_prediction(
        records,
        WATER_READING_FREE_CHLORINE,
        now=start + timedelta(days=1),
        pool_profile={CONF_POOL_TYPE: "outdoor"},
        context=PredictionContext(
            covered=False,
            sunlight=100,
            temperature_f=95,
            usage=1,
            rainfall=1,
        ),
    )

    assert protected is not None
    assert exposed is not None
    assert exposed.value < protected.value


def test_prediction_values_are_clamped() -> None:
    """Predictions stay inside physical reading bounds."""
    start = datetime(2026, 6, 10, 12, tzinfo=UTC)
    ph_prediction = build_prediction(
        [
            build_water_test_record(
                pool_id="pool",
                readings={WATER_READING_PH: 20},
                event_timestamp=start,
            )
        ],
        WATER_READING_PH,
        now=start,
    )
    cya_prediction = build_prediction(
        [
            build_water_test_record(
                pool_id="pool",
                readings={WATER_READING_CYA: -5},
                event_timestamp=start,
            )
        ],
        WATER_READING_CYA,
        now=start,
    )

    assert ph_prediction is not None
    assert ph_prediction.value == 14
    assert cya_prediction is not None
    assert cya_prediction.value == 0
