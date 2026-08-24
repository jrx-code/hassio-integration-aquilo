"""Sensor entities for Aquilo."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_BAT,
    ATTR_DAYS_LEFT,
    ATTR_LST_EMPTY,
    ATTR_LST_READ,
    ATTR_LVL,
    ATTR_LVL_TO_FULL,
    ATTR_PCT,
    DOMAIN,
)
from .coordinator import AquiloCoordinator
from .entity import AquiloEntity


@dataclass(frozen=True, kw_only=True)
class AquiloSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any] = lambda d: None


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    return dt_util.as_utc(parsed) if parsed else None


SENSOR_DESCRIPTIONS: tuple[AquiloSensorDescription, ...] = (
    AquiloSensorDescription(
        key=ATTR_LVL,
        name="Poziom",
        icon="mdi:waves-arrow-up",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(ATTR_LVL),
    ),
    AquiloSensorDescription(
        key=ATTR_PCT,
        name="Wypełnienie",
        icon="mdi:cup-water",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(ATTR_PCT),
    ),
    AquiloSensorDescription(
        key=ATTR_BAT,
        name="Bateria",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get(ATTR_BAT),
    ),
    AquiloSensorDescription(
        key=ATTR_DAYS_LEFT,
        name="Dni do pustego",
        icon="mdi:calendar-alert",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(ATTR_DAYS_LEFT),
    ),
    AquiloSensorDescription(
        key=ATTR_LVL_TO_FULL,
        name="Poziom do pełna",
        icon="mdi:arrow-collapse-up",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get(ATTR_LVL_TO_FULL),
    ),
    AquiloSensorDescription(
        key=ATTR_LST_READ,
        name="Ostatni odczyt",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _parse_ts(d.get(ATTR_LST_READ)),
    ),
    AquiloSensorDescription(
        key=ATTR_LST_EMPTY,
        name="Ostatnie opróżnienie",
        icon="mdi:tanker-truck",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _parse_ts(d.get(ATTR_LST_EMPTY)),
    ),
)


def _descriptions_for_tank(tank_data: dict[str, Any]) -> list[AquiloSensorDescription]:
    """Descriptions that apply to one tank's payload (skips fields the tank type doesn't report)."""
    result: list[AquiloSensorDescription] = []
    for description in SENSOR_DESCRIPTIONS:
        # daysLeft/lvlToFull/lstEmpty aren't reported by every tank type
        if description.value_fn(tank_data) is None and description.key in (
            ATTR_DAYS_LEFT,
            ATTR_LVL_TO_FULL,
            ATTR_LST_EMPTY,
        ):
            continue
        result.append(description)
    return result


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AquiloCoordinator = hass.data[DOMAIN][entry.entry_id]

    known_tank_ids: set[str] = set()

    def _add_new_tanks() -> None:
        new_entities: list[AquiloSensor] = []
        for tank_id, tank_data in coordinator.data.items():
            if tank_id in known_tank_ids:
                continue
            known_tank_ids.add(tank_id)
            for description in _descriptions_for_tank(tank_data):
                new_entities.append(AquiloSensor(coordinator, tank_id, description))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_tanks()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_tanks))


class AquiloSensor(AquiloEntity, SensorEntity):
    entity_description: AquiloSensorDescription

    def __init__(
        self,
        coordinator: AquiloCoordinator,
        tank_id: str,
        description: AquiloSensorDescription,
    ) -> None:
        super().__init__(coordinator, tank_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.host}_{tank_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._tank_data)
