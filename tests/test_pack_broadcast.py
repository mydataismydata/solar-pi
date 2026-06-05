"""Pack-broadcast position decode — verified against REAL frames captured from the packs
(the same vectors the Android app's PackFrameTest uses)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solardash.pack_broadcast import PackBroadcast, crc_valid, parallel_position

# device …25:3D — 56-byte (2026 firmware), master (#1), byte[0]=0x01
FRAME_S = bytes.fromhex(
    "01510000ffff002e14ae00a600230064"
    "0b9d0cf40cdb0b950b920003059a0fa0"
    "0004008b000100000000020602020201"
    "0401000000008a37")
# device …25:44 — 56-byte, slave #2, byte[0]=0x02
FRAME_S2 = bytes.fromhex(
    "02510000ffff002e14cc004a00210064"
    "0bab0d030cf20b9f0b9b0003014e03e8"
    "00010002000000000000030603020301"
    "030200000000f685")
# device …56:72 — 64-byte legacy, byte[0]=0x02 (#2)
FRAME_E = bytes.fromhex(
    "02510000ffff0036152d009400500064"
    "0be30d400d390be70be20003032903e8"
    "000100020000000000000307030b0301"
    "0302000000005aa600000000000000a1")
# device …57:4C — 64-byte legacy master (#1), byte[0]=0x01
FRAME_N = bytes.fromhex(
    "01510000ffff003614e1ff7100530064"
    "0be50d120d090be80be20003068a07d0"
    "000200030000000000000210020c0103"
    "0202000000005aa60000000000006ca4")


class PackBroadcastTest(unittest.TestCase):
    def test_crc_valid_real_frames(self):
        self.assertTrue(crc_valid(FRAME_S, 56))
        self.assertTrue(crc_valid(FRAME_S2, 56))
        self.assertTrue(crc_valid(FRAME_E, 64))
        self.assertTrue(crc_valid(FRAME_N, 64))

    def test_position_from_byte0(self):
        self.assertEqual(parallel_position(FRAME_S), 1)   # 0x01 -> #1
        self.assertEqual(parallel_position(FRAME_S2), 2)  # 0x02 -> #2
        self.assertEqual(parallel_position(FRAME_E), 2)
        self.assertEqual(parallel_position(FRAME_N), 1)

    def test_crc_rejects_corruption(self):
        bad = bytearray(FRAME_E)
        bad[8] = (bad[8] + 1) & 0xFF  # change voltage, leave CRC
        self.assertFalse(crc_valid(bytes(bad), 64))

    def test_assembler_chunked_with_leading_junk(self):
        asm = PackBroadcast()
        self.assertIsNone(asm.feed(bytes.fromhex("dd0400")))  # not a broadcast header
        out = None
        i = 0
        while i < len(FRAME_S):
            end = min(i + 20, len(FRAME_S))  # 20-byte BLE-sized chunks
            r = asm.feed(FRAME_S[i:end])
            if r is not None:
                out = r
            i = end
        self.assertEqual(out, 1)

    def test_assembler_rejects_bad_crc(self):
        bad = bytearray(FRAME_E)
        bad[10] = (bad[10] + 5) & 0xFF  # corrupt current; CRC no longer matches
        self.assertIsNone(PackBroadcast().feed(bytes(bad)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
