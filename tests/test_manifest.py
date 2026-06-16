"""Tests for Home Assistant manifest metadata."""

from __future__ import annotations

import json
from pathlib import Path


def test_manifest_uses_real_project_metadata() -> None:
    """Manifest metadata should be usable by Home Assistant and HACS."""
    manifest = json.loads(
        Path("custom_components/pool_tracker/manifest.json").read_text()
    )

    assert manifest["codeowners"] == ["@bakerlee"]
    assert manifest["documentation"] == "https://github.com/bakerlee/ha-pool-tracker"
    assert manifest["issue_tracker"] == (
        "https://github.com/bakerlee/ha-pool-tracker/issues"
    )
    assert manifest["quality_scale"] == "bronze"
