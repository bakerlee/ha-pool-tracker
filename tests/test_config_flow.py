"""Tests for Pool Tracker config helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")
import voluptuous_serialize  # noqa: E402
from homeassistant import config_entries  # noqa: E402
from homeassistant.helpers import config_validation as cv  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.pool_tracker.config_flow import (  # noqa: E402
    _pool_profile_schema,
    build_pool_config,
    pool_config_from_entry,
)
from custom_components.pool_tracker.const import (  # noqa: E402
    CONF_COVER_ENTITY_ID,
    CONF_DEFAULT_TESTING_METHOD,
    CONF_POOL_ID,
    CONF_POOL_NAME,
    CONF_POOL_TYPE,
    CONF_POOL_VOLUME,
    CONF_POOL_VOLUME_UNIT,
    CONF_POOLS,
    CONF_RAINFALL_ENTITY_ID,
    CONF_SANITIZER_TYPE,
    CONF_SUNLIGHT_ENTITY_ID,
    CONF_SURFACE_TYPE,
    CONF_TEMPERATURE_ENTITY_ID,
    CONF_TYPICALLY_COVERED,
    CONF_USAGE_ENTITY_ID,
    CONF_WEATHER_ENTITY_ID,
    DOMAIN,
)


def test_build_pool_config_keeps_future_calculation_attributes() -> None:
    """Pool config stores optional profile fields for later calculations."""
    pool = build_pool_config(
        {
            CONF_POOL_NAME: "Backyard Pool",
            CONF_POOL_VOLUME: "12000",
            CONF_POOL_VOLUME_UNIT: "gal",
            CONF_POOL_TYPE: "outdoor",
            CONF_SURFACE_TYPE: "plaster",
            CONF_SANITIZER_TYPE: "chlorine",
            CONF_DEFAULT_TESTING_METHOD: "strips",
            CONF_TYPICALLY_COVERED: True,
            CONF_WEATHER_ENTITY_ID: "weather.home",
            CONF_SUNLIGHT_ENTITY_ID: "sensor.pool_sunlight",
            CONF_RAINFALL_ENTITY_ID: "sensor.pool_rainfall",
            CONF_TEMPERATURE_ENTITY_ID: "sensor.pool_temperature",
            CONF_COVER_ENTITY_ID: "binary_sensor.pool_covered",
            CONF_USAGE_ENTITY_ID: "sensor.pool_usage",
        }
    )

    assert pool[CONF_POOL_NAME] == "Backyard Pool"
    assert pool[CONF_POOL_VOLUME] == 12000.0
    assert pool[CONF_POOL_VOLUME_UNIT] == "gal"
    assert pool[CONF_POOL_TYPE] == "outdoor"
    assert pool[CONF_SURFACE_TYPE] == "plaster"
    assert pool[CONF_SANITIZER_TYPE] == "chlorine"
    assert pool[CONF_DEFAULT_TESTING_METHOD] == "strips"
    assert pool[CONF_TYPICALLY_COVERED] is True
    assert pool[CONF_WEATHER_ENTITY_ID] == "weather.home"
    assert pool[CONF_SUNLIGHT_ENTITY_ID] == "sensor.pool_sunlight"
    assert pool[CONF_RAINFALL_ENTITY_ID] == "sensor.pool_rainfall"
    assert pool[CONF_TEMPERATURE_ENTITY_ID] == "sensor.pool_temperature"
    assert pool[CONF_COVER_ENTITY_ID] == "binary_sensor.pool_covered"
    assert pool[CONF_USAGE_ENTITY_ID] == "sensor.pool_usage"


def test_pool_profile_schema_serializes_for_home_assistant_forms() -> None:
    """The options form schema can be converted to frontend JSON."""
    converted = voluptuous_serialize.convert(
        _pool_profile_schema({CONF_POOL_NAME: "Pool"}),
        custom_serializer=cv.custom_serializer,
    )

    assert [field["name"] for field in converted] == [
        CONF_POOL_NAME,
        CONF_POOL_VOLUME,
        CONF_POOL_VOLUME_UNIT,
        CONF_POOL_TYPE,
        CONF_SURFACE_TYPE,
        CONF_SANITIZER_TYPE,
        CONF_DEFAULT_TESTING_METHOD,
        CONF_TYPICALLY_COVERED,
        CONF_WEATHER_ENTITY_ID,
        CONF_SUNLIGHT_ENTITY_ID,
        CONF_RAINFALL_ENTITY_ID,
        CONF_TEMPERATURE_ENTITY_ID,
        CONF_COVER_ENTITY_ID,
        CONF_USAGE_ENTITY_ID,
    ]


def test_pool_config_from_entry_accepts_legacy_pool_list() -> None:
    """Existing entries with the old length-1 pool list continue to load."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Legacy Pool",
        data={CONF_POOLS: [{CONF_POOL_ID: "legacy", CONF_POOL_NAME: "Legacy Pool"}]},
    )

    assert pool_config_from_entry(entry) == {
        CONF_POOL_ID: "legacy",
        CONF_POOL_NAME: "Legacy Pool",
    }


async def test_config_flow_uses_pool_name_for_entry(hass) -> None:
    """Each Pool Tracker config entry represents one pool."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_POOL_NAME: "Rooftop Pool"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Rooftop Pool"
    assert result["result"].unique_id == "rooftop_pool"
    assert result["data"][CONF_POOL_ID] == "rooftop_pool"
    assert result["data"][CONF_POOL_NAME] == "Rooftop Pool"


async def test_config_flow_allows_multiple_pools(hass) -> None:
    """Additional pools create additional config entries instead of aborting."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Rooftop Pool",
        unique_id="rooftop_pool",
        data={CONF_POOL_ID: "rooftop_pool", CONF_POOL_NAME: "Rooftop Pool"},
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_POOL_NAME: "Rooftop Pool"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Rooftop Pool"
    assert result["result"].unique_id == "rooftop_pool_2"
    assert result["data"][CONF_POOL_ID] == "rooftop_pool_2"
