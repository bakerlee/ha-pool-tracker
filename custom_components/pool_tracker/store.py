"""Persistent event storage for Pool Tracker."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Protocol

from homeassistant.helpers.storage import Store

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import CONF_POOL_ID, DEFAULT_POOL_ID, DOMAIN
from .models import PoolRecord, StorageData, latest_reading, latest_record

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.events"


class StoreBackend(Protocol):
    """Protocol for Home Assistant storage and unit-test in-memory storage."""

    async def async_load(self) -> StorageData | None:
        """Load storage data."""

    async def async_save(self, data: StorageData) -> None:
        """Save storage data."""


Listener = Callable[[], None]


class PoolTrackerStore:
    """Append-only event store with an explicit migration boundary."""

    def __init__(
        self, backend: StoreBackend, *, default_pool_id: str = DEFAULT_POOL_ID
    ) -> None:
        self._backend = backend
        self._default_pool_id = default_pool_id
        self._data: StorageData | None = None
        self._listeners: list[Listener] = []

    async def async_load(self) -> None:
        """Load or initialize storage."""
        loaded = await self._backend.async_load()
        self._data = self._migrate(loaded)
        if loaded != self._data:
            await self._backend.async_save(self._data)

    @property
    def data(self) -> StorageData:
        """Return loaded storage data."""
        if self._data is None:
            raise RuntimeError("Pool Tracker storage has not been loaded.")
        return self._data

    def records(self, pool_id: str | None = None) -> list[PoolRecord]:
        """Return event records for one pool."""
        pool = self._pool(pool_id)
        return list(pool["records"])

    def latest_record(
        self, record_type: str, pool_id: str | None = None
    ) -> PoolRecord | None:
        """Return the latest record for one pool and type."""
        return latest_record(self.records(pool_id), record_type)

    def latest_reading(
        self, reading: str, pool_id: str | None = None
    ) -> tuple[PoolRecord, dict[str, Any]] | None:
        """Return the latest explicit reading for a water-test field."""
        return latest_reading(self.records(pool_id), reading)

    async def async_append(self, record: PoolRecord) -> PoolRecord:
        """Append a record and persist it."""
        stored = deepcopy(record)
        pool = self._pool(stored.get(CONF_POOL_ID))
        pool["records"].append(stored)
        await self._backend.async_save(self.data)
        self._notify_listeners()
        return stored

    def async_listen(self, listener: Listener) -> Callable[[], None]:
        """Listen for appended records."""
        self._listeners.append(listener)

        def remove_listener() -> None:
            self._listeners.remove(listener)

        return remove_listener

    def _pool(self, pool_id: str | None) -> StorageData:
        pool_id = pool_id or self._default_pool_id
        pools: dict[str, StorageData] = self.data.setdefault("pools", {})
        pool = pools.setdefault(pool_id, {"records": []})
        pool.setdefault("records", [])
        return pool

    def _notify_listeners(self) -> None:
        for listener in list(self._listeners):
            listener()

    def _migrate(self, loaded: StorageData | None) -> StorageData:
        if not loaded:
            return {"version": 1, "pools": {}}

        version = loaded.get("version", 1)
        if version != 1:
            raise ValueError(f"Unsupported Pool Tracker storage version: {version}")

        data = deepcopy(loaded)
        data.setdefault("version", 1)
        data.setdefault("pools", {})
        for pool in data["pools"].values():
            pool.setdefault("records", [])
        return data


def create_home_assistant_store(hass: HomeAssistant) -> Store[StorageData]:
    """Create the Home Assistant storage backend."""
    return Store(hass, STORAGE_VERSION, STORAGE_KEY)


class MemoryStoreBackend:
    """Simple async backend for focused unit tests."""

    def __init__(self, data: StorageData | None = None) -> None:
        self.saved: StorageData | None = deepcopy(data)

    async def async_load(self) -> StorageData | None:
        """Load memory data."""
        return deepcopy(self.saved)

    async def async_save(self, data: StorageData) -> None:
        """Save memory data."""
        self.saved = deepcopy(data)
