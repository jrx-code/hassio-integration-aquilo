"""AquiloClient.async_get_sensors against a fake aiohttp session."""

from __future__ import annotations

from typing import Any, Self

import aiohttp
import pytest

from custom_components.aquilo.api import AquiloApiError, AquiloClient

from .conftest import HOST, state_payload


class _Response:
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self._payload = payload

    async def json(self, content_type: str | None = "application/json") -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _Session:
    def __init__(self, status: int = 200, payload: Any = None, error: Exception | None = None):
        self.status, self.payload, self.error = status, payload, error
        self.urls: list[str] = []

    def get(self, url: str, timeout: Any = None) -> _Response:
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        return _Response(self.status, self.payload)


async def _get(session: _Session) -> dict[str, dict[str, Any]]:
    return await AquiloClient(session, HOST).async_get_sensors()  # type: ignore[arg-type]


async def test_returns_sensors_by_id():
    session = _Session(payload=state_payload())
    result = await _get(session)
    assert session.urls == [f"http://{HOST}/state"]
    assert set(result) == {"000001", "000002"}
    assert result["000001"]["pct"] == 34


@pytest.mark.parametrize("status", [404, 500, 503])
async def test_http_error(status: int):
    with pytest.raises(AquiloApiError, match=f"HTTP {status}"):
        await _get(_Session(status=status, payload=state_payload()))


async def test_timeout():
    with pytest.raises(AquiloApiError, match="Timeout"):
        await _get(_Session(error=TimeoutError()))


async def test_connection_error():
    with pytest.raises(AquiloApiError, match="Connection error"):
        await _get(_Session(error=aiohttp.ClientConnectionError("refused")))


@pytest.mark.parametrize(
    "payload",
    [
        [],
        "not json object",
        None,
        {},
        {"sensors": None},
        {"sensors": {"id": "000001"}},
        {"devices": []},
    ],
)
async def test_payload_without_sensors_list(payload: Any):
    with pytest.raises(AquiloApiError, match="Unexpected payload"):
        await _get(_Session(payload=payload))


async def test_entries_without_id_or_not_objects_are_skipped():
    payload = {
        "sensors": [
            {"id": "000001", "pct": 10},
            {"pct": 20},
            {"id": "", "pct": 30},
            {"id": None, "pct": 40},
            "garbage",
            42,
        ]
    }
    assert list(await _get(_Session(payload=payload))) == ["000001"]


async def test_empty_sensor_list_is_not_an_error():
    assert await _get(_Session(payload={"sensors": []})) == {}
