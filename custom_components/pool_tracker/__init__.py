"""Pool Tracker custom integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    CONF_DEFAULT_TESTING_METHOD,
    CONF_POOL_ID,
    CONF_POOL_NAME,
    CONF_TYPICALLY_COVERED,
    DEFAULT_TESTING_METHOD,
    DOMAIN,
    EVENT_RECORD_CREATED,
    PLATFORMS,
    SERVICE_LOG_CHEMICAL_ADDITION,
    SERVICE_LOG_WATER_TEST,
    WATER_CLARITY_OPTIONS,
    WATER_READING_CYA,
    WATER_READING_FREE_CHLORINE,
    WATER_READING_PH,
    WATER_READING_TOTAL_ALKALINITY,
    WATER_READING_WATER_CLARITY,
    WATER_TESTING_METHOD,
    WATER_TESTING_METHODS,
)
from .models import build_chemical_addition_record, build_water_test_record
from .store import PoolTrackerStore, create_home_assistant_store

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

    type PoolTrackerConfigEntry = ConfigEntry[PoolTrackerRuntime]

_LOGGER = logging.getLogger(__name__)


@dataclass
class PoolTrackerRuntime:
    """Runtime data for one Pool Tracker config entry."""

    store: PoolTrackerStore
    pools: dict[str, str]
    pool_profiles: dict[str, dict[str, Any]]


def _number(minimum: float | None = None, maximum: float | None = None):
    validators = [vol.Coerce(float)]
    if minimum is not None:
        validators.append(vol.Range(min=minimum))
    if maximum is not None:
        validators.append(vol.Range(max=maximum))
    return vol.All(*validators)


def _positive_number(value: Any) -> float:
    number = vol.Coerce(float)(value)
    if number <= 0:
        raise vol.Invalid("value must be greater than zero")
    return number


def _validate_water_test_content(data: dict[str, Any]) -> dict[str, Any]:
    if any(
        data.get(key) not in (None, "")
        for key in (
            WATER_READING_FREE_CHLORINE,
            WATER_READING_PH,
            WATER_READING_TOTAL_ALKALINITY,
            WATER_READING_CYA,
            WATER_READING_WATER_CLARITY,
            "notes",
        )
    ):
        return data
    raise vol.Invalid(
        "At least one water-test reading, clarity value, or note is required."
    )


def _water_test_service_schema():
    return vol.Schema(
        vol.All(
            {
                vol.Optional(CONF_POOL_ID): cv.string,
                vol.Optional("event_timestamp"): cv.datetime,
                vol.Optional("source", default="service"): cv.string,
                vol.Optional("notes"): cv.string,
                vol.Optional(WATER_READING_FREE_CHLORINE): _number(0),
                vol.Optional(WATER_READING_PH): _number(0, 14),
                vol.Optional(WATER_READING_TOTAL_ALKALINITY): _number(0),
                vol.Optional(WATER_READING_CYA): _number(0),
                vol.Optional(WATER_READING_WATER_CLARITY): vol.In(
                    WATER_CLARITY_OPTIONS
                ),
                vol.Optional(WATER_TESTING_METHOD): vol.In(WATER_TESTING_METHODS),
            },
            _validate_water_test_content,
        )
    )


def _chemical_addition_service_schema():
    return vol.Schema(
        {
            vol.Optional(CONF_POOL_ID): cv.string,
            vol.Optional("event_timestamp"): cv.datetime,
            vol.Optional("source", default="service"): cv.string,
            vol.Optional("notes"): cv.string,
            vol.Required("chemical"): cv.string,
            vol.Required("amount"): _positive_number,
            vol.Required("unit"): cv.string,
        }
    )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Pool Tracker service actions."""
    event_store = PoolTrackerStore(create_home_assistant_store(hass))
    await event_store.async_load()
    hass.data.setdefault(DOMAIN, {})["store"] = event_store

    async def handle_log_water_test(call: ServiceCall) -> dict[str, str]:
        runtime, pool_id = _runtime_for_call(hass, call.data.get(CONF_POOL_ID))
        readings = {
            key: call.data.get(key)
            for key in (
                WATER_READING_FREE_CHLORINE,
                WATER_READING_PH,
                WATER_READING_TOTAL_ALKALINITY,
                WATER_READING_CYA,
                WATER_READING_WATER_CLARITY,
            )
        }
        record = build_water_test_record(
            pool_id=pool_id,
            readings=readings,
            event_timestamp=call.data.get("event_timestamp"),
            source=call.data.get("source"),
            notes=call.data.get("notes"),
            testing_method=call.data.get(WATER_TESTING_METHOD)
            or runtime.pool_profiles.get(pool_id, {}).get(CONF_DEFAULT_TESTING_METHOD),
        )
        await runtime.store.async_append(record)
        _fire_record_created(hass, record)
        return {"record_id": record["id"]}

    async def handle_log_chemical_addition(call: ServiceCall) -> dict[str, str]:
        runtime, pool_id = _runtime_for_call(hass, call.data.get(CONF_POOL_ID))
        record = build_chemical_addition_record(
            pool_id=pool_id,
            chemical=call.data["chemical"],
            amount=call.data["amount"],
            unit=call.data["unit"],
            event_timestamp=call.data.get("event_timestamp"),
            source=call.data.get("source"),
            notes=call.data.get("notes"),
        )
        await runtime.store.async_append(record)
        _fire_record_created(hass, record)
        return {"record_id": record["id"]}

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        handle_log_water_test,
        schema=_water_test_service_schema(),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_CHEMICAL_ADDITION,
        handle_log_chemical_addition,
        schema=_chemical_addition_service_schema(),
        supports_response=SupportsResponse.OPTIONAL,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: PoolTrackerConfigEntry) -> bool:
    """Set up Pool Tracker from a config entry."""
    pool_profiles = _pool_profiles_from_entry(entry)
    pools = {
        pool_id: profile[CONF_POOL_NAME] for pool_id, profile in pool_profiles.items()
    }
    store = hass.data[DOMAIN]["store"]

    entry.runtime_data = PoolTrackerRuntime(
        store=store, pools=pools, pool_profiles=pool_profiles
    )

    _LOGGER.debug(
        "Setting up Pool Tracker entry %s for pools %s", entry.entry_id, pools
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PoolTrackerConfigEntry
) -> bool:
    """Unload a Pool Tracker config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        _LOGGER.debug("Unloaded Pool Tracker entry %s", entry.entry_id)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry versions."""
    if config_entry.version == 1:
        return True
    _LOGGER.error(
        "Unsupported Pool Tracker config entry version %s", config_entry.version
    )
    return False


def _runtime_for_call(
    hass: HomeAssistant, requested_pool_id: str | None
) -> tuple[PoolTrackerRuntime, str]:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError("Pool Tracker is not loaded.")

    matches: list[tuple[PoolTrackerRuntime, str]] = []
    for entry in entries:
        runtime = entry.runtime_data
        for pool_id in runtime.pools:
            if requested_pool_id is None or requested_pool_id == pool_id:
                matches.append((runtime, pool_id))

    if not matches:
        raise ServiceValidationError(
            f"No loaded Pool Tracker pool matches pool_id {requested_pool_id!r}."
        )
    if requested_pool_id is None and len(matches) > 1:
        raise ServiceValidationError(
            "pool_id is required when multiple pools are loaded."
        )

    return matches[0]


def _pool_profiles_from_entry(
    entry: PoolTrackerConfigEntry,
) -> dict[str, dict[str, Any]]:
    pool = dict(entry.options or entry.data)
    pool_id = pool[CONF_POOL_ID]
    pool.setdefault(CONF_DEFAULT_TESTING_METHOD, DEFAULT_TESTING_METHOD)
    pool.setdefault(CONF_TYPICALLY_COVERED, False)
    return {pool_id: pool}


def _fire_record_created(hass: HomeAssistant, record: dict[str, Any]) -> None:
    hass.bus.async_fire(
        EVENT_RECORD_CREATED,
        {
            "record_id": record["id"],
            "pool_id": record["pool_id"],
            "type": record["type"],
        },
    )
