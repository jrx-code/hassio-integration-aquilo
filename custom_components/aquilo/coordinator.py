"""DataUpdateCoordinator for Aquilo."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AquiloApiError, AquiloCloudClient, AquiloLocalClient
from .const import (
    DEFAULT_CLOUD_SCAN_INTERVAL_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    SOURCE_CLOUD,
)

_LOGGER = logging.getLogger(__name__)


class AquiloCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls one Aquilo gateway; data is keyed by sensor id."""

    def __init__(
        self, hass: HomeAssistant, client: AquiloLocalClient | AquiloCloudClient
    ) -> None:
        """Set the poll interval to suit the source.

        Args:
            hass: Home Assistant instance.
            client: The configured source client.
        """
        seconds = (
            DEFAULT_CLOUD_SCAN_INTERVAL_SECONDS
            if client.source == SOURCE_CLOUD
            else DEFAULT_SCAN_INTERVAL_SECONDS
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=seconds),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            return await self.client.async_get_sensors()
        except AquiloApiError as err:
            raise UpdateFailed(str(err)) from err
