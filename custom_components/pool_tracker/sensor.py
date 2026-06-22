"""Read-only sensors for Pool Tracker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_COVER_ENTITY_ID,
    CONF_WEATHER_ENTITY_ID,
    DOMAIN,
    NUMERIC_WATER_READINGS,
    PREDICTED_WATER_READINGS,
    RECORD_TYPE_CHEMICAL_ADDITION,
    RECORD_TYPE_WATER_TEST,
    SERVICE_GET_PREDICTION,
    WATER_CLARITY_OPTIONS,
    WATER_READING_WATER_CLARITY,
    WATER_TEST_READING_PRECISION,
    WATER_TEST_READING_UNITS,
    WATER_TESTING_METHOD,
    enabled_water_test_metrics,
)
from .models import PoolRecord, chemical_summary, parse_utc
from .prediction import PredictionContext, ReadingPrediction, build_prediction

PARALLEL_UPDATES = 0
RECENT_LOG_LIMIT = 8
QUICK_CHEMICAL_LIMIT = 6


@dataclass(frozen=True, kw_only=True)
class PoolSensorDescription(SensorEntityDescription):
    """Description for Pool Tracker sensors."""

    value_fn: Callable[[PoolTrackerSensor], Any]
    attr_fn: Callable[[PoolTrackerSensor], dict[str, Any] | None] = lambda entity: None
    prediction_reading: str | None = None


def _record_attrs(record: PoolRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    attrs = {
        "record_id": record["id"],
        "event_timestamp": record["event_timestamp"],
        "created_timestamp": record["created_timestamp"],
    }
    if testing_method := record.get(WATER_TESTING_METHOD):
        attrs[WATER_TESTING_METHOD] = testing_method
    return attrs


def _latest_record_entity_attrs(
    entity: PoolTrackerSensor, record_type: str
) -> dict[str, Any] | None:
    return _record_attrs(entity.store.latest_record(record_type, entity.pool_id))


def _latest_reading_value(entity: PoolTrackerSensor, reading: str) -> Any:
    latest = entity.store.latest_reading(reading, entity.pool_id)
    if latest is None:
        return None
    return latest[1]["value"]


def _latest_clarity_value(entity: PoolTrackerSensor) -> str | None:
    value = _latest_reading_value(entity, WATER_READING_WATER_CLARITY)
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized if normalized in WATER_CLARITY_OPTIONS else "other"


def _latest_reading_attrs(
    entity: PoolTrackerSensor, reading: str
) -> dict[str, Any] | None:
    latest = entity.store.latest_reading(reading, entity.pool_id)
    if latest is None:
        return _log_attrs(entity) | {"unit": WATER_TEST_READING_UNITS[reading]}
    record, value = latest
    return _log_attrs(entity) | _record_attrs(record) | {"unit": value["unit"]}


def _prediction_value(entity: PoolTrackerSensor, reading: str) -> Any:
    prediction = entity.prediction(reading)
    if prediction is None:
        return None
    return prediction.value


def _prediction_attrs(entity: PoolTrackerSensor, reading: str) -> dict[str, Any] | None:
    prediction = entity.prediction(reading)
    base_attrs = _log_attrs(entity) | {
        "unit": WATER_TEST_READING_UNITS[reading],
        "prediction_sensor": True,
        "prediction_reading": reading,
    }
    if prediction is None:
        return base_attrs
    return base_attrs | {
        "unit": prediction.unit,
        "as_of": prediction.as_of,
        "last_actual_value": prediction.last_actual_value,
        "last_actual_timestamp": prediction.last_actual_timestamp,
        "uncertainty": prediction.uncertainty,
        "lower_bound": prediction.lower_bound,
        "upper_bound": prediction.upper_bound,
    }


def _log_attrs(entity: PoolTrackerSensor) -> dict[str, Any]:
    records = sorted(
        entity.store.records(entity.pool_id),
        key=lambda record: (
            parse_utc(record["event_timestamp"]),
            parse_utc(record["created_timestamp"]),
            str(record["id"]),
        ),
    )
    water_tests = [
        _water_test_summary(record)
        for record in records
        if record.get("type") == RECORD_TYPE_WATER_TEST
    ][-RECENT_LOG_LIMIT:]
    chemical_additions = [
        _chemical_addition_summary(record)
        for record in records
        if record.get("type") == RECORD_TYPE_CHEMICAL_ADDITION
    ][-RECENT_LOG_LIMIT:]

    return {
        "pool_id": entity.pool_id,
        "pool_name": entity.pool_name,
        "tracked_metrics": list(enabled_water_test_metrics(entity._pool_profile)),
        "recent_water_tests": list(reversed(water_tests)),
        "recent_chemical_additions": list(reversed(chemical_additions)),
        "quick_chemical_additions": _quick_chemical_additions(records),
    }


def _water_test_summary(record: PoolRecord) -> dict[str, Any]:
    summary = {
        "record_id": record["id"],
        "event_timestamp": record["event_timestamp"],
        "readings": {
            reading: value.get("value")
            for reading, value in record.get("readings", {}).items()
        },
    }
    if testing_method := record.get(WATER_TESTING_METHOD):
        summary[WATER_TESTING_METHOD] = testing_method
    if notes := record.get("notes"):
        summary["notes"] = notes
    return summary


def _chemical_addition_summary(record: PoolRecord) -> dict[str, Any]:
    summary = {
        "record_id": record["id"],
        "event_timestamp": record["event_timestamp"],
        "chemical": record.get("chemical"),
        "amount": record.get("amount"),
        "unit": record.get("unit"),
        "summary": chemical_summary(record),
    }
    if notes := record.get("notes"):
        summary["notes"] = notes
    return summary


def _quick_chemical_additions(records: list[PoolRecord]) -> list[dict[str, Any]]:
    quick_adds: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in reversed(records):
        if record.get("type") != RECORD_TYPE_CHEMICAL_ADDITION:
            continue
        key = (
            str(record.get("chemical", "")).strip().lower(),
            str(record.get("amount", "")),
            str(record.get("unit", "")).strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        quick_adds.append(
            {
                "chemical": record.get("chemical"),
                "amount": record.get("amount"),
                "unit": record.get("unit"),
                "summary": chemical_summary(record),
            }
        )
        if len(quick_adds) >= QUICK_CHEMICAL_LIMIT:
            break
    return quick_adds


def _prediction_response(prediction: ReadingPrediction) -> dict[str, Any]:
    return {
        "reading": prediction.reading,
        "unit": prediction.unit,
        "as_of": prediction.as_of,
        "value": prediction.value,
        "uncertainty": prediction.uncertainty,
        "lower_bound": prediction.lower_bound,
        "upper_bound": prediction.upper_bound,
        "last_actual_value": prediction.last_actual_value,
        "last_actual_timestamp": prediction.last_actual_timestamp,
        "model_inputs": prediction.model_inputs,
        "series": prediction.series,
        "actuals": prediction.actuals,
        "chemical_additions": prediction.chemical_additions,
    }


SENSOR_DESCRIPTIONS: tuple[PoolSensorDescription, ...] = (
    *(
        PoolSensorDescription(
            key=reading,
            translation_key=reading,
            native_unit_of_measurement=WATER_TEST_READING_UNITS[reading],
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=WATER_TEST_READING_PRECISION[reading],
            value_fn=lambda entity, latest_reading=reading: _latest_reading_value(
                entity, latest_reading
            ),
            attr_fn=lambda entity, latest_reading=reading: _latest_reading_attrs(
                entity, latest_reading
            ),
        )
        for reading in NUMERIC_WATER_READINGS
    ),
    PoolSensorDescription(
        key="water_clarity",
        translation_key="water_clarity",
        device_class=SensorDeviceClass.ENUM,
        options=list(WATER_CLARITY_OPTIONS),
        value_fn=_latest_clarity_value,
        attr_fn=lambda entity: _latest_reading_attrs(
            entity, WATER_READING_WATER_CLARITY
        ),
    ),
    *(
        PoolSensorDescription(
            key=f"{reading}_predicted",
            translation_key=f"{reading}_predicted",
            native_unit_of_measurement=WATER_TEST_READING_UNITS[reading],
            suggested_display_precision=2,
            value_fn=lambda entity, prediction_reading=reading: _prediction_value(
                entity, prediction_reading
            ),
            attr_fn=lambda entity, prediction_reading=reading: _prediction_attrs(
                entity, prediction_reading
            ),
            prediction_reading=reading,
        )
        for reading in PREDICTED_WATER_READINGS
    ),
)


def _enabled_sensor_descriptions(
    pool_profile: dict[str, Any],
) -> tuple[PoolSensorDescription, ...]:
    enabled_metrics = set(enabled_water_test_metrics(pool_profile))
    descriptions: list[PoolSensorDescription] = []
    for description in SENSOR_DESCRIPTIONS:
        if description.prediction_reading:
            if description.prediction_reading in enabled_metrics:
                descriptions.append(description)
            continue
        if (
            description.key in NUMERIC_WATER_READINGS
            or description.key == WATER_READING_WATER_CLARITY
        ):
            if description.key in enabled_metrics:
                descriptions.append(description)
            continue
        descriptions.append(description)
    return tuple(descriptions)


def _sensor_unique_id(entry: ConfigEntry, pool_id: str, description_key: str) -> str:
    """Return the unique ID for a Pool Tracker sensor entity."""
    return f"{entry.entry_id}_{pool_id}_{description_key}"


def _prune_disabled_metric_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    pool_id: str,
    pool_profile: dict[str, Any],
) -> None:
    """Remove registry entries for metrics disabled in the pool profile."""
    enabled_keys = {
        description.key for description in _enabled_sensor_descriptions(pool_profile)
    }
    entity_registry = er.async_get(hass)
    for description in SENSOR_DESCRIPTIONS:
        if description.key in enabled_keys:
            continue
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, _sensor_unique_id(entry, pool_id, description.key)
        )
        if entity_id is not None:
            entity_registry.async_remove(entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pool Tracker sensors."""
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_GET_PREDICTION,
        None,
        "async_get_prediction",
        supports_response=SupportsResponse.ONLY,
    )
    runtime = entry.runtime_data
    for pool_id in runtime.pools:
        _prune_disabled_metric_entities(
            hass, entry, pool_id, runtime.pool_profiles.get(pool_id, {})
        )
    async_add_entities(
        PoolTrackerSensor(entry, pool_id, pool_name, description)
        for pool_id, pool_name in runtime.pools.items()
        for description in _enabled_sensor_descriptions(
            runtime.pool_profiles.get(pool_id, {})
        )
    )


class PoolTrackerSensor(SensorEntity):
    """A read-only sensor derived from the append-only event log."""

    entity_description: PoolSensorDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        pool_id: str,
        pool_name: str,
        description: PoolSensorDescription,
    ) -> None:
        self.entity_description = description
        self.pool_id = pool_id
        self.pool_name = pool_name
        self.store = entry.runtime_data.store
        self._entry = entry
        self._prediction_cache: dict[str, ReadingPrediction | None] = {}
        self._attr_unique_id = _sensor_unique_id(entry, pool_id, description.key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pool_id)},
            name=pool_name,
            manufacturer="Pool Tracker",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to event-log updates."""
        self.async_on_remove(self.store.async_listen(self._handle_store_update))
        if not self.entity_description.prediction_reading:
            return
        entity_ids = self._context_entity_ids()
        if entity_ids:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, entity_ids, self._handle_context_update
                )
            )

    @callback
    def _handle_store_update(self, record: PoolRecord) -> None:
        self._prediction_cache.clear()
        self.async_write_ha_state()

    @callback
    def _handle_context_update(self, event: Event[EventStateChangedData]) -> None:
        self._prediction_cache.clear()
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        """Return the derived sensor value."""
        return self.entity_description.value_fn(self)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return source record metadata."""
        return self.entity_description.attr_fn(self)

    def prediction(self, reading: str) -> ReadingPrediction | None:
        """Return the current prediction for a numeric water reading.

        The result is cached until the next store or context update so that the
        ``native_value`` and ``extra_state_attributes`` reads within a single
        state write share one (relatively expensive) computation.
        """
        if reading not in self._prediction_cache:
            self._prediction_cache[reading] = build_prediction(
                self.store.records(self.pool_id),
                reading,
                pool_profile=self._pool_profile,
                context=self._prediction_context(),
            )
        return self._prediction_cache[reading]

    async def async_get_prediction(self) -> dict[str, Any]:
        """Return the full prediction series for this prediction sensor."""
        reading = self.entity_description.prediction_reading
        if not reading:
            raise HomeAssistantError(
                "get_prediction is only supported on prediction sensors."
            )
        prediction = self.prediction(reading)
        if prediction is None:
            return {"prediction": None}
        return {"prediction": _prediction_response(prediction)}

    @property
    def _pool_profile(self) -> dict[str, Any]:
        return self._entry.runtime_data.pool_profiles.get(self.pool_id, {})

    def _context_entity_ids(self) -> list[str]:
        profile = self._pool_profile
        return [
            entity_id
            for key in (CONF_WEATHER_ENTITY_ID, CONF_COVER_ENTITY_ID)
            if (entity_id := profile.get(key))
        ]

    def _prediction_context(self) -> PredictionContext:
        profile = self._pool_profile
        weather_state = _state(self.hass, profile.get(CONF_WEATHER_ENTITY_ID))
        weather_attrs = weather_state.attributes if weather_state is not None else {}
        forecast_attrs = _first_forecast_attrs(weather_attrs)

        temperature = _temperature_f(
            _float(weather_attrs.get("temperature")),
            unit=weather_attrs.get("temperature_unit"),
        )
        if temperature is None:
            temperature = _temperature_f(
                _float(
                    forecast_attrs.get("temperature")
                    or forecast_attrs.get("native_temperature")
                ),
                unit=weather_attrs.get("temperature_unit"),
            )

        sunlight = _sunlight_from_weather_attrs(weather_attrs)
        if sunlight is None:
            sunlight = _sunlight_from_weather_attrs(forecast_attrs)

        rainfall = _float(
            weather_attrs.get("precipitation")
            or weather_attrs.get("native_precipitation")
        )
        if rainfall is None:
            rainfall = _float(
                forecast_attrs.get("precipitation")
                or forecast_attrs.get("native_precipitation")
            )

        covered = _bool_state(self.hass, profile.get(CONF_COVER_ENTITY_ID))
        sources = {
            key: entity_id
            for key in (CONF_WEATHER_ENTITY_ID, CONF_COVER_ENTITY_ID)
            if (entity_id := profile.get(key))
        }
        return PredictionContext(
            covered=covered,
            sunlight=sunlight,
            rainfall=rainfall,
            temperature_f=temperature,
            weather_condition=(
                weather_state.state if weather_state is not None else None
            ),
            sources=sources or None,
        )


def _state(hass: HomeAssistant, entity_id: str | None):
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
        return None
    return state


def _bool_state(hass: HomeAssistant, entity_id: str | None) -> bool | None:
    state = _state(hass, entity_id)
    if state is None:
        return None
    if state.state == STATE_ON:
        return True
    if state.state == STATE_OFF:
        return False
    if state.state in {"closed", "covered", "true", "yes"}:
        return True
    if state.state in {"open", "uncovered", "false", "no"}:
        return False
    return None


def _sunlight_from_weather_attrs(attrs: dict[str, Any]) -> float | None:
    if (uv_index := _float(attrs.get("uv_index"))) is not None:
        return min(1.0, uv_index / 10)
    if (cloud_coverage := _float(attrs.get("cloud_coverage"))) is not None:
        return min(1.0, max(0.0, 1 - (cloud_coverage / 100)))
    return None


def _first_forecast_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    forecast = attrs.get("forecast")
    if isinstance(forecast, list) and forecast and isinstance(forecast[0], dict):
        return forecast[0]
    return {}


def _temperature_f(value: float | None, unit: str | None = None) -> float | None:
    if value is None:
        return None
    if unit in {UnitOfTemperature.CELSIUS, "C", "°C"}:
        return (value * 9 / 5) + 32
    return value


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None
