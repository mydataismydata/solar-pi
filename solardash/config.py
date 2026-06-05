"""Runtime configuration from environment variables (12-factor style).

Defaults point at a LOCAL SIMULATOR so the dashboard runs anywhere out of the box.
On the Pi at the solar site, set SOLAR_INVERTER_IP / SOLAR_INVERTER_SERIAL to the
real Solarman dongle (the serial is printed on the stick).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Tuple

# The four ECO-LFP48100 packs (BLE MAC, short name). Override with SOLAR_BMS_ADDRESSES.
DEFAULT_BMS_ADDRESSES: List[Tuple[str, str]] = [
    ("AA:C2:37:06:56:72", "065672"),
    ("AA:C2:37:06:57:4C", "06574C"),
    ("AA:C2:37:08:25:3D", "08253D"),
    ("AA:C2:37:08:25:44", "082544"),
]


def _parse_bms_addresses(spec: str) -> List[Tuple[str, str]]:
    """Parse 'MAC=name,MAC=name' (name optional) into [(mac, name), ...]."""
    out: List[Tuple[str, str]] = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        mac, _, name = item.partition("=")
        mac = mac.strip()
        out.append((mac, name.strip() or mac[-6:].replace(":", "")))
    return out


@dataclass
class Config:
    inverter_ip: str = "127.0.0.1"
    inverter_serial: int = 1234567890
    inverter_port: int = 8899
    poll_interval_s: float = 10.0
    db_path: str = "data/solar.sqlite"
    retention_days: int = 0  # 0 = keep forever; >0 prunes samples older than N days
    # Usable battery bank capacity (kWh) for the time-to-full/empty estimate. Used only as a
    # fallback — when the BMS is connected, capacity is auto-derived from the packs' rated Ah.
    battery_capacity_kwh: float = 4.8
    # JBD BMS (BLE) bank
    bms_enabled: bool = True
    bms_interval_s: float = 60.0
    bms_addresses: List[Tuple[str, str]] = field(default_factory=lambda: list(DEFAULT_BMS_ADDRESSES))

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            inverter_ip=os.environ.get("SOLAR_INVERTER_IP", cls.inverter_ip),
            inverter_serial=int(os.environ.get("SOLAR_INVERTER_SERIAL", cls.inverter_serial)),
            inverter_port=int(os.environ.get("SOLAR_INVERTER_PORT", cls.inverter_port)),
            poll_interval_s=float(os.environ.get("SOLAR_POLL_INTERVAL", cls.poll_interval_s)),
            db_path=os.environ.get("SOLAR_DB_PATH", cls.db_path),
            retention_days=int(os.environ.get("SOLAR_RETENTION_DAYS", cls.retention_days)),
            battery_capacity_kwh=float(os.environ.get("SOLAR_BATTERY_CAPACITY_KWH", cls.battery_capacity_kwh)),
            bms_enabled=os.environ.get("SOLAR_BMS_ENABLED", "1") not in ("0", "false", "False"),
            bms_interval_s=float(os.environ.get("SOLAR_BMS_INTERVAL", cls.bms_interval_s)),
            bms_addresses=(
                _parse_bms_addresses(os.environ["SOLAR_BMS_ADDRESSES"])
                if os.environ.get("SOLAR_BMS_ADDRESSES")
                else list(DEFAULT_BMS_ADDRESSES)
            ),
        )
