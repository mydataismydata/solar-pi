#!/usr/bin/env python3
"""Quick BLE probe for the JBD/Xiaoxiang BMS: list services, enable notifications on the
vendor notify characteristic, send JBD basic-info + cell-voltage requests, and dump raw
frames to confirm the protocol + characteristics.

    python deploy/ble_probe.py [MAC] [NOTIFY_UUID] [WRITE_UUID]
"""
import asyncio
import sys

from bleak import BleakClient

ADDR = sys.argv[1] if len(sys.argv) > 1 else "A4:C1:37:11:51:44"
NOTIFY = (sys.argv[2] if len(sys.argv) > 2 else "ff05").lower()
WRITE = (sys.argv[3] if len(sys.argv) > 3 else "ff06").lower()


def short(uuid):
    return uuid.lower().replace("0000", "").split("-")[0]


def cb(_, data):
    b = bytes(data)
    tag = ""
    if len(b) > 1 and b[1] == 0x51:
        tag = "  <- pack broadcast (0x51)"
    elif len(b) > 1 and b[0] == 0xDD:
        tag = f"  <- JBD reply (cmd 0x{b[1]:02x})"
    print(f"  {len(b):3d}B  {b.hex()}{tag}")


async def main():
    print(f"connecting to {ADDR} ...")
    async with BleakClient(ADDR, timeout=25) as c:
        print("connected:", c.is_connected, "\nservices / characteristics:")
        notify_uuid = write_uuid = None
        for s in c.services:
            print(f"  service {short(s.uuid)}")
            for ch in s.characteristics:
                print(f"    char {short(ch.uuid)}  {list(ch.properties)}")
                if short(ch.uuid) == NOTIFY:
                    notify_uuid = ch.uuid
                if short(ch.uuid) == WRITE:
                    write_uuid = ch.uuid
        if not notify_uuid:
            print(f"notify char {NOTIFY} not found; aborting")
            return
        await c.start_notify(notify_uuid, cb)
        print(f"notify on {NOTIFY}; sending JBD 0x04 + 0x03 to {WRITE}, listening 12s...")
        if write_uuid:
            try:
                await c.write_gatt_char(write_uuid, bytes.fromhex("dda50400fffc77"), response=False)
                await asyncio.sleep(1.5)
                await c.write_gatt_char(write_uuid, bytes.fromhex("dda50300fffd77"), response=False)
            except Exception as e:
                print("write error:", e)
        await asyncio.sleep(12)
        await c.stop_notify(notify_uuid)


if __name__ == "__main__":
    asyncio.run(main())
