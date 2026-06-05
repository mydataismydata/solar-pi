"""JBD/Xiaoxiang BMS parser tests, pinned to REAL frames captured from pack ECO-LFP48100-065672
over BLE (including the exact multi-notification fragmentation seen on the wire).
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solardash import jbd

# Real BLE notification chunks captured from the pack:
CELLS_CHUNKS = [
    bytes.fromhex("dd0400200d240d250d220d210d220d210d230d25"),
    bytes.fromhex("0d220d220d210d220d230d220d240d26fce377"),
]
BASIC_CHUNKS = [
    bytes.fromhex("dd0300231505042a1c4b27100002332b00000000"),
    bytes.fromhex("000014480310060ba90bb50ba30ba10ba30ba5f9"),
    bytes.fromhex("f677"),
]


class FrameTest(unittest.TestCase):
    def _assemble(self, chunks):
        asm = jbd.JbdAssembler()
        frames = []
        for c in chunks:
            frames += asm.feed(c)
        return frames

    def test_cell_voltages(self):
        frames = self._assemble(CELLS_CHUNKS)
        self.assertEqual(len(frames), 1)
        cmd, data = frames[0]
        self.assertEqual(cmd, jbd.CMD_CELLS)
        cells = jbd.parse_cell_voltages(data)
        self.assertEqual(len(cells), 16)
        self.assertTrue(math.isclose(cells[0], 3.364))
        self.assertTrue(math.isclose(cells[-1], 3.366))
        self.assertTrue(math.isclose(min(cells), 3.361))
        self.assertTrue(math.isclose(max(cells), 3.366))
        self.assertTrue(math.isclose(max(cells) - min(cells), 0.005, abs_tol=1e-9))

    def test_basic_info(self):
        frames = self._assemble(BASIC_CHUNKS)
        self.assertEqual(len(frames), 1)
        cmd, data = frames[0]
        self.assertEqual(cmd, jbd.CMD_BASIC)
        p = jbd.parse_basic_info(data)
        self.assertTrue(math.isclose(p.voltage, 53.81))
        self.assertTrue(math.isclose(p.current, 10.66))   # + = charging
        self.assertTrue(math.isclose(p.residual_ah, 72.43))
        self.assertTrue(math.isclose(p.nominal_ah, 100.00))
        self.assertEqual(p.soc, 72)
        self.assertEqual(p.cycles, 2)
        self.assertEqual(p.cell_count, 16)
        self.assertEqual(p.protection, 0)
        self.assertFalse(p.has_fault)
        self.assertEqual(len(p.temps_c), 6)
        self.assertTrue(math.isclose(max(p.temps_c), 26.6))
        self.assertTrue(math.isclose(min(p.temps_c), 24.6))
        self.assertTrue(math.isclose(p.power, 53.81 * 10.66))

    def test_interleaved_stream(self):
        # both responses arriving back-to-back through one assembler
        asm = jbd.JbdAssembler()
        frames = []
        for c in CELLS_CHUNKS + BASIC_CHUNKS:
            frames += asm.feed(c)
        self.assertEqual(sorted(f[0] for f in frames), [jbd.CMD_BASIC, jbd.CMD_CELLS])

    def test_rejects_bad_crc(self):
        bad = bytearray(b"".join(CELLS_CHUNKS))
        bad[-3] ^= 0xFF  # corrupt a CRC byte
        self.assertIsNone(jbd.parse_frame(bytes(bad)))

    def test_command_frames_well_formed(self):
        # our outbound request frames must carry a valid JBD request checksum + tail
        for cmd in (jbd.CMD_BASIC_INFO, jbd.CMD_CELL_VOLTS):
            self.assertEqual(cmd[0], 0xDD)
            self.assertEqual(cmd[1], 0xA5)
            self.assertEqual(cmd[-1], 0x77)
            self.assertEqual(((cmd[-3] << 8) | cmd[-2]), jbd.checksum(cmd[2:-3]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
