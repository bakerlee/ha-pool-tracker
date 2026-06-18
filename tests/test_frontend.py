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


def test_frontend_module_registers_panel_and_lovelace_card() -> None:
    """The shipped JS module contains both the panel and custom card elements."""
    module = Path(
        "custom_components/pool_tracker/frontend/pool-tracker-frontend.js"
    ).read_text()

    assert 'const CARD_TAG = "pool-tracker-graph-card"' in module
    assert 'const PANEL_TAG = "pool-tracker-panel"' in module
    assert "customElements.define(CARD_TAG, PoolTrackerGraphCard)" in module
    assert "customElements.define(PANEL_TAG, PoolTrackerPanel)" in module
    assert 'data-log="water-test"' in module
    assert 'data-log="chemical-addition"' in module
    assert "data-quick-chemical" in module
    assert 'callService("pool_tracker", service, payload)' in module
    assert "window.customCards.push" in module


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
    """The sidebar panel should keep its card instance across state pushes."""
    module = Path(
        "custom_components/pool_tracker/frontend/pool-tracker-frontend.js"
    ).read_text()

    assert "this._ensureCard()" in module
    assert "if (!this.shadowRoot || this._card)" in module
    assert "this._card.hass = hass" in module
    assert "this._card = this.shadowRoot.querySelector(CARD_TAG)" in module
