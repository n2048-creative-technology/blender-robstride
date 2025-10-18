#!/usr/bin/env python3
"""
move.py — Send a RobStride target position (degrees) over CAN

Usage:
  sudo python3 move.py <motor_id> <degrees> [host_id]

Examples:
  sudo python3 move.py 127 90
  sudo python3 move.py 0x7F 45 0x0000   # custom master/host ID 0x0000

Notes:
- motor_id is the node ID (0–127).
- host_id (master/host) is 16-bit; default 0x00AA to match your frames.
- Sends a Type=0x12 (single-parameter write) frame with data:
    16 70 00 00 <float32 LE radians>
  (index 0x7016 in little-endian byte order = loc_ref)
"""

import argparse
import math
import os
import struct
import subprocess
import sys
import can

def parse_int(x: str) -> int:
    """Parse decimal or 0x.. hex."""
    return int(x, 0)

def build_ext_id(msg_type: int, host_id: int, motor_id: int) -> int:
    """
    Extended 29-bit ID layout from your working frames:
      [ mode(5) | host_id(16) | motor_id(8) ]
    """
    return ((msg_type & 0x1F) << 24) | ((host_id & 0xFFFF) << 8) | (motor_id & 0xFF)

def main():
    ap = argparse.ArgumentParser(description="Send RobStride target position (degrees) over CAN.")
    ap.add_argument("motor_id", help="Motor/node ID (dec or 0x..)")
    ap.add_argument("degrees",  help="Target position in degrees (float)")
    ap.add_argument("host_id",  nargs="?", default="0x00AA", help="Host/master ID (16-bit, default 0x00AA)")
    ap.add_argument("--iface",  default="can0", help='CAN interface (default "can0")')
    ap.add_argument("--bitrate", type=int, default=1_000_000, help="Bitrate (default 1000000)")
    ap.add_argument("--no-enable", action="store_true", help="Do not try to call ./enable.sh before sending")
    args = ap.parse_args()

    # Parse/validate inputs
    try:
        motor_id = parse_int(args.motor_id)
        host_id  = parse_int(args.host_id)
        degrees  = float(args.degrees)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    if not (0 <= motor_id <= 255):
        print("Error: motor_id must be 0..255")
        sys.exit(1)
    if not (0 <= host_id <= 0xFFFF):
        print("Error: host_id must be 0..65535 (16-bit)")
        sys.exit(1)

    radians = degrees * math.pi / 180.0
    rad_bytes = struct.pack("<f", radians)  # little-endian float32

    # Extended ID for Type=0x12 (single param write): 0x12{HOST16}{MOTOR8}
    arb_id = build_ext_id(0x12, host_id, motor_id)

    # Data payload: 16 70 00 00 <float32 LE radians>
    # (index 0x7016 in little endian)
    data = bytes([0x16, 0x70, 0x00, 0x00]) + rad_bytes

    # Optionally run enable.sh like your bash script
    if not args.no_enable and os.path.isfile("./enable.sh") and os.access("./enable.sh", os.X_OK):
        try:
            # Try passing motor_id; fall back to plain call if that fails
            subprocess.run(["./enable.sh", str(motor_id)], check=True)
        except subprocess.CalledProcessError:
            try:
                subprocess.run(["./enable.sh"], check=False)
            except Exception:
                pass

    # Open CAN and send
    try:
        bus = can.interface.Bus(channel=args.iface, bustype="socketcan", bitrate=args.bitrate)
    except Exception as e:
        print(f"[ERROR] Could not open {args.iface}: {e}")
        sys.exit(1)

    try:
        msg = can.Message(arbitration_id=arb_id, is_extended_id=True, data=data)
        print(f"Motor ID: 0x{motor_id:02X}  Host/Master ID: 0x{host_id:04X}")
        print(f"Target {degrees}° → {radians} rad → data {data.hex(' ').upper()}")
        print(f"Sending on {args.iface}: 0x{arb_id:08X}#{data.hex().upper()}")
        bus.send(msg)
        print("[OK] Frame sent.")
    finally:
        try:
            bus.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()
