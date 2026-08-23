"""DataUpdateCoordinator for Aquilo."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AquiloApiError, AquiloClient
from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AquiloCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls one Aquilo gateway; data is keyed by sensor id."""

    def __init__(self, hass: HomeAssistant, client: AquiloClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            return await self.client.async_get_sensors()
        except AquiloApiError as err:
            raise UpdateFailed(str(err)) from err
