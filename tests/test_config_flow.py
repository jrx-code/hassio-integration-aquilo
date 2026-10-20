"""The `user` step of the config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aquilo.api import AquiloApiError
from custom_components.aquilo.const import DOMAIN

from .conftest import HOST

GET = "custom_components.aquilo.api.AquiloClient.async_get_sensors"
SETUP = "custom_components.aquilo.async_setup_entry"


async def _start(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


@pytest.mark.parametrize(
    "typed", [HOST, f"http://{HOST}", f"https://{HOST}/", f"  {HOST}/  "]
)
async def test_creates_entry_and_cleans_host(hass: HomeAssistant, typed: str):
    result = await _start(hass)
    with (
        patch(GET, return_value={"000001": {"id": "000001"}}),
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: typed}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Aquilo ({HOST})"
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == HOST


async def test_cannot_connect(hass: HomeAssistant):
    result = await _start(hass)
    with patch(GET, side_effect=AquiloApiError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_sensors_found(hass: HomeAssistant):
    result = await _start(hass)
    with patch(GET, return_value={}):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_sensors_found"}


async def test_already_configured(hass: HomeAssistant):
    MockConfigEntry(domain=DOMAIN, unique_id=HOST, data={CONF_HOST: HOST}).add_to_hass(hass)
    result = await _start(hass)
    with patch(GET, return_value={"000001": {"id": "000001"}}):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: f"http://{HOST}/"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
