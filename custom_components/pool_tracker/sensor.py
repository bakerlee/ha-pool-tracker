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
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_COVER_ENTITY_ID,
    CONF_RAINFALL_ENTITY_ID,
    CONF_SUNLIGHT_ENTITY_ID,
    CONF_TEMPERATURE_ENTITY_ID,
    CONF_USAGE_ENTITY_ID,
    CONF_WEATHER_ENTITY_ID,
    DOMAIN,
    NUMERIC_WATER_READINGS,
    POOL_CONTEXT_ENTITY_KEYS,
    RECORD_TYPE_CHEMICAL_ADDITION,
    RECORD_TYPE_WATER_TEST,
    WATER_READING_CYA,
    WATER_READING_FREE_CHLORINE,
    WATER_READING_PH,
    WATER_READING_TOTAL_ALKALINITY,
    WATER_READING_WATER_CLARITY,
    WATER_TESTING_METHOD,
)
from .models import PoolRecord, chemical_summary, parse_utc
from .prediction import PredictionContext, build_prediction

PARALLEL_UPDATES = 0


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


def _latest_reading_attrs(
    entity: PoolTrackerSensor, reading: str
) -> dict[str, Any] | None:
    latest = entity.store.latest_reading(reading, entity.pool_id)
    if latest is None:
        return None
    record, value = latest
    return _record_attrs(record) | {"unit": value["unit"]}


def _prediction_value(entity: PoolTrackerSensor, reading: str) -> Any:
    prediction = entity.prediction(reading)
    if prediction is None:
        return None
    return prediction.value


def _prediction_attrs(entity: PoolTrackerSensor, reading: str) -> dict[str, Any] | None:
    prediction = entity.prediction(reading)
    if prediction is None:
        return None
    return {
        "unit": prediction.unit,
        "as_of": prediction.as_of,
        "last_actual_value": prediction.last_actual_value,
        "last_actual_timestamp": prediction.last_actual_timestamp,
        "uncertainty": prediction.uncertainty,
        "lower_bound": prediction.lower_bound,
        "upper_bound": prediction.upper_bound,
        "model_inputs": prediction.model_inputs,
        "series": prediction.series,
        "actuals": prediction.actuals,
    }


SENSOR_DESCRIPTIONS: tuple[PoolSensorDescription, ...] = (
    PoolSensorDescription(
        key="last_water_test",
        translation_key="last_water_test",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda entity: (
            parse_utc(record["event_timestamp"])
            if (
                record := entity.store.latest_record(
                    RECORD_TYPE_WATER_TEST, entity.pool_id
                )
            )
            else None
        ),
        attr_fn=lambda entity: _latest_record_entity_attrs(
            entity, RECORD_TYPE_WATER_TEST
        ),
    ),
    PoolSensorDescription(
        key="last_chemical_addition",
        translation_key="last_chemical_addition",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda entity: (
            parse_utc(record["event_timestamp"])
            if (
                record := entity.store.latest_record(
                    RECORD_TYPE_CHEMICAL_ADDITION, entity.pool_id
                )
            )
            else None
        ),
        attr_fn=lambda entity: _latest_record_entity_attrs(
            entity, RECORD_TYPE_CHEMICAL_ADDITION
        ),
    ),
    PoolSensorDescription(
        key="free_chlorine",
        translation_key="free_chlorine",
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda entity: _latest_reading_value(
            entity, WATER_READING_FREE_CHLORINE
        ),
        attr_fn=lambda entity: _latest_reading_attrs(
            entity, WATER_READING_FREE_CHLORINE
        ),
    ),
    PoolSensorDescription(
        key="ph",
        translation_key="ph",
        native_unit_of_measurement="pH",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda entity: _latest_reading_value(entity, WATER_READING_PH),
        attr_fn=lambda entity: _latest_reading_attrs(entity, WATER_READING_PH),
    ),
    PoolSensorDescription(
        key="total_alkalinity",
        translation_key="total_alkalinity",
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda entity: _latest_reading_value(
            entity, WATER_READING_TOTAL_ALKALINITY
        ),
        attr_fn=lambda entity: _latest_reading_attrs(
            entity, WATER_READING_TOTAL_ALKALINITY
        ),
    ),
    PoolSensorDescription(
        key="cya",
        translation_key="cya",
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda entity: _latest_reading_value(entity, WATER_READING_CYA),
        attr_fn=lambda entity: _latest_reading_attrs(entity, WATER_READING_CYA),
    ),
    PoolSensorDescription(
        key="water_clarity",
        translation_key="water_clarity",
        value_fn=lambda entity: _latest_reading_value(
            entity, WATER_READING_WATER_CLARITY
        ),
        attr_fn=lambda entity: _latest_reading_attrs(
            entity, WATER_READING_WATER_CLARITY
        ),
    ),
    PoolSensorDescription(
        key="chemical_addition_summary",
        translation_key="chemical_addition_summary",
        value_fn=lambda entity: chemical_summary(
            entity.store.latest_record(RECORD_TYPE_CHEMICAL_ADDITION, entity.pool_id)
        ),
        attr_fn=lambda entity: _latest_record_entity_attrs(
            entity, RECORD_TYPE_CHEMICAL_ADDITION
        ),
    ),
    *(
        PoolSensorDescription(
            key=f"{reading}_prediction",
            translation_key=f"{reading}_prediction",
            native_unit_of_measurement="pH" if reading == WATER_READING_PH else "ppm",
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
            value_fn=lambda entity, prediction_reading=reading: _prediction_value(
                entity, prediction_reading
            ),
            attr_fn=lambda entity, prediction_reading=reading: _prediction_attrs(
                entity, prediction_reading
            ),
            prediction_reading=reading,
        )
        for reading in NUMERIC_WATER_READINGS
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Tracker sensors."""
    runtime = entry.runtime_data
    async_add_entities(
        PoolTrackerSensor(entry, pool_id, pool_name, description)
        for pool_id, pool_name in runtime.pools.items()
        for description in SENSOR_DESCRIPTIONS
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
        self._attr_unique_id = f"{entry.entry_id}_{pool_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pool_id)},
            name=pool_name,
            manufacturer="Pool Tracker",
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
    def _handle_store_update(self) -> None:
        self.async_write_ha_state()

    @callback
    def _handle_context_update(self, event: Event[EventStateChangedData]) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        """Return the derived sensor value."""
        return self.entity_description.value_fn(self)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return source record metadata."""
        return self.entity_description.attr_fn(self)

    def prediction(self, reading: str):
        """Return the current prediction for a numeric water reading."""
        return build_prediction(
            self.store.records(self.pool_id),
            reading,
            pool_profile=self._pool_profile,
            context=self._prediction_context(),
        )

    @property
    def _pool_profile(self) -> dict[str, Any]:
        return self._entry.runtime_data.pool_profiles.get(self.pool_id, {})

    def _context_entity_ids(self) -> list[str]:
        profile = self._pool_profile
        return [
            entity_id
            for key in POOL_CONTEXT_ENTITY_KEYS
            if (entity_id := profile.get(key))
        ]

    def _prediction_context(self) -> PredictionContext:
        profile = self._pool_profile
        weather_state = _state(self.hass, profile.get(CONF_WEATHER_ENTITY_ID))
        weather_attrs = weather_state.attributes if weather_state is not None else {}
        forecast_attrs = _first_forecast_attrs(weather_attrs)

        temperature = _temperature_f(
            _number_state(self.hass, profile.get(CONF_TEMPERATURE_ENTITY_ID))
        )
        if temperature is None:
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

        sunlight = _number_state(self.hass, profile.get(CONF_SUNLIGHT_ENTITY_ID))
        if sunlight is None:
            sunlight = _sunlight_from_weather_attrs(weather_attrs)
        if sunlight is None:
            sunlight = _sunlight_from_weather_attrs(forecast_attrs)

        rainfall = _number_state(self.hass, profile.get(CONF_RAINFALL_ENTITY_ID))
        if rainfall is None:
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
        usage = _usage_state(self.hass, profile.get(CONF_USAGE_ENTITY_ID))
        sources = {
            key: entity_id
            for key in POOL_CONTEXT_ENTITY_KEYS
            if (entity_id := profile.get(key))
        }
        return PredictionContext(
            covered=covered,
            sunlight=sunlight,
            rainfall=rainfall,
            temperature_f=temperature,
            usage=usage,
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


def _number_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    state = _state(hass, entity_id)
    if state is None:
        return None
    return _float(state.state)


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


def _usage_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    state = _state(hass, entity_id)
    if state is None:
        return None
    if state.state == STATE_ON:
        return 1.0
    if state.state == STATE_OFF:
        return 0.0
    return _float(state.state)


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
