#!/usr/bin/env python3
"""
enable.py — Enable a RobStride motor (private CAN protocol)

Usage:
  sudo python3 enable.py <motor_id> [host_id]

Examples:
  sudo python3 enable.py 127
  sudo python3 enable.py 0x7F 0x00AA

Notes:
- motor_id: node ID (0–127), decimal or 0x.. hex.
- host_id:  16-bit master/host ID; default 0x00AA (matches your frames).
- Sends two frames:
    1) Type=0x12 (single param write)  -> data: 05 70 00 00 01 00 00 00
    2) Type=0x03 (enable command)      -> data: 00 00 00 00 00 00 00 00
"""

import argparse
import sys
import time
import can

def parse_int(x: str) -> int:
    return int(x, 0)

def build_ext_id(msg_type: int, host_id: int, motor_id: int) -> int:
    # 29-bit ID layout: [ mode(5) | host_id(16) | motor_id(8) ]
    return ((msg_type & 0x1F) << 24) | ((host_id & 0xFFFF) << 8) | (motor_id & 0xFF)

def main():
    ap = argparse.ArgumentParser(description="Enable a RobStride motor via CAN.")
    ap.add_argument("motor_id", help="Motor/node ID (dec or 0x..)")
    ap.add_argument("host_id", nargs="?", default="0x00AA", help="Host/master ID (default 0x00AA)")
    ap.add_argument("--iface", default="can0", help='CAN interface (default "can0")')
    ap.add_argument("--bitrate", type=int, default=1_000_000, help="Bitrate (default 1000000)")
    ap.add_argument("--delay", type=float, default=0.02, help="Delay between frames in seconds (default 0.02)")
    args = ap.parse_args()

    try:
        motor_id = parse_int(args.motor_id)
        host_id  = parse_int(args.host_id)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    if not (0 <= motor_id <= 255):
        print("Error: motor_id must be 0..255")
        sys.exit(1)
    if not (0 <= host_id <= 0xFFFF):
        print("Error: host_id must be 0..65535")
        sys.exit(1)

    # Frame 1: Type 0x12 (write), payload 05 70 00 00 01 00 00 00
    arb_write = build_ext_id(0x12, host_id, motor_id)
    data_write = bytes.fromhex("05 70 00 00 01 00 00 00")

    # Frame 2: Type 0x03 (enable), payload all zeros
    arb_enable = build_ext_id(0x03, host_id, motor_id)
    data_enable = bytes(8)

    try:
        bus = can.interface.Bus(channel=args.iface, bustype="socketcan", bitrate=args.bitrate)
    except Exception as e:
        print(f"[ERROR] Could not open {args.iface}: {e}")
        sys.exit(1)

    try:
        print(f"Enabling motor 0x{motor_id:02X} (host 0x{host_id:04X}) on {args.iface} @ {args.bitrate} bps")

        # Send write frame
        msg1 = can.Message(arbitration_id=arb_write, is_extended_id=True, data=data_write)
        print(f" -> 0x{arb_write:08X}#{data_write.hex().upper()}")
        bus.send(msg1)

        time.sleep(args.delay)

        # Send enable frame
        msg2 = can.Message(arbitration_id=arb_enable, is_extended_id=True, data=data_enable)
        print(f" -> 0x{arb_enable:08X}#{data_enable.hex().upper()}")
        bus.send(msg2)

        print("[OK] Enable frames sent.")
    finally:
        try:
            bus.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()
