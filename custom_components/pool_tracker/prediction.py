"""Transparent pool reading prediction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import exp
from typing import Any

from .const import (
    CONF_POOL_TYPE,
    CONF_POOL_VOLUME,
    CONF_POOL_VOLUME_UNIT,
    CONF_TYPICALLY_COVERED,
    RECORD_TYPE_CHEMICAL_ADDITION,
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
DEFAULT_POOL_VOLUME_GAL = 10000
DEFAULT_SPA_VOLUME_GAL = 400
DEFAULT_SWIM_SPA_VOLUME_GAL = 1500
LITERS_PER_GALLON = 3.785411784
POUNDS_PER_GALLON_WATER = 8.345404

CHLORINE_AVAILABLE_FRACTIONS = {
    "dichlor": 0.56,
    "sodium dichlor": 0.56,
    "sodium dichloro": 0.56,
    "trichlor": 0.9,
    "cal hypo": 0.65,
    "cal-hypo": 0.65,
    "calcium hypochlorite": 0.65,
    "liquid chlorine": 0.1,
    "bleach": 0.06,
    "sodium hypochlorite": 0.1,
}


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
    last_actual_value: float | None
    last_actual_timestamp: str | None
    model_inputs: dict[str, Any]
    series: list[dict[str, Any]]
    actuals: list[dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class _ActualReading:
    timestamp: datetime
    value: float
    record_id: str
    testing_method: str | None


@dataclass(frozen=True, kw_only=True)
class _ChemicalEffect:
    timestamp: datetime
    record_id: str
    chemical: str
    amount: float
    unit: str
    free_chlorine_delta: float


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
    now = _aware_utc(now)
    profile = pool_profile or {}
    context = context or PredictionContext()
    chemical_effects = _chemical_effects(records, pool_profile=profile)
    actuals = _actual_readings(records, reading)
    if not actuals:
        if reading != WATER_READING_FREE_CHLORINE:
            return None
        return _build_chemical_only_prediction(
            chemical_effects,
            now=now,
            profile=profile,
            context=context,
            step=step,
            history=history,
            future=future,
        )

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
            predicted = _predict_at(
                reading,
                actual.value,
                actual.timestamp,
                cursor,
                profile=profile,
                context=context,
                chemical_effects=chemical_effects,
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
                chemical_effects=chemical_effects,
                start=actual.timestamp,
                end=next_actual.timestamp,
            )
            error = abs(next_actual.value - predicted_at_actual)
            uncertainty_memory = (
                error
                if uncertainty_memory == 0
                else (0.65 * uncertainty_memory + 0.35 * error)
            )

    last_actual = actuals[-1]
    current_hours = max(0.0, _hours_between(last_actual.timestamp, now))
    current_value = _predict_at(
        reading,
        last_actual.value,
        last_actual.timestamp,
        now,
        profile=profile,
        context=context,
        chemical_effects=chemical_effects,
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
        model_inputs=_model_inputs(
            context,
            [
                effect
                for effect in chemical_effects
                if reading == WATER_READING_FREE_CHLORINE
                and last_actual.timestamp < effect.timestamp <= now
            ],
            profile=profile,
        ),
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


def _build_chemical_only_prediction(
    chemical_effects: list[_ChemicalEffect],
    *,
    now: datetime,
    profile: dict[str, Any],
    context: PredictionContext,
    step: timedelta,
    history: timedelta,
    future: timedelta,
) -> ReadingPrediction | None:
    relevant_effects = [
        effect for effect in chemical_effects if effect.timestamp <= now
    ]
    if not relevant_effects:
        return None

    start = relevant_effects[0].timestamp
    window_start = now - history
    future_end = now + future
    series: list[dict[str, Any]] = []
    cursor = max(start, window_start)
    if cursor > start:
        elapsed_steps = int(
            _hours_between(start, cursor) // (step.total_seconds() / 3600)
        )
        cursor = start + (elapsed_steps * step)
        if cursor < window_start:
            cursor += step

    while cursor <= future_end:
        hours = max(0.0, _hours_between(start, cursor))
        predicted = _predict_at(
            WATER_READING_FREE_CHLORINE,
            0.0,
            start,
            cursor,
            profile=profile,
            context=context,
            chemical_effects=chemical_effects,
        )
        uncertainty = _uncertainty(
            WATER_READING_FREE_CHLORINE,
            hours,
            learned_error=0.75,
        )
        if cursor >= window_start:
            series.append(
                _point(
                    cursor,
                    predicted,
                    WATER_READING_FREE_CHLORINE,
                    uncertainty=uncertainty,
                    is_actual=False,
                )
            )
        cursor += step

    current_value = _predict_at(
        WATER_READING_FREE_CHLORINE,
        0.0,
        start,
        now,
        profile=profile,
        context=context,
        chemical_effects=chemical_effects,
    )
    current_uncertainty = _uncertainty(
        WATER_READING_FREE_CHLORINE,
        max(0.0, _hours_between(start, now)),
        learned_error=0.75,
    )
    current_point = _point(
        now,
        current_value,
        WATER_READING_FREE_CHLORINE,
        uncertainty=current_uncertainty,
        is_actual=False,
    )
    if not series or series[-1]["timestamp"] != current_point["timestamp"]:
        series.append(current_point)

    return ReadingPrediction(
        reading=WATER_READING_FREE_CHLORINE,
        unit=WATER_TEST_READING_UNITS[WATER_READING_FREE_CHLORINE],
        as_of=now.isoformat(),
        value=current_point["value"],
        uncertainty=current_point["uncertainty"],
        lower_bound=current_point["lower_bound"],
        upper_bound=current_point["upper_bound"],
        last_actual_value=None,
        last_actual_timestamp=None,
        model_inputs=_model_inputs(
            context,
            relevant_effects,
            profile=profile,
            baseline="assumed_zero_no_free_chlorine_reading",
        ),
        series=_dedupe_points(series)[-MAX_SERIES_POINTS:],
        actuals=[],
    )


def _predict_value(
    reading: str,
    start_value: float,
    hours: float,
    *,
    profile: dict[str, Any],
    context: PredictionContext,
    chemical_effects: list[_ChemicalEffect] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> float:
    days = max(0.0, hours / 24)
    if reading == WATER_READING_FREE_CHLORINE:
        if start is not None and end is not None:
            value = _predict_free_chlorine(
                start_value,
                start,
                end,
                profile=profile,
                context=context,
                chemical_effects=chemical_effects or [],
            )
        else:
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


def _predict_at(
    reading: str,
    start_value: float,
    start: datetime,
    end: datetime,
    *,
    profile: dict[str, Any],
    context: PredictionContext,
    chemical_effects: list[_ChemicalEffect],
) -> float:
    return _predict_value(
        reading,
        start_value,
        _hours_between(start, end),
        profile=profile,
        context=context,
        chemical_effects=chemical_effects,
        start=start,
        end=end,
    )


def _predict_free_chlorine(
    start_value: float,
    start: datetime,
    end: datetime,
    *,
    profile: dict[str, Any],
    context: PredictionContext,
    chemical_effects: list[_ChemicalEffect],
) -> float:
    value = start_value
    cursor = start
    daily_loss = _free_chlorine_daily_loss(profile, context)
    for effect in chemical_effects:
        if effect.timestamp < start or effect.timestamp > end:
            continue
        value -= daily_loss * max(0.0, _hours_between(cursor, effect.timestamp) / 24)
        value = _clamp(WATER_READING_FREE_CHLORINE, value)
        value += effect.free_chlorine_delta
        cursor = effect.timestamp
    value -= daily_loss * max(0.0, _hours_between(cursor, end) / 24)
    return _clamp(WATER_READING_FREE_CHLORINE, value)


def _chemical_effects(
    records: list[PoolRecord], *, pool_profile: dict[str, Any]
) -> list[_ChemicalEffect]:
    effects: list[_ChemicalEffect] = []
    for record in records:
        if record.get("type") != RECORD_TYPE_CHEMICAL_ADDITION:
            continue
        delta = _free_chlorine_delta(record, pool_profile=pool_profile)
        if delta is None or delta <= 0:
            continue
        effects.append(
            _ChemicalEffect(
                timestamp=parse_utc(record["event_timestamp"]),
                record_id=record["id"],
                chemical=str(record.get("chemical", "")),
                amount=float(record.get("amount", 0)),
                unit=str(record.get("unit", "")),
                free_chlorine_delta=delta,
            )
        )
    return sorted(effects, key=lambda effect: (effect.timestamp, effect.record_id))


def _free_chlorine_delta(
    record: PoolRecord, *, pool_profile: dict[str, Any]
) -> float | None:
    fraction = _available_chlorine_fraction(str(record.get("chemical", "")))
    if fraction is None:
        return None
    amount_pounds = _amount_pounds(record.get("amount"), str(record.get("unit", "")))
    if amount_pounds is None:
        return None
    volume_gallons, _source = _pool_volume_gallons(pool_profile)
    water_pounds = volume_gallons * POUNDS_PER_GALLON_WATER
    return (amount_pounds * fraction / water_pounds) * 1_000_000


def _available_chlorine_fraction(chemical: str) -> float | None:
    normalized = chemical.strip().lower()
    for needle, fraction in CHLORINE_AVAILABLE_FRACTIONS.items():
        if needle in normalized:
            return fraction
    return None


def _amount_pounds(amount: Any, unit: str) -> float | None:
    try:
        numeric = float(amount)
    except TypeError, ValueError:
        return None
    if numeric <= 0:
        return None

    normalized = unit.strip().lower().replace(".", "")
    if normalized in {"lb", "lbs", "pound", "pounds"}:
        return numeric
    if normalized in {"oz", "ounce", "ounces"}:
        return numeric / 16
    if normalized in {"g", "gram", "grams"}:
        return numeric / 453.59237
    if normalized in {"kg", "kilogram", "kilograms"}:
        return numeric * 2.2046226218
    if normalized in {"tsp", "teaspoon", "teaspoons"}:
        return (numeric / 6) / 16
    if normalized in {"tbsp", "tablespoon", "tablespoons"}:
        return (numeric / 2) / 16
    if normalized in {"cup", "cups"}:
        return (numeric * 8) / 16
    return None


def _pool_volume_gallons(pool_profile: dict[str, Any]) -> tuple[float, str]:
    volume = pool_profile.get(CONF_POOL_VOLUME)
    if volume not in (None, ""):
        try:
            gallons = float(volume)
        except TypeError, ValueError:
            gallons = 0
        if gallons > 0:
            if pool_profile.get(CONF_POOL_VOLUME_UNIT) == "L":
                return gallons / LITERS_PER_GALLON, "configured_liters"
            return gallons, "configured_gallons"

    pool_type = pool_profile.get(CONF_POOL_TYPE)
    if pool_type == "spa":
        return DEFAULT_SPA_VOLUME_GAL, "default_spa"
    if pool_type == "swim_spa":
        return DEFAULT_SWIM_SPA_VOLUME_GAL, "default_swim_spa"
    return DEFAULT_POOL_VOLUME_GAL, "default_pool"


def _model_inputs(
    context: PredictionContext,
    chemical_effects: list[_ChemicalEffect],
    *,
    profile: dict[str, Any],
    baseline: str | None = None,
) -> dict[str, Any]:
    inputs = context.model_inputs()
    if baseline is not None:
        inputs["baseline"] = baseline
    if chemical_effects:
        volume_gallons, volume_source = _pool_volume_gallons(profile)
        inputs["pool_volume_gallons"] = round(volume_gallons, 1)
        inputs["pool_volume_source"] = volume_source
        inputs["chemical_additions"] = [
            {
                "record_id": effect.record_id,
                "timestamp": effect.timestamp.isoformat(),
                "chemical": effect.chemical,
                "amount": effect.amount,
                "unit": effect.unit,
                "free_chlorine_delta": round(effect.free_chlorine_delta, 3),
            }
            for effect in chemical_effects[-MAX_ACTUAL_POINTS:]
        ]
    return inputs


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
