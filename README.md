# Solar Tracking Dashboard

A self-hosted dashboard for an SRNE / Eco-Worthy hybrid solar inverter and JBD
battery BMS, running headless on a **Raspberry Pi Zero 2 W**. It polls live
telemetry, stores a time-series history (which the companion Android app never
kept), and serves current + historical charts over the local network.

Phase 2 of the "Private Solar Monitoring" project — the protocol layer is a
faithful Python port of that Android app, validated byte-for-byte against the
same reference vectors.

## Data sources

| Source | Transport | Status |
|--------|-----------|--------|
| SRNE/Eco-Worthy inverter | TCP 8899 (Solarman V5 + Modbus-RTU) | **Phase 2a — in progress** |
| JBD BMS (per-cell battery) | BLE (svc 0xFF00 / notify 0xFF01) | Phase 2b — planned |

The inverter also reports battery SOC / voltage / current / temp, so Phase 2a
already covers the core picture; BLE adds per-cell granularity.

## Layout

```
solardash/
  codec.py      CRC-16/Modbus, Modbus-RTU (fn 0x03), Solarman V5 framing
  inverter.py   SRNE register map + decode (InverterStatus)
  client.py     async TCP poller for the Solarman dongle        (next)
  db.py         SQLite time-series store                        (next)
  poller.py     periodic poll -> store loop                     (next)
  server.py     FastAPI: JSON API + serves the dashboard        (next)
  web/          static dashboard (uPlot, styled to the app)     (next)
sim/            offline inverter simulator (replays captured frames)  (next)
tests/          protocol tests pinned to real reference vectors
```

## Tests

Pure-stdlib, no installs needed:

```
python tests/test_codec.py
```

## Build status (Phase 2a)

- [x] Protocol core ported + tested (codec, SRNE decode) — 15/15 green
- [x] Async TCP client + offline simulator — end-to-end, 19/19 green
- [x] SQLite time-series store — WAL, downsampling, prune
- [x] Poll loop — merge + has_core resilience, 29/29 green
- [x] FastAPI server + JSON API (/api/current, /api/history, /api/health) — 33/33 green
- [x] Dashboard UI — uPlot, styled to the Android app's palette, fault catalog
- [x] Custom graphics — radial power wheels (PV/Load/AC-Input), battery SOC bar, power-flow diagram
- [x] Energy tracking — hourly/daily/monthly roll-ups + lifetime totals (/api/energy) — 39/39 green
- [x] Settings menu — show/hide AC Input + energy trends (persisted)
- [x] systemd user services (solardash + solardash-sim), linger=yes, auto-restart
- [x] Deploy on-site — live on the real inverter (192.168.3.38)
- Phase 2b — BLE battery:
  - [x] BMS discovery — 4 ECO-LFP48100 packs found (svc 0xFF00 / ff01 / ff02)
  - [x] JBD parser (0x03 basic info + 0x04 cells) — validated vs real frames
  - [x] BLE poller for all 4 packs + bank aggregation (auto-capacity, cell balance, temps)
  - [x] Dashboard integration (per-cell detail, real temps, auto ETA capacity) — 54/54 green
  - [x] BLE access from the systemd user service + persistent rfkill unblock (bt-unblock.service)

## Service management (on the Pi)

```
systemctl --user status solardash           # health
journalctl --user -u solardash -f           # live logs
systemctl --user restart solardash          # restart after editing solardash.env
```

### Going on-site (real inverter)
1. Edit `~/solardash/solardash.env`: set `SOLAR_INVERTER_IP`, `SOLAR_INVERTER_SERIAL`
   (printed on the Solarman dongle), and `SOLAR_POLL_INTERVAL` (e.g. 10).
2. Disable the simulator: `systemctl --user disable --now solardash-sim`
3. `systemctl --user restart solardash`

## Android app integration (mDNS)

The Private Solar Monitoring Android app can read battery + inverter data straight from this Pi
over `GET /api/battery` and `GET /api/current`, instead of connecting to the batteries over
Bluetooth itself. That matters because the JBD packs allow only one BLE connection at a time — when
the Pi is polling them, the phone can't, and vice-versa. With this Pi on the network the app pulls
from it automatically and leaves the BLE link to the Pi.

Discovery uses mDNS: `server.py` advertises a `_solarpi._tcp` service (port from `SOLAR_HTTP_PORT`,
default 8000) via the `zeroconf` package. It's best-effort — if `zeroconf` isn't installed the
dashboard still serves; the app then falls back to a manually-entered host in its Discover tab.

If you'd rather advertise via the Pi's own avahi-daemon (no Python dependency), drop this in
`/etc/avahi/services/solarpi.service` and `sudo systemctl restart avahi-daemon`:

```xml
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">Solar Pi on %h</name>
  <service>
    <type>_solarpi._tcp</type>
    <port>8000</port>
  </service>
</service-group>
```
