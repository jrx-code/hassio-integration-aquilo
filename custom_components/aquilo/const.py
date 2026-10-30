"""Constants for the Aquilo integration."""
from __future__ import annotations

DOMAIN = "aquilo"

DEFAULT_SCAN_INTERVAL_SECONDS = 300  # 5 min — gateway just echoes the last reading it has
# The cloud answers from its own database and the sensors transmit every few
# hours, so polling someone else's server as often as the gateway on the LAN
# would buy nothing.
DEFAULT_CLOUD_SCAN_INTERVAL_SECONDS = 900
DEFAULT_STALE_HOURS = 24
DEFAULT_OVERFLOW_PCT = 90

# Where the readings come from. "local" polls the gateway's own HTTP endpoint
# and never leaves the network; "cloud" polls the vendor dashboard API, which
# still answers when the gateway is unreachable.
CONF_SOURCE = "source"
SOURCE_LOCAL = "local"
SOURCE_CLOUD = "cloud"
DEFAULT_SOURCE = SOURCE_LOCAL

CONF_STALE_HOURS = "stale_hours"
CONF_OVERFLOW_PCT = "overflow_pct"
CONF_EXCLUDED_TANKS = "excluded_tanks"

ATTR_LVL = "lvl"
ATTR_PCT = "pct"
ATTR_BAT = "bat"
ATTR_LST_READ = "lstRead"
ATTR_LST_EMPTY = "lstEmpty"
ATTR_DAYS_LEFT = "daysLeft"
ATTR_LVL_TO_FULL = "lvlToFull"
ATTR_NAME = "name"
ATTR_ID = "id"
# Raw measurement data the gateway sends with every reading. The echo amplitude
# is the one number that says whether the sensor is actually seeing a liquid
# surface, so it gets its own entity; the rest travels as attributes.
ATTR_AMP1 = "amp1"
ATTR_RAW = "raw"
ATTR_REJECTED = "rejected"
