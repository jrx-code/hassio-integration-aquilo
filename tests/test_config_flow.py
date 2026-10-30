"""The config flow: the source menu, both source steps and reconfigure."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aquilo.api import AquiloApiError, AquiloAuthError
from custom_components.aquilo.const import (
    CONF_SOURCE,
    DOMAIN,
    SOURCE_CLOUD,
    SOURCE_LOCAL,
)

from .conftest import ACCOUNT, HOST

LOCAL_GET = "custom_components.aquilo.api.AquiloLocalClient.async_get_sensors"
CLOUD_GET = "custom_components.aquilo.api.AquiloCloudClient.async_get_sensors"
SETUP = "custom_components.aquilo.async_setup_entry"
ONE_TANK = {"000001": {"id": "000001"}}


async def _menu(hass: HomeAssistant):
    """Start the flow and assert it opens with the source menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert set(result["menu_options"]) == {SOURCE_LOCAL, SOURCE_CLOUD}
    return result


async def _pick(hass: HomeAssistant, result, source: str):
    """Choose a source from a menu and assert the form that follows."""
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": source}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == source
    return result


async def _local_form(hass: HomeAssistant):
    return await _pick(hass, await _menu(hass), SOURCE_LOCAL)


async def _cloud_form(hass: HomeAssistant):
    return await _pick(hass, await _menu(hass), SOURCE_CLOUD)


@pytest.mark.parametrize(
    "typed", [HOST, f"http://{HOST}", f"https://{HOST}/", f"  {HOST}/  "]
)
async def test_local_creates_entry_and_cleans_host(hass: HomeAssistant, typed: str):
    result = await _local_form(hass)
    with (
        patch(LOCAL_GET, return_value=ONE_TANK),
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: typed}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Aquilo ({HOST})"
    assert result["data"] == {CONF_SOURCE: SOURCE_LOCAL, CONF_HOST: HOST}
    assert result["result"].unique_id == HOST
    # The entry has to arrive at the current version, or every fresh install
    # would be migrated on its first load.
    assert result["result"].version == 2


async def test_local_cannot_connect(hass: HomeAssistant):
    result = await _local_form(hass)
    with patch(LOCAL_GET, side_effect=AquiloApiError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_local_no_sensors_found(hass: HomeAssistant):
    result = await _local_form(hass)
    with patch(LOCAL_GET, return_value={}):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_sensors_found"}


async def test_local_already_configured(hass: HomeAssistant):
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        version=2,
        data={CONF_SOURCE: SOURCE_LOCAL, CONF_HOST: HOST},
    ).add_to_hass(hass)
    result = await _local_form(hass)
    with patch(LOCAL_GET, return_value=ONE_TANK):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: f"http://{HOST}/"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_cloud_creates_entry(hass: HomeAssistant):
    result = await _cloud_form(hass)
    with (
        patch(CLOUD_GET, return_value=ONE_TANK),
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: f"  {ACCOUNT} ", CONF_PASSWORD: "secret"},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Aquilo cloud ({ACCOUNT})"
    assert result["data"] == {
        CONF_SOURCE: SOURCE_CLOUD,
        CONF_USERNAME: ACCOUNT,
        CONF_PASSWORD: "secret",
        # A cloud entry still carries an identity label, so every unique id
        # keeps the same shape as a local one.
        CONF_HOST: ACCOUNT,
    }
    assert result["result"].unique_id == ACCOUNT


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AquiloAuthError("nope"), "invalid_auth"),
        (AquiloApiError("boom"), "cannot_connect"),
    ],
)
async def test_cloud_errors(hass: HomeAssistant, error: Exception, expected: str):
    result = await _cloud_form(hass)
    with patch(CLOUD_GET, side_effect=error):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: ACCOUNT, CONF_PASSWORD: "secret"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_cloud_no_sensors_found(hass: HomeAssistant):
    result = await _cloud_form(hass)
    with patch(CLOUD_GET, return_value={}):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: ACCOUNT, CONF_PASSWORD: "secret"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_sensors_found"}


def _existing_local(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        version=2,
        title=f"Aquilo ({HOST})",
        data={CONF_SOURCE: SOURCE_LOCAL, CONF_HOST: HOST},
    )
    entry.add_to_hass(hass)
    return entry


async def _reconfigure_menu(hass: HomeAssistant, entry: MockConfigEntry):
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"
    return result


async def test_reconfigure_local_to_cloud_keeps_the_identity_label(
    hass: HomeAssistant,
):
    """Switching source must not rename the entities, so the label is kept."""
    entry = _existing_local(hass)
    result = await _pick(hass, await _reconfigure_menu(hass, entry), SOURCE_CLOUD)
    with (
        patch(CLOUD_GET, return_value=ONE_TANK),
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: ACCOUNT, CONF_PASSWORD: "secret"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SOURCE] == SOURCE_CLOUD
    assert entry.data[CONF_USERNAME] == ACCOUNT
    assert entry.data[CONF_HOST] == HOST
    assert entry.title == f"Aquilo cloud ({ACCOUNT})"


async def test_reconfigure_cloud_back_to_local(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT,
        version=2,
        title=f"Aquilo cloud ({ACCOUNT})",
        data={
            CONF_SOURCE: SOURCE_CLOUD,
            CONF_USERNAME: ACCOUNT,
            CONF_PASSWORD: "secret",
            CONF_HOST: HOST,
        },
    )
    entry.add_to_hass(hass)
    result = await _pick(hass, await _reconfigure_menu(hass, entry), SOURCE_LOCAL)
    with (
        patch(LOCAL_GET, return_value=ONE_TANK),
        patch(SETUP, return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: f"http://{HOST}/"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_SOURCE: SOURCE_LOCAL, CONF_HOST: HOST}
    assert CONF_PASSWORD not in entry.data
    assert entry.title == f"Aquilo ({HOST})"


async def test_reconfigure_keeps_the_entry_on_an_unreachable_source(
    hass: HomeAssistant,
):
    entry = _existing_local(hass)
    result = await _pick(hass, await _reconfigure_menu(hass, entry), SOURCE_LOCAL)
    with patch(LOCAL_GET, side_effect=AquiloApiError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "10.0.0.9"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data[CONF_HOST] == HOST
