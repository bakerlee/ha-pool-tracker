"""Event entities for Pool Tracker log records."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    EVENT_TYPE_CHEMICAL_ADDITION,
    EVENT_TYPE_WATER_TEST,
    RECORD_TYPE_CHEMICAL_ADDITION,
    RECORD_TYPE_WATER_TEST,
    WATER_TESTING_METHOD,
)
from .models import chemical_summary

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one event entity per event-log record type per pool."""
    runtime = entry.runtime_data
    async_add_entities(
        event_entity
        for pool_id, pool_name in runtime.pools.items()
        for event_entity in (
            PoolWaterTestEvent(entry, pool_id, pool_name),
            PoolChemicalAdditionEvent(entry, pool_id, pool_name),
        )
    )


class PoolRecordEvent(EventEntity):
    """Fire an event whenever a matching record is logged for the pool."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _record_type: str
    _event_type: str

    def __init__(self, entry: ConfigEntry, pool_id: str, pool_name: str) -> None:
        self.pool_id = pool_id
        self.store = entry.runtime_data.store
        self._last_record_id: str | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pool_id)},
            name=pool_name,
            manufacturer="Pool Tracker",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to the event log without replaying historical records."""
        latest = self.store.latest_record(self._record_type, self.pool_id)
        self._last_record_id = latest["id"] if latest else None
        self.async_on_remove(self.store.async_listen(self._handle_store_update))

    @callback
    def _handle_store_update(self) -> None:
        latest = self.store.latest_record(self._record_type, self.pool_id)
        if latest is None or latest["id"] == self._last_record_id:
            return
        self._last_record_id = latest["id"]
        self._trigger_event(self._event_type, self._event_attributes(latest))
        self.async_write_ha_state()

    def _event_attributes(self, record: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class PoolWaterTestEvent(PoolRecordEvent):
    """Fire an event whenever a water test is logged for the pool."""

    _attr_translation_key = "water_test"
    _attr_event_types = [EVENT_TYPE_WATER_TEST]
    _record_type = RECORD_TYPE_WATER_TEST
    _event_type = EVENT_TYPE_WATER_TEST

    def __init__(self, entry: ConfigEntry, pool_id: str, pool_name: str) -> None:
        super().__init__(entry, pool_id, pool_name)
        self._attr_unique_id = f"{entry.entry_id}_{pool_id}_water_test_event"

    def _event_attributes(self, record: dict[str, Any]) -> dict[str, Any]:
        attributes: dict[str, Any] = {
            "readings": record.get("readings", {}),
            "record_id": record["id"],
            "event_timestamp": record["event_timestamp"],
        }
        if testing_method := record.get(WATER_TESTING_METHOD):
            attributes[WATER_TESTING_METHOD] = testing_method
        if notes := record.get("notes"):
            attributes["notes"] = notes
        return attributes


class PoolChemicalAdditionEvent(PoolRecordEvent):
    """Fire an event whenever a chemical addition is logged for the pool."""

    _attr_translation_key = "chemical_addition"
    _attr_event_types = [EVENT_TYPE_CHEMICAL_ADDITION]
    _record_type = RECORD_TYPE_CHEMICAL_ADDITION
    _event_type = EVENT_TYPE_CHEMICAL_ADDITION

    def __init__(self, entry: ConfigEntry, pool_id: str, pool_name: str) -> None:
        super().__init__(entry, pool_id, pool_name)
        self._attr_unique_id = f"{entry.entry_id}_{pool_id}_chemical_addition_event"

    def _event_attributes(self, record: dict[str, Any]) -> dict[str, Any]:
        attributes: dict[str, Any] = {
            "chemical": record.get("chemical"),
            "amount": record.get("amount"),
            "unit": record.get("unit"),
            "summary": chemical_summary(record),
            "record_id": record["id"],
            "event_timestamp": record["event_timestamp"],
        }
        if notes := record.get("notes"):
            attributes["notes"] = notes
        return attributes
