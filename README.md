# Aquilo — Home Assistant integration

Custom integration for [Aquilo](https://aquilo.pl) local-network liquid-level
sensors (septic tank, rainwater tank, well). Not affiliated with or endorsed
by the manufacturer — built by reverse-engineering the local `/state`
endpoint that Aquilo's own [official HA integration
guide](https://aquilo.io/wp-content/uploads/2022/08/Aquilo-Czujnik-poziomu-cieczy-integracja-z-HA-v.1.2-2.pdf)
documents, replacing manual YAML `rest:`/`template:` sensors with a proper
config-flow integration.

## Why

Aquilo's own documentation only shows how to wire up YAML `platform: rest` +
`platform: template` sensors by hand, one tank at a time, with the gateway
IP hardcoded. This integration instead:

- auto-discovers every tank the gateway reports in one config flow step
- gives each tank its own HA device (not a pile of loose entities)
- adds two things the raw API doesn't compute for you: a **stale-data**
  watchdog (battery/comms silently died) and a configurable
  **overflow-risk** alert

## Install

### HACS (custom repository)
1. HACS → Integrations → ⋮ → Custom repositories
2. URL: `https://github.com/jrx-code/hassio-integration-aquilo`, category: Integration
3. Install "Aquilo", restart Home Assistant

### Manual
Copy `custom_components/aquilo` into your `config/custom_components/` and restart.

## Configuration

Settings → Devices & Services → Add Integration → **Aquilo**. Enter the
gateway's local hostname or IP (find it in your router — the vendor's PDF
walks through the same step for the YAML method). The integration hits
`http://<host>/state` once to confirm it's reachable and to list the tanks
it should create devices for.

No cloud account, no API key — this is the same unauthenticated local
endpoint the official YAML instructions use.

## Entities (per tank)

| Entity | Unit | Notes |
|---|---|---|
| Poziom (level) | cm | raw distance/level reading |
| Wypełnienie (fill) | % | |
| Bateria (battery) | % | diagnostic |
| Dni do pustego (days left) | days | only if the gateway reports it |
| Poziom do pełna (level to full) | cm | disabled by default |
| Ostatni odczyt (last read) | timestamp | diagnostic |
| Ostatnie opróżnienie (last emptied) | timestamp | only if reported |
| **Nieaktualne dane** (stale data) | binary | ON when `lstRead` is older than the configured threshold |
| **Ryzyko przepełnienia** (overflow risk) | binary | ON when fill % ≥ configured threshold |

Options (gear icon on the integration): stale-data threshold (hours,
default 24) and overflow-risk threshold (%, default 90).

## Known issues

- Entity friendly names sometimes show the raw `translation_key`
  (e.g. "Battery") instead of the Polish string from
  `translations/pl.json` right after first setup — no error in the log,
  root cause not fully diagnosed yet. Cosmetic only, doesn't affect state
  or automations.
- Tanks discovered after the initial config flow (a new sensor paired to
  the same gateway later) aren't picked up until the integration reloads —
  no dynamic add-on-discovery yet.

## API reference (undocumented beyond the vendor PDF)

`GET http://<gateway>/state` →
```json
{
  "sensors": [
    {"id": "000000", "lvl": 125.6, "pct": 34, "bat": 76,
     "lstRead": "2026-01-01T12:00:00+01:00",
     "lstEmpty": "2025-12-01T09:00:00+01:00",
     "daysLeft": 48, "name": "TANK", "lvlToFull": 121}
  ],
  "from": "node-1"
}
```
`bat`, `daysLeft`, `lvlToFull`, `lstEmpty` aren't mentioned in the 2022
vendor PDF (which only documents `id`/`lvl`/`pct`/`lstRead`) — captured from
a live gateway running current firmware.

## License

MIT
