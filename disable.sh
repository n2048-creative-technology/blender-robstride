#!/bin/bash
# disable.sh — Disable / stop a RobStride motor over CAN
#
# Usage:
#   ./disable.sh <motor_id> [host_id]
#
# Examples:
#   ./disable.sh 127
#   ./disable.sh 0x7F 0x00AA
#
# Notes:
# - motor_id: node ID (0–127). Accepts decimal or 0x.. hex.
# - host_id:  16-bit master/host ID; default 0x00AA to match other scripts.
# - Sends frame:
#     0x04{HOST16}{MOTOR8}#0000000000000000
#   which corresponds to Type=0x04 (STOP command) in the private protocol.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <motor_id> [host_id]"
  exit 1
fi

motor_arg="$1"
host_arg="${2:-0x00AA}"   # default host/master ID = 0x00AA

# Convert decimal or hex to decimal
to_dec() { printf "%d" "$1"; }

MOTOR_DEC="$(to_dec "$motor_arg")"
HOST_DEC="$(to_dec "$host_arg")"

# Range checks
if [ "$MOTOR_DEC" -lt 0 ] || [ "$MOTOR_DEC" -gt 255 ]; then
  echo "Error: motor_id must be 0..255"
  exit 1
fi
if [ "$HOST_DEC" -lt 0 ] || [ "$HOST_DEC" -gt 65535 ]; then
  echo "Error: host_id must be 0..65535 (16-bit)"
  exit 1
fi

# Convert to hex (uppercase, zero-padded)
MOTOR_HEX=$(printf "%02X" "$MOTOR_DEC")
HOST_HEX=$(printf "%04X" "$HOST_DEC")

# Build CAN ID for STOP command (Type 0x04)
EXT_ID="04${HOST_HEX}${MOTOR_HEX}"
PAYLOAD="0000000000000000"

echo "Disabling motor 0x${MOTOR_HEX} (host 0x${HOST_HEX})..."
echo "cansend can0 ${EXT_ID}#${PAYLOAD}"
cansend can0 "${EXT_ID}#${PAYLOAD}"
echo "[OK] Disable/stop frame sent."
