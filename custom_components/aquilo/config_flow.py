"""Config flow for Aquilo.

Two sources answer for the same tanks, so the first thing the flow asks is
which one to use, and a reconfigure step lets that choice change later without
losing the devices: the identity label every unique id is built from is stored
once and kept, so switching source keeps the entities and their history.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AquiloApiError, AquiloAuthError, AquiloCloudClient, AquiloLocalClient
from .const import (
    ATTR_NAME,
    CONF_EXCLUDED_TANKS,
    CONF_OVERFLOW_PCT,
    CONF_SOURCE,
    CONF_STALE_HOURS,
    DEFAULT_OVERFLOW_PCT,
    DEFAULT_STALE_HOURS,
    DOMAIN,
    SOURCE_CLOUD,
    SOURCE_LOCAL,
)

STEP_LOCAL_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})
STEP_CLOUD_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


def _clean_host(raw: str) -> str:
    """Strip a scheme, whitespace and a trailing slash off a typed-in host.

    Args:
        raw: What the user typed.

    Returns:
        A bare host or IP.
    """
    return raw.strip().removeprefix("http://").removeprefix("https://").rstrip("/")


class AquiloConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aquilo."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Ask which source to read the tanks from."""
        return self.async_show_menu(
            step_id="user", menu_options=[SOURCE_LOCAL, SOURCE_CLOUD]
        )

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Configure the gateway on the local network."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = _clean_host(user_input[CONF_HOST])
            session = async_get_clientsession(self.hass)
            try:
                sensors = await AquiloLocalClient(session, host).async_get_sensors()
            except AquiloApiError:
                errors["base"] = "cannot_connect"
            else:
                if not sensors:
                    errors["base"] = "no_sensors_found"
                else:
                    data = {CONF_SOURCE: SOURCE_LOCAL, CONF_HOST: host}
                    if self.source == "reconfigure":
                        return await self._async_apply_reconfigure(data)
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Aquilo ({host})", data=data
                    )

        return self.async_show_form(
            step_id="local", data_schema=STEP_LOCAL_SCHEMA, errors=errors
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Configure the vendor dashboard account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            session = async_get_clientsession(self.hass)
            # Keep the label an existing entry already uses, so a local entry
            # switched to the cloud does not rename every entity.
            label = username
            if self.source == "reconfigure":
                label = self._get_reconfigure_entry().data.get(CONF_HOST) or username
            client = AquiloCloudClient(session, username, password, label)
            try:
                sensors = await client.async_get_sensors()
            except AquiloAuthError:
                errors["base"] = "invalid_auth"
            except AquiloApiError:
                errors["base"] = "cannot_connect"
            else:
                if not sensors:
                    errors["base"] = "no_sensors_found"
                else:
                    data = {
                        CONF_SOURCE: SOURCE_CLOUD,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_HOST: label,
                    }
                    if self.source == "reconfigure":
                        return await self._async_apply_reconfigure(data)
                    await self.async_set_unique_id(username)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Aquilo cloud ({username})", data=data
                    )

        return self.async_show_form(
            step_id="cloud", data_schema=STEP_CLOUD_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Offer the same choice again for an entry that already exists."""
        return self.async_show_menu(
            step_id="reconfigure", menu_options=[SOURCE_LOCAL, SOURCE_CLOUD]
        )

    async def _async_apply_reconfigure(self, data: dict[str, Any]) -> Any:
        """Write the new source onto the existing entry and reload it.

        Args:
            data: The new entry data, already verified against the source.

        Returns:
            The flow result that ends the reconfigure.
        """
        entry = self._get_reconfigure_entry()
        title = (
            f"Aquilo ({data[CONF_HOST]})"
            if data[CONF_SOURCE] == SOURCE_LOCAL
            else f"Aquilo cloud ({data[CONF_USERNAME]})"
        )
        return self.async_update_reload_and_abort(entry, title=title, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return AquiloOptionsFlow(config_entry)


class AquiloOptionsFlow(OptionsFlow):
    """Options: stale-data threshold, overflow-risk threshold, excluded sensors."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry
        self._data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_sensors()

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

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        current_excluded: list[str] = list(
            self._config_entry.options.get(CONF_EXCLUDED_TANKS, [])
        )

        if user_input is not None:
            self._data[CONF_EXCLUDED_TANKS] = user_input.get(CONF_EXCLUDED_TANKS, [])
            return self.async_create_entry(title="", data=self._data)

        coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
        tank_choices: dict[str, str] = {}
        if coordinator is not None:
            for tank_id, tank_data in coordinator.data.items():
                label = tank_data.get(ATTR_NAME) or tank_id
                tank_choices[tank_id] = label.title()
        # keep already-excluded ids selectable even if the source no longer
        # reports them (offline tank, coordinator not yet refreshed)
        for tank_id in current_excluded:
            tank_choices.setdefault(tank_id, tank_id)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_EXCLUDED_TANKS, default=current_excluded
                ): cv.multi_select(tank_choices),
            }
        )
        return self.async_show_form(step_id="sensors", data_schema=schema)
