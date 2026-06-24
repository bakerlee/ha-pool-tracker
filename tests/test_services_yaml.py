"""Tests for Home Assistant service action metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


def test_chemical_addition_service_uses_selectors() -> None:
    """Chemical addition fields should not regress to free-form text."""
    services = yaml.safe_load(
        Path("custom_components/pool_tracker/services.yaml").read_text()
    )

    fields = services["log_chemical_addition"]["fields"]
    assert "select" in fields["chemical"]["selector"]
    assert "select" in fields["unit"]["selector"]
    assert fields["amount"]["selector"]["number"]["step"] == "any"
    unit_options = fields["unit"]["selector"]["select"]["options"]
    assert {option["value"] for option in unit_options} == {
        "g",
        "kg",
        "oz",
        "lb",
        "mL",
        "L",
        "Tbsp",
        "fl. oz.",
        "gal",
    }


def test_water_test_service_metadata_includes_expanded_metrics() -> None:
    """Water-test service metadata should expose the supported reading fields."""
    services = yaml.safe_load(
        Path("custom_components/pool_tracker/services.yaml").read_text()
    )

    fields = services["log_water_test"]["fields"]
    for field in (
        "total_chlorine",
        "combined_chlorine",
        "total_bromine",
        "calcium_hardness",
        "total_hardness",
        "salt",
        "total_dissolved_solids",
        "phosphates",
        "copper",
        "iron",
        "water_temperature",
    ):
        assert "number" in fields[field]["selector"]


def test_delete_record_service_requires_record_id_and_confirmation() -> None:
    """Delete metadata should expose an explicit confirmation control."""
    services = yaml.safe_load(
        Path("custom_components/pool_tracker/services.yaml").read_text()
    )

    fields = services["delete_record"]["fields"]
    assert fields["record_id"]["required"] is True
    assert "text" in fields["record_id"]["selector"]
    assert fields["confirm"]["required"] is True
    assert "boolean" in fields["confirm"]["selector"]
