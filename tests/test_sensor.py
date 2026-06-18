"""Tests for Pool Tracker sensor descriptions."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from custom_components.pool_tracker.sensor import (  # noqa: E402
    PARALLEL_UPDATES,
    SENSOR_DESCRIPTIONS,
)


def test_sensor_descriptions_use_clean_entity_keys() -> None:
    """Sensors use conventional names and reserve last_* for event timestamps."""
    expected_keys = [
        "free_chlorine",
        "total_chlorine",
        "combined_chlorine",
        "total_bromine",
        "ph",
        "total_alkalinity",
        "calcium_hardness",
        "total_hardness",
        "cya",
        "salt",
        "total_dissolved_solids",
        "phosphates",
        "copper",
        "iron",
        "water_temperature",
        "water_clarity",
        "free_chlorine_predicted",
        "ph_predicted",
        "total_alkalinity_predicted",
        "cya_predicted",
    ]

    assert [description.key for description in SENSOR_DESCRIPTIONS] == expected_keys
    assert [
        description.translation_key for description in SENSOR_DESCRIPTIONS
    ] == expected_keys


def test_water_clarity_is_an_enum_sensor() -> None:
    """Clarity is a bounded enum, not a free-text state."""
    from homeassistant.components.sensor import SensorDeviceClass

    clarity = next(
        description
        for description in SENSOR_DESCRIPTIONS
        if description.key == "water_clarity"
    )

    assert clarity.device_class is SensorDeviceClass.ENUM
    assert clarity.options == ["clear", "hazy", "cloudy", "green", "other"]
    assert PARALLEL_UPDATES == 0


def test_prediction_sensors_have_no_measurement_state_class() -> None:
    """Modeled predictions must not flow into long-term statistics."""
    predictions = [
        description
        for description in SENSOR_DESCRIPTIONS
        if description.key.endswith("_predicted")
    ]

    assert predictions
    assert all(description.state_class is None for description in predictions)
