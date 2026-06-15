"""Read-only latest-value sensors for Pool Tracker."""

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    RECORD_TYPE_CHEMICAL_ADDITION,
    RECORD_TYPE_WATER_TEST,
    WATER_READING_CYA,
    WATER_READING_FREE_CHLORINE,
    WATER_READING_PH,
    WATER_READING_TOTAL_ALKALINITY,
    WATER_READING_WATER_CLARITY,
)
from .models import PoolRecord, chemical_summary, parse_utc


@dataclass(frozen=True, kw_only=True)
class PoolSensorDescription(SensorEntityDescription):
    """Description for Pool Tracker latest-value sensors."""

    value_fn: Callable[[PoolTrackerLatestSensor], Any]
    attr_fn: Callable[[PoolTrackerLatestSensor], dict[str, Any] | None] = (
        lambda entity: None
    )


def _record_attrs(record: PoolRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "record_id": record["id"],
        "event_timestamp": record["event_timestamp"],
        "created_timestamp": record["created_timestamp"],
    }


def _latest_record_entity_attrs(
    entity: PoolTrackerLatestSensor, record_type: str
) -> dict[str, Any] | None:
    return _record_attrs(entity.store.latest_record(record_type, entity.pool_id))


def _latest_reading_value(entity: PoolTrackerLatestSensor, reading: str) -> Any:
    latest = entity.store.latest_reading(reading, entity.pool_id)
    if latest is None:
        return None
    return latest[1]["value"]


def _latest_reading_attrs(
    entity: PoolTrackerLatestSensor, reading: str
) -> dict[str, Any] | None:
    latest = entity.store.latest_reading(reading, entity.pool_id)
    if latest is None:
        return None
    record, value = latest
    return _record_attrs(record) | {"unit": value["unit"]}


SENSOR_DESCRIPTIONS: tuple[PoolSensorDescription, ...] = (
    PoolSensorDescription(
        key="latest_water_test_timestamp",
        translation_key="latest_water_test_timestamp",
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
        key="latest_chemical_addition_timestamp",
        translation_key="latest_chemical_addition_timestamp",
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
        key="latest_free_chlorine",
        translation_key="latest_free_chlorine",
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
        key="latest_ph",
        translation_key="latest_ph",
        native_unit_of_measurement="pH",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda entity: _latest_reading_value(entity, WATER_READING_PH),
        attr_fn=lambda entity: _latest_reading_attrs(entity, WATER_READING_PH),
    ),
    PoolSensorDescription(
        key="latest_total_alkalinity",
        translation_key="latest_total_alkalinity",
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
        key="latest_cya",
        translation_key="latest_cya",
        native_unit_of_measurement="ppm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda entity: _latest_reading_value(entity, WATER_READING_CYA),
        attr_fn=lambda entity: _latest_reading_attrs(entity, WATER_READING_CYA),
    ),
    PoolSensorDescription(
        key="latest_water_clarity",
        translation_key="latest_water_clarity",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda entity: _latest_reading_value(
            entity, WATER_READING_WATER_CLARITY
        ),
        attr_fn=lambda entity: _latest_reading_attrs(
            entity, WATER_READING_WATER_CLARITY
        ),
    ),
    PoolSensorDescription(
        key="latest_chemical_addition_summary",
        translation_key="latest_chemical_addition_summary",
        value_fn=lambda entity: chemical_summary(
            entity.store.latest_record(RECORD_TYPE_CHEMICAL_ADDITION, entity.pool_id)
        ),
        attr_fn=lambda entity: _latest_record_entity_attrs(
            entity, RECORD_TYPE_CHEMICAL_ADDITION
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Tracker latest-value sensors."""
    runtime = entry.runtime_data
    async_add_entities(
        PoolTrackerLatestSensor(entry, pool_id, pool_name, description)
        for pool_id, pool_name in runtime.pools.items()
        for description in SENSOR_DESCRIPTIONS
    )


class PoolTrackerLatestSensor(SensorEntity):
    """A read-only latest-value sensor derived from the append-only event log."""

    entity_description: PoolSensorDescription
    _attr_has_entity_name = True

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
        self._attr_unique_id = f"{entry.entry_id}_{pool_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pool_id)},
            name=pool_name,
            manufacturer="Pool Tracker",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to event-log updates."""
        self.async_on_remove(self.store.async_listen(self._handle_store_update))

    @callback
    def _handle_store_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        """Return the latest derived sensor value."""
        return self.entity_description.value_fn(self)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return source record metadata."""
        return self.entity_description.attr_fn(self)
