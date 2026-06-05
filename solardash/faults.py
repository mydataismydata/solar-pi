"""Fault-code catalog loader — maps SRNE/Eco-Worthy fault codes to human text.

Ported from the Android app's FaultCatalog + assets/faults/ecoworthy.json.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

_ASSET = os.path.join(os.path.dirname(__file__), "assets", "faults", "ecoworthy.json")


class FaultCatalog:
    def __init__(self, codes: Dict[int, str], name: str = ""):
        self.codes = codes
        self.name = name

    @classmethod
    def load(cls, path: str = _ASSET) -> "FaultCatalog":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        codes = {int(k): v for k, v in data.get("codes", {}).items()}
        return cls(codes, data.get("name", ""))

    def describe(self, code: int) -> str:
        return self.codes.get(code, f"Unknown fault ({code})")

    def annotate(self, codes: List[int]) -> List[Dict[str, object]]:
        """Turn raw codes into [{code, text}] for the dashboard."""
        return [{"code": c, "text": self.describe(c)} for c in codes]
