"""ECO-LFP48100 unsolicited pack broadcast — extract each pack's position in the parallel group.

Ported from the Android app's PackFrame.kt and validated against the same real frames (see
tests/test_pack_broadcast.py). While connected, each pack emits an unsolicited broadcast on the
notify characteristic (56 bytes on 2026 firmware, 64 bytes legacy). Byte[0] is a single-bit
position mask: 0x01=#1, 0x02=#2, 0x04=#3, 0x08=#4 (#1 is the master). The broadcast has no 0xDD
header, so we scan for the 0x51,00,00,FF,FF signature (it sits at byte[1], one past the position
byte) and accept the first candidate length whose trailing CRC-16/Modbus (little-endian) validates.
"""
from __future__ import annotations

from typing import Optional

LENGTHS = (56, 64)  # shortest first, so a 56B frame isn't mistaken for a 64B one
_TYPE = 0x51
_MAX_BUFFER = 256


def header_at(d, i: int) -> bool:
    """True if a broadcast header signature begins at index [i] (byte[i+1] is the 0x51 marker)."""
    return (i + 6 <= len(d)
            and d[i + 1] == _TYPE
            and d[i + 2] == 0 and d[i + 3] == 0
            and d[i + 4] == 0xFF and d[i + 5] == 0xFF)


def crc16_modbus(d, end: int) -> int:
    crc = 0xFFFF
    for i in range(end):
        crc ^= d[i]
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else (crc >> 1)
    return crc


def crc_valid(frame, length: int) -> bool:
    """CRC over [0, length-2); little-endian tail at [length-2 .. length-1]."""
    if length < 4 or len(frame) < length:
        return False
    got = frame[length - 2] | (frame[length - 1] << 8)
    return got == crc16_modbus(frame, length - 2)


def parallel_position(frame) -> int:
    """1-indexed position from byte[0]'s lowest set bit (0x01->1, 0x02->2, ...); 0 if unknown."""
    pos = frame[0]
    return (pos & -pos).bit_length() if pos else 0


class PackBroadcast:
    """Scans the BLE notify stream for a CRC-valid pack broadcast; returns the parallel position.

    feed(chunk) returns the position (1..) the first time a valid broadcast completes, else None.
    Safe to feed the same stream that also carries the 0xDD JBD command responses — those don't
    match the header signature and are scanned past.
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> Optional[int]:
        self._buf += chunk
        if len(self._buf) > _MAX_BUFFER:
            del self._buf[:-_MAX_BUFFER]
        while True:
            idx = -1
            i = 0
            n = len(self._buf)
            while i + 6 <= n:
                if header_at(self._buf, i):
                    idx = i
                    break
                i += 1
            if idx < 0:
                return None  # no header yet; keep buffering
            if idx:
                del self._buf[:idx]  # drop bytes before the header
            for length in LENGTHS:
                if len(self._buf) < length:
                    continue
                frame = bytes(self._buf[:length])
                if crc_valid(frame, length):
                    del self._buf[:length]
                    return parallel_position(frame)
            if len(self._buf) < LENGTHS[-1]:
                return None  # need more bytes before we can test the longest candidate
            del self._buf[0]  # false header — step past and rescan
