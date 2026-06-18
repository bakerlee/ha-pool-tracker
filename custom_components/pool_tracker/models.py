"""Event model helpers for Pool Tracker."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .const import (
    CHEMICAL_AMOUNT_UNITS,
    CHEMICAL_OPTIONS,
    NUMERIC_WATER_READINGS,
    RECORD_TYPE_CHEMICAL_ADDITION,
    RECORD_TYPE_WATER_TEST,
    WATER_READING_WATER_CLARITY,
    WATER_TEST_READING_UNITS,
    WATER_TESTING_METHOD,
    normalize_chemical_amount_unit,
)

StorageData = dict[str, Any]
PoolRecord = dict[str, Any]

WATER_TEST_FIELDS = (
    *NUMERIC_WATER_READINGS,
    WATER_READING_WATER_CLARITY,
)


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


def to_utc_iso(value: datetime | str | None, *, default: datetime | None = None) -> str:
    """Convert a datetime-ish value into a UTC ISO 8601 string."""
    if value is None:
        value = default or utc_now()
    elif isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        value = datetime.fromisoformat(normalized)

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC).isoformat()


def parse_utc(value: str) -> datetime:
    """Parse a stored UTC timestamp."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_water_test_record(
    *,
    pool_id: str,
    readings: dict[str, Any],
    event_timestamp: datetime | str | None = None,
    source: str | None = None,
    notes: str | None = None,
    testing_method: str | None = None,
    record_id: str | None = None,
    created_timestamp: datetime | str | None = None,
) -> PoolRecord:
    """Build an append-only water test record."""
    explicit_readings: dict[str, dict[str, Any]] = {}
    for field in WATER_TEST_FIELDS:
        if field not in readings or readings[field] in (None, ""):
            continue
        explicit_readings[field] = {
            "value": readings[field],
            "unit": WATER_TEST_READING_UNITS[field],
        }

    if not explicit_readings and not notes:
        raise ValueError(
            "Water tests require at least one reading, clarity value, or note."
        )

    record = _base_record(
        pool_id=pool_id,
        record_type=RECORD_TYPE_WATER_TEST,
        event_timestamp=event_timestamp,
        source=source,
        notes=notes,
        record_id=record_id,
        created_timestamp=created_timestamp,
    ) | {
        "readings": explicit_readings,
    }
    if testing_method:
        record[WATER_TESTING_METHOD] = testing_method
    return record


def build_chemical_addition_record(
    *,
    pool_id: str,
    chemical: str,
    amount: float,
    unit: str,
    event_timestamp: datetime | str | None = None,
    source: str | None = None,
    notes: str | None = None,
    record_id: str | None = None,
    created_timestamp: datetime | str | None = None,
) -> PoolRecord:
    """Build an append-only chemical addition record."""
    chemical = chemical.strip()
    unit = normalize_chemical_amount_unit(unit)
    if not chemical:
        raise ValueError("Chemical is required.")
    if chemical not in CHEMICAL_OPTIONS:
        raise ValueError(f"Unsupported chemical: {chemical}.")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    if not unit:
        raise ValueError("Unit is required.")
    if unit not in CHEMICAL_AMOUNT_UNITS:
        raise ValueError(f"Unsupported chemical amount unit: {unit}.")

    return _base_record(
        pool_id=pool_id,
        record_type=RECORD_TYPE_CHEMICAL_ADDITION,
        event_timestamp=event_timestamp,
        source=source,
        notes=notes,
        record_id=record_id,
        created_timestamp=created_timestamp,
    ) | {
        "chemical": chemical,
        "amount": amount,
        "unit": unit,
    }


def latest_record(records: Iterable[PoolRecord], record_type: str) -> PoolRecord | None:
    """Return the most recent record of a type by event time, then creation time."""
    matches = [record for record in records if record.get("type") == record_type]
    if not matches:
        return None
    return max(matches, key=_record_sort_key)


def latest_reading(
    records: Iterable[PoolRecord], reading: str
) -> tuple[PoolRecord, dict[str, Any]] | None:
    """Return the most recent explicit reading value for a water-test field."""
    matches: list[tuple[PoolRecord, dict[str, Any]]] = []
    for record in records:
        if record.get("type") != RECORD_TYPE_WATER_TEST:
            continue
        value = record.get("readings", {}).get(reading)
        if value is not None:
            matches.append((record, value))

    if not matches:
        return None

    return max(matches, key=lambda item: _record_sort_key(item[0]))


def chemical_summary(record: PoolRecord | None) -> str | None:
    """Return a compact human-readable summary for a chemical addition."""
    if record is None:
        return None
    amount = record.get("amount")
    if isinstance(amount, float) and amount.is_integer():
        amount = int(amount)
    return f"{record.get('chemical')}: {amount} {record.get('unit')}"


def _base_record(
    *,
    pool_id: str,
    record_type: str,
    event_timestamp: datetime | str | None,
    source: str | None,
    notes: str | None,
    record_id: str | None,
    created_timestamp: datetime | str | None,
) -> PoolRecord:
    record: PoolRecord = {
        "id": record_id or uuid4().hex,
        "pool_id": pool_id,
        "type": record_type,
        "event_timestamp": to_utc_iso(event_timestamp),
        "created_timestamp": to_utc_iso(created_timestamp),
    }
    if source:
        record["source"] = source
    if notes:
        record["notes"] = notes
    return record


def _record_sort_key(record: PoolRecord) -> tuple[datetime, datetime, str]:
    return (
        parse_utc(record["event_timestamp"]),
        parse_utc(record["created_timestamp"]),
        str(record["id"]),
    )
