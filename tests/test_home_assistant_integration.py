"""Smoke tests for the Home Assistant config-entry lifecycle."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

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
