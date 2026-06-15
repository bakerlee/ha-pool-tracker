"""Tests for Pool Tracker config helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from custom_components.pool_tracker.config_flow import build_pool_config  # noqa: E402
from custom_components.pool_tracker.const import (  # noqa: E402
    CONF_DEFAULT_TESTING_METHOD,
    CONF_POOL_NAME,
    CONF_POOL_TYPE,
    CONF_POOL_VOLUME,
    CONF_POOL_VOLUME_UNIT,
    CONF_SANITIZER_TYPE,
    CONF_SURFACE_TYPE,
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
        }
    )

    assert pool[CONF_POOL_NAME] == "Backyard Pool"
    assert pool[CONF_POOL_VOLUME] == 12000.0
    assert pool[CONF_POOL_VOLUME_UNIT] == "gal"
    assert pool[CONF_POOL_TYPE] == "outdoor"
    assert pool[CONF_SURFACE_TYPE] == "plaster"
    assert pool[CONF_SANITIZER_TYPE] == "chlorine"
    assert pool[CONF_DEFAULT_TESTING_METHOD] == "strips"
