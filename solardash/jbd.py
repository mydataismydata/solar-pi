"""JBD / Xiaoxiang BMS protocol — the ECO-LFP48100 packs speak this over BLE (service 0xFF00,
notify 0xFF01, write 0xFF02). Parses the 0x03 basic-info and 0x04 cell-voltage responses, and
reassembles frames split across BLE notifications.

Validated byte-for-byte against real frames captured from the packs (see tests/test_jbd.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

NOTIFY_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

# Commands written to 0xFF02:  DD A5 <cmd> 00 <crcHi> <crcLo> 77
CMD_BASIC_INFO = bytes.fromhex("dda50300fffd77")  # 0x03 — voltage/current/SOC/capacity/temps
CMD_CELL_VOLTS = bytes.fromhex("dda50400fffc77")  # 0x04 — per-cell voltages

CMD_BASIC = 0x03
CMD_CELLS = 0x04


def _u16(d: bytes, i: int) -> int:
    return (d[i] << 8) | d[i + 1]


def _i16(d: bytes, i: int) -> int:
    v = _u16(d, i)
    return v - 0x10000 if v & 0x8000 else v


def checksum(status_len_data: bytes) -> int:
    """JBD response checksum: two's complement of sum(status + len + data), 16-bit."""
    return (0x10000 - sum(status_len_data)) & 0xFFFF


def parse_frame(frame: bytes) -> Optional[Tuple[int, bytes]]:
    """Validate a `DD <cmd> <status> <len> <data..> <crcHi> <crcLo> 77` response.
    Returns (cmd, data) or None on any malformed / bad-status / bad-CRC frame."""
    if len(frame) < 7 or frame[0] != 0xDD or frame[-1] != 0x77:
        return None
    cmd, status, length = frame[1], frame[2], frame[3]
    if status != 0x00:
        return None
    data_end = 4 + length
    if len(frame) < data_end + 3:
        return None
    got = (frame[data_end] << 8) | frame[data_end + 1]
    if got != checksum(frame[2:data_end]):
        return None
    return cmd, frame[4:data_end]


class JbdAssembler:
    """Reassembles JBD frames from BLE notification chunks (frames span multiple notifications)."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> List[Tuple[int, bytes]]:
        out: List[Tuple[int, bytes]] = []
        self._buf += chunk
        while True:
            start = self._buf.find(0xDD)
            if start < 0:
                self._buf.clear()
                break
            if start > 0:
                del self._buf[:start]
            if len(self._buf) < 4:
                break
            total = 4 + self._buf[3] + 3  # header(4) + data(len) + crc(2) + tail(1)
            if len(self._buf) < total:
                break
            frame = bytes(self._buf[:total])
            del self._buf[:total]
            parsed = parse_frame(frame)
            if parsed:
                out.append(parsed)
            elif frame:
                # not a valid frame at this 0xDD — skip the false start byte and resync
                self._buf[:0] = frame[1:]
                if self._buf and self._buf[0] == 0xDD:
                    del self._buf[0]
        return out


@dataclass
class PackInfo:
    """Decoded JBD 0x03 basic info for one pack."""

    voltage: float          # V
    current: float          # A (+ charge / - discharge)
    residual_ah: float      # remaining capacity
    nominal_ah: float       # rated/full capacity
    soc: int                # %
    cycles: int
    cell_count: int
    temps_c: List[float]
    protection: int         # protection-status bitmask (0 = OK)

    @property
    def power(self) -> float:
        return self.voltage * self.current

    @property
    def has_fault(self) -> bool:
        return self.protection != 0


def parse_basic_info(data: bytes) -> PackInfo:
    ntc = data[22]
    temps = [round((_u16(data, 23 + 2 * i) - 2731) / 10.0, 1) for i in range(ntc)]
    return PackInfo(
        voltage=_u16(data, 0) / 100.0,
        current=_i16(data, 2) / 100.0,
        residual_ah=_u16(data, 4) / 100.0,
        nominal_ah=_u16(data, 6) / 100.0,
        cycles=_u16(data, 8),
        protection=_u16(data, 16),
        soc=data[19],
        cell_count=data[21],
        temps_c=temps,
    )


def parse_cell_voltages(data: bytes) -> List[float]:
    """16-bit big-endian millivolts per cell -> volts."""
    return [round(_u16(data, 2 * i) / 1000.0, 3) for i in range(len(data) // 2)]
