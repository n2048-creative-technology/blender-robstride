#!/usr/bin/env python3
"""
disable.py — Disable / stop a RobStride motor via CAN

Usage:
  sudo python3 disable.py <motor_id> [host_id]

Examples:
  sudo python3 disable.py 127
  sudo python3 disable.py 0x7F 0x00AA

Notes:
- motor_id: node ID (0–127). Accepts decimal or 0x.. hex.
- host_id:  16-bit master/host ID; default 0x00AA (matches other scripts).
- Sends one CAN frame:
      Type = 0x04 (STOP command)
      Data = 00 00 00 00 00 00 00 00
  → Frame ID format: 0x04{HOST16}{MOTOR8}
"""

import argparse
import sys
import can

def parse_int(x: str) -> int:
    """Parse either decimal or hex strings like 0x7F."""
    return int(x, 0)

def build_ext_id(msg_type: int, host_id: int, motor_id: int) -> int:
    """
    Extended 29-bit CAN ID layout (from RobStride docs):
      bits 28-24 : mode (5 bits)
      bits 23-8  : host/master ID (16 bits)
      bits 7-0   : motor node ID (8 bits)
    """
    return ((msg_type & 0x1F) << 24) | ((host_id & 0xFFFF) << 8) | (motor_id & 0xFF)

def main():
    parser = argparse.ArgumentParser(description="Disable / stop a RobStride motor over CAN.")
    parser.add_argument("motor_id", help="Motor/node ID (decimal or 0x..)")
    parser.add_argument("host_id", nargs="?", default="0x00AA", help="Host/master ID (default 0x00AA)")
    parser.add_argument("--iface", default="can0", help='CAN interface name (default "can0")')
    parser.add_argument("--bitrate", type=int, default=1_000_000, help="CAN bitrate (default 1 Mbps)")
    args = parser.parse_args()

    # --- parse and validate ---
    try:
        motor_id = parse_int(args.motor_id)
        host_id  = parse_int(args.host_id)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    if not (0 <= motor_id <= 255):
        print("Error: motor_id must be 0–255")
        sys.exit(1)
    if not (0 <= host_id <= 0xFFFF):
        print("Error: host_id must be 0–65535 (16-bit)")
        sys.exit(1)

    # --- build CAN frame ---
    msg_type = 0x04  # STOP command
    arb_id = build_ext_id(msg_type, host_id, motor_id)
    data = bytes(8)  # 8 zero bytes

    try:
        bus = can.interface.Bus(channel=args.iface, bustype="socketcan", bitrate=args.bitrate)
    except Exception as e:
        print(f"[ERROR] Could not open {args.iface}: {e}")
        sys.exit(1)

    try:
        print(f"Disabling motor 0x{motor_id:02X} (host 0x{host_id:04X}) on {args.iface} @ {args.bitrate} bps")
        print(f" -> 0x{arb_id:08X}#{data.hex().upper()}")
        msg = can.Message(arbitration_id=arb_id, is_extended_id=True, data=data)
        bus.send(msg)
        print("[OK] Disable/STOP frame sent.")
    finally:
        try:
            bus.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()
