"""Runtime configuration from environment variables (12-factor style).

Defaults point at a LOCAL SIMULATOR so the dashboard runs anywhere out of the box.
On the Pi at the solar site, set SOLAR_INVERTER_IP / SOLAR_INVERTER_SERIAL to the
real Solarman dongle (the serial is printed on the stick).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    inverter_ip: str = "127.0.0.1"
    inverter_serial: int = 1234567890
    inverter_port: int = 8899
    poll_interval_s: float = 10.0
    db_path: str = "data/solar.sqlite"
    retention_days: int = 0  # 0 = keep forever; >0 prunes samples older than N days
    # Usable battery bank capacity (kWh) for the time-to-full/empty estimate.
    # Default = one Eco-Worthy ECO-LFP48100 (48 V x 100 Ah ≈ 4.8 kWh). Set to your bank total.
    battery_capacity_kwh: float = 4.8

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
        )
