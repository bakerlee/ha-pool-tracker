"""Tests for Pool Tracker Lovelace dashboard registration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components import frontend  # noqa: E402
from homeassistant.components.lovelace.const import LOVELACE_DATA  # noqa: E402

from custom_components.pool_tracker import (  # noqa: E402
    FRONTEND_PANEL_URL_PATH,
    PoolTrackerLovelaceConfig,
    _async_reset_dashboard,
    _async_setup_frontend,
)


async def test_frontend_setup_registers_editable_lovelace_panel(
    hass,
) -> None:
    """Frontend setup exposes a zero-config standard Lovelace sidebar panel."""
    hass.data[LOVELACE_DATA] = SimpleNamespace(dashboards={})

    await _async_setup_frontend(hass)

    panel = hass.data[frontend.DATA_PANELS][FRONTEND_PANEL_URL_PATH]
    assert panel.component_name == "lovelace"
    assert panel.sidebar_title == "Pool Tracker"
    assert panel.sidebar_icon == "mdi:pool"
    assert panel.config == {"mode": "storage"}

    lovelace_config = hass.data[LOVELACE_DATA].dashboards[FRONTEND_PANEL_URL_PATH]
    assert await lovelace_config.async_load(False) == {
        "title": "Pool Tracker",
        "views": [
            {
                "title": "Pool Tracker",
                "path": "pool-tracker",
                "cards": [
                    {"type": "markdown", "content": "No Pool Tracker sensors yet."}
                ],
            }
        ],
    }


async def test_frontend_panel_generates_editable_lovelace_cards(hass) -> None:
    """The sidebar dashboard exposes concrete Lovelace cards until edited."""
    hass.states.async_set(
        "sensor.pool_free_chlorine_predicted",
        "3.2",
        {
            "friendly_name": "Pool Free chlorine (Predicted)",
            "pool_id": "pool",
            "pool_name": "Pool",
            "tracked_metrics": ["free_chlorine"],
            "prediction_sensor": True,
            "prediction_reading": "free_chlorine",
            "recent_water_tests": [
                {
                    "record_id": "water-record",
                    "event_timestamp": "2026-06-15T18:30:00+00:00",
                    "readings": {"free_chlorine": 3.0},
                }
            ],
            "recent_chemical_additions": [
                {
                    "record_id": "chemical-record",
                    "event_timestamp": "2026-06-15T19:00:00+00:00",
                    "chemical": "dichlor",
                    "amount": 1,
                    "unit": "Tbsp",
                    "summary": "dichlor: 1 Tbsp",
                }
            ],
            "quick_chemical_additions": [
                {
                    "chemical": "dichlor",
                    "amount": 1,
                    "unit": "Tbsp",
                    "summary": "dichlor: 1 Tbsp",
                }
            ],
        },
    )
    hass.states.async_set(
        "sensor.pool_free_chlorine",
        "3.0",
        {
            "friendly_name": "Pool Free chlorine",
            "pool_id": "pool",
            "pool_name": "Pool",
            "tracked_metrics": ["free_chlorine"],
        },
    )

    lovelace_config = PoolTrackerLovelaceConfig(hass)

    config = await lovelace_config.async_load(False)

    cards = config["views"][0]["cards"]
    assert [card["type"] for card in cards] == [
        "grid",
        "entities",
        "markdown",
        "grid",
        "grid",
    ]
    assert not any(str(card["type"]).startswith("custom:") for card in cards)
    assert cards[0]["title"] == "Predictions now"
    assert cards[0]["cards"] == [
        {
            "type": "tile",
            "entity": "sensor.pool_free_chlorine_predicted",
            "name": "Free chlorine",
        }
    ]
    assert cards[1]["entities"] == ["sensor.pool_free_chlorine"]
    assert "### Water tests" in cards[2]["content"]
    assert cards[3]["title"] == "Repeat chemical additions"
    assert cards[3]["cards"][0]["tap_action"] == {
        "action": "call-service",
        "service": "pool_tracker.log_chemical_addition",
        "data": {
            "pool_id": "pool",
            "source": "dashboard",
            "chemical": "dichlor",
            "amount": 1,
            "unit": "Tbsp",
        },
    }
    assert cards[4]["title"] == "Delete recent records"
    delete_action = cards[4]["cards"][0]["tap_action"]
    assert delete_action == {
        "action": "call-service",
        "service": "pool_tracker.delete_record",
        "confirmation": {"text": delete_action["confirmation"]["text"]},
        "data": {
            "pool_id": "pool",
            "record_id": "water-record",
            "confirm": True,
        },
    }
    assert delete_action["confirmation"]["text"].startswith("Delete ")
    assert cards[4]["cards"][1]["tap_action"]["data"] == {
        "pool_id": "pool",
        "record_id": "chemical-record",
        "confirm": True,
    }


async def test_frontend_panel_persists_user_edited_lovelace_config(hass) -> None:
    """Saved dashboard edits should not be regenerated over user changes."""
    lovelace_config = PoolTrackerLovelaceConfig(hass)
    edited = {
        "title": "My Pool",
        "views": [
            {
                "title": "Main",
                "cards": [{"type": "entities", "entities": ["sensor.pool_ph"]}],
            }
        ],
    }

    await lovelace_config.async_save(edited)
    hass.states.async_set(
        "sensor.pool_ph_predicted",
        "7.4",
        {
            "pool_id": "pool",
            "tracked_metrics": ["ph"],
            "prediction_sensor": True,
            "prediction_reading": "ph",
        },
    )

    assert await lovelace_config.async_load(False) == edited

    await lovelace_config.async_delete()

    regenerated = await lovelace_config.async_load(False)
    assert regenerated["title"] == "Pool Tracker"
    assert regenerated["views"][0]["cards"][0]["type"] == "grid"


async def test_frontend_reset_discards_saved_dashboard_config(hass) -> None:
    """Resetting the dashboard returns edited layouts to generated Lovelace cards."""
    hass.data[LOVELACE_DATA] = SimpleNamespace(dashboards={})
    await _async_setup_frontend(hass)
    lovelace_config = hass.data[LOVELACE_DATA].dashboards[FRONTEND_PANEL_URL_PATH]
    edited = {
        "title": "Edited",
        "views": [{"title": "Main", "cards": [{"type": "markdown", "content": "x"}]}],
    }
    await lovelace_config.async_save(edited)

    await _async_reset_dashboard(hass)

    regenerated = await lovelace_config.async_load(False)
    assert regenerated["title"] == "Pool Tracker"
    assert regenerated["views"][0]["cards"] == [
        {"type": "markdown", "content": "No Pool Tracker sensors yet."}
    ]
