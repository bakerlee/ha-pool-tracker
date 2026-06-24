"""Pool Tracker custom integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import frontend
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.components.lovelace.const import (
    CONF_ICON,
    CONF_REQUIRE_ADMIN,
    CONF_SHOW_IN_SIDEBAR,
    CONF_TITLE,
    LOVELACE_DATA,
    MODE_STORAGE,
)
from homeassistant.components.lovelace.dashboard import LovelaceConfig
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import storage
from homeassistant.helpers.json import json_bytes, json_fragment
from homeassistant.util import dt as dt_util

from .const import (
    CHEMICAL_AMOUNT_UNITS,
    CHEMICAL_OPTIONS,
    CONF_DEFAULT_TESTING_METHOD,
    CONF_POOL_ID,
    CONF_POOL_NAME,
    CONF_TRACKED_METRICS,
    CONF_TYPICALLY_COVERED,
    DEFAULT_TESTING_METHOD,
    DOMAIN,
    EVENT_RECORD_CREATED,
    EVENT_RECORD_DELETED,
    NUMERIC_WATER_READINGS,
    PLATFORMS,
    SELECT_LABELS,
    SERVICE_DELETE_RECORD,
    SERVICE_LOG_CHEMICAL_ADDITION,
    SERVICE_LOG_WATER_TEST,
    SERVICE_RESET_DASHBOARD,
    WATER_CLARITY_OPTIONS,
    WATER_READING_PH,
    WATER_READING_WATER_CLARITY,
    WATER_TESTING_METHOD,
    WATER_TESTING_METHODS,
    enabled_water_test_metrics,
    normalize_chemical_amount_unit,
)
from .models import build_chemical_addition_record, build_water_test_record
from .store import PoolTrackerStore, create_home_assistant_store

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

    type PoolTrackerConfigEntry = ConfigEntry[PoolTrackerRuntime]

_LOGGER = logging.getLogger(__name__)
FRONTEND_PANEL_URL_PATH = DOMAIN
FRONTEND_DASHBOARD_STORAGE_KEY = f"lovelace.{FRONTEND_PANEL_URL_PATH}"
FRONTEND_DASHBOARD_STORAGE_VERSION = 1


class PoolTrackerLovelaceConfig(LovelaceConfig):
    """Editable Lovelace dashboard for the Pool Tracker sidebar tab."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass, FRONTEND_PANEL_URL_PATH, _frontend_dashboard_metadata())
        self._store = storage.Store[dict[str, Any]](
            hass, FRONTEND_DASHBOARD_STORAGE_VERSION, FRONTEND_DASHBOARD_STORAGE_KEY
        )
        self._data: dict[str, Any] | None = None
        self._json_config: json_fragment | None = None

    @property
    def mode(self) -> str:
        """Return the Lovelace config mode."""
        return MODE_STORAGE

    async def async_get_info(self) -> dict[str, Any]:
        """Return dashboard metadata."""
        config = await self.async_load(False)
        return {"mode": self.mode, "views": len(config.get("views", []))}

    async def async_load(self, force: bool) -> dict[str, Any]:
        """Return the generated dashboard config."""
        if force:
            self._data = None
            self._json_config = None
        data = self._data or await self._async_load_data()
        if data["config"] is not None:
            return data["config"]
        return _pool_tracker_lovelace_config(self.hass)

    async def async_json(self, force: bool) -> json_fragment:
        """Return the dashboard config as JSON."""
        config = await self.async_load(force)
        if self._data is not None and self._data["config"] is None:
            return json_fragment(json_bytes(config))
        if self._json_config is None or force:
            self._json_config = json_fragment(json_bytes(config))
        return self._json_config

    async def async_save(self, config: dict[str, Any]) -> None:
        """Persist a user-edited Lovelace config."""
        data = self._data or await self._async_load_data()
        data["config"] = config
        self._json_config = None
        self._config_updated()
        await self._store.async_save(data)

    async def async_delete(self) -> None:
        """Remove the user-edited Lovelace config and return to generated cards."""
        await self._store.async_remove()
        self._data = {"config": None}
        self._json_config = None
        self._config_updated()

    async def _async_load_data(self) -> dict[str, Any]:
        """Load the stored Lovelace config wrapper."""
        self._data = await self._store.async_load() or {"config": None}
        return self._data


@dataclass
class PoolTrackerRuntime:
    """Runtime data for one Pool Tracker config entry."""

    store: PoolTrackerStore
    pools: dict[str, str]
    pool_profiles: dict[str, dict[str, Any]]


def _frontend_dashboard_metadata() -> dict[str, Any]:
    """Return metadata for the Pool Tracker Lovelace dashboard."""
    return {
        "id": FRONTEND_PANEL_URL_PATH,
        CONF_TITLE: "Pool Tracker",
        CONF_ICON: "mdi:pool",
        CONF_SHOW_IN_SIDEBAR: True,
        CONF_REQUIRE_ADMIN: False,
    }


def _pool_tracker_lovelace_config(hass: HomeAssistant) -> dict[str, Any]:
    """Build the default editable Pool Tracker dashboard config."""
    return {
        "title": "Pool Tracker",
        "views": [
            {
                "title": "Pool Tracker",
                "path": "pool-tracker",
                "cards": _pool_tracker_lovelace_cards(hass),
            }
        ],
    }


def _pool_tracker_lovelace_cards(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Build the concrete Lovelace cards for the Pool Tracker dashboard."""
    prediction_states = _prediction_states_for_hass(hass)
    log_states = _pool_log_states_for_hass(hass)
    latest_reading_states = [
        state for state in log_states if not _is_prediction_state(state)
    ]
    selected_log_state = prediction_states[0] if prediction_states else None
    if selected_log_state is None and log_states:
        selected_log_state = log_states[0]

    if not prediction_states and not latest_reading_states:
        return [{"type": "markdown", "content": "No Pool Tracker sensors yet."}]

    cards: list[dict[str, Any]] = []
    if prediction_states:
        cards.append(
            {
                "type": "grid",
                "title": "Predictions now",
                "columns": min(2, len(prediction_states)),
                "square": False,
                "cards": [
                    {
                        "type": "tile",
                        "entity": state.entity_id,
                        "name": _reading_title(state),
                    }
                    for state in prediction_states
                ],
            }
        )

    if latest_reading_states:
        cards.append(
            {
                "type": "entities",
                "title": "Latest readings",
                "show_header_toggle": False,
                "entities": [state.entity_id for state in latest_reading_states],
            }
        )

    if recent_records := _recent_records_markdown(selected_log_state):
        cards.append(
            {
                "type": "markdown",
                "title": "Recent records",
                "content": recent_records,
            }
        )

    if quick_cards := _quick_chemical_cards(selected_log_state):
        cards.append(
            {
                "type": "grid",
                "title": "Repeat chemical additions",
                "columns": min(2, len(quick_cards)),
                "square": False,
                "cards": quick_cards,
            }
        )

    if delete_cards := _delete_record_cards(selected_log_state):
        cards.append(
            {
                "type": "grid",
                "title": "Delete recent records",
                "columns": min(2, len(delete_cards)),
                "square": False,
                "cards": delete_cards,
            }
        )

    return cards


def _prediction_states_for_hass(hass: HomeAssistant) -> list[Any]:
    """Return Pool Tracker prediction states sorted for Lovelace output."""
    return sorted(
        (
            state
            for state in hass.states.async_all("sensor")
            if _is_prediction_state(state)
        ),
        key=_state_title,
    )


def _pool_log_states_for_hass(hass: HomeAssistant) -> list[Any]:
    """Return Pool Tracker log-capable states sorted for Lovelace output."""
    return sorted(
        (
            state
            for state in hass.states.async_all("sensor")
            if _is_pool_log_state(state)
        ),
        key=_state_title,
    )


def _is_prediction_state(state: Any) -> bool:
    """Return whether a state exposes a Pool Tracker prediction sensor."""
    attrs = state.attributes
    return (
        state.entity_id.startswith("sensor.")
        and attrs.get("prediction_sensor") is True
        and isinstance(attrs.get("prediction_reading"), str)
    )


def _is_pool_log_state(state: Any) -> bool:
    """Return whether a state exposes Pool Tracker log attributes."""
    attrs = state.attributes
    return (
        state.entity_id.startswith("sensor.")
        and attrs.get("pool_id") is not None
        and isinstance(attrs.get("tracked_metrics"), list)
    )


def _state_title(state: Any) -> str:
    """Return a friendly title for a Home Assistant state."""
    return state.attributes.get("friendly_name") or state.entity_id


def _clean_title(state: Any) -> str:
    """Return a friendly title without the prediction suffix."""
    return _state_title(state).replace(" (Predicted)", "")


def _reading_title(state: Any) -> str:
    """Return a short reading label for a Pool Tracker sensor."""
    title = _clean_title(state)
    pool_name = state.attributes.get("pool_name")
    if pool_name and title.startswith(f"{pool_name} "):
        return title[len(pool_name) + 1 :]
    return title


def _quick_chemical_cards(state: Any | None) -> list[dict[str, Any]]:
    """Return standard Lovelace button cards for repeat chemical actions."""
    attrs = state.attributes if state is not None else {}
    quick_additions = attrs.get("quick_chemical_additions") or []
    return [
        {
            "type": "button",
            "name": action.get("summary") or _chemical_summary(action),
            "icon": "mdi:repeat",
            "tap_action": {
                "action": "call-service",
                "service": "pool_tracker.log_chemical_addition",
                "data": _compact_object(
                    {
                        "pool_id": attrs.get("pool_id"),
                        "source": "dashboard",
                        "chemical": action.get("chemical"),
                        "amount": _numeric_or_original(action.get("amount")),
                        "unit": action.get("unit"),
                    }
                ),
            },
        }
        for action in quick_additions
    ]


def _delete_record_cards(state: Any | None) -> list[dict[str, Any]]:
    """Return standard Lovelace button cards for recent record deletion."""
    attrs = state.attributes if state is not None else {}
    cards: list[dict[str, Any]] = []
    for record in attrs.get("recent_water_tests") or []:
        if card := _delete_record_card(attrs, record, _water_test_line, "mdi:delete"):
            cards.append(card)
    for record in attrs.get("recent_chemical_additions") or []:
        if card := _delete_record_card(
            attrs, record, _chemical_line, "mdi:delete-outline"
        ):
            cards.append(card)
    return cards


def _delete_record_card(
    attrs: dict[str, Any],
    record: dict[str, Any],
    line_fn: Any,
    icon: str,
) -> dict[str, Any] | None:
    record_id = record.get("record_id")
    if not record_id:
        return None
    label = line_fn(record)
    return {
        "type": "button",
        "name": f"Delete {label}",
        "icon": icon,
        "tap_action": {
            "action": "call-service",
            "service": "pool_tracker.delete_record",
            "confirmation": {"text": f"Delete {label}?"},
            "data": _compact_object(
                {
                    "pool_id": attrs.get("pool_id"),
                    "record_id": record_id,
                    "confirm": True,
                }
            ),
        },
    }


def _recent_records_markdown(state: Any | None) -> str:
    """Return markdown for recent Pool Tracker records."""
    attrs = state.attributes if state is not None else {}
    water_tests = attrs.get("recent_water_tests") or []
    chemical_additions = attrs.get("recent_chemical_additions") or []
    sections: list[str] = []

    if water_tests:
        sections.append(
            "\n".join(
                ["### Water tests"]
                + [f"- {_water_test_line(record)}" for record in water_tests]
            )
        )
    if chemical_additions:
        sections.append(
            "\n".join(
                ["### Chemical additions"]
                + [f"- {_chemical_line(record)}" for record in chemical_additions]
            )
        )

    return "\n\n".join(sections)


def _water_test_line(record: dict[str, Any]) -> str:
    """Return one markdown line for a water test record."""
    readings = ", ".join(
        f"{_label_for(reading)} {_format_number(value)}"
        for reading, value in (record.get("readings") or {}).items()
    )
    return ": ".join(
        part
        for part in (
            _date_label(record.get("event_timestamp")),
            readings or "Test logged",
        )
        if part
    )


def _chemical_line(record: dict[str, Any]) -> str:
    """Return one markdown line for a chemical addition record."""
    return ": ".join(
        part
        for part in (
            _date_label(record.get("event_timestamp")),
            record.get("summary") or _chemical_summary(record),
        )
        if part
    )


def _chemical_summary(record: dict[str, Any]) -> str:
    """Return a short chemical addition summary."""
    return (
        f"{record.get('chemical')}: "
        f"{_format_number(record.get('amount'))} {record.get('unit')}"
    )


def _label_for(value: str) -> str:
    """Return a display label for a stored enum value."""
    if value in SELECT_LABELS:
        return SELECT_LABELS[value]
    return str(value).replace("_", " ").title()


def _format_number(value: Any) -> str:
    """Format a number compactly for dashboard text."""
    try:
        number = float(value)
    except TypeError, ValueError:
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _date_label(timestamp: Any) -> str:
    """Return a short local datetime label."""
    if not timestamp:
        return ""
    parsed = dt_util.parse_datetime(str(timestamp))
    if parsed is None:
        return str(timestamp)
    return dt_util.as_local(parsed).strftime("%b %d, %I:%M %p").replace(" 0", " ")


def _numeric_or_original(value: Any) -> Any:
    """Return a numeric value when possible for service data."""
    try:
        number = float(value)
    except TypeError, ValueError:
        return value
    return int(number) if number.is_integer() else number


def _compact_object(value: dict[str, Any]) -> dict[str, Any]:
    """Drop empty optional service data."""
    return {key: item for key, item in value.items() if item is not None and item != ""}


def _number(minimum: float | None = None, maximum: float | None = None):
    validators = [vol.Coerce(float)]
    if minimum is not None:
        validators.append(vol.Range(min=minimum))
    if maximum is not None:
        validators.append(vol.Range(max=maximum))
    return vol.All(*validators)


def _positive_number(value: Any) -> float:
    number = vol.Coerce(float)(value)
    if number <= 0:
        raise vol.Invalid("value must be greater than zero")
    return number


def _validate_water_test_content(data: dict[str, Any]) -> dict[str, Any]:
    if any(
        data.get(key) not in (None, "")
        for key in (*NUMERIC_WATER_READINGS, WATER_READING_WATER_CLARITY, "notes")
    ):
        return data
    raise vol.Invalid(
        "At least one water-test reading, clarity value, or note is required."
    )


def _water_test_service_schema():
    return vol.Schema(
        vol.All(
            {
                vol.Optional(CONF_POOL_ID): cv.string,
                vol.Optional("event_timestamp"): cv.datetime,
                vol.Optional("source", default="service"): cv.string,
                vol.Optional("notes"): cv.string,
                **{
                    vol.Optional(reading): (
                        _number(0, 14) if reading == WATER_READING_PH else _number(0)
                    )
                    for reading in NUMERIC_WATER_READINGS
                },
                vol.Optional(WATER_READING_WATER_CLARITY): vol.In(
                    WATER_CLARITY_OPTIONS
                ),
                vol.Optional(WATER_TESTING_METHOD): vol.In(WATER_TESTING_METHODS),
            },
            _validate_water_test_content,
        )
    )


def _chemical_addition_service_schema():
    return vol.Schema(
        {
            vol.Optional(CONF_POOL_ID): cv.string,
            vol.Optional("event_timestamp"): cv.datetime,
            vol.Optional("source", default="service"): cv.string,
            vol.Optional("notes"): cv.string,
            vol.Required("chemical"): vol.In(CHEMICAL_OPTIONS),
            vol.Required("amount"): _positive_number,
            vol.Required("unit"): vol.All(
                cv.string, normalize_chemical_amount_unit, vol.In(CHEMICAL_AMOUNT_UNITS)
            ),
        }
    )


def _delete_record_service_schema():
    return vol.Schema(
        {
            vol.Optional(CONF_POOL_ID): cv.string,
            vol.Required("record_id"): cv.string,
            vol.Required("confirm"): vol.All(cv.boolean, vol.Equal(True)),
        }
    )


def _reset_dashboard_service_schema():
    return vol.Schema(
        {
            vol.Required("confirm"): vol.All(cv.boolean, vol.Equal(True)),
        }
    )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Pool Tracker service actions."""
    event_store = PoolTrackerStore(create_home_assistant_store(hass))
    await event_store.async_load()
    hass.data.setdefault(DOMAIN, {})["store"] = event_store
    await _async_setup_frontend(hass)

    async def handle_log_water_test(call: ServiceCall) -> dict[str, str]:
        runtime, pool_id = _runtime_for_call(hass, call.data.get(CONF_POOL_ID))
        readings = {
            key: call.data.get(key)
            for key in (*NUMERIC_WATER_READINGS, WATER_READING_WATER_CLARITY)
        }
        record = build_water_test_record(
            pool_id=pool_id,
            readings=readings,
            event_timestamp=call.data.get("event_timestamp"),
            source=call.data.get("source"),
            notes=call.data.get("notes"),
            testing_method=call.data.get(WATER_TESTING_METHOD)
            or runtime.pool_profiles.get(pool_id, {}).get(CONF_DEFAULT_TESTING_METHOD),
        )
        await runtime.store.async_append(record)
        _fire_record_created(hass, record)
        return {"record_id": record["id"]}

    async def handle_log_chemical_addition(call: ServiceCall) -> dict[str, str]:
        runtime, pool_id = _runtime_for_call(hass, call.data.get(CONF_POOL_ID))
        record = build_chemical_addition_record(
            pool_id=pool_id,
            chemical=call.data["chemical"],
            amount=call.data["amount"],
            unit=call.data["unit"],
            event_timestamp=call.data.get("event_timestamp"),
            source=call.data.get("source"),
            notes=call.data.get("notes"),
        )
        await runtime.store.async_append(record)
        _fire_record_created(hass, record)
        return {"record_id": record["id"]}

    async def handle_delete_record(call: ServiceCall) -> dict[str, str]:
        record_id = call.data["record_id"]
        try:
            deleted = await event_store.async_delete_record(
                record_id, call.data.get(CONF_POOL_ID)
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        if deleted is None:
            raise ServiceValidationError(
                f"No Pool Tracker record matches record_id {record_id!r}."
            )
        _fire_record_deleted(hass, deleted)
        return {
            "record_id": deleted["id"],
            "pool_id": deleted["pool_id"],
            "type": deleted["type"],
        }

    async def handle_reset_dashboard(call: ServiceCall) -> dict[str, str]:
        await _async_reset_dashboard(hass)
        return {"dashboard": FRONTEND_PANEL_URL_PATH}

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_WATER_TEST,
        handle_log_water_test,
        schema=_water_test_service_schema(),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_CHEMICAL_ADDITION,
        handle_log_chemical_addition,
        schema=_chemical_addition_service_schema(),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_RECORD,
        handle_delete_record,
        schema=_delete_record_service_schema(),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_DASHBOARD,
        handle_reset_dashboard,
        schema=_reset_dashboard_service_schema(),
        supports_response=SupportsResponse.OPTIONAL,
    )

    return True


async def _async_setup_frontend(hass: HomeAssistant) -> None:
    """Register the editable Pool Tracker Lovelace dashboard."""
    if LOVELACE_DATA not in hass.data:
        return

    hass.data[LOVELACE_DATA].dashboards[FRONTEND_PANEL_URL_PATH] = (
        PoolTrackerLovelaceConfig(hass)
    )
    frontend.async_register_built_in_panel(
        hass,
        LOVELACE_DOMAIN,
        frontend_url_path=FRONTEND_PANEL_URL_PATH,
        sidebar_title="Pool Tracker",
        sidebar_icon="mdi:pool",
        config={"mode": MODE_STORAGE},
        update=frontend.async_panel_exists(hass, FRONTEND_PANEL_URL_PATH),
    )


async def _async_reset_dashboard(hass: HomeAssistant) -> None:
    """Reset the Pool Tracker Lovelace dashboard to the generated default."""
    dashboard = hass.data.get(LOVELACE_DATA)
    lovelace_config = None
    if dashboard is not None:
        lovelace_config = dashboard.dashboards.get(FRONTEND_PANEL_URL_PATH)
    if isinstance(lovelace_config, PoolTrackerLovelaceConfig):
        await lovelace_config.async_delete()
        return

    await PoolTrackerLovelaceConfig(hass).async_delete()


async def async_setup_entry(hass: HomeAssistant, entry: PoolTrackerConfigEntry) -> bool:
    """Set up Pool Tracker from a config entry."""
    pool_profiles = _pool_profiles_from_entry(entry)
    pools = {
        pool_id: profile[CONF_POOL_NAME] for pool_id, profile in pool_profiles.items()
    }
    store = hass.data[DOMAIN]["store"]

    entry.runtime_data = PoolTrackerRuntime(
        store=store, pools=pools, pool_profiles=pool_profiles
    )

    _LOGGER.debug(
        "Setting up Pool Tracker entry %s for pools %s", entry.entry_id, pools
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PoolTrackerConfigEntry
) -> bool:
    """Unload a Pool Tracker config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        _LOGGER.debug("Unloaded Pool Tracker entry %s", entry.entry_id)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry versions."""
    if config_entry.version == 1:
        return True
    _LOGGER.error(
        "Unsupported Pool Tracker config entry version %s", config_entry.version
    )
    return False


def _runtime_for_call(
    hass: HomeAssistant, requested_pool_id: str | None
) -> tuple[PoolTrackerRuntime, str]:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError("Pool Tracker is not loaded.")

    matches: list[tuple[PoolTrackerRuntime, str]] = []
    for entry in entries:
        runtime = entry.runtime_data
        for pool_id in runtime.pools:
            if requested_pool_id is None or requested_pool_id == pool_id:
                matches.append((runtime, pool_id))

    if not matches:
        raise ServiceValidationError(
            f"No loaded Pool Tracker pool matches pool_id {requested_pool_id!r}."
        )
    if requested_pool_id is None and len(matches) > 1:
        raise ServiceValidationError(
            "pool_id is required when multiple pools are loaded."
        )

    return matches[0]


def _pool_profiles_from_entry(
    entry: PoolTrackerConfigEntry,
) -> dict[str, dict[str, Any]]:
    pool = dict(entry.options or entry.data)
    pool_id = pool[CONF_POOL_ID]
    pool.setdefault(CONF_DEFAULT_TESTING_METHOD, DEFAULT_TESTING_METHOD)
    pool.setdefault(CONF_TYPICALLY_COVERED, False)
    pool.setdefault(CONF_TRACKED_METRICS, list(enabled_water_test_metrics(pool)))
    return {pool_id: pool}


def _fire_record_created(hass: HomeAssistant, record: dict[str, Any]) -> None:
    hass.bus.async_fire(
        EVENT_RECORD_CREATED,
        {
            "record_id": record["id"],
            "pool_id": record["pool_id"],
            "type": record["type"],
            "event_timestamp": record["event_timestamp"],
            "created_timestamp": record["created_timestamp"],
        },
    )


def _fire_record_deleted(hass: HomeAssistant, record: dict[str, Any]) -> None:
    hass.bus.async_fire(
        EVENT_RECORD_DELETED,
        {
            "record_id": record["id"],
            "pool_id": record["pool_id"],
            "type": record["type"],
            "event_timestamp": record["event_timestamp"],
            "created_timestamp": record["created_timestamp"],
        },
    )
