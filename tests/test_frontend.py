"""Tests for bundled Pool Tracker frontend registration."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components import frontend  # noqa: E402

from custom_components.pool_tracker import (  # noqa: E402
    FRONTEND_MODULE_URL,
    FRONTEND_PANEL_URL_PATH,
    FRONTEND_URL_BASE,
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

    await _async_setup_frontend(hass)

    assert hass.http.static_path_configs
    static_config = hass.http.static_path_configs[0]
    assert static_config.url_path == FRONTEND_URL_BASE
    assert static_config.path.endswith("custom_components/pool_tracker/frontend")
    assert static_config.cache_headers is True
    assert module_events == [("added", FRONTEND_MODULE_URL)]

    panel = hass.data[frontend.DATA_PANELS][FRONTEND_PANEL_URL_PATH]
    assert panel.component_name == "custom"
    assert panel.sidebar_title == "Pool Tracker"
    assert panel.sidebar_icon == "mdi:pool"
    assert panel.config["_panel_custom"]["module_url"] == FRONTEND_MODULE_URL
    assert panel.config["_panel_custom"]["name"] == "pool-tracker-panel"
    assert panel.config["_panel_custom"].get("config_panel_domain") is None


def test_frontend_module_registers_panel_and_lovelace_card() -> None:
    """The shipped JS module contains the panel, strategy, and graph card."""
    module = Path(
        "custom_components/pool_tracker/frontend/pool-tracker-frontend.js"
    ).read_text()

    assert 'const CARD_TAG = "pool-tracker-graph-card"' in module
    assert 'const PANEL_TAG = "pool-tracker-panel"' in module
    assert 'const STRATEGY_TAG = "ll-strategy-dashboard-pool-tracker"' in module
    assert "customElements.define(CARD_TAG, PoolTrackerGraphCard)" in module
    assert "customElements.define(PANEL_TAG, PoolTrackerPanel)" in module
    assert "customElements.define(STRATEGY_TAG, PoolTrackerDashboardStrategy)" in module
    assert 'data-log="water-test"' in module
    assert 'data-log="chemical-addition"' in module
    assert "data-quick-chemical" in module
    assert "_renderQuickChemicalActions(attrs.quick_chemical_additions || [])" in module
    assert "Quick chemicals" not in module
    assert "enabledWaterReadingFields(attrs)" in module
    assert "tracked_metrics" in module
    assert "No prediction charts for enabled metrics." in module
    assert 'callService("pool_tracker", service, payload)' in module
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


def test_frontend_panel_reuses_card_between_home_assistant_updates() -> None:
    """The sidebar panel should render standard Lovelace cards."""
    module = Path(
        "custom_components/pool_tracker/frontend/pool-tracker-frontend.js"
    ).read_text()

    assert "window.loadCardHelpers()" in module
    assert "helpers.createCardElement(config)" in module
    assert "_updateCards()" in module
    assert 'type: "tile"' in module
    assert 'type: "entities"' in module
    assert 'type: "markdown"' in module
    assert 'type: "button"' in module
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
