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
- [ ] Deploy on-site, point at the real dongle (edit solardash.env, disable sim)
- [ ] Phase 2b — BLE battery (per-cell voltages)

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
