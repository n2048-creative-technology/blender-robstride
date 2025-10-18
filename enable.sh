#!/bin/bash
# enable.sh — Enable a RobStride motor (private protocol)
# Usage:
#   ./enable.sh <motor_id> [host_id]
# Examples:
#   ./enable.sh 127
#   ./enable.sh 0x7F 0x00AA
#
# Notes:
# - motor_id: node ID (0–127). Accepts decimal or 0x.. hex.
# - host_id:  16-bit master/host ID; default 0x00AA to match your frames.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <motor_id> [host_id]"
  exit 1
fi

motor_arg="$1"
host_arg="${2:-0x00AA}"   # default master/host ID = 0x00AA

# Normalize numeric inputs (dec or 0x.. hex -> decimal)
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

# Hex encodings (upper-case, zero-padded, no 0x)
MOTOR_HEX=$(printf "%02X" "$MOTOR_DEC")
HOST_HEX=$(printf "%04X" "$HOST_DEC")

# Extended IDs (per your working frames):
#  - Type 0x12 write (parameter write)
#  - Type 0x03 enable
EXT_ID_WRITE="12${HOST_HEX}${MOTOR_HEX}"
EXT_ID_ENABLE="03${HOST_HEX}${MOTOR_HEX}"

# Payloads from your original script:
#  - 1200AA7F#0570000001000000
#    -> write index 0x7005 (bytes 05 70 00 00) with value 0x00000001 (enable/runmode flag)
#  - 0300AA7F#0000000000000000
#    -> enable command frame
PAYLOAD_WRITE="0570000001000000"
PAYLOAD_ENABLE="0000000000000000"

echo "Enabling motor 0x${MOTOR_HEX} (host 0x${HOST_HEX})..."

echo "cansend can0 ${EXT_ID_WRITE}#${PAYLOAD_WRITE}"
cansend can0 "${EXT_ID_WRITE}#${PAYLOAD_WRITE}"

# A tiny delay is often helpful
sleep 0.02

echo "cansend can0 ${EXT_ID_ENABLE}#${PAYLOAD_ENABLE}"
cansend can0 "${EXT_ID_ENABLE}#${PAYLOAD_ENABLE}"

echo "[OK] Enable frames sent."
