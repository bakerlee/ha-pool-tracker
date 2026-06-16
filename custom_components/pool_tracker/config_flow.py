"""Config flow for Pool Tracker."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_COVER_ENTITY_ID,
    CONF_DEFAULT_TESTING_METHOD,
    CONF_POOL_ID,
    CONF_POOL_NAME,
    CONF_POOL_TYPE,
    CONF_POOL_VOLUME,
    CONF_POOL_VOLUME_UNIT,
    CONF_POOLS,
    CONF_RAINFALL_ENTITY_ID,
    CONF_SANITIZER_TYPE,
    CONF_SUNLIGHT_ENTITY_ID,
    CONF_SURFACE_TYPE,
    CONF_TEMPERATURE_ENTITY_ID,
    CONF_TYPICALLY_COVERED,
    CONF_USAGE_ENTITY_ID,
    CONF_WEATHER_ENTITY_ID,
    DEFAULT_POOL_ID,
    DEFAULT_POOL_NAME,
    DEFAULT_POOL_VOLUME_UNIT,
    DEFAULT_TESTING_METHOD,
    DOMAIN,
    POOL_CONTEXT_ENTITY_KEYS,
    POOL_SANITIZER_TYPES,
    POOL_SURFACE_TYPES,
    POOL_TYPES,
    POOL_VOLUME_UNITS,
    WATER_TESTING_METHODS,
)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_with_default(key: str, defaults: dict[str, Any]) -> vol.Optional:
    if (default := defaults.get(key)) not in (None, ""):
        return vol.Optional(key, default=default)
    return vol.Optional(key)


def _select(options: tuple[str, ...]) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(options),
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _entity_selector(domain: str | list[str]) -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domain))


def _pool_id_from_name(name: str) -> str:
    """Return a stable pool id candidate from a display name."""
    return slugify(name) or DEFAULT_POOL_ID


def _configured_pool_ids(hass) -> set[str]:
    """Return pool ids already configured for Pool Tracker."""
    pool_ids: set[str] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        pool = pool_config_from_entry(entry)
        if pool_id := pool.get(CONF_POOL_ID):
            pool_ids.add(pool_id)
    return pool_ids


def _unique_pool_id(hass, name: str) -> str:
    """Generate a pool id that does not collide with existing entries."""
    configured_pool_ids = _configured_pool_ids(hass)
    base = _pool_id_from_name(name)
    candidate = base
    suffix = 2
    while candidate in configured_pool_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _pool_profile_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    schema: dict[Any, Any] = {
        vol.Optional(
            CONF_POOL_NAME, default=defaults.get(CONF_POOL_NAME, DEFAULT_POOL_NAME)
        ): str,
        _optional_with_default(CONF_POOL_VOLUME, defaults): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.001,
                step="any",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(
            CONF_POOL_VOLUME_UNIT,
            default=defaults.get(CONF_POOL_VOLUME_UNIT, DEFAULT_POOL_VOLUME_UNIT),
        ): _select(POOL_VOLUME_UNITS),
        _optional_with_default(CONF_POOL_TYPE, defaults): _select(POOL_TYPES),
        _optional_with_default(CONF_SURFACE_TYPE, defaults): _select(
            POOL_SURFACE_TYPES
        ),
        _optional_with_default(CONF_SANITIZER_TYPE, defaults): _select(
            POOL_SANITIZER_TYPES
        ),
        vol.Optional(
            CONF_DEFAULT_TESTING_METHOD,
            default=defaults.get(CONF_DEFAULT_TESTING_METHOD, DEFAULT_TESTING_METHOD),
        ): _select(WATER_TESTING_METHODS),
        vol.Optional(
            CONF_TYPICALLY_COVERED,
            default=defaults.get(CONF_TYPICALLY_COVERED, False),
        ): selector.BooleanSelector(),
        _optional_with_default(CONF_WEATHER_ENTITY_ID, defaults): _entity_selector(
            "weather"
        ),
        _optional_with_default(CONF_SUNLIGHT_ENTITY_ID, defaults): _entity_selector(
            "sensor"
        ),
        _optional_with_default(CONF_RAINFALL_ENTITY_ID, defaults): _entity_selector(
            "sensor"
        ),
        _optional_with_default(CONF_TEMPERATURE_ENTITY_ID, defaults): _entity_selector(
            "sensor"
        ),
        _optional_with_default(CONF_COVER_ENTITY_ID, defaults): _entity_selector(
            ["binary_sensor", "cover", "input_boolean", "switch"]
        ),
        _optional_with_default(CONF_USAGE_ENTITY_ID, defaults): _entity_selector(
            ["binary_sensor", "input_boolean", "sensor", "switch"]
        ),
    }
    return vol.Schema(schema)


def build_pool_config(
    user_input: dict[str, Any], *, pool_id: str | None = None
) -> dict[str, Any]:
    """Build a normalized single-pool config record."""
    pool_name = user_input[CONF_POOL_NAME].strip() or DEFAULT_POOL_NAME
    pool: dict[str, Any] = {
        CONF_POOL_ID: pool_id or _pool_id_from_name(pool_name),
        CONF_POOL_NAME: pool_name,
        CONF_POOL_VOLUME_UNIT: user_input.get(
            CONF_POOL_VOLUME_UNIT, DEFAULT_POOL_VOLUME_UNIT
        ),
        CONF_DEFAULT_TESTING_METHOD: user_input.get(
            CONF_DEFAULT_TESTING_METHOD, DEFAULT_TESTING_METHOD
        ),
        CONF_TYPICALLY_COVERED: bool(user_input.get(CONF_TYPICALLY_COVERED, False)),
    }
    for key in (CONF_POOL_TYPE, CONF_SURFACE_TYPE, CONF_SANITIZER_TYPE):
        if value := _optional_text(user_input.get(key, "")):
            pool[key] = value
    for key in POOL_CONTEXT_ENTITY_KEYS:
        if value := _optional_text(user_input.get(key, "")):
            pool[key] = value
    volume = user_input.get(CONF_POOL_VOLUME)
    if volume not in (None, ""):
        pool[CONF_POOL_VOLUME] = float(volume)
    return pool


def pool_config_from_entry(config_entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Return the active single-pool config for an entry."""
    for mapping in (config_entry.options, config_entry.data):
        if legacy_pools := mapping.get(CONF_POOLS):
            return legacy_pools[0]
        if mapping.get(CONF_POOL_ID) or mapping.get(CONF_POOL_NAME):
            return dict(mapping)
    return {CONF_POOL_ID: DEFAULT_POOL_ID, CONF_POOL_NAME: DEFAULT_POOL_NAME}


class PoolTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Pool Tracker config flow."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return PoolTrackerOptionsFlow()

    async def async_step_user(self, user_input: dict[str, str] | None = None):
        """Create the initial single-pool config entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            pool = build_pool_config(
                user_input,
                pool_id=_unique_pool_id(self.hass, user_input[CONF_POOL_NAME]),
            )
            await self.async_set_unique_id(pool[CONF_POOL_ID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=pool[CONF_POOL_NAME],
                data=pool,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_pool_profile_schema(),
            errors=errors,
        )


class PoolTrackerOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle Pool Tracker options updates."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Update the single-pool profile."""
        if user_input is not None:
            current_pool = pool_config_from_entry(self.config_entry)
            pool = build_pool_config(
                user_input,
                pool_id=current_pool.get(CONF_POOL_ID, DEFAULT_POOL_ID),
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=pool[CONF_POOL_NAME]
            )
            return self.async_create_entry(title="", data=pool)

        return self.async_show_form(
            step_id="init",
            data_schema=_pool_profile_schema(pool_config_from_entry(self.config_entry)),
        )
