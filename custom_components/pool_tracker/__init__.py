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
    pool_profiles: dict[str, dict[str, Any]]


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
        WATER_TESTING_METHOD,
        WATER_TESTING_METHODS,
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
                vol.Optional(WATER_TESTING_METHOD): vol.In(WATER_TESTING_METHODS),
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
        CONF_DEFAULT_TESTING_METHOD,
        CONF_POOL_ID,
        DOMAIN,
        SERVICE_LOG_CHEMICAL_ADDITION,
        SERVICE_LOG_WATER_TEST,
        WATER_READING_CYA,
        WATER_READING_FREE_CHLORINE,
        WATER_READING_PH,
        WATER_READING_TOTAL_ALKALINITY,
        WATER_READING_WATER_CLARITY,
        WATER_TESTING_METHOD,
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
    from .const import (
        CONF_POOL_NAME,
        CONF_POOLS,
        DEFAULT_ENTRY_TITLE,
        DEFAULT_POOL_ID,
        DEFAULT_POOL_NAME,
        DOMAIN,
        PLATFORMS,
    )
    from .store import PoolTrackerStore, create_home_assistant_store

    _normalize_entry_metadata(
        hass,
        entry,
        conf_pools=CONF_POOLS,
        conf_pool_name=CONF_POOL_NAME,
        default_entry_title=DEFAULT_ENTRY_TITLE,
        default_pool_name=DEFAULT_POOL_NAME,
    )
    pool_profiles = _pool_profiles_from_entry(entry)
    pools = {
        pool_id: profile.get(CONF_POOL_NAME, DEFAULT_POOL_NAME)
        for pool_id, profile in pool_profiles.items()
    }
    default_pool_id = next(iter(pools), DEFAULT_POOL_ID)
    store = PoolTrackerStore(
        create_home_assistant_store(hass), default_pool_id=default_pool_id
    )
    await store.async_load()

    entry.runtime_data = PoolTrackerRuntime(
        store=store, pools=pools, pool_profiles=pool_profiles
    )
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


def _pool_profiles_from_entry(
    entry: PoolTrackerConfigEntry,
) -> dict[str, dict[str, Any]]:
    from .const import (
        CONF_DEFAULT_TESTING_METHOD,
        CONF_POOL_ID,
        CONF_POOL_NAME,
        CONF_POOLS,
        DEFAULT_POOL_ID,
        DEFAULT_POOL_NAME,
        DEFAULT_TESTING_METHOD,
    )

    raw_pools = entry.options.get(CONF_POOLS) or entry.data.get(CONF_POOLS, [])
    if not raw_pools:
        raw_pools = [{CONF_POOL_ID: DEFAULT_POOL_ID, CONF_POOL_NAME: DEFAULT_POOL_NAME}]

    profiles: dict[str, dict[str, Any]] = {}
    for raw_pool in raw_pools:
        pool = dict(raw_pool)
        pool_id = pool.setdefault(CONF_POOL_ID, DEFAULT_POOL_ID)
        pool.setdefault(CONF_POOL_NAME, DEFAULT_POOL_NAME)
        pool.setdefault(CONF_DEFAULT_TESTING_METHOD, DEFAULT_TESTING_METHOD)
        profiles[pool_id] = pool
    return profiles


def _normalize_entry_metadata(
    hass: HomeAssistant,
    entry: PoolTrackerConfigEntry,
    *,
    conf_pools: str,
    conf_pool_name: str,
    default_entry_title: str,
    default_pool_name: str,
) -> None:
    """Keep the integration entry distinct from the virtual pool device."""
    if entry.title == default_entry_title:
        return

    updates: dict[str, Any] = {"title": default_entry_title}
    pool_source = "options" if entry.options.get(conf_pools) else "data"
    raw_pools = entry.options.get(conf_pools) or entry.data.get(conf_pools)
    if (
        entry.title
        and entry.title != default_pool_name
        and isinstance(raw_pools, list)
        and len(raw_pools) == 1
    ):
        pool = dict(raw_pools[0])
        if pool.get(conf_pool_name, default_pool_name) == default_pool_name:
            pool[conf_pool_name] = entry.title
            if pool_source == "options":
                updates["options"] = {**entry.options, conf_pools: [pool]}
            else:
                updates["data"] = {**entry.data, conf_pools: [pool]}

    hass.config_entries.async_update_entry(entry, **updates)


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
