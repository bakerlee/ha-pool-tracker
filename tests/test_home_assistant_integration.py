"""Smoke tests for the Home Assistant config-entry lifecycle."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("homeassistant")

from homeassistant.exceptions import ServiceValidationError  # noqa: E402
from homeassistant.helpers import device_registry as dr  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.pool_tracker.const import (  # noqa: E402
    CONF_DEFAULT_TESTING_METHOD,
    CONF_POOL_ID,
    CONF_POOL_NAME,
    CONF_POOL_VOLUME,
    CONF_POOL_VOLUME_UNIT,
    CONF_TRACKED_METRICS,
    CONF_TYPICALLY_COVERED,
    CONF_WEATHER_ENTITY_ID,
    DOMAIN,
    SERVICE_GET_PREDICTION,
    SERVICE_LOG_CHEMICAL_ADDITION,
    SERVICE_LOG_WATER_TEST,
    WATER_READING_CYA,
    WATER_READING_FREE_CHLORINE,
    WATER_READING_PH,
    WATER_READING_TOTAL_ALKALINITY,
    WATER_READING_TOTAL_CHLORINE,
    WATER_READING_TOTAL_HARDNESS,
    WATER_TESTING_METHOD,
)


async def test_setup_unload_reload_config_entry(hass) -> None:
    """Smoke test setup, unload, and reload for a Pool Tracker config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id=DOMAIN,
        data={
            CONF_POOL_ID: "pool",
            CONF_POOL_NAME: "Pool",
            CONF_POOL_VOLUME: 12000.0,
            CONF_POOL_VOLUME_UNIT: "gal",
            CONF_DEFAULT_TESTING_METHOD: "strips",
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
    assert (
        "free_chlorine"
        in entry.runtime_data.pool_profiles["pool"][CONF_TRACKED_METRICS]
    )
    assert entry.runtime_data.pool_profiles["pool"][CONF_TYPICALLY_COVERED] is False
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
        data={CONF_POOL_ID: "pool", CONF_POOL_NAME: "Pool"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entry.runtime_data.pool_profiles["pool"][CONF_DEFAULT_TESTING_METHOD]
        == "strips"
    )
    assert entry.runtime_data.pool_profiles["pool"][CONF_TRACKED_METRICS]


async def test_log_water_test_stores_full_agent_payload(hass) -> None:
    """Agent-submitted water tests store every explicit reading."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="pool",
        data={CONF_POOL_ID: "pool", CONF_POOL_NAME: "Pool"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        {
            "source": "openclaw",
            WATER_READING_FREE_CHLORINE: 1,
            WATER_READING_TOTAL_CHLORINE: 1,
            WATER_READING_PH: 7.8,
            WATER_READING_TOTAL_ALKALINITY: 120,
            WATER_READING_TOTAL_HARDNESS: 250,
            WATER_READING_CYA: 0,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    stored = entry.runtime_data.store.records("pool")[0]
    assert stored["source"] == "openclaw"
    assert stored["readings"] == {
        WATER_READING_FREE_CHLORINE: {"value": 1.0, "unit": "ppm"},
        WATER_READING_TOTAL_CHLORINE: {"value": 1.0, "unit": "ppm"},
        WATER_READING_PH: {"value": 7.8, "unit": "pH"},
        WATER_READING_TOTAL_ALKALINITY: {"value": 120.0, "unit": "ppm"},
        WATER_READING_TOTAL_HARDNESS: {"value": 250.0, "unit": "ppm"},
        WATER_READING_CYA: {"value": 0.0, "unit": "ppm"},
    }


async def test_options_flow_opens_for_existing_pool(hass) -> None:
    """Existing config entries can open the pool profile options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id=DOMAIN,
        data={CONF_POOL_ID: "pool", CONF_POOL_NAME: "Pool"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_fresh_pool_chlorine_sensors_start_unknown(hass) -> None:
    """A pool with no records does not invent chlorine states."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="pool",
        data={CONF_POOL_ID: "pool", CONF_POOL_NAME: "Pool"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    free_chlorine = _sensor_state(hass, "free_chlorine")
    predicted = _sensor_state(hass, "free_chlorine_predicted")
    assert free_chlorine is not None
    assert predicted is not None
    assert free_chlorine.state == "unknown"
    assert predicted.state == "unknown"
    assert predicted.attributes["pool_id"] == "pool"
    assert predicted.attributes["recent_water_tests"] == []
    assert predicted.attributes["recent_chemical_additions"] == []
    assert predicted.attributes["quick_chemical_additions"] == []


async def test_disabled_metrics_do_not_create_reading_or_prediction_sensors(
    hass,
) -> None:
    """Configured metric tracking controls and prunes the exposed sensor set."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="pool",
        data={
            CONF_POOL_ID: "pool",
            CONF_POOL_NAME: "Pool",
            CONF_TRACKED_METRICS: ["salt"],
        },
    )
    entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    ph_unique_id = f"{entry.entry_id}_pool_ph"
    ph_predicted_unique_id = f"{entry.entry_id}_pool_ph_predicted"
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        ph_unique_id,
        suggested_object_id="pool_ph",
        config_entry=entry,
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        ph_predicted_unique_id,
        suggested_object_id="pool_ph_predicted",
        config_entry=entry,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    salt = _sensor_state(hass, "salt")
    assert salt is not None
    assert salt.state == "unknown"
    assert salt.attributes[CONF_TRACKED_METRICS] == ["salt"]
    assert _sensor_state(hass, "ph") is None
    assert _sensor_state(hass, "ph_predicted") is None
    assert _sensor_state(hass, "free_chlorine_predicted") is None
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, ph_unique_id) is None
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, ph_predicted_unique_id)
        is None
    )


async def test_multiple_config_entries_share_store_and_route_by_pool_id(hass) -> None:
    """Multiple configured pools can log records without clobbering storage."""
    rooftop = MockConfigEntry(
        domain=DOMAIN,
        title="Rooftop Pool",
        unique_id="rooftop_pool",
        data={CONF_POOL_ID: "rooftop_pool", CONF_POOL_NAME: "Rooftop Pool"},
    )
    spa = MockConfigEntry(
        domain=DOMAIN,
        title="Spa",
        unique_id="spa",
        data={CONF_POOL_ID: "spa", CONF_POOL_NAME: "Spa"},
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

    assert (
        rooftop.runtime_data.store.records("rooftop_pool")[0]["readings"]["ph"]["value"]
        == 7.2
    )
    assert spa.runtime_data.store.records("spa")[0]["readings"]["ph"]["value"] == 7.6

    with pytest.raises(ServiceValidationError, match="pool_id is required"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_LOG_WATER_TEST,
            {"ph": 7.4},
            blocking=True,
        )


async def test_prediction_sensor_updates_after_water_test_and_context_change(
    hass,
) -> None:
    """Prediction sensors update from records and optional context entities."""
    hass.states.async_set("weather.home", "sunny", {"uv_index": 0})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="pool",
        data={
            CONF_POOL_ID: "pool",
            CONF_POOL_NAME: "Pool",
            CONF_WEATHER_ENTITY_ID: "weather.home",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        {"free_chlorine": 3.0, "ph": 7.4},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = _sensor_state(hass, "free_chlorine_predicted")
    assert state is not None
    assert state.state != "unknown"
    assert state.attributes["model_inputs"]["sunlight"] == 0.0
    assert state.attributes["series"]
    assert state.attributes["actuals"]
    assert state.attributes["chemical_additions"] == []

    prediction = await _get_prediction(hass, state.entity_id)
    assert prediction["series"] == state.attributes["series"]
    assert prediction["actuals"] == state.attributes["actuals"]
    assert prediction["chemical_additions"] == state.attributes["chemical_additions"]

    ph_state = _sensor_state(hass, "ph_predicted")
    assert ph_state is not None
    response = await _get_prediction_response(
        hass, [state.entity_id, ph_state.entity_id]
    )
    assert set(response) == {state.entity_id, ph_state.entity_id}
    assert (
        response[state.entity_id]["prediction"]["series"] == state.attributes["series"]
    )
    assert (
        response[ph_state.entity_id]["prediction"]["series"]
        == ph_state.attributes["series"]
    )

    hass.states.async_set("weather.home", "sunny", {"uv_index": 10})
    await hass.async_block_till_done()

    updated = _sensor_state(hass, "free_chlorine_predicted")
    assert updated is not None
    assert updated.attributes["model_inputs"]["sunlight"] == 1.0


async def test_prediction_sensor_applies_logged_chlorine_addition(hass) -> None:
    """Chemical addition records influence the free chlorine prediction sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Spa",
        unique_id="spa",
        data={
            CONF_POOL_ID: "spa",
            CONF_POOL_NAME: "Spa",
            CONF_POOL_VOLUME: 400,
            CONF_POOL_VOLUME_UNIT: "gal",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        {"free_chlorine": 0.0},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_CHEMICAL_ADDITION,
        {"chemical": "dichlor", "amount": 1, "unit": "Tbsp"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = _sensor_state(hass, "free_chlorine_predicted")
    assert state is not None
    assert float(state.state) > 0
    assert state.attributes["model_inputs"]["chemical_additions"]
    assert state.attributes["chemical_additions"]
    assert state.attributes["recent_chemical_additions"][0]["summary"] == (
        "dichlor: 1 Tbsp"
    )
    assert state.attributes["quick_chemical_additions"] == [
        {
            "chemical": "dichlor",
            "amount": 1.0,
            "unit": "Tbsp",
            "summary": "dichlor: 1 Tbsp",
        }
    ]


async def test_prediction_sensor_applies_chlorine_addition_without_prior_reading(
    hass,
) -> None:
    """Free chlorine prediction stays unknown until an actual reading exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Spa",
        unique_id="spa",
        data={
            CONF_POOL_ID: "spa",
            CONF_POOL_NAME: "Spa",
            CONF_POOL_VOLUME: 400,
            CONF_POOL_VOLUME_UNIT: "gal",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_CHEMICAL_ADDITION,
        {"chemical": "dichlor", "amount": 1, "unit": "Tbsp"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = _sensor_state(hass, "free_chlorine_predicted")
    assert state is not None
    assert state.state == "unknown"

    prediction = await _get_prediction(hass, state.entity_id)
    assert prediction is None


async def test_water_test_event_entity_fires(hass) -> None:
    """Logging a water test triggers the pool's water-test event entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="pool",
        data={CONF_POOL_ID: "pool", CONF_POOL_NAME: "Pool"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    event_state = next(
        state
        for state in hass.states.async_all("event")
        if state.entity_id.endswith("water_test")
    )
    assert event_state.state in ("unknown", "unavailable")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        {"ph": 7.2},
        blocking=True,
    )
    await hass.async_block_till_done()

    updated = hass.states.get(event_state.entity_id)
    assert updated is not None
    assert updated.attributes["event_type"] == "water_test"
    assert updated.attributes["readings"]["ph"] == {"value": 7.2, "unit": "pH"}
    assert updated.attributes[WATER_TESTING_METHOD] == "strips"


async def test_backfilled_water_test_event_entity_fires_for_appended_record(
    hass,
) -> None:
    """Backfilled water tests trigger the event entity with their event time."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="pool",
        data={CONF_POOL_ID: "pool", CONF_POOL_NAME: "Pool"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    event_state = next(
        state
        for state in hass.states.async_all("event")
        if state.entity_id.endswith("water_test")
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        {"event_timestamp": "2026-06-15T12:00:00-05:00", "ph": 7.8},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        {"event_timestamp": "2026-06-14T19:30:00-05:00", "ph": 7.2},
        blocking=True,
    )
    await hass.async_block_till_done()

    updated = hass.states.get(event_state.entity_id)
    assert updated is not None
    assert updated.attributes["event_type"] == "water_test"
    assert updated.attributes["event_timestamp"] == "2026-06-15T00:30:00+00:00"
    assert updated.attributes["readings"]["ph"] == {"value": 7.2, "unit": "pH"}


async def test_chemical_addition_event_entity_fires(hass) -> None:
    """Logging a chemical addition triggers the pool's event entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="pool",
        data={CONF_POOL_ID: "pool", CONF_POOL_NAME: "Pool"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    event_state = next(
        state
        for state in hass.states.async_all("event")
        if state.entity_id.endswith("chemical_addition")
    )
    assert event_state.state in ("unknown", "unavailable")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOG_CHEMICAL_ADDITION,
        {"chemical": "dichlor", "amount": 1, "unit": "Tbsp"},
        blocking=True,
    )
    await hass.async_block_till_done()

    updated = hass.states.get(event_state.entity_id)
    assert updated is not None
    assert updated.attributes["event_type"] == "chemical_addition"
    assert updated.attributes["chemical"] == "dichlor"
    assert updated.attributes["summary"] == "dichlor: 1 Tbsp"


async def _get_prediction(hass, entity_id: str) -> dict[str, Any]:
    response = await _get_prediction_response(hass, entity_id)
    return response[entity_id]["prediction"]


async def _get_prediction_response(
    hass, entity_id: str | list[str]
) -> dict[str, dict[str, Any]]:
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PREDICTION,
        {"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )
    return response


def _sensor_state(hass, suffix: str):
    for state in hass.states.async_all("sensor"):
        if state.entity_id.endswith(suffix):
            return state
    return None
