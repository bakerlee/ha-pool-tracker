"""Smoke tests for the Home Assistant config-entry lifecycle."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.pool_tracker.const import (  # noqa: E402
    CONF_POOL_ID,
    CONF_POOL_NAME,
    CONF_POOLS,
    DOMAIN,
)


async def test_setup_unload_reload_config_entry(hass) -> None:
    """Smoke test setup, unload, and reload for a Pool Tracker config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id=DOMAIN,
        data={CONF_POOLS: [{CONF_POOL_ID: "pool", CONF_POOL_NAME: "Pool"}]},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.pools == {"pool": "Pool"}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.store.records("pool") == []
