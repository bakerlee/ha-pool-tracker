"""Tests for Pool Tracker sensor descriptions."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from custom_components.pool_tracker.sensor import SENSOR_DESCRIPTIONS  # noqa: E402


def test_sensor_descriptions_use_clean_entity_keys() -> None:
    """Sensors use conventional names and reserve last_* for event timestamps."""
    expected_keys = [
        "last_water_test",
        "last_chemical_addition",
        "free_chlorine",
        "ph",
        "total_alkalinity",
        "cya",
        "water_clarity",
        "chemical_addition_summary",
    ]

    assert [description.key for description in SENSOR_DESCRIPTIONS] == expected_keys
    assert [
        description.translation_key for description in SENSOR_DESCRIPTIONS
    ] == expected_keys
