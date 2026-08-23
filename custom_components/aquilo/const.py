"""Constants for the Aquilo integration."""
from __future__ import annotations

DOMAIN = "aquilo"

DEFAULT_SCAN_INTERVAL_SECONDS = 300  # 5 min — gateway just echoes the last reading it has
DEFAULT_STALE_HOURS = 24
DEFAULT_OVERFLOW_PCT = 90

CONF_STALE_HOURS = "stale_hours"
CONF_OVERFLOW_PCT = "overflow_pct"

ATTR_LVL = "lvl"
ATTR_PCT = "pct"
ATTR_BAT = "bat"
ATTR_LST_READ = "lstRead"
ATTR_LST_EMPTY = "lstEmpty"
ATTR_DAYS_LEFT = "daysLeft"
ATTR_LVL_TO_FULL = "lvlToFull"
ATTR_NAME = "name"
ATTR_ID = "id"
