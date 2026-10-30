"""Diagnostics: the cloud password must never reach a download.

A diagnostics download is something people paste into issue trackers, and a
cloud entry holds a vendor account password, so this is a regression test for
the leak fixed in 0.2.1 rather than a shape check.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aquilo.const import (
    CONF_SOURCE,
    DOMAIN,
    SOURCE_CLOUD,
    SOURCE_LOCAL,
)
from custom_components.aquilo.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

from .conftest import ACCOUNT, HOST

LOCAL_GET = "custom_components.aquilo.api.AquiloLocalClient.async_get_sensors"
CLOUD_GET = "custom_components.aquilo.api.AquiloCloudClient.async_get_sensors"
PASSWORD = "Ni3-Do-Pok4zania"
TANKS = {"000001": {"id": "000001", "pct": 34}}


async def _setup(
    hass: HomeAssistant, data: dict[str, Any], target: str
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=HOST, version=2, title=f"Aquilo ({HOST})", data=data
    )
    entry.add_to_hass(hass)
    with patch(target, return_value=TANKS):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_a_cloud_password_is_not_in_the_entry_diagnostics(hass: HomeAssistant):
    entry = await _setup(
        hass,
        {
            CONF_SOURCE: SOURCE_CLOUD,
            CONF_USERNAME: ACCOUNT,
            CONF_PASSWORD: PASSWORD,
            CONF_HOST: HOST,
        },
        CLOUD_GET,
    )
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert PASSWORD not in json.dumps(result)
    assert ACCOUNT not in json.dumps(result["entry"]["data"])
    assert result["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"
    assert result["source"] == SOURCE_CLOUD


async def test_a_cloud_password_is_not_in_the_device_diagnostics(hass: HomeAssistant):
    entry = await _setup(
        hass,
        {
            CONF_SOURCE: SOURCE_CLOUD,
            CONF_USERNAME: ACCOUNT,
            CONF_PASSWORD: PASSWORD,
            CONF_HOST: HOST,
        },
        CLOUD_GET,
    )
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, f"{HOST}_000001")}
    )
    assert device is not None
    result = await async_get_device_diagnostics(hass, entry, device)
    assert PASSWORD not in json.dumps(result)
    assert result["tank_ids"] == ["000001"]
    assert result["sensors"]["000001"]["pct"] == 34


async def test_a_local_entry_still_reports_its_gateway(hass: HomeAssistant):
    entry = await _setup(hass, {CONF_SOURCE: SOURCE_LOCAL, CONF_HOST: HOST}, LOCAL_GET)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["host"] == HOST
    assert result["source"] == SOURCE_LOCAL
    assert result["tank_ids"] == ["000001"]
    assert result["last_update_success"] is True
