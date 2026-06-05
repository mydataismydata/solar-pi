#!/usr/bin/env python3
"""Live read of all four ECO-LFP48100 packs over BLE, with a bank summary.

    python deploy/bms_read.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solardash.bms_client import read_bank, summarize

PACKS = [
    ("AA:C2:37:06:56:72", "065672"),
    ("AA:C2:37:06:57:4C", "06574C"),
    ("AA:C2:37:08:25:3D", "08253D"),
    ("AA:C2:37:08:25:44", "082544"),
]


async def main():
    print("reading bank (one pack at a time)...")
    samples = await read_bank([a for a, _ in PACKS])
    for (addr, name), s in zip(PACKS, samples):
        if s is None:
            print(f"  {name}  <no data>")
            continue
        i = s.info
        d_mv = (s.cell_delta or 0) * 1000
        print(f"  {name}  {i.voltage:6.2f}V {i.current:+7.2f}A  SOC {i.soc:3d}%  "
              f"{i.residual_ah:5.1f}/{i.nominal_ah:.0f}Ah  cells {s.cell_min:.3f}-{s.cell_max:.3f} "
              f"(Δ{d_mv:.0f}mV)  temps {min(i.temps_c):.1f}-{max(i.temps_c):.1f}°C  cyc {i.cycles}"
              f"{'  *FAULT*' if i.has_fault else ''}")

    bank = summarize(samples)
    if bank:
        print(f"\nBANK  {bank.voltage:.2f}V  {bank.current:+.2f}A  {bank.power:.0f}W  "
              f"SOC {bank.soc:.1f}%  {bank.residual_ah:.0f}/{bank.nominal_ah:.0f}Ah = {bank.capacity_kwh:.2f}kWh  "
              f"cellΔ {(bank.cell_delta or 0) * 1000:.0f}mV  temps {bank.temp_min:.1f}-{bank.temp_max:.1f}°C  "
              f"packs {bank.packs}/{len(PACKS)}")
    else:
        print("\nBANK  <no packs read>")


if __name__ == "__main__":
    asyncio.run(main())
