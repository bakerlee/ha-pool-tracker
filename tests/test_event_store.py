"""Unit tests for Pool Tracker event storage semantics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.pool_tracker.const import (
    RECORD_TYPE_CHEMICAL_ADDITION,
    RECORD_TYPE_WATER_TEST,
    WATER_READING_CALCIUM_HARDNESS,
    WATER_READING_FREE_CHLORINE,
    WATER_READING_PH,
    WATER_READING_TOTAL_CHLORINE,
    WATER_READING_TOTAL_HARDNESS,
    WATER_READING_WATER_CLARITY,
    WATER_TESTING_METHOD,
)
from custom_components.pool_tracker.models import (
    build_chemical_addition_record,
    build_water_test_record,
    chemical_summary,
)
from custom_components.pool_tracker.store import MemoryStoreBackend, PoolTrackerStore


@pytest.fixture
async def store() -> PoolTrackerStore:
    """Return a loaded in-memory store."""
    event_store = PoolTrackerStore(MemoryStoreBackend())
    await event_store.async_load()
    return event_store


async def test_storage_append_and_read_behavior(store: PoolTrackerStore) -> None:
    """Records are appended and remain readable from storage."""
    record = build_water_test_record(
        pool_id="pool",
        readings={WATER_READING_FREE_CHLORINE: 2.5},
        record_id="test-record",
    )

    stored = await store.async_append(record)

    assert stored["id"] == "test-record"
    assert store.records("pool") == [stored]
    assert stored["type"] == RECORD_TYPE_WATER_TEST


async def test_storage_delete_record_removes_one_matching_record(
    store: PoolTrackerStore,
) -> None:
    """A targeted delete removes exactly one stored record."""
    deleted_record = await store.async_append(
        build_chemical_addition_record(
            pool_id="pool",
            chemical="dichlor",
            amount=1,
            unit="Tbsp",
            record_id="delete-me",
        )
    )
    kept_record = await store.async_append(
        build_water_test_record(
            pool_id="pool",
            readings={WATER_READING_PH: 7.2},
            record_id="keep-me",
        )
    )

    deleted = await store.async_delete_record("delete-me")

    assert deleted == deleted_record
    assert store.records("pool") == [kept_record]
    assert await store.async_delete_record("delete-me") is None


async def test_storage_delete_record_rejects_ambiguous_record_ids(
    store: PoolTrackerStore,
) -> None:
    """Duplicate record ids require a pool id to make deletion explicit."""
    await store.async_append(
        build_water_test_record(
            pool_id="pool-a",
            readings={WATER_READING_PH: 7.2},
            record_id="duplicate",
        )
    )
    pool_b_record = await store.async_append(
        build_water_test_record(
            pool_id="pool-b",
            readings={WATER_READING_PH: 7.6},
            record_id="duplicate",
        )
    )

    with pytest.raises(ValueError, match="matched multiple records"):
        await store.async_delete_record("duplicate")

    deleted = await store.async_delete_record("duplicate", pool_id="pool-b")

    assert deleted == pool_b_record
    assert store.records("pool-a")[0]["id"] == "duplicate"
    assert store.records("pool-b") == []


async def test_partial_water_test_allows_subset(store: PoolTrackerStore) -> None:
    """A water test may include only one reading."""
    record = build_water_test_record(
        pool_id="pool",
        readings={WATER_READING_PH: 7.2},
    )

    await store.async_append(record)

    readings = store.records("pool")[0]["readings"]
    assert readings == {WATER_READING_PH: {"value": 7.2, "unit": "pH"}}


async def test_water_test_stores_expanded_test_metrics(
    store: PoolTrackerStore,
) -> None:
    """Expanded pool test readings are stored only when submitted."""
    record = build_water_test_record(
        pool_id="pool",
        readings={
            WATER_READING_TOTAL_CHLORINE: 3.4,
            WATER_READING_CALCIUM_HARDNESS: 250,
            WATER_READING_TOTAL_HARDNESS: 275,
        },
    )

    await store.async_append(record)

    readings = store.records("pool")[0]["readings"]
    assert readings == {
        WATER_READING_TOTAL_CHLORINE: {"value": 3.4, "unit": "ppm"},
        WATER_READING_CALCIUM_HARDNESS: {"value": 250, "unit": "ppm"},
        WATER_READING_TOTAL_HARDNESS: {"value": 275, "unit": "ppm"},
    }


async def test_water_test_stores_testing_method(store: PoolTrackerStore) -> None:
    """A water test can record the method used to produce its readings."""
    record = build_water_test_record(
        pool_id="pool",
        readings={WATER_READING_PH: 7.2},
        testing_method="strips",
    )

    await store.async_append(record)

    assert store.records("pool")[0][WATER_TESTING_METHOD] == "strips"


async def test_timestamp_backfilling(store: PoolTrackerStore) -> None:
    """Event timestamps can be backfilled separately from creation time."""
    record = build_chemical_addition_record(
        pool_id="pool",
        chemical="dichlor",
        amount=0.5,
        unit="oz",
        event_timestamp=datetime(2026, 6, 10, 19, 30, tzinfo=UTC),
        created_timestamp=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
    )

    await store.async_append(record)

    stored = store.records("pool")[0]
    assert stored["event_timestamp"] == "2026-06-10T19:30:00+00:00"
    assert stored["created_timestamp"] == "2026-06-15T12:00:00+00:00"


async def test_latest_value_derivation(store: PoolTrackerStore) -> None:
    """Latest values are derived from event timestamps in the event log."""
    await store.async_append(
        build_water_test_record(
            pool_id="pool",
            readings={WATER_READING_FREE_CHLORINE: 1.5},
            event_timestamp="2026-06-10T08:00:00-05:00",
            record_id="older",
        )
    )
    await store.async_append(
        build_water_test_record(
            pool_id="pool",
            readings={WATER_READING_FREE_CHLORINE: 3.0},
            event_timestamp="2026-06-11T08:00:00-05:00",
            record_id="newer",
        )
    )
    await store.async_append(
        build_chemical_addition_record(
            pool_id="pool",
            chemical="muriatic acid",
            amount=12,
            unit="oz",
            event_timestamp="2026-06-11T09:00:00-05:00",
        )
    )

    latest = store.latest_reading(WATER_READING_FREE_CHLORINE, "pool")
    assert latest is not None
    assert latest[0]["id"] == "newer"
    assert latest[1] == {"value": 3.0, "unit": "ppm"}
    assert chemical_summary(
        store.latest_record(RECORD_TYPE_CHEMICAL_ADDITION, "pool")
    ) == ("muriatic acid: 12 oz")


async def test_omitted_water_test_readings_do_not_inherit_previous_readings(
    store: PoolTrackerStore,
) -> None:
    """A later partial test record stores only explicitly submitted readings."""
    await store.async_append(
        build_water_test_record(
            pool_id="pool",
            readings={WATER_READING_FREE_CHLORINE: 4.0},
            event_timestamp="2026-06-10T08:00:00-05:00",
        )
    )
    later = await store.async_append(
        build_water_test_record(
            pool_id="pool",
            readings={WATER_READING_PH: 7.4, WATER_READING_WATER_CLARITY: "clear"},
            event_timestamp="2026-06-11T08:00:00-05:00",
        )
    )

    assert WATER_READING_FREE_CHLORINE not in later["readings"]
    assert later["readings"][WATER_READING_PH] == {"value": 7.4, "unit": "pH"}
    assert later["readings"][WATER_READING_WATER_CLARITY] == {
        "value": "clear",
        "unit": "description",
    }


def test_water_test_requires_content() -> None:
    """Water-test records require at least one explicit field or a note."""
    with pytest.raises(ValueError, match="at least one"):
        build_water_test_record(pool_id="pool", readings={})


def test_chemical_addition_requires_supported_chemical_and_unit() -> None:
    """Chemical-addition records use bounded chemical and unit values."""
    record = build_chemical_addition_record(
        pool_id="pool",
        chemical="dichlor",
        amount=1,
        unit="tablespoons",
    )
    assert record["unit"] == "Tbsp"

    with pytest.raises(ValueError, match="Unsupported chemical"):
        build_chemical_addition_record(
            pool_id="pool",
            chemical="mystery powder",
            amount=1,
            unit="oz",
        )

    with pytest.raises(ValueError, match="Unsupported chemical amount unit"):
        build_chemical_addition_record(
            pool_id="pool",
            chemical="dichlor",
            amount=1,
            unit="scoop",
        )
