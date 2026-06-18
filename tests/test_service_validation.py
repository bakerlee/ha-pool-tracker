"""Tests for Home Assistant service validation schemas."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")
vol = pytest.importorskip("voluptuous")

from custom_components.pool_tracker import (  # noqa: E402
    _chemical_addition_service_schema,
    _water_test_service_schema,
)
from custom_components.pool_tracker.const import (  # noqa: E402
    WATER_READING_CALCIUM_HARDNESS,
    WATER_READING_COMBINED_CHLORINE,
    WATER_READING_COPPER,
    WATER_READING_IRON,
    WATER_READING_PHOSPHATES,
    WATER_READING_SALT,
    WATER_READING_TOTAL_BROMINE,
    WATER_READING_TOTAL_CHLORINE,
    WATER_READING_TOTAL_DISSOLVED_SOLIDS,
    WATER_READING_TOTAL_HARDNESS,
    WATER_READING_WATER_TEMPERATURE,
)


def test_water_test_service_validation_accepts_partial_reading() -> None:
    """The water-test service accepts any non-empty subset of readings."""
    data = _water_test_service_schema()({"ph": "7.2", "testing_method": "strips"})

    assert data["ph"] == 7.2
    assert data["source"] == "service"
    assert data["testing_method"] == "strips"


def test_water_test_service_validation_accepts_expanded_test_metrics() -> None:
    """The water-test service accepts common pool test metrics."""
    payload = {
        WATER_READING_TOTAL_CHLORINE: "3.4",
        WATER_READING_COMBINED_CHLORINE: "0.2",
        WATER_READING_TOTAL_BROMINE: "4.0",
        WATER_READING_CALCIUM_HARDNESS: "250",
        WATER_READING_TOTAL_HARDNESS: "275",
        WATER_READING_SALT: "3200",
        WATER_READING_TOTAL_DISSOLVED_SOLIDS: "1500",
        WATER_READING_PHOSPHATES: "0.1",
        WATER_READING_COPPER: "0.05",
        WATER_READING_IRON: "0.03",
        WATER_READING_WATER_TEMPERATURE: "82.5",
    }

    data = _water_test_service_schema()(payload)

    for key, value in payload.items():
        assert data[key] == float(value)


def test_water_test_service_validation_rejects_empty_payload() -> None:
    """The water-test service requires at least one reading, clarity value, or note."""
    with pytest.raises(vol.Invalid):
        _water_test_service_schema()({})


def test_water_test_service_validation_rejects_unknown_testing_method() -> None:
    """The water-test service only accepts known testing method labels."""
    with pytest.raises(vol.Invalid):
        _water_test_service_schema()({"ph": "7.2", "testing_method": "guessing"})


def test_water_test_service_validation_constrains_water_clarity() -> None:
    """Water clarity is a bounded enum, not free-form text."""
    data = _water_test_service_schema()({"water_clarity": "cloudy"})
    assert data["water_clarity"] == "cloudy"

    with pytest.raises(vol.Invalid):
        _water_test_service_schema()({"water_clarity": "slightly murky"})


def test_chemical_addition_service_validation_requires_core_fields() -> None:
    """Chemical additions require chemical, amount, and unit."""
    schema = _chemical_addition_service_schema()

    with pytest.raises(vol.Invalid):
        schema({"chemical": "dichlor", "amount": 1})

    with pytest.raises(vol.Invalid):
        schema({"chemical": "dichlor", "amount": 0, "unit": "oz"})

    assert schema({"chemical": "dichlor", "amount": "0.5", "unit": "oz"}) == {
        "chemical": "dichlor",
        "amount": 0.5,
        "unit": "oz",
        "source": "service",
    }
    assert schema({"chemical": "dichlor", "amount": "1", "unit": "Tbsp"}) == {
        "chemical": "dichlor",
        "amount": 1.0,
        "unit": "Tbsp",
        "source": "service",
    }
    for unit in ("tbsp", "tablespoon", "tablespoons", "Tablespoons"):
        assert schema({"chemical": "dichlor", "amount": "1", "unit": unit}) == {
            "chemical": "dichlor",
            "amount": 1.0,
            "unit": "Tbsp",
            "source": "service",
        }


def test_chemical_addition_service_validation_rejects_unknown_values() -> None:
    """Chemical addition service values are bounded enums."""
    schema = _chemical_addition_service_schema()

    with pytest.raises(vol.Invalid):
        schema({"chemical": "mystery powder", "amount": 1, "unit": "oz"})

    with pytest.raises(vol.Invalid):
        schema({"chemical": "dichlor", "amount": 1, "unit": "scoop"})
