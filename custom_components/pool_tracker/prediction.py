"""Transparent pool reading prediction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import exp
from typing import Any

from .const import (
    CONF_POOL_TYPE,
    CONF_TYPICALLY_COVERED,
    RECORD_TYPE_WATER_TEST,
    WATER_READING_CYA,
    WATER_READING_FREE_CHLORINE,
    WATER_READING_PH,
    WATER_READING_TOTAL_ALKALINITY,
    WATER_TEST_READING_UNITS,
)
from .models import PoolRecord, parse_utc

DEFAULT_STEP = timedelta(hours=6)
DEFAULT_HISTORY = timedelta(days=14)
DEFAULT_FUTURE = timedelta(days=3)
MAX_SERIES_POINTS = 80
MAX_ACTUAL_POINTS = 40


@dataclass(frozen=True, kw_only=True)
class PredictionContext:
    """Optional inputs that can shape pool reading predictions."""

    covered: bool | None = None
    sunlight: float | None = None
    rainfall: float | None = None
    temperature_f: float | None = None
    usage: float | None = None
    weather_condition: str | None = None
    sources: dict[str, str] | None = None

    def model_inputs(self) -> dict[str, Any]:
        """Return a compact serializable summary of available context."""
        inputs: dict[str, Any] = {}
        for key in (
            "covered",
            "sunlight",
            "rainfall",
            "temperature_f",
            "usage",
            "weather_condition",
        ):
            value = getattr(self, key)
            if value is not None:
                inputs[key] = value
        if self.sources:
            inputs["sources"] = self.sources
        return inputs


@dataclass(frozen=True, kw_only=True)
class ReadingPrediction:
    """Prediction result for one numeric water reading."""

    reading: str
    unit: str
    as_of: str
    value: float
    uncertainty: float
    lower_bound: float
    upper_bound: float
    last_actual_value: float
    last_actual_timestamp: str
    model_inputs: dict[str, Any]
    series: list[dict[str, Any]]
    actuals: list[dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class _ActualReading:
    timestamp: datetime
    value: float
    record_id: str
    testing_method: str | None


def build_prediction(
    records: list[PoolRecord],
    reading: str,
    *,
    now: datetime | None = None,
    pool_profile: dict[str, Any] | None = None,
    context: PredictionContext | None = None,
    step: timedelta = DEFAULT_STEP,
    history: timedelta = DEFAULT_HISTORY,
    future: timedelta = DEFAULT_FUTURE,
) -> ReadingPrediction | None:
    """Build a bounded prediction and chart series for one numeric reading."""
    actuals = _actual_readings(records, reading)
    if not actuals:
        return None

    now = _aware_utc(now)
    profile = pool_profile or {}
    context = context or PredictionContext()
    window_start = now - history
    future_end = now + future
    uncertainty_memory = 0.0
    series: list[dict[str, Any]] = []

    for index, actual in enumerate(actuals):
        if actual.timestamp >= window_start:
            series.append(
                _point(
                    actual.timestamp,
                    actual.value,
                    reading,
                    uncertainty=0,
                    is_actual=True,
                )
            )

        next_actual = actuals[index + 1] if index + 1 < len(actuals) else None
        segment_end = next_actual.timestamp if next_actual is not None else future_end
        cursor = max(actual.timestamp + step, window_start)
        while cursor < segment_end and cursor <= future_end:
            hours = _hours_between(actual.timestamp, cursor)
            predicted = _predict_value(
                reading, actual.value, hours, profile=profile, context=context
            )
            uncertainty = _uncertainty(reading, hours, uncertainty_memory)
            if cursor >= window_start:
                series.append(
                    _point(
                        cursor,
                        predicted,
                        reading,
                        uncertainty=uncertainty,
                        is_actual=False,
                    )
                )
            cursor += step

        if next_actual is not None:
            predicted_at_actual = _predict_value(
                reading,
                actual.value,
                _hours_between(actual.timestamp, next_actual.timestamp),
                profile=profile,
                context=context,
            )
            error = abs(next_actual.value - predicted_at_actual)
            uncertainty_memory = (
                error
                if uncertainty_memory == 0
                else (0.65 * uncertainty_memory + 0.35 * error)
            )

    last_actual = actuals[-1]
    current_hours = max(0.0, _hours_between(last_actual.timestamp, now))
    current_value = _predict_value(
        reading, last_actual.value, current_hours, profile=profile, context=context
    )
    current_uncertainty = _uncertainty(reading, current_hours, uncertainty_memory)
    current_point = _point(
        now,
        current_value,
        reading,
        uncertainty=current_uncertainty,
        is_actual=False,
    )
    if not series or series[-1]["timestamp"] != current_point["timestamp"]:
        series.append(current_point)

    bounded_series = _dedupe_points(series)[-MAX_SERIES_POINTS:]
    bounded_actuals = [
        {
            "timestamp": actual.timestamp.isoformat(),
            "value": round(actual.value, 3),
            "record_id": actual.record_id,
            **(
                {"testing_method": actual.testing_method}
                if actual.testing_method
                else {}
            ),
        }
        for actual in actuals
        if actual.timestamp >= window_start
    ][-MAX_ACTUAL_POINTS:]

    return ReadingPrediction(
        reading=reading,
        unit=WATER_TEST_READING_UNITS[reading],
        as_of=now.isoformat(),
        value=current_point["value"],
        uncertainty=current_point["uncertainty"],
        lower_bound=current_point["lower_bound"],
        upper_bound=current_point["upper_bound"],
        last_actual_value=round(last_actual.value, 3),
        last_actual_timestamp=last_actual.timestamp.isoformat(),
        model_inputs=context.model_inputs(),
        series=bounded_series,
        actuals=bounded_actuals,
    )


def _actual_readings(records: list[PoolRecord], reading: str) -> list[_ActualReading]:
    actuals: list[_ActualReading] = []
    for record in records:
        if record.get("type") != RECORD_TYPE_WATER_TEST:
            continue
        stored = record.get("readings", {}).get(reading)
        if stored is None:
            continue
        try:
            value = float(stored["value"])
        except TypeError, ValueError:
            continue
        actuals.append(
            _ActualReading(
                timestamp=parse_utc(record["event_timestamp"]),
                value=_clamp(reading, value),
                record_id=record["id"],
                testing_method=record.get("testing_method"),
            )
        )
    return sorted(actuals, key=lambda actual: (actual.timestamp, actual.record_id))


def _predict_value(
    reading: str,
    start_value: float,
    hours: float,
    *,
    profile: dict[str, Any],
    context: PredictionContext,
) -> float:
    days = max(0.0, hours / 24)
    if reading == WATER_READING_FREE_CHLORINE:
        value = start_value - _free_chlorine_daily_loss(profile, context) * days
    elif reading == WATER_READING_PH:
        target = 7.6
        rate = 0.035 + 0.015 * _usage_factor(context)
        value = target + (start_value - target) * exp(-rate * days)
    elif reading == WATER_READING_TOTAL_ALKALINITY:
        value = start_value - (0.35 * days) - (1.5 * _rainfall(context))
    elif reading == WATER_READING_CYA:
        value = start_value - (0.08 * days) - (0.35 * _rainfall(context))
    else:
        value = start_value
    return _clamp(reading, value)


def _free_chlorine_daily_loss(
    profile: dict[str, Any], context: PredictionContext
) -> float:
    pool_type = profile.get(CONF_POOL_TYPE)
    factor = 1.0
    if pool_type == "indoor":
        factor *= 0.35
    elif pool_type in {"spa", "swim_spa"}:
        factor *= 1.25

    covered = (
        context.covered
        if context.covered is not None
        else bool(profile.get(CONF_TYPICALLY_COVERED, False))
    )
    if covered:
        factor *= 0.55

    factor *= 0.85 + (0.45 * _sunlight_factor(context))
    factor *= _temperature_factor(context)
    factor *= 1.0 + (0.25 * _usage_factor(context))
    factor *= 1.0 + min(_rainfall(context) * 0.08, 0.25)
    return max(0.05, 0.45 * factor)


def _uncertainty(reading: str, hours: float, learned_error: float) -> float:
    days = max(0.0, hours / 24)
    base = {
        WATER_READING_FREE_CHLORINE: 0.12,
        WATER_READING_PH: 0.025,
        WATER_READING_TOTAL_ALKALINITY: 1.5,
        WATER_READING_CYA: 1.0,
    }[reading]
    growth = {
        WATER_READING_FREE_CHLORINE: 0.18,
        WATER_READING_PH: 0.025,
        WATER_READING_TOTAL_ALKALINITY: 1.6,
        WATER_READING_CYA: 0.9,
    }[reading]
    if hours <= 0:
        return 0.0
    return round(base + learned_error + (growth * days), 3)


def _point(
    timestamp: datetime,
    value: float,
    reading: str,
    *,
    uncertainty: float,
    is_actual: bool,
) -> dict[str, Any]:
    value = round(_clamp(reading, value), 3)
    uncertainty = round(max(0.0, uncertainty), 3)
    lower = _clamp(reading, value - uncertainty)
    upper = _clamp(reading, value + uncertainty)
    return {
        "timestamp": timestamp.isoformat(),
        "value": value,
        "uncertainty": uncertainty,
        "lower_bound": round(lower, 3),
        "upper_bound": round(upper, 3),
        "is_actual": is_actual,
    }


def _dedupe_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for point in points:
        existing = deduped.get(point["timestamp"])
        if existing is None or point["is_actual"]:
            deduped[point["timestamp"]] = point
    return [deduped[key] for key in sorted(deduped)]


def _clamp(reading: str, value: float) -> float:
    if reading == WATER_READING_PH:
        return min(14.0, max(0.0, value))
    return max(0.0, value)


def _sunlight_factor(context: PredictionContext) -> float:
    if context.sunlight is not None:
        sunlight = float(context.sunlight)
        if sunlight > 1:
            sunlight /= 100
        return min(1.0, max(0.0, sunlight))
    if context.weather_condition in {"sunny", "clear", "partlycloudy"}:
        return 0.75
    if context.weather_condition in {"cloudy", "rainy", "pouring"}:
        return 0.25
    return 0.5


def _temperature_factor(context: PredictionContext) -> float:
    if context.temperature_f is None:
        return 1.0
    temperature = context.temperature_f
    if temperature >= 90:
        return 1.25
    if temperature >= 80:
        return 1.12
    if temperature <= 60:
        return 0.75
    if temperature <= 70:
        return 0.9
    return 1.0


def _usage_factor(context: PredictionContext) -> float:
    if context.usage is None:
        return 0.0
    return min(1.0, max(0.0, float(context.usage)))


def _rainfall(context: PredictionContext) -> float:
    if context.rainfall is None:
        return 0.0
    return max(0.0, float(context.rainfall))


def _hours_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600


def _aware_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
