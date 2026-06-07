"""Configured pack parallel positions: parsing + the poller stamping them onto samples."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solardash.config import _parse_bms_positions


class PositionParseTest(unittest.TestCase):
    def test_parse_basic(self):
        got = _parse_bms_positions("AA:C2:37:06:56:72=1, aa:c2:37:06:57:4c=2")
        self.assertEqual(got, {"AA:C2:37:06:56:72": 1, "AA:C2:37:06:57:4C": 2})

    def test_ignores_garbage_and_blanks(self):
        # '=' separator must survive the colons in a MAC; bad/blank entries are dropped.
        got = _parse_bms_positions("AA:BB:CC=3,,bad,DD=x,EE=4")
        self.assertEqual(got, {"AA:BB:CC": 3, "EE": 4})

    def test_empty(self):
        self.assertEqual(_parse_bms_positions(""), {})


class PollerStampTest(unittest.TestCase):
    def test_poller_stamps_configured_position(self):
        from solardash.bms_poller import BmsPoller
        p = BmsPoller([("AA:BB:CC:DD:EE:01", "p1")], positions={"aa:bb:cc:dd:ee:01": 2})
        self.assertEqual(p.positions, {"AA:BB:CC:DD:EE:01": 2})  # normalized upper


if __name__ == "__main__":
    unittest.main(verbosity=2)
