"""The Aquilo integration — local liquid-level gateway (aquilo.pl)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AquiloClient
from .const import CONF_EXCLUDED_TANKS, DOMAIN
from .coordinator import AquiloCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = AquiloClient(session, entry.data[CONF_HOST])
    coordinator = AquiloCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    _async_purge_excluded_tanks(hass, entry, client.host)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _async_purge_excluded_tanks(hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
    """Remove the device (and its entities) for any tank the user excluded.

    Excluding a tank in options only stops new entities from being created —
    a device that already exists from before the exclusion would otherwise
    stick around as a permanently-unavailable leftover.
    """
    excluded = entry.options.get(CONF_EXCLUDED_TANKS, [])
    if not excluded:
        return
    device_registry = dr.async_get(hass)
    for tank_id in excluded:
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"{host}_{tank_id}")}
        )
        if device is not None:
            device_registry.async_remove_device(device.id)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
