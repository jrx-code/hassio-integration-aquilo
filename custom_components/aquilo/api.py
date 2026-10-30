"""Clients for the two places an Aquilo reading can come from.

The gateway is a radio receiver. It hands its raw radar readings to whoever
holds the MQTT broker it talks to, and it mirrors whatever state arrives back on
a plain HTTP endpoint of its own. Which means the same tank can be read two
ways, and they are not equivalent:

* ``AquiloLocalClient`` polls ``http://<host>/state`` on the gateway. Nothing
  leaves the network. What it returns is only as good as whoever computes that
  state -- the vendor cloud by default, or a local service once the broker is
  your own.
* ``AquiloCloudClient`` polls the vendor's dashboard API at
  ``panel.aquilo.pl``. It works when the gateway is unreachable and it carries
  the vendor's own geometry and predictions, at the cost of leaving the house
  and depending on an account.

The cloud API answers with raw readings and tank geometry rather than finished
levels -- the vendor's own dashboard computes those in the browser -- so this
module carries the arithmetic and both clients return the same shape, keyed by
sensor id, in the field names the rest of the integration already uses.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=10)
CLOUD_BASE = "https://panel.aquilo.pl/api/v2"


class AquiloApiError(Exception):
    """Raised when a source can't be reached or returns garbage."""


class AquiloAuthError(AquiloApiError):
    """Raised when the cloud rejects the credentials."""


def compute_levels(read1: float, depth_cm: float, full_cm: float) -> dict[str, Any]:
    """Turn a raw radar reading into the level fields the vendor publishes.

    The reading is the distance from the radar down to the liquid surface, in
    hundredths of a centimetre, so a full tank reads small. Percentage is
    measured against the usable span between the tank's depth and the offset at
    which it counts as full.

    Args:
        read1: Raw reading, in hundredths of a centimetre.
        depth_cm: Tank depth in centimetres.
        full_cm: The "full" offset in centimetres.

    Returns:
        ``{"lvl", "pct", "lvlToFull"}``, rounded as the vendor rounds them.

    Raises:
        ValueError: If the usable span is not positive, which would make the
            percentage meaningless rather than merely wrong.
    """
    span = depth_cm - full_cm
    if span <= 0:
        raise ValueError(f"tank depth {depth_cm} is not above its full offset {full_cm}")
    lvl = read1 / 100
    pct = (depth_cm - lvl) / span * 100
    # A reading past the empty reference goes slightly negative and the vendor
    # reports 0 there.
    pct = max(0.0, min(100.0, pct))
    return {"lvl": round(lvl, 1), "pct": round(pct), "lvlToFull": round(lvl - full_cm)}


class AquiloLocalClient:
    """Reads the tanks from the gateway's own HTTP endpoint.

    One gateway can report several tank sensors in a single response; each
    ``sensors[]`` entry becomes its own Home Assistant device.
    """

    source = "local"

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        """Store the session and the gateway address.

        Args:
            session: Shared aiohttp session.
            host: Gateway host or IP, without a scheme.
        """
        self._session = session
        self._host = host

    @property
    def host(self) -> str:
        """Stable identity label for this entry, used in every unique id."""
        return self._host

    @property
    def configuration_url(self) -> str:
        """Where a user should click through to."""
        return f"http://{self._host}/state"

    async def async_get_sensors(self) -> dict[str, dict[str, Any]]:
        """Fetch the tanks.

        Returns:
            ``{sensor_id: sensor_dict}``.

        Raises:
            AquiloApiError: On any transport or payload problem.
        """
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
        except ValueError as err:
            # A 200 carrying something that is not JSON. Without this it would
            # leave the integration as an unhandled exception instead of a
            # failed update.
            raise AquiloApiError(f"Malformed JSON from {url}: {err}") from err

        if not isinstance(data, dict):
            raise AquiloApiError(f"Unexpected payload from {url}: {data!r}")
        sensors = data.get("sensors")
        if not isinstance(sensors, list):
            raise AquiloApiError(f"Unexpected payload from {url}: {data!r}")

        result: dict[str, dict[str, Any]] = {}
        for entry in sensors:
            if not isinstance(entry, dict):
                _LOGGER.warning("Aquilo sensor entry not an object, skipping: %r", entry)
                continue
            sensor_id = entry.get("id")
            if not sensor_id:
                _LOGGER.warning("Aquilo sensor entry without id, skipping: %s", entry)
                continue
            result[sensor_id] = entry
        return result


class AquiloCloudClient:
    """Reads the tanks from the vendor dashboard API.

    Holds a bearer token and logs in again once on a 401, because the token
    outlives neither a server restart nor its own expiry and a silent single
    retry is cheaper than failing a poll.
    """

    source = "cloud"

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        label: str | None = None,
    ) -> None:
        """Store credentials and the identity label.

        Args:
            session: Shared aiohttp session.
            username: Vendor account, which for a single gateway is its device id.
            password: Vendor account password.
            label: Identity label to keep in unique ids. Defaults to the
                username; an entry converted from a local one passes its old
                host so its entities keep their ids.
        """
        self._session = session
        self._username = username
        self._password = password
        self._label = label or username
        self._token: str | None = None

    @property
    def host(self) -> str:
        """Stable identity label for this entry, used in every unique id."""
        return self._label

    @property
    def configuration_url(self) -> str:
        """Where a user should click through to."""
        return "https://panel.aquilo.pl/"

    async def async_login(self) -> None:
        """Obtain a bearer token.

        Raises:
            AquiloAuthError: If the credentials are rejected.
            AquiloApiError: On any other transport or payload problem.
        """
        url = f"{CLOUD_BASE}/login"
        payload = {"username": self._username, "password": self._password}
        try:
            async with self._session.post(url, json=payload, timeout=TIMEOUT) as resp:
                body = await resp.json(content_type=None)
                if resp.status in (400, 401, 403):
                    raise AquiloAuthError(
                        (body or {}).get("error", "Authentication failed")
                        if isinstance(body, dict)
                        else "Authentication failed"
                    )
                if resp.status != 200:
                    raise AquiloApiError(f"HTTP {resp.status} from {url}")
        except asyncio.TimeoutError as err:
            raise AquiloApiError(f"Timeout talking to {url}") from err
        except aiohttp.ClientError as err:
            raise AquiloApiError(f"Connection error talking to {url}: {err}") from err
        except ValueError as err:
            raise AquiloApiError(f"Malformed JSON from {url}: {err}") from err

        token = (body or {}).get("token") if isinstance(body, dict) else None
        if not token:
            raise AquiloApiError(f"No token in the response from {url}")
        self._token = token

    async def _async_get(self, path: str, retry: bool = True) -> Any:
        """GET a cloud path, logging in first or again as needed.

        Args:
            path: Path under the API base, starting with a slash.
            retry: Whether a 401 may trigger one re-login and one retry.

        Returns:
            The decoded JSON body.

        Raises:
            AquiloAuthError: If the credentials are rejected.
            AquiloApiError: On any other transport or payload problem.
        """
        if self._token is None:
            await self.async_login()
        url = f"{CLOUD_BASE}{path}"
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with self._session.get(url, headers=headers, timeout=TIMEOUT) as resp:
                if resp.status == 401 and retry:
                    self._token = None
                    return await self._async_get(path, retry=False)
                if resp.status != 200:
                    raise AquiloApiError(f"HTTP {resp.status} from {url}")
                return await resp.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise AquiloApiError(f"Timeout talking to {url}") from err
        except aiohttp.ClientError as err:
            raise AquiloApiError(f"Connection error talking to {url}: {err}") from err
        except ValueError as err:
            raise AquiloApiError(f"Malformed JSON from {url}: {err}") from err

    async def async_get_sensors(self) -> dict[str, dict[str, Any]]:
        """Fetch the tanks and normalise them to the local payload's shape.

        Returns:
            ``{sensor_id: sensor_dict}`` using the same field names the gateway
            uses, so nothing downstream has to know which source it got.

        Raises:
            AquiloApiError: On any transport or payload problem.
        """
        data = await self._async_get("/sensors")
        if not isinstance(data, dict) or not isinstance(data.get("sensors"), list):
            raise AquiloApiError(f"Unexpected payload from the cloud: {data!r}")

        result: dict[str, dict[str, Any]] = {}
        for row in data["sensors"]:
            if not isinstance(row, dict):
                continue
            sensor_id = row.get("sensor")
            if not sensor_id:
                _LOGGER.warning("Cloud row without a sensor id, skipping: %s", row)
                continue
            normalised = self._normalise(row)
            if normalised is not None:
                result[sensor_id] = normalised
        return result

    def _normalise(self, row: dict[str, Any]) -> dict[str, Any] | None:
        """Map one cloud row onto the gateway's field names.

        Args:
            row: One entry of the cloud ``sensors`` array.

        Returns:
            The mapped sensor dict, or None when the row carries no usable
            reading.
        """
        sensor_id = str(row["sensor"])
        out: dict[str, Any] = {"id": sensor_id}
        if row.get("settings_name"):
            out["name"] = row["settings_name"]

        read1 = row.get("read1")
        depth = (
            row.get("tank_depth_manual_cm")
            if row.get("tank_depth_mode") == "manual"
            else row.get("tank_depth_auto_cm")
        )
        full = row.get("max_level")
        if read1 is not None and depth is not None and full is not None:
            try:
                out.update(compute_levels(float(read1), float(depth), float(full)))
            except ValueError as err:
                _LOGGER.warning("%s: cannot compute a level (%s)", sensor_id, err)
        else:
            _LOGGER.warning(
                "%s: cloud row lacks read1/depth/max_level, level not computed",
                sensor_id,
            )

        if row.get("battery_pct") is not None:
            out["bat"] = row["battery_pct"]
        if row.get("battery_mv") is not None:
            out["batMv"] = row["battery_mv"]
        if row.get("read_time"):
            out["lstRead"] = row["read_time"]
        if row.get("last_empty"):
            out["lstEmpty"] = row["last_empty"]
        for extra in ("rssi", "temp"):
            if row.get(extra) is not None:
                out[extra] = row[extra]

        days_left = _days_until(row.get("next_full"))
        if days_left is not None:
            out["daysLeft"] = days_left
        return out if len(out) > 1 else None


def _days_until(stamp: Any) -> int | None:
    """Whole days from now until an ISO timestamp, if it is in the future.

    The cloud expresses its fill prediction as a date rather than a countdown,
    and leaves a stale one in place for tanks it cannot predict, so a date in
    the past means "no prediction" rather than "zero days".

    Args:
        stamp: An ISO 8601 timestamp, or anything else.

    Returns:
        The number of whole days, or None when there is no usable future date.
    """
    if not isinstance(stamp, str):
        return None
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = when - datetime.now(timezone.utc)
    return delta.days if delta.days > 0 else None


# Kept so existing imports and any downstream code keep working: the local
# gateway was the only source before the cloud option existed.
AquiloClient = AquiloLocalClient
