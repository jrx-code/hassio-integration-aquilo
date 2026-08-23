"""Minimal client for the Aquilo local gateway `/state` endpoint."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=10)


class AquiloApiError(Exception):
    """Raised when the Aquilo gateway can't be reached or returns garbage."""


class AquiloClient:
    """Talks to a single Aquilo gateway (`http://<host>/state`).

    One gateway can report multiple tank sensors in a single response —
    the integration treats each `sensors[]` entry as its own HA device.
    """

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self._host = host

    @property
    def host(self) -> str:
        return self._host

    async def async_get_sensors(self) -> dict[str, dict[str, Any]]:
        """Fetch and return {sensor_id: sensor_dict}."""
        url = f"http://{self._host}/state"
        try:
            async with self._session.get(url, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise AquiloApiError(f"HTTP {resp.status} from {url}")
                data = await resp.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise AquiloApiError(f"Timeout talking to {url}") from err
        except aiohttp.ClientError as err:
            raise AquiloApiError(f"Connection error talking to {url}: {err}") from err

        sensors = data.get("sensors")
        if not isinstance(sensors, list):
            raise AquiloApiError(f"Unexpected payload from {url}: {data!r}")

        result: dict[str, dict[str, Any]] = {}
        for entry in sensors:
            sensor_id = entry.get("id")
            if not sensor_id:
                _LOGGER.warning("Aquilo sensor entry without id, skipping: %s", entry)
                continue
            result[sensor_id] = entry
        return result
