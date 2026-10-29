"""The Aquilo integration — local liquid-level gateway (aquilo.pl)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .api import AquiloCloudClient, AquiloLocalClient
from .const import (
    CONF_EXCLUDED_TANKS,
    CONF_SOURCE,
    DEFAULT_SOURCE,
    DOMAIN,
    SOURCE_CLOUD,
)
from .coordinator import AquiloCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


def _build_client(
    hass: HomeAssistant, entry: ConfigEntry
) -> AquiloLocalClient | AquiloCloudClient:
    """Return the client for the source this entry is configured for.

    CONF_HOST carries the entry's stable identity label, which every unique id
    is built from. For a local entry it is also the address to poll; for a
    cloud entry it is only the label, so that an entry switched from local to
    cloud keeps its entities instead of growing a second set.

    Args:
        hass: Home Assistant instance.
        entry: The config entry.

    Returns:
        A client exposing ``host``, ``configuration_url`` and
        ``async_get_sensors``.
    """
    session = async_get_clientsession(hass)
    if entry.data.get(CONF_SOURCE, DEFAULT_SOURCE) == SOURCE_CLOUD:
        return AquiloCloudClient(
            session,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data.get(CONF_HOST) or entry.data[CONF_USERNAME],
        )
    return AquiloLocalClient(session, entry.data[CONF_HOST])


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Bring an older entry up to the current version.

    Version 1 predates the source choice and could only ever be the local
    gateway, so it is marked as such and nothing else changes: the identity
    label stays the host it already was, which keeps every entity id.

    Args:
        hass: Home Assistant instance.
        entry: The config entry to migrate.

    Returns:
        True when the entry is usable at the current version.
    """
    if entry.version >= 2:
        return True
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_SOURCE: DEFAULT_SOURCE},
        version=2,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = _build_client(hass, entry)
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


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> bool:
    """Allow a tank device to be deleted from the device page.

    Without this, HA keeps the "Delete" button disabled for every device of
    the integration. A tank the gateway no longer reports can just be removed.
    A tank the gateway still reports would be recreated on the next refresh,
    so we also add it to the excluded list (same effect as unchecking it in
    the options flow) and let the update listener reload the entry.
    """
    coordinator: AquiloCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        return True

    host = coordinator.client.host
    still_reported = {
        tank_id
        for tank_id in coordinator.data
        if (DOMAIN, f"{host}_{tank_id}") in device.identifiers
    }
    if still_reported:
        excluded = set(entry.options.get(CONF_EXCLUDED_TANKS, []))
        excluded |= still_reported
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_EXCLUDED_TANKS: sorted(excluded)},
        )
    return True
