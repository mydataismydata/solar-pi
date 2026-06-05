"""One-time backfill: reconstruct hourly energy from already-stored power samples.

Integrates inverter_samples (pv_power / load_total / battery_power) the same way the
live poller does (trapezoidal, gap-capped) so the energy trends + lifetime aren't empty
on first run. Safe to re-run: it clears energy_hourly first.

Usage (on the Pi, from the project root, with the venv active):
    python deploy/backfill_energy.py [db_path]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solardash.db import TimeSeriesStore
from solardash.poller import MAX_ENERGY_GAP_S

DB = sys.argv[1] if len(sys.argv) > 1 else "data/solar.sqlite"


def main() -> None:
    store = TimeSeriesStore(DB)
    with store._lock:
        store._conn.execute("DELETE FROM energy_hourly")
        store._conn.commit()
        rows = store._conn.execute(
            "SELECT ts, pv_power, load_total, battery_power FROM inverter_samples ORDER BY ts"
        ).fetchall()

    prev = None
    intervals = 0
    for r in rows:
        cur = {
            "ts": r["ts"],
            "pv": r["pv_power"] or 0.0,
            "load": float(r["load_total"] or 0),
            "batt": r["battery_power"] or 0.0,
        }
        if prev is not None:
            dt = cur["ts"] - prev["ts"]
            if 0 < dt <= MAX_ENERGY_GAP_S:
                store.accrue(
                    cur["ts"], dt,
                    (prev["pv"] + cur["pv"]) / 2,
                    (prev["load"] + cur["load"]) / 2,
                    (prev["batt"] + cur["batt"]) / 2,
                )
                intervals += 1
        prev = cur

    lt = store.energy_lifetime()
    print(f"backfilled {len(rows)} samples / {intervals} intervals")
    print(f"lifetime: PV {lt['pv_kwh']} kWh, load {lt['load_kwh']} kWh, "
          f"charged {lt['charge_kwh']} kWh, discharged {lt['discharge_kwh']} kWh")
    store.close()


if __name__ == "__main__":
    main()
