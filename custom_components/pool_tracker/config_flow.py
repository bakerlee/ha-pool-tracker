"""Config flow for Pool Tracker."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_DEFAULT_TESTING_METHOD,
    CONF_POOL_ID,
    CONF_POOL_NAME,
    CONF_POOL_TYPE,
    CONF_POOL_VOLUME,
    CONF_POOL_VOLUME_UNIT,
    CONF_POOLS,
    CONF_SANITIZER_TYPE,
    CONF_SURFACE_TYPE,
    DEFAULT_POOL_ID,
    DEFAULT_POOL_NAME,
    DEFAULT_POOL_VOLUME_UNIT,
    DEFAULT_TESTING_METHOD,
    DOMAIN,
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
    }
    return vol.Schema(schema)


def build_pool_config(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build a normalized single-pool config record."""
    pool: dict[str, Any] = {
        CONF_POOL_ID: "pool",
        CONF_POOL_NAME: user_input[CONF_POOL_NAME].strip() or DEFAULT_POOL_NAME,
        CONF_POOL_VOLUME_UNIT: user_input.get(
            CONF_POOL_VOLUME_UNIT, DEFAULT_POOL_VOLUME_UNIT
        ),
        CONF_DEFAULT_TESTING_METHOD: user_input.get(
            CONF_DEFAULT_TESTING_METHOD, DEFAULT_TESTING_METHOD
        ),
    }
    for key in (CONF_POOL_TYPE, CONF_SURFACE_TYPE, CONF_SANITIZER_TYPE):
        if value := _optional_text(user_input.get(key, "")):
            pool[key] = value
    volume = user_input.get(CONF_POOL_VOLUME)
    if volume not in (None, ""):
        pool[CONF_POOL_VOLUME] = float(volume)
    return pool


def pool_config_from_entry(config_entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Return the active single-pool config for an entry."""
    pools = config_entry.options.get(CONF_POOLS) or config_entry.data.get(
        CONF_POOLS, []
    )
    if pools:
        return pools[0]
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
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            pool = build_pool_config(user_input)
            return self.async_create_entry(
                title=pool[CONF_POOL_NAME],
                data={CONF_POOLS: [pool]},
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
            pool = build_pool_config(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=pool[CONF_POOL_NAME]
            )
            return self.async_create_entry(title="", data={CONF_POOLS: [pool]})

        return self.async_show_form(
            step_id="init",
            data_schema=_pool_profile_schema(pool_config_from_entry(self.config_entry)),
        )
