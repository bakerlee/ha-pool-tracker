"""Smoke tests for the Home Assistant config-entry lifecycle."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from homeassistant.exceptions import ServiceValidationError  # noqa: E402
from homeassistant.helpers import device_registry as dr  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.pool_tracker.const import (  # noqa: E402
    CONF_DEFAULT_TESTING_METHOD,
    CONF_POOL_ID,
    CONF_POOL_NAME,
    CONF_POOL_VOLUME,
    CONF_POOL_VOLUME_UNIT,
    CONF_POOLS,
    DOMAIN,
    SERVICE_LOG_WATER_TEST,
    WATER_TESTING_METHOD,
)


async def test_setup_unload_reload_config_entry(hass) -> None:
    """Smoke test setup, unload, and reload for a Pool Tracker config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id=DOMAIN,
        data={
            CONF_POOLS: [
                {
                    CONF_POOL_ID: "pool",
                    CONF_POOL_NAME: "Pool",
                    CONF_POOL_VOLUME: 12000.0,
                    CONF_POOL_VOLUME_UNIT: "gal",
                    CONF_DEFAULT_TESTING_METHOD: "strips",
                }
            ]
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.pools == {"pool": "Pool"}
    assert entry.runtime_data.pool_profiles["pool"][CONF_POOL_VOLUME] == 12000.0
    assert (
        entry.runtime_data.pool_profiles["pool"][CONF_DEFAULT_TESTING_METHOD]
        == "strips"
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        {"ph": 7.2},
        blocking=True,
    )
    stored = entry.runtime_data.store.records("pool")[0]
    assert stored[WATER_TESTING_METHOD] == "strips"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.store.records("pool")[0][WATER_TESTING_METHOD] == "strips"


async def test_setup_defaults_missing_pool_profile_fields(hass) -> None:
    """Existing config entries get profile defaults at runtime."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id=DOMAIN,
        data={CONF_POOLS: [{CONF_POOL_ID: "pool", CONF_POOL_NAME: "Pool"}]},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entry.runtime_data.pool_profiles["pool"][CONF_DEFAULT_TESTING_METHOD]
        == "strips"
    )


async def test_options_flow_opens_for_existing_pool(hass) -> None:
    """Existing config entries can open the pool profile options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id=DOMAIN,
        data={CONF_POOLS: [{CONF_POOL_ID: "pool", CONF_POOL_NAME: "Pool"}]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_multiple_config_entries_share_store_and_route_by_pool_id(hass) -> None:
    """Multiple configured pools can log records without clobbering storage."""
    rooftop = MockConfigEntry(
        domain=DOMAIN,
        title="Rooftop Pool",
        data={
            CONF_POOLS: [
                {CONF_POOL_ID: "rooftop_pool", CONF_POOL_NAME: "Rooftop Pool"}
            ]
        },
    )
    spa = MockConfigEntry(
        domain=DOMAIN,
        title="Spa",
        data={CONF_POOLS: [{CONF_POOL_ID: "spa", CONF_POOL_NAME: "Spa"}]},
    )
    rooftop.add_to_hass(hass)
    spa.add_to_hass(hass)

    assert await hass.config_entries.async_setup(rooftop.entry_id)
    await hass.async_block_till_done()

    assert rooftop.runtime_data.store is spa.runtime_data.store
    device_registry = dr.async_get(hass)
    rooftop_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "rooftop_pool")}
    )
    spa_device = device_registry.async_get_device(identifiers={(DOMAIN, "spa")})
    assert rooftop_device is not None
    assert rooftop_device.name == "Rooftop Pool"
    assert spa_device is not None
    assert spa_device.name == "Spa"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        {"pool_id": "rooftop_pool", "ph": 7.2},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        {"pool_id": "spa", "ph": 7.6},
        blocking=True,
    )

    assert rooftop.runtime_data.store.records("rooftop_pool")[0]["readings"]["ph"][
        "value"
    ] == 7.2
    assert spa.runtime_data.store.records("spa")[0]["readings"]["ph"]["value"] == 7.6

    with pytest.raises(ServiceValidationError, match="pool_id is required"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_LOG_WATER_TEST,
            {"ph": 7.4},
            blocking=True,
        )
