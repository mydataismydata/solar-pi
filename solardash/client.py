"""Async TCP client for the SRNE inverter via its Solarman WiFi dongle (port 8899).

One read() opens a socket, walks SrneInverter.BLOCKS, and returns decoded + raw
registers. Async port of the Android app's InverterClient.kt, including its
slave-address fallback (1 then 0xFF) and per-block tolerance of dropped replies.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional

from . import inverter
from .codec import modbus_parse_holding, modbus_read_request, v5_decode, v5_encode

CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 5.0


@dataclass
class InverterReading:
    """Decoded status plus the raw registers (handy for verifying the decode)."""

    status: inverter.InverterStatus
    raw: Dict[int, int]


class InverterClient:
    def __init__(
        self,
        ip: str,
        serial: int,
        port: int = 8899,
        connect_timeout: float = CONNECT_TIMEOUT_S,
        read_timeout: float = READ_TIMEOUT_S,
    ):
        self.ip = ip
        self.serial = serial
        self.port = port
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self._seq = 0

    def _next_seq(self) -> int:
        self._seq = (self._seq + 1) & 0xFF
        return self._seq

    async def read(self) -> Optional[InverterReading]:
        """Open a socket, read all register blocks, return decoded+raw or None on failure."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), self.connect_timeout
            )
        except (OSError, asyncio.TimeoutError):
            return None
        try:
            # SRNE Modbus address is usually 1; some firmware uses the universal 0xFF.
            for slave in (1, 0xFF):
                raw: Dict[int, int] = {}
                for start, count in inverter.BLOCKS:
                    regs = await self._read_block(reader, writer, start, count, slave)
                    if regs is not None:
                        for i, value in enumerate(regs):
                            raw[start + i] = value
                if raw:
                    return InverterReading(inverter.decode(raw), raw)
            return None
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _read_block(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, start: int, count: int, slave: int
    ) -> Optional[List[int]]:
        request = v5_encode(self.serial, self._next_seq(), modbus_read_request(slave, start, count))
        writer.write(request)
        await writer.drain()
        frame = await self._read_v5_frame(reader)
        if frame is None:
            return None
        modbus = v5_decode(frame)
        if modbus is None:
            return None
        return modbus_parse_holding(modbus, slave)

    async def _read_v5_frame(self, reader: asyncio.StreamReader) -> Optional[bytes]:
        """Read exactly one V5 frame: the 3-byte header gives total = 13 + payloadLen."""
        try:
            head = await asyncio.wait_for(reader.readexactly(3), self.read_timeout)
            if head[0] != 0xA5:
                return None
            payload_len = head[1] | (head[2] << 8)
            remaining = 13 + payload_len - 3
            rest = await asyncio.wait_for(reader.readexactly(remaining), self.read_timeout)
            return head + rest
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError):
            return None
