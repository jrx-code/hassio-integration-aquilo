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

Settings → Devices & Services → Add Integration → **Aquilo**, then pick where
the readings should come from. The same tanks answer two ways:

| source | what it polls | needs | interval |
|---|---|---|---|
| **Local gateway** | `http://<host>/state` on the gateway itself | the gateway reachable on your network | 5 min |
| **Aquilo cloud** | `panel.aquilo.pl` API with your account | internet and the vendor account | 15 min |

Local is the default and nothing leaves your network: the same unauthenticated
endpoint the vendor's own YAML instructions use. The cloud source exists because
it still answers when the gateway is unreachable, and because the vendor keeps
its own tank geometry and fill prediction there. For a single gateway the cloud
user name is the gateway's device id.

The choice is not permanent. **Settings → Devices & Services → Aquilo →
Reconfigure** offers the same two options again, and switching keeps your tanks,
entities and history: the identity every entity id is built from is stored once
and never changes with the source.

Two differences to expect when you switch, because the sources disagree rather
than because something is wrong:

- **Battery percentage.** The gateway and the cloud compute it differently and
  the two do not match. On a mains-powered sensor neither figure means much, so
  the raw millivolts are exposed as a `batMv` attribute.
- **Days to full.** Locally it comes from the prediction the gateway was handed;
  from the cloud it is derived from the vendor's own `next_full` date, and a
  stale date in the past is reported as no prediction rather than zero days.

Levels and fill percentage do agree: the cloud answers with the raw radar
reading and the tank geometry rather than a finished level, so this integration
computes them the same way in both modes.

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
default 24), overflow-risk threshold (%, default 90), and a per-tank
exclusion list — the second options step lists every tank the gateway has
reported and lets you check the ones to drop. Excluding a tank removes its
device and all its entities from Home Assistant immediately and stops it
from being recreated on the next poll; unchecking it brings it back.

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
