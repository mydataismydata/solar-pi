"""Pure API payload builders over the store — no web framework here, so they unit-test
on a bare Python. server.py is a thin FastAPI adapter that just calls these.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .db import NUMERIC_COLUMNS, TimeSeriesStore
from .faults import FaultCatalog

# Sensible default series for the dashboard's main chart.
DEFAULT_HISTORY_FIELDS = ["pv_power", "load_total", "battery_power", "battery_soc"]


def _battery_eta(d: Dict[str, object], capacity_wh: Optional[float]):
    """Static time-to-full/empty estimate (minutes) from SOC, current power, and capacity.

    Charging -> minutes to full; discharging -> minutes to empty; idle/unknown -> (None, None).
    """
    soc = d.get("battery_soc")
    bw = d.get("battery_power")
    if not capacity_wh or soc is None or bw is None:
        return None, None
    if bw > 10:  # charging
        if soc >= 100:
            return 0, "full"
        remaining_wh = capacity_wh * (100 - soc) / 100.0
        return round(remaining_wh / bw * 60), "full"
    if bw < -10:  # discharging
        if soc <= 0:
            return 0, "empty"
        stored_wh = capacity_wh * soc / 100.0
        return round(stored_wh / (-bw) * 60), "empty"
    return None, None  # ~idle


def current_payload(
    store: TimeSeriesStore,
    catalog: Optional[FaultCatalog] = None,
    battery_capacity_wh: Optional[float] = None,
) -> Dict[str, object]:
    """Latest snapshot for the live tiles, with faults annotated and a battery ETA."""
    latest = store.latest()
    if latest is None:
        return {"available": False}
    faults = latest.get("fault_codes") or []
    annotated = catalog.annotate(faults) if catalog else [{"code": c, "text": str(c)} for c in faults]
    out: Dict[str, object] = {"available": True, "ts": latest["ts"], "faults": annotated}
    for key, value in latest.items():
        if key not in ("ts", "fault_codes"):
            out[key] = value
    # Derive per-string PV power (the stored row keeps PV1/PV2 voltage & current, not the product).
    for n in (1, 2):
        v = out.get(f"pv{n}_voltage")
        i = out.get(f"pv{n}_current")
        out[f"pv{n}_power"] = round(v * i, 1) if (v is not None and i is not None) else None
    out["battery_eta_minutes"], out["battery_eta_kind"] = _battery_eta(out, battery_capacity_wh)
    return out


def history_payload(
    store: TimeSeriesStore,
    fields: Optional[List[str]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
    max_points: int = 1000,
) -> Dict[str, object]:
    """Columnar time-series for charting: {ts:[...], series:{field:[...]}, fields:[...]}.

    Columnar (parallel arrays) is what uPlot consumes directly and keeps the JSON small.
    """
    requested = fields or DEFAULT_HISTORY_FIELDS
    used = [f for f in requested if f in NUMERIC_COLUMNS]
    rows = store.series(used, start=start, end=end, max_points=max_points)
    return {
        "fields": used,
        "ts": [r["ts"] for r in rows],
        "series": {f: [r.get(f) for r in rows] for f in used},
        "count": len(rows),
    }


ENERGY_PERIODS = ("hour", "day", "month")


def energy_payload(
    store: TimeSeriesStore,
    period: str = "day",
    start: Optional[int] = None,
    end: Optional[int] = None,
    limit: Optional[int] = None,
) -> Dict[str, object]:
    """Energy roll-up buckets (kWh) for the trends chart."""
    if period not in ENERGY_PERIODS:
        period = "day"
    return {"period": period, "buckets": store.energy_buckets(period, start=start, end=end, limit=limit)}


def lifetime_payload(store: TimeSeriesStore) -> Dict[str, object]:
    """All-time input (PV) / output (load) energy totals (kWh) for the header strip."""
    return store.energy_lifetime()
