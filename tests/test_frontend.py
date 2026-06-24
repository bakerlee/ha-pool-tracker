"""Tests for bundled Pool Tracker frontend registration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components import frontend  # noqa: E402
from homeassistant.components.lovelace.const import LOVELACE_DATA  # noqa: E402

from custom_components.pool_tracker import (  # noqa: E402
    FRONTEND_MODULE_URL,
    FRONTEND_PANEL_URL_PATH,
    FRONTEND_URL_BASE,
    PoolTrackerLovelaceConfig,
    _async_setup_frontend,
)


class FakeHTTP:
    """Capture static-path registrations."""

    def __init__(self) -> None:
        self.static_path_configs = []

    async def async_register_static_paths(self, configs) -> None:
        """Record static path configs."""
        self.static_path_configs.extend(configs)


async def test_frontend_setup_registers_static_assets_panel_and_card_module(
    hass,
) -> None:
    """Frontend setup exposes bundled assets and a zero-config sidebar panel."""
    hass.http = FakeHTTP()
    module_events = []
    hass.data[frontend.DATA_EXTRA_MODULE_URL] = frontend.UrlManager(
        lambda action, url: module_events.append((action, url)),
        [],
    )
    hass.data[LOVELACE_DATA] = SimpleNamespace(dashboards={})
    frontend.async_register_built_in_panel(
        hass,
        "custom",
        frontend_url_path=FRONTEND_PANEL_URL_PATH,
        sidebar_title="Old Pool Tracker",
    )

    await _async_setup_frontend(hass)

    assert hass.http.static_path_configs
    static_config = hass.http.static_path_configs[0]
    assert static_config.url_path == FRONTEND_URL_BASE
    assert static_config.path.endswith("custom_components/pool_tracker/frontend")
    assert static_config.cache_headers is True
    assert module_events == [("added", FRONTEND_MODULE_URL)]

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
        "custom:pool-tracker-graph-card",
        "grid",
        "entities",
        "markdown",
        "grid",
    ]
    assert cards[0] == {
        "type": "custom:pool-tracker-graph-card",
        "title": "Prediction charts",
        "entities": ["sensor.pool_free_chlorine_predicted"],
        "show_logs": False,
    }
    assert cards[1]["cards"] == [
        {
            "type": "tile",
            "entity": "sensor.pool_free_chlorine_predicted",
            "name": "Free chlorine",
        }
    ]
    assert cards[2]["entities"] == ["sensor.pool_free_chlorine"]
    assert "### Water tests" in cards[3]["content"]
    assert cards[4]["cards"][0]["tap_action"] == {
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
    assert regenerated["views"][0]["cards"][0]["type"] == (
        "custom:pool-tracker-graph-card"
    )


def test_frontend_module_registers_dashboard_strategy_and_lovelace_card() -> None:
    """The shipped JS module contains the strategy and graph card."""
    module = Path(
        "custom_components/pool_tracker/frontend/pool-tracker-frontend.js"
    ).read_text()

    assert 'const CARD_TAG = "pool-tracker-graph-card"' in module
    assert 'const STRATEGY_TAG = "ll-strategy-dashboard-pool-tracker"' in module
    assert "customElements.define(CARD_TAG, PoolTrackerGraphCard)" in module
    assert "customElements.define(STRATEGY_TAG, PoolTrackerDashboardStrategy)" in module
    assert 'data-log="water-test"' in module
    assert 'data-log="chemical-addition"' in module
    assert "data-quick-chemical" in module
    assert "data-delete-record" in module
    assert "_renderQuickChemicalActions(attrs.quick_chemical_additions || [])" in module
    assert "_renderRecentRecords(attrs)" in module
    assert 'this._callService("delete_record", payload, "Record deleted.")' in module
    assert "Delete this Pool Tracker record?" in module
    assert "Quick chemicals" not in module
    assert "enabledWaterReadingFields(attrs)" in module
    assert "tracked_metrics" in module
    assert "No prediction charts for enabled metrics." in module
    assert 'callService("pool_tracker", service, payload)' in module
    assert 'callService(\n        "pool_tracker",\n        "get_prediction"' in module
    assert "prediction_sensor" in module
    assert "window.customCards.push" in module
    assert "window.customStrategies.push" in module


def test_frontend_card_renders_all_prediction_charts_responsively() -> None:
    """The graph card shows every reading together instead of tabbing between them."""
    module = Path(
        "custom_components/pool_tracker/frontend/pool-tracker-frontend.js"
    ).read_text()

    assert '<div class="chart-list">' in module
    assert 'states.map((state) => this._renderReading(state)).join("")' in module
    assert "readingsSummary(states)" in module
    assert "container: pool-tracker-card / inline-size" in module
    assert "@container pool-tracker-card (min-width: 720px)" in module
    assert "@container pool-tracker-card (min-width: 1280px)" in module
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in module
    assert 'role="tab"' not in module
    assert "data-entity" not in module


def test_frontend_preserves_forms_between_home_assistant_updates() -> None:
    """Home Assistant state pushes should not wipe in-progress log forms."""
    module = Path(
        "custom_components/pool_tracker/frontend/pool-tracker-frontend.js"
    ).read_text()

    assert (
        "const formState = preserveFormState ? this._captureFormState() : []" in module
    )
    assert "this._restoreFormState(formState)" in module
    assert "_captureFormState()" in module
    assert "_restoreFormState(formState)" in module
    assert 'element.type !== "hidden"' in module
    assert "this._render({ preserveFormState: false })" in module


def test_frontend_card_exposes_record_delete_controls() -> None:
    """The custom card can delete recent records by record id."""
    module = Path(
        "custom_components/pool_tracker/frontend/pool-tracker-frontend.js"
    ).read_text()

    assert "recent_water_tests" in module
    assert "recent_chemical_additions" in module
    assert "record.record_id" in module
    assert 'data-record-id="${escapeHtml(recordId)}"' in module
    assert 'data-pool-id="${escapeHtml(poolId || "")}"' in module
    assert "confirm: true" in module


def test_frontend_strategy_uses_standard_lovelace_cards() -> None:
    """The dashboard strategy should render standard Lovelace cards."""
    module = Path(
        "custom_components/pool_tracker/frontend/pool-tracker-frontend.js"
    ).read_text()

    assert "class PoolTrackerPanel" not in module
    assert "window.loadCardHelpers()" not in module
    assert 'type: "tile"' in module
    assert 'type: "entities"' in module
    assert 'type: "markdown"' in module
    assert 'type: "button"' in module
    assert "columns: Math.min(2, predictionStates.length)" in module
    assert "name: readingTitle(state)" in module
    assert "show_logs: false" in module


def test_frontend_dashboard_strategy_uses_standard_lovelace_cards() -> None:
    """The Pool Tracker strategy should generate a Lovelace dashboard."""
    module = Path(
        "custom_components/pool_tracker/frontend/pool-tracker-frontend.js"
    ).read_text()

    assert "class PoolTrackerDashboardStrategy extends HTMLElement" in module
    assert "static async generate(config, hass)" in module
    assert "cards: poolTrackerCards(hass)" in module
    assert 'strategyType: "dashboard"' in module
    assert "type: STRATEGY_TYPE" in module
    assert 'service: "pool_tracker.log_chemical_addition"' in module
    assert 'source: "dashboard"' in module
