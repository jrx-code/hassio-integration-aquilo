"""Shared base entity for Aquilo — one HA device per physical tank sensor."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_NAME, DOMAIN
from .coordinator import AquiloCoordinator


class AquiloEntity(CoordinatorEntity[AquiloCoordinator]):
    """Base entity tied to one tank_id within the coordinator's data dict."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AquiloCoordinator, tank_id: str) -> None:
        super().__init__(coordinator)
        self._tank_id = tank_id
        tank_name = self._tank_data.get(ATTR_NAME, tank_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.client.host}_{tank_id}")},
            name=tank_name.title(),
            manufacturer="Aquilo",
            model="Czujnik poziomu cieczy",
            configuration_url=f"http://{coordinator.client.host}/state",
        )

    @property
    def _tank_data(self) -> dict:
        return self.coordinator.data.get(self._tank_id, {})

    @property
    def available(self) -> bool:
        return super().available and self._tank_id in self.coordinator.data
