"""Periodic BLE poll of the JBD BMS bank: reads all packs, aggregates, and holds the latest
snapshot in memory for the API. Slower cadence than the inverter (battery state moves slowly,
and a 4-pack sequential BLE read takes ~15-25 s).
"""
from __future__ import annotations

import asyncio
import time
from typing import List, Optional, Tuple

from .bms_client import BankSummary, PackSample, read_bank, summarize

DEFAULT_BMS_INTERVAL_S = 60.0


class BmsPoller:
    def __init__(self, addresses: List[Tuple[str, str]], interval_s: float = DEFAULT_BMS_INTERVAL_S,
                 clock=time.time):
        self.addresses = addresses          # [(mac, name), ...]
        self.interval_s = interval_s
        self.clock = clock
        self.last_ts: Optional[int] = None
        self.bank: Optional[BankSummary] = None
        self.packs: List[Optional[PackSample]] = []
        self.consecutive_failures = 0

    async def poll_once(self) -> Optional[BankSummary]:
        samples = await read_bank([a for a, _ in self.addresses])
        for sample, (_, name) in zip(samples, self.addresses):
            if sample is not None:
                sample.name = name
        bank = summarize(samples)
        if bank is None:
            self.consecutive_failures += 1
            return None
        self.consecutive_failures = 0
        self.packs = samples
        self.bank = bank
        self.last_ts = int(self.clock())
        return bank

    async def run(self, stop_event: Optional[asyncio.Event] = None) -> None:
        while not (stop_event and stop_event.is_set()):
            try:
                await self.poll_once()
            except Exception:
                self.consecutive_failures += 1
            try:
                if stop_event:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.interval_s)
                else:
                    await asyncio.sleep(self.interval_s)
            except asyncio.TimeoutError:
                pass
