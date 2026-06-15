"""Config flow for Pool Tracker."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_POOL_ID, CONF_POOL_NAME, CONF_POOLS, DEFAULT_POOL_NAME, DOMAIN


class PoolTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Pool Tracker config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, str] | None = None):
        """Create the initial single-pool config entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            name = user_input[CONF_POOL_NAME].strip() or DEFAULT_POOL_NAME
            return self.async_create_entry(
                title=name,
                data={
                    CONF_POOLS: [
                        {
                            CONF_POOL_ID: "pool",
                            CONF_POOL_NAME: name,
                        }
                    ]
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_POOL_NAME, default=DEFAULT_POOL_NAME): str,
                }
            ),
            errors=errors,
        )
