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
