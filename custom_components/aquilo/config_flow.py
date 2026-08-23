"""Config flow for Aquilo."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AquiloApiError, AquiloClient
from .const import (
    CONF_OVERFLOW_PCT,
    CONF_STALE_HOURS,
    DEFAULT_OVERFLOW_PCT,
    DEFAULT_STALE_HOURS,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class AquiloConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aquilo."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            session = async_get_clientsession(self.hass)
            client = AquiloClient(session, host)
            try:
                sensors = await client.async_get_sensors()
            except AquiloApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Aquilo ({host})", data={CONF_HOST: host}
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AquiloOptionsFlow(config_entry)


class AquiloOptionsFlow(OptionsFlow):
    """Options: stale-data threshold + overflow-risk threshold."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STALE_HOURS,
                    default=current.get(CONF_STALE_HOURS, DEFAULT_STALE_HOURS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24 * 30)),
                vol.Required(
                    CONF_OVERFLOW_PCT,
                    default=current.get(CONF_OVERFLOW_PCT, DEFAULT_OVERFLOW_PCT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
