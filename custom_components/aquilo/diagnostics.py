"""Diagnostics support for Aquilo.

Exposes the "Download diagnostics" button on the integration and on each tank
device: the source, the config entry, coordinator state and the raw payload
keyed by sensor id.

The entry's own data is redacted. A local entry holds nothing sensitive, but a
cloud entry holds the vendor account's password, and a diagnostics download is
something people paste into issue trackers.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import AquiloCoordinator

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


def _entry_info(entry: ConfigEntry) -> dict[str, Any]:
    """Summarise the config entry with its credentials removed.

    Args:
        entry: The config entry.

    Returns:
        The entry's title, unique id, redacted data and options.
    """
    return {
        "title": entry.title,
        "unique_id": entry.unique_id,
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: AquiloCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry": _entry_info(entry),
        "host": coordinator.client.host,
        "source": coordinator.client.source,
        "configuration_url": coordinator.client.configuration_url,
        "last_update_success": coordinator.last_update_success,
        "tank_count": len(coordinator.data),
        "tank_ids": sorted(coordinator.data),
        "sensors": coordinator.data,
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    coordinator: AquiloCoordinator = hass.data[DOMAIN][entry.entry_id]
    host = coordinator.client.host
    tank_ids = [
        tank_id
        for tank_id in coordinator.data
        if (DOMAIN, f"{host}_{tank_id}") in device.identifiers
    ]
    return {
        "entry": _entry_info(entry),
        "host": host,
        "source": coordinator.client.source,
        "device": {
            "name": device.name,
            "identifiers": sorted(f"{d}:{i}" for d, i in device.identifiers),
            "serial_number": device.serial_number,
        },
        "tank_ids": tank_ids,
        "sensors": {tank_id: coordinator.data.get(tank_id) for tank_id in tank_ids},
    }
