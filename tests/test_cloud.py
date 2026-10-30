"""The cloud client: login, the single 401 retry, and the arithmetic.

The vendor dashboard answers with a raw reading plus tank geometry rather than
a finished level, so this is where the integration's own arithmetic lives and
where it has to agree with the shape the gateway publishes.
"""

from __future__ import annotations

from typing import Any, Self

import pytest

from custom_components.aquilo.api import (
    AquiloApiError,
    AquiloAuthError,
    AquiloCloudClient,
    compute_levels,
)

from .conftest import ACCOUNT, cloud_row


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
    """Replays a scripted list of `(status, payload)` per method."""

    def __init__(
        self,
        posts: list[tuple[int, Any]] | None = None,
        gets: list[tuple[int, Any]] | None = None,
    ) -> None:
        self._posts = list(posts or [(200, {"token": "t1"})])
        self._gets = list(gets or [])
        self.post_calls: list[str] = []
        self.get_calls: list[tuple[str, str | None]] = []

    def post(self, url: str, json: Any = None, timeout: Any = None) -> _Response:
        self.post_calls.append(url)
        status, payload = self._posts.pop(0) if self._posts else (200, {"token": "t"})
        return _Response(status, payload)

    def get(
        self, url: str, headers: dict[str, str] | None = None, timeout: Any = None
    ) -> _Response:
        self.get_calls.append((url, (headers or {}).get("Authorization")))
        status, payload = self._gets.pop(0) if self._gets else (200, {})
        return _Response(status, payload)


def _client(session: _Session) -> AquiloCloudClient:
    return AquiloCloudClient(session, ACCOUNT, "secret")  # type: ignore[arg-type]


# --- compute_levels ---------------------------------------------------------


def test_compute_levels_matches_the_published_fields():
    # 125.6 cm below the radar in a 220 cm tank that counts as full at 20 cm:
    # 94.4 cm of liquid over a 200 cm usable span.
    assert compute_levels(12560, 220, 20) == {
        "lvl": 125.6,
        "pct": 47,
        "lvlToFull": 106,
    }


@pytest.mark.parametrize(
    ("read1", "expected_pct"),
    [
        (2000, 100),  # above the "full" offset: clamped, not over 100
        (22000, 0),  # past the empty reference: clamped, not negative
    ],
)
def test_compute_levels_clamps(read1: int, expected_pct: int):
    assert compute_levels(read1, 220, 20)["pct"] == expected_pct


@pytest.mark.parametrize(("depth", "full"), [(20, 20), (10, 20)])
def test_compute_levels_rejects_a_non_positive_span(depth: int, full: int):
    with pytest.raises(ValueError, match="not above its full offset"):
        compute_levels(12560, depth, full)


# --- login and token handling ----------------------------------------------


async def test_login_then_fetch_sends_the_bearer():
    session = _Session(gets=[(200, {"sensors": [cloud_row()]})])
    result = await _client(session).async_get_sensors()
    assert session.post_calls == ["https://panel.aquilo.pl/api/v2/login"]
    assert session.get_calls == [
        ("https://panel.aquilo.pl/api/v2/sensors", "Bearer t1")
    ]
    assert set(result) == {"000001"}


@pytest.mark.parametrize("status", [400, 401, 403])
async def test_login_rejected_is_an_auth_error(status: int):
    session = _Session(posts=[(status, {"error": "bad credentials"})])
    with pytest.raises(AquiloAuthError, match="bad credentials"):
        await _client(session).async_get_sensors()


async def test_login_without_a_token_is_an_api_error():
    session = _Session(posts=[(200, {"ok": True})])
    with pytest.raises(AquiloApiError, match="No token"):
        await _client(session).async_get_sensors()


async def test_expired_token_is_retried_once():
    session = _Session(
        posts=[(200, {"token": "stale"}), (200, {"token": "fresh"})],
        gets=[(401, {}), (200, {"sensors": [cloud_row()]})],
    )
    result = await _client(session).async_get_sensors()
    assert len(session.post_calls) == 2
    assert [auth for _, auth in session.get_calls] == ["Bearer stale", "Bearer fresh"]
    assert set(result) == {"000001"}


async def test_a_second_401_is_not_retried_again():
    session = _Session(
        posts=[(200, {"token": "a"}), (200, {"token": "b"})],
        gets=[(401, {}), (401, {})],
    )
    with pytest.raises(AquiloApiError, match="HTTP 401"):
        await _client(session).async_get_sensors()
    assert len(session.get_calls) == 2


# --- normalising a row ------------------------------------------------------


async def _sensors(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    session = _Session(gets=[(200, {"sensors": [row]})])
    return await _client(session).async_get_sensors()


async def test_row_is_mapped_onto_the_gateway_field_names():
    tank = (await _sensors(cloud_row()))["000001"]
    assert tank["id"] == "000001"
    assert tank["name"] == "SZAMBO"
    assert tank["lvl"] == 125.6
    assert tank["pct"] == 47
    assert tank["bat"] == 76
    assert tank["batMv"] == 3610
    assert tank["lstRead"] == "2026-01-01T12:00:00+01:00"


async def test_manual_depth_wins_when_the_mode_says_so():
    row = cloud_row(
        tank_depth_mode="manual", tank_depth_manual_cm=120, tank_depth_auto_cm=220
    )
    assert (await _sensors(row))["000001"]["lvl"] == 125.6
    # 120 cm tank, 125.6 cm reading: past empty, so clamped to 0.
    assert (await _sensors(row))["000001"]["pct"] == 0


async def test_row_without_a_reading_keeps_the_tank_but_no_level():
    row = cloud_row()
    del row["read1"]
    tank = (await _sensors(row))["000001"]
    assert "lvl" not in tank
    assert tank["bat"] == 76


async def test_an_impossible_geometry_does_not_fail_the_whole_poll():
    tank = (await _sensors(cloud_row(tank_depth_auto_cm=10, max_level=20)))["000001"]
    assert "pct" not in tank
    assert tank["bat"] == 76


async def test_row_carrying_nothing_but_an_id_is_dropped():
    assert await _sensors({"sensor": "000001"}) == {}


async def test_rows_without_a_sensor_id_or_not_objects_are_skipped():
    session = _Session(
        gets=[
            (
                200,
                {"sensors": [cloud_row(), {"read1": 1}, {"sensor": ""}, "garbage", 7]},
            )
        ]
    )
    assert list(await _client(session).async_get_sensors()) == ["000001"]


@pytest.mark.parametrize(
    "payload", [None, [], "nope", {}, {"sensors": None}, {"sensors": {}}]
)
async def test_unexpected_cloud_payload(payload: Any):
    session = _Session(gets=[(200, payload)])
    with pytest.raises(AquiloApiError, match="Unexpected payload"):
        await _client(session).async_get_sensors()


async def test_days_left_only_from_a_future_date():
    future = await _sensors(cloud_row(next_full="2099-01-01T00:00:00+00:00"))
    assert future["000001"]["daysLeft"] > 0
    past = await _sensors(cloud_row(next_full="2000-01-01T00:00:00+00:00"))
    assert "daysLeft" not in past["000001"]
    garbage = await _sensors(cloud_row(next_full="soon"))
    assert "daysLeft" not in garbage["000001"]


def test_identity_label_defaults_to_the_account_and_can_be_overridden():
    session = _Session()
    assert _client(session).source == "cloud"
    assert _client(session).host == ACCOUNT
    assert _client(session).configuration_url == "https://panel.aquilo.pl/"
    kept = AquiloCloudClient(session, ACCOUNT, "secret", "10.0.40.246")  # type: ignore[arg-type]
    assert kept.host == "10.0.40.246"
