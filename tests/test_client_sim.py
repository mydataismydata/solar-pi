"""End-to-end: the async InverterClient reads from the offline simulator over a real
TCP socket, proving the whole request -> V5 -> Modbus -> decode path works as a unit.
Also round-trips the response-side codec used by the simulator.

Run from the project root:  python tests/test_client_sim.py
"""
import asyncio
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim.inverter_sim import DAYTIME_SCENE, InverterSimulator
from solardash.client import InverterClient
from solardash.codec import (
    modbus_holding_response,
    modbus_parse_holding,
    modbus_read_request,
    v5_decode,
    v5_decode_request,
    v5_encode,
    v5_encode_response,
)


class ResponseCodecRoundTripTest(unittest.TestCase):
    """The simulator's response-side framing must be readable by the client-side decoders."""

    def test_request_roundtrip(self):
        mb = modbus_read_request(1, 0x0100, 0x0F)
        frame = v5_encode(1234567890, 7, mb)
        self.assertEqual(v5_decode_request(frame), mb)

    def test_response_roundtrip(self):
        regs = [87, 532, 0xFF6A, 250]
        mb_resp = modbus_holding_response(1, regs)
        v5 = v5_encode_response(1234567890, 7, mb_resp)
        recovered = v5_decode(v5)
        self.assertIsNotNone(recovered)
        self.assertEqual(modbus_parse_holding(recovered, 1), regs)


class EndToEndSimTest(unittest.TestCase):
    def _read_once(self, scene=None):
        async def run():
            sim = InverterSimulator(scene=scene)
            server = await sim.start("127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            try:
                client = InverterClient("127.0.0.1", 1234567890, port=port)
                return await client.read()
            finally:
                server.close()
                await server.wait_closed()

        return asyncio.run(run())

    def test_daytime_read(self):
        reading = self._read_once()
        self.assertIsNotNone(reading, "client got no reading from the simulator")
        s = reading.status

        self.assertEqual(s.battery_soc, 87)
        self.assertTrue(math.isclose(s.battery_voltage, 53.2))
        self.assertTrue(math.isclose(s.battery_current, 15.0))   # negative raw -> charging (+)
        self.assertTrue(math.isclose(s.battery_temp, 25.0))
        self.assertTrue(math.isclose(s.output_frequency, 60.0))  # inverter output (off-grid scene)
        self.assertEqual(s.grid_voltage, 0.0)                    # no AC input (off-grid)

        # Derived power: PV1 (148.0*9.2) + PV2 (146.5*7.0) ~= 2387 W
        self.assertTrue(s.pv_power > 2300 and s.pv_power < 2450)
        self.assertEqual(s.load_total, 1180 + 990)               # both split-phase legs
        self.assertEqual(s.load_apparent_total, 1320 + 1100)
        self.assertFalse(s.has_fault)
        self.assertTrue(s.has_data)

        # Raw registers captured for every requested block (battery..load L2).
        self.assertIn(0x0101, reading.raw)
        self.assertIn(0x0234, reading.raw)

    def test_fault_scene(self):
        scene = dict(DAYTIME_SCENE)
        scene[0x0204] = 9  # PV over-voltage fault
        reading = self._read_once(scene=scene)
        self.assertIsNotNone(reading)
        self.assertEqual(reading.status.fault_codes, [9])
        self.assertTrue(reading.status.has_fault)


if __name__ == "__main__":
    unittest.main(verbosity=2)
