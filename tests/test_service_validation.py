"""Tests for Home Assistant service validation schemas."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")
vol = pytest.importorskip("voluptuous")

from custom_components.pool_tracker import (  # noqa: E402
    _chemical_addition_service_schema,
    _water_test_service_schema,
)


def test_water_test_service_validation_accepts_partial_reading() -> None:
    """The water-test service accepts any non-empty subset of readings."""
    data = _water_test_service_schema()({"ph": "7.2"})

    assert data["ph"] == 7.2
    assert data["source"] == "service"


def test_water_test_service_validation_rejects_empty_payload() -> None:
    """The water-test service requires at least one reading, clarity value, or note."""
    with pytest.raises(vol.Invalid):
        _water_test_service_schema()({})


def test_chemical_addition_service_validation_requires_core_fields() -> None:
    """Chemical additions require chemical, amount, and unit."""
    schema = _chemical_addition_service_schema()

    with pytest.raises(vol.Invalid):
        schema({"chemical": "dichlor", "amount": 1})

    with pytest.raises(vol.Invalid):
        schema({"chemical": "dichlor", "amount": 0, "unit": "Tbsp"})

    assert schema({"chemical": "dichlor", "amount": "1", "unit": "Tbsp"}) == {
        "chemical": "dichlor",
        "amount": 1.0,
        "unit": "Tbsp",
        "source": "service",
    }
