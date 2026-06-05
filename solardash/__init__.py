"""Solar Tracking Dashboard — Raspberry Pi server for an SRNE/Eco-Worthy hybrid
inverter (TCP/Solarman) and, later, a JBD BMS (BLE).

Phase 2a: inverter-over-TCP poller -> SQLite time-series -> FastAPI dashboard.

The protocol layer (codec.py, inverter.py) is a faithful Python port of the
Android app "Private Solar Monitoring" (EcoUnworthy), validated byte-for-byte
against the same reference vectors used there.
"""

__version__ = "0.1.0"
