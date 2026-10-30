"""The sensor platform: which entities a tank gets, and the diagnostic ones.

Not every tank type reports every field, so the interesting behaviour here is
what is *not* created, and which entities stay available when the readings do
not.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aquilo.const import (
    CONF_SOURCE,
    DOMAIN,
    SOURCE_CLOUD,
    SOURCE_LOCAL,
)

from .conftest import ACCOUNT, HOST, raw_block

LOCAL_GET = "custom_components.aquilo.api.AquiloLocalClient.async_get_sensors"
CLOUD_GET = "custom_components.aquilo.api.AquiloCloudClient.async_get_sensors"


async def _setup(
    hass: HomeAssistant,
    sensors: list[dict[str, Any]],
    *,
    data: dict[str, Any] | None = None,
    version: int = 2,
    target: str = LOCAL_GET,
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        version=version,
        title=f"Aquilo ({HOST})",
        data=data if data is not None else {CONF_SOURCE: SOURCE_LOCAL, CONF_HOST: HOST},
    )
    entry.add_to_hass(hass)
    with patch(target, return_value={s["id"]: s for s in sensors}):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, tank_id: str, suffix: str) -> State | None:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{HOST}_{tank_id}_{suffix}"
    )
    return hass.states.get(entity_id) if entity_id else None


def _exists(hass: HomeAssistant, tank_id: str, suffix: str) -> bool:
    return (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{HOST}_{tank_id}_{suffix}"
        )
        is not None
    )


async def test_tank_gets_the_core_readings(hass: HomeAssistant):
    await _setup(hass, [{"id": "t", "lvl": 125.6, "pct": 34, "bat": 76}])
    assert _state(hass, "t", "lvl").state == "125.6"
    assert _state(hass, "t", "pct").state == "34"
    assert _state(hass, "t", "bat").state == "76"


async def test_fields_a_tank_does_not_report_get_no_entity(hass: HomeAssistant):
    """The g1 sewage sensor sends no amplitude, so it must not grow the entity."""
    await _setup(hass, [{"id": "g1", "lvl": 125.6, "pct": 34}])
    for absent in ("amp1", "daysLeft", "lvlToFull", "lstEmpty", "raw"):
        assert not _exists(hass, "g1", absent), absent


async def test_echo_quality_entity_only_where_the_hardware_reports_it(
    hass: HomeAssistant,
):
    await _setup(
        hass,
        [
            {"id": "e19", "pct": 34, "amp1": 760},
            {"id": "g1", "pct": 34},
        ],
    )
    assert _state(hass, "e19", "amp1").state == "760"
    assert not _exists(hass, "g1", "amp1")


async def test_raw_entity_carries_the_string_and_every_field(hass: HomeAssistant):
    await _setup(hass, [{"id": "t", "pct": 34, "raw": raw_block()}])
    state = _state(hass, "t", "raw")
    assert state.state == "_e19_493e12_601_3556_760_6_1161_1160_1_6"
    assert state.attributes["read1"] == 3556
    assert state.attributes["amp1"] == 760
    assert state.attributes["rssi"] == -98
    assert state.attributes["rev"] == "e19"
    # the string itself is the state, not an attribute as well
    assert "raw" not in state.attributes


async def test_raw_state_is_truncated_to_what_ha_accepts(hass: HomeAssistant):
    await _setup(hass, [{"id": "t", "pct": 34, "raw": raw_block(raw="x" * 400)}])
    assert len(_state(hass, "t", "raw").state) == 255


async def test_a_rejected_reading_is_visible(hass: HomeAssistant):
    rejected = {"read1": 39300, "limit": 22500, "amp1": 1375, "at": "2026-01-01T12:00:00Z"}
    await _setup(hass, [{"id": "t", "pct": 34, "raw": raw_block(), "rejected": rejected}])
    assert _state(hass, "t", "raw").attributes["rejected"] == rejected


async def test_identity_entities_stay_available_without_a_reading(
    hass: HomeAssistant,
):
    """Id, gateway address and the raw reading are exactly what one wants to
    see when the tank's own readings have gone."""
    await _setup(hass, [{"id": "t", "raw": raw_block()}])
    assert _state(hass, "t", "id").state == "t"
    assert _state(hass, "t", "host").state == HOST
    assert _state(hass, "t", "raw").state != "unavailable"


async def test_host_entity_names_the_source(hass: HomeAssistant):
    await _setup(hass, [{"id": "t", "pct": 34}])
    attrs = _state(hass, "t", "host").attributes
    assert attrs["source"] == SOURCE_LOCAL
    assert attrs["configuration_url"] == f"http://{HOST}/state"


async def test_a_cloud_entry_keeps_the_identity_label_in_its_entity_ids(
    hass: HomeAssistant,
):
    """Switching source must not rename entities, so unique ids stay on the
    label the entry was created with, and only the attributes change."""
    await _setup(
        hass,
        [{"id": "t", "pct": 34}],
        data={
            CONF_SOURCE: SOURCE_CLOUD,
            CONF_USERNAME: ACCOUNT,
            CONF_PASSWORD: "secret",
            CONF_HOST: HOST,
        },
        target=CLOUD_GET,
    )
    attrs = _state(hass, "t", "host").attributes
    assert _state(hass, "t", "host").state == HOST
    assert attrs["source"] == SOURCE_CLOUD
    assert attrs["configuration_url"] == "https://panel.aquilo.pl/"


async def test_excluded_tank_gets_no_entities(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        version=2,
        data={CONF_SOURCE: SOURCE_LOCAL, CONF_HOST: HOST},
        options={"excluded_tanks": ["skip"]},
    )
    entry.add_to_hass(hass)
    with patch(
        LOCAL_GET,
        return_value={"keep": {"id": "keep", "pct": 34}, "skip": {"id": "skip", "pct": 50}},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert _exists(hass, "keep", "pct")
    assert not _exists(hass, "skip", "pct")


async def test_a_version_1_entry_is_migrated_to_the_local_source(
    hass: HomeAssistant,
):
    """Version 1 predates the choice and could only be the local gateway."""
    entry = await _setup(
        hass,
        [{"id": "t", "pct": 34}],
        data={CONF_HOST: HOST},
        version=1,
    )
    assert entry.version == 2
    assert entry.data == {CONF_HOST: HOST, CONF_SOURCE: SOURCE_LOCAL}
    # The label is untouched, so the entity ids are the ones it already had.
    assert _exists(hass, "t", "pct")
