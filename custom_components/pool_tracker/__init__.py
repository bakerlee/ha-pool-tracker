"""Pool Tracker custom integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

    from .store import PoolTrackerStore

    type PoolTrackerConfigEntry = ConfigEntry[PoolTrackerRuntime]


@dataclass
class PoolTrackerRuntime:
    """Runtime data for one Pool Tracker config entry."""

    store: PoolTrackerStore
    pools: dict[str, str]


def _number(minimum: float | None = None, maximum: float | None = None):
    import voluptuous as vol

    validators = [vol.Coerce(float)]
    if minimum is not None:
        validators.append(vol.Range(min=minimum))
    if maximum is not None:
        validators.append(vol.Range(max=maximum))
    return vol.All(*validators)


def _positive_number(value: Any) -> float:
    import voluptuous as vol

    number = vol.Coerce(float)(value)
    if number <= 0:
        raise vol.Invalid("value must be greater than zero")
    return number


def _validate_water_test_content(data: dict[str, Any]) -> dict[str, Any]:
    import voluptuous as vol

    from .const import (
        WATER_READING_CYA,
        WATER_READING_FREE_CHLORINE,
        WATER_READING_PH,
        WATER_READING_TOTAL_ALKALINITY,
        WATER_READING_WATER_CLARITY,
    )

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
    import homeassistant.helpers.config_validation as cv
    import voluptuous as vol

    from .const import (
        CONF_POOL_ID,
        WATER_READING_CYA,
        WATER_READING_FREE_CHLORINE,
        WATER_READING_PH,
        WATER_READING_TOTAL_ALKALINITY,
        WATER_READING_WATER_CLARITY,
    )

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
                vol.Optional(WATER_READING_WATER_CLARITY): cv.string,
            },
            _validate_water_test_content,
        )
    )


def _chemical_addition_service_schema():
    import homeassistant.helpers.config_validation as cv
    import voluptuous as vol

    from .const import CONF_POOL_ID

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
    """Set up Pool Tracker services."""
    from homeassistant.core import SupportsResponse

    from .const import (
        CONF_POOL_ID,
        DOMAIN,
        SERVICE_LOG_CHEMICAL_ADDITION,
        SERVICE_LOG_WATER_TEST,
        WATER_READING_CYA,
        WATER_READING_FREE_CHLORINE,
        WATER_READING_PH,
        WATER_READING_TOTAL_ALKALINITY,
        WATER_READING_WATER_CLARITY,
    )
    from .models import build_chemical_addition_record, build_water_test_record

    hass.data.setdefault(DOMAIN, {"entries": {}})

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
    from .const import (
        CONF_POOL_ID,
        CONF_POOL_NAME,
        CONF_POOLS,
        DEFAULT_POOL_ID,
        DOMAIN,
        PLATFORMS,
    )
    from .store import PoolTrackerStore, create_home_assistant_store

    pools = {
        pool[CONF_POOL_ID]: pool[CONF_POOL_NAME]
        for pool in entry.data.get(CONF_POOLS, [])
    }
    default_pool_id = next(iter(pools), DEFAULT_POOL_ID)
    store = PoolTrackerStore(
        create_home_assistant_store(hass), default_pool_id=default_pool_id
    )
    await store.async_load()

    entry.runtime_data = PoolTrackerRuntime(store=store, pools=pools)
    hass.data[DOMAIN]["entries"][entry.entry_id] = entry

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PoolTrackerConfigEntry
) -> bool:
    """Unload a Pool Tracker config entry."""
    from .const import DOMAIN, PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN]["entries"].pop(entry.entry_id, None)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry versions."""
    if config_entry.version == 1:
        return True
    return False


def _runtime_for_call(
    hass: HomeAssistant, requested_pool_id: str | None
) -> tuple[PoolTrackerRuntime, str]:
    from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

    from .const import DOMAIN

    entries: dict[str, PoolTrackerConfigEntry] = hass.data.get(DOMAIN, {}).get(
        "entries", {}
    )
    if not entries:
        raise HomeAssistantError("Pool Tracker is not loaded.")

    matches: list[tuple[PoolTrackerRuntime, str]] = []
    for entry in entries.values():
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


def _fire_record_created(hass: HomeAssistant, record: dict[str, Any]) -> None:
    from .const import EVENT_RECORD_CREATED

    hass.bus.async_fire(
        EVENT_RECORD_CREATED,
        {
            "record_id": record["id"],
            "pool_id": record["pool_id"],
            "type": record["type"],
        },
    )
