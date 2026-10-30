# Changelog

Dates are GitHub release dates (UTC). Earlier entries were written after the fact
from the tagged commit messages.

## Unreleased

- Config flow and options in English by default: `strings.json` was Polish-only
  (identical to `translations/pl.json`), so non-Polish UIs had no English text.
  Added `translations/en.json`; `pl.json` unchanged (#1). Entity names are still
  Polish, set in code.

## 0.1.6 (2026-08-26)

- Options flow gets a second step listing every tank the gateway has reported,
  with checkboxes to exclude tanks. An excluded tank's device and entities are
  removed and not recreated until it is unchecked.

## 0.1.5 (2026-08-24)

- Entity names sometimes fell back to the raw `translation_key` in Title Case
  (an upstream translation-cache issue for custom integrations). Entity names
  are now literal names in code, not translation keys.

## 0.1.4 (2026-08-23)

- Tanks reported by the gateway after setup are added live, without a reload.
- Config flow rejects a gateway that reports no sensors and strips `http(s)://`
  and a trailing slash pasted into the host field.
- No crash when the gateway sends `"name": null`; malformed JSON from the
  gateway raises a clean API error.
- Hardening and HACS default-store readiness.

## 0.1.3 (2026-08-23)

- `icon.png` and `icon@2x.png` had an opaque white background; real
  transparency restored.

## 0.1.2 (2026-08-23)

- Config entry title is `Aquilo (<host>)` instead of a list of tank names.
- Added the Aquilo wordmark logo.

## 0.1.1 (2026-08-23)

- Integration brand icon.

## 0.1.0 (2026-08-23)

- First release: config flow, tanks discovered from the gateway's `/state`
  endpoint, one device per tank, sensors for level, fill, battery, days left,
  last read and last emptied, plus two binary sensors: stale data and overflow
  risk.
