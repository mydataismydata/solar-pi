"""Offline Solarman-dongle simulator: a TCP server that speaks Solarman V5 + Modbus
just like the real SRNE WiFi stick, answering register reads from a synthetic "scene".

Lets us exercise the full client -> decode -> store -> dashboard pipeline with no
hardware, anywhere. Run standalone to point a real dashboard at fake data:

    python sim/inverter_sim.py            # serves 0.0.0.0:8899, sunny-day scene

Register values below are RAW (pre-scale) — exactly what the dongle would return.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solardash.codec import modbus_holding_response, v5_decode_request, v5_encode_response

DEFAULT_SERIAL = 1234567890

# A sunny mid-day, battery charging (PV > load). Raw register units; see SrneInverter map.
# Battery current 0x0102 is +discharge/-charge on this unit, so a charging pack reads
# negative: 0xFF6A = -150 -> decode negates to +15.0 A (charging).
DAYTIME_SCENE: Dict[int, int] = {
    0x0100: 87,       # SOC 87 %
    0x0101: 532,      # battery 53.2 V
    0x0102: 0xFF6A,   # raw -150 -> +15.0 A (charging)
    0x0103: 250,      # battery 25.0 degC
    0x0107: 1480,     # PV1 148.0 V
    0x0108: 92,       # PV1 9.2 A   -> 1361.6 W
    0x010F: 1465,     # PV2 146.5 V
    0x0110: 70,       # PV2 7.0 A   -> 1025.5 W
    0x0204: 0, 0x0205: 0, 0x0206: 0, 0x0207: 0,  # no faults
    0x0210: 2,        # machine state: running
    0x0213: 0,        # grid (AC input) L1 — off-grid: no input
    0x0215: 0,        # grid frequency — off-grid
    0x0216: 1208,     # output 120.8 V (L1)
    0x0218: 6000,     # 60.00 Hz
    0x0219: 105,      # load current 10.5 A (L1)
    0x021B: 1180,     # load power 1180 W (L1)
    0x021C: 1320,     # load apparent 1320 VA (L1)
    0x0220: 410,      # DC temp 41.0 degC
    0x0221: 385,      # AC temp 38.5 degC
    0x022A: 0,        # grid (AC input) L2 — off-grid: no input
    0x022C: 1206,     # output L2 120.6 V
    0x0230: 88,       # load L2 current 8.8 A
    0x0232: 990,      # load L2 power 990 W
    0x0234: 1100,     # load L2 apparent 1100 VA
}


def registers_for(start: int, count: int, scene: Dict[int, int]) -> List[int]:
    """Registers the dongle would return for [start, start+count); unknown addrs read 0."""
    return [scene.get(start + i, 0) for i in range(count)]


class InverterSimulator:
    def __init__(self, scene: Optional[Dict[int, int]] = None, serial: int = DEFAULT_SERIAL):
        self.scene = dict(scene if scene is not None else DAYTIME_SCENE)
        self.serial = serial

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                head = await reader.readexactly(3)
                if head[0] != 0xA5:
                    break
                payload_len = head[1] | (head[2] << 8)
                rest = await reader.readexactly(13 + payload_len - 3)
                frame = head + rest

                modbus = v5_decode_request(frame)
                if modbus is None or len(modbus) < 6:
                    continue
                slave = modbus[0]
                start = (modbus[2] << 8) | modbus[3]
                count = (modbus[4] << 8) | modbus[5]
                seq = frame[5] | (frame[6] << 8)  # echo the request sequence, like a real dongle

                regs = registers_for(start, count, self.scene)
                mb_resp = modbus_holding_response(slave, regs)
                writer.write(v5_encode_response(self.serial, seq, mb_resp))
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> asyncio.AbstractServer:
        """Start serving and return the asyncio server (port 0 = ephemeral, for tests)."""
        return await asyncio.start_server(self._handle, host, port)


async def _main() -> None:
    sim = InverterSimulator()
    server = await sim.start("0.0.0.0", 8899)
    addr = server.sockets[0].getsockname()
    print(f"Inverter simulator listening on {addr[0]}:{addr[1]} (serial {sim.serial}) — Ctrl+C to stop")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nstopped")
