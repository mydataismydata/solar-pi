"""BLE client for the JBD/Xiaoxiang BMS packs: read one pack (0x03 + 0x04), read a whole bank
(sequentially — one BT radio), and aggregate the packs into a bank summary.

bleak is imported lazily inside the read functions so the parsing/aggregation here stays
importable and unit-testable on a machine without BlueZ.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import List, Optional

from .jbd import (
    CMD_BASIC,
    CMD_BASIC_INFO,
    CMD_CELL_VOLTS,
    CMD_CELLS,
    NOTIFY_UUID,
    WRITE_UUID,
    JbdAssembler,
    PackInfo,
    parse_basic_info,
    parse_cell_voltages,
)
from .pack_broadcast import PackBroadcast

CELL_NOMINAL_V = 3.2  # LiFePO4 nominal cell voltage, for capacity (kWh) derivation


@dataclass
class PackSample:
    address: str
    name: Optional[str]
    info: PackInfo
    cells: List[float] = field(default_factory=list)
    parallel: Optional[int] = None  # position in the parallel group (1=master) from the broadcast

    @property
    def cell_min(self) -> Optional[float]:
        return min(self.cells) if self.cells else None

    @property
    def cell_max(self) -> Optional[float]:
        return max(self.cells) if self.cells else None

    @property
    def cell_delta(self) -> Optional[float]:
        return round(max(self.cells) - min(self.cells), 3) if self.cells else None


@dataclass
class BankSummary:
    packs: int
    voltage: float          # V (parallel packs -> average)
    current: float          # A (sum; + charge / - discharge)
    power: float            # W
    soc: float              # % (capacity-weighted)
    nominal_ah: float       # total rated capacity
    residual_ah: float      # total remaining
    capacity_kwh: float     # derived total energy capacity
    cell_min: Optional[float]
    cell_max: Optional[float]
    cell_delta: Optional[float]
    temp_min: Optional[float]
    temp_max: Optional[float]
    fault_packs: List[str] = field(default_factory=list)


def summarize(packs: List[Optional[PackSample]]) -> Optional[BankSummary]:
    """Aggregate per-pack samples into a bank summary (ignores packs that failed to read)."""
    live = [p for p in packs if p is not None]
    if not live:
        return None
    n = len(live)
    voltage = sum(p.info.voltage for p in live) / n
    current = sum(p.info.current for p in live)
    nominal_ah = sum(p.info.nominal_ah for p in live)
    residual_ah = sum(p.info.residual_ah for p in live)
    soc = (residual_ah / nominal_ah * 100.0) if nominal_ah else 0.0
    cells_per_pack = live[0].info.cell_count or 16
    capacity_kwh = nominal_ah * cells_per_pack * CELL_NOMINAL_V / 1000.0
    all_cells = [c for p in live for c in p.cells]
    all_temps = [t for p in live for t in p.info.temps_c]
    return BankSummary(
        packs=n,
        voltage=round(voltage, 2),
        current=round(current, 2),
        power=round(voltage * current, 1),
        soc=round(soc, 1),
        nominal_ah=round(nominal_ah, 1),
        residual_ah=round(residual_ah, 2),
        capacity_kwh=round(capacity_kwh, 2),
        cell_min=round(min(all_cells), 3) if all_cells else None,
        cell_max=round(max(all_cells), 3) if all_cells else None,
        cell_delta=round(max(all_cells) - min(all_cells), 3) if all_cells else None,
        temp_min=min(all_temps) if all_temps else None,
        temp_max=max(all_temps) if all_temps else None,
        fault_packs=[p.address for p in live if p.info.has_fault],
    )


async def read_pack(address: str, name: Optional[str] = None, connect_timeout: float = 20.0,
                    reply_timeout: float = 6.0, broadcast_timeout: float = 3.0) -> Optional[PackSample]:
    """Connect to one pack, request basic info + cells, capture its position broadcast, disconnect.

    Returns None on failure. The parallel position (1=master) rides an unsolicited broadcast, so
    after the 0x03/0x04 replies arrive we wait a short grace period for one; if none shows in time,
    parallel is left None (the poller carries forward the last-known position).
    """
    from bleak import BleakClient  # lazy: needs BlueZ, only on the Pi

    asm = JbdAssembler()
    bcast = PackBroadcast()
    got = {}
    parallel = None
    done = asyncio.Event()      # basic + cells received
    pos_seen = asyncio.Event()  # parallel position captured from a broadcast

    def cb(_handle, data):
        nonlocal parallel
        raw = bytes(data)
        for cmd, payload in asm.feed(raw):
            got[cmd] = payload
        if CMD_BASIC in got and CMD_CELLS in got:
            done.set()
        if parallel is None:
            pos = bcast.feed(raw)
            if pos:
                parallel = pos
                pos_seen.set()

    try:
        async with BleakClient(address, timeout=connect_timeout) as client:
            await client.start_notify(NOTIFY_UUID, cb)
            await client.write_gatt_char(WRITE_UUID, CMD_BASIC_INFO, response=False)
            await asyncio.sleep(0.4)
            await client.write_gatt_char(WRITE_UUID, CMD_CELL_VOLTS, response=False)
            try:
                await asyncio.wait_for(done.wait(), timeout=reply_timeout)
            except asyncio.TimeoutError:
                pass
            if not pos_seen.is_set():
                try:
                    await asyncio.wait_for(pos_seen.wait(), timeout=broadcast_timeout)
                except asyncio.TimeoutError:
                    pass
            try:
                await client.stop_notify(NOTIFY_UUID)
            except Exception:
                pass
    except Exception:
        return None

    if CMD_BASIC not in got:
        return None
    return PackSample(
        address=address,
        name=name,
        info=parse_basic_info(got[CMD_BASIC]),
        cells=parse_cell_voltages(got[CMD_CELLS]) if CMD_CELLS in got else [],
        parallel=parallel,
    )


async def read_bank(addresses: List[str], gap_s: float = 0.5) -> List[Optional[PackSample]]:
    """Read packs one at a time (single BT radio), with a short gap between connections."""
    out: List[Optional[PackSample]] = []
    for addr in addresses:
        out.append(await read_pack(addr))
        await asyncio.sleep(gap_s)
    return out
