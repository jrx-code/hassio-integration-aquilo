# Changelog

Dates are GitHub release dates (UTC). Earlier entries were written after the fact
from the tagged commit messages.

## Unreleased

- Test suite: the API clients (both sources), the config flow's source menu and
  reconfigure step, the level arithmetic, the sensor and binary-sensor entities,
  the version-1 entry migration and a regression test for the redacted cloud
  password. Ruff and Pytest run on GitHub; `ruff.toml` pins the rule set so a
  new Ruff release cannot turn the lint red on its own.
- The HACS and hassfest workflows run only on GitHub: the Forgejo runner also
  picks up `.github/workflows` when a repo has no `.forgejo/workflows`, and
  those actions do not work there.

## 0.3.0 (2026-10-30)

- Two diagnostic entities per tank carry the measurement behind the computed
  values. "Surowy odczyt" takes the gateway's own raw string as its state and
  everything else it sent as attributes (`read1`, `amp1`, the counters, `crc`,
  `rssi`, `wifi`, `snr`, the revision), including a reading the plausibility
  gate turned away. It stays available when the tank's other entities do not,
  because a rejected reading is what one wants to see then.
- "Jakość echa" exposes the echo amplitude on its own, as a measurement with a
  graph: the one number that says whether the sensor is seeing a liquid surface
  at all. Created only where the hardware reports it, which excludes the `g1`
  sewage sensor.

## 0.2.1 (2026-10-30)

- The readings can now come from either source, chosen in the config flow and
  changeable later through reconfigure: the local gateway's own HTTP endpoint,
  or the vendor dashboard API. The entry's identity label is stored once and
  kept, so switching source keeps every entity and its history. Version-1
  entries are migrated to the local source. The cloud answers with raw readings
  and tank geometry rather than finished levels, so the arithmetic lives in the
  integration and both sources return the same shape. (0.2.0 was never
  released: the two defects below were found reviewing it.)
- Diagnostics handed out the config entry verbatim, which was harmless while an
  entry held only a LAN hostname and a credential leak once it could hold a
  vendor account password. The user name and password are now redacted.
- The three places that decode a JSON body caught timeouts and client errors
  but not a malformed body, so a 200 carrying something that is not JSON
  surfaced as an unhandled `ValueError` instead of a failed update.

## 0.1.8 (2026-10-26)

- Two always-available diagnostic entities per tank: "Identyfikator" (the
  Aquilo sensor id) and "Adres bramki" (where it is read from). Both stay up
  while the gateway is unreachable, because they carry identity and config
  rather than live readings. 0.1.7 only put the id in the device serial number
  and the diagnostics download, so nothing showed under the device page's
  "Diagnostic" section.

## 0.1.7 (2026-10-26)

- "Download diagnostics" on the config entry and on each tank device: the
  gateway host, the config entry, coordinator state and the raw per-tank
  payload keyed by sensor id.
- Each tank's id is the device serial number, visible on the device page.
- The device "Delete" button works. A tank the gateway no longer reports is
  removed; one still reported is also added to the excluded list so the next
  refresh does not recreate it.
- Config flow and options are in English by default: `strings.json` was
  Polish-only, so non-Polish interfaces had no English text. Added
  `translations/en.json`; `pl.json` unchanged (#1). Entity names are still
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
